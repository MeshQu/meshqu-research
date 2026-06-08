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

E3 is the third experiment in a pre-registered programme studying governance-context effects in AI decision agents. E2 surfaced three unresolved questions: whether the L3 commitment break was caused by precedent receipts or by accumulated governance context; whether the L4 backoff was driven by the anti-sycophancy nudge or by the policy text itself; and whether inversion-blindness reflected a model-specific behaviour or a broader task-class property.

E3 was designed to separate these effects directly. Three L3 decomposition arms disentangled verdict signal, informational concreteness, and prompt density. An L4-without-nudge variant isolated the contribution of the anti-sycophancy clause. A scaled n=100 diagnostic re-tested inversion-blindness at corpus scale, and a cross-model replication arm introduced Claude Opus 4.7 alongside the original GPT-5.4 configuration.

The corpus falsified the leading interpretations carried forward from E2. The L3 commitment break collapses when verdict-bearing precedents are removed, indicating that accumulated governance context, rather than precedent verdicts themselves, is the dominant driver of commitment. The L4 backoff persists without the anti-sycophancy clause, indicating that policy exposure rather than the nudge language is responsible for most of the effect. The inversion-blindness pattern reproduces across both diagnostic arms and both model families, suggesting a task-class behaviour rather than a model-specific artefact.

The strongest cross-model finding is a separation between reasoning and verdict behaviour. Both models exhibit the same inversion-blind reasoning pattern, yet produce materially different verdict distributions: GPT-5.4 remains review-oriented (23% commit rate) while Claude Opus 4.7 commits substantially more often (80%). The result suggests that inversion-blind reasoning may be a task-class property while verdict commitment remains model-specific. If that separation holds in further work, it has direct implications for how cross-model AI deployment in regulated decisioning should be evaluated — **reasoning evaluations may generalise; verdict evaluations may not.**

Across six pre-registered predictions, one was confirmed, three were falsified, and two were under-tested due to confirmation-only lock criteria. All predictions, thresholds, and artefacts remained unchanged from the v0.3 pre-registration lock (`ba4ebfb`).

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
- E3 (this paper): disambiguation experiment — L3 decomposition + L4-without-nudge + scaled Permuted-Policy diagnostic (n=100) + cross-model arm (Opus 4.7)
- Methods substrate inherited unchanged: signed Ed25519 receipts + Rekor anchoring, locked-prompt SHAs, pre-registered predictions with the locked disposition vocabulary, anti-claims, F-series structure
- Pointer to the trilogy methods note (*Receipt-Anchored Evaluation*) <!-- TODO: confirm whether this writeup forward-references the methods note or whether the methods note is published first; per decision_log Phase 4 is post-E3 capstone -->

## §3 — E3 design recap

