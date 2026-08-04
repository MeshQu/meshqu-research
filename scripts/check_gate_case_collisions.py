#!/usr/bin/env python3
"""Gate-literal x corpus-distinct-value collision scan (IA-2026-03 pin test).

Guards against the defect class audited in IA-2026-03 (tradequ #761): the
engine's `when`-gate comparisons are STRICT (`===` / `Array.includes`, no case
folding), so a case, whitespace, or type mismatch between a gate literal and a
record value silently disqualifies the rule (NA), producing FEWER violations
and possibly a silent ALLOW. The defect's direction is one-way: any collision
means published violation counts are understated.

What it does, mechanically:

1. Reads `data/DATA_MANIFEST.json` for the list of published corpus tars and
   re-verifies each tar's SHA-256 against the manifest (the corpus identity is
   part of the pin — a digest drift fails the run).
2. For every receipt bundle, extracts the gate inventory (`equals` / `in`
   `when`-clauses) from the bundle's OWN embedded `policy_snapshot.json`, so a
   future corpus that ratifies a different pack is covered automatically.
3. Enumerates the DISTINCT raw values appearing at every gated field path in
   the evaluated contexts (`receipt.json -> context.fields`), and classifies
   each distinct value against each gate literal on that field:

     EXACT               strict match (value and type)
     CASE-VARIANT        equal after case-folding, unequal strict
     WHITESPACE-VARIANT  equal after trim/collapse, unequal strict
     CASE+WS-VARIANT     equal only after both folds
     TYPE-VARIANT        non-string whose JSON/string form folds to the
                         literal (e.g. boolean true vs "true") — recorded,
                         never folded: booleans were never meant to fold
     NO                  none of the above
     ABSENT              field missing from the context (exists-gate domain;
                         legitimately NA, not a collision)

4. Exits 0 iff every classification is EXACT, NO, or ABSENT. Any variant class
   (CASE / WHITESPACE / CASE+WS / TYPE) is a collision: exit 1. A collision on
   a future corpus means a new silent-NA hazard was introduced at ingestion —
   fix the substrate encoding or make the intent explicit in the pack (e.g.
   the gate-level opt-in `case_sensitive` shipped for tradequ #761) before
   publishing.

Condition-level list rules (`rule_type: "list"`) are printed as a labelled
appendix only. They case-fold BY DEFAULT (`case_sensitive ?? false` in
`@meshqu/core` rules/list.ts) — different semantics, different exposure — and
are never mixed into the pass/fail decision.

Run from the repo root (stdlib only, Python >= 3.9):

    python3 scripts/check_gate_case_collisions.py

Uses Python `tarfile` deliberately: bsdtar hides the AppleDouble sidecars
present in the E1 tar, and evidence-grade listings must see every member.
Read-only: never mutates a published artefact.

Provenance: docs/integrity-audits/2026-08-04-when-gate-case-blast-radius.md
(IA-2026-03), which pinned the E1-E3 corpus CLEAN with this scan.
"""

import hashlib
import json
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "DATA_MANIFEST.json"

FAILING_CLASSES = ("CASE-VARIANT", "WHITESPACE-VARIANT", "CASE+WS-VARIANT", "TYPE-VARIANT")
CLASS_ORDER = ["EXACT", *FAILING_CLASSES, "NO", "ABSENT"]

_WS = re.compile(r"\s+")


def ws_fold(s):
    return _WS.sub(" ", s.strip())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_gates(pack):
    """Yield (rule_code, field, kind, literal_or_tuple) for equals/in when-gates."""
    gates = []

    def walk(rule_code, when):
        if not isinstance(when, dict):
            return
        for key in ("all", "any"):
            if key in when:
                for w in when[key]:
                    walk(rule_code, w)
                return
        if "field" in when:
            if "equals" in when:
                gates.append((rule_code, when["field"], "equals", when["equals"]))
            elif "in" in when:
                gates.append((rule_code, when["field"], "in", tuple(when["in"])))

    for rule in pack.get("rules", []):
        walk(rule["code"], rule.get("when"))
    return gates


def classify(value, literal):
    """Classify one raw context value against one gate literal, strict-first."""
    if isinstance(value, str) and isinstance(literal, str):
        if value == literal:
            return "EXACT"
        if value.casefold() == literal.casefold():
            return "CASE-VARIANT"
        if ws_fold(value) == ws_fold(literal):
            return "WHITESPACE-VARIANT"
        if ws_fold(value).casefold() == ws_fold(literal).casefold():
            return "CASE+WS-VARIANT"
        return "NO"
    if type(value) is type(literal) and value == literal:
        return "EXACT"
    # Cross-type: TYPE-VARIANT iff the JSON/string form of either side folds
    # to the other (true vs "true", 30 vs "30", "True" vs true).
    def forms(x):
        out = {str(x).casefold()}
        try:
            out.add(json.dumps(x).casefold())
        except TypeError:
            pass
        return out

    if forms(value) & forms(literal):
        return "TYPE-VARIANT"
    return "NO"


def classify_against(value, kind, literal):
    if kind == "equals":
        return classify(value, literal)
    return min((classify(value, lit) for lit in literal), key=CLASS_ORDER.index)


