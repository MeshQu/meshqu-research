#!/usr/bin/env python3
"""Build the analysis-ready parquet export from the three canonical corpus.tar files.

This script reads ONLY:

    procurement-decisions/results/corpus.tar              (E1, MRP-2026-02)
    procurement-context-gradient/results/corpus.tar       (E2, MRP-2026-03)
    procurement-context-disambiguation/results/corpus.tar (E3, MRP-2026-04)

It never reads results/runs/ directories. Those hold the pre-export execution
trail and are not analysis input.

Each tar member bundles/<decision_id>.bundle.json is a two-layer JSON document:

    layer 1: {"manifest": {...}, "files": {"receipt.json": "<JSON string>", ...}}
    layer 2: each value in "files" is itself a JSON document serialised as a
             string. json.loads(bundle["files"]["receipt.json"]) yields the
             receipt with "context" and "result" objects.

Outputs, written next to this script:

    receipts.parquet    one row per canonical receipt (3,044 rows)
    violations.parquet  one row per policy violation
    DATA_MANIFEST.json  tar digests, row counts, invariants, output digests

The script asserts the published row counts (283 / 1,429 / 1,332) and the
shared policy snapshot. It fails loudly on any mismatch.

Usage:

    pip install pyarrow
    python data/build_export.py
"""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent

CORPORA = {
    "E1": "procurement-decisions/results/corpus.tar",
    "E2": "procurement-context-gradient/results/corpus.tar",
    "E3": "procurement-context-disambiguation/results/corpus.tar",
}

EXPECTED_RECEIPTS = {"E1": 283, "E2": 1429, "E3": 1332}

EXPECTED_CONDITIONS = {
    "E1": {"baseline": 283},
    "E2": {"L0": 283, "L1": 283, "L2": 283, "L3": 283, "L4": 283, "L4_PERMUTED": 14},
    "E3": {
        "arm_a": 283,
        "arm_b": 283,
        "arm_c": 283,
        "l4_without_nudge": 283,
        "diagnostic_primary": 100,
        "diagnostic_claude": 100,
    },
}

# All 3,044 receipts bind the same ratified policy snapshot.
EXPECTED_SNAPSHOT_ID = "cbf12348-6248-48f7-a06f-4e0304cc237e"
EXPECTED_SNAPSHOT_DIGEST = "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_condition(experiment, fields):
    """Normalise the per-experiment condition into one column.

    E1 has a single condition. E2 carries it directly in
    governance_context_level (the 14 Permuted-Policy diagnostic receipts are
    L4_PERMUTED). E3 spreads it across three flags, so we reassemble the six
    arms from l3_arm, nudge_excised, diagnostic and model_id.
    """
    if experiment == "E1":
        return "baseline"
    if experiment == "E2":
        return fields["governance_context_level"]
    # E3
    l3_arm = fields.get("l3_arm")
    if l3_arm in ("A", "B", "C"):
        return "arm_" + l3_arm.lower()
    if fields.get("nudge_excised"):
        return "l4_without_nudge"
    if fields.get("diagnostic"):
        model = fields.get("model_id") or fields.get("agent_model_id") or ""
        return "diagnostic_claude" if model.startswith("claude") else "diagnostic_primary"
    raise ValueError("E3 receipt matches no known arm: %r" % (fields,))


def read_corpus(experiment, tar_path):
    receipt_rows = []
    violation_rows = []
    with tarfile.open(tar_path) as tf:
        for member in sorted(tf.getmembers(), key=lambda m: m.name):
            basename = member.name.rsplit("/", 1)[-1]
            if not member.isfile():
                continue
            if basename.startswith("._"):
                # AppleDouble metadata sidecar (macOS tar artefact). Not a bundle.
                continue
            if not member.name.endswith(".bundle.json"):
                continue
            bundle = json.load(tf.extractfile(member))
            manifest = json.loads(bundle["files"]["bundle_manifest.json"])
            receipt = json.loads(bundle["files"]["receipt.json"])

            decision_id = manifest["decision_id"]
            fields = receipt["context"]["fields"]
            metadata = receipt["context"]["metadata"]
            result = receipt["result"]
            condition = derive_condition(experiment, fields)
            ocid = metadata["ocid"]
            violations = result.get("violations") or []

            receipt_rows.append(
                {
                    "experiment": experiment,
                    "condition": condition,
                    "decision_id": decision_id,
                    "ocid": ocid,
                    "ai_verdict": fields.get("agent_recommended_verdict"),
                    "policy_verdict": result["decision"],
                    "violation_codes": [v["rule_code"] for v in violations],
                    "violations_count": len(violations),
                    "policy_snapshot_id": result["policy_snapshot_id"],
                    "policy_snapshot_digest": result["policy_snapshot_digest"],
                    "timestamp": result["timestamp"],
                    "model_id": fields.get("agent_model_id") or fields.get("model_id"),
                }
            )
            for v in violations:
                violation_rows.append(
                    {
                        "experiment": experiment,
                        "condition": condition,
                        "decision_id": decision_id,
                        "ocid": ocid,
                        "rule_code": v.get("rule_code"),
                        "severity": v.get("severity"),
                        "field": v.get("field"),
                        "reason_code": v.get("reason_code"),
                    }
                )
    return receipt_rows, violation_rows


