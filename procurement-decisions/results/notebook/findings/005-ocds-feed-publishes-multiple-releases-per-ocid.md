# Finding 005 — Contracts Finder OCDS feed publishes multiple releases per OCID; effective corpus n=283, not 300

**Created:** 2026-05-18
**Status:** stable (substrate behaviour empirically confirmed; design decision for the substrate adapter deferred to a future session)
**Bears on:** methodology, substrate honesty

## The claim

The 2026-05-18 corpus run (`dry-run-7ddf7274-…`) attempted 300 records and produced 300 MeshQu receipts. **Only 283 of those are distinct decisions.** 12 OCIDs were returned more than once by the Contracts Finder OCDS Search endpoint within the same date window (`2024-12-01 → 2026-04-30`, `stages=award`). The substrate adapter passed every release through to MeshQu; MeshQu's idempotency cache returned the same receipt on the duplicate POST. **Server state is uncorrupted** — the same `decision_id` appears against each duplicated OCID and the cryptographic chain is intact — but the effective corpus is n=283 distinct procurement records, not n=300.

The substrate-adapter's current behaviour is correct **as a faithful relay of what the OCDS feed publishes**. Whether it should also dedupe by OCID before passing records downstream is a design decision: dedupe gives "one receipt per unique procurement"; pass-through gives "one receipt per release event the feed published." Both are defensible; neither is what the current adapter explicitly chose.

## Evidence

### Dedup distribution

Of the 12 duplicated OCIDs in the corpus:

```
7 ocds-b5fd17-f5052bc7-d3b9-4a56-9bca-fe06c5d44561 indexes: 68 143 191 240 252 253 265
2 ocds-b5fd17-fb3464e4-…  indexes: 171 175
2 ocds-b5fd17-c060e681-…  indexes: 244 246
2 ocds-b5fd17-963c1afb-…  indexes: 66  71
2 ocds-b5fd17-71c68508-…  indexes: 210 211
2 ocds-b5fd17-6bb11187-…  indexes: 212 214
2 ocds-b5fd17-692f6806-…  indexes: 100 105
2 ocds-b5fd17-632ab1c5-…  indexes: 182 193
2 ocds-b5fd17-5818cdef-…  indexes: 148 166
2 ocds-b5fd17-4f5dd7d2-…  indexes: 268 269
2 ocds-b5fd17-39e7a012-…  indexes: 225 228
2 ocds-b5fd17-2d7dff2e-…  indexes: 77  95
```

The distribution rules out "pagination overlap" as the explanation:

- The 7× repeat (`f5052bc7-…`) appears at scattered indexes (68, 143, 191, 240, 252, 253, 265) spanning ~200 records. Pagination overlap would cluster duplicates within a single page boundary (`limit=100`).
- The adjacent or near-adjacent pairs (e.g. 268+269, 210+211, 244+246, 212+214) ARE consistent with pagination, but the broader scattered pattern dominates.

### Feed probe (live)

A direct query against the Contracts Finder OCDS Search endpoint for the 7×-duplicated OCID returns **100 releases on page 1 alone**, with `links.next` present (more pages exist):

```
$ curl -sS '…?stages=award&publishedFrom=2024-12-01&publishedTo=2026-04-30&limit=100&ocid=ocds-b5fd17-f5052bc7-…'
releases returned: 100
  release.id=6ab68eb1-…-895459  tag=['award']  date=2026-04-29T19:31:05+01:00
  release.id=d41da547-…-895458  tag=['award']  date=2026-04-29T17:53:11+01:00
  release.id=f1853da7-…-895457  tag=['award']  date=2026-04-29T17:45:18+01:00
  release.id=ce9a01a9-…-895456  tag=['award']  date=2026-04-29T17:30:17+01:00
  release.id=b44bfac0-…-895455  tag=['award']  date=2026-04-29T17:30:12+01:00
  …
links.next present: True
```

