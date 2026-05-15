# Phase 0.5 Spike — C1 Date-Semantics

> Narrow follow-up spike. Fires only if Sam picks Candidate 1
> ([candidate_faithful_rules.md](candidate_faithful_rules.md)) as the
> faithful-rule pivot. Resolves the single question that decides whether
> C1 is viable.

## Status

**Phase 0.5 — between candidate selection and predictions lock.**

Phase 0 returned three failures against the brief's thresholds and killed `PROC-001-S44`. The candidate-faithful-rules analysis surfaced C1 (PA23 s.53 30-day Contract Details Notice timeliness) as the strongest replacement candidate **conditional on a single data-semantics question being resolved**. That question is the entire scope of this spike.

## The single question

**Does `awards[0].datePublished` in the Contracts Finder OCDS feed reflect the original publication time of the contract details notice, or does it reflect a downstream OCDS-pipeline timestamp (snapshot refresh, bulk re-index, etc.)?**

If original publication time: C1 is viable. Proceed to harness revision and predictions lock.
If pipeline timestamp: C1 is dead. Return to Sam for path 2 (drop faithful framing) vs path 3 (reopen substrate) decision.

## Why the question matters

Phase 0 measured publication delay against the s.53 30-day cap and found 246/255 records breach by a wide margin (p50 = 127 days). On its face, decisive — every direct-award procurement looks non-compliant.

But the spike also observed that `awards[0].datePublished` and top-level `date` are clustered on the spike-pull date for 244/255 records, while `awards[0].date` is spread realistically across 2025-06 to 2025-12. The most likely explanation is that `datePublished` is not the field that carries original publication time — it carries some downstream OCDS pipeline event. If that's right, the 30-day "breach" we measured is an artefact of when records were pulled, not a real compliance signal.

This is structurally the s.44 failure mode: a rule built on a substrate field that doesn't carry what the rule needs. We caught it on s.44 because there were zero relevant fields; on C1 we'd miss it if we assumed `datePublished` means what its name suggests.

## What this spike is NOT

- Not the experiment. No agent runs, no policy authoring, no MeshQu receipts.
- Not pre-registered. We are looking at substrate behaviour, not running the experiment.
- Not exhaustive. Three targeted tests, one decisive answer.
- Not authorised to soften the constraint. If `datePublished` is pipeline time, the verdict is "C1 dead" — do not propose creative workarounds without surfacing to Sam first.

## The three tests

### Test 1 — Same-record re-pull comparison (the decisive test)

Pick **20 OCIDs** from `spike_data/releases.jsonl` where `awards[0].datePublished` clusters at the original spike pull timestamp. Re-fetch each notice from the same OCDS endpoint **today**. For each:

- Record the original `awards[0].datePublished` (from the saved JSONL).
- Record the new `awards[0].datePublished` (from today's pull).
- Record `awards[0].date` for both (should be unchanged — this is the contract award date).
- Record top-level release `date` for both.

**Interpretation:**

- If new `datePublished` matches old `datePublished` (or original-publication anchored): **`datePublished` is publication time. C1 viable on this test.**
- If new `datePublished` has shifted toward today's pull date: **`datePublished` is pipeline time. C1 dead on this test.**
- Mixed results: report per-record; flag for Sam.

This is the load-bearing test. If it returns cleanly, the other two tests are confirmation; if it returns ambiguously, the other two are the tiebreakers.

### Test 2 — UI cross-check

For **5 OCIDs from Test 1**, fetch the Contracts Finder HTML page (e.g. `https://www.contractsfinder.service.gov.uk/Notice/<id>`). The web UI typically displays a "Published" date prominently. For each:

- Note the date displayed in the web UI.
- Compare against the OCDS `awards[0].datePublished` and top-level `date`.

**Interpretation:**

- UI-displayed "Published" matches OCDS `datePublished`: consistent with H1 (publication time).
- UI-displayed date is earlier than OCDS `datePublished` (typically by months): consistent with H2 (pipeline time). The UI is showing original publication; OCDS is showing something else.
- UI doesn't display a "Published" date at all: report and move on; not decisive.

### Test 3 — OCDS spec + schema sweep

Search the OCDS schema and the Contracts Finder OCDS profile documentation for the canonical definition of `datePublished` and any sibling fields that might carry original publication time. Look specifically for:

- The official semantics of `awards[].datePublished` in OCDS 1.1.
- Any Contracts Finder extension that adds a `publishedDate`, `dateOriginalPublished`, or similar field at any level.
- Any structural pattern (notice metadata block, `links` block, `releases[].id` versioning) that anchors original publication.

Cite specific URLs. If a properly-anchored field exists that the Phase 0 spike missed, name it explicitly — C1 may be salvageable on a different field even if `datePublished` is dead.

## What to do with the results

Produce a report at `.harness/agentic-procurement-experiment/feasibility_spike_c1_report.md` with this structure:

```
# C1 Date-Semantics Spike Report

**Date**: [date]
**Records re-pulled**: 20 OCIDs (Test 1) + 5 OCIDs (Test 2) + schema review (Test 3)
**Status**: C1 VIABLE | C1 DEAD | AMBIGUOUS — Sam's call.

## Test 1 — Same-record re-pull
[Per-record table; one line per OCID with old datePublished, new datePublished, awards[0].date, delta_days, interpretation.]

## Test 2 — UI cross-check
[Per-record table; OCID, UI-displayed Published date, OCDS datePublished, difference, interpretation.]

## Test 3 — OCDS spec sweep
[Citations + findings. Name any salvage-fields the Phase 0 spike missed.]

## Verdict (as fact, not judgement)
[State what `datePublished` actually carries. Do NOT issue a GO / NO-GO. State what the test results imply for C1's evaluability.]

## If C1 is dead — salvage paths
[Brief enumeration of paths if `datePublished` proves to be pipeline time:
 - Is there another field (from Test 3) that anchors original publication cleanly?
 - Can the rule be reshaped around a different s.53 obligation surface?
 - Is the rule definitively dead and Sam needs to decide path 2 vs path 3?]
```

## Data discipline (same as Phase 0)

- Save raw JSON to `.harness/agentic-procurement-experiment/spike_data/` — gitignored, sacrificial.
- Log every re-pulled OCID into the report. These records have now been seen twice; on the conservative read, they should also be excluded from the eventual 300-record corpus.
- No LLM agent runs.
- No MeshQu policy authoring or receipt production.
- No Find a Tender Service. Substrate stays Contracts Finder.

## Verdict-as-fact discipline (same as Phase 0)

The report's "Verdict" section states **what `datePublished` actually carries**, not whether C1 is viable. Sam makes the viability call. Phrase findings as facts:

- *"`datePublished` shifted on re-pull for 18/20 records (median shift +89 days), tracking the re-pull date — consistent with a pipeline timestamp, not publication time."*
- NOT: *"C1 is dead."*

## Constraints

**Must:**
- Re-pull from the exact same OCDS endpoint the Phase 0 spike used.
- Compare against the saved `spike_data/releases.jsonl` from the Phase 0 commit (`bf86b097`).
- Report per-record results; no aggregating away outliers.

**Must not:**
- Soften the test if results are unfavourable. If `datePublished` is pipeline time, say so plainly.
- Propose adopting Find a Tender Service as a salvage path. That's a Sam decision, not a spike decision.
- Run LLM agents against the records.
- Author or ratify any policy.

## Time budget

- Background Claude work: 1.5–3 hours. This is narrower than Phase 0.
- Sam's review time: 15–30 minutes.
- Calendar: 1 day if fired immediately.

## GO / NO-GO criteria for C1

These are Sam's, not the spike's. The spike reports facts; Sam decides:

- **C1 VIABLE**: `datePublished` is original publication time. The 246/255 breach observed in Phase 0 is real. Proceed to harness revision (replace `PROC-001-S44` with `PROC-001-S53`), predictions lock against revised design.
- **C1 DEAD, salvage possible**: `datePublished` is pipeline time, but Test 3 found a properly-anchored field the Phase 0 spike missed. Sam decides whether to reshape C1 around that field or proceed to path 2/3.
- **C1 DEAD, no salvage**: `datePublished` is pipeline time and no replacement field exists. Sam decides path 2 (drop faithful framing) vs path 3 (reopen substrate).

## What happens after the report lands

1. Sam reads. ≤30 minutes.
2. If VIABLE: harness revision pass applies the C1 swap across substrate.md, experiment_design.md, predictions.md, project_context.md, writeup_outline.md, decision_log.md. Then predictions lock.
3. If DEAD: decision conversation between Sam and Claude on path 2 vs path 3. No harness edits until that decision lands.
