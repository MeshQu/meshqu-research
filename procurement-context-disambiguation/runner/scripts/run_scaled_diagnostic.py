#!/usr/bin/env python3
"""E3-008 — Scaled Permuted-Policy diagnostic driver.

Runs the locked Permuted-Policy diagnostic over the n=100 OCID subset on
either the primary model (``--arm diagnostic_primary``) or Claude
(``--arm diagnostic_claude``). The same 100 OCIDs in the same order on
both arms makes the cross-model comparison record-matched (the rubric
coder reads the primary's reasoning for OCID-N alongside Claude's
for OCID-N).

## Modes

- ``--smoke``  — first 3 OCIDs from the locked subset (deterministic).
- ``--dry-run`` — first 10 OCIDs (broader exercise of the path, still
                 cheap; used by E3-011 to validate the pipeline end-
                 to-end before the Phase-2 full run).
- ``--dry``     — also force stub agent + stub MeshQu client (no live
                 API calls). Composable with ``--smoke`` and
                 ``--dry-run`` for offline pipeline verification.
- No flag      — full 100 records (Phase-2 invocation).

## What this script does NOT do

- It does NOT regenerate the subset at runtime. The locked
  ``planning/diagnostic_subset.json`` is the source of truth; the
  selector module (``meshqu_runner.diagnostic.subset_selector``)
  exists for re-verification + one-time emit, not for runtime
  consumption.
- It does NOT call live APIs unless explicitly invoked without
  ``--dry`` (the spec's smoke / dry-run flags don't imply live
  calls — they bound the record count; ``--dry`` is orthogonal).
- It does NOT write its own run manifest at the script level —
  ``run_arm`` handles that for the arm's run_dir.

## Receipts + sidecar emit

Each record produces one bundle at
``<run_dir>/diagnostic_<primary|claude>/<decision_id>.bundle.json``
(via the standard ``run_arm`` bundle writer; the arm name becomes the
subdir).

Once per script invocation, the driver writes the **inverted-operator
spec sidecar** at ``<run_dir>/diagnostic/inverted_operator_spec.json``
— the file the E3-009 rubric-coding tool reads to display "what was
inverted" alongside each reasoning text. See
``meshqu_runner.diagnostic.runner:emit_inverted_operator_spec``
for the payload shape.

## Usage examples

    # Smoke probe — 3 records, primary model, stubs (no API calls)
    python scripts/run_scaled_diagnostic.py --arm diagnostic_primary --smoke --dry

    # Dry-run — 10 records, Claude, stubs
    python scripts/run_scaled_diagnostic.py --arm diagnostic_claude --dry-run --dry

    # Phase-2 full run — 100 records, primary, LIVE (requires API keys)
    python scripts/run_scaled_diagnostic.py --arm diagnostic_primary

    # Phase-2 full run — 100 records, Claude, LIVE
    python scripts/run_scaled_diagnostic.py --arm diagnostic_claude
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Make ``meshqu_runner`` importable when running from the script
# directory directly (mirrors the other scripts in this dir).
_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

from meshqu_runner.arms import ARM_PROFILES  # noqa: E402
from meshqu_runner.diagnostic.permute_policy import (  # noqa: E402
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    permute_policy,
)
from meshqu_runner.diagnostic.scaled import (  # noqa: E402
    emit_inverted_operator_spec,
    load_diagnostic_subset,
)

# The "diagnostic" sidecar subdir name matches the convention E2's
# 14-record diagnostic uses (see
# ``meshqu_runner.diagnostic.runner.DIAGNOSTIC_SUBDIR``); declared
# locally to avoid importing the E2-inherited ``diagnostic/runner.py``
# (broken in the E3 fork due to a stale ``multi_pass`` import).
DIAGNOSTIC_SIDECAR_SUBDIR = "diagnostic"
from meshqu_runner.context_levels.level_l4 import (  # noqa: E402
    load_policy_snapshot,
)
from meshqu_runner.arms.diagnostic import (  # noqa: E402
    DEFAULT_POLICY_SNAPSHOT_PATH,
)
from meshqu_runner.multi_pass import (  # noqa: E402
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)


SMOKE_COUNT = 3
"""Number of records ``--smoke`` runs. Deterministic — first 3 OCIDs
from the locked subset, in selection order. The spec's "PR body must
answer: the 3 records the --smoke flag would run on" check reads this
slice at audit time."""

DRY_RUN_COUNT = 10
"""Number of records ``--dry-run`` runs. Broader exercise of the
pipeline (~10% of the full subset); used by E3-011 to validate the
full path end-to-end before Phase-2."""

FULL_COUNT = 100
"""Full locked subset size — matches ``DIAGNOSTIC_SUBSET_SIZE`` in
``meshqu_runner.diagnostic.subset_selector``."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_scaled_diagnostic.py",
        description=(
            "E3-008 scaled Permuted-Policy diagnostic. Runs the locked "
            "n=100 OCID subset on either the primary model or Claude."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=("diagnostic_primary", "diagnostic_claude"),
        required=True,
        help="Which diagnostic arm to dispatch.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=f"Run only the first {SMOKE_COUNT} OCIDs from the locked subset.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=f"Run only the first {DRY_RUN_COUNT} OCIDs from the locked subset.",
    )
    parser.add_argument(
        "--dry",
        action="store_true",
        help=(
            "Use StubAgent + StubMeshQuClient (no live API calls). "
            "Composable with --smoke and --dry-run for offline pipeline "
            "verification."
        ),
    )
    parser.add_argument(
        "--policy-permutation-seed",
        type=int,
        default=LOCKED_PERMUTATION_SEED,
        help=(
            f"Integer seed for the policy permutation. Defaults to "
            f"LOCKED_PERMUTATION_SEED={LOCKED_PERMUTATION_SEED} (E2's "
            f"locked diagnostic seed). DO NOT override in production — "
            f"scaling from 14 to 100 records does not reseed."
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help=(
            "Where to write results/runs/<run_id>/. Defaults to "
            "<runner>/results."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Override run_id; defaults to "
            "'e3-008-<arm>-<mode>-<uuid>'."
        ),
    )
    parser.add_argument(
        "--policy-snapshot-path",
        type=Path,
        default=DEFAULT_POLICY_SNAPSHOT_PATH,
        help=(
            "Policy snapshot path. Defaults to E2's locked snapshot; "
            "override only for tests."
        ),
    )
    parser.add_argument(
        "--inter-request-pause-seconds",
        type=float,
        default=0.0,
        help=(
            "Pace between records (rate-limiting safeguard for live "
            "runs). Defaults to 0; production live runs should set a "
            "non-zero value matching the provider's tolerance."
        ),
    )
    return parser


def _resolve_record_slice(args: argparse.Namespace, all_ocids: list[str]) -> list[str]:
    """Pick the slice of OCIDs to actually run.

    ``--smoke`` and ``--dry-run`` are mutually exclusive (caller-side
    check); each defines the count deterministically. No flag → full.
    """
    if args.smoke and args.dry_run:
        raise SystemExit(
            "FAIL: --smoke and --dry-run are mutually exclusive."
        )
    if args.smoke:
        return all_ocids[:SMOKE_COUNT]
    if args.dry_run:
        return all_ocids[:DRY_RUN_COUNT]
    return all_ocids[:FULL_COUNT]


def _mode_tag(args: argparse.Namespace) -> str:
    """Short label for the run_id default — keeps the artefact path
    self-describing without parsing flags out of a uuid."""
    if args.smoke:
        return "smoke"
    if args.dry_run:
        return "dryrun"
    return "full"


def _build_records(ocids: list[str]) -> list[dict[str, Any]]:
    """Materialise records from the OCID list.

    For E3-008's diagnostic, the L4 envelope is record-independent — the
    handler doesn't reference any per-record field. So a minimal
    record shape (just the OCID + decision_type) is sufficient to
    drive ``run_arm`` end-to-end without dragging the substrate cache
    into the dispatch path.

    The smoke + dry-run modes use this same minimal shape. The Phase-2
    full run via this script also uses it — the diagnostic is
    deliberately substrate-light (the policy permutation is the
    independent variable; the record's substrate fields don't enter
    the L4 envelope anyway).
    """
    return [
        {
            "ocid": ocid,
            "decision_type": "procurement_decision",
            "fields": {},
            "substrate_notes": {},
            "metadata": {"ocid": ocid},
        }
        for ocid in ocids
    ]


def _compute_permutation_log(policy_snapshot_path: Path, seed: int) -> list[dict[str, Any]]:
    """Apply ``permute_policy(...)`` to the locked snapshot and return
    the log entries.

    Surfaced as a helper so the driver script's sidecar-emit path and a
    test can both call it without re-implementing the permutation. The
    log entries carry per-rule original / inverted condition dicts
    that ``emit_inverted_operator_spec`` summarises into human-readable
    spec strings.
    """
    policy = load_policy_snapshot(policy_snapshot_path)
    permuted = permute_policy(policy, seed=seed)
    log = permuted.get(PERMUTATION_LOG_KEY) or {"entries": []}
    return list(log.get("entries", []))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Resolve locked subset
    all_ocids = load_diagnostic_subset()
    ocids = _resolve_record_slice(args, all_ocids)
    records = _build_records(ocids)

    # Decide live vs stub
    is_live = not args.dry
    if is_live:
        # Defensive: require both keys to be present for live mode so a
        # half-configured environment doesn't silently start a partial
        # run.
        missing: list[str] = []
        if args.arm == "diagnostic_primary" and not os.environ.get("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")
        if args.arm == "diagnostic_claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            print(
                f"FAIL: live mode requires {missing!r} in the environment. "
                f"Pass --dry for stubbed pipeline verification.",
                file=sys.stderr,
            )
            return 2

    # Resolve run_dir
    runner_dir = Path(__file__).resolve().parent.parent
    e3_dir = runner_dir.parent  # procurement-context-disambiguation/
    repo_dir = e3_dir.parent  # repo root
    results_dir = args.results_dir if args.results_dir else e3_dir / "results"
    run_id = args.run_id or f"e3-008-{args.arm}-{_mode_tag(args)}-{uuid.uuid4()}"
    run_dir = results_dir / "runs" / run_id

    # Build agent + meshqu client
    if not is_live:
        agent: Any = StubAgent()
        meshqu_client: Any = StubMeshQuClient()
    else:
        # Live agent construction. Imports lazy so --dry never touches
        # the SDKs.
        if args.arm == "diagnostic_primary":
            from meshqu_runner.agent import Agent, load_system_prompt

            agent = Agent(
                api_key=os.environ["OPENAI_API_KEY"],
                system_prompt=load_system_prompt(),
            )
        else:
            from meshqu_runner.agent import load_system_prompt
            from meshqu_runner.agents.claude import ClaudeAgent

            agent = ClaudeAgent(system_prompt=load_system_prompt())

        # Live MeshQu client construction is out of scope for this
        # script; the spec defers full live-mode wiring to E3-010/011.
        # We fail loudly here rather than silently sign with the stub.
        raise NotImplementedError(
            "Live MeshQu client wiring lands in E3-010 / E3-011 (smoke + "
            "dry-run packages). For now, pass --dry to exercise the "
            "pipeline with stubs."
        )

    config = RunConfig(
        run_id=run_id,
        run_phase="dry-run" if not is_live else "phase-2",
        repo_dir=repo_dir,
        run_dir=run_dir,
        arm_name=args.arm,
        policy_snapshot_path=args.policy_snapshot_path,
        policy_permutation_seed=args.policy_permutation_seed,
        inter_request_pause_seconds=args.inter_request_pause_seconds,
    )

    summary = run_arm(
        config=config,
        records=records,
        agent=agent,
        meshqu_client=meshqu_client,
        handler_kwargs={
            "policy_snapshot_path": args.policy_snapshot_path,
            "seed": args.policy_permutation_seed,
        },
    )

    # Sibling artefact — inverted-operator-spec sidecar. Emitted ONCE
    # per script invocation, after the per-record bundles have all
    # been written. The rubric tool (E3-009) reads it alongside the
    # bundles to display "what was inverted" beside each reasoning
    # text. The directory is the *standard* ``<run_dir>/diagnostic/``
    # name — same convention as E2's 14-record diagnostic (see
    # ``meshqu_runner.diagnostic.runner.DIAGNOSTIC_SUBDIR``). NOTE
    # the per-arm bundles land under ``<run_dir>/diagnostic_primary/``
    # or ``<run_dir>/diagnostic_claude/`` via ``run_arm``'s arm-name
    # subdir — the sidecar's location is *independent* of arm because
    # the spec is a function of (policy, seed), not (arm, record).
    permutation_log_entries = _compute_permutation_log(
        args.policy_snapshot_path,
        args.policy_permutation_seed,
    )
    diagnostic_sidecar_dir = run_dir / DIAGNOSTIC_SIDECAR_SUBDIR
    diagnostic_sidecar_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = emit_inverted_operator_spec(
        diagnostic_dir=diagnostic_sidecar_dir,
        ocids=ocids,
        seed=args.policy_permutation_seed,
        permutation_log_entries=permutation_log_entries,
    )

    print(
        f"OK: dispatched arm={args.arm} mode={_mode_tag(args)} "
        f"records={len(records)}; wrote {len(summary.outcomes)} bundle(s) "
        f"under {run_dir}/{args.arm}/ + sidecar at {sidecar_path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
