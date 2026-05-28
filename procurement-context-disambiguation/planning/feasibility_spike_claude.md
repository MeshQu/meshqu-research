# E3 — Claude second-model feasibility spike

**Status**: spike harness landed; awaiting a run with a live key. Mechanics-only,
pre-lock. Results recorded below once run.

## Why this spike exists

The cross-model arm pins a second model *before* the pre-registration tag. Pinning
a model we haven't actually called is how you discover at run-time — after the tag —
that the key doesn't reach the tier, or that the verbatim E2 scaffold doesn't yield a
parseable verdict from a different model family. This spike answers four mechanical
questions on **three throwaway synthetic records** (never the frozen 283-corpus, never
the locked diagnostic-100 subset — no pre-lock peeking at real data):

1. Which Claude model does the key actually reach? (pin confirmation)
2. Does E2's **verbatim** agent scaffold yield a parseable verdict JSON from Claude, or
   does the arm need an output-parsing shim? (portability)
3. `temperature=0` behaviour on the pinned model.
4. Latency + token-usage sanity.

The harness is `runner/spike/claude_spike.py`. It reads E2's `system_prompt.md` verbatim
so the spike exercises byte-identical instructions to the primary-model run.

## Pre-run finding (from the claude-api skill) — forces a pin decision

**Claude Opus 4.7 (`claude-opus-4-7`) removed the `temperature` parameter.** Sending
`temperature=0` returns HTTP 400. E2's primary agent (`gpt-5.4`) ran at temperature 0,
so the cross-model arm **cannot** match "temp 0" on Opus 4.7. Two candidate pins:

| Option | Model | Sampling | Trade-off |
|---|---|---|---|
| **(A)** | `claude-opus-4-7` | no `temperature` | most capable; determinism via low effort + tight prompt, not a temp knob. Sampling mismatch documented as a caveat. |
| **(B)** | `claude-sonnet-4-6` | `temperature=0` | matches the primary agent's temp-0 setting more closely; less capable. |

The arm is **diagnostic-only and asymmetric** (full diagnostic on the primary model, same
diagnostic on Claude) — it buys "is inversion-blindness model-specific or task-class," not a
full second-model corpus. A documented sampling caveat under (A) is acceptable for that
purpose. The harness runs (A) by default and has a `--sonnet` flag to compare (B).

## How to run

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...        # shell env only — never commit the key
cd procurement-context-disambiguation/runner/spike
python3 claude_spike.py            # option (A): claude-opus-4-7, no temperature
python3 claude_spike.py --sonnet   # option (B): claude-sonnet-4-6, temperature=0
```

## Results (run 2026-05-27, both options)

| Q | Option (A) `claude-opus-4-7`, no temp | Option (B) `claude-sonnet-4-6`, temp=0 |
|---|---|---|
| **Q1 — model reached** | `claude-opus-4-7` ✓ | `claude-sonnet-4-6` ✓ |
| **Q2 — verbatim-scaffold parse** | **CLEAN** — raw JSON object, no fence | **NEEDS SHIM** — wraps in ` ```json ` fences; harness fence-strip handles it |
| **Q3 — sampling** | no `temperature` (as expected; no 400) | `temperature=0` accepted |
| **Q4 — latency** | ~2.6–3.4 s / record | ~2.2–3.1 s / record |
| **Q4 — tokens** | in ~860, out 102–133 | in ~605, out 80–103 |

**Verdict agreement across both models** (3 throwaway records, not corpus): identical on
all three — A `review`, B `review`, C `allow` — under both Opus and Sonnet. Reassuring that
the verdict surface isn't model-fragile on simple cases (says nothing yet about hard cases).

Both options are **runnable**. The arm is feasible either way; the choice is a pin, not a
blocker. The Sonnet fence-wrapping is handled by the harness's existing `try_parse_verdict`
shim (prompt stays byte-identical; only extraction adapts), so parse-format is not a real
discriminator.

## Decision (2026-05-27) — Option (A)

- **Pinned second model**: **`claude-opus-4-7`, no `temperature`, `output_config.effort: low`.**
- **Rationale**: the cross-model arm is diagnostic-only and asymmetric — its purpose is "is
  inversion-blindness model-specific or task-class," so the most capable available second model
  gives the most informative result and the strongest critic-resistance. Pinning the weaker
  Sonnet just to match a temp knob would optimise the wrong variable. Capability > temp-matching
  for this arm.
- **Sampling caveat**: Opus 4.7 has no `temperature`, so the arm does not match the primary
  agent's temp-0 sampling. This is documented in the writeup methods section as a caveat, not a
  confound — no verdict-for-verdict comparability is claimed; the comparison is the reasoning-axis
  rubric distribution. `effort: low` is fixed for near-determinism. Reproducibility is carried by
  the signed receipt, not by temp-0 byte-determinism.
- **Parsing**: Opus returns raw verdict JSON — **no shim needed**. (The harness fence-strip shim
  remains in place and is harmless; it would only have mattered under option B.)

`experiment_design.md` → Locked parameters → "Second model" updated to this pin; PENDING marker
removed. Model line is cleared for the pre-registration tag.
