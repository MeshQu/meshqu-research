# Experiment Design

> The methodology. Drafted at planning time; revisions are tracked in
> [`decision_log.md`](decision_log.md). The pre-registered predictions
> against this design live in [`predictions.md`](predictions.md) and are
> committed BEFORE any execution.

## The agent loop, in one diagram

```
┌──────────────────────────┐
│ source data              │   ← substrate-specific (OCDS feed, client archive, etc.)
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Substrate adapter         │   ← per-source: data fetch, schema mapping,
│ (UKContractsFinderAdapter │     governance regime identification
│  for this experiment)     │
└─────────────┬────────────┘
              │
              ▼
       normalised
       DecisionContext
              │
              ▼
┌──────────────────────────┐
│ LLM agent. system prompt │   ← substrate-agnostic
│ asks: "review this        │
│ procurement record. Should │
│ it be approved, denied, or│
│ flagged for review? Cite  │
│ the policy clause that    │
│ justifies your decision." │
└─────────────┬────────────┘
              │
              ▼
        agent verdict
        + reasoning
        + claimed citation
              │
              ▼
┌──────────────────────────┐
│ MeshQu                    │   ← substrate-agnostic
│ POST /v1/decisions/record │
│ decision_type=            │
│   procurement.review      │
│ fields = filing + agent's │
│   structured output       │
└─────────────┬────────────┘
              │
              ▼
       receipt v2:
       • integrity_hash
       • signature
       • policy_snapshot_digest
       • evaluated_rules_hash
       • violations[]
       • fields.agent_model_id, fields.agent_model_version, fields.agent_prompt_sha256
              │
              ▼
       (corpus accumulator)
              │
              ▼
       human review of N% sample
       to ground-truth false-pos / true-pos
```

### Substrate-agnostic design

The harness is structured so the substrate is replaceable. A `Substrate` adapter handles source-specific concerns (data fetching, schema mapping, governance regime identification, field-population handling). It exposes a single interface: given a source-specific identifier, return a normalised `DecisionContext` payload. The `EvaluationPipeline` consumes `DecisionContext` payloads, runs the agent, records decisions through MeshQu, and accumulates receipts. The pipeline does not know what substrate produced the payloads.

For this experiment, the substrate adapter is `UKContractsFinderAdapter`. The adapter encapsulates everything UK-specific: OCDS pagination, the PA23-vs-PCR governance regime inference, the transparency-notice linkage, the description-text extraction. A different substrate — a different source archive, a different schema, a different regulatory regime — would be a new adapter; the rest of the pipeline is unchanged.

This separation costs roughly half a day of additional design time during Stream C (harness build) and compounds in two ways. First, it forces the experiment's own scope to be cleanly source-specific in one place and source-agnostic elsewhere, which sharpens the methodology. Second, it makes future applications of the same methodology a substrate-adapter implementation plus a domain-specific policy authoring pass, rather than a rebuild.

