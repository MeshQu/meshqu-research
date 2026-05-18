# Finding 006 — Binary policy verdict projection collapses the agent/policy agreement signal; PROC-005-OPEN-TENDER dominates the loss

**Created:** 2026-05-18
**Status:** stable (counterfactual analysis run against the corpus; numerical results below)
**Bears on:** methodology, P1, P6, AARM Bundle A (empirical support)

## The claim

The experiment policy was authored binary — every rule at `severity: critical`, so any violation produces DENY. The foundation model agent, by contrast, reasons in three states (ALLOW / REVIEW / DENY) and chose REVIEW on 276 of 283 unique decisions in the corpus run (`dry-run-7ddf7274-…`). **Naive verdict-equality agreement is 7/283 = 2.5%.** This is mechanically misleading: the agent's REVIEW responses correlate strongly with records the policy WOULD have produced REVIEW for, if the policy had been authored with gradient bands instead of binary thresholds.

Counterfactual re-projection against the corpus (no re-run; analysis-only) shows:

- Demoting PROC-001-S53 to a 3-tier band (≤30 ALLOW, 31–60 REVIEW, 60+ DENY) shifts **0 records** — because PROC-001-S53 violations co-occur with other criticals on every record.
- Adding PROC-002-AUTHORITY 3-tier (£500k–£1M REVIEW, £1M+ DENY) shifts **2 more records** — same co-occurrence problem.
- Demoting PROC-005-OPEN-TENDER from critical-by-default to REVIEW (no natural numeric band, but the rule's intent — "this above-threshold record didn't open-tender; explain" — maps cleanly to the AARM Bundle A "DEFER" verdict) shifts **73 additional records**. Combined with PROC-001 + PROC-002 3-tier, total agreement becomes **82/283 = 29%** — an 11× improvement over the binary baseline.

**The empirical headline isn't "PROC-001-S53 needs a REVIEW band." It's "PROC-005-OPEN-TENDER's binary nature dominates the DENY column."** Roughly three quarters of the corpus's DENYs are driven by `procurement_method_open_flag` absence; under a hypothetical Bundle-A-style DEFER verdict for "we don't have enough context on the procurement method," most of those records would synthesise with the agent's REVIEW responses into actual agreement.

## Evidence

### Violation co-occurrence in the corpus (n=283 unique decisions)

```
144  (none, ALLOW)
 41  PROC-005-OPEN-TENDER (alone)
 39  PROC-002-AUTHORITY + PROC-005-OPEN-TENDER
 27  PROC-001-S53 + PROC-002-AUTHORITY + PROC-005-OPEN-TENDER
 24  PROC-001-S53 + PROC-005-OPEN-TENDER
  5  PROC-002-AUTHORITY (alone)
  3  PROC-001-S53 + PROC-002-AUTHORITY
```

PROC-001-S53 fires alone in **zero** records. It always co-occurs with PROC-002-AUTHORITY (3 instances) or PROC-005-OPEN-TENDER (24+27=51 instances) or both (27 instances). Total PROC-001-S53 violations: 54. **PROC-005-OPEN-TENDER fires in 131 of 139 DENY records (94%).** PROC-005 is the operative critical in the corpus.

### Counterfactual scenarios, side-by-side

| Scenario | DENY | REVIEW | ALLOW | Agreement w/ agent |
|---|---|---|---|---|
| Baseline (as-ratified binary) | 139 | 0 | 144 | **7 / 283 (2.5%)** |
| CF-A: PROC-001 3-tier only | 139 | 0 | 144 | 7 (no change) |
| CF-B: PROC-001 + PROC-002 3-tier | 137 | 2 | 144 | 9 (+2) |
| CF-C: aggressive (also demote PROC-005) | 64 | 75 | 144 | **82 / 283 (29%)** |

The CF-C row is the AARM-Bundle-A-realistic counterfactual: it represents a policy authored against the planned C3 DEFER verdict, where "procurement-method-open-flag absent" routes to a "needs more context" pause rather than an immediate DENY.

### Agreement decomposition under CF-C

Of the 82 agreements under CF-C:

- **7** are the baseline ALLOW/ALLOW agreements (records with no violations, both verdicts ALLOW).
- **75** are NEW agreements created by the counterfactual — records where MeshQu's binary verdict was DENY but the agent's REVIEW response would have matched if the policy had used a REVIEW (or DEFER) band.

The 75 new agreements correspond exactly to the 75 records that shift DENY → REVIEW under CF-C. In every one of these records, the agent had chosen REVIEW under the baseline (so the shift creates agreement, not new disagreement).

### Methodological implication

The naive baseline agreement statistic (7/283 = 2.5%) is **not a finding about the agent being wrong**. It's a finding about the cardinality mismatch between a 3-state agent and a 2-state policy. The "true" agent-policy alignment lies somewhere between 2.5% and 29% depending on how one would prefer to read agent-REVIEW outputs:

- If "agent REVIEW" is read as **"the agent doesn't know"**, then the binary policy is the more decisive system and the 7/283 figure stands. The writeup's framing then becomes "agent is over-cautious; policy is more useful."
- If "agent REVIEW" is read as **"the agent has identified a gradient that the binary policy collapses"**, then CF-C's 82/283 is the more honest figure. The writeup's framing becomes "agent reasons in gradient space; policies authored in binary cliff-edges lose information the agent encoded; AARM Bundle A C3 DEFER closes this gap."

Both interpretations are defensible. The CF-C analysis quantifies the gap between them.

## What the corpus tells us about the agent's REVIEW pattern

Of the 276 records where the agent said REVIEW:

- 144 had MeshQu verdict ALLOW (no violations). Agent was being cautious about clean records. The agent's `recommended_action` text on these typically named generic compliance categories ("verify award procedure", "obtain procedure rationale") even though the policy itself produced no violations. This is **agent over-caution that the binary policy correctly contradicted** — score one for the policy.
- 132 had MeshQu verdict DENY. The agent's `recommended_action` text on these mostly named specific rule territories ("Verify procedure basis and publication compliance" → PROC-005 + PROC-001-S53; "Verify procedure basis and notice trail" → PROC-005 + PROC-001-S53). This is **agent caution that maps directly to MeshQu's specific violations** — but the agent declines to commit to DENY. Score 0/132 for the agent on naive equality, but ~75/132 for the agent on substantive-meaning equality (those are the records that would shift under CF-C).

The split is roughly half-and-half. The agent's REVIEW class isn't monolithic; ~half is reasonable caution on clean records (over-cautious) and ~half is substantive recognition of specific compliance concerns (under-confident commitment).

## Caveats

- **CF-C demotes PROC-005 uniformly** — there's no natural numeric threshold ("procurement_method_open_flag" is binary: present or missing). The defensible interpretation is "absence = needs more context (DEFER)" per AARM C3, not "absence = REVIEW per a gradient band." The counterfactual is more accurately "what if PROC-005 mapped to DEFER under Bundle A" than "what if PROC-005 had a 3-tier band."
- **Counterfactual ≠ retroactive policy re-authoring.** The pre-registration discipline is intact: this is post-hoc supplementary analysis against the as-ratified corpus, not a redefinition of what was tested. The writeup will name the as-ratified verdict distribution as the headline result and the counterfactual as analysis-quality supplementary evidence.
- **The 75-record shift is large but specific to this corpus.** A different OCDS window, a different substrate, or a different agent prompt could produce different results. The methodology generalises; the specific numbers don't.
- **The 33 records with PROC-001-S53 in the 31–60 day band that DON'T shift under CF-B** are a useful subset for the writeup's "compounding violations" story: late publication on records that are ALSO over-threshold and ALSO missing-method are pre-dominantly the substrate's "real compliance failures" — multiple rules co-firing because the underlying procurement was procedurally messy, not a single-rule edge case.

## What this changes about the writeup

**Section 5b (worked-example results)**:

- Headline: 7/283 (2.5%) agreement under the as-ratified policy.
- Supplementary: 82/283 (29%) agreement under a hypothetical AARM Bundle A C3 DEFER-equipped policy.
- Frame: the 11× improvement under the counterfactual is **not a fix to apply** (predictions stay locked); it's empirical evidence FOR the platform roadmap's already-planned Verdict v2 work.

**Section 6 (reasoning is data)**:

- The agent's `recommended_action` text consistently names specific rule territories ("procedure basis", "publication compliance", "notice trail"). On ~half the corpus, those names map to MeshQu's actual violations. The agent isn't producing generic caution — it's producing rule-territory-specific caution that the binary policy projects away.

**Section 7 (limitations / methodology in action)**:

- The cardinality-mismatch between agent (3 states) and policy (2 states) is a real methodological caveat. Naive agreement statistics need explicit reframing, and the counterfactual analysis shows what the reframed statistic looks like under defensible alternative policy authoring.

**Section 8 (what's next)**:

- AARM Bundle A — Verdict v2 (Q1–Q2 2027) ships MODIFY + DEFER/STEP_UP + classification dimension. This corpus is the prior comparator; future Verdict-v2 corpora would be the post-comparator. The "11× agreement improvement under a Bundle-A-realistic policy" estimate is a direct platform-investment justification line.

## Cross-references

- Predictions: `planning/predictions.md` — P1 (agent-vs-policy disagreement rate), P6 (direct-award disagreement clusters)
- AARM bundle dossier: `.harness/aarm-roadmap/bundles/BUNDLE-A-verdict-v2.md` in the tradequ monorepo
- AARM candidate dossiers: `.harness/aarm-roadmap/candidates/{C1,C2,C3}-*.md` in the tradequ monorepo
- Prior live observation: `2026-05-18-full-run-live-notes.md` §"AARM Bundle A — the platform roadmap already names this gap"
- UX correlate: tradequ PR #541, `docs/ux/policy-authoring-2026-05.md` §F14 (severity → verdict mapping invisible at edit time)
- Run notebook: `2026-05-18-full-run.md`
