# E3-001 — Runner foundation: fork + arm-aware handler scaffold

You are a background agent. This package forks E2's runner into the E3 directory and introduces the structural change that distinguishes E3 from E2: **the runner is no longer an additive ladder, it is a set of independent probe arms.** Every subsequent package depends on this foundation.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md` — the master plan
- `procurement-context-disambiguation/planning/experiment_design.md` — design + locked parameters
- `procurement-context-gradient/runner/` — **the runner you are forking**, especially:
  - `meshqu_runner/runner.py`, `multi_pass.py`, `eval_loop.py`, `level_handlers.py`
  - `meshqu_runner/agent.py`, `meshqu_runner/meshqu_client.py`, `meshqu_runner/run_manifest.py`
  - `meshqu_runner/substrate.py`, `meshqu_runner/substrate_cache.py`
  - `meshqu_runner/precedent_archive.py`, `meshqu_runner/precedent_selector.py`
  - `pyproject.toml`, `requirements.txt`, `system_prompt.md`
- `procurement-context-disambiguation/runner/README.md` — the current empty scaffolding (which you will replace)

**Hard dependencies**: `v0.3-predictions-locked` tag applied.

## Goal

Stand up `procurement-context-disambiguation/runner/` as a forked, arm-aware runner. After this package merges, the next seven packages (E3-002..E3-007, E3-009) can be dispatched in parallel against the scaffold you produce.

## Scope

### 1. Fork E2's runner

Copy the entire contents of `procurement-context-gradient/runner/` to `procurement-context-disambiguation/runner/`, excluding:

- `runner/spike/` — already exists in E3 (the Claude feasibility spike); leave it alone.
- `runner/prompts/L1_governance_context.md`, `L2_named_rules.md`, `L3_precedent_block_format.md`, `L4_policy_envelope.md` — DO NOT copy these. E3 does not have an L1/L2 rung. Arm A reuses E2's `L3_precedent_block_format.md` *via reference* (importing from the E2 path); Arm B/C/L4-no-nudge prompts already exist in `procurement-context-disambiguation/runner/prompts/` from the locked content.

