"""Tests for the Claude (Anthropic) adapter — ``meshqu_runner.agents.claude``.

Every test mocks the Anthropic SDK; no live API calls. The asserts in
this file enforce the contract from the package spec
(``planning/build_packages/e3-006-claude-swap.md``):

- SDK call signature: ``model="claude-opus-4-7"``, NO ``temperature``
  key, ``output_config={"effort": "low"}``, ``max_tokens=1024``,
  ``system=<verbatim E2 prompt>``.
- Verdict-JSON parser: clean Opus response parses cleanly; the
  fence-strip shim handles Sonnet-style ` ```json ... ``` `.
- Typed Anthropic exceptions get wrapped into ``ClaudeAdapterError``
  with the expected ``kind``.
- ``make_client()`` raises a clean error when ``ANTHROPIC_API_KEY`` is
  absent.
- The Claude arm's receipt integrity payload sets ``model_id``,
  ``model_sampling`` (with ``temperature: None``), ``diagnostic: True``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

import anthropic

from meshqu_runner.agents import DISPATCH, dispatch_call
from meshqu_runner.agents.claude import (
    MAX_TOKENS,
    MODEL_ID,
    OUTPUT_CONFIG,
    ClaudeAdapterError,
    call as claude_call,
    make_client,
    parse_verdict_json,
)
from meshqu_runner.arms import (
    CLAUDE_MODEL_ID,
    CLAUDE_MODEL_SAMPLING,
    inject_arm_fields,
)


# ---------------------------------------------------------------------------
# Stub Anthropic client — captures the kwargs of every call
# ---------------------------------------------------------------------------


@dataclass
class _StubTextBlock:
    text: str
    type: str = "text"


@dataclass
class _StubUsage:
    input_tokens: int = 860
    output_tokens: int = 102


@dataclass
class _StubMessagesResponse:
    content: list[_StubTextBlock]
    model: str = MODEL_ID
    usage: _StubUsage = _StubUsage()


class _StubMessages:
    """Captures kwargs from each ``create()`` call. Returns a queued
    response (text str or Exception)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: list[Any] = []

    def create(self, **kwargs: Any) -> _StubMessagesResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError(
                "stub messages.create ran out of canned responses — "
                "test set up the wrong number"
            )
        behaviour = self.responses.pop(0)
        if isinstance(behaviour, Exception):
            raise behaviour
        # Allow tests to push either a raw string body or a fully formed
        # _StubMessagesResponse for richer assertions.
        if isinstance(behaviour, _StubMessagesResponse):
            return behaviour
        return _StubMessagesResponse(content=[_StubTextBlock(text=behaviour)])


class _StubClient:
    def __init__(self) -> None:
        self.messages = _StubMessages()


# ---------------------------------------------------------------------------
# SDK call shape — the headline contract for the package
# ---------------------------------------------------------------------------


def test_call_uses_claude_opus_4_7_with_no_temperature_and_effort_low():
    """The spike's headline finding: Opus 4.7 has no ``temperature``
    (sending it 400s); the pin is ``effort: low``. Assert by inspecting
    the actual kwargs the SDK is invoked with."""
    client = _StubClient()
    client.messages.responses.append(
        json.dumps(
            {
                "verdict": "review",
                "reasoning": "stubbed reasoning",
                "recommended_action": "follow up",
            }
        )
    )

    claude_call("SYSTEM PROMPT", "USER MESSAGE", client=client)

    assert len(client.messages.calls) == 1
    kwargs = client.messages.calls[0]
    assert kwargs["model"] == "claude-opus-4-7"
    assert kwargs["model"] == MODEL_ID
    assert "temperature" not in kwargs, (
        "Opus 4.7 removed temperature; sending it returns 400. "
        "The adapter MUST NOT pass a temperature kwarg."
    )
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["output_config"] == OUTPUT_CONFIG
    assert kwargs["max_tokens"] == 1024
    assert kwargs["max_tokens"] == MAX_TOKENS
    assert kwargs["system"] == "SYSTEM PROMPT"
    assert kwargs["messages"] == [{"role": "user", "content": "USER MESSAGE"}]


def test_call_uses_verbatim_system_prompt_byte_identical_to_input():
    """Cross-model arm's whole claim rests on byte-identical
    instructions to the primary model. The adapter must NOT mutate,
    trim, or re-encode the system prompt."""
    client = _StubClient()
    client.messages.responses.append(
        json.dumps({"verdict": "allow", "reasoning": ""})
    )
    # Include trailing whitespace, embedded newlines, unicode — none
    # of which the adapter should touch.
    system_prompt = "Line 1\nLine 2  \nLine 3 — em-dash\n"
    claude_call(system_prompt, "user", client=client)
    assert client.messages.calls[0]["system"] == system_prompt


# ---------------------------------------------------------------------------
# Verdict JSON parser — clean Opus response + fence-strip shim
# ---------------------------------------------------------------------------


