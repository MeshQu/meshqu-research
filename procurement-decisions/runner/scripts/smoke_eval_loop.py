"""
End-to-end smoke test for the Inspect-AI eval loop against staging.

Drives 3 hand-crafted OCDS records through the FULL pipeline:
   substrate.ocds_to_decision_context()
       → agent.evaluate() (real OpenAI call)
       → MeshQuClient.record_decision() (real staging POST)
       → decision_traces.jsonl + agent_outputs sidecar + manifest

Each record is designed to exercise a distinct policy path:

   Record A — above-threshold PA23 award, 25-day publication delay
              Expected MeshQu verdict: ALLOW
              (PROC-001-S53 fires but is within the 30-day allowance)

   Record B — above-threshold PA23 award, 35-day publication delay
              Expected MeshQu verdict: DENY
              (PROC-001-S53 violation)

   Record C — below-threshold award
              Expected MeshQu verdict: ALLOW
              (PROC-001-S53 when-clause excludes; no other rule fires)

The agent's verdict is independent. Mismatch is fine — the smoke test
isn't validating agreement, only that every layer of the pipeline works.

Required env vars:
   OPENAI_API_KEY                            (your OpenAI key)
   MESHQU_API_URL                            (staging URL)
   MESHQU_EXPERIMENT_PROCUREMENT_API_KEY     (tenant API key)
   MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID   (tenant UUID — sent as
                                              x-meshqu-tenant-id header)

Optional:
   MESHQU_SMOKE_RUN_DIR                      (default: results/runs/smoke-<ts>/)

Exit codes:
   0  all 3 records produced receipts, no orphans, no parse failures
   1  one or more records skipped or orphaned
   2  preflight failed (missing env vars, etc.)

Usage:
   cd procurement-decisions/runner
   OPENAI_API_KEY=sk-... \\
   MESHQU_API_URL=https://api.staging.meshqu.com \\
   MESHQU_EXPERIMENT_PROCUREMENT_API_KEY=meshqu_... \\
       python3 scripts/smoke_eval_loop.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Allow running this file directly: prepend the runner/ dir to sys.path
# so `meshqu_runner` imports work without installing the package.
RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from meshqu_runner.agent import Agent, load_system_prompt  # noqa: E402
from meshqu_runner.audit import AuditWriter  # noqa: E402
from meshqu_runner.eval_loop import (  # noqa: E402
    EvalLoopConfig,
    make_run_directory,
    run_eval_loop,
)
from meshqu_runner.meshqu_client import MeshQuClient  # noqa: E402
from meshqu_runner.substrate import (  # noqa: E402
    ADAPTER_VERSION,
    ocds_to_decision_context,
    provenance_summary,
)


# ---------------------------------------------------------------------------
# Hand-crafted OCDS records — one per policy path
# ---------------------------------------------------------------------------


PA23_AWARD_DATE = (date(2025, 2, 24) + timedelta(days=120)).isoformat()
"""All test awards dated after PA23 commencement so governed_by_pa23='true'."""


def _record_a_under_threshold_delay_window() -> dict:
    """Above-threshold PA23 award, 25-day publication delay → MeshQu ALLOW."""
    awarded = date.fromisoformat(PA23_AWARD_DATE)
    published = (awarded + timedelta(days=25)).isoformat()
    return {
        "ocid": "ocds-smoke-A",
        "tag": ["award"],
        "tender": {"value": {"amount": 250_000, "currency": "GBP"}, "procurementMethod": "open"},
        "awards": [
            {
                "id": "award-A",
                "date": PA23_AWARD_DATE,
                "datePublished": published,
                "value": {"amount": 250_000, "currency": "GBP"},
                "suppliers": [{"id": "GB-COH-12345678"}],
            }
        ],
    }


def _record_b_late_publication() -> dict:
    """Above-threshold PA23 award, 35-day publication delay → MeshQu DENY."""
    awarded = date.fromisoformat(PA23_AWARD_DATE)
    published = (awarded + timedelta(days=35)).isoformat()
    return {
        "ocid": "ocds-smoke-B",
        "tag": ["award"],
        "tender": {"value": {"amount": 500_000, "currency": "GBP"}, "procurementMethod": "open"},
        "awards": [
            {
                "id": "award-B",
                "date": PA23_AWARD_DATE,
                "datePublished": published,
                "value": {"amount": 500_000, "currency": "GBP"},
                "suppliers": [{"id": "GB-COH-87654321"}],
            }
        ],
    }


def _record_c_below_threshold() -> dict:
    """Below-threshold award → PROC-001-S53 when-clause excludes; ALLOW."""
    awarded = date.fromisoformat(PA23_AWARD_DATE)
    published = (awarded + timedelta(days=10)).isoformat()
    return {
        "ocid": "ocds-smoke-C",
        "tag": ["award"],
        "tender": {"value": {"amount": 50_000, "currency": "GBP"}, "procurementMethod": "open"},
        "awards": [
            {
                "id": "award-C",
                "date": PA23_AWARD_DATE,
                "datePublished": published,
                "value": {"amount": 50_000, "currency": "GBP"},
                "suppliers": [{"id": "GB-COH-11111111"}],
            }
        ],
    }


SMOKE_RECORDS = [
    _record_a_under_threshold_delay_window(),
    _record_b_late_publication(),
    _record_c_below_threshold(),
]


EXPECTED_MESHQU_VERDICTS = {
    "ocds-smoke-A": "ALLOW",
    "ocds-smoke-B": "DENY",
    "ocds-smoke-C": "ALLOW",
}


# ---------------------------------------------------------------------------
# Preflight + summary printing
# ---------------------------------------------------------------------------


def _preflight() -> tuple[str, str, str, str]:
    missing: list[str] = []
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    meshqu_url = os.environ.get("MESHQU_API_URL", "")
    meshqu_key = os.environ.get("MESHQU_EXPERIMENT_PROCUREMENT_API_KEY", "")
    meshqu_tenant_id = os.environ.get("MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID", "")
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    if not meshqu_url:
        missing.append("MESHQU_API_URL")
    if not meshqu_key:
        missing.append("MESHQU_EXPERIMENT_PROCUREMENT_API_KEY")
    if not meshqu_tenant_id:
        missing.append("MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID")
    if missing:
        print(f"error: missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)
    return openai_key, meshqu_url, meshqu_key, meshqu_tenant_id


def _print_outcome_table(summary) -> None:
    print()
    print("=== smoke results ===")
    print(f"  run_id           : {summary.run_id}")
    print(f"  records_attempted: {summary.records_attempted}")
    print(f"  records_with_receipt           : {summary.records_with_receipt}")
    print(f"  records_with_agent_parse_failure: {summary.records_with_agent_parse_failure}")
    print(f"  records_with_agent_call_error  : {summary.records_with_agent_call_error}")
    print(f"  records_with_meshqu_error      : {summary.records_with_meshqu_error}")
    print(f"  records_with_orphaned_receipt  : {summary.records_with_orphaned_receipt}")
    print(f"  policy_snapshot_id            : {summary.policy_snapshot_id}")
    print()
    print(f"{'ocid':<20} {'agent':<8} {'meshqu':<8} {'expected':<10} {'agreement':<10} {'decision_id'}")
    print(f"{'-' * 20} {'-' * 8} {'-' * 8} {'-' * 10} {'-' * 10} {'-' * 36}")
    for o in summary.outcomes:
        expected = EXPECTED_MESHQU_VERDICTS.get(o.ocid or "", "?")
        match_marker = "" if o.meshqu_verdict == expected else "  ← mismatch"
        print(
            f"{(o.ocid or '?'):<20} "
            f"{(o.agent_verdict or '-'):<8} "
            f"{(o.meshqu_verdict or '-'):<8} "
            f"{expected:<10} "
            f"{str(o.agreement):<10} "
            f"{o.decision_id or '-'}"
            f"{match_marker}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    openai_key, meshqu_url, meshqu_key, meshqu_tenant_id = _preflight()

    results_root = Path(
        os.environ.get(
            "MESHQU_SMOKE_RUN_DIR",
            str(RUNNER_DIR.parent / "results"),
        )
    )
    # Always start a fresh run for the smoke (a uuid suffix prevents
    # collision if the user re-runs without changing MESHQU_SMOKE_RUN_DIR).
    run_id = f"smoke-{uuid.uuid4()}"
    run_dir, _ = make_run_directory(results_root, run_id=run_id)
    print(f"smoke run_dir: {run_dir}")
    print(f"records: {len(SMOKE_RECORDS)}")
    print(f"meshqu: {meshqu_url}")
    print()

    audit = AuditWriter(run_dir, run_id)
    config = EvalLoopConfig(
        run_id=run_id,
        run_phase="dry-run",
        repo_dir=RUNNER_DIR.parent.parent,  # meshqu-research root
        run_dir=run_dir,
        meshqu_api_url=meshqu_url,
        meshqu_api_key=meshqu_key,
        meshqu_tenant_id=meshqu_tenant_id,
        meshqu_tenant_label="experiment-procurement",
        agent_api_key=openai_key,
        substrate_adapter_version=ADAPTER_VERSION,
        substrate_source={"feed": "smoke-fixtures-2026-05-17", "record_count": len(SMOKE_RECORDS)},
        record_target_count=len(SMOKE_RECORDS),
        policy_code="procurement-decisions-v1",
        # Smoke test wants live feedback, not a manifest pause:
        inter_request_pause_seconds=0.25,
    )

    # Print per-record progress as the loop runs.
    def _progress(record_index: int, outcome) -> None:
        print(
            f"  [{record_index + 1}/{len(SMOKE_RECORDS)}] "
            f"ocid={outcome.ocid} "
            f"outcome={outcome.outcome} "
            f"agent={outcome.agent_verdict} "
            f"meshqu={outcome.meshqu_verdict} "
            f"decision_id={outcome.decision_id or '-'}"
        )

    summary = run_eval_loop(
        config=config,
        records=SMOKE_RECORDS,
        substrate_callable=ocds_to_decision_context,
        provenance_summary_callable=provenance_summary,
        audit_writer=audit,
        meshqu_client=MeshQuClient(
            base_url=meshqu_url, api_key=meshqu_key, tenant_id=meshqu_tenant_id
        ),
        agent=Agent(api_key=openai_key, system_prompt=load_system_prompt()),
        on_after_record=_progress,
    )

    _print_outcome_table(summary)

    # Exit non-zero if anything went wrong end-to-end.
    if summary.records_with_receipt != len(SMOKE_RECORDS):
        print()
        print("FAIL: not every record produced a receipt — see anomalies.jsonl")
        return 1
    print()
    print(f"OK: {summary.records_with_receipt}/{len(SMOKE_RECORDS)} receipts in {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