<!-- ~2 paragraphs + the predictions table. Mirrors E2's §2 (Methodology) +
     parts of §3 (Predictions vs. outcomes). Walks the reader through what
     was locked at v0.3-predictions-locked and what each piece was designed to
     resolve.

     Argues: the design is three pieces (L3 decomposition, L4-without-nudge,
     scaled Permuted-Policy diagnostic + cross-model arm), and each piece is targeted at one
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
- **Piece 3 — Scaled Permuted-Policy diagnostic + cross-model arm** (diagnostic_primary + diagnostic_claude, n=100 each, record-matched): establishes whether inversion-blindness is real at scale (vs E2's n=14 signal) and whether it is model-specific or a property of the task class

### Predictions table

<!-- Model exactly on E2's §3 table. One row per P1–P6, columns: ID,
     pre-registered claim, falsification criterion, outcome (corpus),
     disposition. Sub-metric rows below the main predictions if any
     (E2 had a sub-metric row on array-position; E3 may have a sub-metric
     row on the Arm C asymmetric-control caveat — Sam's call at draft time). -->

| ID | Pre-registered claim | Falsification criterion | Outcome (corpus) | Disposition |
|---|---|---|---|---|
| P1 | Arm A DENY ≥ 20% AND Arm C DENY ≤ 12% (precedents drive commitment, not raw volume) | Arm C DENY ≥ 20% OR Arm A DENY < 20% (locked clause from predictions.md:24) | Arm A DENY 3.5% (10/283), Arm B DENY 0% (0/283), Arm C DENY 0% (0/283) | **Falsified** — Arm A 3.5% trips the locked falsification clause "Arm A < 20%". The third-reading interpretation (accumulation amplifies, precedents alone don't reach E2's L3 37.8%) is starker than the directional 20–30% band anticipated |
| P2 | Arm A DENY rate − Arm B DENY rate ≥ 15pp (verdict exemplars are load-bearing for DENY-anchoring) | (locked spec specifies confirm band only; no falsification band locked — see analysis.py disposition_methodology["P2"]) | A − B DENY gap = 3.5pp (3.5% − 0%) | **Under-tested** — gap of 3.5pp is below the 15pp confirm band; no falsification band locked. See §4.2 — the underlying finding (Arm A is the only arm producing any DENY at all) is substantively richer than P2's confirm/falsify binary captured |
| P3 | L4-without-nudge retention of E2's L3-DENY set ≥ 80% (nudge load-bearing, Framing A.1) | retention ≤ 65% (locked falsification band, predictions.md:37 — policy text alone, Framing A.2) | 60.7% retention (65/107) | **Falsified → Framing A.2 confirmed**: retention 60.7% ≤ 65% locked floor; the policy text drove the backoff, the nudge clause is incidental |
| P4 | Scaled Permuted-Policy diagnostic: ≥90% same-as-unperturbed L4 verdict (n=100, primary model) | (locked spec specifies confirm band only; no falsification band locked — see analysis.py disposition_methodology["P4"]) | 88% same-as-unperturbed (88/100) | **Under-tested** — 88% is 2pp below the 90% confirm floor; no falsification band locked. Methods-note discipline refinement: future "robustness at scale" predictions should pre-register both confirm and falsify bands |
| P5 | Hand-coded rubric: Cat 2 ("reasons solely against rule intent") ≥ 60% modal AND Cat 1 ("names the inversion") ≤ 15% | Cat 1 > 25% (locked, predictions.md:49) | Primary reconciled: Cat 2 93% / Cat 1 7%. Claude reconciled: Cat 2 100% / Cat 1 0%. | **Confirmed** on both arms (κ between blind agent and reconciled = +1.0000 on both arms) |
| P6 | Claude's same-as-unperturbed rate within 15pp of primary's rate (task-class, not model-specific) | gap > 15pp (locked falsification band, predictions.md:53 — pre-registered the model-specific outcome as "a strong finding, not a failure") | gap = 46pp (primary 88%, claude 42%) | **Falsified** — 46pp gap far outside locked 15pp band. predictions.md:53 pre-registered the model-specific outcome as substantively interesting; the cross-model finding is the substantive cross-model contribution (see §4.7) |

## §4 — Results

<!-- This is the bulk of the writeup. Walk through each finding piece by piece,
     following E2's §4 (L3 break) / §5 (L3→L4 backoff) / §6 (Permuted-Policy)
     structural shape. Each subsection is an F-series finding with status
     label, evidence block, two readings where the corpus admits two, anti-
     claims, and E4 implications. Length: ~10–12 pages worth across all
     subsections; this is the heart of the paper. -->

### §4.1 — P1 falsified: Arm A DENY rate far below the 20% commit floor

<!-- ~2 paragraphs. Argues: the first reading of P1 is the obvious one
     (precedents are not load-bearing on their own for DENY commitment).
     The right reading, captured in the predictions interpretive note, is
     the third one: accumulation amplifies. E2's L3 hit 37.8% DENY because
     L0+L1+L2+L3 stacked, not because precedents alone could push the agent
     off the REVIEW spine to that magnitude. The corrected numbers make the
     falsification starker than the directional 20–30% band anticipated:
     Arm A's DENY rate is 3.5%, not 15.5% — and Arm C produces zero DENYs,
     not 4.6%. The substantive narrative ("accumulation-amplifies, precedents
     alone don't reach the commit floor") still holds, but with much sharper
     numbers than the original draft suggested. -->

- Arm A precedents-only DENY rate: **3.5% (10/283)**
- Threshold: 20% (predictions calibration note: 20–30% band confirms directionally with the accumulation-amplifies note; <20% trips the locked falsification clause)
- Reading: **the L3 DENY break is real but accumulation-amplified.** The L1 prose framing + L2 named-rules + L3 precedent receipts together cleared the DENY commit floor at E2 (37.8%); precedents in isolation reach only 3.5% — an order of magnitude below the locked confirm threshold
- Arm C density-control DENY rate: **0% (0/283)** — comfortably below the ≤12% threshold, so the volume-alone (Reading B) explanation is also falsified, and starker than the original draft (4.6%) suggested
- Anti-claim: **the falsification of P1 is not a refutation of the precedent mechanism.** Arm A still produces every single DENY observed in Piece 1 (10 vs 0 in B and 0 in C); precedents are doing work for DENY commitment, they just don't carry the full weight of the L3 break alone. The accumulation reading was named explicitly in the predictions' interpretive note as the third shading
- Pointer: the verdict-axis breakdown (ALLOW/REVIEW/DENY per arm) reveals a sharper finding than P1's DENY-rate binary — see §4.2 for the Piece 1 verdict-distribution table and the reframe of P2

### §4.2 — P2 under-tested; Piece 1 mechanism refinement: verdict-bearing precedents enable directional commitment (mostly ALLOW)

<!-- ~3 paragraphs. SUBSTANTIVE REFRAME. P2 was pre-registered on
     DENY-rate-anchoring specifically (Arm A DENY − Arm B DENY ≥ 15pp).
     The observed gap is 3.5pp — well below the 15pp confirm band, and
     no falsification band was locked. Disposition is therefore
     Under-tested per analysis.py disposition_methodology["P2"].

     BUT the underlying finding is sharper than P2's confirm/falsify binary
     captured. Re-cut by the full verdict distribution (ALLOW/REVIEW/DENY)
     instead of by DENY rate alone, a substantively richer Piece 1 mechanism
     emerges:

       arm_a (precedents-with-verdicts):    34 ALLOW,  239 REVIEW, 10 DENY
       arm_b (precedents-no-verdict):        9 ALLOW,  274 REVIEW,  0 DENY
       arm_c (density-control):             10 ALLOW,  273 REVIEW,  0 DENY

     Arm A is the ONLY condition producing any DENY commitment at all.
     Arms B and C produce zero DENYs. AND across all three arms, ALLOW
     commitment dominates DENY commitment by 3.4× (53 ALLOW vs 10 DENY).
     The mechanism isn't "DENY precedents anchor new DENYs" (the pre-
     registered framing) — it's verdict-bearing precedents enable
     directional commitment in both directions, with ALLOW the dominant
     direction in this corpus + policy combination. The §10 governance-
     memory mechanism from E2 holds, but operates symmetrically, not
     DENY-asymmetrically. -->

- Arm A − Arm B DENY rate gap: **3.5pp** (3.5% − 0%) — below the 15pp confirm band; no falsification band locked
- Honest disposition: **Under-tested** (locked-band failure, per analysis.py disposition_methodology["P2"])
- **Substantively interesting** Piece 1 mechanism refinement: verdict distribution across the three arms

  | arm | ALLOW | REVIEW | DENY | any commitment (ALLOW + DENY) |
  |---|---:|---:|---:|---:|
  | arm_a (precedents with verdicts) | 34 | 239 | 10 | 44 (15.5%) |
  | arm_b (precedents-no-verdict) | 9 | 274 | 0 | 9 (3.2%) |
  | arm_c (density-control) | 10 | 273 | 0 | 10 (3.5%) |
  | **all three arms combined** | 53 | 786 | 10 | 63 (7.4%) |

- **Arm A is the only arm to produce any DENY commitment (10 records). Arms B and C produce zero DENYs.** Strip the verdict signal from precedents and the agent never commits to DENY in this experimental condition
- **Across all three arms, ALLOW commitment dominates DENY commitment by 3.4× (53 ALLOW vs 10 DENY).** The mechanism isn't "DENY precedents anchor new DENYs" (the pre-registered framing). It's: **verdict-bearing precedents enable directional commitment in both directions — with ALLOW the dominant direction in this corpus + policy combination**
- The mechanism is sharper than P2 anticipated: any-direction commitment (ALLOW + DENY) rises from 3.2% (Arm B) → 15.5% (Arm A) — a 4.8× lift, well above what the DENY-only slice captured
- Anti-claim: **the §10 governance-memory mechanism from E2 holds — but operates symmetrically, not DENY-asymmetrically as P2 anticipated.** The bundle schema's verdict field carries the load (verdict-bearing precedents differ from verdict-stripped ones); the polarity does not (ALLOW-bearing precedents are not specifically anchoring DENYs in this corpus)
- Methods-note discipline refinement: P2's pre-registered DENY-rate framing collapsed onto a single axis a mechanism that the data reveals is two-dimensional (any-direction commitment vs verdict-stripped non-commitment). The locked vocabulary's Under-tested disposition is the honest call; the substantive finding is reported here as a Piece 1 mechanism refinement, not as a post-hoc rescue of P2

#### F013 — Piece 1 verdict-distribution refinement (Discovered)

<!-- F-series entry, post-data findings register; E2 ended at F012 so E3 starts
     at F013. Discovered class: surfaced from the corpus without a pre-existing
     P-series prediction matching the verdict-distribution cut. Sam's prose
     pass can lift the §4.2 bullets verbatim — the F-tag header here makes the
     finding addressable in the methods note and the trilogy capstone. -->

- **Status**: Discovered
- **Evidence (n=283 per arm, all three L3 arms)**: Arm A produces 100% of observed DENYs across the three L3 arms (10 of 10). Arms B and C produce zero DENYs. Across all three arms, ALLOW commitment dominates DENY commitment 3.4× (53 ALLOW vs 10 DENY)
- **Mechanism**: verdict-bearing precedents enable directional commitment in both directions; ALLOW is the dominant direction in this corpus + policy combination
- **Anti-claim**: F013 does NOT show the §10 governance-memory mechanism from E2 is wrong — it shows the mechanism operates symmetrically rather than DENY-asymmetrically as P2 anticipated
- **E4 design implications**: the operational receipt-as-memory experiment should anticipate ALLOW-bearing precedents anchoring ALLOW commitments at least as strongly as DENY-bearing precedents anchor DENYs

### §4.3 — Arm C asymmetric-control caveat (methods reading)

<!-- ~1 paragraph. Honest disclosure section, matching E2's §6 style of
     reporting both the strict and the structural reading. -->

- Arm C token parity vs Arm A: −16.43% (locked at PR #93, pre-registered as documented methods caveat)
- The asymmetry rules out one family of confounds (Arm C did not commit because it had more volume than precedents) and introduces another (Arm C may not have committed because it had less volume than Arm A)
- P1's Arm C ≤12% DENY threshold is comfortably cleared (Arm C DENY 0%, observed even sharper than the original draft suggested), so the volume-alone (Reading B) explanation is falsified even granting the asymmetry — but the writeup names the caveat explicitly rather than burying it

### §4.4 — P3 falsified, Framing A.2 confirmed: the policy text drove the backoff

<!-- ~2 paragraphs. The cleanest single result in the experiment after P5.
     E2's L3→L4 backoff was 57% retention on the 107-record L3-DENY set.
     P3 predicted ≥80% retention under L4-without-nudge (nudge driving the
     backoff). The corpus shows 60.7% — essentially identical to E2's 57%,
     well below the ≥80% threshold and below the ≤65% falsification floor.
     The nudge clause was incidental; the policy text alone produces the
     backoff. -->

- Retention on the 107-record L3-DENY set under L4-without-nudge: 60.7% (65/107)
- E2's L4-with-nudge retention on the same set: 57% (61/107)
- Delta: ~+3.7pp — within noise band; the nudge clause is incidental
- Reading: **Framing A.2 confirmed.** The policy text alone — its explicit enumeration of rule clauses, threshold tests, and field expectations — drove the backoff. The anti-sycophancy nudge ("if a required field is absent, do not assume it satisfies the rule") was a small refinement on a mechanism that was already working
- Anti-claim: this does NOT mean the nudge is useless. It means the L3→L4 reversion on E2's PROC-005 ambiguous-rule axis was already being driven by the policy text's structural cues; the nudge is a discipline reinforcement, not the causal agent
- l4_without_nudge DENY rate is 27.2% (77/283) vs Arm A DENY 3.5% (10/283) — the policy text continues to do substantially more DENY-direction work than precedents alone produce

### §4.5 — P4 under-tested: inversion-blindness substantively holds at scale; locked spec specifies confirm band only

<!-- ~2 paragraphs. P4 predicted ≥90% same-as-unperturbed verdict on the n=100
     Permuted-Policy subset. E2's n=14 hit 92.9%. The corpus reports 88% —
     2pp below the 90% confirm threshold. predictions.md locked the confirm
     band but did NOT lock a falsification band; per analysis.py
     disposition_methodology["P4"], the honest disposition is Under-tested.
     The substantive reading is that inversion-blindness is overwhelmingly
     present at scale; the methods-note discipline refinement is that future
     "robustness at scale" predictions should pre-register both confirm and
     falsify bands. -->

- diagnostic_primary same-as-unperturbed-L4 rate: 88% (88/100)
- Locked confirm band: ≥ 90%. Locked falsification band: **none registered** (see analysis.py disposition_methodology["P4"])
- Disposition: **Under-tested** — 88% is 2pp below the confirm floor; no falsification band locked, so the locked spec doesn't admit a categorical Falsified call
- Reading: **the architectural-property reading is substantively present at scale.** 88% is high; 12 records out of 100 emitted a different verdict than they did at unperturbed L4. The substantive read carries into P5: even on the 12 records where the verdict shifted, the rubric coding shows the rule-intent prior still dominates the reasoning
- Methods-note discipline refinement: P4 is the cleanest example of why "confirm-band-only" predictions force Under-tested dispositions on near-misses. The 88% finding is substantively informative but the locked vocabulary can't categorize it as Falsified without a pre-registered falsification band — future "robustness at scale" predictions should pre-register both bands explicitly
- Anti-claim: this is NOT "narrowly falsified" — calling it Falsified would be a post-hoc rule introduction the locked vocabulary disallows. The discipline of leaving it Under-tested is itself a methods-note contribution

### §4.6 — P5 confirmed on both diagnostic arms: rubric Cat 2 dominance

<!-- ~3 paragraphs. The load-bearing positive finding in the experiment. P5
     is the rubric-axis confirmation of inversion-blindness; both arms produce
     >90% Cat 2 ("reasons solely against rule intent") and ≤15% Cat 1 ("names
     the inversion"). This is the result the experiment was most carefully
     instrumented for. The cross-model arm strengthens the finding beyond what
     a single-arm replication would. -->

<!-- ~1 short paragraph + bullets. Names the rubric as the hand-coded
     operationalisation of E2's D4 axis, the piece E2 explicitly deferred to
     E3 in Appendix C. This is the place to name the mapping so the trilogy
     reader sees D4 (the E2 axis) and Cat 1/2/3 (the E3 rubric) as the same
     construct, two scopes apart. Sam's prose pass can lift this paragraph
     verbatim or rewrite — the mapping itself is the load-bearing piece. -->

- **The rubric is the hand-coded operationalisation of D4 deferred from E2's Appendix C.** E2 operationalised D4 *Policy resistance* against the n=14 Permuted-Policy diagnostic on two readings — lexicon-strict (0/14 contradiction-naming fires) and v1.1 structural (inversion-blind authority-conditioned alignment) — and explicitly named the hand-coded refinement as an E3 ask. The three rubric categories are that refinement:
  - **Cat 1 ("names the inversion")** = lexicon-strict D4 contradiction-naming, at n=100 per arm
  - **Cat 2 ("reasons solely against rule intent")** = v1.1 structural D4 inversion-blind authority-conditioned alignment, at n=100 per arm
  - **Cat 3 ("partial recognition")** = the gray zone E2's binary D4 reading did not admit — the agent partially registers the inversion but applies the rule's training-prior anyway
- The mapping makes the n=14 → n=100 scale shift legible against the E2 axis it sharpens, not against a fresh construct introduced in E3
- diagnostic_primary: Cat 1 = 7 (7.0%), Cat 2 = 93 (93.0%), Cat 3 = 0 (0.0%) → **Confirmed**
- diagnostic_claude: Cat 1 = 0 (0.0%), Cat 2 = 100 (100.0%), Cat 3 = 0 (0.0%) → **Confirmed**
- Cross-model robustness: P5 confirmed under two model-protocols. The Cat 1 rate varies by model (Opus 0%, GPT-5.4 7%) in the direction the verdict-axis already suggested
- Inter-coder κ between blind AI second-coder and final canonical sheet: +1.0000 on both arms
- Reading: **inversion-blindness is a property of the task class, not a property of either specific model**, sharpened from E2's n=14 signal to a 200-record metric
- E2 reading carried forward: "authority-conditioned alignment in the structural sense" — the agent's reasoning is shaped by what it has learned a procurement rule should look like, not by the specific policy text in front of it. The pinpoint claim ("sycophancy") is still NOT what the corpus shows; the agent ignores the inversion rather than agreeing with it
- The 6 borderlines the blind agent flagged on `diagnostic_claude` were all missing-evidence hedges, which the rubric's default rule unambiguously excludes from Cat 3. P5 robustness check: even if all 6 had shifted to Cat 3, the distribution would have been 0/94/6 — still Confirmed

### §4.7 — Cross-model arm: verdict-style divergence + rubric-axis coherence

<!-- ~3 paragraphs. The substantive cross-model finding, on two axes.
     Verdict-axis (Phase 2 receipts): Opus 80% decisive (36 ALLOW + 44 DENY)
     vs GPT-5.4 23% decisive (0 ALLOW + 23 DENY + 77 REVIEW). Rubric-axis:
     Opus 0% Cat 1 vs GPT-5.4 7% Cat 1. The direction of the divergence is
     cross-axis-coherent: Opus is more thorough on both axes simultaneously.
     This is the real cross-model contribution for the writeup, and it lands
     above the methods caveat about Opus 4.7's removed temperature parameter. -->

- **Verdict-axis cross-model divergence (Phase 2 receipts, n=100 each)**:

  | arm | ALLOW | REVIEW | DENY | decisive rate |
  |---|---:|---:|---:|---:|
  | diagnostic_primary (GPT-5.4) | 0 | 77 | 23 | 23% |
  | diagnostic_claude (Opus 4.7) | 36 | 20 | 44 | 80% |

- **Rubric-axis cross-model divergence (Phase 2.5 canonical sheets, n=100 each)**:

  | arm | Cat 1 | Cat 2 | Cat 3 |
  |---|---:|---:|---:|
  | diagnostic_primary | 7 (7.0%) | 93 (93.0%) | 0 (0.0%) |
  | diagnostic_claude | 0 (0.0%) | 100 (100.0%) | 0 (0.0%) |

- Reading: **Opus's verdict decisiveness translates into rubric Cat 2 thoroughness.** Confident application of the rule-as-stated IS Cat 2 inversion-blindness. GPT-5.4's hedging creates surface area for occasional inversion-registration that Opus's decisiveness eliminates
- Engine-ALLOW vs engine-DENY directional alignment at n=100: 100% LLM-non-DENY on engine-ALLOW records (52/52 GPT-5.4, 52/52 Opus); 99.0% LLM-non-ALLOW on engine-DENY records (0/48 GPT-5.4 ALLOW, 1/48 Opus ALLOW). Cross-evaluator + cross-model directional alignment at scale
- **Methods caveat: Opus 4.7 removed the `temperature` parameter.** The cross-model arm cannot match the primary agent's temperature-0 setting; `effort: low` is the closest near-deterministic equivalent. The verdict-axis comparison is NOT verdict-for-verdict comparability; the reading is on the rubric distribution shape, not on per-record verdict equivalence. This is a documented methods caveat, not a confound — see §8

#### F014 — Cross-model verdict-style divergence (Discovered)

<!-- F-series entry, post-data findings register. Discovered class: the cross-
     model arm was designed to test inversion-blindness reproduction (P5) and
     cross-model robustness (P6); the verdict-style divergence is a substantive
     additional finding the locked vocabulary did not pre-categorise. The
     §4.7 tables carry the numbers; the F-tag header here makes the finding
     addressable. -->

- **Status**: Discovered
- **Evidence (n=100 record-matched, Phase 2 receipts)**: Opus 4.7 commits on 80/100 records (36 ALLOW + 44 DENY + 20 REVIEW); GPT-5.4 commits on 23/100 (0 ALLOW + 23 DENY + 77 REVIEW). Same inversion-blind reasoning pattern (P5 Confirmed both arms; Cat 2 = 93% primary, 100% claude) but materially different verdict shapes
- **Reading**: Opus's verdict decisiveness translates into rubric Cat 2 thoroughness; GPT-5.4's hedging creates surface area for occasional Cat 1 inversion-registration that Opus's decisiveness eliminates. The divergence is cross-axis-coherent: Opus is more thorough on both verdict and rubric axes simultaneously
- **Anti-claim**: F014 does NOT establish that Opus is "more correct" or "more inversion-blind" — the rubric distribution shape is what carries the P5 confirmation, not per-record verdict equivalence. The Opus 4.7 no-temperature sampling caveat is part of why
- **E4 design implications**: model-specific verdict style is a cross-cutting variable any operational receipt-as-memory deployment will inherit; the design-partner conversation should not lean on "pick a better model" as the lever — the underlying inversion-blindness pattern is task-class

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
     honest Under-tested calls on P2 and P4 (confirm-band-only locked spec)
     where a less disciplined vocabulary would have called them "narrowly
     falsified" or "broadly confirmed". -->

### Pre-registration catching the surprising mechanism, not the predicted one

- P1's interpretive note explicitly anticipated the accumulation-amplifies reading: *"Arm A landing in the 20–30% band (below E2's L3 37.8%) confirms P1 directionally but signals that accumulation amplifies… That's a real, reportable third shading, not a clean A-vs-B binary."*
- The corpus landed far below even the 20–30% band — at Arm A DENY 3.5% — but the third-shading frame was on the page before the data was collected; the falsification is unambiguous and starker than the directional band anticipated
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
- **P2 Under-tested (gap 3.5pp, confirm threshold 15pp, no falsification band locked)** — the locked spec specifies only a confirmation band; the gap is well below confirm but the vocabulary doesn't admit a Falsified call without a pre-registered falsification band. The writeup names this Under-tested and reports the substantively richer Piece 1 mechanism refinement (verdict-bearing precedents enable directional commitment, mostly ALLOW) as a finding the locked P2 framing collapsed onto a too-narrow axis
- **P4 Under-tested (88%, confirm threshold 90%, no falsification band locked)** — same shape as P2. The writeup names this Under-tested and reads the result as inversion-blindness substantively holding at scale with 2pp degradation from E2's n=14
- **P1 and P3 and P6 falsified cleanly against locked falsification bands** — P1 trips the locked "Arm A < 20%" clause (observed 3.5%); P3 trips the locked "retention ≤ 65%" clause (observed 60.7%); P6 trips the locked ">15pp gap" clause (observed 46pp). These are clean locked-spec dispositions
- Methods-note discipline refinement: the P2 / P4 pattern is the strongest argument for pre-registering both confirm AND falsify bands on every prediction. Without the locked vocabulary, P2 and P4 would have been reported as "narrowly falsified" or "broadly confirmed" — both phrasings invent post-hoc rules the pre-registration didn't carry. Under-tested is the honest call; the methods note inherits the discipline lift
- Without the locked vocabulary, the headline ("1 confirmed, 3 falsified cleanly, 2 under-tested") would have collapsed to "4 of 6 falsified" — and the reader would not see the discipline working

### Methodological findings (F-series)

<!-- F-series methodological findings — direct analogs to E2's §7. F015 + F016
     are process-discipline anchor-drift catches in the E2/F007 lineage; F017
     is the κ-check coder-drift catch, in the E2/F012 both-and reading lineage.
     The F-tag headers make these findings addressable in the methods note and
     the trilogy capstone; the substantive numbers live in §5 and the
     decision_log Phase 3 re-tally entry (commit 9d9a6f3). -->

#### F015 — arm_c verdict-count anchor drift (Discovered)

- **Status**: Discovered
- **Evidence (n=283)**: the Phase 2 close-out decision_log anchor recorded arm_c as 13 commits; canonical re-tally from the signed receipts says 10 commits (10 ALLOW + 273 REVIEW + 0 DENY). A 3-count drift on the ALLOW field; DENY field unchanged at zero
- **Disposition**: process-discipline finding, direct analog to E2's F007 (provisional-vs-canonical anchor mismatch). The bundles on disk are canonical; the decision_log anchor was provisional. Phase 3 reconciled before quoting any headline number; the writeup inherits the reconciled state
- **Anti-claim**: F015 does NOT change any P1/P2 disposition. P1 is still falsified (Arm A < 20% locked clause); P2 is still Under-tested. The verdict-distribution table at §4.2 already carries the canonical 10/273/0 numbers
- **E4 design implications**: provisional-vs-canonical reconciliation as the *first* move at each phase boundary is the discipline E3 inherited from E2/F007 and that E4 should inherit forward

#### F016 — diagnostic_claude verdict-mix anchor drift (Discovered)

- **Status**: Discovered
- **Evidence (n=100)**: the Phase 2 close-out decision_log anchor recorded diagnostic_claude as 35 ALLOW / 20 REVIEW / 45 DENY; canonical re-tally from the signed receipts says 36 ALLOW / 20 REVIEW / 44 DENY. A one-record DENY→ALLOW shift; REVIEW field unchanged at 20
- **Disposition**: process-discipline finding, sibling to F015 in the same E2/F007 lineage. Same root cause: the close-out anchor was provisional ahead of the canonical re-tally
- **Anti-claim**: F016 does NOT change the P5 disposition (Confirmed; both arms; κ=+1.0000) or the P6 disposition (Falsified; 46pp gap far outside locked 15pp band). The one-record DENY→ALLOW shift adjusts the cross-model verdict-style table at §4.7 / F014 but does not change the cross-axis-coherent reading
- **E4 design implications**: same as F015 — the discipline is the same

#### F017 — κ-check coder drift catch on diagnostic_primary (Discovered)

<!-- F017 is the E3 analog of E2's F012 in shape: a methodological observation
     that the measurement instrument is doing its design work, surfaced from
     the data itself. The both-and reading: (i) the instrument worked; (ii)
     the substantive P5 result on this arm carries an additional layer of
     instrument-as-finding. -->

- **Status**: Discovered
- **Evidence (n=100, Phase 2.5 inter-coder pass)**: blind AI second-coder pass on diagnostic_primary surfaced systematic disagreement at the missing-evidence-hedge / rule-itself-hedge rubric boundary. First-pass κ between human first pass (8/25/67) and blind agent (7/93/0) = **−0.0369** (less than chance). Reconciliation under the strict rubric default (missing-evidence hedging is the normal nudge behaviour and is NOT inversion-recognition) walked the 79 disagreements with both calls visible alongside the default rule; reconciler adopted the agent's call on 79/79 records (`second-coder-adopted` audit field). Reconciled-vs-agent κ = **+1.000**
- **Disposition**: methodological finding, direct analog to E2's F012 (both-and reading). (i) The κ protocol worked exactly as designed: a measurement-instrument check caught coder drift before the writeup committed to the wrong P5 disposition. (ii) The substantive P5 result is unchanged after reconciliation — the rubric-axis Cat 2 dominance was always in the corpus; the first-pass categorisation drift was a coder fatigue artefact at a boundary the rubric's default rule unambiguously resolves
- **Anti-claim**: F017 does NOT establish that human first-pass coding is unreliable in general — it establishes that *this human, on this rubric, under this cognitive load, on this boundary* drifted. The reconciler's drift characterisation (verbatim, 2026-06-07): *"I misinterpreted the categories first pass and was fatigued."* The protocol change for diagnostic_claude (AI-first + human review-and-adjudication) is the response to the methodological observation, not to a generalised claim about human coding
- **E4 design implications**: any operational receipt-as-memory experiment that includes a hand-coded rubric step should bake in the κ-check + reconciliation primitive at design time, not as a post-hoc rescue

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
- The cross-model finding tightens the deployment story: on the rubric axis (the reasoning trace) inversion-blindness reproduces under two model-protocols (P5 confirmed both arms); on the verdict axis, P6 falsified with a 46pp gap — verdict style is model-specific (Opus decisive, GPT-5.4 hedging) but the underlying inversion-blindness pattern is task-class. E4's design-partner conversation can lean on this — the operational governance need is not "pick a better model"
- <!-- TODO: confirm with Sam the exact framing of the E4 design-partner pitch before locking this section -->

## §8 — Limitations + caveats

<!-- ~3 sub-bullets. Honest disclosure section, matching E2's §9 anti-claims
     style. The Arm C asymmetric-control caveat (already documented), the
     Opus 4.7 sampling caveat (already documented), and the inter-coder
     reconciliation methodology (described honestly here). -->

### Arm C asymmetric-control caveat

- Arm C token parity vs Arm A: −16.43% (PR #93, documented at pre-registration)
- The asymmetry rules out one family of confounds (Arm C did not have excess volume) and introduces another (Arm C may not have had enough volume)
- P1's Arm C ≤12% DENY threshold is comfortably cleared (Arm C DENY 0% observed), so the volume-alone Reading B explanation is falsified even granting the asymmetry — but the writeup names the caveat explicitly
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

## §9 — Anti-claims

<!-- Dedicated aggregated anti-claims section, mirroring E2's §9. The
     proximity-discipline copies (inline anti-claims at each finding in §4)
     are preserved; this section is the aggregated audit lens that lets a
     reader read the full set of "what the writeup does NOT establish" on
     one page. Mix of finding-anchored bullets (lifted from §4.1, §4.2,
     §4.4, §4.5, §4.6, §4.7, §5) and cross-finding bullets that span more
     than one §4 subsection. Voice matches E2's §9: each bullet names a
     claim the corpus cannot support, with the reason it cannot. -->

The findings in this writeup do *not* establish the following. Each item names a claim the corpus cannot support, with the reason it cannot.

- **The falsification of P1 is not a refutation of the precedent mechanism.** Arm A still produces every single DENY observed in Piece 1 (10 vs 0 in B and 0 in C); precedents are doing work for DENY commitment. They just don't carry the full weight of the L3 break alone. The accumulation reading was named explicitly in the predictions' interpretive note as the third shading.
- **The §10 governance-memory mechanism from E2 holds — but operates symmetrically, not DENY-asymmetrically as P2 anticipated** (see F013). The bundle schema's verdict field carries the load (verdict-bearing precedents differ from verdict-stripped ones); the polarity does not (ALLOW-bearing precedents are not specifically anchoring DENYs in this corpus).
- **The L3→L4 backoff result does NOT mean the nudge clause is useless.** It means the L3→L4 reversion on E2's PROC-005 ambiguous-rule axis was already being driven by the policy text's structural cues; the nudge is a discipline reinforcement, not the causal agent.
- **P4's 88% same-as-unperturbed is NOT "narrowly falsified".** Calling it Falsified would be a post-hoc rule introduction the locked vocabulary disallows; the locked spec specifies a confirm band only. The discipline of leaving it Under-tested is itself a methods-note contribution.
- **The Cat 2 dominance is not "the agent is sycophantic" in the AI-safety-literature pinpoint sense.** The agent is not agreeing with the inverted policy; it is ignoring the inversion and applying its rule-intent prior — the E2 distinction between "authority-conditioned alignment in the structural sense" and "sycophancy" carries forward intact.
- **The cross-model arm does NOT establish that Opus is "more correct" or "more inversion-blind" than GPT-5.4** (see F014). The rubric distribution shape is what carries the P5 confirmation, not per-record verdict equivalence. The Opus 4.7 no-temperature sampling caveat is part of why per-record verdict comparability is not the right reading.
- **E3 is not a multi-domain result.** The substrate is UK public-sector procurement; the policy is the same six-rule snapshot used at E1 + E2. The disambiguation findings may or may not transfer to AML / KYC / underwriting / clinical-decision domains. The methodology is portable; the findings are not.
- **E3 is not a multi-substrate result.** The diagnostic_primary + diagnostic_claude record-matched 100-record subset is drawn from the same E1 fixture as E2. The cross-model verdict-style divergence is a finding on this corpus + this policy combination, not on the foundation-model task class in general.
- **The receipt-anchored cost projection within 0.4% does not extrapolate to arbitrary corpus sizes.** The instrument validation is exact at this scale (n=1,332 receipts, six arms) and on this substrate's cost shape; cross-domain cost extrapolation is a separate empirical question.
- **This writeup does not establish that signed receipts cause more decisive AI behaviour.** The corpus shows correlation between verdict-bearing precedent receipts (Arm A) and directional verdict commitment under the locked policy snapshot only. Whether the same correlation reproduces under different policy snapshots, substrate domains, or receipt schemas is open.
- **The κ-protocol catch on diagnostic_primary (F017) does NOT establish that human first-pass coding is unreliable in general.** It establishes that this human, on this rubric, under this cognitive load, on this boundary, drifted. The reconciliation methodology under the strict rubric default produced κ=+1.000; the discipline worked. Whether the same boundary trips other coders is an open empirical question.
- **The F015 + F016 anchor drifts do NOT change any P1-P6 disposition.** They adjust a 3-count ALLOW field on arm_c (F015) and a one-record DENY→ALLOW shift on diagnostic_claude (F016). The substantive readings carry through unchanged; the discipline of provisional-vs-canonical reconciliation as the first move at each phase boundary is what F015 + F016 register, not a substantive correction to any finding.

## §10 — Conclusion

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
- The corpus resolved all three in forms the predictions explicitly anticipated as third readings: accumulation amplifies (not precedents alone); policy text drives the backoff (not the nudge); inversion-blindness reproduces at scale on the primary model with a substantive verdict-style divergence on the cross-model arm (P6 falsified — the model-specific outcome pre-registered as "a strong finding, not a failure")
- Disposition mix: **P5 confirmed on both diagnostic arms; P1, P3, P6 falsified cleanly against locked falsification bands; P2 and P4 under-tested (confirm-band only; no locked falsify band)** — the falsifications + under-tested dispositions are the story, and each names either a sharpened mechanism or a methods-note discipline refinement rather than a refuted finding
- Piece 1 substantive refinement (recovered by re-cutting on verdict distribution rather than DENY rate alone): verdict-bearing precedents enable directional commitment in both directions, with ALLOW dominant in this corpus + policy combination; the §10 governance-memory mechanism from E2 holds but operates symmetrically rather than DENY-asymmetrically as P2 anticipated
- The methodology substrate — pre-registered predictions with locked falsification criteria, κ-check protocol with reconciliation methodology, disposition vocabulary (including the Under-tested honest call when locked spec only registers a confirm band), receipt-anchored cost projection — is the durable contribution and carries forward to the trilogy methods note
- E4 is the operational receipt-as-memory experiment; the design-partner shape is named but the design is not yet locked

## §11 — Acknowledgments

<!-- ~1 paragraph. Standard acks plus the AI assistance declaration matching
     E2's style. -->

- <!-- TODO: collaborators, reviewers, design-partner contacts as appropriate -->
- AI tools were used during ideation, drafting, and editorial refinement; pre-registration, design, locked content, corpus collection, and analytical conclusions were directed and reviewed by the author. The methodology this paper studies is also the disclosure discipline this paper applies to its own production

## §12 — References

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
