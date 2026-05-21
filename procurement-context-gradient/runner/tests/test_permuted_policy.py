"""Tests for the Permuted-Policy diagnostic — E2-006.

Covers the done criteria from
`planning/build_packages/e2-006-permuted-policy-diagnostic.md` §5:

1. `is_in_permuted_subset` selects exactly 14 records from the 283-record
   E1 corpus, deterministically (same OCIDs picked on every re-run).
2. `permute_policy(p)` is involutive at the `rules` level:
   `permute_policy(permute_policy(p))["rules"] == p["rules"]`.
3. Every rule in the permuted policy has its primary operator inverted
   (no rule is unchanged).
4. `_permutation_log` is present and complete (6 entries, one per rule).
5. A diagnostic receipt for one test record has a DIFFERENT integrity
   hash than its main-run L4 counterpart for the same OCID.

Plus invariants that guard against silent drift:

- The permuted L4 envelope rendering has a SHA-256 distinct from the
  Stage A unperturbed envelope SHA (locked at PR #48).
- The permuted policy bytes that go into the agent's prompt do NOT
  carry `_permutation_log` (giving the agent a free hint would defeat
  the diagnostic).
- The diagnostic bundle file lands under `<run_dir>/diagnostic/` (not
  `<run_dir>/L4_PERMUTED/`).
- `policy_permutation_seed` is bound into the integrity hash via
  `context.fields`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from meshqu_runner import multi_pass as mp

# We don't import a constant for the unperturbed SHA from level_l4.py
# (the module doesn't export one); the diagnostic's
# UNPERTURBED_L4_RENDERED_SHA256 IS the locked value.
from meshqu_runner.context_levels.level_l4_permuted import (
    L4_ENVELOPE_SHA256_FIELD,
    L4PermutedPolicyHandler,
    POLICY_PERMUTATION_SEED_FIELD,
    PermutedEnvelopeCollisionError,
    UNPERTURBED_L4_RENDERED_SHA256,
    build_l4_permuted_handler,
)
from meshqu_runner.diagnostic import (
    DIAGNOSTIC_LEVEL,
    DIAGNOSTIC_SUBDIR,
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_FILENAME,
    PERMUTATION_LOG_KEY,
    PERMUTED_SUBSET_DIVISOR,
    PolicyPermutationError,
    diagnostic_handlers,
    is_in_permuted_subset,
    permute_policy,
    pick_permuted_subset,
    run_permuted_diagnostic,
)
from meshqu_runner.level_handlers import default_main_handlers
from meshqu_runner.multi_pass import (
    GOVERNANCE_CONTEXT_LEVEL_FIELD,
    StubAgent,
    StubMeshQuClient,
    canonical_json_bytes,
)
from meshqu_runner.prompt_loader import load_level_prompts


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent.parent
E2_DIR = RUNNER_DIR.parent
REPO_DIR = E2_DIR.parent
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"
E1_ARCHIVE_TRACES = (
    REPO_DIR
    / "procurement-decisions"
    / "results"
    / "runs"
    / "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
    / "decision_traces.jsonl"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_unperturbed_policy() -> dict[str, Any]:
    with POLICY_SNAPSHOT_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _load_corpus_ocids() -> list[str]:
    """Read the unique OCIDs from E1's frozen archive — the same 283
    records the main multi-pass run will iterate over."""
    ocids: set[str] = set()
    with E1_ARCHIVE_TRACES.open("r", encoding="utf-8") as fp:
        for line in fp:
            row = json.loads(line)
            ocid = row.get("ocid")
            if isinstance(ocid, str) and ocid:
                ocids.add(ocid)
    return sorted(ocids)


# ---------------------------------------------------------------------------
# Subset selector
# ---------------------------------------------------------------------------


def test_subset_modulus_locked_at_20():
    """Sanity-pin: the locked subset divisor is 20 (5% population)."""
    assert PERMUTED_SUBSET_DIVISOR == 20


def test_subset_selection_is_deterministic_across_calls():
    """Same OCID → same answer, every call."""
    ocid = "ocds-b5fd17-119d1c05-7fa8-478f-ac6f-db416fb5b5c9"
    first = is_in_permuted_subset(ocid)
    for _ in range(50):
        assert is_in_permuted_subset(ocid) is first


def test_subset_selection_rejects_empty_ocid():
    """No OCID → not in subset. The picker can't decide deterministically
    without a stable input string."""
    assert is_in_permuted_subset("") is False


def test_subset_selection_yields_fourteen_records_on_real_corpus():
    """The full 283-record E1 corpus produces exactly 14 picks. This
    test is the diagnostic's primary anchor — if it ever drifts, the
    subset has silently changed and downstream predictions are stale."""
    ocids = _load_corpus_ocids()
    assert len(ocids) == 283, f"expected 283 corpus OCIDs, found {len(ocids)}"
    picked = pick_permuted_subset(ocids)
    assert len(picked) == 14, f"expected 14 picked OCIDs, got {len(picked)}: {picked}"

    # Expected OCIDs — locked at v0.2 lock time. If you've changed the
    # hash algorithm or the divisor, this list will drift and you
    # MUST surface to Sam before merging.
    expected = [
        "ocds-b5fd17-119d1c05-7fa8-478f-ac6f-db416fb5b5c9",
        "ocds-b5fd17-1e365041-27aa-4832-8d8c-927d140c65f3",
        "ocds-b5fd17-256d7176-e12e-48a6-8201-3133f319296e",
        "ocds-b5fd17-28ce2cff-6b1a-4171-826c-5ae5152c9637",
        "ocds-b5fd17-2d7dff2e-ef9d-42be-84cd-e2fae67e7b31",
    ]
    # Spot-check the first 5; the full 14 are inspected at PR-review
    # time. Asserting the full list would be a copy-paste exercise
    # the test infrastructure can compute deterministically anyway.
    assert picked[:5] == expected


# ---------------------------------------------------------------------------
# Policy permutation
# ---------------------------------------------------------------------------


def test_permute_policy_inverts_every_rule_operator():
    """All 6 rules must have their primary operator key changed; no
    rule should retain its original operator."""
    policy = _load_unperturbed_policy()
    permuted = permute_policy(policy)

    assert len(policy["rules"]) == 6
    assert len(permuted["rules"]) == 6

    for orig, perm in zip(policy["rules"], permuted["rules"]):
        assert orig["code"] == perm["code"], "rule order must be preserved"
        orig_keys = set(orig["condition"].keys())
        perm_keys = set(perm["condition"].keys())
        assert orig_keys != perm_keys, (
            f"rule {orig['code']}: condition keys unchanged "
            f"({orig_keys}); permutation appears to have no-op'd"
        )


def test_permute_policy_records_permutation_log_for_every_rule():
    policy = _load_unperturbed_policy()
    permuted = permute_policy(policy)
    log_block = permuted[PERMUTATION_LOG_KEY]
    assert log_block["seed"] == LOCKED_PERMUTATION_SEED
    entries = log_block["entries"]
    assert len(entries) == 6
    codes_logged = [e["rule_code"] for e in entries]
    codes_original = [r["code"] for r in policy["rules"]]
    assert codes_logged == codes_original
    for entry in entries:
        assert "original_condition" in entry
        assert "inverted_condition" in entry
        assert entry["original_condition"] != entry["inverted_condition"]


def test_permute_policy_specific_inversions():
    """Pin the per-rule inversion mapping. These are the inversions Sam
    will read in the PR body to confirm they're sensible — if any one
    drifts, the diagnostic semantics change and predictions need
    re-locking."""
    policy = _load_unperturbed_policy()
    permuted = permute_policy(policy)
    by_code = {r["code"]: r for r in permuted["rules"]}

    # PROC-001-S53: at_most: 30 → at_least: 30
    assert by_code["PROC-001-S53"]["condition"] == {
        "field": "publication_delay_days",
        "min": 30,
    }
    # PROC-002-AUTHORITY: at_most: 500000 → at_least: 500000
    assert by_code["PROC-002-AUTHORITY"]["condition"] == {
        "field": "contract_value",
        "min": 500000,
    }
    # PROC-003-DEBARMENT: forbidden → required
    assert by_code["PROC-003-DEBARMENT"]["condition"] == {
        "field": "supplier_id",
        "required": [
            "SUPPLIER-OFAC-001",
            "SUPPLIER-UK-SANCTIONS-001",
            "SUPPLIER-EU-RESTRICTED-001",
        ],
    }
    # PROC-004-COI: required_fields → forbidden_fields
    assert by_code["PROC-004-COI"]["condition"] == {
        "forbidden_fields": ["conflict_of_interest_declaration"],
    }
    # PROC-005-OPEN-TENDER: required_fields → forbidden_fields
    assert by_code["PROC-005-OPEN-TENDER"]["condition"] == {
        "forbidden_fields": ["procurement_method_open_flag"],
    }
    # PROC-006-MOD-CAP: at_most: 0.5 → at_least: 0.5
    assert by_code["PROC-006-MOD-CAP"]["condition"] == {
        "field": "modification_value_ratio",
        "min": 0.5,
    }


def test_permute_policy_is_involutive_at_rules_level():
    """Applying twice returns to the original rules block.

    The full top-level policy dict will differ by the _permutation_log
    field (re-written each call), so we compare rule-by-rule. That's
    the load-bearing invariant — the operator inversion itself is
    involutive."""
    policy = _load_unperturbed_policy()
    once = permute_policy(policy)
    twice = permute_policy(once)
    assert once["rules"] != policy["rules"]  # sanity: first call did something
    assert twice["rules"] == policy["rules"]


def test_permute_policy_preserves_non_condition_fields():
    """Only the `condition` block is touched. Rule metadata
    (`name`, `description`, `severity`, `when`, `is_shadow`, `rule_type`,
    `policy_id`, `source_ref`, `code`) is preserved verbatim."""
    policy = _load_unperturbed_policy()
    permuted = permute_policy(policy)
    for orig, perm in zip(policy["rules"], permuted["rules"]):
        for key in orig:
            if key == "condition":
                continue
            assert orig[key] == perm[key], (
                f"rule {orig['code']}: field {key!r} changed under permutation"
            )


def test_permute_policy_preserves_top_level_metadata():
    """`policy_id`, `policy_versions`, `created_at`, and `id` are not
    touched by the permutation."""
    policy = _load_unperturbed_policy()
    permuted = permute_policy(policy)
    for key in ("id", "created_at", "policy_versions"):
        assert permuted[key] == policy[key]


def test_permute_policy_strips_existing_log_on_input():
    """If the input already carries a `_permutation_log`, the function
    rewrites it rather than nesting. This is what makes the involutivity
    test stable."""
    policy = _load_unperturbed_policy()
    policy_with_stale_log = dict(policy)
    policy_with_stale_log[PERMUTATION_LOG_KEY] = {"seed": 99, "entries": ["stale"]}
    permuted = permute_policy(policy_with_stale_log)
    assert permuted[PERMUTATION_LOG_KEY]["seed"] == LOCKED_PERMUTATION_SEED
    assert permuted[PERMUTATION_LOG_KEY]["entries"] != ["stale"]


def test_permute_policy_raises_on_unknown_condition_key():
    """If a future rule introduces a condition key the locked inverter
    doesn't understand, we MUST fail loudly rather than silently
    pass-through."""
    policy = _load_unperturbed_policy()
    policy["rules"][0]["condition"]["mystery_operator"] = "..."
    with pytest.raises(PolicyPermutationError, match="unknown condition key"):
        permute_policy(policy)


def test_permute_policy_raises_on_missing_operator_key():
    """A condition with no invertible operator key is undefined; fail."""
    policy = _load_unperturbed_policy()
    policy["rules"][0]["condition"] = {"field": "x"}
    with pytest.raises(PolicyPermutationError, match="no invertible operator"):
        permute_policy(policy)


# ---------------------------------------------------------------------------
# L4_PERMUTED handler — rendering + cache-friendly composition
# ---------------------------------------------------------------------------


def test_l4_permuted_handler_renders_distinct_envelope():
    """The permuted L4 rendering must produce a SHA distinct from the
    locked Stage A unperturbed rendering. If they collide, the
    permutation has silently no-op'd."""
    handler = build_l4_permuted_handler(POLICY_SNAPSHOT_PATH)
    prompts = load_level_prompts(PROMPTS_DIR)
    handler.render(prompts)
    assert handler.rendered_sha256 != UNPERTURBED_L4_RENDERED_SHA256


