# Experiment 2 — Design

## Research question

Does providing AI agents with MeshQu's structured governance artefacts (DecisionContext, Decision Receipts, named violations, full policy text) reduce the evidence-incompleteness-driven escalation to REVIEW that E1 documented (97.5% REVIEW rate, 0 DENY)?

The question matters because the answer determines what MeshQu is. If governance context measurably reduces agent escalation: MeshQu's receipts and policy artefacts are *governance input* for AI systems, not just audit output from them — and the moat-story is bidirectional. If governance context does not measurably reduce escalation: the agent's REVIEW-by-default is intrinsic to LLM behaviour under incomplete evidence, and MeshQu's value sits cleanly on the receipt-from side. Either result is publishable; the structure of the experiment is identical regardless of which way the data lands.

## What is held constant

| Element | Value |
|---|---|
| Foundation model | `gpt-5.4-2026-03-05` |
| Temperature | `0` |
| System prompt scaffold | Same as E1; only the per-level context payload is appended |
| Verdict space | `ALLOW / REVIEW / DENY` |
| Output schema | Same structured-JSON contract as E1 |
| Policy under evaluation | `cbf12348-6248-48f7-a06f-4e0304cc237e` (E1's post-clarification snapshot, unchanged) |
| MeshQu tenant | `experiment-procurement` (staging, dedicated experimental tenant) |
| Signing key id | `meshqu-experiment-procurement-2026-05` (E1's experiment kid) |
| Substrate adapter | Same `runner/meshqu_runner/substrate.py` from E1 — no new fetch |
| Corpus | 283 unique decisions from E1's run `dry-run-7ddf7274-…`, reused exactly |

## What varies

**One axis only: governance context.** Five levels, strictly additive. See `context_ladder_design.md` for the full ladder.

Every record is evaluated at every level. The result is a 283 × 5 grid of receipts (1,415 total). Each receipt is independently signed, anchored to Rekor, and verifiable offline. The grid is the data the analysis layer operates on.

## Multi-pass runner

The runner extends E1's harness with one new orchestration layer. For each (record, level) pair:

1. Substrate adapter reads the OCDS record from the cached fetch (no re-fetch — same data E1 saw).
2. Context-payload generator emits the level-specific addendum (see `context_ladder_design.md` for payload shapes).
3. Agent loop sends `{system_prompt_scaffold, record, level_payload}` to the foundation model. Locked model, temp 0, structured-JSON output.
4. MeshQu evaluates the same record against the same policy snapshot. Same evaluator code, same tenant. MeshQu verdict will be identical across levels for the same record — that is the invariant the comparison rests on.
5. Receipt v2 is generated, signed, anchored, bundled. Receipt includes a new `governance_context_level` field (L0..L4) bound into the integrity payload.
6. Receipt is persisted to `results/runs/<run_id>/<level>/<decision_id>.bundle.json`.

The runner is deterministic in execution order: it processes records in OCID-ascending order, then iterates levels L0 → L4 per record (or batches by level — either is fine and the choice is documented in the run manifest). It is not deterministic in receipt timing; the run manifest captures the order and timestamps so any future reproducibility-run can re-establish them.

## Analysis layer — the row-by-row delta lens

The central analytical primitive is the **per-record trajectory**: for each of the 283 records, the sequence of (verdict, reasoning_text) pairs across the 5 levels. This is the lens that makes "context matters" testable.

Three analyses follow from the grid:

### Per-level aggregate statistics

For each level: verdict distribution (ALLOW/REVIEW/DENY counts), naive agreement with MeshQu's verdict, mean reasoning-text length, mean token cost. This is the headline data — does the ladder slope monotonically?

### Per-record trajectory analysis

For each record: the verdict sequence (L0 verdict, L1 verdict, …, L4 verdict). Buckets:

- **Stable-REVIEW**: REVIEW at every level. The agent's caution didn't budge.
- **Stable-ALLOW**: ALLOW at every level. The agent saw a clean record and never wavered.
- **Convergent**: started REVIEW, ended at one of MeshQu's verdicts (ALLOW or DENY). The context unlocked something.
- **Divergent**: changed verdicts non-monotonically. Worth examining.
- **Late-DENY**: REVIEW at L0..L3, DENY at L4 only. Did the policy text specifically unlock commitment?

The worked-example pattern from E1 (decision `ca19e737-…`, the £57M REVIEW-vs-DENY case) becomes the natural Worked Example 2 in the E2 writeup — showing the same record's trajectory across 5 levels.

### Reasoning-text drift study

For each record, what changes in the agent's reasoning text from L0 to L4? The substantive measure is whether the agent's prose starts naming specific rule codes once it has seen them (L2+) or the policy text (L4). This is the test that distinguishes between "the agent reasoned with context" and "the agent regurgitated the policy verbatim" — the **echo-trap check**.

## The echo trap — a structural boundary, not a flaw

If at L4 the agent mirrors MeshQu's DENY verdicts almost perfectly but its reasoning text is paraphrasing the policy rather than reasoning about the record, the finding is "explicit governance context teaches the LLM to apply rules mechanically." That is materially different from "explicit governance context unlocks AI judgment." Both are real findings; only the second is the moat-story. The writeup must report which it found.

The detection mechanism:

1. **P3 + P4 jointly.** P3 predicts ≥30% DENY commitment at L4. P4 predicts naive agreement at L4 stays ≤29% (the CF-C counterfactual ceiling from E1 F006). If both hold: agent reasoning increased its commitment but stayed bounded by what a 3-state agent can mathematically agree with a 2-state policy on — that is plausible judgment, not echo. If P3 holds but P4 is exceeded by a wide margin: the agent is producing high naive agreement *beyond* what reasoned agreement would allow, which is the echo signature.

2. **P5 (citation behaviour at L4).** E1 P3 documented zero citation behaviour at L0. If L4 reasoning suddenly starts citing rule codes ≥50% of the time, the agent is at minimum *reading* the policy. The remaining question is whether it's reasoning from it or paraphrasing it.

3. **Reasoning-text similarity to policy text.** Heuristic — Levenshtein, embedding-cosine, or human-coded. If the agent's reasoning text on a DENY at L4 is structurally identical to the policy rule text for the operative rule, that is the echo. If the reasoning text is recognisably the agent's voice but informed by the policy, that is judgment-with-context.

The writeup pre-commits to reporting whichever pattern the data shows.

## Comparison to E1

E1's headline result is the L0 baseline for E2. Re-running the corpus at L0 in E2 (with the same model, temp, policy snapshot, and substrate) serves as a **reproducibility check** on E1's results. E1's predictions P1 (agent over-permissive) and P4 (verdict non-determinism in 5–20%) were respectively *inverted* and *deferred*. E2's L0 pass tests both implicitly: if L0 produces materially different agreement numbers from E1, that's a reproducibility finding (and possibly a P4 result that E1 deferred).

Expected: L0 in E2 produces verdicts within E1's reproducibility band — same 97.5% REVIEW rate ± small drift from OpenAI backend non-determinism even at temp 0. Documented divergence is interesting either way.

## Substrate posture

No new fetch from Contracts Finder. The OCDS records cached during E1's run are the source-of-truth records for E2. This eliminates substrate drift as a variable (different fetch windows could produce different records for the same OCIDs; reusing the cache holds substrate fixed).

The substrate adapter is unchanged. The per-field provenance envelope is unchanged. The agent at L0 sees exactly what it saw in E1.

## What this experiment is NOT

- It is **not** a fine-tuning experiment. The model is locked and untouched.
- It is **not** a multi-model comparison. Same model across all levels (reasoning-style models are deferred to E2-followup or E3).
- It is **not** a multi-domain experiment. Same UK procurement substrate (cross-domain generalisation is a deferred follow-up).
- It is **not** a tool-use experiment. The agent has no tools, no retrieval. That is E3.
- It is **not** a fresh-corpus reproducibility study (P4 from E1). That would require a re-fetch and re-run at L0. E2 implicitly tests reproducibility-on-cached-corpus only.

## Apparatus risks

Documented honestly in `decision_log.md` as they arise. Known up front:

- **Token cost at L4.** Full policy JSON in the prompt at every record. Pre-flight estimate via smoke run (3 records × 5 levels) before committing to the full run.
- **OpenAI backend non-determinism at temp 0.** Same risk as E1. The L0-vs-E1 comparison detects it.
- **Rate limiting on a 1,415-call run.** Pacing logic from E1's runner already exists; same pattern applies.
- **Receipt-chain integrity at scale.** The cryptographic chain handled 283 receipts cleanly in E1; 1,415 receipts is a 5× test but the chain structure does not depend on count.

## Predictions, briefly

7 predictions in `predictions.md` — monotonic decreases in REVIEW rate, monotonic increases in agreement, DENY commitment at L4, agreement ceiling at the E1 CF-C boundary, citation behaviour at L4, verdict-shift clustering on the PROC-005 missing-method case, and linear token-cost scaling. The echo-trap detection sits in the P3 + P4 + P5 cluster.

## Definition of done for the experiment

- 1,415 receipts in `corpus.tar`, all verifying offline
- L0 verdict distribution within E1's reproducibility band (else: explicit divergence finding)
- All 7 predictions evaluated; status logged in Appendix A of the writeup
- Echo-trap determination made; reported in §6 of the writeup with the detection-mechanism evidence
- F-series findings authored for any apparatus surprises or load-bearing methodological notes
- Writeup published via the same iko-tools publication-discipline lineage as MRP-2026-02
- Cross-level analysis notebook in `results/notebook/cross_level_analysis/` carries the per-record trajectory data for any reader who wants to verify the analysis layer
