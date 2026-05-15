# Candidate Faithful Rules — Post-Spike Pivot Analysis

**Date**: 2026-05-14
**Spike findings reference**: [feasibility_spike_report.md](feasibility_spike_report.md)
**Status**: Analysis only. Sam decides which candidate becomes `PROC-001-vN`, then a narrow second spike runs on the chosen candidate before predictions lock.

## Summary table

| Dim | C1 — s.53 30-day notice | C2 — s.47 framework cap | C3 — s.85/s.86 SME honesty |
|---|---|---|---|
| Statute | PA23 s.53(2); SI 2024/692 regs 32–35 | PA23 s.47(1)–(2) | PA23 s.85, s.86; PPN 005 |
| Shape | `threshold + when` on publication delay | `threshold + when` on contract duration | `when + presence` cross-check |
| Required fields | `awards[].date` 255/255; `datePublished` 255/255 — see Risks | call-off period 255/255; framework term 0/255 (kill switch) | `suitability.sme` 255/255; supplier `details.scale` 239/255 |
| In scope (255) | 255 | 175 call-offs | 137 sme-flagged |
| Fires in 300 sample | ~290 if metric holds; unknown if confounded | ~9 (just under ≥10 threshold, AND wrong primitive) | ~60 |
| Drift | High — agents hallucinate "30 days" against the wrong notice (s.50 vs s.53) | Medium — agents conflate framework with call-off | High — agents rationalise SME flag as aspirational |
| Killer risk | `datePublished` may be the snapshot-release timestamp, not original publication. Load-bearing second-spike check | OCDS exposes the call-off, not the framework. The rule's primitive isn't in the substrate | s.85/s.86 are duty-of-consideration provisions, not binary obligations. "Faithful" framing weaker than s.44 was |

## Substrate context

The Phase 0 spike fixed the constraints: 68.6% of records are framework/DPS call-offs; `procurementMethodRationale` 0/255; description p50 = 12 words; 14 of 20 grid cells <5 records; `tender.framework`, `tender.lots`, `tender.numberOfTenderers`, `tender.documents`, `relatedProcesses`, and `awards[].amendments` all 0/255. Any candidate needing multi-notice temporal linkage, narrative justification, or framework metadata is dead. The 38 OCIDs in spike Appendix A are excluded from the future 300-record corpus.

## Candidate 1 — PA23 s.53 Contract Details Notice timeliness (30 days)

### 1. Statutory citation
Procurement Act 2023, s.53(2): a contracting authority that enters into a public contract must publish a Contract Details Notice before the end of the 30-day period beginning with the day on which the contract is entered into (120 days for light-touch contracts, s.53(3)). Form and content are set by Procurement Regulations 2024 (SI 2024/692), regs 32–35, varying by whether the award was competitive, direct, a framework, or a call-off.

Secondary: Cabinet Office, "Guidance: Contract Details Notices (HTML)" — distinguishes s.53 (post-entry, 30 days) from s.50 (pre-entry Contract Award Notice, no fixed day count). Brabners, "Procurement Act 2023 — transparency and new notice requirements explained" (2024).

### 2. Plain-language statement
After a public contract is signed under PA23, the buyer must publish a Contract Details Notice within 30 days (or 120 days if the contract is in the light-touch services regime).

### 3. Rule shape in MeshQu syntax
```
PROC-001-S53 (faithful — PA23 s.53)
  type: threshold + when
  severity: high
  when: governed_by == "procurement_act_2023"
    AND notice_kind == "contract_details_notice"
    AND contract_signed_date IS NOT NULL
  threshold:
    days_between(notice_published_date, contract_signed_date)
      <= 30  if light_touch == false
      <= 120 if light_touch == true
  outcome on breach: DENY (notice late)
```

