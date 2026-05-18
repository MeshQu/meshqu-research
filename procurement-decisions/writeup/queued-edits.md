# Writeup queued edits — for the post-distance editing pass

> Captured from Sam's editorial review of the assembled draft (2026-05-18).
> These are stylistic / register edits, NOT numerical corrections.
> Numerical corrections were applied immediately; see commit history on `writeup/main.md`.
>
> Per Sam: "do not rush directly into the editing pass immediately after drafting."
> Apply these only after stepping away from the draft for at least one cycle.

## Voice anchors — DO NOT EDIT during the pass

Sam flagged these sentences as load-bearing rhetorical anchors. They are protected. If the editing pass touches surrounding text, re-read against these for tone-match rather than altering them.

- §5a closing: *"The 30% proxy / 29% absent fraction is the substrate honesty in numbers."*
- §5b worked example close: *"Agent names every issue MeshQu finds. Both agree the record warrants attention. Verdicts read 100% disagreement."*
- §5b pattern-at-scale: *"What the corpus measures is two systems with different verdict spaces examining the same evidence."*
- §5b counterfactual close: *"The agent's caution is not generic noise. It correlates strongly with records the policy would have produced REVIEW for if the rules had been authored as a verdict gradient rather than a binary cliff edge."*
- §6 worked-example close: *"The disagreement is not about the facts. The disagreement is about how to respond to incomplete facts."*
- §6 evidence-incompleteness key sentence: *"The agent's REVIEW class is a compressed encoding of 'I cannot verify what I cannot see' — a verdict primitive the binary policy did not have."*
- §6 generalisation line: *"rule engines treat missing evidence as either pass or fail; competent reviewers treat it as a question."*
- §6 close: *"Reconstruction is not proof. Replay is."*
- §6 final: *"Treating reasoning as data, not as logs, is what makes that contract enforceable."*
- §7 close: *"a reader who wants stronger ground truth on any of these dimensions can produce it directly."*
- §8 close: *"The corpus is not assertion. It is verifiable evidence."*

## Edits queued (apply during the editing pass)

### §4 — dedup redundancy with §5a

> *Sam:* OCID dedup explanation currently appears twice in very similar language. Keep the detailed substrate explanation in §4. In §5a simplify to:
>
> *"After OCID deduplication (detailed in §4), the corpus contains 283 unique procurement records."*

**Status:** queued. Compresses §5a's first paragraph by ~3 sentences without losing the n=283-vs-n=300 anchor.

### §4 — product-proof sentence register

> *Sam:* The "doubly load-bearing" framing reads slightly product-marketing. Consider compressing to: *"This methodology also validates the MeshQu platform primitive at scale."*

**Status:** queued for editor's judgment. My current text doesn't actually use "product proof" verbatim — Sam may be reacting to the paragraph's overall density. Two ways to address: (a) Sam's suggested compression, or (b) leave the dense paragraph but compress the final two sentences. Editor picks during the pass.

### §5b — counterfactual transition

> Current: *"The interesting jump is the last row."*
> *Sam:* Replace with *"The pivotal shift occurs in the final counterfactual."*

**Status:** queued. Tightens register; consistent with surrounding tone.

### §5b — prediction framing

> Current: *"The prediction captured the wrong failure mode — disagreement did occur heavily, but its shape was non-commitment, not over-permissiveness."*
> *Sam:* Sharpen to *"The prediction anticipated the wrong failure mode. The corpus reveals a structural divergence rather than a simple error rate."*

**Status:** queued. Sharper. Drops the "did occur heavily" qualifier and reframes from "wrong failure mode" to "structural divergence." Editor consider whether to fold Sam's phrasing as-is or thread it into the surrounding paragraph.

### §9 — open-ended research programme close

> *Sam:* Add a small closing sentence to signal the three-experiment ladder is part of an open-ended research direction, not a finite roadmap. Example:
>
> *"Experiment 3 is the third piece in an open-ended research programme; further work will follow as the methodology develops."*

**Status:** queued. Placement: after the "passive reviewer → context-aware reviewer → governed investigative agent" summary line, before the cross-domain paragraph. Optional but likely strengthens the framing.

### Appendix A — P3 status wording

> Current: `**Refuted**`
> *Sam:* Slightly stronger than the body text supports. Use *"Premise unmet"* / *"Untested under alternate conditions"* / *"No citation behaviour observed"*.

**Status:** queued. Recommended: *"No citation behaviour observed under this model/prompt/temperature; prediction's premise unmet, alternate conditions untested"*.

### Appendix A — P6 status wording

> Current: `Under-tested`
> *Sam:* Use *"Deferred"* / *"Substrate-limited"* / *"Insufficient sample"* and explicitly note the prediction remains open for future runs.

**Status:** queued. Recommended: *"Substrate-limited — too few direct-award records to evaluate at meaningful sample size; prediction remains open for future runs against a substrate that produces a denser direct-award distribution"*.

## Title — three candidates evolved

Original three (preserved in main.md frontmatter):

1. "300 AI procurement decisions, signed and verifiable" (current default)
2. "What an AI agent gets wrong about procurement compliance, and what the receipts say"
3. "An audit trail for AI decisions: a teardown of 300 procurement reviews"

Sam's editorial review proposed three additional candidates closer to the paper's evolved conceptual centre:

4. "When AI hedges and policy commits: 300 signed procurement decisions"
5. "Two systems, one corpus: what 300 signed receipts say about AI-policy disagreement"
6. "The disagreement isn't where you think: 300 procurement decisions, agent vs policy"

**Status:** Sam's call. Title 2 reads weakest against the actual corpus (the agent didn't fundamentally "get wrong" — it didn't commit). Titles 4–6 are closer to §5b's conceptual centre. Title 1 is safest / most-newsy. Pick before publication.

## Process queue (per Sam's "suggested next sequence")

1. ~~Cross-reference verification~~ — done 2026-05-18; numerical errors caught + fixed (this PR)
2. Appendix A number verification — partially done (top-level counts verified; status-wording edits queued above)
3. Appendix B screenshot selection — Sam's visual judgment; pick ~6 from `results/runs/dry-run-7ddf7274-…/screenshots/` (152 captures) following Sam's operational narrative cue: run start, mid-run flow, stable execution, end-state verification
4. **Step away briefly** — Sam's explicit recommendation
5. Return for final editing pass with fresh eyes — apply queued edits above, voice anchors stay protected, watch for register drift

## Outstanding items not in queue

These were flagged in the assembled draft's "editing notes" section. Listed here for visibility, not for the editing pass specifically:

- Independent reader review before publication
- Cross-reference second pass after the editing pass (in case prose changes introduce new §N drift)
- Final word-count check (~4,850 currently; outline budget ~4,400; overage in §1 + §9 deliberate; editor may further trim)
