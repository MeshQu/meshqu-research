"""Tests for the Phase 2 driver — RunController wiring around run_multi_pass.

The Phase 2 driver is the first driver that wraps the existing
`run_multi_pass(...)` + `run_permuted_diagnostic(...)` orchestration in
`RunController.run_start()` / `run_end()` lifecycle calls so Grafana
captures land alongside the bundles.

These tests exercise the driver's orchestration shape in STUB mode —
no live OpenAI / MeshQu / Grafana calls. The stub-mode mechanics
(monkey-patched `dashboard_mirror.fetch_live_dashboard` + monkey-patched
`screenshots.requests`) are exercised end-to-end here so a regression
in the controller wiring shows up as a test failure rather than a
silently-empty captures directory at Phase 2 launch.

Tests deliberately use the committed smoke fixture (3 records → 15
main bundles, 0 diagnostic because the smoke fixture has zero
intersection with the canonical permuted-policy subset). The
diagnostic test path is exercised by the existing
`test_permuted_policy.py` suite — duplicating it here would just
re-prove what those tests already cover.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


RUNNER_DIR = Path(__file__).resolve().parent.parent
E2_DIR = RUNNER_DIR.parent  # procurement-context-gradient/
REPO_DIR = E2_DIR.parent  # meshqu-research/
PHASE_2_DRIVER = RUNNER_DIR / "scripts" / "phase_2_live.py"
SMOKE_FIXTURE = RUNNER_DIR / "tests" / "fixtures" / "smoke_records_live.json"
COMMITTED_DASHBOARD = (
    REPO_DIR
    / "procurement-decisions"
    / "results"
    / "observability"
    / "dashboards"
    / "experiment-tenant-observability.json"
)
FROZEN_ARCHIVE_DIR = (
    REPO_DIR
    / "procurement-decisions"
    / "results"
    / "runs"
    / "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
)


# Both the L3 archive and the committed dashboard JSON live under
# procurement-decisions/ which is intentionally NOT carried in every
# checkout (the bulky E1 archive is gitignored locally and only
# present in working copies that have run the E1 substrate). Skip
# these tests cleanly when the archive / dashboard isn't on disk
# rather than failing in CI for an environmental reason — the
# orchestration shape is what we're verifying, and we can't verify
# it without the archive the live handlers read from.
pytestmark = pytest.mark.skipif(
    not COMMITTED_DASHBOARD.exists() or not FROZEN_ARCHIVE_DIR.exists(),
    reason=(
        "Phase 2 driver tests need the committed dashboard JSON + the E1 "
        "frozen archive on disk. Both live under procurement-decisions/ "
        "which is gitignored — skip when not present (typical for fresh "
        "worktrees)."
    ),
)


def _run_driver_stub(output_dir: Path, run_phase: str = "dry-run") -> tuple[int, str, str]:
    """Invoke the driver in stub mode as a subprocess.

    Subprocess (not in-process import) for two reasons:
      1. The driver monkey-patches global modules
         (`dashboard_mirror.fetch_live_dashboard`,
         `screenshots.requests`); running it in-process would leak
         those patches into other tests.
      2. The subprocess invocation is the SAME thing Sam will type
         when firing Phase 2 — verifying that path works end-to-end
         is the highest-value smoke we can run.
    """
    cmd = [
        sys.executable,
        str(PHASE_2_DRIVER),
        "--stub",
        "--records",
        str(SMOKE_FIXTURE),
        "--output-dir",
        str(output_dir),
        "--run-phase",
        run_phase,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        # PYTHONPATH ensures the driver finds the meshqu_runner package
        # even though we run it as `python <script>` (not as a module).
        env={**dict(_os_environ()), "PYTHONPATH": str(RUNNER_DIR)},
    )
    return result.returncode, result.stdout, result.stderr


def _os_environ() -> dict[str, str]:
    """Snapshot the current process env so subprocess inherits PATH +
    HOME + anything else needed; isolated in a helper so the test body
    stays focused on driver behaviour."""
    import os
    return dict(os.environ)


def test_stub_driver_produces_15_bundles_plus_captures(tmp_path: Path) -> None:
    """Full orchestration smoke — 15 main bundles + 0 diagnostic
    (smoke-fixture-subset intersection is empty) + populated captures
    directory. This is the contract from the task brief: '15 main-grid
    bundles + 1 diagnostic bundle (or zero diagnostic if intersection
    is empty in the smoke fixture — fine) + a populated Grafana
    captures directory'."""
    output_dir = tmp_path / "stub-out"
    returncode, stdout, stderr = _run_driver_stub(output_dir, run_phase="dry-run")

    assert returncode == 0, (
        f"Driver returned {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )

    # Run dir is the only entry under output_dir (driver synthesises
    # the run_id slug at startup).
    run_dirs = list(output_dir.iterdir())
    assert len(run_dirs) == 1, f"Expected 1 run dir, got {run_dirs}"
    run_dir = run_dirs[0]

    # Main bundle count — 3 records × 5 levels = 15 bundles.
    bundles = sorted(run_dir.glob("L*/*.bundle.json"))
    assert len(bundles) == 15, (
        f"Expected 15 main bundles, got {len(bundles)}: {bundles}"
    )

    # Diagnostic bundle count — smoke fixture has zero intersection
    # with is_in_permuted_subset, so the natural-filter pass produces
    # 0 bundles. The permutation_log sidecar still lands (it's pure
    # function of policy + seed, written eagerly before the subset
    # filter).
    diag_bundles = sorted((run_dir / "diagnostic").glob("*.bundle.json"))
    assert len(diag_bundles) == 0, (
        f"Smoke fixture should produce 0 diagnostic bundles "
        f"(empty intersection); got {len(diag_bundles)}"
    )
    assert (run_dir / "diagnostic" / "permutation_log.json").is_file(), (
        "permutation_log sidecar should land even when the diagnostic "
        "subset intersection is empty"
    )

    # Captures directory populated — at minimum run-start + run-end
    # PNGs. The dry-run cadence (every 2 records) also fires one
    # checkpoint mid-run (3 records → checkpoint at record 2), so the
    # full expected count is 3.
    captures_dir = run_dir / "observability" / "screenshots"
    assert captures_dir.is_dir(), f"Captures dir missing: {captures_dir}"
    pngs = sorted(captures_dir.glob("*.png"))
    assert len(pngs) >= 2, (
        f"Expected at least 2 captures (run-start + run-end), got "
        f"{len(pngs)}: {[p.name for p in pngs]}"
    )
    # Filename pattern: <run-phase>_<YYYY-MM-DDTHHMM>_<slug>_<event>.png
    # — run-start and run-end must both be present.
    event_labels = {p.name.rsplit("_", 1)[-1].removesuffix(".png") for p in pngs}
    assert "run-start" in event_labels, f"Missing run-start capture: {event_labels}"
    assert "run-end" in event_labels, f"Missing run-end capture: {event_labels}"

    # PNG byte-validity — capturer rejects non-PNG bodies, so a file
    # on disk is by definition PNG-signed. Spot-check one to confirm
    # the stub PNG bytes match the capturer's signature check.
    sample_bytes = pngs[0].read_bytes()
    assert sample_bytes.startswith(b"\x89PNG\r\n\x1a\n"), (
        f"Capture {pngs[0].name} doesn't start with PNG signature"
    )

    # Audit checkpoints — controller.after_record fires a checkpoint
    # row at each cadence trigger. 3 records on dry-run cadence (every
    # 2) fires once (record index 1, i.e. after record 2 completes).
    checkpoints_path = run_dir / "audit" / "checkpoints.jsonl"
    assert checkpoints_path.is_file(), f"Missing checkpoints log: {checkpoints_path}"
    checkpoint_lines = [
        json.loads(line)
        for line in checkpoints_path.read_text().splitlines()
        if line.strip()
    ]
    assert len(checkpoint_lines) >= 1, (
        f"Expected at least 1 checkpoint row (dry-run cadence + 3 records), "
        f"got {len(checkpoint_lines)}"
    )

    # Index file landed and reflects the run's actual artefact counts.
    index = json.loads((run_dir / "phase_2_index.json").read_text())
    assert index["is_stub"] is True
    assert index["main_grid_outcome_count"] == 15
    assert index["diagnostic_outcome_count"] == 0
    assert index["actual_total_bundles"] == 15
    assert index["controller_run_phase"] == "dry-run"
    assert index["capture_count"] >= 2, (
        f"Index capture_count={index['capture_count']} should be >= 2"
    )


def test_stub_driver_makes_no_live_network_calls(tmp_path: Path, monkeypatch) -> None:
    """Regression guard: stub mode must never call requests.get against
    a real network. We can't test the subprocess directly for this —
    monkey-patching across subprocess boundaries doesn't work — but we
    CAN import the driver in-process, install our own requests fake,
    and assert that fake never gets called against a non-localhost URL
    via the dashboard mirror / screenshots paths.

    The driver's `_install_stub_grafana` is the contract — it must
    monkey-patch BOTH the mirror helper AND the screenshots module
    before the controller fires."""
    # Import the driver module (not its main()) — we want the helpers,
    # not a full run.
    sys.path.insert(0, str(RUNNER_DIR / "scripts"))
    try:
        import phase_2_live  # noqa: WPS433
    finally:
        sys.path.pop(0)

    import meshqu_runner.dashboard_mirror as dm_mod
    import meshqu_runner.screenshots as scr_mod

    # Save the originals so the test doesn't leak state to siblings.
    original_fetch = dm_mod.fetch_live_dashboard
    original_requests = scr_mod.requests
    try:
        # Sentinel: real requests.get raises so any "fall through"
        # would surface immediately.
        class _NeverCall:
            def __init__(self):
                self.calls = 0

            def get(self, *a, **kw):  # noqa: D401, ANN001, ANN201
                self.calls += 1
                raise RuntimeError(
                    "Stub mode leaked a real requests.get call — "
                    "_install_stub_grafana didn't patch screenshots.requests"
                )

            RequestException = Exception

        scr_mod.requests = _NeverCall()  # type: ignore[assignment]

        # Now install the stub — this MUST replace our sentinel.
        phase_2_live._install_stub_grafana(COMMITTED_DASHBOARD)

        assert dm_mod.fetch_live_dashboard is not original_fetch, (
            "_install_stub_grafana must replace fetch_live_dashboard"
        )
        assert not isinstance(scr_mod.requests, _NeverCall), (
            "_install_stub_grafana must replace screenshots.requests"
        )

        # The stub returns the committed dashboard verbatim (no drift).
        from meshqu_runner.config import RunnerConfig

        config = RunnerConfig(
            results_dir=REPO_DIR / "procurement-decisions" / "results",
        )
        result = dm_mod.fetch_live_dashboard(config)
        assert "dashboard" in result, (
            f"Stub fetch should wrap response in Grafana envelope; got keys {list(result.keys())}"
        )

        # And the stub requests.get returns a PNG.
        resp = scr_mod.requests.get("http://stub.invalid")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        # Restore so other tests in the same process see the real
        # modules.
        dm_mod.fetch_live_dashboard = original_fetch  # type: ignore[assignment]
        scr_mod.requests = original_requests  # type: ignore[assignment]


def test_checkpoint_sleep_fn_fires_after_record_at_record_boundaries() -> None:
    """The sleep_fn adapter must convert (record, level) pair-level
    sleep calls into per-record `controller.after_record` invocations.
    Specifically: with N_levels=5 and 3 records, the adapter receives
    14 sleep calls (one between each of the 15 pair iterations) and
    should fire after_record 2 times (once after record 0's full level
    column, once after record 1's full level column — record 2's column
    is the last, no sleep follows).

    Actually — multi_pass.py calls sleep_fn BEFORE each pair (except
    the very first), not after. So the adapter sees 14 sleep calls and
    we expect after_record to fire when call_counter is a multiple of
    n_levels. With 14 calls / 5 levels = 2 firings at calls 5 and 10."""
    sys.path.insert(0, str(RUNNER_DIR / "scripts"))
    try:
        import phase_2_live  # noqa: WPS433
    finally:
        sys.path.pop(0)

    # Capture after_record invocations without a real controller.
    fired_at: list[int] = []

    class _FakeController:
        def after_record(self, record_index: int) -> None:
            fired_at.append(record_index)

    sleep_fn = phase_2_live._make_checkpoint_sleep_fn(
        controller=_FakeController(),  # type: ignore[arg-type]
        n_levels=5,
        inter_request_pause_seconds=0.0,
    )

    # Simulate multi_pass.py's call pattern: 15 pairs (3 records × 5
    # levels), with sleep_fn called before pair 2 through pair 15 (14
    # sleep calls).
    for _ in range(14):
        sleep_fn(0.0)

    # Expected: after_record fires at calls 5 and 10 (and 15 if we had
    # one more call). The record_index passed is (call_count / n_levels) - 1.
    assert fired_at == [0, 1], (
        f"Expected after_record fired at indices [0, 1] (every 5 sleep "
        f"calls converts to one record completion); got {fired_at}"
    )


def test_checkpoint_sleep_fn_swallows_capture_failure() -> None:
    """The capture is supporting evidence, not the operational record —
    a failure in controller.after_record (e.g. transient Grafana
    outage mid-run) must NEVER stop the main grid from completing.
    The adapter swallows the exception and warns; the rest of the run
    proceeds."""
    sys.path.insert(0, str(RUNNER_DIR / "scripts"))
    try:
        import phase_2_live  # noqa: WPS433
    finally:
        sys.path.pop(0)

    class _BoomController:
        def after_record(self, record_index: int) -> None:
            raise RuntimeError("simulated Grafana outage")

    sleep_fn = phase_2_live._make_checkpoint_sleep_fn(
        controller=_BoomController(),  # type: ignore[arg-type]
        n_levels=5,
        inter_request_pause_seconds=0.0,
    )

    # 10 sleep calls → would fire after_record at calls 5 and 10.
    # Both raise; the adapter must not propagate.
    for _ in range(10):
        sleep_fn(0.0)  # must not raise
