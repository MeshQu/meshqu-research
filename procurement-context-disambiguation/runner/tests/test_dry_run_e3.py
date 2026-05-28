"""Tests for E3-011 — the dry-run driver + the validator.

Goals (per the package spec + the agent prompt):

  1. ``dry_run_e3.py --dry`` exercises **all 6 arms × the dry-run
     matrix end-to-end** with stubs in place — 140 receipts emitted
     under the expected arm subdirs, ``dry-run-summary.md`` written,
     no live API calls.

  2. Per-arm integrity markers are correct: every bundle's
     ``context_fields_canonical_json`` carries the locked
     l3_arm / nudge_excised / model_id / diagnostic /
     policy_permutation_seed values per arm. (Re-asserts the smoke
     verifier's table at the dry-run scale.)

  3. ``verify_dry_run_e3.verify_run`` returns PASS=140 / FAIL=0 over
     the produced run dir (with implicit allow-stub since every
     bundle is a stub in --dry mode).

  4. ``verify_dry_run_e3.verify_run`` returns FAIL when an integrity
     marker drifts, when the OCID set is incomplete, when an arm's
     receipt count is short, and when a stub bundle appears in a
     non-stub-allowed run.

  5. Aggregate completeness check (the dry-run-specific addition):
     deleting a bundle to drop one OCID surfaces a "missing OCID"
     completeness violation independent of the count check.

  6. Cost projection logic — smoke→dry-run accuracy ratio + Phase-2
     extrapolation — is exercised in --dry mode with synthetic
     accounting (so the math path runs even with stub agents).

  7. Live-mode env-var validation refuses to run without the five
     required env vars (delegated to smoke_e3's _check_env helper).

These tests do NOT make live API calls. The agent stays stubbed; the
MeshQu client stays stubbed; the file-system writes go to ``tmp_path``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the ``scripts`` directory importable (the scripts themselves are
# top-level Python files, not a package).
_RUNNER_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _RUNNER_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

import dry_run_e3
import verify_dry_run_e3
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


def _make_dry_run(tmp_path: Path, run_id: str = "dry-run-test") -> Path:
    """Drive a full --dry dry-run + return the resulting run_dir."""
    rc = dry_run_e3.main(
        [
            "--dry",
            "--results-dir", str(tmp_path),
            "--run-id", run_id,
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0
    return tmp_path / "runs" / run_id


# ---------------------------------------------------------------------------
# dry_run_e3 — end-to-end dry pass
# ---------------------------------------------------------------------------


def test_dry_run_e3_dry_writes_140_bundles_under_correct_subdirs(tmp_path: Path):
    """The matrix: 4 main arms × 30 OCIDs + 2 diagnostic arms × 10 OCIDs
    = 140 receipts, distributed across six arm subdirs."""
    run_dir = _make_dry_run(tmp_path, run_id="dry-test-counts")

    # 30 receipts per main arm.
    for arm in dry_run_e3.MAIN_ARMS:
        bundles = _list_bundles(run_dir, arm)
        assert len(bundles) == 30, (
            f"{arm!r}: expected 30 bundles, got {len(bundles)}"
        )
    # 10 receipts per diagnostic arm.
    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        bundles = _list_bundles(run_dir, arm)
        assert len(bundles) == 10, (
            f"{arm!r}: expected 10 bundles, got {len(bundles)}"
        )

    # Both summaries exist.
    assert (run_dir / "dry-run-summary.md").exists()
    assert (run_dir / "dry-run-summary.json").exists()

    # Per-arm manifest snapshots — one per arm.
    manifests_dir = run_dir / "manifests"
    for arm in dry_run_e3.MAIN_ARMS + dry_run_e3.DIAGNOSTIC_ARMS:
        assert (manifests_dir / f"{arm}.manifest.json").exists(), (
            f"missing manifest for {arm}"
        )


def test_dry_run_e3_ocids_match_locked_positions(tmp_path: Path):
    """Main arms see positions 0..29 of the locked subset;
    diagnostic arms see positions 0..9."""
    from meshqu_runner.diagnostic.scaled import load_diagnostic_subset

    run_dir = _make_dry_run(tmp_path, run_id="dry-test-ocids")
    locked = load_diagnostic_subset()
    expected_main = set(locked[:30])
    expected_diag = set(locked[:10])

    for arm in dry_run_e3.MAIN_ARMS:
        bundles = [_load_bundle(b) for b in _list_bundles(run_dir, arm)]
        actual = {b["ocid"] for b in bundles}
        assert actual == expected_main, (
            f"{arm!r}: OCID set does not match locked positions 0..29"
        )

    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        bundles = [_load_bundle(b) for b in _list_bundles(run_dir, arm)]
        actual = {b["ocid"] for b in bundles}
        assert actual == expected_diag, (
            f"{arm!r}: OCID set does not match locked positions 0..9"
        )


@pytest.mark.parametrize(
    "arm_name,expected",
    [
        (
            "arm_a",
            {
                "l3_arm": "A", "nudge_excised": False,
                "model_id": "gpt-5.4-2026-03-05",
                "diagnostic": False, "policy_permutation_seed": None,
            },
        ),
        (
            "arm_b",
            {
                "l3_arm": "B", "nudge_excised": False,
                "model_id": "gpt-5.4-2026-03-05",
                "diagnostic": False, "policy_permutation_seed": None,
            },
        ),
        (
            "arm_c",
            {
                "l3_arm": "C", "nudge_excised": False,
                "model_id": "gpt-5.4-2026-03-05",
                "diagnostic": False, "policy_permutation_seed": None,
            },
        ),
        (
            "l4_without_nudge",
            {
                "l3_arm": None, "nudge_excised": True,
                "model_id": "gpt-5.4-2026-03-05",
                "diagnostic": False, "policy_permutation_seed": None,
            },
        ),
        (
            "diagnostic_primary",
            {
                "l3_arm": None, "nudge_excised": False,
                "model_id": "gpt-5.4-2026-03-05",
                "diagnostic": True,
                "policy_permutation_seed": LOCKED_PERMUTATION_SEED,
            },
        ),
        (
            "diagnostic_claude",
            {
                "l3_arm": None, "nudge_excised": False,
                "model_id": "claude-opus-4-7",
                "diagnostic": True,
                "policy_permutation_seed": LOCKED_PERMUTATION_SEED,
            },
        ),
    ],
)
def test_dry_run_e3_per_arm_integrity_markers(
    tmp_path: Path, arm_name: str, expected: dict
):
    """Every bundle for ``arm_name`` carries the locked integrity
    markers per the master plan matrix. Re-asserts at the dry-run
    scale (30 or 10 bundles per arm)."""
    run_dir = _make_dry_run(tmp_path, run_id=f"dry-markers-{arm_name}")
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


def test_dry_run_e3_summary_md_includes_matrix_and_extrapolation(tmp_path: Path):
    """The Markdown summary carries: run id, all 30 main OCIDs, both
    extrapolation tables, the smoke→dry-run accuracy header, the
    aggregate completeness check, the cost-rate caveat."""
    run_dir = _make_dry_run(tmp_path, run_id="dry-md")
    md = (run_dir / "dry-run-summary.md").read_text(encoding="utf-8")

    assert "dry-md" in md
    assert "Receipts written:** 140" in md
    assert "Errors:** 0" in md
    for arm in dry_run_e3.MAIN_ARMS + dry_run_e3.DIAGNOSTIC_ARMS:
        assert f"`{arm}`" in md
    assert "Smoke → dry-run accuracy" in md
    assert "Dry-run → Phase 2 extrapolation" in md
    assert "Aggregate completeness" in md
    assert "v0.3-predictions-locked" in md


def test_dry_run_e3_summary_json_round_trips(tmp_path: Path):
    """The JSON summary mirrors the markdown and parses cleanly."""
    run_dir = _make_dry_run(tmp_path, run_id="dry-json")
    payload = json.loads(
        (run_dir / "dry-run-summary.json").read_text(encoding="utf-8")
    )
    assert payload["run_id"] == "dry-json"
    assert payload["expected_total_receipts"] == 140
    assert payload["total_receipts_written"] == 140
    assert payload["total_errors"] == 0
    assert payload["is_dry"] is True
    assert payload["prereg_tag"] == "v0.3-predictions-locked"
    # Main arms: 30 records / receipts. Diagnostic arms: 10 records.
    for arm in dry_run_e3.MAIN_ARMS:
        assert payload["accountings"][arm]["record_count"] == 30
        assert payload["accountings"][arm]["receipts_written"] == 30
    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        assert payload["accountings"][arm]["record_count"] == 10
        assert payload["accountings"][arm]["receipts_written"] == 10
    # Phase-2 extrapolation rows present for every arm.
    arms_in_extrap = {row["arm"] for row in payload["phase_2_extrapolation"]}
    assert arms_in_extrap == set(
        dry_run_e3.MAIN_ARMS + dry_run_e3.DIAGNOSTIC_ARMS
    )
    # Cost-rate constants are surfaced in the JSON for reproducibility.
    assert (
        payload["cost_rates"]["gpt_5_4"]["usd_per_1k_prompt"]
        == dry_run_e3.GPT_54_USD_PER_1K_PROMPT_TOKENS
    )
    assert (
        payload["cost_rates"]["claude_opus_4_7"]["usd_per_1k_prompt"]
        == dry_run_e3.CLAUDE_OPUS_47_USD_PER_1K_PROMPT_TOKENS
    )


def test_dry_run_e3_completeness_violations_clean_on_dry(tmp_path: Path):
    """On a clean --dry run, the completeness check should pass (zero
    violations) — the driver dispatches against every OCID in the
    locked subset, so every arm's OCIDs match the expected sets."""
    run_dir = _make_dry_run(tmp_path, run_id="dry-completeness-clean")
    payload = json.loads(
        (run_dir / "dry-run-summary.json").read_text(encoding="utf-8")
    )
    assert payload["completeness_violations"] == []


