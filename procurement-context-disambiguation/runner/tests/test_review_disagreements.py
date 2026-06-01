"""Tests for the reconciliation tool (review_disagreements.py).

The build-package contract for this tool, per Sam's dispatch:

1. A 3-record disagreement scenario walked end-to-end with mocked stdin
   covers all four reviewer actions (keep / second-coder / override /
   quit-save).
2. Agreement records skip the prompt and write verbatim from the
   first-pass with reconciliation_action == "agreement-kept".
3. The reconciliation_action field is populated correctly for each
   action.
4. Resume semantics: on a second invocation, already-reconciled OCIDs
   are skipped.
5. Justification override requires a literal substring of the
   reasoning text (else re-prompt).

Plus methodological-honesty guards:

- The module docstring contains the verbatim methods-section sentence.
- The default-rule string surfaced to the reviewer matches the locked
  rubric document.

Hermetic — no network, no model calls, no file IO outside ``tmp_path``
and the repo-shipped fixture directory.
"""
from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from meshqu_runner.diagnostic import review_disagreements
from meshqu_runner.diagnostic.review_disagreements import (
    RECONCILIATION_ACTIONS,
    RUBRIC_DEFAULT_RULE,
    ReconciledEntry,
    append_reconciled_entry,
    read_reconciled_sheet,
    run_reconciliation_session,
)
from meshqu_runner.diagnostic.rubric_io import (
    CodedEntry,
    RubricSchemaError,
    append_entry,
)


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "rubric_diagnostic"
)
SPEC_PATH = FIXTURE_DIR / "inverted_operator_spec.json"
RUBRIC_DOC_PATH = (
    Path(__file__).resolve().parents[2] / "planning" / "diagnostic_rubric.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_bundles(tmp_path: Path) -> Path:
    """Copy bundle JSONs into a temp diagnostic dir."""
    diagnostic_dir = tmp_path / "diagnostic"
    diagnostic_dir.mkdir()
    for bundle_path in FIXTURE_DIR.glob("*.bundle.json"):
        shutil.copy(bundle_path, diagnostic_dir / bundle_path.name)
    return diagnostic_dir


def _write_pass(
    sheet_path: Path,
    rows: list[tuple[str, int, str]],
    coder: str,
    arm: str = "diagnostic_primary",
) -> None:
    """Write a coding sheet from (ocid, category, justification) tuples."""
    for ocid, cat, justification in rows:
        append_entry(
            sheet_path,
            CodedEntry(
                ocid=ocid,
                arm=arm,
                category=cat,
                justification=justification,
                coded_at="2026-05-29T00:00:00Z",
                coder=coder,
            ),
        )


def _read_output_raw(output_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Methodological-honesty guards
# ---------------------------------------------------------------------------


def test_module_docstring_contains_verbatim_methods_sentence():
    """The writeup methods section will lift Sam's verbatim 2026-05-30
    paragraph straight from this docstring. If anyone refactors it
    into 'blind re-coding' framing, this test fails.

    The docstring is whitespace-normalised before matching so a future
    line-wrap re-flow doesn't accidentally break the test — what we
    care about is the sequence of words, not the exact column wrap."""
    docstring = review_disagreements.__doc__ or ""
    # Collapse any run of whitespace (incl. newlines) to a single space.
    normalised = " ".join(docstring.split())
    expected_fragments = [
        "First pass: human coder coded blind.",
        "Second pass: AI second-coder coded blind.",
        "κ check surfaced systematic disagreement at the missing-evidence/rule-itself boundary.",
        "Reconciliation: human coder re-examined the 79 disagreement records with both calls visible alongside the rubric's default rule, applied the rule explicitly, and produced the final coding sheet.",
    ]
    for fragment in expected_fragments:
        assert fragment in normalised, f"missing fragment: {fragment!r}"
    # And the negative guard: every mention of "blind re-cod" in the
    # docstring is in a NEGATIVE framing. There are two such mentions
    # by design (the opening "NOT blind re-coding" + the writeup-anchor
    # "don't describe the reconciled sheet as 'blind re-coded'"). Any
    # mention NOT preceded by NOT / DON'T / NEVER / not- would be a
    # regression — assert that explicitly by checking the contexts.
    lowered = normalised.lower()
    cursor = 0
    while True:
        idx = lowered.find("blind re-cod", cursor)
        if idx == -1:
            break
        # Look at the 80 chars preceding this mention — wide
        # enough to cover both "not blind re-coding" and the longer
        # "describe the reconciled sheet as ..." anchor sentence.
        window = lowered[max(0, idx - 80): idx]
        assert any(
            negation in window
            for negation in ("not ", "don't", "describe the reconciled sheet as", "never")
        ), (
            f"'blind re-cod' mention without a negation prefix at position "
            f"{idx}; context: {lowered[max(0, idx - 100): idx + 30]!r}"
        )
        cursor = idx + len("blind re-cod")


def test_rubric_default_rule_matches_rubric_doc():
    """The default-rule string surfaced to the reviewer is enforced
    against the locked rubric document. If the rubric is ever edited,
    this test fires loud and the reviewer's display follows."""
    rubric_text = RUBRIC_DOC_PATH.read_text(encoding="utf-8")
    # The rubric has '**not**' (bold markdown); the surfaced string
    # strips the markdown emphasis. Normalise both sides on '**'.
    normalised_rubric = rubric_text.replace("**", "")
    assert RUBRIC_DEFAULT_RULE in normalised_rubric, (
        "The verbatim default-rule sentence has drifted from the rubric "
        "document at planning/diagnostic_rubric.md. STOP — surface to "
        "Sam before continuing."
    )


def test_reconciliation_action_vocabulary_locked():
    """The four-value vocabulary is part of the audit-trail contract.
    Adding a new action means downstream analysis-markdown PRs have to
    handle it — surface explicitly."""
    assert RECONCILIATION_ACTIONS == frozenset(
        {
            "agreement-kept",
            "first-pass-kept",
            "second-coder-adopted",
            "override",
        }
    )


# ---------------------------------------------------------------------------
# ReconciledEntry round-trip
# ---------------------------------------------------------------------------


def test_reconciled_entry_roundtrip(tmp_path):
    sheet = tmp_path / "out.jsonl"
    entry = ReconciledEntry(
        ocid="ocid-EX-001",
        arm="diagnostic_primary",
        category=2,
        justification="reasoning quote",
        coded_at="2026-05-30T00:00:00Z",
        coder="sam-reconciled",
        reconciliation_action="first-pass-kept",
        first_pass_category=2,
        second_coder_category=3,
    )
    append_reconciled_entry(sheet, entry)
    rows = read_reconciled_sheet(sheet)
    assert len(rows) == 1
    assert rows[0] == entry
    raw = _read_output_raw(sheet)
    assert set(raw[0].keys()) == {
        "ocid",
        "arm",
        "category",
        "justification",
        "coded_at",
        "coder",
        "reconciliation_action",
        "first_pass_category",
        "second_coder_category",
    }


def test_reconciled_entry_rejects_invalid_action(tmp_path):
    entry = ReconciledEntry(
        ocid="o",
        arm="diagnostic_primary",
        category=1,
        justification="j",
        coded_at="t",
        coder="c",
        reconciliation_action="bogus",
        first_pass_category=1,
        second_coder_category=2,
    )
    with pytest.raises(RubricSchemaError, match="Invalid reconciliation_action"):
        entry.to_json_line()


def test_reconciled_entry_rejects_invalid_category(tmp_path):
    entry = ReconciledEntry(
        ocid="o",
        arm="diagnostic_primary",
        category=7,
        justification="j",
        coded_at="t",
        coder="c",
        reconciliation_action="first-pass-kept",
        first_pass_category=1,
        second_coder_category=2,
    )
    with pytest.raises(RubricSchemaError, match="Invalid category"):
        entry.to_json_line()


# ---------------------------------------------------------------------------
# End-to-end walk: keep / second / override / quit-save
# ---------------------------------------------------------------------------


def test_session_walks_three_disagreements_with_all_actions(tmp_path):
    """3 disagreements + 'k' / 's' / 'o' actions → 3 rows with the
    matching reconciliation_action values."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "first-pass quote 1"),
            ("ocid-EX-002", 2, "first-pass quote 2"),
            ("ocid-EX-003", 1, "first-pass quote 3"),
        ],
        coder="sam-first-pass",
    )
    _write_pass(
        second_coder,
        [
            ("ocid-EX-001", 1, "second-coder quote 1"),
            ("ocid-EX-002", 3, "second-coder quote 2"),
            ("ocid-EX-003", 2, "second-coder quote 3"),
        ],
        coder="ai-second-coder",
    )

    # The override justification must be a literal substring of the
    # third bundle's reasoning text. Fixture says ocid-EX-003's
    # reasoning is about "award_value", so we can quote any substring
    # from the bundle JSON.
    bundle3_text = (FIXTURE_DIR / "ocid-EX-003.bundle.json").read_text(
        encoding="utf-8"
    )
    bundle3_payload = json.loads(bundle3_text)
    reasoning3 = bundle3_payload["agent"]["reasoning"]
    # Take the first ~30 chars of the reasoning as a valid quote.
    override_quote = reasoning3[:40].strip()

    stdin = io.StringIO(
        "k\n"            # disagreement 1: keep first-pass
        "s\n"            # disagreement 2: adopt second-coder
        "o\n"            # disagreement 3: override
        "3\n"            # override category
        f"{override_quote}\n"  # override justification (must substr the reasoning)
    )
    stdout = io.StringIO()

    rows_written = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )

    assert rows_written == 3
    raw = _read_output_raw(output)
    assert [r["ocid"] for r in raw] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    assert [r["reconciliation_action"] for r in raw] == [
        "first-pass-kept",
        "second-coder-adopted",
        "override",
    ]
    # First-pass-kept row: category is first-pass's value (2).
    assert raw[0]["category"] == 2
    assert raw[0]["first_pass_category"] == 2
    assert raw[0]["second_coder_category"] == 1
    assert raw[0]["justification"] == "first-pass quote 1"
    # Second-coder-adopted row: category is second-coder's value (3).
    assert raw[1]["category"] == 3
    assert raw[1]["first_pass_category"] == 2
    assert raw[1]["second_coder_category"] == 3
    assert raw[1]["justification"] == "second-coder quote 2"
    # Override row: category is what the reviewer typed (3).
    assert raw[2]["category"] == 3
    assert raw[2]["first_pass_category"] == 1
    assert raw[2]["second_coder_category"] == 2
    assert raw[2]["justification"] == override_quote
    # All rows carry the reconciliation coder identity, NOT the original
    # coders'.
    assert all(r["coder"] == "sam-reconciled" for r in raw)
    # Display shows the rubric refresher and the verbatim default rule
    # for the reviewer.
    out_text = stdout.getvalue()
    assert "RUBRIC REFRESHER" in out_text
    assert RUBRIC_DEFAULT_RULE in out_text
    assert "Disagreement 1 of 3" in out_text


def test_session_agreements_skip_prompt_and_copy_verbatim(tmp_path):
    """Records where both coders AGREE are copied verbatim from the
    first-pass with reconciliation_action == 'agreement-kept'. The
    reviewer is NEVER prompted for them."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "first-pass quote 1"),
            ("ocid-EX-002", 2, "first-pass quote 2"),
            ("ocid-EX-003", 1, "first-pass quote 3"),
        ],
        coder="sam-first-pass",
    )
    _write_pass(
        second_coder,
        [
            # All three agree with the first-pass.
            ("ocid-EX-001", 2, "second-coder quote 1"),
            ("ocid-EX-002", 2, "second-coder quote 2"),
            ("ocid-EX-003", 1, "second-coder quote 3"),
        ],
        coder="ai-second-coder",
    )

    # Empty stdin: if any prompt fires we'd hit EOFError.
    stdin = io.StringIO("")
    stdout = io.StringIO()

    rows_written = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )

    assert rows_written == 3
    raw = _read_output_raw(output)
    assert all(r["reconciliation_action"] == "agreement-kept" for r in raw)
    # category == first-pass category for every record.
    assert [r["category"] for r in raw] == [2, 2, 1]
    # Justifications are first-pass's (verbatim copy).
    assert raw[0]["justification"] == "first-pass quote 1"
    # The audit-trail fields surface BOTH original categories even when
    # they agree.
    for r in raw:
        assert r["first_pass_category"] == r["second_coder_category"]
    # No 'Disagreement' prompt rendered.
    assert "Disagreement 1 of" not in stdout.getvalue()


