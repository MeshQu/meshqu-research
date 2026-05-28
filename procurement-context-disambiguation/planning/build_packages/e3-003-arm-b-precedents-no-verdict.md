# E3-003 — Arm B handler — precedents-no-verdict

You are a background agent. Arm B uses the **same cases** as Arm A (same kNN selection, same OCIDs), but renders them through a verdict-redacted template. The contrast Arm A − Arm B isolates the verdict-exemplar effect from raw concreteness.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 1
- `procurement-context-disambiguation/runner/prompts/armB_precedent_no_verdict_format.md` — **the locked Arm B template** (verdict / violations / E1-reasoning REDACTED; concrete case fields retained). SHA-bound by `v0.3-predictions-locked`.
- `procurement-context-gradient/runner/prompts/L3_precedent_block_format.md` — the original E2 template, so you can see what was redacted
- `procurement-context-disambiguation/runner/meshqu_runner/precedent_selector.py` (forked from E2)

**Hard dependencies**: E3-001 merged.

## Goal

Register an `arm_b` handler that selects the same 4 precedents per target as Arm A would, then renders them through the locked `armB_precedent_no_verdict_format.md` template (no verdict, no violations, no E1 agent reasoning). Verify no verdict-signal substrings leak into the rendered output.

## Scope

### 1. Handler

`meshqu_runner/arms/arm_b.py`:

```python
from meshqu_runner.arms import register
from meshqu_runner.precedent_archive import load_archive
from meshqu_runner.precedent_selector import select_precedents
from meshqu_runner.prompt_loader import load_prompt

@register("arm_b")
def arm_b_handler(target_record: dict, k: int = 4) -> str:
    archive = load_archive()
    precedents = select_precedents(target_record, archive, k=k)
    template = load_prompt(
        path="procurement-context-disambiguation/runner/prompts/armB_precedent_no_verdict_format.md"
    )
    rendered = render_precedents_redacted(template, precedents)
    return l0_baseline(target_record) + "\n\n## Precedents from MRP-2026-02\n\n" + rendered
```

`render_precedents_redacted(template, precedents)`:
- Pulls only the fields the Arm B template names (OCID, contract value, award date, regime, procurement-method-open flag, publication delay).
- DOES NOT pass through verdict, violations, or E1 agent reasoning fields, even if they exist on the record. The template doesn't reference them, but defence-in-depth: explicitly project to the allowed field set.
- Uses the same string-interpolation idiom as E2's L3 renderer.

### 2. Receipt integrity

`l3_arm: "B"`, `nudge_excised: false`, `model_id: gpt-5.4-2026-03-05`, `diagnostic: false`.

### 3. Tests — contamination check is the core

`tests/test_arm_b.py`:

- **Precedent identity vs Arm A**: for the 3 smoke records, `select_precedents` returns the **same OCIDs** under Arm B as under Arm A. The arms differ only in rendering, not in selection.
- **Contamination check**: assert the rendered Arm B prompt contains NONE of:
  - The literal verdicts (`ALLOW`, `REVIEW`, `DENY`)
  - The word `violation` (case-insensitive)
  - Substrings of any E1 agent reasoning text from the loaded precedents (sample-check the first 50 chars of each precedent's reasoning field; assert none appear in the rendered Arm B output)
  - The MeshQu `recommended_action` field's content (if present in the archive)
- Deterministic: same target + archive → same prompt every time.
- The receipt payload sets `l3_arm: "B"`.

### 4. PR body must answer

- Confirmation that Arm B's 4 selected OCIDs **match** Arm A's for each of the 3 smoke records (paste the OCIDs alongside Arm A's PR).
- The full rendered Arm B prompt for one smoke record (so Sam can read it and confirm no verdict-signal leaked).
- The contamination-check test output (which substrings were checked + the pass result).

## Decision rules

- **Same kNN as Arm A.** If the OCIDs differ, that's a bug — both arms feed the same selector.
- **Project explicitly to the allowed field set.** Don't trust the template to elide fields the record carries.
- **Lower-case substring match is the right contamination check** for E1 reasoning text. Don't get fancy with regex.

## Out of scope

- Arm A's renderer (other package).
- Changes to the precedent selector (frozen-from-E2).
- Authoring the Arm B template (locked; v0.3-bound).

## Definition of done

- Branch `feat/e3-003-arm-b-precedents-no-verdict`.
- Handler registered against `arms.HANDLERS["arm_b"]`.
- All contamination-check assertions pass.
- PR body shows OCID parity with Arm A and the rendered Arm B prompt for inspection.

## Stop conditions

- The Arm B template references a field the precedent archive doesn't carry → STOP, surface to Sam. The template is locked; we'd need a documented amendment.
- Contamination check fires (a verdict word leaks through) → STOP, fix before merge. This invalidates the arm if it ships unfixed.
- Selector returns different OCIDs than Arm A would for the same target → STOP. Same selector, same archive, same target → must produce same OCIDs. If not, something between Arm A and Arm B has drifted.
