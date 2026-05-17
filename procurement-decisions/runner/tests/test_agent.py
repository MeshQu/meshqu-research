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


def _make_agent(
    client: _StubClient,
    prompt: str = "SYSTEM PROMPT",
    *,
    retry_max_attempts: int = 1,  # default to no-retry for existing tests
    sleep_fn=None,
) -> Agent:
    kwargs = {}
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    return Agent(
        api_key="sk-test",
        system_prompt=prompt,
        client=client,
        retry_max_attempts=retry_max_attempts,
        **kwargs,
    )


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


# ---------------------------------------------------------------------------
# Bounded retry + Retry-After behaviour
# ---------------------------------------------------------------------------


class _CapturingSleep:
    """Records every sleep duration without actually sleeping."""

    def __init__(self) -> None:
        self.durations: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.durations.append(seconds)


class _FakeHttpResponse:
    """Mimics the .response attribute on OpenAI errors so we can drive
    the Retry-After extractor."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def _rate_limit_with_retry_after(seconds: str | None) -> _RateLimitError:
    err = _RateLimitError("slow down")
    if seconds is not None:
        err.response = _FakeHttpResponse({"Retry-After": seconds})  # type: ignore[attr-defined]
    return err


class TestRetryBehaviour:
    def test_retries_rate_limit_and_succeeds(self) -> None:
        client = _StubClient()
        # Two rate-limit failures, then success on attempt 3.
        client.completions.responses.append(_RateLimitError("slow"))
        client.completions.responses.append(_RateLimitError("slow"))
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = _make_agent(
            client,
            retry_max_attempts=3,
            sleep_fn=sleep,
        )

        resp = agent.evaluate("payload")

        assert resp.parse_status == "ok"
        assert resp.verdict == "ALLOW"
        assert resp.retry_count == 2  # two retries fired
        assert len(sleep.durations) == 2  # two sleeps before the successful attempt

    def test_retries_exhausted_raises_last_classified_error(self) -> None:
        client = _StubClient()
        client.completions.responses.extend(
            [_TimeoutError("read timeout") for _ in range(3)]
        )
        sleep = _CapturingSleep()
        agent = _make_agent(client, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(AgentCallError) as excinfo:
            agent.evaluate("payload")

        assert excinfo.value.kind == "timeout"
        # 3 attempts → 2 backoff sleeps (no sleep AFTER the last failure)
        assert len(sleep.durations) == 2

    def test_auth_error_not_retried(self) -> None:
        client = _StubClient()
        # Synthesise an AuthenticationError look-alike: must have
        # "AuthenticationError" in the class name to classify correctly.
        class _AuthenticationError(Exception):
            pass

        # If retried, we'd need 3 copies — we only provide 1 to prove
        # the agent gave up after the first attempt.
        client.completions.responses.append(_AuthenticationError("bad key"))
        sleep = _CapturingSleep()
        agent = _make_agent(client, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(AgentCallError) as excinfo:
            agent.evaluate("payload")

        assert excinfo.value.kind == "auth"
        assert sleep.durations == []  # no backoff before terminal error

    def test_unsupported_param_does_not_consume_retry_budget(self) -> None:
        """The json_object → plain_text fallback should NOT burn retries
        on the deterministic unsupported_param rejection."""
        client = _StubClient()
        # First call: response_format unsupported → fall through.
        client.completions.responses.append(
            _BadRequestError("response_format unsupported_parameter")
        )
        # Second call (plain_text mode): succeed immediately.
        client.completions.responses.append('{"verdict":"deny","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = _make_agent(client, retry_max_attempts=3, sleep_fn=sleep)

        resp = agent.evaluate("payload")

        assert resp.parse_status == "ok"
        assert resp.output_mode == "plain_text"
        assert resp.retry_count == 0
        assert sleep.durations == []

    def test_honours_retry_after_header_over_exponential(self) -> None:
        client = _StubClient()
        client.completions.responses.append(_rate_limit_with_retry_after("5"))
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = _make_agent(
            client,
            retry_max_attempts=3,
            sleep_fn=sleep,
        )

        resp = agent.evaluate("payload")
        assert resp.verdict == "ALLOW"
        # Retry-After=5s is a MINIMUM. With positive-only jitter (+0..+20%)
        # we expect 5s ≤ slept ≤ 6s — never below the server's floor.
        assert len(sleep.durations) == 1
        assert 5.0 <= sleep.durations[0] <= 6.0

    def test_retry_after_never_sleeps_below_server_floor(self) -> None:
        """Regression: ±20% jitter could undershoot Retry-After=5 to 4s,
        violating the server's back-pressure guidance. Force jitter_fn
        to return 0 (worst-case downward bias if signed jitter were
        applied) and assert the sleep is still >= Retry-After."""
        client = _StubClient()
        client.completions.responses.append(_rate_limit_with_retry_after("5"))
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = Agent(
            api_key="sk-test",
            system_prompt="P",
            client=client,
            retry_max_attempts=3,
            sleep_fn=sleep,
            jitter_fn=lambda: 0.0,
        )

        agent.evaluate("payload")
        assert sleep.durations == [5.0]  # no negative jitter applied

    def test_caps_retry_after_at_max_backoff(self) -> None:
        client = _StubClient()
        # Malicious / broken server: Retry-After=600s
        client.completions.responses.append(_rate_limit_with_retry_after("600"))
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = Agent(
            api_key="sk-test",
            system_prompt="P",
            client=client,
            retry_max_attempts=3,
            retry_max_backoff_seconds=10.0,
            sleep_fn=sleep,
        )

        agent.evaluate("payload")
        assert len(sleep.durations) == 1
        # cap=10s, positive-only jitter (+0..+20%) → 10s ≤ slept ≤ 12s
        assert 10.0 <= sleep.durations[0] <= 12.0

    def test_retries_carry_across_json_to_plain_text_fallback(self) -> None:
        """Regression: a sequence like (429, 429, unsupported_param,
        success) used to report retry_count=0 because the
        unsupported_param fallback discarded the retries spent in
        json_object mode. Must report retry_count=2."""
        client = _StubClient()
        # json_object mode: two transient 429s, then unsupported_param.
        client.completions.responses.append(_RateLimitError("slow"))
        client.completions.responses.append(_RateLimitError("slow"))
        client.completions.responses.append(
            _BadRequestError("response_format unsupported_parameter")
        )
        # plain_text mode: success on first attempt.
        client.completions.responses.append('{"verdict":"allow","reasoning":"x"}')
        sleep = _CapturingSleep()
        agent = _make_agent(client, retry_max_attempts=3, sleep_fn=sleep)

        resp = agent.evaluate("payload")
        assert resp.parse_status == "ok"
        assert resp.output_mode == "plain_text"
        assert resp.retry_count == 2  # carry-over from json_object mode

    def test_retry_count_persists_through_parse_failure(self) -> None:
        """A successful HTTP call after retries that returns malformed
        JSON should still report retry_count > 0 in the AgentResponse so
        the writeup can correlate retries with parse failures."""
        client = _StubClient()
        client.completions.responses.append(_TimeoutError("slow"))
        client.completions.responses.append("not json")
        sleep = _CapturingSleep()
        agent = _make_agent(client, retry_max_attempts=3, sleep_fn=sleep)

        resp = agent.evaluate("payload")
        assert resp.parse_status == "invalid_json"
        assert resp.retry_count == 1
