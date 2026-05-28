#!/usr/bin/env python3
"""Live dry-run driver — E2-008 Stage C, second validation gate.

Reads `runner/tests/fixtures/dry_run_records.json` (30 deterministic
records, stratified per E2-008 §1), wires the LIVE Agent + MeshQuClient
against `.env.live` credentials, and invokes:

  1. `run_multi_pass(...)` for the 5-level main grid (150 receipts)
  2. `run_permuted_diagnostic(...)` against the SAME 30-record fixture,
     which natively filters via `is_in_permuted_subset(ocid)` and runs
     against the (30 ∩ 14)-record intersection. Expected: ~1–2 receipts.

This is the canonical PRODUCTION driver shape — unlike smoke_live.py
which deliberately bypasses the 5% subset filter for the worked-example
pilot, the dry-run uses the standard filter so the diagnostic
population is the natural intersection of (dry-run records ∩ corpus
subset).

Total budget: ~151–152 LIVE OpenAI calls + matching MeshQu
/v1/decisions/record calls. Realised cost is reported by the validator
once the run completes.

## Why a separate dry-run driver (not extend smoke_live.py)?

Two reasons. (1) The diagnostic invocation shape differs — smoke uses
`_run_diagnostic_pilot` to bypass the subset filter; dry-run uses the
canonical `run_permuted_diagnostic` so the production filter governs
which receipts are emitted. (2) Run-id prefix differs (`dry-run-` vs
`smoke-`) and a few config strings differ to keep the artefacts cleanly
separable. The two drivers share most of their composition pattern —
particularly the `_build_live_handlers` helper which is the canonical
handler-install pattern documented in the E2-007 decision_log entry.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from meshqu_runner.agent import (  # noqa: E402
    Agent,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    load_system_prompt,
)
from meshqu_runner.context_levels.level_l0 import install_live_l0  # noqa: E402
from meshqu_runner.context_levels.level_l3 import install_live_l3  # noqa: E402
from meshqu_runner.context_levels.level_l4 import L4PolicyEnvelopeHandler  # noqa: E402
from meshqu_runner.diagnostic.runner import run_permuted_diagnostic  # noqa: E402
from meshqu_runner.level_handlers import (  # noqa: E402
    GovernanceContextLevel,
    default_main_handlers,
)
from meshqu_runner.meshqu_client import MeshQuClient  # noqa: E402
from meshqu_runner.multi_pass import (  # noqa: E402
    MultiPassConfig,
    run_multi_pass,
)
from meshqu_runner.precedent_archive import (  # noqa: E402
    default_frozen_archive_dir,
    load_frozen_archive,
)
from meshqu_runner.prompt_loader import load_level_prompts  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = (
    "MESHQU_API_URL",
    "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID",
    "MESHQU_EXPERIMENT_PROCUREMENT_API_KEY",
    "OPENAI_API_KEY",
)

DEFAULT_FIXTURE_REL = "tests/fixtures/dry_run_records.json"

# Per-request pause. Same 500ms as smoke. At dry-run scale (150 main
# calls), this adds ~75s of wall-clock pacing — negligible compared to
# per-call latency (mean ~2s observed in smoke).
INTER_REQUEST_PAUSE_SECONDS = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-Z")


def _check_env() -> dict[str, str]:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing required env vars (source .env.live first): "
            + ", ".join(missing)
        )
    return {name: os.environ[name] for name in REQUIRED_ENV_VARS}


def _load_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    with fixture_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return list(data["records"])
    raise SystemExit(
        f"Fixture at {fixture_path} is neither a JSON array nor an "
        f"object with a 'records' key."
    )


def _drop_e1_reference(record: dict[str, Any]) -> dict[str, Any]:
    """Strip the audit-only `e1_reference` block. The orchestrator
    doesn't read it, but eliding it guarantees the canonical-JSON
    `fields` envelope is byte-identical between a fixture record and a
    non-fixture record."""
    return {k: v for k, v in record.items() if k != "e1_reference"}


def _build_live_handlers(
    *,
    repo_dir: Path,
    policy_path: Path,
) -> dict[GovernanceContextLevel, Any]:
    """Canonical handler-install pattern from E2-007's smoke_live.py.

    `default_main_handlers()` only wires L1+L2 to live; L0/L3/L4 stay
    as stubs unless this composition runs. The smoke caught a 16-call
    "all stubs at L4 → 0 cache" bug from skipping this — at dry-run
    scale (150 calls, $3+) the consequences are larger; at full-run
    scale ($9.68) the consequences are larger still. See the 2026-05-21
    decision_log entry §3 for the full diagnosis."""
    handlers = default_main_handlers()
    install_live_l0(handlers)

    archive = load_frozen_archive(default_frozen_archive_dir(repo_dir))
    install_live_l3(handlers, archive=archive)

    handlers["L4"] = L4PolicyEnvelopeHandler(policy_path=policy_path)
    return handlers


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E2-008 live dry-run driver (30 records × 5 levels + intersection-Permuted-Policy diagnostic)"
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help=f"Path to dry-run fixture JSON. Default: runner/{DEFAULT_FIXTURE_REL}",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Where to write results/runs/<run_id>/. Default: <repo>/procurement-context-gradient/results",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id. Default: dry-run-<UTC-timestamp-slug>.",
    )
    parser.add_argument(
        "--skip-diagnostic",
        action="store_true",
        help="Skip the Permuted-Policy diagnostic pass (debug only).",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Run with StubAgent + StubMeshQuClient to validate orchestration "
             "without spending money. NO live OpenAI / MeshQu calls.",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture) if args.fixture else RUNNER_DIR / DEFAULT_FIXTURE_REL
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")
    fixture_records_raw = _load_fixture(fixture_path)
    if not fixture_records_raw:
        raise SystemExit(f"Fixture {fixture_path} contains no records.")
    fixture_records = [_drop_e1_reference(r) for r in fixture_records_raw]

    e2_dir = RUNNER_DIR.parent  # procurement-context-gradient/
    repo_dir = e2_dir.parent  # meshqu-research/
    results_dir = Path(args.results_dir) if args.results_dir else e2_dir / "results"
    run_id = args.run_id or (f"dry-run-{_utc_timestamp_slug()}" if not args.stub else f"dry-run-stub-{_utc_timestamp_slug()}")
    run_dir = results_dir / "runs" / run_id

    policy_path = e2_dir / "policy" / "policy-snapshot-cbf12348.json"
    if not policy_path.exists():
        raise SystemExit(f"Policy snapshot not found at {policy_path}")

    prompts_dir = RUNNER_DIR / "prompts"
    prompts = load_level_prompts(prompts_dir)

    # ---- Construct clients ----------------------------------------------

    if args.stub:
        # Stub-mode orchestration smoke. NO env vars required — kept
        # simple so this driver is testable in CI without secrets.
        from meshqu_runner.multi_pass import StubAgent, StubMeshQuClient  # noqa: WPS433

        agent = StubAgent()
        meshqu_client = StubMeshQuClient()
        api_url = "https://stub.invalid"
        substrate_adapter_version = "stub-dry-run-7ddf7274"
    else:
        env = _check_env()
        system_prompt = load_system_prompt()
        agent = Agent(
            api_key=env["OPENAI_API_KEY"],
            system_prompt=system_prompt,
            model_id=LOCKED_MODEL_ID,
            temperature=LOCKED_TEMPERATURE,
        )
        meshqu_client = MeshQuClient(
            base_url=env["MESHQU_API_URL"],
            api_key=env["MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"],
            tenant_id=env["MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"],
        )
        api_url = env["MESHQU_API_URL"]
        substrate_adapter_version = "cached-e1-dry-run-7ddf7274"

    config = MultiPassConfig(
        run_id=run_id,
        run_phase="dry_run",
        repo_dir=repo_dir,
        run_dir=run_dir,
        prompts_dir=prompts_dir,
        policy_snapshot_path=policy_path,
        meshqu_api_url=api_url,
        meshqu_tenant_label="experiment-procurement",
        substrate_adapter_version=substrate_adapter_version,
        substrate_source={
            "kind": "cached_e1_archive",
            "archive_run_id": "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d",
            "fixture_path": str(fixture_path.relative_to(repo_dir)),
            "fixture_record_count": len(fixture_records),
        },
        inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
        cache_telemetry_enabled=True,
    )

    print(f"==> Run id: {run_id}")
    print(f"    Mode:           {'STUB (no live calls)' if args.stub else 'LIVE (real OpenAI + MeshQu)'}")
    print(f"    Run dir:        {run_dir.relative_to(repo_dir)}")
    print(f"    Fixture:        {fixture_path.relative_to(repo_dir)}")
    print(f"    Records:        {len(fixture_records)}")
    print(f"    Levels (main):  L0 L1 L2 L3 L4  ({len(fixture_records) * 5} receipts)")
    print(f"    Diagnostic:     {'natural-subset Permuted-Policy' if not args.skip_diagnostic else 'SKIPPED'}")
    print()

    live_handlers = _build_live_handlers(repo_dir=repo_dir, policy_path=policy_path)
    print(
        "    Handlers: "
        + ", ".join(f"{lvl}={type(h).__name__}" for lvl, h in sorted(live_handlers.items()))
    )
    print()

    # ---- Main grid -----------------------------------------------------

    t_main_start = time.monotonic()
    summary = run_multi_pass(
        config=config,
        records=fixture_records,
        agent=agent,
        meshqu_client=meshqu_client,
        handlers=live_handlers,
    )
    t_main_end = time.monotonic()
    main_elapsed = t_main_end - t_main_start
    n_main = len(summary.outcomes)
    print(
        f"==> Main grid done. {n_main} receipts in "
        f"{main_elapsed:.1f}s ({main_elapsed / max(n_main, 1):.2f}s/call)."
    )

    # ---- Diagnostic pass ----------------------------------------------

    n_diagnostic = 0
    if not args.skip_diagnostic:
        print("==> Running Permuted-Policy diagnostic against the dry-run fixture…")
        print("    Filter: is_in_permuted_subset(ocid) (the canonical 5% subset)")
        t_diag_start = time.monotonic()
        diag_summary = run_permuted_diagnostic(
            run_id=run_id,
            run_dir=run_dir,
            prompts=prompts,
            policy_path=policy_path,
            records=fixture_records,
            agent=agent,
            meshqu_client=meshqu_client,
            inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
        )
        t_diag_end = time.monotonic()
        n_diagnostic = len(diag_summary.outcomes)
        print(
            f"    Diagnostic done. {n_diagnostic} bundle(s) in "
            f"{t_diag_end - t_diag_start:.1f}s. "
            f"Subset OCIDs in fixture: {len(diag_summary.subset_ocids)}"
        )

    # ---- Index file ---------------------------------------------------

    total = n_main + n_diagnostic
    index = {
        "run_id": run_id,
        "fixture": str(fixture_path.relative_to(repo_dir)),
        "fixture_record_count": len(fixture_records),
        "main_grid_outcome_count": n_main,
        "diagnostic_outcome_count": n_diagnostic,
        "expected_main_total": len(fixture_records) * 5,
        "actual_total_bundles": total,
        "is_stub": bool(args.stub),
        "wall_clock_seconds_main": round(main_elapsed, 1),
    }
    index_path = run_dir / "dry_run_index.json"
    with index_path.open("w", encoding="utf-8") as fp:
        json.dump(index, fp, indent=2, sort_keys=True)
        fp.write("\n")
    print(f"==> Wrote index: {index_path.relative_to(repo_dir)}")

    expected_main = len(fixture_records) * 5
    if n_main != expected_main:
        print(
            f"WARN: expected {expected_main} main bundles, wrote {n_main}.",
            file=sys.stderr,
        )
        return 1

    print(f"==> SUCCESS: {total} bundles in {run_dir.relative_to(repo_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
