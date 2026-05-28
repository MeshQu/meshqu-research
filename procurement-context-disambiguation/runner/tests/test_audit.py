"""Audit JSONL writer — schema honouring + append-only discipline."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from meshqu_runner.audit import AnomalyEvent, AuditWriter


def test_anomaly_event_to_dict_carries_required_fields(tmp_path: Path) -> None:
    writer = AuditWriter(tmp_path, run_id="run-123")
    event = AnomalyEvent(
        run_id="run-123",
        category="screenshot_capture_failed",
        severity="warn",
        summary="render timed out",
        detail="url=… err=ReadTimeout",
        context={"run_phase": "dry-run", "event": "checkpoint-002"},
    )
    aid = writer.write_anomaly(event)
    line = (tmp_path / "anomalies.jsonl").read_text().splitlines()[0]
    parsed = json.loads(line)
    assert parsed["run_id"] == "run-123"
    assert parsed["category"] == "screenshot_capture_failed"
    assert parsed["severity"] == "warn"
    assert parsed["summary"] == "render timed out"
    assert parsed["context"]["run_phase"] == "dry-run"
    assert parsed["anomaly_id"] == aid
    assert parsed["ts"].endswith("Z")


def test_anomalies_jsonl_is_append_only(tmp_path: Path) -> None:
    writer = AuditWriter(tmp_path, run_id="run-1")
    for i in range(3):
        writer.write_anomaly(
            AnomalyEvent(
                run_id="run-1",
                category="latency_spike",
                severity="info",
                summary=f"event {i}",
            )
        )
    lines = (tmp_path / "anomalies.jsonl").read_text().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert [p["summary"] for p in parsed] == ["event 0", "event 1", "event 2"]


def test_checkpoint_row_carries_resumable_state(tmp_path: Path) -> None:
    writer = AuditWriter(tmp_path, run_id="run-7")
    cid = writer.write_checkpoint(
        last_completed_record_index=10,
        next_record_index=11,
        decisions_completed=11,
        decisions_remaining=289,
    )
    parsed = json.loads((tmp_path / "checkpoints.jsonl").read_text().splitlines()[0])
    assert parsed["checkpoint_id"] == cid
    assert parsed["last_completed_record_index"] == 10
    assert parsed["next_record_index"] == 11
    assert parsed["resumable"] is True
    assert parsed["decisions_remaining"] == 289


def test_decision_trace_passes_through_payload_unmodified(tmp_path: Path) -> None:
    writer = AuditWriter(tmp_path, run_id="run-7")
    writer.write_decision_trace(
        {
            "record_index": 5,
            "ocid": "ocds-abc-123",
            "decision_id": "dec-xyz",
            "agree": True,
            "latency_ms": {"agent": 1240, "meshqu_evaluate": 87, "total": 1327},
        }
    )
    parsed = json.loads((tmp_path / "decision_traces.jsonl").read_text().splitlines()[0])
    assert parsed["ocid"] == "ocds-abc-123"
    assert parsed["agree"] is True
    assert parsed["latency_ms"]["meshqu_evaluate"] == 87
    assert parsed["run_id"] == "run-7"
