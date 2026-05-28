"""Tests for the deterministic kNN precedent selector + frozen archive.

Restored verbatim from E2's `test_precedent_selector.py` minus the L3
handler / additivity-invariant scenario (scenario 6 of the original
docstring). The precedent selector and precedent archive modules are
byte-identical between E2 and E3 (see `test_fork_parity.py`); their
behavioural tests belong in the same "preserve" bucket as the source
files themselves.

The L3 handler rendering + additivity-invariant scenario was stripped
because it imports the ladder handlers (`L3LiveHandler`,
`L1ContextHandler`, `L2ContextHandler`, `compose_user_message`) and
exercises the additive ladder semantics that E3 deliberately abandons
in favour of arm-aware dispatch.

Coverage retained from the E2 docstring:

  1. Frozen-archive loader produces 283 PrecedentRecord entries keyed
     by OCID; no HTTP transport is touched (asserted via socket mock).
  2. `select_precedents` is deterministic across re-runs for the 3
     smoke records — the same 4 OCIDs come back across 10 invocations.
  3. Self-exclusion holds: the target OCID never appears in its own
     precedent list (verified for the worked-example record
     `ca19e737-…` and for archive-driven cases).
  4. Tie-break by OCID ascending verified with a constructed tie case.
  5. k=4 produces exactly 4 precedents against the 283-record archive.

The worked-example record (`ca19e737-defb-4e5f-b216-ec97d2fe5859`, the
£57M case) gets its own dedicated "diagnostic" test that prints the 4
precedent picks + their salient fields. The E2 PR body quoted that
output; Sam read it to gauge whether the kNN "reads right" — comparable
value band, same regime, comparable method-flag status.
"""
from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from meshqu_runner.precedent_archive import (
    ArchiveLoadError,
    FROZEN_ARCHIVE_RELATIVE_PATH,
    PrecedentRecord,
    default_frozen_archive_dir,
    load_frozen_archive,
)
from meshqu_runner.precedent_selector import (
    DEFAULT_PRECEDENT_COUNT,
    TargetFeatures,
    select_precedents,
)


RUNNER_DIR = Path(__file__).resolve().parent.parent
E3_DIR = RUNNER_DIR.parent
REPO_DIR = E3_DIR.parent

# Worked-example record (the £57M case quoted in the E2 build package).
WORKED_EXAMPLE_DECISION_ID = "ca19e737-defb-4e5f-b216-ec97d2fe5859"
WORKED_EXAMPLE_OCID = "ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f"

# Smoke records — same fixture the multi_pass tests use.
SMOKE_FIXTURE = RUNNER_DIR / "tests" / "fixtures" / "smoke_records.json"


# ---------------------------------------------------------------------------
# Network-isolation guard
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_network():
    """Catch any code path that tries to open a socket. The frozen
    archive must be read from disk only — a regression here would be
    silent (decision-traces still load) but methodologically fatal
    (L3 isolation broken).

    Patching `socket.socket` covers requests / urllib / urllib3 / httpx.
    Local AF_UNIX usage (none in this codebase) would also be blocked,
    which is fine.
    """

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "Network access is forbidden in L3 tests. "
            "The frozen archive must be read from disk only."
        )

    with patch.object(socket, "socket", side_effect=_blocked) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Archive loader tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def archive() -> dict[str, PrecedentRecord]:
    """Load the canonical frozen E1 archive once per test module."""
    archive_dir = default_frozen_archive_dir(REPO_DIR)
    return load_frozen_archive(archive_dir)


def test_archive_loads_283_unique_records(archive):
    """The E1 archive carries 283 unique OCIDs (300 trace rows
    de-duplicated by decision_id). Documented in
    `planning/context_ladder_design.md`."""
    assert len(archive) == 283
    # OCID-keyed; values are PrecedentRecord.
    for ocid, record in archive.items():
        assert isinstance(record, PrecedentRecord)
        assert record.ocid == ocid


def test_archive_contains_worked_example(archive):
    """The £57M case must be present — the build package + PR body
    both reference it by OCID."""
    assert WORKED_EXAMPLE_OCID in archive
    target = archive[WORKED_EXAMPLE_OCID]
    assert target.contract_value == pytest.approx(57_000_000.0)
    assert target.regime_proxy == "PA23"
    assert target.contract_value_band == ">10M"
    # Stage A's L3 template references e1_agent_reasoning_text — confirm
    # it's non-empty (stop-condition is enforced by the loader).
    assert target.agent_reasoning.strip()


def test_archive_default_path_matches_context_ladder_design():
    """`FROZEN_ARCHIVE_RELATIVE_PATH` must point at the same `dry-run-7ddf7274-…`
    directory `context_ladder_design.md` §L3 names. Drift here would
    silently break the isolation contract."""
    assert "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d" in FROZEN_ARCHIVE_RELATIVE_PATH
    # Loader resolves against the repo root via default_frozen_archive_dir
    assert default_frozen_archive_dir(REPO_DIR).is_dir()


