# Predictions — Experiment 2

> **Status:** DRAFT. Predictions are not yet locked.
>
> **Lock target:** tag `v0.2-predictions-locked` once `context_ladder_design.md` finalises and this document has been reviewed. The lock commit must contain both files at their final pre-run state and the policy snapshot JSON persisted to `policy/policy-snapshot-cbf12348.json`.
>
> **What a pre-registration commits to:** the data we will collect, the statistics we will compute, the thresholds that determine whether each prediction holds. Pre-registration does not commit to a successful prediction; it commits to honest reporting of whichever outcome the data shows.

---

## Predictions

### P1 — REVIEW rate decreases monotonically L0 → L4

The fraction of records on which the agent's verdict is REVIEW decreases at each step of the ladder. Formally:

> `review_rate(L0) ≥ review_rate(L1) ≥ review_rate(L2) ≥ review_rate(L3) ≥ review_rate(L4)`

**Falsification:** any pair `(Li, Li+1)` where `review_rate(Li+1) > review_rate(Li) + ε`, with `ε = 1.5 percentage points` as the within-experiment noise tolerance (calibrated to the 283-record sample size at p<0.05).

**Why this is a prediction worth running:** the alternative — non-monotonic or U-shaped REVIEW rate — would indicate that some intermediate context level is *worse* than no context (e.g. "policy fragments confuse the agent"). That is a published-result-worthy finding, just a different one.

### P2 — Naive agreement with MeshQu's verdict increases monotonically L0 → L4

Naive agreement = (count of records where `agent_verdict == meshqu_verdict`) / 283.

> `agreement(L0) ≤ agreement(L1) ≤ agreement(L2) ≤ agreement(L3) ≤ agreement(L4)`

E1's L0 baseline: 7/283 = 2.5%. E2's L0 should reproduce this within noise.

**Falsification:** any pair where `agreement(Li+1) < agreement(Li) - ε`, with the same 1.5 pp noise band as P1.

### P3 — At L4, agent commits to DENY on ≥30% of MeshQu's 139 DENY records

The agent at L4 stops producing exclusively REVIEW/ALLOW verdicts. At least 30% of the records MeshQu DENY-ed are also DENY-ed by the L4 agent.

> `count(agent_L4_verdict == DENY ∧ meshqu_verdict == DENY) / 139 ≥ 0.30`

**Falsification:** the ratio is <30%.

**Stakes:** P3 holding is the first signal that explicit governance context unlocks verdict commitment. Combined with P4 + P5, it distinguishes commitment-via-reasoning from commitment-via-echoing.

### P4 — Naive agreement at L4 stays at or below E1's CF-C counterfactual ceiling (29%)

E1 F006 computed a counterfactual: if MeshQu's policy were authored with a REVIEW band on PROC-005 (the missing-method case), agent-vs-MeshQu agreement would rise from 2.5% to 29% on the same corpus. That counterfactual ceiling is the mathematical limit a reasoning 3-state agent can hit against a 2-state policy on this corpus.

> `agreement(L4) ≤ 0.29 + tolerance`

Tolerance: 3 pp (allows the agent to slightly exceed the ceiling if it makes verdicts that the counterfactual analysis didn't anticipate, e.g. correctly recognising the CF-A and CF-B records that didn't shift in F006).

**Falsification:** `agreement(L4) > 32%`.

**Why this is the echo-trap detector half-1:** if the L4 agent significantly exceeds the counterfactual ceiling, it is producing agreement *beyond* what a reasoning 3-state agent should achieve on a 2-state policy. The most parsimonious explanation is that the agent is no longer reasoning — it is pattern-matching the policy text and producing the binary verdict directly. That would be an interesting finding (about LLMs imitating rule-engines under explicit context), but it is not the moat-story.

### P5 — At L4, agent reasoning text cites specific rule codes ≥50% of the time

