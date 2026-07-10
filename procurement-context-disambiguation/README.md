# procurement-context-disambiguation

The third worked application of MeshQu's public-research methodology (E3). E2 ended with three open interpretations. E3 was designed to separate them.

Three L3 decomposition arms test whether precedent receipts or accumulated context drive verdict commitment. An L4-without-nudge variant tests whether the anti-sycophancy clause or the policy text drives the L3 to L4 backoff. A scaled n=100 Permuted-Policy diagnostic and a Claude Opus 4.7 replication arm test whether inversion-blindness is a task-class property or a model-specific one.

## Status

`[PUBLISHED]`. Released as MRP-2026-04 on 2026-06-09 at release tag `v1.0-mrp-2026-04`. Predictions were locked before any evaluation call at tag `v0.3-predictions-locked` (2026-05-28).

The canonical dataset is [`results/corpus.tar`](results/corpus.tar): 1,332 signed receipts across six conditions (`arm_a`, `arm_b`, `arm_c`, `l4_without_nudge` at 283 records each, `diagnostic_primary` and `diagnostic_claude` at 100 records each). Analysis-ready exports live in [`../data/`](../data/).

Two older status lines elsewhere in this experiment predate the run and are stale:

- [`results/README.md`](results/README.md) says the results directory is empty. It is not. It was written before the run and is preserved as-is. The corpus, the analysis charts, the rubric coding sheets, and the run trail are all present.
- [`planning/predictions.md`](planning/predictions.md) describes itself as "pre-lock". The `v0.3-predictions-locked` tag is the lock. See [`planning/PREDICTIONS_NOTE.md`](planning/PREDICTIONS_NOTE.md).

## Layout

```
procurement-context-disambiguation/
├── README.md     # this file
├── planning/     # design, predictions, decision log, locked build packages
├── runner/       # multi-arm runner, prompts, diagnostic harness
├── policy/       # reuses E1's ratified snapshot
├── results/      # corpus.tar (canonical), analysis charts, coding sheets, run trail
└── writeup/      # markdown source for the published piece
```

## What carries over

E3 reuses E1's 283-record corpus, E2's model configuration (`gpt-5.4-2026-03-05`, temperature 0, except the Claude arm), and the same ratified policy snapshot (`cbf12348-6248-48f7-a06f-4e0304cc237e`) as both prior experiments. The Claude arm runs `claude-opus-4-7`.

## Key documents

| Document | Purpose |
|---|---|
| [`planning/predictions.md`](planning/predictions.md) | Pre-registered predictions P1 to P6, frozen at `v0.3-predictions-locked` |
| [`planning/PREDICTIONS_NOTE.md`](planning/PREDICTIONS_NOTE.md) | Why the predictions file says "pre-lock" and why that prose is preserved |
| [`planning/decision_log.md`](planning/decision_log.md) | Reverse-chronological journal of design decisions |
| [`writeup/writeup.md`](writeup/writeup.md) | The published piece (MRP-2026-04) |
| [`results/runs/README.md`](results/runs/README.md) | What the run trail is and why it is not analysis input |
