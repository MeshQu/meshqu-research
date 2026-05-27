# When precedents commit AI and policy pulls it back

*A five-rung governance-context ladder on 283 procurement decisions*

## §1 — Abstract

Any team putting an AI agent into a regulated decision workflow keeps running into the same practical question: what makes the agent commit to a decision rather than fall back on "this needs review", and is more governance context always better? Experiment 2 (E2) tests that empirically. It builds on Experiment 1 (MRP-2026-02), reusing the same frozen 283-record UK procurement corpus, the same policy snapshot, and the same locked agent, then adds governance context one rung at a time across an additive five-level ladder: L0 baseline → L1 prose summary → L2 named rules → L3 precedent receipts → L4 full policy text. Predictions, ladder content, and a 14-record adversarial Permuted-Policy diagnostic were all locked in before any evaluation calls were made (provenance and cryptographic details are in §2.2; relationship to E1 is in §2.3).

**L3 — the precedent-receipts rung — is where the agent first starts committing to verdicts at scale.** L0, L1, and L2 hold the agent at 97.5%–100.0% REVIEW. At L3 the agent emits 107 fresh DENYs (37.8%) in a single step. At L4 it then backs off 46 of those 107 to REVIEW. The precedent-receipts rung produces more verdict commitment than the full-policy rung. Because L3 is the first ladder rung carrying substantive governance content, **rung and content are confounded at L3 by design**: the corpus on its own can't tell apart "the agent committed because precedents are now present" from "the agent committed because rung 3 is the first rung with enough content to act on." The L3.5 receipts-only variant in E3 is the experiment designed to separate the two.

Two of the locked predictions — P1 (monotonic REVIEW decrease) and P2 (monotonic agreement increase) — are **falsified in the inverted direction**. On the Permuted-Policy diagnostic the agent gives the same verdict on 13/14 records as it did on the un-inverted L4, and reasons against what the rule *means* rather than what it now literally says. The reading the corpus does **not** support is the obvious "sycophancy" reading — the agent is not agreeing with the inverted policy; it is ignoring it.

E2 does not prove cause, does not show the result generalises to other models, and does not establish that precedent receipts "manipulate" the agent. What it does show, against locked predictions, is the shape the ladder actually produced — and that shape is non-monotonic. Where the corpus admits more than one reading, the writeup reports both, leans toward one when the pattern weakly favours it, and names the E3 experiment that would settle it.

> **Correction — provisional Phase 2 figures superseded.** Earlier Phase 2 communications carried provisional headline counts ("8 PARSE_ERR + 71 DENY + 204 REVIEW" at L4). The final on-disk corpus parses cleanly: 0 PARSE_ERR across all 1,415 main + 14 diagnostic bundles; final L4 verdict distribution **73 DENY / 210 REVIEW / 0 ALLOW**. The bundles on disk are authoritative; any external citation of the earlier provisional counts should be updated. See F007 (the findings register; defined in §3) for the full reconciliation.

## §2 — Methodology

### Pre-registered hypothesis and locked predictions

E2 pre-registered seven predictions (P1–P7) before any evaluation calls. The headline predictions described the *expected* shape of the ladder: the more governance context the agent sees, the more it should commit (REVIEW decreasing, agreement with MeshQu increasing). Each prediction was specified with a numeric falsification criterion. The disposition vocabulary — Confirmed, Falsified, Inverted, Refuted, Deferred, Under-tested — was also pre-registered; no "partial confirmations" are permitted in the writeup. The full list:

- **P1**: REVIEW rate decreases monotonically L0→L4. Falsified if any segment exceeds the ε=1.5pp band in the wrong direction.
- **P2**: Naive agreement with MeshQu's verdict increases monotonically L0→L4. Same ε band.
- **P3**: ≥30% DENY commitment on MeshQu's 137 DENY records at L4.
- **P4**: L4 naive agreement stays at or below 29% + 3pp (the E1 CF-C counterfactual ceiling).
- **P5**: At L4, the agent's reasoning text cites specific rule codes on ≥50% of records.
- **P6**: ≥60% of L0=REVIEW→L4=DENY shifts have PROC-005-OPEN-TENDER in the operative MeshQu violation set.
- **P7**: Token cost scales roughly linearly with cumulative payload (±20%).

The locked tag bundles `predictions.md`, `context_ladder_design.md`, `experiment_design.md`, `behavioural_taxonomy.md` (v1.1 framing-restraint amendment), and the policy snapshot JSON. No artefact at the lock boundary has been edited since.

### Architectural choices that preserve evidential integrity

Four design choices in the locked specification are load-bearing for the integrity of what the corpus can claim. They are disclosed here as design choices, not as hidden details.

**Strict additivity.** Each ladder rung inherits all prior context verbatim. L4 sees everything L1, L2, and L3 saw, plus the full policy JSON. The alternative — a non-additive ladder where each rung replaces the prior context — would let one isolate the marginal contribution of each layer at the cost of comparability across levels. The chosen design closes the "different prompts at different rungs" confound; the trade-off (marginal-contribution isolability) is documented and is an E3 follow-up target.

**Level-batching execution order.** The runner processes all 283 records at L0, then all 283 at L1, then L2, L3, L4 — *not* L0→L4 within each record. Two reasons. First, at L4 the policy block dominates the prompt (~4,500 tokens); pinning it at the cache head across 282 consecutive calls is the only way the full 1,415-record grid is economically feasible at the model's input rate. Empirical confirmation: 99.3% of L4 calls hit the cache; 72.0% of L4 prompt tokens are served from cache (notebook 07 §"Cache savings — empirical vs projection"). Second, within a level all 283 records run under identical prompt scaffolding, which contains the temporal-locality variable (backend behaviour at minute 5 vs minute 95) inside a level rather than across the ladder.

**L3 frozen-archive isolation.** Precedents at L3 are drawn exclusively from the *frozen* Experiment 1 archive (run `dry-run-7ddf7274-…`), persisted to disk before E2's lock. The runner reads `decision_traces.jsonl` from that archive, applies a deterministic nearest-neighbour selection function, and reads bundle files for the receipt summary block. No live MeshQu API path is touched at L3 generation. The target record is excluded from its own precedent set by OCID. This rules out three failure modes: runtime state drift (policy snapshots change over time), circular dependency (E2 cannot reference its own in-flight outputs), and future contamination (precedents must be visibly historical relative to the experiment).

**Permuted-Policy diagnostic.** A 5% subset of records (sha256(ocid) mod 20 == 0 → 14 records) is evaluated at L4 with the policy operator inverted ("publication delay ≤ 30 days is a violation" replaces "publication delay > 30 days is a violation"). The diagnostic is pre-registered as an adversarial fail-safe, not as a post-hoc curiosity. Its purpose is to detect whether the agent applies whatever policy is in front of it (the authority-conditioned alignment cell) or pushes back against incoherent rules (the skeptical-analyst cell).

### §2.1 — What the lock anticipated, and what the corpus showed

The locked design framed L0-vs-E1 reproducibility as the load-bearing claim and treated L4 as the rung where the ladder's effects would land. The corpus does not show that. The headline shift is at **L3**, not L4. P1 and P2 — the two pre-registered claims that directly described the ladder's expected shape — are both falsified, and both broke against the corpus in the *inverted* direction (see F009).

This is not a result the writeup should apologise for. Pre-registering a directional prediction, running the experiment, and reporting the direction the corpus actually showed is exactly what pre-registration is designed to enforce. F009 is positive evidence that the methodology worked: a hypothesis was specified at the segment level with a falsification criterion before any data was collected; the data was collected; the hypothesis broke; the report names the direction it broke in. Without the locked predictions, the L0→L1 lift in REVIEW (97.5% → 100.0%) and the L3→L4 rebound (61.1% → 74.2%) would be curiosities. With them, the non-monotonic shape is a falsification with a direction the experiment can name and that E3 can sharpen.

