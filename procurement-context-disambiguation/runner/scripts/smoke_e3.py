#!/usr/bin/env python3
"""E3-010 — Smoke run driver.

First end-to-end live exercise of every E3 arm on a tiny corpus subset
(3 OCIDs). Goal: surface integration surprises before the dry-run
(E3-011) burns 140 receipts of API spend.

## The smoke matrix

For the first 3 OCIDs from ``planning/diagnostic_subset.json`` (positions
0..2), the driver dispatches:

  - ``arm_a``             → 3 receipts (one per OCID)
  - ``arm_b``             → 3 receipts
  - ``arm_c``             → 3 receipts
  - ``l4_without_nudge``  → 3 receipts
  - ``diagnostic_primary`` → 1 receipt (OCID 0 only)
  - ``diagnostic_claude``  → 1 receipt (OCID 0 only)

Total: **14 receipts**.

The diagnostic arms only need OCID 0 — one record probes the
diagnostic path end-to-end, and the diagnostic prompt is record-
independent so additional records add cost without information.

## Modes

  --dry           — StubAgent + StubMeshQuClient. Hermetic; no API calls.
                    The dry-mode test path exercises this end-to-end so
                    the live run is small-surface-area when Sam fires it.

  (no --dry)      — LIVE OpenAI + LIVE Anthropic + LIVE MeshQu client.
                    Requires every env var listed under
                    ``REQUIRED_LIVE_ENV_VARS`` to be populated.

## Required environment variables (live mode only)

  - ``OPENAI_API_KEY``                        — primary agent
  - ``ANTHROPIC_API_KEY``                     — Claude diagnostic arm
  - ``MESHQU_API_URL``                        — base URL of the MeshQu API
  - ``MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID`` — experiment tenant UUID
  - ``MESHQU_EXPERIMENT_PROCUREMENT_API_KEY``   — experiment tenant API key

The driver refuses to run live mode without all five. It never echoes
the values.

## Output

Writes the run dir at ``<results>/runs/smoke-<UTC-timestamp>-Z/``:

  - ``manifests/<arm_name>.manifest.json`` — per-arm run manifest
  - ``<arm_name>/<decision_id>.bundle.json`` — one bundle per receipt
  - ``smoke-summary.md`` — timestamp, per-arm counts/latency/tokens,
                           cost extrapolation table, errors (if any)
  - ``smoke-summary.json`` — same data, machine-readable

## Live-run invocation (Sam's shell)

    set -a && source procurement-context-disambiguation/runner/.env.live && set +a
    cd procurement-context-disambiguation/runner
    python3 scripts/smoke_e3.py

The expected output is 14 receipts under
``results/runs/smoke-<timestamp>-Z/`` with no errors. Verify next:

    python3 scripts/verify_smoke_e3.py results/runs/smoke-<timestamp>-Z/

## What this script does NOT do

- It does NOT make any live API call when ``--dry`` is passed.
- It does NOT verify receipts itself — that's ``verify_smoke_e3.py``.
- It does NOT regenerate the locked subset; reads positions 0..2 of
  the committed ``planning/diagnostic_subset.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
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


# ---------------------------------------------------------------------------
# The smoke matrix — locked in code, mirrored verbatim in the PR body.
# ---------------------------------------------------------------------------

SMOKE_OCID_COUNT = 3
"""Number of OCIDs the four main arms run against."""

DIAGNOSTIC_OCID_COUNT = 1
"""Number of OCIDs the two diagnostic arms run against. The diagnostic
prompt is record-independent (the L4 envelope doesn't reference per-
record fields), so a single record probes the dispatch path end-to-end
without redundant cost."""

MAIN_ARMS: tuple[str, ...] = ("arm_a", "arm_b", "arm_c", "l4_without_nudge")
"""The four arms that run against every smoke OCID."""

DIAGNOSTIC_ARMS: tuple[str, ...] = ("diagnostic_primary", "diagnostic_claude")
"""The two diagnostic arms — one record each (OCID 0)."""

EXPECTED_TOTAL_RECEIPTS = (
    SMOKE_OCID_COUNT * len(MAIN_ARMS) + DIAGNOSTIC_OCID_COUNT * len(DIAGNOSTIC_ARMS)
)
"""14 — assertion target."""


# ---------------------------------------------------------------------------
# Live mode environment contract
# ---------------------------------------------------------------------------

REQUIRED_LIVE_ENV_VARS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "MESHQU_API_URL",
    "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID",
    "MESHQU_EXPERIMENT_PROCUREMENT_API_KEY",
)
"""Every env var the live driver consults. Missing any → refuse to
start; never half-run."""


INTER_REQUEST_PAUSE_SECONDS_LIVE = 0.5
"""Light pacing for live mode. The OpenAI + Anthropic + MeshQu rate
limits on staging aren't tight, but a 500ms gap keeps a transient 429
from cascading. 0s in --dry mode (no API to throttle)."""


# ---------------------------------------------------------------------------
# Cost extrapolation envelope — informs Sam's gate decision pre-Phase-2.
# ---------------------------------------------------------------------------

# Per the package spec §4 + the Phase-1 build plan: the dry-run scale is
# 30 records × 4 main arms + 10 records × 2 diagnostic arms = 140
# receipts; the full-run scale is 283 × 4 + 100 × 2 = ~1,332 receipts.
DRY_RUN_RECEIPTS_PER_MAIN_ARM = 30
DRY_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM = 10
FULL_RUN_RECEIPTS_PER_MAIN_ARM = 283
FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM = 100


# ---------------------------------------------------------------------------
# Per-arm accounting
# ---------------------------------------------------------------------------


@dataclass
class ArmAccounting:
    """Per-arm latency + token accounting accumulated as the driver
    walks the receipts. The summary writer renders these into the
    Markdown table + the extrapolation table."""

    arm_name: str
    record_count: int
    receipts_written: int = 0
    latencies_ms: list[int] = field(default_factory=list)
    prompt_tokens: list[int] = field(default_factory=list)
    """Per-record prompt-token counts (best-effort: ``None`` values get
    treated as 0 for summing — stub mode emits all-zeros)."""
    errors: list[str] = field(default_factory=list)

    def add_outcome(self, outcome: PassOutcome) -> None:
        self.receipts_written += 1
        self.latencies_ms.append(outcome.agent.latency_ms or 0)
        # prompt_tokens is the only token signal both the primary
        # Agent (OpenAI usage.prompt_tokens) and the ClaudeAgent
        # (usage.input_tokens) expose uniformly. Stub mode emits None;
        # treat as 0 for the sum. The PR body documents this caveat.
        pt = outcome.agent.prompt_tokens
        self.prompt_tokens.append(int(pt) if pt is not None else 0)

    def latency_mean(self) -> float | None:
        if not self.latencies_ms:
            return None
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def latency_min(self) -> int | None:
        return min(self.latencies_ms) if self.latencies_ms else None

    def latency_max(self) -> int | None:
        return max(self.latencies_ms) if self.latencies_ms else None

    def prompt_tokens_total(self) -> int:
        return sum(self.prompt_tokens)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp_slug() -> str:
    """``YYYYMMDDTHHMMSS-Z``. Stable, sortable, no separators that
    fight the filesystem. Matches the E2 ``smoke-<slug>-Z`` convention."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-Z")


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_env() -> dict[str, str]:
    """Validate required env vars are populated for live mode. Returns
    the resolved values; raises ``SystemExit`` if any are missing.

    Never prints values — only reports presence/absence.
    """
    missing = [name for name in REQUIRED_LIVE_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "FAIL: live mode requires env vars: "
            + ", ".join(missing)
            + ". Pass --dry for stubbed pipeline verification, or "
            "source procurement-context-disambiguation/runner/.env.live first."
        )
    return {name: os.environ[name] for name in REQUIRED_LIVE_ENV_VARS}


