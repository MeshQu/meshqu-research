# E2-008 — Dry-run + validation

You are a background agent. Scaled-up smoke. 30 records × 5 levels + the full 14-record Permuted-Policy diagnostic. Same validation as E2-007, applied at 10× scale.

## Inherit first

- `procurement-context-gradient/planning/phase_1_build_plan.md`
- The E2-007 smoke run result — read the PR comments + the smoke run directory

**Hard dependency**: E2-007 smoke clean.

## Goal

Validate the runner at scale just below the full-corpus level. Surface any cost surprise, rate-limiting issue, or scale-only-visible bug.

## Scope

### 1. Dry-run record selection

30 deterministic records from the 283 corpus. Strategy: stratified by `(value_band × method_flag × regime)` to ensure coverage of the substrate's distribution. Specifically:

- 5 records from each value band (4 bands)
- Within each band, prefer mix of method-flag-present vs absent
- Total: 20 records from stratification + 10 records added by simple OCID-asc walk to fill to 30 if stratification under-fills

Committed at `runner/scripts/dry_run_records.json`. Must include the 3 smoke records (so we can cross-check 3 records appear in both runs with identical L0 receipts → tighter reproducibility check).

### 2. Run execution

```bash
python -m meshqu_runner.run \
  --records scripts/dry_run_records.json \
  --output-dir ../results/runs/dry-run-<timestamp>/ \
  --include-permuted-policy-diagnostic
```

Expected: 30 × 5 = 150 main receipts + 14 Permuted-Policy diagnostic receipts (the full deterministic 14-OCID subset of the corpus; some may not be in the 30 dry-run records but the Permuted-Policy subset is the universal `hash(ocid) mod 20 == 0` set — clarify the design here: does the Permuted-Policy diagnostic run against all 14 of those records, or only the ones that intersect the dry-run set?).

**Clarification**: For the dry-run, the Permuted-Policy diagnostic runs against the intersection of (the 14-record full subset) ∩ (the 30 dry-run records). Expected intersection size: ~1–2 records. The FULL 14-record diagnostic runs as part of Phase 2's full run. Document this choice in the PR body and in `experiment_design.md` if the design didn't already specify.

Approximate total receipts: 150 + 1–2 = 151–152.

### 3. Validation steps

All of E2-007's checks (3a–3g) applied at scale:

**3a.** All ~152 bundles verify offline. Script automated; failures listed.

**3b.** Level field correctly distributed: ~30 each of L0/L1/L2/L3/L4 + 1–2 L4_PERMUTED.

**3c.** Level-batching timestamps: max(L0) < min(L1) < ... etc.

**3d.** Cache savings at scale: aggregate cache hit fraction at L4 should be ≥30% (target: 50–80% per the expectation in `experiment_design.md`). Compute and report.

**3e.** L0 reproducibility on the 30 dry-run records: count of L0-vs-E1 verdict matches. Target: 30 of 30; tolerance: 29 of 30 (single-record noise OK).

**3f.** Permuted-Policy reasoning patterns: for the 1–2 diagnostic receipts, quote the agent's reasoning verbatim in the PR body. Compare to the smoke pilot's reasoning — does the pattern hold (flagging vs accepting the inversion)?

**3g.** Rate-limiting: did the runner hit any 429s? If yes, did the pacing logic recover cleanly? Report.

**3h.** New at scale — cost realisation: actual dollar cost of the dry-run + extrapolation to full run (283 / 30 = 9.4× scaling, plus the full Permuted-Policy 14-record diagnostic).

### 4. New checks specific to dry-run scale

**4a. Reproducibility across runs.** The 3 records that appear in both smoke and dry-run sets should produce L0 receipts with identical agent verdicts (modulo OpenAI noise). If verdicts differ, the deterministic-temp=0 assumption is shakier than thought — flag it.

**4b. Per-level latency distribution.** Compute mean + p95 wall-clock per (record, level) pair. The distribution should be similar across levels (or slightly higher at L4 due to token volume). Anomalous spikes might indicate cache misses, network hiccups, or rate-limiting.

**4c. The Permuted-Policy receipts cryptographic distinctness at scale.** Spot-check 1 receipt: same OCID has DIFFERENT integrity hashes between its L4 main-run receipt and its L4_PERMUTED diagnostic receipt. Print both hashes in PR body.

### 5. PR body must answer

- ~152 bundles all verify? Y/N. If N, which failed and why.
- L0-vs-E1 reproducibility: match count / 30. Mismatches listed by OCID.
- Cache hit fraction at L4: number.
- Realised cost of dry-run + projected cost of full run.
- Any rate-limiting? Did pacing recover?
- The Permuted-Policy reasoning pattern: holds from smoke or diverges?

## Decision rules

- **Cryptographic integrity is non-negotiable.** All ~152 must verify.
- **L0 reproducibility below 28/30 is a flag.** Suggest investigation, do not paper over.
- **Cache hit below 30% at L4 means the level-batching savings are below expectation.** Acceptable if Sam okays it; ideally surface to Sam before Phase 2 launch.
- **Any 429s that the pacing logic couldn't recover from → STOP.** The full run will hit them harder.

## Out of scope

- Full 1,415-receipt run (Phase 2).
- The full 14-record Permuted-Policy diagnostic (only the intersection with the 30 dry-run records runs here; the full 14 runs in Phase 2).
- Cross-level analysis (Phase 3).

## Definition of done

- Branch `feat/e2-008-dry-run`.
- Run directory committed; validation results in PR body.
- Cost projection updated.
- Sam reads + signs off before E2-009 starts.

## Stop conditions

- Any verification failure → STOP.
- Cache hit below 10% at L4 → STOP. Architecture issue.
- Rate-limiting recovery failure → STOP.
- L0 verdicts diverge from E1 on >5 of 30 records → STOP. Substrate / prompt / model issue.
- Cost extrapolation projects >5× the expected envelope → STOP. Tell Sam before spending the money on Phase 2.
