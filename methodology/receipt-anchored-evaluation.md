---
title: "Receipt-Anchored Evaluation: a methodology for cryptographically verifiable empirical research on AI-governance behaviour"
subtitle: "A trilogy capstone — methods extracted from three pre-registered applied experiments on UK public procurement substrate"
id: MM-2026-01
authors:
  - Sam Carter (MeshQu)
status: SCAFFOLD (structural skeleton; prose pending)
classification: PUBLIC
version: 0.1-scaffold
published_at: TBD
tags: [methodology, receipts, pre-registration, ai-governance, evaluation, transparency-log]
toc: true
branding: meshqu-research
density: research
references_layout: numbered
---

<!--
  SCAFFOLD CONTRACT — read before authoring prose.

  This file is a *structural* methods note. Each section carries:
    1. A 1–2 sentence intent brief (what the section must achieve)
    2. Bullet placeholders for substantive claims
    3. Citation hooks (HTML comments) pointing at the on-disk artefact
       that supplies the evidence — never paraphrase from training-data recall

  Hard rails (from the scaffolding brief):
    - This is the strategic load-bearing artifact. Bankers, regulators, and
      methodologically careful researchers will read it to decide whether
      Receipt-Anchored Evaluation is a defensible methodology.
    - The note must stand independently. Do not assume the reader has read
      E1 / E2 / E3.
    - Honesty about falsifications is the strength. E3's disposition mix
      — 1 Confirmed (P5), 3 Falsified cleanly against locked bands (P1,
      P3, P6), 2 Under-tested (P2, P4 — confirmation-band-only spec) —
      is the load-bearing example, not a footnote. The 2 Under-tested
      outcomes are themselves the §5.6 discipline refinement, not a
      weakness to bury.
    - Length target: ~10–20 structured pages. Terse, technical, citable.
    - Voice register: borrow from procurement-decisions/writeup/main.md
      (E1) and the E2 published writeup. Practitioner-legible per
      ../programme/STRUCTURAL-PARITY.md "Voice conventions". No precious
      adverbs; technical precision preserved where load-bearing.
-->

# Receipt-Anchored Evaluation: a methodology for cryptographically verifiable empirical research on AI-governance behaviour

## 1 · Abstract

