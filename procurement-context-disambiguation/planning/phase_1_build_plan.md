# E3 Phase 1 — Build + Smoke + Dry-run plan

> **Pre-requisites met** (2026-05-28): `v0.3-predictions-locked` tag applied at commit `ba4ebfb`; all locked content authored and SHA-bound by the tag (Arm B redaction format, Arm C density control [neutrality-reviewed], L4-without-nudge prompt, diagnostic 3-category rubric); model pin resolved (`claude-opus-4-7`, no `temperature`, `output_config.effort: low`); feasibility spike landed at `runner/spike/claude_spike.py`.
>
> **Goal of Phase 1**: build the E3 runner — forked from E2's — wire the three L3 arms + the L4-without-nudge variant + the Claude cross-model arm + the scaled diagnostic + the rubric-coding tooling, smoke-test, dry-run, and arrive at "ready to fire the full corpus run." All work happens between this document landing and the moment of Phase 2 execute kickoff.

## What Phase 1 produces

By the end of Phase 1, the following must be true:

- **E3 runner** lives at `procurement-context-disambiguation/runner/meshqu_runner/`, forked from E2 (`procurement-context-gradient/runner/`), and can be invoked end-to-end to evaluate a record set under any of: Arm A (precedents-only), Arm B (precedents-no-verdict), Arm C (density-control), L4-without-nudge, or the scaled Permuted-Policy diagnostic on either the primary or the cross-model agent.
- **The three L3 arms are mutually distinguishable** in the receipt integrity payload (each arm signs a different `l3_arm` marker, and the rendered prompt SHAs differ).
- **Arm A reproduces E2's L3 verbatim** — byte-identical rendered prompt against E2's `L3_precedent_block_format.md`. The reproducibility check is part of done.
- **Arm B renders the cases without the verdict signal** — automated check that no verdict / violations / E1-reasoning field substrings appear in the rendered Arm B payload.
- **Arm C renders the density-control block** with token count parity (within ±5%) against E2's rendered L3 payload over the same target records.
- **L4-without-nudge handler** renders `L4_without_nudge.md` (the surgical nudge-excision variant) and the receipt carries a `nudge_excised: true` marker.
- **Claude cross-model arm** calls `claude-opus-4-7` via the Anthropic SDK with no `temperature` and `output_config.effort: low`, using E2's verbatim `system_prompt.md`. The receipt's integrity payload includes `model_id: claude-opus-4-7` and the sampling caveat (`temperature: null`, `effort: "low"`).
- **Diagnostic subset (n=100)** generated deterministically by `sha256(ocid)` sort and committed as a locked OCID list at `planning/diagnostic_subset.json`.
- **Rubric-coding tooling** functional: presents each reasoning text + the record's inverted-operator spec side-by-side, takes a category (1/2/3) + a one-line justification quote, writes the coding sheet to a structured artifact.
- **Smoke** (3 records × {Arm A, B, C, L4-no-nudge} + 1 primary diagnostic + 1 Claude diagnostic = 14 receipts) produces all 14, all verifying offline at `verify.meshqu.com`.
- **Dry-run** (30 records × {Arm A, B, C, L4-no-nudge} + 10 primary diagnostic + 10 Claude diagnostic = 140 receipts) produces all 140, all verifying, with cost projection observed for the full corpus run.
- **Pre-full-run readiness checklist** signed off — every gate green before Phase 2 launches.

## Three stages, twelve work items

```
STAGE A (none — locked content is pre-authored; bound by v0.3 tag)

STAGE B (agent-dispatchable, ~30h, highly parallelisable)
├── E3-001  Runner foundation: fork + arm-aware handler scaffold     [foundation]
├── E3-002  Arm A handler — precedents-only                           [depends on E3-001]
├── E3-003  Arm B handler — precedents-no-verdict                     [depends on E3-001]
├── E3-004  Arm C handler — density-control + token parity            [depends on E3-001]
├── E3-005  L4-without-nudge handler                                  [depends on E3-001]
├── E3-006  Claude cross-model swap (anthropic SDK adapter)           [depends on E3-001]
├── E3-007  Diagnostic subset selector + locked OCID list             [depends on E3-001]
├── E3-008  Scaled Permuted-Policy diagnostic (primary + Claude)      [depends on E3-006 + E3-007]
└── E3-009  Rubric-coding tool                                        [depends on E3-001]

STAGE C (sequential, ~7h)
├── E3-010  Smoke run + validation                                    [depends on E3-002..E3-009]
├── E3-011  Dry-run + validation                                       [depends on E3-010]
└── E3-012  Pre-full-run readiness checklist                           [depends on E3-011]
```

## Dependency graph

