"""Tests for E3-010 — the smoke driver + the validator.

Goals (per the package spec + the agent prompt):

  1. ``smoke_e3.py --dry`` exercises **all 6 arms × the matrix end-to-
     end** with stubs in place — 14 receipts emitted under the
     expected arm subdirs, ``smoke-summary.md`` written, no live API
     calls.

  2. Per-arm integrity markers are correct: every bundle's
     ``context_fields_canonical_json`` carries the locked
     l3_arm / nudge_excised / model_id / diagnostic /
     policy_permutation_seed values per arm.

  3. ``verify_smoke_e3.verify_run`` returns PASS=14 / FAIL=0 over the
     produced run dir (with implicit allow-stub since every bundle is
     a stub in --dry mode).

  4. ``verify_smoke_e3.verify_run`` returns FAIL when an integrity
     marker drifts — sanity-check that the assertion is actually
     load-bearing.

  5. ``smoke_e3.build_extrapolation_table`` produces a row per arm
     with the right receipt counts at smoke/dry-run/full-run scales.

  6. Live-mode env-var validation refuses to run without the five
     required env vars.

These tests do NOT make live API calls. The agent stays stubbed; the
MeshQu client stays stubbed; the file-system writes go to ``tmp_path``.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the ``scripts`` directory importable (the scripts themselves are
# top-level Python files, not a package).
_RUNNER_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _RUNNER_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

import smoke_e3
import verify_smoke_e3
from meshqu_runner.diagnostic.permute_policy import LOCKED_PERMUTATION_SEED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_bundles(run_dir: Path, arm_name: str) -> list[Path]:
    return sorted((run_dir / arm_name).glob("*.bundle.json"))


def _load_bundle(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _bundle_fields(bundle: dict) -> dict:
    return json.loads(bundle["context_fields_canonical_json"])


# ---------------------------------------------------------------------------
# smoke_e3 — end-to-end dry pass
# ---------------------------------------------------------------------------


def test_smoke_e3_dry_writes_14_bundles_under_correct_subdirs(tmp_path: Path):
    """The matrix: 4 main arms × 3 OCIDs + 2 diagnostic arms × 1 OCID
    = 14 receipts, distributed across six arm subdirs."""
    rc = smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-test-dry",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0

    run_dir = tmp_path / "runs" / "smoke-test-dry"
    assert run_dir.exists()

    # 3 receipts per main arm, 1 per diagnostic arm.
    for arm in smoke_e3.MAIN_ARMS:
        bundles = _list_bundles(run_dir, arm)
        assert len(bundles) == 3, f"{arm!r}: expected 3 bundles, got {len(bundles)}"
    for arm in smoke_e3.DIAGNOSTIC_ARMS:
        bundles = _list_bundles(run_dir, arm)
        assert len(bundles) == 1, f"{arm!r}: expected 1 bundle, got {len(bundles)}"

    # smoke-summary.md + smoke-summary.json both present.
    assert (run_dir / "smoke-summary.md").exists()
    assert (run_dir / "smoke-summary.json").exists()

    # Per-arm manifest snapshots — one per arm.
    manifests_dir = run_dir / "manifests"
    for arm in smoke_e3.MAIN_ARMS + smoke_e3.DIAGNOSTIC_ARMS:
        assert (manifests_dir / f"{arm}.manifest.json").exists(), f"missing manifest for {arm}"


def test_smoke_e3_dry_first_three_ocids_match_locked_subset(tmp_path: Path):
    """The smoke OCIDs are positions 0..2 of
    ``planning/diagnostic_subset.json``, in that order."""
    from meshqu_runner.diagnostic.scaled import load_diagnostic_subset

    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-test-ocids",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    run_dir = tmp_path / "runs" / "smoke-test-ocids"
    locked = load_diagnostic_subset()[:3]
    # Every main arm should carry exactly those three OCIDs across its
    # three bundles.
    for arm in smoke_e3.MAIN_ARMS:
        bundles = [_load_bundle(b) for b in _list_bundles(run_dir, arm)]
        assert sorted(b["ocid"] for b in bundles) == sorted(locked), (
            f"{arm!r}: OCIDs do not match locked positions 0..2"
        )
    # The diagnostic arms each only run on OCID 0.
    for arm in smoke_e3.DIAGNOSTIC_ARMS:
        bundles = [_load_bundle(b) for b in _list_bundles(run_dir, arm)]
        assert len(bundles) == 1
        assert bundles[0]["ocid"] == locked[0], (
            f"{arm!r}: diagnostic OCID should be position 0; got {bundles[0]['ocid']!r}"
        )


@pytest.mark.parametrize(
    "arm_name,expected",
    [
        ("arm_a", {"l3_arm": "A", "nudge_excised": False, "model_id": "gpt-5.4-2026-03-05", "diagnostic": False, "policy_permutation_seed": None}),
        ("arm_b", {"l3_arm": "B", "nudge_excised": False, "model_id": "gpt-5.4-2026-03-05", "diagnostic": False, "policy_permutation_seed": None}),
        ("arm_c", {"l3_arm": "C", "nudge_excised": False, "model_id": "gpt-5.4-2026-03-05", "diagnostic": False, "policy_permutation_seed": None}),
        ("l4_without_nudge", {"l3_arm": None, "nudge_excised": True, "model_id": "gpt-5.4-2026-03-05", "diagnostic": False, "policy_permutation_seed": None}),
        ("diagnostic_primary", {"l3_arm": None, "nudge_excised": False, "model_id": "gpt-5.4-2026-03-05", "diagnostic": True, "policy_permutation_seed": LOCKED_PERMUTATION_SEED}),
        ("diagnostic_claude", {"l3_arm": None, "nudge_excised": False, "model_id": "claude-opus-4-7", "diagnostic": True, "policy_permutation_seed": LOCKED_PERMUTATION_SEED}),
    ],
)
def test_smoke_e3_per_arm_integrity_markers(tmp_path: Path, arm_name: str, expected: dict):
    """Every bundle for ``arm_name`` carries the locked integrity
    markers per the master plan matrix."""
    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", f"smoke-test-markers-{arm_name}",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    run_dir = tmp_path / "runs" / f"smoke-test-markers-{arm_name}"
    bundles = _list_bundles(run_dir, arm_name)
    assert bundles, f"no bundles for arm {arm_name!r}"
    for bundle_path in bundles:
        fields = _bundle_fields(_load_bundle(bundle_path))
        for key, want in expected.items():
            assert fields.get(key) == want, (
                f"{arm_name!r} bundle {bundle_path.name}: marker {key!r} "
                f"= {fields.get(key)!r}, expected {want!r}"
            )
        # prereg_tag is always v0.3-predictions-locked.
        assert fields.get("prereg_tag") == "v0.3-predictions-locked"


def test_smoke_e3_summary_md_includes_matrix_and_extrapolation(tmp_path: Path):
    """The Markdown summary carries the run id, the smoke OCIDs, the
    per-arm latency block, and the cost-extrapolation table."""
    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-test-md",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    run_dir = tmp_path / "runs" / "smoke-test-md"
    md = (run_dir / "smoke-summary.md").read_text(encoding="utf-8")

    # Run id + matrix
    assert "smoke-test-md" in md
    assert "Receipts written:** 14" in md
    assert "Errors:** 0" in md
    # Per-arm rows
    for arm in smoke_e3.MAIN_ARMS + smoke_e3.DIAGNOSTIC_ARMS:
        assert f"`{arm}`" in md
    # Extrapolation header
    assert "Cost extrapolation" in md
    # Pre-reg tag mention
    assert "v0.3-predictions-locked" in md


def test_smoke_e3_summary_json_round_trips_with_extrapolation(tmp_path: Path):
    """The JSON summary mirrors the markdown and parses cleanly."""
    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-test-json",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    run_dir = tmp_path / "runs" / "smoke-test-json"
    payload = json.loads((run_dir / "smoke-summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "smoke-test-json"
    assert payload["expected_total_receipts"] == 14
    assert payload["total_receipts_written"] == 14
    assert payload["total_errors"] == 0
    assert payload["is_dry"] is True
    assert payload["prereg_tag"] == "v0.3-predictions-locked"
    # Extrapolation has six rows (one per arm).
    arms_in_extrap = {row["arm"] for row in payload["extrapolation"]}
    assert arms_in_extrap == set(smoke_e3.MAIN_ARMS + smoke_e3.DIAGNOSTIC_ARMS)
    # Each main-arm row carries the dry-run + full-run receipt counts
    # per the spec (30 and 283).
    for row in payload["extrapolation"]:
        if row["arm"] in smoke_e3.MAIN_ARMS:
            assert row["dry_run_receipts"] == 30
            assert row["full_run_receipts"] == 283
        else:
            assert row["dry_run_receipts"] == 10
            assert row["full_run_receipts"] == 100


def test_smoke_e3_summary_arm_record_counts_match_matrix(tmp_path: Path):
    """The accountings block in the JSON summary records 3 records per
    main arm and 1 per diagnostic arm — sanity-check that the matrix
    survives the round-trip into the summary."""
    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-test-counts",
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    run_dir = tmp_path / "runs" / "smoke-test-counts"
    payload = json.loads((run_dir / "smoke-summary.json").read_text(encoding="utf-8"))
    for arm in smoke_e3.MAIN_ARMS:
        assert payload["accountings"][arm]["record_count"] == 3
        assert payload["accountings"][arm]["receipts_written"] == 3
    for arm in smoke_e3.DIAGNOSTIC_ARMS:
        assert payload["accountings"][arm]["record_count"] == 1
        assert payload["accountings"][arm]["receipts_written"] == 1


# ---------------------------------------------------------------------------
# Cost extrapolation — exercised even in stub mode
# ---------------------------------------------------------------------------


def test_extrapolation_table_zero_tokens_in_stub_mode():
    """Stub mode reports prompt_tokens=0 for every record. The
    extrapolation table therefore reports 0 projected tokens at
    every scale — but the table structure is fully populated (rows,
    receipt counts, mean) for downstream live runs."""
    accountings: dict[str, smoke_e3.ArmAccounting] = {
        arm: smoke_e3.ArmAccounting(arm_name=arm, record_count=3)
        for arm in smoke_e3.MAIN_ARMS
    }
    for arm in smoke_e3.DIAGNOSTIC_ARMS:
        accountings[arm] = smoke_e3.ArmAccounting(arm_name=arm, record_count=1)
    # Simulate 3 stub receipts per main arm (zero tokens), 1 per diag.
    for arm in smoke_e3.MAIN_ARMS:
        for _ in range(3):
            accountings[arm].prompt_tokens.append(0)
            accountings[arm].latencies_ms.append(0)
            accountings[arm].receipts_written += 1
    for arm in smoke_e3.DIAGNOSTIC_ARMS:
        accountings[arm].prompt_tokens.append(0)
        accountings[arm].latencies_ms.append(0)
        accountings[arm].receipts_written += 1

    rows = smoke_e3.build_extrapolation_table(accountings)
    by_arm = {row["arm"]: row for row in rows}
    assert by_arm["arm_a"]["smoke_receipts"] == 3
    assert by_arm["arm_a"]["dry_run_receipts"] == 30
    assert by_arm["arm_a"]["full_run_receipts"] == 283
    assert by_arm["diagnostic_primary"]["smoke_receipts"] == 1
    assert by_arm["diagnostic_primary"]["dry_run_receipts"] == 10
    assert by_arm["diagnostic_primary"]["full_run_receipts"] == 100
    # Stub-mode tokens are zero everywhere.
    for row in rows:
        assert row["smoke_prompt_tokens_total"] == 0
        assert row["dry_run_prompt_tokens_projected"] == 0
        assert row["full_run_prompt_tokens_projected"] == 0


def test_extrapolation_table_scales_linearly_with_observed_tokens():
    """Hand-built accounting: 100 prompt tokens per main-arm record →
    dry-run projection 3,000, full-run 28,300. Diagnostic with 50 tokens
    → dry-run 500, full-run 5,000."""
    accountings: dict[str, smoke_e3.ArmAccounting] = {}
    arm_a = smoke_e3.ArmAccounting(arm_name="arm_a", record_count=3)
    arm_a.receipts_written = 3
    arm_a.prompt_tokens = [100, 100, 100]
    arm_a.latencies_ms = [500, 600, 700]
    accountings["arm_a"] = arm_a

    diag = smoke_e3.ArmAccounting(arm_name="diagnostic_primary", record_count=1)
    diag.receipts_written = 1
    diag.prompt_tokens = [50]
    diag.latencies_ms = [800]
    accountings["diagnostic_primary"] = diag

    rows = smoke_e3.build_extrapolation_table(accountings)
    by_arm = {row["arm"]: row for row in rows}

    assert by_arm["arm_a"]["smoke_prompt_tokens_total"] == 300
    assert by_arm["arm_a"]["smoke_prompt_tokens_mean_per_record"] == 100.0
    assert by_arm["arm_a"]["dry_run_prompt_tokens_projected"] == 3000
    assert by_arm["arm_a"]["full_run_prompt_tokens_projected"] == 28300

    assert by_arm["diagnostic_primary"]["smoke_prompt_tokens_total"] == 50
    assert by_arm["diagnostic_primary"]["dry_run_prompt_tokens_projected"] == 500
    assert by_arm["diagnostic_primary"]["full_run_prompt_tokens_projected"] == 5000


# ---------------------------------------------------------------------------
# Live-mode env var validation
# ---------------------------------------------------------------------------


def test_smoke_e3_refuses_live_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Without ``--dry`` and with no env vars, the driver must refuse
    to start (SystemExit). Belt-and-braces against an "accidental live
    run on the wrong shell" — the package spec's
    'no partial-config runs' requirement."""
    for name in smoke_e3.REQUIRED_LIVE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as exc:
        smoke_e3.main([
            "--results-dir", str(tmp_path),
            "--run-id", "smoke-live-noenv",
        ])
    # SystemExit's value carries the failure message.
    assert "live mode requires" in str(exc.value)


