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
    - Honesty about falsifications is the strength. E3's "4 of 6 predictions
      falsified" is the load-bearing example, not a footnote.
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
      E3 had 4 of 6 pre-registered predictions falsified, productively
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
- Falsification criteria are numeric and segment-specific. Each prediction states (a) the band that confirms, (b) the band that falsifies, and (c) the interpretive note bound to each direction.
- The lock is the integrity primitive that converts "we observed X" into "we predicted X-or-not-X, and the corpus showed which".

<!-- cite: procurement-context-disambiguation/planning/predictions.md for the worked example of segment-level prediction with explicit falsification bands -->
<!-- cite: programme/PROCESS.md gate #1 "Brief verifies current state before pinning anchors" + gate #8 "Title commitment at the pre-registration lock" -->

### 3.2 The disposition vocabulary

<!--
  Intent: name the six dispositions as a closed vocabulary. The vocabulary
  is the contract — it forces honest reporting because no "partial
  confirmation" escape valve exists.
-->

- **Confirmed** — the corpus produced a value inside the confirmation band.
- **Falsified** — the corpus produced a value inside the falsification band.
- **Inverted** — the corpus produced a value in the opposite direction to the prediction (a sharper form of falsification; the signal exists but ran the other way).
- **Refuted** — the corpus produced a value that rules out the prediction's underlying mechanism.
- **Deferred** — measurement instrument inadequate; the prediction is unresolved on this experiment.
- **Under-tested** — sample size or design did not permit a disposition; not a passive "inconclusive".

<!-- cite: procurement-context-disambiguation/planning/predictions.md §"Definition of 'report honestly'" for the locked vocabulary contract -->
<!-- cite: programme/PROCESS.md "Honest falsification" paragraph for the no-post-hoc-smoothing principle -->

### 3.3 Why this matters: confirmation-bias reduction + honest measurement

<!-- Intent: name the specific bias the discipline is engineered against. -->

- Without pre-registration, post-hoc smoothing is the path of least resistance: a falsified prediction becomes "partially confirmed" or "broadly directional". The disposition vocabulary cuts off that path by construction.
- Without numeric falsification bands, any result can be reframed as supporting the hypothesis. Numeric bands fix the goalposts before the corpus arrives.
- Without SHA-binding of prompts and policy snapshot, the experiment is not replayable — predictions and evidence drift apart in the time between lock and report.

<!-- cite: programme/PROCESS.md "Discipline is the contribution" framing -->

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
  findings into attributions. 4 of 6 predictions were falsified
  (P2, P3, P4, P6); 2 confirmed (P1, P5). This is the load-bearing
  example for the "pre-registration catches the surprising mechanism"
  observation in §5.
-->

- Substrate: identical 283-record corpus + a locked 100-record diagnostic subset.
- Design: three L3 decomposition arms (precedents-only, precedents-no-verdict, density-control); one L4-without-nudge arm; two scaled Permuted-Policy diagnostic arms (primary GPT-5.4 + cross-model Opus 4.7).
- Corpus collection: 1,332 signed receipts across six arms; 80 min 33 s wall-clock; $25.23 actual vs $25.21 projected (within 0.4% on all six arms).
- Headlines:
  - **Accumulation drives commitment**, not raw volume. Arm A (precedents-only) commits 15.5%; Arm B (no verdicts) 3.2%; Arm C (density-control) 4.6%. P1 confirmed directionally; the full E2 ladder amplifies the precedent signal.
  - **Policy text drives backoff**, not the anti-sycophancy nudge. L4-without-nudge commits MORE than Arm A (27.2% vs 15.5%) — the L3→L4 backoff E2 observed did not re-emerge without the nudge in the expected direction. P3 falsified.
  - **88% inversion-blindness at scale**, cross-model. On the n=100 Permuted-Policy subset, both GPT-5.4 (93% rubric Cat 2) and Opus 4.7 (100% rubric Cat 2) predominantly apply the rule's intent rather than its inverted text. P5 confirmed on both arms.
- Lock anchor: `v0.3-predictions-locked`.
- Status: writeup in progress (Phase 3).

<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-05-29 entry "Phase 2 complete: 1,332 receipts, all five gates PASS, $25.23" -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-06-07 entries (×2) for Phase 2.5 rubric outcomes (P5 Confirmed both arms) -->
<!-- cite: procurement-context-disambiguation/planning/predictions.md for the full P1–P6 spec -->

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
  Intent: E3 had 4 of 6 predictions falsified — productively. The point
  is that the falsifications are where the experiment paid off, not
  where it failed. Without the lock, the falsified predictions would
  have been quietly reshaped into post-hoc confirmations.
-->

- P3 (anti-sycophancy nudge load-bearing) was falsified in the opposite direction. The hypothesis was that removing the nudge would reduce backoff; instead, L4-without-nudge committed MORE than Arm A, and the backoff direction itself was confounded.
- P4 (inversion-blindness reproduces at scale) was over-fulfilled: the prediction set the floor at 90%, the corpus produced 93–100% depending on rubric axis. The lock catches the over-fulfilment as evidence of architectural property, not as "we got lucky".
- The two confirmed predictions (P1, P5) carry more weight precisely because they sit alongside four falsifications in the same writeup — the methodology is not selecting for results.

<!-- cite: procurement-context-disambiguation/planning/predictions.md for the P1–P6 falsification bands -->
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
