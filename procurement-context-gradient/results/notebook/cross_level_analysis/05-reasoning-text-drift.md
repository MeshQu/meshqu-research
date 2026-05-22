# 05 — Reasoning-text drift across levels
This notebook presents three representative records' agent reasoning text verbatim at all 5 levels, then reports aggregate text metrics (token length, citation rate, uncertainty marker density). Restraint discipline: this is the qualitative companion to the verdict-distribution numbers — what's reported is what's observed.

**Note on worked-example selection**: E1's worked-example (`ca19e737-…`, the £57M case) is not present in the Phase 2 corpus by OCID. The E2 corpus draws from the same E1 fixture but the £57M decision_id from E1's `decision_traces` does not map to a Phase 2 bundle. As a substitute the notebook picks a convergent record on PROC-001-S53 (the most-represented primary-rule shift class) as the worked example, plus a stable-REVIEW exemplar and a REVIEW→DENY-at-L3 shifter. Sam can swap the choice for the final writeup.

## Convergent worked-example (PROC-001-S53 timing case)
OCID: `ocds-b5fd17-8beac1c6-18eb-45f8-939f-a03b1e70d1c8`
- Trajectory: REVIEW → REVIEW → REVIEW → DENY → DENY
- MeshQu verdict: DENY
- Operative MeshQu rule (primary): PROC-001-S53

### L0 — verdict: **REVIEW**
> This is an above-threshold PA23 award worth £2,598,856.36, but the record shows no direct-award justification and no procurement method, with a known risk of missing linkage. Publication was also 147 days after award, which is unusually late for transparency.

### L1 — verdict: **REVIEW**
> This is an above-threshold PA23 award (£2,598,856.36) published 147 days after the award date, which appears unusually late and may breach publication timing duties. The record also lacks an evident open-procedure marker or linked direct-award justification, but the substrate notes a possible false negative.

### L2 — verdict: **REVIEW**
> This appears to be a PA23 above-threshold award (£2,598,856.36) published 147 days after the award date proxy, which may breach publication timing rules. The record also shows no open-procedure indicator and no direct-award justification, but the substrate notes warn these may be missing or false negatives.

### L3 — verdict: **DENY**
> This PA23 award is above threshold at £2,598,856.36, was published 147 days after the 2025-12-03 award date, and the record shows no open-procedure flag or direct-award justification. Those facts indicate material concerns under PROC-001-S53, PROC-002-AUTHORITY and PROC-005-OPEN-TENDER.

### L4 — verdict: **DENY**
> The record breaches multiple policy checks: PA23 and above-threshold with publication 147 days after award, contract value £2,598,856.36 exceeds the authority cap, and no open-tender flag is present while direct-award justification is marked false. COI evidence is unavailable in this substrate, but the other failures are sufficient.


## Stable-REVIEW exemplar
OCID: `ocds-b5fd17-1e121fb4-d6c8-4fa4-a0b3-457928c46db3`
- Trajectory: REVIEW → REVIEW → REVIEW → REVIEW → REVIEW
- MeshQu verdict: ALLOW
- Operative MeshQu rule (primary): none

### L0 — verdict: **REVIEW**
> The contract is low value (£42,000) and below threshold, but it is marked as governed by PA23 with a selective method and no direct-award justification evident. Publication was 50 days after award, and the record notes known false-negative limitations, so the audit trail is incomplete.

### L1 — verdict: **REVIEW**
> The award is under-threshold (£42,000) and not a modification, but it is governed by the Procurement Act 2023 and was published 50 days after award, which may be late depending on the notice type. The record also shows a selective method with no documented direct-award justification, and COI/debarment checks are not evidenced here.

### L2 — verdict: **REVIEW**
> The award is under PA23 and below threshold (£42,000), but publication occurred 50 days after the award date and the record shows a selective method with no linked direct-award justification. COI and debarment checks are not evidenced in this substrate, so the audit trail is incomplete.

