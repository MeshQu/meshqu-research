# E3-011 — Dry-run + validation

You are a background agent. Mid-scale live run — 30 corpus records × 4 main arms + 10 × 2 diagnostic arms = 140 receipts. Validates the cost projection, surfaces any scale-dependent issues, and proves the runner is ready for the full Phase 2.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/diagnostic_subset.json`
- `procurement-context-gradient/runner/scripts/phase_2_live.py` and `dry_run_live.py` — E2's templates
- The smoke summary from E3-010 (PR body) — your extrapolation references this

**Hard dependencies**: E3-010 merged and clean (all 14 smoke receipts verified).

## Goal

Run the full arm matrix on 30 corpus records (positions 0–29 in the locked subset) for the main arms, and on 10 records (positions 0–9) for each diagnostic arm. Validate all 140 receipts offline. Compare actual cost to the smoke extrapolation; revise the Phase 2 projection if needed.

## Scope

### 1. Dry-run matrix

For 30 OCIDs (positions 0–29 in `diagnostic_subset.json`):
- Arm A → 30 receipts
- Arm B → 30 receipts
- Arm C → 30 receipts
- L4-without-nudge → 30 receipts

For 10 OCIDs (positions 0–9):
- Diagnostic primary → 10 receipts
- Diagnostic Claude → 10 receipts

Total: **140 receipts**.

### 2. Driver

`scripts/dry_run_e3.py`:

```bash
python scripts/dry_run_e3.py
# emits to: results/runs/dry-run-<timestamp>-Z/
```

The script:
- Honours rate-limiting / pacing for both providers. Anthropic and OpenAI have different limits; respect both.
- Writes per-record progress (a tick line per receipt) so the operator can monitor a long run.
- On any unrecoverable error: persist a partial run-manifest, surface the error, exit non-zero. The recovery script from E2 (`recover_orphans.py`) can stitch missing receipts after fix-up.
- Writes a `dry-run-summary.md` with: per-arm receipt count, per-arm latency p50/p95, per-arm total tokens, per-arm total $ cost (using current model rates), the extrapolation to the full ~1,332-receipt run.

### 3. Offline verification

```bash
python scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/
```

All 140 must verify. Same checks as the smoke verifier, scaled up. Add an aggregate-level check: every OCID appears in every applicable arm (no silent drops).

### 4. Receipt-orphan check

E2 surfaced an orphan-recovery need (per the project memory: "Receipt-orphan recovery script still needed before 300-record run"). For the E3 dry-run:
- If `recover_orphans.py` exists in the fork, run it post-dry-run as a sanity check.
- If it doesn't, surface to Sam — this needs to land before Phase 2 fires the full run.

### 5. Cost projection vs smoke

Compare per-arm cost from dry-run to the smoke extrapolation. If the dry-run cost per receipt is within ±15% of the smoke projection, the extrapolation is trustworthy and the full-run projection can be trusted at the same ratio. If outside ±15%, flag the deviation and update the Phase 2 cost estimate.

### 6. PR body must answer

- The 30 OCIDs + 10 diagnostic OCIDs used.
- The 140 receipts' run-manifest path.
- The verification result (all 140 pass / any failures).
- Per-arm latency p50/p95, total tokens, total $ cost.
- Per-arm cost / receipt and total full-run projection.
- Smoke → dry-run extrapolation accuracy (the ±15% check).
- Any 429s or rate-limit warnings observed.
- The orphan-check result.

## Decision rules

- **Same locked subset, in order.** Positions 0–29 for main arms; 0–9 for diagnostic. Don't sample randomly; the order is the locked file's order.
- **Don't tune anything mid-run.** If the dry-run surfaces a fixable issue, it goes in a follow-up PR before Phase 2 — the dry-run itself is read-only with respect to the runner code.
- **Cost is informational here.** The go/no-go for Phase 2 is the readiness checklist (E3-012); cost is one input.

## Out of scope

- The full run (Phase 2).
- Coding the diagnostic reasoning text (Phase 2 / 2.5).
- Re-running the smoke (E3-010 already did that).

## Definition of done

- Branch `feat/e3-011-dry-run`.
- `scripts/dry_run_e3.py` + `scripts/verify_dry_run_e3.py` exist and run clean.
- 140 receipts emitted and all verify offline.
- PR body has the dry-run summary + cost projection + smoke→dry-run accuracy + orphan-check result.

## Stop conditions

- Any receipt fails verification → STOP. Do not proceed to readiness checklist.
- Rate-limit (429) errors that the pacing logic doesn't recover from → STOP. Surface; pacing logic may need a tune before Phase 2.
- Cost projection lands wildly outside the budget envelope (>2x the smoke extrapolation, or >2x what Sam expected) → STOP, surface. Do not proceed to readiness sign-off; Sam needs to decide whether to scale down the full run.
- Orphan-recovery script is absent → run the dry-run anyway but flag clearly. The full run cannot proceed without it.
