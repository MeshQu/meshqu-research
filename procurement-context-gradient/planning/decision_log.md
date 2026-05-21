# Decision Log — Experiment 2

> Reverse-chronological journal of design decisions. Append new entries at the top.
> Each entry: date, decision, alternatives considered, reason picked.

---

## 2026-05-21 — Phase 1 operational scaffolding kept private (publication-discipline alignment with E1)

**Decision**: The Phase 1 build packages (`build_packages/e2-001..009.md`) and the Stage A authoring guide (`stage_a_content_authoring.md`) are kept in the private notes location at `~/Projects/meshqu-research-notes/procurement-context-gradient/planning/`, not in this public repo. The high-level `phase_1_build_plan.md` stays public.

**Alternative considered**: keep all Phase 1 planning material on the public branch. Rejected — would have broken with the publication-discipline precedent E1 established (queued-edits.md was moved to private notes on 2026-05-19 for the same reason; pre-render writeup edits flow through iko-tools rather than this repo per the 2026-05-20 split entry below).

**The boundary**:

- **Public**: methodology, design, predictions, decision log, findings, runner code, the locked prompt content files (`runner/prompts/L1..L4.md`) — anything citable in the writeup or required for cryptographic reproducibility.
- **Private**: agent-dispatchable build packages, internal authoring deliberation guides, dispatch sequencing notes — operational scaffolding analogous to `.harness/` material in the monorepo. Not citable, not reproducibility-load-bearing.

**Specific files moved to private notes**:

- `procurement-context-gradient/planning/stage_a_content_authoring.md` — Sam-only authoring guide for the four locked prompt content files; carries "things to consider" deliberation that's editorial, not methodological.
- `procurement-context-gradient/planning/build_packages/` (10 files: `_INDEX.md` + `e2-001..009.md`) — agent-dispatchable build prompts with stop conditions, branch naming conventions, off-limits-surface references that pull in tradequ-internal conventions. Not appropriate for the public research record.

**What stays public for Phase 1**:

- `phase_1_build_plan.md` — high-level methodology of the build phase + dependency graph. Useful future writeup §2 material.
- Once Stage A authoring lands: the four files at `runner/prompts/L1..L4.md` — these are the actual prompt content the experiment runs on, and their SHA-256 is bound into every receipt's integrity payload. Public for reproducibility.
- Once Stage B builds land: the runner code at `runner/meshqu_runner/`. Public; cited from writeup §8.
- Any F-series findings authored during build/smoke/dry-run.
- This decision log.

**Reason picked**: matches E1 precedent. The public research record carries claims; operational engineering scaffolding lives where it doesn't undercut the published artefact or leak cross-repo internal conventions into a public research repo.

**Note on PR #47**: the initial commit on `plan/procurement-context-gradient-phase1-buildplan` included the operational files on the public branch. The corrective commit on the same branch removes them and adds this entry. Pre-merge correction; no public-history exposure on `main`.

---

## 2026-05-21 — Pre-lock methodology upgrades: level-batching, L3 frozen-archive isolation, sycophancy framing, adversarial fail-safe

**Decision**: applied four methodology upgrades to the Phase 0 planning documents before tagging `v0.2-predictions-locked`. These tighten the operational efficiency of the run, harden the inferential bar on the headline finding, and align the framing with the established AI-safety literature.

**1. Execution order locked to level-batching, not record-cycling.** The runner processes all 283 records at L0, then all 283 at L1, …, then all 283 at L4. Reason: at L4 the prompt carries a ~4,500-token policy JSON; record-cycling order would break the OpenAI prompt cache on every call. Level-batching keeps the static `## Policy` block at the cache head for all 283 consecutive L4 calls. Empirical expectation: 50–80% input-token execution-cost reduction at L4, where cost dominates. Documented in `experiment_design.md` §"Multi-pass runner" and `context_ladder_design.md` §"Token-cost projection".

**Alternative considered**: record-cycling (L0→L4 per record). Rejected — cache-break overhead, plus introduces a temporal-locality variable (OpenAI backend at minute 5 vs minute 95 may behave differently at temp 0).

