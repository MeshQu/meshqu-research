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

## Results

_To be filled in after the run._

- **Q1 — model reached**: _<resp.model from the run>_
- **Q2 — verbatim-scaffold parse**: _CLEAN / NEEDS SHIM / FAILED_
- **Q3 — sampling**: _option run + whether it 400'd_
- **Q4 — latency / tokens**: _per-record_

## Decision (record before the tag)

- **Pinned second model**: _TBD — (A) or (B)_
- **Rationale**: _TBD_
- **Sampling caveat (if A)**: _document in the writeup methods section_

Once decided, update `experiment_design.md` → Locked parameters → "Second model" with the
final pin and remove the PENDING marker.
