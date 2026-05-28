#!/usr/bin/env python3
"""L0-vs-E1 reproducibility comparator.

For a given list of OCIDs (default: 3 deterministically-picked smoke
records from the E1 archive), this script:

1. Loads each OCID's E1 receipt from the frozen archive (decision_traces.jsonl).
2. Loads the corresponding E2 L0 bundle from a given run directory.
3. Prints a verdict-comparison table.
4. Exits 0 if all OCIDs match; 1 otherwise.

Intended for manual invocation AFTER an E2 smoke or dry-run produces L0
bundles. NOT part of the live runner — it's a post-hoc audit tool that
the smoke/dry-run packages (E2-007, E2-008) invoke.

## Usage

    # Default 3 smoke records, default run dir layout
    python -m meshqu_runner.scripts.compare_l0_to_e1 \\
        --run-dir procurement-context-gradient/results/runs/smoke-<timestamp>

    # Specific OCIDs
    python -m meshqu_runner.scripts.compare_l0_to_e1 \\
        --run-dir <path> --ocid ocds-b5fd17-… --ocid ocds-b5fd17-…

## Default smoke selection (3 OCIDs)

Picked deterministically from the E1 archive:

1. The worked-example multi-rule DENY: OCID for decision_id `ca19e737-…`
   (the £57M case, per `procurement-context-gradient/README.md`).
2. The first OCID (OCID-ascending) with a clean ALLOW + zero violations.
3. The first OCID (OCID-ascending) with a single-rule DENY (exactly one
   entry in `violations`).

This mirrors the E2-007 smoke selection criteria (one clean ALLOW, one
single-rule DENY, one multi-rule DENY) but pins the choice
deterministically so re-running the comparator gives the same 3 records
without manual selection. E2-007 can override via `--ocid`.

## Verdict normalisation

E1 receipts carry `meshqu_verdict` ∈ {ALLOW, DENY, REVIEW}. The agent
verdict at L0 is what `agent_verdict` was — a different categorical
than the MeshQu policy verdict. The comparator reports BOTH dimensions
of agreement: the MeshQu side (policy verdict should be identical bit-
for-bit since the policy snapshot is unchanged) AND the agent side
(may drift due to OpenAI's temp=0 non-determinism — known E1 P4).

A "match" is defined as: same `meshqu_verdict` AND same `agent_verdict`.
A divergence on `agent_verdict` alone is documented but not fatal — see
the P4 reproducibility band in `planning/experiment_design.md`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Path-bootstrap: this script lives at runner/scripts/, the package at
# runner/meshqu_runner/. Add runner/ to sys.path so the import works
# whether invoked as `python scripts/compare_l0_to_e1.py` or as
# `python -m scripts.compare_l0_to_e1`.
RUNNER_DIR = Path(__file__).resolve().parent.parent
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from meshqu_runner.substrate_cache import (  # noqa: E402
    CachedRecord,
    SubstrateCacheError,
    load_cached_records,
)


# Worked-example decision id — the OCID for this decision is the multi-
# rule DENY case (£57M, PROC-001 + PROC-002 + PROC-005). Resolved at
# runtime against the loaded archive.
WORKED_EXAMPLE_DECISION_ID = "ca19e737-defb-4e5f-b216-ec97d2fe5859"


# ---------------------------------------------------------------------------
# Comparison result
# ---------------------------------------------------------------------------


@dataclass
class VerdictRow:
    """One row of the comparison table."""

    ocid: str
    e1_decision_id: str
    e1_meshqu_verdict: str | None
    l0_meshqu_verdict: str | None
    e1_agent_verdict: str | None
    l0_agent_verdict: str | None
    meshqu_match: bool
    agent_match: bool
    note: str = ""

    def matches(self) -> bool:
        """Strict match: BOTH dimensions agree.

        The MeshQu verdict should always agree (same policy snapshot,
        same fields → same evaluator output). A MeshQu mismatch points
        at a substrate-loading or hash-binding bug. The agent verdict
        can drift within the temp=0 reproducibility band (E1 P4)."""
        return self.meshqu_match and self.agent_match


# ---------------------------------------------------------------------------
# Default smoke selection
# ---------------------------------------------------------------------------


def select_default_smoke_ocids(records: list[CachedRecord]) -> list[str]:
    """Pick 3 OCIDs deterministically per the criteria in the module
    docstring.

    Returns OCIDs in the order: worked-example, clean ALLOW, single-rule
    DENY. The order is interpretive — the comparator prints rows in this
    order so the worked example always appears first."""
    by_ocid_sorted = sorted(records, key=lambda r: r.ocid)

    # 1) The worked-example record.
    worked = next(
        (r for r in by_ocid_sorted if r.e1_decision_id == WORKED_EXAMPLE_DECISION_ID),
        None,
    )

    # 2) First OCID with clean ALLOW + zero violations.
    clean_allow = next(
        (
            r
            for r in by_ocid_sorted
            if r.e1_meshqu_verdict == "ALLOW" and len(r.e1_violations) == 0
        ),
        None,
    )

    # 3) First OCID with single-rule DENY.
    single_deny = next(
        (
            r
            for r in by_ocid_sorted
            if r.e1_meshqu_verdict == "DENY" and len(r.e1_violations) == 1
        ),
        None,
    )

    selected: list[str] = []
    for candidate in (worked, clean_allow, single_deny):
        if candidate is None:
            continue
        # Avoid duplicates if (e.g.) the worked example IS the only
        # single-rule DENY in the corpus.
        if candidate.ocid not in selected:
            selected.append(candidate.ocid)

    return selected


# ---------------------------------------------------------------------------
# Bundle loading — read one L0 bundle from an E2 run dir
# ---------------------------------------------------------------------------


def find_l0_bundle_by_ocid(run_dir: Path, ocid: str) -> dict | None:
    """Find the L0 bundle whose `ocid` field equals the given OCID.

    Bundle layout: `<run_dir>/L0/<decision_id>.bundle.json`. The decision
    ID isn't predictable from the OCID (it's MeshQu-issued or stub-
    derived), so we scan the L0 directory and match on the `ocid` key
    inside each bundle. For 283 bundles this is trivial; for the 3-record
    smoke it's a 3-file scan."""
    l0_dir = run_dir / "L0"
    if not l0_dir.exists():
        return None
    for bundle_path in sorted(l0_dir.glob("*.bundle.json")):
        try:
            with bundle_path.open("r", encoding="utf-8") as fp:
                bundle = json.load(fp)
        except json.JSONDecodeError:
            continue
        if bundle.get("ocid") == ocid:
            return bundle
    return None


