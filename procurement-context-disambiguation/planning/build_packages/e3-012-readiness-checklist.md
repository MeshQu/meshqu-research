# E3-012 — Pre-full-run readiness checklist

You are a background agent. Final gate before Phase 2. Walks through every item on the readiness checklist (in `phase_1_build_plan.md`) and records the evidence + result for each. Produces a sign-off document. Cannot pass without every item green.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md` § "The pre-full-run readiness checklist (E3-012)"
- The merged outputs of every prior package (E3-001 through E3-011)
- The dry-run summary from E3-011 (PR body) — most of the evidence comes from there
- `procurement-context-gradient/planning/phase_1_readiness_report.md` — E2's template for the readiness report shape

**Hard dependencies**: E3-011 merged and clean (all 140 dry-run receipts verified).

## Goal

Produce `procurement-context-disambiguation/planning/phase_1_readiness_report.md` — for each checklist item, document the evidence (commit SHA + test name + line, or run-manifest path + receipt-id, etc.) and mark pass / fail / N/A. The readiness report is the artifact Sam reads to decide "fire the full run, yes/no."

## Scope

### 1. Walk every checklist item

For each of the 14 items in the master plan's readiness checklist, produce a section in the report:

```markdown
### [ITEM-N] All locked content (v0.3 tag) referenced unchanged from the runner (SHA check)

- Evidence: `tests/test_locked_content_sha.py::test_arm_b_template_sha` (commit <SHA>)
- Result: ✓ PASS
- Notes: SHAs of armB_precedent_no_verdict_format.md, armC_density_control.md,
  L4_without_nudge.md, diagnostic_rubric.md all match the v0.3 tag manifest.
```

If an item is N/A (e.g. "Monitoring dashboards configured" if the team decides to reuse E2's without reconfiguration), note N/A with rationale.

### 2. Items that need new tests

A few items don't already have tests because they span multiple packages. Author these in this PR:

- **Receipt integrity payload distinguishes by all the markers.** `tests/test_receipt_integrity_e3.py` — for each arm, run a stub-signer capture and assert the integrity payload has the expected `l3_arm` / `nudge_excised` / `model_id` / `diagnostic` / `policy_permutation_seed` shape.
- **All receipts in smoke + dry-run verify offline.** Aggregate the E3-010 and E3-011 verification logs into a single confirmation in the report.
- **Run manifest captures everything.** `tests/test_run_manifest_e3.py` — open the smoke + dry-run manifests, assert each contains: model id per arm, prompt SHA per arm, policy snapshot SHA, substrate adapter version, runner git commit, v0.3 tag SHA.

### 3. Sign-off section

At the bottom of the report:

```markdown
## Sign-off

| Item | Pass / Fail / N/A |
|---|---|
| 1. Locked content SHA check        | ✓ |
| 2. Arm A byte-identity             | ✓ |
| 3. Arm B contamination check       | ✓ |
| ... (14 items total)               |   |

**Result**: <READY FOR PHASE 2 / NOT READY — see [items]>

**Recommended next step**: <fire Phase 2 / fix [X] then re-run E3-012 / Sam decision needed on [Y]>
```

If any item is FAIL, the result is `NOT READY` and the recommended next step is "fix [X] then re-run E3-012."
If any item is "Sam decision needed" (e.g. token-parity gap from E3-004), the result is `READY pending Sam decision` and the report surfaces the question.

### 4. PR body must answer

- A summary table mirroring the sign-off (14 items, pass/fail/N/A).
- Direct links (path:line) to the evidence for each item.
- The total receipt count from smoke + dry-run (14 + 140 = 154) and verification rate (should be 100%).
- The cost projection for Phase 2 (lifted from E3-011 dry-run summary).
- Any item flagged "Sam decision needed."

## Decision rules

- **No green-washing.** If an item can't be evidenced, mark it FAIL and surface — don't mark green and hope.
- **Cost projection is informational at the readiness gate.** Phase 2 launch is a Sam decision; the readiness checklist documents whether the *runner* is ready, not whether the *budget* is approved.
- **The readiness report is a markdown artifact**, committed to `planning/`. It becomes part of the public provenance trail for E3.

## Out of scope

- Phase 2 launch itself (Sam decision).
- Coding the diagnostic reasoning text (Phase 2 / 2.5).
- Writeup drafting (Phase 3).

## Definition of done

- Branch `feat/e3-012-readiness-checklist`.
- `planning/phase_1_readiness_report.md` exists, walks every checklist item, has a sign-off table.
- New tests for the items that needed them pass.
- PR body summarises the sign-off table + cost projection.

## Stop conditions

- Any checklist item is FAIL → STOP. Mark NOT READY in the report; do not proceed to Phase 2 dispatch.
- Evidence path is missing for an item (the package that was supposed to produce it didn't) → STOP. Identify which package and surface to Sam; that package needs a follow-up PR before E3-012 can pass.
- Cost projection or rate-limit gating raises a Sam-decision question → mark "READY pending Sam decision" and surface the question. Don't pretend it's not a question.
