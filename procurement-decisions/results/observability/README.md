# Observability — Dashboards and Screenshots

> Grafana dashboard JSON (canonical source, version-controlled) plus
> screenshots captured during the dry run and full run.
> Supports writeup Appendix B.

## What lives here

```
observability/
├── README.md                    ← this file
├── dashboards/
│   ├── README.md                ← mirror discipline; JSON sourced from monorepo
│   └── <dashboard>.json         ← exported Grafana dashboard JSON
└── screenshots/
    ├── README.md                ← naming, cadence, curation
    └── <timestamped>.png        ← Grafana screenshots from the runs
```

## Why both dashboards and screenshots

**Dashboards (JSON).** Committing the dashboard JSON means a reader of the artefact can see exactly what was monitored — panel by panel, query by query, threshold by threshold. The screenshots show what the dashboard showed during the run; the JSON shows what the dashboard would show against any other data. The combination supports the writeup's product-proof claim: "operational observability was real, not aspirational."

**Screenshots (PNG).** Captured at specific moments during the dry run and full run. Curated post-run into the small set that supports the writeup. Living evidence of "this is what we saw at the time" — pre-empts the obvious skeptical question "how do we know the run actually behaved like this?"

## Dashboard JSON discipline

See [`dashboards/README.md`](dashboards/README.md). One-line summary: dashboard JSON is sourced from the monorepo's `monitoring/grafana/dashboards/` directory and mirrored here at build-phase time. The monorepo is the canonical source; the public-repo mirror is for research-piece reproducibility.

## Screenshot discipline

See [`screenshots/README.md`](screenshots/README.md). One-line summary: filename pattern `YYYY-MM-DDTHH-MM_<dashboard-slug>_<event>.png`. Captured automatically at run start, run end, and each checkpoint by the harness; captured manually by the researcher at anomaly investigation moments.

## Build-phase prerequisites

The dashboards being mirrored here depend on the multi-tenant-observability harness in the monorepo completing (specifically `OBS-201` builds the experiment-tenant dashboard; `OBS-202` mirrors it to this directory). The screenshot capture depends on the harness's execution-capture path having access to Grafana's screenshot API (or equivalent — to be specified at harness implementation time).

If the multi-tenant-observability work slips, the experiment can fall back to using the existing platform dashboards (`MeshQu API - Local`, `Policy Evaluation Performance`) filtered by `env: "staging"` rather than by tenant. This fallback is documented in `experiment_design.md` substrate-honesty subsection.