### 4. Evaluability against Contracts Finder OCDS
- Required fields: `awards[].date` (contract-entered proxy), notice-publication date, CPV / `mainProcurementCategory` (to derive light-touch).
- Population in the spike sample: `awards[0].date` 255/255; `awards[0].datePublished` 255/255; top-level `date` 255/255; `mainProcurementCategory` 255/255; CPV `classification.id` 255/255.
- **Confounder found in the data.** 244/255 records carry `awards[0].datePublished` and top-level `date` both clustered around 2026-02-27 (the date of the spike pull), while `awards[0].date` spreads across June–December 2025. The OCDS feed appears to surface the *current* snapshot release timestamp on `datePublished`, not the original notice-publication moment. If verified, the published-date primitive the rule needs is not in a single OCDS pull — it is the *first* release stamp.
- Light-touch is a derived feature: not in OCDS, requires encoding the Schedule 1 SI 2024/692 CPV ranges (health/social work codes 75/79/80/85, etc.). Tractable, adds methodology surface.
- Failure-mode-in-different-form: yes. If `datePublished` is a snapshot stamp, this is the s.44 trap reframed — substrate doesn't carry the named primitive.

### 5. Expected fire-frequency
- In scope: 255/255.
- Naive: 246/255 over 30 days, p50 = 127 days → ~290 DENY in a 300-record sample.
- If the confounder is real: unknown. True value plausibly ranges from near-zero (publication is timely and the spike artefact is OCDS re-rendering) to still-high (buyers genuinely publish late).

### 6. Drift potential
High. Agents reliably "know" that PA23 introduced a 30-day publication rule and reliably conflate s.50 (pre-entry Contract Award Notice, no fixed day count) with s.53 (post-entry Contract Details Notice, 30 days). Disagreement cases where the agent rationalises late deltas as "within the 30-day Award Notice window" are the clean finding.

### 7. Risks
- **Load-bearing**: `datePublished` may be a snapshot timestamp not the original. If so, the rule cannot be evaluated from a single OCDS pull.
- **Light-touch derivation** is interpretive; reviewer can object.
- **Regime ambiguity from Q1**: 96% of records carry no PA23/PCR signal. The rule's `governed_by` predicate must rely on a procedure-end-date proxy (`tender.tenderPeriod.endDate ≥ 2025-02-24`, satisfied by 247/255) — but Q1 showed 66.7% of those are still substantively ambiguous.

### What the second spike would check
- Re-pull 20 spike-sample notices and observe whether `awards[0].datePublished` / top-level `date` change between pulls. Stable → original-publication; changing → snapshot.
- Check whether the OCDS `releases` endpoint (point-in-time) vs `records` endpoint (aggregated history) preserves first-published timestamps per release.
- Hand-verify 5 records with <30-day delta and 5 with >100-day delta against the Contracts Finder web UI's separate "Date published" field.
- Confirm the light-touch CPV mapping against Schedule 1 of SI 2024/692.
- Decide how regime ambiguity is handled — procedure-end-date proxy, explicit-signal restriction, or accept the noise with a methodology caveat.

## Candidate 2 — PA23 s.47 framework-term cap (4 years)

### 1. Statutory citation
Procurement Act 2023, s.47(1): a framework awarded under the Act may not have a term exceeding 4 years. s.47(2)–(3): the cap is 8 years for utilities and defence/security; any framework may exceed its cap where the nature of the call-offs requires a longer term, provided the rationale is published in the Tender or Transparency Notice.

Secondary: Cabinet Office, "Guidance: Frameworks (HTML)"; Ward Hadaway, "Procurement in a Nutshell — PA23: Frameworks" (2024); Fieldfisher, "PA23 — Frameworks and Dynamic Markets" (2024).

### 2. Plain-language statement
A PA23 framework agreement runs at most 4 years (8 for utilities/defence) unless the buyer publishes a written rationale for a longer term in the framework's Tender or Transparency Notice.

### 3. Rule shape in MeshQu syntax
```
PROC-001-S47 (faithful — PA23 s.47)
  type: threshold + when
  severity: medium
  when: governed_by == "procurement_act_2023"
    AND framework_kind == "framework_agreement"   # NOT call-off
  threshold:
    framework_term_days <= 4 * 365   # 8 * 365 for utilities/defence
    OR framework_extended_rationale_published == true
  outcome on breach: REVIEW (excess term without published rationale)
```

