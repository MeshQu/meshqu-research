"""
10-record dry run of the Inspect-AI eval loop against staging.

Fetches 10 real OCDS records from UK Contracts Finder, drives them
through the full pipeline (substrate → agent → MeshQu → trace /
sidecar / manifest), AND captures Grafana screenshots + verifies
dashboard mirror at the OBS-205/206 cadence (checkpoint every 2
records during dry-run).

Differences from `smoke_eval_loop.py`:
  - **Real fetch** from the live Contracts Finder OCDS Search endpoint
    (not hand-crafted fixtures). Surfaces substrate variability the
    smoke fixtures couldn't.
  - **10 records**, configurable via --limit.
  - **No expected-verdicts table** — these are real records, we don't
    know up-front what they'll produce. The script prints what landed.
  - **RunController wired** — fires `run_start` (dashboard mirror +
    initial screenshot), `after_record` per the dry-run cadence
    (every 2 records), and `run_end` (final screenshot). Validates
    the full observability stack before the 300-record full run.

Required env vars:
   OPENAI_API_KEY
   MESHQU_API_URL
   MESHQU_EXPERIMENT_PROCUREMENT_API_KEY
   MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID
   MESHQU_RUNNER_GRAFANA_URL                 (staging Grafana base URL)
   MESHQU_RUNNER_GRAFANA_USER                (defaults to "admin")
   MESHQU_RUNNER_GRAFANA_PASSWORD            (staging Grafana password)

Optional:
   --limit N                                 (default 10)
   --since YYYY-MM-DD                        (default: 30 days ago)
   --until YYYY-MM-DD                        (default: today)
   --skip-mirror-check                       (bypass dashboard drift gate
                                              when you've intentionally
                                              edited the dashboard in
                                              Grafana and not yet
                                              re-committed the mirror JSON)

Exit codes:
   0  all records produced receipts, no orphans, no parse failures,
      mirror passed, all screenshots captured
   1  partial success — see anomalies.jsonl + the printed table
   2  preflight failed (missing env vars, mirror drift without override)

Usage:
   cd procurement-decisions/runner
   doppler run --project shared --config stg --command '
     OPENAI_API_KEY="$OPENAI_API_KEY" \\
     MESHQU_API_URL=https://meshqu-api-staging.up.railway.app \\
     MESHQU_EXPERIMENT_PROCUREMENT_API_KEY=mqu_... \\
     MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID=243f19a5-... \\
     MESHQU_RUNNER_GRAFANA_URL=https://grafana-meshqu-staging.up.railway.app \\
     MESHQU_RUNNER_GRAFANA_USER=admin \\
     MESHQU_RUNNER_GRAFANA_PASSWORD=... \\
       python3 scripts/dry_run_eval_loop.py
   '
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from meshqu_runner.agent import Agent, load_system_prompt  # noqa: E402
from meshqu_runner.audit import AuditWriter  # noqa: E402
from meshqu_runner.config import RunnerConfig  # noqa: E402
from meshqu_runner.dashboard_mirror import MirrorError  # noqa: E402
from meshqu_runner.eval_loop import (  # noqa: E402
    EvalLoopConfig,
    make_run_directory,
    run_eval_loop,
)
from meshqu_runner.meshqu_client import MeshQuClient  # noqa: E402
from meshqu_runner.runner import RunController  # noqa: E402
from meshqu_runner.substrate import (  # noqa: E402
    ADAPTER_VERSION,
    CONTRACTS_FINDER_OCDS_URL,
    fetch_ocds_records,
    ocds_to_decision_context,
    provenance_summary,
)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _preflight() -> dict[str, str]:
    """Validate every required env var. Exit 2 on missing — never partial."""
    required = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "MESHQU_API_URL": os.environ.get("MESHQU_API_URL", ""),
        "MESHQU_EXPERIMENT_PROCUREMENT_API_KEY": os.environ.get(
            "MESHQU_EXPERIMENT_PROCUREMENT_API_KEY", ""
        ),
        "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID": os.environ.get(
            "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID", ""
        ),
        "MESHQU_RUNNER_GRAFANA_URL": os.environ.get("MESHQU_RUNNER_GRAFANA_URL", ""),
        "MESHQU_RUNNER_GRAFANA_PASSWORD": os.environ.get(
            "MESHQU_RUNNER_GRAFANA_PASSWORD", ""
        ),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"error: missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)
    return required


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 scripts/dry_run_eval_loop.py",
        description="10-record dry run against the live Contracts Finder OCDS "
        "feed + staging MeshQu + Grafana screenshot capture.",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Records to process (default: 10)"
    )
    today = date.today()
    parser.add_argument(
        "--since",
        type=lambda s: date.fromisoformat(s),
        default=today - timedelta(days=30),
        help="publishedFrom (YYYY-MM-DD; default: 30 days ago)",
    )
    parser.add_argument(
        "--until",
        type=lambda s: date.fromisoformat(s),
        default=today,
        help="publishedTo (YYYY-MM-DD; default: today)",
    )
    parser.add_argument(
        "--skip-mirror-check",
        action="store_true",
        help="Bypass the dashboard drift gate (use when you've intentionally "
        "edited the dashboard in Grafana but not yet re-committed the mirror JSON).",
    )
    parser.add_argument(
        "--feed-url",
        default=CONTRACTS_FINDER_OCDS_URL,
        help="OCDS feed URL (default: live Contracts Finder).",
    )
    return parser.parse_args(list(argv))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _aggregate_provenance(summaries: Iterable[dict[str, int]]) -> dict[str, int]:
    total: Counter[str] = Counter()
    for s in summaries:
        total.update(s)
    return dict(total)


def _print_summary(summary, provenance_total: dict[str, int]) -> None:
    print()
    print("=== dry-run results ===")
    print(f"  run_id                          : {summary.run_id}")
    print(f"  records_attempted               : {summary.records_attempted}")
    print(f"  records_with_receipt            : {summary.records_with_receipt}")
    print(f"  records_with_agent_parse_failure: {summary.records_with_agent_parse_failure}")
    print(f"  records_with_agent_call_error   : {summary.records_with_agent_call_error}")
    print(f"  records_with_meshqu_error       : {summary.records_with_meshqu_error}")
    print(f"  records_with_orphaned_receipt   : {summary.records_with_orphaned_receipt}")
    print(f"  policy_snapshot_id              : {summary.policy_snapshot_id}")
    print()
    print("  substrate provenance (sum across all records, all fields):")
    for status, count in sorted(provenance_total.items()):
        print(f"    {status:<14}: {count}")
    print()
    print(f"  {'idx':<4} {'ocid':<45} {'agent':<6} {'meshqu':<6} {'agreement':<10} decision_id")
    print(f"  {'-' * 4} {'-' * 45} {'-' * 6} {'-' * 6} {'-' * 10} {'-' * 36}")
    for o in summary.outcomes:
        print(
            f"  {o.record_index:<4} "
            f"{(o.ocid or '?')[:45]:<45} "
            f"{(o.agent_verdict or '-'):<6} "
            f"{(o.meshqu_verdict or '-'):<6} "
            f"{str(o.agreement):<10} "
            f"{o.decision_id or '-'}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args(sys.argv[1:])
    env = _preflight()

    results_root = RUNNER_DIR.parent / "results"
    run_id = f"dry-run-{uuid.uuid4()}"
    run_dir, _ = make_run_directory(results_root, run_id=run_id)

    print(f"dry-run run_dir: {run_dir}")
    print(f"  OCDS window  : {args.since} → {args.until}")
    print(f"  records      : up to {args.limit}")
    print(f"  meshqu       : {env['MESHQU_API_URL']}")
    print(f"  grafana      : {env['MESHQU_RUNNER_GRAFANA_URL']}")
    print()

    # Fetch records first — if this fails, we abort BEFORE creating a
    # manifest so the run directory stays empty + recoverable.
    print(f"fetching OCDS records …")
    try:
        records = fetch_ocds_records(
            feed_url=args.feed_url,
            since=args.since,
            until=args.until,
            limit=args.limit,
        )
    except Exception as err:  # noqa: BLE001
        print(f"error: OCDS fetch failed: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
    print(f"  → fetched {len(records)} records")
    if not records:
        print("  no records in window — try a wider --since/--until")
        return 1
    print()

    # RunnerConfig pulls Grafana env vars via from_env(); pin results_dir
    # explicitly so screenshots/audit land under our run-specific tree.
    os.environ["MESHQU_RUNNER_RESULTS_DIR"] = str(results_root)
    runner_config = RunnerConfig.from_env()

    audit = AuditWriter(run_dir, run_id)
    controller = RunController(
        config=runner_config,
        run_phase="dry-run",
        run_id=run_id,
        total_records=len(records),
    )

    # Mirror check + run-start screenshot. MirrorError = dashboard drift.
    if args.skip_mirror_check:
        print("⚠  --skip-mirror-check: bypassing dashboard drift gate")
        # Fire run-start screenshot without the mirror via capturer directly.
        # (RunController.run_start always does both; we bypass it here.)
        # Capturer needs render_height — read from committed dashboard JSON.
        import json as _json

        with runner_config.committed_dashboard_path.open("r") as fp:
            dashboard_obj = _json.load(fp)
        controller._capturer.render_height = controller._capturer.compute_render_height(
            dashboard_obj
        )
        controller._capturer.capture(
            run_phase="dry-run", event="run-start", from_param="now-1h"
        )
    else:
        try:
            mirror_result, _ = controller.run_start()
            print(
                f"  mirror OK: source={mirror_result.source_of_truth} "
                f"sha={mirror_result.canonical_sha256[:12]}…"
            )
        except MirrorError as err:
            print(f"error: dashboard mirror drift — {err}", file=sys.stderr)
            print(
                "       refresh the committed JSON at "
                f"{runner_config.committed_dashboard_path} or re-run with "
                "--skip-mirror-check.",
                file=sys.stderr,
            )
            return 2

    # Bind the eval-loop's after_record callback to the controller so
    # checkpoint screenshots fire every 2 records (dry-run cadence).
    def _on_after(record_index: int, _outcome) -> None:
        controller.after_record(record_index)

    config = EvalLoopConfig(
        run_id=run_id,
        run_phase="dry-run",
        repo_dir=RUNNER_DIR.parent.parent,  # meshqu-research root
        run_dir=run_dir,
        meshqu_api_url=env["MESHQU_API_URL"],
        meshqu_api_key=env["MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"],
        meshqu_tenant_id=env["MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"],
        meshqu_tenant_label="experiment-procurement",
        agent_api_key=env["OPENAI_API_KEY"],
        substrate_adapter_version=ADAPTER_VERSION,
        substrate_source={
            "feed": args.feed_url,
            "published_from": args.since.isoformat(),
            "published_to": args.until.isoformat(),
            "record_count": len(records),
        },
        record_target_count=len(records),
        policy_code="procurement-decisions-v1",
        inter_request_pause_seconds=0.25,
    )

    # Track per-record provenance summaries so we can aggregate at end.
    provenance_summaries: list[dict[str, int]] = []

    def _provenance_summary_capturing(notes):
        s = provenance_summary(notes)
        provenance_summaries.append(s)
        return s

    def _progress(record_index: int, outcome) -> None:
        print(
            f"  [{record_index + 1:>2}/{len(records)}] "
            f"ocid={(outcome.ocid or '?')[:45]:<45} "
            f"outcome={outcome.outcome:<18} "
            f"agent={outcome.agent_verdict or '-':<6} "
            f"meshqu={outcome.meshqu_verdict or '-':<6}"
        )
        _on_after(record_index, outcome)

    summary = run_eval_loop(
        config=config,
        records=records,
        substrate_callable=ocds_to_decision_context,
        provenance_summary_callable=_provenance_summary_capturing,
        audit_writer=audit,
        meshqu_client=MeshQuClient(
            base_url=env["MESHQU_API_URL"],
            api_key=env["MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"],
            tenant_id=env["MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"],
        ),
        agent=Agent(api_key=env["OPENAI_API_KEY"], system_prompt=load_system_prompt()),
        on_after_record=_progress,
    )

    # Final screenshot via the controller.
    controller.run_end()

    _print_summary(summary, _aggregate_provenance(provenance_summaries))

    # Exit non-zero on any partial failure mode.
    if (
        summary.records_with_receipt != len(records)
        or summary.records_with_orphaned_receipt > 0
    ):
        print()
        print("FAIL: not every record produced a receipt — see anomalies.jsonl")
        return 1

    print()
    print(f"OK: {summary.records_with_receipt}/{len(records)} receipts in {run_dir}")
    print(
        f"    screenshots:   {runner_config.screenshots_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
