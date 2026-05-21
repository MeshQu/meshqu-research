#!/usr/bin/env python3
"""Select 30 deterministic dry-run records from the E1 frozen archive.

Stratification per E2-008 package §1:

  - Strata = (contract_value_band × method_flag-present-vs-absent × regime).
  - 5 records from each of the 4 contract_value_bands (= 20 records).
  - Within each band, prefer a mix of method-flag-present vs absent.
  - 10 records added by OCID-ascending walk over the remainder (de-dup).
  - The 3 smoke records (E2-007 fixture) MUST be in the final set for
    cross-run reproducibility (§4a).

Each picked archive record is projected into the smoke-fixture shape
(`{decision_type, fields, substrate_notes, metadata, e1_reference}`)
that the runner consumes. The substrate fields come from the agent-
output sidecar's `user_message` payload — same source the
`PrecedentRecord` loader uses, just re-projected for the runner instead
of the L3 selector.

Output: a single JSON file
`runner/tests/fixtures/dry_run_records.json` carrying a `__comment__`
header (selection criteria) and a `records` array of 30 records sorted
by OCID ascending. Run is deterministic — same archive → same fixture
bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
E1_ARCHIVE = (
    REPO_ROOT
    / "procurement-decisions"
    / "results"
    / "runs"
    / "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
)

# Path bootstrap so `meshqu_runner.diagnostic.subset` is importable when
# this script runs from any cwd.
_RUNNER_DIR = Path(__file__).resolve().parents[1]
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

from meshqu_runner.diagnostic.subset import is_in_permuted_subset  # noqa: E402

# The 3 OCIDs from the E2-007 smoke fixture. Must be present in our 30.
SMOKE_OCIDS = (
    "ocds-b5fd17-001cf81b-5232-4d78-a0c7-4b8ab05f7658",
    "ocds-b5fd17-0786919f-4875-42c3-99ac-7db01e366670",
    "ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f",
)

# Target: ensure at least 1 OCID from the 14-record Permuted-Policy
# diagnostic subset is in the 30, so the §3f/§4c diagnostic checks
# have signal at dry-run scale. Per the package §3: "Expected
# intersection size: ~1–2 records". We force-include the FIRST OCID-
# ascending OCID from the diagnostic subset; the displacement comes
# from the tail of the OCID-asc remainder (never a band-quota pick).
FORCE_DIAGNOSTIC_INTERSECTION_COUNT = 1


def _band(value: float) -> str:
    if value < 100_000:
        return "<100k"
    if value < 500_000:
        return "100k-500k"
    if value < 10_000_000:
        return "500k-10M"
    return ">10M"


def _load_traces() -> dict[str, dict[str, Any]]:
    """Return {ocid: trace_row}, de-dup'd by decision_id (first wins)."""
    traces_path = E1_ARCHIVE / "decision_traces.jsonl"
    by_decision: dict[str, dict[str, Any]] = {}
    with traces_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            did = row.get("decision_id")
            if did and did not in by_decision:
                by_decision[did] = row
    by_ocid: dict[str, dict[str, Any]] = {}
    for did, row in by_decision.items():
        ocid = row.get("ocid")
        if ocid and ocid not in by_ocid:
            by_ocid[ocid] = row
    return by_ocid


def _load_user_message(decision_id: str) -> dict[str, Any]:
    """Return the parsed user_message dict from agent_outputs/<did>.json."""
    p = E1_ARCHIVE / "agent_outputs" / f"{decision_id}.json"
    with p.open("r", encoding="utf-8") as fp:
        sidecar = json.load(fp)
    raw = sidecar["user_message"]
    return json.loads(raw)


def _project_record(ocid: str, trace: dict[str, Any]) -> dict[str, Any]:
    """Project one (trace, sidecar) row into the runner record shape.

    The runner consumes `{decision_type, fields, substrate_notes,
    metadata}` (same shape as the smoke fixture's non-`e1_reference`
    keys). We add `e1_reference` for audit-only — orchestrator strips
    it before sending to the agent (via _drop_e1_reference in
    smoke_live.py — we mirror that step in the dry-run driver)."""
    did = trace["decision_id"]
    um = _load_user_message(did)
    fields = um.get("fields") or {}
    substrate_notes = um.get("substrate_notes") or {}

    return {
        "decision_type": um.get("decision_type", "procurement_decision"),
        "fields": fields,
        "substrate_notes": substrate_notes,
        "metadata": {
            "adapter_version": "0.1.0-cached",
            "e1_archive_run_id": "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d",
            "experiment_substrate": "uk_contracts_finder_ocds",
            "ocid": ocid,
        },
        "e1_reference": {
            "agent_verdict": trace.get("agent_verdict"),
            "decision_id": did,
            "integrity_hash": trace.get("integrity_hash"),
            "meshqu_verdict": trace.get("meshqu_verdict"),
            "violations": list(trace.get("violations") or []),
        },
    }


