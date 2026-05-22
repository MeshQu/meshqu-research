# F009 — P1 + P2 falsified in inverted direction (L1/L2 increased caution)

**Status**: Falsified (P1 and P2 both pre-registered and both falsified, both in the *inverted* direction relative to the prediction)
**Source experiment**: E2 (procurement-context-gradient) Phase 2 corpus `phase-2-20260522-101324-Z`
**Pre-registered prediction**: P1 (REVIEW rate decreases monotonically L0 → L4) and P2 (naive agreement with MeshQu's verdict increases monotonically L0 → L4)
**Authored**: 2026-05-22
**Restraint discipline**: Reporting a falsified prediction *positively* — the corpus is informative about *which direction* the prediction broke, not just *that* it broke. Taxonomy v1.1 §1.5 applies: do not reach for "anti-sycophancy" framing here because the L1/L2 increase in caution happens *before* any anti-sycophancy nudge is in the prompt.

## Finding

Two pre-registered predictions broke against the corpus in the same surprising direction. P1 predicted monotonic decrease in REVIEW rate L0 → L4; instead L0→L1 *increased* REVIEW (97.5% → 100.0%), L1→L2 held, and L3→L4 *rebounded* (61.1% → 74.2%) — two segments outside the ε=1.5pp tolerance band and both in the wrong direction. P2 predicted monotonic increase in agreement with MeshQu; instead L3 agreement (38.5%) exceeded L4 agreement (25.8%) — a 12.7-pp drop, also in the wrong direction. The cleanest single observation: **adding prose summary (L1) or named rules (L2) on top of L0 makes the agent *more* cautious, not less.** This is the most direct prediction-vs-corpus falsification in the experiment, and it should be reported as the positive finding it is rather than as a hedged disappointment.

## Evidence

- Corpus citation: `procurement-context-gradient/results/notebook/cross_level_analysis/01-per-level-summary.md` §"Verdict distribution by level" + §"D2 — Escalation behaviour"; `02-trajectory-buckets.md` §"L2→L3 is the headline transition"
- Numbers (with units, with denominators):
  - REVIEW rate per level (n=283 per level): L0 **97.5%** (276/283) → L1 **100.0%** (283/283) → L2 **100.0%** (283/283) → L3 **61.1%** (173/283) → L4 **74.2%** (210/283)
  - P1 monotonic-decrease ε band: ±1.5pp per segment. Two violating segments: **L0→L1 (+2.5pp)** and **L3→L4 (+13.1pp)**.
  - Agreement-with-MeshQu rate per level: L0 **2.5%** (7/283) → L1 **0.0%** (0/283) → L2 **0.0%** (0/283) → L3 **38.5%** (109/283) → L4 **25.8%** (73/283)
  - P2 monotonic-increase ε band: ±1.5pp per segment. Violating segment: **L3→L4 (−12.7pp)**.
- L0→L1 specifically: the 7 records that were ALLOW at L0 all became REVIEW at L1 (transition matrix in `02-trajectory-buckets.md` §"L0 → L1"). The agent's L0 ALLOWs are *withdrawn* once the prose summary frames the context as procurement governance.
- L1 and L2 hold a perfect 100% REVIEW spine (n=283 at each). No records escape REVIEW at either rung.
- Worked example (L0→L1 ALLOW withdrawal): `ocds-b5fd17-da6a9dfa-ecde-452d-a2d7-82ced8ab3144` — trajectory ALLOW → REVIEW → REVIEW → REVIEW → REVIEW, MeshQu verdict ALLOW. The agent committed at L0 with no governance framing; once L1's prose summary said *"you are reviewing UK procurement decisions"*, the agent withdrew the commitment and held REVIEW for the rest of the ladder (`02-trajectory-buckets.md` §"Worked-example trajectories", divergent bucket).

## Interpretation

There is one reading the corpus strongly supports and one alternative worth naming.

- **Primary reading**: L1 prose summary and L2 named rules act as **caution-priming context**. The agent reads "you are operating in a procurement governance context" or "the rule set you should consider includes PROC-001…PROC-006" and treats that as an instruction to stay in REVIEW unless evidence forces a commitment. This is the cleanest direct falsification of a "sycophancy"-style prediction in the corpus: P1 was structured around the assumption (inherited from the AI-safety-literature framing the taxonomy v1.1 §1.5 walks back) that more governance context would push the agent toward commitment ("agreement with the authority of the policy"). The corpus shows the opposite — bare governance framing pushes the agent toward *more* caution, not less.
- **Alternative reading**: the L1/L2 prose may be deficient in actionable signal. The agent reads "this is procurement" and "here are the rules" but lacks the substrate detail or precedent material it needs to commit, so it defaults to REVIEW. On this reading the L1/L2 caution lift is a *vacuum effect* (the agent retreats when it lacks evidence), not a *priming effect* (governance framing increasing caution intentionally).

The corpus tilts toward the primary reading because L0 — which has the substrate detail without the governance framing — still emits 7 ALLOWs that L1 immediately withdraws. The substrate is the same at L0 and L1; only the framing changed. Phase 3.3 should commit to the primary reading and acknowledge the alternative.

The L3→L4 segment of P2 (agreement drops from 38.5% to 25.8%) is the same phenomenon F008 documents from a different angle — L4 backs off some L3 commitments, and because many L3 commitments were correct agreements with MeshQu, the backoff reduces aggregate agreement even while it improves epistemic discipline on ambiguous records. Phase 3.3 should not narrate P2's falsification as "the model got worse at L4"; the corpus does not support that. The model got *less committed* at L4, which is a different thing.

## Implications for E3

- **Pre-registration discipline**: P1 and P2 were specified with a monotonic-decrease and monotonic-increase form. The corpus invites a sharper hypothesis class for E3 — non-monotonic with a predicted inflection rung — that the analysis can confirm or refute on the verdict pattern alone. E3's predictions should be specified at the *segment* level (L0→L1, L1→L2, …) rather than as an aggregate trend.
- **L1-only control**: would isolate whether the L1 prose alone (no rule names, no precedents, no policy) causes the ALLOW-withdrawal pattern. The current corpus has L1 = framing + rule names *bundled*; an L1-prose-only variant would disambiguate framing-effect vs rule-list-effect.

## Anti-claims

- This finding does **not** establish that all governance prose makes models more cautious. It establishes that *this prose* + *this model* + *this substrate* did. Generalisation across model, prompt, and domain is E3's job.
- This finding does **not** establish that the agent is "doing the right thing" at L1/L2. Holding 100% REVIEW is not necessarily epistemically correct on every record — MeshQu emits ALLOW on 146/283 records, and the agent's L1/L2 REVIEW on those records may or may not be the right call. The finding is about prediction-vs-corpus direction, not about decision quality.
- This finding does **not** support a "the model is over-cautious" narrative. Over-cautious would require comparing the agent's REVIEW rate to some ground-truth threshold of when REVIEW is warranted; the corpus does not contain that ground-truth signal.
- This finding does **not** invalidate the methodological move of pre-registering directional predictions. The value of P1/P2 is precisely that we can now report which direction the corpus broke; without the pre-registration the L1→L2 lift would be a curiosity rather than a falsification.
