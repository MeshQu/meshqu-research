# E3-010 — Smoke run + validation

You are a background agent. The first live exercise of every arm end-to-end on a tiny corpus subset. Goal: surface any integration surprises before scaling to the dry-run.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/diagnostic_subset.json` — the locked subset (smoke uses the first 3 OCIDs)
- All previously-merged arm handlers (E3-002..E3-007 + E3-009 dependencies satisfied)
- `procurement-context-gradient/runner/scripts/smoke_live.py` — E2's smoke pattern; template for yours

**Hard dependencies**: E3-002 through E3-009 all merged.

## Goal

Run all arms live against 3 corpus records (the first 3 OCIDs from the locked subset) and confirm all 14 receipts verify offline at `verify.meshqu.com`.

## Scope

### 1. Smoke matrix

For 3 OCIDs (positions 0–2 in `diagnostic_subset.json`):
- Arm A → 3 receipts
- Arm B → 3 receipts
- Arm C → 3 receipts
- L4-without-nudge → 3 receipts
- Diagnostic primary → 1 receipt (just OCID 0 — the diagnostic doesn't need 3 for smoke; one record probes the diagnostic path end-to-end)
- Diagnostic Claude → 1 receipt (just OCID 0)

Total: **14 receipts**.

### 2. Driver

`scripts/smoke_e3.py`:

```bash
python scripts/smoke_e3.py
# emits to: results/runs/smoke-<timestamp>-Z/
```

The script:
- Loads the 3 smoke OCIDs.
- For each arm in {arm_a, arm_b, arm_c, l4_without_nudge}, runs the arm against each OCID, signs and persists the receipt.
- For each arm in {diagnostic_primary, diagnostic_claude}, runs against OCID 0 only.
- Records per-record latency + token usage.
- Writes a `smoke-summary.md` with: timestamp, run-manifest path, per-arm receipt counts, per-arm latency mean/min/max, per-arm token totals, any errors.

### 3. Offline verification

After the live run, verify every receipt:

```bash
python scripts/verify_smoke_e3.py results/runs/smoke-<timestamp>-Z/
```

- For each receipt in the run dir, run the offline verifier (the existing `@meshqu/verifier` or the equivalent Python verifier).
- All 14 must verify. If any fail, surface the failure with the offline-verifier output.
- The verification script also asserts the integrity payload contains the expected `l3_arm` / `nudge_excised` / `model_id` / `diagnostic` / `policy_permutation_seed` markers for each arm (cross-check against the matrix in the master plan).

### 4. Live cost projection (informational)

Capture the total tokens used by each arm during smoke. Extrapolate to the dry-run scale (30 records × 4 main arms + 10 × 2 diagnostic arms = 140 receipts) and to the full-run scale (283 × 4 + 100 × 2 = ~1,332 receipts). The dry-run package validates the extrapolation.

### 5. PR body must answer

- The 3 smoke OCIDs (from the locked subset).
- The 14 receipts' SHAs.
- The verification result (all 14 pass / any failure surfaced).
- Per-arm latency mean and token totals.
- Extrapolation table: smoke → dry-run → full-run, per arm.
- Any rendering / response-shape surprises (especially for the Claude arm — first time it sees a real corpus record).

## Decision rules

- **Live API calls.** This is the smoke; mocking would defeat the point. Use `DRY_RUN=false` or whatever flag the runner uses to gate live vs mock.
- **First 3 OCIDs.** Deterministic, traceable, audit-friendly. Don't pick "interesting" records.
- **Stop on first verifier failure.** Don't continue burning API spend if integrity is broken.

## Out of scope

- Coding the diagnostic reasoning text against the rubric — happens in Phase 2.
- The dry-run (E3-011).
- The full run (Phase 2).

## Definition of done

- Branch `feat/e3-010-smoke-run`.
- `scripts/smoke_e3.py` + `scripts/verify_smoke_e3.py` exist and run clean.
- 14 receipts emitted and all verify offline.
- PR body has the smoke summary + extrapolation.

## Stop conditions

- Any receipt fails offline verification → STOP. Do not proceed to dry-run. Surface the failure mode (signature, Rekor anchor, schema, integrity-payload field) so Sam can triage.
- Either model adapter raises an unexpected error (HTTP 4xx/5xx not handled by the typed exception path) → STOP, document, surface.
- Claude verdict shape deviates from spike + Arm A pattern → STOP. This is decision point 5 in the master plan; do not paper over.
- Cost extrapolation lands wildly outside the budget envelope → flag in PR body but do NOT stop the smoke (cost decision is for the dry-run / Phase 2 gate, not smoke).
