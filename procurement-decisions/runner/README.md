# Runner — Harness Execution Capture

> Python harness that drives the procurement-decisions experiment runs and
> emits the machine-readable evidence the writeup depends on.

## What this is

The runner is the execution-capture layer documented in the planning docs
(`planning/experiment_design.md`) and the audit / screenshots / dashboards
READMEs under `results/`. It is what makes the "automation is the primary
mode" discipline (see `results/observability/screenshots/README.md`) true
in practice — the operator launches it and stays off the keyboard except
for notebook entries.

Initial scope (this commit):

| Capability | Spec | Task |
|---|---|---|
| Automated Grafana screenshot capture at run start, checkpoints, run end, and anomaly triggers | `results/observability/screenshots/README.md` "How automated captures actually work" | OBS-205 |
| Automated dashboard JSON mirror + SHA256 drift detection at run start | `results/observability/dashboards/README.md` | OBS-206 |
| Append-only audit JSONL writers for `decision_traces.jsonl`, `anomalies.jsonl`, `checkpoints.jsonl` | `results/audit/README.md` schemas | (supporting) |

The Inspect-AI eval integration, OCDS substrate adapter, and receipt
production loop are not yet implemented — they layer on top of the
lifecycle and audit hooks this commit lands.

## Language and runtime

Python 3.11+. Chosen because the evaluation pipeline is built on
[Inspect AI](https://inspect.ai-safety-institute.org.uk/) — a Python
framework. Keeping the runner in the same language avoids a cross-language
process boundary at the point where the eval loop integrates.

Dependencies are pinned in `requirements.txt`. Standard-library modules
cover most of the surface; only `requests` is third-party.

## Layout

```
runner/
├── README.md                  (this file)
├── requirements.txt           (pinned third-party deps)
├── pyproject.toml             (pytest config + package metadata)
├── meshqu_runner/
│   ├── config.py              RunnerConfig — loads from env or kwargs
│   ├── audit.py               Append-only JSONL writers + AnomalyEvent dataclass
│   ├── screenshots.py         OBS-205 — render call, height calc, filename, failure logging
│   ├── dashboard_mirror.py    OBS-206 — source-of-truth write + SHA256 drift check
│   ├── runner.py              RunController — lifecycle (run_start / checkpoint / anomaly / run_end)
│   └── cli.py                 python -m meshqu_runner.cli <subcommand>
├── scripts/
│   └── smoke.sh               Local smoke against running observability stack
└── tests/                     pytest suite
```

## Quick start

```bash
cd procurement-decisions/runner
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# OBS-206 standalone: write the mirror + verify against live Grafana
python -m meshqu_runner.cli mirror

# OBS-205 standalone: fire a single capture event
python -m meshqu_runner.cli capture --phase dry-run --event manual-test

# Smoke test the full lifecycle (run start, 5 checkpoints, run end)
python -m meshqu_runner.cli smoke
```

## Environment variables

The CLI reads config from env with sensible local-stack defaults:

| Env var | Default | Notes |
|---|---|---|
| `MESHQU_RUNNER_GRAFANA_URL` | `http://localhost:3101` | Local observability stack |
| `MESHQU_RUNNER_GRAFANA_USER` | `admin` | Basic-auth user |
| `MESHQU_RUNNER_GRAFANA_PASSWORD` | `admin` | Basic-auth password |
| `MESHQU_RUNNER_DASHBOARD_UID` | `experiment-tenant-observability` | OBS-201 dashboard |
| `MESHQU_RUNNER_TENANT` | `experiment-procurement` | `var-tenant` parameter on render calls |
| `MESHQU_RUNNER_MONOREPO_DASHBOARD_PATH` | (unset) | If set, source-of-truth for OBS-206 mirror; if unset, runner reads the committed mirror and compares it against live Grafana. |
| `MESHQU_RUNNER_RESULTS_DIR` | `<repo-root>/procurement-decisions/results` | Parent of `observability/` and `audit/`. |

## Renderer pin

The render-URL pattern this runner emits matches the conventions in the
screenshots README. The renderer is pinned to v3.12.5 in the monorepo's
`monitoring/docker-compose.observability.yml` (OBS-204), which defaults
to PNG natively — `encoding=png` is **not** included in the default
params here, matching the pin's intent. If the pin ever moves forward
to v5.x, both the screenshots README and this runner's `screenshots.py`
need updating in lockstep.

## Tests

```bash
pytest -q
```

Tests cover URL construction, filename generation, height calculation,
SHA256 comparison logic, and the anomaly-logging path. Anything that
touches the network is exercised via the live local stack rather than
mocked — the value of these tests is "the runner actually talks to
Grafana correctly", which mocks can't verify.