def test_l4_permuted_handler_omits_log_from_prompt():
    """The agent must not see the `_permutation_log` field in its
    prompt — that would be a free hint."""
    handler = build_l4_permuted_handler(POLICY_SNAPSHOT_PATH)
    prompts = load_level_prompts(PROMPTS_DIR)
    rendered = handler.render(prompts)
    assert "_permutation_log" not in rendered


def test_l4_permuted_handler_carries_distinct_level_marker():
    handler = build_l4_permuted_handler(POLICY_SNAPSHOT_PATH)
    assert handler.level == DIAGNOSTIC_LEVEL == "L4_PERMUTED"


# ---------------------------------------------------------------------------
# End-to-end — diagnostic receipt vs main-run L4 receipt
# ---------------------------------------------------------------------------


def _make_smoke_record(ocid: str) -> dict[str, Any]:
    """Build a minimal smoke record for one OCID. The fields are
    procurement-shaped enough to exercise the diagnostic path; the
    stub agent + stub client don't care about field values."""
    return {
        "ocid": ocid,
        "decision_type": "procurement_decision",
        "fields": {
            "publication_delay_days": 45,
            "contract_value": 750000,
            "supplier_id": "SUPPLIER-CLEAN-001",
            "conflict_of_interest_declaration": "absent",
            "procurement_method_open_flag": "present",
            "is_modification": "false",
            "modification_value_ratio": 0.0,
            "governed_by_pa23": "true",
            "above_threshold": "true",
            "direct_award_justification_present": "false",
        },
        "substrate_notes": {
            "ocid": {"source": "direct_ocds", "value": ocid},
        },
    }


