#!/usr/bin/env python3
"""Live Phase 2 driver — full-run / pilot driver with RunController wiring.

This is the canonical PRODUCTION driver for the Phase 2 full-corpus run.
It is the FIRST driver to wire the OBS-205 / OBS-206 capture
infrastructure (`RunController` + `ScreenshotCapturer` +
`mirror_and_verify`) around the existing `run_multi_pass(...)` +
`run_permuted_diagnostic(...)` orchestration.

## Why a new driver

E2-009's readiness report (§"Decisions for Sam" #2) flagged a gap:
`smoke_live.py` and `dry_run_live.py` both invoke `run_multi_pass(...)`
directly and never instantiate `RunController`, so the dry-run produced
zero runtime Grafana captures. The screenshots README explicitly
contracts automation as "primary mode" for runs of this duration, and
Appendix B of the writeup needs run-start / checkpoint / run-end
captures as operational evidence artefacts (mirrors MRP-2026-02
Appendix B).

This driver does the wiring. It is intentionally a separate file rather
than an edit to `dry_run_live.py` so the dry-run gate stays exactly as
it was at PR #57's audit point (E2-009 §1 evidence still holds against
the unmodified dry-run driver).

## Orchestration shape

Wraps the main grid + diagnostic in `RunController` lifecycle calls:

    controller.run_start()                  # OBS-206 mirror + run-start capture
    summary = run_multi_pass(
        ..., sleep_fn=_checkpoint_sleep_fn  # in-loop checkpoint capture trigger
    )
    diag = run_permuted_diagnostic(...)     # natural-subset diagnostic
    controller.run_end()                    # run-end capture

The `sleep_fn` adapter (`_make_checkpoint_sleep_fn`) is how we get
per-record checkpoints WITHOUT modifying `multi_pass.py`. `run_multi_pass`
calls `sleep_fn(pause)` between every (record, level) pair; we count
those calls and invoke `controller.after_record(record_index)` once per
record (every `len(levels)` sleep_fn calls). The controller's internal
cadence gate (`CHECKPOINT_CADENCE[run_phase]`) decides whether to
actually fire a capture — so the README's "every 2 records (dry-run)
/ every 10 records (full-run)" cadence is honoured without the driver
hard-coding the cadence itself.

This is the smallest possible adapter shape: zero changes to
`multi_pass.py` core, the `LevelHandler` Protocol, or the merged
handler-install pattern from E2-007.

## Stub-mode end-to-end test

`--stub` makes this driver runnable without ANY live network calls —
neither OpenAI nor MeshQu nor Grafana. The Grafana side is faked by
monkey-patching:
  - `meshqu_runner.dashboard_mirror.fetch_live_dashboard` →
    returns the committed dashboard JSON verbatim (no drift, mirror
    passes).
  - `meshqu_runner.screenshots.requests` → fake module whose `.get(...)`
    returns a 200 OK response with a minimal valid PNG body. Captures
    write a real PNG to disk; the orchestration is fully exercised.

This is how the orchestration smoke (and the test under
`tests/test_phase_2_driver.py`) verifies the controller wiring without
touching real services.

## Live-mode invocation

    set -a && source procurement-context-gradient/runner/.env.live && set +a
    python procurement-context-gradient/runner/scripts/phase_2_live.py \
        --fixture procurement-context-gradient/runner/tests/fixtures/dry_run_records.json \
        --run-phase full-run

The `--run-phase` flag selects the controller's checkpoint cadence (per
the screenshots README §"Capture cadence"):
  - dry-run: capture every 2 records
  - full-run: capture every 10 records
  - reproducibility-rerun: capture every 10 records

Default is `full-run`. At 283 records that produces ~30 checkpoint
captures plus run-start + run-end — close to MRP-2026-02 Appendix B's
density. At dry-run scale (30 records) it produces 15 checkpoints —
still useful when re-running the dry-run with captures.

## What the live invocation produces

Under `<results_dir>/runs/<run_id>/`:

  - manifest.json + L0..L4/<decision_id>.bundle.json (existing E2 layout)
  - diagnostic/<decision_id>.bundle.json + permutation_log.json (existing)
  - phase_2_index.json (this driver's per-run index)
  - audit/anomalies.jsonl, audit/checkpoints.jsonl,
    audit/decision_traces.jsonl  (NEW — written by AuditWriter via
    controller; pinned under the run_dir via audit_dir_override)
  - observability/screenshots/<run-phase>_<UTC-timestamp>_<dashboard>_<event>.png
    (NEW — written by ScreenshotCapturer; pinned under the run_dir via
    screenshots_dir_override so all run artefacts stay co-located —
    `cp -r run_dir/ to_writeup/` is a single step)

## Operator setup beyond `.env.live`

The driver needs Grafana credentials to mirror + capture. Add to
`.env.live` (none of these are baked into the driver — sourced at
runtime only):

  - MESHQU_RUNNER_GRAFANA_URL          (e.g. https://grafana.staging.…)
  - MESHQU_RUNNER_GRAFANA_USER         (e.g. admin)
  - MESHQU_RUNNER_GRAFANA_PASSWORD     (the renderer-allowed password)
  - MESHQU_RUNNER_DASHBOARD_UID        (default: experiment-tenant-observability)
  - MESHQU_RUNNER_TENANT               (default: experiment-procurement)

The committed dashboard JSON at
`procurement-decisions/results/observability/dashboards/<uid>.json` is
the comparison source-of-truth — `--stub` mode reuses it (no Grafana
required); live mode SHA-compares it against
`/api/dashboards/uid/<uid>` and aborts the run if they differ.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from meshqu_runner.agent import (  # noqa: E402
    Agent,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    load_system_prompt,
)
from meshqu_runner.config import RunnerConfig  # noqa: E402
from meshqu_runner.context_levels.level_l0 import install_live_l0  # noqa: E402
from meshqu_runner.context_levels.level_l3 import install_live_l3  # noqa: E402
from meshqu_runner.context_levels.level_l4 import L4PolicyEnvelopeHandler  # noqa: E402
from meshqu_runner.diagnostic.runner import run_permuted_diagnostic  # noqa: E402
from meshqu_runner.level_handlers import (  # noqa: E402
    GovernanceContextLevel,
    default_main_handlers,
)
from meshqu_runner.meshqu_client import MeshQuClient  # noqa: E402
from meshqu_runner.multi_pass import (  # noqa: E402
    MultiPassConfig,
    run_multi_pass,
)
from meshqu_runner.precedent_archive import (  # noqa: E402
    default_frozen_archive_dir,
    load_frozen_archive,
)
from meshqu_runner.prompt_loader import load_level_prompts  # noqa: E402
from meshqu_runner.runner import RunController, RunPhase  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_LIVE_ENV_VARS = (
    "MESHQU_API_URL",
    "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID",
    "MESHQU_EXPERIMENT_PROCUREMENT_API_KEY",
    "OPENAI_API_KEY",
)

# Grafana / dashboard env vars — checked separately so the failure
# message can distinguish "MeshQu creds missing" from "Grafana creds
# missing". The RunnerConfig.from_env() classmethod handles the defaults
# for us; we only need to verify the run-critical ones are present in
# live mode. The renderer password is the gating credential — without
# it ScreenshotCapturer's render call returns 401 and every capture
# logs a screenshot_capture_failed anomaly.
REQUIRED_GRAFANA_ENV_VARS = (
    "MESHQU_RUNNER_GRAFANA_URL",
    "MESHQU_RUNNER_GRAFANA_PASSWORD",
)

DEFAULT_FIXTURE_REL = "tests/fixtures/dry_run_records.json"

# Per-request pause — same 0.5s used by smoke + dry-run. The driver
# uses sleep_fn as the in-loop checkpoint trigger; the actual sleep
# duration is unchanged.
INTER_REQUEST_PAUSE_SECONDS = 0.5

# Minimal valid PNG body for stub-mode capture monkey-patching. 8-byte
# PNG signature + minimal IHDR/IDAT/IEND chunks. The capturer only
# checks the signature; this is enough to pass its validation.
_STUB_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-Z")


def _check_live_env() -> dict[str, str]:
    missing = [name for name in REQUIRED_LIVE_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing required MeshQu/OpenAI env vars (source .env.live first): "
            + ", ".join(missing)
        )
    return {name: os.environ[name] for name in REQUIRED_LIVE_ENV_VARS}


def _check_grafana_env() -> None:
    """Soft-check Grafana env vars in live mode. Warns rather than fails
    if missing — captures degrade gracefully (each one logs a
    screenshot_capture_failed anomaly) but the main-grid bundles still
    land, so the run remains useful for the receipt-side analysis even
    when captures fail. The operator sees the warning and decides
    whether to abort + fix or continue."""
    missing = [name for name in REQUIRED_GRAFANA_ENV_VARS if not os.environ.get(name)]
    if missing:
        print(
            "WARN: Grafana env vars not set: "
            + ", ".join(missing)
            + ". Captures will likely fail — each failure logs a "
            "screenshot_capture_failed anomaly. Main-grid bundles will "
            "still land. Continuing.",
            file=sys.stderr,
        )


def _load_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    with fixture_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return list(data["records"])
    raise SystemExit(
        f"Fixture at {fixture_path} is neither a JSON array nor an "
        f"object with a 'records' key."
    )


def _drop_e1_reference(record: dict[str, Any]) -> dict[str, Any]:
    """Strip the audit-only `e1_reference` block — same defensive
    elision as smoke_live.py and dry_run_live.py."""
    return {k: v for k, v in record.items() if k != "e1_reference"}


def _build_live_handlers(
    *,
    repo_dir: Path,
    policy_path: Path,
) -> dict[GovernanceContextLevel, Any]:
    """Canonical handler-install pattern from E2-007. Unchanged from
    smoke_live.py / dry_run_live.py — same registry shape, same archive
    load, same L4 wiring."""
    handlers = default_main_handlers()
    install_live_l0(handlers)

    archive = load_frozen_archive(default_frozen_archive_dir(repo_dir))
    install_live_l3(handlers, archive=archive)

    handlers["L4"] = L4PolicyEnvelopeHandler(policy_path=policy_path)
    return handlers


def _make_checkpoint_sleep_fn(
    *,
    controller: RunController,
    n_levels: int,
    inter_request_pause_seconds: float,
) -> Callable[[float], None]:
    """Adapter that turns `multi_pass.sleep_fn` into a per-record
    checkpoint trigger for `RunController.after_record`.

    `run_multi_pass` calls `sleep_fn(pause)` exactly once between every
    (record, level) pair — that's (n_records × n_levels - 1) calls per
    run. We count those calls and invoke `controller.after_record` once
    per record completion. The controller's internal cadence gate
    (`CHECKPOINT_CADENCE[run_phase]`) decides whether each
    `after_record` call actually fires a capture.

    Why this works without modifying multi_pass.py: the outer loop is
    level-batched (`for level: for record`), so sleep_fn fires N_records
    times within each level. We don't know which record-index is "the
    completed one" without tracking state, so we use a simple counter:
    every N_levels-th call corresponds to "another full record's worth
    of (record, level) pairs has elapsed". For level-batching at scale
    this is imprecise on a per-record-index basis (we fire after the
    first N pairs land regardless of which (record, level) they came
    from), but for the cadence the controller uses — every 2 or every
    10 records — it gives a faithful "every K records' worth of work
    has been done" signal. That's what the screenshots README wants —
    coverage across the run's time axis, not strict per-record
    alignment.
    """
    call_counter = {"n": 0}

    def sleep_fn(pause: float) -> None:
        # Preserve original pacing behaviour first.
        if pause > 0:
            time.sleep(pause)
        call_counter["n"] += 1
        # Approximate "completed records so far". The first sleep fires
        # AFTER the first (record, level) pair completes — so by call N,
        # we've completed N pairs. Divide by n_levels to convert
        # pair-count to record-equivalent count.
        record_equivalent = call_counter["n"] // max(n_levels, 1)
        if record_equivalent > 0 and call_counter["n"] % n_levels == 0:
            # Pass (record_equivalent - 1) so the controller sees a
            # 0-based record index; its internal modulo gate is
            # `(record_index + 1) % checkpoint_n == 0`, matching
            # "every Nth record completion".
            try:
                controller.after_record(record_equivalent - 1)
            except Exception as exc:  # noqa: BLE001 — capture is supporting evidence, never fail the run
                print(
                    f"WARN: controller.after_record({record_equivalent - 1}) raised "
                    f"{type(exc).__name__}: {exc}. Capture skipped; main run continues.",
                    file=sys.stderr,
                )

    return sleep_fn


def _install_stub_grafana(committed_dashboard_path: Path) -> None:
    """Monkey-patch `meshqu_runner.dashboard_mirror.fetch_live_dashboard`
    and `meshqu_runner.screenshots.requests` so the stub-mode
    orchestration smoke can exercise the full RunController lifecycle
    without any live Grafana / renderer calls.

    Mirror: returns the committed dashboard JSON verbatim — wrapped in
    Grafana's `{"dashboard": ..., "meta": {}}` envelope to mimic the
    live API response shape that `_canonical_dashboard_bytes` expects.
    With identical source + live bytes, the SHA-256 check passes and
    `mirror_and_verify` returns drift=False.

    Capture: a fake requests module whose `.get(...)` returns a 200 OK
    response with a minimal valid PNG body. The capturer writes the
    PNG to disk; downstream verification (was the file produced?
    populated dir?) sees the same shape it would in live mode.
    """
    import meshqu_runner.dashboard_mirror as dm
    import meshqu_runner.screenshots as scr

    with committed_dashboard_path.open("r", encoding="utf-8") as fp:
        committed_obj = json.load(fp)
    # Wrap to match the Grafana /api/dashboards/uid/<uid> response shape
    # — the canonical-bytes helper strips back down to the inner body
    # before SHA-comparing, so the source + live bytes match.
    fake_live_obj = {"dashboard": committed_obj, "meta": {}}

    def _fake_fetch(_config):  # noqa: ANN001 — signature match for monkey-patch
        return fake_live_obj

    dm.fetch_live_dashboard = _fake_fetch  # type: ignore[assignment]

    import requests as real_requests

    class _StubResp:
        status_code = 200
        headers = {"Content-Type": "image/png"}
        content = _STUB_PNG_BYTES

    class _StubRequests:
        RequestException = real_requests.RequestException

        def get(self, *_args, **_kwargs):  # noqa: D401, ANN001, ANN201
            return _StubResp()

    scr.requests = _StubRequests()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 live driver — wraps run_multi_pass + "
            "run_permuted_diagnostic in RunController lifecycle calls "
            "so Grafana captures land alongside the bundles."
        )
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help=f"Path to fixture JSON. Default: runner/{DEFAULT_FIXTURE_REL}",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Where to write results/runs/<run_id>/. Default: <repo>/procurement-context-gradient/results",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Alias for --results-dir but treated as the EXACT run_dir parent "
            "(i.e. results/<run_id>/ instead of results/runs/<run_id>/). "
            "Convenience for ad-hoc stub runs into /tmp/."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id. Default: phase-2-<UTC-timestamp-slug>.",
    )
    parser.add_argument(
        "--run-phase",
        choices=("dry-run", "full-run", "reproducibility-rerun"),
        default="full-run",
        help=(
            "Controller checkpoint cadence (per screenshots README): "
            "dry-run=every 2 records, full-run=every 10 records, "
            "reproducibility-rerun=every 10 records. Default: full-run."
        ),
    )
    parser.add_argument(
        "--records",
        default=None,
        help="Alias for --fixture (matches the stub-test invocation in the task brief).",
    )
    parser.add_argument(
        "--skip-diagnostic",
        action="store_true",
        help="Skip the Permuted-Policy diagnostic pass (debug only).",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help=(
            "Run with StubAgent + StubMeshQuClient AND monkey-patched "
            "Grafana, so the full controller lifecycle is exercised "
            "without any live OpenAI / MeshQu / Grafana calls."
        ),
    )
    args = parser.parse_args(argv)

    # --records is an alias for --fixture; --fixture wins if both given.
    fixture_arg = args.fixture or args.records
    fixture_path = (
        Path(fixture_arg) if fixture_arg else RUNNER_DIR / DEFAULT_FIXTURE_REL
    )
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")
    fixture_records_raw = _load_fixture(fixture_path)
    if not fixture_records_raw:
        raise SystemExit(f"Fixture {fixture_path} contains no records.")
    fixture_records = [_drop_e1_reference(r) for r in fixture_records_raw]

    e2_dir = RUNNER_DIR.parent  # procurement-context-gradient/
    repo_dir = e2_dir.parent  # meshqu-research/

    # Resolve output layout. --output-dir is a convenience for ad-hoc
    # stub runs (matches the task brief's `--output-dir /tmp/phase2-…`
    # invocation); it treats the supplied path as the parent of run_dir
    # directly rather than nesting under runs/. --results-dir keeps the
    # canonical results/runs/<run_id>/ layout.
    run_id_default = (
        f"phase-2-{'stub-' if args.stub else ''}{_utc_timestamp_slug()}"
    )
    run_id = args.run_id or run_id_default

    if args.output_dir:
        results_dir = Path(args.output_dir)
        run_dir = results_dir / run_id
    elif args.results_dir:
        results_dir = Path(args.results_dir)
        run_dir = results_dir / "runs" / run_id
    else:
        results_dir = e2_dir / "results"
        run_dir = results_dir / "runs" / run_id

    policy_path = e2_dir / "policy" / "policy-snapshot-cbf12348.json"
    if not policy_path.exists():
        raise SystemExit(f"Policy snapshot not found at {policy_path}")

    prompts_dir = RUNNER_DIR / "prompts"
    prompts = load_level_prompts(prompts_dir)

    # ---- Construct clients ----------------------------------------------

    if args.stub:
        # Stub-mode orchestration smoke. No live calls anywhere — the
        # MeshQu + OpenAI clients are stubs; Grafana is monkey-patched
        # in _install_stub_grafana(). Safe to run in CI without secrets.
        from meshqu_runner.multi_pass import StubAgent, StubMeshQuClient  # noqa: WPS433

        agent = StubAgent()
        meshqu_client = StubMeshQuClient()
        api_url = "https://stub.invalid"
        substrate_adapter_version = "stub-phase-2-7ddf7274"
    else:
        env = _check_live_env()
        _check_grafana_env()
        system_prompt = load_system_prompt()
        agent = Agent(
            api_key=env["OPENAI_API_KEY"],
            system_prompt=system_prompt,
            model_id=LOCKED_MODEL_ID,
            temperature=LOCKED_TEMPERATURE,
        )
        meshqu_client = MeshQuClient(
            base_url=env["MESHQU_API_URL"],
            api_key=env["MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"],
            tenant_id=env["MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"],
        )
        api_url = env["MESHQU_API_URL"]
        substrate_adapter_version = "cached-e1-phase-2-7ddf7274"

    # ---- RunnerConfig — route audit + screenshots under the run dir -----
    #
    # The capture infra defaults (per RunnerConfig.from_env) point at
    # `procurement-decisions/results/observability/screenshots/` which
    # is the SHARED writeup directory. For per-run isolation (so curation
    # is `cp -r <run_dir>/` not a global archaeology dig) we override
    # both `audit_dir` and `screenshots_dir` to live under the run dir.
    # This matches the same pattern dry_run_eval_loop.py uses for E1.
    base_runner_config = RunnerConfig.from_env()
    runner_config = RunnerConfig(
        grafana_url=base_runner_config.grafana_url,
        grafana_user=base_runner_config.grafana_user,
        grafana_password=base_runner_config.grafana_password,
        dashboard_uid=base_runner_config.dashboard_uid,
        tenant=base_runner_config.tenant,
        monorepo_dashboard_path=base_runner_config.monorepo_dashboard_path,
        results_dir=base_runner_config.results_dir,
        render_timeout_seconds=base_runner_config.render_timeout_seconds,
        audit_dir_override=run_dir / "audit",
        screenshots_dir_override=run_dir / "observability" / "screenshots",
    )

    # In stub mode, install the fake Grafana BEFORE the controller is
    # built — RunController.__post_init__ doesn't touch Grafana, but
    # run_start() does (via mirror_and_verify). Installing earlier is
    # harmless and keeps the lifecycle linear.
    if args.stub:
        if not runner_config.committed_dashboard_path.exists():
            raise SystemExit(
                "Stub mode needs a committed dashboard JSON at "
                f"{runner_config.committed_dashboard_path} for the mirror fake. "
                "(This file lives under procurement-decisions/results/observability/dashboards/)"
            )
        _install_stub_grafana(runner_config.committed_dashboard_path)

    # Note: RunPhase literals use hyphens ("dry-run") — matches the
    # screenshots README filename pattern and CHECKPOINT_CADENCE keys.
    controller_run_phase: RunPhase = args.run_phase  # type: ignore[assignment]

    controller = RunController(
        config=runner_config,
        run_phase=controller_run_phase,
        run_id=run_id,
        total_records=len(fixture_records),
    )

    # ---- MultiPassConfig ------------------------------------------------
    #
    # Underlying multi_pass run_phase string follows the existing
    # convention used by smoke_live ("smoke") and dry_run_live ("dry_run")
    # — written with underscore. Distinct from controller_run_phase
    # which is part of the screenshot filename and uses the hyphenated
    # README spelling.
    underlying_run_phase = "phase_2"
    config = MultiPassConfig(
        run_id=run_id,
        run_phase=underlying_run_phase,
        repo_dir=repo_dir,
        run_dir=run_dir,
        prompts_dir=prompts_dir,
        policy_snapshot_path=policy_path,
        meshqu_api_url=api_url,
        meshqu_tenant_label="experiment-procurement",
        substrate_adapter_version=substrate_adapter_version,
        substrate_source={
            "kind": "cached_e1_archive",
            "archive_run_id": "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d",
            "fixture_path": str(fixture_path),
            "fixture_record_count": len(fixture_records),
        },
        inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
        cache_telemetry_enabled=True,
    )

    print(f"==> Run id: {run_id}")
    print(f"    Mode:           {'STUB (no live calls)' if args.stub else 'LIVE (real OpenAI + MeshQu + Grafana)'}")
    print(f"    Controller phase: {controller_run_phase} (checkpoint cadence per README)")
    print(f"    Run dir:        {run_dir}")
    print(f"    Audit dir:      {runner_config.audit_dir}")
    print(f"    Screenshots:    {runner_config.screenshots_dir}")
    print(f"    Fixture:        {fixture_path}")
    print(f"    Records:        {len(fixture_records)}")
    print(f"    Levels (main):  L0 L1 L2 L3 L4  ({len(fixture_records) * 5} receipts)")
    print(f"    Diagnostic:     {'natural-subset Permuted-Policy' if not args.skip_diagnostic else 'SKIPPED'}")
    print()

    live_handlers = _build_live_handlers(repo_dir=repo_dir, policy_path=policy_path)
    print(
        "    Handlers: "
        + ", ".join(f"{lvl}={type(h).__name__}" for lvl, h in sorted(live_handlers.items()))
    )
    print()

    # ---- RunController.run_start ---------------------------------------
    #
    # OBS-206 mirror + OBS-205 run-start capture. If the live dashboard
    # has drifted from the committed mirror this raises MirrorError —
    # we surface that as a clear SystemExit BEFORE any live call lands,
    # consistent with the screenshots README's "fail fast at run start
    # rather than mid-run" guidance.
    try:
        mirror_result, start_capture = controller.run_start()
    except Exception as exc:  # noqa: BLE001 — re-raise as SystemExit with operator context
        raise SystemExit(
            f"RunController.run_start() failed: {type(exc).__name__}: {exc}. "
            f"Check Grafana mirror at {runner_config.committed_dashboard_path} "
            f"vs live {runner_config.grafana_url}."
        )
    print(
        f"==> run_start OK. mirror sha256={mirror_result.canonical_sha256[:12]}…, "
        f"capture ok={start_capture.ok}"
        + (f" path={start_capture.path.name}" if start_capture.path else "")
    )

    # ---- Main grid ------------------------------------------------------

    sleep_fn = _make_checkpoint_sleep_fn(
        controller=controller,
        n_levels=len(config.levels),
        inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
    )

    t_main_start = time.monotonic()
    summary = run_multi_pass(
        config=config,
        records=fixture_records,
        agent=agent,
        meshqu_client=meshqu_client,
        handlers=live_handlers,
        sleep_fn=sleep_fn,
    )
    t_main_end = time.monotonic()
    main_elapsed = t_main_end - t_main_start
    n_main = len(summary.outcomes)
    print(
        f"==> Main grid done. {n_main} receipts in "
        f"{main_elapsed:.1f}s ({main_elapsed / max(n_main, 1):.2f}s/call)."
    )

    # ---- Diagnostic pass -----------------------------------------------

    n_diagnostic = 0
    diag_subset_ocids: list[str] = []
    if not args.skip_diagnostic:
        print("==> Running Permuted-Policy diagnostic (natural-subset filter)…")
        t_diag_start = time.monotonic()
        diag_summary = run_permuted_diagnostic(
            run_id=run_id,
            run_dir=run_dir,
            prompts=prompts,
            policy_path=policy_path,
            records=fixture_records,
            agent=agent,
            meshqu_client=meshqu_client,
            inter_request_pause_seconds=INTER_REQUEST_PAUSE_SECONDS,
        )
        t_diag_end = time.monotonic()
        n_diagnostic = len(diag_summary.outcomes)
        diag_subset_ocids = list(diag_summary.subset_ocids)
        print(
            f"    Diagnostic done. {n_diagnostic} bundle(s) in "
            f"{t_diag_end - t_diag_start:.1f}s. "
            f"Subset OCIDs in fixture: {len(diag_subset_ocids)}"
        )

    # ---- RunController.run_end -----------------------------------------

    try:
        end_capture = controller.run_end()
    except Exception as exc:  # noqa: BLE001 — never fail the run on a final capture
        print(
            f"WARN: controller.run_end() raised {type(exc).__name__}: {exc}. "
            "Run-end capture missing; main bundles still landed.",
            file=sys.stderr,
        )
        end_capture = None

    if end_capture is not None:
        print(
            f"==> run_end OK. capture ok={end_capture.ok}"
            + (f" path={end_capture.path.name}" if end_capture.path else "")
        )

    # ---- Index file ----------------------------------------------------

    total = n_main + n_diagnostic
    captures_dir = runner_config.screenshots_dir
    capture_files = sorted(p.name for p in captures_dir.glob("*.png")) if captures_dir.exists() else []
    index = {
        "run_id": run_id,
        "controller_run_phase": controller_run_phase,
        "fixture": str(fixture_path),
        "fixture_record_count": len(fixture_records),
        "main_grid_outcome_count": n_main,
        "diagnostic_outcome_count": n_diagnostic,
        "diagnostic_subset_ocid_count": len(diag_subset_ocids),
        "expected_main_total": len(fixture_records) * 5,
        "actual_total_bundles": total,
        "is_stub": bool(args.stub),
        "wall_clock_seconds_main": round(main_elapsed, 1),
        "captures_dir": str(captures_dir),
        "capture_files": capture_files,
        "capture_count": len(capture_files),
    }
    index_path = run_dir / "phase_2_index.json"
    with index_path.open("w", encoding="utf-8") as fp:
        json.dump(index, fp, indent=2, sort_keys=True)
        fp.write("\n")
    print(f"==> Wrote index: {index_path}")
    print(f"==> Captures: {len(capture_files)} PNG(s) in {captures_dir}")

    expected_main = len(fixture_records) * 5
    if n_main != expected_main:
        print(
            f"WARN: expected {expected_main} main bundles, wrote {n_main}.",
            file=sys.stderr,
        )
        return 1

    print(f"==> SUCCESS: {total} bundles + {len(capture_files)} captures in {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
