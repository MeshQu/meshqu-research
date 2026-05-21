"""Tests for E2-002 — L0 baseline + substrate cache reader.

Covers the done criteria from
`planning/build_packages/e2-002-l0-baseline-substrate-cache.md`:

- Substrate cache loads 283 records.
- OCIDs are deterministic across re-runs (sorted ascending).
- Provenance envelope is intact (status / confidence / detail / value).
- NO network calls are made by the cache reader (requests transport is
  asserted untouched).
- L0 prompt for the worked-example OCID matches E1's prompt byte-for-byte.
- An end-to-end stub L0 pass through the multi-pass runner emits 3
  bundles with `governance_context_level == "L0"`.
- The L0-vs-E1 comparator script produces the expected table shape.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from meshqu_runner import multi_pass as mp
from meshqu_runner.context_levels.level_l0 import L0LiveHandler, install_live_l0
from meshqu_runner.eval_loop import build_user_message
from meshqu_runner.level_handlers import default_main_handlers
from meshqu_runner.substrate_cache import (
    E1_ARCHIVE_RUN_ID,
    EXPECTED_RECORD_COUNT,
    CachedRecord,
    SubstrateCacheError,
    archive_root,
    load_cached_records,
    select_records,
)


RUNNER_DIR = Path(__file__).resolve().parent.parent  # procurement-context-gradient/runner/
E2_DIR = RUNNER_DIR.parent  # procurement-context-gradient/
REPO_DIR = E2_DIR.parent  # meshqu-research/
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"

E1_ARCHIVE_DIR = REPO_DIR / "procurement-decisions" / "results" / "runs" / E1_ARCHIVE_RUN_ID

# The worked-example record (`ca19e737-…` decision_id, £57M case per
# procurement-context-gradient/README.md). Its OCID is fixed in E1's
# decision_traces.jsonl.
WORKED_EXAMPLE_DECISION_ID = "ca19e737-defb-4e5f-b216-ec97d2fe5859"
WORKED_EXAMPLE_OCID = "ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f"


# ---------------------------------------------------------------------------
# Module-scoped archive-presence gate
# ---------------------------------------------------------------------------


pytestmark = pytest.mark.skipif(
    not E1_ARCHIVE_DIR.exists(),
    reason=(
        f"E1 frozen archive at {E1_ARCHIVE_DIR} not present — these tests "
        "require the procurement-decisions/ archival results to be in the repo."
    ),
)


# ---------------------------------------------------------------------------
# Substrate cache reader
# ---------------------------------------------------------------------------


def test_load_cached_records_returns_283_records():
    """The frozen archive deduplicates 300 release events to 283 unique
    OCIDs — locked by `planning/substrate.md`."""
    records = load_cached_records(REPO_DIR)
    assert len(records) == EXPECTED_RECORD_COUNT == 283


def test_load_cached_records_is_ocid_ascending():
    """Order must be deterministic — tests pin the order so future
    re-runs are reproducible bit-for-bit."""
    records = load_cached_records(REPO_DIR)
    ocids = [r.ocid for r in records]
    assert ocids == sorted(ocids)


def test_load_cached_records_is_deterministic_across_calls():
    """Two consecutive calls produce identical OCID order. Belt-and-
    braces on the determinism guarantee — sort_keys=True is necessary
    but not sufficient if the dedup logic ever picked a different
    'first occurrence' between calls."""
    a = [r.ocid for r in load_cached_records(REPO_DIR)]
    b = [r.ocid for r in load_cached_records(REPO_DIR)]
    assert a == b


def test_load_cached_records_provenance_envelope_intact():
    """Every record carries the full substrate_notes envelope: each
    field has status / confidence / detail (value optional when absent).
    This is the substrate-honesty contract — losing the envelope would
    make L0 NOT a reproducible re-run of E1."""
    records = load_cached_records(REPO_DIR)
    sample = records[0]
    assert sample.substrate_notes, "expected non-empty substrate_notes"
    for field_name, note in sample.substrate_notes.items():
        assert "status" in note, f"{field_name}: missing status"
        assert "confidence" in note, f"{field_name}: missing confidence"
        assert "detail" in note, f"{field_name}: missing detail"


def test_load_cached_records_carries_e1_reference_fields():
    """Each record passes through the E1 audit fields the comparator
    needs (decision_id, agent verdict, MeshQu verdict, violations,
    integrity hash)."""
    records = load_cached_records(REPO_DIR)
    sample = records[0]
    assert sample.e1_decision_id, "e1_decision_id must be non-empty"
    assert sample.e1_meshqu_verdict in {"ALLOW", "DENY", "REVIEW"}
    # agent_verdict CAN be None (parse failure case in E1); but on a
    # clean archive row it's one of the verdict strings.
    assert sample.e1_agent_verdict in {"ALLOW", "DENY", "REVIEW", None}
    assert isinstance(sample.e1_violations, list)
    assert isinstance(sample.e1_integrity_hash, str)


def test_load_cached_records_no_network_calls_made():
    """The cache reader must NEVER hit the network. We patch the
    `requests` module's top-level get/post to assert they aren't called.

    If a future refactor pulled in an HTTP client transitively, this
    test would catch it — the cache reader is meant to be pure disk."""
    import requests  # type: ignore

    with patch.object(requests, "get") as mock_get, patch.object(
        requests, "post"
    ) as mock_post, patch.object(requests.Session, "get") as mock_sess_get:
        load_cached_records(REPO_DIR)
    mock_get.assert_not_called()
    mock_post.assert_not_called()
    mock_sess_get.assert_not_called()


def test_archive_root_resolves_correctly():
    """Bookkeeping: the archive_root helper points at the expected directory."""
    root = archive_root(REPO_DIR)
    assert root == E1_ARCHIVE_DIR


def test_missing_archive_raises_substrate_cache_error(tmp_path: Path):
    """The cache reader fails loudly when the archive is missing — it
    must NEVER silently fall back to a live fetch (substrate posture)."""
    with pytest.raises(SubstrateCacheError):
        load_cached_records(tmp_path)


def test_select_records_preserves_input_order():
    """Caller-driven selection by OCID, ordering preserved."""
    records = load_cached_records(REPO_DIR)
    pick = [records[5].ocid, records[1].ocid, records[10].ocid]
    selected = select_records(REPO_DIR, pick)
    assert [r.ocid for r in selected] == pick


def test_select_records_raises_on_missing_ocid():
    """Asking for an OCID not in the archive is an error, not a silent
    short list. The smoke runner relies on this guard."""
    with pytest.raises(SubstrateCacheError):
        select_records(REPO_DIR, ["ocds-b5fd17-NOT-A-REAL-OCID"])


# ---------------------------------------------------------------------------
# L0 prompt byte-for-byte reproducibility
# ---------------------------------------------------------------------------


def _find_record_by_ocid(records: list[CachedRecord], ocid: str) -> CachedRecord:
    match = next((r for r in records if r.ocid == ocid), None)
    if match is None:
        raise AssertionError(f"OCID {ocid} not present in cache")
    return match


def _read_e1_user_message(decision_id: str) -> str:
    """Pull the raw user_message string E1 sent to the agent."""
    path = E1_ARCHIVE_DIR / "agent_outputs" / f"{decision_id}.json"
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)["user_message"]


def test_l0_prompt_matches_e1_byte_for_byte_worked_example():
    """For the worked-example record, the L0 user_message reconstructed
    via the cache reader + build_user_message must equal E1's raw
    user_message bytes.

    This is the gold-standard reproducibility check the package
    requires. If this fails, the substrate envelope serialisation has
    drifted between E1's runner and E2's, which would invalidate the
    L0 baseline."""
    records = load_cached_records(REPO_DIR)
    rec = _find_record_by_ocid(records, WORKED_EXAMPLE_OCID)
    assert rec.e1_decision_id == WORKED_EXAMPLE_DECISION_ID

    rebuilt = build_user_message(
        context={
            "decision_type": rec.decision_type,
            "fields": rec.fields,
        },
        substrate_notes=rec.substrate_notes,
    )
    original = _read_e1_user_message(rec.e1_decision_id)

    assert rebuilt == original, (
        "L0 user_message does NOT match E1's raw user_message bytes. "
        "The substrate envelope serialisation has drifted between E1's "
        "and E2's runners — the L0 baseline cannot be trusted as a "
        "reproducibility check until this is fixed."
    )


def test_l0_prompt_matches_e1_for_all_records():
    """Stronger version of the byte-for-byte check: not just one OCID,
    every one of the 283 records reconstructs verbatim.

    Marked separately so the worked-example check runs first and fails
    fast in CI without having to compare all 283 records on every run.
    """
    records = load_cached_records(REPO_DIR)
    mismatches: list[str] = []
    for rec in records:
        rebuilt = build_user_message(
            context={"decision_type": rec.decision_type, "fields": rec.fields},
            substrate_notes=rec.substrate_notes,
        )
        original = _read_e1_user_message(rec.e1_decision_id)
        if rebuilt != original:
            mismatches.append(rec.ocid)
    assert not mismatches, (
        f"{len(mismatches)} of {len(records)} records' L0 user_message "
        f"diverged from the E1 archive. First few: {mismatches[:5]}"
    )


# ---------------------------------------------------------------------------
# L0 live handler — empty-addendum contract
# ---------------------------------------------------------------------------


def test_l0_live_handler_returns_empty_addendum():
    """L0 is the baseline. Returns empty string by definition. The
    reproducibility guarantee comes from the substrate cache reader
    feeding the same record — not from any prompt transformation
    here."""
    from meshqu_runner.prompt_loader import LEVEL_PROMPT_FILES, load_level_prompts

    handler = L0LiveHandler()
    prompts = load_level_prompts(PROMPTS_DIR)
    addendum = handler.build_addendum(
        record={"ocid": "ocds-test"},
        ocid="ocds-test",
        prompts=prompts,
    )
    assert addendum == ""


def test_install_live_l0_swaps_registry_entry():
    """The registry-replacement pattern mutates a registry dict in place
    AND returns the same dict for chaining."""
    handlers = default_main_handlers()
    original_l0 = handlers["L0"]
    returned = install_live_l0(handlers)
    assert returned is handlers
    assert isinstance(handlers["L0"], L0LiveHandler)
    assert handlers["L0"] is not original_l0
    # Other entries are untouched (L1..L4 still the stubs E2-001 wired).
    for level in ("L1", "L2", "L3", "L4"):
        assert handlers[level].level == level


# ---------------------------------------------------------------------------
# End-to-end stub multi-pass run on 3 smoke records from the cache
# ---------------------------------------------------------------------------


@pytest.fixture()
def three_cached_records() -> list[dict[str, Any]]:
    """The 3 default smoke records, as plain record dicts the
    orchestrator consumes."""
    records = load_cached_records(REPO_DIR)
    # Worked example + first ALLOW + first single-rule DENY.
    by_ocid = sorted(records, key=lambda r: r.ocid)
    worked = next(r for r in by_ocid if r.e1_decision_id == WORKED_EXAMPLE_DECISION_ID)
    clean_allow = next(
        r for r in by_ocid if r.e1_meshqu_verdict == "ALLOW" and not r.e1_violations
    )
    single_deny = next(
        r for r in by_ocid if r.e1_meshqu_verdict == "DENY" and len(r.e1_violations) == 1
    )
    picked: list[CachedRecord] = []
    for r in (worked, clean_allow, single_deny):
        if r.ocid not in {p.ocid for p in picked}:
            picked.append(r)
    return [r.as_record() for r in picked]


def test_stub_run_at_l0_only_produces_three_bundles(
    tmp_path: Path, three_cached_records: list[dict[str, Any]]
):
    """End-to-end stub run at L0 only: 3 records × 1 level = 3 bundles.
    Each bundle carries `governance_context_level == "L0"` and `is_stub
    == True`.

    Establishes the cache-reader → orchestrator → bundle pipeline works
    end-to-end. The live OpenAI / MeshQu paths are gated by E2-007."""
    handlers = install_live_l0(default_main_handlers())

    run_dir = tmp_path / "runs" / "stub-l0-baseline"
    config = mp.MultiPassConfig(
        run_id="stub-l0-baseline",
        run_phase="smoke",
        repo_dir=REPO_DIR,
        run_dir=run_dir,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        levels=("L0",),
    )
    summary = mp.run_multi_pass(
        config=config,
        records=three_cached_records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
        handlers=handlers,
    )

    assert len(summary.outcomes) == 3
    for outcome in summary.outcomes:
        assert outcome.level == "L0"
        assert outcome.is_stub is True
        # Bundle exists on disk in the L0 subdirectory.
        assert outcome.bundle_path.exists()
        assert outcome.bundle_path.parent.name == "L0"


# ---------------------------------------------------------------------------
# Comparator script — table shape + selection logic
# ---------------------------------------------------------------------------


@pytest.fixture()
def comparator_module():
    """Import compare_l0_to_e1 via its scripts/ path."""
    scripts_dir = RUNNER_DIR / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import compare_l0_to_e1  # type: ignore

        return compare_l0_to_e1
    finally:
        try:
            sys.path.remove(str(scripts_dir))
        except ValueError:
            pass


def test_default_smoke_selection_picks_three_distinct_ocids(comparator_module):
    """The deterministic smoke selection produces 3 distinct OCIDs in
    the worked / clean-allow / single-deny order."""
    records = load_cached_records(REPO_DIR)
    ocids = comparator_module.select_default_smoke_ocids(records)
    assert len(ocids) == 3
    assert len(set(ocids)) == 3
    # The worked example is FIRST in the default ordering.
    assert ocids[0] == WORKED_EXAMPLE_OCID


def test_comparator_against_stub_run_marks_stub_note(
    tmp_path: Path, three_cached_records: list[dict[str, Any]], comparator_module
):
    """Drive the comparator against a stub run. The stub always emits
    `verdict=REVIEW` so verdicts won't match the archive — but the
    comparator MUST flag each row with the stub note so the PR-body
    reader knows this isn't a live reproducibility check.

    Per the package's note on temp=0 noise: verdict-mismatch on 1 of 3
    records is within OpenAI backend noise. We don't assert on that in
    the stub test — the stub's deterministic REVIEW verdict is the
    expected mismatch shape against the live E1 archive."""
    handlers = install_live_l0(default_main_handlers())
    run_dir = tmp_path / "runs" / "stub-cmp"
    config = mp.MultiPassConfig(
        run_id="stub-cmp",
        run_phase="smoke",
        repo_dir=REPO_DIR,
        run_dir=run_dir,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        levels=("L0",),
    )
    mp.run_multi_pass(
        config=config,
        records=three_cached_records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
        handlers=handlers,
    )

    rows = comparator_module.compare(
        repo_dir=REPO_DIR,
        run_dir=run_dir,
        ocids=[r["ocid"] for r in three_cached_records],
    )
    assert len(rows) == 3
    for row in rows:
        # The stub note is the load-bearing signal — a PR reader sees
        # it and knows the run wasn't a real reproducibility check.
        assert row.note == "stub bundle (not a live reproducibility check)"
        # Stub agent always returns REVIEW; stub MeshQu always returns REVIEW.
        assert row.l0_agent_verdict == "REVIEW"
        assert row.l0_meshqu_verdict == "REVIEW"


def test_format_table_returns_string(comparator_module):
    """Smoke test on the table renderer — used in the PR body."""
    from compare_l0_to_e1 import VerdictRow  # type: ignore

    row = VerdictRow(
        ocid="ocds-b5fd17-abcdef0123456789",
        e1_decision_id="dec-1",
        e1_meshqu_verdict="ALLOW",
        l0_meshqu_verdict="ALLOW",
        e1_agent_verdict="REVIEW",
        l0_agent_verdict="REVIEW",
        meshqu_match=True,
        agent_match=True,
    )
    out = comparator_module.format_table([row])
    assert "OCID" in out
    # The OCID column shows the last 12 chars per the renderer's design
    # — short enough for a markdown table, unique enough for 283 records.
    assert row.ocid[-12:] in out
    assert "ALLOW" in out
