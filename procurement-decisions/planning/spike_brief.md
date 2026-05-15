# Feasibility Spike: UK Contracts Finder OCDS Substrate

> **The agent-firing brief.** Hand this to a fresh coding agent. The output
> is [`feasibility_spike_report.md`](feasibility_spike_report.md), filled in
> by the agent. The final GO / NO-GO call is Sam's, not the agent's.

## Status

**Phase 0 — runs BEFORE predictions lock, BEFORE Phase 1 of the broader experiment.**

This is exploratory work, not part of the experiment itself. Its purpose is to confirm the substrate can support the design before pre-registration commits us to it. Findings are documented but not published as experimental results.

## Why this exists

The planning harness commits to a specific experiment design: 300 stratified procurement records from UK Contracts Finder OCDS, six policy rules (one faithful PA23 s.44 implementation, five composites), agent-vs-policy disagreement analysis with PA23-specific drift predictions (P7).

Every part of that design rests on substrate assumptions we have not yet verified. If those assumptions are wrong, we want to find out now and reshape the design — not after predictions are locked and three weeks of build work is done.

## What this spike is NOT

- Not part of the experiment corpus. The ~200 records you pull are sacrificial — they cannot be used in the eventual 300-record sample because they would have been seen before pre-registration.
- Not pre-registered. We are deliberately looking at data to assess feasibility.
- Not the start of execution. No agent runs happen in this spike. No MeshQu receipts are produced. No policy is authored or ratified.
- Not published. The report lives in the harness as `feasibility_spike_report.md` for internal reference and methodology transparency in the eventual writeup.

## What this spike IS

A half-day to one-day exploration of the OCDS API and the data it actually returns, producing a short report that answers five specific feasibility questions and surfaces any design decisions Sam needs to make before Phase 1 starts.

## The five questions to answer

### Q1: Can PA23-governed procurements be reliably identified from OCDS data alone?

The Procurement Act 2023 came into force on 24 February 2025. Some procurements awarded after that date continued under PCR 2015 transition arrangements. PROC-001-S44 only applies to PA23-governed procurements.

**What to check:**

- Does the OCDS record have an explicit field indicating which regime governs it (e.g. a `governed_by`, `legislation`, or `regulation` field)?
- If not, can it be inferred reliably from notice type codes, procedure type codes, or other structured fields?
- If only inferable, what's the false-positive / false-negative risk of the inference?
- Sample-test against 30 records from the post-June-2025 window: how many can be confidently classified as PA23 vs PCR 2015 vs ambiguous?

**Outcome that's a problem:** if more than ~10% of post-June-2025 records are ambiguous regarding which regime governs them, the PROC-001-S44 rule becomes unreliable.

### Q2: Are transparency notices structured-data or PDF-only?

The s.44 obligation requires a published transparency notice with named Schedule 5 grounds and justification text. For the rule to be machine-evaluable, that notice content has to be available as structured data — not just as a linked PDF.

**What to check:**

- For direct-award contracts in the sample, is there a linked transparency notice in the OCDS record?
- If linked, is the linkage structured (a notice ID, a URL with parsable metadata) or unstructured (a free-text reference)?
- Is the transparency notice's content available via the same API? Can you fetch the Schedule 5 ground and justification text without PDF parsing?
- Sample-test: find five direct awards in the post-June-2025 window. For each, can you programmatically retrieve the Schedule 5 ground cited and the justification text?

**Outcome that's a problem:** if transparency notice content is only in PDFs, the s.44 rule cannot be cleanly machine-evaluated. Options if this happens: scope down to "transparency notice exists" as the only s.44 check (loses the Schedule 5 nuance); add PDF/LLM extraction to the harness (adds methodology complexity); pivot the faithful rule to something else entirely.

### Q3: Are there enough direct-award records in the PA23 subset?

The PROC-001-S44 findings depend on having a reasonable number of direct-award cases to evaluate. If the post-June-2025 PA23 subset has only 10 direct awards, the rule fires too rarely to support P6 and P7 statistically.

**What to check:**

- Of all contract awards in the period 2025-06-01 to 2025-12-31, what fraction are direct awards (under PA23 sections 41, 42, or 43)?
- Extrapolate to the eventual 300-record stratified sample — how many direct-award cases would be in it?
- If insufficient, can the window be widened (e.g. to 2025-03-01 onwards, accepting a less clean PA23-vs-PCR transition) without compromising the design?

**Outcome that's a problem:** fewer than ~30 direct awards available in the working window. The s.44 findings become anecdotal rather than statistical, and P7 becomes underpowered.

### Q4: Field-population across the stratified sampling grid

The substrate.md grid stratifies by award method (five categories) and value band (four bands) — 20 cells. Some cells will be naturally sparse (e.g. very-large single-source contracts are rare). But the grid is fictional if too many cells are empty.

**What to check:**

