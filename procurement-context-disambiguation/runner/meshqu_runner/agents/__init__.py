"""Agent adapters — model-keyed dispatch table for the E3 runner.

E3 introduces a second model (`claude-opus-4-7`) for the diagnostic
cross-model arm. The runner needs to route an arm's chosen model_id to
the right SDK adapter. This module is the registration point.

## Registration shape

Each adapter exposes a top-level callable ``call(system_prompt,
user_message, client=None) -> dict`` returning a normalised verdict
payload:

    {
      "verdict": "allow" | "review" | "deny" | None,
      "reasoning": str,
      "recommended_action": str | None,
      "raw": str,
      "usage": {"input_tokens": int, "output_tokens": int},
      "model": str,
      "latency_ms": int,
    }

The ``DISPATCH`` map below routes a model_id to its adapter's ``call``
function. Arms set the model_id they need (via ``ArmProfile.model_id``);
the runner consults ``DISPATCH`` to pick the adapter. The default model
is the primary (`gpt-5.4-2026-03-05`); the Claude adapter activates for
the ``diagnostic_claude`` arm.

## Why this lives alongside ``meshqu_runner.agent``

``meshqu_runner.agent`` still hosts the primary OpenAI ``Agent`` class
that the existing ``run_arm`` flow drives via ``agent.evaluate(...)``.
That surface is preserved verbatim — E2's primary path stays
byte-identical. This module adds the parallel adapter layer for the
cross-model arm without disturbing the primary path: the spec's
``DISPATCH`` dict gives a clean lookup by model_id, and ``primary.call``
+ ``claude.call`` are the two adapter functions registered there.
"""

from __future__ import annotations

from typing import Callable

from .claude import call as claude_call
from .primary import call as primary_call

AdapterCall = Callable[..., dict]
"""All adapters share this signature: ``call(system_prompt: str,
user_message: str, client=None) -> dict``. The ``client=`` kwarg is
optional — adapters construct one lazily from env when omitted."""


DISPATCH: dict[str, AdapterCall] = {
    "gpt-5.4-2026-03-05": primary_call,
    "claude-opus-4-7": claude_call,
}
"""Model-id → adapter ``call`` function. Arms set ``model_id`` (via
``ArmProfile.model_id`` or the CLI ``--model`` override); the runner
looks up the call function here. Unknown model ids raise ``KeyError``
in ``dispatch_call`` — better to surface than to silently fall back."""


def dispatch_call(model_id: str) -> AdapterCall:
    """Resolve ``model_id`` to its adapter's ``call`` function.

    Raises ``KeyError`` if the model isn't registered — same posture as
    ``meshqu_runner.arms.dispatch``. Callers (the runner / tests) catch
    and translate to a runner-level error if they want a softer surface.
    """
    if model_id not in DISPATCH:
        raise KeyError(
            f"No adapter registered for model_id {model_id!r}. "
            f"Known models: {sorted(DISPATCH)!r}."
        )
    return DISPATCH[model_id]


__all__ = [
    "AdapterCall",
    "DISPATCH",
    "dispatch_call",
    "claude_call",
    "primary_call",
]