# ---------------------------------------------------------------------------
# Cost projection — exercised even in stub mode via synthetic accounting
# ---------------------------------------------------------------------------


def test_estimate_arm_cost_usd_envelope():
    """Cost helper: 1000 prompt tokens on a GPT-5.4 arm =
    1 * 0.0025 + (1 * 0.25) * 0.01 = 0.005 USD."""
    cost = dry_run_e3.estimate_arm_cost_usd(
        arm_name="arm_a", prompt_tokens_total=1000
    )
    # Prompt: 1.0 * 0.0025 = 0.0025
    # Completion: (1.0 * 0.25) * 0.01 = 0.0025
    # Total: 0.005
    assert abs(cost - 0.005) < 1e-9

    # Claude arm: rates differ (0.015 prompt, 0.075 completion).
    cost_c = dry_run_e3.estimate_arm_cost_usd(
        arm_name="diagnostic_claude", prompt_tokens_total=1000
    )
    # Prompt: 1.0 * 0.015 = 0.015
    # Completion: 0.25 * 0.075 = 0.01875
    # Total: 0.03375
    assert abs(cost_c - 0.03375) < 1e-9


def test_estimate_arm_cost_usd_unknown_arm_returns_zero():
    """Unknown arm name → defensive 0.0 (not a crash). Future arm
    additions must update ``ARM_RATE_TABLE`` explicitly."""
    assert (
        dry_run_e3.estimate_arm_cost_usd(
            arm_name="not-a-real-arm", prompt_tokens_total=1000
        )
        == 0.0
    )