def test_archive_loader_raises_on_missing_dir(tmp_path):
    with pytest.raises(ArchiveLoadError):
        load_frozen_archive(tmp_path / "does-not-exist")


def test_archive_loader_raises_on_empty_reasoning(tmp_path):
    """Stage A's template references e1_agent_reasoning_text. Empty
    reasoning is a stop condition (per the build package). Reproduce
    with a minimal fixture archive."""
    archive_dir = tmp_path / "archive"
    outputs = archive_dir / "agent_outputs"
    outputs.mkdir(parents=True)

    decision_id = "deadbeef-1111-1111-1111-000000000001"
    ocid = "ocds-test-001"
    (archive_dir / "decision_traces.jsonl").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "ocid": ocid,
                "meshqu_verdict": "ALLOW",
                "violations": [],
            }
        )
        + "\n"
    )
    (outputs / f"{decision_id}.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "agent": {
                    "reasoning": "   ",  # empty after strip
                    "recommended_action": "x",
                },
                "user_message": json.dumps(
                    {
                        "fields": {
                            "contract_value": 1000,
                            "governed_by_pa23": "true",
                            "publication_delay_days": 1,
                        },
                        "substrate_notes": {
                            "governed_by_pa23": {
                                "detail": "awards[0].date=2026-01-01 > PA23 commencement"
                            }
                        },
                    }
                ),
            }
        )
    )

    with pytest.raises(ArchiveLoadError) as exc:
        load_frozen_archive(archive_dir)
    assert "empty agent.reasoning" in str(exc.value)


# ---------------------------------------------------------------------------
# Deterministic kNN tests
# ---------------------------------------------------------------------------


def _load_smoke_records() -> list[dict]:
    with SMOKE_FIXTURE.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def test_select_precedents_deterministic_across_reruns(archive):
    """The build-package contract: same inputs → same OCIDs, every
    invocation. We exercise this for all 3 smoke records, 10 re-runs
    each, asserting the OCID lists are byte-identical."""
    for record in _load_smoke_records():
        runs = [
            tuple(p.ocid for p in select_precedents(record, archive, k=4))
            for _ in range(10)
        ]
        # All 10 runs must return the same sequence (and the same
        # length = 4).
        assert all(r == runs[0] for r in runs)
        assert len(runs[0]) == 4


def test_select_precedents_returns_exactly_k(archive):
    """k=4 against the 283-record archive yields exactly 4 precedents
    for every smoke record (the archive has plenty of candidates in
    every distance bucket)."""
    for record in _load_smoke_records():
        precedents = select_precedents(record, archive, k=4)
        assert len(precedents) == 4


def test_select_precedents_zero_k_returns_empty(archive):
    """k=0 (or negative) yields an empty list — defensive degenerate."""
    record = _load_smoke_records()[0]
    assert select_precedents(record, archive, k=0) == []
    assert select_precedents(record, archive, k=-1) == []


def test_self_exclusion_for_worked_example(archive):
    """When the worked-example record is the target, NONE of its k
    precedents may carry its OCID. Critical correctness property."""
    target = archive[WORKED_EXAMPLE_OCID]
    precedents = select_precedents(target, archive, k=4)
    assert all(p.ocid != WORKED_EXAMPLE_OCID for p in precedents)
    # Also verify when the target is passed as a plain dict shaped
    # like the smoke fixture (the runner's actual call shape).
    target_as_dict = {
        "ocid": WORKED_EXAMPLE_OCID,
        "fields": {
            "contract_value": target.contract_value,
            "governed_by_pa23": target.governed_by_pa23,
            "procurement_method_open_flag": target.procurement_method_open_flag,
        },
    }
    precedents = select_precedents(target_as_dict, archive, k=4)
    assert all(p.ocid != WORKED_EXAMPLE_OCID for p in precedents)


def test_self_exclusion_across_archive(archive):
    """Spot-check self-exclusion holds for every archive entry as
    target. Cheap — 283 selections × 4 precedents."""
    for ocid, record in archive.items():
        precedents = select_precedents(record, archive, k=4)
        assert all(p.ocid != ocid for p in precedents), (
            f"Self appeared as precedent for {ocid}"
        )


def test_tie_break_by_ocid_ascending():
    """Constructed tie: three archive records with the same feature
    vector → the selector must pick OCIDs in ascending order. Without
    this property the selector is not deterministic when the archive
    has features with high collision (e.g. the 264-records-with-flag-absent
    cluster).
    """

    def make(ocid: str) -> PrecedentRecord:
        return PrecedentRecord(
            ocid=ocid,
            decision_id=f"d-{ocid}",
            award_date="2026-01-01",
            contract_value=200_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            publication_delay_days=10,
            meshqu_verdict="ALLOW",
            violations=(),
            agent_reasoning="r",
            agent_recommended_action=None,
        )

    archive = {
        "ocds-aaa": make("ocds-aaa"),
        "ocds-ccc": make("ocds-ccc"),
        "ocds-bbb": make("ocds-bbb"),
    }
    # Target shares features exactly with all 3 → all distances == 0,
    # tie broken by OCID ascending.
    target = {
        "ocid": "ocds-target",
        "fields": {
            "contract_value": 200_000,
            "governed_by_pa23": "true",
        },
    }
    precedents = select_precedents(target, archive, k=3)
    assert [p.ocid for p in precedents] == ["ocds-aaa", "ocds-bbb", "ocds-ccc"]