# ---------------------------------------------------------------------------
# verify_smoke_e3 — assertion semantics
# ---------------------------------------------------------------------------


def _make_dry_run(tmp_path: Path, run_id: str = "verify-dry") -> Path:
    smoke_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", run_id,
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    return tmp_path / "runs" / run_id


def test_verify_run_passes_all_14_on_dry_smoke(tmp_path: Path):
    """The dry-mode pipeline writes 14 stub bundles; verify_run
    treats every-stub as implicit allow-stub and asserts the markers
    correctly. All 14 PASS."""
    run_dir = _make_dry_run(tmp_path)
    result = verify_smoke_e3.verify_run(run_dir)
    assert result.passed_count == 14
    assert result.failed_count == 0
    assert result.all_stubs is True


def test_verify_run_fails_when_marker_drift(tmp_path: Path):
    """Mutate a bundle's ``l3_arm`` marker → verify_run should report
    the mismatch and stop on the first failure."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-drift")
    arm_a_bundle = _list_bundles(run_dir, "arm_a")[0]
    bundle = _load_bundle(arm_a_bundle)
    fields = _bundle_fields(bundle)
    # Mutate the integrity marker.
    fields["l3_arm"] = "Z"
    bundle["context_fields_canonical_json"] = json.dumps(
        fields, sort_keys=True, separators=(",", ":")
    )
    arm_a_bundle.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")

    result = verify_smoke_e3.verify_run(run_dir, stop_on_first_failure=True)
    assert result.failed_count >= 1
    assert result.first_failure is not None
    assert result.first_failure.arm_name == "arm_a"
    assert any("l3_arm" in err for err in result.first_failure.errors)


def test_verify_run_fails_when_diagnostic_seed_drifts(tmp_path: Path):
    """If a diagnostic bundle's ``policy_permutation_seed`` is anything
    other than ``LOCKED_PERMUTATION_SEED`` (0), the verifier must
    surface the drift."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-seed")
    diag_bundle = _list_bundles(run_dir, "diagnostic_primary")[0]
    bundle = _load_bundle(diag_bundle)
    fields = _bundle_fields(bundle)
    fields["policy_permutation_seed"] = 99  # arbitrary non-zero
    bundle["context_fields_canonical_json"] = json.dumps(
        fields, sort_keys=True, separators=(",", ":")
    )
    diag_bundle.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")

    result = verify_smoke_e3.verify_run(run_dir, stop_on_first_failure=False)
    assert result.failed_count >= 1
    diag_failures = [r for r in result.reports if r.arm_name == "diagnostic_primary" and not r.passed]
    assert diag_failures, "expected diagnostic_primary failure on seed drift"
    assert any("policy_permutation_seed" in err for err in diag_failures[0].errors)


