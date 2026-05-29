# E3 Phase 2 — `phase-2-20260529T092611-Z`

- **Started:** 2026-05-29T09:26:18+00:00
- **Finished:** 2026-05-29T10:46:51+00:00
- **Scale:** `phase-2`
- **Mode:** live
- **Pre-registration tag:** `v0.3-predictions-locked`
- **Pacing:** 0.50s between live calls
- **Receipts written:** 1332 / 1332 expected
- **Errors:** 0

## Phase-2 matrix

- **Main-arm records:** 283 (full E1 frozen corpus from `meshqu_runner.substrate_cache.load_cached_records`)
- **Diagnostic-arm OCIDs (positions 0..99 of `planning/diagnostic_subset.json`):** 100
- **Total receipts target:** 1332 (4 main arms × 283 + 2 diag arms × 100)

## Per-arm latency + token + cost

| Arm | Records | Receipts | p50 latency | p95 latency | Prompt-tok total | $ cost |
|---|---:|---:|---:|---:|---:|---:|
| `arm_a` | 283 | 283 | 2078ms | 3140ms | 523548 | $2.6177 |
| `arm_b` | 283 | 283 | 2169ms | 3264ms | 408671 | $2.0434 |
| `arm_c` | 283 | 283 | 2152ms | 3372ms | 460418 | $2.3021 |
| `l4_without_nudge` | 283 | 283 | 2259ms | 3326ms | 729551 | $3.6478 |
| `diagnostic_primary` | 100 | 100 | 2352ms | 3406ms | 260110 | $1.3006 |
| `diagnostic_claude` | 100 | 100 | 3388ms | 4346ms | 394590 | $13.3174 |

Cost is informational only — current public list-price rates + completion-tokens estimated at 25% of prompt-tokens (an envelope; the experiment account's actual billing may differ via tier multipliers and caching discounts).

## Dry-run → Phase 2 accuracy (±15% band)

If observed Phase-2 mean prompt-tokens per record is within ±15% of the pinned dry-run baseline, the dry-run-derived cost envelope ($25.21 per the Phase-1 readiness report) held. Outside the band → record the drift in the Phase-2 writeup.

| Arm | Dry-run mean (tok/rec) | Phase-2 mean (tok/rec) | Ratio | Within ±15%? |
|---|---:|---:|---:|:---:|
| `arm_a` | 1843.0 | 1850.0 | 1.004 | yes |
| `arm_b` | 1443.2 | 1444.1 | 1.001 | yes |
| `arm_c` | 1626.4 | 1626.9 | 1.000 | yes |
| `l4_without_nudge` | 2577.4 | 2577.9 | 1.000 | yes |
| `diagnostic_primary` | 2599.5 | 2601.1 | 1.001 | yes |
| `diagnostic_claude` | 3943.6 | 3945.9 | 1.001 | yes |

## Phase 2 totals

Final per-arm receipts + observed tokens + observed $ cost for the full 1,332-receipt Phase-2 corpus. No further extrapolation — these are the receipts.

| Arm | Receipts | Prompt-tok total | Mean (tok/rec) | $ cost |
|---|---:|---:|---:|---:|
| `arm_a` | 283 | 523548 | 1850.0 | $2.62 |
| `arm_b` | 283 | 408671 | 1444.1 | $2.04 |
| `arm_c` | 283 | 460418 | 1626.9 | $2.30 |
| `l4_without_nudge` | 283 | 729551 | 2577.9 | $3.65 |
| `diagnostic_primary` | 100 | 260110 | 2601.1 | $1.30 |
| `diagnostic_claude` | 100 | 394590 | 3945.9 | $13.32 |
| **TOTAL** | 1332 | | | **$25.23** |

## Aggregate completeness

PASS — every main-subset OCID appears in every main arm (arm_a / arm_b / arm_c / l4_without_nudge); every diagnostic-subset OCID appears in both diagnostic arms (diagnostic_primary / diagnostic_claude). No silent drops.

## Errors

(none)

## Next step

    python3 scripts/verify_dry_run_e3.py phase-2-20260529T092611-Z/ --scale phase-2

(run from inside `procurement-context-disambiguation/runner/` with the run dir resolved relative to `results/runs/`.)
