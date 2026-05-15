# C1 Date-Semantics Spike Report

**Date**: 2026-05-14
**Records re-pulled**: 19 unique OCIDs re-fetched (Test 1; 20 selected, one was a duplicate from a record with two awards) + 5 UI HTML pages fetched (Test 2) + OCDS spec + Contracts Finder extension sweep (Test 3).
**Status**: C1 VIABLE on the date-semantics question — Sam's call.

> **Resolution (2026-05-15, added pre-lock).** The award-date-as-signature-date proxy framing was committed in revision brief 11; see `procurement-decisions/planning/experiment_design.md` PROC-001-S53 row and the substrate-honesty subsection's second-proxy paragraph for the documented decision. This spike report is preserved as a historical record of the date-semantics finding; the original status line above is what the spike concluded at the time it ran.

> The Phase 0 confounder hypothesis was that `awards[0].datePublished`
> tracks the pull moment (a pipeline timestamp). Three tests against
> the live Contracts Finder OCDS feed today disconfirm that hypothesis.
> The field is stable per-OCID across re-pulls (Test 1), matches the
> "Published date" the public UI displays for the same notice (Test 2),
> and is defined by the Crown Commercial Service `ocds_awards_datePublished_extension`
> as "the date that the award was published" (Test 3). The Phase 0
> clustering observation has a simpler explanation: the 244/255 records
> were *genuinely published* in a tight late-February 2026 window,
> 2–7 months after the contract was actually awarded. That is what the
> s.53 30-day rule is designed to surface.

## Test 1 — Same-record re-pull

Method: 20 OCIDs selected deterministically from `spike_data/releases.jsonl`
(filtered to records where `awards[0].datePublished` falls in the Feb 2026
cluster, sorted by OCID, first 20 taken — one OCID had two awards in the
saved data so 19 unique OCIDs). Re-fetched today via the OCDS Search endpoint
with `publishedFrom=2026-02-17&publishedTo=2026-02-28&limit=100`, walking
pages until each target OCID was located. All 19/19 found in the historical
Feb-window query.

Important methodology note. The Contracts Finder OCDS Search endpoint
**silently ignores `?ocid=<OCID>`** (it strips the parameter, applies
`publishedTo=now`, returns the latest 100 releases site-wide). Per-OCID
re-fetch therefore requires walking pages of the historical
publication-window query. The `links.next` cursor works correctly. Raw
re-pull saved at `spike_data/c1_feb_page_*.json`; comparison table at
`spike_data/c1_test1_comparison.json`.

| # | OCID (suffix) | award.date | OLD datePublished | NEW datePublished | dP equal | award.date equal | top date equal |
|---|---|---|---|---|---|---|---|
| 1 | 0084538d…feaab | 2025-09-26 | 2026-02-27T14:46:05Z | 2026-02-27T14:46:05Z | YES | YES | YES |
| 2 | 01041bd3…c843f | 2025-10-20 | 2026-02-24T14:12:19Z | 2026-02-24T14:12:19Z | YES | YES | YES |
| 3 | 012110ef…fa1d7 | 2025-11-25 | 2026-02-24T11:41:06Z | 2026-02-24T11:41:06Z | YES | YES | YES |
| 4 | 04313618…ef53a6 | 2025-10-14 | 2026-02-27T14:42:10Z | 2026-02-27T14:42:10Z | YES | YES | YES |
| 5 | 0446f2f1…39c4c6 | 2025-12-29 | 2026-02-20T11:28:15Z | 2026-02-20T11:28:15Z | YES | YES | YES |
| 6 | 04cbe5d2…3777f | 2025-10-30 | 2026-02-26T17:45:07Z | 2026-02-26T17:45:07Z | YES | YES | YES |
| 7 | 060efa4f…400a8 | 2025-12-19 | 2026-02-23T15:47:51Z | 2026-02-23T15:47:51Z | YES | YES | YES |
| 8 | 077becc5…4d98a | 2025-12-23 | 2026-02-23T16:55:22Z | 2026-02-23T16:55:22Z | YES | YES | YES |
| 9 | 07eec60e…f74ec | 2025-09-10 | 2026-02-23T11:31:21Z | 2026-02-23T11:31:21Z | YES | YES | YES |
| 10 | 0829ae1b…e45f0d | 2025-09-01 | 2026-02-23T15:23:07Z | 2026-02-23T15:23:07Z | YES | YES | YES |
| 11 | 08f1888f…1854b3 | 2025-10-23 | 2026-02-25T17:03:39Z | 2026-02-25T17:03:39Z | YES | YES | YES |
| 12 | 09a8730a…58594 | 2025-08-22 | 2026-02-19T15:47:33Z | 2026-02-19T15:47:33Z | YES | YES | YES |
| 13 | 0bd1dae4…6eb5f1 | 2025-08-22 | 2026-02-19T14:28:22Z | 2026-02-19T14:28:22Z | YES | YES | YES |
| 14 | 0bff344d…2c568 | 2025-07-24 | 2026-02-20T10:31:45Z | 2026-02-20T10:31:45Z | YES | YES | YES |
| 15 | 0d26a82b…9ffb709d | 2025-12-29 | 2026-02-26T11:46:08Z | 2026-02-26T11:46:08Z | YES | YES | YES |
| 16 | 0da49abd…f9c16e | 2025-10-03 | 2026-02-19T16:37:23Z | 2026-02-19T16:37:23Z | YES | YES | YES |
| 17 | 0edca866…981be3 | 2025-08-04 | 2026-02-26T16:43:15Z | 2026-02-26T16:43:15Z | YES | YES | YES |
| 18 | 0fbd6972…fbc587 | 2025-12-15 | 2026-02-20T12:48:38Z | 2026-02-20T12:48:38Z | YES | YES | YES |
| 19 | 10139854…158b6b | 2025-08-22 | 2026-02-19T16:22:08Z | 2026-02-19T16:22:08Z | YES | YES | YES |