### 4. Evaluability against Contracts Finder OCDS
- Required: framework start/end dates, framework kind, rationale-published boolean.
- Spike population: `tender.framework` 0/255 — **kill switch**; `awards[0].contractPeriod.{start,end}Date` 255/255, but these are call-off dates, not framework dates; `procurementMethodDetails` contains framework/DPS strings 175/255.
- The OCDS payload exposes the call-off, not the framework. A call-off's duration may legitimately exceed the framework's term (PA23 explicitly allows it). Long call-offs do not by themselves breach s.47.
- Substrate carries the wrong primitive. Evaluating s.47 properly would require fetching the framework's own record (separate OCID, likely on FTS for above-threshold frameworks) — multi-notice temporal logic, the failure mode the substrate constraint forbids.

### 5. Expected fire-frequency
- Reinterpreted as "call-off duration > 4 years" (NOT s.47 but what OCDS supports): 8/175 → ~9 in a 300-record sample. **Just under the ≥10 threshold, AND on the wrong metric.**
- Faithful against the framework's term: unmeasurable from this substrate.

### 6. Drift potential
Medium. Agents recall "4-year cap" and apply it to whatever date pair the record exposes — i.e. they conflate call-off duration with framework term. That conflation is itself a drift signal, but only if the rule operationalises call-off duration as an explicit proxy. As a faithful rule, it doesn't survive — the provenance string would be dishonest.

### 7. Risks
- Killer is structural: OCDS exposes the call-off, the cap operates on the framework. A second spike won't fix this.
- Reinterpreted version sits just under the brief's fire-frequency floor.
- Broadening to "any contract > 4 years" raises fires but severs the link to s.47.

### What the second spike would check
- Confirm zero population of `tender.framework`, `relatedProcesses`, and framework-term fields on an independent 200-record pull (ruling out sampling artefact).
- Check whether Contracts Finder's *Tender Notice* for framework-establishment carries the framework term (different notice class from the call-off awards in this sample).
- Check whether FTS OCDS publishes framework-term metadata in structured form. If yes, the candidate becomes a two-substrate rule.
- If no path works, formally retire s.47 to the rejected list.

## Candidate 3 — PA23 s.85/s.86 SME suitability flag honesty

### 1. Statutory citation
Procurement Act 2023, s.85: for *regulated below-threshold contracts*, a contracting authority may not restrict who may tender by reference to supplier suitability (legal status, financial standing, technical ability). s.86: before inviting tenders for a regulated below-threshold contract, the authority must consider whether barriers to SME participation can be removed or reduced, and act on that consideration.

Secondary: Cabinet Office, "Guidance: Below-Threshold Contracts (HTML)"; PPN 005, "Guide to reserving below-threshold procurements" (2025); Hempsons, "Regulated below threshold contracts under PA23: a how-to guide" (2024).

### 2. Plain-language statement
For regulated below-threshold contracts published as "suitable for SMEs", the buyer has duties under s.86 to actively reduce SME barriers. The published `suitability.sme = true` flag is a representation that those duties were considered. When the same record's supplier outcome is a large enterprise, the representation is at minimum unscrutinised and worth surfacing.

### 3. Rule shape in MeshQu syntax
```
PROC-001-SME (faithful-adjacent — PA23 s.85, s.86)
  type: when + presence
  severity: medium
  when: tender.suitability.sme == true
    AND award.value.amount < 139_688   # central-gov threshold; sub-central is £214,904
  presence:
    parties[role=supplier].details.scale != "large"
  outcome on breach: REVIEW (SME-suitability flag inconsistent with award outcome)
```

### 4. Evaluability against Contracts Finder OCDS
- Required: `tender.suitability.sme`, supplier `details.scale`, `awards[0].value.amount`.
- Spike population: `suitability.sme` 255/255 (true: 137, false: 118); supplier `details.scale` 239/255 (sme 141, large 98, null 16); award value 255/255.
- Below-£139k subset: 154/255. Cross-tab in that subset: 82 sme-flag-true × sme-supplier; 51 sme-flag-true × large-supplier; 4 sme-flag-true × unknown.
- Derivation: none significant. Direct read.
- Failure-mode-in-different-form: weaker than s.44. `details.scale` is buyer-or-supplier classified and may be inaccurate. A "large supplier won an SME tender" may reflect mis-coding, not substance. Data-quality risk, not substrate-absence.

