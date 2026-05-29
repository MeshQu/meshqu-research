#!/usr/bin/env python3
"""E3-011 / E3-013 — Dry-run + Phase-2 driver.

A single driver that runs every E3 arm at one of two scales:

  - ``--scale dry-run``   (default, the E3-011 contract): 30 main-arm
                          OCIDs + 10 diagnostic-arm OCIDs → 140 receipts.
  - ``--scale phase-2``   (E3-013): the full corpus → 1,332 receipts.
                          283 main-arm records × 4 main arms +
                          100 diagnostic-arm OCIDs × 2 diagnostic arms.

Structurally a scaled-up ``smoke_e3.py``. The live-mode wiring helpers
(``_build_live_primary_agent`` / ``_build_live_claude_agent`` /
``_build_live_meshqu_client``) are imported from ``smoke_e3`` rather
than duplicated, so the live-construction contracts PR #96 + #97 wrote
are honoured byte-identically. Only the matrix scale, the per-record
progress UX, and the summary-emission specifics differ.

## The matrices

### ``--scale dry-run`` (140 receipts; default)

For the first **30 OCIDs** of ``planning/diagnostic_subset.json``
(positions 0..29), the driver dispatches:

  - ``arm_a``             → 30 receipts (one per OCID)
  - ``arm_b``             → 30 receipts
  - ``arm_c``             → 30 receipts
  - ``l4_without_nudge``  → 30 receipts

For the first **10 OCIDs** (positions 0..9):

  - ``diagnostic_primary`` → 10 receipts
  - ``diagnostic_claude``  → 10 receipts

Total: **140 receipts**. (4 main arms × 30) + (2 diag arms × 10) = 140.

### ``--scale phase-2`` (1,332 receipts)

Main arms iterate the **full 283-record E1 frozen corpus** sourced from
``substrate_cache.load_cached_records(repo_dir)`` — NOT the locked
diagnostic subset. The diagnostic-subset filter is dropped for main
arms.

  - ``arm_a``             → 283 receipts
  - ``arm_b``             → 283 receipts
  - ``arm_c``             → 283 receipts
  - ``l4_without_nudge``  → 283 receipts

Diagnostic arms iterate the **full 100-OCID locked subset** (positions
0..99 of ``planning/diagnostic_subset.json``).

  - ``diagnostic_primary`` → 100 receipts
  - ``diagnostic_claude``  → 100 receipts

Total: **1,332 receipts** = (4 × 283) + (2 × 100).

## Modes

  --dry           — StubAgent + StubMeshQuClient. Hermetic; no API calls.
                    The mock-test path exercises this end-to-end so the
                    live run is small-surface-area when Sam fires it.

  (no --dry)      — LIVE OpenAI + LIVE Anthropic + LIVE MeshQu client.
                    Requires every env var listed under
                    ``REQUIRED_LIVE_ENV_VARS`` (inherited from
                    ``smoke_e3``) to be populated.

## OBS-205 / OBS-206 observability capture

The driver mirrors E2's ``phase_2_live.py`` pattern: a ``RunController``
is constructed around the arm loop so the locked Grafana dashboard is
mirrored + captured at run-start / run-end / on-error. Artefacts land
under ``<run_dir>/observability/`` (screenshots/ + audit/ + dashboards
mirror) so curating for the writeup is a single ``cp -r <run_dir>/``.

Gating behaviour:

  - ``--scale phase-2``:    capture ON by default (writeup-anchor run).
  - ``--scale dry-run``:    capture OFF by default (iterable validation).
  - ``--no-observability``: hard opt-out, even in phase-2 mode.
  - ``--observability``:    opt-in for dry-run mode (parity-testing).

Required env vars when capture is enabled:

  - ``MESHQU_RUNNER_GRAFANA_URL``       (e.g. https://grafana.staging.…)
  - ``MESHQU_RUNNER_GRAFANA_PASSWORD``  (renderer-allowed password)

Optional (defaults inherited from ``RunnerConfig.from_env``):

  - ``MESHQU_RUNNER_GRAFANA_USER``      (default: admin)
  - ``MESHQU_RUNNER_DASHBOARD_UID``     (default: experiment-tenant-observability)
  - ``MESHQU_RUNNER_TENANT``            (default: experiment-procurement)

Precondition-vs-runtime contract (different failure policies):

  - **Precondition (missing required env)**: under ``--scale phase-2``,
    missing ``MESHQU_RUNNER_GRAFANA_*`` raises ``SystemExit`` at
    run-start. Phase-2 receipts are signed under the experiment
    kid; a "successful" Phase-2 that silently dropped captures
    would be the structural twin of the record-composition bug
    (cryptographic success masking a methodological drop). Fail
    at the gate. ``--no-observability`` is the documented opt-out
    if the operator knows the gap and accepts it.

  - **Precondition under ``--scale dry-run --observability``** (rare
    opt-in for parity testing): missing env soft-fails (WARN + skip
    capture). Dry-run is iterable validation, not the writeup-anchor
    run.

  - **Runtime (drift, unreachable Grafana)**: under both scales, a
    runtime Grafana issue mid-run logs a WARN and disables capture
    for the remainder. Receipts are NEVER blocked on a runtime
    Grafana issue — they are the load-bearing artefact; captures
    are writeup-anchors. A Grafana outage at minute 47 of a 90-minute
    Phase 2 must not lose the receipts that already landed.

## Required environment variables (live mode only)

Same as the smoke driver — see ``smoke_e3.REQUIRED_LIVE_ENV_VARS``:

  - ``OPENAI_API_KEY``
  - ``ANTHROPIC_API_KEY``
  - ``MESHQU_API_URL``
  - ``MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID``
  - ``MESHQU_EXPERIMENT_PROCUREMENT_API_KEY``

The driver refuses to start live mode without all five.

## Rate-limit / pacing

Default ``INTER_REQUEST_PAUSE_SECONDS_LIVE = 0.5`` (inherited from
``smoke_e3``). For 140 receipts that's ~70s of pure-pause across the
run — well below OpenAI tier-1's 500 RPM cap (140 calls / 70s = 2 RPS)
and well below Anthropic's request rate ceilings on the experiment
account. The driver does NOT switch to a per-provider RPM budget — the
0.5s gap is enough headroom that a transient 429 cannot cascade into a
sustained one. ``--inter-request-pause-seconds`` overrides if the live
run surfaces a tighter limit; Sam can dial it up without a code edit.

## Output

Writes the run dir at ``<results>/runs/<run-id>/``. The run-id default
is scale-keyed: ``dry-run-<UTC>-Z`` for ``--scale dry-run`` and
``phase-2-<UTC>-Z`` for ``--scale phase-2``. The summary filenames are
likewise scale-keyed so a paste-back artefact never lies about its
provenance:

  - ``manifests/<arm_name>.manifest.json`` — per-arm run manifest
                                              (NOT scale-keyed; the
                                              manifest is the same kind
                                              of artefact either way)
  - ``<arm_name>/<decision_id>.bundle.json`` — one bundle per receipt
  - ``dry-run-summary.md`` / ``phase-2-summary.md`` — per-arm receipt
                                              count, latency p50/p95,
                                              total tokens, $ cost,
                                              accuracy + extrapolation
                                              tables (per scale; see
                                              "Summary accuracy tables"
                                              below)
  - ``dry-run-summary.json`` / ``phase-2-summary.json`` — same data,
                                              machine-readable

## Summary accuracy tables

``--scale dry-run`` emits:
  - a smoke → dry-run accuracy table (±15% band); and
  - a dry-run → Phase-2 extrapolation table (forecast).

``--scale phase-2`` emits:
  - a dry-run → Phase-2 accuracy table (if a dry-run baseline is pinned
    in ``DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE`` — "n/a (no
    baseline)" rows otherwise); and
  - the final Phase-2 per-arm totals (no further extrapolation).

## Cost rate constants

The summary computes $ cost from observed prompt-tokens using the
PER_1K_TOKEN_USD rates documented below. The numbers are **current
public list prices** as of 2026-05-28 for the locked model pins; treat
the projection as informational, not authoritative — actual billing
on the experiment account may differ (caching discounts, tier
multipliers).

## Receipt-orphan recovery

The dry-run does NOT auto-run ``recover_orphans`` post-flight; it's
left to the operator. The module lives at
``meshqu_runner/recover_orphans.py`` (with a thin shim at
``scripts/recover_orphans.py`` so the CLI form documented in
``procurement-context-disambiguation/planning/build_packages/e3-011-dry-run.md``
§4 works). If the dry-run emits a partial manifest (any unrecoverable
error during dispatch), invoke it post-flight:

    python3 scripts/recover_orphans.py results/runs/dry-run-<…>-Z/

## Live-run invocations (Sam's shell)

Dry-run (E3-011 — already shipped and re-runnable):

    set -a && source procurement-context-disambiguation/runner/.env.live && set +a
    cd procurement-context-disambiguation/runner
    python3 scripts/dry_run_e3.py --scale dry-run     # or just no flag

Expected: 140 receipts under ``results/runs/dry-run-<timestamp>-Z/``
with no errors. Wall-clock: ~15-20 minutes at the default pacing.
Verify next: ``python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/``.

Phase-2 (E3-013 — the full corpus, 1,332 receipts):

    set -a && source procurement-context-disambiguation/runner/.env.live && set +a
    cd procurement-context-disambiguation/runner
    python3 scripts/dry_run_e3.py --scale phase-2

Expected: 1,332 receipts under ``results/runs/phase-2-<timestamp>-Z/``
with no errors. Wall-clock at 0.50s pacing: ~90 minutes of agent time
(per the dry-run-derived projection). Verify next:
``python3 scripts/verify_dry_run_e3.py results/runs/phase-2-<timestamp>-Z/ --scale phase-2``.

## Filename caveat

The script is still named ``dry_run_e3.py`` even though ``--scale phase-2``
makes it a Phase-2 driver too. The rename was deliberately deferred to
a docs-cleanup batch — chasing imports across tests + docs + the
decision_log to flip a name in one PR was deemed not worth the churn
right at the Phase-2 readiness boundary. See the PR body's "Decisions
recorded" section.

## What this script does NOT do

- It does NOT make any live API call when ``--dry`` is passed.
- It does NOT verify receipts itself — that's ``verify_dry_run_e3.py``.
- For ``--scale dry-run``: it does NOT regenerate the locked subset;
  reads positions 0..29 (main arms) and 0..9 (diagnostic arms) of the
  committed ``planning/diagnostic_subset.json``.
- For ``--scale phase-2``: main arms iterate the full E1 frozen corpus
  via ``substrate_cache.load_cached_records``; diagnostic arms read
  positions 0..99 of ``planning/diagnostic_subset.json``.
- It does NOT modify the live-mode construction helpers in
  ``smoke_e3.py``. Those contracts are inherited verbatim.
- It does NOT modify ``smoke_e3.py`` — that's its own driver.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Path bootstrap — let the script run from any cwd via `python scripts/...`
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from meshqu_runner.arms import ARM_PROFILES, PREREG_TAG  # noqa: E402
from meshqu_runner.arms.diagnostic import (  # noqa: E402
    DEFAULT_POLICY_SNAPSHOT_PATH,
)
from meshqu_runner.config import RunnerConfig  # noqa: E402
from meshqu_runner.diagnostic.permute_policy import (  # noqa: E402
    LOCKED_PERMUTATION_SEED,
)
from meshqu_runner.diagnostic.scaled import (  # noqa: E402
    load_diagnostic_subset,
)
from meshqu_runner.multi_pass import (  # noqa: E402
    PassOutcome,
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)
from meshqu_runner.runner import RunController, RunPhase  # noqa: E402

# Reuse smoke_e3's live-mode construction helpers + env contract. The
# contracts in smoke_e3 are frozen by PR #96 + PR #97; the dry-run
# inherits them rather than duplicating to avoid drift.
import smoke_e3  # noqa: E402
from smoke_e3 import (  # noqa: E402
    REQUIRED_LIVE_ENV_VARS,
    _build_live_claude_agent,
    _build_live_meshqu_client,
    _build_live_primary_agent,
    _check_env,
    _load_precedent_archive_or_empty,
    _snapshot_manifest,
)


# ---------------------------------------------------------------------------
# The matrix — locked in code per scale, mirrored verbatim in the PR body.
# ---------------------------------------------------------------------------

SCALE_DRY_RUN = "dry-run"
SCALE_PHASE_2 = "phase-2"
SUPPORTED_SCALES: tuple[str, ...] = (SCALE_DRY_RUN, SCALE_PHASE_2)
"""The two operating scales this driver supports.

