# 06 — Per-rule verdict shifts + context-positioning sub-metric
This notebook tests P6 ('verdict shifts cluster on PROC-005-OPEN-TENDER records') and the context-positioning sub-metric pre-registered in `experiment_design.md` §Analysis layer.

## P6 — verdict shifts by operative rule
For each operative rule (the primary critical violation MeshQu emitted), this table reports the agent's verdict distribution at each level on records where that rule is the primary operative one.

### PROC-001-S53 (n=53)
| Level | ALLOW | REVIEW | DENY |
|---|---:|---:|---:|
| L0 | 0 | 53 | 0 |
| L1 | 0 | 53 | 0 |
| L2 | 0 | 53 | 0 |
| L3 | 0 | 3 | 50 |
| L4 | 0 | 11 | 42 |

### PROC-002-AUTHORITY (n=44)
| Level | ALLOW | REVIEW | DENY |
|---|---:|---:|---:|
| L0 | 0 | 44 | 0 |
| L1 | 0 | 44 | 0 |
| L2 | 0 | 44 | 0 |
| L3 | 0 | 17 | 27 |
| L4 | 0 | 14 | 30 |

### PROC-005-OPEN-TENDER (n=40)
| Level | ALLOW | REVIEW | DENY |
|---|---:|---:|---:|
| L0 | 0 | 40 | 0 |
| L1 | 0 | 40 | 0 |
| L2 | 0 | 40 | 0 |
| L3 | 0 | 11 | 29 |
| L4 | 0 | 39 | 1 |

### none (n=146)
| Level | ALLOW | REVIEW | DENY |
|---|---:|---:|---:|
| L0 | 7 | 139 | 0 |
| L1 | 0 | 146 | 0 |
| L2 | 0 | 146 | 0 |
| L3 | 3 | 142 | 1 |
| L4 | 0 | 146 | 0 |

## P6 evaluation
Of the 73 records that moved L0=REVIEW → L4=DENY, **69 (94.5%)** have PROC-005-OPEN-TENDER in their operative MeshQu violation set. P6 predicted ≥60%. Observed: **94.5%** → **confirmed**.

## Context-positioning sub-metric
The L4 policy contains 6 rules in a JSON array. Array position is fixed across the run. The pre-registered question: does the agent's L0→L4 commitment rate (REVIEW→ALLOW/DENY) vary with the array-position of the operative rule?

### Rule positions in the L4 policy JSON array
| Position | Rule code |
|---:|---|
| 1 | PROC-001-S53 |
| 2 | PROC-002-AUTHORITY |
| 3 | PROC-003-DEBARMENT |
| 4 | PROC-004-COI |
| 5 | PROC-005-OPEN-TENDER |
| 6 | PROC-006-MOD-CAP |

### Commitment rate (L0=REVIEW → L4≠REVIEW) by primary-rule array position
| Array position | Rule code | n records | L4 commitment rate |
|---:|---|---:|---:|
| 1 | PROC-001-S53 | 53 | 79.2% |
| 2 | PROC-002-AUTHORITY | 44 | 68.2% |
| 5 | PROC-005-OPEN-TENDER | 40 | 2.5% |

**Confound warning**: array position and rule-type are perfectly correlated in this corpus. Position 1 = PROC-001 (unambiguous timing rule, easy commitment); position 5 = PROC-005 (ambiguous missing-method rule, hard commitment). The 76.7-pp difference between position-1 and position-5 commitment rates is dominated by **rule ambiguity**, not by **position in the array**. The pre-registered sub-metric cannot disambiguate the two in this single-pass corpus. A follow-up that permutes the rule array order across runs would isolate the positional effect; that is deferred to E2-followup or E3. **Under-tested** is the honest disposition for the array-position sub-claim.
