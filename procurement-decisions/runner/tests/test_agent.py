"""
Tests for the locked-model agent wrapper.

We DO NOT call the OpenAI API in tests — the Agent class accepts a
`client=` injection so a stub returning canned `chat.completions.create`
responses can drive every branch deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from meshqu_runner.agent import (
    Agent,
    AgentCallError,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    normalise_reasoning,
    normalise_verdict,
    projects_to_agreement,
    sha256_reasoning,
    sha256_system_prompt,
)


# ---------------------------------------------------------------------------
# Stub OpenAI client — exactly enough to satisfy `_call_with_format`.
# ---------------------------------------------------------------------------


@dataclass
class _StubMessage:
    content: str


@dataclass
class _StubChoice:
    message: _StubMessage


@dataclass
class _StubResponse:
    choices: list[_StubChoice]


class _StubCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        # Configurable: list of behaviours, one per call.
        # Each entry is either a str (returned as content) or an
        # Exception (raised).
        self.responses: list[Any] = []

    def create(self, **kwargs: Any) -> _StubResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError(
                "stub completions ran out of canned responses — "
                "test set up the wrong number"
            )
        behaviour = self.responses.pop(0)
        if isinstance(behaviour, Exception):
            raise behaviour
        return _StubResponse(choices=[_StubChoice(message=_StubMessage(content=behaviour))])


class _StubChat:
    def __init__(self, completions: _StubCompletions) -> None:
        self.completions = completions


class _StubClient:
    def __init__(self) -> None:
        self.completions = _StubCompletions()
        self.chat = _StubChat(self.completions)


# Synthetic OpenAI-style exception classes — name-matched in _classify_openai_error.
class _BadRequestError(Exception):
    pass


class _RateLimitError(Exception):
    pass


class _TimeoutError(Exception):
    pass


class _APIConnectionError(Exception):
    pass


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestVerdictNormalisation:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("allow", "ALLOW"),
            ("review", "REVIEW"),
            ("deny", "DENY"),
            ("ALLOW", "ALLOW"),
            ("  deny  ", "DENY"),
        ],
    )
    def test_canonical_inputs(self, raw: str, expected: str) -> None:
        assert normalise_verdict(raw) == expected

    @pytest.mark.parametrize("raw", ["maybe", "approve", "", "  ", None, 42, ["allow"]])
    def test_non_canonical_returns_none(self, raw: Any) -> None:
        assert normalise_verdict(raw) is None


class TestAgreementProjection:
    @pytest.mark.parametrize(
        "agent,meshqu,expected",
        [
            ("ALLOW", "ALLOW", True),
            ("DENY", "DENY", True),
            ("REVIEW", "REVIEW", True),
            ("REVIEW", "ALLOW", False),  # REVIEW is its own state
            ("ALLOW", "REVIEW", False),
            ("ALLOW", "DENY", False),
            ("DENY", "ALLOW", False),
        ],
    )
    def test_canonical_pairs(self, agent: str, meshqu: str, expected: bool) -> None:
        assert projects_to_agreement(agent, meshqu) is expected  # type: ignore[arg-type]

    def test_none_propagates(self) -> None:
        assert projects_to_agreement(None, "ALLOW") is None
        assert projects_to_agreement("ALLOW", None) is None
        assert projects_to_agreement(None, None) is None


class TestReasoningHashing:
    def test_normalisation_strips_outer_whitespace(self) -> None:
        assert normalise_reasoning("  hello  ") == "hello"

    def test_normalisation_collapses_line_endings(self) -> None:
        assert normalise_reasoning("a\r\nb\rc\n") == "a\nb\nc"

    def test_same_logical_text_hashes_identically(self) -> None:
        a = sha256_reasoning("hello\r\nworld")
        b = sha256_reasoning("hello\nworld\n  ")
        assert a == b

    def test_different_text_hashes_differently(self) -> None:
        assert sha256_reasoning("hello") != sha256_reasoning("hellp")

    def test_system_prompt_hash_is_reasoning_hash(self) -> None:
        prompt = "system rules\nhere"
        assert sha256_system_prompt(prompt) == sha256_reasoning(prompt)


# ---------------------------------------------------------------------------
# Agent.evaluate behaviours
# ---------------------------------------------------------------------------


def _make_agent(client: _StubClient, prompt: str = "SYSTEM PROMPT") -> Agent:
    return Agent(api_key="sk-test", system_prompt=prompt, client=client)


class TestAgentEvaluate:
    def test_json_object_mode_happy_path(self) -> None:
        client = _StubClient()
        client.completions.responses.append(
            '{"verdict":"allow","reasoning":"All good","recommended_action":"approve"}'
        )
        agent = _make_agent(client)

        resp = agent.evaluate("payload")

        assert resp.parse_status == "ok"
        assert resp.verdict == "ALLOW"
        assert resp.reasoning == "All good"
        assert resp.recommended_action == "approve"
        assert resp.output_mode == "json_object"
        # response_format kwarg should have been passed on the first call.
        assert client.completions.calls[0].get("response_format") == {"type": "json_object"}

    def test_uses_locked_model_and_temperature_by_default(self) -> None:
        client = _StubClient()
        client.completions.responses.append('{"verdict":"deny","reasoning":"x"}')
        agent = _make_agent(client)
        agent.evaluate("payload")
        call = client.completions.calls[0]
        assert call["model"] == LOCKED_MODEL_ID
        assert call["temperature"] == LOCKED_TEMPERATURE
        assert call["max_completion_tokens"] >= 1
        # CRITICAL: never `max_tokens` on the locked model
        assert "max_tokens" not in call

    def test_falls_back_to_plain_text_on_unsupported_response_format(self) -> None:
        client = _StubClient()
        # First call (json_object mode): raises BadRequestError mentioning response_format.
        client.completions.responses.append(
            _BadRequestError("response_format unsupported_parameter")
        )
        # Second call (plain_text mode): succeeds.
        client.completions.responses.append('{"verdict":"review","reasoning":"borderline"}')
        agent = _make_agent(client)

        resp = agent.evaluate("payload")

        assert resp.output_mode == "plain_text"
        assert resp.verdict == "REVIEW"
        # The fallback call should NOT carry response_format.
        assert "response_format" not in client.completions.calls[1]

    @pytest.mark.parametrize(
        "exc_factory,expected_kind",
        [
            (lambda: _RateLimitError("slow down"), "rate_limit"),
            (lambda: _TimeoutError("read timeout"), "timeout"),
            (lambda: _APIConnectionError("connection refused"), "network"),
        ],
    )
    def test_propagates_non_format_errors_as_agent_call_error(
        self, exc_factory: Any, expected_kind: str
    ) -> None:
        client = _StubClient()
        client.completions.responses.append(exc_factory())
        agent = _make_agent(client)
        with pytest.raises(AgentCallError) as excinfo:
            agent.evaluate("payload")
        assert excinfo.value.kind == expected_kind

    def test_invalid_json_parses_as_invalid_json(self) -> None:
        client = _StubClient()
        client.completions.responses.append("not json at all")
        agent = _make_agent(client)
        resp = agent.evaluate("payload")
        assert resp.parse_status == "invalid_json"
        assert resp.verdict is None

    def test_wrong_shape_parses_as_wrong_shape(self) -> None:
        client = _StubClient()
        client.completions.responses.append('["array","not","object"]')
        agent = _make_agent(client)
        resp = agent.evaluate("payload")
        assert resp.parse_status == "wrong_shape"
        assert resp.verdict is None

    def test_invalid_verdict_parses_as_invalid_verdict(self) -> None:
        client = _StubClient()
        client.completions.responses.append(
            '{"verdict":"maybe","reasoning":"borderline"}'
        )
        agent = _make_agent(client)
        resp = agent.evaluate("payload")
        assert resp.parse_status == "invalid_verdict"
        assert resp.verdict is None
        # Reasoning still captured so anomaly logs can include it.
        assert resp.reasoning == "borderline"

    def test_records_latency_in_ms(self) -> None:
        client = _StubClient()
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        agent = _make_agent(client)
        resp = agent.evaluate("payload")
        assert resp.latency_ms >= 0
