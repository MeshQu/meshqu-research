# Experiment 3 (E3) — experiment design

**Status**: Phase 0 — design draft. **Not locked.** Predictions are not drafted until this design is reviewed; pre-registration lock is a separate gated step (see checklist at the end).

E3 is the **disambiguation experiment**. E2 surfaced two structural findings it could not mechanistically isolate — the L3 commitment break and the L4_PERMUTED inversion-blindness — and left explicit open readings. E3's job is to slice those confounds. It reuses E1/E2's substrate, corpus, policy snapshot, and primary agent unchanged, and adds targeted variants. No new substrate, no investigative-agent format shift (that is E4).

## The open readings E3 must resolve

From E2's writeup, three things are real but unattributed:

1. **The L3 break (Reading A vs Reading B).** At L3 the agent committed 107/283 records to DENY (37.8%) where L0–L2 held ~100% REVIEW. E2 could not separate *"precedents caused the commitment"* (Reading A) from *"L3 is just the first rung with enough content to act on, precedents or not"* (Reading B). Rung-position and precedent-content are confounded by construction in E2's additive ladder.
2. **The L3→L4 backoff (Framing A.1 vs A.2).** L4 reverted 46 of those 107 DENYs to REVIEW, concentrated on PROC-005 (29/40 → 1/40). E2 could not separate *"the L4 anti-sycophancy nudge is doing the work"* (A.1) from *"the full policy text alone is doing the work"* (A.2).
3. **Inversion-blindness (n=14, a signal not a metric).** On the 14-record Permuted-Policy diagnostic, 13/14 records emitted the same verdict as unperturbed L4 and 0/14 named the inversion. E2 could not establish whether this is real at scale, nor whether it is a property of this model or of the task class.

## Scope (locked cut)

E3 commits to three pieces — the spine — and defers two.

**In scope:**

1. **The L3-decomposition variants** — isolate what drove the L3 break (resolves finding 1).
2. **L4-without-nudge variant** — isolate what drove the L3→L4 backoff (resolves finding 2).
3. **Scaled Permuted-Policy diagnostic + one cross-model arm** — establish inversion-blindness at scale and test model-vs-task-class (resolves finding 3).

**Deferred** (strong, but would balloon scope; revisit for E3.1 or fold into E4):
- **Authoritative-vs-hypothetical framing axis** — isolates the "authority-conditioned" qualifier specifically. Valuable but secondary to establishing the effect is real at scale first.
- **Cross-domain substrate** (AML/KYC/clinical) — a methodology-generality claim that needs a new substrate adapter + policy authoring pass. E4-shaped.

> **Note on the deferred L4-without-nudge vs the in-scope decision.** On reflection it belongs *in* scope — it is the clean disambiguator for finding 2 and is cheap (one prompt-variant rerun on the same corpus). Listed in-scope above. The earlier scaffolding draft had it ambiguous; this resolves it in.

## Design

### Piece 1 — L3 decomposition (resolves Reading A vs B, and isolates the mechanism)

The crux. E2's L3 rung = L0 baseline + L1 prose + L2 named rules + L3 precedent receipts, *accumulated additively*. A precedent receipt bundles **three** properties, any of which could drive the L3 commitment: (1) raw context **volume**, (2) **concreteness** (specific prior cases, not abstract rules), (3) **verdict exemplars** (those cases carry verdicts — other records got DENY'd). To separate them, E3 runs three **non-additive** probe arms against the same 283 records, each read against E2's L3 (37.8% DENY):

- **Arm A — precedents-only** = L0 baseline **+ E2's full precedent receipts** (cases + verdicts), L1/L2 stripped. The whole precedent effect in isolation.
- **Arm B — precedents-no-verdict** = same cases as Arm A, **verdict field redacted**. Concreteness *without* the verdict signal.
- **Arm C — density-control** = L0 baseline + **length/structure-matched abstract content** (expanded domain/policy prose), no concrete cases, no verdicts. Raw volume only.

Reading the three arms:

| Outcome | Interpretation |
|---|---|
| A commits, B doesn't, C doesn't | **Verdict exemplars are load-bearing** — prior DENYs anchor new ones. The governance-memory mechanism (E2 §10) made empirical. *(Sharpest result.)* |
| A and B commit, C doesn't | **Concreteness** — seeing similar cases anchors; verdicts not needed. |
| All three commit | **Reading B** — raw volume drives it; precedents not special. *(Deflationary but honest.)* |
| Only C fails to match | Cases matter, volume alone doesn't (collapses to one of the two rows above). |

