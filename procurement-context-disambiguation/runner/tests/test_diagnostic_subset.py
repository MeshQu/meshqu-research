"""E3-007 — diagnostic subset selector tests.

Determinism, reproducibility, and artifact-vs-code-coherence are the
three things that have to hold for the rest of the diagnostic story
to mean anything. If any of these fail, the subset is no longer a
locked reference set.

Test coverage (mirrors the build package §3 + the orchestrator's
"determinism check is load-bearing" requirement):

  1. Twice-run identity over the same input.
  2. Live-substrate-enumeration ↔ sorted-fixture agreement.
  3. ``len(ocids) == 100`` on the 283-corpus.
  4. No verdict / tenant filter (selector takes OCIDs only — proved
     structurally by the function signature, but we lock it with an
     explicit "synthetic OCID list, no records attached" test).
  5. Committed ``planning/diagnostic_subset.json`` matches what the
     live selector produces from the live substrate cache (file
     does not drift from code).
  6. All 100 picked OCIDs are present in the frozen 283-corpus (no
     fabricated identifiers).
  7. Position-100 vs position-101 sha256 hashes differ (cut-off is
     unambiguous; the collision guard would have raised otherwise,
     but pinning this in a test makes the claim falsifiable).
  8. Stop condition: duplicate OCIDs in input → ``DiagnosticSubsetError``.
  9. Stop condition: ``n`` larger than corpus → ``DiagnosticSubsetError``.
 10. Stop condition: sha256 collision at the cut-off → raises.
 11. Output order is hash-ascending (the selection-order contract
     downstream consumers will rely on).
 12. Artifact shape sanity: required keys present, types correct, no
     extra keys silently snuck in by a future refactor.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from meshqu_runner.diagnostic.subset_selector import (
    ARTIFACT_RELATIVE_PATH,
    CORPUS_SOURCE,
    DIAGNOSTIC_SUBSET_SIZE,
    DiagnosticSubsetError,
    LOCKED_TAG,
    SELECTION_RULE,
    build_artifact,
    emit_artifact_json,
    load_corpus_ocids,
    select_diagnostic_subset,
)
from meshqu_runner.substrate_cache import EXPECTED_RECORD_COUNT


RUNNER_DIR = Path(__file__).resolve().parent.parent
E3_DIR = RUNNER_DIR.parent
REPO_DIR = E3_DIR.parent
ARTIFACT_PATH = REPO_DIR / ARTIFACT_RELATIVE_PATH


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_ocids() -> list[str]:
    """The 283-corpus OCIDs, loaded once per test module.

    Module-scoped because ``load_cached_records`` walks 283 sidecar
    files; sharing the result across tests keeps the test suite snappy
    without sacrificing isolation (the list is never mutated)."""
    return load_corpus_ocids(REPO_DIR)


@pytest.fixture(scope="module")
def selected(corpus_ocids: list[str]) -> list[str]:
    """The selector's output over the live corpus."""
    return select_diagnostic_subset(corpus_ocids)


# ---------------------------------------------------------------------------
# 1. Determinism — twice-run identity
# ---------------------------------------------------------------------------


def test_selector_is_deterministic_across_invocations(corpus_ocids: list[str]) -> None:
    """Running the selector twice over the same input must return the
    same list in the same order.

    This is the load-bearing reproducibility claim. If this fails the
    whole "same 100 records on both arms" guarantee dies."""
    first = select_diagnostic_subset(corpus_ocids)
    second = select_diagnostic_subset(corpus_ocids)
    assert first == second, (
        "Selector returned different outputs across two invocations on "
        "identical input. Determinism contract broken."
    )


def test_selector_is_deterministic_across_input_orderings(corpus_ocids: list[str]) -> None:
    """Sort order of the *input* must not affect the *output*.

    The selector re-sorts by digest internally; shuffling the input
    must produce a byte-identical output. This catches a future
    refactor that accidentally introduced an order-dependent fast
    path (e.g. "if already sorted, skip the digest-sort")."""
    reversed_in = list(reversed(corpus_ocids))
    assert select_diagnostic_subset(corpus_ocids) == select_diagnostic_subset(reversed_in)


# ---------------------------------------------------------------------------
# 2. Live-substrate ↔ sorted-fixture agreement
# ---------------------------------------------------------------------------


