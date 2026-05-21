# E2-001 — Multi-pass runner orchestration

You are a background agent. This package is the **foundation** of Phase 1 — every subsequent package depends on it. Care.

## Inherit first

Read these files in order before touching code:

1. `procurement-context-gradient/planning/phase_1_build_plan.md` — overall plan
2. `procurement-context-gradient/planning/experiment_design.md` — methodology including level-batching execution order and diagnostic controls
3. `procurement-context-gradient/planning/context_ladder_design.md` — ladder semantics, additivity invariant
4. `procurement-decisions/runner/meshqu_runner/` — E1's runner; this is what you fork
5. `procurement-decisions/runner/contracts/decision_context.schema.json` — the JSON schema E1 used; reuse for E2

## Goal

Build the multi-pass runner skeleton at `procurement-context-gradient/runner/`. The runner must be invocable end-to-end (even before E2-002..006 fill in the level-specific behaviour) — a stub L0 pass works for E2-001's done criteria.

## Scope

### 1. Fork E1's runner

Copy `procurement-decisions/runner/meshqu_runner/` into `procurement-context-gradient/runner/meshqu_runner/`. **Do not modify E1's runner.** E1 is the published artefact for MRP-2026-02; its runner stays archival.

Copy alongside:

- `runner/scripts/` (if present)
- `runner/contracts/` (the JSON schema)
- `runner/tests/` (the existing tests — they'll need adaptation)
- `runner/pyproject.toml` (or whatever the venv setup is)

The fork commit message must name the source SHA in `procurement-decisions/` so provenance is preserved.

### 2. Multi-pass orchestration layer

Add a new module `meshqu_runner/multi_pass.py` (or extend the existing run loop in place — your call, document the choice in the PR body) that implements:

- **Level-batching execution order.** Process all 283 records at L0, then all 283 at L1, then L2, L3, L4. Records within a level processed in OCID-ascending order. The runner takes a `--level` flag or iterates internally; either is fine.
- **Per-(record, level) receipt persistence.** Output path: `procurement-context-gradient/results/runs/<run_id>/<level>/<decision_id>.bundle.json`. Each level gets its own subdirectory.
- **Run manifest extension.** `run-manifest.json` for this run records: `levels: [L0, L1, L2, L3, L4]`, `level_batched: true`, `prompt_template_sha256` per level (loaded from `runner/prompts/`), `policy_snapshot_sha256` (the SHA of `policy-snapshot-cbf12348.json`), `runner_git_commit`. Inherits E1's manifest format for everything else (model id, temperature, etc.).
- **Receipt format extension.** Receipts gain a new `governance_context_level` field (string: `"L0"` through `"L4"`, or `"L4_PERMUTED"` for the diagnostic). This field is bound into the integrity hash payload — change the integrity-hash computation in `meshqu_runner/integrity.py` (or wherever E1 computes it) accordingly, and increment the receipt schema version to v3 (E1 used v2).
- **Stub level handlers.** For E2-001's done criteria, all five level handlers can be stubs that produce the same L0 prompt. E2-002..005 will wire up the actual level-specific behaviour.

### 3. Prompt loading

The runner reads prompt templates from `procurement-context-gradient/runner/prompts/` at startup:

- `L1_governance_context.md`
- `L2_named_rules.md`
- `L3_precedent_block_format.md`
- `L4_policy_envelope.md`

For E2-001, **create empty stub files** at those paths (single-line "TODO: Stage A content"). The Sam-only Stage A authoring step replaces these. The runner code MUST handle the empty case gracefully (treats as no-op addition).

SHA-256 of each prompt template file is computed at startup and persisted in the run manifest under `prompt_template_sha256.{L1..L4}`.

### 4. Tests

- `tests/test_multi_pass.py` — exercises the runner with the 3-record smoke set (defined in `tests/fixtures/smoke_records.json` — copy from E1's test fixtures if they exist, or stub three test records).
- Verify: 15 receipts produced (3 records × 5 levels), each with `governance_context_level` field set correctly, each in the right subdirectory.
- Verify: level-batching order observed — all L0 receipts have earlier timestamps than all L1 receipts, etc.
- Verify: receipt schema version is 3, integrity hash includes `governance_context_level`.
- All tests pass.

### 5. PR body must answer

- Did you fork E1's runner or share the code? If forked, what's the source SHA?
- What schema version are receipts using? What changed in the integrity hash payload?
- Where do level-payload generators plug in for E2-003..005 to extend?
- Any deviations from `experiment_design.md` or `context_ladder_design.md`? (There should be none. If you find one needed, stop and surface.)

## Decision rules

- **Fork, don't share.** E1's runner stays untouched. E2's runner can diverge.
- **Level-batching is mandatory.** Not optional. The prompt-cache rationale is documented in `experiment_design.md`.
- **Schema version bump is required.** v2 → v3. Receipts from this experiment must be cryptographically distinguishable from E1's by version alone.
- **`governance_context_level` is hash-bound.** Otherwise an attacker (or a bug) could move a receipt between levels.

## Out of scope

- Level-specific prompt content (E2-003..005)
- L3 precedent selector (E2-004)
- Permuted-Policy diagnostic (E2-006)
- Cost projection or smoke-run analysis (E2-007)

## Definition of done

- Branch `feat/e2-001-multi-pass-runner`.
- Runner at `procurement-context-gradient/runner/meshqu_runner/` invocable end-to-end with stub prompts producing 15 valid v3 receipts on the 3-record smoke set.
- Tests passing.
- PR body answers the four questions above.
- This harness's `decision_log.md` gets a new entry recording the fork SHA + schema version bump.

## Stop conditions

- If forking the E1 runner reveals coupling to procurement-decisions-specific assumptions you can't cleanly factor out, stop and surface — Sam may need to adjust the experiment-design scope rather than over-engineer the runner.
- If the integrity-hash change requires modifying `@meshqu/core`'s canonical-json code in the tradequ repo, STOP — that's an off-limits surface. Either the receipt schema extension works without touching `@meshqu/core` (e.g. via additional integrity fields outside the existing canonical-json envelope) OR the schema-version bump needs to be coordinated with a tradequ-side change. Surface to Sam either way.
- If E1's runner uses a Python version, dependency, or test framework you can't reproduce in the new location, stop and surface.
