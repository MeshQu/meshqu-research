"""OBS-205 / OBS-206 observability wiring on ``scripts/dry_run_e3.py``.

Closes the gap Sam caught between PR #101 (``--scale phase-2``) and the
``phase_2_live.py`` pattern in E2: the dry-run-derived driver inherited
the dry-run posture and never picked up ``RunController`` wiring, so a
Phase-2 fire would have produced zero Grafana captures.

The wiring lands at three points in ``dry_run_e3.main()``:

  - **run_start**: after the run dir is created and observability is
    enabled, build a ``RunController``, mirror the dashboard, capture
    the run-start snapshot.
  - **run_end**: after the per-arm summary write succeeds, capture the
    run-end snapshot.
  - **on-error / on-halt**: in the ``except KeyboardInterrupt`` and
    ``except Exception`` paths around the arm loop, fire an
    ``on_anomaly`` capture so the partial operational state is visible
    in the writeup.

Gating contract this file locks:

  - ``--scale phase-2``                          → capture ON.
  - ``--scale phase-2 --no-observability``       → capture OFF.
  - ``--scale dry-run`` (default)                → capture OFF.
  - ``--scale dry-run --observability``          → capture ON.
  - missing ``MESHQU_RUNNER_GRAFANA_*`` under ``--scale phase-2``
                                                  → **fail-loud**
                                                    (``SystemExit``) at
                                                    run-start. Phase-2
                                                    receipts get signed
                                                    under the
                                                    experiment kid; a
                                                    "successful"
                                                    phase-2 that
                                                    silently drops
                                                    captures is the
                                                    structural twin of
                                                    the record-
                                                    composition bug
                                                    (cryptographic
                                                    success masking
                                                    methodological
                                                    drop). Fail at the
                                                    gate, not the
                                                    audit.
  - missing ``MESHQU_RUNNER_GRAFANA_*`` under ``--scale dry-run
    --observability`` (rare opt-in) → soft-fail (WARN, run continues,
                                       no capture). Dry-run is
                                       iterable validation, not the
                                       writeup-anchor run.
  - Grafana endpoint raises ``ConnectionError``  → soft-fail under
                                                    both scales. Runtime
                                                    transient errors
                                                    must not lose
                                                    receipts that
                                                    already landed.

No live Grafana calls. ``meshqu_runner.dashboard_mirror.fetch_live_dashboard``
+ ``meshqu_runner.screenshots.requests`` are monkey-patched per the
established stub-mode idiom in ``phase_2_live.py``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_RUNNER_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _RUNNER_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

import dry_run_e3  # noqa: E402


# ---------------------------------------------------------------------------
# Stub fixtures
# ---------------------------------------------------------------------------

# Minimal valid PNG (8-byte signature + IHDR/IDAT/IEND chunks) — enough
# bytes for ``screenshots.PNG_SIGNATURE`` to validate. Same blob shape
# E2's ``phase_2_live.py`` uses for ``--stub`` mode.
_STUB_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _StubPngResp:
    status_code = 200
    headers = {"Content-Type": "image/png"}
    content = _STUB_PNG_BYTES


class _StubRequests:
    """Counts every ``.get(...)`` so tests can assert capture cadence.

    Matches the surface ``meshqu_runner.screenshots`` consumes:
    ``RequestException`` attribute + ``get(...)`` returning a response
    with ``status_code`` + ``headers`` + ``content``. The committed
    dashboard JSON path is faked separately via
    ``dashboard_mirror.fetch_live_dashboard`` monkey-patch."""

    def __init__(self) -> None:
        import requests as real_requests

        self.RequestException = real_requests.RequestException
        self.calls: list[str] = []

    def get(self, url, *_args, **_kwargs):  # noqa: ANN001 — duck-typed
        self.calls.append(url)
        return _StubPngResp()


class _BoomRequests:
    """Raises ``ConnectionError`` on every ``.get(...)`` — exercises the
    soft-fail-on-unreachable-Grafana path. The mirror call hits this
    first (via ``mirror_and_verify`` → ``fetch_live_dashboard`` →
    ``requests.get``), so ``run_start`` returns ``None`` and no capture
    lands."""

    def __init__(self) -> None:
        import requests as real_requests

        self.RequestException = real_requests.RequestException

    def get(self, *_args, **_kwargs):  # noqa: ANN001
        import requests as real_requests

        raise real_requests.ConnectionError("simulated grafana outage")


@pytest.fixture
def stub_grafana(monkeypatch):
    """Install the stub Grafana surfaces and return the counting
    ``_StubRequests`` so tests can assert per-call cadence."""
    import meshqu_runner.dashboard_mirror as dm
    import meshqu_runner.screenshots as scr

    # Load the committed dashboard JSON the mirror compares against and
    # echo it back to the live-fetch surface — same bytes both sides →
    # canonical-SHA matches → ``mirror_and_verify`` returns drift=False.
    committed_path = (
        _RUNNER_DIR.parents[1]
        / "procurement-decisions"
        / "results"
        / "observability"
        / "dashboards"
        / "experiment-tenant-observability.json"
    )
    assert committed_path.exists(), (
        f"committed dashboard JSON missing at {committed_path} — "
        "fixture cannot run without it"
    )
    with committed_path.open("r", encoding="utf-8") as fp:
        committed_obj = json.load(fp)
    fake_live = {"dashboard": committed_obj, "meta": {}}

    def _fake_fetch(_config):  # noqa: ANN001 — duck-typed
        return fake_live

    monkeypatch.setattr(dm, "fetch_live_dashboard", _fake_fetch)

    stub = _StubRequests()
    monkeypatch.setattr(scr, "requests", stub)

    return stub


@pytest.fixture
def grafana_env(monkeypatch):
    """Pin the Grafana env vars to known values so the soft-check
    passes. Other tests explicitly clear these to exercise the
    missing-env soft-fail path."""
    monkeypatch.setenv("MESHQU_RUNNER_GRAFANA_URL", "http://stub.invalid:3101")
    monkeypatch.setenv("MESHQU_RUNNER_GRAFANA_USER", "admin")
    monkeypatch.setenv("MESHQU_RUNNER_GRAFANA_PASSWORD", "stub")
    monkeypatch.setenv(
        "MESHQU_RUNNER_DASHBOARD_UID", "experiment-tenant-observability"
    )
    monkeypatch.setenv("MESHQU_RUNNER_TENANT", "experiment-procurement")


def _dispatch_dry(
    tmp_path: Path,
    *,
    scale: str,
    run_id: str,
    extra_args: list[str] | None = None,
) -> Path:
    """Drive ``dry_run_e3.main`` in ``--dry`` mode at the given scale.
    Returns the run directory."""
    argv = [
        "--scale", scale,
        "--dry",
        "--results-dir", str(tmp_path),
        "--run-id", run_id,
        "--inter-request-pause-seconds", "0.0",
    ]
    if extra_args:
        argv.extend(extra_args)
    rc = dry_run_e3.main(argv)
    assert rc == 0, f"driver returned {rc} for --scale {scale} {extra_args}"
    return tmp_path / "runs" / run_id


# ---------------------------------------------------------------------------
# Unit tests — observability gating helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scale,no_observability,observability,expected",
    [
        # --scale phase-2: default ON; --no-observability wins; --observability redundant.
        ("phase-2", False, False, True),
        ("phase-2", True, False, False),
        ("phase-2", False, True, True),
        ("phase-2", True, True, False),  # --no-observability beats --observability
        # --scale dry-run: default OFF; --observability flips ON.
        ("dry-run", False, False, False),
        ("dry-run", False, True, True),
        ("dry-run", True, False, False),
        ("dry-run", True, True, False),  # --no-observability beats --observability
    ],
    ids=[
        "phase-2/default-on",
        "phase-2/no-observability-off",
        "phase-2/observability-redundant-on",
        "phase-2/no-observability-wins",
        "dry-run/default-off",
        "dry-run/observability-on",
        "dry-run/no-observability-off",
        "dry-run/no-observability-wins",
    ],
)
def test_resolve_observability_enabled_gating(
    scale: str,
    no_observability: bool,
    observability: bool,
    expected: bool,
) -> None:
    """The gating helper encodes the full contract:

      - phase-2: default ON, --no-observability opts out.
      - dry-run: default OFF, --observability opts in.
      - --no-observability wins over --observability if both passed.
    """
    actual = dry_run_e3._resolve_observability_enabled(
        scale=scale,
        no_observability=no_observability,
        observability=observability,
    )
    assert actual is expected


# ---------------------------------------------------------------------------
# End-to-end — phase-2 with observability ON fires run-start + run-end
# ---------------------------------------------------------------------------


def test_phase_2_default_fires_run_start_and_run_end_captures(
    tmp_path: Path, grafana_env, stub_grafana
):
    """``--scale phase-2`` (without ``--no-observability``) wires the
    full lifecycle: dashboard mirror + run-start capture + run-end
    capture. Two ``screenshots.requests.get`` calls land in
    ``<run_dir>/observability/screenshots/`` per the E2 filename
    pattern."""
    run_dir = _dispatch_dry(
        tmp_path, scale="phase-2", run_id="obs-phase-2-default"
    )

    # Two render calls: run-start + run-end.
    assert len(stub_grafana.calls) == 2, (
        f"expected 2 render calls (run-start + run-end), got "
        f"{len(stub_grafana.calls)}: {stub_grafana.calls}"
    )

    # Captures land in <run_dir>/observability/screenshots/.
    screenshots_dir = run_dir / "observability" / "screenshots"
    assert screenshots_dir.is_dir(), (
        f"expected observability/screenshots/ under {run_dir}, "
        f"got {sorted(p.name for p in run_dir.iterdir())}"
    )
    png_files = sorted(p.name for p in screenshots_dir.glob("*.png"))
    assert len(png_files) == 2, (
        f"expected 2 PNGs (run-start + run-end), got {png_files}"
    )

    # E2's filename pattern: <run-phase>_<UTC-stamp>_<dashboard-uid>_<event>.png
    # Phase-2 uses "full-run" RunPhase per the existing
    # _run_phase_for_scale mapping (matches the CHECKPOINT_CADENCE keys).
    run_start_files = [n for n in png_files if n.endswith("_run-start.png")]
    run_end_files = [n for n in png_files if n.endswith("_run-end.png")]
    assert len(run_start_files) == 1, f"missing run-start PNG in {png_files}"
    assert len(run_end_files) == 1, f"missing run-end PNG in {png_files}"
    for fname in png_files:
        assert fname.startswith("full-run_"), (
            f"phase-2 uses full-run cadence; expected 'full-run_' prefix on "
            f"{fname!r}"
        )
        assert "experiment-tenant-observability" in fname, (
            f"locked dashboard UID missing from filename: {fname!r}"
        )

    # The dashboard-mirror audit dir also lands under the run dir.
    audit_dir = run_dir / "observability" / "audit"
    assert audit_dir.is_dir(), "observability/audit/ should be co-located"


# ---------------------------------------------------------------------------
# End-to-end — phase-2 + --no-observability skips capture
# ---------------------------------------------------------------------------


def test_phase_2_no_observability_skips_capture(
    tmp_path: Path, grafana_env, stub_grafana
):
    """``--scale phase-2 --no-observability`` produces zero capture
    calls and no observability/ tree under the run dir. Receipts still
    land normally (140 / 1,332 totals locked by the existing
    test_phase_2_scale tests)."""
    run_dir = _dispatch_dry(
        tmp_path,
        scale="phase-2",
        run_id="obs-phase-2-disabled",
        extra_args=["--no-observability"],
    )

    assert len(stub_grafana.calls) == 0, (
        f"expected zero render calls with --no-observability, got "
        f"{stub_grafana.calls}"
    )
    assert not (run_dir / "observability").exists(), (
        "observability/ tree must not be created when capture is disabled"
    )


# ---------------------------------------------------------------------------
# End-to-end — dry-run default (no flag) skips capture
# ---------------------------------------------------------------------------


def test_dry_run_default_skips_capture(
    tmp_path: Path, grafana_env, stub_grafana
):
    """``--scale dry-run`` (default, no ``--observability`` flag) is the
    iterable-validation posture — captures off, observability tree
    absent. This preserves the 140-receipt behaviour exactly: existing
    43 tests stay green by construction."""
    run_dir = _dispatch_dry(
        tmp_path, scale="dry-run", run_id="obs-dry-run-default"
    )

    assert len(stub_grafana.calls) == 0, (
        f"expected zero render calls in --scale dry-run default, got "
        f"{stub_grafana.calls}"
    )
    assert not (run_dir / "observability").exists()


# ---------------------------------------------------------------------------
# End-to-end — dry-run + --observability fires captures
# ---------------------------------------------------------------------------


def test_dry_run_with_observability_flag_fires_captures(
    tmp_path: Path, grafana_env, stub_grafana
):
    """``--scale dry-run --observability`` opts in to capture for
    parity-testing the wiring. Filename prefix is ``dry-run_`` (the
    cadence's RunPhase literal) rather than ``full-run_``."""
    run_dir = _dispatch_dry(
        tmp_path,
        scale="dry-run",
        run_id="obs-dry-run-on",
        extra_args=["--observability"],
    )

    assert len(stub_grafana.calls) == 2, (
        f"expected 2 render calls (run-start + run-end), got "
        f"{stub_grafana.calls}"
    )
    screenshots_dir = run_dir / "observability" / "screenshots"
    png_files = sorted(p.name for p in screenshots_dir.glob("*.png"))
    assert len(png_files) == 2
    for fname in png_files:
        assert fname.startswith("dry-run_"), (
            f"--scale dry-run uses dry-run cadence; expected 'dry-run_' "
            f"prefix on {fname!r}"
        )


# ---------------------------------------------------------------------------
# Precondition lock-in — missing MESHQU_RUNNER_GRAFANA_* under --scale phase-2
# ---------------------------------------------------------------------------


def test_phase_2_missing_grafana_env_fails_loud_at_gate(
    tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    """Sam's 2026-05-28 policy-split: precondition vs runtime.

    Phase-2 receipts get signed under the experiment-tenant kid. A
    Phase-2 run that "succeeds" (1,332 cryptographically-verified
    receipts) while silently dropping observability captures is the
    structural twin of the record-composition bug — cryptographic
    success masking a methodological drop. The fix is to fail-loud at
    the gate before any receipts get signed, not to discover the gap
    in audit.

    Under ``--scale phase-2`` with required Grafana env vars missing,
    the driver MUST raise ``SystemExit`` with a clear FAIL message
    before any arm fires. Zero receipts written. The ``--no-
    observability`` opt-out lets the operator say "I know, do it
    anyway" (covered by ``test_phase_2_no_observability_skips_capture``)
    — but the silent path is removed."""
    monkeypatch.delenv("MESHQU_RUNNER_GRAFANA_URL", raising=False)
    monkeypatch.delenv("MESHQU_RUNNER_GRAFANA_PASSWORD", raising=False)

    argv = [
        "--scale", "phase-2",
        "--dry",
        "--results-dir", str(tmp_path),
        "--run-id", "obs-phase-2-fail-loud",
        "--inter-request-pause-seconds", "0.0",
    ]
    with pytest.raises(SystemExit) as exc_info:
        dry_run_e3.main(argv)

    msg = str(exc_info.value)
    assert "FAIL" in msg, (
        f"phase-2 missing-env exit must use FAIL prefix; got: {msg!r}"
    )
    assert "--scale phase-2" in msg and "MESHQU_RUNNER_GRAFANA" in msg, (
        f"FAIL message must name the gate (--scale phase-2) + the missing "
        f"env class; got: {msg!r}"
    )
    assert "--no-observability" in msg, (
        "FAIL message must surface the documented opt-out so the operator "
        "knows how to proceed if Grafana is genuinely unavailable"
    )

    # No receipts landed — fail-loud fires before any arm dispatches.
    candidates = list(tmp_path.glob("**/arm_a/*.bundle.json"))
    assert candidates == [], (
        f"phase-2 fail-loud must not write any receipts; found: {candidates!r}"
    )


# ---------------------------------------------------------------------------
# Soft-fail — missing MESHQU_RUNNER_GRAFANA_* under --scale dry-run + opt-in
# ---------------------------------------------------------------------------


def test_dry_run_observability_optin_missing_env_soft_fails(
    tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    """Under ``--scale dry-run --observability`` (the rare opt-in case
    for parity-testing the wiring without phase-2's cost), missing env
    is a WARN-and-continue. Dry-run is iterable validation, not the
    writeup-anchor run — its receipts don't need the cross-trilogy
    capture parity that phase-2 does."""
    monkeypatch.delenv("MESHQU_RUNNER_GRAFANA_URL", raising=False)
    monkeypatch.delenv("MESHQU_RUNNER_GRAFANA_PASSWORD", raising=False)

    run_dir = _dispatch_dry(
        tmp_path,
        scale="dry-run",
        run_id="obs-dry-run-optin-soft-fail",
        extra_args=["--observability"],
    )

    captured = capsys.readouterr()
    assert "MESHQU_RUNNER_GRAFANA_URL" in captured.err, (
        f"dry-run + observability + missing env must emit a WARN naming "
        f"the missing var; got: {captured.err!r}"
    )
    assert "WARN" in captured.err, (
        "dry-run + observability + missing env must emit a WARN-prefixed "
        "line, not a FAIL — dry-run is iterable, not writeup-anchor"
    )

    # Receipts STILL land — the dry-run matrix shape is preserved.
    assert not (run_dir / "observability").exists(), (
        "observability tree must NOT land when Grafana env is missing — "
        "soft-fail returns None before any capture is attempted"
    )
    for arm in dry_run_e3.MAIN_ARMS:
        bundles = sorted((run_dir / arm).glob("*.bundle.json"))
        assert len(bundles) == 30, (
            f"dry-run + observability + missing env must still produce "
            f"30 receipts per main arm; got {arm!r}={len(bundles)}"
        )


# ---------------------------------------------------------------------------
# Soft-fail — Grafana endpoint unreachable
# ---------------------------------------------------------------------------


def test_grafana_unreachable_emits_warning_but_does_not_halt(
    tmp_path: Path, grafana_env, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    """When the env vars ARE set but the Grafana endpoint raises
    ``ConnectionError``, the soft-fail catches the failure at
    ``run_start`` and disables capture for the rest of the run. The
    receipt-side artefacts must land in full."""
    import meshqu_runner.dashboard_mirror as dm
    import meshqu_runner.screenshots as scr

    # Mirror call raises — surfaces as MirrorError out of
    # mirror_and_verify, caught by _build_observability_controller's
    # try/except around controller.run_start().
    import requests as real_requests

    def _boom_fetch(_config):  # noqa: ANN001
        raise real_requests.ConnectionError("simulated grafana outage")

    monkeypatch.setattr(dm, "fetch_live_dashboard", _boom_fetch)
    monkeypatch.setattr(scr, "requests", _BoomRequests())

    run_dir = _dispatch_dry(
        tmp_path, scale="phase-2", run_id="obs-soft-fail-unreachable"
    )

    captured = capsys.readouterr()
    assert "WARN" in captured.err, (
        f"expected WARN on stderr when Grafana is unreachable; "
        f"got: {captured.err!r}"
    )
    # Either the run_start or the controller-construction WARN fired —
    # both are valid soft-fail paths. We assert the user-facing signal
    # carries the words "run_start" OR "OBS-205/206" so the operator
    # sees what failed.
    assert (
        "run_start" in captured.err
        or "OBS-205/206" in captured.err
        or "RunController" in captured.err
    ), (
        f"WARN must carry an actionable label; got: {captured.err!r}"
    )

    # Receipts still land in full.
    for arm in dry_run_e3.MAIN_ARMS:
        bundles = sorted((run_dir / arm).glob("*.bundle.json"))
        assert len(bundles) == 283, (
            f"phase-2 main arm {arm!r} must produce 283 receipts even "
            f"when Grafana is unreachable; got {len(bundles)}"
        )


# ---------------------------------------------------------------------------
# Capture filename — matches E2's <run-phase>_<UTC>_<dashboard>_<event>.png
# ---------------------------------------------------------------------------


def test_capture_files_match_e2_filename_pattern(
    tmp_path: Path, grafana_env, stub_grafana
):
    """Cross-trilogy parity: capture filenames must match the exact
    pattern E1/E2 emit so the writeup pipeline doesn't need
    per-experiment special-cases. Pattern:

        <run-phase>_<YYYY-MM-DDTHHMM>_<dashboard-slug>_<event>.png

    Run-phase: ``full-run`` for ``--scale phase-2`` / ``dry-run`` for
    ``--scale dry-run --observability``. Dashboard slug: the locked
    ``experiment-tenant-observability`` UID. Events for this driver's
    hook points: ``run-start`` and ``run-end``.
    """
    import re

    run_dir = _dispatch_dry(
        tmp_path, scale="phase-2", run_id="obs-filename-pattern"
    )
    pngs = sorted(
        (run_dir / "observability" / "screenshots").glob("*.png")
    )
    assert len(pngs) == 2
    # Strict pattern check — same regex E2's screenshot tests use.
    pattern = re.compile(
        r"^full-run_\d{4}-\d{2}-\d{2}T\d{4}_"
        r"experiment-tenant-observability_(run-start|run-end)\.png$"
    )
    for p in pngs:
        assert pattern.match(p.name), (
            f"filename {p.name!r} does not match the E2-parity pattern"
        )


# ---------------------------------------------------------------------------
# Existing tests stay green — sanity guard
# ---------------------------------------------------------------------------


def test_dry_run_default_still_produces_140_receipts_with_no_observability_tree(
    tmp_path: Path, grafana_env, stub_grafana
):
    """Existing 43-test invariant: ``--scale dry-run`` (default) still
    produces 140 receipts and NO observability artefacts. This is the
    test_phase_2_scale matrix-shape invariant restated in this file as
    a guard against the wiring drifting it."""
    run_dir = _dispatch_dry(
        tmp_path, scale="dry-run", run_id="obs-back-compat-dry-run"
    )

    total = 0
    for arm, expected_n in (
        ("arm_a", 30),
        ("arm_b", 30),
        ("arm_c", 30),
        ("l4_without_nudge", 30),
        ("diagnostic_primary", 10),
        ("diagnostic_claude", 10),
    ):
        bundles = sorted((run_dir / arm).glob("*.bundle.json"))
        assert len(bundles) == expected_n, (
            f"arm {arm!r}: expected {expected_n}, got {len(bundles)}"
        )
        total += len(bundles)
    assert total == 140
    # Default dry-run mode never lands an observability tree.
    assert not (run_dir / "observability").exists()
    assert len(stub_grafana.calls) == 0