def test_verify_run_fails_when_count_short(tmp_path: Path):
    """Delete a bundle to drop the per-arm count below the matrix
    expectation. The verifier must surface the count mismatch."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-short")
    arm_a_bundles = _list_bundles(run_dir, "arm_a")
    arm_a_bundles[0].unlink()

    result = verify_smoke_e3.verify_run(run_dir, stop_on_first_failure=False)
    # The count assertion synthesises a failure report per arm with
    # the wrong count.
    count_failures = [
        r for r in result.reports
        if r.arm_name == "arm_a" and any("expected 3" in e for e in r.errors)
    ]
    assert count_failures, "expected arm_a count-mismatch failure"


def test_verify_run_no_bundles(tmp_path: Path):
    """Empty run dir → single synthetic FAIL with 'no bundles'."""
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    result = verify_smoke_e3.verify_run(run_dir)
    assert result.failed_count == 1
    assert result.first_failure is not None
    assert any("no bundles" in e for e in result.first_failure.errors)


def test_verify_main_returns_zero_on_dry_run_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """End-to-end through ``verify_smoke_e3.main`` (the actual CLI
    surface): exit code 0 on a clean dry-run, with the expected total
    line in stdout."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-main")
    # Drain stdout from the smoke driver so we only inspect the
    # verifier's output below.
    capsys.readouterr()
    rc = verify_smoke_e3.main([str(run_dir)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "PASS: 14" in captured.out
    assert "FAIL: 0" in captured.out


def test_verify_main_emits_json_when_requested(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """``--json`` switches output to a parseable JSON object."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-json")
    # Drain stdout from the dry-run smoke driver so the JSON we test
    # against is only the verifier's output.
    capsys.readouterr()
    rc = verify_smoke_e3.main([str(run_dir), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["total"] == 14
    assert payload["passed"] == 14
    assert payload["failed"] == 0
    assert payload["all_stubs"] is True


# ---------------------------------------------------------------------------
# Trusted-key pinning regression — the experiment-tenant kid is what
# verify.meshqu.com trusts. Drift between this script + the verify app
# would be a wire-format bug — the assertion here mirrors E2's
# verify_smoke_bundles.py pinning.
# ---------------------------------------------------------------------------


def test_expected_kid_matches_experiment_tenant():
    assert verify_smoke_e3.EXPECTED_KID == "meshqu-experiment-procurement-2026-05"
    assert verify_smoke_e3.EXPECTED_KID in verify_smoke_e3.TRUSTED_KEYS_SPKI_DER_B64
