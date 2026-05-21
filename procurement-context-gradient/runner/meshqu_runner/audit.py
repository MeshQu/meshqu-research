"""Append-only JSONL writers for audit/decision_traces, audit/anomalies, audit/checkpoints.

Schemas live in `procurement-decisions/results/audit/README.md`. Writers here
honour the discipline rules: one-line JSON, UTC ISO-8601 ms timestamps,
append-only file handles opened per write so partial-flush after crash
doesn't drop earlier lines.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


AnomalyCategory = Literal[
    "latency_spike",
    "rekor_anchor_failed",
    "rekor_anchor_slow",
    "verifier_rejected",
    "agent_output_malformed",
    "agent_timeout",
    "substrate_record_malformed",
    "policy_evaluator_error",
    "db_write_slow",
    "db_write_failed",
    "screenshot_capture_failed",
    "dashboard_mirror_drift",
    # Receipt landed at MeshQu but the local post-receipt write
    # (sidecar / manifest patch / decision_traces row) failed. The
    # remote receipt is durable; the local trace is missing. Recovery
    # script: scan anomalies.jsonl for this category, fetch the
    # cached receipt via the captured idempotency key, and replay the
    # local writes.
    "receipt_orphaned",
    "unexpected",
]

AnomalySeverity = Literal["info", "warn", "error"]


def _utc_iso8601_ms() -> str:
    """ISO-8601 UTC timestamp with millisecond precision, e.g. 2026-05-16T14:32:11.123Z."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class AnomalyEvent:
    run_id: str
    category: AnomalyCategory
    severity: AnomalySeverity
    summary: str
    detail: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": _utc_iso8601_ms(),
            "run_id": self.run_id,
            "anomaly_id": self.anomaly_id,
            "category": self.category,
            "severity": self.severity,
            "context": self.context,
            "summary": self.summary,
            "detail": self.detail,
        }


class AuditWriter:
    """Per-run append-only JSONL writer over the three audit files.

    The writer opens each file in append mode for every write rather than
    holding a long-lived handle — this is the trade the README's discipline
    rules nudge toward: partial-flush after crash never drops earlier lines
    because each line is fsync-committed before the next call returns.
    """

    def __init__(self, audit_dir: Path, run_id: str) -> None:
        self.audit_dir = audit_dir
        self.run_id = run_id
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.anomalies_path = self.audit_dir / "anomalies.jsonl"
        self.decision_traces_path = self.audit_dir / "decision_traces.jsonl"
        self.checkpoints_path = self.audit_dir / "checkpoints.jsonl"

    @staticmethod
    def _append_line(path: Path, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
            fp.flush()

    def write_anomaly(self, event: AnomalyEvent) -> str:
        self._append_line(self.anomalies_path, event.to_dict())
        return event.anomaly_id

    def write_decision_trace(self, trace: dict[str, Any]) -> None:
        payload = {"ts": _utc_iso8601_ms(), "run_id": self.run_id, **trace}
        self._append_line(self.decision_traces_path, payload)

    def write_checkpoint(
        self,
        last_completed_record_index: int,
        next_record_index: int,
        decisions_completed: int,
        decisions_remaining: int,
        resumable: bool = True,
        notes: str = "",
    ) -> str:
        checkpoint_id = str(uuid.uuid4())
        payload = {
            "ts": _utc_iso8601_ms(),
            "run_id": self.run_id,
            "checkpoint_id": checkpoint_id,
            "last_completed_record_index": last_completed_record_index,
            "next_record_index": next_record_index,
            "decisions_completed": decisions_completed,
            "decisions_remaining": decisions_remaining,
            "resumable": resumable,
            "notes": notes,
        }
        self._append_line(self.checkpoints_path, payload)
        return checkpoint_id
