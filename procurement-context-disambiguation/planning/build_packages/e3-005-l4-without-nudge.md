# E3-005 — L4-without-nudge handler

You are a background agent. This is the smallest of the build packages — a surgical fork of E2's L4 envelope handler that swaps the prompt to the nudge-excised variant. Reads against E2's L4 to test Framing A.1 (nudge load-bearing) vs A.2 (policy text alone).

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 2 — L4 decomposition
- `procurement-context-disambiguation/runner/prompts/L4_without_nudge.md` — **the locked nudge-excised L4 prompt**, SHA-bound by `v0.3-predictions-locked`
- `procurement-context-gradient/runner/prompts/L4_policy_envelope.md` — E2's original L4 envelope, so you can see what was excised
- `procurement-context-gradient/runner/meshqu_runner/level_handlers.py` — E2's L4 handler, your fork target
- `procurement-context-disambiguation/runner/policy/` — the locked policy snapshot JSON path (unchanged from E2)

**Hard dependencies**: E3-001 merged.

## Goal

Register an `l4_without_nudge` handler that renders the L4 envelope from `L4_without_nudge.md` (everything else identical to E2's L4). Receipt carries a `nudge_excised: true` marker for cryptographic distinguishability from E2's L4 receipts.

## Scope

### 1. Handler

`meshqu_runner/arms/l4_without_nudge.py`:

```python
from meshqu_runner.arms import register
from meshqu_runner.prompt_loader import load_prompt
from meshqu_runner.policy_loader import load_policy_snapshot  # the existing loader

PROMPT_PATH = "procurement-context-disambiguation/runner/prompts/L4_without_nudge.md"

@register("l4_without_nudge")
def l4_without_nudge_handler(target_record: dict) -> str:
    envelope = load_prompt(path=PROMPT_PATH)
    policy = load_policy_snapshot()  # same policy, same SHA as E2
    return l0_baseline(target_record) + render_l4(envelope, policy)
```

`render_l4(envelope, policy)`: identical to E2's L4 renderer (substitutes the `{policy_snapshot_json}` placeholder with the canonical JSON). Reuse E2's function — don't reimplement.

Optional: register an `l4_with_nudge` handler too, pointing at E2's `L4_policy_envelope.md`. This gives the dispatcher a clean way to run the comparison head-to-head in smoke/dry-run. (Strictly speaking the comparison is against E2's already-shipped L4 receipts; but having both arms dispatchable in the same runner is convenient for sanity-checking.)

### 2. Receipt integrity

`l3_arm: null`, `nudge_excised: true`, `model_id: gpt-5.4-2026-03-05`, `diagnostic: false`. The runner foundation already wires these — this handler just sets `nudge_excised` to true.

### 3. Tests

`tests/test_l4_without_nudge.py`:

- The rendered output contains the policy independence sentence ("You are not required to mirror MeshQu's verdict; ...") — the clause that was KEPT.
- The rendered output does **NOT** contain the nudge sentence — assert that the substring "If a rule cannot be confidently evaluated" does not appear (case-insensitive). Same for "explicitly name that uncertainty".
- The receipt payload sets `nudge_excised: true`.
- The rendered prompt is byte-identical to E2's L4 rendered prompt **except** for the missing nudge sentence. Implement this as: render both, diff, assert the diff is exactly the nudge sentence and nothing else.

### 4. PR body must answer

- The full rendered `l4_without_nudge` prompt for one smoke record (so Sam can read it).
- The diff between E2's L4 render and `l4_without_nudge`'s render for the same record (should be exactly the nudge sentence).
- Confirmation that the receipt carries `nudge_excised: true`.

## Decision rules

- **Surgical change only.** The nudge sentence is excised; everything else byte-identical. If the diff is more than the nudge, the locked content has drifted from intent — surface.
- **Same policy snapshot SHA as E2.** This is critical: the test is "nudge alone or policy alone," not "nudge alone or different policy." Reuse E2's policy snapshot path; do not re-author or re-emit.
- **Don't touch E2's L4 envelope.** The comparison run is against E2's already-shipped L4 receipts.

## Out of scope

- The 3 L3 arms (other packages).
- Claude swap (other package).
- L4 with nudge — that's E2's L4, already shipped. Optionally register a handler for in-runner sanity comparison, but don't re-run the corpus on it.

## Definition of done

- Branch `feat/e3-005-l4-without-nudge`.
- Handler registered against `arms.HANDLERS["l4_without_nudge"]`.
- Diff test passes: render diff = exactly the nudge sentence.
- PR body shows the rendered prompt + the diff.

## Stop conditions

- Diff includes anything other than the nudge sentence → STOP. The locked content or E2's L4 envelope has drifted; surface.
- Policy snapshot SHA does not match E2's → STOP. The comparison would be confounded.
- E2's L4 renderer is not importable from the fork → STOP. Foundation should preserve it.