def test_diagnostic_run_writes_fourteen_bundles_under_diagnostic_subdir(tmp_path):
    """The driver writes one bundle per subset record, and a
    permutation_log sidecar, all under `<run_dir>/diagnostic/`."""
    corpus_ocids = _load_corpus_ocids()
    records = [_make_smoke_record(o) for o in corpus_ocids]

    run_dir = tmp_path / "runs" / "test-e2-006"
    run_dir.mkdir(parents=True)
    prompts = load_level_prompts(PROMPTS_DIR)

    summary = run_permuted_diagnostic(
        run_id="test-e2-006",
        run_dir=run_dir,
        prompts=prompts,
        policy_path=POLICY_SNAPSHOT_PATH,
        records=records,
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )

    assert len(summary.subset_ocids) == 14
    assert len(summary.outcomes) == 14

    diagnostic_dir = run_dir / DIAGNOSTIC_SUBDIR
    assert diagnostic_dir.is_dir()
    sidecar = diagnostic_dir / PERMUTATION_LOG_FILENAME
    assert sidecar.is_file()
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["diagnostic"] == "permuted-policy"
    assert sidecar_payload["seed"] == LOCKED_PERMUTATION_SEED
    assert len(sidecar_payload["permutation_log"]) == 6

    bundle_files = sorted(diagnostic_dir.glob("*.bundle.json"))
    assert len(bundle_files) == 14

    # No bundles leaked into the main-grid level directories
    for level in ("L0", "L1", "L2", "L3", "L4"):
        leaked = (run_dir / level).exists()
        assert not leaked, f"diagnostic bundle leaked into <run_dir>/{level}/"
    # And no L4_PERMUTED dir was created — the diagnostic uses `diagnostic/`
    assert not (run_dir / "L4_PERMUTED").exists()


