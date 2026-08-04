---
title: "Receipt-Anchored Evaluation: a methodology for cryptographically verifiable empirical research on AI-governance behaviour"
subtitle: "A trilogy capstone — methods extracted from three pre-registered applied experiments on UK public procurement substrate"
id: MM-2026-01
authors:
  - Sam Carter (MeshQu)
status: DRAFT (§1–§9 authored; references/DOIs + independent review pending)
classification: PUBLIC
version: 0.2-draft
published_at: TBD
tags: [methodology, receipts, pre-registration, ai-governance, evaluation, transparency-log]
toc: true
branding: meshqu-research
density: research
references_layout: numbered
---

<!--
  AUTHORING STATUS: §1–§5 authored and reviewed. §6 (Lessons) carries the
  scaffold bullets + citation hooks for authoring; §7 (Threats), §8
  (Commitments), §9 (Conclusion) are skeletons. §10/§11 are back matter.
  Structure is organised by control (Evidence / Interpretive / Analytical
  integrity), not by chronology. Anchoring claims verified — see IA-2026-01.
-->

# Receipt-Anchored Evaluation: a methodology for cryptographically verifiable empirical research on AI-governance behaviour

## 1 · Introduction

When an AI agent helps make a regulated decision — approve a supplier, flag a transaction, assess a loan — how do you later prove what it decided, on what evidence, against which rules, and that nothing was changed after the fact? Most research on AI decision-making can't: the reader is asked to trust the authors' account of what happened. Receipt-Anchored Evaluation replaces trust in the authors with trust in public cryptographic infrastructure. Two mechanisms make the underlying evidence verifiable; a third guards against the researchers' own errors in analysing it.

First, every decision — whether made by the AI agent or by the governing policy — is captured as a **Decision Receipt**: a tamper-evident, digitally signed record that can be independently verified without relying on the authors' account of events, the way a signed bank statement can be verified without relying on the issuing bank. Second, every prediction the research makes is written down and locked — published and time-stamped — _before any data is collected_, the same discipline clinical trials use to stop researchers from moving the goalposts once results come in. The shift is subtle but large: conventional evaluation preserves the _conclusions_; Receipt-Anchored Evaluation preserves the _evidence those conclusions are built from_ — so every headline number can be independently re-derived from the published decision record, and a prediction that turns out wrong has to be reported as wrong, because the rules of judgment were fixed in advance.

The approach has been stress-tested three times on the same fixed set of 283 UK public-procurement records — roughly 3,000 signed decisions in all — each experiment sharpening the last. The most demanding made six advance predictions: one held up, three were proven wrong against thresholds set beforehand, and two landed in a documented gray zone the predictions hadn't pinned down tightly enough. That honesty is enforced, not hoped for: an independent re-checking step re-coded the same evidence blind and, in that experiment, caught a systematic coding error of the researchers' own before it reached the results. Reporting the misses and the gray zones is the point — the gray zones became the method's own next improvement.

The methodology is designed to travel; the findings are not. The same discipline could be applied to lending, sanctions screening, or clinical triage — but the specific results here belong to this set of records and nowhere else. Nothing in this work claims to describe how AI agents behave in general; only how they behaved on these records, in a way anyone can verify without trusting us.

---

## 2 · The receipt primitive

Receipt-Anchored Evaluation has a single primitive, and every guarantee in this note derives from it: the **Decision Receipt** — a tamper-evident record of one decision, signed and published so anyone can check it. This section says what that object contains, what it is anchored to, and why those two properties make it _evidence_ rather than a log entry.

### 2.1 What a Decision Receipt is

A Decision Receipt is the signed record of one decision — what was decided, on what facts, against which policy, by whom, and that none of it changed afterward.

- It binds into a single object: the substrate facts the decision saw, the policy snapshot it was judged against (pinned by content hash), the verdict and the violations that produced it, the deciding agent's identity and the SHA-256 of its reasoning text, an Ed25519 signature over the record, and the identifier of the signing key (the _kid_).
- It is self-contained and verifiable offline: every byte a verifier needs is in the record, and nothing outside it is required to check the signature.

One real receipt from the corpus (E1, decision `ca19e737` — the £57M award MeshQu denied while the agent hedged to REVIEW; hashes abbreviated):

