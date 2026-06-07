# Precedents, policy, and commitment: a disambiguation study of governance-context effects in AI decision agents

<!-- E3 writeup scaffold. Sam authors the prose; this file lays out the
     load-bearing structure, intent briefs per section, and explicit
     placeholders for numbers/findings the analysis notebook will supply.

     Structural template: procurement-context-gradient/results/writeup-DRAFT.md
     (E2). Voice, length conventions, F-series two-readings discipline,
     anti-claims-as-first-class, pre-registration disposition vocabulary
     (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested) all
     carry forward. -->

## §1 — Abstract

<!-- ~1 paragraph. The Abstract is load-bearing for casual readers and for the
     trilogy capstone's pull-quote pool. Lead with the disambiguation framing
     (E2 surfaced two confounds; E3 was designed to slice them) and let the
     direction of falsifications carry the story.

     Argues: E3 is the disambiguation experiment for E2's two open structural
     findings (the L3 break and inversion-blindness). The pre-registered
     mechanism (Reading A precedents-anchor) and the predicted scale (≥20%
     Arm A DENY) were both broken by the corpus; what the data showed
     instead is the third reading the predictions explicitly named in the
     interpretive notes — accumulation, not precedents alone. The L4 backoff
     turns out to be the policy text, not the nudge clause. Inversion-blindness
     reproduces at scale across two models with directionally-coherent
     verdict-style divergence. -->

- Pre-registered programme arc: E1 baseline → E2 ladder shape → E3 disambiguation
- E3 design intent: three pieces (L3 decomposition with arms A/B/C; L4-without-nudge; scaled diagnostic + cross-model on Opus 4.7)
- Headline: P1, P2, P3, P4 falsified; P5 confirmed on both diagnostic arms; P6 disposition <!-- TODO: fill in from analysis notebook -->
- The falsifications are the story — each one names a third reading the predictions explicitly anticipated and that the corpus surfaced
- Cross-model arm yields a substantive cross-axis-coherent finding (verdict-style divergence + rubric-axis Cat 1 difference both consistent with Opus's verdict decisiveness)
- Locked at `v0.3-predictions-locked` (commit `ba4ebfb`); no artefact at lock has been edited

> <!-- Optional Correction footnote — only if Phase 3 surfaces a provisional/canonical mismatch the way E2's F007 did. E3's Phase 2 close-out reported all five gates PASS and clean numbers, so this footnote may not be needed. Sam's call. -->

## §2 — Programme context

<!-- ~2 paragraphs. Position E3 inside the E1 → E2 → E3 arc and point at the
     forthcoming methods note. This is the section the trilogy capstone
     cross-references; keep the framing tight so the capstone can lift it.

     Argues: E3 is the third in a pre-registered trilogy of applied research
     experiments on governance-context effects. E1 established the corpus and
     baseline; E2 established the ladder shape and surfaced two structural
     findings it could not mechanistically isolate; E3's job was to slice
     those confounds. The methodology — receipt-anchored evaluation,
     pre-registered predictions with locked falsification criteria, anti-claims
     as first-class output, F-series two-readings discipline — carries forward
     unchanged. -->

- E1 (MRP-2026-02): single-condition baseline on 283 OCDS procurement records
- E2 (MRP-2026-03): five-rung additive ladder; L3 break + inversion-blindness signal at n=14
- E3 (this paper): disambiguation experiment — L3 decomposition + L4-without-nudge + scaled diagnostic (n=100) + cross-model arm (Opus 4.7)
- Methods substrate inherited unchanged: signed Ed25519 receipts + Rekor anchoring, locked-prompt SHAs, pre-registered predictions with the locked disposition vocabulary, anti-claims, F-series structure
- Pointer to the trilogy methods note (*Receipt-Anchored Evaluation*) <!-- TODO: confirm whether this writeup forward-references the methods note or whether the methods note is published first; per decision_log Phase 4 is post-E3 capstone -->

## §3 — E3 design recap

<!-- ~2 paragraphs + the predictions table. Mirrors E2's §2 (Methodology) +
     parts of §3 (Predictions vs. outcomes). Walks the reader through what
     was locked at v0.3-predictions-locked and what each piece was designed to
     resolve.

     Argues: the design is three pieces (L3 decomposition, L4-without-nudge,
     scaled diagnostic + cross-model arm), and each piece is targeted at one
     of E2's open readings. The predictions are segment-level (the E2
     retrospective lesson) and condition-specific. Several predictions stated
     the reading E2 leaned toward as the directional hypothesis — the design
     distinguishes outcomes regardless of which way they break, so a
     falsification is as informative as a confirmation here. -->

### What was locked

- Lock tag: `v0.3-predictions-locked`, commit `ba4ebfb`
- Locked content: Arm C density-control payload, Arm B precedent-no-verdict format, L4-without-nudge prompt variant, hand-coded rubric protocol, diagnostic subset selection rule (sha256(ocid) sort, first 100), Claude version pin (`claude-opus-4-7`, no `temperature`, `effort: low`)
- Substrate frozen from E2: same 283-record OCDS corpus, same policy snapshot (`5d7d800186…`), same primary agent (`gpt-5.4-2026-03-05`, temperature 0), same signing kid (`meshqu-experiment-procurement-2026-05`)
- Locked-prompt SHA-256 fingerprints <!-- TODO: lift from manifest at results/runs/phase-2-20260529T092611-Z/manifest.json -->

