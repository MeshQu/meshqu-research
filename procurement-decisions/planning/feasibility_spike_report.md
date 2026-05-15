# Feasibility Spike Report

**Date**: 2026-05-14
**Records inspected**: 255 OCDS releases with `awards[0].date` in 2025-06-01 to 2025-12-31, drawn from 1,300 award notices published 2025-06-01 to 2026-02-28. Plus 5 direct-award HTML award-notice pages and 1 chained "previous notice" HTML page.
**Status**: _GO | GO WITH ADJUSTMENTS | NO-GO_ — Sam's call.

> **Phase 0 — pre-pre-registration.** Records inspected here are
> **sacrificial**. They cannot enter the eventual 300-record corpus.
> Notice IDs touched are listed in the appendix so Phase 1's sampling
> script can exclude them.
>
> The brief that produced this report lives at
> [`spike_brief.md`](spike_brief.md). The final GO / NO-GO verdict is
> Sam's, not the agent's — the agent reports findings and recommends.

## Q1: PA23 identification

**Finding (fact, not verdict).** In a 30-record stratified manual classification (round-robin across the 20 method×band cells, sorted by ocid for reproducibility): **0/30 records contained an explicit PA23 signal, 10/30 carried a PCR-2015-distinctive signal (either explicit text reference or PCR-distinctive PMD vocabulary like "Restricted procedure" or "Negotiated procedure without prior publication"), and 20/30 (66.7%) were ambiguous** — the procedure-end date sat after PA23 commencement (2025-02-24) but no regime-distinguishing signal appeared anywhere in the OCDS payload.

Across the full 255-record sample, broader keyword scan: **3/255 had a PA23 signal, 7/255 had a PCR2015 signal, 245/255 had neither** — i.e. ~96% of records carry no regime marker at all.

The OCDS schema as Contracts Finder publishes it has **no `governed_by` / `legislation` / `regulation` field**. The PMD vocabulary used by Contracts Finder is largely PCR-2015-style ("Open procedure", "Restricted procedure", "Call-off from a framework agreement", "Single tender action (below threshold)", "Negotiated procedure without prior publication"). The PA23-distinctive term "Competitive flexible procedure" appears **0 times** in the 255 records. `tender.procurementMethodRationale` — the field that would carry Schedule 5 reasoning — is **populated 0/255 times (0.0%)**.

The only reliable structural inference is negative: when `tender.tenderPeriod.endDate < 2025-02-24`, the procedure was almost certainly commenced under PCR 2015 and continues under PCR 2015 transition arrangements. That fired in 3/30 sample records.

**Recommendation.** Treat OCDS-only PA23 identification as **infeasible at the 10% ambiguity threshold the brief set**. Two-thirds of records cannot be classified without an external lookup (e.g. cross-referencing the Find a Tender service for the same procurement, or hand-coding from notice URL patterns). Decision adjustments listed below.

## Q2: Transparency notice structured-data availability

**This is the most important single check in the spike. The result is decisive.**

For 5 direct awards (selected as the first 5 records where `procurementMethod=="direct"` or PMD contained "Direct award"/"Single tender action"), I attempted the full retrieval flow: OCDS release → `awards[].documents[].url` → fetch HTML award-notice page → search for any "Schedule 5", "section 41/42/43/44", "transparency notice", "regulation 32", "PA 2023", "PCR 2015", "justification", or "rationale" text → if a "Previous notice about this procurement" link exists, follow it and search again.

Per-record results:

| # | OCID (truncated) | Title | PMD | Notice HTML signals | Previous notice? | Previous notice signals |
|---|---|---|---|---|---|---|
| 1 | 36957619-…-563ca39cd2c8 | Provision of IT Hardware and Peripherals | Direct award | none | yes (ad473d9c-…) | none |
| 2 | 2743870e-…-8fb01193cbc4 | Adobe licenses for the current list of subscriptions held by NCC | Other - Direct award | none | none | n/a |
| 3 | 38fc934f-…-adac6cf96aac | EICR Tests - Mansfield District Council | Direct award | none | none | n/a |
| 4 | e0eb949f-…-6769599f657d | Mechanical Repairs and Maintenance of Council Buildings | Single tender action (below threshold) | none | none | n/a |
| 5 | 0d26a82b-…-6aa99ffb709d | Technical Audit Services (MDC) | Direct award | none | none | n/a |