def test_compute_smoke_accuracy_row_within_band():
    """Mean 2000 tokens vs smoke baseline 1821 (arm_a) → ratio
    ~1.098, within ±15% band."""
    row = dry_run_e3.compute_smoke_accuracy_row(
        arm_name="arm_a", dry_run_mean_tokens=2000.0
    )
    assert row["arm"] == "arm_a"
    assert row["smoke_mean"] == 1821.0
    assert abs(row["ratio"] - 2000.0 / 1821.0) < 1e-9
    assert row["within_band"] is True
    assert row["stub_mode"] is False


def test_compute_smoke_accuracy_row_outside_band():
    """Mean 3000 tokens vs smoke baseline 1821 (arm_a) → ratio
    ~1.647, outside ±15% band."""
    row = dry_run_e3.compute_smoke_accuracy_row(
        arm_name="arm_a", dry_run_mean_tokens=3000.0
    )
    assert row["within_band"] is False


def test_compute_smoke_accuracy_row_stub_mode():
    """Stub mode (zero observed tokens) → within_band=None,
    stub_mode=True. The summary writer renders this as 'n/a (stub)'."""
    row = dry_run_e3.compute_smoke_accuracy_row(
        arm_name="arm_a", dry_run_mean_tokens=0.0
    )
    assert row["ratio"] is None
    assert row["within_band"] is None
    assert row["stub_mode"] is True