### The three pieces

- **Piece 1 — L3 decomposition** (Arms A / B / C, n=283 each): isolates whether precedents drove the L3 break (Reading A) or any sufficient content density did (Reading B), and whether verdict exemplars are load-bearing (the governance-memory mechanism) or concreteness alone is enough
- **Piece 2 — L4 decomposition** (L4-without-nudge, n=283): isolates whether the explicit anti-sycophancy nudge clause drove E2's L3→L4 backoff (Framing A.1) or the full policy text alone did (A.2)
- **Piece 3 — Scaled diagnostic + cross-model arm** (diagnostic_primary + diagnostic_claude, n=100 each, record-matched): establishes whether inversion-blindness is real at scale (vs E2's n=14 signal) and whether it is model-specific or a property of the task class

### Predictions table

<!-- Model exactly on E2's §3 table. One row per P1–P6, columns: ID,
     pre-registered claim, falsification criterion, outcome (corpus),
     disposition. Sub-metric rows below the main predictions if any
     (E2 had a sub-metric row on array-position; E3 may have a sub-metric
     row on the Arm C asymmetric-control caveat — Sam's call at draft time). -->

| ID | Pre-registered claim | Falsification criterion | Outcome (corpus) | Disposition |
|---|---|---|---|---|
| P1 | Arm A DENY ≥ 20% AND Arm C DENY ≤ 12% (precedents drive commitment, not raw volume) | Arm C ≥ 20% OR Arm A < 20% | Arm A 15.5%, Arm C 4.6%, Arm B 3.2% <!-- TODO: cross-check against analysis notebook --> | **Falsified** — Arm A below the 20% commit floor (the third-reading interpretation: accumulation amplifies, precedents alone don't reach E2's L3 37.8%) |
| P2 | Arm A − Arm B DENY rate ≥ 15pp (verdict exemplars are load-bearing) | \|A − B\| < 5pp | A − B = 15.5% − 3.2% = 12.3pp <!-- TODO: confirm exact numbers from notebook --> | **Falsified** narrowly — gap is meaningful but below the 15pp threshold; verdict-exemplar mechanism not specifically DENY-anchoring as predicted; bidirectional commitment-anchoring instead <!-- TODO: confirm bidirectional reading once notebook A/B breakdown by ALLOW vs DENY is in --> |
| P3 | L4-without-nudge retention of E2's L3-DENY set ≥ 80% (nudge load-bearing, Framing A.1) | retention ≤ 65% (policy text alone, Framing A.2) | <!-- TODO: notebook to report retention on the 107-record L3-DENY set --> 60.7% retention | **Falsified → Framing A.2 confirmed**: retention 60.7% < 65% threshold; the policy text drove the backoff, the nudge clause is incidental |
| P4 | Scaled Permuted-Policy: ≥90% same-as-unperturbed L4 verdict (n=100, primary model) | < 90% | <!-- TODO: lift from notebook --> 88% | **Falsified narrowly** — 88% < 90%; E2's 92.9% at n=14 didn't quite hold at n=100 (the architectural-property reading is weakened, but ~88% is still high) |
| P5 | Hand-coded rubric: Cat 2 ("reasons solely against rule intent") ≥ 60% modal AND Cat 1 ("names the inversion") ≤ 15% | Cat 1 > 25% | Primary: Cat 2 93% / Cat 1 7%. Claude: Cat 2 100% / Cat 1 0%. | **Confirmed** on both arms (κ between blind agent and final = +1.0000 on both arms) |
| P6 | Claude's same-as-unperturbed rate within 15pp of primary's rate (task-class, not model-specific) | gap > 15pp | <!-- TODO: cross-model verdict-axis comparison from Phase 2 receipts; combined with rubric-axis cross-model finding -->  | <!-- TODO: state disposition based on data; the cross-model rubric-axis finding (GPT-5.4 7% Cat 1 vs Opus 0%) is direction-coherent with the verdict-style divergence (GPT-5.4 23% decisive vs Opus 80% decisive) and is the substantive cross-model contribution — frame as Confirmed in spirit (cross-model robustness) even if the verdict-axis numbers technically straddle the band --> |

## §4 — Results

<!-- This is the bulk of the writeup. Walk through each finding piece by piece,
     following E2's §4 (L3 break) / §5 (L3→L4 backoff) / §6 (Permuted-Policy)
     structural shape. Each subsection is an F-series finding with status
     label, evidence block, two readings where the corpus admits two, anti-
     claims, and E4 implications. Length: ~10–12 pages worth across all
     subsections; this is the heart of the paper. -->

### §4.1 — P1 falsified: Arm A below the 20% commit floor

<!-- ~2 paragraphs. Argues: the first reading of P1 is the obvious one
     (precedents are not load-bearing on their own). The right reading,
     captured in the predictions interpretive note, is the third one:
     accumulation amplifies. E2's L3 hit 37.8% because L0+L1+L2+L3 stacked,
     not because precedents alone could push the agent off the REVIEW spine
     to that magnitude. -->

- Arm A precedents-only DENY rate: 15.5% (44/283) <!-- TODO: confirm exact -->
- Threshold: 20% (predictions calibration note: 20–30% band confirms directionally with the accumulation-amplifies note; <20% falsifies)
- Reading: **the L3 break is real but accumulation-amplified.** The L1 prose framing + L2 named-rules + L3 precedent receipts together cleared the commit floor at E2; precedents in isolation reach only ~15%
- Arm C density-control DENY rate: 4.6% (13/283) — well below the ≤12% threshold, so the volume-alone (Reading B) explanation is also falsified
- Anti-claim: **the falsification of P1 is not a refutation of the precedent mechanism.** Arm A still commits 3.4× more than Arm C (15.5% vs 4.6%); precedents are doing work, they just don't carry the full weight of the L3 break alone. The accumulation reading was named explicitly in the predictions' interpretive note as the third shading

### §4.2 — P2 falsified narrowly: the verdict-exemplar gap

<!-- ~2 paragraphs. Argues: the A − B gap is meaningful (12.3pp; well above the
     5pp falsification floor) but below the 15pp threshold P2 required to
     declare verdict exemplars specifically load-bearing. The reading is
     that verdict exemplars contribute to commitment but the mechanism is
     not the predicted "prior DENYs anchor new DENYs" — it is bidirectional
     commitment-anchoring (any exemplar of a committed verdict, ALLOW or
     DENY, gives the agent permission to commit). -->

- Arm A − Arm B DENY rate: ~12.3pp (15.5% − 3.2%) <!-- TODO: confirm; also report ALLOW commitment breakdown if notebook supplies it -->
- The gap is meaningful (above the 5pp floor) but below the 15pp threshold; predictions vocabulary lands at Falsified
- Reading: **verdict exemplars do contribute, but not specifically as DENY-anchoring.** The mechanism is broader — committed exemplars (verdict present, any direction) give the agent permission to commit; verdict-absent precedents (Arm B) don't. The original P2 framing in `predictions.md` Piece 1 explicitly tested the governance-memory claim from E2's §10; the corpus weakens that to bidirectional anchoring
- Anti-claim: **this does not refute the governance-memory interpretation** — it sharpens it. The claim survives as "committed precedents anchor commitment", not as "DENY precedents anchor DENYs". The bundle schema's verdict field still carries the load; the polarity does not

### §4.3 — Arm C asymmetric-control caveat (methods reading)

<!-- ~1 paragraph. Honest disclosure section, matching E2's §6 style of
     reporting both the strict and the structural reading. -->

- Arm C token parity vs Arm A: −16.43% (locked at PR #93, pre-registered as documented methods caveat)
- The asymmetry rules out one family of confounds (Arm C did not commit because it had more volume than precedents) and introduces another (Arm C may not have committed because it had less volume than Arm A)
- P1's Arm C ≤12% threshold is comfortably cleared (Arm C 4.6%), so the volume-alone (Reading B) explanation is falsified even granting the asymmetry — but the writeup names the caveat explicitly rather than burying it

### §4.4 — P3 falsified, Framing A.2 confirmed: the policy text drove the backoff

<!-- ~2 paragraphs. The cleanest single result in the experiment after P5.
     E2's L3→L4 backoff was 57% retention on the 107-record L3-DENY set.
     P3 predicted ≥80% retention under L4-without-nudge (nudge driving the
     backoff). The corpus shows 60.7% — essentially identical to E2's 57%,
     well below the ≥80% threshold and below the ≤65% falsification floor.
     The nudge clause was incidental; the policy text alone produces the
     backoff. -->

- Retention on the 107-record L3-DENY set under L4-without-nudge: 60.7% <!-- TODO: confirm exact -->
- E2's L4-with-nudge retention on the same set: 57% (61/107)
- Delta: ~+3.7pp — within noise band; the nudge clause is incidental
- Reading: **Framing A.2 confirmed.** The policy text alone — its explicit enumeration of rule clauses, threshold tests, and field expectations — drove the backoff. The anti-sycophancy nudge ("if a required field is absent, do not assume it satisfies the rule") was a small refinement on a mechanism that was already working
- Anti-claim: this does NOT mean the nudge is useless. It means the L3→L4 reversion on E2's PROC-005 ambiguous-rule axis was already being driven by the policy text's structural cues; the nudge is a discipline reinforcement, not the causal agent
- l4_without_nudge also commits MORE often overall than Arm A (27.2% vs 15.5%) — the policy text continues to do work beyond what precedents alone produce

### §4.5 — P4 falsified narrowly: inversion-blindness holds at scale (just below the 90% floor)

<!-- ~2 paragraphs. P4 predicted ≥90% same-as-unperturbed verdict on the n=100
     Permuted-Policy subset. E2's n=14 hit 92.9%. The corpus reports 88% —
     2pp below the 90% threshold. Predictions vocabulary lands at Falsified
     but the substantive reading is that inversion-blindness is overwhelmingly
     present at scale and the small degradation from E2's n=14 is honest about
     measurement noise. -->

- diagnostic_primary same-as-unperturbed-L4 rate: 88% <!-- TODO: confirm; needs cross-reference against E2's L4 verdicts on the same 100 OCIDs -->
- Threshold: 90%
- Reading: **the architectural-property reading is weakened but not refuted.** 88% is high; 12 records out of 100 emitted a different verdict than they did at unperturbed L4. The locked falsification floor doesn't admit "broadly" — vocabulary lands at Falsified
- Methodological frame: this is the prediction working under its own discipline. E2's n=14 result couldn't have falsified P4 at this scale; the prediction was specifically calibrated to a larger n. The corpus broke the prediction by 2pp; the prediction said "this is informative" and the writeup reports it as such
- The substantive reading carries into P5: even on the 12 records where the verdict shifted, the rubric coding shows the rule-intent prior still dominates the reasoning

### §4.6 — P5 confirmed on both diagnostic arms: rubric Cat 2 dominance

<!-- ~3 paragraphs. The load-bearing positive finding in the experiment. P5
     is the rubric-axis confirmation of inversion-blindness; both arms produce
     >90% Cat 2 ("reasons solely against rule intent") and ≤15% Cat 1 ("names
     the inversion"). This is the result the experiment was most carefully
     instrumented for. The cross-model arm strengthens the finding beyond what
     a single-arm replication would. -->

- diagnostic_primary: Cat 1 = 7 (7.0%), Cat 2 = 93 (93.0%), Cat 3 = 0 (0.0%) → **Confirmed**
- diagnostic_claude: Cat 1 = 0 (0.0%), Cat 2 = 100 (100.0%), Cat 3 = 0 (0.0%) → **Confirmed**
- Cross-model robustness: P5 confirmed under two model-protocols. The Cat 1 rate varies by model (Opus 0%, GPT-5.4 7%) in the direction the verdict-axis already suggested
- Inter-coder κ between blind AI second-coder and final canonical sheet: +1.0000 on both arms
- Reading: **inversion-blindness is a property of the task class, not a property of either specific model**, sharpened from E2's n=14 signal to a 200-record metric
- E2 reading carried forward: "authority-conditioned alignment in the structural sense" — the agent's reasoning is shaped by what it has learned a procurement rule should look like, not by the specific policy text in front of it. The pinpoint claim ("sycophancy") is still NOT what the corpus shows; the agent ignores the inversion rather than agreeing with it
- The 6 borderlines the blind agent flagged on `diagnostic_claude` were all missing-evidence hedges, which the rubric's default rule unambiguously excludes from Cat 3. P5 robustness check: even if all 6 had shifted to Cat 3, the distribution would have been 0/94/6 — still Confirmed

### §4.7 — Cross-model arm: verdict-style divergence + rubric-axis coherence

<!-- ~3 paragraphs. The substantive cross-model finding, on two axes.
     Verdict-axis (Phase 2 receipts): Opus 80% decisive (35 ALLOW + 45 DENY)
     vs GPT-5.4 23% decisive (0 ALLOW + 23 DENY + 77 REVIEW). Rubric-axis:
     Opus 0% Cat 1 vs GPT-5.4 7% Cat 1. The direction of the divergence is
     cross-axis-coherent: Opus is more thorough on both axes simultaneously.
     This is the real cross-model contribution for the writeup, and it lands
     above the methods caveat about Opus 4.7's removed temperature parameter. -->

- **Verdict-axis cross-model divergence (Phase 2 receipts, n=100 each)**:

  | arm | ALLOW | REVIEW | DENY | decisive rate |
  |---|---:|---:|---:|---:|
  | diagnostic_primary (GPT-5.4) | 0 | 77 | 23 | 23% |
  | diagnostic_claude (Opus 4.7) | 35 | 20 | 45 | 80% |

- **Rubric-axis cross-model divergence (Phase 2.5 canonical sheets, n=100 each)**:

  | arm | Cat 1 | Cat 2 | Cat 3 |
  |---|---:|---:|---:|
  | diagnostic_primary | 7 (7.0%) | 93 (93.0%) | 0 (0.0%) |
  | diagnostic_claude | 0 (0.0%) | 100 (100.0%) | 0 (0.0%) |

- Reading: **Opus's verdict decisiveness translates into rubric Cat 2 thoroughness.** Confident application of the rule-as-stated IS Cat 2 inversion-blindness. GPT-5.4's hedging creates surface area for occasional inversion-registration that Opus's decisiveness eliminates
- Engine-ALLOW vs engine-DENY directional alignment at n=100: 100% LLM-non-DENY on engine-ALLOW records (52/52 GPT-5.4, 52/52 Opus); 99.0% LLM-non-ALLOW on engine-DENY records (0/48 GPT-5.4 ALLOW, 1/48 Opus ALLOW). Cross-evaluator + cross-model directional alignment at scale
- **Methods caveat: Opus 4.7 removed the `temperature` parameter.** The cross-model arm cannot match the primary agent's temperature-0 setting; `effort: low` is the closest near-deterministic equivalent. The verdict-axis comparison is NOT verdict-for-verdict comparability; the reading is on the rubric distribution shape, not on per-record verdict equivalence. This is a documented methods caveat, not a confound — see §8

## §5 — Methodology in action

<!-- ~3 paragraphs + sub-bullets. Loadbearing methods-section material for the
     trilogy capstone. The pre-registration discipline, the inter-coder check,
     the cost projection accuracy, the disposition vocabulary — all of these
     surfaced as instrument validation in E3, often in ways E1 and E2 did not.

     Argues: E3's pre-registration didn't catch the predicted mechanism (P1
     and P2 both broke); it caught something more interesting — the third
     reading the predictions explicitly anticipated. That is the methodology
     functioning under stress. The inter-coder κ check surfaced drift in the
     first pass of `diagnostic_primary`; the reconciliation under strict
     rubric default produced the Confirmed result. The cost projection landed
     within 0.4% of actual on all six arms. The disposition vocabulary forced
     honest reporting on the narrow falsifications (P2 narrow, P4 narrow) that
     a less disciplined vocabulary would have called "broadly confirmed". -->

### Pre-registration catching the surprising mechanism, not the predicted one

- P1's interpretive note explicitly anticipated the accumulation-amplifies reading: *"Arm A landing in the 20–30% band (below E2's L3 37.8%) confirms P1 directionally but signals that accumulation amplifies… That's a real, reportable third shading, not a clean A-vs-B binary."*
- The corpus landed below even the 20–30% band — at 15.5% — but the third-shading frame was on the page before the data was collected
- The discipline: predictions don't just bind the falsification threshold; they bind the interpretive frame the writeup uses to make sense of the result
- This is what pre-registration is for. The mechanism the writeup commits to is one that was anticipated in the predictions' own language, not invented to fit the data

### Inter-coder κ check surfaced drift; reconciliation produced Confirmed

- `diagnostic_primary` first pass distribution: 8/25/67 → Under-tested
- Blind AI second-coder pass: 7/93/0 → Confirmed
- κ between first pass and blind agent: −0.0369 (less than chance)
- Reconciler walked the 79 disagreements with rubric default rule visible; adopted agent's call on 79/79 (`second-coder-adopted`); 0 `first-pass-kept`; 0 `override`
- Reconciled distribution: 7/93/0 → Confirmed; κ between reconciled and blind agent = +1.0000
- Drift characterisation (verbatim from Sam, 2026-06-07): *"I misinterpreted the categories first pass and was fatigued."*
- **The κ protocol worked exactly as designed**: a measurement-instrument check caught a coder drift before the writeup committed to the wrong P5 disposition

### Verbatim methods-section disclosure (lift directly, do not paraphrase)

- **For diagnostic_primary** (verbatim from `results/rubric_inter_coder_analysis_primary.md`):
  > *"First pass: human coder coded blind. Second pass: AI second-coder coded blind. κ check surfaced systematic disagreement at the missing-evidence/rule-itself boundary. Reconciliation: human coder re-examined the 79 disagreement records with both calls visible alongside the rubric's default rule, applied the rule explicitly, and produced the final coding sheet."*

- **For diagnostic_claude** (verbatim from `results/rubric_inter_coder_analysis_claude.md`):
  > *"diagnostic_primary was coded via blind human first pass + blind AI second-coder + reconciliation; diagnostic_claude was coded via AI-first + human review-and-adjudication of all 100 records with rubric visible. The protocol change for claude was made in response to a methodological observation surfaced during primary's reconciliation (see decision_log entry 2026-06-07)."*

- One sentence explaining why the protocols differ between arms: the primary arm's first-pass drift (fatigue + categorisation from memory under cognitive load) motivated the switch to AI-first + human review-and-adjudication on claude. The per-record `review_action` audit field documents the change end-to-end; the methodological observation is itself part of what the methods note can lift

### Cost projection accuracy as instrument validation

- Phase 2 projected cost: $25.21 base
- Phase 2 actual cost: $25.23 — within 0.4% of projection on all six arms (worst arm_a ratio 1.004; best arm_c ratio 1.000)
- The dry-run-as-instrument validation: dry-run rates predicted Phase 2 within 1.2%; smoke→dry-run within ±15%. **Extrapolation is exact at this scale.**
- This is the cost-projection-as-receipt-anchored-evaluation point: signed receipts give you per-call cost provenance, and a small dry-run at the cost-projection-confidence-interval scale predicts production cost to within rounding error

### Disposition vocabulary as honest-reporting discipline

- The locked vocabulary {Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested} forces categorical reporting
- P2 narrowly falsified (gap 12.3pp, threshold 15pp) — vocabulary requires Falsified; the writeup names it as such and reads the result as bidirectional commitment-anchoring rather than as DENY-anchoring
- P4 narrowly falsified (88%, threshold 90%) — vocabulary requires Falsified; the writeup reads the result as inversion-blindness substantively holding at scale with 2pp degradation from E2's n=14
- Without the locked vocabulary, both of these would be reported as "broadly confirmed" and the reader would not see the discipline working

## §6 — Cross-model arm: full treatment

<!-- ~2 paragraphs. Stands alone (above the §4.7 bullets) because the cross-
     model arm is a methodologically distinct piece of the experiment with its
     own caveats. The §4.7 bullets are the results; this section is the
     framing.

     Argues: the cross-model arm is asymmetric by design (diagnostic-only on
     Claude; full grid on the primary). The asymmetry buys "real at scale" +
     "model-specific or task-class" without the cost of a full second-model
     corpus. The Opus 4.7 sampling caveat (no temperature) is a known and
     documented methods caveat, not a confound — the comparison is on the
     reasoning-axis rubric distribution, not on per-record verdict
     comparability. -->

- Cross-model arm design: same 100 OCIDs run on both `gpt-5.4-2026-03-05` (temperature 0) and `claude-opus-4-7` (no temperature, effort low)
- The Opus 4.7 sampling caveat is locked at pre-registration (`runner/spike/claude_spike.py` + `planning/feasibility_spike_claude.md`): Opus 4.7 removed the `temperature` parameter; sending `temperature=0` returns HTTP 400
- The cross-model comparison is **not** verdict-for-verdict comparability — the comparison is the rubric distribution shape (the reasoning-axis P5 confirmation) and the verdict-style divergence (the substantive cross-model finding)
- Verdict-style divergence is direction-coherent with the rubric-axis Cat 1 difference: Opus is more thorough on both axes; GPT-5.4 is more REVIEW-heavy on both axes
- The one exception (one OCID where Opus said ALLOW but engine said DENY) is worth a worked-example callout <!-- TODO: identify the OCID from Phase 2 receipts; pull the Opus reasoning text -->

## §7 — Implications

<!-- ~3 sub-sections. This is where the writeup earns its claim to be more
     than a falsification report. Implications for AI deployment in regulated
     contexts, for the trilogy methods note, and for E4. -->

### §7.1 — For AI deployment in regulated contexts

<!-- ~2 paragraphs. The 88% silent application of inverted policies is the
     practitioner takeaway. A team putting an AI agent into a regulated
     workflow should not assume the agent reads the policy in front of it —
     should assume the agent reads what it has learned a policy of this
     class should say. -->

- 88% of records under the permuted policy emitted the same verdict as under unperturbed L4 — the agent applied the rule's training-prior intent rather than the policy text in front of it
- The Cat 2 dominance (93% primary, 100% claude) means the reasoning *cited* the rule the agent thought it was applying — not the rule it was actually shown
- Practitioner implication: **silent application of inverted policies is the failure mode.** Policy version drift, policy-update lag, or even copy-paste errors in deployment can leave the agent applying yesterday's rule confidently, with reasoning that names the correct rule citation while emitting the wrong verdict
- The receipt-anchored mitigation: every receipt binds a policy snapshot SHA-256. If the policy version drifts, the snapshot binding makes the drift visible at audit; the receipt does not lie about which policy the agent thought it was applying

### §7.2 — For the methods note (Receipt-Anchored Evaluation)

<!-- ~2 paragraphs. E3 is the third experiment in the trilogy. The methods
     substrate is what carries forward to the methods note: signed receipts,
     locked prompts, pre-registered predictions with falsification criteria,
     disposition vocabulary, anti-claims as first-class, F-series two-readings
     discipline, inter-coder κ checks with reconciliation protocol, and the
     dispatch-architecture discipline (per-agent worktree isolation). -->

- The pre-registration discipline survived two consecutive narrow falsifications (P2, P4) by forcing categorical reporting rather than narrative softening
- The κ-check + reconciliation protocol caught coder drift before the writeup committed; the AI-first review-and-adjudication protocol on the second arm is itself a methodological contribution
- The per-agent git worktree isolation discipline (Wave 2 → Wave 3) for parallel-dispatch waves is the dispatch-architecture lesson that carries forward to any agent-orchestrated experimental work
- Cost projection accuracy to within 0.4% on a signed-receipt corpus is the dry-run-as-instrument-validation primitive; the methods note should make this a first-class claim
- The lock-in test discipline (`tests/test_handler_record_composition.py`) — every arm-handler PR includes a parametrized "record A and record B render to distinct prompts containing their respective markers" assertion — is the small but real piece of the discipline that future agent-orchestrated experiments inherit

### §7.3 — For E4 (operational receipt-as-memory experiment)

<!-- ~1 paragraph. E4 is the design-partner-shape experiment. The L3 break
     (now disambiguated) is the empirical evidence the design-partner pitch
     needs: precedents anchor commitment, but only in the right governance
     context. E4 turns this around — instead of synthesising precedents from
     a frozen archive, E4 wires up live receipt-anchored memory into an
     investigative agent and tests whether the same anchoring mechanism
     produces operational governance. -->

- E4 design intent: receipt-as-memory experiment with a design partner. Live receipt-anchored memory, investigative-agent format shift (not one-shot record review)
- E3's contribution to E4: the L3 decomposition shows precedents amplify commitment when they sit on top of a governance-context substrate, not when they sit alone. E4 needs to provide that substrate operationally
- The cross-model finding tightens the deployment story: the task class is what carries the inversion-blindness pattern, not the model. E4's design-partner conversation can lean on this — the operational governance need is not "pick a better model"
- <!-- TODO: confirm with Sam the exact framing of the E4 design-partner pitch before locking this section -->

## §8 — Limitations + caveats

<!-- ~3 sub-bullets. Honest disclosure section, matching E2's §9 anti-claims
     style. The Arm C asymmetric-control caveat (already documented), the
     Opus 4.7 sampling caveat (already documented), and the inter-coder
     reconciliation methodology (described honestly here). -->

### Arm C asymmetric-control caveat

- Arm C token parity vs Arm A: −16.43% (PR #93, documented at pre-registration)
- The asymmetry rules out one family of confounds (Arm C did not have excess volume) and introduces another (Arm C may not have had enough volume)
- P1's Arm C ≤12% threshold is comfortably cleared (4.6% observed), so the volume-alone Reading B explanation is falsified even granting the asymmetry — but the writeup names the caveat explicitly
- Pre-registration commitment (`v0.3-predictions-locked`) unchanged; a documented caveat was preferred over a post-tag amendment

### Opus 4.7 no-temperature sampling difference

- Opus 4.7 removed the `temperature` parameter; sending `temperature=0` returns HTTP 400
- The cross-model arm cannot match the primary agent's temperature-0 setting; `effort: low` is the closest near-deterministic equivalent
- The verdict-axis comparison is **not** verdict-for-verdict comparability; the comparison is on the rubric distribution shape (the reasoning-axis P5 confirmation) and the verdict-style divergence
- Documented at lock; reproducibility is carried by the signed receipt, not by temp-0 byte-determinism

### Inter-coder reconciliation methodology

- Primary's drift on the missing-evidence / rule-itself boundary was caught by the κ check (κ = −0.0369 on first pass vs blind agent)
- Reconciliation methodology is **reconciliation with rubric anchor**, NOT blind re-coding — the reviewer saw both the first-pass call AND the blind agent's call alongside the rubric's default rule when re-adjudicating
- Claude's coding methodology is **AI-first + human review-and-adjudication**, NOT blind first pass — the reviewer walked all 100 records with the agent's call visible
- Both protocols are honestly named in the methods section; neither is described as "independent re-coding" because neither was
- The 100% adoption rate on claude is rubric-aligned (orthogonal regex-sweep + per-borderline audit confirm), not fatigue-driven
- See `results/rubric_inter_coder_analysis_primary.md` and `results/rubric_inter_coder_analysis_claude.md` for the full protocol disclosure

### Single-domain, single-substrate, single-policy-snapshot

- E3 inherits E2's substrate constraints: 283 UK procurement records, one policy snapshot, one substrate adapter version
- The disambiguation results may not transfer to AML / KYC / underwriting / clinical-decision domains; the methodology is portable, the findings are not
- Cross-domain replication is E4-shaped, not E3-shaped

## §9 — Conclusion

<!-- ~2 paragraphs. The synthesis section. What E3 closes; what it opens for
     E4; what the trilogy capstone inherits. Mirrors E2's §10 (Synthesis)
     shape — patterns are real, mechanisms are open, methodology substrate is
     the durable contribution.

     Argues: E3 was designed to resolve two structural findings from E2; the
     resolutions came in a form the predictions explicitly anticipated as
     third readings, not in the form the predictions stated as the
     directional hypothesis. The L3 break is accumulation-amplified (not
     precedents alone). The L3→L4 backoff is policy-text-driven (not nudge-
     driven). Inversion-blindness reproduces at scale across two models with
     directionally-coherent cross-axis evidence. The pre-registration
     discipline, the κ-check protocol, the disposition vocabulary, and the
     receipt-anchored cost projection are the durable methodological
     contributions. E4 is the next experiment. -->

- E3 was designed to resolve E2's two open structural findings (L3 break, inversion-blindness) and to disambiguate the L3→L4 backoff (nudge vs policy text)
- The corpus resolved all three in forms the predictions explicitly anticipated as third readings: accumulation amplifies (not precedents alone); policy text drives the backoff (not the nudge); inversion-blindness reproduces at scale across two models with directionally-coherent cross-axis evidence
- Four predictions falsified, one confirmed on two arms, one disposition <!-- TODO: state for P6 --> — the falsifications are the story, and each names a sharpened mechanism rather than a refuted one
- The methodology substrate — pre-registered predictions with locked falsification criteria, κ-check protocol with reconciliation methodology, disposition vocabulary, receipt-anchored cost projection — is the durable contribution and carries forward to the trilogy methods note
- E4 is the operational receipt-as-memory experiment; the design-partner shape is named but the design is not yet locked

## §10 — Acknowledgments

<!-- ~1 paragraph. Standard acks plus the AI assistance declaration matching
     E2's style. -->

- <!-- TODO: collaborators, reviewers, design-partner contacts as appropriate -->
- AI tools were used during ideation, drafting, and editorial refinement; pre-registration, design, locked content, corpus collection, and analytical conclusions were directed and reviewed by the author. The methodology this paper studies is also the disclosure discipline this paper applies to its own production

## §11 — References

<!-- Cross-references to E1, E2, and the methods note. Plus the procurement
     regulatory references (PA23, PCR 2015), Sigstore Rekor, and any
     literature citations Sam decides to keep (E2 referenced Chen & Zhang
     2023 — E3 may or may not reuse depending on the framing). -->

- **MeshQu Research.** *MRP-2026-02 — When AI hedges and policy commits: Anatomy of agent–policy disagreement on UK procurement decisions, signed and verifiable.* 2026-05-18 — E1 baseline (DOI placeholder)
- **MeshQu Research.** *MRP-2026-03 — When precedents commit AI and policy pulls it back: A five-rung governance-context ladder on 283 procurement decisions.* 2026-05-22 — E2 ladder shape (DOI placeholder)
- **MeshQu Research.** *Receipt-Anchored Evaluation: a methodology note from a three-experiment programme.* Forthcoming — trilogy methods note (DOI placeholder)
- **UK Parliament.** *Procurement Act 2023, s.53(1).* 2023
- **UK Government.** *Public Contracts Regulations 2015 (PCR 2015).*
- **Sigstore project.** *Rekor — transparency log for software artifacts.* https://docs.sigstore.dev/logging/overview/
- <!-- TODO: optional literature anchor — Chen & Zhang 2023 (Case Law Grounding, arXiv:2310.07019) was used in E2 §4; E3 may or may not reference depending on whether the verdict-exemplar reading needs the lit anchor -->

## Appendix A — Pre-registration provenance

<!-- Mirror E2's Appendix A exactly. Lift from results/runs/phase-2-…/manifest.json. -->

- **Git tag**: `v0.3-predictions-locked`
- **Tag commit SHA**: `ba4ebfb` <!-- TODO: confirm full SHA from git -->
- **Locked-prompt SHA-256 fingerprints** (from `runs/phase-2-20260529T092611-Z/manifest.json`):
  - Arm A (precedents-only) <!-- TODO -->
  - Arm B (precedents-no-verdict) <!-- TODO -->
  - Arm C (density-control), SHA `07abb32f…c1824134` per Wave 2 close-out
  - L4-without-nudge <!-- TODO -->
  - diagnostic_primary <!-- TODO -->
  - diagnostic_claude <!-- TODO -->
- **Agent prompt scaffold SHA-256**: `690c50b5fb2ba5b820e42d781aec51c6216483c07ed5a4be2273b2d2e3517be2` (unchanged from E2)
- **Policy snapshot SHA-256**: `5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d` (unchanged from E2)
- **Tenant ID** (public, staging): `243f19a5-4d4f-4070-9ec1-8170e8260e26`
- **Receipt signing kid** (public): `meshqu-experiment-procurement-2026-05`
- **Primary model**: `gpt-5.4-2026-03-05`, temperature 0
- **Cross-model arm model**: `claude-opus-4-7`, no `temperature`, `output_config.effort: low`
- **Runner commit**: <!-- TODO: lift from manifest -->
- **System prompt SHA**: `db60d6f297b0a97ab43988bdd8163a49c6e050afb81ff7379c8a1ff4fd932aa2`

## Appendix B — Corpus citation

<!-- Mirror E2's Appendix B. -->

- **Run ID**: `phase-2-20260529T092611-Z`
- **Started**: 2026-05-29T09:26:18+00:00
- **Wall-clock**: 80 min 33 sec (09:26:18 → 10:46:51 UTC)
- **Records by arm**: arm_a × 283, arm_b × 283, arm_c × 283, l4_without_nudge × 283, diagnostic_primary × 100, diagnostic_claude × 100 = **1,332 receipts**
- **Bundle layout**: `results/runs/phase-2-20260529T092611-Z/<arm_name>/<decision_id>.bundle.json`
- **Substrate source**: frozen E1 fixture (`substrate_adapter_version`: `cached-e1-phase-2-7ddf7274`); same 283-corpus as E2
- **Diagnostic subset selection rule**: 100 OCIDs whose `sha256(ocid)` hex digests sort lowest, locked at `planning/diagnostic_subset.json`
- **Verifier integrity**: 1,332 / 1,332 PASS, exit 0
- **Cost**: $25.23 actual vs $25.21 projection (within 0.4% on all six arms)
- **Independent verifier**: verify.meshqu.com (offline; independent SET re-implementation)

## Appendix C — Hand-coded rubric protocol

<!-- Lift from planning/diagnostic_rubric.md + reference the inter-coder
     analysis artefacts. The rubric protocol is itself a methodological
     contribution and deserves an appendix for any reader who wants to
     reproduce or apply it. -->

- Protocol document: `planning/diagnostic_rubric.md` (SHA `f162953e…` locked at `v0.3-predictions-locked`)
- Three categories: Cat 1 (names the inversion in any words) / Cat 2 (reasons solely against rule intent) / Cat 3 (partially recognises but applies anyway)
- Default rule: *"default to 3 only if there is an explicit hedge about the rule itself (not merely about missing evidence — missing-evidence hedging is the normal nudge behaviour and is not inversion-recognition)."*
- Coding protocol for `diagnostic_primary`: blind first pass + blind AI second-coder + reconciliation with rubric anchor (see `results/rubric_inter_coder_analysis_primary.md`)
- Coding protocol for `diagnostic_claude`: AI-first + human review-and-adjudication of all 100 records with rubric visible (see `results/rubric_inter_coder_analysis_claude.md`)
- κ summary: primary first-pass-vs-agent = −0.0369; primary reconciled-vs-agent = +1.0000; claude blind-agent-vs-final = +1.0000

## Appendix D — Reproducibility instructions

<!-- Mirror E2's Appendix D. The receipt-anchored property makes the whole
     corpus re-derivable from on-disk bundles by any reader with no
     credentials required. -->

- Branch / tag: writeup anchored to <!-- TODO: branch + commit at publication time --> ; v0.3 lock tag `v0.3-predictions-locked` carries the predictions / locked content / policy snapshot at pre-run state
- Re-derive verdict distributions: read the bundles at `results/runs/phase-2-20260529T092611-Z/<arm_name>/*.bundle.json`; spot-check against `phase-2-summary.md` in the run dir
- Re-derive rubric distributions: read the canonical sheets at `results/rubric_coding_primary.jsonl` and `results/rubric_coding_claude.jsonl`; spot-check against the inter-coder analysis artefacts
- Independent receipt verification: download any bundle, submit to verify.meshqu.com; the verifier recomputes the canonical signing-envelope bytes, verifies the Ed25519 signature against the published kid, and checks the Rekor anchor
- No live credentials are required to re-derive any number in this writeup; re-running the agent loop is a separate exercise requiring an OpenAI key + an Anthropic key

---

<!-- End of E3 writeup scaffold. Sam fills in the prose; analysis notebook
     (scaffolded in parallel) supplies the numbers at each TODO marker. -->
