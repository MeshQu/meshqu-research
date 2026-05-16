"""Screenshot capture — URL construction, filename pattern, height calc, failure path."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from meshqu_runner.audit import AuditWriter
from meshqu_runner.config import RunnerConfig
from meshqu_runner.screenshots import (
    DEFAULT_RENDER_HEIGHT_FALLBACK,
    ScreenshotCapturer,
)


def _config_for(tmp_path: Path, **overrides) -> RunnerConfig:
    defaults = dict(
        grafana_url="http://localhost:3101",
        grafana_user="admin",
        grafana_password="admin",
        dashboard_uid="experiment-tenant-observability",
        tenant="experiment-procurement",
        results_dir=tmp_path,
        render_timeout_seconds=10.0,
    )
    defaults.update(overrides)
    return RunnerConfig(**defaults)


def _make_capturer(tmp_path: Path, **overrides) -> ScreenshotCapturer:
    config = _config_for(tmp_path, **overrides)
    audit = AuditWriter(config.audit_dir, run_id="run-test")
    return ScreenshotCapturer(config, audit, run_id="run-test", render_height=1200)


def test_render_url_omits_encoding_param_because_renderer_v3_defaults_to_png(tmp_path: Path) -> None:
    """OBS-204 pinned renderer to v3.12.5 → encoding=png must NOT be a default-on param.

    Adding `encoding=png` as default-on would undermine the v3 pin's
    "no per-call workarounds" contract. The capturer omits it.
    """
    capturer = _make_capturer(tmp_path)
    url = capturer.build_render_url()
    qs = parse_qs(urlparse(url).query)
    assert "encoding" not in qs, (
        "encoding=png MUST NOT appear in the default render URL; "
        "v3.12.5 returns PNG natively"
    )


def test_render_url_carries_all_required_params_from_screenshots_readme(tmp_path: Path) -> None:
    capturer = _make_capturer(tmp_path)
    url = capturer.build_render_url()
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.path == "/render/d/experiment-tenant-observability"
    assert qs["orgId"] == ["1"]
    assert qs["width"] == ["1400"]
    assert qs["height"] == ["1200"]
    assert qs["kiosk"] == ["tv"]
    assert qs["var-tenant"] == ["experiment-procurement"]
    assert qs["tz"] == ["UTC"]
    assert qs["from"] == ["now-30m"]
    assert qs["to"] == ["now"]


def test_filename_pattern_matches_readme_spec(tmp_path: Path) -> None:
    when = datetime(2026, 5, 16, 14, 32, tzinfo=timezone.utc)
    fname = ScreenshotCapturer.build_filename(
        run_phase="dry-run",
        dashboard_slug="experiment-tenant-observability",
        event="run-start",
        when=when,
    )
    assert fname == "dry-run_2026-05-16T1432_experiment-tenant-observability_run-start.png"


def test_filename_pattern_with_anomaly_event(tmp_path: Path) -> None:
    when = datetime(2026, 5, 16, 14, 32, tzinfo=timezone.utc)
    fname = ScreenshotCapturer.build_filename(
        run_phase="full-run",
        dashboard_slug="experiment-tenant-observability",
        event="anomaly-rekor_anchor_slow_record-072",
        when=when,
    )
    assert fname == (
        "full-run_2026-05-16T1432_experiment-tenant-observability_"
        "anomaly-rekor_anchor_slow_record-072.png"
    )


def test_render_height_uses_formula_then_clamps_up_for_headroom(tmp_path: Path) -> None:
    capturer = _make_capturer(tmp_path)
    # Live experiment-tenant scaffold: 22 rows × 30 + 100 = 760. Below the
    # 1200 ceiling, so the clamp wins.
    dashboard = {
        "panels": [
            {"gridPos": {"x": 0, "y": 0, "w": 6, "h": 4}},
            {"gridPos": {"x": 0, "y": 4, "w": 12, "h": 9}},
            {"gridPos": {"x": 0, "y": 13, "w": 12, "h": 9}},
        ]
    }
    assert capturer.compute_render_height(dashboard) == 1200


def test_render_height_returns_formula_when_dashboard_is_tall(tmp_path: Path) -> None:
    capturer = _make_capturer(tmp_path)
    # 50 rows + 100 = 1600 — above the 1200 clamp.
    dashboard = {"panels": [{"gridPos": {"x": 0, "y": 41, "w": 24, "h": 9}}]}
    assert capturer.compute_render_height(dashboard) == 1600


def test_render_height_handles_grafana_export_wrapper(tmp_path: Path) -> None:
    capturer = _make_capturer(tmp_path)
    wrapped = {"dashboard": {"panels": [{"gridPos": {"x": 0, "y": 30, "w": 12, "h": 10}}]}}
    # 40 × 30 + 100 = 1300 > clamp.
    assert capturer.compute_render_height(wrapped) == 1300


def test_render_height_fallback_when_no_panels(tmp_path: Path) -> None:
    capturer = _make_capturer(tmp_path)
    assert capturer.compute_render_height({"panels": []}) == DEFAULT_RENDER_HEIGHT_FALLBACK


def test_capture_failure_logs_anomaly_to_jsonl(tmp_path: Path, monkeypatch) -> None:
    """Failure path must log to anomalies.jsonl and never raise."""
    import requests as real_requests

    class _Boom:
        RequestException = real_requests.RequestException

        def get(self, *args, **kwargs):
            raise real_requests.ConnectionError("nope")

    import meshqu_runner.screenshots as scr

    monkeypatch.setattr(scr, "requests", _Boom())

    capturer = _make_capturer(tmp_path)
    result = capturer.capture(run_phase="dry-run", event="run-start")
    assert result.ok is False
    assert result.error == "nope"

    anomalies_path = capturer.config.audit_dir / "anomalies.jsonl"
    assert anomalies_path.exists()
    line = anomalies_path.read_text().splitlines()[0]
    parsed = json.loads(line)
    assert parsed["category"] == "screenshot_capture_failed"
    assert parsed["severity"] == "warn"
    assert parsed["context"]["run_phase"] == "dry-run"
    assert parsed["context"]["event"] == "run-start"


def test_capture_rejects_non_png_body(tmp_path: Path, monkeypatch) -> None:
    """Renderer pin drift — v5 returns PDF labelled image/png. Must catch it."""
    import meshqu_runner.screenshots as scr

    class _Resp:
        status_code = 200
        headers = {"Content-Type": "image/png"}
        content = b"%PDF-1.4 lol nope"

    import requests as real_requests

    class _FakeRequests:
        RequestException = real_requests.RequestException

        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(scr, "requests", _FakeRequests())

    capturer = _make_capturer(tmp_path)
    result = capturer.capture(run_phase="full-run", event="checkpoint-010")
    assert result.ok is False
    assert result.error == "non-png-body"
    anomaly_line = (capturer.config.audit_dir / "anomalies.jsonl").read_text().splitlines()[0]
    parsed = json.loads(anomaly_line)
    assert "renderer pin drift" in parsed["detail"]
