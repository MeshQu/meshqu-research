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

## Capture cadence

**Automatic captures (by the harness):**

- Run start — establishes the baseline state at the moment execution begins.
- Each checkpoint — typically every 10 records during the full run, every 2 records during the dry run.
- Run end — final state at completion (or at the point of stop if interrupted).

**Manual captures (by the researcher):**

- Anomaly investigation moments — when an `anomalies.jsonl` event lands and the researcher wants to capture the dashboard state at that moment for later analysis. Filename includes `_anomaly-<category>_record-<index>` to anchor against the audit entry.
- Pre-publication curation — the final set selected for Appendix B may include captures specifically chosen for the writeup (e.g. "this is the latency histogram showing the long tail on direct-award signing").

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

## Build-phase prerequisites

The capture cadence above assumes the harness has access to Grafana's image renderer (or equivalent — `https://grafana.com/grafana/plugins/grafana-image-renderer/`). The harness implementation needs this configured at run start. If the image renderer isn't available, fall back to manual captures at the same cadence and document the gap as a build-phase note.

Captures must be reproducible from the dashboard JSON + the Prometheus retention window. Don't rely on captures alone as the operational evidence — they're supporting material for the JSON-and-metrics underneath.