- Pull 200 records spread across the post-June-2025 window (this can include some pre-June if needed for sparse cells — the spike sample isn't pre-registered).
- Tabulate the actual distribution across the 20 cells.
- Identify cells with fewer than 5 records available in the period. These are cells the experiment will not be able to fill cleanly.
- Recommend grid adjustments: collapse sparse cells (e.g. combine "framework" and "other" if both are thin), or accept imbalance with a methodology note.

**Outcome that's a problem:** if more than 6 of the 20 cells are unfillable, the stratification claim in the methodology weakens significantly. The experiment may need a simpler stratification (e.g. value band × {direct_award, competitive} as a 2×4 grid).

### Q5: Is the description text rich enough for agent reasoning?

The agent reads each filing and proposes a verdict. If the OCDS-exposed text content is mostly metadata (dates, values, supplier IDs, CPV codes) without substantive description text, the agent has nothing to reason from. The drift signal collapses.

**What to check:**

- For 20 records across the value bands, inspect the description / title / supplementary fields the agent will have access to.
- Note typical length and substantive content. Is there a description paragraph? A scope-of-work summary? A justification text for direct awards?
- Compare against what the Contracts Finder web UI displays — is there content visible on the web page that isn't in the OCDS API response?

**Outcome that's a problem:** if the OCDS API response is mostly structured metadata with thin description text, the agent's reasoning task becomes trivial (just classify a record by its metadata fields) rather than substantive (reason about whether a procurement appears compliant). The experiment loses interest.

## How to do the work

### Setup

- No auth required for public read access. The Contracts Finder OCDS API endpoint is `https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json` (v2) or the OCDS search endpoint per the documentation.
- Use the v2 API. The OCDS-formatted output is at the `/Notices/1/GET-Published-Notice-OCDS-Search` path per the Open Contracting Partnership documentation.
- Reference implementation for pagination: `github.com/uk-third-sector-database/contracts_finder`. Don't copy the code; use it to confirm the pagination pattern works.

### Data pull

- Pull approximately 200 awarded contract notices from the period 2025-06-01 to 2025-12-31.
- Stratified-light sample: try to capture across value bands and award methods so the field-population analysis has variety to inspect.
- Save raw OCDS JSON to a working directory (`spike_data/` in the harness — gitignored, this is sacrificial data).

### Analysis

- For each of Q1, Q2, Q3, Q4, Q5, run the specific checks described above.
- Pay particular attention to direct-award records — these are the load-bearing subset for PROC-001-S44.
- For Q2 specifically, pick five direct awards and attempt the full transparency-notice retrieval flow end-to-end. This is the most important single check in the spike.

### Output: feasibility_spike_report.md

A markdown report in `.harness/agentic-procurement-experiment/feasibility_spike_report.md` with this structure:

```
# Feasibility Spike Report

**Date**: [date of spike completion]
**Records inspected**: ~200 OCDS notices, 2025-06-01 to 2025-12-31
**Status**: [GO | GO WITH ADJUSTMENTS | NO-GO]

## Q1: PA23 identification
[Findings + verdict + recommendation]

## Q2: Transparency notice structured-data availability
[Findings + verdict + recommendation]

## Q3: Direct-award volume
[Findings + verdict + recommendation]

## Q4: Sampling grid field-population
[Findings + verdict + recommendation, including a table of actual cell-population from the spike sample]

## Q5: Description text richness
[Findings + verdict + recommendation, with 2-3 example excerpts of typical description content]

## Design adjustments recommended

[Concrete changes to experiment_design.md, predictions.md, substrate.md based on findings. Each adjustment named explicitly with the file and section it affects.]

## Open decisions for Sam

[Bulleted list of decisions the spike couldn't resolve. Each one needs to be answered before Phase 1 (predictions lock) starts.]

## Confidence assessment

[Honest assessment of whether the design as planned is feasible, and where the residual risks are.]
```

A skeleton matching this template lives at [`feasibility_spike_report.md`](feasibility_spike_report.md) — fill it in.

## What NOT to do in this spike

- Do not run any LLM agents against any of this data. The spike inspects data shape, not agent behaviour.
- Do not author the actual policy in MeshQu. The composite rules and PROC-001-S44 stay paper-only until Phase 3.
- Do not commit any specific notice IDs to the harness as "the sample." The 200 records pulled here are inspection-only; the eventual 300 are sampled fresh after predictions lock.
- Do not make recommendations beyond the five questions. The spike is scoped; broader design opinions can be surfaced for Sam but should be flagged as out-of-scope rather than acted on.
- Do not skip questions because they look easy. Each question has a specific failure mode the spike is designed to catch. Confirm each one explicitly, even if the answer is obvious.

## Time budget

- Background Claude work: 4–6 hours.
- Sam's review time: 30 minutes when the report lands.
- Calendar: 2–3 days total, including the review and any follow-up questions.

## What happens after the spike

1. Sam reads the report and responds to open decisions.
2. The design adjustments (if any) get applied to experiment_design.md, predictions.md, substrate.md via a short revision pass.
3. Predictions get locked (Phase 1).
4. The actual experiment proceeds.

If the spike returns NO-GO, Sam and Claude reshape the design before any further commitment.

## Voice note

This is an internal feasibility report, not a published artefact. Voice should be matter-of-fact and engineering-direct. Findings should be specific (with numbers and examples), recommendations should be concrete (named files and sections), and uncertainty should be named honestly rather than hedged.
