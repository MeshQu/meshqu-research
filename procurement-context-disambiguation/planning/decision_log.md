# Experiment 3 (E3) — decision log

Reverse-chronological. Most recent decision at the top. Each entry: date, decision, why, what's next.

---

## 2026-05-27 — E3 scope locked: the disambiguation experiment

**Decision**: E3 is the disambiguation experiment. It reuses E1/E2's substrate, the frozen 283-record corpus, the policy snapshot, and the primary agent unchanged, and adds targeted variants to slice the confounds E2 surfaced but could not isolate. No new substrate; no investigative-agent format shift (that is E4).

**Scope cut — in:**
1. **L3 decomposition** — two non-additive probe rungs (L3-precedents-only, L3-density-control) to separate "precedents drove the L3 break" (Reading A) from "any sufficient content density drove it" (Reading B).
2. **L4-without-nudge** — excise the anti-sycophancy nudge clause from the L4 policy rung to separate "the nudge drove the L3→L4 backoff" (Framing A.1) from "the policy text alone drove it" (A.2).
3. **Scaled Permuted-Policy diagnostic (n ≥ 100) + hand-coded rubric + one cross-model arm** — establish inversion-blindness at scale (vs the 14-record signal) and test model-property vs task-class. Asymmetric: full diagnostic on the primary model, same diagnostic on one second model — no full second-model corpus.

**Scope cut — deferred:**
- Authoritative-vs-hypothetical framing axis (isolates the "authority-conditioned" qualifier) — secondary to establishing the effect at scale; revisit for E3.1 or E4.
- Cross-domain substrate (AML/KYC/clinical) — needs a new substrate adapter + policy authoring pass; E4-shaped.

**Alternatives considered**: a full cross-model corpus across all rungs (rejected — ~2x collection cost for marginal gain over the diagnostic-only arm); a fresh substrate (rejected — would reintroduce the substrate variable E3 holds fixed); folding the investigative-agent variant in (rejected — format shift, scoped as E4).

**Why**: E3 sharpens E2's findings into attributions. The two structural results (L3 break, inversion-blindness) are real but unattributed; the value of E3 is converting "we observed X" into "X is caused by Y / holds at scale / is/ isn't model-specific." Three completed experiments also become the triangulation base for the Receipt-Anchored Evaluation methods note (deferred to post-E3 as the trilogy capstone).

**Design decisions resolved (2026-05-27)**:
1. **L3 decomposition = 3 arms** — precedents-only (A) / precedents-no-verdict (B) / density-control (C). The 3rd arm isolates the verdict-exemplar signal, directly testing the §10 governance-memory interpretation (do *prior verdicts* anchor, or just prior cases?). Arm C matched on token count + discrete-unit count + prompt position; inspected for verdict-signal contamination before lock.
2. **Second model = Claude** (key available); diagnostic-only cross-model arm.
3. **Scaled-diagnostic n = pre-registered subset, target 100**; same 100 records on both models (record-matched); expandable later.
4. **L4-without-nudge = in scope.**

**What's next**: predictions drafted at segment level (`predictions.md`, pre-lock) — P1/P2 (L3 decomposition), P3 (L4 nudge), P4/P5 (scaled diagnostic), P6 (cross-model). Sam calibrates the falsification bands → pre-registration lock at `v0.X-predictions-locked`.

---

*Add new entries at the top of this section, above this line.*