``dry-run`` (E3-011 default) preserves the 140-receipt mid-scale matrix.
``phase-2`` (E3-013) fires the full 1,332-receipt corpus.
"""

DRY_RUN_MAIN_OCID_COUNT = 30
"""Number of OCIDs the four main arms run against in ``--scale dry-run``
(positions 0..29 of the locked diagnostic subset)."""

DRY_RUN_DIAGNOSTIC_OCID_COUNT = 10
"""Number of OCIDs the two diagnostic arms run against in
``--scale dry-run`` (positions 0..9)."""

MAIN_ARMS: tuple[str, ...] = ("arm_a", "arm_b", "arm_c", "l4_without_nudge")
"""The four main arms that run against every main-arm OCID."""

DIAGNOSTIC_ARMS: tuple[str, ...] = ("diagnostic_primary", "diagnostic_claude")
"""The two diagnostic arms."""

# Per-scale matrix counts — the assertion targets the driver uses in
# both the runtime summary and the test surface.
RECORDS_PER_MAIN_ARM_BY_SCALE: dict[str, int] = {
    SCALE_DRY_RUN: DRY_RUN_MAIN_OCID_COUNT,
    SCALE_PHASE_2: 283,  # smoke_e3.FULL_RUN_RECEIPTS_PER_MAIN_ARM
}
RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE: dict[str, int] = {
    SCALE_DRY_RUN: DRY_RUN_DIAGNOSTIC_OCID_COUNT,
    SCALE_PHASE_2: 100,  # smoke_e3.FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
}


def expected_total_receipts(scale: str) -> int:
    """Per-scale receipt-count assertion target.

    Returns 140 for ``dry-run`` (30×4 + 10×2) and 1,332 for ``phase-2``
    (283×4 + 100×2)."""
    return (
        RECORDS_PER_MAIN_ARM_BY_SCALE[scale] * len(MAIN_ARMS)
        + RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE[scale] * len(DIAGNOSTIC_ARMS)
    )


# Back-compat alias: existing test_dry_run_e3 + verify_dry_run_e3 read
# ``EXPECTED_TOTAL_RECEIPTS``. Keep it at the dry-run value to avoid
# breaking those call sites; the phase-2 path uses
# ``expected_total_receipts(SCALE_PHASE_2)``.
EXPECTED_TOTAL_RECEIPTS = expected_total_receipts(SCALE_DRY_RUN)
"""140 — the dry-run assertion target. Phase-2 uses
``expected_total_receipts(SCALE_PHASE_2)`` (= 1,332) instead."""


# ---------------------------------------------------------------------------
# Cost-rate constants — current public list prices as of 2026-05-28.
#
# Used to compute $ cost from observed prompt-tokens. Informational
# only; the dry-run is a sanity-check on the smoke extrapolation, not
# a billing audit. Caching discounts + tier multipliers on the
# experiment account are not modelled. The PR body documents the
# constants so any future operator can sanity-check them against the
# provider's pricing page before relying on the projected total.
# ---------------------------------------------------------------------------

# GPT-5.4 (gpt-5.4-2026-03-05) — primary model for arms a/b/c/l4_without_nudge/diagnostic_primary
GPT_54_USD_PER_1K_PROMPT_TOKENS = 0.0025
GPT_54_USD_PER_1K_COMPLETION_TOKENS = 0.01

# Claude Opus 4.7 — diagnostic_claude arm
CLAUDE_OPUS_47_USD_PER_1K_PROMPT_TOKENS = 0.015
CLAUDE_OPUS_47_USD_PER_1K_COMPLETION_TOKENS = 0.075

# We typically don't see completion-token counts uniformly across both
# adapter paths (the primary OpenAI usage exposes it; the Claude
# adapter exposes input_tokens consistently but output_tokens are
# adapter-specific). For projection purposes assume completion ≈ 25%
# of prompt; mark explicitly in the summary so the operator knows it's
# an envelope, not a measurement.
COMPLETION_TOKEN_RATIO_OF_PROMPT = 0.25

ARM_RATE_TABLE: dict[str, dict[str, float]] = {
    "arm_a": {
        "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
    },
    "arm_b": {
        "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
    },
    "arm_c": {
        "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
    },
    "l4_without_nudge": {
        "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
    },
    "diagnostic_primary": {
        "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
    },
    "diagnostic_claude": {
        "usd_per_1k_prompt": CLAUDE_OPUS_47_USD_PER_1K_PROMPT_TOKENS,
        "usd_per_1k_completion": CLAUDE_OPUS_47_USD_PER_1K_COMPLETION_TOKENS,
    },
}


# ---------------------------------------------------------------------------
# Smoke baseline — observed prompt-tokens-per-record from the post-fix
# smoke run (smoke-20260528T161121-Z). The dry-run summary writes a
# smoke→dry-run accuracy check: if the dry-run's measured prompt-
# tokens/record falls within ±15% of these baseline values, the smoke
# extrapolation is trustworthy and the Phase-2 projection can be
# trusted at the same ratio.
#
# If the dry-run is stub-mode (zero tokens), the accuracy check is
# emitted with an "n/a — stub mode" marker and not interpreted.
# ---------------------------------------------------------------------------

SMOKE_PROMPT_TOKENS_PER_RECORD_BASELINE: dict[str, float] = {
    "arm_a": 1821.0,
    "arm_b": 1439.0,
    "arm_c": 1624.0,
    "l4_without_nudge": 2575.0,
    "diagnostic_primary": 2593.0,
    "diagnostic_claude": 3940.0,
}

# ±15% per the spec §5: within band → smoke extrapolation trustworthy;
# outside band → flag and update Phase 2 projection.
SMOKE_TO_DRY_RUN_ACCURACY_TOLERANCE = 0.15


# ---------------------------------------------------------------------------
# Dry-run baseline — for the dry-run → Phase-2 accuracy check used by
# ``--scale phase-2``. Same shape as ``SMOKE_PROMPT_TOKENS_PER_RECORD_BASELINE``,
# same ±15% band. Pin per-arm mean prompt-tokens here once a trusted
# dry-run is in hand; the summary will then surface the
# dry-run→phase-2 accuracy table for the operator.
#
# Empty by default — the most recent dry-run results aren't committed,
# so the phase-2 accuracy table renders "n/a (no baseline)" rows until
# this dict is populated in a follow-up. The cost-projection forecast
# is already trusted at the dry-run level (per the phase 1 readiness
# report's $25.21 envelope); this table would only catch a regression
# that materialised between dry-run and phase-2, which the band check
# would surface if populated.
# ---------------------------------------------------------------------------

# lifted from dry-run-20260528T164807-Z (the post-fix dry-run;
# readiness-report-cited; commit 9852c07).
DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE: dict[str, float] = {
    "arm_a": 1843.0,
    "arm_b": 1443.2,
    "arm_c": 1626.4,
    "l4_without_nudge": 2577.4,
    "diagnostic_primary": 2599.5,
    "diagnostic_claude": 3943.6,
}
"""Per-arm dry-run mean prompt-tokens per record. Pinned from the
post-fix dry-run ``dry-run-20260528T164807-Z`` (citation comment
above). Consumed by the Phase-2 summary's dry-run → Phase-2 accuracy
table — actual Phase-2 prompt-tokens-per-record per arm are compared
against these baselines, ±15% band per
``DRY_RUN_TO_PHASE_2_ACCURACY_TOLERANCE``. Same gate language as
smoke→dry-run."""

DRY_RUN_TO_PHASE_2_ACCURACY_TOLERANCE = 0.15
"""Same ±15% band as the smoke→dry-run check."""


# ---------------------------------------------------------------------------
# Full-run scale — for the dry-run → Phase 2 extrapolation table.
# Inherits from smoke_e3 so both drivers report the same Phase-2 target.
# ---------------------------------------------------------------------------

FULL_RUN_RECEIPTS_PER_MAIN_ARM = smoke_e3.FULL_RUN_RECEIPTS_PER_MAIN_ARM  # 283
FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM = (
    smoke_e3.FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
)  # 100


# ---------------------------------------------------------------------------
# OBS-205 / OBS-206 observability wiring — gap-fill mirroring E2's
# ``phase_2_live.py``.
#
# Phase-2 runs are the Phase-2 writeup-anchor; the locked dashboard
# captures at run-start / run-end / on-error make the receipts legible
# alongside the operational state Grafana shows. Dry-run mode keeps
# observability OFF by default (preserves the 140-receipt hermetic path
# exactly — no behavioural change to the existing 43 tests).
#
# Soft-fail contract: a missing ``MESHQU_RUNNER_GRAFANA_*`` env var or
# an unreachable Grafana endpoint must NOT halt the run. The receipts
# are the load-bearing artefact; captures are writeup-anchors. Each
# failure logs a WARN to stderr and the run continues. A Grafana outage
# at minute 47 of a 90-minute Phase 2 must not lose the receipts.
# ---------------------------------------------------------------------------

# Grafana env vars the renderer + mirror need. Same names E2's driver
# uses. Soft-checked at run start; missing → WARN + skip capture, not
# raise. RunnerConfig.from_env() supplies defaults for everything not
# set, so the controller still constructs cleanly.
REQUIRED_GRAFANA_ENV_VARS: tuple[str, ...] = (
    "MESHQU_RUNNER_GRAFANA_URL",
    "MESHQU_RUNNER_GRAFANA_PASSWORD",
)


def _check_grafana_env() -> list[str]:
    """Return the list of missing required Grafana env vars. Empty
    list = all present. Soft-fail — the caller emits a WARN and
    continues even on a non-empty result (matches the soft-fail
    contract; see module-level note above)."""
    return [name for name in REQUIRED_GRAFANA_ENV_VARS if not os.environ.get(name)]


def _resolve_observability_enabled(
    *,
    scale: str,
    no_observability: bool,
    observability: bool,
) -> bool:
    """Resolve whether observability capture is on for this run.

    Gating contract:
      - ``--scale phase-2``: ON by default; ``--no-observability`` opts out.
      - ``--scale dry-run``: OFF by default; ``--observability`` opts in.

    ``--no-observability`` wins if both are passed (defensive — argparse
    can't make them mutually exclusive across a single boolean toggle on
    each side without making the on/off semantics confusing)."""
    if no_observability:
        return False
    if observability:
        return True
    return scale == SCALE_PHASE_2


def _build_observability_runner_config(
    *,
    run_dir: Path,
    repo_dir: Path,
) -> RunnerConfig:
    """Construct ``RunnerConfig`` for observability capture. Reads
    Grafana settings from ``MESHQU_RUNNER_*`` env (with the local-stack
    defaults from ``RunnerConfig.from_env``), then routes audit +
    screenshots under the run dir so all artefacts stay co-located.
    Matches the override pattern in ``phase_2_live.py``."""
    base = RunnerConfig.from_env()
    # Default monorepo path: the committed dashboard JSON lives at
    # ``procurement-decisions/results/observability/dashboards/<uid>.json``
    # (the shared mirror) — same as E2. ``RunnerConfig.from_env`` already
    # points ``results_dir`` at that tree by default, so the mirror's
    # ``committed_dashboard_path`` resolves correctly without override.
    return RunnerConfig(
        grafana_url=base.grafana_url,
        grafana_user=base.grafana_user,
        grafana_password=base.grafana_password,
        dashboard_uid=base.dashboard_uid,
        tenant=base.tenant,
        monorepo_dashboard_path=base.monorepo_dashboard_path,
        results_dir=base.results_dir,
        render_timeout_seconds=base.render_timeout_seconds,
        audit_dir_override=run_dir / "observability" / "audit",
        screenshots_dir_override=run_dir / "observability" / "screenshots",
    )


def _build_observability_controller(
    *,
    run_dir: Path,
    repo_dir: Path,
    scale: str,
    run_id: str,
    total_records: int,
) -> "RunController | None":
    """Construct and run-start the observability controller for this run.

    Precondition vs. runtime contract — different failure policies:

    - **Precondition (missing required env)**: under ``--scale phase-2``,
      missing ``MESHQU_RUNNER_GRAFANA_*`` vars raise ``SystemExit`` at
      run-start. Phase-2 receipts are signed under the experiment kid;
      a "successful" Phase-2 that silently drops captures is the
      structural twin of the record-composition bug (cryptographic
      success masking a methodological drop). Fail-loud at the gate is
      the lock-in for this concern. Under ``--scale dry-run
      --observability`` (rare opt-in for parity testing), the same
      condition WARNs and skips — dry-run is iterable, not the
      writeup-anchor run.
    - **Runtime (Grafana outage, drift)**: WARN + skip capture, return
      ``None``, let the run continue. Receipts are load-bearing; a
      Grafana outage at minute 47 of a 90-minute Phase 2 must not lose
      the receipts that already landed.

    Returns the controller on success; ``None`` on any runtime failure.
    The caller drives captures only when the return is non-None.

    Order of operations matches E2's ``phase_2_live.py``:
      1. ``_check_grafana_env`` — precondition gate (fail-loud on
         phase-2, soft on dry-run).
      2. Build ``RunnerConfig`` overriding audit + screenshots to
         ``<run_dir>/observability/``.
      3. ``RunController(...)`` — capture dir gets created here.
      4. ``controller.run_start()`` — mirror + run-start screenshot.
         Wrapped in try/except so a Grafana outage logs WARN + returns
         ``None`` instead of bubbling up.
    """
    missing = _check_grafana_env()
    if missing:
        msg_body = (
            "Grafana env vars not set: "
            + ", ".join(missing)
            + ". Source .env.live with MESHQU_RUNNER_GRAFANA_URL + "
            "…_PASSWORD set."
        )
        if scale == SCALE_PHASE_2:
            # Phase-2 precondition lock-in. Receipts get signed under the
            # experiment kid; if observability captures don't fire on a
            # writeup-anchor run, that's the same shape as the record-
            # composition bug (success with silent methodological drop).
            # Refuse to start rather than emit signed receipts without
            # the methodological evidence the readiness checklist
            # claimed.
            raise SystemExit(
                "FAIL: --scale phase-2 requires Grafana env vars for "
                "OBS-205/206 capture (writeup-anchor parity with E1/E2). "
                + msg_body
                + " To run phase-2 without observability (rare; e.g. "
                "local debugging on a corrupted Grafana endpoint), pass "
                "--no-observability explicitly to opt out."
            )
        # Dry-run with --observability opt-in: soft-fail. The dry-run is
        # iterable validation, not the writeup-anchor run.
        print(
            "WARN: " + msg_body + " OBS-205/206 capture disabled for "
            "this run. Receipts still land normally.",
            file=sys.stderr,
        )
        return None

    runner_config = _build_observability_runner_config(
        run_dir=run_dir, repo_dir=repo_dir
    )

    # Scale → RunPhase. ``--scale phase-2`` uses the "full-run" cadence
    # (capture every 10 records); ``--scale dry-run`` opt-in uses the
    # "dry-run" cadence (every 2 records). The E3 driver currently does
    # NOT thread per-record checkpoints (run_arm's loop doesn't expose a
    # sleep_fn the way multi_pass.run_multi_pass does), so in practice
    # only run-start / run-end / on-error fire. The RunPhase literal
    # still drives the screenshot filename's <run-phase> field.
    controller_run_phase: RunPhase = (
        "full-run" if scale == SCALE_PHASE_2 else "dry-run"
    )

    try:
        controller = RunController(
            config=runner_config,
            run_phase=controller_run_phase,
            run_id=run_id,
            total_records=total_records,
        )
    except Exception as exc:  # noqa: BLE001 — capture is supporting evidence
        print(
            f"WARN: RunController construction failed: {type(exc).__name__}: "
            f"{exc}. OBS-205/206 capture disabled for this run; receipts "
            "still land normally.",
            file=sys.stderr,
        )
        return None

    try:
        mirror_result, start_capture = controller.run_start()
    except Exception as exc:  # noqa: BLE001 — receipts are load-bearing, captures are anchors
        print(
            f"WARN: controller.run_start() failed: {type(exc).__name__}: "
            f"{exc}. OBS-205/206 capture disabled for this run; receipts "
            "still land normally.",
            file=sys.stderr,
        )
        return None

    print(
        f"==> Observability run_start OK. "
        f"mirror sha256={mirror_result.canonical_sha256[:12]}…, "
        f"capture ok={start_capture.ok}"
        + (f" path={start_capture.path.name}" if start_capture.path else "")
    )
    return controller


def _safe_run_end(controller: "RunController | None") -> None:
    """Fire the run-end capture if observability is enabled. Soft-fails
    on any exception (same contract as run-start)."""
    if controller is None:
        return
    try:
        end_capture = controller.run_end()
    except Exception as exc:  # noqa: BLE001 — never fail the run on a final capture
        print(
            f"WARN: controller.run_end() raised {type(exc).__name__}: "
            f"{exc}. Run-end capture missing; receipts still landed.",
            file=sys.stderr,
        )
        return
    print(
        f"==> Observability run_end OK. capture ok={end_capture.ok}"
        + (f" path={end_capture.path.name}" if end_capture.path else "")
    )


def _safe_run_anomaly_capture(
    controller: "RunController | None",
    *,
    category: str,
    summary: str,
    detail: str,
) -> None:
    """Fire an on-error / on-halt capture if observability is enabled.

    Uses ``controller.on_anomaly`` so the failure is recorded in the
    audit log AND a final dashboard PNG lands — preserves the partial
    operational state for the writeup. Soft-fails on any exception."""
    if controller is None:
        return
    try:
        controller.on_anomaly(
            category=category,
            summary=summary,
            detail=detail,
            severity="error",
        )
    except Exception as exc:  # noqa: BLE001 — never fail an already-failing run on a capture
        print(
            f"WARN: controller.on_anomaly({category!r}) raised "
            f"{type(exc).__name__}: {exc}. Anomaly capture missing.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Per-arm accounting
# ---------------------------------------------------------------------------


@dataclass
class ArmAccounting:
    """Per-arm latency + token accounting accumulated as the driver
    walks the receipts. The summary writer renders these into the
    Markdown table + the smoke→dry-run accuracy table + the dry-run→
    Phase-2 extrapolation table."""

    arm_name: str
    record_count: int
    receipts_written: int = 0
    latencies_ms: list[int] = field(default_factory=list)
    prompt_tokens: list[int] = field(default_factory=list)
    """Per-record prompt-token counts (best-effort: ``None`` values get
    treated as 0 for summing — stub mode emits all-zeros)."""
    errors: list[str] = field(default_factory=list)
    ocids: list[str | None] = field(default_factory=list)
    """Per-record OCIDs in dispatch order. Lets the summary writer
    verify aggregate completeness (every locked OCID appears in every
    applicable arm) without re-reading bundles off disk."""

    def add_outcome(self, outcome: PassOutcome) -> None:
        self.receipts_written += 1
        self.latencies_ms.append(outcome.agent.latency_ms or 0)
        pt = outcome.agent.prompt_tokens
        self.prompt_tokens.append(int(pt) if pt is not None else 0)
        self.ocids.append(outcome.ocid)

    def latency_mean(self) -> float | None:
        if not self.latencies_ms:
            return None
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def latency_p50(self) -> float | None:
        return _percentile(self.latencies_ms, 50)

    def latency_p95(self) -> float | None:
        return _percentile(self.latencies_ms, 95)

    def latency_min(self) -> int | None:
        return min(self.latencies_ms) if self.latencies_ms else None

    def latency_max(self) -> int | None:
        return max(self.latencies_ms) if self.latencies_ms else None

    def prompt_tokens_total(self) -> int:
        return sum(self.prompt_tokens)

    def prompt_tokens_mean_per_record(self) -> float:
        if not self.record_count:
            return 0.0
        return self.prompt_tokens_total() / self.record_count


def _percentile(values: list[int], pct: float) -> float | None:
    """Lightweight percentile (no numpy dependency). pct in [0, 100].

    Mirrors ``scripts/cache_summary.py::_percentile`` — same linear
    interpolation between adjacent ranks. Returns ``None`` on empty
    input."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return s[f] + (s[c] - s[f]) * (k - f)


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------


