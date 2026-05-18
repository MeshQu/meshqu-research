"""
Tests for MeshQuClient — covers field injection, request shape,
response parsing, and HTTP error classification.

The client uses `requests.Session.post`; tests inject a stub session
with a canned `.post` so no real HTTP happens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from meshqu_runner.meshqu_client import (
    CANONICAL_AGENT_FIELD_KEYS,
    MeshQuClient,
    MeshQuClientError,
    inject_agent_fields,
)


# ---------------------------------------------------------------------------
# Stub requests.Session
# ---------------------------------------------------------------------------


@dataclass
class _StubResponse:
    status_code: int
    body: Any  # dict → json-encoded; str → returned verbatim
    _text: str | None = None

    @property
    def text(self) -> str:
        if self._text is not None:
            return self._text
        if isinstance(self.body, str):
            return self.body
        return json.dumps(self.body)

    def json(self) -> Any:
        if isinstance(self.body, str):
            return json.loads(self.body)
        return self.body


class _StubSession:
    """Records calls + returns canned responses/exceptions.

    Supports two APIs:
      - `session.next_response = …` for single-response tests
      - `session.responses = [r1, r2, r3]` for retry tests (FIFO pop)

    If `responses` is non-empty, pops from it; else uses `next_response`.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.next_response: _StubResponse | Exception | None = None
        self.responses: list[_StubResponse | Exception] = []

    def post(self, url: str, *, data: str, headers: dict[str, str], timeout: float) -> _StubResponse:
        self.calls.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        if self.responses:
            behaviour = self.responses.pop(0)
        else:
            behaviour = self.next_response
            self.next_response = None
        if behaviour is None:
            raise AssertionError("no canned response set for stub session")
        if isinstance(behaviour, Exception):
            raise behaviour
        return behaviour


# ---------------------------------------------------------------------------
# Sample receipt payload (matches the API's RecordResponseSchema)
# ---------------------------------------------------------------------------


SAMPLE_RECEIPT_PAYLOAD = {
    "decision": {
        "id": "dec-uuid-1111",
        "tenant_id": "ten-uuid",
        "idempotency_key": "ik",
        "decision_type": "procurement_decision",
        "decision": "ALLOW",
        "context": {},
        "result": {
            "decision": "ALLOW",
            "violations": [],
            "rules_evaluated": 6,
            "evaluation_time_ms": 12,
            "timestamp": "2026-05-16T12:00:00Z",
            "policy_snapshot_id": "snap-uuid",
            "evaluated_rules_hash": "rulesh",
            "integrity_hash": "intgh",
            "signature": "sig-bytes",
            "signature_kid": "meshqu-experiment-procurement-2026-05",
            "policy_snapshot_digest": "psdig",
        },
        "policy_snapshot_id": "snap-uuid",
        "correlation_id": "corr",
        "chain_id": None,
        "chain_step": None,
        "parent_decision_id": None,
        "chain_integrity_hash": None,
        "chain_signature": None,
        "chain_signature_kid": None,
        "chain_signature_algorithm": None,
        "recorded_at": "2026-05-16T12:00:00Z",
        "created_at": "2026-05-16T12:00:00Z",
        "governance_source": {},
        "policy_group_id": None,
        "policy_group_code": None,
    },
    "is_new": True,
    "duration_ms": 30,
    "shadow_mode": {"enabled": False, "original_decision": None},
    "governance_source": {},
}


TEST_TENANT_ID = "243f19a5-4d4f-4070-9ec1-8170e8260e26"


def _make_client(
    session: _StubSession,
    *,
    retry_max_attempts: int = 1,  # default: no retry (existing tests pre-date retry)
    sleep_fn=None,
    jitter_fn=None,
) -> MeshQuClient:
    extra: dict = {}
    if sleep_fn is not None:
        extra["sleep_fn"] = sleep_fn
    if jitter_fn is not None:
        extra["jitter_fn"] = jitter_fn
    return MeshQuClient(
        base_url="https://api.example.com/",
        api_key="key-test",
        tenant_id=TEST_TENANT_ID,
        session=session,  # type: ignore[arg-type]
        retry_max_attempts=retry_max_attempts,
        **extra,
    )