Where "signals" is the disjunction of: `schedule_5`, `section_41`, `section_42`, `section_43`, `section_44`, `regulation_32`, `transparency_notice`, `pa23`, `pcr2015`, `justification`, `rationale`. **All 5 award-notice HTML pages, and the one followed previous-notice page, returned all-False.** None of the pages contain a transparency-notice link, a Schedule 5 ground reference, a section number, or any free-text justification.

The Contracts Finder award notice surfaces only: title, buyer, value, contract dates, procedure type, supplier name + address, a brief description (typically the same one already in the OCDS `tender.description`), and a watch/print/share UI. It is essentially a re-render of the same OCDS fields. There is no Schedule 5 capture surface.

The Schedule 5 / s.44 transparency notice in PA23 is published on **Find a Tender Service (FTS)**, the post-Brexit replacement for OJEU. FTS is a separate publication system from Contracts Finder. It has its own OCDS endpoint. None of the 5 inspected award notices contained a structured cross-link to an FTS transparency notice — the linkage, if it exists at all, would have to be reconstructed by buyer + procurement reference matching across two datasets, with no guarantee FTS captures the Schedule 5 text in structured form either.

**Recommendation.** The s.44 obligation cannot be machine-evaluated end-to-end from Contracts Finder OCDS alone. The faithful PROC-001-S44 rule as currently written in `experiment_design.md` is infeasible against this substrate. Options listed under Design adjustments below.

## Q3: Direct-award volume

**Finding (fact, not verdict).** Of 255 in-window awarded notices: **24 (9.4%) are direct awards** under the OCDS+PMD definition (`procurementMethod=="direct"` OR PMD contains "direct award" OR PMD == "Single tender action (below threshold)"). Breakdown:

- `direct` + "Direct award": 16
- `direct` + "Single tender action (below threshold)": 6
- `None` + "Other - Direct award" / "Other - Direct Award": 2

Extrapolated to a proportional 300-record stratified sample: **~28 direct awards**. The brief flags "fewer than ~30" as the failure threshold for statistical signal.

The 255 in-window records came from 1,300 award notices published in the broader 9-month publication window (2025-06-01 → 2026-02-28). About 19.6% of published award notices had `awards[0].date` falling inside Jun-Dec 2025 — most awards are published months after they are made. Extrapolating naively from 13 pages of 100, **the full universe of awards-with-date-in-window in 2025-06-01..2025-12-31 is on the order of 1,000-2,000 records** (cannot be measured precisely without exhausting the dataset). Direct awards available in absolute terms: probably ~100-200 over the whole period, of which ~28 would land in a proportional 300-record sample.

**Recommendation.** The proportional-sampling design lands at the lower edge of the statistical-power threshold the brief specified. Either (a) oversample direct awards relative to their natural rate (an explicit stratification choice), or (b) widen the window to 2025-03-01..2025-12-31 to grow the absolute pool, accepting more pre-/post-PA23 transition heterogeneity. Note (a) is independent of the Q2 finding — even with oversampling, the s.44 evaluability problem remains.

## Q4: Sampling grid field-population

Observed cell counts from 255 in-window records (NOT pre-registered, NOT a fair sample — pulled in chronological order of publication):

```
                    Award method
Value band       Open  Restricted  Limited  Direct  Framework  Other
< £100k             9          2        4      10        102      9
£100k-£1m           5          3        3      11         56     10
£1m-£10m            2          2        0       3         15      2
> £10m              1          3        1       0          2      0
```

Notes:

- "Framework" here folds `procurementMethod=="selective"` + PMD in {"Call-off from a framework agreement", "Call-off from a dynamic purchasing system"} (175/255 = **68.6% of all records**). This single bucket dominates the dataset.
- "Restricted" is `procurementMethod=="selective"` + PMD == "Restricted procedure" only (10/255 = 3.9%).
- "Limited" is `procurementMethod=="limited"`, predominantly "Competitive quotation (below threshold)" (8/255).
- "Other" is the catch-all where `procurementMethod` is null and PMD is "Other - …" or "Not specified" (21/255).
- Cells with **<5 records** in this 255-sample: `<£100k Restricted` (2), `£100k-£1m Limited` (3), `£100k-£1m Restricted` (3), `£1m-£10m Open` (2), `£1m-£10m Restricted` (2), `£1m-£10m Limited` (0), `£1m-£10m Direct` (3), `£1m-£10m Other` (2), `>£10m Open` (1), `>£10m Restricted` (3), `>£10m Limited` (1), `>£10m Direct` (0), `>£10m Framework` (2), `>£10m Other` (0). That's **14 of 20 cells**, well past the brief's "more than 6 of 20 unfillable" threshold.
- The substrate problem is not just sparsity — the dataset is structurally lopsided. ~70% of UK public-sector awards published on Contracts Finder are framework / DPS call-offs, not first-instance procurements. The "5 procurement methods × 4 value bands" grid imagined in `substrate.md` doesn't match the empirical shape of the data.

**Recommendation.** Drop the 5×4 grid. Adopt either a 2×4 grid (`{direct, competitive}` × value band) or a 3×3 grid (`{framework_call_off, first_instance_competitive, direct}` × `{<£100k, £100k-£1m, >£1m}`). See Design adjustments.

## Q5: Description text richness

20 records, sampled deterministically by ocid sort with 5-per-band stratification across the four value bands. Per-record table:

| # | Band | OCID (truncated) | title_w | desc_w | Title (truncated) |
|---|---|---|---|---|---|
| 1 | <£100k | 04313618-… | 3 | 41 | Digital Maturity Assessment |
| 2 | <£100k | 0446f2f1-… | 6 | 47 | Provision of Vendor Privileged Access Management |
| 3 | <£100k | 04cbe5d2-… | 4 | 69 | Focus group participant recruitment |
| 4 | <£100k | 07eec60e-… | 4 | 4 | ITT for project 10168686 |
| 5 | <£100k | 0829ae1b-… | 4 | 21 | Asset Management Software System |
| 6 | £100k-£1m | 0084538d-… | 4 | 24 | Site 1 Gate Replacement |
| 7 | £100k-£1m | 01041bd3-… | 4 | 64 | Suprasorb P NPM Agreement |
| 8 | £100k-£1m | 012110ef-… | 4 | 5 | Positive Behaviour Support Training |
| 9 | £100k-£1m | 060efa4f-… | 5 | 40 | Revenues & Benefits Telephony/Chatbot Service |
| 10 | £100k-£1m | 08f1888f-… | 2 | 53 | Kitchen Supply |
| 11 | £1m-£10m | 077becc5-… | 11 | 55 | North Northamptonshire Council Fleet Requirements (1) |
| 12 | £1m-£10m | 077becc5-… | 11 | 34 | (same OCID, 2nd award) |
| 13 | £1m-£10m | 0da49abd-… | 9 | 10 | Responsive Repairs for Essex & Suffolk for Hastoe Housing |
| 14 | £1m-£10m | 0edca866-… | 7 | 9 | UK European Applicant Transfer Scheme - Logistics |
| 15 | £1m-£10m | 0fbd6972-… | 8 | 52 | (CPU 7897) EWI installation to Wyton Close, Nottingham |
| 16 | >£10m | 234d42e0-… | 30 | 52 | HCC 09/24 - Residential Placements |
| 17 | >£10m | 2daab022-… | 10 | 86 | Citizen Housing Group Ltd - Faseman Avenue |
| 18 | >£10m | 40fdbc22-… | 13 | 79 | (CPU 7901) Energy Efficiency Works Wave 3 |
| 19 | >£10m | a13eee16-… | 6 | 19 | Award Notice - Contact centre services |
| 20 | >£10m | a60eb9df-… | 7 | 83 | Bristol Avon Flood Strategy Multi-Disciplinary Consultancy |

Distribution across the full 255 records (description word count, not the 20-record sample): **p10 = 4 words, p25 = 6 words, p50 = 12 words, p75 = 43 words, p90 = 78 words, max = 302 words**. Half the dataset has fewer than 12 description-words.