def test_phase_2_extrapolation_scales_linearly():
    """Hand-built accounting: 100 prompt tokens per arm_a record (30
    records) → dry-run total 3000, Phase-2 projection at 283 records ×
    100 tokens = 28,300 tokens."""
    accountings: dict[str, dry_run_e3.ArmAccounting] = {}
    arm_a = dry_run_e3.ArmAccounting(arm_name="arm_a", record_count=30)
    arm_a.receipts_written = 30
    arm_a.prompt_tokens = [100] * 30
    arm_a.latencies_ms = [500] * 30
    accountings["arm_a"] = arm_a

    diag = dry_run_e3.ArmAccounting(
        arm_name="diagnostic_primary", record_count=10
    )
    diag.receipts_written = 10
    diag.prompt_tokens = [50] * 10
    diag.latencies_ms = [800] * 10
    accountings["diagnostic_primary"] = diag

    rows = dry_run_e3.build_phase_2_extrapolation_table(accountings)
    by_arm = {row["arm"]: row for row in rows}

    assert by_arm["arm_a"]["dry_run_prompt_tokens_total"] == 3000
    assert by_arm["arm_a"]["full_run_receipts"] == 283
    assert by_arm["arm_a"]["full_run_prompt_tokens_projected"] == 28300

    assert by_arm["diagnostic_primary"]["dry_run_prompt_tokens_total"] == 500
    assert by_arm["diagnostic_primary"]["full_run_receipts"] == 100
    assert by_arm["diagnostic_primary"]["full_run_prompt_tokens_projected"] == 5000


def test_phase_2_extrapolation_cost_envelope_present():
    """Synthetic accounting → the extrapolation row carries a non-zero
    Phase-2 $-cost projection for known arms."""
    accountings: dict[str, dry_run_e3.ArmAccounting] = {}
    arm_a = dry_run_e3.ArmAccounting(arm_name="arm_a", record_count=30)
    arm_a.receipts_written = 30
    arm_a.prompt_tokens = [1000] * 30  # 30,000 total tokens
    arm_a.latencies_ms = [500] * 30
    accountings["arm_a"] = arm_a

    rows = dry_run_e3.build_phase_2_extrapolation_table(accountings)
    arm_a_row = next(r for r in rows if r["arm"] == "arm_a")
    # Mean tokens/record = 1000. Phase-2 = 283 * 1000 = 283,000 tokens.
    # Prompt cost = 283 * 0.0025 = 0.7075
    # Completion cost = 283 * 0.25 * 0.01 = 0.7075
    # Total = 1.415
    assert abs(arm_a_row["full_run_usd_cost_projected"] - 1.42) < 0.01


# ---------------------------------------------------------------------------
# Aggregate completeness — driver-level check
# ---------------------------------------------------------------------------


def test_assert_aggregate_completeness_clean():
    """Every OCID present in every applicable arm → empty
    violations list."""
    accountings: dict[str, dry_run_e3.ArmAccounting] = {}
    main_ocids = [f"ocid-{i}" for i in range(30)]
    diag_ocids = main_ocids[:10]
    for arm in dry_run_e3.MAIN_ARMS:
        acc = dry_run_e3.ArmAccounting(arm_name=arm, record_count=30)
        acc.ocids = list(main_ocids)
        accountings[arm] = acc
    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        acc = dry_run_e3.ArmAccounting(arm_name=arm, record_count=10)
        acc.ocids = list(diag_ocids)
        accountings[arm] = acc

    violations = dry_run_e3.assert_aggregate_completeness(
        main_ocids=main_ocids,
        diagnostic_ocids=diag_ocids,
        accountings=accountings,
    )
    assert violations == []


