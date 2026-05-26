# Experiment 3 (E3) — planning directory

**Status**: scaffolding only. No content commitments yet.
**Directory name**: `procurement-e3/` is a placeholder. Rename to `procurement-<contribution-axis>/` once Sam commits to E3's scope (e.g. `procurement-context-disambiguation/`, `procurement-investigative-agent/`, etc., following the E1/E2 naming convention).

## Purpose

This directory will hold E3's planning artefacts, mirroring the structure used in `procurement-context-gradient/` (E2) and `procurement-decisions/` (E1).

## Why this exists before content

Per `programme/PROCESS.md` gate #1 (brief verifies current state before pinning anchors) and the broader programme discipline, the mechanical scaffolding (directory shape, decision-log skeleton, predictions placeholder) is independent of content decisions and can be ready before pre-registration lock. Content waits for:

- Reader feedback on E2 (may sharpen one of the open questions)
- Sam's scope decision (L3.5 + disambiguators vs investigative-agent variant vs both)
- Substrate decision (reuse 283-record corpus, expand, or new)
- Model decision (which model(s) for cross-model replication)

## Carry-forward design asks from E2

Recorded in E2's §8 (Implications for E3), §10 (What is justified, and what is not), and §11 (What's next). Consolidated here for reference; **none are committed for E3 yet** until Sam picks scope:

- **L3.5 receipts-only variant** — disentangles "agent committed because precedents are present" from "agent committed at the first rung with substantive content"
- **Larger Permuted-Policy diagnostic** — target n ≥ 100, with a hand-coded three-category reasoning rubric ("names the inversion in any words" / "reasons solely against intent" / "partially recognises but applies anyway")
- **Authoritative-vs-hypothetical framing axis** — isolates the "authority-conditioned" qualifier in F010 ("the policy states that…" vs "suppose a policy stated that…")
- **Cross-model replication** — Claude or Gemini as second model; tests whether the rule-intent prior is a property of this model or of the task class
- **Investigative-agent variant** (per §11) — the larger leap; may be E3 or deferred to E3.5/E4 depending on scope budget

## Process gates that apply (from PROCESS.md)

When content development starts, all ten gates in `programme/PROCESS.md` apply. Particularly load-bearing for E3 kickoff:

- **#1 Brief verifies current state** — applies from the first brief written for E3
- **#3 Structural-parity checklist** — see `programme/STRUCTURAL-PARITY.md`; E3's published paper must satisfy every item
- **#8 Title commitment at pre-registration lock** — pick a working title (with or without placeholder caveat) before locking
- **#9 Citation verification** — standard pre-publication gate; do not let citations enter the writeup until verified

## Files in this directory (as they get written)

| File | Purpose | Status |
|---|---|---|
| `README.md` | This file | Present |
| `decision_log.md` | Reverse-chronological journal of E3 decisions | Skeleton |
| `experiment_design.md` | Locked design at pre-reg boundary | Placeholder |
| `predictions.md` | Locked predictions + falsification criteria | Placeholder |
| `context_ladder_design.md` | (If applicable to E3) ladder rung definitions | Not created yet |
| `behavioural_taxonomy.md` | Taxonomy version applied to E3 | Not created yet |
| `phase_1_build_plan.md` | Build sequencing once design locks | Not created yet |

## What this directory is NOT

- Not a published paper draft (lives in `writeup/` once written)
- Not a corpus (lives in `results/runs/` once collected)
- Not a runner (lives in `runner/` once forked from E2 or built fresh)
- Not committed scope — E3 may end up smaller (just disambiguators) or larger (investigative-agent) than the carry-forward list above suggests