# ---------------------------------------------------------------------------
# inject_agent_fields
# ---------------------------------------------------------------------------


class TestInjectAgentFields:
    def test_all_canonical_keys_present(self) -> None:
        ctx = {"decision_type": "x", "fields": {"foo": "bar"}}
        out = inject_agent_fields(
            ctx,
            agent_model_id="gpt-5.4-2026-03-05",
            agent_temperature=0.0,
            agent_prompt_sha256="ph",
            agent_reasoning_sha256="rh",
            agent_recommended_verdict="ALLOW",
            agent_recommended_action="approve",
        )
        for key in CANONICAL_AGENT_FIELD_KEYS:
            assert key in out["fields"], f"missing canonical key {key}"

    def test_preserves_existing_fields(self) -> None:
        ctx = {"decision_type": "x", "fields": {"foo": "bar", "baz": 1}}
        out = inject_agent_fields(
            ctx,
            agent_model_id="m",
            agent_temperature=0.0,
            agent_prompt_sha256="p",
            agent_reasoning_sha256="r",
            agent_recommended_verdict="DENY",
            agent_recommended_action=None,
        )
        assert out["fields"]["foo"] == "bar"
        assert out["fields"]["baz"] == 1
        assert out["fields"]["agent_recommended_action"] is None

    def test_does_not_mutate_input(self) -> None:
        ctx = {"decision_type": "x", "fields": {"foo": "bar"}}
        snapshot = json.dumps(ctx, sort_keys=True)
        inject_agent_fields(
            ctx,
            agent_model_id="m",
            agent_temperature=0.0,
            agent_prompt_sha256="p",
            agent_reasoning_sha256="r",
            agent_recommended_verdict="DENY",
            agent_recommended_action=None,
        )
        assert json.dumps(ctx, sort_keys=True) == snapshot


# ---------------------------------------------------------------------------
# MeshQuClient.record_decision — happy + error paths
# ---------------------------------------------------------------------------


