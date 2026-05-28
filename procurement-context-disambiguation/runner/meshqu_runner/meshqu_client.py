"""
MeshQu /v1/decisions/record HTTP client for the procurement-decisions
experiment runner.

This is a thin, audited wrapper around the one MeshQu endpoint the eval
loop hits. It exists for three reasons:

1. **Receipt-write atomicity** — `record_decision()` either returns a
   parsed receipt or raises. The caller (eval loop) only writes a
   decision_traces.jsonl row after BOTH this call AND the local-file
   write succeed. A partial state (receipt at MeshQu, no row locally;
   or row locally, no receipt) is never committed.

2. **Agent-output injection point** — the agent's verdict, reasoning
   sha256, recommended action, model id, temperature, and prompt
   sha256 are folded into `context.fields` under the canonical
   `agent_*` keys. The substrate adapter doesn't emit these (it
   doesn't know about the agent); this module does. The injection
   happens here so the request shape sent to MeshQu always carries
   both substrate-derived and agent-emitted fields, and the receipt
   binds them all into one integrity hash.

3. **Error classification** — network / 4xx / 5xx / timeout all
   surface as `MeshQuClientError` with a `kind` enum. The eval loop's
   anomaly log can categorise without re-parsing exception messages.

Auth model: TWO headers, both required:
  - `Authorization: Bearer <api_key>` — proves the caller holds a valid
    key.
  - `x-meshqu-tenant-id: <uuid>` — the tenant scope for this request.
    The API rejects with 400 MISSING_TENANT_ID if absent
    (apps/meshqu-api/src/middleware/tenant.ts), so the client takes the
    tenant UUID at construction time and stamps it on every request.

(The first smoke run hit MISSING_TENANT_ID on all three records under
the earlier assumption that the API key alone scoped the request. The
four-layer tenant isolation model in the monorepo's CLAUDE.md is real:
the request header is one of those layers.)
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping

import requests

# Capture the exception classes at module-load time so retry-loop except
# clauses stay bound to the REAL classes even when tests monkey-patch
# `meshqu_client.requests` with a fake module (mirrors the discipline
# in screenshots.py).
from requests.exceptions import (  # noqa: E402
    ConnectionError as _RequestsConnectionError,
    RequestException as _RequestException,
    Timeout as _Timeout,
)


# ---------------------------------------------------------------------------
# Constants — pinned for the procurement-decisions experiment.
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 30.0
"""Receipt-record requests are expected to complete in <2s under nominal
load. 30s is the generous outer bound — anything longer is a real
server issue, not a transient slow path, and the eval loop should log
it as an anomaly rather than wait."""


# ---------------------------------------------------------------------------
# Retry policy — bounded backoff for transient MeshQu errors
# ---------------------------------------------------------------------------

DEFAULT_RETRY_MAX_ATTEMPTS = 3
"""3 attempts total: initial + 2 retries. Mirrors agent.py's discipline.
Added 2026-05-18 after the first staging corpus-run attempt
(`dry-run-5ac1e02c-…`) hit two TCP resets in the first 17 records,
above the pre-run checklist's 5% kill threshold — see notebook
`2026-05-18-aborted-run.md` + finding `004-meshqu-client-network-retry-gap.md`."""

DEFAULT_RETRY_INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_RETRY_MAX_BACKOFF_SECONDS = 30.0

_RETRYABLE_KINDS: frozenset[str] = frozenset(
    {"network", "timeout", "server_error", "rate_limit"}
)
"""Kinds the retry loop will retry. Network/timeout/server_error/rate_limit
are typically transient (Railway worker recycling, keep-alive idle close,
5xx blips, 429 backpressure). Notably absent:
- `auth` (401/403) — credentials are deterministically wrong; retry
  won't help and would waste tokens.
