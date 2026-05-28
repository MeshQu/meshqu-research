"""Tests for the ``--scale`` flag added to ``dry_run_e3.py`` / the
matching scale-awareness added to ``verify_dry_run_e3.py``.

Goals:

  1. **Lock the per-scale matrix shape.** A parametrized end-to-end
     test fires the driver in ``--dry`` mode at each scale and asserts
     the per-arm bundle count + total. This is the discipline
     carry-forward: any future "simplify the matrix" refactor trips
     this test.

  2. **Lock the summary filename + title per scale.** Dry-run mode
     writes ``dry-run-summary.{md,json}`` and an H1 of ``# E3 dry-run …``;
     phase-2 mode writes ``phase-2-summary.{md,json}`` and an H1 of
     ``# E3 Phase 2 …``. Sam's directive: "the paste-back artefact name
     shouldn't lie about which scale produced it."

  3. **Lock phase-2 main-arm record source.** Main arms in phase-2
     iterate the full 283-record corpus from
     ``substrate_cache.load_cached_records``, NOT the locked diagnostic
     subset. Diagnostic arms still read the locked subset.

  4. **Lock verifier scale-awareness.** ``verify_dry_run_e3.verify_run``
     infers the scale from the summary JSON when not passed explicitly
     and asserts the per-arm counts + completeness against the right
     OCID set.

No live API calls. Stubbed end-to-end via the autouse fixture that
swaps in fixture-backed records when the E1 archive is absent (see
``conftest.py``).
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

import dry_run_e3
import verify_dry_run_e3


# ---------------------------------------------------------------------------
# Per-scale matrix shape — the lock-in test the package spec calls for
# ---------------------------------------------------------------------------


def _list_bundles(run_dir: Path, arm: str) -> list[Path]:
    return sorted((run_dir / arm).glob("*.bundle.json"))


def _dispatch_dry(
    tmp_path: Path, *, scale: str, run_id: str
) -> Path:
    """Drive the dry_run_e3 driver in --dry mode at the given scale.
    Returns the run directory."""
    rc = dry_run_e3.main(
        [
            "--scale", scale,
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", run_id,
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0, f"driver returned {rc} for --scale {scale}"
    return tmp_path / "runs" / run_id


@pytest.mark.parametrize(
    "scale,expected",
    [
        (
            "dry-run",
            {
                "arm_a": 30,
                "arm_b": 30,
                "arm_c": 30,
                "l4_without_nudge": 30,
                "diagnostic_primary": 10,
                "diagnostic_claude": 10,
                "total": 140,
            },
        ),
        (
            "phase-2",
            {
                "arm_a": 283,
                "arm_b": 283,
                "arm_c": 283,
                "l4_without_nudge": 283,
                "diagnostic_primary": 100,
                "diagnostic_claude": 100,
                "total": 1332,
            },
        ),
    ],
    ids=["scale=dry-run (140)", "scale=phase-2 (1332)"],
)
def test_driver_matrix_shape_per_scale(
    scale: str, expected: dict[str, int], tmp_path: Path
):
    """Lock-in: each scale produces exactly its specified matrix when
    fired in --dry mode. 140 receipts for dry-run; 1,332 for phase-2.

    A future refactor that tries to "simplify the matrix" trips this
    test."""
    run_dir = _dispatch_dry(tmp_path, scale=scale, run_id=f"shape-{scale}")

    total = 0
    for arm, count in expected.items():
        if arm == "total":
            continue
        bundles = _list_bundles(run_dir, arm)
        assert len(bundles) == count, (
            f"--scale {scale}: arm {arm!r} expected {count} bundles, "
            f"got {len(bundles)}"
        )
        total += len(bundles)
    assert total == expected["total"], (
        f"--scale {scale}: expected total {expected['total']}, got {total}"
    )


# ---------------------------------------------------------------------------
# Summary filename + H1 title per scale
# ---------------------------------------------------------------------------


def test_dry_run_scale_writes_dry_run_summary_files(tmp_path: Path):
    """``--scale dry-run`` writes ``dry-run-summary.{md,json}`` and
    NOT ``phase-2-summary.*``. H1 title carries 'E3 dry-run'."""
    run_dir = _dispatch_dry(tmp_path, scale="dry-run", run_id="filename-dry")
    md_path = run_dir / "dry-run-summary.md"
    json_path = run_dir / "dry-run-summary.json"
    assert md_path.exists(), "dry-run-summary.md missing"
    assert json_path.exists(), "dry-run-summary.json missing"
    assert not (run_dir / "phase-2-summary.md").exists()
    assert not (run_dir / "phase-2-summary.json").exists()
    md_head = md_path.read_text(encoding="utf-8").splitlines()[0]
    assert md_head.startswith("# E3 dry-run —"), (
        f"unexpected H1 in dry-run summary: {md_head!r}"
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["scale"] == "dry-run"
    assert payload["expected_total_receipts"] == 140


def test_phase_2_scale_writes_phase_2_summary_files(tmp_path: Path):
    """``--scale phase-2`` writes ``phase-2-summary.{md,json}`` and
    NOT ``dry-run-summary.*``. H1 title carries 'E3 Phase 2'."""
    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="filename-phase-2")
    md_path = run_dir / "phase-2-summary.md"
    json_path = run_dir / "phase-2-summary.json"
    assert md_path.exists(), "phase-2-summary.md missing"
    assert json_path.exists(), "phase-2-summary.json missing"
    assert not (run_dir / "dry-run-summary.md").exists()
    assert not (run_dir / "dry-run-summary.json").exists()
    md_head = md_path.read_text(encoding="utf-8").splitlines()[0]
    assert md_head.startswith("# E3 Phase 2 —"), (
        f"unexpected H1 in phase-2 summary: {md_head!r}"
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["scale"] == "phase-2"
    assert payload["expected_total_receipts"] == 1332
    # Phase-2 summary surfaces the Phase-2 totals section (no further
    # extrapolation since the receipts ARE the receipts).
    md_text = md_path.read_text(encoding="utf-8")
    assert "## Phase 2 totals" in md_text
    # Phase-2 summary surfaces the dry-run → Phase-2 accuracy header
    # (will be 'n/a (no baseline)' rows until DRY_RUN_…BASELINE is pinned).
    assert "## Dry-run → Phase 2 accuracy" in md_text
    # Phase-2 summary does NOT carry the dry-run-only smoke→dry-run
    # accuracy or dry-run→phase-2 extrapolation sections.
    assert "## Smoke → dry-run accuracy" not in md_text
    assert "## Dry-run → Phase 2 extrapolation" not in md_text


def test_dry_run_summary_carries_extrapolation_only_in_dry_run_mode(
    tmp_path: Path,
):
    """The dry-run-only sections (smoke→dry-run accuracy +
    dry-run→Phase-2 extrapolation) appear in dry-run summaries and NOT
    in phase-2 summaries."""
    run_dir = _dispatch_dry(tmp_path, scale="dry-run", run_id="extrap-dry")
    md = (run_dir / "dry-run-summary.md").read_text(encoding="utf-8")
    assert "## Smoke → dry-run accuracy" in md
    assert "## Dry-run → Phase 2 extrapolation" in md
    # And NOT the phase-2 accuracy header.
    assert "## Dry-run → Phase 2 accuracy" not in md


# ---------------------------------------------------------------------------
# Phase-2 OCID source — main arms iterate the FULL corpus, not the
# locked diagnostic subset
# ---------------------------------------------------------------------------


def test_phase_2_main_arms_iterate_full_corpus(tmp_path: Path):
    """Main arms in --scale phase-2 see the full 283-OCID corpus from
    substrate_cache.load_cached_records, NOT positions 0..29 of the
    locked diagnostic subset."""
    from meshqu_runner.diagnostic.scaled import load_diagnostic_subset
    from meshqu_runner.substrate_cache import load_cached_records

    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="phase-2-corpus")

    repo_dir = _RUNNER_DIR.parents[1]
    expected_full_corpus_ocids = {cr.ocid for cr in load_cached_records(repo_dir)}
    locked_subset_first_30 = set(load_diagnostic_subset()[:30])

    for arm in dry_run_e3.MAIN_ARMS:
        bundles = [json.loads(p.read_text("utf-8")) for p in _list_bundles(run_dir, arm)]
        actual_ocids = {b["ocid"] for b in bundles}
        assert actual_ocids == expected_full_corpus_ocids, (
            f"--scale phase-2 / arm {arm!r}: OCID set does not match the "
            f"full E1 corpus from substrate_cache.load_cached_records"
        )
        # Sanity: the actual set is much bigger than the dry-run subset.
        assert actual_ocids > locked_subset_first_30, (
            f"--scale phase-2 / arm {arm!r}: main arm appears to be "
            "still iterating the diagnostic subset (regression)"
        )


def test_phase_2_diagnostic_arms_iterate_full_100_subset(tmp_path: Path):
    """Diagnostic arms in --scale phase-2 see positions 0..99 of the
    locked diagnostic subset (the full 100-OCID list), NOT positions
    0..9 (the dry-run slice)."""
    from meshqu_runner.diagnostic.scaled import load_diagnostic_subset

    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="phase-2-diag")

    locked_subset = load_diagnostic_subset()
    expected_diag = set(locked_subset[:100])
    locked_subset_first_10 = set(locked_subset[:10])

    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        bundles = [json.loads(p.read_text("utf-8")) for p in _list_bundles(run_dir, arm)]
        actual_ocids = {b["ocid"] for b in bundles}
        assert actual_ocids == expected_diag, (
            f"--scale phase-2 / arm {arm!r}: diagnostic OCID set does "
            "not match positions 0..99 of the locked subset"
        )
        assert actual_ocids > locked_subset_first_10, (
            f"--scale phase-2 / arm {arm!r}: diagnostic arm appears to "
            "still be iterating positions 0..9 (regression)"
        )


# ---------------------------------------------------------------------------
# Run-id default per scale (no --run-id override)
# ---------------------------------------------------------------------------


def test_run_id_default_is_scale_keyed(tmp_path: Path, monkeypatch):
    """When --run-id is omitted, the default carries the scale prefix:
    'dry-run-<…>-Z' for dry-run; 'phase-2-<…>-Z' for phase-2."""
    # Freeze the timestamp slug so we can match deterministically.
    monkeypatch.setattr(
        dry_run_e3, "_utc_timestamp_slug", lambda: "20260601T120000-Z"
    )

    # Dispatch dry-run without --run-id.
    rc = dry_run_e3.main(
        [
            "--scale", "dry-run",
            "--dry",
            "--results-dir", str(tmp_path / "dr"),
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0
    dr_runs = sorted((tmp_path / "dr" / "runs").iterdir())
    assert len(dr_runs) == 1
    assert dr_runs[0].name == "dry-run-20260601T120000-Z"

    # Dispatch phase-2 without --run-id.
    rc = dry_run_e3.main(
        [
            "--scale", "phase-2",
            "--dry",
            "--results-dir", str(tmp_path / "p2"),
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0
    p2_runs = sorted((tmp_path / "p2" / "runs").iterdir())
    assert len(p2_runs) == 1
    assert p2_runs[0].name == "phase-2-20260601T120000-Z"


# ---------------------------------------------------------------------------
# Verifier — scale-awareness
# ---------------------------------------------------------------------------


def test_verifier_infers_scale_from_phase_2_summary(tmp_path: Path):
    """``verify_run(run_dir)`` (no explicit scale) reads
    phase-2-summary.json → infers scale=phase-2 → asserts 1,332 PASS."""
    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="verifier-infer")
    result = verify_dry_run_e3.verify_run(run_dir)
    assert result.scale == "phase-2"
    assert result.passed_count == 1332, (
        f"expected 1332 PASS, got {result.passed_count}; first failure: "
        f"{result.first_failure}"
    )
    assert result.failed_count == 0
    assert len(result.expected_main_ocids) == 283
    assert len(result.expected_diagnostic_ocids) == 100


def test_verifier_explicit_scale_overrides_inference(tmp_path: Path):
    """Passing ``scale='phase-2'`` against a phase-2 run produces the
    same 1,332-PASS result the inference path produces — explicit and
    inferred are equivalent on a well-formed run dir."""
    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="verifier-explicit")
    result = verify_dry_run_e3.verify_run(run_dir, scale="phase-2")
    assert result.scale == "phase-2"
    assert result.passed_count == 1332
    assert result.failed_count == 0


def test_verifier_dry_run_still_passes_at_140(tmp_path: Path):
    """Verifier on a dry-run dir continues to assert 140 PASS / 0 FAIL.
    Sanity check that the scale generalisation didn't regress the
    default path."""
    run_dir = _dispatch_dry(tmp_path, scale="dry-run", run_id="verifier-dry-back-compat")
    result = verify_dry_run_e3.verify_run(run_dir)
    assert result.scale == "dry-run"
    assert result.passed_count == 140
    assert result.failed_count == 0
    assert len(result.expected_main_ocids) == 30
    assert len(result.expected_diagnostic_ocids) == 10


def test_verifier_cli_emits_phase_2_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """CLI surface: ``verify_dry_run_e3.py <phase-2-run> --json`` emits a
    payload with total=1332 + scale='phase-2'."""
    run_dir = _dispatch_dry(tmp_path, scale="phase-2", run_id="verifier-cli-phase-2")
    capsys.readouterr()
    rc = verify_dry_run_e3.main([str(run_dir), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["total"] == 1332
    assert payload["passed"] == 1332
    assert payload["failed"] == 0
    assert payload["scale"] == "phase-2"
    assert payload["all_stubs"] is True
    assert len(payload["expected_main_ocids"]) == 283
    assert len(payload["expected_diagnostic_ocids"]) == 100


def test_verifier_per_scale_counts_lookup():
    """Module-level helpers: per-scale expected total + per-arm counts
    are consistent and total to the right value."""
    assert verify_dry_run_e3.expected_total_for("dry-run") == 140
    assert verify_dry_run_e3.expected_total_for("phase-2") == 1332
    dr_counts = verify_dry_run_e3.expected_counts_for("dry-run")
    p2_counts = verify_dry_run_e3.expected_counts_for("phase-2")
    assert sum(dr_counts.values()) == 140
    assert sum(p2_counts.values()) == 1332
    assert dr_counts["arm_a"] == 30
    assert p2_counts["arm_a"] == 283
    assert dr_counts["diagnostic_primary"] == 10
    assert p2_counts["diagnostic_primary"] == 100
