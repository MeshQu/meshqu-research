# procurement-context-gradient

The second worked application of MeshQu's public-research methodology. Builds directly on `procurement-decisions/` (MRP-2026-02, published 2026-05-18) by **reusing its corpus, its model, its policy snapshot, and its substrate** — and varying one thing: the governance context the agent sees.

## Status

`[PUBLISHED]`. Released as MRP-2026-03 on 2026-05-27 at [meshqu.com/research/when-precedents-commit-ai-and-policy-pulls-it-back](https://www.meshqu.com/research/when-precedents-commit-ai-and-policy-pulls-it-back). Predictions locked at `v0.2-predictions-locked`. The canonical dataset is [`results/corpus.tar`](results/corpus.tar): 1,429 signed receipts (283 records at each of L0 to L4, plus the 14-record Permuted-Policy diagnostic). Analysis-ready exports live in [`../data/`](../data/).

## The research question

E1's headline finding was *evidence-sensitive caution*: the agent reached for REVIEW on 97.5% of the 283-record corpus, naming evidence gaps in its reasoning, committing to DENY on zero records — while MeshQu's executable policy produced 139 DENYs over the same evidence. The agent was not given the policy text.

E2 asks: **does providing AI agents with MeshQu's structured governance artefacts (DecisionContext, Decision Receipts, named violations, full policy text) reduce that evidence-incompleteness-driven escalation?**

If yes: MeshQu sits on both ends of the workflow — context-in *and* receipt-out. That is the moat-story.
If no: the agent's REVIEW-by-default is intrinsic, not context-driven. That scopes where AI fits in compliance workflows. Either result is a publishable finding.

## What carries over from E1

- **The 283-record corpus.** Reused exactly. Cross-experiment row-by-row delta tracking is the central analytical lens — *how does decision `ca19e737-…` shift from L0 REVIEW to its destination at L4?* Reusing the corpus preserves this comparison.
- **The model.** `gpt-5.4-2026-03-05` at `temperature=0`. Locked.
- **The verdict space.** ALLOW / REVIEW / DENY. Locked. Expanding the action tokens between experiments would invalidate the monotonicity predictions (P1, P2).
- **The policy snapshot.** `cbf12348-6248-48f7-a06f-4e0304cc237e` — the post-PROC-004-COI-clarification snapshot from E1. Locked. Changing rule thresholds between experiments would be measuring a moving target.
- **The substrate adapter.** UK Contracts Finder OCDS. Same field provenance envelope.

## What's new

- A **context-gradient ladder** — 5 strictly additive levels (L0 → L4) of governance context.
- A **multi-pass runner** — same 283 records × 5 levels = 1,415 LLM calls, each producing a signed receipt linked back to E1 via OCID.
- A **cross-level analysis layer** — per-record verdict trajectories across the 5 levels, agent-reasoning-text drift analysis, token-cost scaling.

## Layout

```
procurement-context-gradient/
├── README.md                # this file
├── planning/                # design, predictions, methodology, decision log
├── runner/                  # multi-pass runner (built in Phase 1)
├── policy/                  # reuses E1's ratified snapshot — placeholder for any data-driven amendments
├── results/                 # corpus, manifest, run logs, observability captures
└── writeup/                 # markdown source for the published piece (drafted post-run)
```

## Key documents in `planning/`

| Document | Purpose |
|---|---|
| [`README.md`](planning/README.md) | Top-level summary and rationale |
| [`experiment_design.md`](planning/experiment_design.md) | Methodology — multi-pass runner, ladder semantics, evaluation pipeline, comparison framing |
| [`context_ladder_design.md`](planning/context_ladder_design.md) | The 5 levels, payload shapes, what's added at each step, what is held constant |
| [`predictions.md`](planning/predictions.md) | Pre-registered predictions (to be locked at `v0.2-predictions-locked`) |
| [`substrate.md`](planning/substrate.md) | Substrate posture — primarily a pointer to E1's substrate documentation |
| [`writeup_outline.md`](planning/writeup_outline.md) | The artefact: outline, conceptual centre, the echo-trap as an explicit structural boundary |
| [`decision_log.md`](planning/decision_log.md) | Reverse-chronological journal of design decisions |

## What gets published

In order of importance:

1. **Long-form writeup** at `meshqu.com/research/procurement-context-gradient/` (working slug — final naming locked at publication).
2. **Open repo** at `github.com/meshqu/meshqu-research/procurement-context-gradient/` — full methodology trail under `planning/`.
3. **Receipt corpus** as a downloadable bundle (`corpus.tar`). 1,415 receipts. Verifiable offline at verify.meshqu.com.
4. **Cross-level analysis notebook** as Markdown under `results/notebook/cross_level_analysis/` — per-record verdict trajectories, agreement-progression plots, reasoning-drift study.
5. **Pre-registration commit hash + timestamp** linked from the writeup — points at `v0.2-predictions-locked`.
6. **Raw agent outputs across all 5 levels** so readers can audit how the agent's reasoning evolved with added context.
7. **Grafana captures** documenting operational behaviour during the run.

## How E2 unlocks the methodology extraction

E1 deliberately did NOT create a top-level `methodology/` folder; the speculative scaffold was removed on 2026-05-20 with the explicit rationale that *"the reusable methodology layer will be extracted once a second worked application provides a second anchor point to triangulate the abstraction from."*

**E2 is that second anchor.** Post-publication, the substrate adapter, evaluation pipeline, and policy-authoring patterns that survive *unchanged* across both E1 and E2 are the candidates for `methodology/` extraction. Patterns that diverged become design notes about the limits of the abstraction.

## Pieces this builds toward (Experiment 3)

E2 is the second of three experiments named in MRP-2026-02 §9:

> *Passive reviewer → context-aware reviewer → governed investigative agent.*

E3 (`procurement-investigation/`, deferred) introduces tool use and active evidence-seeking. E2 closes the "what does the agent do with explicit governance context?" question. E3 closes the "can MeshQu govern an investigation, not just a review?" question. The methodology extraction is a prerequisite for E3 being cheap to start.
