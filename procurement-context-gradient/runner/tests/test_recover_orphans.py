"""
Tests for the receipt-orphan recovery script.

Covers:
- parse_orphans: filters by category, tolerates malformed lines + missing
  fields, returns empty when anomalies.jsonl is absent.
- load_agent_sidecar: tolerates missing + corrupt files.
- build_recovered_trace: marks rows as recovered, computes agreement
  when both verdicts are present, null otherwise.
- recover_orphans: re-POSTs with the captured idempotency_key, writes
  recovered_traces.jsonl + recovery_summary.json, exit codes,
  re-fetch failures preserved as failed-not-recovered outcomes.
- CLI dry-run path needs no client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from meshqu_runner.audit import AnomalyEvent, AuditWriter
from meshqu_runner.meshqu_client import MeshQuClient, MeshQuClientError, ReceiptSummary
from meshqu_runner.recover_orphans import (
    build_recovered_trace,
    load_agent_sidecar,
    OrphanRecord,
    parse_orphans,
    recover_orphans,
)


# ---------------------------------------------------------------------------
# Test fixtures / stubs
# ---------------------------------------------------------------------------


def _orphan_anomaly(
    audit: AuditWriter,
    *,
    decision_id: str,
    idempotency_key: str = "ik-1",
    record_index: int = 0,
    ocid: str | None = "ocds-1",
) -> str:
    """Write a single receipt_orphaned anomaly via the real AuditWriter."""
    return audit.write_anomaly(
        AnomalyEvent(
            run_id="rid",
            category="receipt_orphaned",
            severity="error",
            summary="local write failed",
            detail="OSError: disk full",
            context={
                "record_index": record_index,
                "ocid": ocid,
                "decision_id": decision_id,
                "policy_snapshot_id": "snap-uuid",
                "integrity_hash": "intgh",
                "idempotency_key": idempotency_key,
            },
        )
    )


def _receipt(decision_id: str, verdict: str = "ALLOW") -> ReceiptSummary:
    return ReceiptSummary(
        decision_id=decision_id,
        decision=verdict,  # type: ignore[arg-type]
        policy_snapshot_id="snap-uuid",
        integrity_hash="intgh",
        evaluated_rules_hash="ruleh",
        timestamp="2026-05-17T12:00:00Z",
        signature_kid="kid",
        signature="sig",
        policy_snapshot_digest="psdig",
        transparency_anchor=None,
        violations=[],
    )


class _StubMeshQuClient:
    """Records calls + returns canned ReceiptSummary or raises canned error.
    Mirrors the real MeshQuClient.record_decision signature."""

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
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# ---------------------------------------------------------------------------
# parse_orphans
# ---------------------------------------------------------------------------


class TestParseOrphans:
    def test_returns_empty_when_no_anomalies_file(self, tmp_path: Path) -> None:
        assert parse_orphans(tmp_path / "missing.jsonl") == []

    def test_filters_only_receipt_orphaned_category(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        # Non-orphan anomaly
        audit.write_anomaly(
            AnomalyEvent(
                run_id="rid",
                category="agent_output_malformed",
                severity="warn",
                summary="parse fail",
            )
        )
        # Real orphan
        _orphan_anomaly(audit, decision_id="dec-1")

        orphans = parse_orphans(tmp_path / "anomalies.jsonl")
        assert len(orphans) == 1
        assert orphans[0].decision_id == "dec-1"
        assert orphans[0].idempotency_key == "ik-1"

    def test_skips_malformed_lines_with_warning(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "anomalies.jsonl").write_text("not json\n")
        orphans = parse_orphans(tmp_path / "anomalies.jsonl")
        assert orphans == []
        assert "malformed" in capsys.readouterr().err

    def test_skips_orphan_without_decision_id(self, tmp_path: Path, capsys) -> None:
        audit = AuditWriter(tmp_path, "rid")
        audit.write_anomaly(
            AnomalyEvent(
                run_id="rid",
                category="receipt_orphaned",
                severity="error",
                summary="x",
                context={"idempotency_key": "ik"},  # no decision_id
            )
        )
        orphans = parse_orphans(tmp_path / "anomalies.jsonl")
        assert orphans == []
        assert "missing decision_id" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# load_agent_sidecar
# ---------------------------------------------------------------------------


class TestLoadAgentSidecar:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_agent_sidecar(tmp_path, "absent-id") is None

    def test_returns_agent_payload(self, tmp_path: Path) -> None:
        sidecar_dir = tmp_path / "agent_outputs"
        sidecar_dir.mkdir()
        (sidecar_dir / "dec-1.json").write_text(
            json.dumps(
                {
                    "decision_id": "dec-1",
                    "user_message": "...",
                    "agent": {
                        "verdict": "ALLOW",
                        "reasoning_sha256": "rh",
                        "recommended_action": "approve",
                        "retry_count": 1,
                        "latency_ms": 250,
                        "output_mode": "json_object",
                        "parse_status": "ok",
                    },
                }
            )
        )
        got = load_agent_sidecar(tmp_path, "dec-1")
        assert got is not None
        assert got["verdict"] == "ALLOW"
        assert got["retry_count"] == 1

    def test_returns_none_when_sidecar_unreadable(
        self, tmp_path: Path, capsys
    ) -> None:
        sidecar_dir = tmp_path / "agent_outputs"
        sidecar_dir.mkdir()
        (sidecar_dir / "dec-1.json").write_text("{invalid json")
        assert load_agent_sidecar(tmp_path, "dec-1") is None
        assert "unreadable" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# build_recovered_trace
# ---------------------------------------------------------------------------


class TestBuildRecoveredTrace:
    def test_marks_as_recovered_with_anomaly_id(self) -> None:
        orphan = OrphanRecord(
            anomaly_id="aid-1", ts="t", record_index=3, ocid="ocds-x",
            decision_id="dec-x", policy_snapshot_id="ps", integrity_hash="ih",
            idempotency_key="ik", summary="", detail="", raw={},
        )
        trace = build_recovered_trace(
            orphan=orphan, receipt=_receipt("dec-x", "ALLOW"), agent_sidecar=None
        )
        assert trace["is_recovered"] is True
        assert trace["recovery_anomaly_id"] == "aid-1"
        assert trace["record_index"] == 3
        assert trace["decision_id"] == "dec-x"
        assert trace["meshqu_verdict"] == "ALLOW"
        # No sidecar → agent fields null
        assert trace["agent_verdict"] is None
        assert trace["reasoning_sha256"] is None
        assert trace["agreement"] is None

    def test_computes_agreement_when_both_verdicts_present(self) -> None:
        orphan = OrphanRecord(
            anomaly_id="aid", ts="t", record_index=0, ocid=None,
            decision_id="dec", policy_snapshot_id="ps", integrity_hash="ih",
            idempotency_key="ik", summary="", detail="", raw={},
        )
        sidecar = {"verdict": "DENY", "reasoning_sha256": "rh", "retry_count": 0}
        trace = build_recovered_trace(
            orphan=orphan,
            receipt=_receipt("dec", "ALLOW"),
            agent_sidecar=sidecar,
        )
        assert trace["agent_verdict"] == "DENY"
        assert trace["meshqu_verdict"] == "ALLOW"
        assert trace["agreement"] is False
        assert trace["reasoning_sha256"] == "rh"
        assert trace["agent_retry_count"] == 0


# ---------------------------------------------------------------------------
# recover_orphans — end-to-end
# ---------------------------------------------------------------------------


class TestRecoverOrphansLive:
    def test_recovers_single_orphan_and_writes_files(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        _orphan_anomaly(audit, decision_id="dec-1")

        client = _StubMeshQuClient(responses=[_receipt("dec-1", "ALLOW")])

        summary = recover_orphans(
            run_dir=tmp_path, client=client, dry_run=False  # type: ignore[arg-type]
        )

        assert summary.orphans_total == 1
        assert summary.recovered == 1
        assert summary.refetch_failed == 0

        # Re-POST used the captured idempotency_key
        assert client.calls[0]["idempotency_key"] == "ik-1"

        # recovered_traces.jsonl written
        recovered = (tmp_path / "recovered_traces.jsonl").read_text().splitlines()
        assert len(recovered) == 1
        row = json.loads(recovered[0])
        assert row["is_recovered"] is True
        assert row["decision_id"] == "dec-1"

        # recovery_summary.json captures outcomes
        rs = json.loads((tmp_path / "recovery_summary.json").read_text())
        assert rs["orphans_total"] == 1
        assert rs["recovered"] == 1
        assert rs["outcomes"][0]["status"] == "recovered"

    def test_refetch_failure_does_not_write_recovered_row(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        _orphan_anomaly(audit, decision_id="dec-1")
        client = _StubMeshQuClient(
            responses=[MeshQuClientError(kind="server_error", detail="500", status_code=500)]
        )

        summary = recover_orphans(
            run_dir=tmp_path, client=client, dry_run=False  # type: ignore[arg-type]
        )
        assert summary.recovered == 0
        assert summary.refetch_failed == 1
        assert summary.outcomes[0].status == "refetch_failed"
        # Empty recovered_traces.jsonl was still written (empty file)
        assert (tmp_path / "recovered_traces.jsonl").read_text() == ""

    def test_multiple_orphans_mixed_outcomes(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        _orphan_anomaly(audit, decision_id="dec-1", idempotency_key="ik-a", record_index=0)
        _orphan_anomaly(audit, decision_id="dec-2", idempotency_key="ik-b", record_index=1)
        _orphan_anomaly(audit, decision_id="dec-3", idempotency_key="ik-c", record_index=2)

        client = _StubMeshQuClient(
            responses=[
                _receipt("dec-1", "ALLOW"),
                MeshQuClientError(kind="timeout", detail="slow"),
                _receipt("dec-3", "DENY"),
            ]
        )

        summary = recover_orphans(
            run_dir=tmp_path, client=client, dry_run=False  # type: ignore[arg-type]
        )

        assert summary.orphans_total == 3
        assert summary.recovered == 2
        assert summary.refetch_failed == 1
        rows = (tmp_path / "recovered_traces.jsonl").read_text().splitlines()
        decision_ids = [json.loads(r)["decision_id"] for r in rows]
        assert decision_ids == ["dec-1", "dec-3"]

    def test_idempotent_rerun_rewrites_recovered_traces(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        _orphan_anomaly(audit, decision_id="dec-1")

        # First pass
        client1 = _StubMeshQuClient(responses=[_receipt("dec-1", "ALLOW")])
        recover_orphans(run_dir=tmp_path, client=client1, dry_run=False)  # type: ignore[arg-type]

        # Second pass — recovered_traces gets rewritten, not appended
        client2 = _StubMeshQuClient(responses=[_receipt("dec-1", "ALLOW")])
        recover_orphans(run_dir=tmp_path, client=client2, dry_run=False)  # type: ignore[arg-type]

        rows = (tmp_path / "recovered_traces.jsonl").read_text().splitlines()
        assert len(rows) == 1  # not doubled


class TestRecoverOrphansDryRun:
    def test_dry_run_does_not_call_client_or_write_files(self, tmp_path: Path) -> None:
        audit = AuditWriter(tmp_path, "rid")
        _orphan_anomaly(audit, decision_id="dec-1")

        summary = recover_orphans(run_dir=tmp_path, client=None, dry_run=True)

        assert summary.orphans_total == 1
        assert summary.recovered == 0
        assert summary.dry_run is True
        assert summary.outcomes[0].status == "dry_run"
        # Neither file is created in dry-run mode
        assert not (tmp_path / "recovered_traces.jsonl").exists()
        assert not (tmp_path / "recovery_summary.json").exists()

    def test_client_required_when_not_dry_run(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            recover_orphans(run_dir=tmp_path, client=None, dry_run=False)