def test_assert_aggregate_completeness_flags_missing_main_ocid():
    """One arm dropped an OCID → exactly one violation surfaced for
    that arm/OCID pair."""
    main_ocids = [f"ocid-{i}" for i in range(30)]
    diag_ocids = main_ocids[:10]
    accountings: dict[str, dry_run_e3.ArmAccounting] = {}
    for arm in dry_run_e3.MAIN_ARMS:
        acc = dry_run_e3.ArmAccounting(arm_name=arm, record_count=30)
        # Arm B drops ocid-5; everyone else has the full set.
        if arm == "arm_b":
            acc.ocids = [o for o in main_ocids if o != "ocid-5"]
        else:
            acc.ocids = list(main_ocids)
        accountings[arm] = acc
    for arm in dry_run_e3.DIAGNOSTIC_ARMS:
        acc = dry_run_e3.ArmAccounting(arm_name=arm, record_count=10)
        acc.ocids = list(diag_ocids)
        accountings[arm] = acc

    violations = dry_run_e3.assert_aggregate_completeness(
        main_ocids=main_ocids,
        diagnostic_ocids=diag_ocids,
        accountings=accountings,
    )
    assert len(violations) == 1
    assert "arm_b" in violations[0]
    assert "ocid-5" in violations[0]


# ---------------------------------------------------------------------------
# Live-mode env var validation (delegated to smoke_e3._check_env)
# ---------------------------------------------------------------------------


def test_dry_run_e3_refuses_live_without_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Without ``--dry`` and with no env vars, the driver must refuse
    to start. Belt-and-braces against an accidental live run."""
    for name in dry_run_e3.REQUIRED_LIVE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as exc:
        dry_run_e3.main([
            "--results-dir", str(tmp_path),
            "--run-id", "dry-live-noenv",
        ])
    assert "live mode requires" in str(exc.value)


# ---------------------------------------------------------------------------
# verify_dry_run_e3 — assertion semantics
# ---------------------------------------------------------------------------


def test_verify_run_passes_all_140_on_dry(tmp_path: Path):
    """The dry-mode pipeline writes 140 stub bundles; verify_run
    treats every-stub as implicit allow-stub and asserts the markers
    + per-arm counts + aggregate completeness correctly. All 140 PASS."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-dry-clean")
    result = verify_dry_run_e3.verify_run(run_dir)
    assert result.passed_count == 140, (
        f"expected 140 PASS, got {result.passed_count}; "
        f"first failure: {result.first_failure}"
    )
    assert result.failed_count == 0
    assert result.all_stubs is True
    # The verifier loaded the locked-subset expectations.
    assert len(result.expected_main_ocids) == 30
    assert len(result.expected_diagnostic_ocids) == 10


def test_verify_run_fails_when_marker_drifts(tmp_path: Path):
    """Mutate one bundle's ``l3_arm`` marker → verify_run reports the
    mismatch and stops on the first failure."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-drift")
    arm_a_bundle = _list_bundles(run_dir, "arm_a")[0]
    bundle = _load_bundle(arm_a_bundle)
    fields = _bundle_fields(bundle)
    fields["l3_arm"] = "Z"
    bundle["context_fields_canonical_json"] = json.dumps(
        fields, sort_keys=True, separators=(",", ":")
    )
    arm_a_bundle.write_text(
        json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8"
    )

    result = verify_dry_run_e3.verify_run(run_dir, stop_on_first_failure=True)
    assert result.failed_count >= 1
    assert result.first_failure is not None
    assert result.first_failure.arm_name == "arm_a"
    assert any("l3_arm" in err for err in result.first_failure.errors)


def test_verify_run_fails_when_count_short(tmp_path: Path):
    """Delete a bundle to drop a per-arm count below 30 (or 10). The
    verifier must surface a count mismatch."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-short-count")
    arm_a_bundles = _list_bundles(run_dir, "arm_a")
    arm_a_bundles[0].unlink()

    result = verify_dry_run_e3.verify_run(run_dir, stop_on_first_failure=False)
    # Filter for the synthesised count-mismatch report.
    count_failures = [
        r for r in result.reports
        if r.arm_name == "arm_a" and any("expected 30" in e for e in r.errors)
    ]
    assert count_failures, "expected arm_a count-mismatch failure"