<!--
  Intent: one paragraph that captures the full contribution. A
  methodologically careful reader should be able to decide from this
  paragraph alone whether to read the rest. Length: ~250–400 words.

  Must contain, in order:
    - The problem (AI-governance empirical research is conceptual,
      reputational, and non-reproducible)
    - The methodology in one sentence ("Receipt-Anchored Evaluation
      fuses Ed25519-signed, transparency-log-anchored decision receipts
      with clinical-trial-style pre-registration")
    - The contribution (cryptographic verifiability + honest falsification
      vocabulary as a unified discipline)
    - The trilogy as evidence (E1 baseline, E2 context-gradient, E3
      disambiguation; ~3,061 signed decisions across the programme)
    - One headline statistic that lands the methodological observation:
      E3 confirmed 1 prediction (P5, on both diagnostic arms),
      falsified 3 cleanly against locked bands (P1, P3, P6), and
      produced 2 Under-tested results (P2, P4 — observed below the
      confirmation band, with no explicit falsification band registered
      at lock time). The Under-tested outcomes are themselves a
      methodological contribution: a discovered discipline refinement
      for pre-registering cross-axis and robustness-at-scale predictions,
      recommended as a carry-forward for E4. See §5.6.
    - One-sentence anti-claim closing (per the STRUCTURAL-PARITY voice
      convention — what this methodology does NOT establish)

  Citation hooks:
-->
<!-- cite: methodology/README.md "core idea" paragraph for the "product is the research instrument" framing -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry for the 1,332-receipt Phase 2 figure -->
<!-- cite: procurement-decisions/writeup/main.md §1 for the regulatory-stakes framing -->

- _Placeholder: opening paragraph (~250–400 words)._

---

## 2 · The receipt primitive

<!--
  Intent: explain the decision-receipt artefact as a research-grade
  evidence object. Reader after this section should be able to state:
  what a receipt contains, what it is signed with, where it is anchored,
  and why those properties matter for evaluation.

  Length target: ~1.5–2 pages.
-->

### 2.1 What a Decision Receipt is

<!-- Intent: define the primitive in operational terms. -->

- Signed record of one AI-or-policy decision: the inputs (substrate record + field-provenance envelope), the policy snapshot evaluated against, the verdict, the violations, the agent's reasoning hash.
- Ed25519 signature over a canonical-JSON payload, scoped to a tenant-bound signing kid.
- Schema-versioned (`receipt_schema_version`). Forward-compatible field additions are additive; semantic shifts force a version bump.
- Replayable offline: every byte the verifier hashes is in the bundle.

<!-- cite: packages/meshqu-core/src/integrity.ts in the tradequ monorepo for the canonical-JSON hash construction -->
<!-- cite: procurement-decisions/writeup/main.md §2 paragraph on "A receipt records three things" — the what/who/that-nothing-changed framing -->

### 2.2 What a Decision Receipt is anchored to

<!-- Intent: explain transparency-log anchoring and why it removes a trust assumption. -->

- Each signed receipt is anchored to the public Sigstore Rekor transparency log via a DSSE envelope.
- A reader verifies a receipt by checking the Ed25519 signature against the published kid AND checking the Rekor inclusion proof — neither step requires MeshQu's API.
- The verification surface lives at [verify.meshqu.com](https://verify.meshqu.com) and re-implements the SET independently (no shared code with the production verifier).

<!-- cite: methodology/README.md "Why it holds up" section for the four verifiability properties -->
<!-- cite: packages/meshqu-core/src/transparency.ts in the tradequ monorepo for Rekor anchoring -->

### 2.3 Why this matters: cryptographic decision provenance for AI agents

<!--
  Intent: state the load-bearing claim that distinguishes receipts from
  application logging. Single short paragraph plus 3–4 bullets. Avoid
  marketing voice — this is a methodology note, not a product page.
-->

- Application logs are evidence only insofar as you trust the logger; receipts are evidence under the public signing key alone.
- The integrity guarantee is cryptographic and procedural, not reputational. A reader can re-derive every headline number from on-disk bundles without trusting the authors.
- "The product is the research instrument": the same signed receipts MeshQu ships in production double as the reproducibility substrate for empirical research on AI-governance behaviour.

<!-- cite: methodology/README.md "core idea" — "the product is the research instrument" verbatim phrase -->
<!-- cite: programme/PROCESS.md "Reproducibility infrastructure as a layered substrate" — the three-layer framing (artefact / pre-data / post-data) -->

---

## 3 · Pre-registered AI evaluation

<!--
  Intent: explain the research discipline layer that sits on top of the
  receipt primitive. Reader after this section should understand why
  receipts without pre-registration are insufficient, and why the
  disposition vocabulary is a contract not a stylistic preference.

  Length target: ~2 pages.
-->

### 3.1 The clinical-trials borrow

<!-- Intent: state the analogy precisely and bound it. -->

- Predictions, prompts, ladder content, and policy snapshot are SHA-bound and tag-anchored at `v0.X-predictions-locked` **before any data is collected**.
- Predictions specify a confirmation band and, where the experimental hypothesis structure supports it, an explicit falsification band. The disposition vocabulary at `programme/PROCESS.md` (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested) handles the gray zone where observed values fall outside the confirmation band but the locked spec did not register a falsification band. E3 surfaced cases where this gray zone was operative — see §5.6.
- The lock is the integrity primitive that converts "we observed X" into "we predicted X-or-not-X, and the corpus showed which".
- Discipline refinement surfaced by E3: predictions for cross-axis comparisons and robustness-at-scale claims should pre-register BOTH bands at lock time, mapping the gray zone explicitly to Under-tested. Carry-forward observation expanded in §5.6 and prescriptive fix listed in §6.6.

<!-- cite: procurement-context-disambiguation/planning/predictions.md for the worked example of segment-level prediction — P1/P3/P5/P6 lock both bands; P2/P4 lock only the confirmation band -->
<!-- cite: procurement-context-disambiguation/results/analysis.py disposition_methodology block (lines ~599-760) for the locked-vs-script-judgment disclosure pattern that handles the gray zone -->
<!-- cite: programme/PROCESS.md gate #1 "Brief verifies current state before pinning anchors" + gate #8 "Title commitment at the pre-registration lock" -->

### 3.2 The disposition vocabulary

<!--
  Intent: name the disposition vocabularies as closed registers. Two
  sixth-disposition tokens coexist in the trilogy: P-series predictions
  (registered at lock-time) close with Under-tested; F-series findings
  (registered at write-time) close with Discovered. Both are legitimate;
  they apply to different registers. The methods note must enumerate
  both side-by-side, not silently drop one.
-->

The trilogy carries **two** disposition registers — one bound to pre-registered predictions, one bound to post-data findings. They share five tokens and diverge on the sixth. Cross-register conflation is a discipline failure.

**P-series (predictions, registered at lock-time):**

- **Confirmed** — the corpus produced a value inside the confirmation band.
- **Falsified** — the corpus produced a value inside the falsification band.
- **Inverted** — the corpus produced a value in the opposite direction to the prediction (a sharper form of falsification; the signal exists but ran the other way).
- **Refuted** — the corpus produced a value that rules out the prediction's underlying mechanism.
- **Deferred** — measurement instrument inadequate; the prediction is unresolved on this experiment.
- **Under-tested** — observed value sits between the confirmation and falsification bands, or no falsification band was registered at lock time. A positive disposition for under-specified gray zones, not a passive "inconclusive".

**F-series (findings, registered at write-time):**

- **Confirmed** — same definition as P-series.
- **Falsified** — same definition as P-series.
- **Inverted** — same definition as P-series.
- **Refuted** — same definition as P-series.
- **Deferred** — same definition as P-series.
- **Discovered** — the finding did not pre-exist as a P-series prediction but surfaced from the corpus during analysis. The post-data analogue of Under-tested: a positive disposition for a finding the lock did not anticipate, not a backdoor "we predicted this all along".

The two sixth-disposition tokens are not interchangeable. A P-series prediction whose observed value falls in the gray zone is **Under-tested** (the lock did not pre-register what the gray-zone landing means). An F-series finding that surfaced from the corpus without a pre-registered prediction is **Discovered** (no lock to grade it against). Reporting a Discovered finding as Confirmed-from-prediction is post-hoc smoothing; reporting an Under-tested prediction as Discovered is escape-hatch backfill. The trilogy carries both registers; pre-registered predictions get the P-vocabulary; post-data findings get the F-vocabulary.

<!-- cite: procurement-context-disambiguation/planning/predictions.md §"Definition of 'report honestly'" for the locked P-series vocabulary contract (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested) -->
<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 paragraph "F-series structure as a methodological contribution" for the F-series vocabulary contract (Confirmed / Falsified / Inverted / Refuted / Deferred / Discovered) -->
<!-- cite: programme/PROCESS.md "Honest falsification" paragraph for the no-post-hoc-smoothing principle -->

### 3.3 Why this matters: confirmation-bias reduction + honest measurement

<!-- Intent: name the specific bias the discipline is engineered against. -->

- Without pre-registration, post-hoc smoothing is the path of least resistance: a falsified prediction becomes "partially confirmed" or "broadly directional". The disposition vocabulary cuts off that path by construction.
- Without numeric falsification bands, any result can be reframed as supporting the hypothesis. Numeric bands fix the goalposts before the corpus arrives.
- Without SHA-binding of prompts and policy snapshot, the experiment is not replayable — predictions and evidence drift apart in the time between lock and report.

<!-- cite: programme/PROCESS.md "Discipline is the contribution" framing -->

### 3.4 The inherited discipline registers

<!--
  Intent: enumerate the five discipline registers the trilogy carries
  forward. The disposition vocabulary (§3.2) is one register among five.
  Naming all five explicitly is what stops the methods note from
  silently dropping half the discipline that the trilogy ran on. Each
  register is a closed, named contract; together they are what
  "Receipt-Anchored Evaluation" inherits beyond the receipt primitive
  itself.

  Style: intent-brief + bullets matching §3.1–§3.3. Each register names
  its load-bearing definition, names the canonical citation, and notes
  how the trilogy operationalised it.
-->

The trilogy inherits five named registers beyond the receipt primitive. Each is a closed contract — a vocabulary or shape pre-committed-to before the artefact is authored. The discipline is the sum of all five, not the disposition vocabulary alone.

**Register 1 — F-series register for post-data findings.** Each finding follows the same shape, lifted verbatim from E2 writeup-DRAFT.md §7: *"an explicit status label (Confirmed / Falsified / Inverted / Refuted / Deferred / Discovered), a numbered evidence block with denominators, two interpretive readings where the corpus admits two, an explicit anti-claims section that lists what the finding does not establish, and an E3-design implications block"*. E2 used F001–F012; E3 introduces F013–F017 (Piece 1 verdict-distribution refinement; cross-model verdict-style divergence; arm_c and diagnostic_claude anchor drift; κ-check coder drift catch). The F-series is the post-data analogue of the pre-data P-series — the same restraint discipline, applied to interpretation.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 paragraph "F-series structure as a methodological contribution" (the canonical definition lifted verbatim above) -->
<!-- cite: procurement-context-disambiguation/writeup/writeup.md for F013–F017 once the E3 writeup lands -->

**Register 2 — P-series register for pre-registered predictions.** Each prediction states (a) a confirmation band, (b) a falsification band where the experimental hypothesis structure supports it, and (c) the interpretive note bound to each direction. Disposition vocabulary locked at lock-time: {Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested} — see §3.2. The §5.6 observation refines this: predictions for cross-axis and robustness-at-scale claims should pre-register **both** bands, with the gray zone mapped explicitly to Under-tested. Cross-reference §5.6 for the worked example; §6.6 for the prescriptive carry-forward.

<!-- cite: procurement-context-disambiguation/planning/predictions.md §"Definition of 'report honestly'" for the locked vocabulary contract -->
<!-- cite: §3.2 of this note for the side-by-side P-series + F-series vocabulary -->

**Register 3 — D-series register for behavioural axes spanning experiments.** Named axes carried across experiments. E2 Appendix C established D1–D9; the principal load-bearing axes are **D4 Policy resistance**, **D6 Precedent sensitivity**, and **D7 Uncertainty markers**. New D-axes get added at experiment-level as the corpus reveals them, not retrofitted post-hoc to flatter the result. E3's three-category rubric (Cat 1 names-inversion / Cat 2 reasons-against-intent / Cat 3 hybrid) is the hand-coded operationalisation of D4 — deferred from E2 Appendix C's lexicon-strict measurement (which surfaced 0/14 contradiction-naming fires) into E3's larger-n hand-coded protocol. The D-series register makes the cross-experiment continuity machine-checkable: D4 in E3 is **the same axis** as D4 in E2, just under a sharper instrument.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md Appendix C "Behavioural taxonomy v1.1 reference" for the D1–D9 enumeration -->
<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §8 paragraph "Larger Permuted-Policy diagnostic" for the deferred-from-E2-into-E3 hand-coded rubric design -->
<!-- cite: procurement-context-disambiguation/planning/predictions.md for the locked three-category rubric protocol (E3's D4 operationalisation) -->
<!-- cite: §6.7 of this note for the carry-forward -->

**Register 4 — Reading X / Framing X.Y discipline for naming alternative interpretations.** When a finding admits two interpretive readings, both are explicitly named: E3 P1's **Reading A** (precedents-only drives commitment) vs **Reading B** (full E2 ladder drives commitment); E3 P3's **Framing A.1** (nudge load-bearing for L4 backoff) vs **Framing A.2** (policy text load-bearing); E2 F008's **Reading A** vs **Reading B**; E2 F012's methodological **Reading (i)** vs substantive **Reading (ii)**. The receipt-anchored audit trail preserves which Reading was carried into the writeup as the leaned-toward interpretation; the un-leaned-toward reading is not suppressed but explicitly named and dated. Preservation-of-alternatives — not collapse-to-a-single-reading — is the voice the trilogy commits to.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 paragraph "Two-readings discipline as a programme method" for the canonical statement -->
<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §4 "Two readings" subsection for the worked example -->
<!-- cite: procurement-context-disambiguation/writeup/writeup.md for E3's P1 Reading A/B and P3 Framing A.1/A.2 -->

**Register 5 — Anti-claims as first-class output.** Each F-series finding carries inline anti-claims (proximity discipline — the reader sees what a finding does not establish at the point it is established). The writeup also aggregates anti-claims into a dedicated §9 (audit-lens discipline — the reader sees the full ledger of un-established claims in one place). The trilogy's refinement, adopted as canonical: **both** registers — inline-per-finding AND aggregated-§9 — not either-or. This is the §5/§6 discipline-refinement contribution the trilogy lifts forward; do not collapse to one register at lock or write time.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §9 "Anti-claims" for the aggregated §9 worked example -->
<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 (F012 inline anti-claims block within the finding) for the proximity-discipline worked example -->
<!-- cite: §5.6 and §6.6 of this note for the discipline-refinement framing this register sits inside -->

---

## 4 · The three-experiment programme as worked example

<!--
  Intent: ground the methodology in three completed applications. Each
  sub-section is a one-paragraph brief — what the experiment held fixed,
  what it varied, what it found, what disposition each prediction landed
  at. The reader after this section understands that Receipt-Anchored
  Evaluation is not theory — it has been stress-tested three times on
  the same substrate.

  Length target: ~3–4 pages total across the three sub-sections + one
  closing aggregate paragraph.
-->

### 4.1 E1 — procurement-decisions (MRP-2026-02)

<!-- Intent: baseline. Receipt primitive at corpus scale. -->

- Substrate: 283-record UK Contracts Finder OCDS corpus, frozen pre-run.
- Design: locked GPT-5.4 agent reviews each record without policy visibility; MeshQu evaluates the same records against executable policy. Both sides emit signed receipts.
- Headline: evidence-sensitive caution. The agent reached for REVIEW on 97.5% of the corpus, naming evidence gaps in its reasoning; MeshQu's policy produced 139 DENYs over the same evidence.
- Lock anchor: `v0.1-predictions-locked` at `bd7a795` (2026-05-15).
- Status: published 2026-05-18 as MRP-2026-02.

<!-- cite: procurement-decisions/writeup/main.md §1 + §2 -->
<!-- cite: procurement-decisions/README.md for the corpus + lock convention -->
<!-- DOI: pending — link from the references section -->

### 4.2 E2 — procurement-context-gradient (MRP-2026-03)

<!--
  Intent: institutional memory mechanism measured. E2 varies one thing:
  the governance context the agent sees.
-->

- Substrate: identical 283-record corpus. Same agent. Same policy snapshot. Same substrate adapter.
- Design: five-rung ladder (L0 baseline → L4 full policy + precedents + verdicts + nudge), additive content per rung. 283 records × 5 rungs = 1,415 signed receipts.
- Headline: non-monotonic verdict commitment. The agent first commits at scale at the L3 (precedents) rung — 37.8% DENY-rate (107/283). L4 backoff reverts 46 of those 107 to REVIEW.
- Lock anchor: `v0.2-predictions-locked`.
- Status: published 2026-05-27 as MRP-2026-03.

<!-- cite: procurement-context-gradient/README.md "What carries over from E1" + "What's new" -->
<!-- cite: procurement-context-disambiguation/planning/predictions.md "Reference points from E2" — the 37.8% L3 DENY-rate + 46/107 backoff figures -->
<!-- DOI: pending — link from the references section -->

### 4.3 E3 — procurement-context-disambiguation

<!--
  Intent: the methodologically richest experiment. E3 sharpens E2's
  findings into attributions. Disposition mix per the canonical
  analysis table (analysis.py disposition_methodology block):
    - 1 Confirmed: P5 (on both diagnostic arms)
    - 3 Falsified cleanly against locked bands: P1, P3, P6
    - 2 Under-tested: P2, P4 (confirmation-band-only spec; observed
      below confirm with no falsification band registered at lock time)
  This is the load-bearing example for the "pre-registration catches
  the surprising mechanism" observation in §5.1 AND for the
  "pre-register both bands at lock time" discipline refinement in §5.6.
-->

- Substrate: identical 283-record corpus + a locked 100-record diagnostic subset.
- Design: three L3 decomposition arms (precedents-only, precedents-no-verdict, density-control); one L4-without-nudge arm; two scaled Permuted-Policy diagnostic arms (primary GPT-5.4 + cross-model Opus 4.7).
- Corpus collection: 1,332 signed receipts across six arms; 80 min 33 s wall-clock; $25.23 actual vs $25.21 projected (within 0.4% on all six arms).
- Headlines:
  - **Accumulation drives commitment**, not raw volume. Arm A (precedents-only) commits 3.5%; Arm B (no verdicts) 0.0%; Arm C (density-control) 4.6%. P1 falsified by the locked "Arm A < 20%" clause — the full E2 ladder, not precedents alone, drives the commitment signal.
  - **Policy text drives backoff**, not the anti-sycophancy nudge. L4-without-nudge retention on the L3-DENY set sat at 60.7% — below the 65% falsification floor; P3 falsified by the locked band.
  - **Inversion-blindness at scale**, cross-model. On the n=100 Permuted-Policy subset, both GPT-5.4 (93% rubric Cat 2) and Opus 4.7 (100% rubric Cat 2) predominantly apply the rule's intent rather than its inverted text. P5 confirmed on both arms.
  - **Under-tested under-specifications**. P2 (governance-memory mechanism, |A−B| gap) locked only the confirmation band (≥ 15pp); observed +3.5pp gap is below confirm with no falsification band to trip → Under-tested. P4 (inversion-blindness floor at scale) locked only the confirmation band (≥ 90%); observed 88% is 2pp below confirm with no falsification band registered → Under-tested. The under-specifications themselves are the methodological contribution — see §5.6.
- Lock anchor: `v0.3-predictions-locked`.
- Status: writeup in progress (Phase 3).

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry "Phase 2 complete: 1,332 receipts, all five gates PASS, $25.23" -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-06-07 entries (×2) for Phase 2.5 rubric outcomes (P5 Confirmed both arms) -->
<!-- cite: procurement-context-disambiguation/planning/predictions.md for the full P1–P6 spec (verifies which predictions locked both bands vs confirm-band-only) -->
<!-- cite: procurement-context-disambiguation/results/analysis.py disposition_methodology block + procurement-context-disambiguation/results/analysis_outputs.json disposition_table for the canonical 1-Confirmed / 3-Falsified / 2-Under-tested mix -->

### 4.4 Aggregate

<!-- Intent: one short paragraph that names the cumulative scale. -->

- ~3,061 signed decisions across the programme (283 E1 + 1,415 E2 + 1,332 E3 + 31 smoke/dry-run receipts).
- Every receipt verifiable offline against the public Sigstore Rekor log under the experiment kid `meshqu-experiment-procurement-2026-05`.
- The methodology is stress-tested under three substantively different research questions on a held-fixed substrate.

<!-- cite: aggregate computed from each experiment's published receipt count -->

---

## 5 · Methodological observations from the programme

<!--
  Intent: this is the "what the trilogy taught us about the method" section.
  Each sub-section is one observation supported by a worked example drawn
  from a specific experiment. The reader after this section should be able
  to defend each observation under cross-examination.

  Length target: ~3–4 pages. The observations are the load-bearing
  contribution beyond what any single experiment establishes alone.
-->

### 5.1 Pre-registration catches the surprising mechanism, not the expected one

<!--
  Intent: E3 produced 3 clean falsifications (P1, P3, P6) and 2
  Under-tested results (P2, P4). The point is that the falsifications
  are where the experiment paid off, not where it failed. Without the
  lock, the falsified predictions would have been quietly reshaped
  into post-hoc confirmations, and the Under-tested results would
  have become "broadly directional" rather than naming the
  pre-registration gap (which is itself the §5.6 contribution).
-->

- P1 (precedents drive commitment) was falsified by the locked "Arm A < 20%" clause — Arm A observed 3.5% DENY-rate, dramatically outside the directional 20–30% range the prediction anticipated. The full E2 ladder, not precedents alone, drives commitment.
- P3 (anti-sycophancy nudge load-bearing for L3→L4 backoff) was falsified by the locked retention ≤ 65% clause — observed retention 60.7% on the 107-record L3-DENY set. The hypothesis was that removing the nudge would preserve retention; instead the policy text alone drove the backoff in the opposite direction.
- P6 (inversion-blindness is task-class, not model-specific) was falsified by the locked > 15pp clause — observed 46pp gap between primary-model and Claude same-as-unperturbed rates. predictions.md pre-registered this outcome as "a strong finding, not a failure" precisely because the model-specific behaviour is substantively interesting.
- The one confirmed prediction (P5, on both diagnostic arms) carries more weight precisely because it sits alongside three falsifications and two Under-tested results in the same writeup — the methodology is not selecting for results.

<!-- cite: procurement-context-disambiguation/planning/predictions.md for the P1–P6 falsification bands (P1, P3, P5, P6 lock both bands; P2, P4 lock confirmation only) -->
<!-- cite: procurement-context-disambiguation/results/analysis.py disposition_methodology block for the per-prediction locked-vs-script-judgment disclosure -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry "Piece 2 — L4 decomposition" for the L4-without-nudge inversion -->

### 5.2 Inter-coder κ check surfaces drift even with an experienced single coder

<!--
  Intent: the E3 Phase 2.5 worked example. The single coder (Sam) coded
  100 reasoning texts blind, then a blind AI second-coder re-coded;
  κ ≈ −0.04 surfaced systematic drift at one rubric boundary;
  reconciliation under fresh eyes produced 79/79 second-coder-adopted
  on contested records; final κ = +1.00; P5 Confirmed.

  This is a worked example of the discipline catching its own coder's
  fatigue. Without the κ check, the writeup would have committed to
  "Under-tested" on substantively confirmed evidence.
-->

- First-pass single-coder distribution (8 / 25 / 67) would have reported P5 as Under-tested.
- Blind AI second-coder pass surfaced κ = −0.0369 — less than chance agreement — concentrated at the Cat 2 / Cat 3 boundary (66 of 79 disagreements).
- Reconciliation under the rubric's default rule produced 79/79 `second-coder-adopted` actions; reconciled distribution 7/93/0; P5 Confirmed.
- The audit trail is per-record: every contested record carries `first_pass_category`, `second_coder_category`, `reconciliation_action`.

<!-- cite: procurement-context-disambiguation/results/rubric_inter_coder_analysis_primary.md for κ table + 3×3 confusion matrix + reconciliation outcomes -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-06-07 entry "Phase 2.5 diagnostic_primary: drift, reconciliation, P5 Confirmed" -->

### 5.3 Cost projection accuracy at 4 decimal places

<!--
  Intent: the dry-run as instrument validation. E3's Phase 2 cost
  projection nailed actual at $25.23 vs $25.21 projected — within 0.4%
  on all six arms. The dry-run is not just a cost preview; it is a
  measurement instrument validation step.

  Worked example to lift verbatim into the prose: the smoke→dry-run
  ratio is pinned in code; deviation triggers a re-baseline before
  Phase 2 fires.
-->

- Dry-run cost ratios are persisted per arm; Phase 2 cost ratios are computed against the same baseline at run end.
- Five-gate sign-off includes a ±15% cost accuracy gate as one of five PASS conditions; Phase 2 hit ±0.4%.
- The accuracy is not a virtue claim — it is what an instrument-validated runner produces when the substrate, agent, and policy are pinned.

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry §"Five-gate sign-off" for the ±0.4% figure -->

### 5.4 Disposition vocabulary as honest-reporting discipline

<!--
  Intent: the vocabulary is the contract. Once locked, "partial
  confirmation" is unavailable as an escape hatch. The writeup author
  is forced to commit to one of six dispositions per prediction.

  Worked example: E2 retrospective — P1/P2 specified at aggregate-trend
  level reported as falsifications of a uniformity assumption when the
  corpus actually showed non-monotonic shapes per segment. E3 corrected
  by specifying per-segment.
-->

- Closed vocabulary prevents rhetorical drift between "Confirmed" and "broadly directional".
- Segment-level specification (E3) prevents aggregate-level reporting from collapsing real non-monotonic shapes (E2 retrospective).
- The disposition is a per-prediction commitment in §3 of every writeup; never bundled at the experiment level.

<!-- cite: procurement-context-disambiguation/planning/predictions.md §"Definition of 'report honestly'" -->
<!-- cite: programme/STRUCTURAL-PARITY.md §"§3 — Predictions vs outcomes (table-first; per-prediction disposition using locked vocabulary)" -->

### 5.5 Lock-in test discipline for replicable runners

<!--
  Intent: E3 surfaced three lock-in test patterns that should carry
  forward to every future runner. Each catches a specific failure mode
  that would otherwise propagate silently to the writeup.
-->

- **Record-composition test** (PR #97). Parametrized "record A and record B render to distinct prompts containing their respective markers" — locks the property that the runner actually composes per-record prompts, not envelope-only ones. The pre-fix smoke run signed 14 receipts cleanly but received empty records on three arms; the lock-in test would have failed at wave-1.
- **Sidecar emission test**. Diagnostic arms must emit `<run_dir>/diagnostic/inverted_operator_spec.json` alongside the receipts. Tested by reading the sidecar shape rather than the receipts alone.
- **Observability fail-loud preconditions**. Phase 2 readiness gate distinguishes "configured" (dashboards exist) from "captured at runtime" (run-start + run-end PNGs land in `observability/screenshots/`). Item-level granularity required.

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-28 "Smoke read v2 + handler record-composition fix (PR #97)" -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry §"(c) Readiness-item-14 caveat" for the configured-vs-captured distinction -->

### 5.6 Pre-registering both bands at lock time

<!--
  Intent: E3's 2 Under-tested outcomes (P2, P4) surfaced a discipline
  refinement — confirmation-band-only predictions leave the
  falsification side to analyst judgment at analysis time, weakening
  the pre-registration contract. The trilogy methodology recommends
  pre-registering both bands for all predictions, with explicit
  Under-tested zones documented at lock time. For multi-axis
  predictions (P6 in E3, registered on the verdict axis only despite
  rubric data being collected on both axes in the cross-model arm),
  pre-register axis-specific hypotheses with axis-specific bands.

  This is a real methodological contribution to lift, not damage
  control to bury. The trilogy's incomplete pre-registration
  discipline becomes the prescriptive carry-forward (§6.6) for E4.

  Worked example to lift verbatim into the prose: the analysis.py
  disposition_methodology block makes the rule-source distinction
  ("locked" vs script-time judgment) machine-disclosed for each
  prediction; this pattern is itself the honest-disclosure
  contribution for handling under-specified predictions.
-->

- E3's locked spec at `procurement-context-disambiguation/planning/predictions.md`: P1, P3, P5, P6 pre-register **both** a confirmation band AND an explicit falsification band; P2 and P4 pre-register **only** a confirmation band, leaving the falsification side to analyst judgment at analysis time.
- Observed values for P2 (+3.5pp gap, below 15pp confirm) and P4 (88%, 2pp below 90% confirm) fell into the gray zone the locked spec did not map — neither inside the confirmation band nor inside any locked falsification band. The honest disposition is Under-tested, per the locked vocabulary at `programme/PROCESS.md`. The analysis script discloses the rule-source per prediction (`rule_source: "locked"` plus the explicit `(none registered)` note when a falsification band is absent) rather than inventing a post-hoc falsification rule.
- The trilogy methodology recommends: predictions for cross-axis comparisons (P2's |A − B| gap) and robustness-at-scale claims (P4's same-as-L4 floor) should pre-register **both** bands at lock time, with the gray zone between confirm-floor and falsify-ceiling mapped explicitly to Under-tested. The intent is to remove analyst discretion from the disposition call entirely.
- Multi-axis predictions need axis-specific bands. P6 was registered on the verdict axis only ("same-as-unperturbed verdict rate within 15pp") despite the cross-model arm collecting rubric data on both verdict AND rubric axes. Folding multiple axes into one hypothesis under-specifies what the test is actually testing; pre-register axis-specific hypotheses with axis-specific bands.
- Prescriptive carry-forward for E4: see §6.6 ("Pre-register both bands at lock time").

<!-- cite: procurement-context-disambiguation/planning/predictions.md (post-2026-05-27 calibration block) for the worked example — which bands were locked for which predictions -->
<!-- cite: procurement-context-disambiguation/results/analysis.py disposition_methodology block (the rule_source / confirmation_band / falsification_band / note structure per prediction) as the analyst-judgment-disclosure pattern -->
<!-- cite: procurement-context-disambiguation/results/analysis_outputs.json disposition_methodology and disposition_table for the canonical 1-Confirmed / 3-Falsified / 2-Under-tested mix -->
<!-- cite: programme/PROCESS.md disposition vocabulary block (Under-tested as a positive disposition for under-specified gray zones, not a passive "inconclusive") -->

---

## 6 · The discipline carry-forwards

<!--
  Intent: this is the prescriptive section. Five patterns embedded in
  code with worked examples that any future application of
  Receipt-Anchored Evaluation should inherit. The reader after this
  section can author a new substrate's runner without re-deriving these
  patterns.

  Length target: ~2–3 pages.
-->

### 6.1 Per-record SHA distinctness lock-in test

<!-- Intent: the record-composition lock-in pattern. -->

- Every arm-handler PR includes a parametrized test asserting that two distinct records produce distinct rendered prompts containing their respective markers.
- Locked in repository as a wave-1 expectation; "simplifying" a renderer back to envelope-only trips the test.
- Discovered after a real smoke run cryptographically verified clean but signed empty-record receipts.

<!-- cite: procurement-context-disambiguation/runner/tests/test_handler_record_composition.py (parametrized across 7 arms) -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-28 PR #97 arc -->

### 6.2 Cross-record fingerprint sanity checks

<!-- Intent: catch the bug class above at the corpus level too. -->

- At run start and run end, compute distinct prompt-SHA-256 counts per arm; assert > 1 unique prompt-SHA per arm where records differ.
- Catches single-record degenerate runs (every record produced the same prompt) that the per-pair lock-in test misses if both pairs happen to share the same handler bug.

<!-- cite: pattern to be lifted into the runner's pre-flight diagnostic; not yet a named module -->

### 6.3 Worktree-isolation dispatch primitive

<!-- Intent: the Wave 2 lesson, now load-bearing for parallel-agent work. -->

- Any parallel-agent dispatch uses physically isolated working trees: `git worktree add /private/tmp/wt-<task-id> -b feat/<task-id> main` per agent.
- Shared-workspace parallel execution is opt-in and requires explicit justification.
- Worked example: E3 Wave 2 first dispatch had 7 agents racing on a single working tree; only 1 of 7 produced a clean commit. Re-dispatch under worktree isolation: 6 of 6 clean.

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-28 "Wave 2 close-out" §"Process lessons captured" item 1 -->
<!-- cite: programme/PROCESS.md gate #7 "Default isolation for parallel agent work" -->

### 6.4 Receipt-anchored cost projection pinning

<!-- Intent: cost projection as instrument validation. -->

- Pre-run smoke produces per-arm per-call cost; dry-run extrapolates to corpus scale; Phase 2 actual cost recomputes against the same baseline.
- The ±15% accuracy gate is one of five PASS conditions on a Phase 2 readiness sign-off; deviation triggers re-baselining before fire.
- Projection accuracy is itself evidence the runner is pinned correctly.

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 §"Five-gate sign-off" -->

### 6.5 Inter-coder reconciliation protocol

<!-- Intent: the two protocol variants E3 ran, each with a verbatim
     methods-section disclosure sentence. The two-variants observation
     itself is methodologically meaningful.
-->

- **Variant A — blind first pass + blind AI second-coder + reconciliation with rubric anchor** (used for `diagnostic_primary`). Human first-pass coder coded blind; AI second-coder coded blind; reconciler reviewed contested records with both calls visible alongside the rubric's default rule.
- **Variant B — AI-first + human review-and-adjudication** (used for `diagnostic_claude`). Agent coded blind; human reviewed all 100 records with the agent's call + rubric refresher visible per record; per-record `review_action` audit field (`agent-accepted` / `human-overridden`) captured.
- Variant choice depends on what fatigue vector dominates. Variant A is canonical multi-coder reconciliation; Variant B eliminates first-pass-categorisation-from-memory under cognitive load.
- Both variants produce per-record audit trails; the canonical sheet is auditable end-to-end.

<!-- cite: procurement-context-disambiguation/results/rubric_inter_coder_analysis_primary.md for the verbatim Variant A disclosure sentence -->
<!-- cite: procurement-context-disambiguation/results/rubric_inter_coder_analysis_claude.md for the verbatim Variant B disclosure sentence -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-06-07 entry §"Why the protocol differed between arms (honest disclosure for the methods section)" -->

### 6.6 Pre-register both bands at lock time

<!--
  Intent: the prescriptive fix lifted from the §5.6 observation.
  Every prediction in a future application of Receipt-Anchored
  Evaluation should pre-register BOTH a confirmation band AND an
  explicit falsification band, with the gray zone between them
  mapped explicitly to Under-tested. Multi-axis predictions get
  axis-specific hypotheses with axis-specific bands.
-->

- Every prediction pre-registers (a) a confirmation band, (b) an explicit falsification band, and (c) the gray zone between them mapped to Under-tested. No prediction ships with confirmation-only specification — the falsification clause is part of the lock contract.
- For cross-axis comparisons (e.g. |A − B| gaps), both the confirmation magnitude and the falsification magnitude are numeric. The gray zone is the explicit Under-tested band, locked at the same tag as the confirmation band.
- For robustness-at-scale claims (e.g. ≥ X% floor), pre-register the falsification floor explicitly — "anything below X% is Under-tested" is not equivalent to "anything below X% is Falsified" and the lock must pick one.
- Multi-axis predictions decompose into axis-specific hypotheses at lock time. Cross-model arms that collect data on multiple axes (verdict + rubric) get one hypothesis per axis, each with its own bands.
- The analysis script discloses `rule_source` per prediction as a machine-checked invariant — `"locked"` when the disposition follows pre-registered bands; explicit script-time judgment is disallowed by the lock contract under this carry-forward.

<!-- cite: procurement-context-disambiguation/planning/predictions.md — current state showing which predictions locked both bands and which did not; the prescription removes the latter pattern for E4 -->
<!-- cite: procurement-context-disambiguation/results/analysis.py disposition_methodology block — the rule_source / confirmation_band / falsification_band structure to lift into every future runner's analysis layer -->
<!-- cite: §5.6 of this note for the worked example -->

### 6.7 D-series behavioural taxonomy as a cross-experiment register

<!--
  Intent: name the D-series as a discipline carry-forward in its own
  right, alongside receipt-anchored signing, locked-prompt SHAs,
  pre-registered predictions, anti-claims, and F-series. E2 Appendix C
  established D1–D9 as named axes; E3 inherits them and operationalises
  D4 as the hand-coded three-category rubric. Future experiments add new
  D-axes at experiment-level as the corpus reveals them, not retrofitted
  post-hoc. The register is what makes cross-experiment continuity
  machine-checkable.
-->

- Named axes spanning experiments. E2 Appendix C established D1–D9 (D1 Ambiguity handling, D2 Escalation behaviour, D3 Policy obedience, D4 Policy resistance, D5 Evidence sensitivity, D6 Precedent sensitivity, D7 Uncertainty acknowledgement, D8 Governance-context susceptibility, D9 reserved). E3 inherits the same D-numbers under the same definitions; cross-experiment comparison is by axis, not by ad-hoc metric.
- D4 (Policy resistance) is the worked example. E2 measured D4 lexicon-strict against the 14-record Permuted-Policy diagnostic (0/14 contradiction-naming fires); E3 hand-coded D4 as the three-category Cat 1 / Cat 2 / Cat 3 rubric on the n=100 Permuted-Policy diagnostic subset — the same axis, sharper instrument. The Cat 1/2/3 rubric was deferred from E2 Appendix C as the planned refinement and locked at E3's `v0.3-predictions-locked` tag.
- New D-axes get added at experiment-level as the corpus reveals them. E2 introduced D8 (Governance-context susceptibility) as a cumulative cross-axis aggregate after the L3 break surfaced; E3 may introduce additional axes around cross-model verdict-style divergence pending Phase 3 analysis. New axes get a number and a definition before they are measured, not after.
- The trilogy commits to D-series as the cross-experiment behavioural-taxonomy register. Future applications of Receipt-Anchored Evaluation inherit the D-numbers and their definitions; substrate transfer (banking KYC, complaints, credit per §7.2) introduces domain-specific D-axes alongside the inherited ones rather than renumbering.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md Appendix C "Behavioural taxonomy v1.1 reference" for the D1–D9 enumeration -->
<!-- cite: procurement-context-gradient/planning/behavioural_taxonomy.md §1.5 (v1.1 restraint amendment) for the lock-time taxonomy contract -->
<!-- cite: procurement-context-disambiguation/planning/predictions.md for the locked Cat 1/2/3 rubric protocol that operationalises D4 in E3 -->
<!-- cite: §3.4 of this note (Register 3) for the discipline-register definition -->

---

## 7 · Open questions / future work

<!--
  Intent: the forward-looking section. Three specific next-experiment
  shapes named, each scoped to the question it would answer. Avoid
  open-ended futurism — each item is a concrete next experiment that
  would extend Receipt-Anchored Evaluation in a load-bearing direction.

  Length target: ~1–2 pages.
-->

### 7.1 E4 — operational receipt-as-memory agent (design-partner shape)

<!-- Intent: the agent that consumes receipts as its working memory. -->

- E1–E3 measure an agent receiving structured context. E4 inverts: an agent uses signed receipts from prior decisions as its retrieval substrate, with cryptographic provenance per evidence item.
- Open question: does receipt-anchored evidence change the agent's calibration on contested decisions (the "this decision is similar to receipt X with verdict DENY, here is the SET" loop)?
- Design-partner shape: a regulated firm with a closed decision corpus and a willingness to ship receipts as the working substrate for agent-assisted review.

### 7.2 Cross-domain substrate transfer

<!--
  Intent: the methodology has been stress-tested on UK procurement. The
  next question is whether the discipline transfers to substrates with
  different evidential structures.
-->

- **Banking — KYC/AML.** Sanctions screening, transaction monitoring, suspicious-activity reporting. Substrate is privately held but field-provenance envelopes apply identically.
- **Banking — credit.** Lending decisions against affordability frameworks. Discrimination concerns make signed provenance particularly load-bearing.
- **Banking — complaints.** Complaint-handling decisions against FCA/CONC frameworks. Reasoning text drift across complaint categories is the analogue to E3's inversion-blindness measurement.

<!-- cite: methodology/README.md "Reuse" section for the public-vs-client repo separation pattern -->

### 7.3 Multi-step reasoning under receipt-anchored evidence

<!--
  Intent: E1–E3 measure single-decision reasoning. The next axis is
  multi-step — an agent that takes 3+ steps to reach a decision, where
  each step's evidence is receipt-anchored.
-->

- Open question: does step-by-step receipt anchoring change reasoning drift compared to single-shot reasoning? E3 measured one-shot rule application against inverted policy text. A multi-step variant would test whether the agent catches the inversion on step 2 after committing on step 1.
- Methods extension required: receipt-bundle semantics for multi-step traces, per-step Rekor anchoring vs trace-level anchoring trade-off.

---

## 8 · References

<!--
  Intent: numbered references mapped to inline reference markers in the
  body. Each external citation carries arXiv ID / DOI / URL.
  Pre-registration tags and commit hashes are first-class references.

  Length: as long as needed. Likely 12–20 entries.
-->

### 8.1 Programme publications

1. _MRP-2026-02 — "When AI hedges and policy commits."_ Carter, S. (2026). Published 2026-05-18. DOI: pending. Pre-registration tag: `v0.1-predictions-locked` at commit `bd7a795`. <!-- cite: procurement-decisions/writeup/main.md frontmatter -->
2. _MRP-2026-03 — "Procurement context gradient."_ Carter, S. (2026). Published 2026-05-27. DOI: pending. Pre-registration tag: `v0.2-predictions-locked`. <!-- cite: procurement-context-gradient/README.md frontmatter once writeup lands -->
3. _MRP-2026-04 — "Precedents, policy, and commitment" (forthcoming)._ Carter, S. (2026). Pre-registration tag: `v0.3-predictions-locked`. <!-- cite: procurement-context-disambiguation/planning/predictions.md lock convention -->

### 8.2 Programme working documents

4. _Receipt-Anchored Evaluation reference._ [`../methodology/README.md`](./README.md). <!-- cite: methodology/README.md -->
5. _Programme process — research methodology spec._ [`../programme/PROCESS.md`](../programme/PROCESS.md).
6. _Structural-parity checklist._ [`../programme/STRUCTURAL-PARITY.md`](../programme/STRUCTURAL-PARITY.md).

### 8.3 Infrastructure references

7. Sigstore Rekor transparency log. <https://docs.sigstore.dev/logging/overview/>.
8. DSSE envelope specification (in-toto). <https://github.com/secure-systems-lab/dsse>.
9. Ed25519 signature scheme (RFC 8032). <https://datatracker.ietf.org/doc/html/rfc8032>.
10. MeshQu offline receipt verifier. <https://verify.meshqu.com>.

### 8.4 Regulatory anchors

<!--
  Intent: the regulatory anchors lifted from E1 §1 + E2 §1 framing.
  Verify each per programme/PROCESS.md gate #9 before promoting to
  status:STABLE.
-->

11. UK Procurement Policy Notice 02/24 (May 2024). LLM-generated bid content. <!-- cite: procurement-decisions/writeup/main.md §1 verbatim -->
12. UK Procurement Policy Notice 017 (2025). AI-augmented contract decisions.
13. UK Government AI Playbook (February 2025). Meaningful human control principle.
14. EU AI Act, high-risk provisions on automated decision-making.
15. SEC examination priorities on AI in investment advice.

### 8.5 Methodological precedent

<!--
  Intent: precedents from clinical trials + evaluation methodology that
  Receipt-Anchored Evaluation borrows from. Verify each per gate #9
  before promoting.
-->

16. _Pre-registration in clinical trials_ — ClinicalTrials.gov pre-registration discipline as direct precedent.
17. _Cohen's κ_ — Cohen, J. (1960). A coefficient of agreement for nominal scales. <!-- cite: Educational and Psychological Measurement, 20(1), 37–46 -->
18. _Landis & Koch κ interpretation bands_ — Landis & Koch (1977). <!-- cite: Biometrics, 33(1), 159–174 -->
19. _Inspect AI evaluation framework_ — UK AISI. <https://inspect.ai-safety-institute.org.uk/>. <!-- cite: procurement-decisions/writeup/main.md §2 acknowledges Inspect AI patterns -->

---

## 9 · License + verifiable artefacts

<!--
  Intent: the closing section that lands the load-bearing claim — every
  receipt in the programme is verifiable without trusting MeshQu. The
  reproducibility statement is the integrity primitive at publication
  time.

  Length target: ~1 page.
-->

### 9.1 The verifiability claim

> **Every receipt in the programme is verifiable against the public Sigstore Rekor log without trusting MeshQu.**

- The verification path: download the bundle → check the Ed25519 signature against the published kid → check the Rekor inclusion proof → recompute the canonical-JSON hash → confirm it matches the signed payload.
- No MeshQu API credentials are required at any step.
- The verifier at [verify.meshqu.com](https://verify.meshqu.com) is a separate code path from the production signer; the offline verifier re-implements the SET independently.

<!-- cite: methodology/README.md "Why it holds up" section -->
<!-- cite: tradequ memory project_meshqu_positioning entry for the per-decision Rekor anchoring discovery (PR #489) -->

### 9.2 Reproducibility statement

<!-- Intent: the operational instructions for re-deriving every headline
     number in the trilogy from on-disk artefacts. -->

- Each experiment's `results/runs/<run-id>/` directory contains: canonical receipts (one JSON per decision), the run manifest (model id, temperature, prompt SHA-256, policy snapshot SHA-256, runner commit, kid, tenant ID), the observability captures (run-start + run-end PNGs), and the verifier output (`verifier.txt`).
- Each writeup's headline numbers are re-derivable by running the published analysis notebooks against the on-disk bundles. No live API calls are required.
- The reproducibility check: clone the repo, check out the writeup's tag, run the notebook against the on-disk run directory, compare the produced numbers to the writeup's tables.

<!-- cite: programme/STRUCTURAL-PARITY.md Appendix D "Reproducibility instructions" requirements -->

### 9.3 License

<!-- Intent: the license under which the methodology and the corpora are released. -->

- Methodology + writeups: CC BY 4.0.
- Code (runners, verifiers, analysis notebooks): MIT.
- Corpora: published as-is from the underlying public substrate (UK Contracts Finder OCDS); subject to the substrate's own publication terms.
- Receipts: signed under the experiment kid `meshqu-experiment-procurement-2026-05`; the signing key is dedicated to the experiment and not used for production tenants.

<!-- cite: ../LICENSE for the repo-level license -->

---

<!--
  ---  END SCAFFOLD  ---

  Authoring checklist before promoting status from SCAFFOLD to DRAFT:

    [ ] §1 abstract written (~250–400 words, ends with one-sentence anti-claim)
    [ ] §2 receipt primitive expanded with one worked-example receipt JSON snippet
    [ ] §3 disposition vocabulary expanded with one falsified + one confirmed worked example
    [ ] §4.1 / 4.2 / 4.3 each carry their headline disposition table (per STRUCTURAL-PARITY §3)
    [ ] §5 each sub-section carries its worked example as a callout, not a footnote
    [ ] §6 each carry-forward names the file path where the pattern lives in code
    [ ] §7 each future-work item is concrete enough to scope at one paragraph
    [ ] §8 references verified per programme/PROCESS.md gate #9 (citation verification)
    [ ] §9 reproducibility statement carries the no-credentials-needed claim verbatim

  Authoring checklist before promoting status from DRAFT to STABLE:

    [ ] Pass through programme/STRUCTURAL-PARITY.md voice conventions
    [ ] AI-assistance declaration added (per PROCESS.md gate #10)
    [ ] Independent reader feedback folded in (best-effort, per gate #11)
    [ ] DOI minted; bind into §8.1 entries
    [ ] Frontmatter status flipped to STABLE; commit_hash + corpus references pinned
-->