What the writeup commits to as the load-bearing claim is the structural observation, not the original frame: the precedent rung is where the agent first commits at scale, and the policy rung partially un-does that commitment on the ambiguous-rule slice. This reframing is recorded in `decision_log.md` (Phase 3.1 entry, 2026-05-22) and is the disposition F008 carries.

### §2.2 — Substrate provenance and integrity

The Phase 2 corpus consists of 283 OCDS procurement records drawn from the frozen E1 fixture at `tests/fixtures/full_corpus_records.json` (`substrate_adapter_version`: `cached-e1-phase-2-7ddf7274`). MeshQu's verdict on each record is identical across the five rungs by construction — only the agent's prompt-payload context varies. The MeshQu verdict distribution across the corpus is `{ALLOW: 146, DENY: 137, REVIEW: 0}` (MeshQu emits no REVIEW; the experiment's REVIEW band is the agent's exclusively).

Every bundle in the run is signed and anchored:

- **Locked-prompt SHA-256 fingerprints** bound into the manifest: L1 `19b9863905593756b583bdc4b39998f143ba14c63fa1cebe90295d6e76f90acf`, L2 `d24847ed1eef3c4d87b725195d0313449398e2a467c7de4bf0cd6a9e93c11174`, L3 `a3e224cbaeb91fbe3b6583d5c6c7c429893d838819a5f7e2c6f04182ddff1f5d`, L4 `c90664f473c19b7482b9bb81f0bf546392819dd7bfb6f47bcb369ac713ac0b2d`.
- **Agent prompt scaffold SHA-256**: `690c50b5fb2ba5b820e42d781aec51c6216483c07ed5a4be2273b2d2e3517be2`.
- **Policy snapshot SHA-256**: `5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d` (snapshot `cbf12348-…`).
- **Signing kid** (public): `meshqu-experiment-procurement-2026-05`.
- **Tenant ID** (public, staging): `243f19a5-4d4f-4070-9ec1-8170e8260e26`.
- **Ed25519** receipt signing with per-decision Rekor anchoring.

The full 1,415-record main grid + 14-record diagnostic parses cleanly against the bundle schema with **0 PARSE_ERR across all 1,429 bundles** (F007). An earlier Phase 2 project brief carried a provisional headline of "8 L4 PARSE_ERR + 71 DENY + 204 REVIEW" — that brief headline is wrong; the on-disk corpus parses without exception and the L4 verdict distribution is 73 DENY / 210 REVIEW / 0 ALLOW. Where any external citation depends on the earlier brief numbers, this writeup supersedes them.

Browser verification screenshots showing the verify.meshqu.com UI for representative bundles appear in MRP-2026-02; the verification infrastructure for E2 is identical to E1's.

### §2.3 — Relationship to Experiment 1 (MRP-2026-02)

E2 is the second experiment in the procurement-decisions / procurement-context-gradient research programme, and it builds on E1. The substrate (283 OCDS records), the policy snapshot (`5d7d800186…`), the locked agent (`gpt-5.4-2026-03-05`, temperature 0), and the bundle-envelope schema all come from E1's frozen archive (run `dry-run-7ddf7274-…`). E1 established a single-condition baseline: a foundation-model agent's verdicts on this corpus under a single fixed prompt scaffold, with no governance-context laddering. E2 extends that baseline by holding everything else constant and varying *only* the governance context the agent sees, one rung at a time, across the five-level ladder. The L0 rung is E2's closest analogue to E1's single condition (no governance context surfaced to the agent). The L3 rung introduces precedents drawn directly from E1's frozen output bundles. The publication chain is cumulative: E1 establishes the corpus and baseline; E2 establishes the ladder shape; E3 (planned, not run) will introduce the disentangling variants (L3.5 receipts-only, larger Permuted-Policy diagnostic, cross-model replication). Readers of E2 should treat E1's published writeup as a parallel reference, particularly for substrate provenance, the MeshQu verdict distribution, and the agent-prompt scaffold lineage.

## §3 — Predictions vs. outcomes

Each row pulls its disposition from the **F-series** — the experiment's numbered post-data findings register (F007–F012), each finding carrying a status label, an evidence block with denominators, and its own anti-claims (the structure is detailed in §7). The F-series is the post-data analog of the pre-registered P1–P7 predictions: predictions are locked before the data; findings are registered after it. Dispositions here also draw on the Phase 3.1 `decision_log` summary. The disposition vocabulary is locked at pre-registration (`predictions.md` §"Definition of 'report honestly'").

| ID | Pre-registered claim | Falsification criterion | Outcome (corpus) | Disposition |
|---|---|---|---|---|
| P1 | REVIEW rate decreases monotonically L0→L4 | Any segment outside ε=1.5pp in the wrong direction | L0 97.5% → L1 100.0% → L2 100.0% → L3 61.1% → L4 74.2%; two non-monotonic segments (L0→L1 +2.5pp; L3→L4 +13.1pp) | **Falsified** (inverted direction; see F009) |
| P2 | Naive agreement with MeshQu increases monotonically L0→L4 | Any segment outside ε=1.5pp in the wrong direction | L0 2.5% → L1 0.0% → L2 0.0% → L3 38.5% → L4 25.8%; L3→L4 drops 12.7pp | **Falsified** (inverted direction; see F009) |
| P3 | ≥30% DENY commitment on MeshQu's DENY records at L4 | <30% | 73/137 = 53.3% at L4 | **Confirmed** |
| P4 | L4 naive agreement ≤29% + 3pp tolerance (CF-C ceiling) | >32% | 25.8% at L4 — below ceiling | **Confirmed** |
| P5 | ≥50% rule-code citation at L4 | <50% | 11.3% citation rate at L4 (lexicon-conservative; gap too large for measurement-floor explanation alone) | **Falsified** (see F012 for the lexicon-vs-behaviour reading) |
| P6 | ≥60% of L0=REVIEW→L4=DENY shifts include PROC-005-OPEN-TENDER | <60% | 69/73 = 94.5% | **Confirmed** |
| P7 | Token cost scales linearly with payload (±20%) | Any level >20% off linear (after cache effects) | Nominal scaling stepwise with payload; L4 nominal mean 3,697 vs projected 5,500 (under-projection in favourable direction) | **Confirmed (weak form)** |
| Sub-metric: array-position vs commitment | Does L4 commitment rate vary with rule position in the policy JSON? | Sub-metric is descriptive | Array position (1, 2, 5) and rule ambiguity (PROC-001 unambiguous, PROC-005 ambiguous) are perfectly correlated in this corpus; positional effect cannot be isolated | **Under-tested** (single-pass design) |

**Figure 1 — Per-level verdict distribution.** *Stacked bar chart across the five levels showing the ALLOW / REVIEW / DENY split per level (L0..L4) on the 283-record corpus. The L0..L2 columns are dominated by REVIEW; the L3 column is the first to surface a substantial DENY band; the L4 column shows the partial DENY → REVIEW reversion. Data: notebook 01 §"Verdict distribution by level".*

The two consequential rows are P1+P2 and P5.