- `client_error` (other 4xx) — deterministic request shape error
  (e.g. the smoke's `MISSING_TENANT_ID` 400). Retry would re-fail.
- `decode_error` / `shape_error` — server returned 2xx but a malformed
  body. Retry won't make the body well-formed.

Idempotency-key safety: the eval loop passes a deterministic key per
record. A retry that arrives at MeshQu after the server already
committed just returns the cached receipt — no double-charge, no
duplicate row. This is load-bearing for the retry design."""

CANONICAL_AGENT_FIELD_KEYS: tuple[str, ...] = (
    "agent_model_id",
    "agent_model_version",
    "agent_temperature",
    "agent_prompt_sha256",
    "agent_reasoning_sha256",
    "agent_recommended_verdict",
    "agent_recommended_action",
)
"""The exact set of agent-emitted fields injected per record. The
order is canonical so the substrate-vs-agent field separation in the
writeup is stable + machine-checkable.

These are NOT evaluated by the ratified policy — they're audit-only
fields. The policy operates on substrate-derived fields. The agent
fields ride along in `context.fields` so they bind into the receipt's
integrity hash."""


# ---------------------------------------------------------------------------
# Receipt + Error types
# ---------------------------------------------------------------------------


@dataclass
class ReceiptSummary:
    """The fields of the MeshQu receipt the eval loop cares about. The
    full RecordResponse is much larger; this struct picks out exactly
    what gets folded into decision_traces.jsonl.

    All hashes are lowercase hex. `transparency_anchor` is `None` when
    the experiment tenant doesn't have the transparency log integration
    enabled (a known-omitted field in the experiment tenant config —
    confirmed in `decision_log.md` substrate-honesty disclosures)."""

    decision_id: str
    decision: Literal["ALLOW", "DENY", "REVIEW", "ALERT"]
    policy_snapshot_id: str
    integrity_hash: str
    evaluated_rules_hash: str
    timestamp: str  # ISO-8601 from the evaluation
    signature_kid: str | None
    signature: str | None
    policy_snapshot_digest: str | None
    transparency_anchor: dict[str, Any] | None
    violations: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    # Retries the client burned before getting this receipt (0 on the
    # happy path). Surfaces into decision_traces.jsonl as
    # `meshqu_retry_count` alongside `agent_retry_count`. Lets the
    # writeup report "k MeshQu retries fired, 0 corpus losses" rather
    # than "no transient errors observed".
    retry_count: int = 0


@dataclass
class MeshQuClientError(Exception):
    """Raised for any failure to obtain a receipt. The eval loop catches
    this, logs an anomaly with `kind` + `detail`, and skips the record
    (no decision_traces row, no partial state)."""

    kind: Literal[
        "network",
        "timeout",
        "auth",
        "rate_limit",
        "client_error",
        "server_error",
        "decode_error",
        "shape_error",
    ]
    detail: str
    status_code: int | None = None
    response_body: str | None = None
    # Retries the client burned before the error was raised (0 on the
    # very first attempt). Mirrors `AgentCallError.retry_count` so the
    # eval loop's anomaly context carries the same diagnostic field
    # for both halves of the call sequence.
    retry_count: int = 0

    def __str__(self) -> str:
        suffix = f" [HTTP {self.status_code}]" if self.status_code else ""
        return f"{self.kind}: {self.detail}{suffix}"


# ---------------------------------------------------------------------------
# Field injection — substrate context + agent fields → request body
# ---------------------------------------------------------------------------


def inject_agent_fields(
    context: Mapping[str, Any],
    *,
    agent_model_id: str,
    agent_temperature: float,
    agent_prompt_sha256: str,
    agent_reasoning_sha256: str,
    agent_recommended_verdict: str,
    agent_recommended_action: str | None,
    agent_model_version: str | None = None,
) -> dict[str, Any]:
    """Fold the agent's per-record outputs into a DecisionContext's
    `fields` map. Returns a new dict — does not mutate `context`.

    Naming + ordering exactly matches CANONICAL_AGENT_FIELD_KEYS so the
    writeup can group `agent_*` fields against substrate fields without
    string-pattern guessing.

    `agent_model_version` is optional — pinned to None unless the
    OpenAI response surfaces a more specific version than the locked
    model id (it usually doesn't, but the field is reserved for future
    use without a request-shape change)."""

    fields = dict(context.get("fields") or {})
    fields["agent_model_id"] = agent_model_id
    fields["agent_model_version"] = agent_model_version
    fields["agent_temperature"] = agent_temperature
    fields["agent_prompt_sha256"] = agent_prompt_sha256
    fields["agent_reasoning_sha256"] = agent_reasoning_sha256
    fields["agent_recommended_verdict"] = agent_recommended_verdict
    fields["agent_recommended_action"] = agent_recommended_action

    new_context = dict(context)
    new_context["fields"] = fields
    return new_context


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class MeshQuClient:
    """Single-purpose HTTP client. One instance per run.

    Holds the base URL + API key in memory; no caching, no connection
    pooling beyond what `requests.Session` provides by default. The
    eval loop runs serially (one record at a time) so concurrency is
    not in scope."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        tenant_id: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
        retry_max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS,
        retry_initial_backoff_seconds: float = DEFAULT_RETRY_INITIAL_BACKOFF_SECONDS,
        retry_max_backoff_seconds: float = DEFAULT_RETRY_MAX_BACKOFF_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
        jitter_fn: Callable[[], float] = random.random,
    ) -> None:
        if not base_url:
            raise ValueError("base_url must be non-empty")
        if not api_key:
            raise ValueError("api_key must be non-empty")
        if not tenant_id:
            raise ValueError("tenant_id must be non-empty")
        # Normalise: strip trailing slash so urljoin paths are predictable.
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._tenant_id = tenant_id
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._retry_max_attempts = retry_max_attempts
        self._retry_initial_backoff_seconds = retry_initial_backoff_seconds
        self._retry_max_backoff_seconds = retry_max_backoff_seconds
        self._sleep_fn = sleep_fn
        self._jitter_fn = jitter_fn

    # ------------------------------------------------------------------

    def record_decision(
        self,
        *,
        context: Mapping[str, Any],
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> ReceiptSummary:
        """POST /v1/decisions/record. Returns a parsed receipt summary.

        Raises MeshQuClientError on any failure. The caller treats this
        as "no receipt; do not write a decision_traces row".

        `correlation_id` is passed via `x-correlation-id` header so the
        receipt's correlation_id field carries the eval-loop's run-scoped
        id, making receipt ↔ trace correlation possible in the writeup."""

        url = f"{self._base_url}/v1/decisions/record"

        body: dict[str, Any] = {"context": dict(context)}
        if idempotency_key is not None:
            body["options"] = {"idempotency_key": idempotency_key}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-meshqu-tenant-id": self._tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if correlation_id is not None:
            headers["x-correlation-id"] = correlation_id

        body_bytes = json.dumps(body)
        resp, retries_used = self._call_with_retry(url, body_bytes, headers)
        receipt = self._parse_response(resp)
        receipt.retry_count = retries_used
        return receipt

    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        url: str,
        body_bytes: str,
        headers: dict[str, str],
    ) -> tuple[requests.Response, int]:
        """Send POST with bounded retry on transient errors. Returns
        (response, retry_count) on the first 2xx response. Raises
        MeshQuClientError on terminal HTTP errors or exhausted retries.

        Retry decisions:
          - Network/timeout exceptions → retryable, loop
          - 2xx → return for parsing
          - 401/403 (auth) → terminal, raise
          - 429 (rate_limit) → retryable; honor Retry-After header
          - other 4xx (client_error) → terminal, raise
          - 5xx (server_error) → retryable

        Backoff: starts at `retry_initial_backoff_seconds`, doubles per
        attempt, capped at `retry_max_backoff_seconds`. Exponential
        backoff uses ±20% jitter. When honoring `Retry-After`, jitter
        is positive-only — the header value is a minimum wait per
        RFC 7231 §7.1.3; downward jitter would violate the server's
        back-pressure guidance.

        retry_count is stamped onto any raised MeshQuClientError so
        the eval loop's anomaly log carries the diagnostic field even
        on the give-up path."""

        attempt = 0
        retries_used = 0
        backoff = self._retry_initial_backoff_seconds
        last_error: MeshQuClientError | None = None

        while attempt < self._retry_max_attempts:
            attempt += 1
            retry_after: float | None = None
            classified: MeshQuClientError | None = None

            try:
                resp = self._session.post(
                    url,
                    data=body_bytes,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            except _Timeout as err:
                classified = MeshQuClientError(
                    kind="timeout", detail=str(err), retry_count=retries_used
                )
            except (_RequestsConnectionError, _RequestException) as err:
                classified = MeshQuClientError(
                    kind="network", detail=str(err), retry_count=retries_used
                )
            else:
                # Got a Response — classify by HTTP status.
                status = resp.status_code
                if 200 <= status < 300:
                    return resp, retries_used
                kind = _classify_http_status(status)
                classified = MeshQuClientError(
                    kind=kind,
                    detail=f"HTTP {status}",
                    status_code=status,
                    response_body=_safe_truncate(resp.text),
                    retry_count=retries_used,
                )
                if kind not in _RETRYABLE_KINDS:
                    # auth / client_error — terminal. Stamp + raise.
                    raise classified
                if kind == "rate_limit":
                    retry_after = _extract_retry_after_from_response(resp)

            # We're in retryable territory. Decide whether to loop or give up.
            assert classified is not None
            assert classified.kind in _RETRYABLE_KINDS
            last_error = classified

            if attempt >= self._retry_max_attempts:
                break

            retries_used += 1

            if retry_after is not None:
                # Retry-After is a MINIMUM wait — positive-only jitter.
                wait = min(retry_after, self._retry_max_backoff_seconds)
                jitter = wait * 0.2 * self._jitter_fn()
                self._sleep_fn(wait + jitter)
            else:
                # Exponential backoff with ±20% jitter (no server floor).
                wait = min(backoff, self._retry_max_backoff_seconds)
                jitter = wait * 0.2 * (self._jitter_fn() * 2 - 1)
                self._sleep_fn(max(0.0, wait + jitter))
            backoff *= 2

        # Exhausted retries on a retryable kind.
        assert last_error is not None
        last_error.retry_count = retries_used
        raise last_error

    # ------------------------------------------------------------------

    def _parse_response(self, resp: requests.Response) -> ReceiptSummary:
        """Parse a 2xx Response into a ReceiptSummary. Status-code
        classification has already been handled by `_call_with_retry`
        — this method assumes a successful HTTP response and only
        validates body decode + shape. Raises MeshQuClientError on
        `decode_error` or `shape_error` (both terminal — retries
        won't reshape a malformed response)."""
        status = resp.status_code

        # 2xx — decode + extract.
        try:
            payload = resp.json()
        except ValueError as err:
            raise MeshQuClientError(
                kind="decode_error",
                detail=f"JSON decode failed: {err}",
                status_code=status,
                response_body=_safe_truncate(resp.text),
            ) from err

        if not isinstance(payload, dict):
            raise MeshQuClientError(
                kind="shape_error",
                detail=f"response top-level was {type(payload).__name__}, expected object",
                status_code=status,
            )

        decision_obj = payload.get("decision")
        if not isinstance(decision_obj, dict):
            raise MeshQuClientError(
                kind="shape_error",
                detail="response.decision missing or not an object",
                status_code=status,
            )

        result_obj = decision_obj.get("result")
        if not isinstance(result_obj, dict):
            raise MeshQuClientError(
                kind="shape_error",
                detail="response.decision.result missing or not an object",
                status_code=status,
            )

        try:
            return ReceiptSummary(
                decision_id=_require_str(decision_obj, "id"),
                decision=_require_decision(result_obj.get("decision")),
                policy_snapshot_id=_require_str(decision_obj, "policy_snapshot_id"),
                integrity_hash=_require_str(result_obj, "integrity_hash"),
                evaluated_rules_hash=_require_str(result_obj, "evaluated_rules_hash"),
                timestamp=_require_str(result_obj, "timestamp"),
                signature_kid=_optional_str(result_obj, "signature_kid"),
                signature=_optional_str(result_obj, "signature"),
                policy_snapshot_digest=_optional_str(result_obj, "policy_snapshot_digest"),
                transparency_anchor=_optional_object(result_obj, "transparency_anchor"),
                violations=list(result_obj.get("violations") or []),
                raw_response=payload,
            )
        except KeyError as err:
            raise MeshQuClientError(
                kind="shape_error",
                detail=f"required field missing: {err.args[0]}",
                status_code=status,
            ) from err


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ALLOWED_DECISIONS = {"ALLOW", "DENY", "REVIEW", "ALERT"}


def _require_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise KeyError(key)
    return value


def _optional_str(obj: Mapping[str, Any], key: str) -> str | None:
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise KeyError(f"{key} present but not a string")


def _optional_object(obj: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise KeyError(f"{key} present but not an object")


def _require_decision(value: Any) -> Literal["ALLOW", "DENY", "REVIEW", "ALERT"]:
    if value not in _ALLOWED_DECISIONS:
        raise KeyError(f"decision={value!r} not in {sorted(_ALLOWED_DECISIONS)}")
    return value  # type: ignore[return-value]


def _safe_truncate(text: str, limit: int = 2048) -> str:
    """Truncate response bodies before storing them on a MeshQuClientError
    so a misbehaving server can't blow up the anomaly log."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[truncated, {len(text) - limit} bytes omitted]"


def _classify_http_status(
    status: int,
) -> Literal["auth", "rate_limit", "client_error", "server_error"]:
    """Map an HTTP response status to a MeshQuClientError kind.
    Used by `_call_with_retry` to decide retry-vs-terminal before
    parsing the response body."""
    if status == 401 or status == 403:
        return "auth"
    if status == 429:
        return "rate_limit"
    if 400 <= status < 500:
        return "client_error"
    return "server_error"  # 5xx


def _extract_retry_after_from_response(resp: requests.Response) -> float | None:
    """Best-effort `Retry-After` extraction from a requests.Response.

    Honors the seconds form (e.g. `Retry-After: 5`); ignores HTTP-date
    form (rare from MeshQu in practice). Returns None when absent or
    unparseable — the caller falls back to exponential backoff."""
    try:
        value = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    except (AttributeError, TypeError):
        return None
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
