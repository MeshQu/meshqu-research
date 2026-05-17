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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


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


@dataclass
class AgentCallError(Exception):
    """Raised when the OpenAI API itself errors (network / auth / 5xx /
    rate-limit after retries). The eval loop catches this, logs an
    anomaly, and continues with the next record. The current record's
    decision_traces.jsonl row is skipped — no partial row written, to
    honour the receipt-write atomicity requirement."""

    kind: Literal["network", "auth", "rate_limit", "server", "timeout", "unknown"]
    detail: str

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
        raw, output_mode = self._call_with_format(user_message)
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
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call_with_format(self, user_message: str) -> tuple[str, Literal["json_object", "plain_text"]]:
        """Try JSON-object mode first, fall back to plain-text on
        format-not-supported. Anything else (network, auth, rate-limit)
        propagates as AgentCallError."""

        # Common kwargs for both modes
        common = dict(
            model=self._model_id,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self._temperature,
            max_completion_tokens=self._max_completion_tokens,
        )

        # Preferred: JSON object mode
        try:
            resp = self._client.chat.completions.create(
                **common,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content or "", "json_object"
        except Exception as err:  # noqa: BLE001 — classified below
            classified = _classify_openai_error(err)
            if classified.kind == "unsupported_param":
                # Fall through to plain-text mode
                pass
            else:
                raise classified

        # Fallback: plain-text JSON prompting
        try:
            resp = self._client.chat.completions.create(**common)
            return resp.choices[0].message.content or "", "plain_text"
        except Exception as err:  # noqa: BLE001
            raise _classify_openai_error(err)


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