def test_call_returns_parsed_dict_on_clean_json_response():
    """Opus returns raw JSON, no fence. Adapter parses cleanly."""
    client = _StubClient()
    client.messages.responses.append(
        json.dumps(
            {
                "verdict": "review",
                "reasoning": "Concerning timing pattern.",
                "recommended_action": "Request publication-delay rationale.",
            }
        )
    )
    out = claude_call("sys", "user", client=client)
    assert out["verdict"] == "review"
    assert out["reasoning"] == "Concerning timing pattern."
    assert out["recommended_action"] == "Request publication-delay rationale."
    assert isinstance(out["raw"], str)
    assert out["model"] == MODEL_ID
    assert out["usage"] == {"input_tokens": 860, "output_tokens": 102}
    assert isinstance(out["latency_ms"], int)
    assert out["latency_ms"] >= 0


def test_call_handles_fenced_json_response_via_shim():
    """The fence-strip shim from the spike is kept defensively. Even
    though Opus parses clean, the shim must still work — protects
    against a future Sonnet fallback (option B in the spike report)."""
    client = _StubClient()
    fenced = (
        "```json\n"
        + json.dumps(
            {"verdict": "deny", "reasoning": "Clear breach.", "recommended_action": "Block"}
        )
        + "\n```"
    )
    client.messages.responses.append(fenced)
    out = claude_call("sys", "user", client=client)
    assert out["verdict"] == "deny"
    assert out["reasoning"] == "Clear breach."


def test_parse_verdict_json_strips_bare_backticks_no_lang_tag():
    """Some Sonnet variants emit ``` without a `json` language tag."""
    obj = parse_verdict_json("```\n" + json.dumps({"verdict": "allow"}) + "\n```")
    assert obj["verdict"] == "allow"


def test_parse_verdict_json_clean_no_fence():
    obj = parse_verdict_json(json.dumps({"verdict": "review"}))
    assert obj["verdict"] == "review"


def test_parse_verdict_json_raises_on_invalid_json():
    with pytest.raises(ClaudeAdapterError) as exc_info:
        parse_verdict_json("this is not JSON {")
    assert exc_info.value.kind == "parse"


def test_parse_verdict_json_raises_on_non_object_top_level():
    """A bare string or array at top level isn't a verdict object —
    same posture as the OpenAI adapter's ``wrong_shape``."""
    with pytest.raises(ClaudeAdapterError) as exc_info:
        parse_verdict_json('"just a string"')
    assert exc_info.value.kind == "parse"


def test_call_returns_none_verdict_for_out_of_vocab():
    """The system prompt constrains the model to {allow, review, deny}.
    Anything outside that surfaces as ``verdict=None`` (parse failure),
    NOT a fourth tier passed through silently."""
    client = _StubClient()
    client.messages.responses.append(
        json.dumps({"verdict": "MAYBE", "reasoning": "uncertain"})
    )
    out = claude_call("sys", "user", client=client)
    assert out["verdict"] is None
    # The non-verdict fields still surface — useful for debugging.
    assert out["reasoning"] == "uncertain"


def test_call_normalises_uppercase_verdict_to_lowercase():
    """The system prompt asks for lowercase; defensive normalisation."""
    client = _StubClient()
    client.messages.responses.append(json.dumps({"verdict": "ALLOW"}))
    out = claude_call("sys", "user", client=client)
    assert out["verdict"] == "allow"


# ---------------------------------------------------------------------------
# Typed Anthropic exception handling
# ---------------------------------------------------------------------------


def _make_anthropic_error(cls):
    """Construct an Anthropic SDK typed exception for tests.

    The SDK's typed errors (NotFoundError / AuthenticationError /
    PermissionDeniedError / BadRequestError) take a message + a real
    ``httpx.Response`` + body kwargs — they call ``response.request``
    in ``__init__``. We build a minimal real httpx.Response so the
    constructor works without a live HTTP call.
    """
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=400, request=request)
    try:
        return cls("synthetic error message", response=response, body=None)
    except TypeError:
        # Fallback for SDK versions with a simpler constructor.
        return cls("synthetic error message")


def test_call_wraps_not_found_error():
    client = _StubClient()
    client.messages.responses.append(_make_anthropic_error(anthropic.NotFoundError))
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "not_found"


def test_call_wraps_authentication_error():
    client = _StubClient()
    client.messages.responses.append(
        _make_anthropic_error(anthropic.AuthenticationError)
    )
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "auth"


def test_call_wraps_permission_denied_error():
    client = _StubClient()
    client.messages.responses.append(
        _make_anthropic_error(anthropic.PermissionDeniedError)
    )
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "permission"


def test_call_wraps_bad_request_error_as_bad_request():
    """A 400 — e.g. from any future drift in the API contract that
    re-introduced a forbidden param — surfaces as ``bad_request`` so
    the eval loop can log and surface it loudly."""
    client = _StubClient()
    client.messages.responses.append(
        _make_anthropic_error(anthropic.BadRequestError)
    )
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "bad_request"


