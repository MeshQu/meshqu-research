# Receipt-Anchored Evaluation

**Receipt-Anchored Evaluation** is the methodology this research programme runs on: an audit-grade, signed-receipt method for empirical research on AI-governance behaviour. The name is literal — every decision in a study is recorded as a Decision Receipt, signed and anchored to a public transparency log, so the entire evidence corpus is independently verifiable.

**Status**: extracted 2026-05-27, triangulated from two worked applications (E1 / MRP-2026-02 and E2 / MRP-2026-03). Working reference; evolves as further applications add anchor points. The full narrative argument lands in the methods note (see below).

## The core idea

The same signed Decision Receipts that MeshQu ships as a product double as the reproducibility substrate for empirical research on AI-governance behaviour. **The product is the research instrument.**

Most AI-governance writing is conceptual, policy-heavy, and non-reproducible. This methodology produces research where every quantitative claim is re-derivable offline from a corpus of cryptographically signed, transparency-log-anchored receipts. The reproducibility is not a bolt-on; it falls out of using the production decision-receipt infrastructure as the evaluation substrate.

## What the methodology is

Two layers fused: a **technical method** for producing a signed, replayable evidence corpus, and a **research discipline** for making honest claims about it.

### Technical method

1. **Substrate.** Pick a public-record domain (E1/E2: UK Contracts Finder OCDS procurement filings). Build a substrate adapter that maps domain records into a field-provenance envelope. Freeze a corpus before any evaluation — no live reads at the substrate boundary during a run.
2. **Policy.** Author executable policy against the domain's real regulatory frameworks. Snapshot it and SHA-bind the snapshot. The policy is the executable counterpart the agent is measured against.
3. **Agent.** Lock a foundation-model agent: prompt scaffold SHA-bound, temperature 0, model ID pinned. The agent reviews records and proposes verdicts.
4. **Evaluation.** Run the locked agent across the frozen corpus. MeshQu evaluates the same records against the executable policy. Both sides emit Decision Receipts.
5. **Integrity.** Every receipt is signed (Ed25519), anchored to a transparency log (Sigstore Rekor), and verifiable offline at [verify.meshqu.com](https://verify.meshqu.com) with no credentials. Every number in a writeup traces back to an on-disk signed bundle.

### Research discipline

The discipline layer is documented in [`../programme/PROCESS.md`](../programme/PROCESS.md) (the process gates) and [`../programme/STRUCTURAL-PARITY.md`](../programme/STRUCTURAL-PARITY.md) (the publication checklist). In brief:

- **Pre-registration.** Predictions, prompts, ladder content, and policy snapshot are SHA-bound and tag-anchored *before any data is collected*, with numeric falsification criteria.
- **Honest falsification.** When predictions break, the break is reported in the direction the corpus actually showed, using a locked disposition vocabulary (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested). No post-hoc smoothing.
- **Anti-claims.** Every finding states what it does *not* establish, alongside what it does.
- **Two-readings discipline.** Where the corpus admits multiple structurally plausible interpretations, the writeup reports both and names the experiment that would disambiguate them.

## Why it holds up

The integrity guarantees are load-bearing at publication time without requiring trust in the authors:

- A reader can re-derive any headline number from the on-disk bundles.
- A reader can verify any individual receipt's signature offline against the published signing key.
- A reader can confirm the predictions existed before the data, via the pre-registration commit hash.
- The agent, policy, and prompts are all SHA-pinned, so the experiment is replayable.

This is what lets the programme publish strong claims (and honest falsifications) as a research-programme output rather than waiting on peer review — the integrity mechanism is cryptographic and procedural, not reputational.

## Worked applications (anchor points)

- **E1 — MRP-2026-02** ([`../procurement-decisions/`](../procurement-decisions/)). Baseline: a locked agent reviews 283 UK procurement records without policy visibility; MeshQu evaluates the same records against executable policy. Finding: evidence-sensitive caution.
- **E2 — MRP-2026-03** ([`../procurement-context-gradient/`](../procurement-context-gradient/)). Same corpus, same agent, same policy snapshot; varies only the governance context the agent sees, across a five-rung ladder. Finding: non-monotonic verdict commitment — the precedent rung is where the agent first commits at scale.

Each application reuses the technical method and the research discipline unchanged; only the substrate question changes.

## Reuse

- **Research pieces** in this public repo apply the methodology to public-record substrates. Each is published as an `MRP-NNNN-NN` piece.
- **Client engagements** apply the same methodology to private data in separate, client-specific repositories that import the method as a dependency. The techniques are auditable; the engagements are confidential.

## The methods note (planned)

A standalone methods note — the narrative, citable version of Receipt-Anchored Evaluation, distinct from the experiment papers — is planned for publication on the website and GitHub, following the same pipeline as the experiment writeups. Working idea: an `MM-NNNN-NN` (MeshQu Methods) series alongside the `MRP` (MeshQu Research Piece) experiment series. The note argues the "product is the research instrument" framing in full and is the citable anchor for partners (e.g. the University of South Wales collaboration) adopting the method.

## Files

| File | Purpose | Status |
|---|---|---|
| `README.md` | This canonical reference | Present |
| *(methods note)* | Citable narrative version → published as `MM-NNNN-NN` | Planned |

The per-layer technical detail currently lives in the worked applications' planning directories (e.g. [`../procurement-decisions/planning/substrate.md`](../procurement-decisions/planning/substrate.md)). As the abstraction firms up across applications, the reusable form is consolidated here.