**Result: 19/19 byte-for-byte identical** across `awards[0].datePublished`,
`awards[0].date`, and top-level `date`. The clustering observed in Phase 0
is preserved across pulls — these notices were genuinely published in late
February 2026, 53–211 days after the underlying contracts were awarded
(median 136 days post-award, mean 132). Not one of the 19 carries a
publication-to-award delta inside 30 days; the smallest delta in this
hand-selected subset is 53 days (Notice 5, contract awarded 2025-12-29,
notice published 2026-02-20).

Side-evidence corroborating stability: when the same endpoint is queried
without a publication-window filter, the latest 100 releases all carry
`datePublished` very close to the request moment (today, 2026-05-14). But
those are different OCIDs — newly-published notices, not re-stamps of the
saved 19. The endpoint's behaviour is consistent with "each notice
publication emits one OCDS release stamped with its own publication moment,
and subsequent reads of that release return the same stamp."

## Test 2 — UI cross-check

For 5 of the Test-1 OCIDs, fetched the Contracts Finder award-notice HTML
page (via `awards[0].documents[].url` where `documentType=awardNotice`,
which resolves to `https://www.contractsfinder.service.gov.uk/Notice/<release_id>`).
Pages were retrieved with a browser User-Agent (no 403s). HTML and stripped
text are at `spike_data/c1_ui_{0..4}.{html,txt}`; structured extracts at
`spike_data/c1_test2_results.json`. Each page has a "Published date:" label
in the header band and the same string in the metadata footer.

| # | OCID (suffix) | OCDS `awards[0].datePublished` | UI "Published date" | Match |
|---|---|---|---|---|
| 1 | 0084538d…feaab | 2026-02-27 | 27 February 2026 | YES |
| 2 | 01041bd3…c843f | 2026-02-24 | 24 February 2026 | YES |
| 3 | 012110ef…fa1d7 | 2026-02-24 | 24 February 2026 | YES |
| 4 | 04313618…ef53a6 | 2026-02-27 | 27 February 2026 | YES |
| 5 | 0446f2f1…39c4c6 | 2026-02-20 | 20 February 2026 | YES |

**Result: 5/5 perfect match.** The UI uses the exact label "Published date"
(consistent with H1 in the brief). The OCDS field and the UI display are the
same datum. The UI does not separately surface an "original publication"
date that would precede the displayed date.

## Test 3 — OCDS spec + Contracts Finder extension sweep

### Core OCDS 1.1 schema