```json
{
  "decision": "DENY",
  "decision_id": "ca19e737-defb-4e5f-b216-ec97d2fe5859",
  "receipt_schema_version": 2,
  "timestamp": "2026-05-18T10:42:19.888Z",
  "context": {
    "fields": {
      "contract_value": 57000000, "publication_delay_days": 33,
      "agent_model_id": "gpt-5.4-2026-03-05", "agent_recommended_verdict": "REVIEW",
      "agent_reasoning_sha256": "dc31a240…1f04b52a"
    },
    "metadata": { "ocid": "ocds-b5fd17-282a00c5-…", "experiment_substrate": "uk_contracts_finder_ocds" }
  },
  "policy_snapshot_digest": "5d7d8001…8fc0cc9d",
  "violations": [
    { "rule_code": "PROC-001-S53",        "reason_code": "VALUE_ABOVE_MAX", "field": "publication_delay_days", "actual_value": 33,       "expected_value": "<= 30" },
    { "rule_code": "PROC-002-AUTHORITY",  "reason_code": "VALUE_ABOVE_MAX", "field": "contract_value",         "actual_value": 57000000, "expected_value": "<= 500000" },
    { "rule_code": "PROC-005-OPEN-TENDER", "reason_code": "FIELD_MISSING",  "field": "procurement_method_open_flag" }
  ],
  "integrity_hash": "e42a292d…aadb9880",
  "signature_algorithm": "ed25519",
  "signature_kid": "meshqu-experiment-procurement-2026-05",
  "signature": "uc5rRWJ7AQ9n…B2PKCA",
  "transparency_anchor": { "provider": "rekor.sigstore.dev", "log_index": 1566819550, "entry_uuid": "108e9186…9908545d" }
}
```

The agent's identity and reasoning are _inside_ the signed object, not in a side log to be reconciled later; the policy is pinned by digest; the verdict and every violation are explicit.

### 2.2 What a Decision Receipt is anchored to

A signature proves who signed a record and that it hasn't changed. It does not, on its own, prove the signature existed at a given time and wasn't quietly re-issued later. _Anchoring_ closes that gap by publishing each receipt to a public, append-only transparency log no one — including the authors — can rewrite.

- Each receipt is anchored to the public **Sigstore Rekor** transparency log: anchoring wraps the receipt's integrity hash in a standard signed envelope and submits it; Rekor returns a log index and an _inclusion proof_ — cryptographic evidence the entry is part of the public log.
- A reader verifies in two independent steps, neither needing the authors' infrastructure: check the Ed25519 signature against the published key, and check the Rekor inclusion proof against the public log. Both checks are re-implemented by a reference verifier independent of the signer (for this programme, the offline checker at [verify.meshqu.com](https://verify.meshqu.com)).

Anchoring was independently verified end-to-end across all three experiments: each receipt's Rekor entry is re-derivable from its public integrity hash alone, with no access to the authors' systems. For the worked example above, that resolves to Rekor entry `1566819550` and reconciles to the receipt's own subject digest. The full byte-level walkthrough, and the same check applied across E1/E2/E3, are recorded in integrity audit IA-2026-01.

_A note for re-derivers:_ the corpus is published at two layers. The canonical, anchored artefact is the **exported** verification bundle — all three experiments ship a `corpus.tar` of anchored bundles, and any receipt's anchor is also retrievable from the public log by its integrity hash. The raw run-directory emissions are _pre-export source_ and carry a null anchor by design — verify against the exported bundle or the public log, not the run-dir file.

### 2.3 Why this matters: provenance vs logging

The difference between this and ordinary logging is _who you have to trust_.

- Application logs are evidence only insofar as you trust the system that wrote them. A receipt is evidence under a public key and a public log alone.
- The guarantee is cryptographic and procedural, not reputational: a reader re-derives every headline number from on-disk bundles without trusting the authors.
- A receipt preserves _provenance_, not _correctness_. It proves what was decided, against which policy, on what evidence — not that the decision was right, nor that the policy was the right policy. E3 is the sharp case: an agent can faithfully apply an _inverted_ rule, and the receipt records that it did, and against which rule, without endorsing the outcome.

The same receipt primitive that generated the experimental corpus also serves as its reproducibility substrate: the artefact being evaluated is the artefact that preserves the evidence.

### 2.4 Reproducibility constraints

Three properties of the primitive make a receipt re-checkable by a third party rather than only by its author:

- **Canonical JSON.** The record is serialized in one deterministic byte ordering, so the same fields always produce the same bytes — and therefore the same hash and the same signature. Without a single canonical form, two parties could disagree on the bytes and the signature would not reproduce.
- **Content-addressed pinning.** The policy snapshot and rule set are referenced by digest, so a verifier confirms _which_ policy and _which_ rules a decision was judged against — not a name that could later point elsewhere.
- **Schema versioning.** Each receipt declares its `receipt_schema_version`; fields are added additively and a change in meaning forces a version bump, so a verifier reading a receipt years later knows exactly how to interpret it.

<!-- cite: packages/meshqu-core/src/transparency.ts (reconstructDsseEnvelope / anchorToRekor) for the DSSE in-toto anchoring construction -->
<!-- cite: docs/integrity-audits/2026-06-09-rekor-anchoring-scope.md (IA-2026-01) for byte-level anchoring verification across E1/E2/E3 -->
<!-- cite: procurement-decisions/results/corpus.tar → bundles/ca19e737-…bundle.json for the worked receipt -->