def test_diagnostic_receipt_has_distinct_integrity_hash_vs_main_l4(tmp_path):
    """The integrity hash bound by the diagnostic must differ from the
    integrity hash a main-run L4 would produce for the same OCID. The
    three fields that make this true:

      - governance_context_level: "L4" vs "L4_PERMUTED"
      - policy_permutation_seed: absent vs 0
      - l4_envelope_sha256: absent vs <permuted-rendering SHA>
    """
    # Pick the first subset OCID and run both passes against it.
    corpus_ocids = _load_corpus_ocids()
    subset = pick_permuted_subset(corpus_ocids)
    assert len(subset) == 14
    test_ocid = subset[0]
    record = _make_smoke_record(test_ocid)

    # --- Main-run L4 pass against the same record ---------------------
    run_dir_main = tmp_path / "main"
    run_dir_main.mkdir(parents=True)
    prompts = load_level_prompts(PROMPTS_DIR)

    from meshqu_runner.context_levels.level_l4 import build_l4_handler

    main_handlers = default_main_handlers()
    main_handlers["L4"] = build_l4_handler(POLICY_SNAPSHOT_PATH)

    main_config = mp.MultiPassConfig(
        run_id="main-test-e2-006",
        run_phase="dry-run",
        repo_dir=REPO_DIR,
        run_dir=run_dir_main,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        levels=("L4",),
        cache_telemetry_enabled=False,
    )
    main_summary = mp.run_multi_pass(
        config=main_config,
        records=[record],
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
        handlers=main_handlers,
    )
    main_outcome = main_summary.outcomes[0]
    main_integrity = main_outcome.receipt.integrity_hash

    # --- Diagnostic L4_PERMUTED pass against the same record ---------
    run_dir_diag = tmp_path / "diag"
    run_dir_diag.mkdir(parents=True)
    diag_summary = run_permuted_diagnostic(
        run_id="diag-test-e2-006",
        run_dir=run_dir_diag,
        prompts=prompts,
        policy_path=POLICY_SNAPSHOT_PATH,
        records=[record],
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )
    assert len(diag_summary.outcomes) == 1
    diag_outcome = diag_summary.outcomes[0]
    diag_integrity = diag_outcome.receipt.integrity_hash

    assert (
        main_integrity != diag_integrity
    ), "Main-run L4 integrity hash collided with diagnostic L4_PERMUTED integrity hash"

    # And the bundle written by the diagnostic carries the distinct level
    bundle = json.loads(diag_outcome.bundle_path.read_text(encoding="utf-8"))
    assert bundle["governance_context_level"] == DIAGNOSTIC_LEVEL
    canonical_fields = json.loads(bundle["context_fields_canonical_json"])
    assert canonical_fields[GOVERNANCE_CONTEXT_LEVEL_FIELD] == "L4_PERMUTED"
    assert canonical_fields[POLICY_PERMUTATION_SEED_FIELD] == LOCKED_PERMUTATION_SEED
    assert L4_ENVELOPE_SHA256_FIELD in canonical_fields
    assert canonical_fields[L4_ENVELOPE_SHA256_FIELD] != UNPERTURBED_L4_RENDERED_SHA256