Each release has its own `release.id` but the same `ocid`. All carry `tag=['award']` (so it's not amendments) and the dates cluster tightly (minutes apart) suggesting a single contracting event published multiple times.

### Why this happens (OCDS spec angle)

OCDS allows multiple **releases** per **OCID**: each release is a snapshot of the procurement at a point in time. A buyer may publish an initial award notice, then re-publish with corrections, then re-publish on contract signing, etc. The OCID is the procurement identifier; the release is the publication event. The Contracts Finder feed's `releases[]` array is keyed by release event, not by OCID — when queried by date window, it returns every release that landed in the window, regardless of how many of them share an OCID.

This is **compliant with the OCDS spec**; it's not a bug in either Contracts Finder or our adapter. It IS a feature consumers need to be aware of when designing for "one record per procurement."

### MeshQu state confirms idempotency held

Sam's run-day analysis (notebook §"OCDS duplicate-fetch defect") confirmed: all 17 duplicate-trace rows show the **same `receipt_timestamp`** as the original receipt for that OCID. Meaning MeshQu evaluated each unique OCID once and returned the cached receipt on every subsequent POST — the idempotency-key design (see [`runner/meshqu_runner/eval_loop.py`'s `_idempotency_key`](../../runner/meshqu_runner/eval_loop.py)) prevented duplicate evaluation costs and duplicate corpus rows.

## Caveats

- The probe used the `?ocid=` filter, which Contracts Finder's API supports but [the Phase 0.5 C1 spike report](../../planning/feasibility_spike_c1_report.md) noted as "silently strips" in some response paths. The 100-releases-for-one-OCID result is consistent with the feed publishing many releases per OCID, but a more thorough investigation would walk the full `links.next` chain to count total releases per OCID across the corpus window.
- The 12 duplicated OCIDs are not a representative sample of "high-traffic procurements" — they're just the ones that happened to land in the window's first 300 results. The actual distribution of releases-per-OCID across the corpus is likely heavier-tailed than these 12 records suggest.
- The 17-extra-rows-from-12-OCIDs (5.7% of the run) is a useful upper bound on the inefficiency cost: the corpus run made 300 substrate→agent→MeshQu calls but only 283 produced unique cryptographic artefacts. ~5% of OpenAI tokens spent on records MeshQu had already evaluated.

## Design decision deferred to a future session

The substrate adapter's response to this is a **design call**, not a quick patch:

### Option A — Dedupe by OCID at fetch time, keep latest release

- Substrate adapter holds an in-memory set of seen OCIDs across the fetch; on duplicate, replaces the prior release with the latest one before passing to the agent.
- Corpus becomes "one receipt per unique procurement observed in the window."
- Loses the "audit-trail of all release events" angle but matches what most downstream consumers would expect.

### Option B — Pass through every release; dedupe at analysis time

- Current behaviour. Substrate is honest about what the feed returned.
- Corpus carries every release event as a separate receipt; analysis layer dedupes by OCID where needed.
- Methodologically cleaner for "what we observed" claims; cost is the ~5% wasted OpenAI spend and the n-vs-n_unique distinction the notebook has to maintain.

### Option C — Hybrid: dedupe within a fetch, allow re-fetch across runs

- Within a single corpus run, dedupe by OCID (Option A's semantic).
- Across separate runs (e.g. a reproducibility-rerun), accept the same OCID may appear again in fresh receipts.
- Captures intent of "this fetch is a snapshot of distinct procurements in this window" without conflating runs.

### What this finding recommends (preliminary)

**Option C is the methodologically cleanest.** The corpus represents distinct procurements observed in a window; the *experiment* is repeatable (a reproducibility-run is a fresh observation of the same window). Adopting C means:

- Substrate adapter gains an in-fetch OCID-seen set (~10 lines of code).
- Decision-traces include a `release_id` field alongside `ocid` so the audit trail records which specific release event was evaluated.
- Future corpus runs report n_unique alongside n_attempted.

But this is **not in scope for this experiment**. The current corpus's analysis layer correctly dedupes to n=283 for all rate/distribution claims, and the writeup will name this distinction explicitly. Option C ships when the next corpus run is in flight, not retroactively against this one.

## What this changes about the writeup

Section 4 (substrate) gains a paragraph naming the OCDS-release-vs-OCID distinction as a substrate-honesty feature. The corpus's "we observed 283 unique procurements via 300 release events" framing is more honest than collapsing to either single number. Section 7 (limitations) gets the "future-experiment substrate adapter should dedupe in-fetch" recommendation, with this finding as the source of the decision.

Cross-references:

- Notebook entry: `2026-05-18-full-run.md` §"OCDS duplicate-fetch defect"
- Feasibility evidence: `planning/feasibility_spike_c1_report.md` (the spike that originally documented Contracts Finder OCDS endpoint quirks)
- Code: `runner/meshqu_runner/substrate.py` — `fetch_ocds_records()` is the function that would gain the dedup logic under Option C