---

## 3 · Pre-registered evaluation

> The receipt makes the _evidence_ trustworthy; it says nothing about whether the _analysis_ of that evidence is honest. A signed corpus can still be mined for whatever story the analyst wants to tell. The second half of the methodology is the discipline that constrains the analyst — applied with the same rigour, and recorded in the same auditable way, as the receipts themselves.

### 3.1 Pre-registration: locking predictions before the data

Before any decision is collected, the researcher writes down what they expect to see — and, crucially, what would prove them wrong — and locks it.

- Predictions, prompts, the governance-context content, and the policy snapshot are hashed (SHA-256) and committed to a public tag (`v0.X-predictions-locked`) _before the first record is run_. The lock converts _"we observed X"_ into _"we predicted X-or-not-X, and the corpus showed which."_
- Each prediction states a **confirmation band** — the numeric range that would confirm it — and, where the hypothesis supports it, an explicit **falsification band** — the range that would prove it wrong. Fixing the numbers in advance removes the analyst's freedom to move the goalposts once the result is in.
- The lock is content-addressed: a reader confirms the predictions existed _before_ the data by checking the commit hash against the public timeline — the same trust-minimisation the receipt gives the evidence, now applied to the hypotheses. This is clinical-trial pre-registration (ClinicalTrials.gov, the OSF), borrowed and made cryptographic.

**Bidirectional locking.** Every quantitative prediction locks _both_ a confirmation band and a falsification band, with the gray zone between them named in advance. A confirmation-only prediction leaves the falsification side to the analyst's judgment at analysis time — exactly the discretion pre-registration exists to remove. This refinement surfaced from the trilogy itself: two of E3's six predictions locked only a confirmation band, and the honest label for their outcome had to name that gap (§3.2; carried forward as a rule in §6).

<!-- cite: procurement-context-disambiguation/planning/predictions.md — P1/P3/P5/P6 lock both bands; P2/P4 lock only the confirmation band -->
<!-- cite: programme/PROCESS.md gate #1 + gate #8 (state verification + title commitment at the lock) -->

### 3.2 The disposition vocabulary: a closed set of outcome labels

When the data is in, every prediction — and every post-data finding — is reported with one label from a fixed list decided in advance. There is no partial confirmation. The category is removed by construction.

The programme carries **two** vocabularies — one for _predictions_ (claims locked before the data), one for _findings_ (patterns noticed while analysing it) — sharing five labels and diverging on the sixth. They are graded differently because one had a lock to grade against and the other did not.

Five labels are shared by both vocabularies:

| Label | Meaning |
|---|---|
| **Confirmed** | the corpus landed inside the confirmation band |
| **Falsified** | the corpus landed inside the falsification band |
| **Inverted** | the corpus ran the _opposite_ way to the prediction — a sharper falsification: the signal exists, reversed |
| **Refuted** | the corpus rules out the prediction's underlying mechanism |
| **Deferred** | the measurement instrument was inadequate; unresolved on this experiment |

The sixth label is where the two registers diverge — and the divergence is the point:

| Register | Sixth label | Meaning |
|---|---|---|
| **Predictions** (locked before the data) | **Under-tested** | the value fell in a gray zone the lock did not pin — outside the confirmation band, no falsification band registered. A positive label for an under-specified prediction, not a soft "inconclusive." |
| **Findings** (surfaced during analysis) | **Discovered** | the pattern was not predicted; it surfaced from the corpus. The post-data counterpart of Under-tested — an honest "we did not call this in advance," not a backdoor "we knew all along." |

Grading a _discovered_ finding as _confirmed-from-prediction_ is post-hoc smoothing; grading an _under-tested_ prediction as _discovered_ is escape-hatch backfill. Predictions take the Under-tested vocabulary; findings take the Discovered vocabulary; neither borrows the other's sixth label.

Worked, from E3:

- E3 predicted that precedents _alone_ would drive the agent's commitment; the corpus put that arm at 3.5% against a locked floor — **Falsified**, cleanly, by a number set in advance. Without the band, "precedents matter directionally" could have been written up as broadly confirming.
- Two E3 predictions locked only a confirmation band; their observed values landed just outside it with no falsification band to trip — **Under-tested**. The label names the lock's own under-specification rather than rounding the result toward confirmation.

<!-- cite: procurement-context-disambiguation/planning/predictions.md §"Definition of 'report honestly'" (locked P-series vocabulary) -->
<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 "F-series structure as a methodological contribution" (F-series vocabulary) -->
<!-- cite: programme/PROCESS.md "Honest falsification" (no post-hoc smoothing) -->

### 3.3 Why this matters: the bias it is engineered against

