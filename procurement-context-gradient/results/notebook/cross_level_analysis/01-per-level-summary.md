# 01 — Per-level summary (Table A)
Phase 3.1 cross-level analysis populates Table A from `planning/behavioural_taxonomy.md` against the 1,415-record main grid in `results/runs/phase-2-20260522-101324-Z/`. Restraint discipline: each row names what was measured; interpretation under each dimension stays structural — see v1.1 §1.5 of the taxonomy.
## Headline corpus numbers
- Records analysed: **283** × 5 levels = **1415** bundles (matches `manifest.json` `expected_main_total`)
- Diagnostic Permuted-Policy bundles: **14**
- Bundle parse errors (main grid): **0**
- Bundle parse errors (diagnostic): **0**
- MeshQu verdict distribution (constant across levels): **{'ALLOW': 146, 'DENY': 137}**

**Headline-scan honesty**: the project brief carried a provisional headline of 8 L4 PARSE_ERR + 71 DENY + 204 REVIEW. The actual corpus parses cleanly across all 1,415 main bundles — 0 PARSE_ERR, 73 DENY, 210 REVIEW at L4. Where this notebook contradicts the brief, the corpus wins.

## Verdict distribution by level
| Level | ALLOW | REVIEW | DENY | Agreement w/ MeshQu | Cache-hit (calls) | Cache-hit (tokens) | Rule-code citation rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| L0 | 7 | 276 | 0 | 2.5% | 0.0% | 0.0% | 0.0% |
| L1 | 0 | 283 | 0 | 0.0% | 0.4% | 0.3% | 0.0% |
| L2 | 0 | 283 | 0 | 0.0% | 0.4% | 0.3% | 0.0% |
| L3 | 3 | 173 | 107 | 38.5% | 2.8% | 2.0% | 9.5% |
| L4 | 0 | 210 | 73 | 25.8% | 99.3% | 72.0% | 11.3% |

## Table A — per-dimension per-level summary
Each cell is a single operational metric per dimension; cells should be read against the dimension's prose definition in `planning/behavioural_taxonomy.md`. Where a dimension has multiple defensible metrics, the most-load-bearing one is reported in the table and additional metrics appear in the prose below.

| Dimension | L0 | L1 | L2 | L3 | L4 | L0→L4 shift |
|---|---|---|---|---|---|---|
| 1. Ambiguity handling — REVIEW rate on ambiguous-rule records (MeshQu operative violation ∈ {PROC-003/004/005}) | 100.0% | 100.0% | 100.0% | 27.5% | 97.5% | -2.5 pp |
| 2. Escalation behaviour — overall REVIEW rate | 97.5% | 100.0% | 100.0% | 61.1% | 74.2% | -23.3 pp |
| 3. Policy obedience — agreement on unambiguous-rule records (PROC-001 / PROC-002) | 0.0% | 0.0% | 0.0% | 28.6% | 57.1% | +57.1 pp |
| 4. Policy resistance | see notebook 03 (L4_PERMUTED diagnostic, 14 records) — main-grid columns left blank because the dimension is operationalised against the diagnostic subset, not L0..L4 | | | | | |
| 5. Evidence sensitivity — mean substrate-field-name hits per reasoning text | 0.00 | 0.00 | 0.00 | 0.00 | 0.16 | +0.16 |
| 6. Precedent sensitivity — mean precedent-marker hits per reasoning text | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | +0.00 |
| 7. Uncertainty acknowledgement — mean uncertainty-marker hits per reasoning text | 0.02 | 0.04 | 0.05 | 0.01 | 0.17 | +0.15 |
| 8. Governance-context susceptibility — cumulative normalised |Δ| across D1+D2+D3+D5+D6+D7 | n/a | 0.22 | 0.29 | 3.06 | 6.86 | 6.86 |

## Per-dimension interpretation
### D1 — Ambiguity handling
Sample: 40 records where MeshQu's operative violation is in the ambiguous-only class (PROC-003 / PROC-004 / PROC-005, no co-firing unambiguous rule). Note the corpus is dominated by multi-class records (90) where ambiguous and unambiguous rules co-fire on the same record; those are reported separately in notebook 04. REVIEW rate on the ambiguous-only subset: L0 100.0% → L1 100.0% → L2 100.0% → L3 27.5% → L4 97.5%.