def test_session_quit_save_preserves_partial_progress(tmp_path):
    """'q' (quit-save) writes what's been reconciled so far + exits."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "fp1"),
            ("ocid-EX-002", 2, "fp2"),
            ("ocid-EX-003", 1, "fp3"),
        ],
        coder="sam-first-pass",
    )
    _write_pass(
        second_coder,
        [
            ("ocid-EX-001", 1, "sc1"),
            ("ocid-EX-002", 3, "sc2"),
            ("ocid-EX-003", 2, "sc3"),
        ],
        coder="ai-second-coder",
    )

    stdin = io.StringIO("k\n" "q\n")  # first 'k', then quit on second
    stdout = io.StringIO()

    rows_written = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )

    assert rows_written == 1
    raw = _read_output_raw(output)
    assert len(raw) == 1
    assert raw[0]["ocid"] == "ocid-EX-001"
    assert raw[0]["reconciliation_action"] == "first-pass-kept"
    assert "Quit." in stdout.getvalue()


# ---------------------------------------------------------------------------
# Resume semantics
# ---------------------------------------------------------------------------


def test_session_resume_skips_already_reconciled(tmp_path):
    """Second invocation: OCIDs already in the output sheet are
    skipped. Mirror's code_rubric.py's resume idiom."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "fp1"),
            ("ocid-EX-002", 2, "fp2"),
            ("ocid-EX-003", 1, "fp3"),
        ],
        coder="sam-first-pass",
    )
    _write_pass(
        second_coder,
        [
            ("ocid-EX-001", 1, "sc1"),
            ("ocid-EX-002", 3, "sc2"),
            ("ocid-EX-003", 2, "sc3"),
        ],
        coder="ai-second-coder",
    )

    # First session: reconcile only the first disagreement, then quit.
    rows_written_first = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=io.StringIO("k\n" "q\n"),
        stdout=io.StringIO(),
    )
    assert rows_written_first == 1

    # Second session: should NOT re-prompt for ocid-EX-001.
    rows_written_second = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=io.StringIO("s\n" "s\n"),
        stdout=io.StringIO(),
    )
    assert rows_written_second == 2
    raw = _read_output_raw(output)
    assert [r["ocid"] for r in raw] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    # The original action stuck around — resume doesn't overwrite.
    assert raw[0]["reconciliation_action"] == "first-pass-kept"
    assert raw[1]["reconciliation_action"] == "second-coder-adopted"
    assert raw[2]["reconciliation_action"] == "second-coder-adopted"


