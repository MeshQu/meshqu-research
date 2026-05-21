"""Tests for the multi-pass orchestrator (E2-001).

Covers the done criteria from `planning/build_packages/e2-001-multi-pass-runner.md`:

- 15 bundles produced (3 records × 5 levels), each in the right level
  subdirectory under `<run_dir>/<level>/`.
- Each bundle carries `bundle_envelope_version: 1` (the E2-local
  wrapper's version, NOT a bump of the MeshQu receipt-schema).
- Each bundle carries `governance_context_level` matching its
  subdirectory.
- The MeshQu integrity hash includes `governance_context_level`
  (verified by recomputing canonical-JSON SHA-256 over the persisted
  fields map and checking it matches `receipt.integrity_hash`).
- Level-batching observed: all L0 bundles have earlier timestamps than
  all L1 bundles, etc.
- Manifest captures: bundle_envelope_version=1, levels list,
  level_batched=true, prompt_template_sha256 per level, policy snapshot
  SHA, runner_git_commit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from meshqu_runner import multi_pass as mp
from meshqu_runner.level_handlers import MAIN_LEVELS
from meshqu_runner.prompt_loader import LEVEL_PROMPT_FILES


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "smoke_records.json"
RUNNER_DIR = Path(__file__).resolve().parent.parent  # procurement-context-gradient/runner/
E2_DIR = RUNNER_DIR.parent  # procurement-context-gradient/
REPO_DIR = E2_DIR.parent  # meshqu-research/
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"


def _load_records() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture()
def stub_run(tmp_path: Path):
    """Drive a full stub multi-pass run and return (config, summary)."""
    records = _load_records()
    run_dir = tmp_path / "runs" / "stub-run-001"
    config = mp.MultiPassConfig(
        run_id="stub-run-001",
        run_phase="dry-run",
        repo_dir=REPO_DIR,
        run_dir=run_dir,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
    )
    summary = mp.run_multi_pass(
        config=config,
        records=records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
    )
    return config, summary, records


def test_smoke_produces_15_bundles(stub_run):
    """Foundation acceptance test for E2-001."""
    config, summary, records = stub_run
    assert len(summary.outcomes) == 15, "3 records × 5 levels = 15 expected bundles"

    # All five levels represented, 3 outcomes each.
    by_level: dict[str, list[mp.PassOutcome]] = {}
    for o in summary.outcomes:
        by_level.setdefault(o.level, []).append(o)
    assert set(by_level.keys()) == set(MAIN_LEVELS)
    for level in MAIN_LEVELS:
        assert len(by_level[level]) == 3, f"expected 3 outcomes at {level}, got {len(by_level[level])}"

    # Each bundle lives in the right level subdir.
    for outcome in summary.outcomes:
        expected_dir = config.run_dir / outcome.level
        assert outcome.bundle_path.parent == expected_dir
        assert outcome.bundle_path.exists()


def test_bundles_carry_envelope_v1_and_level_marker(stub_run):
    """Every bundle has bundle_envelope_version=1 and
    governance_context_level set to the subdir's level."""
    _, summary, _ = stub_run
    for outcome in summary.outcomes:
        with outcome.bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)
        assert bundle["bundle_envelope_version"] == 1
        assert bundle["governance_context_level"] == outcome.level
        assert bundle["is_stub"] is True


