# E3 dry-run — `dry-run-20260528T164807-Z`

- **Started:** 2026-05-28T16:48:07+00:00
- **Finished:** 2026-05-28T16:57:08+00:00
- **Mode:** live
- **Pre-registration tag:** `v0.3-predictions-locked`
- **Pacing:** 0.50s between live calls
- **Receipts written:** 140 / 140 expected
- **Errors:** 0

## Dry-run matrix

- **Main-arm OCIDs (positions 0..29 from `planning/diagnostic_subset.json`):** 30
  0. `ocds-b5fd17-00d99d64-a859-460c-9630-7511284e3e29`
  1. `ocds-b5fd17-15a37e29-28a4-4e14-a057-f1bc8f8124d6`
  2. `ocds-b5fd17-9a2263a4-c2d5-4023-b405-882f8eacdd1e`
  3. `ocds-b5fd17-16686c9b-ce2c-48c1-b0d5-e00cd67d36a3`
  4. `ocds-b5fd17-9c543846-5b8c-4ebb-b953-769912769137`
  5. `ocds-b5fd17-1aedfd5e-39bb-4365-8334-19ac3337c727`
  6. `ocds-b5fd17-346522c8-f618-4262-8db7-0b52b750f629`
  7. `ocds-b5fd17-43d88d17-6194-41d5-8751-35a1bf79bdc1`
  8. `ocds-b5fd17-cd41c324-0b76-439a-ad5c-44e1c26e418d`
  9. `ocds-b5fd17-8cac0fcb-4df1-46c1-8a06-9556a2646fbe`
  10. `ocds-b5fd17-119d1c05-7fa8-478f-ac6f-db416fb5b5c9`
  11. `ocds-b5fd17-42d7a9b3-b6de-4576-866d-aa107a1778f9`
  12. `ocds-b5fd17-f55a65b9-251d-4d51-b177-0b10c83f3326`
  13. `ocds-b5fd17-f5052bc7-d3b9-4a56-9bca-fe06c5d44561`
  14. `ocds-b5fd17-2bf8b9d2-89ab-4221-96ad-a969e9017ce4`
  15. `ocds-b5fd17-754b2b9a-0b1e-45b1-9472-c9608c95475e`
  16. `ocds-b5fd17-24a62207-e325-4b1a-a84e-97b8f8bb42ff`
  17. `ocds-b5fd17-e08e7d68-9f48-4abd-9379-174f3b5fc544`
  18. `ocds-b5fd17-4aa9de69-11e7-442c-bc8e-014368c4bb96`
  19. `ocds-b5fd17-4ffed17e-a6a2-4672-951f-b4b5faba137d`
  20. `ocds-b5fd17-2fa34b9a-2c67-425e-8697-53ed47621c2c`
  21. `ocds-b5fd17-7535d7b0-b6bb-4cb3-8ac6-a4ec534d75fb`
  22. `ocds-b5fd17-612ce9e0-3652-4c7b-b553-2eb8816bfe3c`
  23. `ocds-b5fd17-e8b2fd62-5921-4788-955f-4e4bcad68b82`
  24. `ocds-b5fd17-2b968d96-15b3-4fd2-9343-f386b0cb49a6`
  25. `ocds-b5fd17-ac66d536-9ef5-4d5b-af90-1f9abb565822`
  26. `ocds-b5fd17-5054b9c9-fc10-45a8-9aa1-a650ca6e61c9`
  27. `ocds-b5fd17-7e628cef-5bea-49e1-9175-976bd6b73735`
  28. `ocds-b5fd17-b1749ec1-c05e-4f11-bee7-8b72a8571ccc`
  29. `ocds-b5fd17-66343e17-443a-4509-ac57-3e9d13f95c80`

- **Diagnostic-arm OCIDs (positions 0..9):** 10 (subset of the main-arm OCIDs)

## Per-arm latency + token + cost

| Arm | Records | Receipts | p50 latency | p95 latency | Prompt-tok total | $ cost |
|---|---:|---:|---:|---:|---:|---:|
| `arm_a` | 30 | 30 | 2254ms | 3792ms | 55289 | $0.2764 |
| `arm_b` | 30 | 30 | 2340ms | 4012ms | 43297 | $0.2165 |
| `arm_c` | 30 | 30 | 2364ms | 4287ms | 48791 | $0.2440 |
| `l4_without_nudge` | 30 | 30 | 2230ms | 4208ms | 77321 | $0.3866 |
| `diagnostic_primary` | 10 | 10 | 2564ms | 3046ms | 25995 | $0.1300 |
| `diagnostic_claude` | 10 | 10 | 3404ms | 4297ms | 39436 | $1.3310 |

Cost is informational only — current public list-price rates + completion-tokens estimated at 25% of prompt-tokens (an envelope; the experiment account's actual billing may differ via tier multipliers and caching discounts).

## Smoke → dry-run accuracy (±15% band)

Per the package spec §5: if observed dry-run mean prompt-tokens per record is within ±15% of the smoke baseline, the smoke→Phase-2 extrapolation is trustworthy. Outside ±15% → update the Phase-2 projection.

| Arm | Smoke mean (tok/rec) | Dry-run mean (tok/rec) | Ratio | Within ±15%? |
|---|---:|---:|---:|:---:|
| `arm_a` | 1821.0 | 1843.0 | 1.012 | yes |
| `arm_b` | 1439.0 | 1443.2 | 1.003 | yes |
| `arm_c` | 1624.0 | 1626.4 | 1.001 | yes |
| `l4_without_nudge` | 2575.0 | 2577.4 | 1.001 | yes |
| `diagnostic_primary` | 2593.0 | 2599.5 | 1.003 | yes |
| `diagnostic_claude` | 3940.0 | 3943.6 | 1.001 | yes |

## Dry-run → Phase 2 extrapolation

Linear extrapolation of observed dry-run mean prompt-tokens per record to the full Phase-2 receipt counts (283 per main arm, 100 per diagnostic arm). Stub-mode numbers are zero by design.

| Arm | Dry-run receipts | Dry-run prompt-tok | $ cost | Phase-2 receipts | Phase-2 prompt-tok | Phase-2 $ cost |
|---|---:|---:|---:|---:|---:|---:|
| `arm_a` | 30 | 55289 | $0.2764 | 283 | 521560 | $2.61 |
| `arm_b` | 30 | 43297 | $0.2165 | 283 | 408435 | $2.04 |
| `arm_c` | 30 | 48791 | $0.2440 | 283 | 460262 | $2.30 |
| `l4_without_nudge` | 30 | 77321 | $0.3866 | 283 | 729395 | $3.65 |
| `diagnostic_primary` | 10 | 25995 | $0.1300 | 100 | 259950 | $1.30 |
| `diagnostic_claude` | 10 | 39436 | $1.3310 | 100 | 394360 | $13.31 |
| **TOTAL** | | | | | | **$25.21** |

## Aggregate completeness

PASS — every main-subset OCID appears in every main arm (arm_a / arm_b / arm_c / l4_without_nudge); every diagnostic-subset OCID appears in both diagnostic arms (diagnostic_primary / diagnostic_claude). No silent drops.

## Errors

(none)

## Next step

    python3 scripts/verify_dry_run_e3.py dry-run-20260528T164807-Z/

(run from inside `procurement-context-disambiguation/runner/` with the run dir resolved relative to `results/runs/`.)