`awards[].datePublished` is **not in core OCDS 1.1.** The core Award block
defines `id`, `title`, `description`, `status`, `date`, `value`,
`suppliers`, `items`, `contractPeriod`, `documents`, `amendments`,
`amendment`. The top-level release `date` in core OCDS is defined as
"The date on which the information contained in the release was first
recorded in, or published by, any system" — a release-emission timestamp,
not a publication timestamp. The `datePublished` term appears in core only
on the **document** block: "The date on which the document was first
published. This is particularly important for legally important documents
such as notices of a tender."

Source: <https://standard.open-contracting.org/1.1/en/schema/reference/>

### Crown Commercial Service `ocds_awards_datePublished_extension`

Listed in the `extensions` array of every Contracts Finder OCDS response.
Field: `awards[].datePublished`. Authoritative schema:

```json
{
  "title": "Date published",
  "description": "The date that the award was published.",
  "type": ["string", "null"],
  "format": "date-time"
}
```

Extension purpose: "enables the inclusion of the publication date for
awards objects in subsequent releases of contracting data" — i.e. the
date the award was first published, preserved across release versions.

Sources:
- <https://github.com/Crown-Commercial-Service/ocds_awards_datePublished_extension/blob/main/release-schema.json>
- <https://github.com/Crown-Commercial-Service/ocds_awards_datePublished_extension/blob/main/extension.json>

### Other date-bearing extensions present

- `ocds_tenderDatePublished_extension` (portaledcahn) — adds
  `tender.datePublished`, "The date when the tender was published." Field
  population in saved 255-record corpus: **3/255 (1.2%)**. Not viable as a
  primary publication-time field for award-stage analysis.
- No "originalDatePublished" or "firstPublicationDate" sibling found in
  the extension list. There is no superseding extension that would carry
  an earlier publication moment than `awards[0].datePublished`.

### Sibling fields in saved corpus

| Field | Population |
|---|---|
| top-level `date` | 255/255 |
| `tender.datePublished` | 3/255 |
| `awards[0].date` (award-decision date) | 255/255 |
| `awards[0].datePublished` (notice-publication date) | 255/255 |
| `awards[0].contractPeriod.startDate` | 255/255 |

**Conclusion of Test 3.** No salvage field was needed. The field that the
Phase 0 analysis suspected of being a pipeline stamp is in fact governed by
a CCS-published OCDS extension that defines it as the award-publication
date, in plain words. The Phase 0 spike did not miss a better field.

## Verdict (as fact, not judgement)

**`awards[0].datePublished` is stable per OCID across re-pulls (19/19
byte-identical), matches the "Published date" the Contracts Finder UI
shows the public for the same notices (5/5 exact match), and is defined
by the CCS OCDS extension as "The date that the award was published."**

The field carries the original publication moment of the Contract Award
Notice as it landed on the Contracts Finder transparency surface. It is
not a snapshot-render timestamp or pipeline emit stamp.

The Phase 0 observation — that 244/255 saved records have `datePublished`
clustered around the spike pull date — has a simpler explanation than the
"pipeline timestamp" hypothesis: the Phase 0 pull (2026-02-27) was the day
on which a backlog of late-published contract-details notices were
genuinely published. Notices that were *already* published days or weeks
before the pull retained their earlier timestamps (11 of the 255 records
in the saved corpus have `datePublished` before 2026-02-17). The single
day with the heaviest publication volume in the corpus is 2026-02-19 (59
notices), followed by 2026-02-23 (32) and 2026-02-20 (31). That is the
shape of UK buyer publication behaviour, not the shape of an OCDS pipeline.

For C1 evaluability: the publication-delay primitive the rule needs IS
in a single OCDS pull, on the field its name suggests, with the meaning a
reader would expect.

## If C1 is dead — salvage paths

Not applicable on the date-semantics question. C1's stated load-bearing
risk (per `candidate_faithful_rules.md` §1.7) was the date-semantics
confounder, and the three tests above resolve it in C1's favour.

Other risks identified in the candidate analysis still stand and are
out of scope for this spike:

- **Light-touch derivation** (§4 of C1 analysis) — requires Schedule 1
  SI 2024/692 CPV mapping. Tractable; adds methodology surface.
