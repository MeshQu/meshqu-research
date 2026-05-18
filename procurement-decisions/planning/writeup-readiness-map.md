# Writeup readiness map — 2026-05-18 post-corpus

> Routing document: for each section of [`writeup_outline.md`](writeup_outline.md), points at the materials that populate it.
> Created after the 300-record corpus run completed (effective n=283 unique decisions).
> Use this when starting the writeup draft so each section opens onto the relevant artifacts rather than archaeology.

## Status legend

- 🟢 **ready** — materials sufficient to draft to length budget without further analysis
- 🟡 **partial** — main materials present; one bounded analysis or curation step remaining
- 🔴 **needs-work** — significant analysis or decision still required

## Materials inventory

| Class | Location |
|---|---|
| Corpus | [`results/corpus.tar`](../results/corpus.tar) — 283 v2 receipt bundles, SHA-256 `1b6192df6eb5d3c38738b6abc5cea82c92d99d53ae890308569a4c240c232be0` |
| Decision traces | `results/runs/dry-run-7ddf7274-…/decision_traces.jsonl` (300 rows, 283 unique decision_ids) |
| Agent outputs | `results/runs/dry-run-7ddf7274-…/agent_outputs/<decision_id>.json` (283 files; full reasoning text per record) |
| Run manifest | `results/runs/dry-run-7ddf7274-…/manifest.json` |
| Per-day notebook | [`results/notebook/2026-05-18-full-run.md`](../results/notebook/2026-05-18-full-run.md), [`2026-05-18-full-run-live-notes.md`](../results/notebook/2026-05-18-full-run-live-notes.md), [`2026-05-18-aborted-run.md`](../results/notebook/2026-05-18-aborted-run.md), [`2026-05-17-build-and-dry-run.md`](../results/notebook/2026-05-17-build-and-dry-run.md) |
| Findings | [`results/notebook/findings/001`](../results/notebook/findings/001-tenant-header-missing-in-runner-client.md)–[`006`](../results/notebook/findings/006-binary-policy-projects-gradient-information.md).md |
| Predictions | [`planning/predictions.md`](predictions.md) — locked at tag `v0.1-predictions-locked` (2026-05-15) |
| Decision log | [`planning/decision_log.md`](decision_log.md) — model lock, policy clarification, snapshot ids |
| Substrate doc | [`planning/substrate.md`](substrate.md) |
| Experiment design | [`planning/experiment_design.md`](experiment_design.md) |
| Verifier screenshots | `results/observability/screenshots/verify-bundle_2026-05-18_*.png` (2 curated) |
| Grafana run screenshots | `results/runs/dry-run-7ddf7274-…/screenshots/` (152 PNGs — curate to ~6 for Appendix B) |

## Section-by-section routing

### 1 · The question (~300 words) — 🟢 ready

- Frame opens from [`planning/project_context.md`](project_context.md) "The one-sentence summary" and "What success looks like."
- Existing outline at [`writeup_outline.md`](writeup_outline.md) §1 has scaffolding.
- Lift / paraphrase. No new analysis needed.

### 2 · How we ran it (~800 words) — 🟢 ready

- **Methodology**: experiment_design.md (predictions locked before runs, single foundation model at temp 0, regulator-fidelity rule under test).
- **Build apparatus**: planning/decision_log.md (foundation model lock, post-smoke policy clarification, snapshot ids, model API quirks).
- **Discipline narrative**: notebook entries chronologically (2026-05-17 build → 2026-05-18 aborted run → retry patch → full run). F001 (tenant header) + F002 (PROC-004 clarification) + F004 (retry gap) demonstrate "smoke + dry-run catching real apparatus gaps before corpus collection."
- Length budget will accommodate (a) what we tested, (b) what discipline rules governed the test, (c) one concrete example of the discipline working (F001 or F002).

### 3 · The policy under test (~400 words) — 🟢 ready

- Six rules, all `severity: critical`, ratified under `policy_snapshot_id=cbf12348-…` after the post-smoke PROC-004 clarification.
- PROC-001-S53 is the regulator-fidelity rule under test (PA23 s.53 30-day publication window).
- Cross-reference: [F002](../results/notebook/findings/002-proc-004-coi-absence-clarification.md) for the PROC-004 clarification.
- **Binary-by-authoring note**: every rule at critical severity → every violation = DENY. Cross-reference [F006](../results/notebook/findings/006-binary-policy-projects-gradient-information.md) for the implications.