def test_fewer_candidates_than_k():
    """When the archive has fewer than k entries after self-exclusion,
    the selector returns however many exist — caller (the L3 handler)
    is responsible for deciding whether sub-k blocks are acceptable.
    For the 283-record archive this never triggers; tested with a
    constructed 2-record archive."""

    def make(ocid: str) -> PrecedentRecord:
        return PrecedentRecord(
            ocid=ocid,
            decision_id=f"d-{ocid}",
            award_date="2026-01-01",
            contract_value=200_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            publication_delay_days=10,
            meshqu_verdict="ALLOW",
            violations=(),
            agent_reasoning="r",
            agent_recommended_action=None,
        )

    archive = {
        "ocds-aaa": make("ocds-aaa"),
        "ocds-bbb": make("ocds-bbb"),
    }
    target = {"ocid": "ocds-aaa", "fields": {"contract_value": 200_000}}
    precedents = select_precedents(target, archive, k=4)
    assert len(precedents) == 1
    assert precedents[0].ocid == "ocds-bbb"


def test_target_features_projection_smoke():
    """Sanity-check the TargetFeatures projection over the 4 contract
    value bands + the 2 regime values."""
    tf = TargetFeatures.from_target(
        {"fields": {"contract_value": 50_000, "governed_by_pa23": "true"}}
    )
    assert tf.contract_value_band == "<100k"
    assert tf.regime == "PA23"

    tf = TargetFeatures.from_target(
        {"fields": {"contract_value": 300_000, "governed_by_pa23": "false"}}
    )
    assert tf.contract_value_band == "100k-500k"
    assert tf.regime == "PCR_2015"

    tf = TargetFeatures.from_target(
        {"fields": {"contract_value": 2_000_000, "governed_by_pa23": "true"}}
    )
    assert tf.contract_value_band == "500k-10M"

    tf = TargetFeatures.from_target(
        {"fields": {"contract_value": 100_000_000, "governed_by_pa23": "true"}}
    )
    assert tf.contract_value_band == ">10M"


# ---------------------------------------------------------------------------
# Worked-example diagnostic — read this in the PR body
# ---------------------------------------------------------------------------


def test_worked_example_picks_diagnostic(archive, capsys):
    """For the £57M case (`ca19e737-…`), print the 4 selected
    precedent OCIDs + key fields. The E2 PR body for E2-004 quoted this
    output; Sam read it to judge whether the kNN "reads right".

    The test asserts on STRUCTURAL properties only (4 precedents
    returned, all distinct from target). The qualitative judgement is
    in the printed output."""
    target = archive[WORKED_EXAMPLE_OCID]
    precedents = select_precedents(target, archive, k=4)

    assert len(precedents) == 4
    assert all(p.ocid != WORKED_EXAMPLE_OCID for p in precedents)

    # Print the diagnostic. Captured via capsys; the PR body quotes
    # this section.
    print()
    print("=" * 78)
    print(f"WORKED EXAMPLE — target OCID: {target.ocid}")
    print(f"  decision_id     : {target.decision_id}")
    print(
        f"  contract_value  : £{int(target.contract_value):,}  "
        f"band={target.contract_value_band}"
    )
    print(f"  regime_proxy    : {target.regime_proxy}")
    print(f"  method_open_flag: {target.procurement_method_open_flag!r}")
    print(f"  pub_delay_days  : {target.publication_delay_days}")
    print(f"  meshqu_verdict  : {target.meshqu_verdict}")
    print(f"  violations      : {list(target.violations)}")
    print()
    print(f"4 precedents picked by deterministic kNN (k={DEFAULT_PRECEDENT_COUNT}):")
    for i, p in enumerate(precedents, start=1):
        print(f"  [{i}] OCID: {p.ocid}")
        print(
            f"      contract_value : £{int(p.contract_value):,}  "
            f"band={p.contract_value_band}"
        )
        print(f"      regime_proxy   : {p.regime_proxy}")
        print(f"      method_flag    : {p.procurement_method_open_flag!r}")
        print(f"      pub_delay_days : {p.publication_delay_days}")
        print(f"      meshqu_verdict : {p.meshqu_verdict}")
        print(f"      violations     : {list(p.violations)}")
        print(f"      reasoning      : {p.agent_reasoning[:140]}")
    print("=" * 78)

    captured = capsys.readouterr()
    # Sanity — make sure the print actually fired and captured.
    assert "WORKED EXAMPLE" in captured.out
    assert all(p.ocid in captured.out for p in precedents)