def test_call_wraps_generic_api_error():
    """Catch-all APIError — 5xx, network glitches the SDK exposes as
    generic APIError. Mapped to kind ``api``."""

    class _FakeAPIError(anthropic.APIError):
        def __init__(self):
            self.message = "synthetic"
            self.body = None
            self.request = None  # type: ignore[assignment]

        def __str__(self):
            return "synthetic"

    client = _StubClient()
    client.messages.responses.append(_FakeAPIError())
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "api"


# ---------------------------------------------------------------------------
# make_client() — env-var precondition
# ---------------------------------------------------------------------------


def test_make_client_raises_without_anthropic_api_key(monkeypatch):
    """The adapter requires a live key; surface its absence loudly so
    the test isn't deferred to the SDK's first-call lazy error."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ClaudeAdapterError) as exc_info:
        make_client()
    assert exc_info.value.kind == "auth"
    assert "ANTHROPIC_API_KEY" in exc_info.value.detail


def test_make_client_returns_anthropic_client_with_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-test-key")
    client = make_client()
    assert isinstance(client, anthropic.Anthropic)


# ---------------------------------------------------------------------------
# DISPATCH map wiring
# ---------------------------------------------------------------------------


def test_dispatch_table_maps_claude_opus_to_claude_call():
    assert DISPATCH["claude-opus-4-7"] is claude_call
    assert dispatch_call("claude-opus-4-7") is claude_call


def test_dispatch_table_includes_primary_model():
    """The DISPATCH map carries both adapters — the spec is explicit."""
    assert "gpt-5.4-2026-03-05" in DISPATCH


def test_dispatch_call_raises_on_unknown_model():
    with pytest.raises(KeyError, match="No adapter registered"):
        dispatch_call("not-a-real-model")


# ---------------------------------------------------------------------------
# Receipt integrity payload — Claude arm sets all expected fields
# ---------------------------------------------------------------------------


def test_receipt_payload_for_claude_arm_records_model_fields():
    """End-to-end: ``inject_arm_fields`` for the ``diagnostic_claude``
    arm produces the integrity payload the runner will sign. The payload
    must record:

    - ``model_id: "claude-opus-4-7"``
    - ``model_sampling.temperature == None`` (records the *fact* of the
      no-temperature pin; the writeup methods section interprets it)
    - ``model_sampling.effort == "low"``
    - ``diagnostic: True``
    - ``policy_permutation_seed`` non-None (diagnostic gate)

    This is the "stub-signer test output" the package spec calls for in
    the PR body."""
    base_context = {"fields": {}}
    enriched = inject_arm_fields(
        base_context,
        arm_name="diagnostic_claude",
        runner_git_commit="deadbeef-test",
        policy_permutation_seed=42,
    )
    f = enriched["fields"]
    assert f["model_id"] == "claude-opus-4-7"
    assert f["model_id"] == CLAUDE_MODEL_ID
    assert f["model_sampling"]["temperature"] is None
    assert f["model_sampling"]["effort"] == "low"
    assert f["model_sampling"] == CLAUDE_MODEL_SAMPLING
    assert f["diagnostic"] is True
    assert f["policy_permutation_seed"] == 42
    assert f["runner_git_commit"] == "deadbeef-test"
    assert f["prereg_tag"] == "v0.3-predictions-locked"
    assert f["nudge_excised"] is False
    assert f["l3_arm"] is None


def test_receipt_payload_model_sampling_block_omits_temperature_field_implicitly():
    """The sampling block records ``temperature: None`` — the field is
    present and explicitly None, NOT omitted. A verifier asking "what
    sampling did this run use" gets the same answer whether or not
    Opus accepts the param: the receipt records the call shape."""
    enriched = inject_arm_fields(
        {"fields": {}},
        arm_name="diagnostic_claude",
        runner_git_commit="commit",
        policy_permutation_seed=7,
    )
    sampling = enriched["fields"]["model_sampling"]
    assert "temperature" in sampling
    assert sampling["temperature"] is None


# ---------------------------------------------------------------------------
# Edge: empty content block list (defensive)
# ---------------------------------------------------------------------------


def test_call_handles_response_with_no_text_blocks():
    """If the SDK returns an empty content list, the adapter raises a
    parse error (no JSON to parse) rather than silently returning a
    None-verdict payload."""
    client = _StubClient()
    client.messages.responses.append(
        _StubMessagesResponse(content=[])
    )
    with pytest.raises(ClaudeAdapterError) as exc_info:
        claude_call("sys", "user", client=client)
    assert exc_info.value.kind == "parse"


def test_call_response_with_mixed_blocks_concatenates_text():
    """If the SDK returns multiple text blocks (or interleaves other
    block types), the adapter concatenates the text blocks in order."""

    class _NonText:
        type = "non_text"
        text = "should be ignored"

    body = json.dumps({"verdict": "allow", "reasoning": "ok"})
    blocks = [
        _StubTextBlock(text=body[: len(body) // 2]),
        _NonText(),
        _StubTextBlock(text=body[len(body) // 2 :]),
    ]
    client = _StubClient()
    client.messages.responses.append(_StubMessagesResponse(content=blocks))
    out = claude_call("sys", "user", client=client)
    assert out["verdict"] == "allow"
    assert out["reasoning"] == "ok"
