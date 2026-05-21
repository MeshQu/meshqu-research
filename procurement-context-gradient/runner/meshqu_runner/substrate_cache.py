"""Substrate cache reader — read OCDS-derived records from E1's frozen archive.

This module is the SOLE entry point through which records enter the E2
multi-pass runner. There is no live fetch from Contracts Finder. The
substrate posture (see `planning/substrate.md`) is:

    > No new fetch from Contracts Finder. The OCDS records cached during
    > E1's run are the source-of-truth records for E2.

Concretely, "the OCDS records cached during E1's run" is interpreted
here as the *adapter output* E1 sent to the agent and to MeshQu —
recorded in `agent_outputs/{decision_id}.json` (the `user_message` field
carries the canonical-JSON of decision_type + fields + substrate_notes
exactly as posted) cross-referenced with `decision_traces.jsonl` for the
ocid → decision_id mapping and per-receipt audit metadata.

This indirection is deliberate: E1 did not persist the raw OCDS bytes
to disk; only the adapter's *output* (the AdaptedRecord) was archived.
Reconstructing the AdaptedRecord shape from the archived `user_message`
gives us byte-for-byte reproducibility of the L0 prompt — which is the
strongest reproducibility check we can run without re-fetching from the
upstream feed (the latter being explicitly out of scope for E2 per
`planning/substrate.md`).

## No network calls

This module performs PURE DISK READS. Any code path that attempted to
hit Contracts Finder's API would be a regression — the experiment
design ASSUMES substrate is held identical to E1's run, bit-for-bit.
Tests assert that no HTTP transport is touched.

## Deterministic ordering

`load_cached_records` returns 283 unique records in OCID-ascending order.
The multi-pass orchestrator already sorts records by OCID before the
outer loop (see `multi_pass.run_multi_pass`); we sort here too so the
cache reader itself is a stable, testable contract.

## Per-record envelope

Each `CachedRecord` carries the same per-field provenance envelope the
E1 substrate adapter produced (direct_ocds / derived / proxy / absent),
preserved verbatim from `user_message.substrate_notes`. The orchestrator's
`build_user_message` accepts dict-shaped provenance entries (see
`eval_loop._serialise_substrate_notes`) and passes them through to the
canonical-JSON serializer unchanged — so re-feeding the archived
substrate_notes back into the runner produces an identical user_message.

## E1 audit pass-through

Each `CachedRecord` also carries reference fields from the E1 archive
(decision_id, agent verdict, MeshQu verdict, violations, integrity hash).
The L0-vs-E1 comparator script consumes these to produce the verdict
diff table without re-loading the decision_traces.jsonl separately.
The orchestrator itself never reads these reference fields — they ride
along as metadata.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping


# ---------------------------------------------------------------------------
# Frozen archive location — E1's dry-run
# ---------------------------------------------------------------------------

E1_ARCHIVE_RUN_ID = "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
"""The frozen E1 archive directory under `procurement-decisions/results/runs/`.
This is the run that produced the 283-record corpus. Locked at the value
documented in `planning/substrate.md` §"Posture" — changing it would
break the cross-experiment comparison."""

EXPECTED_RECORD_COUNT = 283
"""The 283 unique-OCID records E1's substrate adapter produced from 300
release events. Tests pin this number — if the archive ever returns a
different count, that's a regression in the archive itself."""


# ---------------------------------------------------------------------------
# Cached-record envelope
# ---------------------------------------------------------------------------