The evaluation pipeline is built on **Inspect AI** (<https://ukgovernmentbeis.github.io/inspect_evals/>), the UK AI Safety Institute's framework for systematic LLM evaluation. Inspect AI provides multi-provider support (OpenAI, Anthropic, Google, Mistral, Hugging Face Inference), explicit model selection and configuration, temperature control, structured output enforcement, and evaluation artefacts that integrate with downstream analysis. The choice is deliberate: using a purpose-built evaluation framework rather than direct API calls or a generic agent framework signals that this is a controlled experiment, not an integration. The substrate adapter handles source-specific concerns and produces normalised `DecisionContext` payloads; Inspect AI handles the evaluation loop and produces structured outputs and traces.

### The experiment as MeshQu product proof

The experiment serves three purposes simultaneously: it produces a public research artefact, it develops methodology infrastructure reusable across future applications, and it stress-tests MeshQu's production behaviour at corpus scale on real external data. The third purpose is not incidental. Most demonstrations of decision-receipt infrastructure are either synthetic-data demos that don't exercise real-world substrate variability, or single-decision examples that don't exercise sustained signing-and-anchoring load.

This experiment is different. It runs 300 real procurement records through a dedicated MeshQu staging tenant, produces 300 signed receipts under sequential load, anchors each to Sigstore Rekor, and round-trips the resulting bundle through verify.meshqu.com using source-code-registered trust anchors. Every component of MeshQu's production signing and verification path is exercised end-to-end against substrate the development environment didn't fully anticipate.

The staging environment runs the same code path as production. Operational observability is provided by Grafana dashboards scoped to the experiment tenant, covering signing operations (rate, latency p50/p95/p99, failure count), Sigstore Rekor anchoring (rate, latency, failure count), database write throughput, and Fastify application-level error rates. The Grafana dashboards read from Prometheus-style metrics exposed by MeshQu's signing service (signing operations, latency histograms with sub-millisecond resolution at the low end, failure modes), the Rekor anchoring client (request rate, latency histogram with wider buckets reflecting external-dependency variance, failure modes by reason), the PostgreSQL/Supabase connection layer (write throughput, connection pool health, exhaustion events), and the Fastify application layer (request rates and error rates by route and status code). The instrumentation is verified production-equivalent on staging — including `tenant`-label coverage so dashboards can filter to the experiment tenant — before the run starts; gaps are closed via small instrumentation PRs in the build phase. The run is monitored in real time; anomalies surface within minutes rather than hours.

The corpus that results is therefore both research evidence and product evidence. A prospective client who asks "does MeshQu actually work end-to-end on real data at scale" can be pointed at this corpus and shown the receipts verifying cleanly. The Grafana observability data, captured as screenshots taken during the run, provides supporting operational evidence: signing latency under sustained load, Rekor anchoring reliability, end-to-end behaviour across a realistic decision corpus. That's a categorically different kind of credibility than architectural diagrams or feature claims. The experiment's findings document what AI-assisted compliance review reveals; the experiment's artefacts document that MeshQu's infrastructure produces verifiable evidence of those decisions reliably.

The build phase is structured to surface this dimension explicitly: the harness captures anomalies and failures alongside successful operations, the substrate adapter is built and tested independently before integration with the evaluation pipeline, and the full 300-record run is preceded by a 10-record dry run that exercises the full path under realistic conditions.

### Build phase discipline

The build phase respects four operational principles given the run's product-proof load.

First, the substrate adapter, Inspect AI integration, and receipt-production flow are built and tested independently before being combined. Each has a different failure mode; combining them prematurely means failures compound in ways that are hard to debug.

Second, the harness captures anomalies and edge cases alongside successful operations. If a receipt fails to sign correctly, that's captured. If the verifier rejects a receipt, the rejection reason is logged. If Rekor anchoring is slow or partial, metrics record it. The harness serves as both a research instrument and an integration-test instrument.

Third, the full 300-record run is preceded by a 10-record dry run that exercises the complete path: substrate adapter, evaluation pipeline, receipt production, bundle generation, verifier round-trip. The dry run surfaces integration issues without burning the full corpus and validates that Grafana observability is correctly capturing the operational signal.

Fourth, the 300-record run uses explicit checkpointing. Failure at record N allows resumption from N+1 rather than restart from 1. Grafana real-time visibility ensures failures are caught within minutes, allowing clean checkpoint-and-resume rather than discovering issues at corpus-validation time. Combined with the dry run, this ensures a clean completed run is achievable without depending on perfect first-attempt execution.

## The policy under test

Six rules authored against today's MeshQu rule types (`presence | threshold | list | when` clauses). **One rule is a faithful implementation of a specific named UK statute. The other five are composites synthesised from named real-world frameworks.** The writeup carries the per-rule provenance forward so readers can see exactly which rule is which.

| Rule code | Type | Severity | Provenance | Logic summary |
|---|---|---|---|---|
| `PROC-001-S53` | threshold + when | critical | **Faithful — Procurement Act 2023 s.53(1) + Procurement Regulations 2024 (SI 2024/692) reg. 32 (core content for contract details notices under s.53(1)), with reg. 33 (frameworks), reg. 34 (call-offs under frameworks), and reg. 35 (direct awards) layering specific content requirements on reg. 32(2) for different contract types. Reg. 36 is a separate content specification for below-threshold notices published under s.87(3), not s.53(1), and is therefore outside this rule's scope (see logic summary). The 30-day publication clock in s.53(1) runs from contract signature (120 days for light-touch contracts) per Cabinet Office Procure-phase guidance.** | When `governed_by_pa23 = true` AND `above_threshold = true` (i.e., the contract is a public contract subject to s.53(1) rather than a below-threshold contract subject to s.87(3)) AND a Contract Details Notice exists, `publication_delay_days` (notice publication date minus contract award date) must be ≤ 30. *The contract award date (`awards[0].date`) is used as a proxy for contract signature date, which is what PA23 s.53(1) measures from. The proxy is imposed by substrate limitations — the OCDS feed exposes award decision date, not signature date — and is documented in the substrate-honesty subsection. The rule does not apply to below-threshold contracts, which have a separate publication regime under s.87(3) with a different timing standard ("as soon as reasonably practicable") that is not amenable to a strict numeric threshold check.* |
| `PROC-002-AUTHORITY` | threshold | critical | Composite — UK PA23 delegated-authority frameworks; EU Directive 2014/24/EU Art. 4 thresholds | Contract value above £X requires authority tier ≥ Y |
| `PROC-003-DEBARMENT` | list | critical | Composite — UK PA23 Schedule 6; EU Directive 2014/24/EU Art. 57; FAR 9.4 | Supplier is NOT on the published sanctions / debarment list |
| `PROC-004-COI` | presence | high | Composite — UK PA23 s.81; EU Directive 2014/24/EU Art. 24; FAR 3.101 | `conflict_of_interest_declaration` field must exist |
| `PROC-005-OPEN-TENDER` | threshold + when | critical | Composite — UK PA23 s.19 (competitive tendering as the norm) + s.41 (direct-award circumstances, themselves triggering transparency under s.44 + Procurement Regulations 2024 reg. 26); EU Directive 2014/24/EU thresholds; US FAR | Above-threshold contracts require open competition unless a direct-award justification under s.41 applies |
| `PROC-006-MOD-CAP` | threshold + when | high | Composite — UK PA23 s.74 (substantial modification grounds, including the 10% duration test under s.74(3) and the material change in scope or economic balance limb); UK PA23 Schedule 8 (permitted modifications generally, with the 50% value cap appearing specifically in Schedule 8 para 8 for additional goods/services/works); EU Directive 2014/24/EU Art. 72 (analogous safe harbours, including 50% caps); Procurement Regulations 2024 reg. 40 (contract change notice content) | When `is_modification = true`, `modification_value / original_value` must be ≤ 50% |

### One faithful rule, five composites

The policy under test mixes one faithfully-implemented rule with five illustrative composites. `PROC-001-S53` implements the Procurement Act 2023 s.53 30-day Contract Details Notice publication obligation — a specific statutory time-window rule with binary evaluation against verified OCDS date fields (`awards[0].datePublished` minus `awards[0].date`). The other five rules synthesise shapes from named procurement frameworks (UK PA23, EU 2014/24/EU, US FAR) without being faithful implementations of any one regime. This split lets the experiment surface drift against a precise statutory time-window the agent is unlikely to know correctly, while keeping the other five rules broad enough to fire across the full sample.

The faithful rule is structurally different from the s.44 rule originally drafted: it is a timeliness rule against derived field data, not a presence-and-content rule against linked notices. This shape suits the substrate. Phase 0 / Phase 0.5 spikes confirmed the underlying date fields are stable, well-defined, and populate at 255/255 in the spike corpus.

These get authored in a real MeshQu tenant. Dedicated `experiment` tenant on local Supabase, mirrored to a public-facing tenant for the published bundle. The policy is ratified through the normal flow so it has a real `policy_snapshot_digest` and approval lineage.

The policy is **published as part of the artefact** so readers can inspect the rules independently of MeshQu's UI. The policy_snapshot.json is included in every bundled receipt.

## Substrate analysis preceding pre-registration

The current design is the product of two pre-registration spikes. The discipline is methodological: substrate behaviour gets checked against design assumptions before predictions lock, and design adjusts to what the substrate actually carries.

**Phase 0 (full spike).** Five questions checked against the Contracts Finder OCDS substrate. Three returned failures against the brief's thresholds. (1) PA23/PCR governance regime is not directly identifiable from OCDS fields — 96% of records carry no regime marker; the only reliable proxy is contract award date relative to PA23 commencement (24 February 2025). (2) Transparency notice content for Schedule 5 grounds is not present in any format on Contracts Finder — not in OCDS, not in the HTML award notice, not in linked PDFs. The original faithful rule (PROC-001-S44, Schedule 5 transparency notice) was killed on this finding. (3) The 5×4 award-method × value-band stratification grid was structurally lopsided — 14 of 20 cells under-populated; framework call-offs dominate at 68.6% of records.

**Phase 0.5 (narrow C1 spike).** One question: whether `awards[0].datePublished` carries original publication time or a downstream pipeline timestamp. Three tests resolved it. Re-pull stability: 19/19 records byte-identical across pulls today vs the Phase 0 snapshot. UI parity: 5/5 records' OCDS `datePublished` matches the Contracts Finder web UI's "Published date" string-for-string. Spec sweep: the Crown Commercial Service `ocds_awards_datePublished_extension` defines the field as "The date that the award was published." The Phase 0 clustering observation had a sharper explanation than the artefact hypothesis: the cluster represents a real publication backlog (59 notices on 2026-02-19, 32 on 2026-02-23, 31 on 2026-02-20). The substrate exposes real buyer publication patterns, not pipeline artefacts.

**Design adjustments and documented limitations.** Faithful rule pivoted from s.44 to s.53 (publication-delay timeliness, evaluable from verified OCDS fields). Stratification grid revised from 5×4 to 3×3 reflecting empirical reality. Agent task rescoped to metadata-driven compliance review with brief justification, given thin description text (p50 = 12 description-words). Regime identification documented as a proxy: contract award date after 2025-02-24 is treated as PA23-governed, with the caveat that some procurements may have begun under PCR 2015 transition arrangements. The corpus reports findings on `PROC-001-S53` against the proxy-identified PA23 subset, with records of ambiguous governance reported as a separate subset rather than excluded silently.

A second proxy applies to the s.53 timing computation itself. PA23 s.53(1) measures the 30-day clock from contract signature; the OCDS substrate exposes award decision date, not signature date. The experiment uses `awards[0].date` as a proxy for signature date. Award decision and contract signature are typically close together but legally distinct; findings on `PROC-001-S53` are scoped to this proxy and the methodology surfaces the limitation explicitly.

A third scope decision applies to the sample itself. Below-threshold contracts are excluded from the sample because s.53(1) (the 30-day publication clock) applies to above-threshold contracts only. Below-threshold contracts use a separate publication regime under s.87(3) with different timing semantics. The PROC-001-S53 rule's empirical findings are therefore scoped to above-threshold PA23-governed contracts. This scope is operationalised in the substrate adapter (above-threshold filter on `tender.value.amount` against the relevant PA23 thresholds).

**Above-threshold scope sanity check (performed pre-lock).** Before predictions lock, an operational sanity check was performed against the Contracts Finder OCDS feed to confirm the 3×3 stratification grid is fillable from the above-threshold PA23-governed population. The check pulled 2,900 award notices published between 2025-04-01 and 2026-05-15, filtered to records with `awards[0].date` in the PA23 era (after 2025-02-24), and applied a £139k above-threshold proxy (the sub-central services threshold under PA23 Schedule 1). The check found 120 above-threshold records in the in-window subset, of which 6 were direct awards distributed across the £100k–£1m (4 records) and >£1m (2 records) value bands with zero records in <£100k. This was substantially below the originally-proposed 60-record direct-award floor; the design was adjusted accordingly. The sampling floor was revised to 20 direct-award records (approximately 7% of corpus, calibrated to roughly 4× over-sampling versus natural rate within achievable bounds). The <£100k value band was confirmed structurally near-empty for direct above-threshold records and removed from the per-band floor requirement. P6-C's falsification criterion was recalibrated to acknowledge the modest statistical power (≥10 percentage point disagreement gap to surface clearly; smaller gaps may not be detectable reliably). The 2,900 OCIDs touched during the sanity check are preserved at `procurement-decisions/planning/spike_data/sanity_check_12_ocids.jsonl` (gitignored) for conservative-read exclusion at sample construction time, alongside the Phase 0 and Phase 0.5 exclusion lists.

The Open Contracting Partnership's June 2025 analysis of the first three months of PA23 data ("UK Procurement Act implementation: what does the first three months of data tell us?", <https://www.open-contracting.org/2025/06/23/uk-procurement-act-implementation-what-does-the-first-three-months-of-data-tell-us/>) provides early descriptive statistics on compliance behaviour; this experiment should be read alongside that work — we are not the first empirical analysis of PA23 compliance, only the first to apply audit-grade decision-receipt methodology to AI-assisted compliance review on this substrate.

## Execution environment

The experiment runs against a dedicated MeshQu tenant on the staging environment, isolated from any production data. The tenant is provisioned specifically for this experiment with its own ed25519 signing key. The staging environment runs the same code path as production (Fastify on Railway, PostgreSQL on Supabase, Sigstore Rekor anchoring); the receipts produced are structurally identical to production receipts and verifiable via the published public key.

This isolation serves three purposes. First, the experiment cannot contaminate production data. Second, the dedicated signing key means readers verify the corpus against a key explicitly tied to this experiment rather than a general MeshQu production key. Third, the staging-tenant posture mirrors how the methodology would apply in a deployed environment, making this experiment a faithful rehearsal of the same methodology applied elsewhere.

Every receipt's `source` block carries `environment: "staging"` so the environment is honestly disclosed in the corpus itself. Tenant disclosure works differently: the `MeshQuSource` schema has no `tenant` field ([packages/meshqu-types/src/source.ts](../../packages/meshqu-types/src/source.ts)) because tenant scoping is via the `X-Tenant-ID` request header. Tenant provenance is therefore disclosed two ways instead. First, the writeup states explicitly that the corpus was produced by the `experiment-procurement` tenant on staging. Second, every receipt's `signature_kid` resolves to a public key that is uniquely the experiment's — the kid is cryptographic tenant provenance. A reader cannot misattribute receipts in the published corpus to any other tenant.

**Trust roots arrive via an independent channel.** The experiment's public key ships in the bundle as `trusted_keys.json` for fingerprint comparison, but the verifier (`verify.meshqu.com`) deliberately does not consume bundle-supplied keys as trust roots. Trust roots are sourced from the verifier's own out-of-band registry ([apps/meshqu-verify/src/lib/keys.ts](../../apps/meshqu-verify/src/lib/keys.ts) plus a build-time env var) so a self-signed bundle cannot authenticate itself. The experiment's public key is registered into that registry as a pre-publication step; the writeup names this discipline as part of why bundle verification is meaningful.

## The agent

**Single-model scope.** This experiment tests a single foundation model, pinned to a specific version, at temperature 0. The agent model is selected at build-phase kickoff (see build-phase decision log). The single-model scope is a methodological commitment, not a hedge against future expansion: this first piece tests AI-policy disagreement dynamics with one well-characterised agent rather than introducing model-variance confounders. Multi-model comparison is appropriately located in Follow-up B (the agent context gradient piece), not in this first experiment. The Phase 2 second-run variant referenced in earlier draft material is reframed accordingly — Phase 2 is not in scope for this piece's writeup; it sits in the methodology roadmap as a follow-up direction.

- **Provider**: TBD. pick the most credible foundation model at experiment time
- **Model + version**: pinned exactly. Recorded in DecisionContext `fields.agent_model_id` and `fields.agent_model_version` so they're included in the receipt's integrity hash (`metadata` is stripped before hashing — see [decision_log.md](decision_log.md) 2026-05-14 codebase-audit corrections).
- **Temperature**: 0 (deterministic where the API allows). needed for reproducibility
- **System prompt**: pinned and published as part of the artefact. The system prompt does NOT include the policy text. the agent reasons from first principles + the filing.

The agent is **deliberately not given the policy text**. Two reasons:

1. We want to see the agent's natural compliance reasoning, then check it against the policy. If we hand the agent the rules, the experiment becomes "can the LLM follow rules" — uninteresting.
2. We want to surface **drift** — cases where the agent's reasoning sounds confident but conflicts with the policy. That's the interesting signal.

## The corpus

Target size: **300 receipts** for the first writeup. Enough for statistical signal without being a research paper. Methodology extends to N=1,000 as natural follow-up.

Sampling:

- **Stratified by award method × value band on a 3×3 grid**: `{framework_call_off, first_instance_competitive, direct}` × `{<£100k, £100k–£1m, >£1m}`. Replaces the 5×4 grid originally drafted; the 3×3 reflects the empirical shape of Contracts Finder (framework-dominated, ~68.6% framework call-offs in the Phase 0 spike) and fills cleanly per Phase 0 Q4. Direct-award cells are over-sampled relative to natural rate to give `PROC-001-S53` enough fire events.
- **Time window**: contract award dates in 2025 (corresponds to the post-PA23-commencement period for governance-proxy purposes; see "Substrate analysis preceding pre-registration" below).
- **Above-threshold scope.** The sample is filtered to above-threshold contracts only. Below-threshold contracts are excluded because their publication regime under s.87(3) is structurally different from s.53(1) — different statutory section, different content specification (reg. 36 rather than regs 32-35), different timing standard ("as soon as reasonably practicable" rather than a 30-day cap). The PROC-001-S53 rule's 30-day timing check applies only to s.53(1) contracts; including below-threshold contracts would produce rule firings that are methodologically incorrect. The above-threshold filter is implemented in the substrate adapter based on the `tender.value.amount` or equivalent OCDS field against the relevant PA23 threshold values for the contract's type.
- **Direct-cell floor.** The sampling guarantees a minimum of 20 direct-award records in the 300-record corpus (approximately 7% of total, up from the ~5% natural rate of direct awards in the above-threshold PA23-governed population). This floor is distributed across the £100k–£1m and >£1m value bands with minimum 10 records in each. The <£100k value band is not separately floored for direct awards: above-threshold direct-award records in that band are structurally near-empty (a <£100k contract can only be above threshold if it's a central-government goods/services buy above £90k, and direct awards in that narrow slice are rare). The floor is calibrated to what the Contracts Finder substrate actually supports (see substrate-honesty subsection); the original 60-record floor in pre-sanity-check planning was substrate-incompatible and was revised downward based on empirical findings. P6-C's statistical power on a 20-versus-roughly-280 comparison is modest; the prediction is honest about needing a substantial disagreement-rate gap to surface clearly. The substrate adapter applies this floor at sample construction; if the candidate population at sampling time has fewer than 20 above-threshold direct-award records in the time window, the sampling logic surfaces the constraint as an error rather than silently under-filling cells.

The sample list itself is published as part of the artefact (filing references, not raw documents. we don't redistribute records the open-data licences don't authorise).

## What's measured

Three categories of measurement, all reported in the writeup:

### 1. Volume + verdict distribution

- N receipts produced
- Verdict distribution (ALLOW / DENY / REVIEW / ALERT)
- Rules-fired distribution
- Latency: per-decision evaluation time

### 2. Agent-vs-policy disagreement

The interesting signal. For each receipt:

- Agent's recommended verdict (from its structured output)
- MeshQu's verdict (from the evaluator)
- Agreement / disagreement

When they disagree:

- **Agent says ALLOW, MeshQu says DENY**: the agent rationalised past a rule. This is the "drift" case the writeup leans on.
- **Agent says DENY, MeshQu says ALLOW**: the agent flagged something the policy doesn't actually prohibit. Less interesting but worth surfacing.
- **Agent says REVIEW, MeshQu says ALLOW** (or vice versa): grey zone. Reported but with caveats.

### 3. Reproducibility

A subset of decisions (say 10%) are **re-run** with the same input + same snapshot. Same verdict = reproducibility holds. Different verdict = the LLM is non-deterministic on this input. Publishing these numbers honestly is part of the credibility argument.

A second subset is **replayed** through the meshqu-verifier CLI from the bundled archive, confirming that the bundle round-trips offline.

Reproducibility does not depend on the original execution environment. A reader cloning the repository can run the harness against the published policy snapshot using their own MeshQu instance (production, staging, or local) and produce a corpus that round-trips through verify.meshqu.com identically — the receipt verification flow uses the bundled public key, not a particular environment's trust anchors. The original corpus was generated in MeshQu's staging environment against a tenant provisioned specifically for this experiment.

## Human review pass

A sample of disagreement cases (target N=30) is reviewed by the experimenter against the published procurement frameworks. For each:

- Does the human agree with the agent or with MeshQu?
- What's the underlying disagreement type? Rule interpretation. Data quality. Agent hallucination. Policy gap.

This is not independent expert review. Cases where rule interpretation is genuinely contested are flagged as such rather than adjudicated. A skeptical reader who wants stronger ground truth knows to discount accordingly.

Honest framing is stronger than hedged framing. The same phrasing appears in the writeup's limitations section.

## What gets published

In order of importance:

1. **Blog post** at `meshqu.com/research/procurement-decisions/` — narrative writeup with charts.
2. **Open repo** at `github.com/meshqu/meshqu-research`, specifically the `procurement-decisions/` directory — agent harness, MeshQu client wiring, evaluation scripts, sample selection criteria, system prompts.
3. **Methodology layer** at `github.com/meshqu/meshqu-research/methodology/` — substrate adapter pattern, evaluation pipeline (Inspect AI integration), policy authoring playbook. Reusable across future research pieces and client engagements.
4. **Receipt corpus** as a downloadable bundle (tar) at `meshqu.com/research/procurement-decisions/corpus.tar`. Reader drops it into verify.meshqu.com.
5. **Policy snapshot JSON** alongside the corpus, so readers can inspect the rules.
6. **Pre-registration commit hash + timestamp** linked from the writeup — points at the locked-predictions commit in the public `meshqu-research` repo.
7. **Raw agent outputs** (anonymised if needed) so readers can audit the LLM's reasoning, not just the structured verdicts.
8. **Grafana screenshots** in `procurement-decisions/results/observability/` documenting operational behaviour during the run (see "The experiment as MeshQu product proof" subsection above).

## What does NOT get published

- Any data outside the open-data licence of the source.
- The MeshQu signing private key (obviously). The published `trusted_keys.json` is the public-key half only.
- Internal MeshQu URL paths or admin credentials.

## Honest limitations the writeup names

- The policy mixes one faithful rule (`PROC-001-S53` — Procurement Act 2023 s.53 30-day Contract Details Notice publication obligation) with five illustrative composites. The composites are not certified by any one regulator. The faithful rule is not a substitute for an independent procurement-law expert's interpretation; it's a good-faith implementation of the statutory time-window plus published secondary analysis.
- Governance regime (PA23 vs PCR 2015 transition arrangements) is identified via a contract-award-date proxy (post-2025-02-24 → PA23), not a direct OCDS field. The proxy is documented; `PROC-001-S53` findings are scoped to the proxy-identified PA23 subset.
- The agent is a single foundation model at a single version. Results may not generalise.
- Human review is by the experimenter, not an independent procurement-law expert.
- The sample is biased toward UK / English-language records if UK Contracts Finder is the primary substrate.
- Receipts validate the *integrity* of the decision, not the *correctness* of the policy. A flawed policy correctly enforced still produces a clean receipt.

Stating these up-front is the credibility move. Defensive writeups that hide limitations get torn apart by skeptical readers; honest ones earn trust.
