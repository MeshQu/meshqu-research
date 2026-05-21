# OBS-401 Smoke-test Report — 2026-05-16T1453

- **Run ID**: `(latest — detected from artefacts)`
- **Results directory**: `procurement-decisions/results`
- **Generated**: 2026-05-16T14:53:39.372530+00:00

## Summary

`3 PASS | 1 FAIL | 1 MANUAL`

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | screenshots fire at expected moments | ✅ PASS | 5 PNGs covering start, checkpoints, end |
| 2 | PNGs are valid | ✅ PASS | all 5 files are valid PNG |
| 3 | dashboard panels show series | ❌ FAIL | 80,255B — below empty-render baseline; panels likely empty |
| 4 | audit JSONL populated per schema | ✅ PASS | all required files populated, schema-clean |
| 5 | bundle round-trips through verify.meshqu.com | 🔍 MANUAL | 10 receipt(s) available for round-trip; verifier check is manual |

## Detail

### ✅ PASS  1. screenshots fire at expected moments

5 PNGs covering start, checkpoints, end

- total screenshots: 5
- events: {'anomaly-rekor_anchor_slow_record-003': 1, 'checkpoint-002': 1, 'checkpoint-004': 1, 'run-end': 1, 'run-start': 1}

### ✅ PASS  2. PNGs are valid

all 5 files are valid PNG

- checked: 5 files
- size range: 80255B – 81087B

### ❌ FAIL  3. dashboard panels show series

80,255B — below empty-render baseline; panels likely empty

- run-end screenshot: procurement-decisions/results/observability/screenshots/dry-run_2026-05-16T1452_experiment-tenant-observability_run-end.png
- size: 80,255 bytes
- heuristic: empty Grafana render ≈ 85 KB, populated render ≈ 150+ KB

### ✅ PASS  4. audit JSONL populated per schema

all required files populated, schema-clean

-   ✓ decision_traces.jsonl: 10 record(s) [decision-load-smoke=10]
-   ✓ anomalies.jsonl: 1 record(s)
-   ✓ checkpoints.jsonl: 2 record(s)

### 🔍 MANUAL  5. bundle round-trips through verify.meshqu.com

10 receipt(s) available for round-trip; verifier check is manual

- sample decision IDs: ['2e425ab8', '92349c0d', '188f9362']
- for each: curl /v1/decisions/<id>/bundle?format=tar > out.tar
- drop into verify.meshqu.com — confirm green checkmarks on signature + Rekor inclusion
- if every bundle verifies, mark this checkpoint PASS in the writeup; otherwise FAIL with the failing decision IDs noted

## Next action

❌ One or more checks failed. Address before running against staging.
