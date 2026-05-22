# F008 — L3 is the behavioural break, not L4 (precedent-rung anchoring)

**Status**: Discovered (no pre-registered prediction targeted L3 specifically; closest pre-reg is P1 monotonic decrease, which this falsifies in a direction nobody predicted)
**Source experiment**: E2 (procurement-context-gradient) Phase 2 corpus `phase-2-20260522-101324-Z`
**Pre-registered prediction**: P1 (REVIEW rate decreases monotonically L0→L4) — falsified; this finding documents *why* and *where* the break actually lands
**Authored**: 2026-05-22
**Restraint discipline**: The corpus shows verdicts moving at L3; it does not show "precedents caused the shift" in a causal sense. The taxonomy v1.1 §1.5 caution against AI-safety-literature pinpoint claims applies — this finding uses "anchoring" in the structural-observation sense (the corpus pattern is consistent with the agent treating L3 receipts as permissive evidence to commit) without claiming the manipulation mechanism that "anchoring" implies in the cognitive-bias literature.

## Finding

The headline behavioural break across the context ladder is **at L3 (precedents), not at L4 (full policy text)**. Levels L0/L1/L2 hold the agent at 97.5%–100% REVIEW. At L3 the agent emits **107 fresh DENYs** out of 283 records (37.8%), collapsing REVIEW to 61.1%. At L4 the agent then *backs off* 46 of those 107 L3-DENYs to REVIEW, rebounding REVIEW to 74.2%. The full-policy rung *reduces* committed-verdict count compared to the precedents-only rung. Whatever the experiment's writeup says about L4, the structural fact is that the precedent rung is where the agent's verdict surface first commits at scale, and the policy rung partially re-asserts caution against that commitment.

## Evidence

- Corpus citation: `procurement-context-gradient/results/notebook/cross_level_analysis/02-trajectory-buckets.md` §"L2→L3 is the headline transition" + §"L3 → L4 detail"; and `06-per-rule-shifts.md` §"PROC-005-OPEN-TENDER (n=40)"
- Numbers (with units, with denominators):
  - L2 → L3 transition (n=283 records): 173 REVIEW → REVIEW, **107 REVIEW → DENY**, 3 REVIEW → ALLOW
  - L3 → L4 transition (n=107 L3-DENYs): **46 DENY → REVIEW (backoff)**, 61 DENY → DENY (commitment survives)
  - Aggregate REVIEW rate by level: L0 97.5% → L1 100.0% → L2 100.0% → L3 61.1% → L4 74.2%
  - Agreement-with-MeshQu rate by level: L0 2.5% → L1 0.0% → L2 0.0% → L3 38.5% → L4 25.8% (L4 *lower* than L3)
- Worked example: `ocds-b5fd17-f5d7b902-87b4-4f05-84bc-2dcab9047651` (PROC-002-AUTHORITY operative rule, MeshQu verdict DENY). Trajectory: REVIEW → REVIEW → REVIEW → **DENY** → DENY. At L2 the agent says *"this is an above-threshold £7,781,577 award under the pre-PA23 regime with an open procedure, but the award appears published 574 days after the award date, which is unusually late… the audit trail is incomplete"* (REVIEW). At L3 the same record is *"this £7,781,577 above-threshold award under PCR 2015 shows an extreme 574-day publication delay despite an open procedure, indicating a clear publication-timing failure and weak audit trail"* (DENY). The publication-delay number is identical at both levels; what changed between L2 and L3 is the presence of precedent receipts. The reasoning at L4 retains the DENY but reframes the same record under explicit policy citations (`05-reasoning-text-drift.md` §"L2→L3 shifter").
- Worked example for the L3→L4 backoff direction: PROC-005-OPEN-TENDER records (n=40, primary operative rule). L3 commits DENY on **29/40** records. L4 commits DENY on **1/40**. The 28-record swing is the cleanest single-axis backoff in the corpus (`06-per-rule-shifts.md` §"PROC-005-OPEN-TENDER").

## Interpretation

Two readings are defensible and both are visible in the corpus:

- **Reading A (precedent-rung anchoring)**: L3 receipts give the agent permissive evidence to commit — concrete cases with concrete verdicts on similar substrate. The agent reads those receipts as license to leave REVIEW, then L4 policy text *re-asserts caution* by exposing missing-metadata gaps by name (PROC-005's missing-method check is the canonical example). On this reading L4 is doing what the experiment design hoped: differentiating signal from style.
- **Reading B (L4 anti-sycophancy nudge is load-bearing)**: the L4 envelope contains explicit nudge language ("if a required field is absent, do not assume it satisfies the rule"). On this reading the agent does not read L3 receipts as permissive — the agent commits at L3 because that's the first rung with substantive case content, then *learns* at L4 that the policy demands stricter epistemic discipline.

The corpus does not adjudicate between (A) and (B) cleanly, but the **direction of the L3→L4 backoff weakly favours (A)**: the 46-record backoff concentrates on ambiguous-rule records (PROC-005's 29/40 → 1/40 swing is the dominant single cluster), and the agent's L4 reasoning on those records specifically names the missing-metadata gap. That pattern is more structurally consistent with "L3 gave permission the agent shouldn't have taken; L4 told it to back off" (Reading A) than with "L4 is teaching the agent something new" (Reading B). Reading B is not falsified — it remains a viable interpretation. Phase 3.3 should commit weakly to (A) and flag (B) as the alternative E3 must disentangle.

## Implications for E3

- **An L3.5 variant — precedents WITHOUT L4 policy text** — would isolate which direction the anchoring runs. If L3.5 verdicts look like L3 (committed) rather than L4 (rebound), Reading A is sharpened. If L3.5 verdicts look like L4 (rebound), Reading B is sharpened.
- **A larger Permuted-Policy diagnostic at the L3 rung** — currently the diagnostic is L4-only. An L3_PERMUTED variant (precedents intact, no policy text) would test whether the agent commits to verdicts that contradict the (absent) policy spirit on the basis of precedents alone.
- **Both asks belong in E3's experiment_design.md before pre-registration lock.**

## Anti-claims

- This finding does **not** establish that L3 receipts are "manipulating" the agent. The L0..L2 ladders did not include receipts and the agent had no precedents to weigh. L3 is the *first* rung where precedent material exists, so rung and content are confounded. E3's L3.5 variant separates them.
- This finding does **not** establish that L4 is "doing nothing". L4 is doing the L3→L4 backoff (46 records moved DENY→REVIEW) and the unambiguous-rule obedience lift (57.1% at L4 vs 28.6% at L3 on PROC-001/002 records). The claim is about *where the first behavioural break lands*, not that L4 is inert.
- This finding does **not** support the colloquial reading "L3 makes the model worse". The L3 verdicts are not wrong-in-aggregate — many of the 107 fresh L3-DENYs are records MeshQu also DENYs. The claim is about *commitment rate change*, not *commitment correctness*.
- This finding does **not** generalise to other models or other substrates. The corpus is single-model (`gpt-5.4-2026-03-05`) on a single procurement substrate. E3's cross-model replication is the mechanism by which generalisation gets earned.
