# Decision Log — Experiment 2

> Reverse-chronological journal of design decisions. Append new entries at the top.
> Each entry: date, decision, alternatives considered, reason picked.

---

## 2026-05-21 — Phase 0 scaffold: folder skeleton + planning documents drafted

**Decision**: created `procurement-context-gradient/` as a sibling folder to `procurement-decisions/`. Drafted the Phase 0 planning documents (`experiment_design.md`, `context_ladder_design.md`, `predictions.md`, `substrate.md`, `writeup_outline.md`, plus this `decision_log.md`).

**Folder structure decision — sibling, not subfolder.** Considered three options:

- **Sibling folder** (chosen): `procurement-context-gradient/` next to `procurement-decisions/`. Each experiment self-contained, separate predictions-lock, separate writeup, separate corpus. Cross-experiment references via explicit relative paths.
- **Subfolder of procurement-decisions**: e.g. `procurement-decisions/experiment-2/`. Considered but rejected — would conflate two pre-registrations under one folder name. Pre-registration cleanliness matters more than colocation.
- **Top-level `experiments/` directory**: considered but rejected — introduces a layer for no clear gain given the repo currently has one and soon two pieces. Defer until E3+ if it becomes useful.

**Reason picked**: separate predictions-lock per experiment requires separate folders. The `methodology/` extraction (E1 decision_log 2026-05-20) is the right place for shared infrastructure once E2 confirms what's actually shared; until then, separate folders preserve clean per-experiment archival.

**Naming decision**: `procurement-context-gradient/` chosen over `procurement-decisions-e2/` or `experiment-2-context-gradient/`. The chosen name carries the domain (procurement) and names what changes (context gradient) without sequence-numbering. The slug is publication-friendly (will likely be the URL slug at `meshqu.com/research/procurement-context-gradient/`).

**E1 → E2 inheritance**: locked at Phase 0 — same model, same temperature, same verdict space, same policy snapshot, same substrate adapter, same 283-record corpus reused exactly. The justification for each is in `experiment_design.md`. Changing any of these between experiments would mean measuring a moving target.

**Context ladder shape**: 5 levels (L0 through L4), strictly additive. The L1-vs-L2 distinction is preserved (not merged) because the "prose summary vs structured rules" choice answers a question worth measuring directly — see `context_ladder_design.md` rationale.

**Substrate posture**: no new Contracts Finder fetch. Reuse the cached OCDS records from E1's `dry-run-7ddf7274-…` run as a read-only source. This eliminates substrate drift as a variable and makes row-by-row delta tracking across levels interpretable.

**Echo-trap detection**: pre-committed in `predictions.md` as a structural boundary, not as a flaw to discover post-hoc. The P3 + P4 + P5 cluster forms the detection mechanism. The four-way matrix in `predictions.md` enumerates what each combination of outcomes means. The writeup commits to reporting whichever cell the data lands in.

**Out of scope but flagged**:

- Tag `v0.2-predictions-locked` is NOT yet applied. Lock target is post-review of `predictions.md` and `context_ladder_design.md`, with the policy snapshot JSON persisted to `policy/policy-snapshot-cbf12348.json` at the same commit. Until tagged, predictions are drafts.
- The L3 precedent-selection function is described in spec but not yet committed in code. The deterministic nearest-neighbour function must be in the runner at lock time.
- The multi-pass runner extends E1's `runner/meshqu_runner/`. Whether to fork the directory into `procurement-context-gradient/runner/` or import the E1 runner as a path-relative dependency is a Phase 1 decision; both options preserve provenance.

**Reason this entry exists**: establishes the Phase 0 baseline so any post-lock change is testable against an honest prior state.

---
