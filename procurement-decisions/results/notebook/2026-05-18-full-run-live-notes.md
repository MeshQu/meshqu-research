# 2026-05-18 — Live observations during the full corpus run

> Contemporaneous notes captured during `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`
> (300-record full corpus run). Append-only. The post-run notebook entry
> (`2026-05-18-full-run.md`) draws on this file rather than reconstructing.
>
> Records here are by hand pick — Sam noticed them and called them out during
> the run. The full corpus is in `decision_traces.jsonl`; this file is the
> curated highlight reel for the writeup's worked-example slots.

---

## Pattern emerging: above-threshold + late publication + missing open-flag → triple critical, agent REVIEWs

Multiple records pasted in real time during the run, same structural shape. The agent consistently chooses REVIEW with `recommended_action` text that names the specific rule territories in plain English but does not escalate to DENY.

### Record 36 — £57M contract, 33-day delay

- **OCID**: `ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/36`
- **Timestamp**: 2026-05-18T10:42:19Z
- **Substrate**: `contract_value=57,000,000`, `publication_delay_days=33`, `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED (substrate honestly absent — OCDS didn't say "open"), `direct_award_justification_present=false`
- **MeshQu**: DENY (4 evaluated, 2 NA). Violations:
  - **PROC-001-S53** — `publication_delay_days=33` > 30 (`VALUE_ABOVE_MAX`)
  - **PROC-002-AUTHORITY** — `contract_value=£57M` > £500k (`VALUE_ABOVE_MAX`)
  - **PROC-005-OPEN-TENDER** — `procurement_method_open_flag` missing (`FIELD_MISSING`)
- **Agent**: `REVIEW` with `recommended_action="Obtain procedure rationale and notice trail"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677a25bce5f8d63511fc7f9ef20c50ec0299d8cce4dd9908545d04c9e7af27a35364`, `log_index=1566819550`

**Why it matters**:
- First record where **PROC-002-AUTHORITY fires** — the £500k authority threshold is much harder to hit on the OCDS substrate's lower-value records, so seeing it on a £57M public contract is the rule working as designed.
- The agent's `recommended_action` text **maps directly onto two of the three MeshQu violations**: "procedure rationale" → PROC-005, "notice trail" → PROC-001-S53. Agent sees + names the structural issues but chooses REVIEW over DENY.

### Record 61 — £3.3M contract, 119-day delay

- **OCID**: `ocds-b5fd17-536c115b-55f7-49c0-83d8-d21788b3f872`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/61`
- **Timestamp**: 2026-05-18T10:44:54Z
- **Substrate**: `contract_value=3,335,171.93`, `publication_delay_days=119` (≈4× the 30-day limit), `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED, `direct_award_justification_present=false`
- **MeshQu**: DENY (4 evaluated, 2 NA). Same three violations as record 36:
  - PROC-001-S53 — `publication_delay_days=119` > 30
  - PROC-002-AUTHORITY — `contract_value=£3.3M` > £500k
  - PROC-005-OPEN-TENDER — `procurement_method_open_flag` missing
- **Agent**: `REVIEW` with `recommended_action="Verify procedure basis and publication compliance"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677a548c2425092f1447fe178b8cc97ef80ddf03121ad336a94c5aa165a131581179`, `log_index=1566824794`

**Why it matters**:
- 119-day publication delay is **way past** the s.53 30-day window. Real-world record of a public contract whose details notice landed nearly 4 months late.
- Same agent verbal pattern as record 36 (verb + "procedure" + "publication"); two-record streak.

### Record 72 — £336k contract, 59-day delay (PROC-002 correctly silent)

- **OCID**: `ocds-b5fd17-a044ca88-7d4c-451e-afe6-2f3247205efc`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/72`
- **Timestamp**: 2026-05-18T10:46:08Z
- **Substrate**: `contract_value=336,000`, `publication_delay_days=59`, `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED, `direct_award_justification_present=false`, `supplier_id="GB-COH-02579852"` (real Companies House number — different ID scheme than records 36/61's `GB-CFS-*`)
- **MeshQu**: DENY (4 evaluated, 2 NA). **Two** violations (not three — PROC-002 NA because £336k < £500k):
  - PROC-001-S53 — `publication_delay_days=59` > 30
  - PROC-005-OPEN-TENDER — `procurement_method_open_flag` missing
- **Agent**: `REVIEW` with `recommended_action="Obtain procedure and publication justification"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677aa9a68f8b4139b9089b70464f802f0420d2dcb5a23c0ee117240d96ba3900851a`, `log_index=1566827700`

**Why it matters**:
- **Contrast with records 36/61/85**: above-PA23-threshold but under-authority-threshold zone (£139k < `contract_value` < £500k). PROC-002-AUTHORITY correctly does NOT fire — the authority-threshold rule's specificity is working.
- **Supplier ID scheme variety surfaced**: `GB-COH-02579852` is a real Companies House registration number (records 36/61 had `GB-CFS-*` which is Contracts Finder Supplier IDs). Both schemes flow through the substrate adapter without normalisation issues.

### Record 81 — £32k contract, 29-day delay (below threshold; likely ALLOW — agent still REVIEWs)

- **OCID**: `ocds-b5fd17-b50fe3af-421f-497c-b405-764d48ff89c0`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/81`
- **Substrate**: `contract_value=32,754`, `publication_delay_days=29` (just inside the 30-day limit), `above_threshold=false` (under PA23 sub-central threshold), `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED, `direct_award_justification_present=false`, `supplier_id="GB-COH-07183575"`
- **MeshQu**: result not captured in real-time paste; from substrate values **inferred to be ALLOW** (PROC-001-S53 and PROC-005-OPEN-TENDER both have `when: above_threshold=true` so both NA on this below-threshold record). Verify post-run via `decision_traces.jsonl` line 81.
- **Agent**: `REVIEW` with `recommended_action="Verify award procedure and justification record"`

**Why it matters**:
- **Strongest evidence yet of agent REVIEW-by-default**: this is the cleanest record we've seen — below-threshold, narrow-margin delay (29d, inside the 30d limit). MeshQu almost certainly ALLOWs. Agent still REVIEWs.
- Agent's `recommended_action` mentions "award procedure" + "justification record" — but PROC-005-OPEN-TENDER is NA on this record (because `above_threshold=false`). **Agent is being cautious about issues the policy explicitly excludes for this record class**. Drift candidate for the writeup.

### Record 85 — £2M contract, 33-day delay (near-duplicate of record 36 shape)

- **OCID**: `ocds-b5fd17-8cac0fcb-4df1-46c1-8a06-9556a2646fbe`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/85`
- **Timestamp**: 2026-05-18T10:47:30Z
- **Substrate**: `contract_value=2,009,954`, `publication_delay_days=33` (same as record 36), `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED, `direct_award_justification_present=false`, `supplier_id="GB-COH-144585"`
- **MeshQu**: DENY (4 evaluated, 2 NA). Same three violations as records 36 + 61:
  - PROC-001-S53 — `publication_delay_days=33` > 30
  - PROC-002-AUTHORITY — `contract_value=£2M` > £500k
  - PROC-005-OPEN-TENDER — `procurement_method_open_flag` missing
- **Agent**: `REVIEW` with `recommended_action="Verify procedure basis and notice trail"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677ac6abbf65d3f26bda715ac4233b6a0bf77375bc6b03fd08d0ad9ff2122e867736`, `log_index=1566830863`

**Why it matters**:
- **Near-identical shape to record 36** (same 33-day delay, same three violations, just lower contract value). Reproducibility-friendly: two different records, same substrate-driven verdict path. The writeup gets a clean "same-shape inputs → same-shape outputs" reproducibility example.
- Agent's `recommended_action` is **structurally near-identical to record 36** ("rationale and notice trail" → "basis and notice trail"). The agent's verbal output is converging on a stable template across multi-violation records — interesting from an LLM-stability angle (P4 territory).

## Cross-record observations (live; will be re-verified against full corpus)

- **Agent REVIEW-by-default pattern**: 5 / 5 of the flagged records → agent REVIEW. Zero agent DENYs in our real-time view, even on records with severe violations (PROC-001-S53 119d, PROC-002 at £57M) and even on the below-threshold likely-ALLOW record 81. Holding strongly at ~85-record scale. If this holds at 300, it's the writeup's headline P1 + P6 finding.
- **Agent verbal template**: `recommended_action` consistently uses [verb] + ["procedure" | "publication" | "notice trail" | "justification"]. Five records, five variants of the same template. Worth a stylometric note in the writeup's "reasoning is data" section.
- **PROC-001-S53 firing distribution (so far)**: 33d (record 36), 33d (record 85), 59d (record 72), 119d (record 61). All real-world late publications, all detected. Substrate honesty win.
- **PROC-002-AUTHORITY firing**: 3 / 4 above-threshold records (36, 61, 85 yes; 72 below £500k). Will need full-corpus distribution to say whether high-value records dominate the DENY column.
- **PROC-004-COI**: consistently NA across every flagged record (`when: exists: true` gate working as designed). Yesterday's [F002 clarification](findings/002-proc-004-coi-absence-clarification.md) doing its job.
- **PROC-006-MOD-CAP**: consistently NA on non-modification records. None of the flagged records are modifications.
- **Substrate variety**: `GB-CFS-*` and `GB-COH-*` supplier ID schemes both flowing through the substrate adapter without normalisation issues. Different OCDS publishers; substrate stays honest about what it received.

## Open watching briefs (not findings yet)

- **Will any record produce agent=DENY before the run ends?** Five flagged, zero. Hypothesis: temperature-0 foundation model is structurally cautious on compliance verdicts. Falsified if any record produces agent DENY.
- **PROC-002-AUTHORITY firing rate across full corpus**: 3/4 of flagged above-threshold records have it, but the flagged set is curated. Full distribution will tell us how much of the corpus is high-value.
- **Multi-violation vs single-violation distribution**: 36/61/85 → triple, 72 → double, 81 → likely zero. Full breakdown needs the corpus.
- **Verbal-template stability**: 5 records, 5 near-identical phrasings of `recommended_action`. Does it ever break the template? Worth checking against the full corpus for "Bears on P4" (LLM non-determinism band).

---

## ~T+5min into the run — in-app analytics screenshot (staging console)

Sam pasted a screenshot of the staging-console analytics for the experiment-procurement tenant at ~176 evaluations. Confirms the patterns from the per-record entries above + adds aggregate-scale observations not visible record-by-record.

### Headline numbers (decision-type `procurement_decision`, all-time-but-effectively-2026-05-18)

- **Evaluations**: 176
- **Pass rate**: 49% (Allow 86 / Review 0 / Deny 90)
- **Failures by severity**: Critical 156, High 3, Medium 0, Low 0
- **Total violations**: 159 (avg 1.77 per DENY record — matches our per-record observations of 2-3 violations per DENY)

### Most triggered rules

| Rule | Firings | % of evaluations | Severity |
|---|---|---|---|
| PROC-005-OPEN-TENDER | 80 | 50.3% | critical |
| PROC-002-AUTHORITY | 44 | 27.7% | critical |
| PROC-001-S53 | 32 | 20.1% | critical |
| PROC-004-COI | 3 | 1.9% | **high** |

### Observations the dashboard makes that record-by-record didn't

- **Zero MeshQu REVIEW verdicts in 176 evaluations.** MeshQu's policy is binary — ALLOW or DENY based on whether any rule fires; there's no synthesized REVIEW outcome. Combined with the agent's REVIEW-by-default streak (5/5 in our flagged records → all REVIEW), this means **P1's agreement projection is asymmetric**: every time the agent picks REVIEW (which is most of the time), agreement = False against MeshQu's ALLOW-or-DENY binary. The writeup must treat agreement non-naively — `==` between three-state agent and two-state MeshQu loses signal. Possible reframings: (a) "did agent's REVIEW correctly flag a record MeshQu DENY'd?" (a precision-style metric), (b) per-rule comparison rather than verdict comparison, (c) ROC-style analysis treating agent REVIEW as a recall threshold. Decision deferred to post-run analysis session.
- **PROC-005-OPEN-TENDER is the most-fired rule (50.3%).** Half of UK public-procurement records in this window aren't "open" tenders by default; substrate honestly omits the open flag and PROC-005's presence rule fires. Real-world finding about procurement-method distribution, not just an artifact.
- **PROC-001-S53 fired on 32 / 176 records ≈ 18%.** Roughly one in five contracts in the corpus window missed the s.53 30-day publication window. This is the experimental rule's real-world hit rate — the writeup's headline number.
- **PROC-004-COI fired 3 times.** This is EXACTLY the count from yesterday's pre-clarification smoke (`smoke-0507305a-…`, 3 records that all DENY'd on PROC-004 under the pre-clarification snapshot `c6256a8e-…`). After F002's clarification was applied (snapshot `cbf12348-…`), PROC-004 has fired **zero times in the 173 post-clarification records**. The dashboard is empirically confirming F002 is doing exactly what it was designed to do: the 3 historical firings are bound forever to the pre-clarification snapshot id; everything after is clean.
- **Volume chart shape**: experiment-procurement tenant traffic is effectively zero before 2026-05-13 (the first phase-A receipts), small bumps on 2026-05-17 (yesterday's smoke + dry-runs), enormous spike on 2026-05-18 dominated by today's runs. The dashboard tells the truth about when this tenant became live.

### Bears on (writeup)

- **P1 (agreement rate)**: needs the asymmetric-projection caveat. Naive `==` comparison loses signal because of the verdict-cardinality mismatch.
- **P2 (rule-firing distribution)**: PROC-005-OPEN-TENDER topping the chart and PROC-001-S53 at 18% is the substantive procurement-policy finding the writeup builds on.
- **F002 promotion to `stable`**: the dashboard's PROC-004-COI=3 count is direct empirical confirmation that the post-clarification snapshot has zero spurious COI firings. After the corpus run completes, F002 can be promoted with this analytics screenshot as evidence.
- **Section 6 (reasoning is data)**: the dashboard itself is an artifact — proves the receipt corpus is queryable in production-grade observability tools, not just JSONL. Reinforces "what an AI-assisted decision's audit trail actually looks like" framing.

### Open watching brief

- **0 MeshQu REVIEW** is a structural property of how the policy is authored (binary "violation present? → DENY else ALLOW"). Some MeshQu policies (not this one) author REVIEW thresholds explicitly. Worth mentioning in the writeup that the asymmetry is a policy-design choice, not a platform limitation.

---

## Correction to the analytics-screenshot section above (mid-run)

Earlier in this file, the "Zero MeshQu REVIEW verdicts in 176 evaluations" observation said:

> "MeshQu's policy is binary — ALLOW or DENY based on whether any rule fires; there's no synthesized REVIEW outcome."

That's wrong, or at least misleading. Sam pointed it out mid-run.

**MeshQu the platform supports a REVIEW verdict.** What's true is that **this experiment's policies were authored as binary** — every rule's severity is `critical`, the policy doesn't include explicit REVIEW thresholds for borderline cases, and the evaluator's "any critical violation → DENY else ALLOW" reduction therefore produces ALLOW/DENY only. That's a policy-authorship choice in `experiment-procurement`'s policy `900996de-…`, not a platform property.

**Why the distinction matters for the writeup**:

- "MeshQu can only produce binary verdicts" would be a platform-limitation framing — and it would be false.
- "These specific procurement policies were authored binary, while the agent's verdict space is three-state" is a **design-decision framing** — and it opens the actual interesting research question: **should some of the rules (e.g. PROC-001-S53 at 31-day delay vs 119-day delay) have had REVIEW thresholds for borderline cases?** A 31-day publication delay and a 119-day publication delay are both PROC-001-S53 DENYs under the current policy, but a reviewer might reasonably treat them very differently.
- This is a stronger writeup hook than the original: the agent's REVIEW-by-default isn't necessarily over-cautious — it might be picking up gradient information the binary policy is throwing away. That reframes the P1 disagreement from "agent is wrong" to "agent is naming something the policy authoring chose not to encode."

**Implications for the post-run notebook entry**:

- The asymmetric-projection caveat still holds — naive `==` agreement is still wrong because the verdict spaces have different cardinalities. But the cause should be named correctly as policy-authoring choice, not platform behavior.
- The P1 reframing question now has a third option alongside "precision-style" and "per-rule": **"what would the agreement projection look like if PROC-001-S53 had a REVIEW threshold at e.g. 60-90 days?"** That's a counterfactual analysis the writeup can run against the corpus (treating 30-60 days as a hypothetical REVIEW band, 60+ as DENY). The corpus is rich enough to support it.
- F-future candidate: "The procurement policy was authored binary. Some PROC-001-S53 violations are 31 days late and some are 119 days late — both DENY under the current policy. The corpus suggests a policy redesign with REVIEW thresholds would change the agent/policy agreement story materially." Not a finding for THIS experiment (which uses the policy as-ratified) but a write-up hook + a follow-up-research candidate.

The original observation up the file stays as-written for the audit trail. This entry is the correction.

---

## AARM Bundle A — the platform roadmap already names this gap

Recording mid-run so the framing doesn't get lost.

The verdict-cardinality asymmetry (agent: ALLOW/REVIEW/DENY; this experiment's policy: ALLOW/DENY) is **not a platform limitation and not a new finding the writeup discovers**. It's a gap MeshQu's product roadmap has already identified and planned for. The experiment provides **empirical support** for already-planned platform work, which is a stronger writeup story than "we found a gap":

### What's planned: [Bundle A — Verdict v2](https://github.com/MeshQu/tradequ/blob/main/.harness/aarm-roadmap/bundles/BUNDLE-A-verdict-v2.md) (Q1–Q2 2027)

Three candidates shipped together against a single receipt v3 envelope migration:

- **[C1 — Classification](https://github.com/MeshQu/tradequ/blob/main/.harness/aarm-roadmap/candidates/C1-classification.md)** (Q3 2026, Tier 1, ships first). Adds a classification dimension on rules: `forbidden | context_deny | context_allow | context_defer`. **Complementary to severity** — severity says "how bad," classification says "what kind of rule." Decouples the two jobs severity currently does.
- **[C2 — MODIFY](https://github.com/MeshQu/tradequ/blob/main/.harness/aarm-roadmap/candidates/C2-modify-verdict.md)** (Q1 2027). Adds a fifth verdict: "approve with transformed parameters" (e.g. a £57M procurement clamped to the authority-tier max). Receipt records both original and modified parameters, cryptographically bound.
- **[C3 — DEFER vs STEP_UP](https://github.com/MeshQu/tradequ/blob/main/.harness/aarm-roadmap/candidates/C3-defer-stepup.md)** (Q1 2027). Splits the current REVIEW verdict into STEP_UP (decision shape is understood, needs elevated authority) and DEFER (decision can't be made yet, needs more context).

### The writeup framing this unlocks

The honest paragraph for the writeup:

> "During the corpus run we observed an asymmetric verdict-space mismatch: the foundation model reasons in three states (ALLOW / REVIEW / DENY) plus a free-text recommended_action; the experiment policy was authored binary because all rules carry severity=critical and the current evaluator reduces critical → DENY. The platform roadmap already identifies this gap (AARM Bundle A — Verdict v2, planned Q1–Q2 2027) and plans a classification dimension plus MODIFY and DEFER/STEP_UP verdicts to address it. This corpus is a record of what binary-policy verdict projection looks like at scale across real-world procurement records; future corpora under Verdict v2 would be the comparator. The asymmetry is not an artifact of platform capability — MeshQu the platform supports REVIEW (and will support MODIFY / STEP_UP / DEFER) — but a function of how this specific policy was authored against the currently-shipped verdict primitive."

That framing is stronger than the alternative ("we found a UX gap") for three reasons:

1. **It's true.** The roadmap pre-dates the experiment. The gap was named conceptually before the corpus surfaced it empirically. Both halves of the argument deserve credit.
2. **It connects to product strategy.** The writeup becomes a piece of evidence in a longer-running conversation about what audit-trail primitives need to evolve into. Not just "AI + rules disagree."
3. **It generalises beyond procurement.** The "binary policies project away gradient information that AI systems naturally encode" point is independent of the s.53 publication-delay rule. A future researcher applying this methodology in a different domain (LC validation, AML, healthcare prior authorisation) would hit the same wall and the same Bundle A solution.

### Counterfactual analysis the corpus enables

The corpus is rich enough to support a re-projection without re-running: **"what would agreement have looked like if PROC-001-S53 had a REVIEW band at 31–60 days and DENY only at 60+ days?"** The pre-registration discipline stays intact (we don't retrospectively change PROC-001's authored thresholds for the headline finding) but the writeup gets to show:

- Headline: agreement under the binary policy as-authored.
- Counterfactual: agreement under a hypothetical 3-tier policy.
- Difference between the two: an empirical estimate of how much of the "agent over-cautious" gap is actually "policy under-expressive."

That's a concrete piece of supplementary analysis that turns the verdict-cardinality observation from a methodological caveat into a substantive finding.

### What's NOT in Bundle A (and what we're shipping anyway)

The standalone Tier-1 visibility fix — "show the live severity → verdict mapping under the severity picker in the v2 editor" — is **not part of Bundle A**. Bundle A fixes the underlying conceptual problem (verdicts and classification) but doesn't fix the "implicit mapping is invisible at edit time" UX problem standalone. Between now and Q3 2026 (when C1 ships) authors will keep making the same binary-by-accident mistake we did unless the visibility fix lands separately.

Filed today as **F14** in the moderated UX test doc (tradequ PR #541, `docs/ux/policy-authoring-2026-05.md`). Half-day standalone PR; doesn't preempt Bundle A.

### Memory hook for future sessions

The writeup's "what we'd recommend the platform do differently" section should:

1. Point to **Bundle A as the strategic answer** (already planned; this corpus is empirical support).
2. Recommend **F14's Tier-1 visibility fix** as the tactical interim measure (ships independently; prevents the next binary-by-accident).
3. Treat the **counterfactual re-projection** as supplementary analysis the methodology section can show.

This framing also affects how F004 should be promoted post-run: F004 is a methodology finding (apparatus-gap caught + fixed); the verdict-cardinality observation is a product-design empirical finding that maps to an already-planned bundle. They're different in kind and should be filed accordingly when the corpus run is fully analysed.

---

## Post-run corpus shipment — corpus.tar landed + verified

Post-run packaging delivered. All 283 unique bundles fetched from staging (with rate-limit pacing — staging tenant tier kicked in after ~60 fetches; backed off + paced at 2s for the remaining 223; all 223 recovered) and packed into a single tar at `procurement-decisions/results/corpus.tar`.

| | |
|---|---|
| Archive size | 5.3 MB uncompressed (5,297,664 bytes) |
| Entries | 285 (1 README + bundles/ dir + 283 bundle files) |
| Bundle structure (each) | `receipt.json` + `policy_snapshot.json` + `trusted_keys.json` + `transparency_proof.json` + `bundle_manifest.json` + top-level `manifest` |
| Validation | 283/283 bundles validated structurally (all carry the expected `files.receipt.json` + `files.bundle_manifest.json` + `files.policy_snapshot.json` keys) |
| **SHA-256** | **`1b6192df6eb5d3c38738b6abc5cea82c92d99d53ae890308569a4c240c232be0`** |

`results/corpus.tar` includes a `README.md` covering: run metadata, three verification paths (verify.meshqu.com / `@meshqu/verifier` CLI / independent Rekor lookup), and pointers back to the planning + notebook + findings docs.

Manual bundle verification at verify.meshqu.com produced "Bundle Verified with Caveats" on both worked-example decision_ids (`7b6ead10-…` for the ALLOW agreement case, `ca19e737-…` for the £57M triple-violation DENY case) — screenshots committed under `results/observability/screenshots/`.

**Item 1 from yesterday's pending-Sam-owned list is now closed.** All four remaining items (F002 promotion, OCDS-dupe investigation, counterfactual PROC-001-S53 REVIEW-band re-projection, writeup itself) stay open as separate sessions.
