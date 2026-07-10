# procurement-decisions

The first worked application of MeshQu's public-research methodology: an LLM agent reviews 300 public UK procurement filings and proposes compliance verdicts; MeshQu evaluates each decision against a documented policy and produces a signed receipt; the resulting corpus is published, downloadable, and verifiable offline at [verify.meshqu.com](https://verify.meshqu.com).

## Status

`[PUBLISHED]`. Released as MRP-2026-02 on 2026-05-18. The canonical dataset is [`results/corpus.tar`](results/corpus.tar): 283 signed receipts, one per unique procurement record. The run attempted 300 releases; the source feed returned 12 OCIDs more than once, so the corpus deduplicates to 283 unique decisions. Analysis-ready exports live in [`../data/`](../data/).

## Layout

```
procurement-decisions/
├── README.md     # this file
├── planning/     # design, predictions, methodology, decision log, spike reports
├── runner/       # agent harness + MeshQu client wiring (built during build phase)
├── policy/       # ratified policy snapshot (authored at build phase)
├── results/      # corpus, manifest, run logs, Grafana screenshots (populated during the run)
└── writeup/      # markdown source for the published piece (drafted post-run)
```

The planning harness contains everything needed to understand and audit the experiment design before predictions lock. Start with [`planning/README.md`](planning/README.md) for a top-level orientation, then [`planning/project_context.md`](planning/project_context.md) for full design context.

## Key documents in `planning/`

| Document | Purpose |
|---|---|
| [`README.md`](planning/README.md) | Top-level summary and rationale |
| [`project_context.md`](planning/project_context.md) | Full orientation for a fresh reader |
| [`experiment_design.md`](planning/experiment_design.md) | Methodology — agent loop, policy under test, evaluation pipeline, substrate-honesty |
| [`predictions.md`](planning/predictions.md) | Pre-registered predictions (locked before the run) |
| [`substrate.md`](planning/substrate.md) | Data sourcing — UK Contracts Finder, sampling, ethical posture |
| [`writeup_outline.md`](planning/writeup_outline.md) | The artefact: blog-post outline, what gets published where |
| [`decision_log.md`](planning/decision_log.md) | Reverse-chronological journal of design decisions |
| [`feasibility_spike_report.md`](planning/feasibility_spike_report.md) | Phase 0 substrate spike findings |
| [`feasibility_spike_c1_report.md`](planning/feasibility_spike_c1_report.md) | Phase 0.5 narrow spike confirming `awards[0].datePublished` semantics |
| [`candidate_faithful_rules.md`](planning/candidate_faithful_rules.md) | Post-Phase-0 candidate rule analysis |

## What gets published

In order of importance:

1. **Blog post** at `meshqu.com/research/procurement-decisions/`.
2. **Open repo** at `github.com/meshqu/meshqu-research/procurement-decisions/` — includes the methodology trail (substrate adapter, evaluation pipeline, policy authoring) under `planning/`.
3. **Receipt corpus** as a downloadable bundle (tar) at `meshqu.com/research/procurement-decisions/corpus.tar`. Reader drops it into verify.meshqu.com.
4. **Policy snapshot JSON** alongside the corpus.
5. **Pre-registration commit hash + timestamp** linked from the writeup — points at the locked-predictions commit in this repo.
6. **Raw agent outputs** so readers can audit the LLM's reasoning.
7. **Grafana screenshots** in `results/observability/` documenting operational behaviour during the run.

## How to read this

Engineers at regulated firms are the primary audience. The piece is engineer-to-engineer: methodology-heavy, data published, receipt corpus reproducible. Compliance leads read it second, through their engineer's forwarding.

For a one-paragraph summary of the thesis, see [`planning/writeup_outline.md`](planning/writeup_outline.md) — the locked voice reference at the bottom is the gold-standard opening 300 words.
