"""
Tests for eval_loop — orchestration discipline:
- receipt-write atomicity (no trace row on parse-failure or MeshQu error)
- agent-output sidecar lands per receipt
- manifest gets the policy_snapshot_id on first receipt
- agreement projection per record
- run-end summary reflects per-bucket counts

Substrate is stubbed via plain callables so this file is independent of
the substrate-adapter PR being merged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from meshqu_runner.agent import AgentCallError, AgentResponse
from meshqu_runner.audit import AuditWriter
from meshqu_runner.eval_loop import (
    EvalLoopConfig,
    build_user_message,
    make_run_directory,
    run_eval_loop,
)
from meshqu_runner.meshqu_client import MeshQuClient, MeshQuClientError, ReceiptSummary


# ---------------------------------------------------------------------------
# Lightweight stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubAdaptedRecord:
    ocid: str | None
    context: dict[str, Any]
    substrate_notes: dict[str, Any]


def _make_adapter(records_to_adapt: dict[str, _StubAdaptedRecord]):
    def adapter(record: Mapping[str, Any]) -> _StubAdaptedRecord:
        return records_to_adapt[record["id"]]
    return adapter


def _empty_provenance_summary(notes: Mapping[str, Any]) -> dict[str, int]:
    return {"direct_ocds": 0, "derived": 0, "proxy": 0, "absent": 0}


class _StubAgent:
    """Stand-in for meshqu_runner.agent.Agent. Only exposes the bits the
    eval loop actually reads."""

    def __init__(
        self,
        *,
        responses: list[Any] | None = None,
        model_id: str = "gpt-5.4-2026-03-05",
        temperature: float = 0.0,
        system_prompt_sha256: str = "PROMPTHASH",
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.system_prompt_sha256 = system_prompt_sha256
        self._responses = list(responses or [])

    def evaluate(self, user_message: str) -> AgentResponse:
        if not self._responses:
            raise AssertionError("stub agent ran out of canned responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _agent_response_ok(verdict: str = "ALLOW", reasoning: str = "ok") -> AgentResponse:
    return AgentResponse(
        verdict=verdict,  # type: ignore[arg-type]
        reasoning=reasoning,
        reasoning_sha256="RH",
        recommended_action="proceed",
        raw_response=f'{{"verdict":"{verdict.lower()}"}}',
        latency_ms=12,
        output_mode="json_object",
        parse_status="ok",
    )


def _agent_response_parse_fail() -> AgentResponse:
    return AgentResponse(
        verdict=None,
        reasoning="",
        reasoning_sha256="EMPTY",
        recommended_action=None,
        raw_response="garbage",
        latency_ms=12,
        output_mode="plain_text",
        parse_status="invalid_json",
        parse_detail="not json",
    )


class _StubMeshQuClient:
    """Records calls + returns canned ReceiptSummary or raises canned error."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def record_decision(
        self,
        *,
        context: Mapping[str, Any],
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> ReceiptSummary:
        self.calls.append(
            {
                "context": dict(context),
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
            }
        )
        if not self._responses:
            raise AssertionError("stub meshqu client ran out of canned responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _receipt(decision_id: str = "dec-1", verdict: str = "ALLOW") -> ReceiptSummary:
    return ReceiptSummary(
        decision_id=decision_id,
        decision=verdict,  # type: ignore[arg-type]
        policy_snapshot_id="snap-uuid",
        integrity_hash="intgh",
        evaluated_rules_hash="ruleh",
        timestamp="2026-05-16T12:00:00Z",
        signature_kid="meshqu-experiment-procurement-2026-05",
        signature="sig",
        policy_snapshot_digest="psdig",
        transparency_anchor=None,
    )


# ---------------------------------------------------------------------------
# Fixtures + builders
# ---------------------------------------------------------------------------


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    rd, _ = make_run_directory(tmp_path / "results", run_id="test-run")
    return rd


def _make_config(
    run_dir: Path,
    repo_dir: Path,
    count: int = 1,
    *,
    inter_request_pause_seconds: float = 0.0,
) -> EvalLoopConfig:
    # Patch the system prompt to avoid hitting the real file.
    prompt_path = run_dir / "system_prompt.md"
    prompt_path.write_text("Test system prompt.")
    return EvalLoopConfig(
        run_id="test-run",
        run_phase="dry-run",
        repo_dir=repo_dir,
        run_dir=run_dir,
        meshqu_api_url="https://api.example.com/",
        meshqu_api_key="sk-test",
        meshqu_tenant_id="243f19a5-4d4f-4070-9ec1-8170e8260e26",
        meshqu_tenant_label="experiment-procurement",
        agent_api_key="ai-test",
        substrate_adapter_version="0.1.0",
        substrate_source={"feed": "ocds-stub"},
        record_target_count=count,
        system_prompt_path=prompt_path,
        inter_request_pause_seconds=inter_request_pause_seconds,
    )


# ---------------------------------------------------------------------------
# build_user_message — canonical JSON
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    def test_is_canonical_json(self) -> None:
        msg = build_user_message(
            context={"decision_type": "procurement_decision", "fields": {"b": 2, "a": 1}},
            substrate_notes={},
        )
        # Reparse and round-trip — keys sorted, no whitespace.
        parsed = json.loads(msg)
        assert parsed["fields"] == {"a": 1, "b": 2}
        assert "  " not in msg
        # Re-serialise with same options → byte-identical (canonical)
        again = json.dumps(parsed, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert msg == again

    def test_serialises_field_provenance_objects(self) -> None:
        @dataclass
        class FP:
            status: str
            confidence: str
            detail: str
            value: Any = None

        msg = build_user_message(
            context={"decision_type": "x", "fields": {}},
            substrate_notes={"x": FP("proxy", "medium", "proxy detail", "true")},
        )
        parsed = json.loads(msg)
        assert parsed["substrate_notes"]["x"]["status"] == "proxy"
        assert parsed["substrate_notes"]["x"]["confidence"] == "medium"
        assert parsed["substrate_notes"]["x"]["value"] == "true"


# ---------------------------------------------------------------------------
# Eval-loop happy path
# ---------------------------------------------------------------------------


class TestEvalLoopHappyPath:
    def test_full_run_writes_manifest_traces_and_sidecar(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path, count=1)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")])
        meshqu = _StubMeshQuClient(responses=[_receipt("dec-1", "ALLOW")])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-uk-1",
                context={"decision_type": "procurement_decision", "fields": {"a": 1}},
                substrate_notes={},
            )
        }

        summary = run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        # 1) manifest exists + policy_snapshot_id patched
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["policy_snapshot_id"] == "snap-uuid"
        assert manifest["agent_model_id"] == "gpt-5.4-2026-03-05"
        # 2) run_end exists with status=completed
        run_end = json.loads((run_dir / "run_end.json").read_text())
        assert run_end["status"] == "completed"
        assert run_end["records_with_receipt"] == 1
        # 3) decision_traces row written
        traces_file = run_dir / "decision_traces.jsonl"
        assert traces_file.exists()
        trace = json.loads(traces_file.read_text().splitlines()[0])
        assert trace["decision_id"] == "dec-1"
        assert trace["agent_verdict"] == "ALLOW"
        assert trace["meshqu_verdict"] == "ALLOW"
        assert trace["agreement"] is True
        # 4) sidecar written
        sidecar = run_dir / "agent_outputs" / "dec-1.json"
        assert sidecar.exists()
        sc = json.loads(sidecar.read_text())
        assert sc["decision_id"] == "dec-1"
        # 5) returned summary matches files
        assert summary.records_with_receipt == 1
        assert summary.policy_snapshot_id == "snap-uuid"
        assert summary.outcomes[0].outcome == "receipt"
        assert summary.outcomes[0].agreement is True

    def test_injects_agent_fields_into_meshqu_request_context(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("DENY", reasoning="bad signal")])
        meshqu = _StubMeshQuClient(responses=[_receipt("dec-2", "DENY")])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-uk-2",
                context={"decision_type": "procurement_decision", "fields": {"x": 1}},
                substrate_notes={},
            )
        }
        run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        ctx_sent = meshqu.calls[0]["context"]
        assert ctx_sent["fields"]["x"] == 1  # substrate preserved
        assert ctx_sent["fields"]["agent_model_id"] == "gpt-5.4-2026-03-05"
        assert ctx_sent["fields"]["agent_recommended_verdict"] == "DENY"
        assert ctx_sent["fields"]["agent_temperature"] == 0.0
        assert ctx_sent["fields"]["agent_prompt_sha256"] == "PROMPTHASH"
        # Idempotency key + correlation id are non-empty
        assert meshqu.calls[0]["idempotency_key"]
        assert meshqu.calls[0]["correlation_id"] == "test-run/0"


