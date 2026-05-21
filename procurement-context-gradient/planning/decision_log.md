# Decision Log — Experiment 2

> Reverse-chronological journal of design decisions. Append new entries at the top.
> Each entry: date, decision, alternatives considered, reason picked.

---

## 2026-05-21 — E2-001 multi-pass runner: fork source, receipt-schema bump, level-marker hash-binding

**Decisions captured for the build-package paper trail.**

**1. Fork source.** Forked `procurement-decisions/runner/meshqu_runner/` at SHA `10f5475d9efa8c4682ac73b6956e3aeb46854e70` into `procurement-context-gradient/runner/meshqu_runner/`. E1's runner stays untouched — it is the published artefact for MRP-2026-02. The fork is the new baseline for all E2 work; subsequent build packages (E2-002..006) modify only the E2 copy. Provenance is preserved here, in the README at `procurement-context-gradient/runner/README.md`, and in the run-manifest's `runner_git_commit` field.

**Alternative considered**: importing the E1 runner as a path-relative Python dependency. Rejected — would require touching E1's `pyproject.toml` (renaming the package, opening it for path-based imports), creating cross-experiment coupling exactly where we want isolation. The duplication a fork creates is the price for E1's archival cleanliness; the eventual `methodology/` extraction (Phase 4 post-publish) is where the shared infrastructure consolidates.

**2. Receipt schema v2 → v3 bump.** The locally-persisted bundle file at `results/runs/<run_id>/<level>/<decision_id>.bundle.json` carries `schema_version: 3`. v2 is implicit in E1 (E1 never persisted local bundles; the MeshQu-issued receipts it fetched on demand carried the v2 envelope shape). v3's load-bearing addition is one field: `governance_context_level`.

The run manifest also carries `receipt_schema_version: 3` so a downstream consumer can identify the schema without reading any individual bundle.

**3. Where `governance_context_level` binds into the integrity hash.** Bound into the MeshQu-issued integrity hash via the existing `context.fields` injection point — the same audit-only-but-hash-bound pattern E1 uses for the seven `agent_*` keys. The multi-pass orchestrator injects `governance_context_level` (alongside the `agent_*` fields) BEFORE posting to `/v1/decisions/record`; the API canonicalises the fields map and binds it into the integrity hash. **No `@meshqu/core` change required.** The policy never references this key, so it rides as audit-only metadata — invisible to evaluation, cryptographically attested.

The contract schema at `runner/contracts/decision_context.schema.json` is updated to document the new key under `fields`, with an explicit enum (`L0`, `L1`, `L2`, `L3`, `L4`, `L4_PERMUTED`).

**Why this binding point**: the stop condition in the package prompt flagged the alternative — modifying `@meshqu/core`'s canonical-JSON envelope — as something to surface to Sam rather than implement. The injection-via-fields pattern is structurally identical to what E1 already does for `agent_*` (these fields are not policy-evaluable but ARE in the canonical fields map MeshQu hashes), so the E2 extension is a strict superset of E1's pattern. No upstream surprise; no coordination needed with `@meshqu/core`.

**Local-bundle integrity test**: the bundle file persists the exact canonical-JSON bytes the integrity hash was computed over, so a future verifier (or a tighter test) can recompute SHA-256 and confirm hash → bytes → field-set match. The test `test_governance_context_level_is_hash_bound` verifies in stub mode that:
- the level marker is present in the canonicalised fields
- recomputed SHA matches `receipt.integrity_hash`
- stripping the marker changes the hash (proving it is materially bound, not bypassed)

**4. Level-batching execution order.** Implemented in `multi_pass.py::run_multi_pass`. Outer loop walks levels in `MAIN_LEVELS = (L0, L1, L2, L3, L4)`; inner loop walks records in OCID-ascending order. Records missing an OCID sort to the end (deterministic). The test `test_level_batching_observed` enforces the invariant.

**5. Per-level handler plug-in point.** `level_handlers.py` defines a `LevelHandler` Protocol; `default_main_handlers()` returns the five stubs (L0..L4) the orchestrator uses by default. E2-002..005 each replace one entry in this registry. E2-006's Permuted-Policy diagnostic registers a sixth entry (`L4_PERMUTED`) in its own registry passed to `run_multi_pass(handlers=...)` — keeping the main grid uncontaminated.

**6. Empty-prompt contract preserved despite Stage A being already merged.** The package prompt was written assuming Stage A hadn't landed yet ("create empty stub files… the Sam-only Stage A authoring step replaces these"). Stage A merged in PR #48; the real prompts are now in place. The runner code still honours the empty-file contract — empty L1..L4 markdowns produce empty addenda, the orchestration loop still emits 15 bundles, and the SHA-binding contract still holds with the empty content cryptographically attested. The test `test_empty_prompts_handled_gracefully` enforces this so a future contributor who empties a prompt file does not break the orchestration loop, only the locked-content invariant (which would surface at predictions-lock verification, not runtime).

