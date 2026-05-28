"""E3-001 foundation tests — arm registry, integrity payload, CLI dispatch.

The three assertions called out in
``planning/build_packages/e3-001-runner-foundation.md`` §6:

1. All arms register against ``HANDLERS`` cleanly without import-time
   errors (placeholder no-op handlers are fine for now; the real
   handlers land in later packages).
2. The receipt integrity payload includes the seven new fields
   (verified via a stub signer that captures the field payload it
   would hash).
3. The CLI parses ``--arm`` and dispatches to the correct handler.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from meshqu_runner import arms
from meshqu_runner.arms import (
    ARM_NAMES,
    ARM_PROFILES,
    CLAUDE_MODEL_ID,
    CLAUDE_MODEL_SAMPLING,
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_SAMPLING,
    HANDLERS,
    PREREG_TAG,
    inject_arm_fields,
)
from meshqu_runner import cli as cli_module
from meshqu_runner.multi_pass import (
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    canonical_json_bytes,
    run_arm,
)


# ---------------------------------------------------------------------------
# §6 Assertion 1 — every arm registers cleanly without import-time errors
# ---------------------------------------------------------------------------


def test_every_arm_in_arm_names_has_a_handler():
    """All ARM_NAMES have a registered placeholder. The arms module
    runs this assertion at import; this test re-asserts at runtime so
    a regression in the import-time loop fires loudly."""
    for arm in ARM_NAMES:
        assert arm in HANDLERS, f"missing handler for arm {arm!r}"


def test_every_arm_has_a_profile():
    """ARM_PROFILES is the source of truth for integrity-payload
    defaults. Every arm must have one."""
    for arm in ARM_NAMES:
        assert arm in ARM_PROFILES, f"missing profile for arm {arm!r}"
        assert ARM_PROFILES[arm].arm_name == arm


def test_arm_handlers_callable_with_just_a_record():
    """Placeholder handlers accept a record alone (foundation contract).
    Later real handlers may require kwargs; ``arms.dispatch`` filters
    them by signature so the foundation's CLI keeps working with the
    placeholder set."""
    record = {"ocid": "stub-ocid-test", "decision_type": "procurement_decision"}
    for arm in ARM_NAMES:
        prompt = HANDLERS[arm](record)
        assert isinstance(prompt, str)
        assert arm in prompt, f"placeholder for {arm!r} should mention its name"
        assert "stub-ocid-test" in prompt


def test_register_rejects_unknown_arm_name():
    """Typo'd arm names must surface at registration. Otherwise a stray
    decorator could silently sit in HANDLERS forever, and the CLI's
    ``--arm`` choices would not detect the mistake."""
    with pytest.raises(ValueError, match="Unknown arm name"):

        @arms.register("arm_bogus")
        def _bogus(record, **_):  # pragma: no cover
            return ""


def test_dispatch_unknown_arm_raises_keyerror():
    """Dispatching against an unknown arm raises ``KeyError`` (clean
    surface for the CLI to catch and translate to an error message)."""
    with pytest.raises(KeyError, match="No handler registered"):
        arms.dispatch("arm_does_not_exist", {"ocid": "x"})


def test_l3_arm_profiles_carry_letters():
    """Arms A/B/C carry the human-readable letter; everything else None."""
    assert ARM_PROFILES["arm_a"].l3_arm == "A"
    assert ARM_PROFILES["arm_b"].l3_arm == "B"
    assert ARM_PROFILES["arm_c"].l3_arm == "C"
    assert ARM_PROFILES["l4_without_nudge"].l3_arm is None
    assert ARM_PROFILES["l4_with_nudge"].l3_arm is None
    assert ARM_PROFILES["l0_baseline"].l3_arm is None
    assert ARM_PROFILES["diagnostic_primary"].l3_arm is None
    assert ARM_PROFILES["diagnostic_claude"].l3_arm is None


def test_nudge_excised_only_for_l4_without_nudge():
    for arm in ARM_NAMES:
        expected = arm == "l4_without_nudge"
        assert ARM_PROFILES[arm].nudge_excised is expected, (
            f"nudge_excised wrong for {arm!r}"
        )


def test_diagnostic_flag_only_for_diagnostic_arms():
    for arm in ARM_NAMES:
        expected = arm.startswith("diagnostic_")
        assert ARM_PROFILES[arm].diagnostic is expected, (
            f"diagnostic wrong for {arm!r}"
        )


def test_claude_arm_carries_claude_model_id_and_no_temperature():
    """The cross-model diagnostic arm is pinned to ``claude-opus-4-7``
    with no ``temperature`` and ``effort: low`` — per the locked
    parameters in ``planning/experiment_design.md``."""
    profile = ARM_PROFILES["diagnostic_claude"]
    assert profile.model_id == CLAUDE_MODEL_ID == "claude-opus-4-7"
    assert profile.model_sampling == CLAUDE_MODEL_SAMPLING
    assert profile.model_sampling["temperature"] is None
    assert profile.model_sampling["effort"] == "low"


def test_primary_model_arm_carries_default_model_and_temperature_zero():
    for arm in ARM_NAMES:
        if arm == "diagnostic_claude":
            continue
        profile = ARM_PROFILES[arm]
        assert profile.model_id == DEFAULT_MODEL_ID == "gpt-5.4-2026-03-05"
        assert profile.model_sampling == DEFAULT_MODEL_SAMPLING
        assert profile.model_sampling["temperature"] == 0


# ---------------------------------------------------------------------------
# §6 Assertion 2 — integrity payload includes the seven new fields
# ---------------------------------------------------------------------------


SEVEN_NEW_FIELDS = (
    "l3_arm",
    "nudge_excised",
    "model_id",
    "model_sampling",
    "diagnostic",
    "policy_permutation_seed",
    "runner_git_commit",
    # plus prereg_tag — the package spec calls this the seventh, with
    # ``runner_git_commit`` being implicit-context. We carry both to
    # bind both into the integrity hash.
    "prereg_tag",
)


def test_inject_arm_fields_adds_all_seven_fields_to_context_fields():
    """The integrity payload extension lands its fields under
    ``context.fields`` — the same audit-only-but-hash-bound channel E2
    uses for ``agent_*`` fields."""
    base_context = {"decision_type": "procurement_decision", "fields": {"existing": "kept"}}
    new = inject_arm_fields(
        base_context,
        arm_name="arm_a",
        runner_git_commit="deadbeef",
    )
    for field_name in SEVEN_NEW_FIELDS:
        assert field_name in new["fields"], (
            f"missing {field_name!r} in integrity payload"
        )
    # Existing fields preserved (additive contract).
    assert new["fields"]["existing"] == "kept"


def test_inject_arm_fields_does_not_mutate_input():
    base = {"fields": {"original": True}}
    inject_arm_fields(base, arm_name="arm_a", runner_git_commit="abc")
    assert base == {"fields": {"original": True}}


def test_inject_arm_fields_values_for_arm_a():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="arm_a",
        runner_git_commit="commit-sha-here",
    )
    f = new["fields"]
    assert f["l3_arm"] == "A"
    assert f["nudge_excised"] is False
    assert f["model_id"] == DEFAULT_MODEL_ID
    assert f["model_sampling"] == {"temperature": 0}
    assert f["diagnostic"] is False
    assert f["policy_permutation_seed"] is None
    assert f["runner_git_commit"] == "commit-sha-here"
    assert f["prereg_tag"] == PREREG_TAG == "v0.3-predictions-locked"


def test_inject_arm_fields_values_for_l4_without_nudge():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="l4_without_nudge",
        runner_git_commit="commit",
    )
    f = new["fields"]
    assert f["l3_arm"] is None
    assert f["nudge_excised"] is True
    assert f["model_id"] == DEFAULT_MODEL_ID
    assert f["diagnostic"] is False


def test_inject_arm_fields_values_for_diagnostic_claude():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="diagnostic_claude",
        runner_git_commit="commit",
        policy_permutation_seed=42,
    )
    f = new["fields"]
    assert f["l3_arm"] is None
    assert f["nudge_excised"] is False
    assert f["model_id"] == CLAUDE_MODEL_ID
    assert f["model_sampling"]["temperature"] is None
    assert f["model_sampling"]["effort"] == "low"
    assert f["diagnostic"] is True
    assert f["policy_permutation_seed"] == 42


def test_inject_arm_fields_requires_seed_for_diagnostic_arms():
    """Diagnostic arms refuse to sign without a permutation seed —
    otherwise we'd lose attribution at audit time."""
    with pytest.raises(ValueError, match="policy_permutation_seed.*required"):
        inject_arm_fields(
            {"fields": {}},
            arm_name="diagnostic_primary",
            runner_git_commit="commit",
        )