### 5. Expected fire-frequency
- In scope: 137/255 sme-flagged → ~161 in 300 sample.
- Fires (large-supplier-won): 51/137 = 37% → **~60 fires**. Comfortably clears ≥10.

### 6. Drift potential
High. An agent seeing "tender flagged SME-suitable but won by large supplier" will rationalise: suitability is an aspiration, the tender was open to all, this is fine. That rationalisation is *partially* correct — the OCDS `sme` flag is a hint, not a reservation. But under s.85/s.86, the published flag is a representation of duty-discharge. Whether the flag-vs-outcome gap is substantive, a data-quality issue, or a non-issue is genuinely contested. The contestation is the drift signal.

### 7. Risks
- **"Faithful" framing is weaker than s.44.** s.85 prohibits suitability-based *participation* restrictions; s.86 imposes a *consideration* duty; neither makes "SME-suitable flag must result in an SME win" a binary obligation. The rule operationalises a duty as a flag-vs-outcome check — one interpretive step between statute and rule. A reviewer can call this a composite.
- `details.scale` is supplier-side; 16 "unknown" cases need a handling policy.
- Drift may be trivial: if the agent is the better legal reader, the disagreement is uninteresting.
- Regulated below-threshold scope (£30k–£139k goods/services, £30k–£214k sub-central) needs settling. ~120 of the 154 below-£139k records are likely above £30k (second-spike confirm).

### What the second spike would check
- Confirm `details.scale` population stays >90% across an independent 200-record pull, and the `sme`/`large`/`vcse` enumeration is stable.
- Re-run the cross-tab with the £30k floor and the £214k sub-central threshold applied.
- Hand-review 10 records where `sme=true` and a large supplier won — read description, check whether the tender was open or genuinely reserved.
- Probe published Cabinet Office / NAO commentary that operationalises s.86 as a flag-vs-outcome check. If no commentary frames it this way, downgrade to composite.
- Check the VCSE flag in parallel (41/255 flagged). Tighter category — may surface a cleaner signal.

## Directions considered and rejected

