# E2-007 — Smoke run + validation

You are a background agent. This package executes the first end-to-end live run of the multi-pass runner — small (3 records × 5 levels + 1 Permuted-Policy pilot = 16 receipts) — and validates everything from cryptographic integrity to cache savings.

## Inherit first

- `procurement-context-gradient/planning/phase_1_build_plan.md` §"Decision points" — especially decision points 3 (L0-vs-E1 reproducibility) and 5 (Permuted-Policy pilot outcome)
- `procurement-context-gradient/planning/experiment_design.md` §"Definition of done"
- The completed runner at `procurement-context-gradient/runner/`

**Hard dependencies**: E2-001..006 all merged.

## Goal

Run a small-scale live smoke that exercises every code path. Validate cryptographic integrity, level-batching cache behaviour, L0 reproducibility, and Permuted-Policy receipt distinctness.

## Scope

### 1. Smoke record selection

Three deterministic records from the 283-record corpus, picked to exercise distinct conditions:

- One record with a clean E1 verdict (MeshQu=ALLOW, agent=ALLOW or REVIEW) — exercises the "clean" branch
- One record with a single-rule MeshQu DENY — exercises a clean DENY case
- One record with the worked-example shape (multi-rule DENY: e.g. `ca19e737-…`, the £57M case) — exercises the load-bearing case the writeup uses

Smoke records committed at `runner/scripts/smoke_records.json` (deterministic for re-runs).

### 2. Run execution

Execute the runner against the 3-record smoke set:

```bash
cd procurement-context-gradient/runner
python -m meshqu_runner.run --records scripts/smoke_records.json --output-dir ../results/runs/smoke-<timestamp>/
```

Expected output: 16 bundles (3 × 5 main levels + 1 Permuted-Policy pilot on the worked-example record).

### 3. Validation steps

For each, write a short script under `runner/scripts/` or run inline and record results:

**3a. Cryptographic integrity.** All 16 bundles verify via the offline `meshqu-verifier` CLI:
```bash
for b in $RUN_DIR/**/*.bundle.json; do meshqu-verifier verify "$b" || echo "FAIL: $b"; done
```
All 16 must pass.

**3b. Level field present.** Each bundle's receipt has the right `governance_context_level` field:
```bash
for b in $RUN_DIR/**/*.bundle.json; do
  level=$(jq -r '.files."receipt.json"' "$b" | jq -r '.governance_context_level')
  echo "$b: $level"
done
```
Expected: L0/L1/L2/L3/L4 for main run; L4_PERMUTED for diagnostic.

**3c. Level-batching observed.** Receipt timestamps within a level cluster together; across levels they progress. Specifically: max(L0 timestamps) < min(L1 timestamps), and so on. The runner ran L0 first, then L1, etc.

**3d. Cache savings observed (L4).** The 3rd L4 call's `cached_tokens` (from `cache_telemetry.jsonl` per E2-005) is > 0. If the second is also > 0, even better.

**3e. L0 reproducibility check.** Run `scripts/compare_l0_to_e1.py` against the 3 smoke records. Document the verdict-comparison table in the PR body.

**3f. Permuted-Policy pilot inspection.** For the 1 Permuted-Policy receipt:
- Verifies offline (3a check covers this)
- Has `governance_context_level == "L4_PERMUTED"`
- The agent's reasoning text: does it flag the contradiction? Quote the verbatim reasoning in the PR body. Sam will read this to gauge whether the diagnostic is producing useful signal.

**3g. Integrity-hash distinctness.** For the worked-example record (`ca19e737-…`), the L4 main-run receipt and the L4_PERMUTED diagnostic receipt MUST have different integrity hashes (different policy bytes → different hash). Print both hashes in the PR body.

### 4. Cost projection

From the smoke's actual token usage, project the full-run cost (1,415 main calls + 14 diagnostic). Print in PR body. Compare against the pre-run budget envelope.

### 5. PR body must answer

- All 16 bundles verify? Y/N.
- L0 verdicts vs E1 verdicts on the 3 smoke records — table.
- Permuted-Policy pilot reasoning verbatim — quoted.
- Cache hit fraction at L4 — number.
- Projected full-run cost — dollar amount.

## Decision rules

- **The smoke fails if ANY bundle doesn't verify.** All 16 must pass cryptographic checks. No exceptions.
- **L0-vs-E1 divergence on ≥2 of 3 records is investigation-worthy.** Surface to Sam in the PR body before continuing to E2-008.
- **Cache hit at 0% on the 3rd L4 call is a real problem.** The level-batching design assumes cache hits. If they're not happening, the runner architecture needs review before scaling to 283 records.
- **Permuted-Policy agent reasoning that doesn't engage with the inverted logic** is not a bug in the runner — it's the diagnostic outcome being measured. Just quote it honestly.

## Out of scope

- Dry-run (E2-008) — that's 30 records and the full 14-record Permuted-Policy diagnostic.
- Full run (Phase 2) — that's 283 records.
- Cross-level analysis (Phase 3).

## Definition of done

- Branch `feat/e2-007-smoke-run`.
- Run directory committed (smoke artefacts) — or committed as a tagged smoke result, your call. Sam should be able to inspect them.
- PR body answers the 5 questions in §5.
- All validation steps recorded with pass/fail + numbers.

## Stop conditions

- Any cryptographic verification failure → STOP. Do not advance to E2-008. Surface to Sam.
- Cache hits stay at 0 → STOP. The runner architecture needs review.
- L0 verdicts differ from E1 on all 3 records → STOP. Substrate-loading or prompt-construction bug.
- The Permuted-Policy pilot receipt cannot be cryptographically distinguished from a main-run L4 receipt → STOP. The integrity-hash binding for `policy_permutation_seed` isn't working.