def estimate_arm_cost_usd(
    *,
    arm_name: str,
    prompt_tokens_total: int,
) -> float:
    """Estimate $ cost for an arm from observed prompt-tokens. Models
    completion-tokens as ``COMPLETION_TOKEN_RATIO_OF_PROMPT`` × prompt
    (an envelope; the actual completion token counts vary
    significantly per arm and per record). Returns 0.0 for unknown arms
    (defensive)."""
    rates = ARM_RATE_TABLE.get(arm_name)
    if rates is None:
        return 0.0
    prompt_cost = (prompt_tokens_total / 1000.0) * rates["usd_per_1k_prompt"]
    completion_cost = (
        (prompt_tokens_total * COMPLETION_TOKEN_RATIO_OF_PROMPT) / 1000.0
    ) * rates["usd_per_1k_completion"]
    return prompt_cost + completion_cost


def compute_smoke_accuracy_row(
    *,
    arm_name: str,
    dry_run_mean_tokens: float,
) -> dict[str, Any]:
    """Compute the per-arm smoke→dry-run accuracy check. Returns a row
    with the smoke baseline, the dry-run observed mean, the ratio, and
    a boolean ``within_band`` flag at the ±15% tolerance. Stub-mode
    (zero observed) rows are marked ``within_band=None``."""
    smoke_baseline = SMOKE_PROMPT_TOKENS_PER_RECORD_BASELINE.get(arm_name)
    if smoke_baseline is None or smoke_baseline <= 0.0:
        return {
            "arm": arm_name,
            "smoke_mean": smoke_baseline,
            "dry_run_mean": dry_run_mean_tokens,
            "ratio": None,
            "within_band": None,
            "stub_mode": dry_run_mean_tokens == 0.0,
        }
    if dry_run_mean_tokens <= 0.0:
        # Stub mode — accuracy not interpretable.
        return {
            "arm": arm_name,
            "smoke_mean": smoke_baseline,
            "dry_run_mean": dry_run_mean_tokens,
            "ratio": None,
            "within_band": None,
            "stub_mode": True,
        }
    ratio = dry_run_mean_tokens / smoke_baseline
    within = (
        (1.0 - SMOKE_TO_DRY_RUN_ACCURACY_TOLERANCE)
        <= ratio
        <= (1.0 + SMOKE_TO_DRY_RUN_ACCURACY_TOLERANCE)
    )
    return {
        "arm": arm_name,
        "smoke_mean": smoke_baseline,
        "dry_run_mean": dry_run_mean_tokens,
        "ratio": ratio,
        "within_band": within,
        "stub_mode": False,
    }


