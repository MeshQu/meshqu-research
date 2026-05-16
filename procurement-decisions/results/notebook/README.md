# Notebook — Researcher's Observations

> Where Sam writes things down as the experiment runs and after.
> Append-only, timestamped, linked back to the run data it bears on.
> The writeup draws from here; the writeup does not reconstruct.

## Why this exists

Three months after the run, the writeup needs to draw on observations that were sharp at the time and have a tendency to blur. "Most of the direct-award misfires happen in central-government records" is the kind of finding that's obvious sitting in front of the data on Tuesday and ambiguous from memory on Friday. The notebook captures it on Tuesday so the writeup can quote it on Friday.

Two more reasons the discipline matters:

- **Pre-registration credibility.** The methodology says predictions were locked before runs. The notebook discipline says observations were captured at the time of observation rather than reconstructed afterwards. Same family of argument: contemporaneous record over after-the-fact narrative.
- **Methodology reusability.** A future research piece applying the same methodology starts with notebook discipline as part of the playbook, not just the harness code. The notebook is part of what generalises.

## What lives here

```
notebook/
├── README.md                                ← this file: discipline
├── YYYY-MM-DD-<phase>.md                    ← per-day rolling notes during a run
└── findings/
    ├── README.md                            ← findings document conventions
    └── NNN-<short-slug>.md                  ← discrete post-run findings
```

Two kinds of entry:

- **Per-day rolling notes** (`YYYY-MM-DD-<phase>.md`): chronological, append-only within the day. The unit of writing is a session — a chunk of time during which Sam was actively observing the run or its output. New session within the same day appends to that day's file.
- **Findings documents** (`findings/NNN-<short-slug>.md`): discrete post-run analyses. One topic per document. Numbered sequentially. Each is self-contained — a reader can pick one up and understand the finding without reading others.

## Per-day rolling notes — entry shape

Each entry starts with a time marker and a context line.

```markdown
## 14:32 — dry run record 47

Latency on this one was 2.8s vs the ~1.6s p50 we've been seeing. Checked anomalies.jsonl — no anomaly fired (the auto threshold is 5s for `latency_spike`). Looked at the agent's reasoning trace — verbose, ~700 tokens. Possibly a model-side latency tail rather than infrastructure. Going to keep watching for similar; if a pattern emerges, lower the anomaly threshold for dry run.

Linked: decision_id 0fbd6972-cb0d (record 47), audit/decision_traces.jsonl line for run-id 2026-MM-DD-dry-001.

## 14:51 — same pattern at record 52

Another 2.6s. Both records are central-government direct awards. Possibility: agent reasoning is longer on those because the prompt has more context to chew on. Not a finding yet, more a watching brief. Bears on P6-C if it correlates with disagreement rate.

Linked: decision_id 04313618-dcfb, audit/decision_traces.jsonl line for run-id 2026-MM-DD-dry-001.
```

### Required components of a per-day entry

- **Time marker** in the entry's `##` header (UTC, 24-hour).
- **One-line context** in the header — what's happening, what's being observed.
- **Linked: line** at the bottom listing the IDs / SHAs / record indexes that the entry references. Even if a finding is observational ("seemed slower"), reference at least one record so the entry is anchored.

### Discipline rules for the per-day notes

1. **Append-only.** Adding to today's file is fine. Editing past entries is not. Corrections get a new entry that says "earlier I said X; correction: Y" rather than rewriting the original.
2. **No silent overwriting on subsequent days.** If a finding from yesterday's notes turns out to be wrong, today's note records the correction. Yesterday's note stays.
3. **Reference IDs over reproducing data.** Don't paste the agent's full reasoning into the notebook; reference the decision_id and the trace file. The notebook is interpretation, not data.
4. **Voice: founder-direct.** Same convention as the planning files. Short declarative sentences, paragraph breaks as beats, no hedging beyond what the evidence demands. The notebook isn't a private journal; it's an artefact that future-Sam (or a reader of the published repo) reads alongside the data.

## Findings documents

When an observation matures beyond a session note into a stable claim — something the writeup might cite — it gets a findings document. Discrete topic, self-contained, numbered.

See [`findings/README.md`](findings/README.md) for the findings document conventions in detail.

Typical lifecycle:

1. Observation in per-day notes ("noticing a pattern at records X, Y, Z").
2. Pattern repeats; per-day notes accumulate references.
3. Pattern firms up enough to claim. Findings document created: `findings/NNN-<short-slug>.md` with the claim, the evidence, the predictions it bears on, the caveats.
4. Per-day notes from then forward reference the findings document rather than re-arguing the claim.

## Linking discipline

The notebook is interpretive; the audit files are data. The link between them is the reference syntax.

| Notebook references | What it means |
|---|---|
| `decision_id <uuid>` | A specific MeshQu decision; appears in `audit/decision_traces.jsonl` and the receipt corpus. |
| `record <index>` | The N-th processed record in this run; cross-reference to `audit/decision_traces.jsonl` filtered by record_index. |
| `audit/decision_traces.jsonl line N` | A specific line in the audit JSONL; useful for citing precise telemetry. |
| `anomaly_id <uuid>` | A specific event in `audit/anomalies.jsonl`. |
| `screenshot <filename>` | A captured Grafana state; cite by filename relative to `observability/screenshots/`. |
| `P<N>` (P1, P2, ..., P6-C, P7) | A locked prediction in `predictions.md`. Findings that bear on a prediction always reference it by ID. |
| `OBS-<NNN>` | A task in the multi-tenant-observability harness (in the monorepo). Used when the notebook references upstream platform work. |
| `findings/<NNN>` | An existing findings document. Used in per-day notes after a finding has been written up. |

References are how the writeup chains "we observed X" → "here's the receipt where X happened" → "here's the dashboard panel that showed it" without trusting any single artefact in isolation.

## Voice references

The notebook voice should sound like Sam's own drafting anchors (see `writeup_outline.md`'s locked-voice reference at the bottom). Short declarative sentences. Specific names ("PROC-001-S53", not "the timing rule"). No abstract about-ness ("the agent struggled" — what struggled, how do you know).

Phrases that match the locked voice from the writeup:

- "semantically plausible but procedurally incorrect"
- "the agent mistakes publication existence for publication compliance"
- "reconstruction is not proof"

Use them when they fit, don't force them when they don't.

## What the notebook is NOT

- Not a journal of feelings. "I'm getting tired of this dry run" doesn't go here.
- Not a place to put data. Data goes in `audit/`, `corpus.tar`, screenshots. The notebook references and interprets.
- Not a place to draft writeup prose. Writeup drafts go in `writeup/`. The notebook produces findings that the writeup cites.
- Not a place to record decisions about the methodology. Those go in `planning/decision_log.md`. The notebook records observations about how the methodology behaved in execution.

## Cross-references

- [`procurement-decisions/results/README.md`](../README.md) — top-level discipline overview
- [`procurement-decisions/results/audit/README.md`](../audit/README.md) — machine-readable evidence the notebook references
- [`procurement-decisions/planning/predictions.md`](../../planning/predictions.md) — locked predictions the notebook cites by ID
- [`procurement-decisions/writeup/`](../../writeup/) — the writeup that draws from this notebook