def _extract_l0_meshqu_verdict(bundle: dict) -> str | None:
    """Pull the MeshQu policy verdict from the bundle's nested receipt."""
    receipt = bundle.get("receipt") or {}
    return receipt.get("decision")


def _extract_l0_agent_verdict(bundle: dict) -> str | None:
    """Pull the agent's verdict from the bundle's agent payload."""
    agent = bundle.get("agent") or {}
    return agent.get("verdict")


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------


def format_table(rows: Iterable[VerdictRow]) -> str:
    """Render a small ASCII table the PR body can quote directly."""
    rows_list = list(rows)
    if not rows_list:
        return "(no rows)"

    headers = [
        "OCID (last 12)",
        "E1 MeshQu",
        "L0 MeshQu",
        "E1 Agent",
        "L0 Agent",
        "Match",
        "Note",
    ]
    table_rows = []
    for r in rows_list:
        table_rows.append(
            [
                r.ocid[-12:],
                r.e1_meshqu_verdict or "-",
                r.l0_meshqu_verdict or "-",
                r.e1_agent_verdict or "-",
                r.l0_agent_verdict or "-",
                "yes" if r.matches() else "no",
                r.note,
            ]
        )

    widths = [max(len(h), *(len(row[i]) for row in table_rows)) for i, h in enumerate(headers)]

    def _fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines = [_fmt_row(headers), separator]
    for tr in table_rows:
        lines.append(_fmt_row(tr))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Comparison driver
# ---------------------------------------------------------------------------