def compute_dry_run_accuracy_row(
    *,
    arm_name: str,
    phase_2_mean_tokens: float,
) -> dict[str, Any]:
    """Compute the per-arm dry-run → Phase-2 accuracy check for the
    ``--scale phase-2`` summary.

    Mirrors ``compute_smoke_accuracy_row`` shape so the renderer can
    share its formatting path. The baseline comes from
    ``DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE``; if that dict is
    empty (no dry-run baseline pinned yet) the row is emitted with
    ``within_band=None`` and ``stub_mode=False`` — the renderer
    interprets a missing baseline as "n/a (no baseline)" rather than
    "n/a (stub)"."""
    dry_run_baseline = DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE.get(arm_name)
    if dry_run_baseline is None or dry_run_baseline <= 0.0:
        return {
            "arm": arm_name,
            "dry_run_mean": dry_run_baseline,
            "phase_2_mean": phase_2_mean_tokens,
            "ratio": None,
            "within_band": None,
            "stub_mode": phase_2_mean_tokens == 0.0,
            "no_baseline": True,
        }
    if phase_2_mean_tokens <= 0.0:
        return {
            "arm": arm_name,
            "dry_run_mean": dry_run_baseline,
            "phase_2_mean": phase_2_mean_tokens,
            "ratio": None,
            "within_band": None,
            "stub_mode": True,
            "no_baseline": False,
        }
    ratio = phase_2_mean_tokens / dry_run_baseline
    within = (
        (1.0 - DRY_RUN_TO_PHASE_2_ACCURACY_TOLERANCE)
        <= ratio
        <= (1.0 + DRY_RUN_TO_PHASE_2_ACCURACY_TOLERANCE)
    )
    return {
        "arm": arm_name,
        "dry_run_mean": dry_run_baseline,
        "phase_2_mean": phase_2_mean_tokens,
        "ratio": ratio,
        "within_band": within,
        "stub_mode": False,
        "no_baseline": False,
    }


