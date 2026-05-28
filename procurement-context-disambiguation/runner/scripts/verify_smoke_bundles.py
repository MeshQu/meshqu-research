#!/usr/bin/env python3
"""Offline cryptographic verifier for E2-007 smoke bundles.

For each bundle under `<run_dir>/{L0,L1,L2,L3,L4,diagnostic}/`, this
script reconstructs the v2 signing envelope from the receipt fields
the bundle persisted and verifies the Ed25519 signature against the
bundled experiment-tenant public key. Mirrors what
`@meshqu/verifier` does, but operates on bundle envelopes rather than
raw receipt JSON.

## Why a Python verifier instead of `meshqu-verify`

The published `@meshqu/verifier` CLI expects a receipt JSON of the
shape `{context, result}` or `{context, integrity_hash}`. Our E2
bundle is a wrapper around the receipt fields the runner persisted
(plus the canonical `fields` bytes and operational metadata). The
runner deliberately does NOT persist the full DecisionContext
verbatim — only the canonical `fields` bytes (the integrity-hash-
bound subset). The CLI verifier can't be invoked directly on a
bundle without reconstructing the full context, which we can't do
without re-fetching from the API.

What we CAN verify offline from a bundle:

  1. **Ed25519 signature over the v2 signing envelope.** The envelope
     is `canonicalJson({evidence_manifest_digest, integrity_hash,
     policy_snapshot_digest, receipt_schema_version: 2,
     signature_algorithm: 'ed25519', signature_kid, timestamp})` —
     every input field is present in our bundle. A valid signature
     proves the integrity_hash + policy_snapshot_digest + timestamp
     trio was attested by MeshQu's signing key for the experiment
     tenant.

  2. **Signature kid matches the experiment tenant.** Production
     receipts on staging should carry kid
     `meshqu-experiment-procurement-2026-05` — the key the verify.meshqu.com
     web app trusts by default for this tenant.

  3. **(stub bundles only) `is_stub: true` flag visible.** Stub
     bundles are never signed; the verifier treats unsigned bundles
     as FAIL (the smoke MUST run live; an unsigned bundle in the
     smoke directory indicates a configuration bug, not a stub run).

A future tightening would include integrity-hash reverification by
persisting the full DecisionContext (or its context_hash) in the
bundle. Tracked as a follow-up; not in E2-007's scope.

## Trusted keys

Pinned in this script per the v0.2-locked tenant kid
(`meshqu-experiment-procurement-2026-05`). Mirrors the value in
`apps/meshqu-verify/src/lib/keys.ts` (tradequ repo). A divergence
between the two would be a wire-format bug — surface immediately.

## Exit code

  0 — all bundles passed
  1 — any bundle failed verification (signature invalid, missing
       signature, wrong kid, or unparseable bundle)
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Trusted keys — kept in lockstep with apps/meshqu-verify/src/lib/keys.ts.
# ---------------------------------------------------------------------------

TRUSTED_KEYS_SPKI_DER_B64: dict[str, str] = {
    # Experiment tenant key. See E1 decision_log: rotated R1 mid-experiment;
    # the kid here is the post-rotation key, which is what every receipt
    # written after the rotation event carries.
    "meshqu-experiment-procurement-2026-05": (
        "MCowBQYDK2VwAyEAQKw/FAIkqj9HTt1pDd6WsPUf3gQQz04k2aV8tjRhWCw="
    ),
}

EXPECTED_KID = "meshqu-experiment-procurement-2026-05"


# ---------------------------------------------------------------------------
# Canonical-JSON — matches @meshqu/core's canonical-json.ts contract
# (alphabetic key order, no whitespace, ensure_ascii=False, UTF-8 bytes).
# ---------------------------------------------------------------------------


def canonical_json(payload: Any) -> str:
    """sort_keys=True, separators=(',', ':'), ensure_ascii=False."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Signing envelope reconstruction
# ---------------------------------------------------------------------------


def build_signing_envelope_bytes(
    *,
    integrity_hash: str,
    signature_kid: str,
    signature_algorithm: str,
    timestamp: str,
    policy_snapshot_digest: str,
    evidence_manifest_digest: str | None,
) -> bytes:
    """Reconstruct the v2 signing envelope per @meshqu/core's
    `buildReceiptV2EnvelopeBytes`. Alphabetic key order, canonical JSON,
    UTF-8 bytes. THIS is what was signed; the signature verifies over
    these bytes."""
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
# Ed25519 signature verification (stdlib only via cryptography fallback)
# ---------------------------------------------------------------------------


def verify_ed25519_signature(
    *,
    envelope_bytes: bytes,
    signature_b64url: str,
    public_key_spki_der_b64: str,
) -> tuple[bool, str]:
    """Verify an Ed25519 signature in base64url over `envelope_bytes`
    using the supplied SPKI-DER base64-encoded public key.

    Returns (ok, detail).

    Uses `cryptography` (already in the runner's requirements per
    OBS-205). Falls back to `nacl.signing` only if `cryptography` is
    unavailable — the runner env always has the first.
    """
    # Pad base64url and decode
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
# Bundle scan
# ---------------------------------------------------------------------------


