# Findings — Discrete Post-Run Analyses

> One topic per document. Numbered sequentially.
> Self-contained — readable without reference to other findings.

## What lives here

Discrete findings documents that emerge from the per-day notebook entries.
Each is a stable claim grounded in run data.

Filename pattern: `NNN-<short-slug>.md`. Examples:

- `001-direct-award-disagreement-cluster.md`
- `002-pcr-citation-taxonomy.md`
- `003-rekor-anchoring-latency-tail.md`

Numbers are assigned sequentially in the order findings firm up — they
don't denote ranking or importance.

## When to create a findings document

A per-day notebook entry observes; a findings document claims. The promotion happens when:

1. The observation has repeated enough that it's stable (typically 3+ references across per-day notes).
2. The claim is specific enough to test (i.e. a future analyst could decide whether to agree or disagree).
3. The writeup might cite it — either in section 5b (worked example), 5b's prediction-by-prediction results, section 6 (reasoning is data), or section 7 (limitations).

Findings that don't meet all three stay in per-day notes. The bar exists to keep findings/ as the load-bearing analysis layer; otherwise it accumulates noise.

## Findings document structure

Every findings document carries the same four sections.

```markdown
# Finding NNN — <one-line claim>

**Created:** YYYY-MM-DD
**Status:** draft | stable | superseded by NNN-...
**Bears on:** P1 | P2 | ... | P6-C | P7 | (or "methodology" if not a prediction-specific finding)

## The claim

One paragraph. Direct, specific, falsifiable. What's observed; what's claimed; what scope it applies within.

## Evidence

The data that supports the claim. References by ID (decision_id, record index, anomaly_id, screenshot filename) — not pasted data. A reader follows the references to verify.

## Caveats

What this finding does NOT say. What conditions might invalidate it. What sample-size or scope limitations apply. Honest framing rather than hedging — if a caveat is real, name it.

## Cross-references

Predictions the finding bears on. Per-day notebook entries the finding emerged from. Other findings it relates to.
```

## Discipline rules

1. **One topic per document.** A finding about direct-award disagreement is one document; a finding about Rekor latency tails is another. Don't bundle.
2. **Self-contained.** A reader picking up `005-...` should not need to read `001..004` to understand it. Cross-reference where relevant; don't assume prior reading.
3. **Status field is current.** A finding starts at `draft`, moves to `stable` when the evidence is firm, becomes `superseded by NNN-...` if a later finding refutes or refines it. Superseded findings stay in this directory (don't delete) with the status pointer.
4. **Bears-on field is explicit.** Findings that touch a prediction name the prediction ID. Findings that are methodology-level (not prediction-specific) say so explicitly rather than leaving the field blank.
5. **No new findings during pre-registration cool-down.** This directory is empty at pre-registration lock; findings accumulate during and after the run.

## How findings inform the writeup

| Writeup section | Finding type that feeds it |
|---|---|
| §5a (volume + verdict distribution) | Methodology-level findings about run shape, latency distributions, anomaly counts |
| §5b (worked example) | The findings that surface the s.44/s.53 conflation pattern; P6-C and P7 evidence specifically |
| §5b (prediction-by-prediction) | Findings that bear on each prediction (P1, P3, P4, P6-C, P7) |
| §6 (reasoning is data) | Findings that illustrate the broader thesis — usually a specific worked case grounded in a finding document |
| §7 (limitations) | Methodology-level findings about substrate-imposed constraints, sample-power limits, anomaly categories that didn't fit |

A finding cited by the writeup carries its document's full discipline — claim, evidence, caveats. The writeup quotes; the finding is the citable record.

## Voice

Same as the per-day notebook — founder-direct, specific, no hedging beyond what the evidence demands. The four-section structure imposes form without forcing voice.

Phrases from the writeup's locked voice reference fit naturally:

- "semantically plausible but procedurally incorrect" — for findings about agent failure modes
- "the agent mistakes X for Y" — for s.44/s.53-shaped misclassifications
- "reconstruction is not proof" — for findings that illustrate the MeshQu thesis

Use when they fit. Don't force.

## Cross-references

- [`procurement-decisions/results/notebook/README.md`](../README.md) — notebook discipline
- [`procurement-decisions/planning/predictions.md`](../../../planning/predictions.md) — locked predictions findings cite
- [`procurement-decisions/writeup/`](../../../writeup/) — where findings get quoted
