# planning — procurement-context-gradient

This folder is the methodology layer for the second piece. It contains the experiment design, the pre-registered predictions, the substrate posture, the decision log, and the writeup outline. Read it before the runner, the corpus, or the writeup — it is the contract everything downstream evaluates against.

## Why so much planning for what looks like a re-run

E2 reuses E1's corpus, model, policy snapshot, and substrate adapter. The methodological discipline is harder *because* of the reuse — every reused element is a fixed point that lets E2's findings attach to E1's results without ambiguity. The variation is one axis only: governance context. Locking the ladder shape, the verdict space, and the analytical lens before the run is what makes the L0 → L4 trajectory interpretable.

## Reading order for a fresh reader

1. `experiment_design.md` — methodology, multi-pass runner, what's held constant, what varies
2. `context_ladder_design.md` — the 5 levels, payload shapes, the L1-vs-L2 distinction (rationale matters), additivity invariant
3. `predictions.md` — the 7 pre-registered predictions, falsification criteria, the echo-trap detection pair (P3 + P4 + P5)
4. `substrate.md` — primarily a pointer to E1's substrate documentation; lists the few additions
5. `writeup_outline.md` — what gets published, the conceptual centre, the structural boundaries

## What's locked

| Element | Value | Source |
|---|---|---|
| Foundation model | `gpt-5.4-2026-03-05` | Locked in E1 (decision_log 2026-05-17) |
| Temperature | `0` | Locked in E1 |
| Verdict space | `ALLOW / REVIEW / DENY` | Locked in E1 |
| Policy snapshot | `cbf12348-6248-48f7-a06f-4e0304cc237e` | Locked in E1 (post-PROC-004-COI clarification, 2026-05-17) |
| Corpus | 283 unique decisions from E1 (`corpus.tar`, SHA-256 `1b6192df…`) | Inherited from E1 |
| Substrate | UK Contracts Finder OCDS (no new fetch) | Inherited from E1 |
| Number of context levels | 5 (L0 through L4) | Locked at Phase 0 |
| Additivity invariant | Each level sees *everything* the previous level saw plus the new addition | Locked at Phase 0 |

## What's NOT locked yet

- `predictions.md` is drafted but not yet tagged. Lock at `v0.2-predictions-locked` only after the design has been reviewed.
- The runner is not yet built; Phase 1 work.
- Cost budget envelope (token consumption, total OpenAI spend) — to be finalised after smoke run.

## Pre-registration target

Tag `v0.2-predictions-locked` once `predictions.md` and `context_ladder_design.md` are finalised. The lock commit must include both files at their final pre-run state.
