# E3 Phase 1 — build packages index

Twelve self-contained agent prompts. Each is dispatchable to a background agent that has **not** seen the conversation that authored these — read the package, the locked content it cites, and the runner foundation, and you have what you need.

## Pre-requisites for every package

- Tag `v0.3-predictions-locked` exists at `ba4ebfb` and binds the locked content.
- Repo is `MeshQu/meshqu-research`. Open PRs into `main`. Branch names: `feat/e3-XXX-<slug>`.
- The conventions inherited from E2 (substrate adapter, Ed25519 signing + Rekor, bundle envelope versioning, frozen-archive isolation for any precedent material) are non-negotiable.
- All packages start by reading `procurement-context-disambiguation/planning/phase_1_build_plan.md` and the specific files the package's "Inherit first" section names.

## Packages

| ID | Title | File | Hard deps | Effort | Wave |
|---|---|---|---|---|---|
| **E3-001** | Runner foundation — fork + arm-aware handler scaffold | [e3-001-runner-foundation.md](e3-001-runner-foundation.md) | v0.3 tag | ~5h | 1 |
| **E3-002** | Arm A handler — precedents-only | [e3-002-arm-a-precedents-only.md](e3-002-arm-a-precedents-only.md) | E3-001 | ~2h | 2 |
| **E3-003** | Arm B handler — precedents-no-verdict | [e3-003-arm-b-precedents-no-verdict.md](e3-003-arm-b-precedents-no-verdict.md) | E3-001 | ~3h | 2 |
| **E3-004** | Arm C handler — density-control + token parity | [e3-004-arm-c-density-control.md](e3-004-arm-c-density-control.md) | E3-001 | ~3h | 2 |
| **E3-005** | L4-without-nudge handler | [e3-005-l4-without-nudge.md](e3-005-l4-without-nudge.md) | E3-001 | ~2h | 2 |
| **E3-006** | Claude cross-model swap (anthropic SDK) | [e3-006-claude-swap.md](e3-006-claude-swap.md) | E3-001 | ~5h | 2 |
| **E3-007** | Diagnostic subset selector (n=100) | [e3-007-diagnostic-subset-selector.md](e3-007-diagnostic-subset-selector.md) | E3-001 | ~2h | 2 |
| **E3-008** | Scaled Permuted-Policy diagnostic (primary + Claude) | [e3-008-scaled-permuted-policy.md](e3-008-scaled-permuted-policy.md) | E3-006, E3-007 | ~4h | 3 |
| **E3-009** | Rubric-coding tool | [e3-009-rubric-coding-tool.md](e3-009-rubric-coding-tool.md) | E3-001 | ~3h | 2 |
| **E3-010** | Smoke run + validation | [e3-010-smoke-run.md](e3-010-smoke-run.md) | E3-002..E3-009 | ~2h | 4 |
| **E3-011** | Dry-run + validation | [e3-011-dry-run.md](e3-011-dry-run.md) | E3-010 | ~3h | 5 |
| **E3-012** | Pre-full-run readiness checklist | [e3-012-readiness-checklist.md](e3-012-readiness-checklist.md) | E3-011 | ~2h | 6 |

## Dispatch waves

```
Wave 1 (sequential foundation)
  └── E3-001

Wave 2 (parallel — fire all 7 background agents at once after E3-001 merges)
  ├── E3-002 Arm A
  ├── E3-003 Arm B
  ├── E3-004 Arm C
  ├── E3-005 L4-no-nudge
  ├── E3-006 Claude swap
  ├── E3-007 Subset selector
  └── E3-009 Rubric tool

Wave 3 (sequential — after E3-006 + E3-007 merge)
  └── E3-008 Scaled diagnostic

Wave 4 (sequential — after all of Wave 2 + Wave 3 merge)
  └── E3-010 Smoke

Wave 5 (sequential — after smoke clean)
  └── E3-011 Dry-run

Wave 6 (sequential — after dry-run clean)
  └── E3-012 Readiness checklist  →  PHASE 2 LAUNCH DECISION
```

## How to dispatch a package as a background agent

Use the harness pattern Sam already runs for parallel work:

1. From the meshqu-research repo, on a fresh branch from `main`, hand the package file as the agent's initial prompt.
2. The agent reads the package + the "Inherit first" files + the runner foundation, builds the work, runs the tests in the package's Definition of done, and opens a PR titled `feat(e3-XXX): <slug>`.
3. The PR body answers the "PR body must answer" section of the package (where present).
4. Sam reviews, requests changes if needed, merges when ready.

The packages are deliberately scoped to be *small* and *finishable in one session*. If an agent finds the scope ballooning, the stop conditions tell it to surface to Sam rather than expand the work.

## Provenance

Each merged PR adds an entry to `procurement-context-disambiguation/planning/decision_log.md` noting: PR number, merge SHA, task ID, key decisions made, anything the next agent in the chain needs to know.
