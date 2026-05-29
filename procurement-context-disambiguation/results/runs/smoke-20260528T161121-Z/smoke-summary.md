# E3 smoke run — `smoke-20260528T161121-Z`

- **Started:** 2026-05-28T16:11:21+00:00
- **Finished:** 2026-05-28T16:12:13+00:00
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
| `arm_a` | 3 | 3 | 2627ms | 2285ms | 3032ms | 5463 |
| `arm_b` | 3 | 3 | 2658ms | 2156ms | 3453ms | 4316 |
| `arm_c` | 3 | 3 | 2689ms | 2036ms | 3838ms | 4873 |
| `l4_without_nudge` | 3 | 3 | 2213ms | 2088ms | 2299ms | 7726 |
| `diagnostic_primary` | 1 | 1 | 2343ms | 2343ms | 2343ms | 2593 |
| `diagnostic_claude` | 1 | 1 | 3354ms | 3354ms | 3354ms | 3940 |

## Cost extrapolation (smoke → dry-run → full-run)

Linear extrapolation of observed mean prompt tokens per record. Operationally an envelope — record-by-record variation isn't modeled. Stub-mode numbers are zero by design (the stub agent doesn't report token usage).

| Arm | Smoke receipts | Smoke prompt-tok total | Mean / record | Dry-run receipts | Dry-run prompt-tok proj. | Full-run receipts | Full-run prompt-tok proj. |
|---|---:|---:|---:|---:|---:|---:|---:|
| `arm_a` | 3 | 5463 | 1821.0 | 30 | 54630 | 283 | 515343 |
| `arm_b` | 3 | 4316 | 1438.7 | 30 | 43160 | 283 | 407143 |
| `arm_c` | 3 | 4873 | 1624.3 | 30 | 48730 | 283 | 459686 |
| `l4_without_nudge` | 3 | 7726 | 2575.3 | 30 | 77260 | 283 | 728819 |
| `diagnostic_primary` | 1 | 2593 | 2593.0 | 10 | 25930 | 100 | 259300 |
| `diagnostic_claude` | 1 | 3940 | 3940.0 | 10 | 39400 | 100 | 394000 |

## Errors

(none)

## Next step

    python3 scripts/verify_smoke_e3.py smoke-20260528T161121-Z/

(run from inside `procurement-context-disambiguation/runner/` with the run dir resolved relative to `results/runs/`.)