def test_governance_context_level_is_hash_bound(stub_run):
    """The integrity hash MUST include governance_context_level. We verify
    this by:
      1. Reading the persisted canonical-JSON of the fields map.
      2. Confirming `governance_context_level` is in that map.
      3. Recomputing SHA-256 over the canonical bytes and confirming it
         matches `receipt.integrity_hash` (because the stub client uses
         the same canonicalisation as MeshQu's real API).
      4. Sanity check: stripping the level marker and recomputing
         produces a DIFFERENT hash (proving the marker is materially
         hash-bound, not bypassed by canonicalisation)."""
    _, summary, _ = stub_run
    for outcome in summary.outcomes:
        with outcome.bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)

        canonical_str = bundle["context_fields_canonical_json"]
        fields = json.loads(canonical_str)

        # 1. Level marker present in the hashed bytes.
        assert fields.get("governance_context_level") == outcome.level
        assert mp.GOVERNANCE_CONTEXT_LEVEL_FIELD in canonical_str

        # 2. Recomputed hash matches.
        recomputed = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        assert recomputed == bundle["receipt"]["integrity_hash"]

        # 3. Stripping the marker produces a different hash. This is the
        #    "you cannot move a receipt between levels" guarantee.
        stripped = {k: v for k, v in fields.items() if k != mp.GOVERNANCE_CONTEXT_LEVEL_FIELD}
        stripped_canonical = json.dumps(
            stripped, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        stripped_hash = hashlib.sha256(stripped_canonical).hexdigest()
        assert stripped_hash != bundle["receipt"]["integrity_hash"], (
            f"governance_context_level was not actually hash-bound at {outcome.level} "
            f"for record {outcome.ocid} — stripping it left the hash unchanged"
        )


def test_level_batching_observed(stub_run):
    """All L0 timestamps must precede (or equal) all L1 timestamps, etc.

    Equality is tolerated because the stub records to ISO-second
    granularity — 15 records can fall inside a single wall-clock
    second. The invariant the test enforces is that no L{k+1} outcome
    precedes any L{k} outcome.
    """
    _, summary, _ = stub_run
    for k in range(len(MAIN_LEVELS) - 1):
        lower = MAIN_LEVELS[k]
        higher = MAIN_LEVELS[k + 1]
        lower_max = max(o.timestamp for o in summary.outcomes if o.level == lower)
        higher_min = min(o.timestamp for o in summary.outcomes if o.level == higher)
        assert lower_max <= higher_min, (
            f"{higher} outcome at {higher_min} precedes {lower} outcome at {lower_max} — "
            f"level-batching invariant violated"
        )


def test_within_level_ocid_ascending(stub_run):
    """Within a single level batch, records are processed in
    OCID-ascending order."""
    _, summary, _ = stub_run
    for level in MAIN_LEVELS:
        outcomes = [o for o in summary.outcomes if o.level == level]
        ocids = [o.ocid for o in outcomes]
        assert ocids == sorted(ocids), f"records at {level} not in OCID-ascending order: {ocids}"


def test_manifest_records_e2_extensions(stub_run):
    """manifest.json captures the E2 extension fields."""
    config, _, _ = stub_run
    manifest_path = config.run_dir / "manifest.json"
    assert manifest_path.exists()
    with manifest_path.open("r", encoding="utf-8") as fp:
        manifest = json.load(fp)

    assert manifest["bundle_envelope_version"] == 1
    assert manifest["levels"] == list(MAIN_LEVELS)
    assert manifest["level_batched"] is True
    assert manifest["is_stub"] is True

    # All four prompt SHAs present and 64-hex.
    prompt_shas = manifest["prompt_template_sha256"]
    for level, _filename in LEVEL_PROMPT_FILES:
        sha = prompt_shas[level]
        assert isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)

    # Policy snapshot SHA matches the locked value.
    expected_policy_sha = "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d"
    assert manifest["policy_snapshot_sha256"] == expected_policy_sha

    assert manifest["runner_git_commit"]  # not 'unknown' since we ran inside the repo


def test_prompt_shas_match_locked_values(stub_run):
    """Stage A SHAs in the manifest match the values frozen in the
    package prompt. Pinning the test against the literal values protects
    against silent prompt drift."""
    config, _, _ = stub_run
    with (config.run_dir / "manifest.json").open("r", encoding="utf-8") as fp:
        manifest = json.load(fp)
    expected = {
        "L1": "19b9863905593756b583bdc4b39998f143ba14c63fa1cebe90295d6e76f90acf",
        "L2": "d24847ed1eef3c4d87b725195d0313449398e2a467c7de4bf0cd6a9e93c11174",
        "L3": "a3e224cbaeb91fbe3b6583d5c6c7c429893d838819a5f7e2c6f04182ddff1f5d",
        "L4": "c90664f473c19b7482b9bb81f0bf546392819dd7bfb6f47bcb369ac713ac0b2d",
    }
    assert manifest["prompt_template_sha256"] == expected


