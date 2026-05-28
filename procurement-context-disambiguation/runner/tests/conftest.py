"""Pytest configuration for the E3 runner test suite.

The default record-loading path (``meshqu_runner.substrate_cache.load_cached_records``)
walks the E1 frozen archive on disk at
``procurement-decisions/results/runs/<E1_ARCHIVE_RUN_ID>/``. The archive
is multi-gigabyte and is not committed to the monorepo — Sam keeps it
locally, but CI runners and fresh clones don't have it.

When the archive is absent, we autouse-monkeypatch ``load_cached_records``
(and the related ``select_records`` / ``iter_cached_records`` helpers) to
return ``CachedRecord`` instances reconstructed from the committed test
fixture at ``tests/fixtures/full_corpus_records.json``. The fixture
carries all 283 records in OCID-ascending order with the exact shape
the loader emits (``ocid`` / ``decision_type`` / ``fields`` /
``substrate_notes``), so the runner's record-consumption paths see the
same record content either way.

When the real archive IS present, this fixture is a no-op — we want the
real archive walker exercised whenever it's available, and the fixture
only kicks in to keep the test suite hermetic in fresh environments.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))


def _archive_available() -> bool:
    """Return True iff the E1 frozen archive is present at the expected
    on-disk location. Imports happen lazily so the substrate_cache
    module's import-time invariants are honoured."""
    from meshqu_runner.substrate_cache import archive_root  # noqa: WPS433

    # Repo root = runner_dir.parents[1] (runner → e3 dir → repo root).
    repo_dir = _RUNNER_DIR.parents[1]
    return archive_root(repo_dir).exists()


def _build_cached_records_from_fixture() -> list:
    """Load the committed full-corpus fixture and reconstruct
    ``CachedRecord`` instances. Returns a list of 283 records,
    OCID-ascending, matching the loader's deterministic order."""
    from meshqu_runner.substrate_cache import CachedRecord, E1_ARCHIVE_RUN_ID

    fixture_path = (
        _RUNNER_DIR / "tests" / "fixtures" / "full_corpus_records.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    if not records:
        raise RuntimeError(
            f"full_corpus_records.json fixture is empty at {fixture_path}"
        )
    out: list[CachedRecord] = []
    for entry in records:
        out.append(
            CachedRecord(
                ocid=str(entry["ocid"]),
                decision_type=str(entry["decision_type"]),
                fields=dict(entry["fields"]),
                substrate_notes={
                    k: dict(v)
                    for k, v in (entry.get("substrate_notes") or {}).items()
                },
                metadata={
                    "ocid": entry["ocid"],
                    "experiment_substrate": "uk_contracts_finder_ocds",
                    "adapter_version": "0.1.0-cached-fixture",
                    "e1_archive_run_id": E1_ARCHIVE_RUN_ID,
                },
            )
        )
    # Loader contract: OCID-ascending. The fixture is already sorted but
    # belt-and-braces to mirror the loader.
    out.sort(key=lambda cr: cr.ocid)
    return out


@pytest.fixture(autouse=True)
def _patch_substrate_cache_when_archive_absent(monkeypatch):
    """Autouse — substitute ``load_cached_records`` / ``select_records`` /
    ``iter_cached_records`` with fixture-backed implementations when the
    real E1 archive isn't on disk. No-op when the archive IS present.

    Scoped to autouse=True for every test in this directory so the
    existing test suite that already calls into the loader transparently
    works in fresh checkouts. Sam's local env has the archive, so this
    fixture is invisible there."""
    if _archive_available():
        return

    from meshqu_runner import substrate_cache as _sc

    cached = _build_cached_records_from_fixture()

    def _fake_load_cached_records(repo_dir):
        return list(cached)

    def _fake_iter_cached_records(repo_dir):
        for record in cached:
            yield record

    def _fake_select_records(repo_dir, ocids):
        by_ocid = {cr.ocid: cr for cr in cached}
        missing = [o for o in ocids if o not in by_ocid]
        if missing:
            raise _sc.SubstrateCacheError(
                f"Requested OCIDs not present in fixture: {missing}"
            )
        return [by_ocid[o] for o in ocids]

    monkeypatch.setattr(_sc, "load_cached_records", _fake_load_cached_records)
    monkeypatch.setattr(_sc, "iter_cached_records", _fake_iter_cached_records)
    monkeypatch.setattr(_sc, "select_records", _fake_select_records)