Files that ARE copied: everything in `meshqu_runner/`, `scripts/`, `tests/`, `contracts/`, `system_prompt.md`, `pyproject.toml`, `requirements.txt`, top-level `README.md` (you'll replace this).

Update `system_prompt.md` to be **byte-identical** to E2's. The cross-model arm relies on this.

### 2. Strip the additive-ladder logic

E2's runner ladders L0 → L1 → L2 → L3 → L4 additively. E3 doesn't. Refactor:

- `meshqu_runner/multi_pass.py` and `level_handlers.py` — gut the additive accumulation. Replace with a flat dispatch keyed on **arm name**:
  - `"arm_a"`, `"arm_b"`, `"arm_c"` (the three L3 decomposition arms)
  - `"l4_with_nudge"`, `"l4_without_nudge"` (the two L4 variants — E2's L4 is the baseline for the L4-no-nudge comparison; you may want it dispatchable for sanity checks)
  - `"l0_baseline"` (kept for any L0 freshness check the dry-run wants)
  - `"diagnostic_primary"`, `"diagnostic_claude"` (the two diagnostic-arm flavours)
- Each arm's handler is a *self-contained* function that takes a target record and returns a rendered prompt string. No cross-arm dependencies, no shared state between arms beyond the substrate cache + precedent archive.
- The arm dispatch is by string lookup; new arms get added by registering a new handler. Subsequent packages will register their handlers here.

### 3. Receipt integrity payload — arm-aware

Extend the receipt integrity payload (in whichever module signs receipts) so every receipt records:

- `l3_arm`: one of `"A"`, `"B"`, `"C"`, or `null` (for non-L3 arms)
- `nudge_excised`: boolean (true only for `l4_without_nudge`)
- `model_id`: string (defaults to `gpt-5.4-2026-03-05`, set per arm)
- `model_sampling`: object with the actual sampling params used (e.g. `{"temperature": 0}` for the primary; `{"temperature": null, "effort": "low"}` for Claude)
- `diagnostic`: boolean (true for the Permuted-Policy diagnostic arms)
- `policy_permutation_seed`: integer or null (only set when `diagnostic: true`)
- `runner_git_commit`: SHA of the runner code at run time
- `prereg_tag`: literal `"v0.3-predictions-locked"`

These are additive to whatever E2 already wrote. Backwards compatibility with E2's bundle envelope is preserved (existing fields unchanged; bump the schema version if any inherited library requires it).

### 4. Arm-aware handler registry

`meshqu_runner/arms.py` (new):

```python
HANDLERS: dict[str, callable] = {}

def register(arm_name: str):
    def wrap(fn):
        HANDLERS[arm_name] = fn
        return fn
    return wrap
```

Each subsequent package (E3-002..E3-006) registers its handler against this registry. The CLI / eval-loop dispatches by arm name.

### 5. CLI entrypoint

`meshqu_runner/cli.py` — accept `--arm <arm_name>` as a flag. Default to `--arm arm_a` for quick smoke probing. Accept `--records <count>` and `--ocid-list <path>` for targeting specific records (used by the diagnostic subset selector). Accept `--model <model_id>` to override the default model.

### 6. Tests

`tests/test_arm_registry.py`:

- All arms register against `HANDLERS` cleanly without import-time errors (placeholder no-op handlers are fine for now; the real handlers land in later packages).
- The receipt integrity payload includes all the new fields (use a stub signer that captures the payload).
- The CLI parses `--arm` and dispatches to the correct handler.

`tests/test_fork_parity.py`:

- The forked `agent.py`, `meshqu_client.py`, `substrate.py`, `substrate_cache.py`, `precedent_archive.py`, `precedent_selector.py`, `system_prompt.md` are byte-identical to E2's (SHA comparison). The fork is supposed to be a *fork* not a *rewrite*.

### 7. README

Replace `procurement-context-disambiguation/runner/README.md` with the actual runner README, documenting the arm-aware structure, how to add a new arm, and how to invoke each arm via the CLI.

## Decision rules

- **Fork, don't share.** Same logic as E2: the published artefact (E2's runner) must not be touched post-publication. The fork preserves provenance and surfaces the eventual methodology extraction.
- **Bytes-identical core.** Agent prompt, meshqu client, substrate adapter, precedent archive reader, precedent selector — these are the parts the cross-experiment integrity claims rest on. SHA-check them in tests.
- **No live API calls in foundation tests.** Mock the meshqu client and the model client.
- **DO NOT advance into any arm handler.** That work is for E3-002..E3-006.

## Out of scope

- Any arm handler logic (E3-002..E3-006).
- Claude SDK adapter (E3-006).
- Diagnostic subset selection (E3-007).
- Diagnostic runner (E3-008).
- Rubric tool (E3-009).
- Smoke / dry-run scripts (E3-010..E3-011).

## Definition of done

- Branch `feat/e3-001-runner-foundation`.
- Runner forked at `procurement-context-disambiguation/runner/`; tests pass.
- `meshqu_runner/arms.py` registry exists with at least a placeholder no-op handler registered for each of the 7 arm names, so subsequent packages have a clear extension point.
- Receipt integrity payload extended with the new fields (verified by stub-signer test).
- CLI dispatches by `--arm`; `python -m meshqu_runner.cli --arm arm_a --records 1 --dry` runs end-to-end with no errors (using stub handlers).
- README reflects the arm-aware structure.

## Stop conditions

- A file you tried to fork from E2 has drifted from what this package expected — STOP and surface to Sam (the E2 runner is supposed to be frozen post-publication; drift means provenance is in question).
- The arm-aware refactor would require touching the substrate adapter or the precedent selector — STOP. Those are byte-identical-from-E2 by design.
- The bundle envelope versioning rule conflicts with the added fields — STOP and surface; we may need a documented bump rather than silent extension.
