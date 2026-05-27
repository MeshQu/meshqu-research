# Structural-parity checklist

**Status**: working document. Updated after each publication ships.
**Source**: extracted from MRP-2026-02 (E1) and MRP-2026-03 (E2) published structure.
**Gate**: every publication in this programme must pass through this checklist before claiming publication-ready (per `PROCESS.md` gate #3).

## How to use

Tick through every item below before triggering the final iko-tools render. Items present in both E1 and E2 are mandatory; items present in only one are convention-not-rule and require an explicit decision to skip.

Missing items are the most common late-stage discovery in this programme — drafting and confirming the checklist at the pre-publication boundary catches them before they become trickled iko-tools round-trips.

## Body sections (in order)

- [ ] **§1 — Abstract** (~250-450 words). Practitioner-stakes opening; methodology; headline result; falsifications; one-sentence anti-claim closing.
- [ ] **Errata / Correction callout** if any provisional numbers from prior phases were superseded.
- [ ] **§2 — Methodology**. Sub-sections:
  - [ ] Pre-registered hypothesis and locked predictions
  - [ ] Architectural choices that preserve evidential integrity
  - [ ] **§2.1 — Honest reframe** (what the locked frame anticipated vs what the corpus actually showed)
  - [ ] **§2.2 — Substrate provenance and integrity** (SHA fingerprints, signing kid, tenant ID, Ed25519 + Rekor)
  - [ ] **§2.3 — Relationship to prior experiment** (E1 cross-reference, in E2; E2 cross-reference, in E3+)
- [ ] **§3 — Predictions vs outcomes** (table-first; per-prediction disposition using locked vocabulary)
- [ ] **§4+ — Findings sections** (one per headline finding; each finding has worked example, two readings where applicable, structural confound discussion)
- [ ] **§N — Methodological findings (meta-layer)** — corpus-clean parse correction, lexicon limits, two-readings discipline as programme method
- [ ] **§N+1 — Implications for next experiment** (specific design asks)
- [ ] **§N+2 — Anti-claims** (dedicated section; each bullet states what is NOT established and why)
- [ ] **§N+3 — Synthesis** with sub-sections:
  - [ ] A provisional interpretation (the speculative reading the corpus opens, bounded)
  - [ ] What is justified, and what is not
  - [ ] Pre-publication checklist (out-of-scope items deferred to publication mechanics)
- [ ] **§N+4 — What's next** (E1→E2→…→En arc as a coherent progression, not a list of disconnected follow-ups)

## Closing elements (in order, after a `---` divider)

- [ ] **Declaration of AI assistance** (one short paragraph; methodologically obligatory)
- [ ] **References** (numbered; each entry maps to an inline reference in the body; external citations carry arXiv ID / DOI / URL)

## Appendices (in order)

- [ ] **Appendix A — Pre-registration provenance**:
  - [ ] Git tag (`v0.X-predictions-locked`)
  - [ ] Tag commit SHA
  - [ ] Locked-prompt SHA-256 fingerprints (one per ladder rung if laddered)
  - [ ] Agent prompt scaffold SHA-256
  - [ ] Policy snapshot SHA-256
  - [ ] Tenant ID (public)
  - [ ] Receipt signing kid (public)
  - [ ] Foundation model + temperature
  - [ ] Runner commit
- [ ] **Appendix B — Curated Grafana captures** (5 captures: run-start + 3 mid + run-end; each with operational caption)
- [ ] **Appendix C — Behavioural taxonomy reference** (if a versioned taxonomy applies)
- [ ] **Appendix D — Reproducibility instructions** (branch / tag, re-derivation steps, independent receipt verification, no-credentials-needed claim)

## Voice conventions

- [ ] Practitioner-legible vocabulary (per `feedback_writeup_voice.md`). Plain alternatives over precious adverbs; technical precision preserved where load-bearing.
- [ ] Voice-anchor sentences identified per-section and preserved through edit passes.
- [ ] Two-readings discipline named explicitly where the corpus admits multiple structurally plausible interpretations.
- [ ] Restraint vocabulary (anti-claims, "Confirmed/Falsified/Inverted/Refuted/Deferred/Under-tested", explicit confound discussion).
- [ ] "Correction" not "Errata". "Obvious" not "colloquial". "Different operational consumers" not "heterogeneous consumers". (Live list; add as more emerge.)
- [ ] Practitioner takeaway as a blockquote callout in the synthesis section.

## Hash / identifier conventions

- [ ] `commit_hash` frontmatter: 7 chars (no ellipsis). Renderer truncates defensively.
- [ ] `corpus_sha256` frontmatter: 16 chars in source, renderer slices to 12 + ellipsis.
- [ ] Full hashes in Appendix A only.
- [ ] Tenant ID and signing kid published verbatim (public-by-design).
- [ ] Private keys, API keys, credentials NEVER in source — `.env.live` gitignored at repo root.

## Figures (in document order; numbered contiguously 1..N)

E2 baseline: 5 mandatory + 1 supporting. Each carries a `**Figure N — Title.**` callout in the body with a one-sentence caption + data source. iko-tools renders the figure inline at that callout point.

- [ ] Per-level verdict distribution (stacked bars) — if laddered
- [ ] L0→Ln transition flow (Sankey/alluvial) — if laddered
- [ ] Commitment-emergence (% commitment by rung) — the load-bearing "structural break" graphic
- [ ] Worked-example trajectory (single record, all rungs side-by-side)
- [ ] Adversarial-diagnostic per-record summary (table-as-figure)
- [ ] Supporting / rule-class breakdown (optional if space-constrained)

Visual register: Anthropic system-card / IBM Research / GDS register. Restrained, systems-oriented, research-grade. No glossy AI imagery, no neon, no decorative gradients.

## iko-tools rendering

- [ ] Frontmatter complete (per E1 convention: `type`, `title`, `subtitle`, `id`, `authors`, `published_at`, `version`, `classification`, `status`, `commit_hash`, `corpus_sha256`, `tags`, `toc`, `branding`, `density`, `references_layout`).
- [ ] Cover-page rendering verified (eyebrow / title / subtitle / authors / id-line / evidence-line / tags / wordmark — 7 stacked elements).
- [ ] Page-1 evidence line matches expected shape: `predictions-lock SHORTSHA · corpus SHORTSHA…`.
- [ ] Cross-references between writeup body and figure callouts verified end-to-end.
- [ ] Pagination sanity-checked (E2 landed at 31-33 pages; E1 around similar).
- [ ] Appendix nested-lists render correctly (per the CSS fix shipped during E2 — `body.format-research .body ul ul` etc.).

## Reader-facing artefacts

- [ ] `reader-briefing.md` produced for the independent reader (per E2 pattern). One page, ~400 words, names the four most useful challenges.
- [ ] `figures-spec.md` produced as iko-tools handoff (per-figure caption, data tables, chart type, highlight notes, source pointers).

## Cross-repo separation (gate #4 from PROCESS.md)

- [ ] Source markdown changes happen in `meshqu-research` only.
- [ ] Frontmatter, doc-engine, rendering changes happen in iko-tools only.
- [ ] No brief asks for cross-repo edits; if a fix needs both sides it's split into two coordinated commits across the two repos.

## How this document evolves

After each publication ships, audit the published artefact against this checklist. Anything that's now convention (because both E2 and E3 carry it) gets promoted to mandatory. Anything that turned out not to matter gets removed. Anything new gets added with a note about which publication first introduced it.

## Application log

- **E2 — MRP-2026-03 (published 2026-05-27).** First paper to pass through this checklist as a gate. Cleared all body sections, closing elements, Appendices A–D, the 5-capture Grafana convention, contiguous figure numbering, and the voice conventions. The checklist was itself triangulated from E1 + E2, so E2 is both an input and the first audited artefact; no items required promotion or removal on this pass. One item newly exercised: AI-assistance declaration (gate #10) — E2 carries it after E1's precedent, confirming it as mandatory.


Drift from the checklist is fine — that's what the checklist exists to catch — but un-drifted-from-without-review-pass is the failure mode this gate exists to prevent.
