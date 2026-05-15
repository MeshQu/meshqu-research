# Writeup Outline

A Stripe-style commercial research report. Written engineer-to-engineer. The piece is the deliverable. Every other artefact in this harness exists to make the piece defensible.

## Title

The title is the piece's first credibility signal. Flat, descriptive. A skeptical engineer scanning a feed should know what the piece contains before clicking.

Three candidates for Sam to pick from:

1. *300 AI procurement decisions, signed and verifiable*
2. *What an AI agent gets wrong about procurement compliance, and what the receipts say*
3. *An audit trail for AI decisions: a teardown of 300 procurement reviews*

The opening line of the piece is the framing question that used to be the title: *what does a defensible audit trail of an AI-assisted decision actually look like? Here are 300.* It opens section 1, not the headline.

## Author

Byline: **Sam Carter, MeshQu**. Named human, not "the MeshQu team." Stripe convention. Credibility partly comes from a named individual standing behind the work.

## Publication surface

`meshqu.com/research/<slug>`. Not `/blog/`.

One research post on a clean research surface reads stronger than one research post in a mixed blog feed. Sets up a future research cadence without committing to a blog cadence that doesn't exist yet.

## Audience

Priority order:

1. **Engineers who support compliance, audit, and procurement teams at regulated firms.** They read it first and forward it internally.
2. **The compliance, audit, and procurement leads themselves.** They read it because their engineer flagged it.
3. **Regulators monitoring AI deployment in regulated decisions.** They read it because someone they trust forwarded it.
4. **Other engineers in the AI governance and audit-trail space.** They read it because the methodology is rebuilable.
5. **Investors and analysts evaluating MeshQu.** They read it as evidence the founder ships credible technical work.

Writing for compliance leads as the primary audience drifts the voice into consultant-register and breaks engineering credibility. Write to the engineer. The compliance officer reads it second, through the engineer's forwarding.

## Length budget

~4,000 words total. Methodology is weighted at least as heavily as results.

| Section | Approx. words |
|---|---|
| 1 · The question | 300 |
| 2 · How we ran it (methodology) | 800 |
| 3 · The policy under test | 400 |
| 4 · The substrate | 300 |
| 5 · What the corpus shows | 1,200 |
| 6 · Reasoning is data | 600 |
| 7 · Limitations | 400 |
| 8 · Reproduce it yourself | 200 |
| 9 · What's next | 200 |

Methodology earns its weight. Results without methodology aren't legible. A skeptical engineer who wants to rebuild the experiment from the piece should be able to.

## Section-by-section outline

### 1 · The question (~300 words)

Open with the supervisory pain point in one paragraph. AI proposes a decision. A human approves it. The audit trail is opaque. Was the human reviewing or rubber-stamping. Can you reproduce the decision in eighteen months. Can you tell which model produced the recommendation. Cite the specific regulator language. EU AI Act high-risk provisions. SEC examination priorities on AI in investment advice. FCA, MAS, BaFin AI guidance.

Ground the framing in named UK government policy on AI in procurement specifically: **PPN 02/24** (May 2024, "How should we be using AI in the public sector?" — addresses LLM-generated bid content risks, accuracy, hallucination concerns); **PPN 017** (2025 update extending PPN 02/24 with operational guidance); and the **UK Government AI Playbook** (February 2025, ten principles for safe and lawful AI use including meaningful human control). Named references with URLs are sufficient — direct quotes are not necessary.

State the experiment in one sentence. We ran 300 public UK procurement records through an LLM agent, asked it to recommend a verdict, recorded each decision through MeshQu against a documented policy, and verified the resulting receipt corpus offline. Here's what the audit trail looks like.

End the section with the link to the pre-registered predictions. Commit hash plus timestamp. This is the credibility anchor for everything that follows.

### 2 · How we ran it (~800 words)

Methodology is load-bearing. An engineer should be able to read this section and rebuild the experiment.

Cover, in order:

- The agent loop. Diagram of the data flow. Substrate to LLM to MeshQu to signed receipt. One paragraph per stage.
- The agent setup. Single foundation model, pinned to a specific version. Temperature 0. System prompt published as part of the artefact bundle, hash bound into every receipt's metadata. The experiment is implemented using **Inspect AI**, the UK AI Safety Institute's evaluation framework, which provides multi-provider model access, explicit model selection and configuration, structured output enforcement, and trace generation.
- The deliberate constraint. Agent is not given the policy text. Reasons from first principles plus its training data. The interesting signal is drift. Where the agent's reasoning sounds confident but conflicts with the policy.
- Sampling. Stratified by award method × value band on a 3×3 grid. 300 records. Notice IDs frozen and committed publicly before any run.
- **Substrate analysis preceding pre-registration.** A short subsection (200-300 words) summarising the two pre-registration spikes: Phase 0 (full five-question feasibility check that killed the original `PROC-001-S44` rule on substrate grounds), Phase 0.5 (narrow check that confirmed the s.53 rule's load-bearing field carries original publication time). Names the substrate's documented limitations: 96% of records carry no PA23/PCR regime signal in OCDS, so governance is identified by contract-award-date proxy; framework call-offs dominate ~68.6% of records, so the grid is 3×3 not 5×4. Prose drafted from `experiment_design.md` "Substrate analysis preceding pre-registration" at writeup time.
- What we controlled for. Pinned model, pinned policy snapshot, pinned system prompt, pinned sample set.
- What we didn't control for. Day-to-day LLM provider behaviour. Network conditions. Records modified by the source dataset after sampling.
- What would change the result. Different model. Different policy. Different sample stratification. Each calibrated honestly so a reader knows what they'd vary to test the experiment's robustness.
- The receipt anatomy. What's signed. What isn't. What binds to what. Show one receipt's key fields with annotations. Cryptographic integrity is the technical core of the piece.

This section is what makes everything that follows readable. Take the words it needs.

One short paragraph at the end of section 2 plants the methodology-generalises seed without making it the focus:

> The methodology described here is substrate-agnostic. UK Contracts Finder is the worked example because it is open, recent, and rich enough to support meaningful agent reasoning. The same structure applies to any historic-decision corpus where the source data, the governing policy framework, and the decision context can be cleanly separated.

### 3 · The policy under test (~400 words)

Lead with the one-faithful-five-composite framing. The reader should leave the section knowing exactly which rule is which.

**The faithful rule.** One short paragraph. `PROC-001-S53` implements the Procurement Act 2023 s.53(1) 30-day Contract Details Notice publication obligation, operationalised through Procurement Regulations 2024 (SI 2024/692) reg. 32 (core content) layered with reg. 33 (frameworks), reg. 34 (call-offs under frameworks), reg. 35 (direct awards), and reg. 36 (below-threshold). The Cabinet Office Procure-phase guidance confirms the 30-day clock runs from contract signature (120 days for light-touch contracts). State that the Act came into force 24 February 2025 and that the experiment evaluates this rule against the proxy-identified PA23 subset of the corpus (records with `awards[0].date > 2025-02-24`, since Contracts Finder OCDS records do not carry an explicit governing-regime field — proxy methodology covered in §2).

**The five composites.** One short paragraph. Each rule's shape is synthesised from named procurement frameworks (UK PA23, EU 2014/24/EU, US FAR) without being a faithful implementation of any one regime. Provenance is shown per-rule in the table so the reader can see exactly which named regimes shaped which rule.

Then the table:

| Rule | Type | Severity | Provenance |
|---|---|---|---|
| `PROC-001-S53` | threshold + when | critical | **Faithful — Procurement Act 2023 s.53(1) + Procurement Regulations 2024 reg. 32-36** |
| `PROC-002-AUTHORITY` | threshold | critical | Composite — UK PA23 delegated-authority frameworks; EU 2014/24/EU Art. 4 |
| `PROC-003-DEBARMENT` | list | critical | Composite — UK PA23 Schedule 6; EU 2014/24/EU Art. 57; FAR 9.4 |
| `PROC-004-COI` | presence | high | Composite — UK PA23 s.81; EU 2014/24/EU Art. 24; FAR 3.101 |
| `PROC-005-OPEN-TENDER` | threshold + when | critical | Composite — UK PA23 default-competition principle; EU 2014/24/EU thresholds |
| `PROC-006-MOD-CAP` | threshold + when | high | Composite — UK PA23 s.74; EU 2014/24/EU Art. 72 |

Show `PROC-001-S53`'s full JSON inline. Link to the policy_snapshot.json in the bundle for the rest.

Close the section with the explicit framing: the five composites are illustrative and not equivalent to any one regime; `PROC-001-S53` is a faithful implementation of a specific named UK statutory time-window, and the writeup leads its drift case study with that rule. The faithful rule is structurally different from the s.44 rule originally drafted — a timeliness rule against verified OCDS date fields rather than a presence-and-content rule against linked notices. This shape was chosen because it survives the substrate constraints surfaced in the pre-registration spikes; the methodology section (§2) summarises that work.

### 4 · The substrate (~300 words)

UK Contracts Finder. Open Government Licence v3.0. Records awarded in 2025. Stratified sample described in `substrate.md`. The frozen-notice-IDs commit is linked.

Short visual: the 3×3 sampling grid (award method × value band) with cell counts. Note that the grid was revised from 5×4 to 3×3 after the Phase 0 substrate spike found 14 of 20 original cells under-populated — the revision is documented in §2 alongside the rest of the substrate-analysis findings.

State the limitation up front. Sample is UK-only and English-language. EU TED and US SAM.gov are flagged in section 9 as natural follow-ups.

One short paragraph cross-referencing §2: pre-registration was preceded by two substrate spikes (Phase 0 and Phase 0.5). The methodology section in §2 summarises what those spikes checked and what design adjustments followed. This is engineering discipline visible to the reader, not hidden in footnotes.

Two methodological proxies are documented in the substrate-honesty subsection (see [experiment_design.md](experiment_design.md), "Substrate analysis preceding pre-registration"): governance regime identified by contract award date relative to PA23 commencement, and contract signature date proxied by award decision date for the s.53 timing computation. Both are documented limitations; findings on `PROC-001-S53` are scoped accordingly.

One short line of honest disclosure at the end of section 4:

> Receipts were generated against a dedicated MeshQu tenant on the staging environment, signed with a key whose public half is published alongside the corpus. Verification is environment-independent — the bundle includes the public key needed to verify offline.

A second short paragraph surfaces the product-proof dimension:

> The corpus produced by this experiment is doubly load-bearing. It serves as the empirical evidence for the findings reported in section 5, and it serves as production-scale evidence that MeshQu's infrastructure — signing, anchoring, bundling, verification — works reliably on real external data. Every receipt in the corpus was produced by the same code path that runs in MeshQu's production environment, signed by an ed25519 key whose public half is registered in verify.meshqu.com's source-code trust registry (see §2 methodology), and anchored to Sigstore Rekor at the moment of decision. Operational behaviour during the run was monitored via Grafana dashboards; screenshots are included as supporting evidence (see Appendix B). A reader who wants to verify that MeshQu actually works end-to-end can download the corpus and verify it offline; the Grafana captures provide secondary evidence of how the infrastructure behaved at corpus scale during production.

### 5 · What the corpus shows (~1,200 words)

Results, reported honestly against the pre-registered predictions.

**5a · Volume and verdict distribution.** Counts. Charts. Latency. Short. Headline statistics report against two denominators: the full corpus (for the five composite rules) and the proxy-identified PA23 subset (for `PROC-001-S53`). The split is visible in the section — quietly aggregating across both would obscure the methodology. The illustrative receipt shown alongside the counts includes its full `source` block (`environment: "staging"`) and its `signature_kid`. The kid resolves to the experiment's published public key; together with the prose tenant disclosure in §4, that's how a reader confirms which tenant produced the corpus — the schema has no `source.tenant` field.

**5b · Agent-vs-policy disagreement.** The interesting section. Led by the `PROC-001-S53` worked example, then sub-sectioned by prediction headline.

**Worked example: a PA23 direct-award case where transparency notice existence misled the agent on s.53 timing.** Walk one case end-to-end as a six-step trace. The structure is committed in advance; the specific case is selected from the corpus during writeup drafting based on what actually fires in the data.

1. **Procurement awarded.** Show the contract record (buyer, supplier, value, award method = direct award, contract award date).
2. **Transparency notice exists.** Show that a s.44 transparency notice was published before contract award. This is the structural detail that makes the agent's mistake plausible.
3. **Agent infers compliance.** Show the agent's reasoning verbatim, including its inference from notice existence to compliance verdict.
4. **MeshQu policy evaluates s.53 timing.** Show the `publication_delay_days` calculation against the 30-day cap, with the policy verdict.
5. **Statutory breach surfaced.** Show `PROC-001-S53` firing DENY with the specific timing violation and statutory citation (PA23 s.53(1) + Procurement Regulations 2024 reg. 35 for direct awards).
6. **Receipt preserves the chain cryptographically.** Show the receipt structure binding the agent's reasoning, the policy snapshot digest, the timing computation, the signature, and the Sigstore Rekor anchor reference.

This is the case study a buyer-adjacent reader actually engages with. The structure makes the failure mode concrete and the cryptographic resolution explicit. **Step 4 is the moment the experiment's thesis lands cryptographically rather than rhetorically; step 6 demonstrates the MeshQu thesis in microcosm.** The prose is written from the actual corpus at writeup time, not drafted now.

Then the prediction-by-prediction results:

- *P1 result vs prediction.* Overall disagreement rate, direction, what surprised us.
- *P3 result vs prediction.* General hallucinated citations across the full corpus. One or two named examples with the agent's reasoning verbatim, the cited clause, whether it exists or is misapplied.
- *P6 result vs prediction.* Direct-award disagreement rate vs competitive-procurement disagreement rate on `PROC-001-S53`, scoped to the proxy-identified PA23 subset. Chart plus commentary on whether the s.44/s.53 conflation predicted in the theoretical prior actually showed up.
- *P7 result vs prediction.* 30-day-cap-recognition rate on `PROC-001-S53` denials. Citation taxonomy chart. For agents that do recognise the cap, whether they reason about the 30-day specifics correctly or approximately. P6 and P7 reported as a paired result: P6 names *where* the disagreement clusters; P7 names *why*.

Predictions that didn't pan out are reported with the same emphasis as ones that did. Quietly dropping failed predictions is the move that gets writeups dismissed.

**5c · Reproducibility.** Verdict stability across re-runs. Bundle round-trip results from verify.meshqu.com. P4's expected non-determinism band reported against the observed rate.

### 6 · Reasoning is data (~600 words)

Single direct argument. No audience segmentation.

AI agent reasoning is data. Most teams treat it as logs. Here's what changes when you treat it as cryptographically bound, replayable data instead.

#### Voice references for section 6 (captured 2026-05-15 during P6 selection)

These phrases capture the thesis at the right register. The eventual section 6 prose should land in this voice — direct, specific about the failure mode, not abstract about AI governance:

- "semantically plausible but procedurally incorrect"
- "the agent mistakes publication existence for publication compliance"
- "the agent infers procedural legitimacy without understanding the temporal statutory obligation"
- "reconstruction is not proof"
- "the agent's mistake is not irrational, random, or hallucinated nonsense — it is semantically plausible but procedurally incorrect"

Use these as anchors when drafting section 6. They sharpen the existing structural argument (AI agent reasoning is data; treating it as cryptographically bound, replayable data is a different mental model from log-and-forget) by giving it specific named failure modes that a compliance officer recognises.

Walk through one full receipt from the corpus. Pick the strongest example surfaced in section 5b. The full receipt is shown verbatim — the `source` block (`environment: "staging"`), the `signature_kid` that resolves to the experiment's published key, and the agent provenance fields inside `fields` (`agent_model_id`, `agent_model_version`, `agent_temperature`, `agent_prompt_sha256`, `agent_reasoning`) so a reader can see exactly which model, which prompt, and which reasoning the integrity hash binds. Nothing is hidden between the prose and the artefact. Show what a compliance officer challenged on the decision can actually do with it:

- Open the receipt. See the agent's reasoning verbatim.
- See the exact policy snapshot the decision was evaluated against.
- See which rules fired and which didn't.
- Replay the decision six months later. Same input, same snapshot, same verdict. Independent of LLM stability.
- Hand the bundle to an auditor who has no access to MeshQu's infrastructure. They verify it offline.

The compliance and regulator implications fall out of the engineering argument. Don't enumerate them. An engineer reading this can derive them for their compliance partner without being walked through.

End the section with the technical insight. The receipt is the contract between the AI-augmented decision and everyone who has to defend it later. Treating reasoning as data, not logs, is what makes that contract enforceable.

### 7 · Limitations (~400 words)

Honest enumeration. A reader who wants stronger ground truth knows to discount accordingly. They don't catch you pretending.

Items to name, in this order:

- Policy mixes one faithful rule (`PROC-001-S53`, Procurement Act 2023 s.53 30-day Contract Details Notice publication obligation) with five illustrative composites. The composites are not certified by any one regulator. The faithful rule is the author's good-faith implementation of the statutory time-window plus published secondary analysis, not an independent procurement-law expert's interpretation.
- Governance regime (PA23 vs PCR 2015 transition arrangements) is identified by proxy — `awards[0].date > 2025-02-24` is treated as PA23-governed because Contracts Finder OCDS records carry no direct regime field. Records with ambiguous governance are reported as a separate subset rather than excluded silently. §2 covers the proxy methodology.
- The s.53 timing computation uses award decision date (`awards[0].date`) as a proxy for contract signature date, which is what PA23 s.53(1) actually measures from. The proxy is imposed by substrate limitations — the OCDS feed exposes award decision date, not signature date. Award decision and contract signature are typically close together but legally distinct. Findings on `PROC-001-S53` are reported with this proxy explicit.
- Single foundation model at a single version. Results may not generalise across models.
- Disagreement cases were reviewed by the experimenter against published procurement frameworks. Not independent expert review. Cases where rule interpretation is genuinely contested are flagged as such rather than adjudicated.
- Sample is UK-only and English-language. Procurement vocabulary differs across regimes.
- Receipts validate decision integrity, not policy correctness. A flawed policy correctly enforced still produces a clean receipt.
- LLM non-determinism may exceed the pre-registered band. Reported honestly with the observed rate.

The writeup reads as if I want readers to find more limitations and write follow-ups. That's how credibility compounds.

### 8 · Reproduce it yourself (~200 words)

Clone the repo. Install dependencies. Run the agent harness against the bundled policy snapshot. The receipts you produce should be functionally identical to the published corpus, modulo LLM non-determinism that section 5c quantified.

Then: download the corpus tar, drop it into verify.meshqu.com, see the same verdict the writeup shows.

End with a link to the repo and the corpus.

### 9 · What's next (~200 words)

Three specifically named follow-up directions:

- **Follow-up A — Above-threshold UK procurement with richer narrative.** UK Find a Tender Service (<https://www.find-tender.service.gov.uk/>) is the natural sibling to Contracts Finder, using the same OCDS format under the same OGL licensing. Above-threshold notices typically carry richer narrative content. The same methodology applies; the substrate adapter changes.
- **Follow-up B — Agent context gradient.** Same Contracts Finder substrate, same policy, but with the agent receiving varying levels of policy context: none (Arm A, this experiment), general procurement guidance only (Arm B), full policy text including specific rule references (Arm C). Measures how disagreement rates change with deployment posture.
- **Follow-up C — Rich narrative substrate via UK Find Case Law.** UK Find Case Law (<https://caselaw.nationalarchives.gov.uk/>) carries full judicial reasoning text under the Open Justice Licence. Application of the methodology to court judgments — for example, evaluating procedural compliance against statutory time-limits — would demonstrate the substrate-agnostic methodology on dramatically richer narrative content. Requires a separate computational-access licence from MoJ.

Each follow-up piece would publish under the same `meshqu-research` umbrella as a separate sibling directory alongside `procurement-decisions/`, with its own substrate adapter, policy authoring, and writeup. The `methodology/` layer is shared across pieces and matures with each application.

Close the section with the architectural note:

> The harness is built around a substrate-adapter abstraction, so each of these extensions is a substrate-adapter implementation plus a domain-specific policy authoring pass — not a rebuild.

No call-to-action. The artefact is the pitch.

## Appendices

**Appendix A — Sample notice IDs.** The frozen 300-record sampling commit-hash anchor; full OCID list with award-method and value-band assignment so a reader can independently re-derive the corpus from Contracts Finder.

**Appendix B — Operational observability during the run.** Grafana dashboard screenshots captured during the 10-record dry run and the full 300-record run, documenting: signing operations (rate, latency p50/p95/p99, failure count), Sigstore Rekor anchoring (rate, latency, failure count), database write throughput, and Fastify application-level error rates throughout the experiment duration. These provide supporting operational evidence for the product-proof dimension of the experiment described in section 4 and §2 methodology. Captured at run time, curated post-run.

## Tone

Match meshqu.com's editorial register.

Short declarative sentences. Paragraph breaks as beats. No exclamation marks. No superlatives. No "revolutionary." No "deeply." No "fundamentally." Citations to real regulator language. No fabricated quotes. The author is a system designer reporting findings, not a salesperson pitching.

Contractions are fine. First-person where natural.

## Drafting plan

**Step 0 — before drafting any section, write the opening 300 words.**

If those 300 words read in Stripe voice — flat, descriptive, engineer-to-engineer, no rhetorical lifts, no "revolutionary," methodology-confident — the rest of the piece writes itself in the same voice. If they don't, the voice isn't locked yet. Don't proceed to other sections until the opening 300 lands.

### Locked voice reference (the opening 300 words)

This is the gold-standard opening, written by Sam at planning time. Every subsequent draft section is read against this for tone-match before it's committed.

> When a regulated firm deploys an AI agent inside a decision workflow, a question follows it: how was this decision made? Most firms cannot answer it well. The agent's reasoning sits in application logs. The policy the agent was meant to follow lives in a separate document, version-controlled somewhere else. The decision itself is recorded as a row in a database. Six months later, when a regulator asks the question or a customer disputes the outcome, the firm reconstructs the answer from three sources that were never bound to each other. That reconstruction is not evidence. It is a story told after the fact.
>
> MeshQu builds infrastructure for binding decisions to their evidence at the moment they are made. Each decision produces a signed receipt, bound to the exact policy snapshot evaluated against it, replayable by anyone holding the public key. We wanted to see what that looks like at corpus scale. So we ran an experiment.
>
> We passed 300 public UK procurement filings to an LLM agent. The agent was asked to review each filing and recommend a verdict — approve, deny, or flag for review — and to cite the policy clause that justified its decision. The agent was not given the policy text. It reasoned from its training data. Every decision was then recorded through MeshQu against a documented procurement-compliance policy. The resulting corpus of 300 signed receipts is published, downloadable, and verifiable offline.
>
> Before any of the runs, we committed a set of predictions to a public repository — what we expected the corpus to show, what would falsify each prediction, what we deliberately did not predict. [pre-registration commit: hash + date].
>
> This is what the receipts look like.

**Why this is locked**: it nails the voice. Short declarative sentences. The pain is named in plain language ("the firm reconstructs the answer from three sources that were never bound to each other. That reconstruction is not evidence. It is a story told after the fact"). MeshQu enters as infrastructure, not as a pitch. The methodology is sketched in two paragraphs and ends with a closing line that earns the rest of the piece. Use this as the tone-match reference whenever a later section drifts.

**Em-dashes**: the locked reference uses them where they read naturally. The "no em dashes" earlier voice note was a directional caution against using them as a stylistic crutch, not a hard ban. Sam's calibration reference is the actual standard.

After the opening lands:

1. Draft section 5 (results). Everything else is shaped around results.
2. Draft sections 1, 2, and 6 (frame, methodology, argument). The headline narrative.
3. Draft sections 3, 4, 7, 8, 9. Supporting structure.
4. Cross-read by one external reader before publishing.
5. Pre-flight check: every claim is verifiable from the published artefacts. Anything not verifiable gets cut.

## What the writeup does NOT do

- Does not pitch MeshQu. The piece IS the pitch by being credible. Calls-to-action stay in a small footer, not in the body.
- Does not benchmark the LLM. The agent's accuracy is interesting but not the subject. If the writeup becomes about the LLM's accuracy, the framing has drifted.
- Does not make legal claims. The policy is illustrative; the receipts are evidence of process integrity, not compliance certification.
- Does not name customers. There aren't any yet.

## Success criteria

A reader who is an engineer at a regulated firm can:

1. Read the title plus opening section and decide whether to keep reading. ~60 seconds.
2. Read the methodology and rebuild it themselves. ~3 minutes to scan, ~1 evening to run.
3. Verify the receipt corpus offline. ~2 minutes.
4. Forward it internally to their compliance partner with a one-line summary.
5. Cite the experiment in their own work.

If those five hold for a handful of readers at MeshQu's target firms, the artefact has done its job.