The pattern is clear: text richness rises with value band, but even at the top end the description rarely exceeds 100 words. The Contracts Finder award-notice HTML page contains the same `description` text plus a "Previous notice" link and a structured contract-summary box — **nothing substantively richer than the OCDS payload**. There is no scope-of-work document, no procurement plan, no justification text. Where a contract has documents (as in Q2 records 8-9 with eu-supply.com URLs), they are tender-portal links requiring login, not public scope documents.

Three representative excerpts:

1. **Thin (typical, p25 area)**: *"Asset Management System, Annual Licence including stock condition, DHS, Housing Health and Safety Rating System (HHSRS) module"* (21 words, ITT for project 10168686).
2. **Mid (p75 area, 64 words)**: *"National Pricing Matrix Agreement via NHS Supply Chain for the purchasing of L&R Medical's Suprasorb P negative pressure wound therapy products. The contract enables NHS Trusts and other public sector bodies to purchase the products at agreed pricing for an initial 4-year term with the option to extend by 2 further 12-month periods."*
3. **Top end (p90+, 86 words)**: *"All Suppliers invited to this opportunity have passed the minimum requirements of the Procurement Hub's Development Contractor Dynamic Purchasing System (DPS) OJEU Reference Number 2019/S 111-270743. Citizen New Homes Limited (Citizen) are developing (on behalf of Citizen Housing Group Limited) a site known as Faseman House, Faseman Avenue, Coventry, CV4 9QP. A sole contractors was sought for works comprising of design and construction and completion of a residential development of 50 apartments over 3 storeys for supported housing; along with associated external works…"*

**Recommendation.** The description text is too thin for substantive agent reasoning on most records. An agent given only OCDS fields will, in the median case, see: a 3-12 word title, a 4-12 word description, a value, a method, a buyer, a supplier, a CPV code. The reasoning task collapses to metadata classification — exactly the failure mode the brief flagged. The high-value tail (>£1m) is somewhat richer but still well below what would let an agent reason about, e.g., whether a procurement appears compliant.

## Design adjustments recommended

- [x] **substrate.md — replace 5×4 grid.** Empirical method distribution is heavily framework-dominated (68.6% framework/DPS call-offs). Replace the 5-method grid with one of:
  - **3×3 minimal**: `{framework_call_off, first_instance_competitive, direct}` × `{<£100k, £100k-£1m, >£1m}`. Cells fill cleanly.
  - **2×4 even more conservative**: `{direct_award, competitive}` × value band. Still fills but loses the framework distinction.
  Either way, document that "selective" in OCDS means call-off/DPS and not "selective procedure".

- [x] **substrate.md — broaden window or oversample directs.** Direct awards are 9.4% of in-window records. A proportional 300-record sample yields ~28 direct awards, on the lower edge of statistical viability. Either widen to 2025-03-01..2025-12-31 (~+50% pool, with a documented PCR/PA23 transition heterogeneity caveat) or oversample direct awards 3-4× and apply weights at analysis time.

- [x] **experiment_design.md — rewrite or descope PROC-001-S44.** The faithful s.44 rule cannot evaluate "Schedule 5 ground was named in a published transparency notice and the justification text is on point" from Contracts Finder OCDS alone. Options (least → most invasive):
  1. Scope down to **"a transparency notice exists"** as the only s.44 check, evaluated by presence/absence of an FTS notice cross-reference. Loses the Schedule 5 nuance entirely.
  2. **Add Find a Tender Service (FTS) as a second substrate**, cross-reference by buyer+procurement-reference. Adds ~1 week of substrate work and may still not surface Schedule 5 text in structured form.
  3. **Pivot the faithful rule** to something OCDS *can* support cleanly (e.g. PROC-002 below-threshold-direct-award notice timeliness, or PROC-003 SME-suitable-flag accuracy). PROC-001-S44 stays paper-only as a reference.

- [x] **experiment_design.md — agent-input enrichment decision.** Description text is too thin for the agent to do substantive reasoning. Either (a) restrict the agent to a metadata-classification task and rewrite predictions accordingly, or (b) supplement OCDS with the Contracts Finder HTML award-notice page (only marginal richness gain — ~0 in the 5 cases I checked) plus the buyer's published procurement plan / strategy where retrievable from the buyer website (high cost, very uneven coverage).

