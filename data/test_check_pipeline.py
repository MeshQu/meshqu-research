#!/usr/bin/env python3
"""Tests for check_pipeline.py.

Each test reproduces a specific mistake a student is likely to make while
cleaning the corpus, then asserts that check_pipeline catches it AND that the
message points at the right cause. The point of the script is that a student
understands the mistake from the output alone, so the message text is part of
what is under test, not incidental.

Run:  python data/test_check_pipeline.py     (standalone)
      pytest data/test_check_pipeline.py     (if pytest is available)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_pipeline import (  # noqa: E402
    _default_corpus,
    _load,
    check_pipeline,
)

CORPUS = _load(_default_corpus())


def names(failures) -> set[str]:
    return {f.name for f in failures}


def find(failures, name):
    for f in failures:
        if f.name == name:
            return f
    raise AssertionError("expected a failure named %r, got %s" % (name, sorted(names(failures))))


# ------------------------------------------------------------ baseline


def test_shipped_corpus_passes():
    assert check_pipeline() == [], "the shipped corpus must satisfy every invariant"


def test_shipped_csv_passes():
    csv_path = _default_corpus().parent / "receipts.csv"
    if not csv_path.exists():
        return
    assert check_pipeline(csv_path) == [], "receipts.csv must agree with receipts.parquet"


def test_csv_and_parquet_agree():
    csv_path = _default_corpus().parent / "receipts.csv"
    if not csv_path.exists():
        return
    assert check_pipeline(csv_path) == check_pipeline(_default_corpus()) == []


# --------------------------------------------- trap 1: filling the nulls


def test_fillna_on_open_flag_is_caught():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") in (None, ""):
            r["procurement_method_open_flag"] = "false"

    failures = check_pipeline(rows)
    assert "procurement_method_open_flag non-null" in names(failures)

    f = find(failures, "procurement_method_open_flag non-null")
    assert f.expected == 204 and f.actual == 3044
    # the message must state the consequence in plain language
    assert "94.9%" in f.cause
    assert "no false branch" in f.cause
    assert "Leave the nulls in place" in f.cause


def test_boolean_cast_introducing_false_is_caught():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        v = r.get("procurement_method_open_flag")
        r["procurement_method_open_flag"] = "true" if v == "true" else "false"

    failures = check_pipeline(rows)
    f = find(failures, "procurement_method_open_flag values")
    assert "false" in str(f.actual)
    assert "fillna" in f.cause or "astype" in f.cause


def test_dropping_null_flag_rows_is_caught():
    rows = [r for r in copy.deepcopy(CORPUS) if r.get("procurement_method_open_flag")]
    failures = check_pipeline(rows)
    got = names(failures)
    # this mistake breaks several invariants at once; row count must be one
    assert "row count" in got
    assert find(failures, "row count").actual == 204
    assert "policy_verdict == DENY" in got
    assert "PROC-005-OPEN-TENDER firings" in got
    # and PROC-005's message must redirect to the open-flag explanation
    assert "open flag" in find(failures, "PROC-005-OPEN-TENDER firings").cause


# ------------------------------------ trap 2: inner join to reasoning_texts


def test_inner_join_dropping_e1_is_caught():
    rows = [r for r in copy.deepcopy(CORPUS) if r.get("experiment") != "E1"]
    failures = check_pipeline(rows)

    rc = find(failures, "row count")
    assert rc.actual == 2761
    assert "reasoning_texts" in rc.cause

    e1 = find(failures, "E1 row count")
    assert e1.actual == 0
    assert "inner join" in e1.cause and "left join" in e1.cause


# ------------------------------------------- trap 3: dedupe on ocid


def test_dedupe_on_ocid_is_caught():
    seen, rows = set(), []
    for r in copy.deepcopy(CORPUS):
        if r["ocid"] in seen:
            continue
        seen.add(r["ocid"])
        rows.append(r)

    failures = check_pipeline(rows)
    rc = find(failures, "row count")
    assert rc.actual == 283
    assert "Deduplicated on ocid" in rc.cause


# ----------------------------------- trap 7: splitting violation_codes


def test_comma_split_violation_codes_is_caught():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        codes = r["violation_codes"]
        if isinstance(codes, list):
            codes = json.dumps(codes)
        # the classic mistake: hand the raw string through as if it were a scalar
        r["violation_codes"] = codes.replace("[", "").replace("]", "")

    failures = check_pipeline(rows)
    f = find(failures, "violation_codes parseable")
    assert "json.loads" in f.cause


def test_json_string_and_list_forms_agree():
    as_strings = copy.deepcopy(CORPUS)
    for r in as_strings:
        if isinstance(r["violation_codes"], list):
            r["violation_codes"] = json.dumps(r["violation_codes"])
    assert check_pipeline(as_strings) == []


# ----------------------------------------- structural / robustness checks


def test_missing_column_is_reported_not_crashed():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        del r["procurement_method_open_flag"]

    failures = check_pipeline(rows)
    f = find(failures, "required columns present")
    assert "procurement_method_open_flag" in str(f.actual)


def test_renamed_column_is_reported():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        r["open_flag"] = r.pop("procurement_method_open_flag")
    failures = check_pipeline(rows)
    assert "required columns present" in names(failures)


def test_dead_rule_appearing_is_caught():
    rows = copy.deepcopy(CORPUS)
    codes = rows[0]["violation_codes"]
    rows[0]["violation_codes"] = (list(codes) if isinstance(codes, list) else json.loads(codes)) + [
        "PROC-004-COI"
    ]

    failures = check_pipeline(rows)
    f = find(failures, "PROC-004-COI firings")
    assert f.expected == 0 and f.actual == 1
    assert "cannot fire" in f.cause


def test_nan_is_treated_as_null():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") is None:
            r["procurement_method_open_flag"] = float("nan")
    assert check_pipeline(rows) == [], "NaN must be normalised to null, not counted"


def test_empty_string_is_treated_as_null():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") is None:
            r["procurement_method_open_flag"] = ""
    assert check_pipeline(rows) == []


def test_pandas_dataframe_input():
    try:
        import pandas as pd
    except ImportError:
        return
    df = pd.DataFrame(copy.deepcopy(CORPUS))
    assert check_pipeline(df) == [], "a pandas DataFrame of the corpus must pass"


def test_pandas_fillna_roundtrip_is_caught():
    try:
        import pandas as pd
    except ImportError:
        return
    df = pd.DataFrame(copy.deepcopy(CORPUS))
    df["procurement_method_open_flag"] = df["procurement_method_open_flag"].fillna("false")
    failures = check_pipeline(df)
    assert "procurement_method_open_flag non-null" in names(failures)


def test_pandas_from_parquet_with_ndarray_codes():
    """The most common student load path: pq.read_table(...).to_pandas().

    Parquet list columns come back as numpy ndarrays, not Python lists. A
    scalar NaN comparison against one raises ValueError rather than returning
    failures, so the checker used to crash on exactly the path most students
    take. Regression test for that.
    """
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return
    parquet = _default_corpus().parent / "receipts.parquet"
    if not parquet.exists():
        return

    df = pq.read_table(parquet).to_pandas()
    assert type(df["violation_codes"].iloc[0]).__name__ == "ndarray", (
        "precondition: this test is only meaningful while parquet list columns "
        "arrive as ndarrays"
    )
    assert check_pipeline(df) == [], "ndarray violation_codes must be counted, not crash"


def test_ndarray_codes_counted_not_just_tolerated():
    try:
        import numpy as np
    except ImportError:
        return
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        codes = r["violation_codes"]
        r["violation_codes"] = np.array(
            codes if isinstance(codes, list) else json.loads(codes), dtype=object
        )
    assert check_pipeline(rows) == [], "arrays must produce the same counts as lists"


def test_integer_one_is_not_a_valid_flag():
    """1 == True in Python, so a naive set difference accepts an int cast."""
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") == "true":
            r["procurement_method_open_flag"] = 1

    failures = check_pipeline(rows)
    f = find(failures, "procurement_method_open_flag values")
    assert "int" in str(f.actual)
    assert "integer" in f.cause


def test_float_one_is_not_a_valid_flag():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") == "true":
            r["procurement_method_open_flag"] = 1.0
    assert "procurement_method_open_flag values" in names(check_pipeline(rows))


def test_literal_true_boolean_is_accepted():
    """The documented wire format is a string, but a real bool is not a
    corruption of the count, so it must not be reported as a stray value."""
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") == "true":
            r["procurement_method_open_flag"] = True
    assert "procurement_method_open_flag values" not in names(check_pipeline(rows))


def test_failure_render_is_self_explanatory():
    rows = copy.deepcopy(CORPUS)
    for r in rows:
        if r.get("procurement_method_open_flag") in (None, ""):
            r["procurement_method_open_flag"] = "false"
    text = find(check_pipeline(rows), "procurement_method_open_flag non-null").render()
    assert "expected: 204" in text and "actual:   3044" in text
    assert "PROC-005" in text


def test_unreadable_path_surfaces_cleanly():
    try:
        check_pipeline("does/not/exist.parquet")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


# --------------------------------------------------------------- runner


def _run_standalone() -> int:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("  pass  %s" % name)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print("  FAIL  %s\n          %s: %s" % (name, type(exc).__name__, exc))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
