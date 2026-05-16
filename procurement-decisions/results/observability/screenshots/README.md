# Screenshots — Grafana Captures from the Runs

> PNG screenshots from the dry run and full run.
> Curated set surfaces in writeup Appendix B.

## What lives here

Time-stamped Grafana screenshots organised by run phase and capture moment.

### Filename pattern

```
<run-phase>_<YYYY-MM-DDTHHMM>_<dashboard-slug>_<event>.png
```

Examples:

- `dry-run_2026-MM-DDTHHMM_experiment-tenant_run-start.png`
- `dry-run_2026-MM-DDTHHMM_experiment-tenant_checkpoint-005.png`
- `dry-run_2026-MM-DDTHHMM_experiment-tenant_run-end.png`
- `full-run_2026-MM-DDTHHMM_experiment-tenant_anomaly-rekor-slow_record-072.png`
- `full-run_2026-MM-DDTHHMM_experiment-tenant_run-end.png`

Phases: `dry-run`, `full-run`, optionally `reproducibility-rerun`.

## Capture cadence — automation is the primary mode

**Automation default.** The harness drives screenshot capture during a run; the researcher's hands are off the keyboard except for notebook entries. A 300-record run takes several hours; an operator manually capturing at each checkpoint loses attention, misses moments, and produces inconsistent filenames. Automation gives the writeup a reliable evidence base regardless of operator focus.

**Automated captures (harness fires the render API call):**

| Moment | Cadence | Purpose |
|---|---|---|
| Run start | Once | Baseline state at execution begin |
| Each checkpoint | Every 10 records in the full run; every 2 in the dry run | Progression evidence; supports "the run behaved steadily over time" claim |
| Run end | Once | Final state at completion or stop |
| Anomaly trigger | When an `anomalies.jsonl` event with `severity: warn` or `error` lands | State-at-the-moment evidence anchored to the audit entry; filename includes `_anomaly-<category>_record-<index>` |

**Manual captures (fallback or researcher-led):**

- **Investigation moments** during the run when the researcher wants the dashboard state for context that exceeds an automated anomaly trigger (e.g. "I want to see the latency tail at this exact moment because it might bear on P6-C"). Filename pattern: `<run-phase>_<YYYY-MM-DDTHHMM>_<dashboard-slug>_manual-<short-note>.png`.
- **Pre-publication curation** of the Appendix B set from the accumulated automated + manual captures. Selection is reviewer judgement; the curated subset is referenced by filename from the writeup.
- **Fallback when the renderer is unavailable.** If the renderer container is down or unreachable at run time, the harness logs the failure to `audit/anomalies.jsonl` (category `screenshot_capture_failed`) and the researcher captures manually at the same cadence using the Grafana UI's "Direct link rendered image" share option.

## Curation discipline

Captured screenshots accumulate across the run; not all of them end up in the writeup.

The Appendix B set is **curated**, not exhaustive. Typical selection:

- One run-start, one run-end per phase (dry run + full run) showing the baseline.
- The most operationally interesting moments — anomaly captures that informed the methodology, latency-histogram captures that demonstrate the product-proof claim.
- Total set sized to roughly 8-15 images for the appendix. More than that and it becomes a screenshot dump rather than a curated evidence set.

The full set stays in this directory (uncurated). The curated subset for the appendix is referenced by filename from the writeup's Appendix B section in `writeup/`. A reader who wants more detail clones the repo and browses this directory.

## What screenshots should show

The four panels brief 7 specified (signing operations, Rekor anchoring, database write throughput, Fastify error rate) should be visible in every capture taken against the experiment-tenant dashboard. The dashboard layout puts all four on one screen so a single screenshot captures all four at once.

Additional panels added during build phase (e.g. anomaly-count timeseries, capacity-headroom indicators) appear on the same dashboard and therefore in the same screenshots.

## What screenshots must NOT show

- Internal MeshQu admin URLs or credentials.
- Other tenants' data (the dashboard's tenant variable filters to `experiment-procurement`; verify before capture).
- Personally-identifiable information beyond what's already public in the OCDS records (signatory names in award notices are already public; nothing else should appear).

If a capture inadvertently includes one of these, delete and re-capture rather than committing.

## File-size discipline

PNG files at typical Grafana resolution are 100-300 KB each. A run produces dozens; the full directory might be 5-15 MB. That's comfortable in git.

If a capture is much larger (multi-MB) it's probably a full-page screenshot rather than a dashboard capture — use the dashboard's own export-PNG function rather than browser screenshot tools.

## How automated captures actually work

The harness calls Grafana's `/render/d/<dashboard-uid>` endpoint at each cadence trigger. The render call is constructed from a small set of conventions.

### Render URL pattern

```
http://<grafana-host>:<port>/render/d/<dashboard-uid>?<params>
```

### Query parameters the harness sets

