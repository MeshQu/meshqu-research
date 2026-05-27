# Experiment 3 (E3) — predictions

**Status**: DRAFT — pre-lock. Scope is resolved (see `experiment_design.md`); these predictions are drafted for review. **Not yet locked.** Bands are defensible starting points and need Sam's calibration before the `v0.X-predictions-locked` tag. Pre-registration lock is a separate gated step; no evaluation calls until it lands.

## Lock convention

Per `programme/PROCESS.md` and E1+E2 precedent:

- Predictions are SHA-bound and tag-anchored at git tag `v0.X-predictions-locked` **before any evaluation calls are made**.
- Each prediction is numbered (P1, P2, …) and has an explicit numeric falsification criterion.
- Disposition vocabulary is locked: **Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested**. No "partial confirmations" permitted in the writeup.
- Predictions are specified at the **segment level** where applicable (E2 retrospective): P1/P2 in E2 were specified at the aggregate-trend level, which made the inverted segments report as falsifications of a uniformity assumption. E3 should specify per-segment so non-monotonic shapes can be predicted explicitly.

## Predictions (draft — bands need calibration before lock)

Reference points from E2: L3 DENY-rate **37.8%** (107/283); L0–L2 ≈ **0%**; L4 backoff reverted 46/107; PROC-005-OPEN-TENDER **29/40 → 1/40** (L3→L4); Permuted-Policy same-as-unperturbed **13/14 = 92.9%** at n=14, contradiction-naming lexicon **0/14**.

Each prediction is condition-specific (segment-level, per the E2 retrospective). E3 is a disambiguation experiment, so several predictions state the reading E2 leaned toward (weak Reading A) as the directional hypothesis — but the design distinguishes outcomes regardless of which way they break, and a falsification is as informative as a confirmation here.

### Piece 1 — L3 decomposition

**P1 — precedents drive commitment, not raw volume.**
Arm A (precedents-only) DENY-rate **≥ 25%** AND Arm C (density-control) DENY-rate **≤ 10%**.
*Falsified if* Arm C ≥ 25% (volume alone commits → Reading B) **or** Arm A ≤ 10% (precedents in isolation don't commit → the accumulated ladder was needed; a third reading).

**P2 — verdict exemplars are load-bearing (the governance-memory mechanism).**
Arm A DENY-rate − Arm B (precedents-no-verdict) DENY-rate **≥ 15pp**.
*Falsified if* |A − B| < 5pp (verdicts immaterial → the effect is concreteness/seeing-similar-cases, not prior-verdict anchoring).

> P1 + P2 together adjudicate the four outcome rows in `experiment_design.md` Piece 1.

### Piece 2 — L4 decomposition

**P3 — the anti-sycophancy nudge is load-bearing for the L3→L4 backoff (Framing A.1).**
Under L4-without-nudge, PROC-005-OPEN-TENDER DENY-rate **≥ 50%** (commitment largely survives once the nudge is removed → the nudge caused the backoff).
*Falsified if* PROC-005 DENY-rate ≤ 10% under L4-without-nudge (≈ E2's L4 1/40 → the policy text alone caused the backoff; Framing A.2).

### Piece 3 — Scaled diagnostic + cross-model

**P4 — inversion-blindness reproduces at scale.**
On the n=100 Permuted-Policy subset (primary model), **≥ 85%** of records emit the same verdict as their unperturbed-L4 verdict.
*Falsified if* < 85% (the n=14 signal doesn't hold at scale).

**P5 — the reasoning pattern is reasons-against-intent, not inversion-naming.**
Hand-coded rubric on the n=100: "reasons solely against rule intent" is the modal category at **≥ 60%**, and "names the inversion in any words" is **≤ 15%**.
*Falsified if* "names the inversion" > 25% (the agent does detect the inversion at scale, contra the n=14 read).

**P6 — inversion-blindness is task-class, not model-specific.**
Claude's same-as-unperturbed verdict rate on the same 100 records is **within 15pp** of the primary model's rate.
*Falsified if* the gap > 15pp (the property is model-specific). Note: this is the prediction E3 is least sure of — Claude is heavily tuned against sycophancy and may detect inversions the primary model misses. The alternative outcome (model-specific) is itself a strong finding, not a failure.

### Calibration notes for Sam (resolve before lock)

- **P1 bands (25% / 10%)** — anchored loosely to E2's L3 37.8% and L0–L2 ~0%. Is 25% the right "commits" floor, or higher (closer to L3)?
- **P3 (50%)** — PROC-005 is the hardest-ambiguity class; 50% is a midpoint guess. Could be set against the broader L3-DENY-set backoff rate instead of PROC-005 specifically.
- **P4 (85%)** — E2 was 92.9% at n=14. Is 85% too lenient a floor for "reproduces"?
- **P6 (15pp)** — the agreement band. Tighter (10pp) makes "task-class" a stronger claim but raises falsification risk.

## Definition of "report honestly"

Inherited from E1+E2. The disposition vocabulary is the contract. The writeup must use exactly one of {Confirmed, Falsified, Inverted, Refuted, Deferred, Under-tested} for each prediction in §3 — never "partially", "weakly", or "broadly".
