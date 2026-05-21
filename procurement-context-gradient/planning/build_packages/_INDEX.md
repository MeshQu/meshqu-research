# Build packages — Phase 1

Self-contained agent prompts for the Phase 1 build. Each package is dispatch-ready: an agent reads its own `mt-NNN.md` (or `e2-NNN.md` here) plus the shared `project_context.md`-equivalent (which lives at `phase_1_build_plan.md`) plus the specific design documents referenced in the prompt.

## Sequence at a glance

```
STAGE A (Sam-only, ~2h)         STAGE B (agent-dispatchable, ~25h)         STAGE C (sequential, ~6h)
─────────────────────         ─────────────────────────────────────         ────────────────────────
Locked content authoring    →  E2-001 Multi-pass runner foundation       →  E2-007 Smoke + validation
(L1, L2, L3, L4 prompts)    ┌→ E2-002 L0 baseline + substrate cache         │
                            │  E2-003 L1 + L2 payload generators            ▼
                            │  E2-004 L3 precedent selector            →  E2-008 Dry-run + validation
                            │  E2-005 L4 policy + cache preservation        │
                            │  E2-006 Permuted-Policy diagnostic            ▼
                            │                                          →  E2-009 Pre-full-run readiness
                            │                                                │
                            │                                                ▼
                            │                                          PHASE 2 BEGINS
                            │
                            └ (E2-002..006 parallel after E2-001 merges)
```

## Package index

| Package | Title | Effort | Dispatch order | Risk |
|---|---|---|---|---|
| [`e2-001-multi-pass-runner.md`](e2-001-multi-pass-runner.md) | Multi-pass runner orchestration (foundation) | ~8h | First (Stage B) | medium — foundation; touches integrity-hash schema |
| [`e2-002-l0-baseline-substrate-cache.md`](e2-002-l0-baseline-substrate-cache.md) | L0 baseline + substrate cache reader | ~4h | After E2-001; parallel with 003..005 | low — read-only substrate |
| [`e2-003-l1-l2-payload-generators.md`](e2-003-l1-l2-payload-generators.md) | L1 + L2 payload generators (consumes Stage A) | ~3h | After E2-001 + Stage A; parallel with 002,004,005 | low — string interpolation |
| [`e2-004-l3-precedent-selector.md`](e2-004-l3-precedent-selector.md) | L3 nearest-neighbour precedent selector (frozen archive only) | ~5h | After E2-001 + Stage A; parallel | medium — only algorithmically novel piece |
| [`e2-005-l4-policy-payload.md`](e2-005-l4-policy-payload.md) | L4 full policy payload + cache preservation | ~3h | After E2-001 + Stage A; parallel | medium — cache-friendly placement is load-bearing |
| [`e2-006-permuted-policy-diagnostic.md`](e2-006-permuted-policy-diagnostic.md) | Permuted-Policy diagnostic control | ~4h | After E2-005 | medium — receipt-schema extension |
| [`e2-007-smoke-run.md`](e2-007-smoke-run.md) | Smoke run + validation (16 receipts live) | ~2h | After E2-002..006 all merged | low — observational |
| [`e2-008-dry-run.md`](e2-008-dry-run.md) | Dry-run + validation (~152 receipts live) | ~2h | After E2-007 clean | low |
| [`e2-009-full-run-readiness.md`](e2-009-full-run-readiness.md) | Pre-full-run readiness checklist | ~2h | After E2-008 Sam sign-off | low |

**Total Stage B+C effort**: ~35h. ~3 days with parallelism, ~1 week linear.

## What every package inherits

Each prompt starts with "Inherit first" — a list of files the agent reads before touching code. The common minimum:

- `procurement-context-gradient/planning/phase_1_build_plan.md` — overall plan and dependency context
- The specific design document(s) the package addresses (e.g. E2-001 reads `experiment_design.md`; E2-004 reads `context_ladder_design.md`)
- Any prior-package outputs that this package depends on

## Convention reminders

- Branches: `feat/e2-NNN-short-slug` for feature packages; `chore/e2-009-readiness-report` for the final report.
- Commits: conventional + task ID — `feat(runner): E2-001 - multi-pass runner foundation`.
- PRs: open in this repo (meshqu-research), not in tradequ. Each PR body answers the specific questions named in the package prompt.
- Tests: required for every code-touching package. Pass before merge.
- Definition of done: every package lists explicit done criteria; the agent must satisfy each before opening the PR.
- Stop conditions: every package lists explicit stop conditions; the agent surfaces rather than guesses.

## What this directory does NOT contain

- Phase 2 execution prompts — out of scope until Phase 1 closes.
- Phase 3 analysis / writeup prompts — drafted post-Phase 2.
- Phase 4 methodology extraction prompts — drafted post-publish.

## Dispatch pattern

Three modes, same as `.harness/done/background-pack/`:

1. **Manual sequential** — Sam reads a package, dispatches one agent at a time. Predictable; slow.
2. **Background parallel** — Sam reads the index, fires Stage B's parallel-safe packages (E2-002..005) as 4 concurrent background agents after E2-001 lands. Same orchestrator pattern as background-pack proved out (12 PRs in a day).
3. **Hybrid** — Sam authors Stage A in parallel with E2-001 (background); after both land, fires the parallel Stage B batch. Recommended.

When Phase 1 starts, the dispatch decision is in `phase_1_build_plan.md` §"Recommended dispatch sequence".