# ---------------------------------------------------------------------------
# Receipt-write atomicity — skip paths must NOT write a trace row
# ---------------------------------------------------------------------------


class TestReceiptAtomicity:
    def test_agent_parse_failure_skips_meshqu_and_trace(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_parse_fail()])
        # Critical: if eval loop calls MeshQu after a parse failure, this
        # stub raises (empty responses list).
        meshqu = _StubMeshQuClient(responses=[])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-1",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }

        summary = run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        # MeshQu was NOT called
        assert meshqu.calls == []
        # No trace row
        assert not (run_dir / "decision_traces.jsonl").exists()
        # Anomaly was logged
        anomalies = (run_dir / "anomalies.jsonl").read_text().splitlines()
        assert len(anomalies) == 1
        assert json.loads(anomalies[0])["category"] == "agent_output_malformed"
        assert summary.records_with_agent_parse_failure == 1
        assert summary.records_with_receipt == 0

    def test_agent_call_error_skips_meshqu_and_trace(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[AgentCallError(kind="timeout", detail="slow")])
        meshqu = _StubMeshQuClient(responses=[])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid=None,
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }

        summary = run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        assert meshqu.calls == []
        assert not (run_dir / "decision_traces.jsonl").exists()
        anomaly = json.loads((run_dir / "anomalies.jsonl").read_text().splitlines()[0])
        assert anomaly["category"] == "agent_timeout"
        assert summary.records_with_agent_call_error == 1
        # Regression: must persist into run_end.json (was previously dropped)
        run_end = json.loads((run_dir / "run_end.json").read_text())
        assert run_end["records_with_agent_call_error"] == 1

    def test_meshqu_error_skips_trace(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")])
        meshqu = _StubMeshQuClient(
            responses=[MeshQuClientError(kind="server_error", detail="500", status_code=500)]
        )

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-1",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }
        summary = run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        # No trace row, no sidecar
        assert not (run_dir / "decision_traces.jsonl").exists()
        assert not (run_dir / "agent_outputs").exists()
        anomaly = json.loads((run_dir / "anomalies.jsonl").read_text().splitlines()[0])
        assert anomaly["category"] == "db_write_failed"
        assert summary.records_with_meshqu_error == 1


# ---------------------------------------------------------------------------
# Orphaned-receipt path — receipt at MeshQu, local write fails
# ---------------------------------------------------------------------------


class _RaisingAuditWriter(AuditWriter):
    """AuditWriter that raises on write_decision_trace — simulates a
    local disk failure after the MeshQu receipt already landed.

    Inherits write_anomaly behaviour so the eval loop can still record
    the orphan event."""

    def write_decision_trace(self, trace: dict) -> None:  # type: ignore[override]
        raise OSError("disk full")


class TestOrphanedReceipt:
    def test_local_write_failure_after_receipt_emits_orphan_anomaly(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = _RaisingAuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")])
        meshqu = _StubMeshQuClient(responses=[_receipt("dec-orphan", "ALLOW")])
        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-orphan",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }

        summary = run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        # MeshQu WAS called (orphan means receipt exists remotely)
        assert len(meshqu.calls) == 1
        # NOT counted as a successful receipt
        assert summary.records_with_receipt == 0
        assert summary.records_with_orphaned_receipt == 1
        # Anomaly recorded with decision_id + idempotency_key for recovery
        anomalies = [
            json.loads(line)
            for line in (run_dir / "anomalies.jsonl").read_text().splitlines()
        ]
        assert len(anomalies) == 1
        anomaly = anomalies[0]
        assert anomaly["category"] == "receipt_orphaned"
        assert anomaly["severity"] == "error"
        assert anomaly["context"]["decision_id"] == "dec-orphan"
        assert anomaly["context"]["idempotency_key"]
        # Outcome reports orphan + carries the decision_id so the test
        # harness/recovery script can act on summary.outcomes too.
        assert summary.outcomes[0].outcome == "orphaned_receipt"
        assert summary.outcomes[0].decision_id == "dec-orphan"
        # run_end persists the orphan counter
        run_end = json.loads((run_dir / "run_end.json").read_text())
        assert run_end["records_with_orphaned_receipt"] == 1
        assert run_end["records_with_receipt"] == 0


# ---------------------------------------------------------------------------
# Multi-record loop — agreement projection across mixed verdicts
# ---------------------------------------------------------------------------


class TestMultiRecordLoop:
    def test_agreement_projection_across_records(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(run_dir, repo_dir=tmp_path, count=3)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(
            responses=[
                _agent_response_ok("ALLOW"),  # match
                _agent_response_ok("DENY"),  # disagreement
                _agent_response_ok("REVIEW"),  # match (REVIEW vs REVIEW)
            ]
        )
        meshqu = _StubMeshQuClient(
            responses=[
                _receipt("d1", "ALLOW"),
                _receipt("d2", "ALLOW"),
                _receipt("d3", "REVIEW"),
            ]
        )
        adapted = {
            f"r{i}": _StubAdaptedRecord(
                ocid=f"ocds-{i}",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
            for i in range(1, 4)
        }

        summary = run_eval_loop(
            config=config,
            records=[{"id": f"r{i}"} for i in range(1, 4)],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        assert [o.agreement for o in summary.outcomes] == [True, False, True]
        assert summary.records_with_receipt == 3
        # Three trace rows
        rows = (run_dir / "decision_traces.jsonl").read_text().splitlines()
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# Inter-request pacing
# ---------------------------------------------------------------------------


class TestInterRequestPause:
    def test_pauses_between_records_not_before_first(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(
            run_dir, repo_dir=tmp_path, count=3, inter_request_pause_seconds=0.5
        )
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")] * 3)
        meshqu = _StubMeshQuClient(responses=[_receipt(f"d{i}", "ALLOW") for i in range(3)])
        adapted = {
            f"r{i}": _StubAdaptedRecord(
                ocid=f"ocds-{i}",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
            for i in range(1, 4)
        }
        sleeps: list[float] = []

        run_eval_loop(
            config=config,
            records=[{"id": f"r{i}"} for i in range(1, 4)],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
            sleep_fn=sleeps.append,
        )

        # 3 records → 2 inter-request sleeps (between records 1-2 and 2-3).
        assert sleeps == [0.5, 0.5]

    def test_no_sleep_when_pause_is_zero(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        config = _make_config(
            run_dir, repo_dir=tmp_path, count=2, inter_request_pause_seconds=0.0
        )
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")] * 2)
        meshqu = _StubMeshQuClient(responses=[_receipt(f"d{i}", "ALLOW") for i in range(2)])
        adapted = {
            f"r{i}": _StubAdaptedRecord(
                ocid=f"ocds-{i}",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
            for i in range(1, 3)
        }
        sleeps: list[float] = []

        run_eval_loop(
            config=config,
            records=[{"id": f"r{i}"} for i in range(1, 3)],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
            sleep_fn=sleeps.append,
        )

        assert sleeps == []

    def test_retry_count_persists_into_trace_row(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        """Agent retries should surface in decision_traces.jsonl rows so
        the writeup can correlate retries with downstream behaviour."""
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        # Bake retry_count=2 into the canned agent response.
        agent_resp = _agent_response_ok("ALLOW")
        agent_resp.retry_count = 2
        agent = _StubAgent(responses=[agent_resp])
        meshqu = _StubMeshQuClient(responses=[_receipt("dec-rx", "ALLOW")])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-1",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }
        run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        trace = json.loads((run_dir / "decision_traces.jsonl").read_text().splitlines()[0])
        assert trace["agent_retry_count"] == 2

    def test_meshqu_retry_count_persists_into_trace_row(
        self, tmp_path: Path, run_dir: Path
    ) -> None:
        """Mirror of agent_retry_count: MeshQu retries (added 2026-05-18
        after the aborted run surfaced the gap) must surface in the
        trace row so the writeup can report 'k network resets absorbed,
        0 corpus losses' rather than 'no errors observed'."""
        config = _make_config(run_dir, repo_dir=tmp_path)
        audit = AuditWriter(run_dir, config.run_id)
        agent = _StubAgent(responses=[_agent_response_ok("ALLOW")])
        # Bake retry_count=3 into the canned receipt.
        receipt = _receipt("dec-mqu-rx", "ALLOW")
        receipt.retry_count = 3
        meshqu = _StubMeshQuClient(responses=[receipt])

        adapted = {
            "r1": _StubAdaptedRecord(
                ocid="ocds-1",
                context={"decision_type": "x", "fields": {}},
                substrate_notes={},
            )
        }
        run_eval_loop(
            config=config,
            records=[{"id": "r1"}],
            substrate_callable=_make_adapter(adapted),
            provenance_summary_callable=_empty_provenance_summary,
            audit_writer=audit,
            meshqu_client=meshqu,  # type: ignore[arg-type]
            agent=agent,  # type: ignore[arg-type]
        )

        trace = json.loads((run_dir / "decision_traces.jsonl").read_text().splitlines()[0])
        assert trace["meshqu_retry_count"] == 3
        # Sanity: agent_retry_count still defaults to 0 on the happy path
        assert trace["agent_retry_count"] == 0
