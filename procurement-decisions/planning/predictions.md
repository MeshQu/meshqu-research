# Pre-registered Predictions

> **Pre-registration matters more than any other artefact in this experiment.**
> The credibility argument collapses if predictions are written after looking
> at results.
>
> When the predictions below are final, the commit hash + timestamp gets
> linked from the published writeup so any skeptical reader can confirm the
> predictions were locked in BEFORE the runs.

## Status

- [ ] Drafted
- [ ] Reviewed (Sam + optionally one advisor)
- [ ] **Locked** (no further edits without a versioned addendum below)
- [ ] Linked from writeup

## Lock procedure

1. When the predictions feel final, change the status box above to `[ ] Drafted [x] Reviewed [ ] Locked`.
2. After a 24-hour cool-down, set `[x] Locked` and commit. The commit hash + timestamp is what the writeup links to.
3. Any post-lock change is appended as a **dated addendum** at the bottom, NOT an edit. The addendum explains why the prediction shifted.

## Headline predictions

Stub structure. Sam fills in the actual numbers / qualitative bets before locking. Examples shown in italics, not commitments.

### P1. Agent-vs-policy disagreement rate

> *Example bet: 15–25% of agent-recommended ALLOWs will be DENYs under MeshQu's policy.*

What we expect:

- _N% disagreement (TBD)_
- Direction: agent over-permissive vs MeshQu (i.e. agent leans ALLOW, MeshQu leans DENY)

What would invalidate this:

- _Disagreement rate < 5%. agent is conservative; the experiment doesn't surface useful drift._
- _Or >50%. the policy is so strict it makes the agent's reasoning irrelevant; not informative either._

### P2. Rule-firing distribution

> *Example bet: `PROC-001-S53` and `PROC-002-AUTHORITY` will be the top-two violation drivers, accounting for >60% of MeshQu denials. (`PROC-001-S53` numerator is the proxy-identified PA23 subset, per the reporting boundaries in substrate.md.)*

What we expect:

- Top 2 violation drivers (TBD)
- Bottom rule(s). rules that fire rarely or never (TBD). Important to publish: a quiet rule isn't a bug, it just reflects the corpus.

### P3. Hallucinated citations

> *Example bet: at least 5% of agent reasoning narratives will cite specific regulatory clauses that don't exist or don't apply.*

The agent is **not given the policy text**, so it reasons from training data. When it cites specific clauses (FAR 6.302, EU Directive 2014/24/EU Article 32, etc.), it may invent or misapply them. We expect to find some.

What we expect:

- _N% of reasoning narratives contain at least one specific regulatory citation_
- _Of those, M% will be wrong (verified by spot-check)_

This prediction is **load-bearing for the writeup's "drift" framing**. If hallucinated citations are rare, the framing pivots to other drift types.

### P4. LLM non-determinism band

Foundation model providers are increasingly explicit that temperature 0 doesn't guarantee determinism. Batch-level variation, hardware variation, silent model updates. Pre-register an expected band, not a hoped-for stability rate.

> We expect verdict non-determinism in the 5–20% range across re-runs at temperature 0. We will report the observed rate honestly and discuss what this means for receipt-corpus reproducibility regardless of LLM stability.

This protects the writeup from an awkward pivot if observed non-determinism exceeds the hoped-for stability rate. The receipt corpus is reproducible even when the LLM substrate isn't. That's a stronger argument than "the LLM is stable" and it's the one MeshQu actually owns.

What we report:

- Observed rate vs the pre-registered band.
- Where the non-determinism concentrates. Verdict shifts vs reasoning-text drift with identical verdicts.
- What this means for the receipt as an audit primitive when the underlying LLM substrate isn't stable.

### P5. Bundle round-trip

> *Example bet: 100% of bundled receipts verify offline at verify.meshqu.com.*

Highest-confidence prediction. If this fails, it's a bug in the platform that we want to find.

If it fails on a meaningful subset, the experiment STOPS and we file fixes. Don't paper over.

### P6. Publication delay disagreement clusters on direct-award procurements

What we expect:

- The agent-policy disagreement rate on s.53 compliance is meaningfully higher for direct-award procurements than for competitive procurements (open tender, restricted, framework call-offs).
- Scope: predictions apply to the proxy-identified PA23 subset only, since s.53 only applies under PA23 (see Methodology scoping note above).

