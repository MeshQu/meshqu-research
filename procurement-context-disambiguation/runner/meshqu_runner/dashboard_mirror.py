"""OBS-206 — automated dashboard JSON mirror + SHA256 drift detection.

Contract from `procurement-decisions/results/observability/dashboards/README.md`:

  At run start the runner re-mirrors the source-of-truth dashboard JSON
  to `results/observability/dashboards/<uid>.json`, then fetches the
  same dashboard from live Grafana and SHA256-compares them. If they
  differ, the committed JSON would lie about what the screenshots show,
  so the run fails clearly.

Source-of-truth resolution order:
  1. `config.monorepo_dashboard_path` if reachable — the canonical file
     in the private monorepo (`monitoring/dashboards/<uid>.json`).
  2. The committed mirror at `config.committed_dashboard_path` — what's
     already in the public repo. The "standalone, no monorepo" path.
  3. Neither reachable → MirrorError. Don't silently fall through.

Comparison is byte-level after canonical JSON normalisation: both sides
get re-serialised with the same separators/sort to absorb cosmetic
formatting differences. If the canonical bytes still differ, the
content is genuinely out of sync.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import requests

from .audit import AnomalyEvent, AuditWriter
from .config import RunnerConfig


class MirrorError(RuntimeError):
    """Raised when the mirror cannot be reconciled with live Grafana."""


@dataclass(frozen=True)
class MirrorResult:
    mirror_path: Path
    source_of_truth: str  # 'monorepo' | 'committed-mirror'
    canonical_sha256: str
    live_grafana_sha256: str
    drift: bool


# Grafana-internal bookkeeping fields that are non-deterministic between
# the committed source and the live API response, and which carry no
# semantic content about what the dashboard renders. Strip from the
# canonical comparison so a freshly-provisioned dashboard doesn't read
# as drift purely because Grafana assigned it an internal primary key.
_GRAFANA_INTERNAL_FIELDS = ("id", "version")


def _canonical_dashboard_bytes(dashboard_obj: dict) -> bytes:
    """Normalise dashboard JSON for comparison.

    The Grafana export wraps the dashboard in `{"dashboard": {...},
    "meta": {...}}` and the meta block carries non-deterministic fields
    (`updated`, `version`, `slug`, etc.). The committed file is just the
    inner dashboard. Strip down to the dashboard body, then drop the
    Grafana-internal bookkeeping fields, before comparing.
    """
    body = dashboard_obj.get("dashboard", dashboard_obj)
    body = {k: v for k, v in body.items() if k not in _GRAFANA_INTERNAL_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_live_dashboard(config: RunnerConfig) -> dict:
    """GET /api/dashboards/uid/<uid> against the configured Grafana."""
    url = f"{config.grafana_url.rstrip('/')}/api/dashboards/uid/{config.dashboard_uid}"
    response = requests.get(
        url,
        auth=(config.grafana_user, config.grafana_password),
        timeout=config.render_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def load_source_of_truth(config: RunnerConfig) -> tuple[dict, str]:
    """Resolve source-of-truth dashboard JSON. Returns (parsed, label)."""
    if config.monorepo_dashboard_path and config.monorepo_dashboard_path.is_file():
        text = config.monorepo_dashboard_path.read_text(encoding="utf-8")
        return json.loads(text), "monorepo"
    if config.committed_dashboard_path.is_file():
        text = config.committed_dashboard_path.read_text(encoding="utf-8")
        return json.loads(text), "committed-mirror"
    raise MirrorError(
        "No source-of-truth dashboard JSON available: neither "
        f"{config.monorepo_dashboard_path!s} (monorepo) nor "
        f"{config.committed_dashboard_path!s} (committed mirror) is readable."
    )


def mirror_and_verify(
    config: RunnerConfig,
    audit_writer: AuditWriter | None = None,
    run_id: str | None = None,
) -> MirrorResult:
    """Write source-of-truth to the mirror dir and SHA256-compare to live Grafana.

    Raises MirrorError on drift so the caller (RunController.run_start)
    can fail the run before any screenshots are captured. If
    audit_writer is provided, drift is also logged as an anomaly
    (severity=error, category=dashboard_mirror_drift) for the run's
    audit trail.
    """
    source_obj, source_label = load_source_of_truth(config)
    try:
        live_obj = fetch_live_dashboard(config)
    except requests.RequestException as exc:
        raise MirrorError(
            f"Could not fetch live dashboard from Grafana at "
            f"{config.grafana_url}: {type(exc).__name__}: {exc}"
        ) from exc

    # Refresh the public-repo mirror from the source-of-truth.
    #
    # Per the dashboards README ("When mirroring, copy the entire file
    # verbatim. Don't reformat, don't strip metadata, don't selectively
    # include panels."), this is a byte-for-byte copy when the source
    # is the monorepo path. When the source is already the committed
    # mirror, the write is a no-op — skip it so we don't accidentally
    # touch mtime or trigger needless git churn.
    config.dashboards_dir.mkdir(parents=True, exist_ok=True)
    if source_label == "monorepo":
        assert config.monorepo_dashboard_path is not None  # type-narrow
        config.committed_dashboard_path.write_bytes(
            config.monorepo_dashboard_path.read_bytes()
        )

    source_canonical = _canonical_dashboard_bytes(source_obj)
    live_canonical = _canonical_dashboard_bytes(live_obj)
    source_sha = _sha256(source_canonical)
    live_sha = _sha256(live_canonical)
    drift = source_sha != live_sha

    if drift:
        detail = (
            f"source_of_truth={source_label} "
            f"source_sha256={source_sha} live_sha256={live_sha} "
            f"committed_mirror_path={config.committed_dashboard_path}"
        )
        if audit_writer is not None and run_id is not None:
            audit_writer.write_anomaly(
                AnomalyEvent(
                    run_id=run_id,
                    category="dashboard_mirror_drift",
                    severity="error",
                    summary=(
                        "Live Grafana dashboard differs from source-of-truth "
                        "JSON — screenshots would not reflect committed state."
                    ),
                    detail=detail,
                    context={
                        "dashboard_uid": config.dashboard_uid,
                        "source_of_truth": source_label,
                    },
                )
            )
        raise MirrorError(
            "Dashboard drift detected at run start. " + detail
        )

    return MirrorResult(
        mirror_path=config.committed_dashboard_path,
        source_of_truth=source_label,
        canonical_sha256=source_sha,
        live_grafana_sha256=live_sha,
        drift=False,
    )