```
                              v0.3-predictions-locked
                                       │
                                       ▼
                                E3-001 (runner foundation: fork + arm scaffold)
        ┌──────────┬──────────┬──────┬─┴─┬──────────┬──────────┬──────────┐
        ▼          ▼          ▼      ▼   ▼          ▼          ▼          ▼
      E3-002    E3-003     E3-004  E3-005  E3-006   E3-007    E3-009    (parallel — up to 7 background agents)
      Arm A     Arm B      Arm C   L4-no-  Claude   Subset    Rubric
                                   nudge   swap     selector  tool
                                                       │         │
                                                       └────┬────┘
                                                            ▼
                                                         E3-008 (scaled diagnostic, primary + Claude)
                                                            │
        ┌───────────────────────────────────────────────────┘
        ▼
      E3-010 (smoke) — gate after all of E3-002..E3-009
        │
        ▼
      E3-011 (dry-run) — gate after smoke clean
        │
        ▼
      E3-012 (full-run readiness) — final gate
        │
        ▼
      PHASE 2 BEGINS
```

## Effort estimates

| Item | Effort | Notes |
|---|---|---|
| E3-001 Runner foundation | ~5h | Fork E2's runner; introduce the arm-aware handler scaffold; preserve substrate cache + signing path |
| E3-002 Arm A handler | ~2h | Wires E2's existing L3 precedent selector + `L3_precedent_block_format.md` to a no-L1/L2 baseline. Byte-identity check against E2 is part of done. |
| E3-003 Arm B handler | ~3h | Reuses E2's precedent selector; renders through `armB_precedent_no_verdict_format.md` (verdict-redacted); contamination check (no verdict/violation/E1-reasoning substrings) |
| E3-004 Arm C handler | ~3h | No precedent selector; renders the static `armC_density_control.md`; token-count parity check against E2's L3 payload over the same target records |
| E3-005 L4-without-nudge handler | ~2h | Surgical fork of E2's L4 envelope handler; swaps prompt to `L4_without_nudge.md`; receipt marker `nudge_excised: true` |
| E3-006 Claude swap | ~5h | Anthropic SDK adapter; no `temperature`, `effort: low`; verbatim E2 `system_prompt.md`; verdict-JSON parser (Opus parses clean per spike); receipt `model_id` + sampling-caveat fields |
| E3-007 Diagnostic subset selector | ~2h | Deterministic util: sha256(ocid) sort, lowest 100; emits `planning/diagnostic_subset.json` (committable locked artifact) |
| E3-008 Scaled diagnostic | ~4h | Extends E2's Permuted-Policy diagnostic to run over the locked n=100 on primary; same n=100 on Claude (record-matched) |
| E3-009 Rubric tool | ~3h | CLI coder script: presents reasoning text + inverted-operator spec side-by-side; captures category + justification quote; outputs structured coding sheet |
| E3-010 Smoke | ~2h | 14 receipts; verify all offline; surface any rendering-shape surprises before dry-run |
| E3-011 Dry-run | ~3h | 140 receipts; verify all offline; cost projection extrapolated to full ~1,400-receipt run |
| E3-012 Readiness | ~2h | Final checklist sign-off |
| **TOTAL** | **~36h** | ~1 working week linear; ~3 days with 7-way parallelism in Stage B |

## Parallelism opportunities

- **After E3-001 lands, E3-002..E3-007 + E3-009 all run in parallel** (7 background agents). Same dispatch idiom as E2's PACK-A/B/C/D, just wider.
- **E3-008 (scaled diagnostic) waits for E3-006 + E3-007** to merge. Once both are in, it's a single-agent task.
- **E3-009 (rubric tool) is offline** (no model calls, no runner orchestration) and can run any time after E3-001.
- **Stage C (E3-010..012) is strictly sequential.** Each depends on the previous passing clean.

## Recommended dispatch sequence

**Day 1**
- Spawn E3-001 in background (~5h agent time)

**Day 2**
- E3-001 done, ready to review. Merge.
- Spawn E3-002, E3-003, E3-004, E3-005, E3-006, E3-007, E3-009 in parallel (7 background agents)

**Day 3**
- Review + merge E3-002..E3-007 + E3-009.
- Spawn E3-008 (scaled diagnostic)

**Day 4**
- Review + merge E3-008
- Spawn E3-010 smoke
- Review smoke; if clean, spawn E3-011 dry-run

**Day 5**
- Review dry-run; if clean, spawn E3-012 readiness checklist
- E3-012 sign-off; Phase 2 launch decision

## Decision points along the way

These warrant explicit Sam-touches:

1. **E3-001 fork strategy.** Fork E2's runner (recommended) — same reasoning as E2's E2-001: E2 is the published artefact, modifying its runner post-publication is uncomfortable, and forking surfaces the duplication that informs the eventual methodology extraction. Provenance preserved via decision_log + run-manifest IDs.

