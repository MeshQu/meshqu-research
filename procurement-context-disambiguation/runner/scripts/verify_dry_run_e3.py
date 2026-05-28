#!/usr/bin/env python3
"""E3-011 — Dry-run validator.

Walks a dry-run directory (the output of ``dry_run_e3.py``) and, for
every bundle:

  1. Asserts the per-arm integrity markers in the canonical-JSON
     ``context_fields_canonical_json`` blob match the locked matrix
     (``EXPECTED_MARKERS_BY_ARM`` below). Same matrix as the smoke
     verifier — inherits ``verify_smoke_e3``'s table verbatim so
     drift between the two verifiers is impossible.

  2. For LIVE bundles (``is_stub: false``), verifies the v2 Ed25519
     signature against the experiment-tenant pinned public key
     (``meshqu-experiment-procurement-2026-05``). Reuses the canonical-
     JSON signing-envelope reconstruction from ``verify_smoke_e3``.

  3. For STUB bundles (``is_stub: true``), skips the signature check
     but still asserts the integrity markers (same posture as the
     smoke verifier).

  4. **Aggregate completeness** (the dry-run-specific addition over
     the smoke verifier): asserts every OCID at positions 0..29 of
     ``planning/diagnostic_subset.json`` appears in every main-arm
     subdir, and every OCID at positions 0..9 appears in both
     diagnostic arm subdirs. A single missing OCID → FAIL. Stops on
     first failure (same decision rule as the smoke verifier, scaled
     here).

## Decision rules (per E3-011 package spec + inherited from E3-010)

- **Stop on first verifier failure** (unless ``--no-stop``).
- **All 140 must pass.** The matrix is fixed: 4 main arms × 30 + 2
  diagnostic arms × 10.

## Usage

    python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/
    python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/ --json
    python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/ --allow-stub
    python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/ --no-stop

The ``--allow-stub`` flag is implicit when every bundle in the run dir
is a stub (a ``--dry`` driver run). Explicit otherwise.

## Why a separate file vs scaling the smoke verifier in place

The smoke verifier hard-codes ``EXPECTED_RECEIPT_COUNTS`` at the smoke
matrix (3 / 3 / 3 / 3 / 1 / 1). Trying to make a single verifier serve
both runs adds an inferred-count argument and a count-mode-switch
branch that would obscure the contract. The dry-run verifier reuses
every primitive that doesn't depend on the matrix (markers,
signature, envelope, trusted keys) but reimplements the run-dir
walker for clarity.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — let the script run from any cwd via `python scripts/...`
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# Inherit the verifier primitives that are matrix-independent. The
# smoke verifier owns the canonical contract; the dry-run verifier
# scales it. Importing keeps the trusted-keys table single-sourced —
# if a key rotation lands in E3-011's window, only the smoke verifier
# needs an edit and this script picks it up.
from verify_smoke_e3 import (  # noqa: E402
    ARM_SUBDIRS,
    EXPECTED_KID,
    EXPECTED_MARKERS_BY_ARM,
    TRUSTED_KEYS_SPKI_DER_B64,
    BundleReport,
    _check_markers,
    _read_bundle,
    _verify_live_signature,
    build_signing_envelope_bytes,
    canonical_json,
    verify_bundle,
    verify_ed25519_signature,
)


# ---------------------------------------------------------------------------
# Dry-run matrix counts — independent from the smoke verifier's table.
# ---------------------------------------------------------------------------

EXPECTED_RECEIPT_COUNTS: dict[str, int] = {
    "arm_a": 30,
    "arm_b": 30,
    "arm_c": 30,
    "l4_without_nudge": 30,
    "diagnostic_primary": 10,
    "diagnostic_claude": 10,
}

EXPECTED_TOTAL_RECEIPTS = sum(EXPECTED_RECEIPT_COUNTS.values())  # 140

MAIN_ARMS: tuple[str, ...] = ("arm_a", "arm_b", "arm_c", "l4_without_nudge")
DIAGNOSTIC_ARMS: tuple[str, ...] = ("diagnostic_primary", "diagnostic_claude")

DRY_RUN_MAIN_OCID_COUNT = 30
DRY_RUN_DIAGNOSTIC_OCID_COUNT = 10


# ---------------------------------------------------------------------------
# Run-dir walker
# ---------------------------------------------------------------------------


def iter_arm_bundles(run_dir: Path) -> list[tuple[str, Path]]:
    """Yield ``(arm_name, bundle_path)`` for every bundle under the six
    expected arm subdirs. Order: ``ARM_SUBDIRS`` order (inherited from
    the smoke verifier), then sorted bundle filenames within each
    arm."""
    pairs: list[tuple[str, Path]] = []
    for arm_name in ARM_SUBDIRS:
        subdir = run_dir / arm_name
        if not subdir.exists():
            continue
        for bundle_path in sorted(subdir.glob("*.bundle.json")):
            pairs.append((arm_name, bundle_path))
    return pairs


# ---------------------------------------------------------------------------
# Aggregate completeness — the dry-run-specific addition.
# ---------------------------------------------------------------------------


def _load_locked_subset_ocids() -> list[str]:
    """Load the locked diagnostic subset from
    ``planning/diagnostic_subset.json``. The verifier's completeness
    check reads positions 0..29 (main arms) and 0..9 (diagnostic arms)
    of this list, so the verifier is decoupled from the driver's
    runtime subset selection — even if a future driver mis-slices,
    the verifier catches the drift."""
    # The subset file lives at procurement-context-disambiguation/
    # planning/diagnostic_subset.json. _RUNNER_DIR.parent is the E3
    # subproject root.
    subset_path = (
        _RUNNER_DIR.parent / "planning" / "diagnostic_subset.json"
    )
    with subset_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    ocids = payload.get("ocids")
    if not isinstance(ocids, list):
        raise RuntimeError(
            f"diagnostic_subset.json malformed: expected 'ocids' list, "
            f"got {type(ocids).__name__}"
        )
    return list(ocids)


def assert_completeness(
    *,
    bundles_by_arm: dict[str, list[Path]],
    expected_main_ocids: list[str],
    expected_diagnostic_ocids: list[str],
) -> list[BundleReport]:
    """Return a list of synthetic-failure reports — empty when every
    main-subset OCID appears in every main arm and every diagnostic-
    subset OCID appears in both diagnostic arms. One report per
    missing OCID-arm pair so the first-failure log is precise."""
    failures: list[BundleReport] = []
    main_set = set(expected_main_ocids)
    diag_set = set(expected_diagnostic_ocids)

    for arm_name in MAIN_ARMS:
        bundles = bundles_by_arm.get(arm_name, [])
        present: set[str] = set()
        for bundle_path in bundles:
            bundle, _err = _read_bundle(bundle_path)
            if bundle is None:
                continue
            ocid = bundle.get("ocid")
            if isinstance(ocid, str):
                present.add(ocid)
        missing = main_set - present
        for ocid in sorted(missing):
            report = BundleReport(
                arm_name=arm_name,
                bundle_path=Path(arm_name) / f"(missing-ocid:{ocid})",
            )
            report.ocid = ocid
            report.errors.append(
                f"arm {arm_name!r}: locked main-subset OCID {ocid!r} "
                "is missing from this arm's subdir — silent drop"
            )
            failures.append(report)

    for arm_name in DIAGNOSTIC_ARMS:
        bundles = bundles_by_arm.get(arm_name, [])
        present = set()
        for bundle_path in bundles:
            bundle, _err = _read_bundle(bundle_path)
            if bundle is None:
                continue
            ocid = bundle.get("ocid")
            if isinstance(ocid, str):
                present.add(ocid)
        missing = diag_set - present
        for ocid in sorted(missing):
            report = BundleReport(
                arm_name=arm_name,
                bundle_path=Path(arm_name) / f"(missing-ocid:{ocid})",
            )
            report.ocid = ocid
            report.errors.append(
                f"arm {arm_name!r}: locked diagnostic-subset OCID {ocid!r} "
                "is missing from this arm's subdir — silent drop"
            )
            failures.append(report)

    return failures


# ---------------------------------------------------------------------------
# Run verification
# ---------------------------------------------------------------------------


@dataclass
class RunVerification:
    run_dir: Path
    reports: list[BundleReport] = field(default_factory=list)
    all_stubs: bool = False
    passed_count: int = 0
    failed_count: int = 0
    first_failure: BundleReport | None = None
    expected_main_ocids: list[str] = field(default_factory=list)
    expected_diagnostic_ocids: list[str] = field(default_factory=list)

    def update_from_report(self, report: BundleReport, stop_on_failure: bool) -> bool:
        """Add report; return True if we should stop iterating."""
        self.reports.append(report)
        if report.passed:
            self.passed_count += 1
            return False
        self.failed_count += 1
        if self.first_failure is None:
            self.first_failure = report
        return stop_on_failure


def verify_run(
    run_dir: Path,
    *,
    allow_stub: bool = False,
    stop_on_first_failure: bool = True,
) -> RunVerification:
    """Verify every bundle under ``run_dir`` against the dry-run matrix.

    Pre-scans bundles to decide the implicit-stub-allow + collect per-
    arm bundle lists for the completeness check. Per-bundle verifier
    re-reads the bundle (same posture as the smoke verifier — keeps
    each report independent and the file open scoped tight).
    """
    result = RunVerification(run_dir=run_dir)

    # Load the locked subset's OCID positions 0..29 / 0..9 — the
    # verifier's completeness expectation. Decoupled from the driver:
    # the driver could mis-slice and the verifier still catches it.
    try:
        all_locked_ocids = _load_locked_subset_ocids()
    except Exception as exc:
        fake = BundleReport(arm_name="(none)", bundle_path=run_dir)
        fake.errors.append(
            f"failed to load planning/diagnostic_subset.json: {exc}"
        )
        result.update_from_report(fake, stop_on_failure=True)
        return result

    if len(all_locked_ocids) < DRY_RUN_MAIN_OCID_COUNT:
        fake = BundleReport(arm_name="(none)", bundle_path=run_dir)
        fake.errors.append(
            f"locked subset has {len(all_locked_ocids)} OCIDs; "
            f"dry-run verifier requires ≥ {DRY_RUN_MAIN_OCID_COUNT}"
        )
        result.update_from_report(fake, stop_on_failure=True)
        return result

    result.expected_main_ocids = all_locked_ocids[:DRY_RUN_MAIN_OCID_COUNT]
    result.expected_diagnostic_ocids = all_locked_ocids[
        :DRY_RUN_DIAGNOSTIC_OCID_COUNT
    ]

    pairs = iter_arm_bundles(run_dir)
    if not pairs:
        fake = BundleReport(arm_name="(none)", bundle_path=run_dir)
        fake.errors.append(f"no bundles found under {run_dir}")
        result.update_from_report(fake, stop_on_failure=True)
        return result

    # Pre-scan: collect per-arm bundle lists for the completeness check
    # + decide implicit-stub-allow.
    bundles_by_arm: dict[str, list[Path]] = {arm: [] for arm in ARM_SUBDIRS}
    pre_stub_flags: list[bool] = []
    for arm_name, bundle_path in pairs:
        bundles_by_arm[arm_name].append(bundle_path)
        bundle, _err = _read_bundle(bundle_path)
        pre_stub_flags.append(bool(bundle.get("is_stub")) if bundle else False)

    result.all_stubs = all(pre_stub_flags) if pre_stub_flags else False
    effective_allow_stub = allow_stub or result.all_stubs

    # Per-bundle verification.
    counts_by_arm: dict[str, int] = {arm: 0 for arm in ARM_SUBDIRS}
    for arm_name, bundle_path in pairs:
        report = verify_bundle(bundle_path, arm_name)
        counts_by_arm[arm_name] = counts_by_arm.get(arm_name, 0) + 1
        if report.is_stub and not effective_allow_stub:
            if not any("stub bundle" in e for e in report.errors):
                report.passed = False
                report.errors.append(
                    "stub bundle (is_stub=true) in a non-stub-allowed "
                    "run; use --allow-stub or run a live dry-run"
                )
        if result.update_from_report(report, stop_on_first_failure):
            return result

    # Per-arm count assertion.
    for arm_name, expected in EXPECTED_RECEIPT_COUNTS.items():
        actual = counts_by_arm.get(arm_name, 0)
        if actual != expected:
            fake = BundleReport(arm_name=arm_name, bundle_path=run_dir / arm_name)
            fake.errors.append(
                f"arm {arm_name!r} produced {actual} receipts; "
                f"expected {expected} (per the dry-run matrix)"
            )
            result.update_from_report(fake, stop_on_failure=stop_on_first_failure)
            if stop_on_first_failure:
                return result

    # Aggregate completeness — every locked OCID present in every
    # applicable arm. This is the dry-run-specific addition.
    completeness_failures = assert_completeness(
        bundles_by_arm=bundles_by_arm,
        expected_main_ocids=result.expected_main_ocids,
        expected_diagnostic_ocids=result.expected_diagnostic_ocids,
    )
    for failure in completeness_failures:
        if result.update_from_report(failure, stop_on_failure=stop_on_first_failure):
            return result

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_run_summary(result: RunVerification, *, as_json: bool) -> None:
    total = result.passed_count + result.failed_count
    if as_json:
        payload = {
            "run_dir": str(result.run_dir),
            "total": total,
            "passed": result.passed_count,
            "failed": result.failed_count,
            "all_stubs": result.all_stubs,
            "expected_main_ocids": list(result.expected_main_ocids),
            "expected_diagnostic_ocids": list(result.expected_diagnostic_ocids),
            "reports": [
                {
                    "arm_name": r.arm_name,
                    "bundle_path": str(r.bundle_path),
                    "decision_id": r.decision_id,
                    "ocid": r.ocid,
                    "is_stub": r.is_stub,
                    "passed": r.passed,
                    "errors": list(r.errors),
                }
                for r in result.reports
            ],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return

    # Compact per-report line. Don't print 140 lines if everyone passed —
    # only print FAILures + final tally on a clean run. (The smoke
    # verifier printed every line because it was 14; at 140 the noise
    # eats the operator's eye.)
    if result.failed_count == 0:
        # Single-line per-arm receipt count check.
        counts_by_arm: dict[str, int] = {arm: 0 for arm in ARM_SUBDIRS}
        for r in result.reports:
            counts_by_arm[r.arm_name] = counts_by_arm.get(r.arm_name, 0) + 1
        for arm_name in ARM_SUBDIRS:
            print(
                f"PASS  {arm_name:>20}  {counts_by_arm.get(arm_name, 0):>3} receipts"
            )
    else:
        for r in result.reports:
            if r.passed:
                continue
            stub_tag = " [stub]" if r.is_stub else ""
            print(
                f"FAIL{stub_tag}  {r.arm_name:>20}  "
                f"{(r.ocid or '?'):<60}  {r.bundle_path.name}"
            )
            for err in r.errors:
                print(f"        - {err}")
    print()
    print(
        f"Total: {total}   PASS: {result.passed_count}   FAIL: {result.failed_count}   "
        f"{'(all stubs)' if result.all_stubs else '(live)'}"
    )
    if result.first_failure is not None:
        print()
        print("First failure:", file=sys.stderr)
        print(f"  arm:    {result.first_failure.arm_name}", file=sys.stderr)
        print(f"  bundle: {result.first_failure.bundle_path}", file=sys.stderr)
        for err in result.first_failure.errors:
            print(f"  error:  {err}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_dry_run_e3.py",
        description=(
            "Verify every bundle under an E3-011 dry-run dir: assert "
            "per-arm integrity markers, the Ed25519 signature (live "
            "bundles), the per-arm receipt count, and aggregate "
            "OCID completeness against the locked subset."
        ),
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help=(
            "Dry-run directory. Either an absolute path or a path "
            "relative to <runner>/results/runs/. Must contain the six "
            "arm subdirs."
        ),
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of status lines.",
    )
    parser.add_argument(
        "--allow-stub",
        action="store_true",
        help=(
            "Treat stub bundles as PASS even when not all bundles are "
            "stubs. Implicitly enabled when every bundle is_stub=true "
            "(a --dry driver run). Use this only when intentionally "
            "verifying a mixed run."
        ),
    )
    parser.add_argument(
        "--no-stop",
        action="store_true",
        help=(
            "Continue past the first failing bundle. Default is to "
            "stop on first failure (per E3-010 / E3-011 decision rule)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_dir: Path = args.run_dir
    if not run_dir.is_absolute() and not run_dir.exists():
        candidate = _RUNNER_DIR.parent / "results" / "runs" / run_dir
        if candidate.exists():
            run_dir = candidate
    if not run_dir.exists():
        print(f"FAIL: run directory not found: {run_dir}", file=sys.stderr)
        return 2

    result = verify_run(
        run_dir,
        allow_stub=args.allow_stub,
        stop_on_first_failure=not args.no_stop,
    )
    _print_run_summary(result, as_json=args.as_json)
    return 0 if result.failed_count == 0 else 1


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
