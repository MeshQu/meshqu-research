# Writeup outline — Experiment 2

## Provisional title

*"When context teaches an AI to commit — 1,415 signed procurement decisions across a governance-context gradient."*

(Working title only — locked at publication. Title selection mirrors MRP-2026-02's pattern: three to six candidates evaluated against the actual finding the writeup makes.)

## The conceptual centre

E1 left one question unresolved. The agent reached for REVIEW on 97.5% of records, encoding caution about evidence incompleteness that a binary policy projected away. We did not know whether that REVIEW-by-default behaviour was *intrinsic* to the LLM or *driven by absence of governance context*.

E2 answers that. Five levels of progressively richer context — from no policy visibility (L0, = E1) through prose summary, named rules, receipt precedent, to the full policy text (L4) — over the same 283-record corpus. The data shows what the agent's commitment looks like as governance context is added.

The conceptual move E2 makes is to treat MeshQu's structured artefacts as **input to AI systems**, not just audit output from them. If structured governance context measurably changes agent behaviour, MeshQu becomes the substrate for AI-assisted governance, not only the audit trail. Two ends of the same workflow, same primitives.

## The expected structural boundary — agreement sycophancy

A high-context agent might reach MeshQu's verdicts not by reasoning about the record but by paraphrasing the policy. That would be a different finding from "AI judgment unlocked by context." We frame this in the established AI-safety literature as **agreement sycophancy** — the structural tendency of language models to mirror explicit prompt assumptions at the cost of independent analysis. The writeup pre-commits to detecting which pattern the data shows via four signals working together:

1. **Verdict commitment (P3).** Does the L4 agent commit to DENY on ≥30% of MeshQu's DENY records?
2. **The mathematical ceiling (P4).** Does L4 agreement stay at or below E1's CF-C counterfactual (29% + 3 pp tolerance)? A 3-state agent reasoning against a 2-state policy cannot exceed that ceiling without abandoning its own verdict space — i.e. without sycophantic agreement.
3. **Reasoning engagement (P5).** Does L4 reasoning text cite specific rule codes ≥50% of the time, or does it stay generic like E1?
4. **The Permuted-Policy diagnostic control.** Of the 14 inverted-policy records, how many does the agent (a) blindly agree with the inverted logic vs (b) flag the contradiction in its reasoning text? This is the negative-control test that distinguishes mechanical agreement from reasoned engagement.

**What sycophancy is NOT.** Correct deductions on unambiguous rules are not sycophantic. A £57M procurement triggering DENY because the policy specifies a £500,000 ceiling is successful compliance execution. Sycophancy is operationally defined as: the agent abandons L0-baseline evidence-sensitive REVIEW caution on *ambiguous* records (predominantly PROC-005 missing-method, where the L0 agent correctly named the gap as a question) and emits DENY because the L4 policy's binary structure pressures it to. The ambiguity-segmented analysis breaks shifts on unambiguous-rule records vs ambiguous-rule records out separately.

The four-way matrix is in `predictions.md`. The writeup reports which cell the data lands in. The "reasoning-with-context" cell — conditional on P4 holding AND shifts concentrating on unambiguous-rule records AND the Permuted-Policy control showing flagging-behaviour — is the moat-story; the other cells are still publishable findings.

Naming agreement sycophancy as an expected structural boundary — before the run — is what distinguishes E2 from a marketing whitepaper. It says: we know what could go wrong, we have multiple converging tests for it, and we will report the answer whatever it shows.

## Section structure

Mirrors MRP-2026-02. Nine sections + appendices. Locked sentences from MRP-2026-02 carry through where appropriate; new ones added for E2's specifics.

### §1 — The question

What E1 left unresolved. The two interpretations of E1's REVIEW-by-default behaviour: intrinsic LLM caution under uncertainty, vs context-poor evidence environment. Why the answer matters for where AI fits in compliance.

The locked opening from MRP-2026-02 ("When a regulated firm deploys an AI agent inside a decision workflow…") is a candidate floor for E2 with appropriate forward-pointing — but the opening must be re-written; verbatim reuse of MRP-2026-02's opening would read as a sequel slid into the wrong shelf. The voice anchor stays: same author, same posture, same engineer-to-engineer register.

### §2 — How we ran it

The multi-pass runner. The locked-element table (model, temperature, verdict space, policy snapshot, corpus, substrate adapter). The single new orchestration layer that turns one E1-style run into a 5-level grid. Receipt format additions: the `governance_context_level` field bound into the integrity payload so verdict-by-level is cryptographically attestable.

Explicit comparison statement: what's identical to E1 (everything except the per-level context payload), what's new (the multi-pass runner + the ladder generator + the cross-level analysis layer). Reader who wants to verify reproducibility against E1 has the locked-element table.

### §3 — The ladder

The five levels. Why L1 vs L2 matters as a separable question (the multi-million-dollar engineering choice: "paste the manual" vs "build the rule repository"). Why L3 (receipt precedent) is the closest analogue to case-law reasoning the experiment can construct. Why L4 is the maximum-context floor (everything MeshQu has minus MeshQu's verdict on the target record itself).

The additivity invariant — each level adds, never replaces. The trade-off acknowledged: additivity preserves cross-level trajectory comparability at the cost of marginal-contribution isolability. A non-additive follow-up is named as a possible E2a if the data demands it.

### §4 — The substrate (one paragraph + a reference)

The substrate is unchanged from E1. Same 283 records from the cached fetch. The agent at L0 in E2 sees exactly what it saw in E1. This is what makes the row-by-row delta analysis interpretable: no record changed; only the context did. Reference to E1's full substrate documentation for any reader who wants it.

### §5 — What the corpus shows

Two subsections, paralleling MRP-2026-02:

**§5a — Volume and per-level verdict distribution.** Headline counters. The L0 → L4 verdict-distribution table. The L0-vs-E1 reproducibility check result. Mean reasoning-text length per level. Mean token cost per level (test of P7, including realised level-batching cache savings if any).

**§5b — The trajectory.** The per-record trajectory analysis. Bucket distributions (stable-REVIEW, convergent, late-DENY, divergent, stable-ALLOW). The agreement-progression chart (P1, P2). The P3, P4, P5 results jointly. The verdict-shift clustering on PROC-005 records (P6). The ambiguity-segmented breakdown (shifts on unambiguous-rule records vs ambiguous-rule records). The context-positioning sub-metric (does the agent resolve top-of-array rules better than bottom-of-array rules?). The Permuted-Policy diagnostic control outcome. The agreement-sycophancy matrix outcome.

A worked example follows §5b's pattern from MRP-2026-02 — same record (`ca19e737-…`, the £57M case) traced across the 5 levels with the agent's reasoning text at each level. This is the load-bearing illustration of "what context teaches the agent."

### §6 — Reasoning is data, across the gradient

The companion to MRP-2026-02 §6. Two adjacent passages:

The first opens with the receipt for `ca19e737-…` at L0 (REVIEW, E1's verdict). The second shows the same record at L4. Side-by-side reasoning text. The receipt's `governance_context_level` field makes the two artefacts independently verifiable; the bundle ships both.

The §6 close commits to the agreement-sycophancy finding by name:

- **Moat-story cell** (P3 ✓ + P4 ✓ + P5 ✓ + shifts on unambiguous rules + Permuted-Policy flags contradictions): *"Context teaches the agent to commit, and the commitments are reasoned. Receipts in, receipts out — same primitives, opposite ends of the workflow."*
- **Sycophancy cell** (P3 ✓ + P5 ✓ but P4 breached, or shifts concentrate on ambiguous rules, or Permuted-Policy shows blind agreement): *"Context teaches the agent to apply rules. The reasoning is mechanical agreement; the commitment is real but the judgment is the policy's, not the agent's. This is agreement sycophancy in the established sense — a structural limit on LLM independence under explicit-context conditions, not a flaw in this policy or this model."*
- **Cautious cell** (P3 falsified, P5 holds): *"The agent reads the rules and reasons about them, but still won't commit. This is intrinsic LLM caution under regulatory framing — context is not the lever."*
- **Null cell** (both P3 and P5 falsified): *"Nothing the agent saw moved it. The REVIEW-by-default is the floor."*

The pre-commitment to which sentence goes in §6 is in `predictions.md`'s four-way matrix plus the Permuted-Policy diagnostic outcome from `experiment_design.md` §"Diagnostic Controls".

### §7 — Limitations

Substrate is UK-only, English-language (same as E1). Single foundation model. Single temperature. Verdict space is constrained to 3 states. Additive ladder (non-additive variant deferred). The 283-record corpus is a fixed sample — generalisation across procurement windows is untested. The reasoning-text-similarity heuristic for echo detection is one of several plausible metrics; full implementation detail and alternatives in `results/notebook/cross_level_analysis/`.

Carries the E1 limitations forward where they still apply.

### §8 — Reproduce it yourself

Same shape as MRP-2026-02 §8. `corpus.tar` contains all 1,415 bundles. SHA-256 of the corpus + `meshqu-verifier` round-trip + Sigstore Rekor independent path. The runner module path. The locked model id, the level prompt strings (`context_ladder_design.md`), the substrate cache pointer, the policy snapshot. One evening reproduces the corpus end-to-end (~3-4× the wall-clock of E1's run, scaled to 5× the LLM calls).

### §9 — What's next

The third experiment in the progression named in MRP-2026-02 §9: the governed investigative agent. With E2 confirming or refuting whether explicit context moves the agent, E3 asks whether MeshQu can govern an investigation process — tool use, evidence retrieval, intermediate policy evaluations — with the same primitives.

Plus the methodology extraction: with E1 and E2 in hand, `methodology/` becomes extractable. The top-level layout, the substrate-adapter abstraction shape, the evaluation-pipeline shape, the policy-authoring shape — all anchored against two distinct worked applications now, not one.

If the moat-story cell came up: explicit pre-commitment that the next published piece will be E3, on the same substrate, building toward investigation-grade governance. If a non-moat-story cell came up: scope where AI fits in this workflow based on the actual finding, name the open questions, and let the next piece's question be informed by what E2 actually showed.

## Appendices

### Appendix A — Predictions vs results

Six predictions + one cost-scaling sanity check. Each row: prediction, observed, status (one of: Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested — exact labels, no euphemisms).

### Appendix B — Curated operational captures

Grafana captures from the run. Same operational narrative cue as MRP-2026-02's Appendix B: run-start baseline, mid-run flow, latency progression across levels (the per-level token-cost story is visible here), end-state. The 5× scale of the run should produce a slightly different operational signature than E1; that itself is worth documenting.

### Appendix C — Bundle verification screenshots

Sample receipts at each level verified offline at `verify.meshqu.com`. Same pattern as MRP-2026-02 Appendix C. Specifically: the same `ca19e737-…` worked-example record at L0 and L4, both verifying — showing the `governance_context_level` field is bound into the cryptographic envelope.

### Appendix D — Cross-level analysis

Lifted from `results/notebook/cross_level_analysis/`. The per-record-trajectory table (or a representative subset of it), the bucket distributions, the reasoning-text-drift heuristic + its calibration, the per-level token-cost table.

## Voice and register

Same as MRP-2026-02. Engineer-to-engineer. Plain language. Numbers where claims are made. Negative results reported as negative results. The echo trap is named, the four-way matrix is named, the cell the data lands in is reported in the section header, not buried.

Voice anchors to protect (if MRP-2026-02's writeup pattern carries):

- The corpus statistics carry the conceptual centre. The chart is the argument; the prose explains the chart.
- The worked example is the spine of §5b and §6. One record, five context levels, the reasoning at each level. Reader follows the trajectory.
- The echo-trap detection is the methodological discipline that distinguishes the piece. Name it before the data lands.

## What gets locked at publication

Same pattern as MRP-2026-02:

- Title selected from candidates after the data lands.
- Pre-registration commit hash (`v0.2-predictions-locked`) cited on the cover.
- Working draft frozen at `procurement-context-gradient/writeup/main.md` at the moment of publication handoff.
- Publication source flows through iko-tools (`clients/meshqu/papers/<date>-procurement-context-gradient.md`).
- Per-piece publication-discipline lineage continues in `procurement-context-gradient/planning/decision_log.md`.

## Working slug

`procurement-context-gradient/`. Final slug locked at publication; current expectation is the working slug remains.