def _stratify(by_ocid: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], list[str]]:
    """Bucket OCIDs by (band, method_flag, regime). method_flag is
    'present' / 'absent'."""
    buckets: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for ocid, trace in sorted(by_ocid.items()):  # OCID ascending
        did = trace["decision_id"]
        try:
            um = _load_user_message(did)
        except FileNotFoundError:
            continue
        fields = um.get("fields") or {}
        try:
            value = float(fields.get("contract_value") or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        band = _band(value)
        method_flag = fields.get("procurement_method_open_flag")
        flag_key = "present" if method_flag not in (None, "") else "absent"
        regime = (
            "PA23" if str(fields.get("governed_by_pa23")).lower() == "true" else "PCR_2015"
        )
        buckets[(band, flag_key, regime)].append(ocid)
    return buckets


def select_thirty(by_ocid: dict[str, dict[str, Any]]) -> list[str]:
    """Apply the §1 stratification → 20 stratified + remainder via
    OCID-asc walk → ensure the 3 smoke records are present.

    Algorithm:

      1. Bucket into (band × method_flag × regime).
      2. For each of the 4 bands, aim for 5 records (the package says
         "5 from each band"). Within a band, take method_flag='present'
         first (rarer — only ~19/283 carry the flag), then method-flag
         absent. Ties broken by OCID-asc. Skip duplicates from earlier
         picks.
      3. If stratification under-fills (e.g. only 3 records in a band-
         method-regime cell), continue to the next cell within the
         same band.
      4. After the 20 stratified picks, walk the corpus OCID-asc and
         add the first 10 OCIDs not yet picked — to reach 30.
      5. After this whole process, force-add the 3 smoke OCIDs by
         displacing the last-picked OCIDs (from step 4 — never
         displace a band-quota pick). This guarantees the 3 smoke
         OCIDs are in the final set while preserving stratification.
    """
    buckets = _stratify(by_ocid)
    picked: list[str] = []
    picked_set: set[str] = set()

    # Step 1-3: band quotas of EXACTLY 5 per band (20 stratified total),
    # preferring method=present. Within a (band, flag) cell, walk
    # OCIDs ascending. Cells walked in fixed order to keep the function
    # deterministic when a band has multiple regimes.
    band_quota_picks: list[str] = []  # track these separately for §4 audit
    for band in ("<100k", "100k-500k", "500k-10M", ">10M"):
        band_picked: list[str] = []
        cells = [
            (band, "present", "PA23"),
            (band, "present", "PCR_2015"),
            (band, "absent", "PA23"),
            (band, "absent", "PCR_2015"),
        ]
        for key in cells:
            if len(band_picked) >= 5:
                break
            for ocid in buckets.get(key, []):
                if ocid in picked_set:
                    continue
                band_picked.append(ocid)
                picked_set.add(ocid)
                if len(band_picked) >= 5:
                    break
        if len(band_picked) < 5:
            raise SystemExit(
                f"Band {band} under-filled: got {len(band_picked)}/5. "
                "Edit the cell ordering or relax the quota."
            )
        picked.extend(band_picked)
        band_quota_picks.extend(band_picked)

    # Step 4: OCID-asc walk for the remainder until we hit 30.
    remainder_added: list[str] = []
    for ocid in sorted(by_ocid.keys()):
        if len(picked) >= 30:
            break
        if ocid in picked_set:
            continue
        picked.append(ocid)
        picked_set.add(ocid)
        remainder_added.append(ocid)

    # Step 5: force-include
    #   (a) the 3 smoke OCIDs (cross-run reproducibility check §4a),
    #   (b) FORCE_DIAGNOSTIC_INTERSECTION_COUNT OCIDs from the 14-record
    #       Permuted-Policy subset (so §3f/§4c have signal at dry-run scale).
    # Displacement comes from the tail of `remainder_added` (never a band-
    # quota pick — those carry stratification meaning).
    must_include: list[str] = []
    must_include.extend(o for o in SMOKE_OCIDS if o not in picked_set)

    # Pick the first OCID-asc OCIDs from the diagnostic subset that
    # aren't already in picked_set, up to the configured count.
    diag_candidates = [
        o for o in sorted(by_ocid.keys())
        if is_in_permuted_subset(o) and o not in picked_set
    ]
    forced_diag: list[str] = []
    for o in diag_candidates:
        if len(forced_diag) >= FORCE_DIAGNOSTIC_INTERSECTION_COUNT:
            break
        forced_diag.append(o)
    must_include.extend(forced_diag)

    for missing in must_include:
        if missing in picked_set:
            continue  # may have been added via earlier displacement loop iteration
        if not remainder_added:
            raise SystemExit(
                f"Cannot include forced OCID {missing}: no remainder "
                f"slots to displace and band quotas fill 30 already."
            )
        displaced = remainder_added.pop()
        picked.remove(displaced)
        picked_set.discard(displaced)
        picked.append(missing)
        picked_set.add(missing)

    if len(picked) != 30:
        raise SystemExit(
            f"Selector produced {len(picked)} records, expected 30. "
            f"Re-check the band quotas / displacement logic."
        )

    return sorted(picked)  # final fixture sorts by OCID for stable bytes


def write_fixture(
    output_path: Path,
    by_ocid: dict[str, dict[str, Any]],
    selected: list[str],
) -> None:
    records = [_project_record(o, by_ocid[o]) for o in selected]

    # Audit-print the strata distribution
    strata_counts: dict[str, int] = defaultdict(int)
    for r in records:
        fields = r["fields"]
        try:
            v = float(fields.get("contract_value") or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        band = _band(v)
        flag_key = (
            "present"
            if fields.get("procurement_method_open_flag") not in (None, "")
            else "absent"
        )
        regime = (
            "PA23" if str(fields.get("governed_by_pa23")).lower() == "true" else "PCR_2015"
        )
        strata_counts[f"{band}/{flag_key}/{regime}"] += 1

    smoke_present = [o for o in SMOKE_OCIDS if o in selected]

    comment = (
        "Dry-run fixture for E2-008 (Stage C dry-run, 30 records).\n"
        "Generated by scripts/select_dry_run_records.py — deterministic.\n"
        "\n"
        "Selection criteria (E2-008 §1):\n"
        "  - Stratified by (contract_value_band x method_flag x regime).\n"
        "  - 5 records per contract_value_band (4 bands = 20 records).\n"
        "  - Within a band, method_flag=present preferred (rarer); then absent.\n"
        "    Ties broken by OCID ascending.\n"
        "  - Remaining 10 records added by OCID-ascending walk of the\n"
        "    283-record E1 corpus.\n"
        "  - The 3 E2-007 smoke OCIDs are force-included by displacing\n"
        "    the tail of the OCID-asc remainder (never a band-quota pick).\n"
        "  - Final list sorted by OCID for stable fixture bytes.\n"
        "\n"
        f"Strata observed in the final 30: {dict(sorted(strata_counts.items()))}\n"
        f"E2-007 smoke OCIDs present: {smoke_present}\n"
        "\n"
        "Each record carries (decision_type, fields, substrate_notes,\n"
        "metadata) matching the runner contract, plus an `e1_reference`\n"
        "block with the E1 archive verdicts. The orchestrator strips\n"
        "`e1_reference` before sending to the agent (via the dry-run\n"
        "driver's _drop_e1_reference)."
    )

    payload = {"__comment__": comment, "records": records}
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write("\n")

    print(f"Wrote {output_path} ({len(records)} records).")
    print(f"Strata distribution: {dict(sorted(strata_counts.items()))}")
    print(f"E2-007 smoke OCIDs included: {len(smoke_present)}/3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "dry_run_records.json",
    )
    args = parser.parse_args(argv)

    by_ocid = _load_traces()
    print(f"Loaded {len(by_ocid)} unique-OCID traces from {E1_ARCHIVE.name}")

    selected = select_thirty(by_ocid)
    write_fixture(args.output, by_ocid, selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