def _build_records(ocids: Iterable[str]) -> list[dict[str, Any]]:
    """Materialise the minimal-shape records the runner dispatches.

    The smoke driver intentionally feeds a minimal record shape (OCID +
    decision_type + empty fields/substrate_notes). The four main arms
    in smoke mode don't depend on substrate fields — Arm A/B select
    precedents from the frozen archive by OCID, Arm C is static, and
    L4-without-nudge is record-independent. The dry-run (E3-011) will
    swap in the substrate-cache-fed records.

    The smoke run's purpose is the integration probe — render the
    arm, call the model, sign the receipt, verify offline — not a
    substrate test. So a minimal record is correct here.
    """
    return [
        {
            "ocid": ocid,
            "decision_type": "procurement_decision",
            "fields": {},
            "substrate_notes": {},
            "metadata": {"ocid": ocid},
        }
        for ocid in ocids
    ]


def _records_for_arm(arm_name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice the record set per the smoke matrix."""
    if arm_name in DIAGNOSTIC_ARMS:
        return records[:DIAGNOSTIC_OCID_COUNT]
    return records


def _snapshot_manifest(run_dir: Path, arm_name: str) -> Path | None:
    """``run_arm`` writes ``<run_dir>/manifest.json``; we run 6 arms
    against a shared run_dir so the manifest gets overwritten. Copy
    each invocation's manifest into ``<run_dir>/manifests/<arm>.json``
    immediately after the run so per-arm provenance survives.

    Returns the snapshot path (or ``None`` if the source manifest is
    missing — shouldn't happen but defensive)."""
    src = run_dir / "manifest.json"
    if not src.exists():
        return None
    dst_dir = run_dir / "manifests"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{arm_name}.manifest.json"
    dst.write_bytes(src.read_bytes())
    return dst


# ---------------------------------------------------------------------------
# Live-mode client construction
# ---------------------------------------------------------------------------


def _build_live_primary_agent(env: dict[str, str]) -> Any:
    """Build the live primary OpenAI Agent. Imports are lazy so
    --dry mode never touches the openai SDK."""
    from meshqu_runner.agent import Agent, load_system_prompt

    return Agent(
        api_key=env["OPENAI_API_KEY"],
        system_prompt=load_system_prompt(),
    )


def _build_live_claude_agent() -> Any:
    """Build the live ClaudeAgent. ANTHROPIC_API_KEY is read from the
    environment inside the Anthropic SDK; we don't pass it explicitly.

    Imports lazy."""
    from meshqu_runner.agent import load_system_prompt
    from meshqu_runner.agents.claude import ClaudeAgent

    return ClaudeAgent(system_prompt=load_system_prompt())


def _build_live_meshqu_client(env: dict[str, str]) -> Any:
    """Build the live MeshQuClient. Reads MESHQU_API_URL,
    MESHQU_EXPERIMENT_PROCUREMENT_API_KEY,
    MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID from the supplied env map.

    This is the wiring E3-008's run_scaled_diagnostic.py deferred to
    E3-010 (with a ``NotImplementedError``). It's additive at the
    driver layer — ``meshqu_client.py`` itself is unchanged."""
    from meshqu_runner.meshqu_client import MeshQuClient

    return MeshQuClient(
        base_url=env["MESHQU_API_URL"],
        api_key=env["MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"],
        tenant_id=env["MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"],
    )


def _load_precedent_archive_or_empty() -> dict[str, Any]:
    """Best-effort load of the frozen precedent archive. Arms A and B
    take the archive via ``handler_kwargs``; if it isn't available on
    disk the handlers soft-fail to "no precedents" rendering (smoke
    still completes; the writeup notes the precedent block is empty).

    The dry-run and full run depend on the real archive; the smoke run
    uses it if present, falls back gracefully otherwise."""
    try:
        from meshqu_runner.precedent_archive import (
            ArchiveLoadError,
            default_frozen_archive_dir,
            load_frozen_archive,
        )
    except Exception:
        return {}

    try:
        # Repo root = runner_dir.parent.parent
        repo_root = _RUNNER_DIR.parent.parent
        return dict(load_frozen_archive(default_frozen_archive_dir(repo_root)))
    except ArchiveLoadError:
        return {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Summary emission — Markdown + JSON
# ---------------------------------------------------------------------------


def _format_latency_block(acc: ArmAccounting) -> str:
    mean = acc.latency_mean()
    if mean is None:
        return "  (no successful calls)"
    return (
        f"  mean={mean:.0f}ms  min={acc.latency_min()}ms  max={acc.latency_max()}ms"
    )


def build_extrapolation_table(
    accountings: dict[str, ArmAccounting],
) -> list[dict[str, Any]]:
    """Compute the per-arm cost extrapolation rows: smoke → dry-run →
    full-run. The numbers are linear extrapolations of observed mean
    prompt tokens × the target receipt count per arm. Operationally
    only an envelope — actual token usage on the full run will vary
    record-by-record."""
    rows: list[dict[str, Any]] = []
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None or acc.record_count == 0:
            continue
        mean_tokens_per_record = (
            (acc.prompt_tokens_total() / acc.record_count)
            if acc.record_count
            else 0.0
        )
        if arm_name in DIAGNOSTIC_ARMS:
            dry_run_count = DRY_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
            full_run_count = FULL_RUN_RECEIPTS_PER_DIAGNOSTIC_ARM
        else:
            dry_run_count = DRY_RUN_RECEIPTS_PER_MAIN_ARM
            full_run_count = FULL_RUN_RECEIPTS_PER_MAIN_ARM
        rows.append(
            {
                "arm": arm_name,
                "smoke_receipts": acc.record_count,
                "smoke_prompt_tokens_total": acc.prompt_tokens_total(),
                "smoke_prompt_tokens_mean_per_record": round(mean_tokens_per_record, 1),
                "dry_run_receipts": dry_run_count,
                "dry_run_prompt_tokens_projected": int(round(mean_tokens_per_record * dry_run_count)),
                "full_run_receipts": full_run_count,
                "full_run_prompt_tokens_projected": int(round(mean_tokens_per_record * full_run_count)),
            }
        )
    return rows


def write_summary(
    *,
    run_dir: Path,
    run_id: str,
    started_at: str,
    finished_at: str,
    ocids: list[str],
    is_dry: bool,
    accountings: dict[str, ArmAccounting],
    extrapolation: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """Emit ``smoke-summary.md`` and ``smoke-summary.json``. Returns
    both paths so the caller can echo them."""

    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    md_lines: list[str] = []
    md_lines.append(f"# E3 smoke run — `{run_id}`")
    md_lines.append("")
    md_lines.append(f"- **Started:** {started_at}")
    md_lines.append(f"- **Finished:** {finished_at}")
    md_lines.append(f"- **Mode:** {'--dry (stubs)' if is_dry else 'live'}")
    md_lines.append(f"- **Pre-registration tag:** `{PREREG_TAG}`")
    md_lines.append(f"- **Smoke OCIDs (positions 0..2 from `planning/diagnostic_subset.json`):**")
    for i, ocid in enumerate(ocids):
        md_lines.append(f"  {i}. `{ocid}`")
    md_lines.append("")
    md_lines.append(
        f"- **Receipts written:** {total_receipts} / {EXPECTED_TOTAL_RECEIPTS} expected"
    )
    md_lines.append(f"- **Errors:** {total_errors}")
    md_lines.append("")
    md_lines.append(
        "- **Per-arm manifests:** `manifests/<arm_name>.manifest.json`  "
        "(one per arm; `manifest.json` at the run root reflects the "
        "last arm dispatched — provenance survives in the per-arm "
        "snapshots)"
    )
    md_lines.append("")

    md_lines.append("## Per-arm latency + token totals")
    md_lines.append("")
    md_lines.append(
        "| Arm | Records | Receipts | Latency mean | Latency min | Latency max | Prompt tokens total |"
    )
    md_lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for arm_name in MAIN_ARMS + DIAGNOSTIC_ARMS:
        acc = accountings.get(arm_name)
        if acc is None:
            md_lines.append(f"| `{arm_name}` | 0 | 0 | — | — | — | — |")
            continue
        mean = acc.latency_mean()
        mean_str = f"{mean:.0f}ms" if mean is not None else "—"
        min_str = f"{acc.latency_min()}ms" if acc.latency_min() is not None else "—"
        max_str = f"{acc.latency_max()}ms" if acc.latency_max() is not None else "—"
        md_lines.append(
            f"| `{arm_name}` | {acc.record_count} | {acc.receipts_written} | "
            f"{mean_str} | {min_str} | {max_str} | {acc.prompt_tokens_total()} |"
        )
    md_lines.append("")

    md_lines.append("## Cost extrapolation (smoke → dry-run → full-run)")
    md_lines.append("")
    md_lines.append(
        "Linear extrapolation of observed mean prompt tokens per record. "
        "Operationally an envelope — record-by-record variation isn't "
        "modeled. Stub-mode numbers are zero by design (the stub agent "
        "doesn't report token usage)."
    )
    md_lines.append("")
    md_lines.append(
        "| Arm | Smoke receipts | Smoke prompt-tok total | Mean / record | Dry-run receipts | Dry-run prompt-tok proj. | Full-run receipts | Full-run prompt-tok proj. |"
    )
    md_lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in extrapolation:
        md_lines.append(
            f"| `{row['arm']}` | {row['smoke_receipts']} | "
            f"{row['smoke_prompt_tokens_total']} | "
            f"{row['smoke_prompt_tokens_mean_per_record']} | "
            f"{row['dry_run_receipts']} | "
            f"{row['dry_run_prompt_tokens_projected']} | "
            f"{row['full_run_receipts']} | "
            f"{row['full_run_prompt_tokens_projected']} |"
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
    md_lines.append(
        "    python3 scripts/verify_smoke_e3.py "
        f"{run_dir.name}/"
    )
    md_lines.append("")
    md_lines.append(
        "(run from inside `procurement-context-disambiguation/runner/` "
        "with the run dir resolved relative to `results/runs/`.)"
    )

    md_path = run_dir / "smoke-summary.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    json_payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "is_dry": is_dry,
        "ocids": ocids,
        "expected_total_receipts": EXPECTED_TOTAL_RECEIPTS,
        "total_receipts_written": total_receipts,
        "total_errors": total_errors,
        "prereg_tag": PREREG_TAG,
        "accountings": {
            name: {
                "arm_name": acc.arm_name,
                "record_count": acc.record_count,
                "receipts_written": acc.receipts_written,
                "latencies_ms": list(acc.latencies_ms),
                "prompt_tokens": list(acc.prompt_tokens),
                "latency_mean_ms": acc.latency_mean(),
                "latency_min_ms": acc.latency_min(),
                "latency_max_ms": acc.latency_max(),
                "prompt_tokens_total": acc.prompt_tokens_total(),
                "errors": list(acc.errors),
            }
            for name, acc in accountings.items()
        },
        "extrapolation": extrapolation,
    }
    json_path = run_dir / "smoke-summary.json"
    json_path.write_text(
        json.dumps(json_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return md_path, json_path


# ---------------------------------------------------------------------------
# Arm dispatch
# ---------------------------------------------------------------------------


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
    the package-spec stop rule "live-mode errors must surface" — we
    record into ``acc.errors`` and continue so the summary captures
    full state even on partial failure."""
    profile = ARM_PROFILES[arm_name]
    acc = ArmAccounting(arm_name=arm_name, record_count=len(records))

    # Pick agent + client
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

    # Policy permutation seed: required for diagnostic arms; None
    # elsewhere (the runner asserts this invariant).
    policy_permutation_seed = (
        LOCKED_PERMUTATION_SEED if arm_name in DIAGNOSTIC_ARMS else None
    )

    config = RunConfig(
        run_id=run_id,
        run_phase="smoke",
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
        # Diagnostic arms read these (others ignore via **_ignored).
        "policy_snapshot_path": DEFAULT_POLICY_SNAPSHOT_PATH,
        "seed": LOCKED_PERMUTATION_SEED,
    }
    if arm_name in ("arm_a", "arm_b") and archive:
        # Arm A/B consume the archive; pass it through. The handlers
        # accept ``archive`` as a keyword.
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

    for outcome in summary.outcomes:
        acc.add_outcome(outcome)

    # Snapshot per-arm manifest so subsequent arms' overwrites don't
    # erase provenance.
    _snapshot_manifest(run_dir, arm_name)

    return acc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smoke_e3.py",
        description=(
            "E3-010 smoke driver. Runs 14 receipts across all six E3 "
            "arms on the first 3 OCIDs from the locked diagnostic subset."
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
            "<runner>/../results (i.e. procurement-context-disambiguation/results)."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Override run_id; defaults to 'smoke-<UTC-timestamp>-Z'."
        ),
    )
    parser.add_argument(
        "--inter-request-pause-seconds",
        type=float,
        default=None,
        help=(
            "Pace between live calls. Defaults to "
            f"{INTER_REQUEST_PAUSE_SECONDS_LIVE}s in live mode, 0s in --dry."
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

    # Load locked subset → first 3 OCIDs
    all_ocids = load_diagnostic_subset()
    smoke_ocids = all_ocids[:SMOKE_OCID_COUNT]
    records = _build_records(smoke_ocids)

    # Resolve run dir
    runner_dir = _RUNNER_DIR
    e3_dir = runner_dir.parent  # procurement-context-disambiguation/
    repo_dir = e3_dir.parent  # repo root
    results_dir = args.results_dir if args.results_dir else e3_dir / "results"
    run_id = args.run_id or f"smoke-{_utc_timestamp_slug()}"
    run_dir = results_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    inter_request_pause = args.inter_request_pause_seconds
    if inter_request_pause is None:
        inter_request_pause = 0.0 if is_dry else INTER_REQUEST_PAUSE_SECONDS_LIVE

    # Pre-load the frozen archive once for Arm A/B. (No-op in stub
    # mode unless the archive happens to be on disk — handlers
    # soft-fail to empty either way.)
    archive = _load_precedent_archive_or_empty()

    print(f"==> Run id: {run_id}")
    print(f"    Mode:           {'--dry (stubs)' if is_dry else 'LIVE'}")
    print(f"    Run dir:        {run_dir}")
    print(f"    Smoke OCIDs:    {len(smoke_ocids)}")
    for i, ocid in enumerate(smoke_ocids):
        print(f"      [{i}] {ocid}")
    print(
        f"    Receipts target: {EXPECTED_TOTAL_RECEIPTS} "
        f"(4 main arms × {SMOKE_OCID_COUNT} + 2 diag arms × {DIAGNOSTIC_OCID_COUNT})"
    )
    if archive:
        print(f"    Frozen archive: {len(archive)} precedents loaded")
    else:
        print("    Frozen archive: NOT loaded (Arm A/B will render no-precedents)")
    print()

    started_at = _utc_iso_now()
    t0 = time.monotonic()

    accountings: dict[str, ArmAccounting] = {}

    # Main arms: every smoke OCID
    for arm_name in MAIN_ARMS:
        arm_records = _records_for_arm(arm_name, records)
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

    # Diagnostic arms: only OCID 0
    for arm_name in DIAGNOSTIC_ARMS:
        arm_records = _records_for_arm(arm_name, records)
        print(f"==> {arm_name} — {len(arm_records)} records (OCID 0 only)")
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

    finished_at = _utc_iso_now()
    elapsed = time.monotonic() - t0

    extrapolation = build_extrapolation_table(accountings)
    md_path, json_path = write_summary(
        run_dir=run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        ocids=smoke_ocids,
        is_dry=is_dry,
        accountings=accountings,
        extrapolation=extrapolation,
    )

    total_receipts = sum(a.receipts_written for a in accountings.values())
    total_errors = sum(len(a.errors) for a in accountings.values())

    print()
    print(f"==> wrote {total_receipts}/{EXPECTED_TOTAL_RECEIPTS} receipts in {elapsed:.1f}s")
    print(f"    summary (md):   {md_path}")
    print(f"    summary (json): {json_path}")
    print()
    if total_errors:
        print(f"WARN: {total_errors} errors recorded. Inspect smoke-summary.md.", file=sys.stderr)
    if total_receipts != EXPECTED_TOTAL_RECEIPTS:
        print(
            f"WARN: expected {EXPECTED_TOTAL_RECEIPTS} receipts, wrote {total_receipts}.",
            file=sys.stderr,
        )
        return 1
    print(
        "==> SUCCESS. Verify with:\n"
        f"    python3 scripts/verify_smoke_e3.py {run_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