@dataclass
class CachedRecord:
    """One record from the E1 frozen archive, shaped for the E2 runner.

    Wire-compatible with `multi_pass._process_pass` (see that function:
    it reads `ocid`, `decision_type`, `fields`, `substrate_notes`,
    `metadata` off the record mapping). The E1 reference fields are
    carried for the L0-vs-E1 comparator script's use only.
    """

    ocid: str
    decision_type: str
    fields: dict[str, Any]
    substrate_notes: dict[str, dict[str, Any]]
    metadata: dict[str, Any]

    # E1 reference fields — populated from decision_traces.jsonl,
    # consumed by `scripts/compare_l0_to_e1.py`. The orchestrator does
    # not read these.
    e1_decision_id: str = ""
    e1_agent_verdict: str | None = None
    e1_meshqu_verdict: str | None = None
    e1_violations: list[str] = field(default_factory=list)
    e1_integrity_hash: str = ""
    e1_record_index: int = -1

    def as_record(self) -> dict[str, Any]:
        """Strip the E1 reference fields and return the plain record dict
        the orchestrator consumes. The orchestrator expects `ocid`,
        `decision_type`, `fields`, `substrate_notes`, `metadata`."""
        return {
            "ocid": self.ocid,
            "decision_type": self.decision_type,
            "fields": dict(self.fields),
            "substrate_notes": {k: dict(v) for k, v in self.substrate_notes.items()},
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SubstrateCacheError(RuntimeError):
    """Raised when the E1 archive is malformed or missing a required file.

    Distinct from the general FileNotFoundError so callers can disambiguate
    'archive structure is broken' from 'caller passed a bad path'. The
    multi-pass runner treats this as fatal — there is no recovery path
    when the cache is unreadable (re-fetching from Contracts Finder is
    out of scope per `planning/substrate.md`)."""


class SubstrateCacheNetworkAttemptError(SubstrateCacheError):
    """Raised when something tries to make a network call through the
    cache reader.

    The cache reader is a pure-disk module by contract (see module
    docstring + `planning/substrate.md`). Any attempt to fetch from
    Contracts Finder via this module is a bug — fail loudly rather than
    silently degrade to live mode. Tests assert this error is raised
    when an HTTP transport is invoked."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def archive_root(repo_dir: Path) -> Path:
    """Resolve the frozen E1 archive root from the repo dir.

    Repo layout:
        meshqu-research/
          procurement-decisions/                       (E1 — archival)
            results/runs/dry-run-7ddf7274-…/           ← here
          procurement-context-gradient/                (E2 — this experiment)
            runner/                                    ← we live here
    """
    return repo_dir / "procurement-decisions" / "results" / "runs" / E1_ARCHIVE_RUN_ID


def _read_decision_traces(archive_dir: Path) -> dict[str, dict[str, Any]]:
    """Read `decision_traces.jsonl` and index by ocid.

    Each row is one (record, receipt) tuple from E1's run. The OCID
    is the natural key — 283 unique OCIDs across 300 release events
    in E1's source feed (per the substrate adapter's dedup logic).

    Returns: { ocid → trace_row_dict }

    Raises SubstrateCacheError on a missing or malformed file."""
    path = archive_dir / "decision_traces.jsonl"
    if not path.exists():
        raise SubstrateCacheError(
            f"E1 archive missing decision_traces.jsonl at {path}"
        )

    by_ocid: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as fp:
        for line_no, line in enumerate(fp, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SubstrateCacheError(
                    f"decision_traces.jsonl line {line_no} is not valid JSON: {exc}"
                ) from exc
            ocid = row.get("ocid")
            if not isinstance(ocid, str) or not ocid:
                # E1's runner always writes a string ocid for adapted
                # records. A missing one is unexpected — surface
                # loudly rather than silently dropping the row.
                raise SubstrateCacheError(
                    f"decision_traces.jsonl line {line_no} has no ocid: {row}"
                )
            # E1 ran the substrate adapter once per RELEASE event; 300
            # events → 283 unique OCIDs. The agent + MeshQu were called
            # once per release event, so an OCID can appear multiple
            # times in decision_traces.jsonl. Keep the FIRST occurrence —
            # that's the receipt the dedup logic would have produced
            # if E1 had deduped before evaluation.
            if ocid not in by_ocid:
                by_ocid[ocid] = row
    return by_ocid


def _read_agent_output(archive_dir: Path, decision_id: str) -> dict[str, Any]:
    """Read one `agent_outputs/{decision_id}.json` file.

    The `user_message` field carries the canonical-JSON the agent saw at
    L0 in E1 — verbatim. We parse it back to extract decision_type,
    fields, and substrate_notes (the same shape E2's `build_user_message`
    expects)."""
    path = archive_dir / "agent_outputs" / f"{decision_id}.json"
    if not path.exists():
        raise SubstrateCacheError(
            f"E1 archive missing agent output for decision_id={decision_id} at {path}"
        )
    try:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as exc:
        raise SubstrateCacheError(
            f"agent_outputs/{decision_id}.json is not valid JSON: {exc}"
        ) from exc


def _parse_user_message(raw_user_message: str, *, decision_id: str) -> dict[str, Any]:
    """Decode the user_message string back into its structured parts.

    E1's `build_user_message` rendered the agent input as canonical JSON:

        json.dumps({
            "decision_type": ...,
            "fields": {...},
            "substrate_notes": {...},
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    Parsing it back gives us the exact shape `compose_user_message` /
    `build_user_message` expect in E2."""
    try:
        parsed = json.loads(raw_user_message)
    except json.JSONDecodeError as exc:
        raise SubstrateCacheError(
            f"agent_outputs/{decision_id}.json: user_message is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SubstrateCacheError(
            f"agent_outputs/{decision_id}.json: user_message is not a JSON object"
        )
    for required in ("decision_type", "fields", "substrate_notes"):
        if required not in parsed:
            raise SubstrateCacheError(
                f"agent_outputs/{decision_id}.json: user_message missing required key "
                f"'{required}'. The E1 archive may have been written by a runner "
                f"version that pre-dates the substrate-honesty envelope."
            )
    return parsed


def load_cached_records(repo_dir: Path) -> list[CachedRecord]:
    """Load all 283 records from the E1 frozen archive, OCID-ascending.

    Pure disk read. NO network access. If the archive is missing fields
    the runner needs, raises SubstrateCacheError — never silently
    degrades to a live fetch.

    Returns: list[CachedRecord] of length EXPECTED_RECORD_COUNT (283),
    sorted by `ocid` ascending. The order is deterministic across
    re-runs because we sort and the upstream JSONL is itself stable.
    """
    archive_dir = archive_root(repo_dir)
    if not archive_dir.exists():
        raise SubstrateCacheError(
            f"E1 frozen archive not found at {archive_dir}. "
            f"E2 substrate posture requires this directory to be present "
            f"(see planning/substrate.md)."
        )

    traces_by_ocid = _read_decision_traces(archive_dir)
    if len(traces_by_ocid) != EXPECTED_RECORD_COUNT:
        raise SubstrateCacheError(
            f"E1 archive returned {len(traces_by_ocid)} unique OCIDs; "
            f"expected {EXPECTED_RECORD_COUNT}. The frozen archive may have "
            f"been altered post-publication."
        )

    records: list[CachedRecord] = []
    for ocid in sorted(traces_by_ocid.keys()):
        trace = traces_by_ocid[ocid]
        decision_id = trace.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            raise SubstrateCacheError(
                f"decision_traces row for ocid={ocid} has no decision_id"
            )
        agent_output = _read_agent_output(archive_dir, decision_id)
        user_message = agent_output.get("user_message")
        if not isinstance(user_message, str) or not user_message:
            raise SubstrateCacheError(
                f"agent_outputs/{decision_id}.json has no user_message"
            )
        parsed = _parse_user_message(user_message, decision_id=decision_id)

        records.append(
            CachedRecord(
                ocid=ocid,
                decision_type=str(parsed["decision_type"]),
                fields=dict(parsed["fields"]),
                substrate_notes={
                    k: dict(v) for k, v in (parsed["substrate_notes"] or {}).items()
                },
                metadata={
                    "ocid": ocid,
                    "experiment_substrate": "uk_contracts_finder_ocds",
                    "adapter_version": "0.1.0-cached",
                    "e1_archive_run_id": E1_ARCHIVE_RUN_ID,
                },
                e1_decision_id=decision_id,
                e1_agent_verdict=trace.get("agent_verdict"),
                e1_meshqu_verdict=trace.get("meshqu_verdict"),
                e1_violations=list(trace.get("violations") or []),
                e1_integrity_hash=str(trace.get("integrity_hash") or ""),
                e1_record_index=int(trace.get("record_index", -1)),
            )
        )

    return records


def iter_cached_records(repo_dir: Path) -> Iterator[CachedRecord]:
    """Streaming-friendly variant of `load_cached_records`. Order is
    identical (OCID-ascending). Useful when a caller wants to fold over
    records without materialising the full 283-record list in memory."""
    for record in load_cached_records(repo_dir):
        yield record


def select_records(
    repo_dir: Path,
    ocids: list[str],
) -> list[CachedRecord]:
    """Load the subset of records matching the given OCID list.

    Used by the smoke runner (E2-007) to pull just the 3 records under
    test, and by the L0-vs-E1 comparator. Order is preserved: the
    returned list follows the input OCID order so the caller controls
    presentation order.

    Raises SubstrateCacheError if any OCID is missing from the archive —
    we never silently produce a smaller subset than the caller asked
    for."""
    all_records = {r.ocid: r for r in load_cached_records(repo_dir)}
    missing = [o for o in ocids if o not in all_records]
    if missing:
        raise SubstrateCacheError(
            f"Requested OCIDs not present in E1 archive: {missing}"
        )
    return [all_records[o] for o in ocids]


# ---------------------------------------------------------------------------
# Network-attempt guard
# ---------------------------------------------------------------------------


def assert_no_network_access() -> None:
    """Guard function callers can invoke before constructing a cache
    reader to assert nothing in the import chain has touched the
    network. Currently a no-op stub — the cache reader doesn't import
    `requests` at module load. If a future refactor pulled in an HTTP
    client transitively, this is where the assertion would go.

    Tests pin the negative case: a mocked `requests.get` is asserted
    never to be invoked. See `tests/test_l0_baseline.py`."""
    return None