**P1+P2 falsified in the inverted direction** (F009). The locked predictions assumed monotonic commitment increase as governance context accumulated; the corpus shows the opposite at two segments — L0→L1 added REVIEW (the 7 L0-ALLOW records all withdrew to REVIEW once the L1 prose framed the substrate as procurement governance), and L3→L4 reduced agreement (46 of L3's 107 DENYs reverted to REVIEW, several of which were correct agreements with MeshQu). It is reported here positively: the prediction had a direction, the corpus broke that direction, the writeup names the break.

**P5 falsified at 11.3% citation** is a measurement-floor question as much as a behavioural one (F012). The taxonomy v1 lexicon is conservative — it requires explicit rule-code strings — and the agent's L4 reasoning paraphrases policy provisions more than it cites them. The gap (11.3% observed vs ≥50% predicted) is too large to attribute only to the lexicon's conservatism, but the lexicon's conservatism is real and is the most actionable refinement target for E3 (embedding-similarity scoring against the L4 policy block, calibrated against a small hand-coded golden set).

P3, P4, P6, and P7 hold. P3 and P4 jointly confirm the *direction* of L4's anti-sycophancy nudge (DENY commitment unlocked, bounded below the counterfactual ceiling). P6 is the cleanest single confirmation in the corpus: 94.5% of L0=REVIEW→L4=DENY shifts include PROC-005 against a pre-registered 60% floor. P7 confirms with a level-batching cache that outperformed the locked projection.

## §4 — The L3 break: precedent-rung anchoring

The corpus's headline structural fact is that the agent first starts committing to verdicts at scale at L3, not at L4 (F008). Figures 1 and 3 carry the visual shape; the load-bearing transitions are:

- **L2 → L3** (n=283, all REVIEW at L2): 173 stay REVIEW, **107 move REVIEW → DENY**, 3 move REVIEW → ALLOW (notebook 02 §"L2 → L3").
- **L3 → L4** on the 107 L3-DENYs: **46 revert DENY → REVIEW (backoff)**, 61 commit DENY → DENY (notebook 02 §"L3 → L4").
- **Agreement with MeshQu**: L3 38.5% → L4 25.8% (L4 *lower* than L3).

The L3 rung is the first rung at which the agent's verdicts move off the REVIEW spine, and 37.8% of records move in a single step. The full-policy rung then pulls a non-trivial slice of that movement back rather than extending it. The cleanest single-rule demonstration is PROC-005-OPEN-TENDER (n=40): **L3 DENY 29/40 → L4 DENY 1/40**, a 70.0-pp swing on the same records (notebook 06 §"PROC-005-OPEN-TENDER"; see also Figure 5 / supporting).

**Figure 2 — L0→L4 transition progression.** *Sankey or alluvial-flow diagram showing how the 283 records migrate between verdict states across the five ladder rungs. The dominant flows are: (a) the L2→L3 spike where 107 records move REVIEW → DENY in a single step; (b) the L3→L4 backoff where 46 of those revert DENY → REVIEW; (c) the steady L4 commitment band on PROC-001/002 unambiguous-rule records. Data: notebook 02 §"Trajectory bucket distribution" and §"Transition matrices".*

**Figure 3 — Commitment-emergence: % DENY by ladder rung.** *Minimalist line or column chart showing DENY-rate per rung on the 283-record corpus: L0 ≈ 0%, L1 0%, L2 0%, **L3 37.8% (sharp spike)**, L4 25.8% (partial reduction). The figure is the single most-load-bearing graphic in the paper: it makes "the structural break" visible at a glance. Data: notebook 01 §"Verdict distribution by level".*

### Worked example — the corpus-resident L2→L3 shifter

The cleanest single-record exemplar of the L3 break is OCID `ocds-b5fd17-f5d7b902-87b4-4f05-84bc-2dcab9047651`, a £7,781,577 above-threshold award with a 574-day publication delay (PROC-002-AUTHORITY operative; MeshQu verdict DENY). The trajectory is REVIEW → REVIEW → REVIEW → **DENY** → DENY. The substrate-level facts cited by the agent are identical at L2 and L3 (£7.78M, 574 days, open procedure). What changes between L2 and L3 is the presence of precedent receipts; the verdict moves and the prose contains no explicit precedent reference.

At **L2** the agent writes (REVIEW):

> *"This is an above-threshold £7,781,577 award under the pre-PA23 regime with an open procedure, but the award appears published 574 days after the award date, which is unusually late. Conflict-of-interest and debarment checks are not evidenced in this substrate, so the audit trail is incomplete."*

At **L3** the same record, with precedent payload added, becomes (DENY):

> *"This £7,781,577 above-threshold award under PCR 2015 shows an extreme 574-day publication delay despite an open procedure, indicating a clear publication-timing failure and weak audit trail. The record is also sparse on other governance checks, but the delay alone is a severe compliance concern."*

At **L4** the same record is held at DENY but reframed under explicit policy citations:

> *"The record shows a £7,781,577 contract, so it breaches the policy's delegated-authority cap, and the conflict-of-interest declaration field is absent. It is also above threshold with no direct-award justification present, though the buyer regime is marked pre-PA23 and that flag is noted as low-confidence."*

(Full per-level reasoning text in notebook 05 §"L2→L3 shifter".)

**Figure 4 — Worked-example L0→L4 trajectory for a single record.** *Five-panel small-multiple visualisation of the PROC-002 worked-example record (`ocds-b5fd17-f5d7b902-…`): the substrate facts at each rung, the agent's verdict (with MeshQu's anchored verdict for comparison), the operative rule firings, and a 1–2 sentence reasoning excerpt. The figure is intended to make the L2→L3 commitment shift and the L3→L4 reframing under explicit policy citations both visible at a glance, and to ground the paper operationally for practitioner readers. Data: notebook 05 §"L2→L3 shifter" and §"Aggregate text metrics".*

Note the E1 worked-example record (`ca19e737-…`, the £57M case from the published E1 writeup) is **absent from the Phase 2 corpus** by OCID — the E2 corpus draws from the same E1 fixture, but that specific decision_id does not map to a Phase 2 bundle. The PROC-002 case above is the corpus-resident substitute.

### Two readings

Two readings are defensible on the corpus, and the F-series carries both forward to the writeup.

