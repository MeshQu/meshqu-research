# F007 — Headline-scan correction: corpus parses clean across 1,415 bundles

**Status**: Discovered (process-discipline)
**Source experiment**: E2 (procurement-context-gradient) Phase 2 corpus `phase-2-20260522-101324-Z`
**Pre-registered prediction**: None — discovered post-data during Phase 3.1 corpus reconciliation
**Authored**: 2026-05-22
**Restraint discipline**: This is a measurement-correction finding, not a behavioural claim. Framing stays at "what the corpus actually contains" vs "what the brief said". Honour taxonomy v1.1 §1.5 by not letting a provisional brief headline (now disproved) seep into Phase 3.3 framing.

## Finding

The Phase 2 project brief carried a provisional headline of "8 L4 PARSE_ERR + 71 DENY + 204 REVIEW". The actual Phase 2 corpus parses cleanly across all 1,415 main-grid bundles and all 14 diagnostic bundles: **0 PARSE_ERR at every level**, and the L4 verdict distribution is **73 DENY / 210 REVIEW / 0 ALLOW** (not 71/204). The brief's count appears to have been a pre-run estimate or pre-merge snapshot; the on-disk corpus is canonical. Phase 3.3 writeup §1 Methodology and any prose that depended on the 8-error claim must be scrubbed.

## Evidence

- Corpus citation: `procurement-context-gradient/results/notebook/cross_level_analysis/01-per-level-summary.md` §"Headline corpus numbers" + §"Headline-scan honesty"
- Numbers (with units, with denominators):
  - Records analysed: **283 × 5 levels = 1,415 main-grid bundles** (matches `manifest.json` `expected_main_total`)
  - Diagnostic Permuted-Policy bundles: **14**
  - Bundle parse errors (main grid): **0 / 1,415**
  - Bundle parse errors (diagnostic): **0 / 14**
  - MeshQu verdict distribution (constant across levels by design): **{ALLOW: 146, DENY: 137, REVIEW: 0}** (note: 146 + 137 = 283; MeshQu emits no REVIEW)
- L4 verdict distribution as actually observed:
  | Verdict | Brief (provisional) | Corpus (actual) |
  |---|---:|---:|
  | PARSE_ERR | 8 | **0** |
  | DENY | 71 | **73** |
  | REVIEW | 204 | **210** |
  | ALLOW | (unstated) | **0** |
- Worked example: the entire 1,415-row main grid is the evidence — every bundle in `results/runs/phase-2-20260522-101324-Z/L{0,1,2,3,4}/` was parsed without exception during the Phase 3.1 driver pass at `/private/tmp/phase-3-1-scratch/analyse.py`.

## Interpretation

There is essentially one reading here — the brief was wrong, the corpus is right. The on-disk artefacts are the canonical source because they are what receipt-verifies, what gets cited downstream, and what reviewers can replay. A brief headline is provisional by construction; a bundle on disk is not. Where Phase 3.3 narrative inherited the 8-error count it must be replaced with "0 PARSE_ERR at every level" or omitted entirely.

The secondary reading worth naming: the brief's miscount is itself informative about how a research programme that runs many overlapping phases can carry provisional numbers forward unless reconciled at hand-off. Phase 3.1's first move was a corpus reconciliation pass precisely because this kind of drift is the default state, not the exception. Phase 3.3 should adopt the same first-move discipline before quoting any numeric headline.

## Implications for E3

E3 should bake corpus-reconciliation-before-narrative into its phase contract — specifically, a "headline-scan honesty" gate at the top of each notebook batch. The discipline costs an analyst 30 minutes and prevents a writeup-level error.

## Anti-claims

- This finding does **not** establish that there are no agent-side errors in the corpus. Bundles parsing cleanly establishes envelope integrity (JSON well-formed, schema-conformant, expected files present) — it says nothing about whether the agent's reasoning content is correct, defensible, or stable across re-runs.
- This finding does **not** establish that the Phase 2 driver is bug-free in general — it establishes that the run on this corpus emitted no malformed bundles. A different record set, a different model snapshot, or a different prompt revision could surface latent issues that this run did not.
- This finding does **not** invalidate the brief as a whole — only the specific provisional counts (8/71/204). The brief's methodological commitments (level-batching, Permuted-Policy diagnostic shape, fixed verdict-distribution invariant) all hold up against the corpus.
