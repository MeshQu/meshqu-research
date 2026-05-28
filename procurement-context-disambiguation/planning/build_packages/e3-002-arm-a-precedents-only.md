# E3-002 — Arm A handler — precedents-only

You are a background agent. Arm A is the most conservative arm: it reuses E2's L3 precedent block **byte-identically**, but on top of L0 baseline only (no L1 prose, no L2 named rules). The result tests whether the L3 commitment effect survives when precedents are the *only* added content above L0.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 1 — L3 decomposition
- `procurement-context-gradient/runner/prompts/L3_precedent_block_format.md` — the **locked E2 L3 block** (Arm A reuses this byte-identically; do **not** copy it into the E3 prompts/ dir — reference it from the E2 path)
- `procurement-context-gradient/runner/meshqu_runner/precedent_selector.py` and `precedent_archive.py` — the E2 selector and archive reader, which the foundation already forked into E3 byte-identically
- `procurement-context-disambiguation/runner/meshqu_runner/arms.py` — the arm registry from E3-001

**Hard dependencies**: E3-001 merged.

## Goal

Register an `arm_a` handler that produces a rendered prompt = L0 baseline + E2's full L3 precedent block (4 precedents per target). Verify the rendered prompt is byte-identical to E2's L3 rung output for the same target record + same precedent set.

## Scope

### 1. Handler

`meshqu_runner/arms/arm_a.py`:

```python
from meshqu_runner.arms import register
from meshqu_runner.precedent_archive import load_archive
from meshqu_runner.precedent_selector import select_precedents
from meshqu_runner.prompt_loader import load_prompt

@register("arm_a")
def arm_a_handler(target_record: dict, k: int = 4) -> str:
    archive = load_archive()
    precedents = select_precedents(target_record, archive, k=k)
    template = load_prompt(
        path="procurement-context-gradient/runner/prompts/L3_precedent_block_format.md"
    )
    rendered = render_precedents(template, precedents)
    return l0_baseline(target_record) + "\n\n## Precedents from MRP-2026-02\n\n" + rendered
```

- `l0_baseline(target_record)`: the L0 baseline render — copy E2's L0 render exactly (it's part of the forked runner). No new logic here.
- `load_prompt(path=...)`: extend the existing prompt loader to accept an external path so Arm A can reference E2's locked content directly without copying it.
- `render_precedents(template, precedents)`: identical interpolation to E2's. Use the existing renderer if E2 has one factored out; otherwise lift it from E2's L3 handler.

### 2. Receipt integrity

When the agent fires with `arm: "arm_a"`, the integrity payload sets `l3_arm: "A"`, `nudge_excised: false`, `model_id: gpt-5.4-2026-03-05`, `diagnostic: false`. The runner foundation already wires these — Arm A just sets the `l3_arm` value.

### 3. Tests

`tests/test_arm_a.py`:

- **Byte-identity check** (the core test): for the 3 smoke records, run E2's L3 handler against the same records + same precedents, and run Arm A's handler. The rendered prompts must be **byte-identical**. If they're not, the test fails and the PR body must explain the diff.
- Deterministic: same target + same archive → same prompt every time.
- The receipt payload sets `l3_arm: "A"`.
- No L1 or L2 strings appear in the rendered prompt (since Arm A skips them).

### 4. PR body must answer

- For each of the 3 smoke target records, the OCIDs of the 4 precedents Arm A selected.
- Confirmation that the byte-identity test passes against E2's L3 renderer (paste the SHA of the rendered prompt for one record, computed by both renderers).
- If byte-identity fails: a focused diff and a hypothesis (most likely cause: a whitespace nudge in the prompt loader; second-likely: an order difference in the precedent selector tie-breaking).

## Decision rules

- **Use E2's locked L3 prompt by reference.** Do not copy it into E3's prompts dir — that would create a second SHA for the same locked content and introduce drift risk. Reference the E2 path.
- **Precedent selector reused unchanged from the fork.** Don't refactor it.
- **Byte-identity is non-negotiable.** If you cannot make the renders byte-identical, surface — don't paper over with a "close enough" test.

## Out of scope

- Arm B, Arm C, L4-no-nudge, Claude swap (other packages).
- Changes to the precedent selector or archive reader (frozen-from-E2 by design).
- Re-authoring E2's L3 prompt (locked content, SHA-bound by `v0.2-predictions-locked`).

## Definition of done

- Branch `feat/e3-002-arm-a-precedents-only`.
- Handler registered against `arms.HANDLERS["arm_a"]`.
- Byte-identity test passes against E2's L3 renderer.
- PR body lists precedent OCIDs for the smoke records and the byte-identity SHA.

## Stop conditions

- Byte-identity test fails and you cannot trace the cause to a single mechanical difference → STOP. Surface to Sam with the diff.
- E2's L3 renderer is no longer importable (path drift since the fork) → STOP. The foundation should preserve byte-identity of the underlying renderer.
- Precedent selector returns fewer than k=4 precedents for any of the 3 smoke records → surface to Sam (this would be an E2 drift to record, not a bug Arm A should fix).
