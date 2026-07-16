#!/usr/bin/env python3
"""Build the verified reasoning-text supplement from the production runs.

The canonical Decision Receipts bind SHA-256 hashes of the agent's reasoning
(context.fields.agent_reasoning_sha256), not the texts. The raw texts exist
only in the pre-export production run directories. This script extracts them,
verifies each text against the hash its canonical receipt binds, and publishes
only the verified set.

The integrity rule: a text ships only if sha256(text encoded as UTF-8) equals
the agent_reasoning_sha256 in the corresponding canonical receipt from
corpus.tar. The bound hash was reproduced on a cross-experiment sample before
this script was written: it is the SHA-256 of the UTF-8 bytes of the reasoning
string, no normalisation. A failing text is recorded and excluded, never
edited to make the hash pass. A receipt with no matching production text is
recorded as missing.

Reads (read-only):

    procurement-context-gradient/results/corpus.tar
    procurement-context-disambiguation/results/corpus.tar
    procurement-decisions/results/corpus.tar
    procurement-context-gradient/results/runs/phase-2-20260522-101324-Z/
    procurement-context-disambiguation/results/runs/phase-2-20260529T092611-Z/

E1's production run (dry-run-7ddf7274-..., production despite the name) was
never committed; its runs directory holds only a README. When the raw outputs
are absent, every E1 receipt is recorded as missing and no E1 text ships.

Writes, next to this script:

    reasoning_texts.parquet  one row per verified text
    reasoning_texts.csv      the same rows as a courtesy copy
    DATA_MANIFEST.json       updated in place: supplement coverage + digests

Regenerate order: run build_export.py first if you need to rebuild the core
export, then this script. Both are deterministic; two consecutive runs of
this script produce byte-identical outputs.

Usage (Python 3.10 or newer):

    pip install pyarrow==25.0.0
    python data/build_reasoning_supplement.py
"""

import csv
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

PINNED_PYARROW = "25.0.0"

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent

CORPORA = {
    "E1": "procurement-decisions/results/corpus.tar",
    "E2": "procurement-context-gradient/results/corpus.tar",
    "E3": "procurement-context-disambiguation/results/corpus.tar",
}

# Production runs only. Smoke, dry-rehearsal, superseded and aborted runs are
# never read. E1's production run was never committed (see that experiment's
# results/runs/README.md); None means no texts can be extracted.
PRODUCTION_RUNS = {
    "E1": None,
    "E2": "procurement-context-gradient/results/runs/phase-2-20260522-101324-Z",
    "E3": "procurement-context-disambiguation/results/runs/phase-2-20260529T092611-Z",
}

EXPECTED_RECEIPTS = {"E1": 283, "E2": 1429, "E3": 1332}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_condition(experiment, fields):
    """Same normalisation as build_export.py."""
    if experiment == "E1":
        return "baseline"
    if experiment == "E2":
        return fields["governance_context_level"]
    l3_arm = fields.get("l3_arm")
    if l3_arm in ("A", "B", "C"):
        return "arm_" + l3_arm.lower()
    if fields.get("nudge_excised"):
        return "l4_without_nudge"
    if fields.get("diagnostic"):
        model = fields.get("model_id") or fields.get("agent_model_id") or ""
        return "diagnostic_claude" if model.startswith("claude") else "diagnostic_primary"
    raise ValueError("E3 receipt matches no known arm: %r" % (fields,))


def read_canonical(experiment, tar_path):
    """decision_id -> canonical facts including the bound reasoning hash."""
    out = {}
    with tarfile.open(tar_path) as tf:
        for member in sorted(tf.getmembers(), key=lambda m: m.name):
            basename = member.name.rsplit("/", 1)[-1]
            if basename.startswith("._"):
                continue
            if not member.isfile() or not member.name.endswith(".bundle.json"):
                continue
            bundle = json.load(tf.extractfile(member))
            manifest = json.loads(bundle["files"]["bundle_manifest.json"])
            receipt = json.loads(bundle["files"]["receipt.json"])
            fields = receipt["context"]["fields"]
            out[manifest["decision_id"]] = {
                "ocid": receipt["context"]["metadata"]["ocid"],
                "condition": derive_condition(experiment, fields),
                "model_id": fields.get("agent_model_id") or fields.get("model_id"),
                "reasoning_sha256": fields["agent_reasoning_sha256"],
            }
    return out


