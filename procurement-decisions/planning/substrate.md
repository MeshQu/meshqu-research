# Substrate Sourcing

> Where the data comes from, under what licence, and how it gets sampled.
> The credibility of the writeup depends on every record being traceable
> back to a publicly verifiable source.

> **First worked application.** This document covers the substrate for the
> first worked application of the methodology: UK Contracts Finder + Find a
> Tender. The harness supports substrate swapping (see
> [`experiment_design.md`](experiment_design.md), "Substrate-agnostic
> design"); future applications would each have their own substrate
> document of similar shape, paired with their own substrate adapter.

## Primary substrate options, ranked

### Option 1. UK Contracts Finder + Find a Tender (RECOMMENDED)

- **What it is**: UK government's published procurement records. Contracts Finder covers below-threshold; Find a Tender covers above-threshold (post-Brexit replacement for OJEU).
- **Licence**: Open Government Licence (OGL) v3.0. Permits redistribution with attribution.
- **Access**:
  - Contracts Finder API: `https://www.contractsfinder.service.gov.uk/api/`
  - Find a Tender API: `https://www.find-tender.service.gov.uk/api/`
  - Both return JSON. No auth for public records.
- **Volume**: Tens of thousands of records per year between the two.
- **Fields useful for the experiment**:
  - Contract value, award date, buyer, supplier
  - Award method (open tender, restricted, single source, framework)
  - Description text
  - Standstill / objection windows
- **Why ranked first**: cleanest schema, sufficient volume, OGL is the most permissive open licence in this space, English-language so easier to reason about for the human-review pass.

### Option 2. EU TED (Tenders Electronic Daily)

- **What it is**: pan-EU procurement gazette. All notices above EU thresholds are published here.
- **Licence**: Free re-use (EU PSI Directive). Some restrictions on bulk redistribution; check the specific dataset.
- **Access**: TED API + bulk downloads in XML.
- **Volume**: Massive. ~700k notices/year.
- **Fields**: Schema-rich but heterogeneous (different national templates).
- **Why ranked second**: bigger and broader, but the heterogeneous schema makes the experiment harder to design. Better as Phase 2 once the UK-only run has shape.

### Option 3. US SAM.gov

- **What it is**: US federal procurement records.
- **Licence**: Public domain (US Government works).
- **Access**: SAM.gov API.
- **Volume**: Federal-scale, large.
- **Fields**: Different vocabulary (FAR, set-asides, NAICS codes, etc.).
- **Why ranked third**: most distant from MeshQu's seed-data shape, schema is US-specific. Adds breadth but not depth.

### Recommendation

**Start with UK Contracts Finder + Find a Tender as the sole substrate for the first writeup.** Document EU TED and US SAM.gov as natural follow-ups in the "what's next" section. The writeup's headline narrative is best served by one substrate done well.

## Licensing posture

Every record used in the experiment must be traceable to its source URL + licence. Concrete rules:

1. **Never redistribute raw records.** The published artefact references each record by its public ID (e.g. Contracts Finder "Notice Identifier") and source URL. Readers fetch the original record themselves if they want to inspect it.
2. **The experiment's own outputs** (receipts, agent reasoning narratives, our derived `fields` payload) ARE redistributed in the corpus bundle.
3. **Attribution**: every artefact links back to the source dataset's licence page.
4. **No transformation that obscures provenance.** If a field is derived (e.g. "is_modification" inferred from the notice type), it's flagged in the receipt's `metadata.derivation_notes`.

## Sampling strategy

The corpus of 300 receipts is **stratified** on a 3×3 grid that reflects empirical reality on Contracts Finder. The original 5×4 grid was retired post-Phase-0 — 14 of 20 cells were under-populated against the spike sample; framework call-offs dominate the substrate at ~68.6% of records.

```
                                   Award method
                       Framework  First-instance  Direct
                       call-off   competitive
Value band  
< £100k                  [a]         [b]            [c]
£100k–£1m                [d]         [e]            [f]
> £1m                    [g]         [h]            [i]
```

Nine cells. Direct-award cells `[c, f, i]` are over-sampled relative to their natural rate so `PROC-001-S53` has enough fire events to be informative. The other cells are proportional. The grid revision is recorded in [decision_log.md](decision_log.md).

"Direct" maps to OCDS `procurementMethod = "direct"` plus PMDs in the set `{"Direct award", "Single tender action (below threshold)", "Other - Direct award"}` — the union the Phase 0 spike used to enumerate the cohort. "Framework call-off" maps to `procurementMethod = "selective"` with PMD in `{"Call-off from a framework agreement", "Call-off from a dynamic purchasing system"}`. "First-instance competitive" is everything else.

## Time window

Records awarded between **2025-01-01 and 2025-12-31** (one full year, recent, stable). Avoid 2026 records because procedure changes may still be settling.

The sample list (notice identifiers) is **frozen and published** as part of the artefact. Readers can confirm the same records were used.

## Proxy-identified PA23 subset for PROC-001-S53

`PROC-001-S53` only applies to procurements governed by the Procurement Act 2023. The Act commenced **24 February 2025**; procurements begun under the Public Contracts Regulations 2015 continue under the old regime.

Phase 0 Q1 found that Contracts Finder OCDS records carry no direct regime field — 96% of records have no PA23 / PCR signal in the OCDS payload. Regime identification is therefore done by **proxy**: `contract_award_date > 2025-02-24` is treated as PA23-governed. The proxy is documented in the receipt's `metadata.derivation_notes` and in the methodology section of the writeup.

Two reporting consequences follow:

1. The sampling script tags every notice with `governed_by_pa23 ∈ {true, ambiguous}` derived from the contract award date. ("False" — i.e. PCR-2015-only — is rare in a 2025-window corpus by construction.) The "clean PA23" subset is contracts awarded **2025-06-01 to 2025-12-31** (a four-month settling-in buffer past commencement).
2. Findings on `PROC-001-S53` are reported against the proxy-identified PA23 subset. Findings on the five composite rules are reported against the full corpus. Records with ambiguous regime (e.g. contracts awarded close to the commencement date where transition arrangements may apply) are reported as a separate subset in the writeup, not silently excluded. The writeup's methodology section makes both reporting boundaries explicit.

The notice-IDs commit includes the `governed_by_pa23` flag per notice, so reviewers can independently verify the subsetting without re-deriving it.

## OCDS endpoint quirk (operational note for Phase 1)

The Contracts Finder OCDS Search endpoint silently strips `?ocid=<OCID>` — passing it returns the latest 100 releases site-wide rather than the single targeted notice. Per-OCID retrieval must walk the publication-window query (`publishedFrom` / `publishedTo` plus `links.next` pagination) or hit the Notice HTML URL directly (`https://www.contractsfinder.service.gov.uk/Notice/<release_id>`). The harness's substrate adapter (`UKContractsFinderAdapter`) must handle this internally; downstream code consuming the normalised `DecisionContext` does not need to know. Discovered 2026-05-14 in the Phase 0.5 C1 spike.

## Mapping a procurement record into a MeshQu DecisionContext

Each record becomes a `POST /v1/decisions/record` payload like:

```json
{
  "decision_type": "procurement.review",
  "fields": {
    "contract_value": 450000,
    "currency": "GBP",
    "award_method": "direct_award",
    "contract_award_date": "2025-08-14",
    "contract_details_notice_published_date": "2025-12-20",
    "publication_delay_days": 128,
    "publication_window_breached": true,
    "governed_by_pa23": true,
    "supplier_name": "Acme Ltd",
    "supplier_id": "GB12345678",
    "buyer_organisation": "Department for ...",
    "is_modification": false,
    "conflict_of_interest_declaration": null,
    "agent_recommended_verdict": "ALLOW",
    "agent_recommended_action": "approve_with_no_changes",
    "agent_reasoning": "Contract details notice was published; supplier identity and value disclosed; appears compliant.",
    "agent_model_id": "claude-opus-4-7",
    "agent_model_version": "claude-opus-4-7-20260101",
    "agent_temperature": "0",
    "agent_prompt_sha256": "<sha256 of the exact published system prompt>"
  },
  "metadata": {
    "experiment_id": "ape-v1",
    "source_dataset": "uk_contracts_finder",
    "source_notice_id": "CF-2025-00012345",
    "source_url": "https://www.contractsfinder.service.gov.uk/notice/...",
    "derivation_notes": "publication_delay_days = awards[0].datePublished - awards[0].date; publication_window_breached = publication_delay_days > 30; governed_by_pa23 = awards[0].date > 2025-02-24 (PA23 commencement proxy — see experiment_design.md 'Substrate analysis preceding pre-registration')"
  },
  "source_artifact": {
    "type": "JSON_PAYLOAD",
    "hash": "<sha256 of the raw source filing bytes>",
    "hash_algorithm": "SHA-256",
    "byte_size": 1234
  },
  "source": {
    "service": "agentic-procurement-experiment",
    "environment": "staging"
  }
}
```

### Publication-delay field mapping (for `PROC-001-S53`)

The s.53 obligation maps to a small group of derived fields on the DecisionContext. Three are computed from verified OCDS fields; one is a documented proxy.

- `contract_award_date` — direct read from `awards[0].date`. Populated 255/255 in the Phase 0 spike sample. **This is the award decision date, not the contract signature date.** PA23 s.53(1) measures the 30-day publication clock from contract signature; the OCDS substrate does not expose signature date directly. The experiment uses award date as a proxy. The proxy is documented in the methodology section and named explicitly in PROC-001-S53's logic description; award decision and contract signature are typically close together but legally distinct.
- `contract_details_notice_published_date` — direct read from `awards[0].datePublished`. Populated 255/255 in the Phase 0 spike sample. Phase 0.5 confirmed the field carries original publication time (Crown Commercial Service `ocds_awards_datePublished_extension`: "the date that the award was published"; re-pull stability 19/19; UI parity 5/5).
- `publication_delay_days` — **derived**: `contract_details_notice_published_date - contract_award_date`. Recorded in `metadata.derivation_notes`.
- `publication_window_breached` — **derived**: `publication_delay_days > 30`. Recorded in `metadata.derivation_notes`. The 30-day cap is PA23 s.53.
- `governed_by_pa23` — **derived as a proxy**: `contract_award_date > 2025-02-24` (PA23 commencement). Recorded in `metadata.derivation_notes` with explicit proxy framing. This is the field that determines whether `PROC-001-S53` even applies; the proxy nature is load-bearing for the rule's scope and is documented in [`experiment_design.md`](experiment_design.md) ("Substrate analysis preceding pre-registration"). Records with ambiguous regime are reported as a separate subset in the writeup, not silently excluded.

The corpus reports `PROC-001-S53` findings against the proxy-identified PA23 subset only. Findings on the five composite rules are reported against the full corpus.

### Locked decisions (see decision_log.md)

- **All agent-provenance fields live in `fields`**, not `metadata`. That includes `agent_reasoning`, `agent_recommended_verdict`, `agent_recommended_action`, `agent_model_id`, `agent_model_version`, `agent_temperature`, and `agent_prompt_sha256`. Everything in `fields` is included in the integrity hash; `metadata` is stripped before hashing ([packages/meshqu-core/src/integrity.ts](../../packages/meshqu-core/src/integrity.ts)). Putting agent provenance in `fields` is what makes the writeup's cryptographic-binding argument hold — a reader can verify which model, which version, which prompt, and which reasoning produced the receipt without taking our word for it.
- **`metadata` carries operational annotations only.** Experiment ID, source dataset references, derivation notes. These are disclosed but not bound by the integrity hash; the writeup treats them as informational.
- **`source_artifact.hash` binds the raw source filing.** The receipt anchors to the exact bytes of the public record. Without this, a reader can't tell whether the receipt anchors to the actual filing or a derived summary.
- **No `tenant` field in `source`.** Tenant scoping is via the `X-Tenant-ID` request header, not the DecisionContext payload ([packages/meshqu-types/src/source.ts](../../packages/meshqu-types/src/source.ts)). Tenant provenance in the published corpus is disclosed two ways instead: (1) prose disclosure in the writeup naming the `experiment-procurement` staging tenant, and (2) the receipt's `signature_kid` resolves to a public key that is uniquely the experiment's — so the kid itself is cryptographic tenant provenance.

## Ethical / legal posture

- All substrate is public-record data published under open licences.
- No personal data of named individuals beyond what the source dataset already published (typically signatories of public contracts. already public).
- No claim that any specific contract in the corpus is non-compliant. The receipt records what MeshQu's policy would say; that is not the same as a legal opinion.
- Buyer organisations / suppliers named in the corpus are NOT contacted, accused, or graded. The writeup explicitly says so in the methodology.

## Operational checklist before sampling

- [ ] Contracts Finder API access confirmed (no auth required for public records, but check current rate limits)
- [ ] Find a Tender API access confirmed
- [ ] Sample selection script reproducible (seed + criteria → notice IDs)
- [ ] Notice IDs frozen and committed publicly before any agent runs
- [ ] OGL v3.0 attribution copy drafted for the writeup
