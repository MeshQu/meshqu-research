"""Claude cross-model adapter — Anthropic SDK at the locked pin.

The cross-model diagnostic arm (``diagnostic_claude``) calls
``claude-opus-4-7`` via the Anthropic Python SDK with E2's verbatim
``system_prompt.md``. The pin is set by the pre-registration tag
``v0.3-predictions-locked`` and the feasibility spike at
``planning/feasibility_spike_claude.md``:

- Model: ``claude-opus-4-7``
- Sampling: NO ``temperature`` parameter (Opus 4.7 removed it —
  sending ``temperature=0`` returns HTTP 400).
- ``output_config={"effort": "low"}`` for near-determinism on this
  classification-style diagnostic.
- ``max_tokens`` = 1024 (matches the spike).

The spike confirmed Opus parses E2's verbatim scaffold CLEAN — the
verdict JSON is the raw response body, no markdown fence. The
fence-strip shim lifted from ``runner/spike/claude_spike.py`` is kept
as a defensive harmless layer: it's a no-op when the response is clean
and would only matter under a future Sonnet fallback (Sonnet wraps
fences). Keeping it now avoids a code change later if the pin is ever
revisited via a tag amendment.

## Why the receipt records ``temperature: null`` and not a caveat

The receipt's integrity payload records the *fact* of the sampling
block — ``{"temperature": null, "effort": "low", "max_tokens": 1024}``.
The methods caveat ("Opus 4.7 cannot match the primary agent's temp-0
setting; the sampling-mismatch is documented but not a confound — the
cross-model arm compares the *reasoning-axis* rubric distribution, not
verdict-for-verdict") lives in the writeup. The receipt records the
truth; the writeup interprets it. Per
``planning/build_packages/e3-006-claude-swap.md`` §2.

## Live calls vs CI

The runner's production code imports ``anthropic`` at module load and
calls ``client.messages.create`` for the diagnostic arm. CI does NOT
run live calls — every test injects a mock client. The smoke + dry-run
packages exercise the live path on real records. See
``planning/build_packages/e3-006-claude-swap.md`` §4.
"""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic
from anthropic import (
    APIError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
)


# ---------------------------------------------------------------------------
# Locked pin — bound by v0.3-predictions-locked
# ---------------------------------------------------------------------------

MODEL_ID = "claude-opus-4-7"
"""Pinned at the pre-registration tag. Opus 4.7 removed the
``temperature`` parameter (sending it returns HTTP 400). DO NOT add a
``temperature`` kwarg to the SDK call — see
``planning/feasibility_spike_claude.md``."""

MAX_TOKENS = 1024
"""Matches the spike. Opus's verdict JSON for the classification
prompt is in the low-hundreds range; 1024 gives generous headroom
while keeping per-record cost bounded."""

OUTPUT_CONFIG: dict[str, Any] = {"effort": "low"}
"""``effort: low`` is the near-determinism knob on Opus 4.7. Fixed by
the pre-registration tag; do NOT vary it via a CLI flag (the pin binds
it)."""


# ---------------------------------------------------------------------------
# Runner-level error surface
# ---------------------------------------------------------------------------


class ClaudeAdapterError(Exception):
    """Wrap Anthropic SDK exceptions into a single runner-level error
    type with a classified ``kind``. Mirrors the shape of
    ``meshqu_runner.agent.AgentCallError`` so the eval loop's catch +
    log path stays uniform across the two adapters."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def make_client() -> anthropic.Anthropic:
    """Construct an Anthropic client. Reads ``ANTHROPIC_API_KEY`` from
    the environment (the SDK default). Raises ``ClaudeAdapterError`` of
    kind ``auth`` with a clear message when the env var is absent —
    surfacing this loudly avoids the SDK's lazy "AuthenticationError on
    first call" pattern which masks the real cause."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ClaudeAdapterError(
            "auth",
            "ANTHROPIC_API_KEY not set in environment. The Claude "
            "adapter requires a live key; set it before invoking the "
            "diagnostic_claude arm.",
        )
    return anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Verdict JSON parser — fence-strip shim lifted from the spike
# ---------------------------------------------------------------------------


