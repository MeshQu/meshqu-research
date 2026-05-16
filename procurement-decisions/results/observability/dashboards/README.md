# Dashboards — Mirrored from Monorepo

> Grafana dashboard JSON for the experiment-tenant observability surface.
> Canonical source lives in the monorepo; this directory is the
> public-repo mirror.

## What lives here

Exported Grafana dashboard JSON files. One per dashboard:

- `experiment-tenant-observability.json` — combined dashboard with signing latency, Rekor anchoring, receipt-write throughput, Fastify error-rate panels. Filterable by `tenant` Grafana variable (default value: `experiment-procurement`). Produced by multi-tenant-observability harness task `OBS-201`.
- (Future: additional dashboards as the run surfaces specific debugging needs.)

## Mirror discipline

The monorepo `monitoring/grafana/dashboards/experiment-tenant-observability.json` is the canonical source. This directory is the public-repo mirror, refreshed when the monorepo's dashboard JSON changes.

The mirror happens at three points:

1. **Initial commit** — when the multi-tenant-observability harness task `OBS-202` runs, it copies the dashboard JSON from the monorepo to this directory. Single commit.
2. **At run start** — the harness re-mirrors at run start to ensure the committed dashboard JSON matches the live Grafana state at the moment screenshots are captured.
3. **At any deliberate dashboard change** — if the dashboard evolves during build phase (e.g. adding a panel for an anomaly type that surfaced during dry run), the change lands as a monorepo PR followed by a mirror commit to this directory.

**Discipline rules:**

- Don't edit dashboard JSON in this directory directly. Edits land in the monorepo first (against `monitoring/grafana/dashboards/`); the mirror to this directory comes after.
- When mirroring, copy the entire file verbatim. Don't reformat, don't strip metadata, don't selectively include panels. The file in this directory should diff cleanly against the monorepo's version.
- The mirror commit message references the source commit SHA from the monorepo: e.g. "mirror experiment-tenant-observability.json from monorepo@<sha>".

## Why mirror at all

The monorepo is private — readers of the public research artefact can't see it. The dashboard JSON in this directory is what makes the writeup's product-proof claim auditable from outside MeshQu: a reader can inspect the panels, the queries, the bucket choices, without trusting any prose claim about "we monitored signing latency."

For internal MeshQu development, the monorepo version remains canonical. The mirror is a research-piece artefact.

## How to verify the mirror is fresh

```bash
# From the monorepo
shasum monitoring/grafana/dashboards/experiment-tenant-observability.json

# From the public repo
shasum procurement-decisions/results/observability/dashboards/experiment-tenant-observability.json
```

The two checksums should match. If they don't, the public mirror is stale — refresh by `cp`'ing the monorepo version, committing, and pushing.

The harness's run-start mirror step should make this verification automatic, but the manual check is a sanity check before screenshots get curated for the writeup.