2. **Arm A byte-identity check (E3-002).** Arm A is supposed to render the L3 precedent block byte-identically to E2 for the same target record + same precedent set. If the byte check fails, either E3-002 has drifted from E2's L3 renderer, or E2's renderer was non-deterministic in a way we hadn't noticed. Surface to Sam in the PR body either way.

3. **Arm C token-count parity threshold (E3-004).** The design specifies "within ±5%" of E2's rendered L3 payload over the same target records. If the realised parity is ±10% or worse, decide: (a) accept and document as a methods caveat (a 10% volume gap doesn't undermine the *no concrete records / no verdicts* control claim); or (b) author a brief Arm C top-up to close the gap (would require a planned post-tag content addendum with a fresh SHA bound into the receipts).

4. **Claude swap — receipt schema impact (E3-006).** The receipt now needs to carry `model_id`, and for Opus 4.7 also `temperature: null`, `effort: "low"`. This may bump the receipt schema version (or use the v2 envelope's extensibility). Decide: extend in place vs new schema version. Default recommendation: extend in place, since cross-model is a metadata addition not a semantic shift.

5. **Smoke pilot — Claude verdict shape (E3-010).** The spike confirmed Opus parses verdict JSON cleanly on 3 synthetic records. The smoke runs Claude on 1 real corpus record — first time the cross-model arm sees the locked diagnostic substrate. If the verdict shape or JSON structure deviates (unexpected fields, wrapped formats, etc.), surface before dry-run scale.

6. **Dry-run cost projection (E3-011).** Extrapolate observed token consumption to the full run: ~849 receipts for the three L3 arms (283 × 3), ~283 for L4-without-nudge, ~100 for primary diagnostic, ~100 for Claude diagnostic = **~1,332 receipts** (plus reruns and any L0-baseline freshness check, so budget ~1,500). If projection lands wildly off budget, decide before committing to Phase 2.

## The pre-full-run readiness checklist (E3-012)

For convenience, the gating items the final checklist covers:

- [ ] All locked content (v0.3 tag) referenced unchanged from the runner (SHA check)
- [ ] Arm A renders E2's `L3_precedent_block_format.md` byte-identically against the same record + precedent set (reproducibility verified on ≥3 records)
- [ ] Arm B rendered output contains NO verdict / violations / E1-reasoning field substrings (automated assertion in tests)
- [ ] Arm C rendered output token count is within ±5% of E2's rendered L3 payload over the same target records (≥5 records sampled)
- [ ] L4-without-nudge handler renders `L4_without_nudge.md` (not E2's `L4_policy_envelope.md`); receipt carries `nudge_excised: true`
- [ ] Diagnostic subset list (n=100) generated, committed to `planning/diagnostic_subset.json`, and reproduces deterministically across re-runs
- [ ] Claude SDK call uses `claude-opus-4-7`, NO `temperature`, `output_config: {effort: "low"}` — verified by inspecting the actual SDK call in tests
- [ ] Receipt integrity payload distinguishes by: `l3_arm` (A / B / C / null for L4-no-nudge), `nudge_excised` flag, `model_id`, `diagnostic: true` vs main-run, `policy_permutation_seed` for diagnostic
- [ ] All receipts in smoke + dry-run verify offline at `verify.meshqu.com`
- [ ] `governance_context_level` (or E3-equivalent rung marker) present in every receipt's integrity payload
- [ ] No service-role surfaces invoked from the runner (only signed API key)
- [ ] Run manifest captures: model id per arm, prompt SHA per arm, policy snapshot SHA, substrate adapter version, runner git commit, v0.3 tag SHA
- [ ] Rubric-scoring tooling functional + dry-coded on ≥5 reasoning texts produces valid output
- [ ] Monitoring dashboards configured (reuse the Grafana captures from E2)
- [ ] Cost projection within budget envelope
- [ ] Rate-limiting pacing verified (no 429s in dry-run on either provider)

## What this plan does NOT cover

- **The full ~1,332-receipt run itself** (Phase 2).
- **The 200 reasoning-text hand-codings** against the rubric — 100 primary diagnostic + 100 Claude diagnostic (Phase 2 or 2.5; runs after Phase 2 receipts exist).
- **Cross-arm + cross-model analysis notebook authoring** (Phase 3).
- **Writeup drafting** (Phase 3).
- **Methodology extraction to top-level `methodology/`** (the trilogy capstone — Phase 4, post-publish).

These are explicitly scoped out so Phase 1's exit gate (E3-012) is unambiguous: "ready to fire the full run, end of phase."

## Build packages reference

The 12 build packages are in [`build_packages/`](build_packages/). Each is a self-contained agent prompt suitable for background dispatch. [`build_packages/_INDEX.md`](build_packages/_INDEX.md) summarises them and shows the dispatch waves.
