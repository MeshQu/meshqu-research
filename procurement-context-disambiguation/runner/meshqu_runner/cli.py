"""CLI entry point for the arm-aware E3 runner.

E2's CLI was a small set of operational sub-commands (mirror, capture,
smoke). E3's CLI is a single command driven by ``--arm`` because every
run is "pick an arm, run it against N records". The operational
sub-commands from E2 (dashboard mirror, screenshot capture) are still
available as importable functions in ``meshqu_runner.dashboard_mirror``
and ``meshqu_runner.screenshots`` — they just don't ride on the
default CLI surface any more.

## Invocation

    # Smoke probe — Arm A against 1 stubbed record, no live API calls
    python -m meshqu_runner.cli --arm arm_a --records 1 --dry

    # Real run against a target OCID list, primary model
    python -m meshqu_runner.cli --arm arm_b --ocid-list path/to/ocids.json

    # Cross-model diagnostic run
    python -m meshqu_runner.cli --arm diagnostic_claude --records 100 \\
        --policy-permutation-seed 42 --dry

The ``--dry`` flag forces ``StubAgent`` + ``StubMeshQuClient`` so no
OpenAI / Anthropic / MeshQu credentials are needed. This is the only
mode the foundation supports — live mode lands in E3-002..006.

## Foundation contract

The foundation's CLI must run end-to-end in ``--dry`` mode without
errors and dispatch to the correct placeholder handler. Subsequent
packages will:

- Wire their real handlers in via ``arms.register(...)``
- Add live-mode (no ``--dry``) wiring with ``--meshqu-api-key`` etc.
- Add an ``--ocid-list`` resolver that maps OCID strings to corpus
  records (E3-007's diagnostic subset selector emits the list format)
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

from .arms import ARM_NAMES
from .multi_pass import (
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)


def _synthetic_stub_records(count: int) -> list[dict[str, Any]]:
    """Build N deterministic stub records for ``--dry`` mode.

    The shape mirrors the smoke fixture's pattern (``ocid``,
    ``decision_type``, ``fields``, ``substrate_notes``) so the
    placeholder handlers and the bundle writer can exercise the
    same code paths they'd see against real corpus records.

    Used only when no ``--ocid-list`` is provided. The OCIDs are
    synthetic (``stub-ocid-000`` etc.) — explicitly not real
    corpus OCIDs so a dry-run can never be confused with a real
    record's pass.
    """
    return [
        {
            "ocid": f"stub-ocid-{i:03d}",
            "decision_type": "procurement_decision",
            "fields": {
                "buyer_country": "stub",
                "tender_value": 0,
            },
            "substrate_notes": {},
            "metadata": {"ocid": f"stub-ocid-{i:03d}"},
        }
        for i in range(count)
    ]


def _load_records_from_ocid_list(path: Path) -> list[dict[str, Any]]:
    """Read an OCID list and return stub records for each.

    Foundation behaviour: only the OCID list itself is consumed; the
    placeholder handlers do not need real substrate. Later packages
    (E3-002 onward) will replace this with a substrate-loader that
    pulls real corpus records from the frozen E1 archive.

    The OCID list format is the same one E3-007 will emit at
    ``planning/diagnostic_subset.json``: a JSON array of objects with
    an ``ocid`` field, or a plain JSON array of OCID strings.
    """
    if not path.exists():
        raise FileNotFoundError(f"OCID list not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        raise ValueError(
            f"OCID list at {path} must be a JSON array; got {type(data).__name__}"
        )
    ocids: list[str] = []
    for entry in data:
        if isinstance(entry, str):
            ocids.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("ocid"), str):
            ocids.append(entry["ocid"])
        else:
            raise ValueError(
                f"OCID list entries must be strings or objects with an "
                f"'ocid' field; got {entry!r}"
            )
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meshqu_runner.cli",
        description="Arm-aware E3 runner. Dispatches a single arm against the record set.",
    )
    parser.add_argument(
        "--arm",
        default="arm_a",
        choices=list(ARM_NAMES),
        help="Which arm to dispatch. Defaults to arm_a for smoke probes.",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=None,
        help=(
            "Generate N synthetic stub records (no real OCIDs). "
            "Mutually exclusive with --ocid-list. Defaults to 1 when "
            "neither is provided."
        ),
    )
    parser.add_argument(
        "--ocid-list",
        type=Path,
        default=None,
        help=(
            "Path to a JSON array of OCIDs (or objects with an 'ocid' "
            "field) to evaluate. Replaces --records."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Override the arm's default model_id. Lands in the receipt's "
            "integrity payload as `model_id`; sampling block falls back "
            "to the arm profile's default."
        ),
    )
    parser.add_argument(
        "--policy-permutation-seed",
        type=int,
        default=None,
        help=(
            "Integer seed for the policy permutation. REQUIRED when "
            "--arm is a diagnostic arm; rejected for non-diagnostic arms."
        ),
    )
    parser.add_argument(
        "--dry",
        action="store_true",
        help=(
            "Use StubAgent + StubMeshQuClient. Foundation only supports "
            "--dry; live mode lands in subsequent packages."
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Where to write results/runs/<run_id>/. Defaults to <runner>/results.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id; defaults to 'e3-001-dry-<uuid>'.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.dry:
        print(
            "FAIL: E3-001 foundation only supports --dry mode. Live mode "
            "lands in E3-002..006.",
            file=sys.stderr,
        )
        return 2

    if args.records is not None and args.ocid_list is not None:
        print(
            "FAIL: --records and --ocid-list are mutually exclusive.",
            file=sys.stderr,
        )
        return 2

    # Load record set
    if args.ocid_list is not None:
        records: list[dict[str, Any]] = _load_records_from_ocid_list(args.ocid_list)
    else:
        count = args.records if args.records is not None else 1
        records = _synthetic_stub_records(count)

    runner_dir = Path(__file__).resolve().parent.parent
    repo_dir = runner_dir.parent.parent  # procurement-context-disambiguation/runner -> repo root
    e3_dir = runner_dir.parent  # procurement-context-disambiguation/
    results_dir = args.results_dir if args.results_dir else e3_dir / "results"
    run_id = args.run_id or f"e3-001-dry-{uuid.uuid4()}"
    run_dir = results_dir / "runs" / run_id

    config = RunConfig(
        run_id=run_id,
        run_phase="dry-run",
        repo_dir=repo_dir,
        run_dir=run_dir,
        arm_name=args.arm,
        policy_snapshot_path=None,
        policy_permutation_seed=args.policy_permutation_seed,
        model_id_override=args.model,
    )

    summary = run_arm(
        config=config,
        records=records,
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )

    print(
        f"OK: dispatched arm={args.arm} over {len(records)} record(s); "
        f"wrote {len(summary.outcomes)} bundle(s) to {run_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
