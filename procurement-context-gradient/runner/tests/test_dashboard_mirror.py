"""Dashboard mirror + SHA256 drift detection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from meshqu_runner.audit import AuditWriter
from meshqu_runner.config import RunnerConfig
from meshqu_runner.dashboard_mirror import (
    MirrorError,
    _canonical_dashboard_bytes,
    _sha256,
    load_source_of_truth,
    mirror_and_verify,
)


SAMPLE_DASHBOARD = {
    "uid": "experiment-tenant-observability",
    "title": "Experiment Tenant Observability",
    "schemaVersion": 39,
    "panels": [{"id": 1, "gridPos": {"x": 0, "y": 0, "w": 12, "h": 4}}],
}


def _config_for(tmp_path: Path, *, monorepo_path: Path | None = None) -> RunnerConfig:
    return RunnerConfig(
        grafana_url="http://example.invalid",
        grafana_user="admin",
        grafana_password="admin",
        dashboard_uid="experiment-tenant-observability",
        tenant="experiment-procurement",
        results_dir=tmp_path,
        monorepo_dashboard_path=monorepo_path,
    )


def test_canonical_bytes_strip_grafana_export_wrapper() -> None:
    body = {"panels": [{"id": 1}], "uid": "x"}
    wrapped = {"dashboard": body, "meta": {"updated": "non-deterministic"}}
    assert _canonical_dashboard_bytes(body) == _canonical_dashboard_bytes(wrapped)


def test_canonical_bytes_ignore_grafana_internal_id_and_version() -> None:
    """Grafana assigns its own `id` + bumps `version` on save — these are
    bookkeeping fields, not content. Must be stripped before comparison
    so a freshly-provisioned dashboard doesn't read as drift purely
    because Grafana gave it an internal primary key.
    """
    committed = {"uid": "x", "id": None, "version": 1, "panels": []}
    live = {"uid": "x", "id": 42, "version": 7, "panels": []}
    assert _sha256(_canonical_dashboard_bytes(committed)) == _sha256(_canonical_dashboard_bytes(live))


def test_canonical_bytes_sorted_so_key_order_doesnt_cause_false_drift() -> None:
    a = {"uid": "x", "title": "t"}
    b = {"title": "t", "uid": "x"}
    assert _sha256(_canonical_dashboard_bytes(a)) == _sha256(_canonical_dashboard_bytes(b))


def test_load_source_of_truth_prefers_monorepo_when_available(tmp_path: Path) -> None:
    monorepo_path = tmp_path / "monorepo-dashboard.json"
    monorepo_path.write_text(json.dumps({**SAMPLE_DASHBOARD, "title": "From Monorepo"}))
    config = _config_for(tmp_path, monorepo_path=monorepo_path)
    # Also write a committed mirror so we can verify monorepo wins
    config.committed_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    config.committed_dashboard_path.write_text(json.dumps({**SAMPLE_DASHBOARD, "title": "From Mirror"}))

    obj, label = load_source_of_truth(config)
    assert label == "monorepo"
    assert obj["title"] == "From Monorepo"


def test_load_source_of_truth_falls_back_to_committed_mirror(tmp_path: Path) -> None:
    config = _config_for(tmp_path, monorepo_path=tmp_path / "does-not-exist.json")
    config.committed_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    config.committed_dashboard_path.write_text(json.dumps(SAMPLE_DASHBOARD))

    obj, label = load_source_of_truth(config)
    assert label == "committed-mirror"
    assert obj["uid"] == "experiment-tenant-observability"


def test_load_source_of_truth_raises_when_neither_available(tmp_path: Path) -> None:
    config = _config_for(tmp_path)
    with pytest.raises(MirrorError, match="No source-of-truth"):
        load_source_of_truth(config)


def test_mirror_and_verify_succeeds_when_live_matches(tmp_path: Path, monkeypatch) -> None:
    config = _config_for(tmp_path)
    config.committed_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    config.committed_dashboard_path.write_text(json.dumps(SAMPLE_DASHBOARD))

    import meshqu_runner.dashboard_mirror as dm

    def fake_fetch(cfg):
        # Grafana wraps the body in {"dashboard": ..., "meta": ...}
        return {"dashboard": SAMPLE_DASHBOARD, "meta": {"updated": "ignore"}}

    monkeypatch.setattr(dm, "fetch_live_dashboard", fake_fetch)

    result = dm.mirror_and_verify(config)
    assert result.drift is False
    assert result.source_of_truth == "committed-mirror"
    assert result.canonical_sha256 == result.live_grafana_sha256


def test_mirror_and_verify_detects_drift_and_raises(tmp_path: Path, monkeypatch) -> None:
    config = _config_for(tmp_path)
    config.committed_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    config.committed_dashboard_path.write_text(json.dumps(SAMPLE_DASHBOARD))

    audit = AuditWriter(config.audit_dir, run_id="run-drift")

    import meshqu_runner.dashboard_mirror as dm

    def fake_fetch(cfg):
        drifted = {**SAMPLE_DASHBOARD, "title": "Stale Title"}
        return {"dashboard": drifted, "meta": {"updated": "ignore"}}

    monkeypatch.setattr(dm, "fetch_live_dashboard", fake_fetch)

    with pytest.raises(MirrorError, match="drift detected"):
        dm.mirror_and_verify(config, audit_writer=audit, run_id="run-drift")

    anomaly_line = (config.audit_dir / "anomalies.jsonl").read_text().splitlines()[0]
    parsed = json.loads(anomaly_line)
    assert parsed["category"] == "dashboard_mirror_drift"
    assert parsed["severity"] == "error"
    assert parsed["run_id"] == "run-drift"


def test_mirror_and_verify_rewrites_committed_mirror_from_monorepo(tmp_path: Path, monkeypatch) -> None:
    """Source-of-truth=monorepo case must refresh the public-repo mirror file."""
    monorepo_path = tmp_path / "monorepo-dashboard.json"
    monorepo_dashboard = {**SAMPLE_DASHBOARD, "title": "Authoritative From Monorepo"}
    monorepo_path.write_text(json.dumps(monorepo_dashboard))

    config = _config_for(tmp_path, monorepo_path=monorepo_path)
    config.committed_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    config.committed_dashboard_path.write_text(json.dumps({**SAMPLE_DASHBOARD, "title": "Stale Mirror"}))

    import meshqu_runner.dashboard_mirror as dm

    monkeypatch.setattr(
        dm, "fetch_live_dashboard",
        lambda cfg: {"dashboard": monorepo_dashboard, "meta": {}},
    )

    dm.mirror_and_verify(config)
    refreshed = json.loads(config.committed_dashboard_path.read_text())
    assert refreshed["title"] == "Authoritative From Monorepo"
