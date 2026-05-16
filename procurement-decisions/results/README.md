# Results — Execution Capture and Research Notebook

> This directory holds everything produced by running the experiment.
> Operational telemetry, signed receipt corpus, observability captures,
> and the researcher's notebook all live here. The writeup draws from
> this directory; the writeup does not invent.

## Status

`[PRE-EXECUTION]`. Directory layout committed at revision brief 10 application; populated during build phase + run.

## What lives here

```
procurement-decisions/results/
├── README.md                 ← this file: discipline overview
├── run-manifest.json         ← canonical index per run (created at run time)
├── corpus.tar                ← signed receipt bundle (created post-run)
├── corpus/                   ← per-receipt files (gitignored if large; corpus.tar canonical)
├── audit/                    ← machine-readable: anomalies, checkpoints, decision traces
├── observability/            ← Grafana dashboard JSON + screenshots
└── notebook/                 ← researcher's notes; appendable findings documents
```

Each subdirectory has its own README explaining the discipline that governs it.

## Two complementary kinds of artefact

The discipline separates **machine-readable telemetry** from **human-readable interpretation**.

**Machine-readable (audit/, observability/dashboards/, run-manifest.json, corpus.tar).** Produced by the harness or by Grafana export. Per-decision audit JSONL, anomaly events with categorisation, checkpoint markers, dashboard JSON for reproducibility. These exist to support the writeup's "you could re-run this" claim — a reader can clone the repo, pull the substrate the same way, run against the same policy snapshot, and verify the receipts byte-for-byte against this corpus.

**Human-readable (notebook/, observability/screenshots/).** Produced by Sam during and after the run. Live notes ("record 147 saw 3s signing latency; investigated; network blip"). Post-run findings ("most direct-award misfires happen in central-government records; reason TBD"). Decision rationale for in-flight adjustments. Cross-references between observations and pre-registered predictions. These exist to support the writeup's interpretive claims — the writeup quotes from the notebook rather than reconstructing from memory.

Both anchor to the same run via the run manifest (its commit hash, its OCID list, its model version + prompt hash + tenant).

## Discipline at a glance

| Rule | Why |
|---|---|
| **Notebook is append-only.** Edits to past entries get a `[corrected YYYY-MM-DD]` note rather than silent overwrites. | Writeup credibility leans on the notebook being a contemporaneous record. Silent overwrites turn it into a story-after-the-fact. |
| **Every notebook entry is timestamped and linked.** Entry header carries the date; references to specific decisions / runs / commits use IDs and SHAs. | A finding has to point at evidence. References are how the writeup chains "we observed X" → "here's the receipt where X happened." |
| **Findings cite pre-registered predictions by ID.** A finding that bears on P6-C says so. | Section 5b's prediction-by-prediction reporting walks straight from findings to predictions; the linkage exists in the notebook so it survives writeup-time. |
| **No raw OCDS records in committed corpus.** OGL v3.0 covers redistribution with attribution, but the discipline is "references not redistributions" — corpus references each record by its public OCID and source URL. | Per substrate.md ethical-posture decisions. |
| **Audit JSONL files are append-only at run time.** The harness writes new lines; nothing rewrites past lines. | Same reason as the notebook — a contemporaneous record. |
| **Grafana dashboard JSON is committed before screenshots.** The dashboard that produced a screenshot is also the dashboard that's auditable. | Reproducibility of the operational claim. |

## Relationship to the run manifest

`run-manifest.json` is the canonical index. Every artefact in this directory references back to the manifest's run-id and the manifest references back to the planning-harness commit it was run against. When the writeup says "we ran 300 records against the locked policy", the chain is:

- `run-manifest.json` declares: locked-predictions commit hash, policy snapshot ID, agent model + version, prompt SHA-256, OCID list of the 300 records, run start/end timestamps, total receipts produced.
- Each receipt in `corpus.tar` carries its own integrity hash, signature, and `policy_snapshot_digest` matching the manifest.
- Each entry in `audit/decision_traces.jsonl` references the manifest's run-id and the specific OCID + receipt.
- Notebook entries reference manifest run-id when they bear on a specific run.

A reader following the chain from notebook entry → decision trace → receipt → manifest → planning-harness commit → predictions lock can verify the entire claim chain without trusting any single artefact.

## What gets committed vs gitignored

| Artefact | Committed? | Notes |
|---|---|---|
| `run-manifest.json` | Yes | Canonical per-run index |
| `corpus.tar` | Yes | Signed bundle; size manageable (300 receipts ≈ tens of MB) |
| `corpus/` (unbundled per-receipt files) | Gitignored | Bundle is canonical; per-receipt files are reconstructable |
| `audit/*.jsonl` | Yes | Per-decision traces, anomalies, checkpoints — machine-readable evidence |
| `observability/dashboards/*.json` | Yes | Dashboard JSON for reproducibility |
| `observability/screenshots/*.png` | Yes | Captured during the run; Appendix B source material |
| `notebook/*.md`, `notebook/findings/*.md` | Yes | Append-only human notes |
| `spike_data/` (sibling of results, in planning/) | Gitignored | Sacrificial pre-pre-registration data, separate concern |

The gitignored `corpus/` exception accommodates the "30 reproducibility re-run records" case: per-record JSON files might be useful working artefacts during analysis but are reconstructable from `corpus.tar` plus the re-run command. Don't commit them; do reference them in the manifest if produced.

## Build-phase prerequisites

This directory layout commits at revision brief 10 application. Three build-phase capabilities depend on it being honoured:

1. The harness's execution-capture path writes to `audit/` per the schemas documented in `audit/README.md`. The substrate adapter + evaluation pipeline both honour the audit conventions.
2. The dry run (Phase C) and full run (Phase D) populate `audit/`, `observability/screenshots/`, and `corpus*` per these conventions; the notebook captures observations as they happen.
3. The writeup drafting (Phase G) cites from this directory; section 5b worked example pulls from a specific receipt + its audit trace + the notebook entry that records the finding.

If the harness execution ever bypasses these conventions, the writeup loses its evidence chain. The discipline is the credibility argument.

## Cross-references

- [`procurement-decisions/planning/experiment_design.md`](../planning/experiment_design.md) — methodology that this directory supports
- [`procurement-decisions/planning/predictions.md`](../planning/predictions.md) — locked predictions that the notebook references by ID
- [`procurement-decisions/planning/decision_log.md`](../planning/decision_log.md) — the brief-10 application entry that committed this discipline
- [`procurement-decisions/writeup/`](../writeup/) — the writeup that draws from this directory
