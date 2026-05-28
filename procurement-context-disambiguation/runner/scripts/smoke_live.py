#!/usr/bin/env python3
"""Live smoke driver — E2-007 Stage C entry point.

Reads `runner/tests/fixtures/smoke_records_live.json` (3 deterministic
records from the E1 frozen archive), wires the LIVE `Agent` +
`MeshQuClient` against credentials from environment variables, and
invokes:

  1. `run_multi_pass(...)` for the 5-level main grid (15 receipts)
  2. `run_permuted_diagnostic(...)` with a 1-record subset bypassing
     the deterministic 5% filter — the worked-example OCID
     (ca19e737-…). Bypassing the filter is intentional for the smoke
     pilot (per E2-007 package §3g — the diagnostic must run on the
     worked example so we can check integrity-hash distinctness
     against the main-grid L4 receipt on the same OCID).

Total budget: 16 LIVE OpenAI calls + 16 LIVE MeshQu /v1/decisions/record
calls. Real tokens consumed, real receipts written to staging.

## Credential source

Credentials are NEVER passed on the command line. They live in
`procurement-context-gradient/runner/.env.live` (gitignored, perms 600,
populated by Sam pre-run). The expected pattern is:

    set -a && source procurement-context-gradient/runner/.env.live && set +a
    python procurement-context-gradient/runner/scripts/smoke_live.py [...]

The driver reads the four required env vars and refuses to run if any
are missing. It never echoes the values.

  - MESHQU_API_URL
  - MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID
  - MESHQU_EXPERIMENT_PROCUREMENT_API_KEY
  - OPENAI_API_KEY

## Run directory

    procurement-context-gradient/results/runs/smoke-<UTC-timestamp>/

with the standard E2 layout (manifest.json, L0..L4 subdirs, diagnostic/,
cache_telemetry.jsonl).

## Why not extend multi_pass._main()

Two reasons. (1) The diagnostic Permuted-Policy pilot is a SEPARATE
function call (`run_permuted_diagnostic`) layered on top of
`run_multi_pass`; putting both behind a single CLI flag muddies the
contract. (2) The smoke driver does light orchestration the main
runner doesn't need — it bypasses `is_in_permuted_subset` for the
diagnostic so the worked-example OCID gets a Permuted-Policy receipt
regardless of its corpus-wide hash position. A dry-run or full run
should NEVER bypass that filter; this is smoke-only behaviour.

The bypass is implemented by feeding the diagnostic only the worked-
example record and calling the inner pass directly — see
`_run_diagnostic_pilot` below.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path bootstrap — let the script run from any cwd via `python scripts/...`
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
from meshqu_runner.diagnostic.permute_policy import LOCKED_PERMUTATION_SEED  # noqa: E402
from meshqu_runner.diagnostic.runner import (  # noqa: E402
    DIAGNOSTIC_LEVEL,
    DIAGNOSTIC_SUBDIR,
    PERMUTATION_LOG_FILENAME,
    _process_diagnostic_pass,
    _write_permutation_log_sidecar,
    diagnostic_handlers,
)
from meshqu_runner.level_handlers import (  # noqa: E402
    GovernanceContextLevel,
    default_main_handlers,
)
from meshqu_runner.meshqu_client import MeshQuClient  # noqa: E402
from meshqu_runner.multi_pass import (  # noqa: E402
    MultiPassConfig,
    PassOutcome,
    _extract_ocid,
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

WORKED_EXAMPLE_OCID = "ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f"
"""The OCID for decision_id ca19e737-… — the £57M multi-rule DENY.
E2-007 §3g requires the Permuted-Policy pilot to run on this OCID so
the integrity-hash distinctness check (main L4 vs L4_PERMUTED on the
same record) is meaningful."""

DEFAULT_FIXTURE_REL = "tests/fixtures/smoke_records_live.json"
"""Default fixture path relative to runner/. The Option B fixture
committed alongside this driver."""

INTER_REQUEST_PAUSE_SECONDS = 0.5
"""Light pacing between live calls. The OpenAI + MeshQu rate limits
on staging aren't tight, but a 500ms gap keeps a transient 429 from
cascading. Smaller than E1's 1.0s — we have a 16-call budget so total
wall time stays modest (~30s on the API side, dominated by per-call
latency)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp_slug() -> str:
    """`YYYYMMDD-HHMMSS-Z` (Z is literal). Stable, sortable, no separators
    that fight the filesystem."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-Z")


def _check_env() -> dict[str, str]:
    """Validate required env vars are present. Returns a dict for
    structured access. Refuses to print values — only reports presence."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing required env vars (source .env.live first): "
            + ", ".join(missing)
        )
    return {name: os.environ[name] for name in REQUIRED_ENV_VARS}


