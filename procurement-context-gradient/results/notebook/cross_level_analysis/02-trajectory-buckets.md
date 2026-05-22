# 02 — Trajectory buckets + transition matrices
For each of the 283 records this notebook walks the (L0, L1, L2, L3, L4) verdict sequence and bins the trajectory per `experiment_design.md` §Per-record trajectory analysis. Bucket definitions are reproduced inline so the file is readable on its own.

## Bucket definitions
- **Stable-REVIEW**: REVIEW at every level.
- **Stable-ALLOW**: ALLOW at every level.
- **Convergent**: starts REVIEW at L0, ends at MeshQu's verdict (ALLOW or DENY), no return-to-REVIEW after leaving REVIEW.
- **Late-DENY**: REVIEW at L0..L3, DENY at L4 only.
- **Divergent**: non-monotonic — verdict drops back to REVIEW after leaving it, ends on a non-MeshQu verdict, or otherwise non-monotonic.

## Bucket distribution
| Bucket | Count | Share of 283 |
|---|---:|---:|
| stable-REVIEW | 154 | 54.4% |
| stable-ALLOW | 0 | 0.0% |
| convergent | 61 | 21.6% |
| late-DENY | 12 | 4.2% |
| divergent | 56 | 19.8% |

## Worked-example trajectories
| Bucket | OCID | L0 → L4 | MeshQu |
|---|---|---|---|
| stable-REVIEW | `ocds-b5fd17-1e121fb4-d6c8-4fa4-a0b3-457928c46db3` | REVIEW → REVIEW → REVIEW → REVIEW → REVIEW | ALLOW |
| stable-REVIEW | `ocds-b5fd17-cf1a592f-cf43-4a0b-be31-a8ce99bd81a1` | REVIEW → REVIEW → REVIEW → REVIEW → REVIEW | ALLOW |
| stable-REVIEW | `ocds-b5fd17-9830af26-953b-4427-8b5e-cf1a7da9d371` | REVIEW → REVIEW → REVIEW → REVIEW → REVIEW | ALLOW |
| convergent | `ocds-b5fd17-f5d7b902-87b4-4f05-84bc-2dcab9047651` | REVIEW → REVIEW → REVIEW → DENY → DENY | DENY |
| convergent | `ocds-b5fd17-e94295cf-e7be-474d-9de3-24dff20aacf7` | REVIEW → REVIEW → REVIEW → DENY → DENY | DENY |
| convergent | `ocds-b5fd17-8beac1c6-18eb-45f8-939f-a03b1e70d1c8` | REVIEW → REVIEW → REVIEW → DENY → DENY | DENY |
| late-DENY | `ocds-b5fd17-ea8fee4a-2905-42bd-94aa-ae1cb2cf0869` | REVIEW → REVIEW → REVIEW → REVIEW → DENY | DENY |
| late-DENY | `ocds-b5fd17-09d0f7a1-208c-497d-88bf-0c22ba865858` | REVIEW → REVIEW → REVIEW → REVIEW → DENY | DENY |
| late-DENY | `ocds-b5fd17-0786919f-4875-42c3-99ac-7db01e366670` | REVIEW → REVIEW → REVIEW → REVIEW → DENY | DENY |
| divergent | `ocds-b5fd17-da6a9dfa-ecde-452d-a2d7-82ced8ab3144` | ALLOW → REVIEW → REVIEW → REVIEW → REVIEW | ALLOW |
| divergent | `ocds-b5fd17-6d469dd2-cc2e-4180-9cb4-9361a037ec40` | REVIEW → REVIEW → REVIEW → DENY → REVIEW | DENY |
| divergent | `ocds-b5fd17-a29a701a-df51-43ac-b9ad-031bc8a6ee81` | REVIEW → REVIEW → REVIEW → DENY → REVIEW | DENY |

## Transition matrices
For each adjacent level pair, the count of records whose verdict transitions between those two levels. Rows = source level verdict; columns = destination verdict.

### L0 → L1
| | → ALLOW | → REVIEW | → DENY | Row total |
|---|---|---|---|---|
| ALLOW | 0 | 7 | 0 | 7 |
| REVIEW | 0 | 276 | 0 | 276 |
| DENY | 0 | 0 | 0 | 0 |

### L1 → L2
| | → ALLOW | → REVIEW | → DENY | Row total |
|---|---|---|---|---|
| ALLOW | 0 | 0 | 0 | 0 |
| REVIEW | 0 | 283 | 0 | 283 |
| DENY | 0 | 0 | 0 | 0 |

### L2 → L3
| | → ALLOW | → REVIEW | → DENY | Row total |
|---|---|---|---|---|
| ALLOW | 0 | 0 | 0 | 0 |
| REVIEW | 3 | 173 | 107 | 283 |
| DENY | 0 | 0 | 0 | 0 |

### L3 → L4
| | → ALLOW | → REVIEW | → DENY | Row total |
|---|---|---|---|---|
| ALLOW | 0 | 3 | 0 | 3 |
| REVIEW | 0 | 161 | 12 | 173 |
| DENY | 0 | 46 | 61 | 107 |

## L2→L3 is the headline transition
At L2 all 283 records are REVIEW. At L3 the same 283 split: REVIEW → REVIEW: 173, REVIEW → DENY: 107, REVIEW → ALLOW: 3. The precedent rung is what unlocks the agent's first verdict commitments at scale. The L3→L4 step then takes **46 of 107 L3-DENYs** back to REVIEW — the full policy text *reduces* committed-verdict count on a non-trivial slice. P1 and P2 are both falsified by the L3→L4 segment.

### L3 → L4 detail
- 46 records went L3:DENY → L4:REVIEW (agent backed off its commitment when given the policy text)
- 61 records went L3:DENY → L4:DENY (commitment survived the policy text)
- 12 records went L3:REVIEW → L4:DENY (policy text triggered fresh commitment)
- 161 records went L3:REVIEW → L4:REVIEW (the persistent-REVIEW spine)
- 3 L3:ALLOW records moved at L4