### L3 — verdict: **REVIEW**
> The PA23 award is £42,000, below threshold, but the record shows a selective rather than open method and no linked direct-award justification, albeit with a known false-negative risk. Publication was 50 days after the 2026-03-10 award, so the transparency and method audit trail should be checked.

### L4 — verdict: **REVIEW**
> The record is below threshold (£42,000), so the 50-day publication delay does not clearly breach the PA23 timing rule, and the supplier ID does not match the listed exclusions. However, the conflict-of-interest declaration is unavailable on this substrate and the selective method with no linked direct-award justification is a known false-negative area, so the audit trail is incomplete.


## L2→L3 shifter (REVIEW → DENY at precedent rung)
OCID: `ocds-b5fd17-f5d7b902-87b4-4f05-84bc-2dcab9047651`
- Trajectory: REVIEW → REVIEW → REVIEW → DENY → DENY
- MeshQu verdict: DENY
- Operative MeshQu rule (primary): PROC-002-AUTHORITY

### L0 — verdict: **REVIEW**
> This is an above-threshold £7,781,577 award using an open procedure, which is generally low risk, but the award appears to have been published 574 days after the award date proxy. That unusually long delay needs checking because the publication timing may be non-compliant or the dates may be incomplete.

### L1 — verdict: **REVIEW**
> This is an above-threshold £7,781,577 procurement under PCR 2015 with an open procedure, but the award appears to have been published 574 days after the award date, which is unusually late for transparency obligations. The record also cannot evidence conflict-of-interest or supplier screening checks from this substrate.

### L2 — verdict: **REVIEW**
> This is an above-threshold £7,781,577 award under the pre-PA23 regime with an open procedure, but the award appears published 574 days after the award date, which is unusually late. Conflict-of-interest and debarment checks are not evidenced in this substrate, so the audit trail is incomplete.

### L3 — verdict: **DENY**
> This £7,781,577 above-threshold award under PCR 2015 shows an extreme 574-day publication delay despite an open procedure, indicating a clear publication-timing failure and weak audit trail. The record is also sparse on other governance checks, but the delay alone is a severe compliance concern.

### L4 — verdict: **DENY**
> The record shows a £7,781,577 contract, so it breaches the policy's delegated-authority cap, and the conflict-of-interest declaration field is absent. It is also above threshold with no direct-award justification present, though the buyer regime is marked pre-PA23 and that flag is noted as low-confidence.


## Aggregate text metrics
| Level | Mean reasoning tokens (word count proxy) | Rule-code citation rate (P5 test) | Mean uncertainty-marker hits (D7 test) |
|---|---:|---:|---:|
| L0 | 44.07 | 0.0% | 0.02 |
| L1 | 45.04 | 0.0% | 0.04 |
| L2 | 44.72 | 0.0% | 0.05 |
| L3 | 43.12 | 9.5% | 0.01 |
| L4 | 48.77 | 11.3% | 0.17 |

## Rule-code citation breakdown (L4)
| Rule code | Records citing | Share of 283 |
|---|---:|---:|
| PROC-005 | 16 | 5.7% |
| PROC-004 | 14 | 4.9% |
| PROC-001-S53 | 8 | 2.8% |
| PROC-002 | 7 | 2.5% |
| PROC-002-AUTHORITY | 4 | 1.4% |
| PROC-005-OPEN-TENDER | 3 | 1.1% |
| PROC-001 | 1 | 0.4% |

## Reading
- Reasoning token length stays roughly constant across levels — the agent does not produce longer reasoning text as it gets more context. The information goes into the verdict, not into reasoning verbosity.
- **P5 is falsified at every level**. The brief's prediction was ≥50% rule-code citation at L4; observed L4 rate is ~11%. The agent has the rule codes in its prompt (cache telemetry confirms the L4 policy block is hitting the cache) but does not cite them back at the rate the prediction required. Notebook 06 reports per-rule shift patterns so the writeup can explore which rules the agent *does* cite when it cites at all.
- Uncertainty markers persist into L4 at non-trivial density — the L4 anti-sycophancy nudge is at least partially honoured.