def check(label, actual, expected):
    if actual != expected:
        sys.exit("MISMATCH %s: expected %r, got %r" % (label, expected, actual))
    print("  OK %s = %r" % (label, expected))


def main():
    all_receipts = []
    all_violations = []
    manifest = {
        "generated_by": "data/build_export.py",
        "regenerate_with": "python data/build_export.py",
        "corpora": {},
        "policy_snapshot": {
            "id": EXPECTED_SNAPSHOT_ID,
            "digest": EXPECTED_SNAPSHOT_DIGEST,
            "note": "All 3,044 receipts bind this one ratified snapshot.",
        },
        "notes": {
            "e1_dedup": (
                "E1 attempted 300 releases. The Contracts Finder OCDS feed "
                "returned 12 OCIDs more than once in the sample window, and "
                "MeshQu's idempotency cache returned the same receipt for each "
                "duplicate POST. The canonical corpus therefore holds 283 "
                "unique decisions, not 300."
            ),
            "condition_normalisation": (
                "E1 is single-condition (baseline). E2 uses "
                "governance_context_level as-is, including L4_PERMUTED for the "
                "14 Permuted-Policy diagnostic receipts. E3 arms are derived "
                "from l3_arm, nudge_excised, diagnostic and model_id."
            ),
        },
        "outputs": {},
    }

    for experiment, rel_path in CORPORA.items():
        tar_path = REPO / rel_path
        print("Reading %s (%s)" % (experiment, rel_path))
        receipts, violations = read_corpus(experiment, tar_path)
        check("%s receipt count" % experiment, len(receipts), EXPECTED_RECEIPTS[experiment])
        conditions = {}
        for row in receipts:
            conditions[row["condition"]] = conditions.get(row["condition"], 0) + 1
        check("%s condition counts" % experiment, conditions, EXPECTED_CONDITIONS[experiment])
        for row in receipts:
            if row["policy_snapshot_id"] != EXPECTED_SNAPSHOT_ID:
                sys.exit("MISMATCH policy_snapshot_id on %s" % row["decision_id"])
            if row["policy_snapshot_digest"] != EXPECTED_SNAPSHOT_DIGEST:
                sys.exit("MISMATCH policy_snapshot_digest on %s" % row["decision_id"])
        unique_ocids = len({row["ocid"] for row in receipts})
        print("  %s unique OCIDs: %d" % (experiment, unique_ocids))
        manifest["corpora"][experiment] = {
            "path": rel_path,
            "sha256": sha256_file(tar_path),
            "receipts": len(receipts),
            "conditions": dict(sorted(conditions.items())),
            "unique_ocids": unique_ocids,
        }
        all_receipts.extend(receipts)
        all_violations.extend(violations)

    if manifest["corpora"]["E1"]["unique_ocids"] != 283:
        sys.exit("MISMATCH: E1 must deduplicate to 283 unique OCIDs")

    all_receipts.sort(key=lambda r: (r["experiment"], r["condition"], r["decision_id"]))
    all_violations.sort(
        key=lambda v: (v["experiment"], v["condition"], v["decision_id"], v["rule_code"], v["field"])
    )

    receipts_schema = pa.schema(
        [
            ("experiment", pa.string()),
            ("condition", pa.string()),
            ("decision_id", pa.string()),
            ("ocid", pa.string()),
            ("ai_verdict", pa.string()),
            ("policy_verdict", pa.string()),
            ("violation_codes", pa.list_(pa.string())),
            ("violations_count", pa.int32()),
            ("policy_snapshot_id", pa.string()),
            ("policy_snapshot_digest", pa.string()),
            ("timestamp", pa.string()),
            ("model_id", pa.string()),
        ]
    )
    violations_schema = pa.schema(
        [
            ("experiment", pa.string()),
            ("condition", pa.string()),
            ("decision_id", pa.string()),
            ("ocid", pa.string()),
            ("rule_code", pa.string()),
            ("severity", pa.string()),
            ("field", pa.string()),
            ("reason_code", pa.string()),
        ]
    )

    for name, rows, schema in (
        ("receipts.parquet", all_receipts, receipts_schema),
        ("violations.parquet", all_violations, violations_schema),
    ):
        out_path = OUT_DIR / name
        table = pa.Table.from_pylist(rows, schema=schema)
        pq.write_table(table, out_path, compression="zstd")
        manifest["outputs"][name] = {"rows": len(rows), "sha256": sha256_file(out_path)}
        print("Wrote %s: %d rows, sha256 %s" % (name, len(rows), manifest["outputs"][name]["sha256"]))

    check("total receipts", len(all_receipts), 3044)

    manifest_path = OUT_DIR / "DATA_MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("Wrote %s" % manifest_path.name)


if __name__ == "__main__":
    main()