- [x] **predictions.md — re-derive P6 and P7 against the new substrate.** P7 (PA23-specific drift) is unsupportable: 96% of records carry no regime signal in the OCDS payload, and a manual 30-record classification leaves 67% ambiguous. Rewrite P7 around something the substrate can support — e.g. drift on framework call-off vs first-instance procurements, or below-threshold vs above-threshold treatment.

- [x] **project_context.md — update substrate description.** Note that "OCDS via Contracts Finder" means PCR-2015-style PMD vocabulary, no Schedule 5 capture, no transparency-notice cross-link, framework-dominated distribution.

- [x] **writeup_outline.md — methodology section needs a "what the data does and doesn't carry" subsection.** Auditors will ask why a paper claiming to evaluate PA23 compliance was built on a substrate that doesn't represent regime. Pre-empt the question.

- [x] **decision_log.md — convert "use Contracts Finder OCDS as substrate" from ✅ to a constrained ✅** with a recorded caveat covering Q1, Q2, Q4, Q5 findings.

## Open decisions for Sam

- **Faithful rule pivot.** Does PROC-001-S44 stay as the faithful reference rule (and we accept the substrate-substrate gap and write it as a "would-be-faithful-if-data-existed" rule), or do we pivot to a different statutory provision that the substrate can actually evaluate? The latter is much cleaner methodologically.
- **Substrate widening vs second source.** Stay on Contracts Finder alone with a wider window, or add Find a Tender Service as a second substrate? FTS adds a week of work and uncertain payoff on the Schedule 5 question, but it is the canonical PA23 publication channel.
- **Stratification grid.** 3×3 framework-aware vs 2×4 minimal? The framework-aware version preserves more of the original framing; the 2×4 is more defensible if reviewer pushback is expected on cell-count thinness.
- **Agent input scope.** OCDS-only (clean methodology, very thin agent task), or OCDS + Contracts Finder HTML (negligible enrichment), or OCDS + buyer-published procurement docs (high effort, uneven coverage)? My read is that none of these gives the agent enough to do substantive reasoning, which means the task itself may need rescoping.
- **PA23 detection method.** Accept that ~67% of records cannot be confidently regime-classified from OCDS alone and either (a) restrict the corpus to records where a regime can be confidently assigned (~33% of the ~1000-record monthly volume, still leaves ~330 candidates for a 300-record sample but with selection bias toward records that explicitly cite legislation), or (b) drop regime as a stratification axis altogether.

## Confidence assessment

**The design as currently written is not feasible against this substrate.** Three of the five questions returned negative findings against the brief's own thresholds:

- Q1 (PA23 identification ambiguity): brief threshold "more than ~10% ambiguous" → observed **66.7% ambiguous** in the 30-record manual classification, **96% no-signal** across the full 255-record sweep.
- Q2 (transparency notice content availability): brief threshold "if only in PDFs" → observed **content not in PDFs nor HTML nor OCDS — content is not in Contracts Finder at all**. The full retrieval flow on 5 direct awards returned zero Schedule 5 / s.44 / transparency-notice signals.
- Q4 (sampling grid populated): brief threshold "more than 6 of 20 cells unfillable" → observed **14 of 20 cells with <5 records** in 255-sample.

Q3 (direct-award volume) sits on the lower edge — workable with oversampling or a wider window. Q5 (description richness) is structurally thin (median 12 description-words) but not fatal if the agent's task is rescoped.

**The single most consequential decision now**: whether to pivot the faithful rule (PROC-001-S44) to a statutory obligation that *can* be machine-evaluated from Contracts Finder data, or to invest in a second substrate (FTS) on the chance that PA23 transparency notices exist there in structured form. The first is faster and more defensible; the second is more ambitious but may still hit the same wall.

Residual risks even after the recommended adjustments:

- Adding FTS does not guarantee Schedule 5 text capture. A pre-spike for FTS would be needed before committing.
- A 2×4 or 3×3 grid is more honest but still leaves the writeup needing to defend why the substrate is what it is.
- Agent reasoning over 12-word descriptions will be visibly thin in the eventual writeup. Rescoping the agent task to "metadata classification with brief justification" may be the only honest framing.

---

## Appendix — Sample notice IDs inspected

> The Phase 1 sampling script MUST exclude these notice IDs from the
> 300-record corpus. They have already been seen by the spike runner.
> Total: 38 unique OCIDs across Q1, Q2, Q5. (255 records were *pulled*
> for Q3/Q4 aggregate counting; only the 38 below were *individually
> inspected*. The full 255-OCID list is preserved in `spike_data/releases.jsonl`
> under the recorded sha256 of that directory and SHOULD also be
> excluded from Phase 1 sampling on the conservative read.)

| Notice OCID | Q | Award date | Notes |
|---|---|---|---|
| ocds-b5fd17-0084538d-de8f-4344-97fd-c5cf7b7feaab | Q1/Q5 | 2025-09-26 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-012110ef-fdf4-4a96-b2c1-98e2555fa1d7 | Q1/Q5 | 2025-11-25 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-04313618-dcfb-4b20-bbf5-bfb566ef53a6 | Q1/Q5 | 2025-10-14 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-0446f2f1-7118-4b7c-b008-fe15ce39c4c6 | Q1/Q5 | 2025-12-29 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-077becc5-9d7e-4b5b-8c87-33bbd2f4d98a | Q1/Q5 | 2025-12-23 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-0da49abd-1499-45a8-bc46-1d11fbf9c16e | Q1/Q5 | 2025-10-03 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-0fbd6972-cb0d-4d85-9ea9-d4c19dfbc587 | Q1/Q5 | 2025-12-15 | PCR2015 (PMD vocab) |
| ocds-b5fd17-1ddc420f-fd3d-45b3-8a26-3d9cd06d5561 | Q1 | 2025-10-29 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-1e54534a-530a-4563-aa1b-41e4d136a9e6 | Q1 | 2025-12-27 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-20f15a04-edd8-43cb-bf22-fd47bf6e5dae | Q1 | 2025-10-29 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-234d42e0-9d94-4cc6-b821-627b61432f8b | Q1/Q5 | 2025-11-10 | PCR2015 (procedure pre-Feb-2025) |
| ocds-b5fd17-2daab022-b911-4dc6-afa4-b795c9b2c4c2 | Q1/Q5 | 2025-10-07 | PCR2015 (explicit) |
| ocds-b5fd17-321c0906-f074-4f86-b47c-bce87fda976d | Q1 | 2025-12-16 | PCR2015 (PMD vocab) |
| ocds-b5fd17-32c0b2fd-e84a-4561-bd83-9ed7f861806f | Q1 | 2025-11-30 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-3469db85-8612-452d-9442-f5fd6e7614fa | Q1 | 2025-12-09 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-35a35327-b376-47ee-90a1-ac51b9556af6 | Q1 | 2025-06-26 | PCR2015 (explicit) |
| ocds-b5fd17-38fc934f-9a67-4cfe-b107-adac6cf96aac | Q1/Q2 | 2025-11-07 | direct award; Q2 HTML had no Schedule 5 / s.41-44 / justification text |
| ocds-b5fd17-3bd98870-6f5b-4398-9bec-e141bf2c2e92 | Q1 | 2025-12-01 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-722b8805-6f11-41a7-b35c-22bec1e3f97a | Q1 | 2025-09-16 | PCR2015 (PMD vocab) |
| ocds-b5fd17-a13eee16-04c9-4c7c-9d7b-88510ae21dc1 | Q1/Q5 | 2025-07-21 | PCR2015 (procedure pre-Feb-2025) |
| ocds-b5fd17-d069c385-f712-4db4-ac59-1d513cb935d4 | Q1 | 2025-12-10 | PCR2015 (PMD vocab) |
| ocds-b5fd17-01041bd3-fc28-4011-ad59-da8d309c843f | Q1/Q5 | 2025-10-20 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-0d26a82b-b705-42b2-b257-6aa99ffb709d | Q1/Q2 | 2025-12-29 | direct award; Q2 HTML had no Schedule 5 / s.41-44 / justification text |
| ocds-b5fd17-04cbe5d2-26a7-4387-94a3-e056f833777f | Q1/Q5 | 2025-10-30 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-07eec60e-bf4b-4a37-a28d-136211af74ec | Q1/Q5 | 2025-09-10 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-42a785e7-17e8-4a5f-934f-1fd4f0ddd2bd | Q1 | 2025-09-30 | PCR2015 (procedure pre-Feb-2025) |
| ocds-b5fd17-c20bfe4b-b2f5-4acf-a7be-743f5cf771f5 | Q1 | 2025-07-09 | PCR2015 (PMD vocab) |
| ocds-b5fd17-2897efd7-eaf0-4ecc-9dca-96ec753bb0d4 | Q1 | 2025-12-11 | ambiguous (procedure post-Feb-2025 but no regime signal) |
| ocds-b5fd17-2743870e-31aa-4263-8097-8fb01193cbc4 | Q1/Q2 | 2025-11-10 | direct award; Q2 HTML had no Schedule 5 / s.41-44 / justification text |
| ocds-b5fd17-0829ae1b-09e2-4258-a97d-29028be45f0d | Q5 | — | <£100k value band sample |
| ocds-b5fd17-060efa4f-c8b5-43db-ab1d-6f55ff8400a8 | Q5 | — | £100k-£1m value band sample |
| ocds-b5fd17-08f1888f-4694-4876-ab33-a9369a1854b3 | Q5 | — | £100k-£1m value band sample |
| ocds-b5fd17-0edca866-ed79-413b-8727-2757d3981be3 | Q5 | — | £1m-£10m value band sample |
| ocds-b5fd17-40fdbc22-7e1f-4581-8cac-5dc70ff663eb | Q5 | — | >£10m value band sample |
| ocds-b5fd17-a60eb9df-6aa5-4d96-896e-64748e862974 | Q5 | — | >£10m value band sample |
| ocds-b5fd17-36957619-0c21-46ee-8804-563ca39cd2c8 | Q2 | 2025-12-08 | direct award; "Previous notice" HTML chased — also empty of Schedule 5 / justification |
| ocds-b5fd17-e0eb949f-be1f-44c9-b41c-6769599f657d | Q2 | 2025-12-24 | single tender action below threshold; HTML empty of regime signal |