class TestRecordDecisionHappyPath:
    def test_returns_parsed_receipt(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=201, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)

        receipt = client.record_decision(
            context={"decision_type": "procurement_decision", "fields": {}},
            idempotency_key="ik-abc",
            correlation_id="corr-xyz",
        )

        assert receipt.decision_id == "dec-uuid-1111"
        assert receipt.decision == "ALLOW"
        assert receipt.policy_snapshot_id == "snap-uuid"
        assert receipt.signature_kid == "meshqu-experiment-procurement-2026-05"
        assert receipt.policy_snapshot_digest == "psdig"
        assert receipt.transparency_anchor is None  # not present on this fixture
        assert receipt.violations == []

    def test_request_url_strips_double_slash(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        client.record_decision(context={"decision_type": "x", "fields": {}})
        assert session.calls[0]["url"] == "https://api.example.com/v1/decisions/record"

    def test_request_carries_bearer_tenant_and_correlation_id(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        client.record_decision(
            context={"decision_type": "x", "fields": {}},
            correlation_id="corr-xyz",
        )
        headers = session.calls[0]["headers"]
        assert headers["Authorization"] == "Bearer key-test"
        # Regression for the first-smoke-run bug: tenant header MUST be sent.
        # Without it, the API returns 400 MISSING_TENANT_ID.
        assert headers["x-meshqu-tenant-id"] == TEST_TENANT_ID
        assert headers["Content-Type"] == "application/json"
        assert headers["x-correlation-id"] == "corr-xyz"

    def test_tenant_header_sent_even_without_correlation_id(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        client.record_decision(context={"decision_type": "x", "fields": {}})
        assert session.calls[0]["headers"]["x-meshqu-tenant-id"] == TEST_TENANT_ID

    def test_idempotency_key_serialised_into_body_options(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        client.record_decision(
            context={"decision_type": "x", "fields": {}},
            idempotency_key="ik-abc",
        )
        body = json.loads(session.calls[0]["data"])
        assert body["options"]["idempotency_key"] == "ik-abc"

    def test_no_options_when_idempotency_key_absent(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        client.record_decision(context={"decision_type": "x", "fields": {}})
        body = json.loads(session.calls[0]["data"])
        assert "options" not in body


class TestRecordDecisionErrorClassification:
    @pytest.mark.parametrize(
        "status,expected_kind",
        [
            (401, "auth"),
            (403, "auth"),
            (429, "rate_limit"),
            (400, "client_error"),
            (404, "client_error"),
            (500, "server_error"),
            (503, "server_error"),
        ],
    )
    def test_http_status_codes_classified(self, status: int, expected_kind: str) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=status, body={"error": "x"})
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == expected_kind
        assert excinfo.value.status_code == status

    def test_truncates_oversized_error_body(self) -> None:
        session = _StubSession()
        big_body = "x" * 5000
        session.next_response = _StubResponse(
            status_code=500,
            body={"unused": True},
            _text=big_body,
        )
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        # default truncation = 2048
        assert excinfo.value.response_body is not None
        assert "truncated" in excinfo.value.response_body
        assert len(excinfo.value.response_body) < 5000

    def test_decode_error_when_2xx_returns_non_json(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body="this is not json")
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "decode_error"

    def test_shape_error_when_decision_missing(self) -> None:
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body={"is_new": True})
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "shape_error"

    def test_shape_error_when_result_missing(self) -> None:
        session = _StubSession()
        broken = {"decision": {"id": "x", "policy_snapshot_id": "y"}, "is_new": True}
        session.next_response = _StubResponse(status_code=200, body=broken)
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "shape_error"

    def test_network_error_classified(self) -> None:
        import requests as _r

        session = _StubSession()
        session.next_response = _r.exceptions.ConnectionError("refused")
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "network"

    def test_timeout_classified(self) -> None:
        import requests as _r

        session = _StubSession()
        session.next_response = _r.exceptions.Timeout("slow")
        client = _make_client(session)
        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "timeout"


class TestConstructorValidation:
    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(ValueError):
            MeshQuClient(base_url="", api_key="k", tenant_id=TEST_TENANT_ID)

    def test_rejects_empty_api_key(self) -> None:
        with pytest.raises(ValueError):
            MeshQuClient(base_url="https://x/", api_key="", tenant_id=TEST_TENANT_ID)

    def test_rejects_empty_tenant_id(self) -> None:
        with pytest.raises(ValueError):
            MeshQuClient(base_url="https://x/", api_key="k", tenant_id="")


# ---------------------------------------------------------------------------
# Bounded retry — added 2026-05-18 after aborted run dry-run-5ac1e02c
# (see findings/004-meshqu-client-network-retry-gap.md)
# ---------------------------------------------------------------------------


class _CapturingSleep:
    """Records every sleep duration without actually sleeping."""

    def __init__(self) -> None:
        self.durations: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.durations.append(seconds)


def _resp_with_retry_after(status: int, seconds: str) -> _StubResponse:
    """Build a _StubResponse with a Retry-After header. The default
    _StubResponse uses `text`/`json` properties but no headers; this
    helper subclasses it with a headers dict for the rate-limit tests."""

    class _RespWithHeaders(_StubResponse):
        @property
        def headers(self):  # type: ignore[override]
            return {"Retry-After": seconds}

    return _RespWithHeaders(status_code=status, body={"error": "rate-limited"})


class TestRecordDecisionRetryBehaviour:
    def test_retries_connection_reset_then_succeeds(self) -> None:
        """The aborted-run smoking gun: TCP reset on first attempt,
        success on retry. Mirrors what staging-Railway showed at
        records 8 and 17 of dry-run-5ac1e02c-…"""
        import requests as _r

        session = _StubSession()
        session.responses = [
            _r.exceptions.ConnectionError(
                "('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))"
            ),
            _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD),
        ]
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        receipt = client.record_decision(
            context={"decision_type": "x", "fields": {}}
        )
        assert receipt.decision_id == "dec-uuid-1111"
        assert receipt.retry_count == 1
        assert len(session.calls) == 2
        assert len(sleep.durations) == 1  # one sleep before the retry

    def test_retries_5xx_then_succeeds(self) -> None:
        session = _StubSession()
        session.responses = [
            _StubResponse(status_code=503, body={"error": "x"}),
            _StubResponse(status_code=503, body={"error": "x"}),
            _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD),
        ]
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        receipt = client.record_decision(
            context={"decision_type": "x", "fields": {}}
        )
        assert receipt.retry_count == 2
        assert len(sleep.durations) == 2

    def test_retries_exhausted_raises_with_retry_count(self) -> None:
        import requests as _r

        session = _StubSession()
        session.responses = [
            _r.exceptions.ConnectionError("reset") for _ in range(3)
        ]
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "network"
        assert excinfo.value.retry_count == 2  # 3 attempts → 2 sleeps before failure
        assert len(sleep.durations) == 2

    def test_auth_error_not_retried(self) -> None:
        """401/403 are terminal: credentials are deterministically wrong,
        retry would just waste budget."""
        session = _StubSession()
        session.responses = [_StubResponse(status_code=401, body={"error": "bad key"})]
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "auth"
        assert excinfo.value.retry_count == 0
        assert sleep.durations == []  # no sleeps before terminal raise
        assert len(session.calls) == 1  # exactly one attempt

    def test_client_error_400_not_retried(self) -> None:
        """The smoke's MISSING_TENANT_ID shape — 400 is terminal.
        Retry would just re-fail; regression for that scenario."""
        session = _StubSession()
        session.responses = [
            _StubResponse(
                status_code=400,
                body={"error": {"code": "MISSING_TENANT_ID", "message": "..."}},
            )
        ]
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "client_error"
        assert excinfo.value.retry_count == 0
        assert sleep.durations == []
        assert len(session.calls) == 1

    def test_shape_error_not_retried(self) -> None:
        """2xx with malformed body — terminal (decode/shape errors won't
        reshape on retry)."""
        session = _StubSession()
        session.responses = [_StubResponse(status_code=200, body={"is_new": True})]  # no decision
        sleep = _CapturingSleep()
        client = _make_client(session, retry_max_attempts=3, sleep_fn=sleep)

        with pytest.raises(MeshQuClientError) as excinfo:
            client.record_decision(context={"decision_type": "x", "fields": {}})
        assert excinfo.value.kind == "shape_error"
        assert sleep.durations == []
        assert len(session.calls) == 1

    def test_honours_retry_after_on_429(self) -> None:
        """Rate-limit response with Retry-After=5 → sleep ≥ 5s
        (positive-only jitter; never undershoots the server's floor)."""
        session = _StubSession()
        session.responses = [
            _resp_with_retry_after(429, "5"),
            _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD),
        ]
        sleep = _CapturingSleep()
        client = _make_client(
            session,
            retry_max_attempts=3,
            sleep_fn=sleep,
            jitter_fn=lambda: 0.0,  # worst-case downward bias if signed jitter were applied
        )

        receipt = client.record_decision(context={"decision_type": "x", "fields": {}})
        assert receipt.retry_count == 1
        assert sleep.durations == [5.0]  # exactly the server's minimum, no negative jitter

    def test_caps_retry_after_at_max_backoff(self) -> None:
        """Malicious / broken server: Retry-After=600s caps at
        retry_max_backoff_seconds + positive jitter."""
        session = _StubSession()
        session.responses = [
            _resp_with_retry_after(429, "600"),
            _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD),
        ]
        sleep = _CapturingSleep()
        client = MeshQuClient(
            base_url="https://x/",
            api_key="k",
            tenant_id=TEST_TENANT_ID,
            session=session,  # type: ignore[arg-type]
            retry_max_attempts=3,
            retry_max_backoff_seconds=10.0,
            sleep_fn=sleep,
        )

        client.record_decision(context={"decision_type": "x", "fields": {}})
        assert 10.0 <= sleep.durations[0] <= 12.0  # cap + 0..20% jitter

    def test_happy_path_retry_count_zero(self) -> None:
        """Sanity: zero retries → retry_count = 0 on the ReceiptSummary."""
        session = _StubSession()
        session.next_response = _StubResponse(status_code=200, body=SAMPLE_RECEIPT_PAYLOAD)
        client = _make_client(session)
        receipt = client.record_decision(context={"decision_type": "x", "fields": {}})
        assert receipt.retry_count == 0
