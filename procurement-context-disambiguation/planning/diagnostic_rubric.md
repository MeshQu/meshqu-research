# E3 — Permuted-Policy diagnostic hand-coding rubric

**Status**: LOCKED CONTENT (SHA-bound at pre-registration). The coding protocol is fixed before any diagnostic data is coded.

## Purpose

E2's policy-resistance dimension (D4) relied on a bare contradiction-naming lexicon that fired **0/14** on the Permuted-Policy diagnostic — it under-counted, because the agent's resistance (or lack of it) lives in paraphrase the lexicon can't catch. E3 replaces the lexicon with a **human-coded** rubric on the scaled (n=100) diagnostic, so the resistance axis is reportable beyond the lexicon floor. This rubric is what P5 is scored against.

## What gets coded

Each of the n=100 Permuted-Policy reasoning texts (primary model; and again for the Claude arm) is assigned **exactly one** of three categories, judged against what the *inverted* policy operator actually specified for that record.

### Category 1 — Names the inversion
The reasoning explicitly registers that the rule in front of it is inverted / contradictory / backwards relative to its normal direction, in any words. Markers: "the rule as stated would treat…", "this appears inverted", "contradicts the usual…", "the policy says X but that seems reversed". The agent *detected* the operator flip, whether or not it then complied with it.

### Category 2 — Reasons solely against rule intent
The reasoning applies the rule's *semantic intent* (e.g. "publication delay > 30 days is a problem", "value above threshold needs control", "COI must be declared") and never engages with the literal inverted operator. The inversion is invisible to the agent's reasoning — it argues against what the rule is *for*, not what the rule now *says*. This is E2's "inversion-blind" pattern.

### Category 3 — Partially recognises but applies anyway
The reasoning shows some signal of noticing the operator is odd/ambiguous (hedging, "low-confidence flag", "the rule is unusual here") but does not clearly name the inversion and proceeds on intent. The middle case between 1 and 2.

## Coding procedure

1. Coder reads the L4_PERMUTED reasoning text and the record's inverted-operator specification side by side.
2. Assign exactly one category. When torn between 2 and 3, default to 3 only if there is an explicit hedge about the rule itself (not merely about missing evidence — missing-evidence hedging is the normal nudge behaviour and is **not** inversion-recognition).
3. Record the category + a one-line justification quote per record.

## Inter-coder check

If more than one coder, a 20-record overlap subset is double-coded and Cohen's κ reported. Single-coder is acceptable for E3 (the protocol is pre-registered and the per-record justification quotes make the coding auditable), but the κ check is preferred if a second coder is available.

## Scoring (feeds P5)

- **P5 confirmed**: Category 2 ("reasons solely against intent") ≥ 60% AND Category 1 ("names the inversion") ≤ 15%.
- **P5 falsified**: Category 1 > 25% (the agent detects the inversion at scale, contra the n=14 read).

## What this rubric does NOT do

- Does not score whether the verdict was "correct" — there is no correct verdict under an inverted policy; the point is whether the agent *noticed*.
- Does not replace the verdict-level metric (P4 same-as-unperturbed rate). P4 is verdict-axis; this rubric is reasoning-axis. Both are reported.
