# E2-007 smoke validation — smoke-20260521-170331-Z

Run directory: `procurement-context-gradient/results/runs/smoke-20260521-170331-Z`
Bundles loaded: 16

### §3b — Level field distribution
  L0             3 bundle(s)
  L1             3 bundle(s)
  L2             3 bundle(s)
  L3             3 bundle(s)
  L4             3 bundle(s)
  L4_PERMUTED    1 bundle(s)
  Status: PASS

### §3c — Level-batching (timestamps progress level-by-level)
  L0: min=2026-05-21T17:03:35+00:00  max=2026-05-21T17:03:41+00:00
  L1: min=2026-05-21T17:03:44+00:00  max=2026-05-21T17:03:51+00:00
  L2: min=2026-05-21T17:03:54+00:00  max=2026-05-21T17:04:00+00:00
  L3: min=2026-05-21T17:04:03+00:00  max=2026-05-21T17:04:10+00:00
  L4: min=2026-05-21T17:04:14+00:00  max=2026-05-21T17:04:21+00:00
  Status: PASS

### §3d — Cache savings observed at L4
  3 L4 telemetry rows
    call #1  ocid=ocds-b5fd17-001cf81b-5232-4d78-a0c7-4b8ab05f7658  cached_tokens=0  prompt_tokens=3718
    call #2  ocid=ocds-b5fd17-0786919f-4875-42c3-99ac-7db01e366670  cached_tokens=0  prompt_tokens=3711
    call #3  ocid=ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f  cached_tokens=1792  prompt_tokens=3772
  L4 cache: n=3 observed=3 hits=1 fraction=0.333 mean_cached=597.3 mean_prompt=3733.7
  1/2 post-first L4 calls observed cached_tokens > 0
  Status: PASS

### §3e — L0 vs E1 verdict reproducibility

| OCID | E1 MeshQu | L0 MeshQu | match | E1 agent | L0 agent | match |
|------|-----------|-----------|-------|----------|----------|-------|
| `ocds-b5fd17-0786919f-4875-42c3-99ac-7db01e366670` | DENY | DENY | YES | REVIEW | REVIEW | YES |
| `ocds-b5fd17-001cf81b-5232-4d78-a0c7-4b8ab05f7658` | ALLOW | ALLOW | YES | REVIEW | REVIEW | YES |
| `ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f` | DENY | DENY | YES | REVIEW | REVIEW | YES |

  MeshQu mismatches: 0/3   Agent mismatches: 0/3 (drift expected per P4 band)
  Status: PASS

### §3f — Permuted-Policy pilot agent reasoning (verbatim)
  OCID:        `ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f`
  Decision id: `481566c3-03c8-49ff-85c0-f28163449751`
  Agent verdict: DENY
  MeshQu decision: DENY

  Reasoning (verbatim):
  ```
  This above-threshold PA23 award (£57,000,000) was published 33 days after the 2026-03-27 award date proxy, breaching the 30-day timing rule, and the record also lacks evidence of open competition or a direct-award justification. Conflict-of-interest and authority approval cannot be confirmed from this substrate, but the recorded failures are already material.
  ```
  Status: PASS (qualitative; Sam to read the reasoning above)

### §3g — Integrity-hash distinctness (worked example)
  L4 main         integrity_hash: `af3916a660cc0347caa3cd423501440be9dbf00f3e0cb646f3590798e2b3ee66`
  L4_PERMUTED     integrity_hash: `968e6921ff1104bdc79a45ade94c1b6491b84418f39a2042e836cb35e9610683`
  Distinct? YES
  Status: PASS

### §4 — Cost projection from observed token usage

  Output-token estimate: ~102 tokens / call (chars/4 over 16 bundles)

| Level | Smoke calls | Mean prompt | Mean cached | Full-run calls |  Projected USD |
|------:|------------:|------------:|------------:|---------------:|---------------:|
| L0           |           3 |        1006 |           0 |            283 |        1.2889 |
| L1           |           3 |        1138 |           0 |            283 |        1.4010 |
| L2           |           3 |        1255 |           0 |            283 |        1.5003 |
| L3           |           3 |        2136 |           0 |            283 |        2.2483 |
| L4           |           3 |        3734 |         597 |            283 |        3.2246 |
| L4_PERMUTED  |           0 |           0 |           0 |             14 |        0.0215 |

  **Total projected full-run cost: USD $9.68** (1,415 main + 14 diagnostic calls; assumes cache hit rates observed at L4 hold at corpus scale)

---
Overall: **PASS**