def self_test():
    cases = [
        ("true", "true", "EXACT"),
        ("True", "true", "CASE-VARIANT"),
        ("TRUE", "true", "CASE-VARIANT"),
        (" true", "true", "WHITESPACE-VARIANT"),
        ("true ", "true", "WHITESPACE-VARIANT"),
        (" True ", "true", "CASE+WS-VARIANT"),
        (True, "true", "TYPE-VARIANT"),
        (False, "false", "TYPE-VARIANT"),
        ("false", "true", "NO"),
        (1, "true", "NO"),
        (True, True, "EXACT"),
        ("true", True, "TYPE-VARIANT"),
        (30, 30, "EXACT"),
        ("30", 30, "TYPE-VARIANT"),
        (31, 30, "NO"),
    ]
    for value, literal, expected in cases:
        got = classify(value, literal)
        assert got == expected, f"classify({value!r}, {literal!r}) = {got}, expected {expected}"
    assert classify_against("Apple", "in", ("apple", "pear")) == "CASE-VARIANT"
    assert classify_against("apple", "in", ("apple", "pear")) == "EXACT"
    assert classify_against("plum", "in", ("apple", "pear")) == "NO"
    print("self-test: 18 classifier cases OK")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return 0

    manifest = json.loads(MANIFEST.read_text())
    failures = []
    rows = []
    appendix = []

    for corpus_name, meta in manifest["corpora"].items():
        tar_path = REPO / meta["path"]
        actual = sha256_file(tar_path)
        if actual != meta["sha256"]:
            print(f"FAIL {corpus_name}: tar digest {actual} != manifest {meta['sha256']}")
            return 1

        # (snapshot_digest) -> {"gates": [...], "list_rules": [...]}
        packs = {}
        values = defaultdict(dict)
        receipts = 0
        with tarfile.open(tar_path) as tar:
            for member in tar:
                base = member.name.rsplit("/", 1)[-1]
                if not member.name.endswith(".json") or base.startswith("._"):
                    continue
                bundle = json.load(tar.extractfile(member))
                snap_str = bundle["files"]["policy_snapshot.json"]
                digest = hashlib.sha256(snap_str.encode()).hexdigest()
                if digest not in packs:
                    pack = json.loads(snap_str)
                    packs[digest] = {
                        "gates": extract_gates(pack),
                        "list_rules": [
                            (
                                r["code"],
                                r["condition"]["field"],
                                tuple(r["condition"].get("forbidden") or r["condition"].get("allowed") or ()),
                            )
                            for r in pack["rules"]
                            if r.get("rule_type") == "list"
                        ],
                    }
                receipt = json.loads(bundle["files"]["receipt.json"])
                fields = receipt["context"]["fields"]
                gated = {g[1] for g in packs[digest]["gates"]}
                listed = {f for _, f, _ in packs[digest]["list_rules"]}
                for field in gated | listed:
                    if field in fields:
                        v = fields[field]
                        key = (type(v).__name__, json.dumps(v, sort_keys=True))
                    else:
                        v, key = None, ("ABSENT", "ABSENT")
                    slot = values[field].setdefault(key, [v, 0])
                    slot[1] += 1
                receipts += 1

        if receipts != meta["receipts"]:
            print(f"FAIL {corpus_name}: scanned {receipts} receipts, manifest says {meta['receipts']}")
            return 1

        seen_list_rules = set()
        for digest, pack_info in packs.items():
            for rule_code, field, kind, literal in pack_info["gates"]:
                for key, (v, count) in sorted(values[field].items()):
                    cls = "ABSENT" if key == ("ABSENT", "ABSENT") else classify_against(v, kind, literal)
                    rows.append((corpus_name, rule_code, field, kind, literal, key[1], key[0], count, cls))
                    if cls in FAILING_CLASSES:
                        failures.append(rows[-1])

            # Appendix: condition-level list rules, informational only.
            for rule_code, field, lits in pack_info["list_rules"]:
                if (rule_code, field) in seen_list_rules:
                    continue
                seen_list_rules.add((rule_code, field))
                folded = {str(l).casefold() for l in lits}
                matches = {
                    key[1]: count
                    for key, (v, count) in values[field].items()
                    if key != ("ABSENT", "ABSENT") and str(v).casefold() in folded
                }
                appendix.append((corpus_name, rule_code, field, len(values[field]), matches))

        digest_list = ", ".join(sorted(packs))
        print(f"{corpus_name}: {receipts} receipts scanned, tar sha256 verified, "
              f"embedded pack digest(s): {digest_list}")

    print("\nGate-level collision table (strict === / includes semantics):")
    print(f"{'corpus':<4} {'rule':<22} {'field':<36} {'gate':<18} {'value':<12} {'type':<6} {'n':>5}  class")
    for corpus, rule, field, kind, literal, val, typ, count, cls in rows:
        gate = f"{kind}={literal!r}"
        print(f"{corpus:<4} {rule:<22} {field:<36} {gate:<18} {val:<12} {typ:<6} {count:>5}  {cls}")

    print("\nAppendix — condition-level list rules (case-fold by default; informational):")
    for corpus, rule, field, n_distinct, matches in appendix:
        print(f"  {corpus} {rule}: field={field}, {n_distinct} distinct values, fold-matches={matches or 'none'}")

    if failures:
        print(f"\nCOLLISIONS FOUND: {len(failures)} — a gate literal and a corpus value "
              f"differ only by case/whitespace/type. See IA-2026-03 for triage.")
        for f in failures:
            print("  !!", f)
        return 1
    print(f"\nCLEAN: no case/whitespace/type variant between any gate literal and any corpus value.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
