# procurement-decisions

The first worked application of MeshQu's public-research methodology: an LLM agent reviews 300 public UK procurement filings and proposes compliance verdicts; MeshQu evaluates each decision against a documented policy and produces a signed receipt; the resulting corpus is published, downloadable, and verifiable offline at [verify.meshqu.com](https://verify.meshqu.com).

## Status

`[PLANNING]`. Predictions not yet locked. Build phase has not started.

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
2. **Open repo** at `github.com/meshqu/meshqu-research/procurement-decisions/`.
3. **Methodology layer** at `github.com/meshqu/meshqu-research/methodology/` — substrate adapter, evaluation pipeline (Inspect AI integration), policy authoring playbook.
4. **Receipt corpus** as a downloadable bundle (tar) at `meshqu.com/research/procurement-decisions/corpus.tar`. Reader drops it into verify.meshqu.com.
5. **Policy snapshot JSON** alongside the corpus.
6. **Pre-registration commit hash + timestamp** linked from the writeup — points at the locked-predictions commit in this repo.
7. **Raw agent outputs** so readers can audit the LLM's reasoning.
8. **Grafana screenshots** in `results/observability/` documenting operational behaviour during the run.

## How to read this

Engineers at regulated firms are the primary audience. The piece is engineer-to-engineer: methodology-heavy, data published, receipt corpus reproducible. Compliance leads read it second, through their engineer's forwarding.

For a one-paragraph summary of the thesis, see [`planning/writeup_outline.md`](planning/writeup_outline.md) — the locked voice reference at the bottom is the gold-standard opening 300 words.
