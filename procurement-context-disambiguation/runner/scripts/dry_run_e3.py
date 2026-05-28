#!/usr/bin/env python3
"""E3-011 — Dry-run driver.

Mid-scale live exercise of every E3 arm on 30 corpus records (main
arms) + 10 corpus records (diagnostic arms). Validates the cost
projection from the smoke run (E3-010), surfaces any scale-dependent
issues, and proves the runner is ready for the full Phase 2 run.

Structurally a scaled-up ``smoke_e3.py``. The live-mode wiring helpers
(``_build_live_primary_agent`` / ``_build_live_claude_agent`` /
``_build_live_meshqu_client``) are imported from ``smoke_e3`` rather
than duplicated, so the live-construction contracts PR #96 + #97 wrote
are honoured byte-identically. Only the matrix scale, the per-record
progress UX, and the dry-run-specific summary additions differ.

## The dry-run matrix

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

## Modes

  --dry           — StubAgent + StubMeshQuClient. Hermetic; no API calls.
                    The mock-test path exercises this end-to-end so the
                    live run is small-surface-area when Sam fires it.

  (no --dry)      — LIVE OpenAI + LIVE Anthropic + LIVE MeshQu client.
                    Requires every env var listed under
                    ``REQUIRED_LIVE_ENV_VARS`` (inherited from
                    ``smoke_e3``) to be populated.

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

Writes the run dir at ``<results>/runs/dry-run-<UTC-timestamp>-Z/``:

  - ``manifests/<arm_name>.manifest.json`` — per-arm run manifest
  - ``<arm_name>/<decision_id>.bundle.json`` — one bundle per receipt
  - ``dry-run-summary.md`` — per-arm receipt count, latency p50/p95,
                              total tokens, $ cost, smoke→dry-run
                              extrapolation accuracy check (±15%),
                              dry-run→Phase-2 extrapolation
  - ``dry-run-summary.json`` — same data, machine-readable

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

## Live-run invocation (Sam's shell)

    set -a && source procurement-context-disambiguation/runner/.env.live && set +a
    cd procurement-context-disambiguation/runner
    python3 scripts/dry_run_e3.py

Expected: 140 receipts under ``results/runs/dry-run-<timestamp>-Z/``
with no errors. Wall-clock: ~15-20 minutes at the default pacing
(140 receipts × ~6s average call + 0.5s pause ≈ 15 min). Verify next:

    python3 scripts/verify_dry_run_e3.py results/runs/dry-run-<timestamp>-Z/

## What this script does NOT do

- It does NOT make any live API call when ``--dry`` is passed.
- It does NOT verify receipts itself — that's ``verify_dry_run_e3.py``.
- It does NOT regenerate the locked subset; reads positions 0..29
  (main arms) and 0..9 (diagnostic arms) of the committed
  ``planning/diagnostic_subset.json``.
- It does NOT modify the live-mode construction helpers in
  ``smoke_e3.py``. Those contracts are inherited verbatim.
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
# The dry-run matrix — locked in code, mirrored verbatim in the PR body.
# ---------------------------------------------------------------------------

DRY_RUN_MAIN_OCID_COUNT = 30
"""Number of OCIDs the four main arms run against (positions 0..29)."""

DRY_RUN_DIAGNOSTIC_OCID_COUNT = 10
"""Number of OCIDs the two diagnostic arms run against (positions 0..9)."""

MAIN_ARMS: tuple[str, ...] = ("arm_a", "arm_b", "arm_c", "l4_without_nudge")
"""The four arms that run against every dry-run main OCID."""

DIAGNOSTIC_ARMS: tuple[str, ...] = ("diagnostic_primary", "diagnostic_claude")
"""The two diagnostic arms — 10 records each."""

EXPECTED_TOTAL_RECEIPTS = (
    DRY_RUN_MAIN_OCID_COUNT * len(MAIN_ARMS)
    + DRY_RUN_DIAGNOSTIC_OCID_COUNT * len(DIAGNOSTIC_ARMS)
)
"""140 — assertion target."""


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
# Full-run scale — for the dry-run → Phase 2 extrapolation table.
# Inherits from smoke_e3 so both drivers report the same Phase-2 target.
# ---------------------------------------------------------------------------

FULL_RUN_RECEIPTS_PER_MAIN_ARM = smoke_e3.FULL_RUN_RECEIPTS_PER_MAIN_ARM  # 283
FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM = (
    smoke_e3.FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
)  # 100


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
    """Slice the record set per the dry-run matrix. Main arms get all
    30 records; diagnostic arms get the first 10."""
    if arm_name in DIAGNOSTIC_ARMS:
        return diagnostic_records
    return main_records


# ---------------------------------------------------------------------------
# Summary emission — Markdown + JSON
# ---------------------------------------------------------------------------


def _format_latency_block(acc: ArmAccounting) -> str:
    p50 = acc.latency_p50()
    if p50 is None:
        return "  (no successful calls)"
    p95 = acc.latency_p95()
    return f"  p50={p50:.0f}ms  p95={(p95 or 0.0):.0f}ms"


def write_summary(
    *,
    run_dir: Path,
    run_id: str,
    started_at: str,
    finished_at: str,
    main_ocids: list[str],
    diagnostic_ocids: list[str],
    is_dry: bool,
    accountings: dict[str, ArmAccounting],
    phase_2_extrapolation: list[dict[str, Any]],
    smoke_accuracy: list[dict[str, Any]],
    completeness_violations: list[str],
    inter_request_pause_seconds: float,
) -> tuple[Path, Path]:
    """Emit ``dry-run-summary.md`` and ``dry-run-summary.json``. Returns
    both paths so the caller can echo them."""

    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    md_lines: list[str] = []
    md_lines.append(f"# E3 dry-run — `{run_id}`")
    md_lines.append("")
    md_lines.append(f"- **Started:** {started_at}")
    md_lines.append(f"- **Finished:** {finished_at}")
    md_lines.append(f"- **Mode:** {'--dry (stubs)' if is_dry else 'live'}")
    md_lines.append(f"- **Pre-registration tag:** `{PREREG_TAG}`")
    md_lines.append(
        f"- **Pacing:** {inter_request_pause_seconds:.2f}s between live calls"
    )
    md_lines.append(
        f"- **Receipts written:** {total_receipts} / {EXPECTED_TOTAL_RECEIPTS} expected"
    )
    md_lines.append(f"- **Errors:** {total_errors}")
    md_lines.append("")

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
    md_lines.append(f"    python3 scripts/verify_dry_run_e3.py {run_dir.name}/")
    md_lines.append("")
    md_lines.append(
        "(run from inside `procurement-context-disambiguation/runner/` "
        "with the run dir resolved relative to `results/runs/`.)"
    )

    md_path = run_dir / "dry-run-summary.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    json_payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "is_dry": is_dry,
        "main_ocids": main_ocids,
        "diagnostic_ocids": diagnostic_ocids,
        "expected_total_receipts": EXPECTED_TOTAL_RECEIPTS,
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
    json_path = run_dir / "dry-run-summary.json"
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


def _run_one_arm(
    *,
    arm_name: str,
    records: list[dict[str, Any]],
    run_id: str,
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
        run_phase="dry-run",
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
            "E3-011 dry-run driver. Runs 140 receipts across all six E3 "
            "arms — 30 main-arm OCIDs (positions 0..29 of the locked "
            "subset) + 10 diagnostic-arm OCIDs (positions 0..9)."
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
            "Override run_id; defaults to 'dry-run-<UTC-timestamp>-Z'."
        ),
    )
    parser.add_argument(
        "--inter-request-pause-seconds",
        type=float,
        default=None,
        help=(
            "Pace between live calls. Defaults to "
            f"{smoke_e3.INTER_REQUEST_PAUSE_SECONDS_LIVE}s in live mode "
            "(140 receipts × 0.5s = ~70s of pause across the run — "
            "comfortably below OpenAI tier-1's 500 RPM cap), 0s in --dry."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    is_dry = bool(args.dry)
    env: dict[str, str] | None
    if is_dry:
        env = None
    else:
        env = _check_env()

    # Load locked subset → positions 0..29 for main arms, 0..9 for diag arms.
    all_ocids = load_diagnostic_subset()
    if len(all_ocids) < DRY_RUN_MAIN_OCID_COUNT:
        raise SystemExit(
            f"FAIL: locked diagnostic subset has {len(all_ocids)} OCIDs; "
            f"dry-run requires ≥ {DRY_RUN_MAIN_OCID_COUNT}. Re-check "
            "planning/diagnostic_subset.json."
        )

    main_ocids = all_ocids[:DRY_RUN_MAIN_OCID_COUNT]
    diagnostic_ocids = all_ocids[:DRY_RUN_DIAGNOSTIC_OCID_COUNT]

    main_records = _build_records(main_ocids)
    diagnostic_records = _build_records(diagnostic_ocids)

    runner_dir = _RUNNER_DIR
    e3_dir = runner_dir.parent  # procurement-context-disambiguation/
    repo_dir = e3_dir.parent  # repo root
    results_dir = args.results_dir if args.results_dir else e3_dir / "results"
    run_id = args.run_id or f"dry-run-{_utc_timestamp_slug()}"
    run_dir = results_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    inter_request_pause = args.inter_request_pause_seconds
    if inter_request_pause is None:
        inter_request_pause = (
            0.0 if is_dry else smoke_e3.INTER_REQUEST_PAUSE_SECONDS_LIVE
        )

    archive = _load_precedent_archive_or_empty()

    print(f"==> Run id: {run_id}")
    print(f"    Mode:           {'--dry (stubs)' if is_dry else 'LIVE'}")
    print(f"    Run dir:        {run_dir}")
    print(
        f"    Main OCIDs:     {len(main_ocids)} "
        f"(positions 0..{DRY_RUN_MAIN_OCID_COUNT - 1})"
    )
    print(
        f"    Diag OCIDs:     {len(diagnostic_ocids)} "
        f"(positions 0..{DRY_RUN_DIAGNOSTIC_OCID_COUNT - 1})"
    )
    print(
        f"    Receipts target: {EXPECTED_TOTAL_RECEIPTS} "
        f"(4 main arms × {DRY_RUN_MAIN_OCID_COUNT} + 2 diag arms × "
        f"{DRY_RUN_DIAGNOSTIC_OCID_COUNT})"
    )
    print(f"    Pacing:         {inter_request_pause:.2f}s between calls")
    if archive:
        print(f"    Frozen archive: {len(archive)} precedents loaded")
    else:
        print("    Frozen archive: NOT loaded (Arm A/B will render no-precedents)")
    print()

    started_at = _utc_iso_now()
    t0 = time.monotonic()

    accountings: dict[str, ArmAccounting] = {}
    error_arm: str | None = None
    error_detail: str | None = None

    try:
        # Main arms: every dry-run main OCID
        for arm_name in MAIN_ARMS:
            arm_records = _records_for_arm(arm_name, main_records, diagnostic_records)
            print(f"==> {arm_name} — {len(arm_records)} records")
            acc = _run_one_arm(
                arm_name=arm_name,
                records=arm_records,
                run_id=run_id,
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

        # Diagnostic arms: every dry-run diag OCID
        for arm_name in DIAGNOSTIC_ARMS:
            arm_records = _records_for_arm(arm_name, main_records, diagnostic_records)
            print(f"==> {arm_name} — {len(arm_records)} records")
            acc = _run_one_arm(
                arm_name=arm_name,
                records=arm_records,
                run_id=run_id,
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
    except Exception as exc:  # pragma: no cover — defensive
        # Bubble the arm name from accountings (last one added) if any.
        if accountings:
            error_arm = list(accountings)[-1]
        else:
            error_arm = "(none)"
        error_detail = f"{type(exc).__name__}: {exc}"

    finished_at = _utc_iso_now()
    elapsed = time.monotonic() - t0

    completeness_violations = assert_aggregate_completeness(
        main_ocids=main_ocids,
        diagnostic_ocids=diagnostic_ocids,
        accountings=accountings,
    )

    smoke_accuracy: list[dict[str, Any]] = []
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            continue
        smoke_accuracy.append(
            compute_smoke_accuracy_row(
                arm_name=arm_name,
                dry_run_mean_tokens=acc.prompt_tokens_mean_per_record(),
            )
        )

    phase_2_extrapolation = build_phase_2_extrapolation_table(accountings)
    md_path, json_path = write_summary(
        run_dir=run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        main_ocids=main_ocids,
        diagnostic_ocids=diagnostic_ocids,
        is_dry=is_dry,
        accountings=accountings,
        phase_2_extrapolation=phase_2_extrapolation,
        smoke_accuracy=smoke_accuracy,
        completeness_violations=completeness_violations,
        inter_request_pause_seconds=inter_request_pause,
    )

    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    if error_arm is not None:
        _persist_partial_manifest(
            run_dir=run_dir,
            accountings=accountings,
            error_arm=error_arm,
            error_detail=error_detail or "",
        )

    print()
    print(
        f"==> wrote {total_receipts}/{EXPECTED_TOTAL_RECEIPTS} "
        f"receipts in {elapsed:.1f}s"
    )
    print(f"    summary (md):   {md_path}")
    print(f"    summary (json): {json_path}")
    print()
    if completeness_violations:
        print(
            "WARN: aggregate completeness violations detected — see "
            "dry-run-summary.md §'Aggregate completeness'.",
            file=sys.stderr,
        )
    if total_errors:
        print(
            f"WARN: {total_errors} per-arm errors recorded. "
            "Inspect dry-run-summary.md.",
            file=sys.stderr,
        )
    if error_arm is not None:
        print(
            f"FAIL: unrecoverable error in arm {error_arm}: {error_detail}. "
            f"Partial manifest at {run_dir / 'partial-run-manifest.json'}",
            file=sys.stderr,
        )
        return 1
    if total_receipts != EXPECTED_TOTAL_RECEIPTS:
        print(
            f"WARN: expected {EXPECTED_TOTAL_RECEIPTS} receipts, "
            f"wrote {total_receipts}.",
            file=sys.stderr,
        )
        return 1
    if completeness_violations:
        return 1
    print(
        "==> SUCCESS. Verify with:\n"
        f"    python3 scripts/verify_dry_run_e3.py {run_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
