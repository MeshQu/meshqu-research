# Context-gradient ladder — design

## The ladder

| Level | Name | What the agent sees beyond L0 | Approx. payload size |
|---|---|---|---|
| **L0** | Baseline (= E1) | Nothing — record fields + per-field provenance envelope only | 0 tokens added |
| **L1** | Domain summary | A ~100-word prose description of the policy *territory* (no rule codes, no thresholds) | ~150 tokens |
| **L2** | Named rules | The six rule codes + one-line semantic descriptions (no thresholds, no `when` clauses) | ~250 tokens cumulative |
| **L3** | Receipt precedent | 3–5 Decision Receipts from MeshQu-evaluated comparable records (showing the verdict-with-violations on similar substrate) | ~1,500 tokens cumulative |
| **L4** | Full policy | The full ratified policy JSON — all 6 rules with their `condition`, `severity`, `when` clauses, NA-reason templates | ~4,500 tokens cumulative |

Each level is **strictly additive**. L4 sees everything L0 saw plus L1 plus L2 plus L3 plus the policy text.

## Why the L1 vs L2 distinction is load-bearing

It answers a question worth measuring directly: **do regulated firms need to build rule repositories, or can they paste their compliance manual into the system prompt and get the same behaviour?**

- L1 is "describe the policy territory in prose" — the path of least engineering investment. If L1 produces materially better verdict commitment than L0, organisations can encode governance in plain language and skip the rule-engine work.
- L2 is "name the rules and their shapes" — the path that requires a structured rule repository but stops short of full policy text. If L2 outperforms L1 by a meaningful margin, the rule-repository investment is justified.
- L4 is "the full policy" — the path that requires the rule engine AND the policy authoring discipline. If L4 outperforms L2 by a meaningful margin, the full MeshQu-style governance authoring is justified.

The slope from L1 to L2 to L4 is the data that scopes the engineering investment.

## Payload shapes

### L0 — Baseline (no addition)

The agent receives the same prompt scaffold and the same record fields + provenance envelope that E1 used. No mention of "MeshQu", no mention of "policy", no rule codes. The agent is asked to review the procurement record.

This level exists as a re-run control. The L0 verdicts should match E1's verdicts within OpenAI's reproducibility band at temp 0. Any divergence is logged as a finding (and possibly closes E1's P4 deferral).

### L1 — Domain summary

Prepended to the user message as a `## Governance context` section. Locked text (any change to this string requires a new predictions-lock tag):

> *"You are reviewing this procurement record under a compliance policy applied by the buyer organisation. The policy governs UK public-sector procurement in two regimes — the Procurement Act 2023 (post-24-February-2025 awards) and the Public Contracts Regulations 2015 (pre-24-February-2025 awards). It covers: publication timing obligations, contract-value authority thresholds, supplier debarment screening, conflict-of-interest declarations, procurement-method documentation (open tender or justified direct award), and modification-cap limits on awarded contracts. Your verdict should reflect whether the record satisfies this policy area; you do not have the rule definitions themselves."*

No rule codes. No thresholds. No structured payload. This is what a compliance manager would say to a junior reviewer in the hallway.

### L2 — Named rules

L1 text plus a section naming the six rules:

> *"## Rules in force*
>
> *- PROC-001-S53 — Publication-delay timing*
> *- PROC-002-AUTHORITY — Contract-value authority threshold*
> *- PROC-003-DEBARMENT — Supplier exclusion list*
> *- PROC-004-COI — Conflict-of-interest disclosure*
> *- PROC-005-OPEN-TENDER — Open-procedure or justified-direct-award*
> *- PROC-006-MOD-CAP — Modification-value cap*
>
> *The rule codes are the canonical identifiers. Each rule applies binary judgement based on the record's field values. The agent does not see the thresholds or applicability conditions."*

This level names the rule territory without giving the rule semantics. Question being answered: does naming the categories sharpen the agent's reasoning even without the rules' content?

### L3 — Receipt precedent

L2 text plus 3–5 Decision Receipts from MeshQu-evaluated comparable records. Format: receipt summary blocks, one per precedent, listing record fields, MeshQu verdict, named violations, the agent's recommended_action from E1 (so the agent sees its own prior reasoning on similar cases).

Selection logic: similarity by procurement value band, procurement method flag, and governance regime (PA23 vs PCR 2015). Reproducibility-critical — the same precedent set must be selected for the same target record across re-runs. Implementation: deterministic nearest-neighbour over a small feature vector, with the selection function committed to the runner code.

Constraint: the precedent records are drawn from E1's same 283-record corpus, NOT from a separate pool. This means each record's L3 precedents are *not the record itself* — exclude self by OCID. It also means precedents change per target record (each record has a different nearest-neighbour set).

Question being answered: does showing the agent how a comparable record was evaluated unlock commitment? This is the closest analogue to "case law" reasoning the experiment can construct without explicit policy text.

### L4 — Full policy

L3 text plus the full ratified policy JSON for snapshot `cbf12348-…`, formatted as a structured `## Policy` block. All six rules, all `condition` operators, all `when` clauses, all `severity` markers, all NA-reason templates.

This level is the maximum-context floor: the agent has everything MeshQu has, except MeshQu's verdict on the target record itself (that would be a leakage). The agent is asked to produce its verdict given the policy.

Question being answered: with full policy in hand, does the agent converge on MeshQu's verdict — and if so, is the convergence reasoned (judgment) or paraphrased (echo)?

## Additivity invariant

Each level *adds* to the previous, never replaces. This means:

- The L0 prompt is the floor. Every higher-level prompt contains it verbatim.
- Adding context never removes the earlier context. The agent at L4 has seen the domain summary (L1), the rule codes (L2), the precedents (L3), and the full policy (L4).
- The verdict at level N is therefore a function of the *cumulative* context through level N, not the level's marginal payload alone.

The alternative — non-additive ladders where each level *replaces* the context — would let us isolate the marginal contribution of each layer but at the cost of comparability across levels. The chosen ordering preserves the cleaner cross-level trajectory at the cost of marginal-contribution isolability. The trade-off is documented; if the data demands it, a follow-up experiment can run a non-additive variant.

## Token-cost projection

Approximate per-record token consumption (input only; output is held constant across levels):

| Level | Cumulative tokens per call |
|---|---|
| L0 | ~800 (base prompt + record + provenance) |
| L1 | ~950 |
| L2 | ~1,050 |
| L3 | ~2,300 |
| L4 | ~5,500 |

Across 283 records: roughly 3.0M input tokens for the full grid. At `gpt-5.4-2026-03-05` rates this is well within budget but the smoke run will confirm before committing.

## What gets locked at `v0.2-predictions-locked`

This document is the locked specification. Specifically:

- The 5 levels (no more, no fewer)
- The L1 prose verbatim (the "Governance context" string)
- The L2 rule-list format and content
- The L3 precedent-selection function (committed in code at lock time)
- The L4 source: the JSON of policy snapshot `cbf12348-…` as fetched from MeshQu at lock time, persisted to `policy/policy-snapshot-cbf12348.json` in this repo for reproducibility
- The additivity invariant

Any post-lock change to this document is recorded in `decision_log.md` with the same defensibility analysis as E1's PROC-004-COI clarification: was a corpus already collected at the time of the change, what did the change affect, what stayed frozen.