The goal is not to eliminate interpretation — empirical work always involves it — but to make interpretation accountable to a framework declared before the data. Each piece of the discipline targets a specific, well-documented way empirical claims drift toward their authors' hopes.

- Without pre-registration, post-hoc smoothing is the path of least resistance — a wrong prediction quietly becomes "partially confirmed" or "broadly directional." The closed vocabulary cuts that path off: the analyst must pick one label.
- Without numeric falsification bands, any result can be reframed as supporting the hypothesis. Numbers fixed before the corpus arrives fix the goalposts.
- Without cryptographically binding the experimental configuration, predictions and evidence can drift apart between lock and report, and the experiment stops being replayable.

The outcome is a corpus where a falsified prediction is reported as falsified — and where that honesty is _checkable_, because the predictions, the bands, and the disposition each one landed at are all on the public record, dated before the data. A reader who doubts the conclusions can still audit the process.

---

## 4 · The finding registers

Locked predictions and the disposition vocabulary are two of the named contracts the programme runs on. Four more govern how findings are written, how behaviour is compared across experiments, how competing interpretations are handled, and how the limits of each claim are stated. Each is a shape fixed before the artefact is authored — the discipline is the sum of all of them, not the vocabulary alone.

- **The finding shape (F-series).** Every post-data finding follows one structure: a disposition label, a numbered evidence block with denominators, both interpretive readings where the data admits two, an explicit list of what the finding does _not_ establish, and a note on the experiment that would sharpen it. The restraint pre-registration imposes on predictions, applied to interpretation. (E2 ran F001–F012; E3 added F013–F017.)
- **Behavioural axes (D-series).** Behaviour is compared across experiments along named, numbered axes — policy resistance, precedent sensitivity, uncertainty acknowledgement, and others — each defined before it is measured. Comparing by axis rather than by ad-hoc metric is what makes "the same behaviour, under a sharper instrument" a checkable claim: an axis measured in one experiment is the _same_ axis in the next. (E2's Appendix C established D1–D8; E3 inherits the numbers under the same definitions.)
- **Two readings.** Where the corpus admits more than one defensible interpretation, both are named; the writeup leans toward one only when the pattern weakly favours it, and names the experiment that would settle the question. The un-leaned-toward reading is not suppressed — it is recorded and dated. Preservation of alternatives, not collapse to a single story, is the committed voice.
- **Anti-claims as first-class output.** Every finding carries, at the point it is made, an explicit list of what it does not establish; the writeup also aggregates these into one section, so a reader sees the full ledger of un-made claims in one place. Both registers — inline _and_ aggregated — not either-or.

Together with the receipt primitive (§2) and pre-registration (§3), these registers are what the name _Receipt-Anchored Evaluation_ denotes: not the receipt alone, but the receipt plus the closed contracts that govern how it becomes a claim.

<!-- cite: procurement-context-gradient/results/writeup-DRAFT.md §7 (F-series shape, two-readings discipline) + §9 (aggregated anti-claims) + Appendix C (D1–D8) -->
<!-- cite: procurement-context-disambiguation/writeup/writeup.md for F013–F017 and E3's Reading A/B + Framing A.1/A.2 -->
<!-- cite: D-series is D1–D8 per writeup-DRAFT Appendix C; do not reintroduce a D9 without a sourced definition -->

---

## 5 · Reconciliation: auditing the analysis step

> The receipt secures the evidence; pre-registration secures the predictions. But some measurements are not read off a meter — they require human judgment. Coding a thousand reasoning texts into behavioural categories is the clearest case: the categories are defined in advance, but applying them is a judgment call, and judgment drifts — most of all under fatigue, and invisibly to the person doing it. This is the discipline that audits the judgment step itself. Reconciliation treats coding decisions as _measurements subject to error_, not as authoritative observations; the object under audit is the measurement, not the person.

**The mechanism.** A second coder, working blind, re-codes the same material. The two codings are compared with **Cohen's κ** — a standard measure of agreement beyond chance, where 0 is no better than guessing and 1 is perfect. A low κ does not say which coder is right; it says they systematically disagree, which is the signal that one has drifted. Where κ surfaces disagreement, a **reconciliation** pass resolves each contested record against the rubric's pre-declared default rule. The reconciled sheet — not either original pass — is the canonical one, and its provenance is auditable record by record: for every record it carries which call was kept, which was adopted from the other coder, and which was overridden. Most reports state only that disagreements were resolved; here, every adoption and every override survives in the published coding.

**Two protocols, chosen by failure mode.** The trilogy ran the step two ways, and the choice is itself methodological:

- **Blind second-coder, then reconcile.** Both coders work independently; κ flags drift; a reconciliation pass adjudicates each contested record against the rubric. The canonical multi-coder design.
- **Machine-first, then human adjudication.** An automated coder codes blind; a human then reviews every record with the automated call and the rubric in view, recording an accept-or-override per record. This eliminates _first-pass categorisation from memory under load_ — a specific fatigue vector the first design is exposed to.

In the trilogy the blind second-coder was an AI instrument. Its independence derives from blindness to the first pass and adherence to the same rubric — not from human status: it is an independent measurement instrument, not a second opinion with a vote. Choosing between the protocols is a choice about which failure mode dominates, not about which coder is better.

**Worked case — self-detection of coding drift.** In E3, one hundred reasoning texts were hand-coded into three categories (does the agent _name_ an inverted rule, _reason against its intent_, or _partially do both_). The single coder's first pass distributed them 8 / 25 / 67. On that pass the prediction under test (P5) would have been reported **Under-tested** — the modal category sat well below its confirmation threshold.

A blind AI second-coder re-coded the same hundred. The two codings agreed at **κ = −0.04** — _worse than chance_ — and the 79 records they disagreed on were not scattered: 66 of the 79 sat at a single rubric boundary. Random error does not concentrate like that; systematic drift does. Each contested record was then adjudicated against the rubric's _pre-declared default rule_ — the rule fixed before any coding began — record by record. On all 79 the rubric's default overturned the first pass and matched the second coder; the reconciled distribution was 7 / 93 / 0, and under it P5 was **Confirmed**.

The shape of that shift is the drift's fingerprint. The first pass's modal category was _partial_ — 67 of 100 — and _partial_ is the category a fatigued coder reaches for when not looking closely. Re-read against the rubric, almost none of those records were genuinely ambiguous: the _partial_ pile emptied to zero and resolved overwhelmingly into _reasons against rule intent_.

Adopting the second coder on all 79 with zero overrides can look like one coder capitulating to another, and the perfect agreement it mechanically produces — a reconciled-versus-second-coder κ of +1.00 — is circular: adopt the other reading on every disagreement and perfect agreement follows by construction. That number is not evidence, and is not reported as one. The evidence that the _second_ pass was the on-rubric one runs the other way, and is checkable without trusting either coder: the adjudication rule was declared before the data, the 66-of-79 boundary concentration shows the first pass erred systematically rather than at random, and the published per-record sheet lets any reader re-apply the rubric's default to each contested record and confirm the call. That the correction moved a prediction _toward_ confirmation — the direction pre-registration exists to police — is exactly why the rule was fixed in advance and the reconciliation left on the public record: the move is one a reader can audit, not one the analyst chose.

The point is not that a coder made an error. The point is that the methodology caught it before it reached the results. Without the κ check, a real prediction would have been reported Under-tested on the strength of a fatigued first pass — a quiet, plausible, wrong conclusion. The check turned an invisible analyst error into a recorded, reconciled, and disclosed one.

The discipline does not assume the analyst is reliable. It measures whether they were, records the answer, and leaves the measurement on the public record.

<!-- cite: procurement-context-disambiguation/results/rubric_inter_coder_analysis_primary.md — first-pass↔reconciled κ = −0.0369; reconciled↔agent κ = +1.0000; 21 agreement-kept / 79 second-coder-adopted / 0 override; 8/25/67 → 7/93/0 -->
<!-- cite: procurement-context-disambiguation/planning/decision_log.md 2026-06-07 "Why the protocol differed between arms" + the fatigue admission -->
<!-- cite: procurement-context-disambiguation/results/rubric_inter_coder_analysis_claude.md for Variant B (machine-first + human adjudication) -->

---

## 6 · Lessons and carry-forwards from the trilogy

The three pillars define the methodology; this section records what three applications taught about operating it.

### 6.1 Stress-testing the methodology

The methodology was stress-tested — not merely exercised — across three experiments over a fixed 283-record procurement substrate, each raising the methodological demand: E1 validated the receipt primitive at corpus scale; E2 added governance-context variation; E3 added disambiguation arms, inter-coder reconciliation, and cross-model evaluation. Across the programme, 3,044 signed decisions were emitted — 283 in E1, 1,429 in E2, 1,332 in E3 — each anchored to the public Rekor log by the same pipeline, with coverage independently verified at 283 / 283 for E1 and by sampled receipts for E2 and E3 (IA-2026-01). E1 processed 300 OCDS release events to produce those 283 receipts: the Contracts Finder feed published 12 OCIDs more than once, and each repeat POST was answered from the evaluator's idempotency cache, producing no new decision, no new signature, and no new Rekor entry (see IA-2026-02). Three research questions. One held-fixed corpus. Increasing methodological demand.

<!-- cite: procurement-decisions/writeup/main.md; procurement-context-gradient/README.md; procurement-context-disambiguation/results/analysis_outputs.json disposition_table -->

### 6.2 The falsifications were the payoff

E3 made six pre-registered predictions; three were proven wrong against their locked bands. Reported under a closed vocabulary, those falsifications are _where the experiment paid off_ — each named a mechanism the expected story had wrong (precedents alone do not drive commitment; policy text, not the nudge, drives the backoff). The single confirmed prediction carries more weight precisely because it sits alongside three clean falsifications and two honestly-labelled Under-tested results in the same writeup. A methodology that reports its misses is not selecting for its hits.

<!-- cite: procurement-context-disambiguation/planning/predictions.md (P1–P6 bands); results/analysis.py disposition_methodology block -->

### 6.3 Carry-forwards

Four lessons an implementer inherits, each pulled from a concrete failure the programme caught:

- **Instrument validation through independent projection.** The experimental runner is itself an instrument, and an instrument can be silently miscalibrated. An independent pre-run projection that the production run then reproduces — in the trilogy, a per-arm cost projection the full run matched within tolerance — is evidence the runner is pinned. (The projected figure is disclosed as a modeled estimate, not a billing reconciliation; the honest pairing is the lesson, not the accuracy.)
- **Runner validation through lock-in tests.** A run can pass every cryptographic check and still be substantively empty — one smoke run signed its receipts cleanly while feeding empty records to three arms (_cryptographically clean, operationally empty_). Validation therefore requires operational lock-in tests in addition to receipt verification: parametrized tests that assert the runner produces distinct inputs per record, and that observability is captured at runtime rather than merely configured, catch the class of failure a signature cannot.
- **Parallel-execution isolation.** Parallel experimental execution requires isolation guarantees. Early E3 runs showed that a shared execution environment can cross-contaminate independent experimental branches; isolated workspaces eliminated the failure mode.
- **Ambiguity preservation.** Several E2 and E3 findings admitted more than one defensible interpretation. Forcing a single narrative would have overstated the evidence, so the methodology treats alternative readings, anti-claims, and Under-tested outcomes as first-class outputs rather than editorial weaknesses — the same restraint surfacing in several places (§3's Under-tested, §4's two-readings and anti-claims), recognised here as one lesson: resolve ambiguity in the experiment, not in the prose.

<!-- cite: decision_log.md 2026-05-29 "Five-gate sign-off" + writeup/writeup.md §8 (cost-as-instrument + modeled-vs-billed caveat); decision_log.md 2026-05-28 (PR #97 record-composition; Wave 2 isolation); programme/PROCESS.md gate #7 -->

---

## 7 · Threats to validity

> A methodology's credibility is partly in what it refuses to claim. The trilogy's own line — _the methodology is designed to travel; the findings are not_ — is the first entry on this list; the rest mark where the guarantees stop.

**Substrate dependence.** Every quantitative finding is bound to a single 283-record UK public-procurement corpus. The receipts make those findings _checkable_; they do not make them _general_. No result here transfers to another domain except as a hypothesis to be re-tested under the same discipline.

**Model-version dependence.** Findings are specific to the locked model versions, and E3's cross-model arm is the cautionary case: the _verdict_ an agent emitted diverged across models, while the _reasoning pattern_ — applying a rule's intent over its inverted text — reproduced. An evaluation built only on verdict outputs may produce conclusions that do not survive a model change; reasoning-level findings travel further than verdict-level ones, but neither is guaranteed across versions.

**Policy dependence.** The experiments measure the interaction between an agent and an _authored_ policy artefact — its rules, thresholds, decomposition, and drafting. E3 showed that policy structure is itself a major variable: which rung of the governance ladder carried the commitment signal, and whether policy text or an anti-sycophancy nudge drove the backoff, were the questions the experiment existed to disambiguate. The findings therefore attach to the policy as authored, not merely to the domain it governs; a different policy structure over the same records could produce different behaviour.

**Rubric dependence.** Where behaviour is hand-coded (§5), the categories are only as good as the rubric that defines them. Reconciliation can drive agreement to κ = 1, but perfect agreement on a poorly-chosen rubric still measures the wrong thing — reliability is not validity. The rubric is pre-registered and published precisely so this dependence is auditable rather than hidden.

**Coder effects.** Reconciliation detects and bounds an individual coder's drift; it does not remove the framing choices baked into the rubric by its author. The discipline measures whether the coding was applied consistently — not that the categories carve the behaviour at its joints.

**Transparency-log trust assumptions.** "Verifiable without trusting the authors" is not "verifiable without trusting anything." Verification inherits Sigstore Rekor's append-only guarantees, the integrity of the published signing key, and the standard assumptions behind Ed25519 and SHA-256. These are widely held and well-scrutinised — but they are assumptions, and the methodology rests on them.

**Public-record survivorship.** The substrate is what UK Contracts Finder published, not the full population of procurement decisions. Records withheld, delayed, or never filed are absent from the corpus, and any selection effect in the public feed is inherited by every finding.

**Reasoning-text limitations.** The agent's reasoning text is what the model emitted, not a faithful trace of the computation that produced its verdict. Findings about reasoning are findings about the emitted text — its content, its drift, what it names and omits — not claims about the model's internal process.

**External validity.** The methodology's portability is, at this point, an argument rather than a result. It has been stress-tested three times on one substrate; it has not been carried to a different evidential structure. Until it is (§9), "portable" describes a design property, not a demonstrated one.

---

## 8 · The five commitments of Receipt-Anchored Evaluation

<!-- AUTHORING NOTE (§8 skeleton): one short page. The distilled methodology,
     plain language, no MUST/SHOULD, no conformance framing. Extracted from
     the body once §6/§7 are authored; refine wording then. -->

Distilled, Receipt-Anchored Evaluation makes five commitments:

1. **Preserve evidence, not merely conclusions.** Keep the signed decision artefacts the conclusions are built from, so the conclusions can be rebuilt and checked.
2. **Lock expectations before observing outcomes.** Pre-register predictions, prompts, and policy — with both a confirmation and a falsification band — before any data is collected.
3. **Constrain interpretation through explicit contracts.** Report against a closed disposition vocabulary and fixed finding shapes, so no result can be smoothed after the fact.
4. **Audit measurements that require judgment.** Treat hand-coding as a measurement subject to error; detect drift, reconcile it, and leave the reconciliation on the record.
5. **Preserve alternatives and state anti-claims.** Keep competing readings where the data is ambiguous, and say at each finding what it does not establish.

---

## 9 · Conclusion and future work

Empirical claims about AI-governance behaviour are usually asked to be believed. Receipt-Anchored Evaluation asks instead to be checked — and builds the checking into the artefacts, not the reputation of the authors.

The contribution is not the receipt alone. A signed corpus without locked interpretation still permits narrative drift: the evidence is trustworthy, but the story told over it is not constrained. A locked interpretation without trustworthy artefacts still requires trust: the discipline is sound, but the data behind it cannot be re-derived. The methodology needs both — and a third part besides, the audit of the judgment steps that neither receipts nor pre-registration reach. Evidence integrity, interpretive integrity, and analytical integrity are not alternatives; each is necessary, and only together do they let a reader who distrusts the conclusions still trust the process.

The wider claim the trilogy makes is small to state and large in consequence: empirical AI-governance research should preserve the evidentiary artefacts its conclusions are built from, not merely publish the conclusions. A conclusion is a summary. An artefact can be audited. Preserving the artefact is what turns "trust us" into "check it."

The trilogy's own results demonstrate why the distinction matters: predictions were falsified, coding drift was detected, and alternative readings were preserved — without requiring the reader to trust the authors' account of any of them.

What remains is to show the discipline travels. It has been stress-tested three times on one substrate; its portability is, for now, an argument — and the next experiments are built to test it.

### 9.1 E4 — operational receipt-as-memory agent (design-partner shape)

- E1–E3 measure an agent _receiving_ structured context; E4 inverts it — an agent _uses_ signed receipts from prior decisions as its retrieval substrate, with cryptographic provenance per evidence item. Provisional and partner-specific: the substrate, not the model, is the load-bearing variable, and it cannot be authored against a synthetic fixture.

### 9.2 Cross-domain substrate transfer

- Banking KYC/AML, credit/affordability, and complaints (FCA/CONC) are the near-term transfer targets; field-provenance envelopes apply identically while the substrate is privately held. Portability becomes a _result_ only when the discipline is carried to one of these, not a UK-procurement corpus.

### 9.3 Multi-step reasoning under receipt-anchored evidence

- E1–E3 measure single-decision reasoning; a multi-step variant would test whether an agent catches an inversion on step 2 after committing on step 1, with per-step vs trace-level anchoring as the methods question.

<!-- cite: methodology/README.md "Reuse" (public-vs-client repo separation); procurement-context-disambiguation/writeup/writeup.md §7.3 (E4 provisional shape) -->

---

## 10 · References

### 10.1 Programme publications

1. _MRP-2026-02 — "When AI hedges and policy commits."_ Carter, S. (2026). Published 2026-05-18. DOI: pending. Pre-registration tag `v0.1-predictions-locked` at commit `bd7a795`.
2. _MRP-2026-03 — "When precedents commit AI and policy pulls it back."_ Carter, S. (2026). Published 2026-05-27. DOI: pending. Pre-registration tag `v0.2-predictions-locked`.
3. _MRP-2026-04 — "Precedents, policy, and commitment."_ Carter, S. (2026). Published 2026-06-09. DOI: pending. Pre-registration tag `v0.3-predictions-locked`; release tag `v1.0-mrp-2026-04`.

### 10.2 Programme working documents

4. _Receipt-Anchored Evaluation reference._ [`./README.md`](./README.md).
5. _Programme process — research methodology spec._ [`../programme/PROCESS.md`](../programme/PROCESS.md).
6. _Structural-parity checklist._ [`../programme/STRUCTURAL-PARITY.md`](../programme/STRUCTURAL-PARITY.md).
7. _Integrity audit IA-2026-01 — Rekor anchoring._ [`../docs/integrity-audits/2026-06-09-rekor-anchoring-scope.md`](../docs/integrity-audits/2026-06-09-rekor-anchoring-scope.md).

### 10.3 Infrastructure references

8. Sigstore Rekor transparency log. <https://docs.sigstore.dev/logging/overview/>.
9. DSSE envelope specification (in-toto). <https://github.com/secure-systems-lab/dsse>.
10. Ed25519 signature scheme (RFC 8032). <https://datatracker.ietf.org/doc/html/rfc8032>.
11. MeshQu offline receipt verifier. <https://verify.meshqu.com>.

### 10.4 Regulatory anchors

<!-- Verify each per programme/PROCESS.md gate #9 before promoting to STABLE. -->

12. UK Procurement Policy Note 02/24 — _Improving Transparency of AI use in Procurement_ (Cabinet Office, March 2024). Names LLM "hallucination" as an accuracy risk in AI-assisted bids.
13. UK Procurement Policy Note 017 (from 24 February 2025) — the Procurement Act 2023 renumbering of PPN 02/24; same AI-transparency policy, updated terminology, no policy change.
14. UK Government AI Playbook (February 2025). Meaningful human control principle.
15. EU AI Act, high-risk provisions on automated decision-making.

### 10.5 Methodological precedent

16. _Pre-registration in clinical trials_ — ClinicalTrials.gov and the Open Science Framework (OSF) as direct precedent.
17. Cohen, J. (1960). _A coefficient of agreement for nominal scales._ _Educational and Psychological Measurement_, 20(1), 37–46.
18. Landis, J.R. & Koch, G.G. (1977). _The measurement of observer agreement for categorical data._ _Biometrics_, 33(1), 159–174. (κ bands: < 0 poor … 0.81–1.00 almost perfect.)
19. _Inspect_ — LLM evaluation framework, UK AI Security Institute (AISI). <https://inspect.aisi.org.uk/>.

---

## 11 · License and verifiable artefacts

### 11.1 The verifiability claim

> **Every receipt in the programme is verifiable against the public Sigstore Rekor log without trusting the authors.**

- The verification path: obtain the exported bundle (or the entry by integrity hash) → check the Ed25519 signature against the published kid → check the Rekor inclusion proof against the public log → recompute the canonical-JSON hash → confirm it matches the signed payload.
- No MeshQu credentials are required at any step. A reference verifier ([verify.meshqu.com](https://verify.meshqu.com)) re-implements the checks independently of the signer.
- Anchoring was independently confirmed across E1/E2/E3 by content search against the public log — see IA-2026-01.

### 11.2 Reproducibility statement

- Each experiment's run directory contains the canonical receipts, the run manifest (model id, temperature, prompt SHA-256, policy snapshot SHA-256, runner commit, kid, tenant id), the observability captures, and the verifier output. The **anchored** bundles are the exported corpus — E1, E2, and E3 each ship a `corpus.tar`; run-directory emissions are pre-export source (§2.2).
- Each writeup's headline numbers are re-derivable by running the published analysis against the on-disk bundles. No live API calls are required.

### 11.3 License

- Methodology + writeups: CC BY 4.0. Code (runners, verifiers, analysis): MIT.
- Corpora: published as-is from the UK Contracts Finder OCDS substrate; subject to the substrate's own publication terms.
- Receipts: signed under the experiment kid `meshqu-experiment-procurement-2026-05`, dedicated to the experiment and not used for production tenants.

### 11.4 AI-assistance declaration

This methods note was drafted with AI assistance — large-language-model tools were used for prose drafting, structural revision, and locating candidate citations — under the author's direction and review. The cryptographic verification reported in §2 and in IA-2026-01 was performed against the public Rekor log and the on-disk artefacts, not generated by a model; every quantitative figure is re-derivable from the cited sources. Disclosing the assistance trail is the same primitive this note advocates: making the work legible at the point of the work.

<!--
  AUTHORING CHECKLIST (remaining):
    [ ] §6 subsections authored from cited sources (prose, not bullets)
    [ ] §7 each threat → short paragraph
    [ ] §8 commitments wording finalised after body complete
    [ ] §9 conclusion prose authored
    [ ] §10 references verified per PROCESS.md gate #9; DOIs minted
    [ ] AI-assistance declaration added (PROCESS.md gate #10)
    [ ] Frontmatter status → STABLE; version pinned
-->
