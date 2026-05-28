# E2-008 dry-run validation — dry-run-20260521-181714-Z

Run directory: `procurement-context-gradient/results/runs/dry-run-20260521-181714-Z`
Bundles loaded: 151
L0 bundles (record count proxy): 30
Smoke run reference: `procurement-context-gradient/results/runs/smoke-20260521-170331-Z`

### §3b — Level field distribution
  L0             30 bundle(s)
  L1             30 bundle(s)
  L2             30 bundle(s)
  L3             30 bundle(s)
  L4             30 bundle(s)
  L4_PERMUTED    1 bundle(s)
  Status: PASS

### §3c — Level-batching (timestamps progress level-by-level)
  L0: min=2026-05-21T18:17:19+00:00  max=2026-05-21T18:18:55+00:00  (30 bundles)
  L1: min=2026-05-21T18:18:58+00:00  max=2026-05-21T18:20:31+00:00  (30 bundles)
  L2: min=2026-05-21T18:20:34+00:00  max=2026-05-21T18:22:10+00:00  (30 bundles)
  L3: min=2026-05-21T18:22:12+00:00  max=2026-05-21T18:24:08+00:00  (30 bundles)
  L4: min=2026-05-21T18:24:10+00:00  max=2026-05-21T18:25:46+00:00  (30 bundles)
  Status: PASS

### §3d — Cache savings at L4 (aggregate fraction)
  L4 calls=30  observed=30  hits=27  hit_fraction=0.900  mean_cached=1766  mean_prompt=3694
  Status: PASS

### §3e — L0 vs E1 verdict reproducibility (at dry-run scale)
  L0 records evaluated: 30
  MeshQu verdict matches: 29/30  (mismatches: 1)
  Agent verdict matches: 27/30  (mismatches: 3 — drift expected per P4 band)
  MeshQu mismatches (OCIDs):
    - ocds-b5fd17-6bb11187-ac69-45a7-8246-73ce1b53100d
  Status: PASS

### §3f — Permuted-Policy reasoning (verbatim, per intersection OCID)

  OCID:        `ocds-b5fd17-119d1c05-7fa8-478f-ac6f-db416fb5b5c9`
  Decision id: `dc92b58b-a754-4873-a872-0b9847886e90`
  Agent verdict: DENY
  MeshQu decision: DENY

  Reasoning (verbatim):
  ```
  The record shows an above-threshold PA23 award with publication_delay_days of 85, exceeding the 30-day rule, and no open-tender flag or direct-award justification is present. COI cannot be evaluated on this substrate, but the identified critical failures are sufficient to reject.
  ```

  Status: PASS (qualitative; Sam to read the reasoning above)

### §3g — Worked-example L4 vs L4_PERMUTED integrity-hash distinctness
  Worked example present in main L4 but NOT in the diagnostic subset (hash mod 20 != 0).
  Status: SKIP (worked-example not in 14-record subset)

### §4a — Reproducibility across runs (smoke vs dry-run, shared OCIDs)
  Shared OCIDs at L0: 3

| OCID | smoke agent | dry agent | match | smoke MeshQu | dry MeshQu | match |
|------|-------------|-----------|-------|--------------|------------|-------|
| `ocds-b5fd17-001cf81b-5232-4d78-a0c7-4b8ab05f7658` | REVIEW | REVIEW | YES | ALLOW | ALLOW | YES |
| `ocds-b5fd17-0786919f-4875-42c3-99ac-7db01e366670` | REVIEW | REVIEW | YES | DENY | DENY | YES |
| `ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f` | REVIEW | REVIEW | YES | DENY | DENY | YES |

  Agent verdict matches: 3/3  (temp=0 reproducibility check; mismatches surface model noise)
  MeshQu verdict matches: 3/3  (MeshQu re-eval should be deterministic on same fields)
  Status: PASS (MeshQu matches; agent drift 0/3 surfaced)

### §4b — Per-level latency distribution

| Level | n | mean_ms | p50_ms | p95_ms | min_ms | max_ms |
|------:|--:|--------:|-------:|-------:|-------:|-------:|
| L0           | 30 |    2218 |   2100 |   3384 |   1364 |   4789 |
| L1           | 30 |    2156 |   2048 |   2802 |   1647 |   4934 |
| L2           | 30 |    2195 |   2089 |   3080 |   1684 |   3782 |
| L3           | 30 |    2863 |   2021 |   8179 |   1604 |  16355 |
| L4           | 30 |    2192 |   2098 |   2602 |   1653 |   6112 |
| L4_PERMUTED  |  1 |    2014 |   2014 |   2014 |   2014 |   2014 |

  No automatic threshold — Sam to eyeball the distribution.
  Expected: L4 ≥ L3 ≥ L2 ≥ L1 ≥ L0 (more tokens → more latency).
  Anomalous spikes (single calls > 3x p50) flagged in JSON sidecar.
  Status: PASS (descriptive — no hard threshold)

### §4c — Permuted-Policy receipts cryptographically distinct (every intersection OCID)

| OCID | L4 main hash | L4_PERMUTED hash | distinct? |
|------|--------------|-------------------|-----------|
| `ocds-b5fd17-119d1c05-7fa8-478f-ac6f-db416fb5b5c9` | `9adbac9dfa482b9c…` | `57790d2c039f1f2f…` | YES |

  Status: PASS

### Rate-limiting incidents (§3g at dry-run scale)
  Agent retry_count distribution: {0: 151}
  MeshQu retry_count distribution: {0: 151}
  No retries observed — no rate-limit incidents at dry-run scale.

### §3h — Cost realisation + refined full-run projection

  Output-token estimate: ~100 tokens/call (151 bundles, chars/4)

| Level | dry-run calls | mean prompt | mean cached | cache hit | per-call USD | dry-run USD | full-run calls | projected USD |
|------:|--------------:|------------:|------------:|----------:|-------------:|------------:|---------------:|--------------:|
| L0           |            30 |         999 |           0 |     0.000 |     0.00450 |      0.1350 |            283 |       1.2739 |
| L1           |            30 |        1131 |           0 |     0.000 |     0.00490 |      0.1469 |            283 |       1.3860 |
| L2           |            30 |        1248 |           0 |     0.000 |     0.00525 |      0.1575 |            283 |       1.4853 |
| L3           |            30 |        2096 |          34 |     0.033 |     0.00772 |      0.2315 |            283 |       2.1836 |
| L4           |            30 |        3694 |        1766 |     0.900 |     0.00861 |      0.2584 |            283 |       2.4373 |
| L4_PERMUTED  |             0 |           0 |           0 |     0.000 |     0.00150 |      0.0000 |             14 |       0.0211 |

  **Dry-run realised total: USD $0.9293**
  **Refined full-run projection: USD $8.79** (1,415 main + 14 diagnostic; assumes dry-run cache pattern holds at corpus scale)

  Envelope reference (E2-007 smoke projection): USD $9.68
  Refined / reference multiple: 0.91x
  Status: within envelope (<5.0x reference).

---
Overall: **PASS**
Sidecar JSON: procurement-context-gradient/runner/scripts/dry-run-validation-20260521-181714-Z.json