def test_inject_arm_fields_rejects_seed_for_non_diagnostic_arms():
    """Non-diagnostic arms reject a seed — otherwise a stray seed
    would mis-attribute the receipt as diagnostic at audit time."""
    with pytest.raises(ValueError, match="not diagnostic"):
        inject_arm_fields(
            {"fields": {}},
            arm_name="arm_a",
            runner_git_commit="commit",
            policy_permutation_seed=7,
        )


def test_model_overrides_propagate_to_integrity_payload():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="arm_a",
        runner_git_commit="commit",
        model_id="model-override",
        model_sampling={"temperature": 0.7, "top_p": 1.0},
    )
    assert new["fields"]["model_id"] == "model-override"
    assert new["fields"]["model_sampling"] == {"temperature": 0.7, "top_p": 1.0}


def test_stub_signer_captures_seven_fields_for_every_arm(tmp_path: Path):
    """End-to-end: run each arm through ``run_arm`` against the
    ``StubMeshQuClient`` and assert the captured ``fields`` map (the
    bytes the stub hashes for the integrity hash) contains all seven
    E3-specific fields.

    This is the package's §6 stub-signer assertion.
    """
    for arm in ARM_NAMES:
        client = StubMeshQuClient()
        config = RunConfig(
            run_id=f"test-{arm}",
            run_phase="dry-run",
            repo_dir=tmp_path,  # repo_dir is consulted for git SHA; tmp is fine
            run_dir=tmp_path / f"run-{arm}",
            arm_name=arm,
            policy_snapshot_path=None,
            policy_permutation_seed=(7 if ARM_PROFILES[arm].diagnostic else None),
        )
        summary = run_arm(
            config=config,
            records=[
                {"ocid": "stub-ocid-001", "decision_type": "procurement_decision"}
            ],
            agent=StubAgent(),
            meshqu_client=client,
        )
        assert len(summary.outcomes) == 1
        # Single record → single captured field payload
        assert len(client.captured_field_payloads) == 1
        captured = client.captured_field_payloads[0]
        for field_name in SEVEN_NEW_FIELDS:
            assert field_name in captured, (
                f"arm {arm!r} did not bind {field_name!r} into integrity hash"
            )
        # Spot-check that profile defaults landed
        assert captured["l3_arm"] == ARM_PROFILES[arm].l3_arm
        assert captured["nudge_excised"] == ARM_PROFILES[arm].nudge_excised
        assert captured["diagnostic"] == ARM_PROFILES[arm].diagnostic
        assert captured["prereg_tag"] == PREREG_TAG