### 4 · The substrate (~300 words) — 🟢 ready

- OCDS feed from UK Contracts Finder (post-PA23 Find a Tender Service is the follow-up path).
- **n=283 unique decisions from 300 release events** — see [F005](../results/notebook/findings/005-ocds-feed-publishes-multiple-releases-per-ocid.md) for the dedup rationale. Be explicit about this in the writeup; don't collapse to one number.
- Substrate provenance: 2,830 cells across 283 records × 10 fields. Distribution: ~direct_ocds / derived / proxy / absent counts in the notebook §"Substrate provenance aggregate."
- Substrate-honesty disclosures: award-date as signature-date proxy (PROC-001-S53 numerator), £139k sub-central threshold conservative choice, COI never in OCDS (F002 makes this concrete).

### 5 · What the corpus shows (~1,200 words) — 🟡 partial

The longest section, with the richest material — but **needs a deliberate framing decision before drafting**:

**The headline tension**: P1 originally predicted "agent over-permissive vs MeshQu (i.e. agent leans ALLOW, MeshQu leans DENY)." The actual finding inverts this: agent is over-cautious-by-default (REVIEW-by-default), not over-permissive. Naive agreement is 7/283 (2.5%). The writeup needs to (a) honestly report the prediction-inversion, (b) reframe agreement non-naively via [F006](../results/notebook/findings/006-binary-policy-projects-gradient-information.md)'s counterfactual analysis.

**Concrete materials**:

- Verdict + agreement distributions: notebook §"Verdict + agreement distributions (deduped by decision_id)"
- Rule firing distribution: notebook §"Rule firing distribution (deduped, n=283)" — PROC-005 dominates at 80 firings, PROC-001-S53 at 32, PROC-002 at 43.
- F006's full counterfactual table (CF-A / CF-B / CF-C) is the worked example
- Worked-example decision_ids: `7b6ead10-…` (ALLOW agreement), `ca19e737-…` (£57M triple-violation DENY) — both with verifier screenshots committed.
- Live-notes' 5 flagged records (36, 61, 72, 81, 85) for concrete per-record narrative.

**Framing decision Sam needs to make before drafting**: how to handle the P1 inversion. Three options:
- "Predicted X, found Y (inverse), here's the richer story." — most honest; matches pre-registration discipline; recommended.
- "Predicted X, found Y, both are interesting." — softer pivot.
- "Original P1 was misframed; the correct frame is Y." — strongest claim; needs supporting evidence to land.

### 6 · Reasoning is data (~600 words) — 🟢 ready

