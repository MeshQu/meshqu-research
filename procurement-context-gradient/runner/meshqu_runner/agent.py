"""
Agent call wrapper — OpenAI client at the locked model.

Targets `gpt-5.4-2026-03-05` at temperature 0 (locked at
`meshqu-research`'s `v0.2-model-locked` tag).

This module honours every Brief #2 refinement from the run-up to PR #17:

- **Structured-output mode preference hierarchy** — tries native JSON
  mode first (OpenAI's `response_format: {type: 'json_object'}`), falls
  back to plain-text JSON prompting only if the model rejects it. Never
  regex-extracts.
- **Reasoning hashing algorithm** — `sha256(utf8(normalised_reasoning))`
  where normalisation = trim outer whitespace + LF newlines only.
- **Verdict normalisation table** — agent returns lowercase `allow` /
  `review` / `deny`; this module normalises to uppercase
  `ALLOW` / `REVIEW` / `DENY` for the decision_traces row + the
  agreement projection.
- **No fall-back to a different model** — the experiment's single-model
  commitment is enforced here; agent errors propagate up so the eval
  loop can log + skip a record, never silently retry on a different model.
- **Uses `max_completion_tokens` not `max_tokens`** — GPT-5+ API
  convention (the model-lock decision_log entry captures this).

Why a direct OpenAI SDK wrapper instead of Inspect AI's full framework:
the experiment uses a single provider, single model, single temperature,
structured-JSON output, and per-record evaluation — a tight subset of
what Inspect AI handles. Building a small wrapper with Inspect-AI-style
discipline (locked model, structured output preference, evaluation
traces) keeps the dependency surface small and the code auditable. The
patterns map 1:1 to an Inspect AI migration if a future experiment
needs multi-provider comparison.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


# ---------------------------------------------------------------------------
# Locked model contract — pinned at meshqu-research v0.2-model-locked
# ---------------------------------------------------------------------------

LOCKED_MODEL_ID = "gpt-5.4-2026-03-05"
"""DO NOT CHANGE without re-running predictions-lock + model-lock discipline."""

LOCKED_TEMPERATURE = 0.0
"""The design's reproducibility commitment. GPT-5.5 rejects this (operates
as reasoning model under the hood); GPT-5.4 honors it."""

DEFAULT_MAX_COMPLETION_TOKENS = 500
"""Generous headroom for the agent's three-key JSON response. The system
prompt caps reasoning at 60 words; 500 tokens absorbs any reasonable
overhead from JSON framing + the model's tokenisation."""


# ---------------------------------------------------------------------------
# Retry policy — bounded backoff for transient OpenAI errors
# ---------------------------------------------------------------------------

DEFAULT_RETRY_MAX_ATTEMPTS = 3
"""3 attempts total: initial + 2 retries. Keeps a 300-record run bounded
in the worst case (300 × 3 × max_backoff ≈ tractable) while still
absorbing the typical transient 429 / 5xx / timeout pattern."""

DEFAULT_RETRY_INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_RETRY_MAX_BACKOFF_SECONDS = 30.0
"""Exponential backoff capped at 30s. OpenAI's typical Retry-After on
rate limit is well under this; the cap exists to defend against a
broken server returning absurdly high Retry-After values."""

_RETRYABLE_KINDS: frozenset[str] = frozenset({"rate_limit", "timeout", "server", "network"})
"""Kinds the retry loop will retry. Notably absent:
- `auth` — credentials are deterministically wrong; retry won't help.
- `unsupported_param` — caller (the json_object → plain_text fallback)
  needs to see it immediately, not after 3 retries.
- `unknown` — better to surface than silently retry an unclassified
  error that might be a logic bug."""


# ---------------------------------------------------------------------------
# Verdict normalisation table
# ---------------------------------------------------------------------------

NormalisedVerdict = Literal["ALLOW", "REVIEW", "DENY"]

_VERDICT_NORMALISATION: dict[str, NormalisedVerdict] = {
    "allow": "ALLOW",
    "review": "REVIEW",
    "deny": "DENY",
    # Defensive: tolerate uppercase if the model returns canonical form
    "ALLOW": "ALLOW",
    "REVIEW": "REVIEW",
    "DENY": "DENY",
}


def normalise_verdict(raw: Any) -> NormalisedVerdict | None:
    """Convert the agent's lowercase verdict to canonical uppercase.

    Returns None if the input isn't one of the three canonical strings —
    the eval loop treats `None` as a model-misbehaviour event (logs to
    anomalies.jsonl) and continues.

    Adheres to the system prompt's "Do not create additional verdict tiers"
    constraint — anything outside {allow, review, deny} is a parse failure,
    not a fourth tier.
    """
    if not isinstance(raw, str):
        return None
    return _VERDICT_NORMALISATION.get(raw.strip())


