# Experiment signing key

- **kid**: `meshqu-experiment-procurement-2026-05`
- **algorithm**: Ed25519
- **public_spki_b64**: `MCowBQYDK2VwAyEAQKw/FAIkqj9HTt1pDd6WsPUf3gQQz04k2aV8tjRhWCw=`
- **generated_at**: 2026-05-16T09:20:00.708Z
- **scope**: signs receipts emitted by the `experiment-procurement` tenant on staging during the May-2026 procurement-decisions experiment.
- **trust**: bundled in `apps/meshqu-verify/src/lib/keys.ts` (commit: `1b042d26`).

## How to verify a receipt under this kid

1. Download the receipt bundle (`tar` or `json`) from the experiment corpus.
2. Either:
   - Open https://verify.meshqu.com and upload the bundle — the kid above is
     already in the bundled trust list as of the commit referenced above, so
     verification works offline (no network call required).
   - OR pass the public SPKI above to your own Ed25519 verifier of choice
     and verify against the `signature` field in the receipt v2 envelope.
3. The verifier confirms (a) the signature is valid under the listed SPKI,
   (b) the `policy_snapshot_digest` and `evidence_manifest_digest` match the
     content in the bundle, and (c) the Rekor inclusion proof anchors the
     receipt to the public transparency log.

## Why a dedicated kid for the experiment

Receipts under this kid are deliberately separable from production receipts:
a reader of the writeup can verify the experiment corpus in isolation
without needing to trust the broader MeshQu signing-key history. The kid is
scoped, dated, and bound to the tenant it signs for — see the harness
`decision_log.md` (`.harness/multi-tenant-observability/`) for the rationale.

## Revocation

This kid is intended to be retired at the end of the experiment. After
publication, the experiment-procurement tenant rotates to a sealed
post-experiment kid; this kid's public SPKI stays in the bundled trust list
indefinitely so historical receipts in the experiment corpus continue to
verify.