# ---------------------------------------------------------------------------
# Override justification must be a literal substring of reasoning
# ---------------------------------------------------------------------------


def test_override_justification_must_be_substring(tmp_path):
    """Override justification that isn't a substring of the reasoning
    text re-prompts."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [("ocid-EX-001", 2, "fp")],
        coder="sam-first-pass",
    )
    _write_pass(
        second_coder,
        [("ocid-EX-001", 1, "sc")],
        coder="ai-second-coder",
    )

    bundle_payload = json.loads(
        (FIXTURE_DIR / "ocid-EX-001.bundle.json").read_text(encoding="utf-8")
    )
    valid_quote = bundle_payload["agent"]["reasoning"][:25]

    stdin = io.StringIO(
        "o\n"                      # action: override
        "2\n"                      # category
        "totally-made-up-quote\n"  # not in reasoning -> reprompt
        "\n"                       # empty -> reprompt
        f"{valid_quote}\n"         # valid substring
    )
    stdout = io.StringIO()

    rows = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    out_text = stdout.getvalue()
    assert out_text.count("must be a literal substring") >= 1
    assert out_text.count("Justification cannot be empty") >= 1
    raw = _read_output_raw(output)
    assert raw[0]["justification"] == valid_quote
    assert raw[0]["reconciliation_action"] == "override"
    assert raw[0]["category"] == 2


# ---------------------------------------------------------------------------
# Invalid action re-prompts; one-side-only OCIDs reported
# ---------------------------------------------------------------------------


def test_invalid_action_reprompts(tmp_path):
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(first_pass, [("ocid-EX-001", 1, "fp")], coder="a")
    _write_pass(second_coder, [("ocid-EX-001", 2, "sc")], coder="b")

    stdin = io.StringIO(
        "x\n"  # invalid
        "K\n"  # uppercase k — accepted (we .lower())
    )
    stdout = io.StringIO()
    rows = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    assert "Invalid action" in stdout.getvalue()


def test_one_side_only_ocids_reported_not_written(tmp_path):
    """OCIDs in one sheet only are reported to stdout but NOT written
    to the output sheet — the reviewer should re-run the missing pass
    before reconciling."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "fp1"),
            ("ocid-EX-002", 2, "fp2"),
        ],
        coder="a",
    )
    _write_pass(
        second_coder,
        [
            ("ocid-EX-001", 2, "sc1"),
            ("ocid-EX-003", 1, "sc3"),
        ],
        coder="b",
    )

    stdin = io.StringIO("")
    stdout = io.StringIO()
    rows = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )
    # Only the one shared agreement (ocid-EX-001) is written.
    assert rows == 1
    raw = _read_output_raw(output)
    assert len(raw) == 1
    assert raw[0]["ocid"] == "ocid-EX-001"
    out_text = stdout.getvalue()
    # Warnings surface both one-sided sets.
    assert "in first-pass only" in out_text
    assert "in second-coder only" in out_text