def projects_to_agreement(
    agent_verdict: NormalisedVerdict | None,
    meshqu_verdict: NormalisedVerdict | None,
) -> bool | None:
    """Agreement projection per the locked design.

    | Agent | MeshQu | Agreement |
    |---|---|---|
    | ALLOW | ALLOW | True |
    | DENY | DENY | True |
    | REVIEW | REVIEW | True |
    | REVIEW | * (anything else) | False (REVIEW is its own state) |
    | * | REVIEW | False |
    | ALLOW | DENY | False |
    | DENY | ALLOW | False |
    | None (parse fail) | * | None (excluded from agreement statistics) |

    `None` agreement means "agent didn't produce a parseable verdict";
    those records are excluded from the writeup's agreement statistics
    but counted separately as parse-failure rate.
    """
    if agent_verdict is None or meshqu_verdict is None:
        return None
    return agent_verdict == meshqu_verdict


# ---------------------------------------------------------------------------
# Reasoning hashing — sha256 of normalised reasoning text
# ---------------------------------------------------------------------------


def normalise_reasoning(text: str) -> str:
    """Deterministic normalisation before hashing:
    - trim outer whitespace
    - replace CRLF + CR with LF (single newline convention)

    Same text → same hash, regardless of platform line-ending conventions
    or trailing whitespace from the model's tokenisation."""
    if not isinstance(text, str):
        return ""
    normalised = text.strip()
    normalised = normalised.replace("\r\n", "\n").replace("\r", "\n")
    return normalised


def sha256_reasoning(text: str) -> str:
    """sha256(utf8(normalise_reasoning(text))) — hex digest.

    The agent's full reasoning text doesn't go into decision_traces.jsonl
    directly (would make the rows large + leak agent text into the audit
    layer); only the hash does. Full reasoning is captured separately in
    `results/agent_outputs/{decision_id}.json` for the writeup to quote
    from."""
    normalised = normalise_reasoning(text)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# System prompt loading + hashing
# ---------------------------------------------------------------------------


def load_system_prompt(path: Path | None = None) -> str:
    """Load the system prompt from `runner/system_prompt.md`. Path can be
    overridden for tests; default resolves to the canonical location
    relative to this module."""
    if path is None:
        # __file__ → runner/meshqu_runner/agent.py → up two → runner/
        path = Path(__file__).resolve().parent.parent / "system_prompt.md"
    return path.read_text(encoding="utf-8")


def sha256_system_prompt(prompt_text: str) -> str:
    """sha256(utf8(normalised prompt text)) — same normalisation as the
    reasoning hash so the discipline is uniform.

    Pinned into every receipt's `fields.agent_prompt_sha256` per record
    so the prompt is hash-bound into the receipt's integrity hash.

    The prompt hash is computed ONCE at run start (per Brief #2's
    "Hash the system prompt at startup, NOT per record" requirement)
    and used verbatim for every record in the run. A prompt change
    mid-run is invalid — the run must restart with a fresh manifest."""
    return sha256_reasoning(prompt_text)


# ---------------------------------------------------------------------------
# Agent response — parsed + normalised
# ---------------------------------------------------------------------------


@dataclass
class AgentResponse:
    """Parsed agent response. The eval loop folds these fields into the
    decision_traces.jsonl row + the agent-outputs sidecar file."""

    verdict: NormalisedVerdict | None  # None on parse failure
    reasoning: str  # raw reasoning text (may be empty on parse failure)
    reasoning_sha256: str  # sha256 of normalised reasoning
    recommended_action: str | None
    raw_response: str  # the raw model output, for debugging + audit
    latency_ms: int
    output_mode: Literal["json_object", "plain_text", "unknown"]
    parse_status: Literal["ok", "invalid_json", "wrong_shape", "invalid_verdict"]
    parse_detail: str = ""
    # Number of retries the OpenAI call burned before producing this
    # response (0 on the happy path). Surfaces into decision_traces and
    # the run-end summary so the writeup can report "k retries fired,
    # 0 records lost" rather than just "no errors observed".
    retry_count: int = 0
    # E2-005: cached-tokens telemetry from OpenAI's `usage` block.
    # `cached_tokens > 0` means the model served part of the prompt
    # from its prompt cache (input billing discounted). At L4 with the
    # cache-preservation placement, the second and subsequent L4 calls
    # in a batch are expected to report cached_tokens > 0; the smoke
    # test in `test_cache_preservation_smoke.py` is what verifies that
    # empirically. None means "not observed" — distinct from
    # "observed but zero" — and is the value the stub agent emits.
    cached_tokens: int | None = None
    prompt_tokens: int | None = None


