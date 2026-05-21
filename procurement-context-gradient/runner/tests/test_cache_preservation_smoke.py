"""LIVE smoke test for L4 cache preservation — E2-005.

Authored as the empirical verification of the cache-friendly L4
placement. Marked `@pytest.mark.live` so a default `pytest` run
SKIPS this test. To run it:

    OPENAI_API_KEY=sk-... pytest -m live procurement-context-gradient/runner/tests/test_cache_preservation_smoke.py

What it verifies
----------------
The runner posts three L4-only calls back-to-back against the live
OpenAI model. The second and third calls must report
`cached_tokens > 0` in OpenAI's `usage.prompt_tokens_details` block —
that is the empirical signal that the ~4,500-token policy block sat
inside OpenAI's cached prefix.

If `cached_tokens == 0` on the second call:

- Either the cache hasn't built up yet (some OpenAI deployments take
  a few seconds to register the prefix — the test waits 2s between
  calls to give it a chance), OR
- The composition order is wrong (policy not at the head of the
  message), OR
- The model doesn't support prompt caching for this prompt size.

The test reports all three numbers + asserts on the second-call hit
so a failure tells you exactly which condition triggered.

Why this isn't part of the default suite
----------------------------------------
This calls the real OpenAI API and costs real money (~$0.05 for the
smoke run at the locked model rate). The default `pytest` MUST run
hermetic.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from meshqu_runner.agent import Agent, load_system_prompt
from meshqu_runner.context_levels.level_l4 import build_l4_handler
from meshqu_runner.level_handlers import (
    L0Handler,
    L1Handler,
    L2Handler,
    L3Handler,
    compose_user_message,
)
from meshqu_runner.prompt_loader import load_level_prompts


RUNNER_DIR = Path(__file__).resolve().parent.parent
E2_DIR = RUNNER_DIR.parent
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"
FIXTURE_PATH = RUNNER_DIR / "tests" / "fixtures" / "smoke_records.json"


pytestmark = pytest.mark.live


def _load_records() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def test_l4_cache_preservation_three_records() -> None:
    """Send three L4 prompts; expect cached_tokens > 0 on call #2 and
    call #3.

    Skips automatically when:
      - `OPENAI_API_KEY` is unset (CI / hermetic dev).
      - `pytest` was invoked without `-m live` (the module's marker
        excludes it from the default selection).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY unset — live smoke not runnable")

    # Build the production L4 handler and the standard registry.
    handler = build_l4_handler(POLICY_SNAPSHOT_PATH)
    handlers = {
        "L0": L0Handler(),
        "L1": L1Handler(),
        "L2": L2Handler(),
        "L3": L3Handler(),
        "L4": handler,
    }
    prompts = load_level_prompts(PROMPTS_DIR)
    handler.render(prompts)

    # Live agent against the locked model.
    system_prompt = load_system_prompt()
    agent = Agent(api_key=api_key, system_prompt=system_prompt)

    records = _load_records()[:3]
    cached_tokens_by_call: list[int | None] = []
    prompt_tokens_by_call: list[int | None] = []

    for i, record in enumerate(records):
        # Reuse the eval_loop's user-message format so the live test
        # mirrors what the multi_pass orchestrator sends.
        from meshqu_runner.eval_loop import build_user_message

        base = build_user_message(
            context={
                "decision_type": record.get("decision_type"),
                "fields": record.get("fields") or {},
            },
            substrate_notes={},
        )
        user_message = compose_user_message(
            level="L4",
            record=record,
            ocid=record.get("ocid"),
            prompts=prompts,
            handlers=handlers,
            base_message=base,
        )
        response = agent.evaluate(user_message)
        cached_tokens_by_call.append(response.cached_tokens)
        prompt_tokens_by_call.append(response.prompt_tokens)

        # Brief pause so OpenAI's cache has time to register the prefix
        # before the next call. 2s is empirically generous; the first
        # cache hit usually appears on call #2 with no wait.
        if i < len(records) - 1:
            time.sleep(2)

    # Diagnostic dump — visible on failure.
    print("\ncached_tokens by L4 call:", cached_tokens_by_call)
    print("prompt_tokens by L4 call:", prompt_tokens_by_call)

    # First call: cache miss is expected (cold prefix). Don't assert.
    # Second call: at least one cached token expected — this is the
    # load-bearing signal. If this fails the placement is wrong.
    assert cached_tokens_by_call[1] is not None, (
        "Second call's response carried no usage info — OpenAI SDK "
        "shape may have changed; check _extract_usage_tokens in agent.py"
    )
    assert cached_tokens_by_call[1] > 0, (
        f"Second L4 call shows cached_tokens={cached_tokens_by_call[1]}; "
        "expected > 0 because the policy block + system prompt are "
        "stable across calls. Check L4 composition order."
    )

    # Third call: cache hit should grow OR hold steady (cache is
    # additive within the prefix).
    assert cached_tokens_by_call[2] is not None
    assert cached_tokens_by_call[2] >= cached_tokens_by_call[1], (
        f"Third call's cached_tokens={cached_tokens_by_call[2]} fell "
        f"below second call's {cached_tokens_by_call[1]} — cache "
        "appears to have invalidated between calls. Investigate."
    )
