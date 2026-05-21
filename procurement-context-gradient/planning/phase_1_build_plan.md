# Phase 1 — Build + Smoke + Dry-run plan

> **Pre-requisites met** (2026-05-21): `v0.2-predictions-locked` tag applied at commit `2ac6005e`; policy snapshot persisted at `policy/policy-snapshot-cbf12348.json`; Phase 0 planning documents merged on `main`.
>
> **Goal of Phase 1**: build the multi-pass runner, smoke-test it, dry-run-test it, and arrive at "ready to fire the full 1,415-receipt corpus run." All work happens between this document landing and the moment of Phase 2 execute kickoff.

## What Phase 1 produces

By the end of Phase 1, the following must be true:

- **Multi-pass runner** lives at `procurement-context-gradient/runner/` and can be invoked end-to-end to evaluate a record set across all 5 context levels plus the Permuted-Policy diagnostic.
- **L0 baseline reproduces E1** within OpenAI's noise band at temp 0 (the L0-vs-E1 reproducibility check).
- **Level-batching execution order** is implemented and verified to preserve the L4 prompt-cache prefix.
- **L3 deterministic precedent selector** reads exclusively from E1's frozen archive and produces reproducible neighbour sets.
- **L4 full-policy prompt** renders the locked snapshot JSON into a cache-friendly prefix.
- **Permuted-Policy diagnostic** generates the 14-record adversarial control with `policy_permutation_seed` bound into the receipt integrity payload.
- **Smoke** (3 records × 5 levels + 1 Permuted-Policy pilot) produces 16 receipts, all verifying offline at `verify.meshqu.com`.
- **Dry-run** (30 records × 5 levels + full 14-record Permuted-Policy) produces 164 receipts, all verifying, with cost projection observed.
- **Pre-full-run checklist** signed off — every readiness gate green before Phase 2 launches.

## Three stages, ten work items

```
STAGE A (Sam authors, ~2h focused)
└── Locked content authoring (L1 prose, L2 format, L3 block format, L4 envelope)

STAGE B (agent-dispatchable, ~25h, parallelisable)
├── E2-001  Multi-pass runner orchestration              [foundation]
├── E2-002  L0 baseline + substrate cache reader         [depends on E2-001]
├── E2-003  L1 + L2 payload generators                   [depends on E2-001 + Stage A]
├── E2-004  L3 nearest-neighbour precedent selector      [depends on E2-001 + Stage A]
├── E2-005  L4 full policy payload + cache preservation  [depends on E2-001 + Stage A]
└── E2-006  Permuted-Policy diagnostic control            [depends on E2-005]

STAGE C (sequential, ~6h)
├── E2-007  Smoke run + validation                       [depends on E2-002..006]
├── E2-008  Dry-run + validation                          [depends on E2-007]
└── E2-009  Pre-full-run readiness checklist              [depends on E2-008]
```

## Dependency graph

```
                              v0.2-predictions-locked
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
                   STAGE A                         E2-001 (runner foundation)
        ┌──────────┬─┴─┬──────────┐                    │
        ▼          ▼   ▼          ▼                    │
       L1 prose  L2  L3 block   L4 envelope            │
        │         │   │          │                     │
        └────┬────┘   │          └───────┬─────────────┘
             │        │                  │
             ▼        ▼                  ▼
           E2-003   E2-004             E2-005
             │        │                  │
             │        │                  ▼
             │        │                E2-006 (Permuted-Policy)
             │        │                  │
             └────────┼──────────────────┘
                      ▼
                   E2-002 (L0 baseline) — actually independent;
                                          can run in parallel with E2-003..006
                      │
                      ▼
                   E2-007 (smoke) — gate after all of E2-002..006
                      │
                      ▼
                   E2-008 (dry-run) — gate after smoke clean
                      │
                      ▼
                   E2-009 (full-run readiness) — final gate
                      │
                      ▼
                   PHASE 2 BEGINS
```

## Effort estimates

| Item | Effort | Notes |
|---|---|---|
| Stage A (locked content) | ~2h focused | Sam-only |
| E2-001 Multi-pass runner | ~8h | Foundation; fork E1's runner |
| E2-002 L0 + substrate cache | ~4h | Reproducibility sanity check is part of done |
| E2-003 L1 + L2 generators | ~3h | Trivial once Stage A content lands |
| E2-004 L3 precedent selector | ~5h | The most algorithmically novel piece |
| E2-005 L4 + cache preservation | ~3h | Mechanical given the locked JSON |
| E2-006 Permuted-Policy diagnostic | ~4h | Operator-permutation function + receipt format extension |
| E2-007 Smoke run + validation | ~2h | Mostly observation + verification |
| E2-008 Dry-run + validation | ~2h | Mostly observation; uncovers cost surprise if any |
| E2-009 Full-run readiness | ~2h | Checklist sign-off |
| **TOTAL** | **~35h** | ~1 working week if linear; ~3 days with parallelism |