E1 P3 documented zero specific rule-code or clause citations across all 283 records (the agent's `recommended_action` text was consistently generic). At L4, the agent has the rule codes in the prompt; if it is using them in any way other than purely as scaffolding, the codes should appear in its reasoning.

> `count(agent_L4_reasoning_text contains rule code from {PROC-001-S53, PROC-002-AUTHORITY, …}) / 283 ≥ 0.50`

**Falsification:** <50%.

**Why this is the echo-trap detector half-2:** P5 measures whether the agent is engaging with the rule structure at all. The combination with P3 and P4 yields a four-way matrix:

| | P3 holds (commits to DENY) | P3 falsified |
|---|---|---|
| **P5 holds (cites rules)** | Reasoning with context (moat-story) IF P4 also holds | Reasons about rules but stays cautious — confidence floor for LLMs in compliance |
| **P5 falsified (no citation)** | Commits without engaging — concerning; possibly accidental hit | LLMs are intrinsically over-cautious regardless of context |

The "Reasoning with context" cell is the only outcome that *both* differentiates E2 from E1 *and* clears the echo-trap. Any other cell is still a publishable finding.

### P6 — Verdict shifts cluster on records where the operative rule is PROC-005-OPEN-TENDER

E1 F006 documented that PROC-005-OPEN-TENDER fired in 131 of 139 DENY records (94% of MeshQu's DENYs) and corresponded to "missing-method" — substrate-driven absence of a procurement-method flag, not buyer misconduct. F006's CF-C counterfactual shifted exactly 75 records (PROC-005-driven DENYs) into the REVIEW band.

P6 predicts that if E2's L4 agent shifts verdicts compared to L0, those shifts will concentrate on PROC-005-driven records — because the missing-method substrate condition is the kind of thing explicit policy guidance can *teach the agent to handle*, whereas e.g. a publication-delay-only DENY is a straightforward timing rule that may not need policy guidance to commit on.

> Of the records that move from L0=REVIEW to L4=DENY: ≥60% have PROC-005-OPEN-TENDER as one of the operative MeshQu violations.

**Falsification:** <60%.

**Why this prediction matters:** confirmation tightens F006's "binary policy projects gradient information" claim by adding a second test — *explicit context resolves the same gradient*. Falsification would mean the shifts are distributed differently, which itself is interesting and would constrain the F006 narrative.

### P7 — Token cost scales roughly linearly with level

Input-token consumption at each level grows approximately linearly with cumulative context size.

> `cost(Li+1) - cost(Li) ≈ marginal_payload(Li+1) ± 20%`

**Falsification:** any level shows >20% deviation from linear, after accounting for prompt-caching effects if any are enabled.

**Why this is a prediction:** the alternative — sub- or super-linear scaling — would indicate something unexpected in the model's pricing or tokenisation under structured context. Worth reporting either way.

## Negative predictions — what we explicitly do NOT predict

Documenting absence as well as presence:

- **NOT predicted:** that L4 agreement matches MeshQu's verdicts perfectly (>50%). The 3-state-vs-2-state cardinality mismatch caps reasoned agreement at the CF-C ceiling (29% + tolerance). Higher agreement would trigger the echo-trap detector.
- **NOT predicted:** that the agent's verdict at L4 is "correct" in any external sense. MeshQu's verdict is the comparator, not ground truth.
- **NOT predicted:** that the agent reasons better at higher levels. We measure verdict shifts and reasoning-text properties, not reasoning quality on its own.
- **NOT predicted:** that the L1 prose summary is sufficient. L1 may or may not move the agent; either result is a finding.
- **NOT predicted:** that the foundation model's behaviour at L4 generalises to other models. Same-model, same-temperature is the locked frame.

## What pre-registration does NOT cover

- The number of records that fall into each per-record-trajectory bucket (stable-REVIEW, convergent, late-DENY, etc.). This is descriptive analysis on the data, computed post-hoc; we do not predict bucket distributions in advance.
- The specific decision_id used as Worked Example 2 in the writeup. Selected post-hoc as the most illustrative example of a typical trajectory.
- The cross-level reasoning-text-similarity heuristic threshold. Calibrated against the data, not pre-registered.

## Definition of "report honestly"

Each prediction's status in Appendix A of the writeup will be one of:

- **Confirmed** — held within the falsification bounds.
- **Falsified** — outside the falsification bounds. Report what was observed instead.
- **Inverted** — the observation was the opposite shape of the prediction (E1 P1 was an inverted result).
- **Refuted** — the prediction's premise was wrong (e.g. P3 in E1: the prediction assumed the agent would reach for citations; the agent didn't reach for citations at all).
- **Deferred** — the data does not support a decision (e.g. P6 in E1: corpus contained too few direct-award records).
- **Under-tested** — same as deferred, with a specific reason (e.g. substrate-limited).

The writeup must use these labels exactly. No "partial confirmations" or "trending toward".
