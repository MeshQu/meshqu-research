# Independent-reader briefing — E2 writeup-DRAFT

Thank you for reading. This note sets the frame so your review time goes to the things that most need it.

## What you're being asked to do

Read `writeup-DRAFT.md` in full, then push back where you think the paper overclaims or underclaims. The paper is a draft for MRP-2026-03 in the procurement-decisions / procurement-context-gradient research programme. The first paper in the programme (E1 / MRP-2026-02) is the methodological baseline; this one (E2) varies governance context one rung at a time over the same frozen 283-record UK procurement corpus and reports the resulting behavioural shape.

## What the paper is claiming

- That, on this corpus and with this single locked agent, the L3 rung (precedent receipts) is where verdict commitment first emerges at scale — and that L4 (full policy text) partially reverts the commitment on ambiguous-rule records.
- That two of the pre-registered predictions (P1 monotonic REVIEW decrease, P2 monotonic agreement increase) are falsified in the inverted direction.
- That the 14-record adversarial Permuted-Policy diagnostic shows inversion-blind behaviour: the agent reasons against the rule's semantic intent rather than the inverted operator, on 13/14 records.

## What the paper is **not** claiming (the anti-claims to test)

This is the part most likely to be misread. The paper carries an explicit anti-claims section (§9) and a methodology-restraint section (§2.1). Both are load-bearing. Specifically, the paper does **not** claim:

- Causal mechanism for the L3 commitment (rung and content are confounded at L3 by design — the L3.5 variant in E3 is the disambiguator)
- Cross-model generalisation (single-model, single-substrate, single-policy)
- That precedent receipts "manipulate" the agent
- That the L4_PERMUTED inversion-blindness is "sycophancy" in the AI-safety-literature pinpoint sense (the agent isn't agreeing with the inverted policy — it's ignoring it)
- That the schema-level "actor-agnostic" property of the receipts has been empirically demonstrated across human vs AI originators (it has not — that's future work)

If any sentence in the paper feels like it's collapsing one of those anti-claims, flag it.

## Four challenges that would most usefully test the paper

1. **The L3-vs-L4 attribution.** §4 commits weakly to Reading A (precedent-rung anchoring) over Reading B (L4 nudge is load-bearing) and names L3.5 as the E3 disambiguator. Is the weak commitment too strong? Too weak? Is there a third reading the corpus also admits?

2. **The "authority-conditioned" qualifier in F010 / §6.** The structural label "inversion-blind authority-conditioned alignment" is preserved from the v1.1 taxonomy. The corpus doesn't yet separate which of three plausible causes is doing the work: authoritative framing of the policy text, the policy content itself, or the model's general training priors. Does the paper handle this scope-limit honestly enough?

3. **The §10 governance-memory interpretation.** §10 registers a provisional reading that signed decision receipts may function as transferable governance-memory artefacts — explicitly bounded as interpretation, not as a finding the corpus establishes, and explicitly noting that the actor-agnostic property is a schema property not a corpus-level demonstration. Does the framing hold up to scrutiny, or does any phrase tip into overclaim?

4. **The L4_PERMUTED diagnostic at n=14.** §6 reports the diagnostic as "a signal not a metric" and names a larger Permuted-Policy diagnostic (target n ≥ 100) as the E3 ask. Is n=14 too small to carry the rhetorical weight the paper places on it? Or is the explicit small-n flag sufficient cover?

## How to submit feedback

Inline comments on `writeup-DRAFT.md` in whatever form is easiest — Google-doc, markdown line-anchored notes, or a single doc with §-numbered notes. Brevity is fine. A page of sharp criticism is more valuable than five pages of measured agreement.

If a single sentence in the paper made you stop and re-read because it didn't sit right, that's the most useful signal — flag those by line.

## What's out of scope for your review

- The figures (Figures 1–6) are not yet rendered — they are spec'd in `figures-spec.md` for production by the iko-tools session. Imagine them at the callout points and review the prose around them.
- Typos and stylistic prose-polish are useful but secondary to the four challenges above
- The title (currently *"When precedents commit AI and policy pulls it back"*) is committed; structural feedback on it is welcome but not the primary ask
- The publication metadata block (MRP number, byline, DOI) is out of scope — handled by iko-tools

## Programme context (briefly)

- E1 (MRP-2026-02) established the corpus, the locked agent, and the baseline; published 2026-05-18.
- E2 (this paper) varies the governance-context ladder over E1's corpus; pre-registration locked under git tag `v0.2-predictions-locked` (commit `a8c6f47ded43e8d3e0b3e150eaa21e20a7688f0b`).
- E3 (planned, not run) introduces L3.5 (receipts-only), larger Permuted-Policy diagnostic, authoritative-vs-hypothetical framing axis, and cross-model replication — i.e. the experiments specifically designed to disambiguate the open readings this paper carries.

Thank you for taking the time.
