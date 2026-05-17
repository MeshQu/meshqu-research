"""OBS-205 — automated Grafana screenshot capture.

The contract lives in `procurement-decisions/results/observability/screenshots/README.md`.
Anything here that diverges from that doc is a bug in here, not the doc.

Capture trigger moments (driven by `runner.RunController`):

  - run start  — once
  - checkpoint — every N records (N=10 full, N=2 dry per the README)
  - run end    — once
  - anomaly    — when an `anomalies.jsonl` event with severity warn/error lands

Filename pattern: <run-phase>_<YYYY-MM-DDTHHMM>_<dashboard-slug>_<event>.png

Renderer is pinned to v3.12.5 (OBS-204) — defaults to PNG natively. The
README's belt-and-braces note allows `encoding=png` on v5 but we
deliberately do NOT pass it: the v3 pin's value is "no per-call
workarounds", and adding `encoding=png` as a default would undermine
that contract.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

# Capture the exception classes at module-load time so they stay bound
# to the REAL classes even when tests monkey-patch `screenshots.requests`
# with a fake module that doesn't expose `.exceptions`.
from requests.exceptions import (  # noqa: E402
    ConnectionError as _RequestsConnectionError,
    ReadTimeout as _ReadTimeout,
    RequestException as _RequestException,
)

from .audit import AnomalyEvent, AuditWriter
from .config import RunnerConfig


# Renderer v3.12.5 returns image/png. Reject any other content type — a
# non-PNG body means the renderer pin has drifted (most likely to v5,
# which silently labels PDFs `image/png`). Don't paper over by accepting
# anything that smells like PNG; require the bytes to start with the
# 8-byte PNG signature.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Belt-and-braces height ceiling per OBS-201 progress entry — current
# scaffold renders at ~760px, so 1200 leaves headroom for Sam's
# refinement pass without exceeding what the writeup uses as a figure.
DEFAULT_RENDER_HEIGHT_FALLBACK = 1200


@dataclass(frozen=True)
class CaptureResult:
    ok: bool
    path: Path | None
    bytes_written: int
    duration_seconds: float
    status_code: int | None
    content_type: str | None
    error: str | None = None


class ScreenshotCapturer:
    """Issues render-API calls to Grafana and writes PNGs into the screenshots dir.

    A single instance is created per run by `RunController`. The render
    height is computed once at run start (via the dashboard JSON), cached
    on the instance, and reused for every subsequent capture this run.
    """

    def __init__(
        self,
        config: RunnerConfig,
        audit_writer: AuditWriter,
        run_id: str,
        render_height: int | None = None,
    ) -> None:
        self.config = config
        self.audit_writer = audit_writer
        self.run_id = run_id
        # Allow injection (tests / explicit override) but otherwise leave
        # None and let the first capture-at-run-start compute it.
        self.render_height = render_height

    def compute_render_height(self, dashboard_json: dict) -> int:
        """Apply the formula from the screenshots README to dashboard panels.

        Formula: (max grid_y + max grid_h) × 30 + 100px margin. Returns
        the README's recommended height; the caller decides whether to
        clamp upward for ceiling headroom.
        """
        panels = (
            dashboard_json.get("dashboard", {}).get("panels")
            if "dashboard" in dashboard_json
            else dashboard_json.get("panels")
        )
        if not panels:
            return DEFAULT_RENDER_HEIGHT_FALLBACK
        max_extent = max(
            (p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0))
            for p in panels
        )
        recommended = max_extent * 30 + 100
        # For the experiment-tenant dashboard specifically the scaffold
        # is 22 rows → 760px. Clamp upward to 1200 so headroom exists
        # for any panels Sam adds during the refinement pass (per
        # OBS-201 progress entry's "render at 1200 height" guidance).
        return max(recommended, DEFAULT_RENDER_HEIGHT_FALLBACK)

    def build_render_url(
        self,
        *,
        from_param: str = "now-30m",
        to_param: str = "now",
        height: int | None = None,
    ) -> str:
        params = {
            "orgId": "1",
            "from": from_param,
            "to": to_param,
            "width": "1400",
            "height": str(height or self.render_height or DEFAULT_RENDER_HEIGHT_FALLBACK),
            "kiosk": "tv",
            "var-tenant": self.config.tenant,
            "tz": "UTC",
        }
        return (
            f"{self.config.grafana_url.rstrip('/')}/render/d/"
            f"{self.config.dashboard_uid}?{urlencode(params)}"
        )

    @staticmethod
    def build_filename(
        *,
        run_phase: str,
        dashboard_slug: str,
        event: str,
        when: datetime | None = None,
    ) -> str:
        when = when or datetime.now(timezone.utc)
        stamp = when.strftime("%Y-%m-%dT%H%M")
        return f"{run_phase}_{stamp}_{dashboard_slug}_{event}.png"

    def capture(
        self,
        *,
        run_phase: str,
        event: str,
        from_param: str = "now-30m",
        to_param: str = "now",
    ) -> CaptureResult:
        """Render the dashboard and write the PNG to disk.

        Failure path (per the screenshots README + OBS-205 spec):
          - non-200 response, request timeout, or non-PNG body → log an
            anomaly with category=screenshot_capture_failed and return
            ok=False. Caller continues the run; capture is supporting
            evidence, not the operational record.
        """
        url = self.build_render_url(from_param=from_param, to_param=to_param)
        filename = self.build_filename(
            run_phase=run_phase,
            dashboard_slug=self.config.dashboard_uid,
            event=event,
        )
        out_path = self.config.screenshots_dir / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Single retry on transient network failure (ReadTimeout /
        # ConnectionError). The first dry-run on staging saw a 1/7
        # capture timeout against the Railway-hosted renderer —
        # cold-start latency spikes are real but rarely repeat
        # back-to-back, so one retry recovers them cheaply. Non-network
        # failures (non-200, non-PNG body) are NOT retried — those are
        # deterministic and re-running would just re-fail.
        #
        # Exception classes captured into local names at module load so
        # they stay bound to the REAL classes when tests monkey-patch
        # `scr.requests` with a fake module.
        start = time.monotonic()
        response = None
        last_exc: _RequestException | None = None
        for attempt in (1, 2):
            try:
                response = requests.get(
                    url,
                    auth=(self.config.grafana_user, self.config.grafana_password),
                    timeout=self.config.render_timeout_seconds,
                )
                break  # success — exit retry loop
            except (_ReadTimeout, _RequestsConnectionError) as exc:
                last_exc = exc
                if attempt == 2:
                    break  # exhausted retries, fall through to failure log
                # Else: try once more, no backoff (the first timeout
                # already consumed render_timeout_seconds — by the time
                # we re-issue, the renderer has likely warmed up).
            except _RequestException as exc:
                # Non-retryable network exception (DNS failure, malformed
                # URL, etc.). Don't burn a retry on it.
                last_exc = exc
                break

        if response is None:
            duration = time.monotonic() - start
            assert last_exc is not None
            self._log_capture_failure(
                run_phase=run_phase,
                event=event,
                summary=f"render request failed: {type(last_exc).__name__}",
                detail=f"url={url} error={last_exc} attempts={attempt}",
                status_code=None,
                content_type=None,
            )
            return CaptureResult(
                ok=False,
                path=None,
                bytes_written=0,
                duration_seconds=duration,
                status_code=None,
                content_type=None,
                error=str(last_exc),
            )

        duration = time.monotonic() - start
        ct = response.headers.get("Content-Type", "")
        body = response.content

        if response.status_code != 200:
            self._log_capture_failure(
                run_phase=run_phase,
                event=event,
                summary=f"render returned non-200 status={response.status_code}",
                detail=f"url={url} bytes={len(body)} content_type={ct!r}",
                status_code=response.status_code,
                content_type=ct,
            )
            return CaptureResult(
                ok=False,
                path=None,
                bytes_written=0,
                duration_seconds=duration,
                status_code=response.status_code,
                content_type=ct,
                error="non-200",
            )

        if not body.startswith(PNG_SIGNATURE):
            # Renderer pin drift — likely v5 returning a PDF labelled as PNG.
            self._log_capture_failure(
                run_phase=run_phase,
                event=event,
                summary="render response is not a PNG (first 8 bytes mismatch)",
                detail=(
                    f"url={url} bytes={len(body)} content_type={ct!r} "
                    f"first8={body[:8].hex()} — likely renderer pin drift"
                ),
                status_code=response.status_code,
                content_type=ct,
            )
            return CaptureResult(
                ok=False,
                path=None,
                bytes_written=0,
                duration_seconds=duration,
                status_code=response.status_code,
                content_type=ct,
                error="non-png-body",
            )

        out_path.write_bytes(body)
        return CaptureResult(
            ok=True,
            path=out_path,
            bytes_written=len(body),
            duration_seconds=duration,
            status_code=response.status_code,
            content_type=ct,
        )

    def _log_capture_failure(
        self,
        *,
        run_phase: str,
        event: str,
        summary: str,
        detail: str,
        status_code: int | None,
        content_type: str | None,
    ) -> None:
        self.audit_writer.write_anomaly(
            AnomalyEvent(
                run_id=self.run_id,
                category="screenshot_capture_failed",
                severity="warn",
                summary=summary,
                detail=detail,
                context={
                    "run_phase": run_phase,
                    "event": event,
                    "dashboard_uid": self.config.dashboard_uid,
                    "status_code": status_code,
                    "content_type": content_type,
                },
            )
        )