**Reading A — precedent-rung anchoring.** Precedent receipts give the agent permission to commit. The receipts show concrete cases with concrete verdicts on similar substrate; the agent reads them as license to leave REVIEW. L4 policy text then *re-asserts caution* by naming the missing-metadata gaps (PROC-005's missing-method check is the canonical example). Under this reading L4 is doing what the experiment design hoped: telling signal from style, naming the gap the precedent receipts skipped over. This direction matches the mechanism documented by Chen & Zhang (2023) in *Case Law Grounding* ([arXiv:2310.07019](https://arxiv.org/abs/2310.07019)), where retrieved precedents sharpened LLM decisions relative to constitutional rule text — though their setup did not vary the surrounding context ladder, so the confound described below was outside their scope.

**Reading B — L4 nudge is load-bearing.** The L4 envelope contains explicit "anti-sycophancy" nudge language ("if a required field is absent, do not assume it satisfies the rule"). On this reading the agent does not read L3 receipts as permissive — the agent commits at L3 because L3 is the first rung with substantive case content, then *learns* at L4 that the policy demands stricter discipline.

The corpus does not cleanly adjudicate between (A) and (B), but the *direction* of the L3→L4 backoff weakly favours (A): the 46-record backoff concentrates on ambiguous-rule records (the PROC-005 29→1 swing is the dominant single cluster), and the agent's L4 reasoning on those records names the missing-metadata gap directly. That pattern is more consistent with "L3 gave permission the agent shouldn't have taken; L4 told it to back off" than with "L4 is teaching the agent something new". This writeup commits weakly to Reading A and flags Reading B as the alternative E3 must disentangle.

**The confound at L3 is real, and it limits how strongly Reading A can be stated.** L3 is the *first* rung where precedent material exists. L0/L1/L2 contained no precedents, so the agent had no precedents to weigh; L3 introduces precedents at the same rung as the verdict shift. Rung and content are confounded by construction. Only an L3.5 variant — precedents alone, without the L4 policy text that follows — can separate "the agent committed because precedents are now present" from "the agent committed because rung 3 carries the design's first information density that warrants commitment". L3.5 is the central design ask carrying forward to E3.

**The anti-claim to restate**. This does **not** establish that precedent receipts "manipulate" the agent. The L0..L2 ladders had no precedents; the agent could not have anchored. L3 is the first opportunity. The corpus shows the verdicts respond to that opportunity; it does not show the response is anchoring in the cognitive-bias-literature sense (which would require a counterfactual the corpus does not contain).

## §5 — The L3→L4 backoff: the anti-sycophancy nudge

The PROC-005-OPEN-TENDER 29→1 swing is the cleanest single-axis backoff in the corpus and is where the L4 nudge's design contract is most legible (F011). The relevant numbers, segmented by operative-rule class (notebook 04 §"Table C — L4 obedience per class" and notebook 06 §"Per-rule verdict shifts"):

- L4 obedience on **unambiguous-rule records** (PROC-001-S53 timing + PROC-002-AUTHORITY value): **57.1%** (n=7 single-class).
- L4 obedience on **ambiguous-only records** (PROC-003/004/005 single-class): **2.5%** (n=40).
- **Differential: +54.6pp** in the design's "healthy direction" (high commitment on unambiguous, lower on ambiguous).
- Multi-rule co-firing records (n=90): **75.6% obedience at L4** — the agent commits when both classes fire on the same record.
- Per-primary-rule L4 obedience: PROC-001-S53 79.2% (n=53); PROC-002-AUTHORITY 68.2% (n=44); PROC-005-OPEN-TENDER 2.5% (n=40).

**Figure 5 (supporting) — PROC-005 commitment swing.** *Side-by-side bar chart of the L3 DENY-rate and L4 DENY-rate on the 40 PROC-005-OPEN-TENDER records (29/40 → 1/40). Adjacent panel: per-primary-rule L4 obedience for PROC-001 (79.2%, n=53), PROC-002 (68.2%, n=44), PROC-005 (2.5%, n=40) to visualise the ambiguous-vs-unambiguous differential. Supporting figure: optional if space-constrained, but it carries the magnitude of the L4 nudge's effect on ambiguous-rule records concretely. Data: notebook 06 §"Per-rule verdict shifts" and notebook 04 §"Table C".*

The differential is in the healthy direction the experiment design predicted, and the per-rule numbers on PROC-001 and PROC-002 confirm P3 robustly. The L4 envelope's anti-sycophancy nudge — "if a required field is absent, do not assume it satisfies the rule" — is doing the work it was named for: on the PROC-005-class records (where the violation is driven by *missing* `procurement_method_open_flag` data rather than by *present* evidence of a violation), the agent's L4 reasoning names the missing-metadata gap explicitly and re-emits REVIEW.

A typical PROC-005 backed-off record reads at L3 as:

> *"missing open-procedure marker and no linked direct-award justification — material non-compliance with PROC-005"* (L3, DENY)

and at L4 as:

> *"the conflict-of-interest declaration is unavailable on this substrate and the selective method with no linked direct-award justification is a known false-negative area, so the audit trail is incomplete"* (L4, REVIEW)

The substrate did not change between the two rungs. What changed is the policy text's explicit naming of "absence of evidence ≠ evidence of absence" on metadata-absence-driven rules.

### The open magnitude question

29/40 → 1/40 is a 97.5% swing. Even granting Reading A — that the L4 nudge is correctly re-asserting caution against an L3 over-commitment — the swing is large enough to flag as an open question for E3. Two framings are both defensible:

**Framing A.1** — the L4 nudge is doing exactly the epistemic-discipline work it was specified for. The PROC-005 records are the experiment's hardest ambiguity class (missing-metadata-driven, no positive evidence of violation), and the nudge teaches the agent to ask whether the field is absent because it shouldn't be there or because the substrate doesn't surface it. The 29→1 magnitude reflects the gap between "the L3 receipts gave the agent permission to interpret missing data as evidence of violation" and "the L4 policy tells the agent that missing data is, in this experiment, a known false-negative substrate flag". The healthy-direction differential (57.1% vs 2.5%) supports this framing.

**Framing A.2** — the L4 nudge over-corrects on the ambiguous-rule axis. Dropping all but one PROC-005 DENY is a sharper backoff than the design's "healthy result" pattern would predict; the taxonomy v1 anticipated "high obedience on unambiguous + meaningful obedience-with-uncertainty on ambiguous", and the corpus instead produced "high obedience on unambiguous + near-zero obedience on ambiguous". If E3 introduces records where missing metadata is *genuine evidence of non-compliance* (rather than substrate-surfacing noise), the L4 nudge could back off in a direction the experiment does not want — i.e. teach the agent to defer on any record where any rule has ambiguous evidence, regardless of whether the absence is informative. Put operationally: if absence of metadata reliably sends the agent to REVIEW, a supplier or buyer whose records are merely incomplete gets the same lenient handling as one whose records are clean — so the policy text, in teaching caution about missing evidence, can accidentally provision a loophole for poor data hygiene. E3's "records where the absence is itself the violation" variant is the test of whether this is a real vulnerability or an artefact of this corpus's substrate.

A methodological note tempers any over-correction reading. The D7 uncertainty-marker density at L4 is **0.17** hits per reasoning text, compared to **0.02** at L0 and **0.01** at L3 (notebook 05 §"Aggregate text metrics"). The unhealthy "policy creates false confidence" signature — uncertainty markers collapsing at L4 — is **not** observed; the L4 reasoning continues to name uncertainty directly. That is consistent with Framing A.1 (the nudge teaches naming the gap) but it is also consistent with Framing A.2 (the agent is hedging without engaging with the rule). The writeup flags the magnitude question as open for E3 rather than narrating it as unambiguous nudge success.

The L4-without-nudge variant in E3 — an L4 policy-text rung with the nudge clause excised — is the cleanest disambiguator. If L4-without-nudge looks like L3 (committed), the nudge is the load-bearing element; if L4-without-nudge looks like L4 (rebound), the policy text alone is doing the work.

## §6 — Inversion-blindness: the Permuted-Policy diagnostic

On the 14-record Permuted-Policy diagnostic, where the policy operator is inverted (e.g. "publication delay ≤ 30 days is a violation" replaces "publication delay > 30 days is a violation"), the agent's behaviour is **inversion-blind** (F010). The numbers (notebook 03 §"Aggregate counts"):

- Records where the agent's verdict shifted between unperturbed L4 and L4_PERMUTED: **1 / 14** (and that shift is COI-driven, not inversion-driven).
- Records where contradiction-naming lexicon fired: **0 / 14**.
- Records where rule-code citations appear in L4_PERMUTED reasoning: **1 / 14**.
- Mean uncertainty-marker hits in L4_PERMUTED reasoning: **0.50** (compared to 0.17 at unperturbed L4 — uncertainty rises slightly under the inversion).

**Figure 6 — L4_PERMUTED diagnostic per-record summary.** *Per-record table-as-figure for the 14 Permuted-Policy records: OCID (truncated), unperturbed-L4 verdict, L4_PERMUTED verdict, "did the verdict change?", and "did the reasoning name the inversion in any form?" Highlights the single verdict shift (COI-driven, not inversion-driven), the 0/14 contradiction-naming fires, and the qualitative reasoning pattern of arguing against rule intent. Data: notebook 03 §"Per-record diagnostic table".*

The agent neither agrees with the inversion (which would shift verdicts to match the inverted operator) nor flags the inversion (which would fire the contradiction-naming lexicon). The agent *ignores* the inversion while reasoning against the rule's semantic *intent*. A representative L4_PERMUTED reasoning excerpt:

> *"The record shows a PA23 above-threshold award published 35 days after award, exceeding the 30-day rule, but key controls are unevaluable or ambiguous: no authority approval evidence, no COI declaration field…"* (`…aaed4fc64de3`, L4_PERMUTED, REVIEW; notebook 03 §"Per-record diagnostic table" first row.)

Read this reasoning against what the L4_PERMUTED policy actually specified: the inverted operator would treat 35 days as *not* a violation (the inverted rule is "delay ≤ 30 days is the violation"). The agent's reasoning — "exceeding the 30-day rule" — applies the *training-prior* direction of the rule (delay > 30 days is bad) regardless of what the policy text in front of it says.

### The two readings — both reported, neither suppressed

Under the v1 lexicon-and-threshold reading (notebook 03 §"Cell determination"), the diagnostic lands in **low-obedience × low-resistance (intrinsic over-caution)** because the rule-code citation rate is 11.3% (fails the ≥50% obedience threshold) and the contradiction-naming lexicon fires zero times (fails the >7/14 resistance threshold). The strict reading is what the v1 instrument produces.

Under the **v1.1 structural reading** (taxonomy §1.5; applied in F010), the corpus pattern lands as **"inversion-blind authority-conditioned alignment in the structural sense"** — the agent's reasoning is shaped by what it has *learned* a procurement rule should look like, not by the specific policy text in front of it. The per-primary-rule obedience numbers at unperturbed L4 (79.2% on PROC-001, 68.2% on PROC-002) are not "intrinsic over-caution" behaviour, and the diagnostic reasoning *does* contain rule-code citations on some records (e.g. an `s.53(1)` citation) that the v1 lexicon undercounts. Reading B is more honest about the qualitative content.

This writeup adopts the structural reading as the headline and reports the lexicon-strict reading alongside as a measurement note. Both are visible in the corpus; the v1 lexicon undersells what the reasoning texts contain on the qualitative axis but is correct on its own measurement plane. Phase 3.1 flagged this as a framing call; Phase 3.2 (F010) made the call under v1.1's restraint discipline.

### What the writeup is **not** claiming

The structural label "inversion-blind authority-conditioned alignment" is **not** the AI-safety-literature pinpoint claim "sycophancy". Sycophancy in the pinpoint sense requires the agent to be *agreeing with the authority* of the inverted policy. The corpus does not show that — the agent is not agreeing with the inverted operator; it is *ignoring* the inversion and applying its prior. That is a different property, and the v1.1 amendment to the taxonomy was written specifically to preserve this distinction at pre-data scale.

The diagnostic is small (n=14). A 14-record adversarial control is a signal, not a metric, and the writeup names it as such. The single largest E3 design ask coming out of this finding is a larger Permuted-Policy diagnostic — target n ≥ 100 — combined with a hand-coded reasoning-text rubric (three categories: "names the inversion in any words" / "reasons solely against intent" / "partially recognises but applies anyway"). If E3's 100-record diagnostic shows 90+ records following the same pattern, the structural claim is earned at scale.

## §7 — Methodological findings

Three findings in the F-series document the experiment's measurement instruments, not the agent's behaviour directly. They are reported here because the writeup's restraint discipline requires both the substantive and the methodological readings to coexist on the page.

**F007 — corpus-clean-parse correction.** The Phase 2 project brief carried a provisional headline ("8 L4 PARSE_ERR + 71 DENY + 204 REVIEW"). The actual on-disk corpus parses cleanly: 0 PARSE_ERR across 1,415 main + 14 diagnostic bundles; L4 verdict distribution 73 DENY / 210 REVIEW / 0 ALLOW. The brief's numbers were provisional; the bundles on disk are canonical. The finding is process-discipline rather than behavioural — and it is reported here because it is informative about how research programmes that run overlapping phases can carry provisional numbers forward unless reconciliation is the *first* move at each phase boundary. Phase 3.1 reconciled before quoting any headline number; Phase 3.3 inherits that reconciled state.

**F012 — D6 lexicon-null + silent precedent anchoring.** The taxonomy v1 precedent-marker lexicon ("similar to", "comparable to", "as in record", "the prior decision", "the precedent suggests") fired **zero times across all 1,415 reasoning texts** — at every level including L3 (where 107 records moved REVIEW → DENY at the precedent rung) and L4. At the same time, the L2 → L3 verdict shift is the experiment's headline transition and it is the rung at which precedent material first enters the prompt. The agent IS responding to precedents — verdicts move — but its prose does NOT name them. The writeup commits to **both** simultaneously-true framings:

- **(i) Methodological**: the v1 lexicon is conservative. Embedding-similarity scoring between L3 reasoning and the L3 precedent payload (with a threshold calibrated against a small hand-coded golden set) is the v2 refinement target. The bare lexicon is the wrong instrument for D6 specifically; other dimensions' lexicons (uncertainty markers, substrate-field names) do fire and do move across the ladder. v1's design choice was not wrong in general; it is wrong for this dimension.
- **(ii) Substantive**: silent anchoring is a real behavioural mode in its own right — and the gap between behavioural anchoring (verdicts move) and explicit articulation (the lexicon never fires) is best read as an intrinsic property of current foundation models, not a defect in the instrument. The agent consumes the precedent context and acts on it; it just doesn't externalise that influence the way a human analyst citing case law would. Even if a v2 lexicon caught 80% of paraphrased precedent-influenced reasoning, the *fact that v1 caught 0%* is informative — the agent does not adopt the "I am applying this prior decision to this record" framing that a human analyst would. Three plausible mechanisms fit the observation: a meta-cognitive limit (the agent cannot report which input shifted its weighting), a stylistic property of GPT-class models (which tend to synthesise rather than cite), or a learned property of legal-policy reasoning (where citation is a separate communicative act from analysis). All three are plausible; the corpus does not settle between them.

Collapsing F012 to a single reading would betray the data. The verdict-level data and the lexicon-level data together force the both-and: if verdicts had not moved, reading (i) would suffice; if verdicts had moved AND the lexicon had fired, reading (i) would not be needed. The corpus produces the exact pattern that makes both readings load-bearing.

**F-series structure as a methodological contribution.** Each finding in the F-series follows the same shape: an explicit **status** label (Confirmed / Falsified / Inverted / Refuted / Deferred / Discovered), a numbered evidence block with denominators, two interpretive readings where the corpus admits two, an explicit **anti-claims** section that lists what the finding does *not* establish, and an E3-design implications block. The discipline is the same one pre-registration enforces on predictions, applied to post-data interpretation. Restraint, made operational. It is the discipline this writeup inherits as its reporting voice.

**Two-readings discipline as a programme method.** Where the corpus admits more than one defensible interpretation, the writeup reports both, leans toward one when the pattern weakly favours it, and names the E3 experiment that would settle the question. F008 (Reading A precedent-rung anchoring vs Reading B L4 nudge load-bearing → L3.5 disambiguator), F010 (lexicon-strict vs v1.1 structural reading → larger n + hand-coded rubric), F011 (Framing A.1 nudge-working vs Framing A.2 over-correction → L4-without-nudge variant), and F012 (methodological vs substantive → embedding-similarity scoring) all carry this shape. Naming the discipline acknowledges that preservation-of-alternatives — not collapse-to-a-single-reading — is the voice this writeup commits to. The E3 design ladder is, in part, the list of experiments meant to convert weakly-held readings into decided ones.

## §8 — Implications for E3

The corpus closes some questions and opens others. The closed questions are descriptive (the ladder's shape, the L3 break's existence and magnitude, the L3→L4 backoff direction on PROC-005). The open questions are mechanistic and methodological. E3's experiment_design should bake the following asks in before pre-registration lock.

**L3.5 receipts-only variant.** L3 in the current ladder is the first rung carrying *any* substantive content (the L1 prose summary and L2 rule names are framing). An L3.5 variant — precedents intact, no L4 policy text appended — disentangles "the agent committed because precedents are now present" from "the agent committed at L4 because the policy nudge teaches it to back off". If L3.5 verdicts look like L3 (committed), Reading A from §4 is sharpened. If L3.5 verdicts look like L4 (rebound), Reading B is sharpened.

**Larger Permuted-Policy diagnostic.** The 14-record diagnostic surfaced a clean structural signal but is a signal not a metric. Target n ≥ 100. Add a hand-coded reasoning-text rubric (three categories: "names the inversion in any words" / "reasons solely against intent" / "partially recognises but applies anyway") so the resistance axis can be reported beyond the bare lexicon. Cross-model replication (at least one of Claude or Gemini in addition to the current model) tests whether the rule-intent prior is a property of this model or of the task class.

**Embedding-similarity D6 lexicon refinement.** Replace the bare-string-match v1 precedent-marker lexicon with embedding-cosine-similarity scoring between L3 reasoning and the L3 precedent payload. Calibrate the threshold against a 20-record hand-coded golden set. This is the single most actionable methodological refinement coming out of F012.

**Pre-registration discipline at the segment level.** P1 and P2 were specified at the aggregate-trend level (monotonic decrease / monotonic increase). E3 should specify predictions at the *segment* level (L0→L1, L1→L2, …) so that non-monotonic shapes can be predicted explicitly rather than reported as falsifications of a uniformity assumption.

What E2 closes vs what it opens, in one sentence: **the L3 finding is real; the mechanism behind it is open.** The L3.5 variant is the central E3 ask carrying forward.

## §9 — Anti-claims

The findings in this writeup do *not* establish the following. Each item names a claim the corpus cannot support, with the reason it cannot.

- **E2 is not a multi-model result.** The corpus is single-model (`gpt-5.4-2026-03-05`, temperature 0) on a single procurement substrate. The L3 break, the L3→L4 backoff, and the L4_PERMUTED inversion-blindness pattern may or may not reproduce under Claude, Gemini, or any other model family. Cross-model replication is the mechanism by which generalisation gets earned and is an explicit E3 ask.
- **E2 is not a multi-domain result.** The substrate is UK public-sector procurement; the policy is a six-rule snapshot authored against PA23 / PCR 2015. The structural patterns observed may or may not transfer to AML / KYC / underwriting / any other regulated-decision domain. Domain replication is on the E3 roadmap but is not closed by this corpus.
- **E2 is not a multi-turn dialogue result.** Each record is evaluated one-shot. The agent does not have access to its prior decisions on previous records within the run, does not engage in follow-up dialogue, and does not iterate on its verdict. The patterns named here cannot be extrapolated to chat or investigative-agent settings; the investigative-agent variant is E3's defining axis.
- **The L3 break is not "manipulation".** L3 is the first ladder rung where precedent material exists. Rung and content are confounded by design (see §4). Only the L3.5 variant in E3 can disentangle "the agent anchored on precedents" from "the agent committed at the first rung with substantive information density".
- **The L4_PERMUTED inversion-blindness is not "sycophancy" in the AI-safety-literature pinpoint sense.** The agent is not *agreeing* with the inverted policy. It is *ignoring* the inversion and applying its rule-intent prior. The structural label "authority-conditioned alignment" is broader than "sycophancy" by design; the v1.1 amendment to the taxonomy preserves the option to narrow later under E3 evidence, and does not commit to the narrower claim here.
- **The "authority-conditioned" qualifier in F010's structural label is not yet isolated to authority.** The v1.1 taxonomy retains "authority-conditioned alignment" as the structural label for the inversion-blindness pattern, but the corpus does not separate which of three plausible causes is doing the work: the authoritative framing of the policy text, the policy content itself, or the model's general training priors about how procurement rules should read. An E3 axis comparing authoritative versus hypothetical policy framings (*"the policy states that…"* vs *"suppose a policy stated that…"*) would isolate the qualifier; until that axis runs, the qualifier is preserved as nomenclature, not as a demonstrated cause.
- **The L0→L1 ALLOW-withdrawal pattern (F009) is not generalised "governance prose makes models more cautious".** It establishes that *this prose* + *this model* + *this substrate* + *this set of 7 ALLOW records* did. Whether the same pattern reproduces under different prompt phrasings, model families, or substrate domains is open.
- **The L1/L2 100% REVIEW spine is not necessarily "the right call".** Holding 100% REVIEW is not, on its own, evidence of epistemic correctness. MeshQu emits ALLOW on 146 / 283 records, and the agent's L1/L2 REVIEW on those records may or may not be the appropriate verdict. The finding is about prediction-vs-corpus direction (F009), not about decision quality.
- **The PROC-005 29→1 backoff is not unambiguous nudge success.** The magnitude is large enough to warrant flagging as an open question (F011, Framing A.2). The L4 nudge could be doing the work it was named for (Framing A.1) or it could be over-correcting on the ambiguous-rule axis. The L4-without-nudge variant in E3 is the disambiguator.
- **Silent precedent anchoring (F012) is not "the agent is hiding something".** Chain-of-thought-style externalisation is a separate capability from being-influenced-by-a-prompt-input. The agent may simply lack the meta-cognitive surface to report which input shifted its weighting; that is not concealment.
- **The array-position sub-metric is not a positional-attention finding.** Array position and rule ambiguity are perfectly correlated in this corpus (position 1 = PROC-001 unambiguous; position 5 = PROC-005 ambiguous). The 76.7pp gap between position-1 and position-5 L4 commitment rates is dominated by rule ambiguity, not by array position. The positional question is **Under-tested**; a follow-up that permutes the rule array order across runs would isolate the positional effect.

## §10 — Synthesis

Adding governance context to the agent's prompt did not move its verdict surface monotonically. Figures 1 and 3 carry the shape; the corpus-level observation is that L0, L1, and L2 held the agent on the REVIEW spine; L3 — the first rung carrying precedent receipts — moved 37.8% of records off it in a single step, and L4 then reverted 46 of those 107 fresh DENYs back to REVIEW, concentrated on the PROC-005 ambiguous-rule class (29/40 → 1/40).

Two structural observations follow. The precedent-receipts rung is the first rung at which large-scale verdict commitment emerged in this experimental design. The full-policy rung pulled a non-trivial slice of that commitment back rather than extending it. Both observations are descriptive; neither is mechanistic. **The L3 finding is real; the mechanism behind it is open.** The L3.5 receipts-only variant in E3 is the disambiguator the corpus does not provide.

### A provisional interpretation — Decision Receipts as governance-memory artefacts

One interpretation worth registering — provisionally, as a reading that emerges from the corpus rather than a claim the corpus establishes — is that signed, verifiable Decision Receipts may function as transferable governance-memory artefacts. The L3 pattern is consistent with the broader proposition that decision receipts can carry institutional precedent across different operational consumers: humans reviewing prior cases, AI agents conditioned on case histories, workflow engines pattern-matching against archived decisions, and operational systems escalating on receipt-level provenance.

The receipts in this experiment are structurally uniform in three ways that matter for this interpretation. They are **actor-agnostic** — the bundle schema does not distinguish whether the originating decision was issued by a human reviewer, an automated rule engine, or a model-driven agent; the same envelope format anchors a verdict, a policy reference, and an integrity signature regardless of the source. They are **policy-bound** — every receipt is anchored to a specific policy snapshot SHA-256 and signing kid, so any downstream consumer can verify which authority and which version of which policy the verdict was emitted against. And they are **schema-uniform across rungs** — the L3 precedent payload format is the same on-disk format as the receipts the agent (and other receipt-producing systems) would produce in operational deployment. The corpus demonstrates structural-format equivalence between the precedent payload at L3 and the produced receipt at L4; it does not demonstrate deployment-time precedent consumption, which is a separate empirical question. That uniformity raises the possibility — but does not establish — that governance memory may become transferable across heterogeneous decision surfaces rather than siloed within individual systems.

A scope note tempers any over-reading of the actor-agnostic property. **The receipts in this corpus are AI-issued only.** The Attested Manual Check (AMC) capability that produces structurally identical receipts for human-issued decisions exists in the platform but has not been empirically demonstrated at corpus scale in either E1 or E2. The actor-agnostic claim is therefore a property of the *schema*, not of the *corpus*: the envelope format is uniform regardless of originator, but the empirical demonstration of actor-agnostic behaviour across human-issued and AI-issued decisions at scale remains future work. The L3 pattern reported here is a pattern in AI-on-AI precedent reading; whether the same pattern holds when an AI agent reads precedents issued by a human reviewer, or vice versa, is an open empirical question and is not foreclosed by these findings.

The corpus does not establish the governance-memory proposition. What it provides is one empirical surface on which receipts behaved as governance context rather than as inert audit output. The phrase "governance-memory primitive" is used here as interpretation, not as a mechanism. Whether the interpretation generalises across model families, decision domains, receipt schemas, or originator classes is open and is not foreclosed by these findings.

The interpretation above is offered as a reading the corpus opens, not as a finding it closes. What the corpus demonstrates directly — and what it leaves open — sits below.

### What is justified, and what is not

The findings here justify further investigation: the L3.5 receipts-only variant that disentangles rung from content, a larger Permuted-Policy diagnostic with a hand-coded reasoning rubric, the authoritative-versus-hypothetical framing axis that isolates the "authority-conditioned" qualifier, cross-model replication of the structural pattern, and the actor-agnostic corpus that demonstrates the schema property empirically rather than only structurally. They do not justify a general theory. The patterns described in §4–§6 are real on this corpus; the mechanism behind them is open. The writeup commits to the patterns and defers the mechanism to E3.

> **Practitioner takeaway.** A team putting an AI agent into a regulated workflow should expect verdict commitment to respond non-linearly to the kind of governance context they hand it — and should expect precedent-style context to move the agent's verdicts more than the same agent reading the policy text alone. Whether that's desirable depends on whether the precedents in front of the agent are the right precedents.

The methodological substrate is itself a contribution of the programme, independent of how the mechanism question eventually lands. Six pieces — grouped into three layers — form durable reproducibility infrastructure for governed experimentation, generalisable beyond E2's specific findings and reusable across other governed-decision domains.

- **Artefact layer.** **Signed receipts** (Ed25519, anchored to a policy snapshot SHA-256 and signing kid, verifiable offline) and **public verification** (verify.meshqu.com — independent SET re-implementation, no credentials required) together make every claim in the writeup independently re-derivable from on-disk bundles by any reader.
- **Pre-data discipline layer.** **Locked prompts** (SHA-256-bound into the manifest at pre-registration) and **pre-registered predictions** (with locked falsification criteria and a disposition vocabulary fixed before data collection) together close the "specification-after-data" failure mode. The locked tag is the artefact that lets a future reader audit which claims existed before the corpus did.
- **Post-data discipline layer.** **Anti-claims as a first-class section** (each finding lists what it does *not* establish, alongside what it does) and **F-series methodology** (status label + evidence block + two readings + anti-claims + E3 implications) together make the interpretation pass auditable on the same terms as the data collection. Restraint, made operational.

This is reproducibility architecture for governed experimentation, not a feature list. The infrastructure survives regardless of which way the mechanism question lands in E3, and is the part of the work most readily portable to AML / KYC / underwriting / clinical-decision domains where the methodology — not the procurement-specific findings — is the transferable contribution.

### Pre-publication checklist (out of scope for this DRAFT)

These items are required before iko-tools publication and are not produced in this draft:

- **Inline graphics** for the five mandatory Figure callouts (§3, §4, §6) and one optional supporting figure (§5). Mandatory: Figure 1 ladder verdict distribution (stacked bars), Figure 2 transition flow (Sankey/alluvial), Figure 3 commitment-emergence (% DENY by rung; the load-bearing "structural break" graphic), Figure 4 worked-example trajectory (single-record, all five rungs side-by-side), Figure 6 permuted-policy inversion comparison. Optional: Figure 5 PROC-005 commitment swing (supporting if space allows). Visual style: restrained, systems-oriented, research-grade — Anthropic system-card / IBM Research / government-digital-service register. No glossy AI imagery, no decorative diagrams, no neon. Notebook references alone are insufficient for the published paper.
- **iko-tools publication metadata block** — title is committed in the H1 (*"When precedents commit AI"* + subtitle); MRP-2026-03 number, byline, publication surface URL, and DOI placeholder if assigned still need to be added.
- **E1 cross-reference link** resolved to the published MRP-2026-02 surface URL once iko-tools renders E2 alongside it.
- **Worked-example reasoning quotes** (§4) reproduced from notebook 05 — the published version should attach the exact bundle paths and decision IDs in a verifier-friendly appendix so any reader can re-derive the quoted texts from the on-disk bundles.

## §11 — What's next

E2 is the second experiment in a three-experiment programme. E1 (MRP-2026-02) established the baseline — a foundation-model agent reviewing real procurement records without policy visibility, reaching for REVIEW under incomplete evidence. E2 extends that baseline by adding governance context one rung at a time and reporting the resulting non-monotonic shape. **E3** introduces the investigative-agent variant: instead of reviewing static records, the agent actively retrieves linked notices, inspects documents, verifies timelines, and gathers evidence — with MeshQu governing the investigation process itself as a replayable, cryptographically verifiable receipt chain.

The arc is: passive reviewer → context-aware reviewer → governed investigative agent. Each experiment compounds on the same methodology substrate: signed receipts, locked prompts, pre-registered predictions, anti-claims as first-class output, and the F-series two-readings discipline.

E3 also carries the disambiguators E2 surfaced: the **L3.5 receipts-only variant** that separates precedent influence from information-density influence, the **larger Permuted-Policy diagnostic** (n ≥ 100 with a hand-coded reasoning rubric), the **authoritative-versus-hypothetical framing axis** that isolates the "authority-conditioned" qualifier, and **cross-model replication** to test whether the rule-intent prior is a property of this model or of the task class.

The pattern — governance-context structure as a first-class object of empirical study, not just an audit trail emitted from one — generalises beyond procurement to AML, KYC, underwriting, and clinical-decision domains. The methodology there is one substrate-adapter implementation and one domain-specific policy-authoring pass away, not a rebuild.

---

## Declaration of AI assistance

AI tools were used during ideation, drafting, and editorial refinement of this paper. The pre-registration, ladder design, locked-prompt SHA fingerprints, corpus collection, and analytical conclusions were directed and reviewed by the author. In a paper on agent behaviour under governance context, disclosing the assistance trail is the same primitive the paper advocates for — making the work legible at the point of the work.

## References

1. **Chen, Q.Z. & Zhang, A.X.** *Case Law Grounding: Using Past Cases to Align Decision-Making for Humans and AI*. arXiv:2310.07019, 2023 (accepted ACM Collective Intelligence 2025). https://arxiv.org/abs/2310.07019
2. **MeshQu Research.** *MRP-2026-02 — When AI hedges and policy commits: Anatomy of agent–policy disagreement on UK procurement decisions, signed and verifiable*. 2026-05-18. (The programme's E1 baseline; see §2.3.)
3. **UK Parliament.** *Procurement Act 2023, s.53(1) — Contract Details Notice publication obligation*. 2023.
4. **UK Government.** *Public Contracts Regulations 2015 (PCR 2015)*. (Referenced in §4 as the pre-PA23 regulatory regime governing the worked-example record.)
5. **Sigstore project.** *Rekor — transparency log for software artifacts*. https://docs.sigstore.dev/logging/overview/

## Appendix A — Pre-registration provenance

- **Git tag**: `v0.2-predictions-locked`
- **Tag commit SHA**: `a8c6f47ded43e8d3e0b3e150eaa21e20a7688f0b`
- **Locked-prompt SHA-256 fingerprints** (from `runs/phase-2-20260522-101324-Z/manifest.json`):
  - L1: `19b9863905593756b583bdc4b39998f143ba14c63fa1cebe90295d6e76f90acf`
  - L2: `d24847ed1eef3c4d87b725195d0313449398e2a467c7de4bf0cd6a9e93c11174`
  - L3: `a3e224cbaeb91fbe3b6583d5c6c7c429893d838819a5f7e2c6f04182ddff1f5d`
  - L4: `c90664f473c19b7482b9bb81f0bf546392819dd7bfb6f47bcb369ac713ac0b2d`
- **Agent prompt scaffold SHA-256**: `690c50b5fb2ba5b820e42d781aec51c6216483c07ed5a4be2273b2d2e3517be2`
- **Policy snapshot SHA-256**: `5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d` (snapshot id `cbf12348-6248-48f7-a06f-4e0304cc237e`, persisted to `policy/policy-snapshot-cbf12348.json`)
- **Tenant ID** (public, staging): `243f19a5-4d4f-4070-9ec1-8170e8260e26` (label: `experiment-procurement`)
- **Receipt signing kid** (public): `meshqu-experiment-procurement-2026-05`
- **Foundation model**: `gpt-5.4-2026-03-05`, temperature 0
- **Runner commit**: `96fccb73f40c8b25b612b5ad765dc0e115acaa16` (manifest reports dirty tree; the source-tree state at this commit is what produced the run)

## Appendix B — Corpus citation

- **Run ID**: `phase-2-20260522-101324-Z`
- **Started**: 2026-05-22T10:13:34+00:00
- **Records**: 283 unique OCDS procurement records × 5 levels = **1,415 main-grid bundles**; **14 Permuted-Policy diagnostic bundles** (sha256(ocid) mod 20 == 0); total **1,429 bundles**
- **Bundle layout**: `results/runs/phase-2-20260522-101324-Z/L{0,1,2,3,4}/<decision_id>.bundle.json` for the main grid; `results/runs/phase-2-20260522-101324-Z/diagnostic/<decision_id>.bundle.json` for the Permuted-Policy subset
- **Substrate source**: `tests/fixtures/full_corpus_records.json` (`substrate_adapter_version`: `cached-e1-phase-2-7ddf7274`; archive_run_id `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`)
- **MeshQu verdict distribution** (constant across levels by design): ALLOW 146, DENY 137, REVIEW 0; ALLOW + DENY = 283
- **Cache telemetry summary** (notebook 07): total nominal input tokens 2,598,716; cached input tokens 767,232 (29.5%); uncached 1,831,484; L4 cache-hit rate by calls 99.3%; L4 cache-hit rate by tokens 72.0%
- **Operational evidence**: 30 Grafana dashboard captures at `results/runs/phase-2-20260522-101324-Z/observability/screenshots/`
- **Independent verifier**: verify.meshqu.com (offline verifier, independent SET re-implementation; downloads a bundle, recomputes the canonical signing-envelope bytes, verifies the Ed25519 signature against the published kid, checks the Rekor anchor)

## Appendix C — Behavioural taxonomy v1.1 reference

Each dimension reported in notebook 01 §"Table A" — per-level summary; v1.1 restraint amendment (`planning/behavioural_taxonomy.md` §1.5) applies throughout.

- **D1 Ambiguity handling** — REVIEW rate on ambiguous-only-rule records (PROC-003/004/005 single-class). L0..L4: 100.0% → 100.0% → 100.0% → 27.5% → 97.5%. L3 collapse + L4 rebound; the design's "healthy result" signature partially observed.
- **D2 Escalation behaviour** — overall REVIEW rate per level. L0..L4: 97.5% → 100.0% → 100.0% → 61.1% → 74.2%. Non-monotonic; P1 falsified.
- **D3 Policy obedience** — agreement on unambiguous-rule records (PROC-001/002) at L4. L0..L4: 0.0% → 0.0% → 0.0% → 28.6% → 57.1%. Steady lift; P3 confirmed.
- **D4 Policy resistance** — operationalised against the 14-record Permuted-Policy diagnostic (not L0..L4 on the main grid). Lexicon-strict: 0/14 contradiction-naming fires (low resistance). v1.1 structural reading: inversion-blind authority-conditioned alignment.
- **D5 Evidence sensitivity** — mean substrate-field-name hits per reasoning text. L0..L4: 0.00 → 0.00 → 0.00 → 0.00 → 0.16. Citation rate at L4: 11.3% (P5 falsified at the ≥50% threshold).
- **D6 Precedent sensitivity** — mean precedent-marker hits per reasoning text. L0..L4: 0.00 → 0.00 → 0.00 → 0.00 → 0.00. Methodological flag: lexicon-null across all levels (F012). Verdict-level data (L2→L3 shift) and lexicon-level data (zero fires) jointly force the both-and reading.
- **D7 Uncertainty acknowledgement** — mean uncertainty-marker hits per reasoning text. L0..L4: 0.02 → 0.04 → 0.05 → 0.01 → 0.17. Partial healthy-pattern signature: uncertainty persists at L4 rather than collapsing.
- **D8 Governance-context susceptibility** — cumulative normalised |Δ| across D1+D2+D3+D5+D6+D7. Per-step magnitude: L1 0.22, L2 0.07, L3 2.77, L4 3.80. Cumulative L4: 6.86. The L3 step is the dominant single-rung contributor.

## Appendix D — Reproducibility instructions

- **Branch tag**: writeup anchored to `feat/phase-3-3-writeup` (stacked on `feat/phase-3-2-findings`, in turn stacked on `feat/phase-3-1-cross-level-analysis`). v0.2 lock tag `v0.2-predictions-locked` carries the predictions / ladder / policy snapshot at pre-run state.
- **Re-derive Table A per-level summary**:
  1. Clone `meshqu-research` at this branch tag.
  2. Read the bundles at `procurement-context-gradient/results/runs/phase-2-20260522-101324-Z/L{0,1,2,3,4}/*.bundle.json` and `diagnostic/*.bundle.json`.
  3. Apply the analysis driver pattern documented in `decision_log.md` (Phase 3.1 entry, 2026-05-22) — read-only over the corpus, no live API calls. The Phase 3.1 driver was committed at `/private/tmp/phase-3-1-scratch/analyse.py` for the original pass; the notebook outputs in `results/notebook/cross_level_analysis/` are the authoritative re-derivable artefacts.
  4. Spot-check against notebook 01 §"Headline corpus numbers": 283 × 5 = 1,415 main bundles; 14 diagnostic bundles; 0 PARSE_ERR; MeshQu verdict distribution ALLOW 146 / DENY 137.
- **Independent receipt verification**:
  1. Download any bundle from the run directory (JSON or tar).
  2. Submit to verify.meshqu.com (no account, no credentials required).
  3. The verifier recomputes the canonical signing-envelope bytes, verifies the Ed25519 signature against the published kid `meshqu-experiment-procurement-2026-05`, and checks the Rekor anchor against the public transparency log.
- **No live credentials are required to re-derive any number in this writeup.** The staging tenant ID and signing kid are public-by-design. No Doppler config is read; no API keys are needed. Re-running the agent loop against the foundation model is a separate exercise requiring an OpenAI API key and is outside the scope of corpus re-derivation.
