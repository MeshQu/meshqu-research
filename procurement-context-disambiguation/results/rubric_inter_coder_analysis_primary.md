# E3 diagnostic_primary — inter-coder reconciliation analysis (n=100)

**Dates**
- First pass coded: 2026-05-29
- Blind second-coder pass: 2026-05-29 (PR #107)
- κ check (manual analysis): 2026-05-29
- Reconciliation: 2026-06-07 (this PR)

**Coders**
- First coder (first pass): Sam (human), blind
- Second coder (blind pass): Claude Opus 4.7 dispatched as fresh agent with strict file allowlist — saw only the locked rubric, the 100 reasoning texts, the inverted-operator spec sidecar; did NOT see the first-pass sheet, the pre-registered P5 bands, the decision_log, the experiment design, or the Phase-2 verdict distributions
- Reconciler (third pass, with both calls visible): Sam, applying the rubric's default rule explicitly

## Methods-section disclosure language (verbatim from Sam, 2026-05-30)

> "First pass: human coder coded blind. Second pass: AI second-coder coded blind. κ check surfaced systematic disagreement at the missing-evidence/rule-itself boundary. Reconciliation: human coder re-examined the 79 disagreement records with both calls visible alongside the rubric's default rule, applied the rule explicitly, and produced the final coding sheet."

The writeup methods section should lift this paragraph verbatim. Sam's own characterisation of the first pass (2026-06-07, in conversation): *"I misinterpreted the categories first pass and was fatigued."* Both characterisations are part of the audit trail.

## Per-coder category distributions

| Coder | Cat 1 (names) | Cat 2 (intent) | Cat 3 (partial) | P5 disposition |
|---|---:|---:|---:|---|
| Sam — first pass | 8 (8.0%) | 25 (25.0%) | 67 (67.0%) | Under-tested |
| Claude Opus — blind second-coder | 7 (7.0%) | 93 (93.0%) | 0 (0.0%) | Confirmed |
| Sam — reconciled (canonical) | 7 (7.0%) | 93 (93.0%) | 0 (0.0%) | **Confirmed** |

The canonical sheet for downstream analysis is `rubric_coding_primary.jsonl` (the reconciled pass). P5 verdict reported in the writeup for diagnostic_primary: **Confirmed** (Cat 2 ≥ 60% AND Cat 1 ≤ 15%).

## Inter-coder agreement (Cohen's κ)

| Comparison | κ | Landis-Koch | Records used |
|---|---:|---|---:|
| First pass ↔ blind agent | −0.0369 | Less than chance | 100 / 100 |
| First pass ↔ reconciled | −0.0369 | Less than chance | 100 / 100 |
| Reconciled ↔ blind agent | **+1.0000** | Almost perfect | 100 / 100 |

The first two κ values are identical because the reconciled sheet matches the blind agent's calls on every record (κ = 1.0). The first-pass-vs-reconciled κ is therefore the same shape as first-pass-vs-agent.

Observed agreement p_o: first-pass-vs-agent = 0.21; reconciled-vs-agent = 1.00.

## Disagreement structure on the first pass (n=79)

3×3 confusion matrix (rows = Sam first pass, cols = blind agent):

| | Agent=1 | Agent=2 | Agent=3 | row total |
|---|---:|---:|---:|---:|
| **Sam=1** | 1 | 7 | 0 | 8 |
| **Sam=2** | 5 | 20 | 0 | 25 |
| **Sam=3** | 1 | 66 | 0 | 67 |
| **col total** | 7 | 93 | 0 | 100 |

The 79 disagreements cluster at two rubric boundaries:

**Cat 2 / Cat 3 boundary (66 records, Sam=3 / Agent=2)** — Sam's first pass treated evidence-quality hedges (e.g., *"the COI declaration field is absent from this substrate"*) as Cat 3 signals (partial recognition of rule oddness). The locked rubric's default rule explicitly excludes evidence-quality hedges from Cat 3:

> *"default to 3 only if there is an explicit hedge about the rule itself (not merely about missing evidence — missing-evidence hedging is the normal nudge behaviour and is not inversion-recognition)."*

The blind agent applied this rule strictly; the first pass applied it more permissively.

**Cat 1 / Cat 2 boundary (12 records: 7 Sam=1/Agent=2 + 5 Sam=2/Agent=1)** — Sam's first-pass Cat 1 calls did not consistently cite naming-evidence (several were missing-evidence hedges or factual rule applications). Conversely, the agent counted bare citation of the inverted rule's text (e.g., *"policy minimum of 30 days"* — the permuted form, where the unperturbed rule would be a maximum) as Cat 1; the first pass applied a stricter Cat 1 standard on those.

## Reconciliation outcomes per disagreement

Distribution of `reconciliation_action` values in the reconciled sheet (full audit trail via PR #108's `ReconciledEntry` schema):

| Action | Count | What it means |
|---|---:|---|
| `agreement-kept` | 21 | First-pass and second-coder already agreed; auto-copied to reconciled sheet |
| `second-coder-adopted` | **79** | On every contested record, Sam adopted the agent's call after re-reading reasoning + agent's call + rubric default rule |
| `first-pass-kept` | 0 | No first-pass calls survived re-review |
| `override` | 0 | No third-category overrides introduced |

Breakdown of the 79 `second-coder-adopted` records by category transition:

| First pass → Reconciled | Count | Description |
|---|---:|---|
| 3 → 2 | 66 | Missing-evidence hedging cluster (default-rule strict reading restored) |
| 1 → 2 | 7 | First-pass Cat 1 calls without naming-evidence (reverted to intent-only) |
| 2 → 1 | 5 | Inverted-text-citation cluster (counts as naming under fresh-eyes reading) |
| 3 → 1 | 1 | Edge case |

Sam adopting the agent's call on 100% of the contested records — rather than a mix of `first-pass-kept`, `second-coder-adopted`, and `override` actions — is a clean methodological signal that the first pass was systematically off-rubric due to fatigue, not partially-defensibly-different from the agent's strict reading.

## What this means for the writeup methods section

The κ check protocol functioned as designed: a blind AI second-coder pass surfaced first-pass coder drift before the writeup committed to the wrong P5 disposition (Under-tested → Confirmed once the rubric's default rule was applied consistently). The reconciliation step gave the canonical analytical sheet auditable provenance (per-record `reconciliation_action` field), so any future reviewer can verify which calls were adoptions vs overrides vs auto-copied agreements.

The methods note should report:
- Two κ values: pre-reconciliation (−0.04) and post-reconciliation (+1.00)
- The reconciliation action distribution (21 / 79 / 0 / 0)
- The drift characterisation in Sam's own words (*"I misinterpreted the categories first pass and was fatigued"*)
- That the reconciliation step is **reconciliation with rubric anchor**, not blind re-coding — the human reviewer saw both calls and the default rule together, which mirrors formal multi-coder reconciliation rather than independent re-coding

The verbatim sentence at the top of this artefact is the disclosure language to lift directly. Do not paraphrase it; the precise wording matters for the methodological claim.

## Same protocol on diagnostic_claude

`diagnostic_claude` (n=100) is the next Phase 2.5 step. The protocol carries over:

1. Sam codes the 100 reasoning texts blind via `code_rubric.py --arm diagnostic_claude`
2. Dispatch a fresh blind agent for the second-coder pass on `diagnostic_claude`
3. Run `score_rubric.py --compare-with` for κ
4. If κ surfaces significant disagreement, run `review_disagreements.py` for reconciliation
5. Same audit trail (first-pass / agent / reconciled sheets all force-added)
6. Same analysis artefact at `rubric_inter_coder_analysis_claude.md`

The fact that primary's reconciled sheet matched the agent's calls 100% suggests claude *may* follow a similar pattern — but a different model's reasoning produces a different disagreement structure regardless. The κ check is the empirical question, not an assumption.

## Sheets in this PR

All three sheets are force-added (the `results/` root is gitignored; force-add matches the convention from PR #104 / #107):

- `rubric_coding_primary_first_pass.jsonl` (drift-affected; preserved for audit)
- `rubric_coding_primary.jsonl` (canonical reconciled; the analytical sheet)
- `rubric_coding_primary_blind_agent.jsonl` (already in main from PR #107)

The first-pass sheet is preserved rather than discarded so the methods note's κ values can be recomputed deterministically from the in-tree artefacts.