| Param | Default | Notes |
|---|---|---|
| `orgId` | `1` | Grafana org — always 1 for the experiment tenant |
| `from` | `now-30m` for checkpoints; `now-1h` for start/end | Time range visible in the capture |
| `to` | `now` | Time range end |
| `width` | `1400` | Render viewport width in px |
| `height` | sized to dashboard — see below | Render viewport height in px |
| `encoding` | `png` | **Required when using grafana-image-renderer v5.x** (default behaviour is PDF without it). See "Renderer version gotcha" below. |
| `kiosk` | `tv` | Removes Grafana's top nav bar — cleaner crop, more dashboard per pixel |
| `var-tenant` | `experiment-procurement` | Sets the dashboard's tenant variable to the experiment tenant |
| `tz` | `UTC` | Force timezone in axis labels for cross-region reproducibility |

### Sizing the height correctly

`height` must be tall enough to capture every panel in the dashboard. If the dashboard has panels below the rendered viewport, those panels don't appear in the screenshot.

Formula: `height = (max grid_y + max grid_h) × 30 + 100px margin`.

For any dashboard, compute via the API:

```bash
DASH_UID=experiment-tenant-observability
curl -s -u admin:admin "http://localhost:3101/api/dashboards/uid/${DASH_UID}" | \
  python3 -c "
import json, sys
panels = json.load(sys.stdin).get('dashboard', {}).get('panels', [])
max_y = max((p.get('gridPos', {}).get('y', 0) + p.get('gridPos', {}).get('h', 0)) for p in panels) if panels else 0
print(f'recommended height: {max_y * 30 + 100}px ({max_y} grid rows + 100px margin)')
"
```

The harness implementation calculates this at run start (once per dashboard) and caches the value for the duration of the run.

**Design-time recommendation for the experiment dashboard.** Design the experiment-tenant dashboard to fit in a single 1400×1200 render: top row of 4 KPI single-stats (signing rate, Rekor anchoring rate, receipt-write throughput, error rate), 2-3 rows of histograms below. Keeping it tight at design time means writeup figures don't require scrolling and operators see operational state at a glance. The existing `MeshQu API - Local` dashboard (31 panels, ~2400px) is great for operational debugging but too sprawling for a writeup figure.

### Two render styles

**Full dashboard** via `/render/d/<uid>`. One image, all panels. Used for the systematic baseline captures (run start, checkpoint, run end). File size ~150-500KB depending on panel count.

**Single panel** via `/render/d-solo/<uid>?panelId=N`. One image, one panel. Used for anomaly captures or pre-publication figure curation when calling out a specific panel ("the signing-latency p99 histogram during the run shows the long tail"). File size ~50-150KB; sharper crop suitable for inline writeup figures.

### Renderer version gotcha

`grafana/grafana-image-renderer:latest` resolves to v5.0.0, which introduced PDF as a possible output. When Grafana sends `encoding=` (empty) in its render-API call, v5 defaults to PDF — but Grafana sets the response `Content-Type: image/png` regardless, masking the issue until you try to open the file.

Two stable resolutions:

- **Pin the renderer to v3.12.5** (`grafana/grafana-image-renderer:3.12.5`) in `monitoring/docker-compose.observability.yml`. v3.x defaults to PNG without the encoding param. No per-call workaround.
- **Pass `encoding=png` explicitly** in every render call. This README's default-params table assumes this approach; the harness honours it.

The build-phase decision for this is tracked as `OBS-204` in the monorepo's `.harness/multi-tenant-observability/` harness. The README's default of `encoding=png` works in both scenarios.

## File-size discipline

PNG files at typical Grafana resolution are 100-300 KB each (single dashboard at 1400×1200; larger if you render the 31-panel API dashboard at 2400px). A run produces dozens; the full directory might be 5-15 MB. That's comfortable in git.

If a capture is much larger (multi-MB) it's probably a full-page browser screenshot rather than a render-API capture — verify the harness is using the `/render` endpoint, not headless-browser-screenshot tools.

## Build-phase prerequisites

Three things must be in place before the harness can drive automated capture:

1. **The image renderer is running and reachable from the harness's host network.** The `OBS-203` task added the renderer sidecar to `monitoring/docker-compose.observability.yml`; staging Grafana needs equivalent setup before screenshots from the staging run work.
2. **The experiment-tenant dashboard exists.** Built by `OBS-201`; mirrored to `dashboards/` by `OBS-206`. The harness reads the dashboard UID from a known config location.
3. **The harness implementation calls the render API at the cadence above and writes PNG files with the canonical filename pattern.** Tracked as `OBS-205`.

If any of these aren't ready at run time, the harness falls back to logging the gap to `audit/anomalies.jsonl` and continues — the researcher captures manually at the same cadence.

Captures must be reproducible from the dashboard JSON (committed in `dashboards/`) + the Prometheus retention window. Screenshots are supporting evidence, not the operational record itself — the audit JSONL files and the receipt corpus carry the load-bearing claims.