def test_stub_signer_integrity_hash_is_canonical_json_sha256(tmp_path: Path):
    """The stub's integrity_hash is sha256(canonical_json(fields)).
    Recompute and compare so we know the binding is non-trivial."""
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="test-canonical",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run-canonical",
        arm_name="arm_a",
        policy_snapshot_path=None,
    )
    summary = run_arm(
        config=config,
        records=[{"ocid": "stub-ocid-001", "decision_type": "procurement_decision"}],
        agent=StubAgent(),
        meshqu_client=client,
    )
    import hashlib

    captured = client.captured_field_payloads[0]
    recomputed = hashlib.sha256(canonical_json_bytes(captured)).hexdigest()
    assert summary.outcomes[0].receipt.integrity_hash == recomputed


# ---------------------------------------------------------------------------
# §6 Assertion 3 — CLI parses --arm and dispatches to the correct handler
# ---------------------------------------------------------------------------


def test_cli_default_arm_is_arm_a():
    parser = cli_module._build_parser()
    args = parser.parse_args(["--dry"])
    assert args.arm == "arm_a"


def test_cli_accepts_every_arm_in_arm_names():
    parser = cli_module._build_parser()
    for arm in ARM_NAMES:
        args = parser.parse_args(["--arm", arm, "--dry"])
        assert args.arm == arm


def test_cli_rejects_unknown_arm(capsys):
    parser = cli_module._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--arm", "arm_unknown", "--dry"])
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err.lower()


