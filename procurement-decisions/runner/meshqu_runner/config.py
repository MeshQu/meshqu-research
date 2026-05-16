"""Runner configuration — loaded from environment with local-stack defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]  # …/meshqu-research
DEFAULT_RESULTS_DIR = REPO_ROOT / "procurement-decisions" / "results"


@dataclass(frozen=True)
class RunnerConfig:
    """Resolved configuration for one runner invocation.

    Defaults match the local observability stack defined in the monorepo's
    `monitoring/docker-compose.observability.yml`. Override via env vars
    (prefix `MESHQU_RUNNER_`) for staging / production stacks.
    """

    grafana_url: str = "http://localhost:3101"
    grafana_user: str = "admin"
    grafana_password: str = "admin"
    dashboard_uid: str = "experiment-tenant-observability"
    tenant: str = "experiment-procurement"
    monorepo_dashboard_path: Path | None = None
    results_dir: Path = field(default_factory=lambda: DEFAULT_RESULTS_DIR)
    render_timeout_seconds: float = 10.0

    @property
    def screenshots_dir(self) -> Path:
        return self.results_dir / "observability" / "screenshots"

    @property
    def dashboards_dir(self) -> Path:
        return self.results_dir / "observability" / "dashboards"

    @property
    def audit_dir(self) -> Path:
        return self.results_dir / "audit"

    @property
    def committed_dashboard_path(self) -> Path:
        """The public-repo mirror copy of the dashboard JSON."""
        return self.dashboards_dir / f"{self.dashboard_uid}.json"

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        def env(key: str, default: str | None = None) -> str | None:
            return os.environ.get(f"MESHQU_RUNNER_{key}", default)

        monorepo_path = env("MONOREPO_DASHBOARD_PATH")
        results_dir = env("RESULTS_DIR")
        timeout = env("RENDER_TIMEOUT_SECONDS")

        return cls(
            grafana_url=env("GRAFANA_URL", "http://localhost:3101"),
            grafana_user=env("GRAFANA_USER", "admin"),
            grafana_password=env("GRAFANA_PASSWORD", "admin"),
            dashboard_uid=env("DASHBOARD_UID", "experiment-tenant-observability"),
            tenant=env("TENANT", "experiment-procurement"),
            monorepo_dashboard_path=Path(monorepo_path) if monorepo_path else None,
            results_dir=Path(results_dir) if results_dir else DEFAULT_RESULTS_DIR,
            render_timeout_seconds=float(timeout) if timeout else 10.0,
        )