@dataclass
class AgentCallError(Exception):
    """Raised when the OpenAI API itself errors (network / auth / 5xx /
    rate-limit after retries). The eval loop catches this, logs an
    anomaly, and continues with the next record. The current record's
    decision_traces.jsonl row is skipped — no partial row written, to
    honour the receipt-write atomicity requirement."""

    kind: Literal["network", "auth", "rate_limit", "server", "timeout", "unknown"]
    detail: str
    # Number of retries spent before the call ultimately failed (or
    # was aborted on a terminal classification). Carried on the error
    # so the json_object → plain_text fallback in `_call_with_format`
    # can carry retries across the mode switch — otherwise a sequence
    # like (429, 429, unsupported_param, success) would under-report
    # retry_count by 2 in the trace row.
    retry_count: int = 0

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


# ---------------------------------------------------------------------------
# OpenAI client wrapper
# ---------------------------------------------------------------------------


class Agent:
    """Calls the locked OpenAI model with the locked system prompt at
    the locked temperature. One Agent instance per run; the system
    prompt + its sha256 are captured at construction."""

    def __init__(
        self,
        *,
        api_key: str,
        system_prompt: str,
        model_id: str = LOCKED_MODEL_ID,
        temperature: float = LOCKED_TEMPERATURE,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        client: Any = None,
        retry_max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS,
        retry_initial_backoff_seconds: float = DEFAULT_RETRY_INITIAL_BACKOFF_SECONDS,
        retry_max_backoff_seconds: float = DEFAULT_RETRY_MAX_BACKOFF_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
        jitter_fn: Callable[[], float] = random.random,
    ) -> None:
        # Lazy import — keeps the module importable in test envs that
        # don't have openai installed (tests use the `client=` injection
        # path with a mock).
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self._client = client
        self._model_id = model_id
        self._temperature = temperature
        self._max_completion_tokens = max_completion_tokens
        self._system_prompt = system_prompt
        self._system_prompt_sha256 = sha256_system_prompt(system_prompt)
        self._retry_max_attempts = retry_max_attempts
        self._retry_initial_backoff_seconds = retry_initial_backoff_seconds
        self._retry_max_backoff_seconds = retry_max_backoff_seconds
        self._sleep_fn = sleep_fn
        self._jitter_fn = jitter_fn

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def system_prompt_sha256(self) -> str:
        return self._system_prompt_sha256

    def evaluate(self, user_message: str) -> AgentResponse:
        """Single-record agent call.

        Output-mode preference hierarchy (Brief #2 refinement):
        1. OpenAI structured output / JSON mode
           (`response_format: {type: "json_object"}`).
        2. Plain-text JSON prompting (rely on the system prompt's
           "Output valid JSON only" constraint).
        3. (NOT IMPLEMENTED — deliberately) Regex extraction. The
           system prompt is strict; if the model can't follow it under
           plain-text mode, that's a parse-failure event to log, not
           something to regex our way around.

        We try (1) first because it gives OpenAI a server-side constraint
        on output shape. Falls back to (2) if the model rejects
        response_format (some pinned versions don't support it cleanly).
        """

        request_started = time.monotonic()
        raw, output_mode, retry_count, cached_tokens, prompt_tokens = (
            self._call_with_format(user_message)
        )
        latency_ms = int((time.monotonic() - request_started) * 1000)

        # Parse
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as err:
            return AgentResponse(
                verdict=None,
                reasoning="",
                reasoning_sha256=sha256_reasoning(""),
                recommended_action=None,
                raw_response=raw,
                latency_ms=latency_ms,
                output_mode=output_mode,
                parse_status="invalid_json",
                parse_detail=str(err),
                retry_count=retry_count,
                cached_tokens=cached_tokens,
                prompt_tokens=prompt_tokens,
            )

        if not isinstance(parsed, dict):
            return AgentResponse(
                verdict=None,
                reasoning="",
                reasoning_sha256=sha256_reasoning(""),
                recommended_action=None,
                raw_response=raw,
                latency_ms=latency_ms,
                output_mode=output_mode,
                parse_status="wrong_shape",
                parse_detail=f"Top-level JSON value was {type(parsed).__name__}, expected object",
                retry_count=retry_count,
                cached_tokens=cached_tokens,
                prompt_tokens=prompt_tokens,
            )

        verdict = normalise_verdict(parsed.get("verdict"))
        if verdict is None:
            return AgentResponse(
                verdict=None,
                reasoning=str(parsed.get("reasoning") or ""),
                reasoning_sha256=sha256_reasoning(str(parsed.get("reasoning") or "")),
                recommended_action=parsed.get("recommended_action"),
                raw_response=raw,
                latency_ms=latency_ms,
                output_mode=output_mode,
                parse_status="invalid_verdict",
                parse_detail=f"verdict={parsed.get('verdict')!r} not in {{allow, review, deny}}",
                retry_count=retry_count,
                cached_tokens=cached_tokens,
                prompt_tokens=prompt_tokens,
            )

        reasoning_text = str(parsed.get("reasoning") or "")
        recommended_action_raw = parsed.get("recommended_action")
        recommended_action: str | None = (
            str(recommended_action_raw)
            if isinstance(recommended_action_raw, str) and recommended_action_raw.strip()
            else None
        )

        return AgentResponse(
            verdict=verdict,
            reasoning=reasoning_text,
            reasoning_sha256=sha256_reasoning(reasoning_text),
            recommended_action=recommended_action,
            raw_response=raw,
            latency_ms=latency_ms,
            output_mode=output_mode,
            parse_status="ok",
            retry_count=retry_count,
            cached_tokens=cached_tokens,
            prompt_tokens=prompt_tokens,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call_with_format(
        self, user_message: str
    ) -> tuple[str, Literal["json_object", "plain_text"], int, int | None, int | None]:
        """Try JSON-object mode first, fall back to plain-text on
        format-not-supported. Anything else (auth, unknown) propagates
        as AgentCallError. Transient errors (rate_limit, timeout,
        server, network) are retried with bounded backoff by
        `_call_with_retry`.

        Returns (raw_content, output_mode, total_retry_count,
        cached_tokens, prompt_tokens). The retry count aggregates
        retries across BOTH the json_object attempt and the plain_text
        fallback so the writeup can report "k retries fired across the
        full call sequence". cached_tokens / prompt_tokens are
        extracted from the SUCCESSFUL response's `usage` block
        (E2-005); they're None if the response carries no usage info."""

        # Common kwargs for both modes
        common: dict[str, Any] = dict(
            model=self._model_id,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self._temperature,
            max_completion_tokens=self._max_completion_tokens,
        )

        # Preferred: JSON object mode
        carry_over_retries = 0
        try:
            resp, json_retries = self._call_with_retry(
                {**common, "response_format": {"type": "json_object"}},
            )
            cached, prompt = _extract_usage_tokens(resp)
            return (
                resp.choices[0].message.content or "",
                "json_object",
                json_retries,
                cached,
                prompt,
            )
        except AgentCallError as err:
            if err.kind != "unsupported_param":
                raise
            # Fall through to plain-text mode. Capture any retries spent
            # before the unsupported_param response so they aren't lost
            # from the aggregate count — sequence like (429, 429,
            # unsupported_param, success) must report retry_count=2.
            carry_over_retries = err.retry_count

        # Fallback: plain-text JSON prompting
        resp, text_retries = self._call_with_retry(common)
        cached, prompt = _extract_usage_tokens(resp)
        return (
            resp.choices[0].message.content or "",
            "plain_text",
            carry_over_retries + text_retries,
            cached,
            prompt,
        )

    def _call_with_retry(
        self, kwargs: dict[str, Any]
    ) -> tuple[Any, int]:
        """Call OpenAI with bounded exponential backoff for transient
        errors. Returns (response, retry_count) on success; raises
        AgentCallError on terminal failure (auth, unsupported_param,
        unknown, or transient kind that exhausted attempts).

        Backoff: starts at `retry_initial_backoff_seconds`, doubles per
        attempt, capped at `retry_max_backoff_seconds`. Jitter is ±20%
        of the backoff value so concurrent runs don't synchronise their
        retry storms. Honors `Retry-After` from the OpenAI error
        response when present — that's the server's own guidance and
        beats our exponential formula."""

        attempt = 0
        retries_used = 0
        backoff = self._retry_initial_backoff_seconds
        last_error: AgentCallError | None = None

        while attempt < self._retry_max_attempts:
            try:
                return self._client.chat.completions.create(**kwargs), retries_used
            except Exception as err:  # noqa: BLE001 — classified below
                classified = _classify_openai_error(err)
                if classified.kind not in _RETRYABLE_KINDS:
                    # auth / unsupported_param / unknown — terminal.
                    # Stamp retries_used onto the error so the caller
                    # (e.g. _call_with_format's fallback) can carry
                    # them into the aggregate retry count.
                    classified.retry_count = retries_used
                    raise classified
                last_error = classified
                attempt += 1
                if attempt >= self._retry_max_attempts:
                    break
                retries_used += 1
                # Honor Retry-After if present, else exponential backoff.
                retry_after = _extract_retry_after_seconds(err)
                if retry_after is not None:
                    # Retry-After is a MINIMUM wait — downward jitter
                    # would violate the server's back-pressure guidance
                    # and likely cause repeat 429s. Use +0..+20% only.
                    wait = min(retry_after, self._retry_max_backoff_seconds)
                    jitter = wait * 0.2 * self._jitter_fn()
                    self._sleep_fn(wait + jitter)
                else:
                    # Exponential backoff: ±20% jitter is fine because
                    # there's no server-imposed floor to respect.
                    wait = min(backoff, self._retry_max_backoff_seconds)
                    jitter = wait * 0.2 * (self._jitter_fn() * 2 - 1)
                    self._sleep_fn(max(0.0, wait + jitter))
                backoff *= 2

        # Exhausted attempts. last_error must be set — the loop only
        # exits via `break` after a retryable classification.
        assert last_error is not None
        last_error.retry_count = retries_used
        raise last_error


def _classify_openai_error(err: Exception) -> AgentCallError:
    """Map OpenAI SDK exceptions to AgentCallError categories. Keeps
    the eval loop's catch-and-log code path uniform."""
    name = type(err).__name__
    msg = str(err)

    if "AuthenticationError" in name:
        return AgentCallError(kind="auth", detail=msg)
    if "RateLimit" in name:
        return AgentCallError(kind="rate_limit", detail=msg)
    if "Timeout" in name:
        return AgentCallError(kind="timeout", detail=msg)
    if "APIConnectionError" in name or "Network" in name:
        return AgentCallError(kind="network", detail=msg)
    if "BadRequest" in name and ("response_format" in msg or "unsupported_parameter" in msg):
        # Synthetic kind used internally to trigger the plain-text fallback.
        # Never reaches the eval loop — caller intercepts.
        return AgentCallError(kind="unsupported_param", detail=msg)  # type: ignore[arg-type]
    if "InternalServerError" in name or "APIError" in name:
        return AgentCallError(kind="server", detail=msg)
    return AgentCallError(kind="unknown", detail=f"{name}: {msg}")


def _extract_retry_after_seconds(err: Exception) -> float | None:
    """Best-effort extraction of `Retry-After` from an OpenAI SDK error.

    OpenAI's RateLimitError carries the original httpx.Response on
    `.response`. The header may be in seconds (e.g. "5") or HTTP-date
    format; we honour the simple seconds case and ignore HTTP-date
    (rare from OpenAI in practice). Returns None when unavailable or
    unparseable — the caller falls back to exponential backoff."""

    response = getattr(err, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("Retry-After") or headers.get("retry-after")
    except (AttributeError, TypeError):
        return None
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_usage_tokens(resp: Any) -> tuple[int | None, int | None]:
    """Extract (cached_tokens, prompt_tokens) from an OpenAI chat
    completion response. (E2-005 cache-preservation telemetry.)

    OpenAI's `ChatCompletion.usage` exposes `prompt_tokens` and, when
    prompt caching is active, `prompt_tokens_details.cached_tokens`.
    The SDK's actual object shape differs slightly between versions
    (pydantic model vs dict on raw HTTP responses), so we probe for
    both attribute access and dict-style access. Returns (None, None)
    when usage is absent — happens with mocked tests + older API
    surfaces.

    The cached_tokens field, when present, is the COUNT of input
    tokens that hit the cache (NOT a fraction or a hit/miss flag).
    Downstream telemetry interprets it as: cached_tokens > 0 = cache
    hit for at least part of the prompt prefix."""
    usage = getattr(resp, "usage", None)
    if usage is None and isinstance(resp, dict):
        usage = resp.get("usage")
    if usage is None:
        return None, None

    def _get(obj: Any, key: str) -> Any:
        if hasattr(obj, key):
            return getattr(obj, key)
        if isinstance(obj, dict):
            return obj.get(key)
        return None

    prompt_tokens = _get(usage, "prompt_tokens")
    details = _get(usage, "prompt_tokens_details")
    cached_tokens = _get(details, "cached_tokens") if details is not None else None

    # Coerce to int when possible; tolerate None / non-numeric.
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return _as_int(cached_tokens), _as_int(prompt_tokens)