- **PA23 s.50 Award Notice content completeness.** Core fields (`buyer.name`, award value, supplier name, CPV, contract end) all 255/255. Rule fires 0 times. Trivially derivable from notice type — the brief forbids this. Rejected on fire-frequency.
- **PA23 s.74 modification disclosure.** `tender.amendments`, `awards[].amendments`, `relatedProcesses`, `awardAmendment`/`tenderAmendment` tags all 0/255. Only `awardUpdate` (18/255) appears, carrying no structured modification metadata. Multi-notice temporal-linkage failure — the s.44 trap. Rejected.
- **PA23 s.41–s.43 direct-award Schedule 5 grounding.** `procurementMethodRationale` 0/255; the rule fires DENY on every above-threshold direct (11/255), a uniform-pathological signal indistinguishable from substrate absence. The s.44 problem reframed. Rejected.
- **PA23 s.52 KPI publication for >£5m contracts.** `tender.documents` 0/255; above-£5m subset 11/255 has scope but no KPI primitive. Rejected on substrate-absence.
- **PA23 s.99 conflict-of-interest declaration publication.** No CoI field in OCDS. Rejected on substrate-absence.
- **PA23 s.93(2) £30k below-threshold notice publication.** All 255 spike records *are* published notices — selection bias. The interesting case (buyers who don't publish) is unobservable from a corpus of published records. Rejected.
- **Stand-alone "30-day publication" rule (no date-semantics check).** Naive measurement showed 246/255 over 30 days. The confounder — top-level `date` and `datePublished` clustered at 244/255 in February 2026 against `awards[0].date` spread across June–December 2025 — means the metric as-measured cannot be trusted. Elevated to Candidate 1 with an explicit second-spike check rather than rejected outright; flagged here for transparency.
- **Reserved contracts (PA23 s.32 supported-employment).** No reservation flag in OCDS. VCSE (41/255) is adjacent but distinct. Rejected on substrate-absence.
- **Multi-supplier award detection (DPS overuse).** 10/255 awards with >1 supplier — under fire threshold and weak legal anchor. Rejected.

## Honest assessment

None of the three candidates is as clean a single faithful rule as `PROC-001-S44` was *intended* to be — and s.44 itself proved infeasible against the substrate, so the comparison is to an ideal the substrate never supported.

The three candidates fail in different ways:

- **C1 (s.53 30-day Contract Details Notice)** is the strongest substrate fit on paper — high in-scope volume, clean rule shape, well-known statute, good drift potential (agents plausibly confuse s.50 with s.53). One load-bearing risk: the date-semantics confounder. If the second spike shows `datePublished` is a snapshot timestamp, the candidate collapses. If it shows the field carries the original publication moment (or that the `releases` endpoint preserves it), C1 is the only candidate here that genuinely supports the "faithful rule" framing.
- **C2 (s.47 framework cap)** is the cleanest *statute* but the worst *substrate fit*. The OCDS payload exposes the call-off, not the framework. Any rule the substrate supports breaks the "faithful" claim — it would name s.47 in its provenance while measuring something s.47 doesn't govern. Either kill it or downgrade to composite.
- **C3 (s.85/s.86 SME suitability)** has the highest fire rate and lowest faithfulness. s.85/s.86 are duty-of-consideration provisions, not binary obligations. The rule operationalises the duty as a flag-vs-outcome cross-check, which is interpretive. The drift signal is real and the data is clean; the cost is that the "one faithful, five composite" framing weakens — there's no hard statutory anchor of the s.44 kind.

**Read on whether the original framing survives.** "One faithful rule, five composites" was load-bearing — the writeup's headline claim was drift against a real specific statutory rule the agent is unlikely to know correctly. C1 fully meets that ambition, conditional on the second spike. C2 cannot be made to. C3 weakens the framing to "one statutorily-anchored rule + five composites" — defensible, but a subtle retreat.

If C1's date semantics fail the second spike, the honest move is to drop the "one faithful rule" framing rather than dress up C2 or C3 to fill the slot. The experiment can still surface drift against six composites (or five composites and one interpretive rule with a careful provenance string), and the writeup's methodology section can name the substrate limit as the reason — itself a methodologically transparent finding worth publishing.

The substrate has now constrained the experiment twice (s.44, potentially again on s.53). A third pivot would suggest the substrate cannot support the original ambition and the design needs to change shape rather than rule choice.

---

## Sources

Statutory: Procurement Act 2023 ([s.32](https://www.legislation.gov.uk/ukpga/2023/54/section/32), [s.47](https://www.legislation.gov.uk/ukpga/2023/54/section/47), [s.53](https://www.legislation.gov.uk/ukpga/2023/54/section/53)); Procurement Regulations 2024 (SI 2024/692), regs 32–35.

Cabinet Office guidance: [Contract Details Notices](https://www.gov.uk/government/publications/procurement-act-2023-guidance-documents-procure-phase/guidance-contract-details-notices-html); [Contract Award Notices and Standstill](https://www.gov.uk/government/publications/procurement-act-2023-guidance-documents-procure-phase/guidance-contract-award-notices-and-standstill-html); [Frameworks](https://www.gov.uk/government/publications/procurement-act-2023-guidance-documents-define-phase/guidance-frameworks-html); [Below-Threshold Contracts](https://www.gov.uk/government/publications/procurement-act-2023-guidance-documents-define-phase/guidance-below-threshold-contracts-html); [PPN 005 reserved below-threshold](https://assets.publishing.service.gov.uk/media/67af5f3e6e6c8d18118ace43/PPN_005_Guide_to_reserving_below_threshold.pdf).

Law-firm commentary: [Brabners — transparency / new notices](https://www.brabners.com/insights/procurement/procurement-act-2023-transparency-and-new-notice-requirements-explained); [Ward Hadaway — Frameworks](https://www.wardhadaway.com/insights/updates/procurement-in-a-nutshell-procurement-act-2023-frameworks/); [Fieldfisher — Frameworks and Dynamic Markets](https://www.fieldfisher.com/en/insights/procurement-act-2023-frameworks-and-dynamic-markets); [Hempsons — regulated below-threshold](https://www.hempsons.co.uk/news-articles/regulated-below-threshold-contracts-under-the-procurement-act-2023-a-how-to-guide/); [Trowers & Hamlins — Award notices / standstill](https://www.trowers.com/insights/2024/january/pod-contract-award-notices-assessment-summaries-and-the-standstill-period).