- 283 `agent_outputs/<decision_id>.json` sidecars carry the full agent reasoning text.
- **Pattern observed**: agent's `recommended_action` uses a stable verbal template — `[verb] + [procedure | publication | notice trail | justification]`. Maps to specific rule territories on multi-violation records (see live-notes records 36, 61, 72, 85).
- **No hallucinated citations observed in the live-notes sample**. This is a finding about P3 (predicted: some agent reasoning would invent regulatory citations; observed: agent doesn't cite at all). Honest: report this, don't dress it up. The corpus refutes the prediction's specific shape; the underlying concern (drift) is captured better by [F006](../results/notebook/findings/006-binary-policy-projects-gradient-information.md).
- Concrete records to quote: pull 2-3 `agent_outputs/<decision_id>.json` for verbatim reasoning excerpts.

### 7 · Limitations (~400 words) — 🟢 ready

- **Substrate**: OCDS-feed-publishes-multiple-releases-per-OCID ([F005](../results/notebook/findings/005-ocds-feed-publishes-multiple-releases-per-ocid.md)). Effective n=283 vs target n=300.
- **Policy authoring**: binary-by-authoring; the AARM Bundle A roadmap addresses this conceptually ([F006](../results/notebook/findings/006-binary-policy-projects-gradient-information.md) + UX correlate at tradequ PR #541 F14).
- **Verifier UX**: raw-receipt-paste warns "Tampered" on receipts with server-injected metadata; bundle path is canonical ([F003](../results/notebook/findings/003-bundle-is-canonical-verifier-path.md)). The writeup must direct auditors to the bundle path.
- **Apparatus gaps caught + fixed**: F001 (tenant header missing), F004 (retry gap — patch shipped but didn't fire on this run). Honesty note: F004 stays draft until a future run exercises the retry path.
- **Cardinality mismatch**: 3-state agent vs 2-state policy — discussed under §5 framing.

### 8 · Reproduce it yourself (~200 words) — 🟢 ready

- `results/corpus.tar` SHA-256: `1b6192df6eb5d3c38738b6abc5cea82c92d99d53ae890308569a4c240c232be0`
- Three verification paths from the corpus's README: verify.meshqu.com, `@meshqu/verifier` CLI, independent Rekor lookup.
- The two verify-bundle screenshots in `results/observability/screenshots/` are the "what you should see" reference.
- Substrate adapter, eval loop, runner all in `runner/`; pinned to commit `8e54281` (PR #28 plus subsequent fixes).
- Predictions locked at tag `v0.1-predictions-locked`.

### 9 · What's next (~200 words) — 🟢 ready

- **AARM Bundle A — Verdict v2** (Q1–Q2 2027) is the natural sequel. This corpus is empirical evidence for the bundle's hypothesis. The writeup should name this explicitly: "the platform roadmap already plans the verdict-cardinality fix; the experiment provides empirical support for it."
- **Follow-up A**: Find a Tender Service (above-threshold PA23 records with richer narrative).
- **Follow-up B**: agent context-gradient experiment — reasoning-style models (gpt-5.5+, o-series) on the same substrate.
- **OCDS substrate adapter**: Option C from [F005](../results/notebook/findings/005-ocds-feed-publishes-multiple-releases-per-ocid.md) (in-fetch OCID dedupe, release_id field in trace rows) ships when the next corpus run is scoped.

### Appendices

- **Appendix A — Predictions vs results**: P1 (inverted), P2 (rule firing distribution matches PROC-005 + PROC-002 + PROC-001 ordering), P3 (refuted — no hallucinated citations observed), P4 (untested — single run), P5 (confirmed — bundle verification works), P6 (under-tested — corpus doesn't have enough direct-award records to evaluate).
- **Appendix B — Curated Grafana screenshots**: 6 from `results/runs/dry-run-7ddf7274-…/screenshots/` — need curation. Recommended set: run-start, mid-run checkpoint showing receipt rate, run-end, the decision-to-anchor flow Sam shared mid-run.
- **Appendix C — Bundle verification screenshots**: the 2 `verify-bundle_*.png` files already committed.
- **Appendix D — Counterfactual analysis (F006)**: the CF-A/B/C table.

## Drafting order suggestion

1. **§2 (How we ran it)** first — it's the most narrative-friendly section and the discipline story carries itself. Drafting it will get the experiment-as-discipline framing locked in.
2. **§5 (Corpus shows)** second — but only after §2 is drafted, because §5 needs §2's frame to land cleanly. Make the P1-inversion framing decision before drafting.
3. **§6, §7, §8, §9** in any order — each is self-contained.
4. **§1, §3, §4** last — short, lookup-heavy, can be drafted in an afternoon once the heavier sections are set.

Estimated drafting time: 2-3 focused half-days for a complete draft. Editing + review separate.

## Outstanding analyses that would strengthen the writeup but aren't blocking

- **P3 deep-pull**: spot-check 20-30 `agent_outputs/<decision_id>.json` records for any regulatory citations (FAR, EU directives, PA23 section refs). Current observation is "no citations seen in the 5 records flagged live"; a 20-30 record sample makes the negative finding stronger.
- **P6 examination**: filter `decision_traces.jsonl` for records with `direct_award_justification_present="true"` and compute disagreement rate on s.53. May be too few records to say anything (corpus may not have enough direct-award examples — direct-award records are themselves rare in OCDS).
- **Per-rule agreement matrix**: for each of PROC-001/002/005, what fraction of agent-REVIEWs correlate with that specific rule firing? Tells us which rule the agent is "noticing" most.

Each of these is half a day. None are blocking; all strengthen the writeup's substantive section §5.