Theoretical prior:

- Direct awards under PA23 have a separate transparency-notice requirement (s.44 — published before contract award) that buyers may treat as substituting for the s.53 contract details notice (published within 30 days after contract award). The agent, reasoning without the policy text, is likely to conflate these — to read transparency-notice existence as evidence of compliance and miss the specific s.53 timing obligation.

What would invalidate this:

- <10 percentage point difference between direct-award disagreement rate and competitive-procurement disagreement rate. The 10-point threshold (revised from 5 points pre-sanity-check) accounts for the modest statistical power of the comparison given the substrate-constrained sample composition. Differences smaller than 10 points may exist in the underlying population but cannot be reliably distinguished from sampling noise at N=20-vs-N=280.
- Sample size scope: this prediction requires a minimum of 20 direct-award records and a minimum of 100 competitive-procurement records for the comparison to carry methodological weight. The direct-cell floor in experiment_design.md sampling subsection guarantees the former; the latter is satisfied by the 3×3 grid's natural construction from the above-threshold population. If the underlying disagreement-rate gap is large (the theoretical prior of s.44/s.53 confusion suggests it may be), the prediction is detectable. If the gap is small (a few percentage points), the experiment is honest about its limited power to detect it.

Relationship to P7:

- P6 and P7 form an explanatory pair. P6 identifies *where* disagreement clusters (direct awards); P7 identifies the *mechanism* (agent treats publication existence as compliance evidence without recognising the 30-day cap).

### P7. Publication-delay drift — agent unaware of 30-day statutory cap

When the agent recommends ALLOW on a Contract Details Notice published >30 days after award (PA23-subset records only), we predict that **>60% of agent reasoning narratives cite the existence of the published notice as evidence of compliance without recognising the 30-day cap exists.** Specifically: the agent treats "notice exists" as the compliance criterion rather than "notice exists AND is timely."

Theoretical prior: LLM training data is heavily weighted toward general publication-obligation principles and lightly weighted toward specific statutory time-windows. The agent likely knows there is a publication obligation under PA23; it likely does not know the specific 30-day rule from s.53. This is a binary, theoretically anchored, statute-specific prediction with a clean falsification criterion.

What we report:

- 30-day-cap-recognition rate vs the pre-registered 60% bet.
- Citation taxonomy: PA23 s.53 explicitly named / "Procurement Act 2023" cited without section / "publication obligation" cited without statute / "transparency notice" conflation with s.44 / no statutory anchor at all.
- For agents that do recognise the cap: whether the agent reasons about the cap correctly (citing 30 days) or approximately (citing a different window).

Invalidation: <20% of agent reasoning narratives miss the 30-day cap. Suggests the agent has been trained on enough PA23 commentary to know the specific obligation; the writeup's "training data weighted toward generality" framing pivots.

This prediction is **load-bearing for the writeup's section 5b worked example** — the corpus's strongest agent-misses-the-30-day-cap case becomes the walkthrough.

## Methodology scoping note

`PROC-001-S53` applies only to procurements governed by the Procurement Act 2023. Governance is identified via the contract-award-date proxy (`awards[0].date > 2025-02-24`), not a direct OCDS field — see [substrate.md](substrate.md) "Proxy-identified PA23 subset for PROC-001-S53" and [experiment_design.md](experiment_design.md) "Substrate analysis preceding pre-registration".

Predictions P6 and P7 are **scoped to the proxy-identified PA23 subset of the corpus.** Records with ambiguous governance (contracts awarded close to the commencement date where PCR transition arrangements may apply) are reported as a separate subset rather than excluded silently. The headline statistics report both totals.

## Predictions that are NOT here

Things deliberately not pre-registered (so we can describe them post-hoc without overclaiming):

- Specific anecdotes / case studies from the corpus. Those are illustration, not prediction.
- "Which buyer persona will find this most compelling." That's marketing intuition, not experiment evidence.
- Numerical effect sizes more precise than ~10-percentage-point bands. Pre-registering 17.3% would be false precision.

## Audit trail of changes (post-lock)

| Date | Change | Reason |
|---|---|---|
| (none yet) | | |