**The contamination risk lives in Arm C.** Match the precedent payload on what Reading B would plausibly credit: **token count** (the volume claim), **number of discrete informational units** (precedents are N items; the control is N items), and **prompt position** (same slot). Differ on: no concrete records, no verdicts. Perfect density-matching is impossible (precedents have a case→facts→verdict→reasoning structure prose can't replicate) — so the matching criteria are pre-registered for transparency, and the authored Arm-C payload is inspected for accidental verdict-signal before lock. We don't need perfect; we need "no one can argue Arm C smuggled in decision-relevant signal."

> **Terminology fix carried into the writeup later:** E2 used "L3.5" loosely for this. E3 retires "L3.5" entirely — the single label hid that *three* probe conditions are needed to isolate the mechanism, not one.

### Piece 2 — L4 decomposition (resolves Framing A.1 vs A.2)

- **L4-without-nudge** = the full L4 policy-text rung with the explicit anti-sycophancy nudge clause ("if a required field is absent, do not assume it satisfies the rule") **excised**, everything else identical.

Reading against E2's L4 (the 46-record backoff, PROC-005 29→1):

| L4-without-nudge result | Interpretation |
|---|---|
| Looks like L3 (commitment survives, no backoff) | **A.1** — the nudge clause is load-bearing; it caused the backoff |
| Looks like L4 (backoff persists) | **A.2** — the policy text alone causes the backoff; the nudge is incidental |

### Piece 3 — Scaled diagnostic + cross-model arm (resolves inversion-blindness)

- **Scaled Permuted-Policy diagnostic**: lift from 14 records to **n ≥ 100** (target the full corpus or a pre-registered larger subset). Add a **hand-coded reasoning rubric** — three categories per record: *names the inversion in any words* / *reasons solely against rule intent* / *partially recognises but applies anyway*. This moves D4 (policy resistance) from lexicon-only (which fired 0/14 in E2) to human-coded, so the resistance axis is reportable beyond the bare lexicon.
- **Cross-model arm**: run **the scaled diagnostic only** (not the full ladder) on **Claude** (second model confirmed; key available). Asymmetric design — full diagnostic on the primary model, same diagnostic on Claude — buying "is inversion-blindness real at scale" *and* "is it model-specific or task-class" without a full second-model corpus.

**Scaled-diagnostic n: a pre-registered subset** (confirmed — expandable later if the subset signal warrants it). Target n = 100 records, selected by a deterministic, pre-registered rule over the 283-corpus (e.g. `sha256(ocid) mod 283 < 100`, or the first 100 by sorted OCID — to be fixed at lock). The same 100 run on both the primary model and Claude, so the cross-model comparison is record-matched.

## Substrate

**Reuse the frozen 283-record corpus unchanged.** Same fixture, same policy snapshot (`5d7d800186…`), same field-provenance envelope. This is non-negotiable for E3's purpose: every E3 verdict must be directly comparable to its E2 counterpart on the same OCID. Expanding or changing the corpus would reintroduce the substrate variable E3 is trying to hold fixed.

## Execution plan (carry-forwards from E2)

- **Level-batching execution order** — all records at one condition, then the next, for prompt-cache preservation.
- **Frozen-archive isolation** for precedent material — precedents drawn from E1's frozen archive, target record excluded by OCID, no live API at precedent-generation.
- **Bundle envelope** — `BUNDLE_ENVELOPE_VERSION = 1` unless a variant needs a new field (the hand-coded rubric output may warrant a sidecar rather than an envelope bump — design decision at build time).
- **Signed receipts** — Ed25519 + Rekor, same signing kid lineage; cross-model receipts signed under the same tenant so the corpus stays one verifiable whole.
- **Runner** — fork E2's multi-pass runner; add the probe-rung handlers (L3-precedents-only, L3-density-control, L4-without-nudge) and the model-swap adapter for the cross-model arm.

## What each piece buys (payoff summary)

| Piece | Resolves | Output |
|---|---|---|
| L3 decomposition | Reading A vs B (did precedents drive L3?) | A clean attribution, or a named third reading |
| L4-without-nudge | Framing A.1 vs A.2 (did the nudge drive the backoff?) | Nudge load-bearing, or policy-text-alone |
| Scaled diagnostic + rubric | Is inversion-blindness real at scale? | A metric, not a 14-record signal |
| Cross-model arm | Model-property or task-class? | Universality evidence, or model-specificity |

## Pre-registration lock checklist (per `programme/PROCESS.md` + `STRUCTURAL-PARITY.md`)

Not started — gated behind design review. When ready:

- [ ] Predictions specified at **segment level** (E2 retrospective lesson — not aggregate-trend like E2's P1/P2)
- [ ] Falsification criteria numeric and specific (esp. the L3-decomposition bands and the cross-model agreement band)
- [ ] Disposition vocabulary locked (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested)
- [ ] Density-control payload authored, reviewed, and SHA-bound (the contamination risk lives here)
- [ ] All prompt variants SHA-bound and committed
- [ ] Policy snapshot SHA-bound (reused from E2; reconfirm hash)
- [ ] Hand-coded rubric protocol written (coder instructions, the three categories, inter-coder check if more than one coder)
- [ ] Second model + version pinned
- [ ] Scaled-diagnostic n committed (full corpus or pre-registered subset)
- [ ] Working title committed (or placeholder with intent)
- [ ] Git tag created: `v0.X-predictions-locked`

## Decisions resolved (2026-05-27)

1. **L3 decomposition: 3 arms** — precedents-only (A) / precedents-no-verdict (B) / density-control (C). The 3rd arm isolates the verdict-exemplar mechanism, directly testing the §10 governance-memory interpretation. Arm C matched on token count + number of discrete units + prompt position; inspected for verdict-signal contamination before lock.
2. **Second model: Claude** (key available). Diagnostic-only cross-model arm.
3. **Scaled-diagnostic n: pre-registered subset, target 100** — same 100 records on both models (record-matched); deterministic selection rule fixed at lock. Expandable later if the subset signal warrants.
4. **L4-without-nudge: in scope.**

Design is resolved. Next: draft segment-level predictions (`predictions.md`), then pre-registration lock.