def test_verify_run_fails_when_ocid_missing(tmp_path: Path):
    """Delete a bundle AND copy another bundle in to keep the count
    correct — completeness check surfaces the missing OCID even though
    the count is right."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-missing-ocid")
    arm_a_bundles = _list_bundles(run_dir, "arm_a")
    # Read the OCID we're about to drop.
    victim_bundle = _load_bundle(arm_a_bundles[0])
    victim_ocid = victim_bundle["ocid"]

    # Replace the victim bundle with a copy of bundle[1] (different OCID,
    # different decision_id, same arm) — the count stays at 30, but the
    # OCID set is now missing the victim.
    donor = _load_bundle(arm_a_bundles[1])
    # Mutate the decision_id so the file is unique.
    donor_copy = dict(donor)
    donor_copy["decision_id"] = donor["decision_id"] + "-clone"
    arm_a_bundles[0].write_text(
        json.dumps(donor_copy, indent=2, sort_keys=True), encoding="utf-8"
    )

    result = verify_dry_run_e3.verify_run(run_dir, stop_on_first_failure=False)

    # The arm now has 30 bundles (count check passes) but is missing
    # the victim OCID (completeness check fails).
    completeness_failures = [
        r for r in result.reports
        if r.arm_name == "arm_a"
        and any(victim_ocid in err and "missing" in err for err in r.errors)
    ]
    assert completeness_failures, (
        f"expected completeness failure for arm_a/{victim_ocid}"
    )


def test_verify_run_no_bundles(tmp_path: Path):
    """Empty run dir → single synthetic FAIL with 'no bundles'."""
    run_dir = tmp_path / "empty-dry-run"
    run_dir.mkdir()
    result = verify_dry_run_e3.verify_run(run_dir)
    assert result.failed_count == 1
    assert result.first_failure is not None
    assert any("no bundles" in e for e in result.first_failure.errors)


def test_verify_main_returns_zero_on_clean_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """End-to-end through ``verify_dry_run_e3.main`` (CLI surface):
    exit code 0 on a clean dry-run; PASS: 140 in stdout."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-main-dry")
    capsys.readouterr()
    rc = verify_dry_run_e3.main([str(run_dir)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "PASS: 140" in captured.out
    assert "FAIL: 0" in captured.out


def test_verify_main_emits_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """``--json`` switches output to a parseable JSON object with the
    expected counts + the locked subset OCIDs."""
    run_dir = _make_dry_run(tmp_path, run_id="verify-json-dry")
    capsys.readouterr()
    rc = verify_dry_run_e3.main([str(run_dir), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["total"] == 140
    assert payload["passed"] == 140
    assert payload["failed"] == 0
    assert payload["all_stubs"] is True
    assert len(payload["expected_main_ocids"]) == 30
    assert len(payload["expected_diagnostic_ocids"]) == 10


# ---------------------------------------------------------------------------
# Trusted-key pinning regression — inherits from smoke verifier
# ---------------------------------------------------------------------------


def test_dry_run_verifier_inherits_expected_kid():
    """The dry-run verifier reuses the smoke verifier's pinned key
    table — no drift between the two scripts. If a key rotation lands
    in the E3-011 window only the smoke verifier needs an edit."""
    assert (
        verify_dry_run_e3.EXPECTED_KID
        == "meshqu-experiment-procurement-2026-05"
    )
    assert (
        verify_dry_run_e3.EXPECTED_KID
        in verify_dry_run_e3.TRUSTED_KEYS_SPKI_DER_B64
    )


# ---------------------------------------------------------------------------
# recover_orphans shim — only that it imports + dispatches to the module.
# The module itself is exhaustively tested in test_recover_orphans.py.
# ---------------------------------------------------------------------------


def test_recover_orphans_shim_imports_cleanly():
    """The scripts/ shim is a thin pass-through to
    meshqu_runner.recover_orphans.main. We assert only that the import
    surface holds — the module-level tests in test_recover_orphans.py
    cover behaviour."""
    import importlib

    shim = importlib.import_module("recover_orphans")
    # The module-level `_main` attribute is the wrapped entry point.
    assert callable(shim._main)