BUNDLE_LEVELS = ("L0", "L1", "L2", "L3", "L4", "diagnostic")


def iter_bundles(run_dir: Path):
    """Yield (level_or_diagnostic, bundle_path) for every bundle under
    the standard E2 layout."""
    for subdir_name in BUNDLE_LEVELS:
        subdir = run_dir / subdir_name
        if not subdir.exists():
            continue
        for bundle_path in sorted(subdir.glob("*.bundle.json")):
            yield subdir_name, bundle_path


def verify_bundle(bundle_path: Path) -> tuple[bool, dict[str, Any]]:
    """Return (passed, report)."""
    report: dict[str, Any] = {
        "path": str(bundle_path),
    }
    try:
        with bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)
    except json.JSONDecodeError as exc:
        report["error"] = f"JSON decode failed: {exc}"
        return False, report

    receipt = bundle.get("receipt") or {}
    report["governance_context_level"] = bundle.get("governance_context_level")
    report["ocid"] = bundle.get("ocid")
    report["decision_id"] = bundle.get("decision_id")
    report["integrity_hash"] = receipt.get("integrity_hash")
    report["signature_kid"] = receipt.get("signature_kid")
    report["is_stub"] = bundle.get("is_stub")

    if bundle.get("is_stub"):
        report["error"] = "bundle is_stub=true; live smoke must not produce stub bundles"
        return False, report

    signature = receipt.get("signature")
    sig_kid = receipt.get("signature_kid")
    if not signature or not sig_kid:
        report["error"] = (
            f"missing signature or signature_kid (signature={'present' if signature else 'absent'}, "
            f"kid={sig_kid!r})"
        )
        return False, report

    if sig_kid != EXPECTED_KID:
        report["error"] = f"unexpected signature_kid {sig_kid!r} (expected {EXPECTED_KID!r})"
        return False, report

    public_key_b64 = TRUSTED_KEYS_SPKI_DER_B64.get(sig_kid)
    if public_key_b64 is None:
        report["error"] = f"no trusted key registered for kid {sig_kid!r}"
        return False, report

    integrity_hash = receipt.get("integrity_hash")
    timestamp = receipt.get("timestamp")
    policy_snapshot_digest = receipt.get("policy_snapshot_digest")
    if not (integrity_hash and timestamp and policy_snapshot_digest):
        report["error"] = (
            "v2 signing envelope requires integrity_hash, timestamp, and "
            "policy_snapshot_digest in the receipt"
        )
        return False, report

    # v2 signing algorithm is locked to ed25519. The receipt currently
    # carries no `signature_algorithm` field in our bundle envelope —
    # the v2 product hardcodes 'ed25519'. Re-emit it here exactly as
    # the signer would have.
    envelope_bytes = build_signing_envelope_bytes(
        integrity_hash=integrity_hash,
        signature_kid=sig_kid,
        signature_algorithm="ed25519",
        timestamp=timestamp,
        policy_snapshot_digest=policy_snapshot_digest,
        evidence_manifest_digest=None,
    )
    report["signing_envelope_sha256_first_bytes"] = envelope_bytes[:64].decode("utf-8")

    ok, detail = verify_ed25519_signature(
        envelope_bytes=envelope_bytes,
        signature_b64url=signature,
        public_key_spki_der_b64=public_key_b64,
    )
    if not ok:
        report["error"] = f"signature verification failed: {detail}"
        return False, report

    report["verified"] = True
    return True, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline crypto-verify every bundle under a run dir."
    )
    parser.add_argument("run_dir", type=Path, help="Path to results/runs/<run_id>/")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable status lines.",
    )
    args = parser.parse_args(argv)

    if not args.run_dir.exists():
        raise SystemExit(f"Run directory not found: {args.run_dir}")

    passed = 0
    failed = 0
    reports: list[dict[str, Any]] = []
    fail_paths: list[str] = []

    for level, bundle_path in iter_bundles(args.run_dir):
        ok, report = verify_bundle(bundle_path)
        report["level"] = level
        reports.append(report)
        if ok:
            passed += 1
            if not args.json:
                print(
                    f"PASS  {level:>11}  {report.get('ocid','?'):<55}  "
                    f"kid={report.get('signature_kid','?')}  "
                    f"hash={(report.get('integrity_hash') or '')[:12]}…"
                )
        else:
            failed += 1
            fail_paths.append(str(bundle_path))
            if not args.json:
                print(
                    f"FAIL  {level:>11}  {report.get('ocid','?'):<55}  "
                    f"{report.get('error','?')}"
                )

    if args.json:
        json.dump({"passed": passed, "failed": failed, "reports": reports}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        total = passed + failed
        print()
        print(f"Total: {total}   PASS: {passed}   FAIL: {failed}")
        if failed:
            print("Failing bundles:")
            for p in fail_paths:
                print(f"  - {p}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