def compare(
    *,
    repo_dir: Path,
    run_dir: Path,
    ocids: list[str] | None = None,
) -> list[VerdictRow]:
    """Load E1 archive + E2 L0 bundles, return a row per OCID.

    When `ocids` is None, picks the 3-record default smoke set
    deterministically (see `select_default_smoke_ocids`)."""
    records = load_cached_records(repo_dir)
    by_ocid = {r.ocid: r for r in records}

    if ocids is None:
        ocids = select_default_smoke_ocids(records)
        if len(ocids) < 3:
            # Defensive: an archive with no clean ALLOW or no single-rule
            # DENY is a finding in itself. Continue with whatever we have.
            pass

    rows: list[VerdictRow] = []
    for ocid in ocids:
        record = by_ocid.get(ocid)
        if record is None:
            rows.append(
                VerdictRow(
                    ocid=ocid,
                    e1_decision_id="-",
                    e1_meshqu_verdict=None,
                    l0_meshqu_verdict=None,
                    e1_agent_verdict=None,
                    l0_agent_verdict=None,
                    meshqu_match=False,
                    agent_match=False,
                    note="OCID not in E1 archive",
                )
            )
            continue

        bundle = find_l0_bundle_by_ocid(run_dir, ocid)
        if bundle is None:
            rows.append(
                VerdictRow(
                    ocid=ocid,
                    e1_decision_id=record.e1_decision_id,
                    e1_meshqu_verdict=record.e1_meshqu_verdict,
                    l0_meshqu_verdict=None,
                    e1_agent_verdict=record.e1_agent_verdict,
                    l0_agent_verdict=None,
                    meshqu_match=False,
                    agent_match=False,
                    note="L0 bundle missing in run dir",
                )
            )
            continue

        l0_meshqu = _extract_l0_meshqu_verdict(bundle)
        l0_agent = _extract_l0_agent_verdict(bundle)
        is_stub = bool(bundle.get("is_stub"))

        meshqu_match = l0_meshqu == record.e1_meshqu_verdict
        agent_match = l0_agent == record.e1_agent_verdict

        note = ""
        if is_stub:
            # Stub bundles synthesise verdicts deterministically and DO
            # NOT call OpenAI or the MeshQu API. They cannot be used for
            # reproducibility — the comparator marks them as such so a
            # human reading the PR body doesn't mistake a stub-stub run
            # for a live-vs-archive comparison.
            note = "stub bundle (not a live reproducibility check)"

        rows.append(
            VerdictRow(
                ocid=ocid,
                e1_decision_id=record.e1_decision_id,
                e1_meshqu_verdict=record.e1_meshqu_verdict,
                l0_meshqu_verdict=l0_meshqu,
                e1_agent_verdict=record.e1_agent_verdict,
                l0_agent_verdict=l0_agent,
                meshqu_match=meshqu_match,
                agent_match=agent_match,
                note=note,
            )
        )

    return rows


def _default_repo_dir() -> Path:
    """Resolve the repo root from this script's location."""
    return Path(__file__).resolve().parent.parent.parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="E2 multi-pass run directory (contains L0/<decision_id>.bundle.json)",
    )
    parser.add_argument(
        "--ocid",
        action="append",
        default=None,
        help="OCID to compare (repeatable). Default: 3 deterministically-picked smoke records.",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=None,
        help="Repo root (defaults to inferred location).",
    )
    args = parser.parse_args(argv)

    repo_dir = args.repo_dir or _default_repo_dir()

    try:
        rows = compare(
            repo_dir=repo_dir,
            run_dir=args.run_dir,
            ocids=args.ocid,
        )
    except SubstrateCacheError as exc:
        print(f"error: substrate cache: {exc}", file=sys.stderr)
        return 2

    print(format_table(rows))
    print()

    all_match = all(r.matches() for r in rows)
    if all_match:
        print(f"All {len(rows)} OCIDs match (MeshQu + agent verdicts identical).")
        return 0

    meshqu_diverged = [r for r in rows if not r.meshqu_match]
    agent_diverged = [r for r in rows if not r.agent_match]
    print(
        f"{len(meshqu_diverged)} MeshQu-verdict divergence(s), "
        f"{len(agent_diverged)} agent-verdict divergence(s)."
    )
    if meshqu_diverged:
        print(
            "MeshQu-verdict divergence indicates a substrate-loading "
            "or hash-binding bug (not OpenAI noise). Investigate before "
            "proceeding."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