def build_phase_2_extrapolation_table(
    accountings: dict[str, "ArmAccounting"],
) -> list[dict[str, Any]]:
    """Compute the per-arm dry-run → Phase-2 extrapolation rows.
    Linear projection of observed dry-run mean prompt-tokens × the
    Phase-2 receipt count per arm. Operationally an envelope —
    record-by-record variation on the remaining ~253 main / ~90 diag
    records isn't modelled."""
    rows: list[dict[str, Any]] = []
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None or acc.record_count == 0:
            continue
        mean_tokens = acc.prompt_tokens_mean_per_record()
        if arm_name in DIAGNOSTIC_ARMS:
            full_count = FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
        else:
            full_count = FULL_RUN_RECEIPTS_PER_MAIN_ARM
        full_tokens_proj = int(round(mean_tokens * full_count))
        full_cost_proj = estimate_arm_cost_usd(
            arm_name=arm_name,
            prompt_tokens_total=full_tokens_proj,
        )
        rows.append(
            {
                "arm": arm_name,
                "dry_run_receipts": acc.record_count,
                "dry_run_prompt_tokens_total": acc.prompt_tokens_total(),
                "dry_run_prompt_tokens_mean_per_record": round(mean_tokens, 1),
                "dry_run_usd_cost": round(
                    estimate_arm_cost_usd(
                        arm_name=arm_name,
                        prompt_tokens_total=acc.prompt_tokens_total(),
                    ),
                    4,
                ),
                "full_run_receipts": full_count,
                "full_run_prompt_tokens_projected": full_tokens_proj,
                "full_run_usd_cost_projected": round(full_cost_proj, 2),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Aggregate completeness check
# ---------------------------------------------------------------------------


def assert_aggregate_completeness(
    *,
    main_ocids: list[str],
    diagnostic_ocids: list[str],
    accountings: dict[str, ArmAccounting],
) -> list[str]:
    """Return a list of completeness-violation messages (empty when
    every OCID in the main-arm subset appears in every main-arm
    accounting, and every OCID in the diagnostic-arm subset appears in
    every diagnostic-arm accounting).

    The dry-run-completeness contract: no silent drops. If an arm
    handler softly skipped an OCID (e.g. a non-fatal record-load
    exception), the count would still match the matrix but the OCID
    set wouldn't. This check catches that drift."""
    violations: list[str] = []
    main_set = set(main_ocids)
    diag_set = set(diagnostic_ocids)

    for arm_name in MAIN_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            violations.append(f"arm {arm_name!r}: no accounting (matrix gap)")
            continue
        present = {o for o in acc.ocids if o is not None}
        missing = main_set - present
        if missing:
            violations.append(
                f"arm {arm_name!r}: missing OCIDs from main subset: "
                + ", ".join(sorted(missing))
            )
        extra = present - main_set
        if extra:
            violations.append(
                f"arm {arm_name!r}: unexpected OCIDs not in main subset: "
                + ", ".join(sorted(extra))
            )

    for arm_name in DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            violations.append(f"arm {arm_name!r}: no accounting (matrix gap)")
            continue
        present = {o for o in acc.ocids if o is not None}
        missing = diag_set - present
        if missing:
            violations.append(
                f"arm {arm_name!r}: missing OCIDs from diagnostic subset: "
                + ", ".join(sorted(missing))
            )
        extra = present - diag_set
        if extra:
            violations.append(
                f"arm {arm_name!r}: unexpected OCIDs not in diagnostic subset: "
                + ", ".join(sorted(extra))
            )

    return violations


# ---------------------------------------------------------------------------
# Helpers — pulled from smoke_e3 conceptually, kept inline for clarity.
# ---------------------------------------------------------------------------


def _utc_timestamp_slug() -> str:
    """``YYYYMMDDTHHMMSS-Z``. Stable, sortable. Matches the smoke
    driver's convention."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-Z")


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_records(ocids: Iterable[str]) -> list[dict[str, Any]]:
    """Materialise the records the runner dispatches against —
    delegates to ``smoke_e3._build_records`` so the substrate-cache
    walking logic stays single-sourced (and any future fix to that
    helper flows into the dry-run too)."""
    return smoke_e3._build_records(ocids)


def _records_for_arm(
    arm_name: str,
    main_records: list[dict[str, Any]],
    diagnostic_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Slice the pre-built record set per arm.

    Main arms (``arm_a``, ``arm_b``, ``arm_c``, ``l4_without_nudge``)
    get ``main_records``; diagnostic arms get ``diagnostic_records``.
    The caller constructs both lists per the active scale:

      - ``--scale dry-run``: main_records = positions 0..29 of the
        locked diagnostic subset (30 records); diagnostic_records =
        positions 0..9 (10 records).
      - ``--scale phase-2``: main_records = all 283 records from
        ``substrate_cache.load_cached_records`` (the full E1 frozen
        corpus); diagnostic_records = the full 100-OCID locked subset.
    """
    if arm_name in DIAGNOSTIC_ARMS:
        return diagnostic_records
    return main_records


def _build_main_arm_records_phase_2(repo_dir: Path) -> list[dict[str, Any]]:
    """Materialise the full 283-record main-arm corpus for
    ``--scale phase-2``. Loads every cached record from the E1 frozen
    archive via ``substrate_cache.load_cached_records`` and returns the
    plain dict shape the orchestrator consumes (via ``as_record()``).

    Order is OCID-ascending — the substrate cache itself guarantees
    that. We don't reshuffle.
    """
    # Lazy import — matches the smoke driver's pattern. Keeps --dry-mode
    # imports of stale archive code paths off the critical path.
    from meshqu_runner.substrate_cache import load_cached_records

    cached_records = load_cached_records(repo_dir)
    return [cr.as_record() for cr in cached_records]


# ---------------------------------------------------------------------------
# Summary emission — Markdown + JSON
# ---------------------------------------------------------------------------


def _format_latency_block(acc: ArmAccounting) -> str:
    p50 = acc.latency_p50()
    if p50 is None:
        return "  (no successful calls)"
    p95 = acc.latency_p95()
    return f"  p50={p50:.0f}ms  p95={(p95 or 0.0):.0f}ms"


def _summary_filename_stem(scale: str) -> str:
    """``dry-run-summary`` or ``phase-2-summary`` — the stem the .md/.json
    artefacts share. Centralised so callers never invent a divergent
    name."""
    if scale == SCALE_PHASE_2:
        return "phase-2-summary"
    return "dry-run-summary"


def _summary_h1_title(scale: str, run_id: str) -> str:
    """Scale-keyed H1 title for the summary Markdown."""
    if scale == SCALE_PHASE_2:
        return f"# E3 Phase 2 — `{run_id}`"
    return f"# E3 dry-run — `{run_id}`"


def write_summary(
    *,
    run_dir: Path,
    run_id: str,
    scale: str,
    started_at: str,
    finished_at: str,
    main_ocids: list[str],
    diagnostic_ocids: list[str],
    is_dry: bool,
    accountings: dict[str, ArmAccounting],
    phase_2_extrapolation: list[dict[str, Any]],
    smoke_accuracy: list[dict[str, Any]],
    dry_run_accuracy: list[dict[str, Any]],
    completeness_violations: list[str],
    inter_request_pause_seconds: float,
) -> tuple[Path, Path]:
    """Emit ``<stem>.md`` and ``<stem>.json`` where ``<stem>`` is
    ``dry-run-summary`` (``--scale dry-run``) or ``phase-2-summary``
    (``--scale phase-2``). Returns both paths so the caller can echo
    them.

    ``smoke_accuracy`` / ``phase_2_extrapolation`` are only rendered in
    dry-run mode; ``dry_run_accuracy`` is only rendered in phase-2 mode.
    The JSON payload always carries every list (per-scale absent ones
    are empty) so a downstream consumer can read either summary with
    one schema."""

    expected_total = expected_total_receipts(scale)
    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    md_lines: list[str] = []
    md_lines.append(_summary_h1_title(scale, run_id))
    md_lines.append("")
    md_lines.append(f"- **Started:** {started_at}")
    md_lines.append(f"- **Finished:** {finished_at}")
    md_lines.append(f"- **Scale:** `{scale}`")
    md_lines.append(f"- **Mode:** {'--dry (stubs)' if is_dry else 'live'}")
    md_lines.append(f"- **Pre-registration tag:** `{PREREG_TAG}`")
    md_lines.append(
        f"- **Pacing:** {inter_request_pause_seconds:.2f}s between live calls"
    )
    md_lines.append(
        f"- **Receipts written:** {total_receipts} / {expected_total} expected"
    )
    md_lines.append(f"- **Errors:** {total_errors}")
    md_lines.append("")

    # Matrix section. In dry-run mode we list all 30 main OCIDs inline
    # (preserves the original artefact's contents); in phase-2 mode the
    # 283-line dump is too noisy, so we report counts only and let the
    # operator cross-reference the substrate-cache file if needed.
    if scale == SCALE_PHASE_2:
        md_lines.append("## Phase-2 matrix")
        md_lines.append("")
        md_lines.append(
            f"- **Main-arm records:** {len(main_ocids)} "
            "(full E1 frozen corpus from "
            "`meshqu_runner.substrate_cache.load_cached_records`)"
        )
        md_lines.append(
            f"- **Diagnostic-arm OCIDs (positions 0..{len(diagnostic_ocids) - 1} "
            f"of `planning/diagnostic_subset.json`):** {len(diagnostic_ocids)}"
        )
        md_lines.append(
            f"- **Total receipts target:** {expected_total} "
            f"(4 main arms × {RECORDS_PER_MAIN_ARM_BY_SCALE[scale]} + "
            f"2 diag arms × {RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE[scale]})"
        )
        md_lines.append("")
    else:
        md_lines.append("## Dry-run matrix")
        md_lines.append("")
        md_lines.append(
            f"- **Main-arm OCIDs (positions 0..{DRY_RUN_MAIN_OCID_COUNT - 1} from "
            f"`planning/diagnostic_subset.json`):** {len(main_ocids)}"
        )
        for i, ocid in enumerate(main_ocids):
            md_lines.append(f"  {i}. `{ocid}`")
        md_lines.append("")
        md_lines.append(
            f"- **Diagnostic-arm OCIDs (positions 0..{DRY_RUN_DIAGNOSTIC_OCID_COUNT - 1}):** "
            f"{len(diagnostic_ocids)} (subset of the main-arm OCIDs)"
        )
        md_lines.append("")

    md_lines.append("## Per-arm latency + token + cost")
    md_lines.append("")
    md_lines.append(
        "| Arm | Records | Receipts | p50 latency | p95 latency | Prompt-tok total | $ cost |"
    )
    md_lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            md_lines.append(f"| `{arm_name}` | 0 | 0 | — | — | — | — |")
            continue
        p50 = acc.latency_p50()
        p95 = acc.latency_p95()
        p50_str = f"{p50:.0f}ms" if p50 is not None else "—"
        p95_str = f"{p95:.0f}ms" if p95 is not None else "—"
        cost = estimate_arm_cost_usd(
            arm_name=arm_name, prompt_tokens_total=acc.prompt_tokens_total()
        )
        md_lines.append(
            f"| `{arm_name}` | {acc.record_count} | {acc.receipts_written} | "
            f"{p50_str} | {p95_str} | {acc.prompt_tokens_total()} | ${cost:.4f} |"
        )
    md_lines.append("")
    md_lines.append(
        "Cost is informational only — current public list-price rates + "
        f"completion-tokens estimated at {int(COMPLETION_TOKEN_RATIO_OF_PROMPT * 100)}% "
        "of prompt-tokens (an envelope; the experiment account's actual "
        "billing may differ via tier multipliers and caching discounts)."
    )
    md_lines.append("")

    if scale == SCALE_DRY_RUN:
        # Dry-run mode: smoke→dry-run accuracy (±15%) + dry-run→Phase-2
        # extrapolation forecast.
        md_lines.append("## Smoke → dry-run accuracy (±15% band)")
        md_lines.append("")
        md_lines.append(
            "Per the package spec §5: if observed dry-run mean prompt-tokens "
            f"per record is within ±{int(SMOKE_TO_DRY_RUN_ACCURACY_TOLERANCE * 100)}% "
            "of the smoke baseline, the smoke→Phase-2 extrapolation is "
            "trustworthy. Outside ±15% → update the Phase-2 projection."
        )
        md_lines.append("")
        md_lines.append(
            "| Arm | Smoke mean (tok/rec) | Dry-run mean (tok/rec) | Ratio | Within ±15%? |"
        )
        md_lines.append("|---|---:|---:|---:|:---:|")
        for row in smoke_accuracy:
            ratio = row["ratio"]
            ratio_str = f"{ratio:.3f}" if ratio is not None else "—"
            if row["stub_mode"]:
                within_str = "n/a (stub)"
            elif row["within_band"] is True:
                within_str = "yes"
            elif row["within_band"] is False:
                within_str = "**no**"
            else:
                within_str = "n/a"
            smoke_mean = row["smoke_mean"]
            smoke_str = f"{smoke_mean:.1f}" if smoke_mean is not None else "—"
            md_lines.append(
                f"| `{row['arm']}` | {smoke_str} | "
                f"{row['dry_run_mean']:.1f} | {ratio_str} | {within_str} |"
            )
        md_lines.append("")

        md_lines.append("## Dry-run → Phase 2 extrapolation")
        md_lines.append("")
        md_lines.append(
            "Linear extrapolation of observed dry-run mean prompt-tokens "
            "per record to the full Phase-2 receipt counts "
            f"({FULL_RUN_RECEIPTS_PER_MAIN_ARM} per main arm, "
            f"{FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM} per diagnostic arm). "
            "Stub-mode numbers are zero by design."
        )
        md_lines.append("")
        md_lines.append(
            "| Arm | Dry-run receipts | Dry-run prompt-tok | $ cost | Phase-2 receipts | Phase-2 prompt-tok | Phase-2 $ cost |"
        )
        md_lines.append("|---|---:|---:|---:|---:|---:|---:|")
        total_full_cost = 0.0
        for row in phase_2_extrapolation:
            md_lines.append(
                f"| `{row['arm']}` | {row['dry_run_receipts']} | "
                f"{row['dry_run_prompt_tokens_total']} | "
                f"${row['dry_run_usd_cost']:.4f} | "
                f"{row['full_run_receipts']} | "
                f"{row['full_run_prompt_tokens_projected']} | "
                f"${row['full_run_usd_cost_projected']:.2f} |"
            )
            total_full_cost += row["full_run_usd_cost_projected"]
        md_lines.append(f"| **TOTAL** | | | | | | **${total_full_cost:.2f}** |")
        md_lines.append("")
    else:
        # Phase-2 mode: dry-run→Phase-2 accuracy (±15%; "n/a (no
        # baseline)" until DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE is
        # pinned) + final per-arm Phase-2 totals (no further
        # extrapolation; the receipts are the receipts).
        md_lines.append("## Dry-run → Phase 2 accuracy (±15% band)")
        md_lines.append("")
        if DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE:
            md_lines.append(
                "If observed Phase-2 mean prompt-tokens per record is within "
                f"±{int(DRY_RUN_TO_PHASE_2_ACCURACY_TOLERANCE * 100)}% of the "
                "pinned dry-run baseline, the dry-run-derived cost envelope "
                "($25.21 per the Phase-1 readiness report) held. Outside the "
                "band → record the drift in the Phase-2 writeup."
            )
        else:
            md_lines.append(
                "**No dry-run baseline pinned.** Rows render as "
                "`n/a (no baseline)`. Populate "
                "`DRY_RUN_PROMPT_TOKENS_PER_RECORD_BASELINE` from a trusted "
                "dry-run summary to enable the band check in a follow-up PR."
            )
        md_lines.append("")
        md_lines.append(
            "| Arm | Dry-run mean (tok/rec) | Phase-2 mean (tok/rec) | Ratio | Within ±15%? |"
        )
        md_lines.append("|---|---:|---:|---:|:---:|")
        for row in dry_run_accuracy:
            ratio = row["ratio"]
            ratio_str = f"{ratio:.3f}" if ratio is not None else "—"
            if row.get("no_baseline"):
                within_str = "n/a (no baseline)"
            elif row["stub_mode"]:
                within_str = "n/a (stub)"
            elif row["within_band"] is True:
                within_str = "yes"
            elif row["within_band"] is False:
                within_str = "**no**"
            else:
                within_str = "n/a"
            dry_run_mean = row["dry_run_mean"]
            dry_run_str = (
                f"{dry_run_mean:.1f}" if dry_run_mean is not None else "—"
            )
            md_lines.append(
                f"| `{row['arm']}` | {dry_run_str} | "
                f"{row['phase_2_mean']:.1f} | {ratio_str} | {within_str} |"
            )
        md_lines.append("")

        md_lines.append("## Phase 2 totals")
        md_lines.append("")
        md_lines.append(
            "Final per-arm receipts + observed tokens + observed $ cost for "
            "the full 1,332-receipt Phase-2 corpus. No further extrapolation "
            "— these are the receipts."
        )
        md_lines.append("")
        md_lines.append(
            "| Arm | Receipts | Prompt-tok total | Mean (tok/rec) | $ cost |"
        )
        md_lines.append("|---|---:|---:|---:|---:|")
        total_observed_cost = 0.0
        for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
            acc = accountings.get(arm_name)
            if acc is None:
                md_lines.append(f"| `{arm_name}` | 0 | 0 | — | — |")
                continue
            cost = estimate_arm_cost_usd(
                arm_name=arm_name,
                prompt_tokens_total=acc.prompt_tokens_total(),
            )
            md_lines.append(
                f"| `{arm_name}` | {acc.receipts_written} | "
                f"{acc.prompt_tokens_total()} | "
                f"{acc.prompt_tokens_mean_per_record():.1f} | ${cost:.2f} |"
            )
            total_observed_cost += cost
        md_lines.append(
            f"| **TOTAL** | {total_receipts} | | | **${total_observed_cost:.2f}** |"
        )
        md_lines.append("")

    md_lines.append("## Aggregate completeness")
    md_lines.append("")
    if completeness_violations:
        md_lines.append("**FAIL** — the following completeness violations were observed:")
        md_lines.append("")
        for v in completeness_violations:
            md_lines.append(f"- {v}")
    else:
        md_lines.append(
            "PASS — every main-subset OCID appears in every main arm "
            "(arm_a / arm_b / arm_c / l4_without_nudge); every "
            "diagnostic-subset OCID appears in both diagnostic arms "
            "(diagnostic_primary / diagnostic_claude). No silent drops."
        )
    md_lines.append("")

    any_errors = any(a.errors for a in accountings.values())
    if any_errors:
        md_lines.append("## Errors")
        md_lines.append("")
        for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
            acc = accountings.get(arm_name)
            if acc and acc.errors:
                md_lines.append(f"- **`{arm_name}`** ({len(acc.errors)}):")
                for err in acc.errors:
                    md_lines.append(f"  - {err}")
        md_lines.append("")
    else:
        md_lines.append("## Errors")
        md_lines.append("")
        md_lines.append("(none)")
        md_lines.append("")

    md_lines.append("## Next step")
    md_lines.append("")
    if scale == SCALE_PHASE_2:
        md_lines.append(
            f"    python3 scripts/verify_dry_run_e3.py {run_dir.name}/ --scale phase-2"
        )
    else:
        md_lines.append(
            f"    python3 scripts/verify_dry_run_e3.py {run_dir.name}/"
        )
    md_lines.append("")
    md_lines.append(
        "(run from inside `procurement-context-disambiguation/runner/` "
        "with the run dir resolved relative to `results/runs/`.)"
    )

    stem = _summary_filename_stem(scale)
    md_path = run_dir / f"{stem}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    json_payload = {
        "run_id": run_id,
        "scale": scale,
        "started_at": started_at,
        "finished_at": finished_at,
        "is_dry": is_dry,
        "main_ocids": main_ocids,
        "diagnostic_ocids": diagnostic_ocids,
        "expected_total_receipts": expected_total,
        "total_receipts_written": total_receipts,
        "total_errors": total_errors,
        "prereg_tag": PREREG_TAG,
        "inter_request_pause_seconds": inter_request_pause_seconds,
        "accountings": {
            name: {
                "arm_name": acc.arm_name,
                "record_count": acc.record_count,
                "receipts_written": acc.receipts_written,
                "latencies_ms": list(acc.latencies_ms),
                "prompt_tokens": list(acc.prompt_tokens),
                "ocids": list(acc.ocids),
                "latency_mean_ms": acc.latency_mean(),
                "latency_p50_ms": acc.latency_p50(),
                "latency_p95_ms": acc.latency_p95(),
                "latency_min_ms": acc.latency_min(),
                "latency_max_ms": acc.latency_max(),
                "prompt_tokens_total": acc.prompt_tokens_total(),
                "prompt_tokens_mean_per_record": acc.prompt_tokens_mean_per_record(),
                "estimated_usd_cost": estimate_arm_cost_usd(
                    arm_name=acc.arm_name,
                    prompt_tokens_total=acc.prompt_tokens_total(),
                ),
                "errors": list(acc.errors),
            }
            for name, acc in accountings.items()
        },
        "smoke_to_dry_run_accuracy": smoke_accuracy,
        "phase_2_extrapolation": phase_2_extrapolation,
        "dry_run_to_phase_2_accuracy": dry_run_accuracy,
        "completeness_violations": completeness_violations,
        "cost_rates": {
            "gpt_5_4": {
                "usd_per_1k_prompt": GPT_54_USD_PER_1K_PROMPT_TOKENS,
                "usd_per_1k_completion": GPT_54_USD_PER_1K_COMPLETION_TOKENS,
            },
            "claude_opus_4_7": {
                "usd_per_1k_prompt": CLAUDE_OPUS_47_USD_PER_1K_PROMPT_TOKENS,
                "usd_per_1k_completion": CLAUDE_OPUS_47_USD_PER_1K_COMPLETION_TOKENS,
            },
            "completion_token_ratio_of_prompt": COMPLETION_TOKEN_RATIO_OF_PROMPT,
        },
    }
    json_path = run_dir / f"{stem}.json"
    json_path.write_text(
        json.dumps(json_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return md_path, json_path


# ---------------------------------------------------------------------------
# Per-record progress + arm dispatch
# ---------------------------------------------------------------------------


def _print_tick(
    *,
    arm_name: str,
    n: int,
    total: int,
    outcome: PassOutcome,
) -> None:
    """One progress line per receipt. Format:

        [arm_name] [n/N] ocid=… latency=…ms tokens=…

    The operator monitoring a long live run can spot a stalled arm or a
    runaway latency by eyeball without grepping a JSON file."""
    pt = outcome.agent.prompt_tokens
    pt_str = str(pt) if pt is not None else "—"
    print(
        f"[{arm_name}] [{n}/{total}] ocid={outcome.ocid} "
        f"latency={outcome.agent.latency_ms}ms tokens={pt_str}",
        flush=True,
    )


def _run_phase_for_scale(scale: str) -> str:
    """Map the driver's ``--scale`` to the ``RunPhase`` literal recorded
    in the per-arm RunConfig + manifest.

    ``dry-run`` → ``"dry-run"`` (the existing E3-011 phase).
    ``phase-2`` → ``"full-run"`` (the established literal for the full
                  corpus run; see ``meshqu_runner.run_manifest.RunPhase``).
    """
    if scale == SCALE_PHASE_2:
        return "full-run"
    return "dry-run"


def _run_one_arm(
    *,
    arm_name: str,
    records: list[dict[str, Any]],
    run_id: str,
    run_phase: str,
    run_dir: Path,
    repo_dir: Path,
    is_dry: bool,
    env: dict[str, str] | None,
    archive: dict[str, Any],
    inter_request_pause_seconds: float,
) -> ArmAccounting:
    """Build the per-arm agent + client and call ``run_arm``. Returns
    a populated ``ArmAccounting``. Catches and records exceptions per
    the package-spec partial-run-resilience rule — we record into
    ``acc.errors`` and continue so the summary captures full state
    even on partial failure."""
    profile = ARM_PROFILES[arm_name]
    acc = ArmAccounting(arm_name=arm_name, record_count=len(records))

    if is_dry:
        agent: Any = StubAgent(
            model_id=profile.model_id,
            temperature=(
                profile.model_sampling.get("temperature", 0)
                if profile.model_sampling.get("temperature") is not None
                else 0
            ),
        )
        meshqu_client: Any = StubMeshQuClient()
    else:
        assert env is not None  # _check_env() called by caller
        if arm_name == "diagnostic_claude":
            agent = _build_live_claude_agent()
        else:
            agent = _build_live_primary_agent(env)
        meshqu_client = _build_live_meshqu_client(env)

    policy_permutation_seed = (
        LOCKED_PERMUTATION_SEED if arm_name in DIAGNOSTIC_ARMS else None
    )

    config = RunConfig(
        run_id=run_id,
        run_phase=run_phase,  # "dry-run" or "full-run" per scale
        repo_dir=repo_dir,
        run_dir=run_dir,
        arm_name=arm_name,
        policy_snapshot_path=DEFAULT_POLICY_SNAPSHOT_PATH,
        meshqu_api_url=(env or {}).get("MESHQU_API_URL", "https://api.meshqu.com"),
        meshqu_tenant_label="experiment-procurement",
        inter_request_pause_seconds=inter_request_pause_seconds,
        policy_permutation_seed=policy_permutation_seed,
    )

    handler_kwargs: dict[str, Any] = {
        "policy_snapshot_path": DEFAULT_POLICY_SNAPSHOT_PATH,
        "seed": LOCKED_PERMUTATION_SEED,
    }
    if arm_name in ("arm_a", "arm_b") and archive:
        handler_kwargs["archive"] = archive

    try:
        summary = run_arm(
            config=config,
            records=records,
            agent=agent,
            meshqu_client=meshqu_client,
            handler_kwargs=handler_kwargs,
        )
    except Exception as exc:  # pragma: no cover — exercised by live-run only
        acc.errors.append(f"run_arm raised: {type(exc).__name__}: {exc}")
        return acc

    total = len(summary.outcomes)
    for i, outcome in enumerate(summary.outcomes, start=1):
        acc.add_outcome(outcome)
        _print_tick(arm_name=arm_name, n=i, total=total, outcome=outcome)

    _snapshot_manifest(run_dir, arm_name)

    return acc


def _persist_partial_manifest(
    *,
    run_dir: Path,
    accountings: dict[str, ArmAccounting],
    error_arm: str,
    error_detail: str,
) -> None:
    """Write a partial-run manifest at the run-dir root so the operator
    knows exactly which arms completed before the unrecoverable error.
    The orphan-recovery script (``meshqu_runner.recover_orphans``) can
    stitch missing receipts after fix-up."""
    payload = {
        "partial_run": True,
        "error_arm": error_arm,
        "error_detail": error_detail,
        "completed_arms": [
            {
                "arm_name": acc.arm_name,
                "record_count": acc.record_count,
                "receipts_written": acc.receipts_written,
                "errors": list(acc.errors),
            }
            for acc in accountings.values()
        ],
        "next_step": (
            "Inspect dry-run-summary.md for full state. If any receipts "
            "were recorded remotely but missed local sidecars, run "
            "`python3 scripts/recover_orphans.py <this-run-dir>`."
        ),
    }
    path = run_dir / "partial-run-manifest.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dry_run_e3.py",
        description=(
            "E3 dry-run / Phase-2 driver. Runs every E3 arm at the "
            "configured scale: 140 receipts in --scale dry-run (default), "
            "1,332 receipts in --scale phase-2 (the full E1 corpus)."
        ),
    )
    parser.add_argument(
        "--scale",
        choices=SUPPORTED_SCALES,
        default=SCALE_DRY_RUN,
        help=(
            "Matrix scale. 'dry-run' (default) fires the 140-receipt "
            "mid-scale matrix (30 main-arm OCIDs + 10 diagnostic-arm "
            "OCIDs from the locked subset). 'phase-2' fires the full "
            "1,332-receipt corpus (283 main-arm records from the E1 "
            "frozen archive + 100 diagnostic-arm OCIDs)."
        ),
    )
    parser.add_argument(
        "--dry",
        action="store_true",
        help=(
            "Hermetic mode: StubAgent + StubMeshQuClient. No live API "
            "calls. Used by the PR's mock tests; Sam runs the live "
            "mode (no flag) by hand."
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help=(
            "Where to write results/runs/<run_id>/. Defaults to "
            "<runner>/../results "
            "(i.e. procurement-context-disambiguation/results)."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Override run_id; defaults to '<scale>-<UTC-timestamp>-Z' "
            "(i.e. 'dry-run-…' or 'phase-2-…' per --scale)."
        ),
    )
    parser.add_argument(
        "--inter-request-pause-seconds",
        type=float,
        default=None,
        help=(
            "Pace between live calls. Defaults to "
            f"{smoke_e3.INTER_REQUEST_PAUSE_SECONDS_LIVE}s in live mode "
            "for both scales (140 receipts × 0.5s = ~70s pause across "
            "the dry-run; 1,332 receipts × 0.5s = ~11 minutes pause "
            "across phase-2 — comfortably below OpenAI tier-1's 500 RPM "
            "cap and the experiment-account Anthropic ceilings), 0s in "
            "--dry."
        ),
    )
    # OBS-205 / OBS-206 observability capture gating.
    #
    # Gating contract (see ``_resolve_observability_enabled``):
    #   - ``--scale phase-2``: default ON. The Phase-2 writeup needs
    #     Grafana captures alongside the receipts; that's the whole
    #     reason this wiring exists.
    #   - ``--scale dry-run``: default OFF. The 140-receipt dry-run is
    #     iterable validation; captures would burn GPU and the existing
    #     test suite stays green by construction with no capture by
    #     default.
    #   - ``--no-observability``: hard opt-out (even in phase-2 mode).
    #     Local debugging / cost-free re-runs.
    #   - ``--observability``: opt-in for dry-run mode. Rare; used to
    #     parity-test the wiring against a known-good Grafana before
    #     a real Phase-2 fire.
    parser.add_argument(
        "--observability",
        action="store_true",
        help=(
            "Force OBS-205/206 capture ON. In --scale phase-2 this is "
            "the default; in --scale dry-run this opts in (rare — used "
            "to parity-test the wiring without firing the full corpus)."
        ),
    )
    parser.add_argument(
        "--no-observability",
        action="store_true",
        help=(
            "Force OBS-205/206 capture OFF even in --scale phase-2. "
            "Receipts still land normally. Use for local debugging or "
            "cost-free re-runs."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    scale: str = args.scale
    if scale not in SUPPORTED_SCALES:  # pragma: no cover — argparse pre-filters
        raise SystemExit(
            f"FAIL: unsupported --scale {scale!r}; choose from "
            f"{', '.join(SUPPORTED_SCALES)}."
        )

    is_dry = bool(args.dry)
    env: dict[str, str] | None
    if is_dry:
        env = None
    else:
        env = _check_env()

    expected_total = expected_total_receipts(scale)
    main_count = RECORDS_PER_MAIN_ARM_BY_SCALE[scale]
    diag_count = RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE[scale]
    run_phase = _run_phase_for_scale(scale)

    runner_dir = _RUNNER_DIR
    e3_dir = runner_dir.parent  # procurement-context-disambiguation/
    repo_dir = e3_dir.parent  # repo root

    # Record-set construction is scale-specific.
    #
    # Main arms:
    #   - dry-run: first 30 OCIDs of the locked diagnostic subset.
    #   - phase-2: the full 283-record E1 frozen corpus (via
    #     substrate_cache.load_cached_records). The diagnostic-subset
    #     filter is dropped — main arms see the WHOLE corpus.
    #
    # Diagnostic arms:
    #   - dry-run: first 10 OCIDs of the locked subset.
    #   - phase-2: the full 100-OCID locked subset.
    all_locked_ocids = load_diagnostic_subset()
    if len(all_locked_ocids) < diag_count:
        raise SystemExit(
            f"FAIL: locked diagnostic subset has {len(all_locked_ocids)} OCIDs; "
            f"--scale {scale} requires ≥ {diag_count}. Re-check "
            "planning/diagnostic_subset.json."
        )
    diagnostic_ocids = all_locked_ocids[:diag_count]
    diagnostic_records = _build_records(diagnostic_ocids)

    if scale == SCALE_PHASE_2:
        main_records = _build_main_arm_records_phase_2(repo_dir)
        if len(main_records) != main_count:
            raise SystemExit(
                f"FAIL: --scale phase-2 expected {main_count} main-arm "
                f"records from substrate_cache.load_cached_records; got "
                f"{len(main_records)}. The E1 frozen archive may have "
                "drifted from the 283-record contract."
            )
        main_ocids = [r["ocid"] for r in main_records]
    else:
        if len(all_locked_ocids) < main_count:
            raise SystemExit(
                f"FAIL: locked diagnostic subset has {len(all_locked_ocids)} "
                f"OCIDs; --scale {scale} requires ≥ {main_count}. Re-check "
                "planning/diagnostic_subset.json."
            )
        main_ocids = all_locked_ocids[:main_count]
        main_records = _build_records(main_ocids)

    results_dir = args.results_dir if args.results_dir else e3_dir / "results"
    run_id = args.run_id or f"{scale}-{_utc_timestamp_slug()}"
    run_dir = results_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    inter_request_pause = args.inter_request_pause_seconds
    if inter_request_pause is None:
        inter_request_pause = (
            0.0 if is_dry else smoke_e3.INTER_REQUEST_PAUSE_SECONDS_LIVE
        )

    # Resolve observability gating — per-scale defaults + opt-out / opt-in.
    observability_enabled = _resolve_observability_enabled(
        scale=scale,
        no_observability=bool(args.no_observability),
        observability=bool(args.observability),
    )

    archive = _load_precedent_archive_or_empty()

    print(f"==> Run id: {run_id}")
    print(f"    Scale:          {scale}")
    print(f"    Mode:           {'--dry (stubs)' if is_dry else 'LIVE'}")
    print(f"    Run dir:        {run_dir}")
    if scale == SCALE_PHASE_2:
        print(
            f"    Main records:   {len(main_ocids)} (full E1 frozen corpus)"
        )
        print(
            f"    Diag OCIDs:     {len(diagnostic_ocids)} "
            f"(positions 0..{diag_count - 1} of locked subset)"
        )
    else:
        print(
            f"    Main OCIDs:     {len(main_ocids)} "
            f"(positions 0..{main_count - 1} of locked subset)"
        )
        print(
            f"    Diag OCIDs:     {len(diagnostic_ocids)} "
            f"(positions 0..{diag_count - 1})"
        )
    print(
        f"    Receipts target: {expected_total} "
        f"(4 main arms × {main_count} + 2 diag arms × {diag_count})"
    )
    print(f"    Pacing:         {inter_request_pause:.2f}s between calls")
    if archive:
        print(f"    Frozen archive: {len(archive)} precedents loaded")
    else:
        print("    Frozen archive: NOT loaded (Arm A/B will render no-precedents)")
    print(
        f"    Observability: {'ON (OBS-205/206 capture)' if observability_enabled else 'OFF'}"
    )
    print()

    # OBS-205 / OBS-206 — run-start mirror + capture. Soft-fails on any
    # Grafana issue (missing env, drift, unreachable endpoint) → returns
    # ``None`` + WARN to stderr; subsequent capture sites no-op. Total
    # records for the cadence gate = expected_total (Phase-2: 1,332).
    observability_controller: RunController | None = None
    if observability_enabled:
        observability_controller = _build_observability_controller(
            run_dir=run_dir,
            repo_dir=repo_dir,
            scale=scale,
            run_id=run_id,
            total_records=expected_total,
        )

    started_at = _utc_iso_now()
    t0 = time.monotonic()

    accountings: dict[str, ArmAccounting] = {}
    error_arm: str | None = None
    error_detail: str | None = None

    try:
        # Main arms: every main OCID
        for arm_name in MAIN_ARMS:
            arm_records = _records_for_arm(arm_name, main_records, diagnostic_records)
            print(f"==> {arm_name} — {len(arm_records)} records")
            acc = _run_one_arm(
                arm_name=arm_name,
                records=arm_records,
                run_id=run_id,
                run_phase=run_phase,
                run_dir=run_dir,
                repo_dir=repo_dir,
                is_dry=is_dry,
                env=env,
                archive=archive,
                inter_request_pause_seconds=inter_request_pause,
            )
            accountings[arm_name] = acc
            print(
                f"    receipts={acc.receipts_written}/{acc.record_count}"
                + (f"  errors={len(acc.errors)}" if acc.errors else "")
            )

        # Diagnostic arms: every diag OCID
        for arm_name in DIAGNOSTIC_ARMS:
            arm_records = _records_for_arm(arm_name, main_records, diagnostic_records)
            print(f"==> {arm_name} — {len(arm_records)} records")
            acc = _run_one_arm(
                arm_name=arm_name,
                records=arm_records,
                run_id=run_id,
                run_phase=run_phase,
                run_dir=run_dir,
                repo_dir=repo_dir,
                is_dry=is_dry,
                env=env,
                archive=archive,
                inter_request_pause_seconds=inter_request_pause,
            )
            accountings[arm_name] = acc
            print(
                f"    receipts={acc.receipts_written}/{acc.record_count}"
                + (f"  errors={len(acc.errors)}" if acc.errors else "")
            )
    except KeyboardInterrupt:
        error_arm = "(interrupted)"
        error_detail = "KeyboardInterrupt"
        # OBS-205 — on-halt capture so the partial operational state is
        # visible in the writeup.
        _safe_run_anomaly_capture(
            observability_controller,
            category="run_halted",
            summary="Run interrupted (KeyboardInterrupt)",
            detail=f"completed_arms={list(accountings)}",
        )
    except Exception as exc:  # pragma: no cover — defensive
        # Bubble the arm name from accountings (last one added) if any.
        if accountings:
            error_arm = list(accountings)[-1]
        else:
            error_arm = "(none)"
        error_detail = f"{type(exc).__name__}: {exc}"
        # OBS-205 — on-error capture so the partial operational state is
        # visible in the writeup.
        _safe_run_anomaly_capture(
            observability_controller,
            category="run_errored",
            summary=f"Run errored in arm {error_arm}",
            detail=error_detail,
        )

    finished_at = _utc_iso_now()
    elapsed = time.monotonic() - t0

    completeness_violations = assert_aggregate_completeness(
        main_ocids=main_ocids,
        diagnostic_ocids=diagnostic_ocids,
        accountings=accountings,
    )

    smoke_accuracy: list[dict[str, Any]] = []
    dry_run_accuracy: list[dict[str, Any]] = []
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            continue
        if scale == SCALE_DRY_RUN:
            smoke_accuracy.append(
                compute_smoke_accuracy_row(
                    arm_name=arm_name,
                    dry_run_mean_tokens=acc.prompt_tokens_mean_per_record(),
                )
            )
        else:
            dry_run_accuracy.append(
                compute_dry_run_accuracy_row(
                    arm_name=arm_name,
                    phase_2_mean_tokens=acc.prompt_tokens_mean_per_record(),
                )
            )

    # Forecast extrapolation only meaningful in dry-run mode (phase-2 IS
    # the full run; nothing left to extrapolate to).
    phase_2_extrapolation: list[dict[str, Any]] = []
    if scale == SCALE_DRY_RUN:
        phase_2_extrapolation = build_phase_2_extrapolation_table(accountings)

    md_path, json_path = write_summary(
        run_dir=run_dir,
        run_id=run_id,
        scale=scale,
        started_at=started_at,
        finished_at=finished_at,
        main_ocids=main_ocids,
        diagnostic_ocids=diagnostic_ocids,
        is_dry=is_dry,
        accountings=accountings,
        phase_2_extrapolation=phase_2_extrapolation,
        smoke_accuracy=smoke_accuracy,
        dry_run_accuracy=dry_run_accuracy,
        completeness_violations=completeness_violations,
        inter_request_pause_seconds=inter_request_pause,
    )

    # OBS-205 — run-end capture lands after the summary is written so
    # the dashboard snapshot reflects the end-of-run state inclusive of
    # the final receipts. Only fires on the success path; the
    # error / interrupt paths already fired an on-error capture above.
    if error_arm is None:
        _safe_run_end(observability_controller)

    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    if error_arm is not None:
        _persist_partial_manifest(
            run_dir=run_dir,
            accountings=accountings,
            error_arm=error_arm,
            error_detail=error_detail or "",
        )

    summary_basename = md_path.name
    print()
    print(
        f"==> wrote {total_receipts}/{expected_total} "
        f"receipts in {elapsed:.1f}s"
    )
    print(f"    summary (md):   {md_path}")
    print(f"    summary (json): {json_path}")
    print()
    if completeness_violations:
        print(
            f"WARN: aggregate completeness violations detected — see "
            f"{summary_basename} §'Aggregate completeness'.",
            file=sys.stderr,
        )
    if total_errors:
        print(
            f"WARN: {total_errors} per-arm errors recorded. "
            f"Inspect {summary_basename}.",
            file=sys.stderr,
        )
    if error_arm is not None:
        print(
            f"FAIL: unrecoverable error in arm {error_arm}: {error_detail}. "
            f"Partial manifest at {run_dir / 'partial-run-manifest.json'}",
            file=sys.stderr,
        )
        return 1
    if total_receipts != expected_total:
        print(
            f"WARN: expected {expected_total} receipts, "
            f"wrote {total_receipts}.",
            file=sys.stderr,
        )
        return 1
    if completeness_violations:
        return 1
    verifier_scale_flag = " --scale phase-2" if scale == SCALE_PHASE_2 else ""
    print(
        "==> SUCCESS. Verify with:\n"
        f"    python3 scripts/verify_dry_run_e3.py {run_dir}{verifier_scale_flag}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