## Appendix — Reproducibility

- Spike branch: `main` (all spike artefacts inside `.harness/agentic-procurement-experiment/spike_data/`, gitignored)
- Spike commit hash at spike start: `bf86b097f170c847554829990e99f3fe634bf51e`
- Pull script: `spike_data/pull.py` (paginates from `https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?stages=award&publishedFrom=2025-06-01&publishedTo=2026-02-28&limit=100`, follows `links.next`, filters in-app to `awards[0].date` in [2025-06-01, 2025-12-31], stops at 250 in-window).
- Analysis scripts: `spike_data/analyse.py`, `spike_data/q1_q5_detail.py`, `spike_data/q2_fetch_html.py`, `spike_data/q2_chase_previous.py`.
- Raw data: `spike_data/` (gitignored). Tar sha256 captured 2026-05-14: `b39488939f9f8e55bcc69f83f32ac6184e9cbddd245e1eee71296cf2769b4517` (covers all `page_*.json`, `releases.jsonl`, `direct_awards.jsonl`, `q1_classifications.json`, `q2_results.json`, `q2_chase_results.json`, `q5_records.json`, `q2_notice_*.html`, `q2_notice_*.txt`, `q2_prev_*.html`, `q2_prev_*.txt`).
- Re-runnable: **partial**. `pull.py` is deterministic from a given START URL; the API uses cursor-based pagination, so identical re-runs yield identical pages until upstream data is amended (rare for already-published award notices). HTML page-fetch results may drift if Contracts Finder rerenders templates. The OCID set is what actually anchors reproducibility.
- API auth: none required. Public read.
- Rate-limit behaviour: pull script sleeps 0.3s between OCDS pages; HTML fetches sleep 0.5s. No 429s observed across 13 OCDS pages + 6 HTML pages.
