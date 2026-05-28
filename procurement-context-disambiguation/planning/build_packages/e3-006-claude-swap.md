# E3-006 — Claude cross-model swap (anthropic SDK adapter)

You are a background agent. This package adds the second-model adapter for the diagnostic cross-model arm. The model pin is **already resolved** (`claude-opus-4-7`, no `temperature`, `output_config.effort: low`) and the feasibility spike has already confirmed the verbatim E2 scaffold parses cleanly on Opus. Your job is to wire it into the runner properly — not to re-litigate the pin.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 3 + § Locked parameters → "Second model"
- `procurement-context-disambiguation/planning/feasibility_spike_claude.md` — **read this in full**; the results, decision, and sampling caveat are all spelled out
- `procurement-context-disambiguation/runner/spike/claude_spike.py` — **the working reference implementation** (typed exception handling, fence-strip shim, verdict-JSON parser); your adapter generalises this
- `procurement-context-disambiguation/runner/system_prompt.md` — the verbatim E2 system prompt; the adapter MUST use this byte-identically
- `procurement-context-gradient/runner/meshqu_runner/agent.py` — E2's primary-agent adapter (openai SDK); template for the structure of yours
- The Anthropic Python SDK docs for `claude-opus-4-7` — Opus 4.7 removed `temperature`/`top_p`/`top_k`; thinking content is omitted by default; `output_config.effort` is a top-level sampling parameter

**Hard dependencies**: E3-001 merged.

## Goal

Add an Anthropic SDK adapter at `meshqu_runner/agents/claude.py` that exposes the same call interface as E2's primary agent, but talks to `claude-opus-4-7`. The runner's agent dispatcher selects this adapter when the arm name is `diagnostic_claude` (or when `--model claude-opus-4-7` is passed via CLI).

## Scope

### 1. Adapter

`meshqu_runner/agents/claude.py`:

```python
import anthropic
from anthropic import (
    NotFoundError, AuthenticationError, PermissionDeniedError,
    BadRequestError, APIError,
)

MODEL_ID = "claude-opus-4-7"
MAX_TOKENS = 1024

def make_client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY from env. Raises if absent.
    return anthropic.Anthropic()

def call(
    system_prompt: str,
    user_message: str,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """
    Returns a parsed verdict object: {"verdict": str, "reasoning": str,
    "recommended_action": str, "raw": str, "usage": {...},
    "model": str, "latency_ms": int}.
    """
    client = client or make_client()
    # NO temperature param (Opus 4.7 removed it — sending it 400s).
    # effort: low for near-determinism on this classification-style task.
    resp = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        output_config={"effort": "low"},
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    parsed = parse_verdict_json(raw)  # reuses spike's fence-strip shim
    return {
        "verdict": parsed.get("verdict"),
        "reasoning": parsed.get("reasoning"),
        "recommended_action": parsed.get("recommended_action"),
        "raw": raw,
        "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        "model": resp.model,
        "latency_ms": ...,
    }
```

- Lift `parse_verdict_json` (with the fence-strip shim) from `runner/spike/claude_spike.py`. Opus parses clean (no fence) but the shim is harmless if a future Sonnet fallback is ever needed.
- Surface the typed Anthropic exceptions (NotFound / Authentication / PermissionDenied / BadRequest / APIError) — wrap into runner-level errors with the same message style E2's agent uses.

### 2. Receipt integrity

When the agent dispatcher selects this adapter, the receipt integrity payload sets:

- `model_id: "claude-opus-4-7"`
- `model_sampling: {"temperature": null, "effort": "low", "max_tokens": 1024}`
- `model_provider: "anthropic"`
- The `runner_git_commit` and `prereg_tag` fields stay as set by the foundation.

The methods-caveat note (no temperature available on Opus 4.7) is documented in the writeup — the receipt records the *fact* (`temperature: null`), not the rationale.

### 3. Agent dispatcher wiring

`meshqu_runner/agents/__init__.py` (or wherever the foundation centralised this):

```python
from meshqu_runner.agents.primary import call as primary_call
from meshqu_runner.agents.claude import call as claude_call

DISPATCH = {
    "gpt-5.4-2026-03-05": primary_call,
    "claude-opus-4-7": claude_call,
}
```

Arms set the `model_id` they need; the dispatcher picks the adapter. Default model is the primary; the Claude adapter activates for `diagnostic_claude`.

### 4. Tests

`tests/test_claude_adapter.py`:

- Mocked client: assert `client.messages.create` is called with `model="claude-opus-4-7"`, no `temperature` key in the call kwargs, and `output_config={"effort": "low"}`.
- Mocked client returning a clean JSON response: `call()` returns a parsed dict with `verdict`, `reasoning`, `recommended_action`.
- Mocked client returning a fenced JSON response: still parses cleanly (shim works).
- Typed exception handling: each of NotFound / Authentication / PermissionDenied / BadRequest surfaces as a runner-level error.
- `ANTHROPIC_API_KEY` absent: `make_client()` raises with a clear message.
- The receipt payload built around a `claude-opus-4-7` call sets all the expected `model_*` fields.
- **NO live API call in tests.** All mocked.

### 5. PR body must answer

- Confirmation that the SDK call signature matches the spike (no `temperature`, `effort: "low"`, verbatim system prompt).
- The list of exception types handled.
- A pointer to where the receipt schema records `model_*` fields.
- (Do NOT run a live call from CI. The smoke/dry-run packages will exercise the live path.)

## Decision rules

- **No temperature.** Opus 4.7 removed it; sending it 400s. This is the spike's headline finding.
- **`effort: low` is part of the pin.** Don't add a CLI flag to vary it; the pre-registration tag binds it.
- **Verbatim system prompt.** The cross-model arm's claim rests on byte-identical instructions. Don't refactor or "improve" the system prompt for Claude.
- **Receipt records the sampling fact, not the caveat.** Methods caveat ("no temperature available") goes in the writeup; the receipt records `temperature: null`.

## Out of scope

- The diagnostic runner itself (E3-008).
- Subset selection (E3-007).
- Switching to Sonnet (the pin is Opus; if a future revisit is needed, it's a tag amendment, not an agent decision).
- Live integration testing (smoke/dry-run packages).

## Definition of done

- Branch `feat/e3-006-claude-swap`.
- `meshqu_runner/agents/claude.py` implements the adapter as specified.
- Agent dispatcher routes by `model_id`.
- Mock-based tests pass; no live calls in CI.
- Receipt payload extends cleanly per the integrity schema from E3-001.

## Stop conditions

- The Anthropic SDK version pinned in the runner's requirements doesn't accept `output_config.effort` → STOP. Bump the SDK version (it's GA, no beta header needed) and document the bump in `decision_log.md`.
- The verbatim system prompt parses but produces wildly different verdict shapes than the spike showed → STOP. The spike used 3 throwaway records; a smoke-set surprise here is the early signal the decision-point flagged (master plan, point 5).
- The schema-version bump for the `model_*` fields conflicts with E2's bundle envelope contract → STOP, surface. The foundation should have already handled this; if not, propagate the question.
