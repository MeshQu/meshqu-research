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

Auth model: API key in `Authorization: Bearer …` header. The MeshQu
auth middleware resolves the tenant from the key, so we don't need to
send an `x-tenant-id` header.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

import requests


# ---------------------------------------------------------------------------
# Constants — pinned for the procurement-decisions experiment.
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 30.0
"""Receipt-record requests are expected to complete in <2s under nominal
load. 30s is the generous outer bound — anything longer is a real
server issue, not a transient slow path, and the eval loop should log
it as an anomaly rather than wait."""

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
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url must be non-empty")
        if not api_key:
            raise ValueError("api_key must be non-empty")
        # Normalise: strip trailing slash so urljoin paths are predictable.
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

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
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if correlation_id is not None:
            headers["x-correlation-id"] = correlation_id

        try:
            resp = self._session.post(
                url,
                data=json.dumps(body),
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except requests.exceptions.Timeout as err:
            raise MeshQuClientError(kind="timeout", detail=str(err)) from err
        except requests.exceptions.ConnectionError as err:
            raise MeshQuClientError(kind="network", detail=str(err)) from err
        except requests.exceptions.RequestException as err:
            raise MeshQuClientError(kind="network", detail=str(err)) from err

        return self._parse_response(resp)

    # ------------------------------------------------------------------

    def _parse_response(self, resp: requests.Response) -> ReceiptSummary:
        status = resp.status_code

        # Classify HTTP errors before attempting JSON decode. 4xx/5xx
        # bodies may still be JSON (error envelopes) but they're not
        # receipts — surface them as errors with the body attached.
        if status == 401 or status == 403:
            raise MeshQuClientError(
                kind="auth",
                detail=f"auth rejected (HTTP {status})",
                status_code=status,
                response_body=_safe_truncate(resp.text),
            )
        if status == 429:
            raise MeshQuClientError(
                kind="rate_limit",
                detail="rate limited",
                status_code=status,
                response_body=_safe_truncate(resp.text),
            )
        if 400 <= status < 500:
            raise MeshQuClientError(
                kind="client_error",
                detail=f"client error (HTTP {status})",
                status_code=status,
                response_body=_safe_truncate(resp.text),
            )
        if 500 <= status < 600:
            raise MeshQuClientError(
                kind="server_error",
                detail=f"server error (HTTP {status})",
                status_code=status,
                response_body=_safe_truncate(resp.text),
            )

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