def read_production_texts(run_rel):
    """decision_id -> (reasoning text, repo-relative bundle path)."""
    out = {}
    run_dir = REPO / run_rel
    for path in sorted(run_dir.glob("*/*.bundle.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        decision_id = bundle["decision_id"]
        if decision_id in out:
            sys.exit("DUPLICATE decision_id %s in %s" % (decision_id, run_rel))
        text = (bundle.get("agent") or {}).get("reasoning")
        out[decision_id] = (text, str(path.relative_to(REPO)))
    return out


def main():
    if pa.__version__ != PINNED_PYARROW:
        print(
            "WARNING: pyarrow %s installed, %s pinned. Parquet bytes may not "
            "match the recorded digests." % (pa.__version__, PINNED_PYARROW)
        )

    rows = []
    failures = []
    coverage = {}

    for experiment, tar_rel in CORPORA.items():
        canonical = read_canonical(experiment, REPO / tar_rel)
        if len(canonical) != EXPECTED_RECEIPTS[experiment]:
            sys.exit(
                "MISMATCH %s canonical receipts: expected %d, got %d"
                % (experiment, EXPECTED_RECEIPTS[experiment], len(canonical))
            )

        run_rel = PRODUCTION_RUNS[experiment]
        if run_rel is None or not (REPO / run_rel).is_dir():
            texts = {}
            run_note = "production run not in repository"
        else:
            texts = read_production_texts(run_rel)
            run_note = run_rel

        found = verified = 0
        missing = []
        for decision_id in sorted(canonical):
            fact = canonical[decision_id]
            if decision_id not in texts or texts[decision_id][0] is None:
                missing.append(decision_id)
                continue
            found += 1
            text, source = texts[decision_id]
            computed = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if computed != fact["reasoning_sha256"]:
                failures.append(
                    {
                        "experiment": experiment,
                        "decision_id": decision_id,
                        "source_run_path": source,
                        "computed_sha256": computed,
                        "expected_sha256": fact["reasoning_sha256"],
                    }
                )
                continue
            verified += 1
            rows.append(
                {
                    "decision_id": decision_id,
                    "ocid": fact["ocid"],
                    "experiment": experiment,
                    "condition": fact["condition"],
                    "model_id": fact["model_id"],
                    "reasoning_sha256": fact["reasoning_sha256"],
                    "reasoning_text": text,
                    "source_run_path": source,
                    "verified": True,
                }
            )

        extraneous = sorted(set(texts) - set(canonical))
        coverage[experiment] = {
            "canonical_receipts": len(canonical),
            "production_run": run_note,
            "texts_found": found,
            "texts_verified": verified,
            "texts_failed_hash_check": found - verified,
            "texts_missing": len(missing),
            "run_bundles_not_in_corpus": len(extraneous),
        }
        print(
            "%s: %d receipts, %d texts found, %d verified, %d failed, %d missing"
            % (experiment, len(canonical), found, verified, found - verified, len(missing))
        )
        if extraneous:
            print("  NOTE %s: %d run bundles have no canonical receipt (ignored)" % (experiment, len(extraneous)))

    if failures:
        print("\nHASH FAILURES (excluded from outputs):")
        for f in failures:
            print("  %(experiment)s %(decision_id)s %(source_run_path)s computed=%(computed_sha256)s expected=%(expected_sha256)s" % f)

    rows.sort(key=lambda r: (r["experiment"], r["condition"], r["decision_id"]))

    schema = pa.schema(
        [
            ("decision_id", pa.string()),
            ("ocid", pa.string()),
            ("experiment", pa.string()),
            ("condition", pa.string()),
            ("model_id", pa.string()),
            ("reasoning_sha256", pa.string()),
            ("reasoning_text", pa.string()),
            ("source_run_path", pa.string()),
            ("verified", pa.bool_()),
        ]
    )

    outputs = {}
    parquet_path = OUT_DIR / "reasoning_texts.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), parquet_path, compression="zstd")
    outputs["reasoning_texts.parquet"] = {"rows": len(rows), "sha256": sha256_file(parquet_path)}

    csv_path = OUT_DIR / "reasoning_texts.csv"
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    columns = [f.name for f in schema]
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row[c] for c in columns)
    csv_path.write_text(buf.getvalue(), encoding="utf-8")
    outputs["reasoning_texts.csv"] = {"rows": len(rows), "sha256": sha256_file(csv_path)}

    for name, meta in outputs.items():
        print("Wrote %s: %d rows, sha256 %s" % (name, meta["rows"], meta["sha256"]))

    manifest_path = OUT_DIR / "DATA_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["reasoning_supplement"] = {
        "generated_by": "data/build_reasoning_supplement.py",
        "hash_rule": "sha256 of the UTF-8 bytes of the reasoning text equals the receipt-bound agent_reasoning_sha256",
        "coverage": coverage,
        "hash_failures": failures,
    }
    manifest["outputs"].update(outputs)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("Updated DATA_MANIFEST.json")


if __name__ == "__main__":
    main()