- **Regime ambiguity** (§7) — 96% of records carry no PA23/PCR signal in
  OCDS; rule's `governed_by` predicate must rely on a procedure-end-date
  proxy. Phase 0 finding, not a date-semantics finding.

## OCIDs seen twice (exclude from eventual 300-record corpus)

These 19 OCIDs have now been re-pulled and should be conservatively
excluded from the Phase 1 corpus, in addition to the 38 already listed
in Appendix A of `feasibility_spike_report.md`. The full 255-OCID list
in `spike_data/releases.jsonl` was not individually re-fetched in this
spike — only the 19 below were.

```
ocds-b5fd17-0084538d-de8f-4344-97fd-c5cf7b7feaab
ocds-b5fd17-01041bd3-fc28-4011-ad59-da8d309c843f
ocds-b5fd17-012110ef-fdf4-4a96-b2c1-98e2555fa1d7
ocds-b5fd17-04313618-dcfb-4b20-bbf5-bfb566ef53a6
ocds-b5fd17-0446f2f1-7118-4b7c-b008-fe15ce39c4c6
ocds-b5fd17-04cbe5d2-26a7-4387-94a3-e056f833777f
ocds-b5fd17-060efa4f-c8b5-43db-ab1d-6f55ff8400a8
ocds-b5fd17-077becc5-9d7e-4b5b-8c87-33bbd2f4d98a
ocds-b5fd17-07eec60e-bf4b-4a37-a28d-136211af74ec
ocds-b5fd17-0829ae1b-09e2-4258-a97d-29028be45f0d
ocds-b5fd17-08f1888f-4694-4876-ab33-a9369a1854b3
ocds-b5fd17-09a8730a-5bae-4703-9441-c3e73c058594
ocds-b5fd17-0bd1dae4-5597-4e0b-af43-d1f05f6eb5f1
ocds-b5fd17-0bff344d-7291-49dc-a1b1-788adc72d568
ocds-b5fd17-0d26a82b-b705-42b2-b257-6aa99ffb709d
ocds-b5fd17-0da49abd-1499-45a8-bc46-1d11fbf9c16e
ocds-b5fd17-0edca866-ed79-413b-8727-2757d3981be3
ocds-b5fd17-0fbd6972-cb0d-4d85-9ea9-d4c19dfbc587
ocds-b5fd17-10139854-910c-491b-904e-eb4b01158b6b
```

Overlap with Phase 0 Appendix A: 15 of the 19 above were already
individually inspected in Phase 0 (Q1/Q2/Q5 sample). The 4 net-new OCIDs
this spike adds to the exclusion list are:

```
ocds-b5fd17-09a8730a-5bae-4703-9441-c3e73c058594
ocds-b5fd17-0bd1dae4-5597-4e0b-af43-d1f05f6eb5f1
ocds-b5fd17-0bff344d-7291-49dc-a1b1-788adc72d568
ocds-b5fd17-10139854-910c-491b-904e-eb4b01158b6b
```

## Reproducibility

- Selection script: `spike_data/c1_test1_selected.json` (generated from
  `releases.jsonl`, first 20 by sorted OCID with `datePublished` in
  `2026-02-*`).
- Re-pull script: `spike_data/c1_repull.py`. Walks the OCDS Search endpoint
  with `publishedFrom=2026-02-17&publishedTo=2026-02-28&limit=100` and
  follows `links.next`. Took 10 pages (≈3 seconds with 0.3s polite sleep).
- UI fetch script: `spike_data/c1_test2_ui.py`. Uses a Chrome User-Agent
  to avoid the 403 the spike brief warned about.
- Saved raw responses: `spike_data/c1_feb_page_{000..009}.json`,
  `spike_data/c1_ui_{0..4}.{html,txt}`.
- Saved comparisons: `spike_data/c1_test1_comparison.json`,
  `spike_data/c1_test2_results.json`, `spike_data/c1_repull_results.json`.
- Endpoint behaviour gotcha worth recording for Phase 1: the OCDS Search
  endpoint silently strips `?ocid=<OCID>`. Per-OCID lookups must use the
  Notice HTML URL (`/Notice/<release_id>`) or walk the historical
  publication-window query.
- API auth: none required. Public read.
- No rate-limit issues observed across 14 OCDS-page fetches + 5 HTML
  fetches at 0.3–0.5s sleep.