**Out of scope for E2-001 (handed to subsequent packages)**:
- Live OpenAI wiring beyond the stub agent (the live `Agent` is imported and the orchestrator uses its `model_id` / `temperature` / `system_prompt_sha256` properties, but the live OpenAI call is only exercised by E1's inherited tests, not by the multi_pass smoke).
- L0 substrate-cache reader (E2-002).
- Level-specific prompt-addendum semantics (E2-003 for L1+L2, E2-004 for L3, E2-005 for L4).
- Permuted-Policy diagnostic (E2-006).
- Atomicity / receipt-orphan reconciliation in the multi-pass loop (inherits from E1's eval_loop; the multi-pass orchestrator does not yet wrap each pass in the same `receipt_orphaned` recovery contract — to be added when E2-002 wires the live path).

**Files added** (under `procurement-context-gradient/runner/`):
- `meshqu_runner/multi_pass.py` — orchestrator + StubAgent + StubMeshQuClient + bundle writer + manifest writer
- `meshqu_runner/level_handlers.py` — Protocol + L0..L4 stub handlers + `compose_user_message` (additivity)
- `meshqu_runner/prompt_loader.py` — Stage A SHA-256 loader with empty-file tolerance
- `tests/test_multi_pass.py` — 11 tests covering the done criteria
- `tests/fixtures/smoke_records.json` — the 3-record smoke fixture

**Files modified**:
- `contracts/decision_context.schema.json` — added `governance_context_level` to `fields`; retitled
- `pyproject.toml` / `__init__.py` / `README.md` — package metadata + fork provenance

**Done criteria status**: 15 bundles produced on the 3-record × 5-level smoke; all 11 multi-pass tests pass; all 209 inherited tests still pass (no behavioural change to E1 code); CLI `python -m meshqu_runner.multi_pass --records … --stub` works end-to-end.

---

## 2026-05-21 — Stage A content refinements + emergent reframing of the experiment's conceptual centre

**Decision (mechanical)**: applied four refinements to the Stage A prompt content files at `runner/prompts/`:

- **L1**: "Your verdict should reflect whether the record *satisfies this policy area*" → "*appears compliant within this policy area*." Softens commitment, better matches uncertainty semantics.
- **L2**: unchanged.
- **L3**: added `OCID` and `award_date` back into the per-precedent template (now 9 fields instead of 7). Not because the model needs them semantically, but because temporal anchoring and precedent traceability matter for reasoning models that treat the precedent block as a governance case record. The template stays lean enough to keep L3's cumulative payload in the ~1,500-token band.
- **L4**: anti-sycophancy nudge tightened from "*If a rule's condition cannot be evaluated because evidence is missing, name that uncertainty in your reasoning*" to "*If a rule cannot be confidently evaluated because evidence is missing or ambiguous, explicitly name that uncertainty in your reasoning.*" Adds "confidently" (matches the evidence-sensitive-caution finding from E1), "or ambiguous" (covers the ambiguity-segmented analysis already in `experiment_design.md`), and "explicitly" (encourages articulation without sounding defensive).

These are **pre-receipt-generation refinements** to prompt content that has never produced a receipt. They are NOT post-lock modifications to the v0.2-locked planning documents (`predictions.md`, `context_ladder_design.md`, `experiment_design.md`, `writeup_outline.md`, `policy/policy-snapshot-cbf12348.json`). Prompt content gets its SHA-256 bound into receipts only when the runner starts generating; until then, content is in active authoring.

**Strategic observation worth recording (not a decision yet)**: the four-level ladder, once seen end-to-end, is structurally probing something larger than "does more context help the agent commit?" Each layer introduces a distinct kind of governance scaffolding:

| Layer | Governance artefact type |
|---|---|
| L1 | governance awareness (domain framing) |
| L2 | symbolic policy awareness (rule identifiers without semantics) |
| L3 | precedent + receipt memory (institutional / case-record reasoning) |
| L4 | executable-policy visibility (full rule semantics) |

The reframing this surfaces: E2 is no longer *"give the AI more context and see if it commits more"*. It is *"measure which kinds of governance artefacts meaningfully alter AI reasoning and escalation behaviour."* That is a materially different — and stronger — research question. The cleanest way to surface it is in the writeup at draft time (§1's question framing and §9's "what's next"); the locked planning artefacts don't need editing now, because the ladder shape and predictions cleanly support either framing.

**L3 is the most novel layer.** L1/L2/L4 are expected probes (domain framing / symbolic identifiers / raw policy text). L3 is genuinely unusual because it tests whether **Decision Receipts function as governance memory primitives for agents** — a conceptual shift from "receipts as passive audit objects" to "receipts as active reasoning infrastructure." If E2 finds meaningful L3 effect (e.g. ALLOW→DENY or REVIEW→DENY shifts that concentrate at L3, not L4), that is a load-bearing finding for MeshQu's product narrative. The writeup §6 should lean into this if the data supports it.

**Future variant flagged (NOT in E2's scope)**: an **L3.5 receipt-only reasoning** condition — same L3 precedent block, but with L1 / L2 / L4 stripped. The agent sees only historical Decision Receipts, prior reasoning, and violation codes; no policy text, no rule names, no domain framing. Tests whether governance can emerge through precedent memory alone (case-law-like behaviour). Captured here as a candidate for E2-followup or for E3's scope discussion when the time comes; explicitly out-of-scope for E2 to keep the predictions-lock clean.

**Reason picked (for the four refinements)**: each is a small wording adjustment that improves the prompt's match to the experiment design without changing the experiment design. The L3 field additions (OCID + award_date) align the precedent block with what makes it feel like a governance case record — the methodology language already in `context_ladder_design.md` and `predictions.md` describes L3 as "case-law analogue," so the precedent block format should embody that.

**Out of scope for this entry**: the broader conceptual reframing ("which governance artefacts meaningfully alter AI reasoning"). This is recorded as an observation, not a design change. The writeup will surface it at draft time; the planning artefacts remain valid descriptions of what is being run.

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
