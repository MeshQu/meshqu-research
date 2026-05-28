# E3-004 — Arm C handler — density-control + token parity

You are a background agent. Arm C is the volume-matched control: it adds prompt content of comparable size and structure to E2's L3 precedent block, but with NO concrete prior cases, NO verdicts, and NO compliance-alert tone. Arm A − Arm C isolates raw volume effects from the precedent effect.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 1 — especially the **two faces of contamination risk** (volume *and* semantic flavour)
- `procurement-context-disambiguation/runner/prompts/armC_density_control.md` — **the locked Arm C content** (4 dry/neutral schema-description references; SHA-bound by `v0.3-predictions-locked`; **neutrality-reviewed** — do not edit)
- `procurement-context-gradient/runner/prompts/L3_precedent_block_format.md` — for the token-parity comparison
- `procurement-context-disambiguation/runner/meshqu_runner/precedent_archive.py` — to load the same target records the parity check needs

**Hard dependencies**: E3-001 merged.

## Goal

Register an `arm_c` handler that produces a rendered prompt = L0 baseline + the locked Arm C density-control block (verbatim, no interpolation against target). Verify token count is within ±5% of E2's rendered L3 payload over the same target records.

## Scope

### 1. Handler

`meshqu_runner/arms/arm_c.py`:

```python
from meshqu_runner.arms import register
from meshqu_runner.prompt_loader import load_prompt

ARM_C_TEMPLATE_PATH = "procurement-context-disambiguation/runner/prompts/armC_density_control.md"

@register("arm_c")
def arm_c_handler(target_record: dict) -> str:
    # Arm C uses NO precedent selector — it adds STATIC content matched on
    # volume/structure, not on the target. The target_record arg is taken
    # for signature parity with the other arms but only the L0 baseline
    # uses it.
    block = load_prompt(path=ARM_C_TEMPLATE_PATH)
    # Strip the HTML neutrality-contract comment at the top — that's
    # authoring metadata, not part of the prompt rendered to the model.
    block = strip_html_comment_block(block)
    return l0_baseline(target_record) + "\n\n## Reference notes\n\n" + block
```

- `strip_html_comment_block(text)`: removes the leading `<!-- ... -->` neutrality contract from the Arm C template. The HTML comment is for human inspectors; the model doesn't need to see it. The four `## Reference N: ...` sections are what gets rendered.
- No precedent selector, no archive read. Arm C is static.

### 2. Token-parity check (the core)

`meshqu_runner/arms/arm_c.py` also exposes:

```python
def measure_token_parity(target_records: list[dict]) -> dict:
    """
    For each target, render the Arm C prompt and E2's L3 prompt (via Arm A's
    handler). Return per-record token counts (using the primary agent's
    tokenizer) and the delta. The aggregate ratio must be within +/-5%.
    """
```

- Use the same tokenizer the primary agent uses. For `gpt-5.4`, that's `tiktoken` with the appropriate encoding. If the tokenizer is already wrapped in the forked runner, reuse it; do not re-instantiate.
- Compare against Arm A's full rendered output (so the comparison includes the L0 baseline both sides).
- Report mean ratio + per-record min/max ratio across the smoke set (3 records minimum) and an extended set (10 records, sampled from the corpus deterministically).

### 3. Receipt integrity

`l3_arm: "C"`, `nudge_excised: false`, `model_id: gpt-5.4-2026-03-05`, `diagnostic: false`.

### 4. Tests

`tests/test_arm_c.py`:

- The HTML neutrality-contract comment is stripped from the rendered output (the model should not see authoring metadata). Verified by substring check.
- The four `## Reference N:` sections appear in the rendered output.
- Token-parity check: for 10 deterministically-sampled corpus records, the mean Arm C / Arm A token-count ratio is within `[0.95, 1.05]`. If outside, the test fails and the PR body documents the gap (this is decision point 3 in the master plan).
- No live model call in tests; tokenizer is local.
- The receipt payload sets `l3_arm: "C"`.

### 5. PR body must answer

- The per-record token counts and ratios for the 10-record parity sample (markdown table).
- The mean ratio and the min/max.
- If the parity is outside ±5%: a recommendation (accept-with-caveat vs author a top-up). **Do NOT author a top-up unilaterally** — the Arm C content is locked by the v0.3 tag; any change requires a documented amendment.

## Decision rules

- **Static content.** Arm C does not vary per target. The same block is appended to every L0 baseline.
- **No new content.** The locked Arm C block is SHA-bound. If parity is bad, the answer is *not* to edit the Arm C block — surface to Sam.
- **Strip the HTML comment, keep everything else.** The neutrality contract is for human inspectors only.

## Out of scope

- Arm A or Arm B logic (other packages).
- Authoring or modifying the Arm C content (locked; v0.3-bound).
- The semantic-flavour neutrality review (already done by Sam pre-tag).

## Definition of done

- Branch `feat/e3-004-arm-c-density-control`.
- Handler registered against `arms.HANDLERS["arm_c"]`.
- Token-parity check runs on 10 records and the mean ratio is within ±5% (or, if outside, the PR surfaces the gap with a recommendation).
- PR body lists the per-record ratios + mean + min/max.

## Stop conditions

- Token-parity is wildly off (mean ratio < 0.85 or > 1.15) → STOP. Surface to Sam. The control's claim to be "volume-matched" is in question; a top-up to the locked content requires a tag amendment, not an agent decision.
- The HTML-comment stripper produces an empty or malformed block → STOP. Check the parser; the four `## Reference N:` sections should remain.
- Tokenizer mismatch with the primary agent → STOP. The token-parity claim only holds against the model that will actually consume the prompt; using a different tokenizer would invalidate the check.
