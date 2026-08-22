#!/usr/bin/env python3
"""Self-check for cleaning pipelines built on the MeshQu research corpus.

WHAT THIS IS
    A set of invariants that hold for the published corpus. Run your cleaned
    dataframe through it. If an invariant breaks, the output names it, gives
    expected against actual, and states the most likely cause.

WHY IT EXISTS
    Several of the corpus's properties look like data-quality problems and are
    not. The most important is `procurement_method_open_flag`, which is null on
    2,840 of 3,044 rows. Filling or dropping those nulls is ordinary cleaning
    hygiene and it destroys roughly 94.9% of the DENY signal without raising a
    single error. This script turns that silent failure into a loud one.

WHEN TO RUN IT
    - Once against the shipped corpus, before you change anything, to confirm
      your environment reads the files correctly.
    - After every cleaning step that drops rows, fills values, joins another
      table, or changes a dtype.
    - Before you report any number derived from this corpus.

USAGE
    python data/check_pipeline.py                    # smoke-test shipped corpus
    python data/check_pipeline.py path/to/mine.csv   # check your own export
    python data/check_pipeline.py path/to/mine.parquet

    from check_pipeline import check_pipeline
    check_pipeline(my_dataframe)                     # returns list of failures

EXIT CODES
    0 = every invariant holds. 1 = at least one broke.

See data/KNOWN_ISSUES.md for the full list of traps and what to do instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------- invariants

ROWS = 3044
OCIDS = 283
DENY = 1475
ALLOW = 1569
VIOLATIONS = 2740
RULE_FIRINGS = {
    "PROC-001-S53": 569,
    "PROC-002-AUTHORITY": 771,
    "PROC-005-OPEN-TENDER": 1400,
}
DEAD_RULES = ("PROC-003-DEBARMENT", "PROC-004-COI", "PROC-006-MOD-CAP")
OPEN_FLAG_NON_NULL = 204
EXPERIMENT_ROWS = {"E1": 283, "E2": 1429, "E3": 1332}

REQUIRED_COLUMNS = (
    "experiment",
    "ocid",
    "policy_verdict",
    "violation_codes",
    "procurement_method_open_flag",
)

_ROW_COUNT_CAUSES = """Common causes, in the order they usually happen:
  - Inner-joined receipts to reasoning_texts. E1 has no reasoning texts, so an
    inner join silently drops all 283 E1 rows and leaves 2,761.
  - Dropped rows where procurement_method_open_flag is null. That leaves 204.
  - Deduplicated on ocid. There are only 283 distinct OCIDs; the corpus is
    those records replayed across 13 conditions, so this leaves 283.
  - Applied dropna() across all columns, which removes every row whose
    open flag is null."""

_OPEN_FLAG_CAUSE = """You have almost certainly filled or dropped nulls in
procurement_method_open_flag. Do not do this.

That column is not a boolean with missing data. It is an "open detected" flag:
it holds the string 'true' on 204 rows and null on the other 2,840, and it has
no false branch anywhere in the generating code. A null means the procurement
method was something other than open (usually 'selective'), not that the value
is unknown.

Rule PROC-005-OPEN-TENDER treats the null as the violation state. PROC-005
accounts for 1,400 of 2,740 violations and 94.9% of all DENY verdicts, so
filling or dropping these nulls destroys most of the signal the corpus exists
to demonstrate — and it does so without raising an error.

Leave the nulls in place. Treat the column as two-state: open vs not-open."""


class Failure:
    """One broken invariant."""

    def __init__(self, name: str, expected, actual, cause: str):
        self.name = name
        self.expected = expected
        self.actual = actual
        self.cause = cause

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Failure(%s: expected %r, got %r)" % (self.name, self.expected, self.actual)

    def render(self) -> str:
        head = "FAIL  %s\n        expected: %s\n        actual:   %s" % (
            self.name,
            self.expected,
            self.actual,
        )
        body = "\n".join("        " + line for line in self.cause.splitlines())
        return head + "\n\n" + body + "\n"


# ------------------------------------------------------------------ loading


def _is_array_like(value) -> bool:
    """True for numpy arrays and similar sequence containers.

    A parquet list column arrives as a numpy ndarray once the table has been
    through .to_pandas(), which is the most common way a student loads this
    corpus. Comparing an array to itself yields an array rather than a bool, so
    containers must be converted before any scalar test touches them.
    """
    return (
        not isinstance(value, (str, bytes, dict))
        and hasattr(value, "__len__")
        and hasattr(value, "tolist")
    )


def _is_nan(value) -> bool:
    """Scalar NaN test. Only safe once containers have been ruled out."""
    return value != value


def _is_true_flag(value) -> bool:
    """Only the string 'true' or the boolean True count as a set flag.

    Deliberately strict about type. Python treats 1 == True, so an equality or
    set-membership test would silently accept an integer or float 1 — meaning a
    column cast to int would pass while violating the documented string-boolean
    wire format.
    """
    if isinstance(value, bool):
        return value is True
    return isinstance(value, str) and value == "true"


def _clean(value):
    """Normalise containers to lists, and NaN / empty strings to None."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if _is_array_like(value):
        return value.tolist()
    if isinstance(value, str):
        return None if value.strip() == "" else value
    if _is_nan(value):
        return None
    return value


