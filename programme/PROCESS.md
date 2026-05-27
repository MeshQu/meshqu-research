# Programme process — research methodology spec

**Status**: working document. Updated after each publication.
**Programme**: MeshQu Research Programme.
**Published outputs to date**: MRP-2026-02 (E1 — procurement-decisions, published 2026-05-18); MRP-2026-03 (E2 — procurement-context-gradient, in publication).

This document captures the process discipline applied across the programme. It is a working spec, not a polished publication. It evolves as the programme accumulates evidence about what works and what creates friction. Each gate below exists because we either started with it (and it held up) or added it after a specific friction surfaced.

Two principles run through everything below:

1. **Discipline is the contribution.** The papers treat anti-claims and pre-registration as load-bearing methodological contributions, not as defensive hedges. The process gates here apply the same principle to the workflow that produces them.
2. **Restraint, made operational.** Each gate is a procedural commitment that costs something at execution time and pays off in credibility downstream. Where a gate stops paying off, it gets removed.

## What's working — load-bearing patterns

These have held across both published papers and should carry forward unchanged.

- **Pre-registration with a locked tag and explicit falsification criteria.** Predictions, ladder content, prompts, and policy snapshot are SHA-bound and tag-anchored before any data is collected. Falsification criteria are numeric and segment-specific. When predictions break, they break informatively — naming the direction the corpus actually showed against the direction the lock anticipated.
- **Anti-claims as a first-class section.** Every finding lists what it does *not* establish, alongside what it does. Surfacing the limit makes the positive claim more credible, not less.
- **Two-readings discipline.** Where the corpus admits multiple structurally plausible interpretations, the writeup reports both, commits weakly when the pattern weakly favours one reading, and names the experiment that would settle the question. Preservation-of-alternatives is the load-bearing voice.
- **Cross-repo scope separation.** Research artefacts (corpus, notebooks, writeups, findings, decision logs) live in the research repo. Publication artefacts (rendered PDFs, doc-engine sources, styling) live in the publication repo. The boundary is enforced, not aspirational.
- **Reproducibility infrastructure as a layered substrate.** Three layers — artefact (signed receipts + public verification), pre-data discipline (locked prompts + pre-registered predictions), post-data discipline (anti-claims + structured findings) — together form the reproducibility architecture each paper publishes against.
- **Hand-off artefacts pattern.** Cross-session work is brokered through portable input documents (figure specs, reader briefings) rather than shared state. Each session reads its inputs and reports back outputs; no session edits another's primary repo.

## Process gates

Each gate exists because a specific friction surfaced during E1 or E2. Each is framed as a forward-looking commitment. The cost of each is small at execution time; the cost of not having it is paid once per paper at the worst possible moment.

### 1. Brief verifies current state before pinning anchors

Any task brief — for a session, an agent, or future-self — opens with a verification step that re-reads the current state of the file before pinning section numbers, line ranges, figure labels, or other position-dependent references. Briefs written against stale mental models are the most expensive class of error in the programme; the fix is a one-line preflight, not a heroic recovery.

### 2. Phase-boundary number reconciliation

At every phase boundary, provisional figures (counts, percentages, run telemetry) are frozen and reconciled against the on-disk artefacts before any number is quoted in a brief, headline, or downstream artefact. Provisional numbers from one phase do not propagate into the next without a fresh read.

### 3. Structural-parity checklist (live document)

A living checklist of every structural element the programme's published papers carry — sections, appendices, declarations, conventions, hash-truncation rules, capture counts, frontmatter keys, voice-anchor sentences. Lives at [`STRUCTURAL-PARITY.md`](./STRUCTURAL-PARITY.md). Updated after each paper publishes. Mandatory pass-through before any paper claims publication-ready.

### 4. Cross-repo edit scope convention

Source markdown edits happen in the research repo. Rendering, doc-engine, and publication artefacts live in the publication repo. The boundary is documented in each repo's contributor guide. Any brief that requests a cross-repo edit is misrouted by construction and should be split, not blanket-authorised.

### 5. Pre-publication bundled review pass

Before triggering the publication-side render, one comprehensive pre-publication pass against the structural-parity checklist. Catches missing sections, drifted conventions, and capture-count discrepancies in a single bundled brief — not in trickled discoveries across multiple round-trips.

### 6. Stop-editing gate after personal-edit pass

After the author's personal editing pass completes, further changes require an explicit trigger: independent-reader feedback, a factual error, or a structural-parity checklist item. Refinement-for-its-own-sake is the failure mode this gate guards against.

### 7. Default isolation for parallel agent work

Any task that dispatches parallel agents (e.g. a build pack with multiple independent packages) uses isolated workspaces by default. Shared-workspace parallel execution is opt-in and requires explicit justification.

### 8. Title commitment at the pre-registration lock

The publication's title — or a deliberate placeholder with stated intent — is committed at the pre-registration lock boundary. Late-stage title churn is a smell; the lock pins it early.

### 9. Citation verification as a standard pre-publication gate

External citations are verified before they enter the writeup, not after. An independent verification pass (against original sources, not against training-data recall) is part of the pre-publication track. Unverified citations are cut, regardless of how rhetorically convenient.

### 10. AI-assistance declaration in every publication

Every paper in the programme carries a short declaration naming where AI tools were used in its production. In a programme on auditable AI decision-making, disclosing the assistance trail is the same primitive the papers advocate for — making the work legible at the point of the work.

### 11. Independent reader review is best-effort, not publication-blocking

Independent reader review strengthens a paper but is not a gate on publication. A finished paper is not held indefinitely for want of an available reviewer. Publication proceeds at `status: STABLE` once the structural-parity checklist passes; independent review is sought when a reviewer is available and folded in as a versioned revision (v1.1 / correction note) if it surfaces something substantive. The programme's correction primitive (errata, version bumps) makes review-after-publication a clean operation, not a compromise. The integrity the programme leans on — pre-registration, locked predictions, signed corpus, anti-claims — is load-bearing at publication time; the human reader is a strengthening pass, not the integrity mechanism.

## How this document evolves

This is a working spec. It is updated:

- After each publication ships, by the author, with any new gates or refinements that emerged.
- When a friction surfaces mid-flight that doesn't map onto an existing gate, by adding a new entry — framed as a forward-looking commitment, not a backward-looking failure note.

Gates that stop paying off in credibility downstream are removed, not kept for tradition. The point of the discipline is the discipline, not the document.