def test_selector_output_matches_independent_recomputation(corpus_ocids: list[str]) -> None:
    """Independent verification of the rule: recompute ``sha256(ocid)``
    here in the test, sort, slice, and assert equality.

    This is the "is the implementation actually applying the rule the
    spec says?" check. If the selector's internal helper ever drifted
    from "sha256 of UTF-8 bytes, lex-sort ascending", this test would
    fail — independently of the selector's own self-tests."""
    expected = sorted(
        ((hashlib.sha256(o.encode("utf-8")).hexdigest(), o) for o in corpus_ocids),
        key=lambda t: t[0],
    )
    expected_ocids = [o for _, o in expected[:DIAGNOSTIC_SUBSET_SIZE]]
    assert select_diagnostic_subset(corpus_ocids) == expected_ocids


# ---------------------------------------------------------------------------
# 3. Exact count
# ---------------------------------------------------------------------------


def test_selector_returns_exactly_one_hundred(selected: list[str]) -> None:
    """``len(ocids) == 100`` — the locked diagnostic size."""
    assert len(selected) == 100
    assert DIAGNOSTIC_SUBSET_SIZE == 100  # module constant pin


# ---------------------------------------------------------------------------
# 4. No verdict / tenant filter — synthetic-OCID round-trip
# ---------------------------------------------------------------------------


def test_selector_filters_purely_on_ocid_identity() -> None:
    """The selector takes a list of strings and outputs a list of
    strings. There is no path through it that depends on a verdict, a
    tenant, a policy snapshot, or any other context.

    Lock this structurally with a synthetic OCID list — no MeshQu
    records attached, no verdicts, just strings. The selector works
    and returns exactly n of them, deterministically."""
    synthetic = [f"ocds-synth-{i:04d}" for i in range(200)]
    out = select_diagnostic_subset(synthetic, n=50)
    assert len(out) == 50
    assert all(o in synthetic for o in out)
    # And the rule still holds on synthetic input
    expected = sorted(
        ((hashlib.sha256(o.encode("utf-8")).hexdigest(), o) for o in synthetic),
        key=lambda t: t[0],
    )
    assert out == [o for _, o in expected[:50]]


# ---------------------------------------------------------------------------
# 5. Committed artifact ↔ live selector coherence
# ---------------------------------------------------------------------------


def test_committed_artifact_matches_live_selector(
    corpus_ocids: list[str], selected: list[str]
) -> None:
    """The file on disk must match what the selector produces from the
    live substrate cache.

    If they drift, either the file was edited by hand (illegal — it's
    a locked artifact regenerated by the CLI) or the selector changed
    semantics post-lock (also illegal — would invalidate v0.3 tag).
    Either way, surface."""
    assert ARTIFACT_PATH.exists(), (
        f"Committed artifact missing: {ARTIFACT_PATH}. "
        f"Regenerate with `python -m meshqu_runner.diagnostic.subset_selector --emit "
        f"> {ARTIFACT_RELATIVE_PATH}`."
    )
    with ARTIFACT_PATH.open("r", encoding="utf-8") as fp:
        on_disk = json.load(fp)

    assert on_disk["ocids"] == selected, (
        "Committed diagnostic_subset.json drifted from the live selector. "
        "Regenerate the file."
    )
    assert on_disk["n"] == 100
    assert on_disk["selection_rule"] == SELECTION_RULE
    assert on_disk["corpus_source"] == CORPUS_SOURCE
    assert on_disk["tag"] == LOCKED_TAG
    assert on_disk["experiment"] == "E3"


# ---------------------------------------------------------------------------
# 6. Picked OCIDs are real (subset of the 283-corpus)
# ---------------------------------------------------------------------------


def test_all_picked_ocids_are_in_the_frozen_corpus(
    corpus_ocids: list[str], selected: list[str]
) -> None:
    """Sanity: no fabricated OCIDs. Every picked OCID must come from
    the substrate cache."""
    corpus_set = set(corpus_ocids)
    assert set(selected).issubset(corpus_set)
    assert len(set(selected)) == len(selected), "Selector emitted a duplicate"


def test_corpus_size_is_283(corpus_ocids: list[str]) -> None:
    """The frozen archive must still be 283 records. If this fails the
    archive has drifted post-v0.3-lock; surface to Sam, do not re-cut
    the subset against a moving corpus."""
    assert len(corpus_ocids) == EXPECTED_RECORD_COUNT == 283


# ---------------------------------------------------------------------------
# 7. Cut-off is unambiguous (positions 100 and 101 have different hashes)
# ---------------------------------------------------------------------------


