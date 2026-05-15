# Decision Log

> Reverse-chronological journal of design decisions. Append new entries at the top.
> Each entry: date, decision, alternatives considered, reason picked.

---

## 2026-05-15 — Predictions locked

**Decision**: predictions in [`procurement-decisions/planning/predictions.md`](predictions.md) are locked against the experiment design at this commit hash. From this commit forward, the experiment design is fixed; all downstream artefacts (corpus, review pass, writeup) are evaluated against the design at this state.

**Locked predictions**:

- P1: agent-policy disagreement rate
- P2: rule-firing distribution (PROC-001-S53 expected top driver)
- P3: hallucinated citations rate
- P4: reproducibility band (5–20% expected non-determinism)
- P5: bundle round-trip success (100% expected)
- P6-C: disagreement clusters on direct-award procurements (10pp falsification threshold; sample size scope: ≥20 direct-award records, ≥100 competitive-procurement records)
- P7: agent treats notice existence as compliance evidence

**Pre-lock state of the design**:

- Twelve revision briefs applied (briefs 1-9 in initial commit; brief 10 deferred to build-phase as execution capture conventions; brief 11 as PR #1; brief 12 as PR #2)
- Pre-lock editorial cleanup committed as PR #3 (Stripe-style borrowed positioning removed; Sam's-call placeholders resolved; no substantive content changes)
- Two formal spike phases completed (Phase 0, Phase 0.5)
- Personal citation verification of Procurement Regulations 2024 regs 32-36 against legislation.gov.uk
- Pre-lock substrate sanity check (2,900 records pulled; OCID exclusion list at `planning/spike_data/sanity_check_12_ocids.jsonl`)
- Single-model scope committed; multi-model deferred to Follow-up B
- 24-hour cool-down completed with briefs 11, 12, and the editorial cleanup as substantive pre-lock revisions

**Explicitly NOT locked (deferred to later stages)**:

- Specific foundation model selection — deferred to build-phase kickoff per single-model commitment
- Threshold values for above-threshold filter — deferred to build-phase verification against current Statutory Instruments under PA23 s.18
- Empirical results in P1–P5 and P7 falsification criteria — these are filled in post-run, not at lock time

**Tag**: `v0.1-predictions-locked` (applied as a separate operation after this commit lands)

**Reason for locking**: the experiment design has reached the point where further refinement is unlikely to change the predictions. The cool-down surfaced three substantive revisions (briefs 11, 12, editorial cleanup) — that was its purpose. The substrate has been empirically checked. The legal precision has been verified. The methodology is fully specified. The language is at final state. Locking now means the build phase, dry run, full run, and human review pass all proceed against a fixed design. Findings get evaluated against this committed state.

**What's next**:

1. Build phase begins with revision brief 10 (execution capture conventions) as the first operation
2. Phase A foundation work: staging tenant provisioning, verify.meshqu.com trust registry update, Grafana dashboard scoping, end-to-end smoke test
3. Phase B harness build: UK Contracts Finder substrate adapter, policy authoring in MeshQu, Inspect AI evaluation pipeline, sampling and notice-ID freezing
4. Phase C dry run (10 records)
5. Phase D full run (300 records) + reproducibility re-run (30 records)
6. Phase E bundle and verify round-trip
7. Phase F human review pass (30 disagreement cases)
8. Phase G writeup drafting
9. Phase H publication

---

## 2026-05-15 — Pre-lock editorial cleanup

**Decision**: swept the planning harness for working-language artefacts, borrowed positioning, and resolved-but-not-updated placeholders. Editorial polish only; no substantive content changes.

**Changes applied**:

- **"Stripe-style" borrowed positioning** replaced with direct descriptions of the work's actual character ("practitioner-direct commercial research report", "founder-direct voice, technical readers"). Forward-facing harness files updated: [`README.md`](README.md), [`writeup_outline.md`](writeup_outline.md) (3 references: opening line, byline rationale, voice-check step). Historical decision_log entries documenting the original 2026-05-14 positioning decision are preserved verbatim — they record what was decided at the time and shouldn't be retrospectively edited. The resolved-list at-a-glance summary is updated to reflect the cleaned wording with a back-reference to the original entry.
- **"Sam's call" placeholders** resolved in the spike reports via appended resolution notes rather than editing original status lines. Phase 0 spike report records the GO WITH ADJUSTMENTS verdict and the three design pivots that followed. Phase 0.5 C1 spike report records that the date-semantics proxy was committed in revision brief 11. Spike reports are preserved as historical artefacts; resolution notes resolve the placeholders without rewriting the original findings.
- **Pending-list cleanup**: the "Direct-cell over-sampling floor for PROC-001-S53" item is struck through, resolved by revised brief 12 (20-record floor). The "legislation.gov.uk verification of regs 32-36" item is struck through, resolved pre-lock via revision brief 11. The "Specific foundation model" item stays pending — that decision is genuinely deferred to build-phase kickoff.
- **General sweep** for working-language artefacts (`I'm thinking`, `we discussed`, etc.) and cross-reference drift returned no findings — the harness was kept clean during planning.

**Forward-looking notes that look like pending items but are not**: the `substrate.md` `above_threshold` field has a "to be confirmed at build-phase time" note for the actual statutory-instrument threshold values. The `predictions.md` TBDs are placeholders for empirical results that don't exist until the experiment runs. The `experiment_design.md` agent-provider TBD is a build-phase decision. None of these are pre-lock pending; they're correctly forward-looking and left as-is.

**Source**: identified during pre-lock consistency read — initially "Stripe-style" and "Sam's call", broadened to a single focused sweep to avoid finding more items one at a time over subsequent exchanges.

**Reason**: the locked design should read as genuinely final. Editorial scaffolding from planning shouldn't survive into the locked state. This is the final pre-lock cleanup; predictions lock follows as the next commit.

---

## 2026-05-15 — Revision brief 12 (revised): direct-cell floor calibrated to substrate; sanity check past tense; single-model commitment

**Decision**: three pending items from the planning phase closed before predictions lock, calibrated to the empirical substrate composition surfaced by the pre-lock sanity check:

1. **Direct-cell floor**: minimum 20 direct-award records in the 300-record corpus (approximately 7% of corpus, ~4× natural rate; distributed at minimum 10 records each in £100k–£1m and >£1m value bands; no floor for <£100k which is structurally near-empty for above-threshold direct awards). This revises the original brief 12 proposal of 60 records, which the sanity check revealed was substrate-incompatible.
2. **Above-threshold scope sanity check**: performed against Contracts Finder pre-lock; pulled 2,900 records published 2025-04-01 to 2026-05-15; filtered to PA23-era awards (≥ 2025-02-24); applied £139k above-threshold proxy. Found 120 above-threshold records in-window of which 6 were direct awards. Design adjusted accordingly. Documented past tense in the substrate-honesty subsection.
3. **Single-model commitment**: the first piece tests a single foundation model only. Multi-model comparison relocated from "Phase 2 second-run variant" to Follow-up B (agent context gradient), where it sits alongside the context gradient as natural future-piece extensions.

**Source of findings**:

- Outstanding pending items identified in the brief 11 status report and predictions-lock sequencing notes.
- Above-threshold sanity check performed by the harness operations engineer pre-lock; full data preserved at `/tmp/sanity-check-12/` at execution time and OCID list at `procurement-decisions/planning/spike_data/sanity_check_12_ocids.jsonl` (gitignored) for conservative-read exclusion at build time.

**Alternatives considered**:

- Lower the floor to 30 records as originally proposed. Rejected — substrate sanity check found only 6 above-threshold direct-award records in the 2025 sample, and even with broader time window the population is too thin to support 30 reliably.
- Drop above-threshold scope from brief 11 to broaden the direct-award population. Rejected — reverses brief 11's correctness gain; s.53(1) vs s.87(3) is a real statutory distinction that the harness was correct to honour.
- Pivot the faithful rule from PROC-001-S53 to PROC-001-SME. Rejected — would require rewriting P6-C and P7 from scratch and losing the elegant s.44/s.53 theoretical prior.
- Lower the floor to 20 records calibrated to actual substrate composition. **Chosen** — preserves brief 11's correctness gain, preserves PROC-001-S53 as the faithful rule, preserves P6-C's theoretical prior, accepts modest statistical power as the honest cost of substrate constraint.

**Reason**: the cool-down's purpose was to surface and resolve exactly this kind of ambiguity. The substrate sanity check did its job: locking against a 60-record floor would have failed at build time. The 20-record floor is what the substrate can credibly support. P6-C's falsification criterion is recalibrated to ≥10 percentage point difference (revised from ≥5 points) to acknowledge the modest statistical power. The honest framing strengthens the methodology narrative — the experiment scopes to what the substrate empirically supports rather than to an externally-imposed target.

**Impact assessment**: affects sampling (20-record direct floor with band distribution), substrate adapter (floor enforcement plus the conservative-read exclusion list), PROC-001-S53 (no rule-level change; still scoped to above-threshold), P6-C falsification (10-point threshold; sample size scope explicit), Follow-up B framing (multi-model dimension named), section 7 limitations (both substrate-power and sanity-check-exclusion bullets added). Build-phase implication: substrate adapter implementation must enforce the 20-record floor and apply the sanity-check-12 exclusion list alongside Phase 0 and Phase 0.5 exclusions. Agent selection at build kickoff pins one model at one version with temperature 0.

---

## 2026-05-15 — Revision brief 11: PROC-001-S53 scope corrected to above-threshold; reg. 36 framing tightened

**Decision**: PROC-001-S53 rule scope narrowed to above-threshold PA23-governed contracts only. Below-threshold contracts excluded from the 300-record sample. Reg. 36 framing in the provenance entry updated to distinguish reg. 36 (separate spec for below-threshold notices under s.87(3)) from regs 33-35 (which layer on reg. 32 for s.53(1) notices).

**Source of finding**: Sam's personal citation verification against legislation.gov.uk during the predictions-lock cool-down. Confirmed regs 32-35 substantively accurate as described in the harness; identified that the harness's framing did not distinguish reg. 36's structural difference (self-contained spec for below-threshold notices under s.87(3), not layered on reg. 32) and that PROC-001-S53 as written would fire incorrectly on below-threshold contracts.

**Alternatives**:

- Keep PROC-001-S53 scope as-is and treat below-threshold misfirings as a known methodological limitation. Rejected — undermines the rule's evaluation discipline; below-threshold disagreement findings would be methodologically suspect.
- Create a separate rule (PROC-001b-S87) for below-threshold publication timing under s.87(3). Rejected — s.87(3)'s "as soon as reasonably practicable" standard is not amenable to a strict numeric threshold check; not a good fit for a faithful rule in the experiment's first piece.
- Scope the sample to above-threshold contracts only. **Chosen** — operationally simple, methodologically clean, preserves the PROC-001-S53 rule's evaluation integrity.

**Reason**: the citation verification did its job: surfacing a real but bounded scope issue before predictions lock. The fix is small (sampling filter + provenance phrasing) and preserves the rule's interpretive accuracy. The honest disclosure that the experiment scopes to above-threshold contracts strengthens the methodology narrative; it makes the substrate-honesty discipline complete (three documented proxies / scope decisions now: regime, signature date, above-threshold).

**Impact assessment**: the change affects the substrate adapter (new `above_threshold` filter), the sampling logic (now applies the filter before stratification), the PROC-001-S53 rule logic (now has an above-threshold trigger condition), and the methodology subsection's substrate-honesty paragraphs (now documents the third scope decision). The 300-record target is unchanged but applies to the above-threshold subset. Below-threshold disagreement findings, if any were observed in the corpus, would not be valid under PROC-001-S53 — they are now scope-excluded.

**Build-phase implication (not addressed in this brief)**: PA23 Schedule 1 threshold values themselves need explicit numeric capture in the substrate adapter code at build time, with citation to the source SI under PA23 s.18. This is implicit in the brief and explicit in the build phase.

---

## 2026-05-15 — Legal review tightening applied before predictions lock

**Decision**: three tightening points applied in response to external legal review of the harness's citation provenance and proxy claims. None is a substantive error; all strengthen the credibility argument by being precise about what the underlying law actually says.

**The three points**:

1. **PROC-001-S53 names the award-date-as-proxy-for-signature-date relationship.** PA23 s.53(1) measures the 30-day clock from contract signature; the OCDS substrate exposes award decision date, not signature date. The rule's logic summary, the substrate-honesty subsection, and the substrate.md derivation note all now name this proxy explicitly. Award decision and contract signature are typically close together but legally distinct.
2. **PROC-006-MOD-CAP provenance expanded to map the 10% and 50% figures to their actual statutory sources.** The 10% figure is one limb of the substantial modification test in s.74 and relates specifically to contract *duration* (s.74(3)). The 50% figure comes from Schedule 8 para 8 (additional goods/services/works), not from the general definition of substantial modification. Provenance now names both elements separately rather than implying a single integrated definition.
3. **Approximate phrasings tightened.** "Open procedure as default" (s.19) → "competitive tendering as the norm" (closer to literal statutory text). "Strict version pinning" (Inspect AI) → "explicit model selection and configuration" (strictness depends on provider configuration, not Inspect's own functionality).

**Reason**: the review surfaced no substantive errors but identified places where harness phrasing was slightly stronger than underlying law supported. The discipline pattern of naming proxies explicitly (already applied to governance regime identification in revision brief 5) extends naturally to the s.53 timing proxy. Predictions lock against the tightened design rather than retrofitting at writeup time.

**Cross-references propagated**: experiment_design.md (rule table for PROC-001-S53, PROC-005-OPEN-TENDER, PROC-006-MOD-CAP; Inspect AI paragraph; substrate-honesty subsection second-proxy paragraph), substrate.md (DecisionContext mapping `contract_award_date` derivation note), writeup_outline.md (§4 two-proxies sentence; §7 limitations bullet for the timing proxy).

---

## 2026-05-15 — P6 selected: award method cross-cut on the s.44/s.53 distinction

**Decision**: P6-C is committed as the single P6 entry in [predictions.md](predictions.md). The agent-policy disagreement rate on `PROC-001-S53` is predicted to be meaningfully higher for direct-award procurements than for competitive procurements (open tender, restricted, framework call-offs), within the proxy-identified PA23 subset. Falsification: <5 percentage point difference.

**Alternatives considered**:

- **P6-A — buyer-organisation-type cross-cut** (local-authority vs central-government). Rejected: drifts toward procurement sociology and operational maturity variation, weakening the central thesis. The theoretical prior is real but doesn't directly test the experiment's core claim about AI-assisted compliance review.
- **P6-B — value-band cross-cut** (small <£100k vs large >£1m). Rejected: introduces confounders around organisational diligence and weakens the theoretical anchor. The prior assumes a relationship between contract size and procurement-workflow attention that's plausible but not statute-anchored.
- **P6-C — award-method cross-cut** (direct vs competitive). **Selected.** Directly tests whether the agent confuses publication existence with publication compliance — exactly the failure mode the MeshQu thesis ("reconstruction is not proof") is built to address. Anchors the experiment to the specific PA23 dynamic where the drift case is most semantically interesting.

**Reason**: P6-C and P7 form a coherent explanatory pair — P6 identifies *where* disagreement clusters (direct awards), P7 identifies the *mechanism* (agent treats publication existence as compliance evidence without recognising the 30-day cap). The choice also produces the strongest worked example for the writeup's section 5b: a six-step cryptographic trace from procurement award through receipt preservation that demonstrates the MeshQu thesis in microcosm. The failure mode P6 surfaces is not irrational, random, or hallucinated — it is semantically plausible but procedurally incorrect, which is exactly the kind of failure operationally dangerous in production deployment.

**Status**: P6-A and P6-B removed from predictions.md. The predictions file has no remaining P6 ambiguity. The 24-hour cool-down on predictions lock starts from this commit landing.

---

## 2026-05-15 — Planning harness extracted to public `meshqu-research` repo before predictions lock

**Decision**: the planning harness moves from `[monorepo]/.harness/agentic-procurement-experiment/` to `meshqu-research/procurement-decisions/planning/` in a new public GitHub repo under the `meshqu` org. Initial commit is the current state of the planning harness with a clear lineage commit message. From that commit forward, work happens in the public repo. The monorepo's `.harness/agentic-procurement-experiment/` directory is either deleted or replaced with a stub pointing at the public repo (recommend delete to avoid drift).

**Alternatives considered**:

- Stay in the monorepo through build and extract before publication. Rejected: the pre-registration commit needs to be publicly auditable from the moment predictions lock; an extract-later flow forfeits that property because external readers cannot verify a commit they cannot see.
- Set up complex monorepo↔public-repo mirroring. Rejected: adds tooling overhead without solving the core issue. The work belongs in one place; that place is public from predictions-lock onward.

**Reason**: pre-registration discipline depends on the locked commit being verifiable by external readers from the moment it lands. The public repo from day one of predictions lock makes that work cleanly. As a side benefit, the public repo also gives the methodology layer (next entry) a natural home.

---

## 2026-05-15 — Repo structure separates `procurement-decisions/` from `methodology/`

**Decision**: `meshqu-research` is structured as `procurement-decisions/` (this experiment, including planning, runner, policy, results, writeup) alongside `methodology/` (substrate adapter, evaluation pipeline, policy authoring playbook). The `methodology/` directory is empty at planning time and gets populated during the build phase as components are written. The procurement-decisions piece is the first consumer; future research pieces and client engagements depend on the same methodology layer.

**Alternatives considered**:

- Collapse methodology into the procurement-decisions piece. Rejected: couples reusability to a specific piece, makes future extractions harder, weakens the methodology-as-public-research framing.
- Set up methodology in a separate repo entirely. Rejected: adds friction without clear benefit when both surfaces are public. Same-repo separation enforces the abstraction architecturally without requiring cross-repo dependency tooling.

**Reason**: same-repo separation enforces the abstraction architecturally from day one. The methodology compounds across pieces; the procurement-decisions piece is the first consumer; the structure visible at the repo root explains the public/private split (methodology public, engagements private) at a glance.

**Sam's operational checklist for the extraction (before predictions lock):**

- [ ] Create `meshqu` GitHub organisation if it doesn't exist.
- [ ] Create `meshqu-research` public repo with MIT or Apache-2.0 license (either defensible).
- [ ] Initial commit: mirror current state of `.harness/agentic-procurement-experiment/` to `meshqu-research/procurement-decisions/planning/`. Single squash commit, message: "initial commit: agentic procurement experiment planning harness, mirrored from MeshQu monorepo. Includes Phase 0 + Phase 0.5 spike reports, six revision briefs, decision log, and full planning artefacts. See decision_log.md for design lineage."
- [ ] Verify `spike_data/` directories are gitignored and contain nothing sensitive (re-check for buyer/supplier names that might warrant redaction even though procurement data is mostly public).
- [ ] Draft a top-level `meshqu-research/README.md` explaining the research surface (small but worth getting right — first thing a visitor reads).
- [ ] Update internal monorepo references that point at `.harness/agentic-procurement-experiment/` to point at the public repo.
- [ ] Decide whether to delete the monorepo's `.harness/agentic-procurement-experiment/` directory or replace with a stub. Recommend delete.

---

## 2026-05-15 — Prometheus instrumentation verified production-equivalent on staging before the run

**Decision**: the Grafana dashboards specified in the product-proof subsection depend on Prometheus-style metrics exposed by the underlying services. Before the build phase starts, an instrumentation audit verifies that signing operations, Rekor anchoring, database writes on the receipt path, and Fastify application-level metrics all expose the right histograms, counters, and labels (especially `tenant`) to support the dashboards. Gaps are closed via small instrumentation PRs.

**Specific metrics required**:

- `meshqu_signing_requests_total{tenant, result, error_type}` (counter) and `meshqu_signing_duration_seconds{tenant}` (histogram, sub-millisecond to second buckets).
- `meshqu_rekor_requests_total{result, error_type}` (counter) and `meshqu_rekor_duration_seconds` (histogram, wider buckets reflecting external-dependency variance: 0.05s up to 30s).
- Standard PostgreSQL pool metrics (active/waiting/max connections, exhaustion events) plus `meshqu_receipt_write_duration_seconds{tenant}` and `meshqu_receipt_write_errors_total{tenant, error_type}`.
- Standard Fastify Prometheus metrics: request count and duration histogram by route and status code.

**Alternatives considered**:

- Rely on existing instrumentation as-is. Rejected: gaps in `tenant` labelling and signing-specific histograms would mean the dashboards either didn't filter to the experiment tenant or didn't have sufficient latency resolution.
- Skip the instrumentation audit and treat any gaps as build-phase issues. Rejected: discovering instrumentation gaps mid-run is much more expensive than catching them pre-build, and the product-proof claim depends on the dashboards meaning what they appear to mean.

**Reason**: the product-proof claim depends on observability being real, not aspirational. Verifying instrumentation pre-build ensures Grafana visibility is meaningful, the screenshots in writeup Appendix B actually show what they claim to show, and the operational dimension of the experiment is supported by real telemetry.

**Sam's operational checklist for the audit (before build phase):**

- [ ] Audit current Prometheus instrumentation on the staging MeshQu deployment against the metrics list above. Confirm what exists, what's labelled with `tenant`, what's missing.
- [ ] For missing metrics or missing labels, add instrumentation as small PRs (typically 1-5 lines per metric with the right library setup).
- [ ] Verify Grafana can filter dashboards to the experiment tenant once provisioned. If existing platform dashboards aren't tenant-filterable, build a scoped dashboard (revision brief 6 operational checklist).
- [ ] During the 10-record dry run, validate that all four metric surfaces are visible in Grafana before committing to the full 300-record run.

---

## 2026-05-15 — Citation cluster anchored for PROC-001-S53

**Decision**: PROC-001-S53 provenance now references PA23 s.53(1) plus Procurement Regulations 2024 (SI 2024/692) reg. 32-36 specifically. The 30-day publication window is operationalised through s.53(1); reg. 32 specifies core content; reg. 33-35 layer framework / call-off / direct-award specifics; reg. 36 handles below-threshold. Cabinet Office Procure-phase guidance ("Contract Details Notices and Contract Documents", <https://www.procurementpathway.civilservice.gov.uk/documents/guidance/contract-details-notices-and-contract-documents/>) confirms the 30-day clock runs from contract signature (120 days for light-touch contracts).

**Sources**: Perplexity research output 2026-05-14; verification against legislation.gov.uk (regs 33-36 URLs in revision brief 6) pending Sam personally before predictions lock.

**Reason**: closes the previously-pending Procurement Regulations 2024 citation item; anchors the rule provenance specifically rather than citing the SI in the abstract.

---

## 2026-05-15 — Inspect AI selected as evaluation framework

**Decision**: the evaluation pipeline is built on Inspect AI (UK AI Safety Institute framework, <https://ukgovernmentbeis.github.io/inspect_evals/>). Multi-provider model access (OpenAI, Anthropic, Google, Mistral, HF Inference), strict version pinning, temperature control, structured output enforcement, evaluation traces. Substrate adapter still produces normalised `DecisionContext` payloads; Inspect AI handles the evaluation loop.

**Alternatives considered**:

- Direct API calls. Rejected: lacks evaluation primitives, harder to make reproducible across providers.
- LangChain or LlamaIndex. Rejected: agent-orchestration frameworks, not evaluation frameworks. Would add complexity without matching the experiment's actual needs.
- DSPy. Rejected: prompt-optimisation framework, not the right shape for a controlled experimental comparison.

**Reason**: Inspect AI is purpose-built for systematic LLM evaluation across providers. The UK AI Safety Institute origin is a small but real credibility signal for a piece that's already leaning into UK government policy framing.

---

## 2026-05-15 — Experiment positioned as product proof, not just research

**Decision**: the experiment is explicitly triple-duty work — research credibility, methodology infrastructure development, and production-scale product proof. The build phase respects this with operational discipline (independent component build-and-test, 10-record dry run before full run, explicit checkpointing, anomaly capture). New "The experiment as MeshQu product proof" subsection in `experiment_design.md` makes this visible to the reader; new "Build phase discipline" subsection records the operational principles.

**Alternatives considered**:

- Position purely as research. Rejected: undersells the product-evidence value of a 300-record signing-and-anchoring run on real external substrate. Most decision-receipt demonstrations are synthetic-data demos that don't exercise real-world variability or single-decision examples that don't exercise sustained load.
- Position purely as product demonstration. Rejected: undersells the research methodology and weakens the pre-registration credibility argument.

**Reason**: the same artefact does all three jobs. Making this explicit means the build phase is planned with appropriate operational discipline rather than treating the production-load dimension as incidental.

---

## 2026-05-15 — Grafana observability captured as product-proof evidence

**Decision**: the experiment run is monitored in real time via Grafana dashboards scoped to the experiment tenant on staging. Dashboards cover signing operations (rate, latency p50/p95/p99, failure count), Sigstore Rekor anchoring (rate, latency, failure count), database write throughput, and Fastify application-level error rates. Screenshots captured during the 10-record dry run and the full 300-record run are preserved as supporting evidence in **Appendix B** of the published artefact.

**Alternatives considered**:

- Rely on application logs alone. Rejected: less visible during the run, harder to demonstrate operational behaviour to a reader. Logs are time-series text; dashboards are at-a-glance evidence.
- Do without observability captures. Rejected: undersells the product-proof dimension by omitting the operational evidence that's already available — Grafana is already deployed on staging.

**Reason**: Grafana on staging means observability infrastructure already exists. Using it deliberately for the run produces operational evidence that strengthens the product-proof dimension at no additional cost. Screenshots become part of the published artefact alongside the receipt corpus.

---

## 2026-05-14 — Faithful rule swap: PROC-001-S44 → PROC-001-S53

**Decision**: `PROC-001-S44` is retired. The faithful rule is now `PROC-001-S53` — the Procurement Act 2023 s.53 30-day Contract Details Notice publication obligation, operationalised by the Procurement Regulations 2024 (specific regulation number to confirm at writeup time). The "one faithful rule, five composites" framing survives intact; only the rule identity changes.

**Alternatives considered**:

- Drop the faithful framing entirely (path 2). Viable but materially weaker than the original two-tier framing — composites alone don't anchor the writeup against statutory text.
- Reopen the substrate question (path 3). Expensive, uncertain payoff, and unnecessary given that the Phase 0.5 C1 spike returned VIABLE.
- Pick a different candidate (C2 framework-term cap or C3 SME-suitability honesty). C2 dead per spike findings; C3 viable on data but s.85/s.86 are duty-of-consideration provisions, not binary statutory obligations — "faithful" framing weakens.

**Reason**: the Phase 0.5 C1 spike confirmed `awards[0].datePublished` is original publication time (re-pull stability 19/19 byte-identical, UI parity 5/5 exact match, CCS OCDS extension `ocds_awards_datePublished_extension` defines the field as "the date that the award was published"). The 246/255 records breaching the 30-day cap in Phase 0 is real buyer-publication-delay behaviour, not a pipeline artefact. The 30-day cap is a clean, specific, theoretically-anchored faithful rule with strong drift potential. Median publication delay in the spike sample was 136 days — a substantive empirical hook for the writeup's §5b worked example.

---

## 2026-05-14 — Exclusion list scope: conservative read adopted

**Decision**: all records inspected during Phase 0 or Phase 0.5 spikes are excluded from the eventual 300-record pre-registered corpus. Total exclusion ≈ 262 records (the 255 in `spike_data/releases.jsonl` plus the 38 individually inspected from Phase 0 plus the 19 re-pulled in Phase 0.5 plus the 5 UI-checked in Phase 0.5, with overlap; Phase 0.5 added 4 net-new OCIDs over Phase 0 Appendix A).

**Alternatives considered**:

- Strict read (~60 records, only individually inspected). Preserves more of the available pool. Rejected: the methodology benefit of "no spike-inspected record made it into the pre-registered corpus" is real and the strict read forfeits it.

**Reason**: the year-window has tens of thousands of available records. 262 excluded is rounding error against a corpus that needs 300. Any reader auditing the methodology can verify that the spike samples and the pre-registered corpus are disjoint.

---

## 2026-05-14 — Regime identification via contract-award-date proxy

**Decision**: PA23 vs PCR 2015 governance is identified via `awards[0].date > 2025-02-24` as a proxy, since Contracts Finder OCDS records do not carry an explicit governing-regime field (Phase 0 Q1: 96% no-signal).

**Alternatives considered**:

- Exclude records with ambiguous governance from the corpus entirely. Rejected: would over-restrict the sample given the no-signal rate.
- Infer regime from procedure-type codes. Rejected: adds methodology surface without resolving the ambiguity — the OCDS PMD vocabulary used by Contracts Finder is largely PCR-2015-style regardless of regime.

**Reason**: the proxy is honest, documented in `experiment_design.md` "Substrate analysis preceding pre-registration" and `substrate.md`, and the `PROC-001-S53` findings are scoped to the proxy-identified PA23 subset rather than claimed to apply universally. Records with ambiguous governance (e.g. contracts awarded close to commencement where PCR transition arrangements may apply) are reported as a separate subset in the writeup.

---

## 2026-05-14 — P6 reformulation: three options pending Sam's pick

**Decision (pending)**: P6's cross-cut variable is chosen from three reformulation options sketched in [predictions.md](predictions.md):

- **P6-A** — disagreement varies by buyer-organisation type (local-authority vs central-government).
- **P6-B** — disagreement varies by value band (small <£100k vs large >£1m).
- **P6-C** — disagreement varies by award method (direct vs competitive). Closest reformulation to the original direct-award-anchored P6.

**Reason**: with `PROC-001-S53` as the faithful rule, the original P6's direct-award cross-cut is no longer the most informative cut. Each option represents a different theoretical prior about *why* disagreement should vary; the choice affects what the experiment is most informative about.

**Status**: open. Sam picks one before the 24-hour cool-down on predictions lock. The other two are removed from `predictions.md` at lock time.

---

## 2026-05-14 — Codebase-audit corrections to four prior assumptions

A pre-build audit cross-checked the harness's claims against the actual code. Four corrections follow; older entries below describe the prior (wrong-in-some-detail) state and remain as history.

**1. Agent provenance lives in `fields`, not `metadata`.** The integrity hash payload includes everything in `fields` and excludes `metadata` ([packages/meshqu-core/src/integrity.ts](../../packages/meshqu-core/src/integrity.ts)). The earlier "system prompt hash bound in receipt; prompt published" decision implied the binding went through `metadata`; it does not. All agent-provenance fields (`agent_model_id`, `agent_model_version`, `agent_temperature`, `agent_prompt_sha256`, `agent_reasoning`, `agent_recommended_verdict`, `agent_recommended_action`) now sit in `fields` so the writeup's cryptographic-binding argument actually holds. `metadata` carries operational annotations only — experiment ID, source dataset, derivation notes.

**2. No `tenant` field in `source`.** The `MeshQuSource` schema has only `service`, `environment` (enum: `production | staging | shadow | development`), `region?`, `version?` — no `tenant` ([packages/meshqu-types/src/source.ts](../../packages/meshqu-types/src/source.ts)). Tenant scoping is via the `X-Tenant-ID` request header. The earlier "every receipt's `source` block carries `tenant`" claim was wrong. Tenant provenance is disclosed two ways instead: (a) prose in the writeup names the `experiment-procurement` staging tenant; (b) every receipt's `signature_kid` resolves to a public key that is uniquely the experiment's, so the kid IS cryptographic tenant provenance. No design change beyond removing the field — actually a stronger disclosure story.

**3. Rekor anchoring is gated by GLOBAL `config.transparencyEnabled`, not per-tenant.** Confirmed at [apps/meshqu-api/src/services/decision-service.ts:670-675](../../apps/meshqu-api/src/services/decision-service.ts#L670-L675) and `packages/meshqu-core/src/transparency.ts`. Flipping the flag affects the whole staging environment, not just `experiment-procurement`. Operational implication: if other staging tenants exist, confirm with their owners that enabling transparency is acceptable, or coordinate the experiment run during a known-empty staging window.

**4. Drafts produce no `policy_snapshot_digest`.** `snapshot-service.ts:232-237` hard-fails on unratified versions. Phase 3 must ratify the experiment policy BEFORE any decisions are recorded; running decisions against a draft is not a silent fallback to a null digest — it's a hard error. Adding to the operational checklist explicitly.

**Confirmed as drafted (no change):**
- `source_artifact` is a real top-level field with `type / hash / hash_algorithm / byte_size / reference_id? / filename?` — bound into the integrity hash via `source_artifact_hash` ([packages/meshqu-core/src/integrity.ts](../../packages/meshqu-core/src/integrity.ts)).
- `GET /v1/receipts/:id/bundle?format=tar` exists; bundles `receipt.json`, `policy_snapshot.json`, `trusted_keys.json` plus conditionally `policy_approval_receipts.json` (when snapshot has approval lineage) and `evidence_manifest.json` (when evidence is bound).
- Rate limits: 1000/60s post-auth ([apps/meshqu-api/src/config.ts:244-245](../../apps/meshqu-api/src/config.ts#L244-L245)). 300 sequential decisions is well within budget.

**Additional operational checklist items (Phase 3 / Phase 4):**

- [ ] Author the policy, ratify the version, capture the snapshot — BEFORE any decision is recorded. Decisions against drafts hard-fail; this isn't a silent foot-gun but it would waste a run.
- [ ] If the staging environment hosts other tenants, coordinate the global `transparencyEnabled` flip (or accept that all staging tenants get Rekor-anchored during the experiment window).

---

## 2026-05-14 — Experiment runs on a dedicated staging tenant (`experiment-procurement`)

**Decision**: the experiment runs against a dedicated MeshQu tenant on the staging environment, not in production and not local-only. The tenant has its own ed25519 signing key; the public-key half is published alongside the corpus. Every receipt's `source` block carries `environment: "staging"` and `tenant: "experiment-procurement"`.

**Alternatives considered**:

- Local-only execution (laptop, Docker compose). Rejected: doesn't exercise the same infrastructure paths as a deployed environment. Weaker rehearsal of the methodology applied in a deployed setting, less faithful infrastructure path, no Rekor anchoring against the public log.
- Production tenant. Rejected: mixes experimental receipts with any other production data; operationally messy; small but real risk of confusion later. No methodological benefit over staging — the receipt is self-contained and verifiable via the bundled public key, so a reader cannot tell which environment produced it.
- Staging with a shared multi-purpose tenant. Rejected: a dedicated tenant means the experiment's receipts are unambiguously distinct, and the dedicated signing key gives readers a key explicitly tied to this experiment rather than a general staging key.

**Reason**: staging exercises the same code path as production (Fastify on Railway, Postgres on Supabase, Sigstore Rekor anchoring) while keeping the experiment fully isolated. The dedicated tenant plus dedicated signing key is the cleanest operational choice and makes the experiment a faithful rehearsal of the methodology applied in a deployed environment — relevant to the reusability framing locked in the third revision brief.

**Sam's operational checklist (before Phase 4 — harness build):**

- [ ] Confirm the staging environment is in a stable state suitable for an experimental tenant.
- [ ] Provision the `experiment-procurement` tenant on staging.
- [ ] Generate and document the dedicated ed25519 signing key for the experiment tenant; archive the private half under the existing key-management posture; ship the public half into the bundle as `trusted_keys.json` (informational, for fingerprint comparison only — see next item for the actual trust-root path).
- [ ] **Register the experiment tenant's public key into the verify.meshqu.com trust registry.** The bundle's own `trusted_keys.json` is deliberately NOT used as a trust root by the verifier — letting self-signed bundles authenticate themselves is the exact failure the verifier was built to prevent ([bundle.ts:207-213](../../apps/meshqu-verify/src/lib/bundle.ts#L207-L213), [bundle/page.tsx:43-56](../../apps/meshqu-verify/src/app/bundle/page.tsx#L43-L56)). Two paths:
  - **Source-code path (preferred for a published research artefact):** add the kid to `DEFAULT_TRUSTED_KEYS` in [`apps/meshqu-verify/src/lib/keys.ts`](../../apps/meshqu-verify/src/lib/keys.ts) and ship in a normal verify.meshqu.com release. Trust root is publicly auditable in the verifier's source. Best fit for the writeup's "trust roots arrive via an independent channel" argument.
  - **Env-var path:** set `NEXT_PUBLIC_MESHQU_TRUSTED_SIGNING_KEYS` on the verify.meshqu.com Railway build with `{"meshqu-experiment-procurement-<year>": "<base64 SPKI>"}`. Faster but the trust root is invisible to source-code auditors.
- [ ] Confirm Sigstore Rekor anchoring works from staging (network reach, credentials, `transparencyEnabled` flag set on the experiment tenant).
- [ ] **Tenant-scoped Grafana dashboard** — verify the experiment tenant has dedicated Grafana visibility for: signing operations (rate, latency p50/p95/p99, failure count), Sigstore Rekor anchoring (rate, latency, failure count), database write throughput, Fastify application-level error rate. If existing platform dashboards cover these with tenant filtering, scope confirms; otherwise build a tenant-scoped dashboard before build phase starts (~couple of hours; reusable for future tenant operations beyond this experiment).
- [ ] **10-record dry run** — run before the full 300-record run. Exercises the complete path (substrate adapter, evaluation pipeline, receipt production, bundle generation, verifier round-trip) on a small subset; validates Grafana observability is correctly capturing the operational signal.
- [ ] **Capture Grafana screenshots** — during both the dry run and the full run. These document operational behaviour and serve as supporting evidence in writeup Appendix B.
- [ ] **Watch the dashboard live during the run.** Pause and investigate any anomaly before continuing. Use checkpointing to resume cleanly after intervention.
- [ ] **Implement explicit checkpointing in the harness** — failure at record N allows resumption from N+1 rather than restart from 1.
- [ ] **Capture anomalies and edge cases** alongside successful operations in the harness logs. The harness is both a research instrument and an integration-test instrument.
- [ ] **Bug-handling policy decided in advance**: if a MeshQu bug surfaces during the run, when do you fix-and-rerun vs document-and-ship? Default: fix-and-rerun for anything affecting receipt validity or signing correctness; document-and-ship for minor anomalies that don't affect the cryptographic claims.

---

## 2026-05-14 — Harness built with substrate-agnostic abstraction; methodology positioned as generalisable

**Decision**: the harness is built around a `Substrate` adapter pattern. Per-source concerns (data fetching, schema mapping, governance-regime identification, field-population handling) live in adapters; the `EvaluationPipeline` consumes a normalised `DecisionContext` and is source-agnostic. For this experiment the adapter is `UKContractsFinderAdapter`. The writeup positions the methodology as reusable beyond this experiment.

**Alternatives considered**:

- Build UK-specific throughout, no abstraction. Rejected: methodology reusability is now a goal, not just a nice-to-have. Retrofitting the abstraction later costs days because the pipeline accumulates implicit coupling to UK-specific assumptions; building it now costs hours.
- Over-engineer with multiple substrate adapters from the start (EU TED, US SAM.gov). Rejected: only `UKContractsFinderAdapter` is needed for this experiment. Future adapters are implementations against an already-defined interface, not speculative scaffolding now.

**Reason**: the experiment serves both a research-credibility purpose and a methodology-development purpose. The reusable harness compounds value — if applied to a future engagement, setup time drops materially (substrate adapter + policy authoring pass, not a rebuild). If never applied beyond this experiment, the cost of the abstraction is small and absorbable inside Stream C's existing build time.

---

## 2026-05-14 — No specific future engagements named in any harness file or writeup section

**Decision**: nowhere in the harness, the writeup outline, or any artefact published from this experiment names a specific potential client engagement. Adjacent regulated-domain applications (credit underwriting, customer onboarding, trade pre-screening) are referenced generically in the writeup's "what's next" section without commitment.

**Alternatives considered**:

- Name credit underwriting / customer onboarding / trade pre-screening as concrete next steps. Rejected: overclaims pipeline that isn't there.
- Reference adjacent regulated-domain applications generically. Kept — section 9 of the writeup mentions extensions without committing.
- Stay silent on generalisability entirely. Rejected: silence forfeits the methodology-template framing, which is a material part of why the harness has a substrate-adapter abstraction in the first place.

**Reason**: maintains discipline of not overclaiming uncommitted relationships. The methodology-generalises framing is enough; specific applications announce themselves when they activate. Any future client engagement using this methodology will be its own separately-scoped piece of work.

---

## 2026-05-14 — Phase 0 feasibility spike scoped before predictions lock

**Decision**: a half-day to one-day spike pulls ~200 sacrificial OCDS records from UK Contracts Finder (2025-06-01 to 2025-12-31), answers five specific feasibility questions, and produces a Sam-reviewed report at [`feasibility_spike_report.md`](feasibility_spike_report.md). The brief lives at [`spike_brief.md`](spike_brief.md). Records inspected are listed in the report's appendix and **must be excluded from the eventual 300-record corpus** — they have been seen before pre-registration.

**Alternatives considered**:

- Lock predictions first, build the runner, discover substrate issues mid-build. Rejected: predictions written after looking at data destroy the credibility argument; discovering a PDF-only transparency-notice substrate three weeks into the build costs 2–3 weeks of wrong-direction work.
- Skip the spike and ship a smaller pilot run instead. Rejected: a pilot run produces non-sacrificial data (records that *would* enter the 300) and contaminates the pre-registration discipline. The spike is deliberately sacrificial; a pilot is not.
- Make the GO / NO-GO call inside the spike itself. Rejected: the agent reports findings and recommends; Sam decides whether the substrate carries the design. Keeps accountability for the call with the experimenter, not the substrate scout.

**Reason**: every part of the design — PA23 subset, `PROC-001-S44` mechanics, 20-cell stratification, agent reasoning task — rests on substrate assumptions that have not been verified. Cheap to verify now, expensive to discover mid-build. The spike's sacrificial-data discipline preserves pre-registration integrity.

---

## 2026-05-14 — One rule faithfully implements PA23 s.44; five remain composite

**Decision**: of the six policy rules, `PROC-001-S44` is a faithful implementation of Procurement Act 2023 s.44 + Schedule 5 (transparency notice for direct awards). The other five rules remain composites with per-rule framework provenance as previously locked.

**Alternatives considered**:

- Keep all six composite. Rejected: credibility ceiling is materially lower. "Synthesised across three named regimes" is good; "one faithful implementation of a named UK statute plus five synthesised composites" is materially stronger and harder to dismiss.
- Implement all six faithfully. Rejected: multi-month scope, requires procurement-law expertise we don't have, and dilutes the worked example by spreading attention across six rules.
- Implement one rule from a different regime (FAR 6.302 sole-source justification, or EU 2014/24/EU Art. 32). Considered. UK PA23 s.44 was preferred because the OCDS substrate is UK-primary, the Act is recent enough (commenced 24 February 2025) to produce maximal LLM training-data drift, the s.44 obligation has unusually clean binary evaluation outcomes against named Schedule 5 grounds, and published law-firm analysis (Burges Salmon, Freshfields, Squire Patton Boggs) provides solid secondary sourcing.

**Reason**: disproportionate credibility gain for roughly half a day's additional policy-authoring work. The faithful rule becomes the natural worked example in section 5b of the writeup — the drift-case teardown that buyer-adjacent readers actually engage with.

---

## 2026-05-14 — `PROC-001-S44` evaluated only on contracts awarded 2025-06-01 to 2025-12-31

**Decision**: `PROC-001-S44` is reported against a filtered subset of the corpus — contracts awarded between 2025-06-01 and 2025-12-31. Findings on the five composite rules are reported against the full corpus.

**Alternatives considered**:

- Full 2025 calendar year. Rejected: early-2025 procurements often pre-date PA23 commencement on 24 February 2025 and continue under PCR 2015.
- 2026 procurements. Rejected: out of scope per the existing substrate.md time-window decision.
- Apply `PROC-001-S44` to the full corpus and treat pre-commencement records as automatic compliance. Rejected: would distort the headline rule-firing rate and invite "you're evaluating a rule against records it doesn't apply to" criticism.

**Reason**: ensures the `PROC-001-S44` subset is cleanly under the new regime, with a four-month settling-in buffer past 24 February 2025. The two-tier reporting (full-corpus for composites, filtered subset for the faithful rule) is the cleanest way to handle a regime change inside the corpus window.

---

## 2026-05-14 — P7 added: PCR 2015 citation drift on PA23 procurements

**Decision**: predictions.md gains a new P7 — when the agent recommends ALLOW on a direct award governed by PA23 and `PROC-001-S44` fires DENY, we predict >40% of those agent reasoning narratives cite PCR 2015 or "Regulation 32" rather than PA23 s.44.

**Alternatives considered**:

- Leave P3 (general hallucinated citations) to cover this. Rejected: too generic. The specific PCR-on-PA23 drift is the strongest predictable signal in the experiment and deserves its own line in the pre-registration.
- Predict on a narrower citation taxonomy (PCR 2015 specifically, not "Regulation 32"). Rejected: agents will pattern-match to a mix of regulation numbers and informal regulation names; the 40% threshold covers the family.

**Reason**: load-bearing for the writeup's drift framing. Specific, falsifiable, statute-anchored. The result either confirms the headline narrative or pivots it — both outcomes are publishable.

---

## 2026-05-14 — Positioning locked: Stripe-style commercial research report

**Decision**: this is a commercial research report in the Stripe-engineering-blog mould. Not a peer-reviewable paper. Not a demo. Not a customer case study. A vendor publishing rigorous applied work on its own infrastructure.

**Alternatives considered**:
- Peer-reviewable academic paper, possibly co-authored with USW. Rejected: USW collaboration is months out and not on this artefact's critical path. Stripe-style ships faster, lands the commercial-credibility goal sooner, doesn't preclude a later academic version.
- Customer case study. Rejected: no customer to anchor it on.
- Demo writeup. Rejected: demos look like sales fiction. The experiment is the opposite.

**Reason**: the goal is buyer-credible evaluation-conversation ammunition. The Stripe-engineering-blog shape (named author, engineer-to-engineer voice, methodology-heavy, real data on real infrastructure, no CTA in the body) is calibrated for exactly that audience.

---

## 2026-05-14 — Audience priority inverted: engineer-first

**Decision**: primary audience is engineers who support compliance, audit, and procurement teams at regulated firms. Compliance leads themselves are secondary, reached through the engineer's forwarding.

**Alternatives considered**:
- Compliance / audit lead as primary audience. Rejected: writing for compliance leads as the primary reader drifts the voice into consultant-register and breaks engineering credibility.
- Multi-audience segmentation (one section per persona). Rejected: dilutes the argument. An engineer reading a piece written to them can derive the implications for their compliance partner. The reverse doesn't hold.

**Reason**: Stripe convention. Engineers read it first, send it internally, the compliance officer reads it because their engineer flagged it.

---

## 2026-05-14 — Methodology section weighted as heavily as results

**Decision**: methodology section grows to ~800 words. Results section trims to ~1,200 words. Total length budget unchanged (~4,000 words).

**Alternatives considered**:
- Results-heavy structure with a brief methodology paragraph. Rejected: results without methodology aren't legible to a skeptical reader.

**Reason**: an engineer should be able to rebuild the experiment from reading the methodology section. That's what makes results legible and the writeup re-runnable.

---

## 2026-05-14 — "What this means" section collapsed to single argument

**Decision**: the section formerly titled "What this means" is now "Reasoning is data." Single direct argument to the engineer. No audience segmentation. Length unchanged (~600 words).

**Argument**: AI agent reasoning is data. Most teams treat it as logs. Here's what changes when you treat it as cryptographically bound, replayable data instead.

**Alternatives considered**:
- Keep the three-audience subsections (compliance / regulator / engineer). Rejected: enumerating implications for each audience reads as marketing segmentation, not engineering argument.

**Reason**: the engineering insight subsumes the compliance and regulator implications. A reader can derive both from the engineering argument without being walked through.

---

## 2026-05-14 — Title style locked: flat-descriptive

**Decision**: titles are flat and descriptive in Stripe convention. The framing question ("what does a defensible audit trail of an AI-assisted decision actually look like? Here are 300.") becomes the opening line of the piece, not the title.

**Three title candidates** for Sam to pick from:

1. *300 AI procurement decisions, signed and verifiable*
2. *What an AI agent gets wrong about procurement compliance, and what the receipts say*
3. *An audit trail for AI decisions: a teardown of 300 procurement reviews*

**Reason**: the title is the piece's first credibility signal. A skeptical engineer scanning a feed should know what the piece contains before clicking.

---

## 2026-05-14 — Author byline: named individual

**Decision**: byline is "Sam Carter, MeshQu." Not "the MeshQu team."

**Reason**: Stripe convention. Credibility partly comes from a named individual standing behind the work. A team byline reads as committee-written and lowers the credibility signal.

---

## 2026-05-14 — Publication surface: /research, not /blog

**Decision**: publish at `meshqu.com/research/<slug>` rather than `meshqu.com/blog/`.

**Alternatives considered**:
- `meshqu.com/blog/`. Rejected: one research post in a mixed blog feed reads weaker than one research post on a clean research surface.

**Reason**: sets up a future research cadence without committing to a blog cadence MeshQu doesn't have yet. Easier to publish one research piece every six months on a /research surface than to publish weekly blog posts to fill out a /blog surface.

---

## 2026-05-14 — Framework provenance exposed per rule

**Decision**: each of the six policy rules carries an explicit "framework provenance" column naming which real-world frameworks shaped it. UK Procurement Act 2023, EU Directive 2014/24/EU, FAR. The writeup section 3 shows the same provenance alongside each rule.

**Reason**: "composite, we made it up" invites dismissal. "Synthesised across three named regimes" is materially stronger. Same content, different framing, much harder to dismiss.

---

## 2026-05-14 — Human-review pass framed as experimenter review

**Decision**: the human-review pass is framed as "reviewed by the experimenter against the published procurement frameworks." Cases where rule interpretation is genuinely contested are flagged as such rather than adjudicated.

**Alternatives considered**:
- Hedged framing ("Sam plus optionally one advisor, isn't perfect ground truth"). Rejected: invites skeptical dismissal.

**Reason**: honest framing is stronger than hedged framing. A reader who wants stronger ground truth knows to discount accordingly. They don't catch you pretending.

---

## 2026-05-14 — P4 reframed as non-determinism band

**Decision**: prediction P4 pre-registers an expected non-determinism range (5–20% at temperature 0), not a hoped-for stability rate.

**Alternatives considered**:
- Pre-register ">95% verdict-stable across re-runs." Rejected: foundation model providers are increasingly explicit that temperature 0 doesn't guarantee determinism. Batch-level variation, hardware variation, silent model updates. A high stability prediction would force an awkward pivot if observed non-determinism exceeded it.

**Reason**: the receipt corpus is reproducible even when the LLM substrate isn't. That's a stronger argument than "the LLM is stable" and it's the one MeshQu actually owns.

---

## 2026-05-14 — Corpus size locked at 300

**Decision**: 300 receipts for the first writeup. Methodology section notes the design extends to larger corpora as natural follow-up.

**Alternatives considered**:
- 500 or 1,000. Background-Claude execution capacity makes larger runs cheap.

**Reason**: speed-to-publish matters more than corpus depth for the commercial-credibility goal. 300 is enough for statistical signal in the bigger value bands. Sample-sparse cells get flagged honestly. The methodology extends to N=1,000 without changes; future runs can scale.

---

## 2026-05-14 — System prompt hash bound in receipt; prompt published

**Decision**: the receipt's metadata binds `agent_prompt_sha256`. The system prompt itself is published as part of the artefact bundle.

**Reason**: a reader can fetch the published prompt, hash it, and confirm the bound digest matches the prompt that produced the agent's reasoning. Closes the "what prompt produced this" question cryptographically.

---

## 2026-05-14 — agent_reasoning locked into fields (integrity-hashed)

**Decision**: `agent_reasoning` lives in the `fields` object, not `metadata`. The reasoning is bound by the integrity hash.

**Reason**: a reader can verify the agent's reasoning wasn't edited after the receipt was produced. The cryptographic-binding argument in the writeup ("reasoning is data, not logs") leans directly on this.

---

## 2026-05-14 — Harness scaffolded

**Decision**: open this harness as `[PLANNING]` only — no implementation work yet. Mirror the structure of `.harness/aarm-roadmap/` (planning harness, not implementation harness).

**Alternatives considered**:
- Jump straight to building the runner repo. Rejected: the pre-registered-prediction discipline collapses if predictions are written after results — need a deliberate planning phase first.
- Build the experiment inside the existing `apps/meshqu-demo/` codebase. Rejected: experiment runner should be a separate public repo so reviewers can clone and run it without pulling the monorepo. The experiment is *about* MeshQu, not part of MeshQu.

**Reason**: the credibility argument depends on pre-registration, which only works if there's a deliberate gap between "what we expect" and "what we ran".

---

## 2026-05-14 — Picked B2B procurement over consumer / financial-advice / hiring scenarios

**Decision**: procurement compliance is the scenario for the first writeup.

**Alternatives considered**:
- AI coding agent + repo governance — natural for the engineering audience but narrow buyer story.
- AI financial-advice / KYC — high regulator attention but politically charged and harder to source clean substrate.
- AI hiring agent — strongest narrative on consumer-protection grounds but the highest legal / reputational risk (EEOC, NYC LL144).
- Public-records compliance agent — substrate is good but narrative is academic, not commercial.

**Reason**:

1. Substrate is genuinely open (UK Contracts Finder + Find a Tender, EU TED, US SAM.gov).
2. Low political volatility — engineering and compliance audiences can engage on technical merit.
3. Maps to MeshQu's existing capability mix (policy versions, snapshots, receipts, bundles, audit trail) without needing C1/C2/C3/C5 to ship first.
4. Buyer profile is clean: compliance, audit, procurement teams at regulated firms.
5. Adjacent angle for free — one paragraph at the end extends to credit underwriting, customer onboarding, trade pre-screening.

**Trade-off accepted**: procurement is less hot politically than consumer AI, so the writeup won't go viral on the consumer-protection beat. That's fine; the goal is buyer credibility, not virality.

---

## 2026-05-14 — Agent will NOT be given the policy text

**Decision**: the agent reasons about each procurement filing from first principles + its training data. The policy text is not in the system prompt.

**Alternatives considered**:
- Hand the agent the policy text and ask it to apply the rules. Rejected: collapses the experiment into "can the LLM follow rules", which is not what we want to show.
- Two parallel runs — with and without the policy text — for comparison. Deferred: too much scope for the first writeup. Mentioned in "what's next" as a follow-up.

**Reason**: the interesting signal is *drift* — cases where the agent's reasoning sounds confident but conflicts with the policy. That signal only exists if the agent isn't told the rules.

---

## Pending decisions (to resolve before locking predictions)

- [ ] **Substrate scope**: UK only, or UK + EU TED from the start? Current lean: UK only for the first writeup. Cleaner schema, single language for human review, OGL v3.0 is the most permissive licence in the space. Decide and lock.
- [ ] **Single model or multi-model**: current lean is single model, multi-model as a follow-up. Multi-model multiplies the corpus by N and dilutes the headline. Decide and lock before sample selection runs.
- [ ] **Title pick**: three candidates listed in writeup_outline.md. Sam picks one. Title locks at draft time, not before, but the candidates are the shortlist.
- ~~**Pre-registration surface**~~: resolved by revision brief 7 — the locked-predictions commit lands in the public `meshqu-research/procurement-decisions/planning/` repo. Sam executes the extraction before predictions lock per the operational checklist in the brief-7 decision_log entry above.
- [ ] **Specific foundation model**: pick the model and pin the exact version at experiment time. Recorded in `metadata.agent_model_id` and `metadata.agent_model_version`. Decision deferred until execution starts; what matters now is that the choice gets pinned and published.
- ~~**P6 reformulation**~~: resolved 2026-05-15 — P6-C (award method) selected. P6-A and P6-B removed from predictions.md. See decision_log entry above.
- ~~**Direct-cell over-sampling floor for `PROC-001-S53`**~~: resolved 2026-05-15 — revised brief 12 set the floor at 20 records (≥10 per value band across £100k–£1m and >£1m), calibrated to the pre-lock sanity check finding (only 6 above-threshold direct-award records in the Phase 0.5+ sample). See revised brief 12 entry above.
- ~~**legislation.gov.uk verification of regs 32-36**~~: resolved 2026-05-15 — verification completed pre-lock; reg. 36 framing tightened in revision brief 11 to distinguish s.87(3) below-threshold notices from s.53(1) (regs 32-35 layered on reg. 32).

Resolved decisions (see entries above):

- ✅ Execution environment: dedicated staging tenant `experiment-procurement` with dedicated ed25519 key
- ✅ Substrate-agnostic harness (adapter pattern); methodology positioned as reusable
- ✅ No specific future engagements named anywhere in the harness or writeup
- ✅ Phase 0 feasibility spike scoped (sacrificial pull, Sam-decided verdict)
- ✅ Positioning: practitioner-direct commercial research report (originally framed as "Stripe-style" during planning; reframed at pre-lock cleanup — see 2026-05-14 positioning entry for the original decision)
- ✅ Audience priority: engineer-first
- ✅ Methodology weight: equal to results
- ✅ "What this means" → single argument
- ✅ Title style: flat-descriptive
- ✅ Byline: named individual
- ✅ Publication surface: /research
- ✅ Legal review tightening: PROC-001-S53 signature-date proxy named; PROC-006-MOD-CAP provenance mapped 10% and 50% to actual statutory sources; "open procedure as default" → "competitive tendering as the norm"; "strict version pinning" → "explicit model selection and configuration"
- ✅ Planning harness extracted to public `meshqu-research/procurement-decisions/planning/` before predictions lock
- ✅ Repo structure: `procurement-decisions/` + `methodology/` (public methodology layer, private engagement layer)
- ✅ Prometheus instrumentation audit pre-build (signing, Rekor, receipt-write, Fastify; `tenant` label coverage)
- ✅ PROC-001-S53 citation cluster: PA23 s.53(1) + Procurement Regulations 2024 reg. 32-36 (legislation.gov.uk verification completed pre-lock; reg. 36 framing tightened in revision brief 11 to distinguish s.87(3) below-threshold notices from s.53(1))
- ✅ Inspect AI selected as evaluation framework
- ✅ Experiment positioned as triple-duty: research + methodology + product proof
- ✅ Grafana observability captured as product-proof evidence (writeup Appendix B)
- ✅ Faithful rule: `PROC-001-S53` (PA23 s.53 30-day Contract Details Notice timeliness); previously `PROC-001-S44` (retired post-Phase-0)
- ✅ `PROC-001-S53` reporting: proxy-identified PA23 subset (`awards[0].date > 2025-02-24`); ambiguous-regime records reported as a separate subset
- ✅ Exclusion list: conservative read — all spike-inspected records (~262) excluded from the 300-record corpus
- ✅ Stratification grid: 3×3 (`{framework_call_off, first_instance_competitive, direct}` × value band) replacing 5×4; reflects empirical reality post-Phase-0
- ✅ P7 reframed: 30-day-cap-recognition drift (PA23 s.53), replacing PCR 2015 citation drift
- ✅ P6 selected: award-method cross-cut on the s.44/s.53 distinction (P6-C); P6-A and P6-B removed
- ✅ Framework provenance: per-rule
- ✅ Human-review framing: experimenter review, contested cases flagged
- ✅ P4: non-determinism band
- ✅ Corpus size: 300
- ✅ System prompt hash: bound in receipt; prompt published
- ✅ `agent_reasoning`: in `fields`, integrity-hashed
- ✅ `source_artifact.hash`: binds raw source filing bytes

---

*Append new entries above this line.*