def _codes(value):
    """violation_codes is a list in parquet and a JSON array string in CSV."""
    value = _clean(value)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return ["<UNPARSEABLE:%s>" % value[:40]]
        return list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
    return [value]


def _have_pyarrow() -> bool:
    try:
        import pyarrow.parquet  # noqa: F401, PLC0415 - availability probe
    except ImportError:
        return False
    return True


def _default_corpus() -> Path:
    """Prefer the canonical parquet; fall back to the CSV when pyarrow is
    unavailable, so this script runs on a stock interpreter with no extras."""
    here = Path(__file__).resolve().parent
    names = ("receipts.parquet", "receipts.csv") if _have_pyarrow() else ("receipts.csv",)
    for name in names:
        candidate = here / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No shipped corpus found next to this script. Pass a path explicitly. "
        "(Reading receipts.parquet needs pyarrow; receipts.csv needs nothing.)"
    )


def _load(source) -> list[dict]:
    """Accept a dataframe, a path, or None for the shipped corpus."""
    if source is None:
        source = _default_corpus()

    # pandas DataFrame (duck-typed so pandas stays an optional import)
    if hasattr(source, "to_dict") and hasattr(source, "columns"):
        return list(source.to_dict("records"))

    if isinstance(source, list):
        return list(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError("No such file: %s" % path)

    if path.suffix == ".parquet":
        import pyarrow.parquet as pq  # noqa: PLC0415 - optional, parquet only

        return pq.read_table(path).to_pylist()

    if path.suffix in (".csv", ".txt"):
        import csv  # noqa: PLC0415 - stdlib, csv only

        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    raise ValueError(
        "Unsupported file type %r. Pass a .parquet or .csv path, or a dataframe."
        % path.suffix
    )


# ---------------------------------------------------------------- the checks


def check_pipeline(source=None) -> list[Failure]:
    """Return a list of Failure objects. Empty list means everything holds."""
    rows = _load(source)
    failures: list[Failure] = []

    present = set(rows[0].keys()) if rows else set()
    missing = [c for c in REQUIRED_COLUMNS if c not in present]
    if missing:
        failures.append(
            Failure(
                "required columns present",
                "all of: %s" % ", ".join(REQUIRED_COLUMNS),
                "missing: %s" % ", ".join(missing),
                "These columns are needed to check the corpus invariants. If you\n"
                "renamed or dropped them, the remaining checks below are skipped\n"
                "or unreliable. Rename them back before relying on this script.",
            )
        )

    # 1. row count
    if len(rows) != ROWS:
        failures.append(
            Failure("row count", ROWS, len(rows), _ROW_COUNT_CAUSES)
        )

    # 2. distinct OCIDs
    if "ocid" in present:
        distinct = len({_clean(r.get("ocid")) for r in rows})
        if distinct != OCIDS:
            failures.append(
                Failure(
                    "distinct ocids",
                    OCIDS,
                    distinct,
                    "The corpus is 283 procurement records replayed across 13\n"
                    "conditions. Fewer distinct OCIDs means rows were dropped;\n"
                    "more means rows from outside this corpus were joined in.",
                )
            )

    # 3-4. verdict split
    if "policy_verdict" in present:
        verdicts = [_clean(r.get("policy_verdict")) for r in rows]
        for label, expected in (("DENY", DENY), ("ALLOW", ALLOW)):
            actual = verdicts.count(label)
            if actual != expected:
                failures.append(
                    Failure(
                        "policy_verdict == %s" % label,
                        expected,
                        actual,
                        "The published split is 1,475 DENY / 1,569 ALLOW over 3,044\n"
                        "rows. If DENY has fallen sharply, check the open-flag\n"
                        "invariant below first — that is the usual cause.\n"
                        "Note policy_verdict is the rule engine, ai_verdict is the\n"
                        "model. They disagree by design; that disagreement is the\n"
                        "subject of the research, not an error to clean away.",
                    )
                )

    # 5-7. violations and rule firings
    if "violation_codes" in present:
        all_codes: list[str] = []
        for r in rows:
            all_codes.extend(_codes(r.get("violation_codes")))

        unparseable = [c for c in all_codes if str(c).startswith("<UNPARSEABLE:")]
        if unparseable:
            failures.append(
                Failure(
                    "violation_codes parseable",
                    "JSON arrays",
                    "%d unparseable values, e.g. %s" % (len(unparseable), unparseable[0]),
                    "In receipts.csv, violation_codes is a JSON array serialised as\n"
                    'a string, for example ["PROC-001-S53","PROC-005-OPEN-TENDER"].\n'
                    "Parse it with json.loads(). Splitting on commas breaks the\n"
                    "rule codes apart and produces fragments with stray quotes.",
                )
            )

        if len(all_codes) != VIOLATIONS:
            failures.append(
                Failure(
                    "total violation rows",
                    VIOLATIONS,
                    len(all_codes),
                    "The flattened violation count should equal the row count of\n"
                    "violations.parquet. If it is lower, rows were dropped; if the\n"
                    "codes failed to parse, fix that first — the count above is\n"
                    "computed from whatever parsed.",
                )
            )

        for code, expected in sorted(RULE_FIRINGS.items()):
            actual = all_codes.count(code)
            if actual != expected:
                extra = ""
                if code == "PROC-005-OPEN-TENDER":
                    extra = (
                        "\n\nPROC-005 is the rule most sensitive to cleaning. It fires\n"
                        "when a record is above threshold and the open flag is null.\n"
                        "If this count moved, read the open-flag invariant below."
                    )
                failures.append(
                    Failure(
                        "%s firings" % code,
                        expected,
                        actual,
                        "Rule-firing counts are fixed properties of the published\n"
                        "corpus. A change here means rows were added, dropped, or\n"
                        "their violation_codes altered." + extra,
                    )
                )

        for code in DEAD_RULES:
            actual = all_codes.count(code)
            if actual != 0:
                failures.append(
                    Failure(
                        "%s firings" % code,
                        0,
                        actual,
                        "This rule cannot fire on this corpus and never does in the\n"
                        "published data. PROC-003 needs a supplier on a synthetic\n"
                        "sanctions list, PROC-004 needs a conflict-of-interest field\n"
                        "that the OCDS substrate does not carry, and PROC-006 needs\n"
                        "is_modification to be true, which it never is.\n"
                        "A non-zero count means the data is not the published corpus.",
                    )
                )

    # 8. the open flag - the one that matters most
    if "procurement_method_open_flag" in present:
        non_null = sum(
            1 for r in rows if _clean(r.get("procurement_method_open_flag")) is not None
        )
        if non_null != OPEN_FLAG_NON_NULL:
            failures.append(
                Failure(
                    "procurement_method_open_flag non-null",
                    OPEN_FLAG_NON_NULL,
                    non_null,
                    _OPEN_FLAG_CAUSE,
                )
            )

        seen = [_clean(r.get("procurement_method_open_flag")) for r in rows]
        invalid = sorted(
            {"%s (%s)" % (v, type(v).__name__) for v in seen if v is not None and not _is_true_flag(v)}
        )
        if invalid:
            failures.append(
                Failure(
                    "procurement_method_open_flag values",
                    "only the string 'true', or null",
                    invalid,
                    "This column never holds a false value anywhere in the corpus,\n"
                    "and its set values are the string 'true', not a boolean or a\n"
                    "number. If you see anything else, it was introduced by a\n"
                    "fillna, an astype(bool) that turned null into False, or an\n"
                    "integer cast. Note that an integer 1 is not equivalent here:\n"
                    "the wire format is a string boolean and the dtype is part of\n"
                    "what this corpus documents.",
                )
            )

    # 9. experiment split
    if "experiment" in present:
        for name, expected in sorted(EXPERIMENT_ROWS.items()):
            actual = sum(1 for r in rows if _clean(r.get("experiment")) == name)
            if actual != expected:
                extra = ""
                if name == "E1" and actual == 0:
                    extra = (
                        "\n\nE1 is missing entirely. The usual cause is an inner join to\n"
                        "reasoning_texts, which covers E2 and E3 only.\n"
                        "Use a left join if you need to keep the baseline arm."
                    )
                failures.append(
                    Failure(
                        "%s row count" % name,
                        expected,
                        actual,
                        "Expected split is E1 283, E2 1,429, E3 1,332." + extra,
                    )
                )

    return failures


# --------------------------------------------------------------------- CLI


def main(argv: list[str]) -> int:
    source = argv[1] if len(argv) > 1 else None
    label = source if source else "shipped corpus (%s)" % _default_corpus().name

    try:
        failures = check_pipeline(source)
    except Exception as exc:  # noqa: BLE001 - surface any load error plainly
        print("Could not read %s\n  %s: %s" % (label, type(exc).__name__, exc))
        return 1

    print("check_pipeline - %s\n" % label)

    if not failures:
        print("PASS  all %d invariants hold." % _invariant_count())
        print("      3,044 rows / 283 OCIDs / 1,475 DENY / 2,740 violations")
        print("      PROC-005 1,400 / PROC-002 771 / PROC-001 569")
        print("      204 non-null open flags, 2,840 nulls left in place.")
        return 0

    for failure in failures:
        print(failure.render())
    print("%d invariant(s) broke. See data/KNOWN_ISSUES.md." % len(failures))
    return 1


def _invariant_count() -> int:
    return 1 + 1 + 1 + 2 + 2 + len(RULE_FIRINGS) + len(DEAD_RULES) + 2 + len(EXPERIMENT_ROWS)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
