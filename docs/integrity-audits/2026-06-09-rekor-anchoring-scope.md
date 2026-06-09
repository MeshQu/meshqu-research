# Integrity Audit IA-2026-01 — Rekor anchoring in the MRP corpus

**Date:** 2026-06-09
**Auditor:** Sam Carter (MeshQu)
**Affects:** MRP-2026-02 (E1), MRP-2026-03 (E2), MRP-2026-04 (E3)
**Claim under audit:** *Every decision in the corpus is recorded as a Decision Receipt, signed (Ed25519) and anchored to the public Sigstore Rekor transparency log, independently verifiable offline.*
**Disposition:** **Confirmed** (anchoring) · **Discovered** (a reproducibility-instruction gap, documented here; permanent fix on a closure track)

> This audit applies the programme's own discipline — *evidence before assertion* — to one of its own load-bearing claims. The claim was treated as falsifiable: a check was specified that could resolve it in either direction, the check was run against the public transparency log (a source of truth independent of any MeshQu-held artefact), and the result was conclusive. It is recorded here because publishing the check is the discipline — an audit that confirms a claim belongs in the record alongside one that overturns it. The check pointed, at first, at the auditor's own initial inference; following the evidence rather than the inference is the point.

## 1 · What was audited, and why

The trilogy's strongest single property is that its quantitative claims are re-derivable, offline, from a corpus of cryptographically signed, transparency-log-anchored receipts — without trusting MeshQu. A receipt is **signed** (Ed25519, verifiable against the published key) and **anchored** (a Sigstore Rekor entry whose inclusion proof is verifiable against the public append-only log). The signing leg is self-evidently checkable from any bundle; this audit independently verifies the **anchoring** leg against the public Rekor log, for all three experiments.

The audit was prompted, during methods-note authoring, by an on-disk observation: the run-directory bundles (`results/runs/.../*.bundle.json`) carry `transparency_anchor: null`. Taken alone, that emission-layer artefact is consistent with two hypotheses — (i) the corpus was never anchored, or (ii) anchoring is applied at a later export step and the run-dir files are pre-export source. The audit distinguishes them by querying the public log directly, which depends on no MeshQu artefact.

## 2 · Evidence — three independent methods, three experiments, one answer

All three checks are re-runnable by any reader: the inputs are public `integrity_hash` values and the public Rekor API.

### (a) E1 — corpus coverage + cryptographic byte-match

The published `procurement-decisions/results/corpus.tar` contains 283 v2 verification bundles. **283 / 283 carry a complete `transparency_proof`** (Rekor `entry_uuid`, `log_index`, inclusion proof), across **283 distinct log indices** — one anchor per receipt. The §6 worked example (`ca19e737`, the £57M DENY) was byte-matched end to end:

```
receipt integrity_hash (H)               e42a292d3557ca2e925a0ddc48f6aad1872f093e45ad25b7bd05d160aadb9880
sha256( in-toto statement built from H ) eea200200a45d1e21ad5a3e71520eb1e5efd088c5cb6bf8ad6712eed8adfb993
Rekor entry payloadHash (live + bundle)  eea200200a45d1e21ad5a3e71520eb1e5efd088c5cb6bf8ad6712eed8adfb993   ✓ equal
DSSE subject digest decoded from entry   e42a292d…                                                          ✓ == H
Rekor entry_uuid  108e9186…9908545d   log_index 1566819550   integratedTime 2026-05-18T10:42:20Z
```

The hashed object is the in-toto Statement v0.1 that the signer/anchorer produces (`packages/meshqu-core/src/transparency.ts → reconstructDsseEnvelope`), whose `subject[0].digest.sha256` is the receipt integrity hash. `sha256(statement)` equals the `payloadHash` of the **live** Rekor entry, and the entry's decoded subject digest equals `H`. The public-log entry is genuinely the anchor for this receipt.

### (b) E2 — live content search

Receipt `9a909071-9038-495f-8545-6441e107a2ee` (phase-2), integrity_hash `2c6e7def506031b6879d00c43e8e0262517beb7a401027013e03ab805d710538`, resolves by content search to Rekor entry `108e9186…4982849d`.

### (c) E3 — live content search, double-keyed

Receipt `54d702ac-8c51-4d59-948f-76293f731fa0` (the cross-model worked example, integrity_hash `cf62d0c88aef5bc40b68894801cbb04c17bbe330da6ec7b07788227f12a2a662`) resolves to entry `108e9186…72a73b5a5` by **two independent keys that can agree only if the entry is its genuine anchor**: the subject digest (`cf62d0c8…`) and the independently-computed payload hash (`sha256(statement(cf62d0c8…)) = 03c9e687b13c7af1139ea7ddcaecd572f7f7151e34f66a76172cdb4e66487671`). Both return the same entry.

### Instrument validation

The negative branch ("not found" = unanchored) is only trustworthy if the search index works, so it was validated with a positive control: E1's known-anchored receipt (`e42a292d…`) was searched first and resolved to its known entry (`108e9186…9908545d`, log_index 1566819550), and continued to resolve during the E2/E3 queries.

### Conclusion

Every receipt tested, in every experiment, is anchored in the public Sigstore Rekor log. The corpus-wide anchoring claim is **Confirmed**. The published "anchored to Sigstore Rekor, independently verifiable" language is accurate.

## 3 · Discovered — a reproducibility-instruction gap (not an integrity gap)

The repository carries the receipt corpus at **two layers**, and only one is anchored:

- **Run-directory emissions** (`results/runs/.../*.bundle.json`) — the runner's pre-export output. `transparency_anchor: null` **by design**: anchoring is applied by the export-and-anchor pipeline, not at emission time.
- **Exported verification bundles** — the canonical, anchored artefact. E1 commits these as `corpus.tar` (283 / 283 anchored). E2 and E3 do **not** commit an equivalent tarball; their anchors are confirmable via the public Rekor log (§2) and via on-demand export.

E2's and E3's reproducibility sections instruct a reader to *"download any bundle from the run directory"* and verify it. Followed literally, that yields a **pre-export** bundle with a null anchor, from which a careful reader could reasonably — and wrongly — conclude the corpus is unanchored. That is exactly the inference this audit's own first pass made. **The gap is in the instructions, not the anchoring.**

### Worked retrieval — confirm any receipt's anchor from the public log alone

Given only a receipt's `integrity_hash` (`H`):

```bash
# 1. Find the Rekor entry by content (H is the in-toto subject digest).
#    The public index is rate-limited; retry on 5xx.
curl -s -X POST https://rekor.sigstore.dev/api/v1/index/retrieve \
  -H 'Content-Type: application/json' \
  --retry 8 --retry-all-errors -d "{\"hash\":\"sha256:$H\"}"
# → ["<entry_uuid>"]

# 2. Pull the entry + inclusion proof, decode the body, read the payloadHash.
curl -s "https://rekor.sigstore.dev/api/v1/log/entries/<entry_uuid>"
#    base64-decode .<uuid>.body → .spec.payloadHash.value

# 3. Bind it to the receipt. Rebuild the in-toto Statement from H and hash it:
#    {"_type":"https://in-toto.io/Statement/v0.1",
#     "predicateType":"https://meshqu.dev/receipt/v1",
#     "subject":[{"name":"receipt","digest":{"sha256":H}}],
#     "predicate":{"integrity_hash":H}}
#    sha256(statement) MUST equal the entry's payloadHash, and the entry's
#    decoded subject digest MUST equal H.
```

A match proves the public log holds an anchor issued for *this* receipt. Where an exported/anchored bundle is in hand (e.g. any bundle in E1's `corpus.tar`), it ships the `entry_uuid` directly, so step 1 can be skipped and the entry fetched by UUID — the more robust path, since it avoids the rate-limited search index. The programme's signing kid is `meshqu-experiment-procurement-2026-05`; the canonicalisation profile is `meshqu-canonical/v0`.

## 4 · Anti-claims — what this audit does not establish

- It does **not** establish that any receipt schema, signing-key management, or canonical-envelope construction is incorrect — those are unchanged and out of scope.
- It does **not** establish that the published quantitative findings depend on anchoring. They depend on signature + integrity-hash + canonicalisation, which are independently offline-verifiable and were never in question.
- It does **not** revise any published number. No corpus data changed; this audit reads existing artefacts and the public log.
- It does **not** speculate on how the documentation gap arose. There is no integrity finding to remediate — only an instruction to clarify.
- The **Confirmed** disposition is bounded by what was tested: full coverage proven for E1 (283 / 283); for E2 and E3, one receipt each verified against the public log, plus the uniform anchoring mechanism. A reader can extend coverage to any receipt using the worked retrieval above.

## 5 · Going forward (closure track)

- **Methods note** (`methodology/receipt-anchored-evaluation.md`). §2 / §9 state Rekor anchoring as **verified**, with `ca19e737`'s byte-match as the canonical demonstration, and carry the run-dir-vs-export reproducibility instruction so no future reader repeats the pre-export inference. *(In progress.)*
- **Reproducibility-instruction fix.** E2 / E3 reproducibility sections to point readers at the exported/anchored bundle and the public-log retrieval above, rather than the pre-export run-dir file. *(Committed; lands with the next minor revision.)*
- **Self-contained corpora** *(committed-deliverable, not urgent)*. Publish an anchored `corpus.tar` for E2 and E3 matching E1's pattern, so the repository is self-contained rather than relying on the export endpoint or the live log. Fold into a future minor revision (E2 → MRP-2026-03 v1.0.1, E3 → MRP-2026-04 v1.0.1) when engineering bandwidth opens. *(Tracked; closure does not gate current publication.)*
- **No errata.** The published anchoring claims are accurate; no correction notes are warranted.

## 6 · Audit trail

- DSSE / anchor construction: `packages/meshqu-core/src/transparency.ts` (`reconstructDsseEnvelope`, `anchorToRekor`, `verifyAnchorSubjectBinding`).
- Anchoring gate: `apps/meshqu-api/src/services/decision-service.ts` (`config.transparencyEnabled`, global).
- E1 coverage + byte-match source: `procurement-decisions/results/corpus.tar → bundles/ca19e737-defb-4e5f-b216-ec97d2fe5859.bundle.json` (`files.transparency_proof.json`).
- Live Rekor entries (re-runnable; share the log tree-ID prefix `108e9186e8c5677a`):
  - **E1** receipt `ca19e737` → `…25bce5f8…9908545d`, log_index 1566819550 — `https://rekor.sigstore.dev/api/v1/log/entries/108e9186e8c5677a25bce5f8d63511fc7f9ef20c50ec0299d8cce4dd9908545d04c9e7af27a35364`
  - **E2** receipt `9a909071` → `…0eea798b…4982849d`
  - **E3** receipt `54d702ac` → `…20561080…72a73b5a5`
- Verification method: `POST https://rekor.sigstore.dev/api/v1/index/retrieve {"hash":"sha256:<integrity_hash>"}` (positive-control-validated against E1).
