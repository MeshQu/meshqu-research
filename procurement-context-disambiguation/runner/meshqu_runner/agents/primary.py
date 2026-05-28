"""Primary-agent adapter — thin functional wrapper around
``meshqu_runner.agent.Agent`` (OpenAI / ``gpt-5.4-2026-03-05``).

The runner's existing ``Agent`` class is the canonical primary surface
— it carries the locked-model retry loop, JSON-mode preference, prompt
hashing, and the verdict normaliser. This module gives that surface a
``call(system_prompt, user_message, client=None) -> dict`` shape so the
``DISPATCH`` table in ``meshqu_runner.agents`` can key it uniformly
with the Claude adapter.

Existing callers that already construct an ``Agent`` and invoke
``.evaluate(user_message)`` are unaffected — this adapter wraps the
same path without changing it.
"""

from __future__ import annotations

import os
from typing import Any

from ..agent import (
    Agent,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    load_system_prompt,
)


def call(
    system_prompt: str,
    user_message: str,
    client: Any | None = None,
) -> dict:
    """Run one primary-model agent call. Returns a normalised payload
    matching the adapter contract documented in
    ``meshqu_runner.agents.__init__``.

    A ``client`` may be injected for tests; otherwise an ``OpenAI``
    client is constructed from ``OPENAI_API_KEY``.

    Note: this is a functional convenience that wraps ``Agent``. The
    ``run_arm`` orchestrator drives ``Agent.evaluate`` directly and
    does NOT go through this adapter. The adapter exists so that the
    ``DISPATCH`` map has a uniform shape across the primary + Claude
    paths — useful for tests, smoke tooling, and the methodology
    extraction in Phase 4.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    agent = Agent(
        api_key=api_key,
        system_prompt=system_prompt,
        client=client,
    )
    response = agent.evaluate(user_message)
    return {
        "verdict": response.verdict.lower() if response.verdict else None,
        "reasoning": response.reasoning,
        "recommended_action": response.recommended_action,
        "raw": response.raw_response,
        "usage": {
            "input_tokens": response.prompt_tokens,
            "output_tokens": None,  # OpenAI's chat response exposes
            # `completion_tokens` separately; the primary path's
            # AgentResponse only carries prompt_tokens + cached_tokens.
            # Future work: surface completion_tokens too if a cross-
            # adapter usage analysis ever needs it.
        },
        "model": getattr(agent, "model_id", LOCKED_MODEL_ID),
        "latency_ms": response.latency_ms,
    }


__all__ = ["call", "LOCKED_MODEL_ID", "LOCKED_TEMPERATURE", "load_system_prompt"]
