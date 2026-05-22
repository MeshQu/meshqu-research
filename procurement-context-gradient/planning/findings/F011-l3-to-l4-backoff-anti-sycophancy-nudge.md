# F011 — L3 → L4 backoff: L4 anti-sycophancy nudge re-asserts caution on ambiguous records

**Status**: Confirmed (qualitative; P3 quantitative DENY-commitment was confirmed at 53.3%, which bears on this finding indirectly)
**Source experiment**: E2 (procurement-context-gradient) Phase 2 corpus `phase-2-20260522-101324-Z`
**Pre-registered prediction**: P3 (≥30% DENY commitment on MeshQu's DENY records at L4) is the closest pre-registered touchpoint and is confirmed at 53.3%. The L3→L4 *backoff* itself was not pre-registered as a specific direction — the design assumed monotonic increase in commitment (P1/P2) — but the differential-obedience pattern (high on unambiguous, low on ambiguous at L4) IS the experiment design's "healthy result" signature.
**Authored**: 2026-05-22
**Restraint discipline**: The word "anti-sycophancy" appears in this finding's title because it is the literal name of the nudge in the L4 envelope text. Per taxonomy v1.1 §1.5, "sycophancy" appears in this document only as part of the nudge's pre-existing name (it is the L4 envelope author's choice of vocabulary) and inside scare quotes when contrasted with the restrained framing. This finding makes no claim that the agent was being "sycophantic" at L3 — only that the L4 nudge does the work the nudge was named for.

## Finding

Between L3 (precedents) and L4 (full policy + nudge), the agent backs off 46 of its 107 L3-emerged DENYs to REVIEW. The backoff concentrates on **ambiguous-rule records** — most dramatically on PROC-005-OPEN-TENDER (missing-method records): L3 commits DENY on 29/40 (72.5%), L4 commits DENY on 1/40 (2.5%). On unambiguous-rule records the backoff is much milder (PROC-001-S53 L3 50/53 DENY → L4 42/53 DENY; PROC-002-AUTHORITY L3 27/44 DENY → L4 30/44 DENY — slight *increase*). The qualitative reading of L4 reasoning on backed-off records is consistent: the agent names the missing-metadata gap explicitly (*"the COI declaration field is absent from this substrate"*, *"no linked direct-award justification"*) and concludes REVIEW pending evidence rather than DENY on suspicion. **The L4 envelope's "anti-sycophancy" nudge is doing the work it was named for** — re-asserting caution on records where the agent's L3 commitment outran the evidence.

## Evidence

- Corpus citation: `procurement-context-gradient/results/notebook/cross_level_analysis/04-ambiguity-segmented-obedience.md` §"Table C — L4 obedience per class" + §"Per-primary-rule obedience at L4"; `06-per-rule-shifts.md` §"PROC-005-OPEN-TENDER (n=40)"
- Numbers (with units, with denominators):
  - L3 → L4 DENY-to-REVIEW backoff (n=107 L3-DENYs): **46 records back off to REVIEW**, 61 records hold DENY
  - PROC-005-OPEN-TENDER swing (n=40 records, ambiguous-rule class): **L3 DENY 29/40 (72.5%) → L4 DENY 1/40 (2.5%)** — a 28-record / 70.0-pp swing
  - PROC-001-S53 swing (n=53, unambiguous): L3 DENY 50/53 (94.3%) → L4 DENY 42/53 (79.2%) — 8-record / 15.1-pp backoff
  - PROC-002-AUTHORITY swing (n=44, unambiguous): L3 DENY 27/44 (61.4%) → L4 DENY 30/44 (68.2%) — 3-record *increase*
  - L4 differential obedience: **57.1% on unambiguous-rule records (n=7) vs 2.5% on ambiguous-only records (n=40)** = +54.6pp differential (`04-ambiguity-segmented-obedience.md` §"Table C")
  - L4 multi-rule (co-firing) records (n=90): 75.6% obedience at L4 — the agent commits when both classes of rule fire on the same record
- Worked example (PROC-005 backoff): the per-rule shift table in `06-per-rule-shifts.md` shows 29/40 → 1/40 explicitly. A typical reasoning text on one of the backed-off records reads at L3 as *"missing open-procedure marker and no linked direct-award justification — material non-compliance with PROC-005"* (DENY) and at L4 as *"the conflict-of-interest declaration is unavailable on this substrate and the selective method with no linked direct-award justification is a known false-negative area, so the audit trail is incomplete"* (REVIEW). The substrate did not change between L3 and L4. What changed is that L4's policy text contains the explicit nudge that absent fields do not constitute evidence of violation. (See worked-example texts in `05-reasoning-text-drift.md` §"Stable-REVIEW exemplar" for the L4 voice on this kind of record.)
- The differential-obedience pattern is the design's "healthy result" signature — see `behavioural_taxonomy.md` Dimension 1 prose and Dimension 3 prose. The corpus produces it.

## Interpretation

Two readings are visible and both are honest:

- **Reading A (anti-sycophancy nudge working as designed)**: the L4 envelope contains nudge language asking the agent to recognise the missing-metadata gap by name. On records where L3 committed DENY on the basis of "this looks like a non-open procedure" or "no COI declaration visible", L4 teaches the agent to ask *"is the field absent because it shouldn't be there, or because the substrate doesn't surface it?"* and to default to REVIEW pending evidence. The PROC-005 swing is the cleanest demonstration. Under Reading A the experiment's L4 design choice is vindicated — the nudge is load-bearing and doing precisely the epistemic-discipline work it was specified to do.
- **Reading B (L4 over-corrects on the ambiguous-rule axis)**: 29 → 1 is a 97% backoff. That is a large swing for a single rung. Even granted that L3 may have been over-committed, dropping all but one PROC-005 DENY raises the question: is L4 teaching the agent to *recognise* a missing-metadata gap, or to *defer* on any record where any rule has ambiguous evidence? The latter is a different (and less helpful) skill. If E3 introduces records where the missing-metadata gap is *genuine evidence of non-compliance* (rather than substrate-surfacing noise), the L4 nudge could backoff in a direction the experiment does not want.

**Commitment**: this finding reports both readings rather than picking one — the 57.1% unambiguous-rule obedience vs 2.5% ambiguous-rule obedience at L4 (Table C) is in the *healthy direction* the experiment design predicted, which weakly favours Reading A. But the magnitude of the PROC-005 backoff (29→1) is too large to wave through without flagging it as Reading B's open question. The taxonomy v1 was designed assuming a healthy result would land at "high obedience on unambiguous + meaningful obedience-with-uncertainty on ambiguous"; the corpus produces "high obedience on unambiguous + near-zero obedience on ambiguous". The "near-zero" is in the right *direction* but its *magnitude* is something the writeup should explicitly acknowledge as an open question for E3 rather than narrate as unambiguous success.

The uncertainty-marker density at L4 (mean 0.17 hits per reasoning text, vs 0.01 at L3) supports Reading A: the agent's L4 reasoning *does* contain uncertainty language on the backed-off records, which is what a working nudge would produce. But the same density is also compatible with Reading B (the agent is hedging without specifically engaging with the rule). See `05-reasoning-text-drift.md` §"Aggregate text metrics".

## Implications for E3

- **The L4 nudge's calibration is testable**: an L4-without-nudge variant would isolate the nudge's contribution from the policy text alone. If L4-without-nudge looks like L3 (committed), the nudge is the load-bearing element; if L4-without-nudge looks like L4 (rebound), the policy text alone is doing the work.
- **A genuine-non-compliance-on-ambiguous-rule test**: introducing records where missing metadata is *evidence of non-compliance* (e.g. a record where regulation specifies "the absence of an open-tender flag means the procurement was direct-awarded") would test whether the L4 nudge backs off appropriately or over-corrects.
- **PROC-005-class records are the load-bearing diagnostic** — the corpus shows that the model's behaviour swings most violently here. E3 should weight its record selection toward this class to get tighter error bars on the backoff direction.

## Anti-claims

- This finding does **not** establish that the L4 nudge is "safe" in general. It establishes that on PROC-005-class records in this corpus, the nudge dominates the precedent-priming and produces a REVIEW-leaning verdict. Whether the same nudge is safe under different substrates, different rule types, or different precedent compositions is open.
- This finding does **not** call the agent "sycophantic at L3". The agent's L3 commitments are not all wrong — many overlap with MeshQu's DENYs. The claim is structural (the L4 nudge re-asserts caution on a specific record class), not normative about L3.
- This finding does **not** establish that 79.2% obedience on PROC-001-S53 is the "correct" level. It establishes the level. Whether 79.2% is too high, too low, or right depends on a calibration target the experiment does not specify.
- This finding does **not** support a moat-story reading where MeshQu's policy text is "uniquely effective" — the L4 envelope is one possible policy text; other phrasings might produce different backoff magnitudes. The finding is about *this* L4, not about policy-text-effectiveness in general.
- This finding does **not** conflict with F008. F008 says L3 is where the first behavioural break lands; F011 says L4 partially un-does the break on the ambiguous-rule slice. Both are simultaneously true.
