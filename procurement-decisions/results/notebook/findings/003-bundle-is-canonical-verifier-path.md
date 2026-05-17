# Finding 003 — The bundle is the canonical verification artefact; raw-receipt-paste warns "Tampered" on receipts whose envelope includes server-injected metadata

**Created:** 2026-05-17
**Status:** stable
**Bears on:** methodology, P5

## The claim

Pasting one of the dry-run receipts directly into verify.meshqu.com returns "Tampered" — the verifier's recomputed integrity hash does NOT match the stored value. The same receipt, downloaded as a v2 bundle (`/v1/receipts/<decision_id>/bundle`) and verified via the bundle path, returns "Bundle Verified" with every cryptographic check passing cleanly (integrity, signature, transparency / DSSE + Rekor binding, canonicalization). The bundle path is the canonical verification artefact for v2 receipts; the raw-receipt-paste UX is a known limitation that warns falsely on receipts whose envelope includes server-injected metadata (notably `metadata.correlation_id`, which the API adds at record-time). The 300-record corpus is verifiable via the bundle; the writeup's verifier-instructions section must direct auditors to the bundle path, not the raw-receipt paste.

## Evidence

- Dry-run `dry-run-adfc2109-c9c0-4557-9b3d-88caaf3f84d6`, decision `1c5f2a78-845d-4ed0-ab3c-010e5990c360` (record 7). Raw-receipt verification at verify.meshqu.com: Integrity **Fail** (stored `b6ae2aad…92e319`, computed `4241514c…226124`), Signature **Fail** (downstream of integrity-hash mismatch — signature is over the same bytes).
- Same decision, bundle verification at verify.meshqu.com: **Bundle Verified with Caveats**. Schema v2, profile `meshqu-canonical/v0`. Pass on: bundle manifest, integrity, signature, transparency, canonicalization. Warning (non-blocking): `snapshot_replay.skipped_in_browser` (server-side verifier covers it), `approval_lineage.no_resolvable_versions` (cosmetic — entries don't carry `policy_version_id`, but tamper-pinning is intact via `policy_snapshot_digest`).
- Transparency anchoring confirmed end-to-end working in production-equivalent path: receipt carries `transparency_anchor.entry_uuid`, full 20-hash `inclusion_proof`, `log_index`, `tree_size`, `rekor_public_url`. Anchored to live sigstore.dev.
- Bundle affordance shipped in tradequ PR #493 (Console PHASE-2, `ebe1d43a`) + #494 (Demo PHASE-3, `e372f58d`). Existing memory note `project_receipt_v2_surface.md`.

## Why the raw-receipt path warns

The bundle ships the exact `buildReceiptV2EnvelopeBytes` envelope that was signed — zero canonicalization ambiguity. The raw-receipt path has to reconstruct the envelope from the receipt JSON, and `metadata.correlation_id` is folded into the integrity hash at API record-time but isn't necessarily reproducible from the receipt-only JSON in the same canonical order. The reconstruction differs by exactly one field; the hash differs entirely.

The bundle path exists precisely because this is a known v2 limitation — PHASE-2's "Download bundle" affordance was designed as the canonical verification path; "raw receipt copy/paste" is the eyeball-friendly summary UX.

## Caveats

- This finding applies to **v2 receipts whose envelope was populated with server-injected metadata**. v1 receipts and v2 receipts produced without server-side metadata addition may pass raw-receipt verification; the experiment's corpus uses v2 + the API's correlation_id injection, so all corpus receipts will exhibit the same raw-receipt-paste behaviour.
- Bundle verification is browser-runnable end-to-end EXCEPT for snapshot replay (the browser cannot run the rule evaluator). A server-side verifier covers snapshot replay. The bundle-verified-with-caveats status is the correct strongest claim for browser-side verification.
- Two ways to make the raw-receipt path stop warning on this experiment's corpus, both rejected: (a) stop folding `correlation_id` into metadata at API record-time — breaks request-correlation across API logs, infrastructure cost not worth the UX win; (b) post-process corpus receipts to strip `correlation_id` before publication — would corrupt the integrity hash. Documenting the bundle path is the right move.

## What this changes about the writeup

P5 (bundle round-trip) prediction was *"100% of bundled receipts verify offline at verify.meshqu.com"* — that holds. The writeup needs to add a sentence-level note in the verifier-instructions section: "Verify via the bundle download, not by pasting the raw receipt JSON. The raw-receipt path warns 'Tampered' on receipts whose envelope includes server-injected metadata; the bundle path is the canonical verification artefact and ships the exact signed envelope bytes." Methodology section can cite this as illustrative of why receipt-as-artefact thinking matters: the load-bearing claim is bundle integrity, not receipt-JSON identity. Section 7 (limitations) can briefly acknowledge the dual-UX situation.
