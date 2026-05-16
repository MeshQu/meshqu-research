"""RunController — orchestrates the lifecycle and fires capture/audit at each event.

The eval loop and substrate adapter wire up later; this module is the
skeleton that integration code calls into:

    controller = RunController(config, run_phase="dry-run")
    controller.run_start()
    for record_index, record in enumerate(records):
        # ... evaluate, write decision_trace ...
        controller.after_record(record_index)
        if anomaly_event:
            controller.on_anomaly(anomaly_event)
    controller.run_end()

Checkpoint cadence per `results/observability/screenshots/README.md`:
  - dry-run:  every 2 records
  - full-run: every 10 records
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Literal

from .audit import AnomalyEvent, AnomalySeverity, AuditWriter
from .config import RunnerConfig
from .dashboard_mirror import mirror_and_verify, MirrorResult
from .screenshots import CaptureResult, ScreenshotCapturer


RunPhase = Literal["dry-run", "full-run", "reproducibility-rerun"]


CHECKPOINT_CADENCE = {
    "dry-run": 2,
    "full-run": 10,
    "reproducibility-rerun": 10,
}


@dataclass
class RunController:
    config: RunnerConfig
    run_phase: RunPhase
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0  # known up-front; used for resumable checkpoints
    _audit: AuditWriter = field(init=False)
    _capturer: ScreenshotCapturer = field(init=False)
    _checkpoint_n: int = field(init=False)
    _records_completed: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._audit = AuditWriter(self.config.audit_dir, self.run_id)
        self._capturer = ScreenshotCapturer(
            self.config, self._audit, run_id=self.run_id
        )
        self._checkpoint_n = CHECKPOINT_CADENCE[self.run_phase]

    # ----- lifecycle ----------------------------------------------------

    def run_start(self) -> tuple[MirrorResult, CaptureResult]:
        """OBS-206 mirror + OBS-205 run-start capture, in that order.

        Order matters: if the mirror step detects drift, the run aborts
        before the run-start screenshot lands. The first screenshot a
        successful run produces represents the verified-fresh state.
        """
        mirror_result = mirror_and_verify(self.config, self._audit, self.run_id)

        # Cache the render height from the verified dashboard JSON.
        # We just wrote it to disk, so reading from there is fine and
        # keeps the dashboard-mirror module decoupled from screenshots.
        with self.config.committed_dashboard_path.open("r", encoding="utf-8") as fp:
            dashboard_obj = json.load(fp)
        self._capturer.render_height = self._capturer.compute_render_height(dashboard_obj)

        capture_result = self._capturer.capture(
            run_phase=self.run_phase,
            event="run-start",
            from_param="now-1h",
        )
        return mirror_result, capture_result

    def after_record(self, record_index: int) -> CaptureResult | None:
        """Called after each record completes. Fires a checkpoint capture every N records.

        Also writes a `checkpoints.jsonl` row at the same cadence so the
        audit log lines up with the screenshot moments.
        """
        self._records_completed = record_index + 1
        if (record_index + 1) % self._checkpoint_n != 0:
            return None

        self._audit.write_checkpoint(
            last_completed_record_index=record_index,
            next_record_index=record_index + 1,
            decisions_completed=self._records_completed,
            decisions_remaining=max(self.total_records - self._records_completed, 0),
        )
        checkpoint_label = f"checkpoint-{record_index + 1:03d}"
        return self._capturer.capture(
            run_phase=self.run_phase,
            event=checkpoint_label,
            from_param="now-30m",
        )

    def on_anomaly(
        self,
        category: str,
        summary: str,
        *,
        severity: AnomalySeverity = "warn",
        detail: str = "",
        context: dict | None = None,
        record_index: int | None = None,
    ) -> tuple[str, CaptureResult | None]:
        """Log an anomaly and fire a capture if severity is warn or error.

        Returns (anomaly_id, capture_result-or-None). The capture
        filename embeds `_anomaly-<category>_record-<NNN>` so curators
        can correlate the PNG with the JSONL line.
        """
        ctx = dict(context or {})
        if record_index is not None and "record_index" not in ctx:
            ctx["record_index"] = record_index
        event = AnomalyEvent(
            run_id=self.run_id,
            category=category,  # type: ignore[arg-type]  # runtime-validated by category union
            severity=severity,
            summary=summary,
            detail=detail,
            context=ctx,
        )
        anomaly_id = self._audit.write_anomaly(event)

        if severity in ("warn", "error"):
            event_label = f"anomaly-{category}"
            if record_index is not None:
                event_label += f"_record-{record_index:03d}"
            capture = self._capturer.capture(
                run_phase=self.run_phase,
                event=event_label,
                from_param="now-30m",
            )
            return anomaly_id, capture
        return anomaly_id, None

    def run_end(self) -> CaptureResult:
        return self._capturer.capture(
            run_phase=self.run_phase,
            event="run-end",
            from_param="now-1h",
        )