def _load_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    """Load the Option B fixture. The committed file wraps the record
    array in `{"__comment__": "...", "records": [...]}`; tolerate both
    that shape and a bare JSON array for ad-hoc fixtures."""
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
    doesn't read it, but leaving it in the record would let it ride
    into the canonical-JSON fields envelope if the substrate code path
    ever changed — defensive elision keeps the bytes the agent sees
    identical to a non-fixture record."""
    return {k: v for k, v in record.items() if k != "e1_reference"}


def _find_record_by_ocid(
    records: list[dict[str, Any]], ocid: str
) -> dict[str, Any] | None:
    for r in records:
        if _extract_ocid(r) == ocid:
            return r
    return None


def _build_live_handlers(
    *,
    repo_dir: Path,
    policy_path: Path,
) -> dict[GovernanceContextLevel, Any]:
    """Build the full live handler registry — L0, L1, L2, L3, L4 all
    bound to their production implementations.

    `default_main_handlers()` only wires L1 + L2 to live by default
    (the stubs at L0, L3, L4 stay in place). Without this composition,
    L4 uses the STUB L4Handler which has no `compose_full_message`
    method — the policy block then sits behind L1/L2/L3 addenda and
    never caches.

    This function performs the install_live_{l0,l3} + L4 registry swap
    that the runner's own README documents but which is intentionally
    left to the driver to compose (so the runner remains testable
    without the E1 archive on disk).
    """
    handlers = default_main_handlers()
    install_live_l0(handlers)

    archive = load_frozen_archive(default_frozen_archive_dir(repo_dir))
    install_live_l3(handlers, archive=archive)

    handlers["L4"] = L4PolicyEnvelopeHandler(policy_path=policy_path)
    return handlers


# ---------------------------------------------------------------------------
# Diagnostic pilot — bypass the 5% subset filter
# ---------------------------------------------------------------------------


def _run_diagnostic_pilot(
    *,
    run_id: str,
    run_dir: Path,
    prompts: Any,
    policy_path: Path,
    worked_record: dict[str, Any],
    main_handlers_registry: dict[GovernanceContextLevel, Any],
    agent: Agent,
    meshqu_client: MeshQuClient,
    seed: int = LOCKED_PERMUTATION_SEED,
) -> PassOutcome:
    """Run a single Permuted-Policy pass on the supplied worked record.

    Mirrors `diagnostic.runner.run_permuted_diagnostic` but
    INTENTIONALLY bypasses `is_in_permuted_subset(ocid)`. Reason:
    E2-007 §3g requires the Permuted-Policy receipt on the *worked
    example* (ca19e737-…) so we can compare its integrity hash to the
    main-grid L4 receipt on the same OCID. The 5% subset filter is for
    the full-corpus 14-record diagnostic; in smoke we deliberately
    bypass it.

    The smoke driver writes only ONE Permuted-Policy bundle. The
    permutation_log.json sidecar still lands at
    `<run_dir>/diagnostic/permutation_log.json` so a verifier can
    confirm which inversion was applied.
    """
    handlers = diagnostic_handlers(
        policy_path=policy_path,
        seed=seed,
        main_handlers=main_handlers_registry,
    )

    permuted_handler = handlers[DIAGNOSTIC_LEVEL]
    # Eagerly render so we have the envelope SHA available for the
    # hash-bound fields and for the sidecar.
    permuted_handler.render(prompts)
    envelope_sha256 = permuted_handler.rendered_sha256
    permuted_policy = permuted_handler.permuted_policy

    diagnostic_dir = run_dir / DIAGNOSTIC_SUBDIR
    diagnostic_dir.mkdir(parents=True, exist_ok=True)

    _write_permutation_log_sidecar(
        diagnostic_dir=diagnostic_dir,
        permuted_policy=permuted_policy,
        envelope_sha256=envelope_sha256,
    )

    ocid = _extract_ocid(worked_record)
    if ocid is None:
        raise SystemExit("Worked-example record is missing an OCID; cannot run pilot.")

    outcome = _process_diagnostic_pass(
        run_id=run_id,
        diagnostic_dir=diagnostic_dir,
        prompts=prompts,
        record_index=0,
        record=worked_record,
        ocid=ocid,
        handlers=handlers,
        agent=agent,
        meshqu_client=meshqu_client,
        envelope_sha256=envelope_sha256,
        seed=seed,
        is_stub=False,
    )
    return outcome


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E2-007 live smoke driver (3 records × 5 levels + 1 Permuted-Policy pilot)"
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help=f"Path to smoke fixture JSON. Default: runner/{DEFAULT_FIXTURE_REL}",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Where to write results/runs/<run_id>/. Default: <repo>/procurement-context-gradient/results",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id. Default: smoke-<UTC-timestamp-slug>.",
    )
    parser.add_argument(
        "--skip-diagnostic",
        action="store_true",
        help="Skip the Permuted-Policy pilot (15 receipts instead of 16). For debugging only.",
    )
    args = parser.parse_args(argv)

    env = _check_env()

    fixture_path = Path(args.fixture) if args.fixture else RUNNER_DIR / DEFAULT_FIXTURE_REL
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")
    fixture_records_raw = _load_fixture(fixture_path)
    if not fixture_records_raw:
        raise SystemExit(f"Fixture {fixture_path} contains no records.")
    fixture_records = [_drop_e1_reference(r) for r in fixture_records_raw]

    worked_record = _find_record_by_ocid(fixture_records, WORKED_EXAMPLE_OCID)
    if worked_record is None and not args.skip_diagnostic:
        raise SystemExit(
            f"Worked-example record (ocid={WORKED_EXAMPLE_OCID}) not in fixture — "
            f"the Permuted-Policy pilot needs it for §3g."
        )

    e2_dir = RUNNER_DIR.parent  # procurement-context-gradient/
    repo_dir = e2_dir.parent  # meshqu-research/
    results_dir = Path(args.results_dir) if args.results_dir else e2_dir / "results"
    run_id = args.run_id or f"smoke-{_utc_timestamp_slug()}"
    run_dir = results_dir / "runs" / run_id

    policy_path = e2_dir / "policy" / "policy-snapshot-cbf12348.json"
    if not policy_path.exists():
        raise SystemExit(f"Policy snapshot not found at {policy_path}")

    prompts_dir = RUNNER_DIR / "prompts"
    prompts = load_level_prompts(prompts_dir)

    # ---- Construct LIVE clients ---------------------------------------

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

    config = MultiPassConfig(
        run_id=run_id,
        run_phase="smoke",
        repo_dir=repo_dir,
        run_dir=run_dir,
        prompts_dir=prompts_dir,
        policy_snapshot_path=policy_path,
        meshqu_api_url=env["MESHQU_API_URL"],
        meshqu_tenant_label="experiment-procurement",
        substrate_adapter_version="cached-e1-dry-run-7ddf7274",
        substrate_source={
            "kind": "cached_e1_archive",
            "archive_run_id": "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d",
            "fixture_path": str(fixture_path.relative_to(repo_dir)),
        },
        inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
        cache_telemetry_enabled=True,
    )

    print(f"==> Run id: {run_id}")
    print(f"    Run dir:        {run_dir.relative_to(repo_dir)}")
    print(f"    Fixture:        {fixture_path.relative_to(repo_dir)}")
    print(f"    Records:        {len(fixture_records)}")
    print(f"    Levels (main):  L0 L1 L2 L3 L4  ({len(fixture_records) * 5} receipts)")
    print(f"    Diagnostic:     {'L4_PERMUTED pilot (1 receipt)' if not args.skip_diagnostic else 'SKIPPED'}")
    print(f"    Budget total:   {len(fixture_records) * 5 + (0 if args.skip_diagnostic else 1)} live calls")
    print()

    # Build the live handler registry FIRST so a load-archive failure
    # surfaces before any live OpenAI / MeshQu call is made. Reused by
    # both the main grid and the diagnostic pilot below.
    live_handlers = _build_live_handlers(repo_dir=repo_dir, policy_path=policy_path)
    print(
        "    Handlers: "
        + ", ".join(f"{lvl}={type(h).__name__}" for lvl, h in sorted(live_handlers.items()))
    )
    print()

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
    print(
        f"==> Main grid done. {len(summary.outcomes)} receipts in "
        f"{main_elapsed:.1f}s ({main_elapsed / max(len(summary.outcomes), 1):.2f}s/call)."
    )

    diagnostic_outcome: PassOutcome | None = None
    if not args.skip_diagnostic and worked_record is not None:
        print("==> Running Permuted-Policy pilot on worked example (bypassing 5% subset filter)…")
        t_diag_start = time.monotonic()

        # Reuse the SAME live handler registry used by the main grid so
        # L0..L3 addenda are byte-identical between the main L4 pass
        # and the diagnostic L4_PERMUTED pass. Only the L4 block
        # differs (permuted policy vs unperturbed) — that delta is
        # exactly what the §3g integrity-hash distinctness check
        # measures.
        diagnostic_outcome = _run_diagnostic_pilot(
            run_id=run_id,
            run_dir=run_dir,
            prompts=prompts,
            policy_path=policy_path,
            worked_record=worked_record,
            main_handlers_registry=live_handlers,
            agent=agent,
            meshqu_client=meshqu_client,
        )
        t_diag_end = time.monotonic()
        print(
            f"    Diagnostic pilot wrote 1 bundle in {t_diag_end - t_diag_start:.1f}s. "
            f"decision_id={diagnostic_outcome.decision_id}"
        )

    # ---- Index file --------------------------------------------------

    expected_total = len(fixture_records) * 5 + (0 if args.skip_diagnostic else 1)
    actual_total = len(summary.outcomes) + (1 if diagnostic_outcome else 0)
    index = {
        "run_id": run_id,
        "fixture": str(fixture_path.relative_to(repo_dir)),
        "fixture_record_count": len(fixture_records),
        "main_grid_outcome_count": len(summary.outcomes),
        "diagnostic_outcome_count": 1 if diagnostic_outcome else 0,
        "expected_total_bundles": expected_total,
        "actual_total_bundles": actual_total,
        "main_outcomes": [
            {
                "level": o.level,
                "ocid": o.ocid,
                "decision_id": o.decision_id,
                "decision": o.receipt.decision,
                "agent_verdict": o.agent.verdict,
                "integrity_hash": o.receipt.integrity_hash,
                "signature_kid": o.receipt.signature_kid,
                "timestamp": o.timestamp,
                "bundle_path": str(o.bundle_path.relative_to(repo_dir)),
            }
            for o in summary.outcomes
        ],
        "diagnostic_outcome": (
            {
                "level": diagnostic_outcome.level,
                "ocid": diagnostic_outcome.ocid,
                "decision_id": diagnostic_outcome.decision_id,
                "decision": diagnostic_outcome.receipt.decision,
                "agent_verdict": diagnostic_outcome.agent.verdict,
                "integrity_hash": diagnostic_outcome.receipt.integrity_hash,
                "signature_kid": diagnostic_outcome.receipt.signature_kid,
                "timestamp": diagnostic_outcome.timestamp,
                "bundle_path": str(diagnostic_outcome.bundle_path.relative_to(repo_dir)),
            }
            if diagnostic_outcome
            else None
        ),
    }
    index_path = run_dir / "smoke_index.json"
    with index_path.open("w", encoding="utf-8") as fp:
        json.dump(index, fp, indent=2, sort_keys=True)
        fp.write("\n")
    print(f"==> Wrote index: {index_path.relative_to(repo_dir)}")

    if actual_total != expected_total:
        print(
            f"WARN: expected {expected_total} bundles, wrote {actual_total}. "
            "Inspect the run dir.",
            file=sys.stderr,
        )
        return 1

    print(f"==> SUCCESS: {actual_total} bundles in {run_dir.relative_to(repo_dir)}")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by E2-007 smoke run
    raise SystemExit(main())