## Parallelism opportunities

- **Stage A runs in parallel with E2-001.** Sam authors content while an agent forks the runner.
- **E2-003 / E2-004 / E2-005 / E2-006 can all run in parallel after E2-001 lands** (plus their Stage A dependencies). Four agents in parallel — same background-pack pattern as PACK-A/B/C/D.
- **E2-002 runs in parallel with E2-003..006** — it only depends on E2-001 + the substrate cache reader, no Stage A content.
- **Stage C (E2-007..009) is strictly sequential.** Each depends on the previous passing.

## Recommended dispatch sequence

**Day 1**
- Sam authors Stage A content (~2h)
- Spawn E2-001 in background (~8h agent time)

**Day 2**
- E2-001 done, ready to review
- Spawn E2-002, E2-003, E2-004, E2-005 in parallel (4 background agents)
- E2-006 waits for E2-005

**Day 3**
- Review + merge E2-002..005
- Spawn E2-006 (1 background agent)

**Day 4**
- Review + merge E2-006
- Spawn E2-007 smoke run
- Review smoke; if clean, spawn E2-008 dry-run
- Review dry-run; if clean, spawn E2-009 readiness checklist

**Day 5 (or later — gate)**
- E2-009 sign-off
- Phase 2 launch decision

## Decision points along the way

These warrant explicit Sam-touches:

1. **Stage A content review.** Once Sam writes L1 prose etc., does the L0-vs-L1 prose feel like a meaningful step? If it reads too similar to L0, the ladder collapses on this rung. Adjust before E2-003 starts.

2. **E2-001 forking decision.** Fork E1's runner into `procurement-context-gradient/runner/` OR import it as a path-relative dependency. Recommended in E2-001: fork. Reason: (a) E1 is the published artefact; modifying its runner post-publication is uncomfortable. (b) Forking surfaces the duplication that informs the eventual `methodology/` extraction. (c) Provenance preserved via decision_log + run-manifest IDs.

3. **L0-vs-E1 reproducibility band.** After E2-002 produces L0 receipts for the 3 smoke records, compare against E1's receipts for the same OCIDs. If the verdicts differ on ≥1 of 3, decide: continue (within reproducibility noise) or investigate (something has drifted). The E1 P4 deferral becomes a finding either way.

4. **Smoke cost projection.** E2-007 measures actual token consumption with level-batching cache active. If realised cost is dramatically above projection, the dry-run gives one more data point before committing to the full 1,415-call run. If realised cost is dramatically below — even better, but verify the cache is actually being read.

5. **Permuted-Policy outcome on the pilot.** The Permuted-Policy diagnostic runs on a small pilot during E2-007. The point of running it early is to surface implementation bugs in the permutation function before the full 14-record diagnostic in E2-008. If the smoke pilot's verdict pattern is implausible (e.g. the agent flags the contradiction at L4_PERMUTED but accepts the inverted logic in its own reasoning), the permutation function may not be doing what we think.

## The pre-full-run readiness checklist (E2-009)

For convenience, the gating items the final checklist covers:

- [ ] All 1,415 expected (record × level) pairs have a runner code path that exercises them
- [ ] L0-vs-E1 reproducibility verified on ≥10 records (smoke + dry-run combined)
- [ ] Level-batching cache savings observed in token-usage logs (≥30% L4 reduction realised)
- [ ] All receipts in smoke + dry-run verify offline at `verify.meshqu.com`
- [ ] `governance_context_level` field present in every receipt's integrity payload
- [ ] Permuted-Policy 14-record diagnostic produces 14 distinct receipts with `policy_permutation_seed` bound into each
- [ ] Permuted-Policy receipts cryptographically distinguishable from main-run receipts (different level marker, different policy SHA)
- [ ] No service-role surfaces invoked from the runner (only signed API key)
- [ ] Run manifest captures: model id, temperature, prompt SHA per level, policy snapshot SHA, substrate adapter version, runner git commit
- [ ] Monitoring dashboards configured (the Grafana captures Appendix B will use)
- [ ] Cost projection within budget envelope
- [ ] Rate-limiting pacing verified (no 429s in dry-run)

## What this plan does NOT cover

- **The full 1,415-receipt run itself** (Phase 2).
- **Cross-level analysis notebook authoring** (Phase 3).
- **Writeup drafting** (Phase 3).
- **Methodology extraction to top-level `methodology/`** (Phase 4, post-publish).

These are explicitly scoped out so Phase 1's exit gate (E2-009) is unambiguous: "ready to fire the full run, end of phase."

## Build packages reference

The 9 build packages are in [`build_packages/`](build_packages/). Each is a self-contained agent prompt suitable for background dispatch. [`build_packages/_INDEX.md`](build_packages/_INDEX.md) summarises them.

Stage A authoring guidance is in [`stage_a_content_authoring.md`](stage_a_content_authoring.md).
