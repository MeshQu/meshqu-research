#!/usr/bin/env python3
"""Post-hoc reconstruction of the inverted-operator-spec sidecar for
a completed Phase-2 (or dry-run) run that landed without one.

## Why this exists

Contract drift between sibling drivers (see decision_log Phase-2
close-out + this PR's body):

  - PR #95 (run_scaled_diagnostic.py) emitted the sidecar in-band.
  - PR #91 (rubric tool) requires the sidecar at the run-dir root.
  - PR #96 (smoke_e3.py) forked without emission.
  - PR #99 (dry_run_e3.py) extended smoke_e3 — still no emission.

Phase 2 fired 2026-05-29 via dry_run_e3.py --scale phase-2 produced
1,332 cryptographically-verified bundles + summaries + observability
captures but NO inverted-operator-spec sidecar. The user caught the
drift when trying to start Phase 2.5 hand-coding via the rubric tool.

The driver fix lands in the same PR as this script (see the prior
commit on this branch). This script's job is the one-time retroactive
reconstruction for the already-completed Phase-2 corpus so Phase 2.5
can start without a re-fire (which would cost ~$25, two hours, and
new receipt timestamps that don't match the writeup-anchor run).

## Why this is byte-deterministic and safe

The sidecar is metadata about the policy permutation, derivable from
inputs that are all locked by ``v0.3-predictions-locked``:

  - the n=100 locked diagnostic-subset OCIDs at
    ``planning/diagnostic_subset.json``
  - E2's locked policy snapshot at
    ``procurement-context-gradient/policy/policy-snapshot-cbf12348.json``
  - ``LOCKED_PERMUTATION_SEED=0`` from
    ``meshqu_runner.diagnostic.permute_policy``
  - the producer at
    ``meshqu_runner.diagnostic.scaled.emit_inverted_operator_spec``
    (byte-identical-from-PR-#95; uses sort_keys=True + atomic write)

Re-applying the same locked permutation to the same locked policy
snapshot is a pure function. The reconstructed sidecar is byte-
equivalent to what an in-band emission would have produced during the
original Phase 2 fire. No receipts need to be re-signed because the
sidecar is NOT part of the signed bundle.

## What this script does NOT do

- It does NOT modify any receipt bundle.
- It does NOT call any live API.
- It does NOT modify any locked-content file.
- It does NOT regenerate the diagnostic subset.

## Usage

    # Default — Phase-2 canonical run dir
    python3 scripts/generate_inverted_spec_post_hoc.py

    # Explicit run dir override
    python3 scripts/generate_inverted_spec_post_hoc.py \\
        --run-dir results/runs/phase-2-20260529T092611-Z

    # Custom seed (would only be used for stochastic-variant runs;
    # the canonical Phase 2 used LOCKED_PERMUTATION_SEED=0)
    python3 scripts/generate_inverted_spec_post_hoc.py --seed 0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Path bootstrap — let the script run from any cwd via
# ``python3 scripts/generate_inverted_spec_post_hoc.py`` from the runner
# directory.
_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

from meshqu_runner.arms.diagnostic import (  # noqa: E402
    DEFAULT_POLICY_SNAPSHOT_PATH,
)
from meshqu_runner.context_levels.level_l4 import (  # noqa: E402
    load_policy_snapshot,
)
from meshqu_runner.diagnostic.permute_policy import (  # noqa: E402
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    permute_policy,
)
from meshqu_runner.diagnostic.scaled import (  # noqa: E402
    emit_inverted_operator_spec,
    load_diagnostic_subset,
)


PHASE_2_CANONICAL_RUN_ID = "phase-2-20260529T092611-Z"
"""The 2026-05-29 canonical Phase-2 run (committed in PR #104). This is
the run that needs the retroactive sidecar."""


def _resolve_default_run_dir() -> Path:
    """Default to the committed Phase-2 canonical run dir."""
    e3_dir = _RUNNER_DIR.parent  # procurement-context-disambiguation/
    return e3_dir / "results" / "runs" / PHASE_2_CANONICAL_RUN_ID


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_inverted_spec_post_hoc.py",
        description=(
            "Post-hoc reconstruction of the inverted-operator-spec "
            "sidecar for a completed Phase-2 (or dry-run) run. Closes "
            "the contract-drift gap between sibling drivers (PR #95 "
            "had emission; PR #96 + PR #99 forked without it; Phase 2 "
            "landed without the sidecar)."
        ),
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "Run directory the sidecar lands inside. Defaults to "
            f"results/runs/{PHASE_2_CANONICAL_RUN_ID}/ — the committed "
            "Phase-2 canonical run."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=LOCKED_PERMUTATION_SEED,
        help=(
            f"Policy-permutation seed. Defaults to "
            f"LOCKED_PERMUTATION_SEED={LOCKED_PERMUTATION_SEED} (E2's "
            f"locked seed; what Phase 2 actually used). Override only "
            f"for stochastic-variant runs that ran on a non-canonical "
            f"seed."
        ),
    )
    parser.add_argument(
        "--policy-snapshot-path",
        type=Path,
        default=DEFAULT_POLICY_SNAPSHOT_PATH,
        help=(
            "Locked policy snapshot path. Defaults to E2's locked "
            "snapshot at policy-snapshot-cbf12348.json — what Phase 2 "
            "actually used. Override only for testing."
        ),
    )
    parser.add_argument(
        "--print-sample",
        type=int,
        default=3,
        help=(
            "Print the first N OCIDs' generated spec entries after "
            "emit. Defaults to 3 (matches the PR body's evidence "
            "section). Pass 0 to skip."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    run_dir: Path = args.run_dir if args.run_dir else _resolve_default_run_dir()
    if not run_dir.exists():
        print(
            f"FAIL: run dir {run_dir} does not exist. Use --run-dir to "
            "point at a different run, or check the v0.3 tag is checked "
            "out cleanly.",
            file=sys.stderr,
        )
        return 2

    # The 100 OCIDs the diagnostic arms ran against. The locked subset
    # is the single source of truth here — same selector E3-008 +
    # E3-011 read at dispatch time.
    diagnostic_ocids = load_diagnostic_subset()
    print(
        f"==> Loaded {len(diagnostic_ocids)} locked diagnostic-subset "
        f"OCIDs (planning/diagnostic_subset.json)."
    )

    # E2's locked policy snapshot — what the Phase 2 diagnostic arms
    # rendered against verbatim.
    policy = load_policy_snapshot(args.policy_snapshot_path)
    print(
        f"==> Loaded locked policy snapshot from "
        f"{args.policy_snapshot_path}."
    )

    # Same in-memory permutation the drivers compute. Pure function of
    # (policy, seed) → same byte-deterministic output as an in-band
    # emission during the original Phase 2 fire would have produced.
    permuted = permute_policy(policy, seed=args.seed)
    log = permuted.get(PERMUTATION_LOG_KEY) or {"entries": []}
    permutation_log_entries = list(log.get("entries", []))
    print(
        f"==> Computed permutation log "
        f"({len(permutation_log_entries)} rule entries; seed={args.seed})."
    )

    # Same producer the in-band emission would have called. Atomic
    # write + sort_keys=True from PR #95 — byte-deterministic.
    sidecar_path = emit_inverted_operator_spec(
        diagnostic_dir=run_dir,
        ocids=diagnostic_ocids,
        seed=args.seed,
        permutation_log_entries=permutation_log_entries,
    )
    print(f"==> Wrote sidecar: {sidecar_path}")

    # Roundtrip-verify through the consumer the rubric tool uses. If
    # this raises, the producer/consumer contract is broken — surface,
    # don't silently emit a sidecar the rubric tool can't read.
    from meshqu_runner.diagnostic.rubric_io import load_inverted_specs

    loaded = load_inverted_specs(sidecar_path)
    assert len(loaded) == len(diagnostic_ocids), (
        f"FAIL: round-trip mismatch — wrote {len(diagnostic_ocids)} "
        f"OCIDs, read back {len(loaded)}. Producer/consumer drift."
    )
    print(
        f"==> Roundtrip-verified via "
        f"meshqu_runner.diagnostic.rubric_io.load_inverted_specs "
        f"({len(loaded)} entries)."
    )

    if args.print_sample > 0:
        print()
        print(f"==> First {args.print_sample} OCIDs' generated spec entries:")
        for i, ocid in enumerate(diagnostic_ocids[: args.print_sample]):
            spec_obj = loaded[ocid]
            print()
            print(f"  [{i}] OCID: {ocid}")
            print(f"      spec: {spec_obj.spec}")

    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