**2. L3 precedent source isolated to frozen E1 archive.** The L3 nearest-neighbour precedent selector reads exclusively from `procurement-decisions/results/runs/dry-run-7ddf7274-…/decision_traces.jsonl` (the published, static MRP-2026-02 corpus). No live MeshQu API path, no E2 in-flight outputs, no target-record self-reference. Documented in `context_ladder_design.md` §L3.

**Reason**: rules out three failure modes — runtime state drift (live lookups change over time), circular dependency (E2 in-flight outputs feeding L3 of later records in the same run), and future contamination (precedents must be visibly historical relative to the experiment, not "what MeshQu would say today"). Frozen archive enforces all three.

**3. Echo-trap reframed as agreement sycophancy with explicit boundary conditions.** The structural-boundary finding was previously framed informally as the "echo trap." Reframed to use the established AI-safety term **agreement sycophancy** — the structural tendency of LLMs to mirror explicit prompt assumptions at the cost of independent analysis. Operational definition tightened:

> Sycophancy = the agent abandons L0-baseline evidence-sensitive REVIEW caution on **ambiguous records** (where the operative MeshQu violation is driven by missing metadata, predominantly PROC-005-OPEN-TENDER missing-method) and emits DENY because the L4 policy's binary structure pressures it to.

Explicit false-positive guard: correct deductions on unambiguous rules (e.g. £57M procurement DENY against a £500k ceiling) are not sycophantic — they are successful compliance execution. The ambiguity-segmented analysis reports verdict shifts on unambiguous-rule records vs ambiguous-rule records separately. Documented in `experiment_design.md`, `predictions.md`, and `writeup_outline.md`.

**Reason**: terminological precision aligns the writeup with the AI-safety literature an academic reviewer would expect; the false-positive guard prevents the writeup from over-claiming sycophancy where correct rule-application is the parsimonious explanation; the ambiguity segmentation gives the matrix a more rigorous decision boundary than the original three-signal version.

**4. Permuted-Policy diagnostic control added.** A 5% subset of the corpus (14 records, deterministically selected by `hash(ocid) mod 20 == 0`) gets an auxiliary diagnostic pass where the agent is given an L4 policy with inverted operators. Two outcomes:

- Case A — agent flips verdicts to match inverted logic without flagging contradiction: direct sycophancy evidence.
- Case B — agent flags the logical contradiction in reasoning text: direct evidence of independent judgment.

Negligible additional cost (14 calls). Runs during Phase 1 smoke phase. Documented in `experiment_design.md` §"Diagnostic Controls".

**Reason**: the main run produces only correlational evidence (more context → more commitment). The Permuted-Policy control raises the inferential bar from correlation toward causal-claim-ready by introducing a deliberate negative-control test that the moat-story cell of the four-way matrix must clear. Without it, the writeup could only say "verdicts shifted under context"; with it, the writeup can say "the context ladder unlocked judgment that pushes back against inverted policy" — a substantively different claim.

**5. Context-positioning sub-metric added.** Cross-cut analysis on the L0→L4 verdict shifts, partitioning records by the array-position of the operative MeshQu rule in the L4 policy JSON. Documents whether the agent's convergence rate varies with where the rule sits in the prompt — i.e. whether the experiment is also detecting a long-context attention-allocation limit rather than a policy-content effect. Documented in `experiment_design.md` §"Analysis layer" as a sub-analysis.

**Reason**: at L4 the agent is reading ~5,500 input tokens. The position of the operative rule within the policy JSON is a confound for "context teaches the agent to commit." Pre-registering the sub-cut means the writeup can report it cleanly regardless of which direction it points; post-hoc it would look like reaching.

**What stayed unchanged from the Phase 0 baseline (2026-05-21 earlier today)**:

- The five-level ladder (L0..L4)
- The additivity invariant
- The model, temperature, verdict space, policy snapshot, substrate, corpus
- The 7 predictions (only their framing language in the matrix update — no falsification criteria changed)
- The writeup outline shape

**Lock target status**: ready to tag `v0.2-predictions-locked` once the policy snapshot JSON is persisted to `policy/policy-snapshot-cbf12348.json` and a final read of the four updated documents (`experiment_design.md`, `context_ladder_design.md`, `predictions.md`, `writeup_outline.md`) confirms the content is what should be frozen. These pre-lock adjustments are routine — they do not invoke the post-corpus defensibility analysis the post-lock E1 PROC-004-COI clarification required, because no corpus exists yet for E2.

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