def parse_verdict_json(raw: str) -> dict[str, Any]:
    """Parse Claude's response body into a verdict dict.

    Opus returns the verdict JSON cleanly (no markdown fence) per the
    spike. The fence-strip shim is kept as a defensive layer — it's a
    no-op on Opus's output but handles the ``` ```json ... ``` ```
    wrapper Sonnet adds (option B in the spike). Keeping it now avoids
    a code change later if the pin is ever revisited via a tag
    amendment.

    Returns a dict with at least the verdict's expected keys (with
    ``None`` for missing ones). Raises ``ClaudeAdapterError`` of kind
    ``parse`` if the body isn't parseable as JSON at all, or if the
    top-level value isn't a JSON object — same posture as the OpenAI
    adapter's parse-failure handling.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        # Markdown fence — strip and retry. Lifted verbatim from
        # ``runner/spike/claude_spike.py``: trim all backticks, then
        # drop a leading ``json`` language tag.
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as err:
        raise ClaudeAdapterError(
            "parse", f"Claude response body is not valid JSON: {err}"
        ) from err
    if not isinstance(obj, dict):
        raise ClaudeAdapterError(
            "parse",
            f"Claude response top-level JSON value is {type(obj).__name__}, "
            f"expected object",
        )
    return obj


# ---------------------------------------------------------------------------
# Adapter entry point
# ---------------------------------------------------------------------------


def call(
    system_prompt: str,
    user_message: str,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Run one Claude (``claude-opus-4-7``) agent call.

    Returns a normalised payload matching the adapter contract
    documented in ``meshqu_runner.agents.__init__``:

        {
          "verdict": "allow" | "review" | "deny" | None,
          "reasoning": str,
          "recommended_action": str | None,
          "raw": str,
          "usage": {"input_tokens": int, "output_tokens": int},
          "model": str,
          "latency_ms": int,
        }

    The SDK call shape is fixed by the locked pin:

    - ``model=claude-opus-4-7``
    - NO ``temperature`` kwarg (Opus 4.7 removed it; sending it 400s)
    - ``output_config={"effort": "low"}``
    - ``max_tokens=1024``
    - ``system=system_prompt`` (E2's verbatim system prompt)
    - ``messages=[{"role": "user", "content": user_message}]``

    Anthropic SDK exceptions are caught + classified into
    ``ClaudeAdapterError`` (kind ∈ {``not_found``, ``auth``,
    ``permission``, ``bad_request``, ``api``}). The eval loop catches
    this and logs an anomaly — identical posture to the primary
    adapter's ``AgentCallError``.
    """
    client = client or make_client()

    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            output_config=OUTPUT_CONFIG,
            # IMPORTANT: NO `temperature` kwarg. Opus 4.7 removed it;
            # sending it returns HTTP 400. The spike confirmed this.
        )
    except NotFoundError as err:
        raise ClaudeAdapterError(
            "not_found",
            f"Model {MODEL_ID} not found / not accessible on this key: {err}",
        ) from err
    except AuthenticationError as err:
        raise ClaudeAdapterError(
            "auth", f"ANTHROPIC_API_KEY invalid or missing: {err}"
        ) from err
    except PermissionDeniedError as err:
        raise ClaudeAdapterError(
            "permission", f"Key lacks access to {MODEL_ID}: {err}"
        ) from err
    except BadRequestError as err:
        raise ClaudeAdapterError(
            "bad_request",
            f"400 from {MODEL_ID} (likely a temperature/param issue): {err}",
        ) from err
    except APIError as err:
        raise ClaudeAdapterError(
            "api", f"API error from {MODEL_ID}: {err}"
        ) from err
    latency_ms = int((time.monotonic() - t0) * 1000)

    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    parsed = parse_verdict_json(raw)

    verdict = parsed.get("verdict")
    if isinstance(verdict, str):
        verdict = verdict.strip().lower() or None
        if verdict not in {"allow", "review", "deny"}:
            # Out-of-vocab verdict. We return it as None (parse
            # failure) rather than passing through — the system prompt
            # constrains the model to three verdicts; anything else is
            # a parse-failure event the eval loop logs.
            verdict = None
    else:
        verdict = None

    reasoning_raw = parsed.get("reasoning")
    reasoning = reasoning_raw if isinstance(reasoning_raw, str) else ""

    action_raw = parsed.get("recommended_action")
    recommended_action: str | None = None
    if isinstance(action_raw, str) and action_raw.strip():
        recommended_action = action_raw

    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None) if usage else None
    output_tokens = getattr(usage, "output_tokens", None) if usage else None

    return {
        "verdict": verdict,
        "reasoning": reasoning,
        "recommended_action": recommended_action,
        "raw": raw,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
        "model": getattr(resp, "model", MODEL_ID),
        "latency_ms": latency_ms,
    }


__all__ = [
    "MODEL_ID",
    "MAX_TOKENS",
    "OUTPUT_CONFIG",
    "ClaudeAdapterError",
    "call",
    "make_client",
    "parse_verdict_json",
]