def test_no_hash_collision_at_cut_boundary(corpus_ocids: list[str]) -> None:
    """Position-100 (last picked) and position-101 (first dropped) must
    have different sha256 digests, otherwise the cut is ambiguous.

    The selector raises ``DiagnosticSubsetError`` if this fires; this
    test pins the *absence* of a collision so the claim "the 100th and
    101st digests are different" is checkable as a positive assertion
    in CI, not only a not-raised-an-exception."""
    keyed = sorted(
        ((hashlib.sha256(o.encode("utf-8")).hexdigest(), o) for o in corpus_ocids),
        key=lambda t: t[0],
    )
    assert keyed[99][0] != keyed[100][0], (
        f"sha256 collision at cut boundary: {keyed[99]} vs {keyed[100]}. "
        f"The 100th and 101st picks would be ambiguous."
    )


# ---------------------------------------------------------------------------
# 8. Stop condition: duplicates raise
# ---------------------------------------------------------------------------


def test_duplicate_ocids_raise() -> None:
    """The substrate cache promises unique OCIDs. A duplicate is an
    upstream bug; surface it rather than silently de-dup (which would
    shift the cut boundary)."""
    with pytest.raises(DiagnosticSubsetError, match="Duplicate OCID"):
        select_diagnostic_subset(["a", "b", "a"])


# ---------------------------------------------------------------------------
# 9. Stop condition: n larger than corpus raises
# ---------------------------------------------------------------------------


def test_n_larger_than_corpus_raises() -> None:
    """A misconfigured caller (n=500 against a 283-corpus) gets a
    loud failure, not a silently-truncated list."""
    with pytest.raises(DiagnosticSubsetError, match="exceeds corpus size"):
        select_diagnostic_subset(["a", "b", "c"], n=10)


# ---------------------------------------------------------------------------
# 10. Stop condition: cut-off collision raises
# ---------------------------------------------------------------------------


def test_cut_boundary_collision_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ``hashlib.sha256`` (as imported by the selector) so two
    distinct OCIDs produce identical digests at the cut boundary, then
    confirm ``DiagnosticSubsetError`` fires.

    This is testing the *guard* — the real path can never reach this
    state at sha256 scale, but the guard is load-bearing and we want
    the failure mode pinned in a test."""

    class _ConstantDigest:
        def __init__(self, _bytes: bytes) -> None:
            pass

        def hexdigest(self) -> str:
            return "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

    import meshqu_runner.diagnostic.subset_selector as mod

    monkeypatch.setattr(mod.hashlib, "sha256", _ConstantDigest)
    with pytest.raises(DiagnosticSubsetError, match="collision at cut-off"):
        select_diagnostic_subset(["a", "b", "c", "d"], n=2)


# ---------------------------------------------------------------------------
# 11. Output order is hash-ascending (downstream relies on this)
# ---------------------------------------------------------------------------


def test_output_order_is_hash_ascending(selected: list[str]) -> None:
    """The selection-order contract: the returned list is sorted by
    sha256(ocid) ascending, NOT by OCID ascending. Downstream
    consumers (E3-008) can rely on this ordering."""
    digests = [hashlib.sha256(o.encode("utf-8")).hexdigest() for o in selected]
    assert digests == sorted(digests)


# ---------------------------------------------------------------------------
# 12. Artifact shape sanity
# ---------------------------------------------------------------------------


def test_build_artifact_shape(selected: list[str]) -> None:
    """Shape of the in-memory artifact dict — pin the keys and types so
    a future refactor that drops a field or changes a type triggers
    a CI failure."""
    art = build_artifact(selected, generated_at="2026-05-28T00:00:00+00:00")
    assert set(art.keys()) == {
        "experiment",
        "selection_rule",
        "corpus_source",
        "n",
        "tag",
        "generated_at",
        "ocids",
    }
    assert art["experiment"] == "E3"
    assert art["selection_rule"] == SELECTION_RULE
    assert art["corpus_source"] == CORPUS_SOURCE
    assert art["n"] == 100
    assert art["tag"] == LOCKED_TAG
    assert art["generated_at"] == "2026-05-28T00:00:00+00:00"
    assert isinstance(art["ocids"], list)
    assert all(isinstance(o, str) for o in art["ocids"])
    assert art["ocids"] == selected  # not mutated


def test_emit_artifact_json_round_trips(selected: list[str]) -> None:
    """The serialiser produces parseable JSON whose decoded form is
    structurally equal to the input artifact. Trailing newline is
    enforced (POSIX text-file convention)."""
    art = build_artifact(selected, generated_at="2026-05-28T00:00:00+00:00")
    payload = emit_artifact_json(art)
    assert payload.endswith("\n")
    assert json.loads(payload) == art