def test_cli_dry_run_dispatches_correct_arm(tmp_path: Path, capsys, monkeypatch):
    """End-to-end CLI: run --arm arm_b --records 1 --dry, then verify
    the bundle file landed under the ``arm_b/`` subdir (not ``arm_a/``)."""
    monkeypatch.chdir(tmp_path)
    rc = cli_module.main(
        [
            "--arm",
            "arm_b",
            "--records",
            "1",
            "--dry",
            "--results-dir",
            str(tmp_path / "results"),
            "--run-id",
            "cli-test-arm-b",
        ]
    )
    assert rc == 0
    bundles = list((tmp_path / "results" / "runs" / "cli-test-arm-b").rglob("*.bundle.json"))
    assert len(bundles) == 1
    # The bundle MUST live under arm_b/ — proves dispatch picked the
    # right arm (not the default arm_a).
    assert bundles[0].parent.name == "arm_b"

    # And the bundle's arm_name field matches.
    with bundles[0].open() as fp:
        bundle = json.load(fp)
    assert bundle["arm_name"] == "arm_b"
    # Bundle's canonical fields carry the seven E3-specific fields
    payload = json.loads(bundle["context_fields_canonical_json"])
    for field_name in SEVEN_NEW_FIELDS:
        assert field_name in payload, f"missing {field_name!r} in bundle"
    assert payload["l3_arm"] == "B"


def test_cli_dry_run_diagnostic_requires_seed(tmp_path: Path, capsys):
    """Diagnostic arms fail without ``--policy-permutation-seed`` —
    surfaces at run time via inject_arm_fields. The CLI propagates
    the exception."""
    with pytest.raises(ValueError, match="policy_permutation_seed.*required"):
        cli_module.main(
            [
                "--arm",
                "diagnostic_primary",
                "--records",
                "1",
                "--dry",
                "--results-dir",
                str(tmp_path / "results"),
                "--run-id",
                "cli-diag-no-seed",
            ]
        )


def test_cli_dry_run_diagnostic_with_seed_succeeds(tmp_path: Path):
    rc = cli_module.main(
        [
            "--arm",
            "diagnostic_primary",
            "--records",
            "1",
            "--dry",
            "--policy-permutation-seed",
            "13",
            "--results-dir",
            str(tmp_path / "results"),
            "--run-id",
            "cli-diag-with-seed",
        ]
    )
    assert rc == 0
    bundles = list((tmp_path / "results" / "runs" / "cli-diag-with-seed").rglob("*.bundle.json"))
    assert len(bundles) == 1
    with bundles[0].open() as fp:
        bundle = json.load(fp)
    payload = json.loads(bundle["context_fields_canonical_json"])
    assert payload["diagnostic"] is True
    assert payload["policy_permutation_seed"] == 13


def test_cli_rejects_live_mode(capsys):
    """Foundation only supports --dry. Live mode is a 2 exit code."""
    rc = cli_module.main(["--arm", "arm_a", "--records", "1"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "only supports --dry" in captured.err


def test_cli_rejects_records_and_ocid_list_together(tmp_path: Path, capsys):
    ocid_path = tmp_path / "ocids.json"
    ocid_path.write_text(json.dumps(["stub-ocid-x"]))
    rc = cli_module.main(
        [
            "--arm",
            "arm_a",
            "--records",
            "1",
            "--ocid-list",
            str(ocid_path),
            "--dry",
        ]
    )
    assert rc == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_cli_ocid_list_loads_correct_records(tmp_path: Path):
    ocid_path = tmp_path / "ocids.json"
    ocid_path.write_text(json.dumps(["ocid-from-list-1", "ocid-from-list-2"]))
    rc = cli_module.main(
        [
            "--arm",
            "arm_a",
            "--ocid-list",
            str(ocid_path),
            "--dry",
            "--results-dir",
            str(tmp_path / "results"),
            "--run-id",
            "cli-ocid-list",
        ]
    )
    assert rc == 0
    bundles = sorted(
        (tmp_path / "results" / "runs" / "cli-ocid-list").rglob("*.bundle.json")
    )
    assert len(bundles) == 2
    ocids_in_bundles = []
    for b in bundles:
        with b.open() as fp:
            bundle = json.load(fp)
        ocids_in_bundles.append(bundle["ocid"])
    assert sorted(ocids_in_bundles) == ["ocid-from-list-1", "ocid-from-list-2"]


def test_cli_model_override_lands_in_receipt(tmp_path: Path):
    rc = cli_module.main(
        [
            "--arm",
            "arm_a",
            "--records",
            "1",
            "--dry",
            "--model",
            "custom-model-id",
            "--results-dir",
            str(tmp_path / "results"),
            "--run-id",
            "cli-model-override",
        ]
    )
    assert rc == 0
    bundles = list(
        (tmp_path / "results" / "runs" / "cli-model-override").rglob("*.bundle.json")
    )
    with bundles[0].open() as fp:
        bundle = json.load(fp)
    payload = json.loads(bundle["context_fields_canonical_json"])
    assert payload["model_id"] == "custom-model-id"