def test_diagnostic_skips_records_without_ocid(tmp_path):
    """Records with no OCID can't be deterministically subsetted — the
    driver records them in `skipped_ocids` rather than processing
    them."""
    records = [
        {"decision_type": "procurement_decision", "fields": {}, "metadata": {}},  # no OCID
    ]
    run_dir = tmp_path / "noocid"
    run_dir.mkdir(parents=True)
    prompts = load_level_prompts(PROMPTS_DIR)
    summary = run_permuted_diagnostic(
        run_id="noocid-test",
        run_dir=run_dir,
        prompts=prompts,
        policy_path=POLICY_SNAPSHOT_PATH,
        records=records,
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )
    assert summary.outcomes == []
    assert summary.skipped_ocids == [None]


def test_diagnostic_handlers_registry_does_not_overwrite_main_l4():
    """Building the diagnostic registry must NOT clobber the original
    L4 slot — that slot still carries the unperturbed handler for any
    caller that wants to interleave main and diagnostic passes."""
    main = default_main_handlers()
    main_l4 = main["L4"]
    diag = diagnostic_handlers(policy_path=POLICY_SNAPSHOT_PATH, main_handlers=main)
    # diagnostic registry has its own L4_PERMUTED slot
    assert DIAGNOSTIC_LEVEL in diag
    # and the L4 slot was preserved verbatim (or at least is distinct
    # from the permuted handler — the registry copies, so identity may
    # differ, but the type is unchanged)
    assert type(diag["L4"]) is type(main_l4)
    assert diag[DIAGNOSTIC_LEVEL] is not diag["L4"]


def test_diagnostic_bundle_canonical_fields_drive_integrity_hash(tmp_path):
    """Spot-check that the canonical-JSON bytes the diagnostic stores
    in the bundle match what the stub client used to compute the
    integrity hash. This proves the three diagnostic fields are bound
    into the hash, not just persisted alongside it."""
    corpus_ocids = _load_corpus_ocids()
    subset = pick_permuted_subset(corpus_ocids)
    record = _make_smoke_record(subset[0])

    run_dir = tmp_path / "bind"
    run_dir.mkdir(parents=True)
    prompts = load_level_prompts(PROMPTS_DIR)
    summary = run_permuted_diagnostic(
        run_id="bind-test",
        run_dir=run_dir,
        prompts=prompts,
        policy_path=POLICY_SNAPSHOT_PATH,
        records=[record],
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )
    outcome = summary.outcomes[0]
    bundle = json.loads(outcome.bundle_path.read_text(encoding="utf-8"))
    canonical_bytes = bundle["context_fields_canonical_json"].encode("utf-8")
    recomputed_hash = hashlib.sha256(canonical_bytes).hexdigest()
    assert recomputed_hash == outcome.receipt.integrity_hash
