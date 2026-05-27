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

**Open design decisions before predictions can be drafted** (see `experiment_design.md`): density-control payload definition; second model (Claude recommended); scaled-diagnostic n; final confirmation L4-without-nudge is in.

**What's next**: Sam reviews the design draft → resolve the four open decisions → draft predictions at segment level → pre-registration lock at `v0.X-predictions-locked`.

---

*Add new entries at the top of this section, above this line.*
