#!/usr/bin/env python3
"""E3-010 — Smoke run validator.

Walks a smoke run directory (the output of ``smoke_e3.py``) and, for
every bundle:

  1. Asserts the per-arm integrity markers in the canonical-JSON
     ``context_fields_canonical_json`` blob match the locked matrix
     (``EXPECTED_MARKERS_BY_ARM`` below). These are the seven
     E3-specific fields ``arms.inject_arm_fields`` injects into
     ``context.fields`` and which MeshQu binds into the receipt's
     ``integrity_hash``.

  2. For LIVE bundles (``is_stub: false``), verifies the v2 Ed25519
     signature against the experiment-tenant pinned public key
     (``meshqu-experiment-procurement-2026-05``). Reuses the canonical-
     JSON v2 signing-envelope reconstruction from
     ``@meshqu/core``'s ``buildReceiptV2EnvelopeBytes`` (mirrored
     here in Python — same byte order, same key set).

  3. For STUB bundles (``is_stub: true``), skips the signature check
     but still asserts the integrity markers. Stub bundles never
     verify cryptographically — they're produced only by ``--dry``
     runs of ``smoke_e3.py`` (for the PR's mock tests) and would not
     appear in a live smoke output. The verifier flags any stub
     bundles encountered as informational, not a failure, so the
     ``--dry`` end-to-end test path can still pass through the
     verifier and validate the marker assertions.

## Decision rules (per E3-010 package spec)

- **Stop on first verifier failure.** The smoke is small; integrity
  failures must surface immediately rather than be lost in a long
  log. The script returns non-zero on the first failing bundle with
  a stderr summary describing the failure mode (missing marker,
  wrong marker value, missing signature, signature invalid, schema
  mismatch).
- **All 14 must pass.** A live smoke run produces exactly 14
  bundles across the six arm subdirs. The verifier asserts the
  count and the matrix.

## Usage

    python3 scripts/verify_smoke_e3.py results/runs/smoke-<timestamp>-Z/
    python3 scripts/verify_smoke_e3.py results/runs/smoke-<timestamp>-Z/ --json
    python3 scripts/verify_smoke_e3.py results/runs/smoke-<timestamp>-Z/ --allow-stub

The ``--allow-stub`` flag is implicit when *every* bundle in the run
dir is a stub (i.e., a ``--dry`` smoke run). It's also explicit for
tests that want to assert the verifier accepts stub bundles when
their markers are correct.

## Why not just call @meshqu/verifier

The published CLI verifier expects a raw receipt JSON of shape
``{context, result}`` or ``{context, integrity_hash}``. The smoke
bundle is a wrapper around the receipt-issued fields the runner
persisted plus the canonical-JSON ``fields`` bytes the runner sent to
MeshQu. ``@meshqu/verifier`` can't be invoked directly on a bundle
without reconstructing the full DecisionContext. So we do offline
verification in Python using the same canonical-JSON contract that
@meshqu/core's signing envelope encodes.

This mirrors the E2 ``verify_smoke_bundles.py`` pattern (which iterates
the E2-shaped ``L0..L4 + diagnostic`` layout). The E3 verifier shares
the trusted-keys table + envelope reconstruction logic; the bundle
walker is rewritten for the arm-subdir layout (six arms, not five
levels). See the PR body for the reuse decision.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap (mirrors smoke_e3.py — let the script run from any cwd)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))


# ---------------------------------------------------------------------------
# Expected integrity markers per arm — locked from the master plan
# matrix. The verifier's central assertion is "every bundle's
# context_fields_canonical_json carries these exact values for its
# arm." Any drift → FAIL with the specific mismatch reported.
# ---------------------------------------------------------------------------

EXPECTED_MARKERS_BY_ARM: dict[str, dict[str, Any]] = {
    "arm_a": {
        "l3_arm": "A",
        "nudge_excised": False,
        "model_id": "gpt-5.4-2026-03-05",
        "diagnostic": False,
        "policy_permutation_seed": None,
    },
    "arm_b": {
        "l3_arm": "B",
        "nudge_excised": False,
        "model_id": "gpt-5.4-2026-03-05",
        "diagnostic": False,
        "policy_permutation_seed": None,
    },
    "arm_c": {
        "l3_arm": "C",
        "nudge_excised": False,
        "model_id": "gpt-5.4-2026-03-05",
        "diagnostic": False,
        "policy_permutation_seed": None,
    },
    "l4_without_nudge": {
        "l3_arm": None,
        "nudge_excised": True,
        "model_id": "gpt-5.4-2026-03-05",
        "diagnostic": False,
        "policy_permutation_seed": None,
    },
    "diagnostic_primary": {
        "l3_arm": None,
        "nudge_excised": False,
        "model_id": "gpt-5.4-2026-03-05",
        "diagnostic": True,
        "policy_permutation_seed": 0,
    },
    "diagnostic_claude": {
        "l3_arm": None,
        "nudge_excised": False,
        "model_id": "claude-opus-4-7",
        "diagnostic": True,
        "policy_permutation_seed": 0,
    },
}

ARM_SUBDIRS: tuple[str, ...] = tuple(EXPECTED_MARKERS_BY_ARM.keys())

EXPECTED_RECEIPT_COUNTS: dict[str, int] = {
    "arm_a": 3,
    "arm_b": 3,
    "arm_c": 3,
    "l4_without_nudge": 3,
    "diagnostic_primary": 1,
    "diagnostic_claude": 1,
}

EXPECTED_TOTAL_RECEIPTS = sum(EXPECTED_RECEIPT_COUNTS.values())


# ---------------------------------------------------------------------------
# Trusted keys — kept in lockstep with apps/meshqu-verify/src/lib/keys.ts.
# Inherited verbatim from E2's verify_smoke_bundles.py (same experiment
# tenant; same key rotation post-R1).
# ---------------------------------------------------------------------------

TRUSTED_KEYS_SPKI_DER_B64: dict[str, str] = {
    "meshqu-experiment-procurement-2026-05": (
        "MCowBQYDK2VwAyEAQKw/FAIkqj9HTt1pDd6WsPUf3gQQz04k2aV8tjRhWCw="
    ),
}

EXPECTED_KID = "meshqu-experiment-procurement-2026-05"


# ---------------------------------------------------------------------------
# Canonical JSON — matches @meshqu/core's canonical-json.ts contract:
# alphabetic key order, no whitespace, ensure_ascii=False, UTF-8 bytes.
# ---------------------------------------------------------------------------


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_signing_envelope_bytes(
    *,
    integrity_hash: str,
    signature_kid: str,
    signature_algorithm: str,
    timestamp: str,
    policy_snapshot_digest: str,
    evidence_manifest_digest: str | None,
) -> bytes:
    """Reconstruct the v2 signing envelope per ``@meshqu/core``'s
    ``buildReceiptV2EnvelopeBytes``. Same byte order; same keys."""
    payload = {
        "evidence_manifest_digest": evidence_manifest_digest,
        "integrity_hash": integrity_hash,
        "policy_snapshot_digest": policy_snapshot_digest,
        "receipt_schema_version": 2,
        "signature_algorithm": signature_algorithm,
        "signature_kid": signature_kid,
        "timestamp": timestamp,
    }
    return canonical_json(payload).encode("utf-8")


# ---------------------------------------------------------------------------
# Ed25519 signature verification
# ---------------------------------------------------------------------------


def verify_ed25519_signature(
    *,
    envelope_bytes: bytes,
    signature_b64url: str,
    public_key_spki_der_b64: str,
) -> tuple[bool, str]:
    """Verify an Ed25519 signature in base64url over ``envelope_bytes``
    using the supplied SPKI-DER base64 public key. Returns
    ``(ok, detail)``."""
    pad = "=" * ((4 - len(signature_b64url) % 4) % 4)
    try:
        sig_bytes = base64.urlsafe_b64decode(signature_b64url + pad)
    except Exception as exc:
        return False, f"signature base64url decode failed: {exc}"

    try:
        pub_der = base64.b64decode(public_key_spki_der_b64)
    except Exception as exc:
        return False, f"public-key base64 decode failed: {exc}"

    try:
        from cryptography.hazmat.primitives.serialization import load_der_public_key
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        return False, f"cryptography library missing: {exc}"

    try:
        public_key = load_der_public_key(pub_der)
    except Exception as exc:
        return False, f"public-key SPKI parse failed: {exc}"

    try:
        public_key.verify(sig_bytes, envelope_bytes)
    except InvalidSignature:
        return False, "signature invalid"
    except Exception as exc:
        return False, f"verify raised: {exc}"

    return True, "ok"


# ---------------------------------------------------------------------------
# Per-bundle verification
# ---------------------------------------------------------------------------


@dataclass
class BundleReport:
    arm_name: str
    bundle_path: Path
    decision_id: str | None = None
    ocid: str | None = None
    is_stub: bool = False
    passed: bool = False
    errors: list[str] = field(default_factory=list)


def _read_bundle(bundle_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with bundle_path.open("r", encoding="utf-8") as fp:
            return json.load(fp), None
    except json.JSONDecodeError as exc:
        return None, f"JSON decode failed: {exc}"


def _check_markers(
    *,
    fields: dict[str, Any],
    arm_name: str,
) -> list[str]:
    """Return a list of per-marker mismatch messages (empty when all
    markers match expectation)."""
    expected = EXPECTED_MARKERS_BY_ARM[arm_name]
    mismatches: list[str] = []
    for key, want in expected.items():
        if key not in fields:
            mismatches.append(f"missing marker {key!r} (expected {want!r})")
            continue
        got = fields[key]
        if got != want:
            mismatches.append(
                f"marker {key!r} mismatch: got {got!r}, expected {want!r}"
            )
    # Also assert prereg_tag — present in every E3 receipt regardless of arm.
    if fields.get("prereg_tag") != "v0.3-predictions-locked":
        mismatches.append(
            f"marker 'prereg_tag' mismatch: got {fields.get('prereg_tag')!r}, "
            "expected 'v0.3-predictions-locked'"
        )
    return mismatches


def verify_bundle(bundle_path: Path, arm_name: str) -> BundleReport:
    """Verify one bundle. Returns a BundleReport with ``passed`` set
    and any error strings populated."""
    report = BundleReport(arm_name=arm_name, bundle_path=bundle_path)
    bundle, decode_err = _read_bundle(bundle_path)
    if bundle is None:
        report.errors.append(decode_err or "unknown JSON decode error")
        return report

    report.is_stub = bool(bundle.get("is_stub"))
    report.decision_id = bundle.get("decision_id")
    report.ocid = bundle.get("ocid")

    # 1. Schema sanity
    bundle_arm = bundle.get("arm_name")
    if bundle_arm != arm_name:
        report.errors.append(
            f"bundle arm_name {bundle_arm!r} does not match dir {arm_name!r}"
        )
        return report

    # 2. Markers
    canonical_str = bundle.get("context_fields_canonical_json")
    if not isinstance(canonical_str, str):
        report.errors.append("bundle missing context_fields_canonical_json")
        return report
    try:
        fields = json.loads(canonical_str)
    except json.JSONDecodeError as exc:
        report.errors.append(f"context_fields_canonical_json decode failed: {exc}")
        return report
    marker_errs = _check_markers(fields=fields, arm_name=arm_name)
    if marker_errs:
        report.errors.extend(marker_errs)
        return report

    # 3. Signature (LIVE bundles only)
    if not report.is_stub:
        sig_err = _verify_live_signature(bundle)
        if sig_err:
            report.errors.append(sig_err)
            return report

    report.passed = True
    return report


def _verify_live_signature(bundle: dict[str, Any]) -> str | None:
    """Verify the v2 Ed25519 signature on a live bundle. Returns an
    error string on failure, ``None`` on pass."""
    receipt = bundle.get("receipt") or {}
    signature = receipt.get("signature")
    sig_kid = receipt.get("signature_kid")
    if not signature or not sig_kid:
        return (
            f"missing signature or signature_kid "
            f"(signature={'present' if signature else 'absent'}, "
            f"kid={sig_kid!r})"
        )
    if sig_kid != EXPECTED_KID:
        return f"unexpected signature_kid {sig_kid!r} (expected {EXPECTED_KID!r})"
    public_key_b64 = TRUSTED_KEYS_SPKI_DER_B64.get(sig_kid)
    if public_key_b64 is None:
        return f"no trusted key registered for kid {sig_kid!r}"

    integrity_hash = receipt.get("integrity_hash")
    timestamp = receipt.get("timestamp")
    policy_snapshot_digest = receipt.get("policy_snapshot_digest")
    if not (integrity_hash and timestamp and policy_snapshot_digest):
        return (
            "v2 signing envelope requires integrity_hash, timestamp, "
            "and policy_snapshot_digest in the receipt"
        )

    envelope_bytes = build_signing_envelope_bytes(
        integrity_hash=integrity_hash,
        signature_kid=sig_kid,
        signature_algorithm="ed25519",
        timestamp=timestamp,
        policy_snapshot_digest=policy_snapshot_digest,
        evidence_manifest_digest=None,
    )
    ok, detail = verify_ed25519_signature(
        envelope_bytes=envelope_bytes,
        signature_b64url=signature,
        public_key_spki_der_b64=public_key_b64,
    )
    if not ok:
        return f"signature verification failed: {detail}"
    return None


# ---------------------------------------------------------------------------
# Run-dir walker
# ---------------------------------------------------------------------------


def iter_arm_bundles(run_dir: Path) -> list[tuple[str, Path]]:
    """Yield ``(arm_name, bundle_path)`` for every bundle under the
    six expected arm subdirs. Order: arm_name order from
    ``ARM_SUBDIRS``, then sorted bundle filenames within each arm."""
    pairs: list[tuple[str, Path]] = []
    for arm_name in ARM_SUBDIRS:
        subdir = run_dir / arm_name
        if not subdir.exists():
            continue
        for bundle_path in sorted(subdir.glob("*.bundle.json")):
            pairs.append((arm_name, bundle_path))
    return pairs


@dataclass
class RunVerification:
    run_dir: Path
    reports: list[BundleReport] = field(default_factory=list)
    all_stubs: bool = False
    passed_count: int = 0
    failed_count: int = 0
    first_failure: BundleReport | None = None

    def update_from_report(self, report: BundleReport, stop_on_failure: bool) -> bool:
        """Add report; return True if we should stop iterating (i.e.
        failure + stop_on_failure)."""
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
    """Verify every bundle under ``run_dir`` against the smoke matrix.

    ``allow_stub`` is implicit when every bundle's ``is_stub`` is
    True; explicit otherwise. A mixed live/stub run is treated as
    failure unless ``allow_stub=True`` (stub bundles in a smoke
    intended to be live indicate a configuration bug — see the
    package spec's stop conditions).
    """
    result = RunVerification(run_dir=run_dir)

    pairs = iter_arm_bundles(run_dir)
    if not pairs:
        # No bundles found — synthesise a single failure report.
        fake = BundleReport(arm_name="(none)", bundle_path=run_dir)
        fake.errors.append(f"no bundles found under {run_dir}")
        result.update_from_report(fake, stop_on_failure=True)
        return result

    # Pre-scan to decide implicit-stub-allow.
    pre_stub_flags = []
    for arm_name, bundle_path in pairs:
        bundle, _err = _read_bundle(bundle_path)
        pre_stub_flags.append(bool(bundle.get("is_stub")) if bundle else False)
    result.all_stubs = all(pre_stub_flags) if pre_stub_flags else False

    effective_allow_stub = allow_stub or result.all_stubs

    # Per-arm count check (deferred until we've walked all bundles).
    counts_by_arm: dict[str, int] = {arm: 0 for arm in ARM_SUBDIRS}

    for arm_name, bundle_path in pairs:
        report = verify_bundle(bundle_path, arm_name)
        counts_by_arm[arm_name] = counts_by_arm.get(arm_name, 0) + 1
        if report.is_stub and not effective_allow_stub:
            # Add a synthetic error so the run is marked failed.
            if not any("stub bundle" in e for e in report.errors):
                report.passed = False
                report.errors.append(
                    "stub bundle (is_stub=true) in a non-stub-allowed run; "
                    "use --allow-stub or run a live smoke"
                )
        if result.update_from_report(report, stop_on_first_failure):
            return result

    # Count assertion. Only fired if we got this far without an
    # earlier per-bundle stop.
    for arm_name, expected in EXPECTED_RECEIPT_COUNTS.items():
        actual = counts_by_arm.get(arm_name, 0)
        if actual != expected:
            fake = BundleReport(arm_name=arm_name, bundle_path=run_dir / arm_name)
            fake.errors.append(
                f"arm {arm_name!r} produced {actual} receipts; "
                f"expected {expected} (per the smoke matrix)"
            )
            result.update_from_report(fake, stop_on_failure=stop_on_first_failure)
            if stop_on_first_failure:
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

    for r in result.reports:
        status = "PASS" if r.passed else "FAIL"
        stub_tag = " [stub]" if r.is_stub else ""
        print(
            f"{status}{stub_tag}  {r.arm_name:>20}  "
            f"{(r.ocid or '?'):<60}  {r.bundle_path.name}"
        )
        if r.errors:
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
        prog="verify_smoke_e3.py",
        description=(
            "Verify every bundle under an E3-010 smoke run dir: "
            "assert per-arm integrity markers + (for live bundles) "
            "the Ed25519 signature against the experiment-tenant key."
        ),
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help=(
            "Smoke run directory. Either an absolute path or a path "
            "relative to <runner>/results/runs/. Must contain the six "
            "arm subdirs."
        ),
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable status lines.",
    )
    parser.add_argument(
        "--allow-stub",
        action="store_true",
        help=(
            "Treat stub bundles as PASS even when not all bundles are "
            "stubs. Implicitly enabled when every bundle is_stub=true "
            "(a --dry smoke run). Use this only when intentionally "
            "verifying a mixed run."
        ),
    )
    parser.add_argument(
        "--no-stop",
        action="store_true",
        help=(
            "Continue past the first failing bundle. Default is to "
            "stop on first failure (per E3-010 decision rule)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_dir: Path = args.run_dir
    if not run_dir.is_absolute() and not run_dir.exists():
        # Try as a path relative to <runner>/results/runs/
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