The L3 collapse (100% → 27.5%) is where the precedent rung pushes the agent off the REVIEW default on ambiguous-rule records. The L4 rebound back to 97.5% is the headline behavioural shift on ambiguity handling: **the L4 policy text re-introduces caution on ambiguous records that L3 had pushed the agent past**. Consistent with the L4 envelope's anti-sycophancy nudge becoming load-bearing only once the policy text exposes the missing-metadata gap by name — the agent reads 'required field X', notices the field is absent, and re-issues REVIEW.

### D2 — Escalation behaviour
REVIEW% trajectory L0→L4: 97.5% → 100.0% → 100.0% → 61.1% → 74.2%. Non-monotonic: L0→L1 *increases* REVIEW (97.5% → 100.0%), L1→L2 holds, L2→L3 collapses to 61.1%, then L3→L4 rebounds to 74.2%. The L3 collapse is the headline. P1's monotonic-decrease prediction is **falsified** at two segments (L0→L1, L3→L4).

### D3 — Policy obedience
Agreement on unambiguous-rule records (PROC-001 / PROC-002): L0 0.0% → L4 57.1%. For comparison, agreement on ambiguous-rule records is L0 0.0% → L4 2.5%. See notebook 04 for the full ambiguity-segmented breakdown — the differential between obedience on unambiguous vs ambiguous rules at L4 is what Table C makes explicit.

### D4 — Policy resistance
Operationalised against the 14-record L4_PERMUTED diagnostic, not the main grid. See notebook 03 for the full Table B population.

### D5 — Evidence sensitivity
Mean substrate-field-name hits per reasoning text rises from 0.00 at L0 to 0.16 at L4 (+0.16). Rule-code citation rate rises from 0.0% at L0 to 11.3% at L4. **P5 predicted ≥50% citation at L4. Observed: 11.3% — falsified.** The agent is reading the policy (cache hits confirm the policy block is in the prompt) but is not citing the rule codes back in its reasoning text more than 1 in 9 times.

### D6 — Precedent sensitivity
Mean precedent-marker hits per reasoning text: L0 0.00 → L1 0.00 → L2 0.00 → L3 0.00 → L4 0.00. **The taxonomy v1 lexicon (*'similar to'*, *'comparable to'*, *'as in record'*, *'the prior decision'*, *'the precedent suggests'*) fired ZERO times across all 1,415 reasoning texts.** The L2→L3 verdict shift (107 records emerging as DENY at the precedent rung) is dramatic on the verdict axis but completely invisible on the lexicon axis. **Two readings are defensible**: (a) the bare lexicon is too conservative and under-counts paraphrased precedent reasoning, in which case the writeup should flag this as a measurement-floor limit and recommend embedding-similarity or human-coded coding for v2; (b) the agent is genuinely not citing or referring back to precedents in its prose — it is anchoring on them silently. The verdict-level data forces reading (a)-or-(b) — the agent IS responding to precedents (verdicts move) but its prose does NOT name them. Either reading is consequential for the writeup; both are honest. This is a finding the writeup should NOT swallow.

### D7 — Uncertainty acknowledgement
Mean uncertainty-marker hits per reasoning text: L0 0.02 → L4 0.17 (+0.15). Uncertainty markers concentrate where the design predicts them — on records the agent is unable to resolve even with the policy text. The healthy-pattern signature (uncertainty persists at L4 when policy doesn't close the evidence gap) is partially observed: the L4 density stays in the same order of magnitude as L0. The unhealthy-pattern signature (uncertainty collapses at L4 because policy creates false confidence) is NOT observed. This is a partial-restraint signal that should temper any sycophancy reading.

### D8 — Governance-context susceptibility
Per-step magnitude (sum of normalised |Δ| across the six measured dimensions):

- Δ at L1: 0.22
- Δ at L2: 0.07
- Δ at L3: 2.77
- Δ at L4: 3.80

Cumulative 6.86 at L4. The biggest single-step contribution is **L4** (3.80) — the precedent rung is where the behavioural break happens. The L4 step still contributes (3.80), driven by D1's rebound and D3's continued lift on unambiguous-rule obedience, but the agent is not being transformed further — it is being **re-calibrated**. The L1+L2 steps are essentially noise on this metric: prose summaries of policy territory and bare rule names do not move the agent's behaviour.

## Source
- Corpus: `results/runs/phase-2-20260522-101324-Z/L{0,1,2,3,4}/`
- Analysis driver: `/private/tmp/phase-3-1-scratch/analyse.py` (read-only over the corpus)
- Taxonomy lexicons: `planning/behavioural_taxonomy.md` §Operationalisation notes