# ---------------------------------------------------------------------------
# 'back' action
# ---------------------------------------------------------------------------


def test_back_action_rewinds_previous_record(tmp_path):
    """'b' (back) removes the previous record from the output and
    re-prompts for it."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(
        first_pass,
        [
            ("ocid-EX-001", 2, "fp1"),
            ("ocid-EX-002", 2, "fp2"),
        ],
        coder="a",
    )
    _write_pass(
        second_coder,
        [
            ("ocid-EX-001", 1, "sc1"),
            ("ocid-EX-002", 3, "sc2"),
        ],
        coder="b",
    )

    # Walk: first record 'k' (typo), then on second record 'b' (back),
    # re-do first record with 's', then second record with 'k'.
    stdin = io.StringIO(
        "k\n"
        "b\n"
        "s\n"  # rewound to record 1; pick second-coder this time
        "k\n"  # record 2
    )
    stdout = io.StringIO()
    rows = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 2
    raw = _read_output_raw(output)
    assert len(raw) == 2
    # ocid-EX-001 was rewound and re-coded as second-coder-adopted.
    by_ocid = {r["ocid"]: r for r in raw}
    assert by_ocid["ocid-EX-001"]["reconciliation_action"] == "second-coder-adopted"
    assert by_ocid["ocid-EX-002"]["reconciliation_action"] == "first-pass-kept"


def test_back_on_first_record_reprompts(tmp_path):
    """'b' on the first record (no previous) re-prompts; doesn't crash."""
    diagnostic_dir = _copy_bundles(tmp_path)
    first_pass = tmp_path / "first_pass.jsonl"
    second_coder = tmp_path / "second_coder.jsonl"
    output = tmp_path / "reconciled.jsonl"

    _write_pass(first_pass, [("ocid-EX-001", 2, "fp")], coder="a")
    _write_pass(second_coder, [("ocid-EX-001", 1, "sc")], coder="b")

    stdin = io.StringIO("b\n" "k\n")
    stdout = io.StringIO()
    rows = run_reconciliation_session(
        first_pass_path=first_pass,
        second_coder_path=second_coder,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_primary",
        coder="sam-reconciled",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    assert "No previous record to go back to" in stdout.getvalue()
