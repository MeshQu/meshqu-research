# E2-009 — Pre-full-run readiness checklist

You are a background agent. Final gate before Phase 2. Verify every readiness item; do not invent or fix anything new — your job is to confirm prior packages delivered.

## Inherit first

- `procurement-context-gradient/planning/phase_1_build_plan.md` §"The pre-full-run readiness checklist"
- Smoke run results (E2-007 PR + smoke directory)
- Dry-run results (E2-008 PR + dry-run directory)
- All E2-001..006 PRs (read the PR bodies for documented decisions)

**Hard dependency**: E2-008 dry-run clean and Sam signed off.

## Goal

Run through the readiness checklist, mark each item ✓ or ✗ with evidence. Produce a single-page report that Sam reads as the green-light decision for Phase 2.

## Scope

### The checklist (from `phase_1_build_plan.md`, verbatim)

For each item: ✓ or ✗ + evidence + (if ✗) what's needed to remediate.

- [ ] **All 1,415 expected (record × level) pairs have a runner code path that exercises them.** Evidence: code review of `multi_pass.py`'s loop bounds + the dry-run produced 150 receipts in the expected per-level distribution.
- [ ] **L0-vs-E1 reproducibility verified on ≥10 records.** Evidence: counts from smoke (3) + dry-run (30) = 33 records compared; report verdict-match-count.
- [ ] **Level-batching cache savings observed.** Evidence: L4 aggregate cache-hit fraction from dry-run.
- [ ] **All receipts in smoke + dry-run verify offline at `verify.meshqu.com` or via `meshqu-verifier`.** Evidence: total verification count + any failures.
- [ ] **`governance_context_level` field present in every receipt's integrity payload.** Evidence: spot-check 5 receipts manually (one per level) + the runner's hash-bind test passing.
- [ ] **Permuted-Policy diagnostic produces cryptographically distinguishable receipts with `policy_permutation_seed` hash-bound.** Evidence: the worked-example record's L4 vs L4_PERMUTED integrity-hash comparison + receipt schema spot-check.
- [ ] **No service-role surfaces invoked from the runner.** Evidence: grep `meshqu_runner/` for service-role references; the runner must use API-key auth only.
- [ ] **Run manifest captures provenance.** Evidence: example `run-manifest.json` from dry-run contains: `agent_model_id`, `agent_temperature`, `prompt_template_sha256` per level, `policy_snapshot_sha256`, `substrate_adapter_version`, `runner_git_commit`. List each.
- [ ] **Monitoring dashboards configured.** Evidence: the Grafana captures Appendix B will use — is the dashboard already configured? Or is this a manual step Sam needs to do before pressing go?
- [ ] **Cost projection within budget envelope.** Evidence: dollar estimate from E2-008's dry-run extrapolation. Sam confirms budget OK in the readiness PR comment.
- [ ] **Rate-limiting pacing verified.** Evidence: dry-run hit how many 429s? Did all recover? At 9.4× scale will the pacing still hold?

### Additional gates

- [ ] **The PR for E2-001..006 are all merged to main.** Evidence: `git log --oneline main` shows the merge commits.
- [ ] **The Phase 1 build-plan branch (this branch) is also merged or in active review.** Evidence: PR status.
- [ ] **Stage A content files are populated (not stub).** Evidence: `runner/prompts/L1..L4` files have non-empty content matching `stage_a_content_authoring.md` spec.
- [ ] **Decision log up to date.** Evidence: `decision_log.md` carries entries for any post-lock methodology adjustments made during Phase 1.

### What to produce

Single document at `procurement-context-gradient/planning/phase_1_readiness_report.md`:

```markdown
# Phase 1 readiness report — <date>

## Summary

<one paragraph: are we go for Phase 2 or not?>

## Checklist results

<the checklist verbatim, each marked ✓/✗ with evidence>

## Outstanding items (if any)

<what needs to be done before Phase 2 launches; null if none>

## Decisions for Sam

<any judgment calls — e.g. "cache hit fraction was 35%, below the 50–80% expectation. Phase 2 cost projection assumes this; if you want to investigate further before launching, here's where to start.">

## Sign-off

Sam confirms Phase 2 ready: [ ]
Date: ____________
```

### PR body must answer

- Did all checklist items pass? Y/N count.
- If N: what's the single most-important blocker?
- Sam decision: green-light for Phase 2? (Sam responds in PR comment.)

## Decision rules

- **Don't fix anything in this package.** If a checklist item fails, surface it; the remediation belongs to a separate package or to Sam.
- **The readiness report is a record, not a plan.** No new work is scoped here.
- **Sam's sign-off is the green light.** Even if every checklist item passes, Phase 2 doesn't launch until Sam confirms.

## Out of scope

- Phase 2 execution.
- Cross-level analysis.
- Writeup work.

## Definition of done

- Branch `chore/e2-009-readiness-report`.
- `phase_1_readiness_report.md` committed with full checklist + evidence.
- PR opened.
- Sam's sign-off comment requested in PR body.

## Stop conditions

- Any cryptographic integrity issue in receipts → STOP. This shouldn't happen if E2-007 + E2-008 passed; if it shows up now, something regressed between merges.
- The readiness report finds an item that requires actual code changes → STOP and surface; do not fix unilaterally.
