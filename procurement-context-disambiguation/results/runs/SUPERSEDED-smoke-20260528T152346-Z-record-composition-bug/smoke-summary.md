# E3 smoke run — `smoke-20260528T152346-Z`

- **Started:** 2026-05-28T15:23:46+00:00
- **Finished:** 2026-05-28T15:24:37+00:00
- **Mode:** live
- **Pre-registration tag:** `v0.3-predictions-locked`
- **Smoke OCIDs (positions 0..2 from `planning/diagnostic_subset.json`):**
  0. `ocds-b5fd17-00d99d64-a859-460c-9630-7511284e3e29`
  1. `ocds-b5fd17-15a37e29-28a4-4e14-a057-f1bc8f8124d6`
  2. `ocds-b5fd17-9a2263a4-c2d5-4023-b405-882f8eacdd1e`

- **Receipts written:** 14 / 14 expected
- **Errors:** 0

- **Per-arm manifests:** `manifests/<arm_name>.manifest.json`  (one per arm; `manifest.json` at the run root reflects the last arm dispatched — provenance survives in the per-arm snapshots)

## Per-arm latency + token totals

| Arm | Records | Receipts | Latency mean | Latency min | Latency max | Prompt tokens total |
|---|---:|---:|---:|---:|---:|---:|
| `arm_a` | 3 | 3 | 2805ms | 2052ms | 3377ms | 3958 |
| `arm_b` | 3 | 3 | 2266ms | 1748ms | 2979ms | 2782 |
| `arm_c` | 3 | 3 | 2299ms | 1980ms | 2863ms | 3315 |
| `l4_without_nudge` | 3 | 3 | 2156ms | 1847ms | 2617ms | 6111 |
| `diagnostic_primary` | 1 | 1 | 2397ms | 2397ms | 2397ms | 2060 |
| `diagnostic_claude` | 1 | 1 | 2723ms | 2723ms | 2723ms | 3087 |

## Cost extrapolation (smoke → dry-run → full-run)

Linear extrapolation of observed mean prompt tokens per record. Operationally an envelope — record-by-record variation isn't modeled. Stub-mode numbers are zero by design (the stub agent doesn't report token usage).

| Arm | Smoke receipts | Smoke prompt-tok total | Mean / record | Dry-run receipts | Dry-run prompt-tok proj. | Full-run receipts | Full-run prompt-tok proj. |
|---|---:|---:|---:|---:|---:|---:|---:|
| `arm_a` | 3 | 3958 | 1319.3 | 30 | 39580 | 283 | 373371 |
| `arm_b` | 3 | 2782 | 927.3 | 30 | 27820 | 283 | 262435 |
| `arm_c` | 3 | 3315 | 1105.0 | 30 | 33150 | 283 | 312715 |
| `l4_without_nudge` | 3 | 6111 | 2037.0 | 30 | 61110 | 283 | 576471 |
| `diagnostic_primary` | 1 | 2060 | 2060.0 | 10 | 20600 | 100 | 206000 |
| `diagnostic_claude` | 1 | 3087 | 3087.0 | 10 | 30870 | 100 | 308700 |

## Errors

(none)

## Next step

    python3 scripts/verify_smoke_e3.py smoke-20260528T152346-Z/

(run from inside `procurement-context-disambiguation/runner/` with the run dir resolved relative to `results/runs/`.)