def test_decision_ids_unique_across_levels(stub_run):
    """Same record at different levels must produce DIFFERENT decision_ids.

    This is the load-bearing receipt-isolation guarantee — if the same
    decision_id were emitted at L0 and L1 for the same OCID, MeshQu's
    idempotency cache would return the L0 receipt for the L1 call,
    silently collapsing two distinct evaluations into one."""
    _, summary, _ = stub_run
    decision_ids = [o.decision_id for o in summary.outcomes]
    assert len(set(decision_ids)) == len(decision_ids), (
        "decision_id collision across (record, level) — idempotency key derivation is broken"
    )

    # Confirm the same OCID at different levels produces different ids.
    by_ocid: dict[str, list[str]] = {}
    for o in summary.outcomes:
        by_ocid.setdefault(o.ocid, []).append(o.decision_id)
    for ocid, ids in by_ocid.items():
        assert len(ids) == 5
        assert len(set(ids)) == 5, f"OCID {ocid} produced colliding decision_ids across levels"


def test_empty_prompts_handled_gracefully(tmp_path: Path):
    """Per the package prompt: 'The runner code MUST handle the empty
    case gracefully (treats as no-op addition).'

    Stage A is now merged with real prompts, but the runner contract
    must still work if a future contributor empties them — they would
    just produce L_k = L0 prompts, with no agent failures."""
    empty_prompts = tmp_path / "prompts"
    empty_prompts.mkdir()
    for _level, filename in LEVEL_PROMPT_FILES:
        (empty_prompts / filename).write_text("", encoding="utf-8")

    records = _load_records()
    run_dir = tmp_path / "runs" / "empty-prompts"
    config = mp.MultiPassConfig(
        run_id="empty-prompts-test",
        run_phase="dry-run",
        repo_dir=REPO_DIR,
        run_dir=run_dir,
        prompts_dir=empty_prompts,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
    )
    summary = mp.run_multi_pass(
        config=config,
        records=records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
    )
    assert len(summary.outcomes) == 15
    # Bundles still emitted with correct level markers.
    for outcome in summary.outcomes:
        assert outcome.bundle_path.exists()
        with outcome.bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)
        assert bundle["governance_context_level"] == outcome.level


def test_user_message_composition_is_additive(tmp_path: Path):
    """L_k user message must contain L_{k-1}'s addendum verbatim.

    Empty Stage A prompts trivially satisfy this (every addendum is
    empty), so the test loads the real prompts and checks that L4's
    composed message strictly contains L3's, L2's, L1's headers in
    order."""
    from meshqu_runner import level_handlers as lh
    from meshqu_runner.prompt_loader import load_level_prompts

    prompts = load_level_prompts(PROMPTS_DIR)
    handlers = lh.default_main_handlers()
    record = _load_records()[0]
    base = "BASE_RECORD_MESSAGE"

    composed_by_level = {
        level: lh.compose_user_message(
            level=level,
            record=record,
            ocid=record["ocid"],
            prompts=prompts,
            handlers=handlers,
            base_message=base,
        )
        for level in MAIN_LEVELS
    }

    # Additivity: each non-L0 composition contains the lower-level
    # composition's prefix verbatim.
    for k in range(1, len(MAIN_LEVELS)):
        lower = composed_by_level[MAIN_LEVELS[k - 1]]
        higher = composed_by_level[MAIN_LEVELS[k]]
        # Strip the base_message suffix and check the higher level's
        # prefix starts with the lower level's prefix.
        lower_prefix = lower.removesuffix(base).rstrip("\n")
        if lower_prefix:
            assert lower_prefix in higher, (
                f"{MAIN_LEVELS[k]} composition does not contain {MAIN_LEVELS[k - 1]} addendum"
            )

    # L0 must compose to just the base message (Stage A may have empty
    # L1 in the empty-fixture case; here L0 always adds nothing).
    assert composed_by_level["L0"] == base


def test_bundle_canonical_json_matches_meshqu_format(stub_run):
    """The bundle's `context_fields_canonical_json` MUST use the same
    canonicalisation as MeshQu's wire format (sort_keys=True,
    ensure_ascii=False, separators=',:'). If it doesn't, an external
    verifier recomputing the hash would diverge."""
    _, summary, _ = stub_run
    for outcome in summary.outcomes:
        with outcome.bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)
        canonical = bundle["context_fields_canonical_json"]
        # Re-parse and re-serialise; the round-trip must be a fixed point.
        parsed = json.loads(canonical)
        re_serialised = json.dumps(
            parsed, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        assert canonical == re_serialised, (
            f"bundle at {outcome.bundle_path} is not in canonical-JSON form"
        )
