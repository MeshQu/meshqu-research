"""Tests for the AI-first review-and-adjudication tool (review_all.py).

The build-package contract for this tool, per Sam's dispatch:

1. A 3-record agent-sheet scenario walked end-to-end with mocked stdin
   covers all four actions (accept / override / back / quit-save).
2. Every record receives the prompt (no auto-skip — this protocol has no
   "agreement-kept" auto-copy from agreement records).
3. The ``review_action`` field is populated correctly for each action
   (``agent-accepted`` for accept, ``human-overridden`` for override).
4. The ``agent_category`` / ``agent_justification`` / ``agent_identity``
   fields are populated from the input agent sheet.
5. Resume semantics: on a second invocation, already-reviewed OCIDs are
   skipped.
6. Override justification requires a literal substring of the reasoning
   text (else re-prompt) — same machinery as ``review_disagreements.py``.
7. Agent-sheet / diagnostic-dir OCID count + content cross-check
   STOPs at startup with a clear error before any prompting.
8. The output sheet is a CodedEntry SUPERSET — ``score_rubric.read_sheet``
   loads it unchanged for κ computation against any other coding sheet.

Plus methodological-honesty guards (mirror of PR #108's pattern):

- The module docstring contains the verbatim 2026-06-07 protocol
  disclosure sentence from Sam.
- "blind first pass" appears in the docstring ONLY in negative framings
  (each occurrence preceded by NOT / NEVER / not-).
- "AI-first" appears positively framed.
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

from meshqu_runner.diagnostic import review_all
from meshqu_runner.diagnostic.review_all import (
    AIFirstReviewedEntry,
    REVIEW_ACTIONS,
    RUBRIC_DEFAULT_RULE,
    append_ai_first_reviewed_entry,
    read_ai_first_reviewed_sheet,
    run_review_session,
)
from meshqu_runner.diagnostic.rubric_io import (
    CodedEntry,
    RubricSchemaError,
    append_entry,
    read_sheet,
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


def _write_agent_sheet(
    sheet_path: Path,
    rows: list[tuple[str, int, str]],
    coder: str = "claude-opus-4-7-blind-agent",
    arm: str = "diagnostic_claude",
) -> None:
    """Write an agent coding sheet from (ocid, category, justification) tuples."""
    for ocid, cat, justification in rows:
        append_entry(
            sheet_path,
            CodedEntry(
                ocid=ocid,
                arm=arm,
                category=cat,
                justification=justification,
                coded_at="2026-06-07T00:00:00Z",
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


def test_module_docstring_contains_verbatim_protocol_disclosure():
    """The writeup methods section will lift Sam's verbatim 2026-06-07
    paragraph straight from this docstring. If anyone refactors it
    into 'blind first pass' or 'reconciliation' framing, this test fails.

    Mirrors the docstring test in test_review_disagreements.py — the
    docstring is whitespace-normalised before matching so a future
    line-wrap re-flow doesn't accidentally break the test."""
    docstring = review_all.__doc__ or ""
    normalised = " ".join(docstring.split())
    expected_fragments = [
        "diagnostic_primary was coded via blind human first pass + blind "
        "AI second-coder + reconciliation;",
        "diagnostic_claude was coded via AI-first + human review-and-"
        "adjudication of all 100 records with rubric visible.",
        "The protocol change for claude was made in response to a "
        "methodological observation surfaced during primary's "
        "reconciliation (see decision_log entry 2026-06-07).",
    ]
    for fragment in expected_fragments:
        assert fragment in normalised, f"missing fragment: {fragment!r}"


def test_module_docstring_blind_first_pass_only_in_negative_framings():
    """Every mention of 'blind first pass' / 'blind first-pass' /
    'blind-human-first-pass' in the docstring must appear in a context
    that frames it as either (a) negated ("NOT blind first-pass"),
    (b) attributed to primary's failed protocol ("primary's
    reconciliation ... the blind-human-first-pass protocol produced
    drift"), or (c) inside the verbatim Sam quote which describes
    primary, not this tool.

    Positive framings — using "blind first pass" to describe THIS
    tool's protocol — would mis-characterise the AI-first tool as
    something it isn't, so they're forbidden. This is the same
    enforcement structure as PR #108's docstring test."""
    docstring = review_all.__doc__ or ""
    normalised = " ".join(docstring.split())
    lowered = normalised.lower()
    # Find every occurrence of the substring "blind" followed by "first"
    # within a short window — catches "blind first pass", "blind
    # first-pass", "blind-human-first-pass".
    cursor = 0
    occurrences = 0
    while True:
        idx = lowered.find("blind", cursor)
        if idx == -1:
            break
        # Look forward 25 chars for "first".
        window_after = lowered[idx: idx + 30]
        if "first" not in window_after:
            cursor = idx + len("blind")
            continue
        occurrences += 1
        # Look at the 100 chars preceding this mention. Wide enough to
        # catch the contextual anchors that frame the mention as a
        # description of primary's protocol (not this tool's).
        window_before = lowered[max(0, idx - 100): idx]
        # Acceptable framings:
        #   - Sam's verbatim quote describing primary's protocol.
        #   - Explicit negation (NOT / not / NEVER / never / don't).
        #   - "primary's reconciliation" anchor — the docstring's
        #     "Why this protocol exists" paragraph attributes the
        #     failure to primary's protocol; the AI-first tool was
        #     added in response.
        sam_quote_anchor = "diagnostic_primary was coded via"
        in_sam_quote = sam_quote_anchor in window_before
        has_negation = any(
            tok in window_before
            for tok in ("not ", "never", "don't")
        )
        attributed_to_primary = any(
            tok in window_before
            for tok in (
                "primary's reconciliation",
                "primary protocol",
                "in response to",
            )
        )
        assert in_sam_quote or has_negation or attributed_to_primary, (
            f"'blind...first' mention without negation prefix, Sam-quote "
            f"anchor, or primary-attribution anchor at position {idx}; "
            f"context: "
            f"{lowered[max(0, idx - 120): idx + 50]!r}"
        )
        cursor = idx + len("blind")
    # At least two occurrences are expected (1 explicit negation +
    # 1 inside Sam's quote, at minimum). Belt-and-braces: if this drops
    # to zero, the docstring's been gutted and the test should fire.
    assert occurrences >= 2, (
        f"Expected >=2 'blind...first' mentions in docstring "
        f"(1 negative framing + 1 in Sam's quote); got {occurrences}."
    )


def test_module_docstring_ai_first_appears_with_positive_framing():
    """'AI-first' appears in the module docstring with positive framing
    (NOT NEGATED). The protocol disclosure quotes it positively; if
    someone refactored to make every 'AI-first' mention negated, the
    tool would be mis-described."""
    docstring = review_all.__doc__ or ""
    normalised = " ".join(docstring.split())
    lowered = normalised.lower()
    assert "ai-first" in lowered, (
        "Module docstring must mention 'AI-first' (the tool's protocol "
        "name)."
    )
    # At least one occurrence must NOT be preceded by a negation in the
    # 30 chars before it.
    cursor = 0
    saw_positive = False
    while True:
        idx = lowered.find("ai-first", cursor)
        if idx == -1:
            break
        window_before = lowered[max(0, idx - 30): idx]
        if not any(tok in window_before for tok in ("not ", "never", "don't")):
            saw_positive = True
            break
        cursor = idx + len("ai-first")
    assert saw_positive, (
        "Every 'AI-first' mention in the docstring is preceded by a "
        "negation. The tool's protocol name should be used positively at "
        "least once."
    )


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


def test_review_action_vocabulary_locked():
    """The 2-value vocabulary is part of the audit-trail contract.
    Adding a new action means downstream analysis-markdown PRs have to
    handle it — surface explicitly. The contrast with reconciliation's
    4-value vocabulary is deliberate (this protocol has no
    'agreement-kept' / 'first-pass-kept' — there's only ever one prior
    coder)."""
    assert REVIEW_ACTIONS == frozenset(
        {
            "agent-accepted",
            "human-overridden",
        }
    )


# ---------------------------------------------------------------------------
# AIFirstReviewedEntry round-trip
# ---------------------------------------------------------------------------


def test_ai_first_reviewed_entry_roundtrip(tmp_path):
    sheet = tmp_path / "out.jsonl"
    entry = AIFirstReviewedEntry(
        ocid="ocid-EX-001",
        arm="diagnostic_claude",
        category=2,
        justification="reasoning quote",
        coded_at="2026-06-07T00:00:00Z",
        coder="sam",
        review_action="agent-accepted",
        agent_category=2,
        agent_justification="reasoning quote",
        agent_identity="claude-opus-4-7-blind-agent",
    )
    append_ai_first_reviewed_entry(sheet, entry)
    rows = read_ai_first_reviewed_sheet(sheet)
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
        "review_action",
        "agent_category",
        "agent_justification",
        "agent_identity",
    }


def test_ai_first_reviewed_entry_rejects_invalid_action():
    entry = AIFirstReviewedEntry(
        ocid="o",
        arm="diagnostic_claude",
        category=1,
        justification="j",
        coded_at="t",
        coder="c",
        review_action="agreement-kept",  # from the other tool's vocab
        agent_category=1,
        agent_justification="j",
        agent_identity="a",
    )
    with pytest.raises(RubricSchemaError, match="Invalid review_action"):
        entry.to_json_line()


def test_ai_first_reviewed_entry_rejects_invalid_category():
    entry = AIFirstReviewedEntry(
        ocid="o",
        arm="diagnostic_claude",
        category=7,
        justification="j",
        coded_at="t",
        coder="c",
        review_action="agent-accepted",
        agent_category=1,
        agent_justification="j",
        agent_identity="a",
    )
    with pytest.raises(RubricSchemaError, match="Invalid category"):
        entry.to_json_line()


def test_ai_first_reviewed_entry_rejects_invalid_agent_category():
    entry = AIFirstReviewedEntry(
        ocid="o",
        arm="diagnostic_claude",
        category=1,
        justification="j",
        coded_at="t",
        coder="c",
        review_action="agent-accepted",
        agent_category=42,
        agent_justification="j",
        agent_identity="a",
    )
    with pytest.raises(RubricSchemaError, match="Invalid agent_category"):
        entry.to_json_line()


# ---------------------------------------------------------------------------
# End-to-end walk: accept / override / back / quit-save
# ---------------------------------------------------------------------------


def test_session_walks_three_records_with_accept_and_override_actions(tmp_path):
    """3 records walked: accept + override + accept → 3 rows with the
    matching review_action values + agent provenance fields populated.

    Every record is prompted — no auto-skip."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "agent quote 1"),
            ("ocid-EX-002", 2, "agent quote 2"),
            ("ocid-EX-003", 1, "agent quote 3"),
        ],
        coder="claude-opus-4-7-blind-agent",
    )

    # The override justification must be a literal substring of the
    # second bundle's reasoning text.
    bundle2_payload = json.loads(
        (FIXTURE_DIR / "ocid-EX-002.bundle.json").read_text(encoding="utf-8")
    )
    reasoning2 = bundle2_payload["agent"]["reasoning"]
    override_quote = reasoning2[:40].strip()

    stdin = io.StringIO(
        "a\n"                  # record 1: accept
        "o\n"                  # record 2: override
        "3\n"                  # override category
        f"{override_quote}\n"  # override justification
        "a\n"                  # record 3: accept
    )
    stdout = io.StringIO()

    rows_written = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
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
    assert [r["review_action"] for r in raw] == [
        "agent-accepted",
        "human-overridden",
        "agent-accepted",
    ]

    # Accepted row: category + justification come from agent, audit
    # fields preserve agent identity.
    assert raw[0]["category"] == 2
    assert raw[0]["justification"] == "agent quote 1"
    assert raw[0]["agent_category"] == 2
    assert raw[0]["agent_justification"] == "agent quote 1"
    assert raw[0]["agent_identity"] == "claude-opus-4-7-blind-agent"

    # Overridden row: category + justification are reviewer's; agent
    # fields preserve what the agent had said.
    assert raw[1]["category"] == 3
    assert raw[1]["justification"] == override_quote
    assert raw[1]["agent_category"] == 2
    assert raw[1]["agent_justification"] == "agent quote 2"
    assert raw[1]["agent_identity"] == "claude-opus-4-7-blind-agent"

    # Third accepted row.
    assert raw[2]["category"] == 1
    assert raw[2]["justification"] == "agent quote 3"
    assert raw[2]["agent_category"] == 1
    assert raw[2]["agent_identity"] == "claude-opus-4-7-blind-agent"

    # All rows carry the reviewer's identity in the coder field, NOT
    # the agent's.
    assert all(r["coder"] == "sam" for r in raw)

    # Display shows the rubric refresher, the verbatim default rule,
    # and the AI agent's call for every record.
    out_text = stdout.getvalue()
    assert "RUBRIC REFRESHER" in out_text
    assert RUBRIC_DEFAULT_RULE in out_text
    assert "AI AGENT'S CALL" in out_text
    assert "Record 1 of 3" in out_text
    assert "Record 2 of 3" in out_text
    assert "Record 3 of 3" in out_text


def test_session_quit_save_preserves_partial_progress(tmp_path):
    """'q' (quit-save) writes what's been reviewed so far + exits."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "agent1"),
            ("ocid-EX-002", 2, "agent2"),
            ("ocid-EX-003", 1, "agent3"),
        ],
    )

    stdin = io.StringIO("a\n" "q\n")  # accept first, then quit
    stdout = io.StringIO()

    rows_written = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )

    assert rows_written == 1
    raw = _read_output_raw(output)
    assert len(raw) == 1
    assert raw[0]["ocid"] == "ocid-EX-001"
    assert raw[0]["review_action"] == "agent-accepted"
    assert "Quit." in stdout.getvalue()


def test_back_action_rewinds_previous_record(tmp_path):
    """'b' (back) removes the previous record from the output and
    re-prompts for it."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
        ],
    )

    # Walk: accept first (typo), at record 2 go back, then override
    # record 1, then accept records 2 and 3.
    bundle1_payload = json.loads(
        (FIXTURE_DIR / "ocid-EX-001.bundle.json").read_text(encoding="utf-8")
    )
    override_quote = bundle1_payload["agent"]["reasoning"][:30].strip()

    stdin = io.StringIO(
        "a\n"                  # record 1: accept (typo)
        "b\n"                  # record 2: back -> rewind to 1
        "o\n"                  # record 1 re-do: override
        "3\n"
        f"{override_quote}\n"
        "a\n"                  # record 2: accept
        "a\n"                  # record 3: accept
    )
    stdout = io.StringIO()
    rows = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    raw = _read_output_raw(output)
    by_ocid = {r["ocid"]: r for r in raw}
    # ocid-EX-001 was rewound and re-coded as human-overridden.
    assert by_ocid["ocid-EX-001"]["review_action"] == "human-overridden"
    assert by_ocid["ocid-EX-001"]["category"] == 3
    # Records 2 and 3 accepted.
    assert by_ocid["ocid-EX-002"]["review_action"] == "agent-accepted"
    assert by_ocid["ocid-EX-003"]["review_action"] == "agent-accepted"


def test_back_on_first_record_reprompts(tmp_path):
    """'b' on the first record (no previous) re-prompts; doesn't crash."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
        ],
    )
    stdin = io.StringIO("b\n" "a\n" "a\n" "a\n")
    stdout = io.StringIO()
    rows = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    assert "No previous record to go back to" in stdout.getvalue()


# ---------------------------------------------------------------------------
# Resume semantics
# ---------------------------------------------------------------------------


def test_session_resume_skips_already_reviewed(tmp_path):
    """Second invocation: OCIDs already in the output sheet are
    skipped. Mirrors code_rubric.py + review_disagreements.py's resume
    idiom."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
        ],
    )

    # First session: accept first record, then quit.
    rows_first = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=io.StringIO("a\n" "q\n"),
        stdout=io.StringIO(),
    )
    assert rows_first == 1

    # Second session: should NOT re-prompt for ocid-EX-001; accepts the
    # remaining two.
    second_stdout = io.StringIO()
    rows_second = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=io.StringIO("a\n" "a\n"),
        stdout=second_stdout,
    )
    assert rows_second == 2
    raw = _read_output_raw(output)
    assert [r["ocid"] for r in raw] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    # Original action stuck around — resume doesn't overwrite.
    assert raw[0]["review_action"] == "agent-accepted"
    # Second session output reports the resume state.
    second_text = second_stdout.getvalue()
    assert "already reviewed      : 1" in second_text
    assert "to review this session: 2" in second_text


# ---------------------------------------------------------------------------
# Override justification must be a literal substring of reasoning
# ---------------------------------------------------------------------------


def test_override_justification_must_be_substring(tmp_path):
    """Override justification that isn't a substring of the reasoning
    text re-prompts."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    # Single-record diagnostic dir (only EX-001) — drop the other two
    # bundles so the agent sheet just covers the one we test against.
    for ocid in ("ocid-EX-002", "ocid-EX-003"):
        (diagnostic_dir / f"{ocid}.bundle.json").unlink()

    _write_agent_sheet(
        agent_sheet,
        [("ocid-EX-001", 2, "agent quote 1")],
    )

    bundle_payload = json.loads(
        (FIXTURE_DIR / "ocid-EX-001.bundle.json").read_text(encoding="utf-8")
    )
    valid_quote = bundle_payload["agent"]["reasoning"][:25].strip()

    stdin = io.StringIO(
        "o\n"                      # action: override
        "2\n"                      # category
        "totally-made-up-quote\n"  # not in reasoning -> reprompt
        "\n"                       # empty -> reprompt
        f"{valid_quote}\n"         # valid substring
    )
    stdout = io.StringIO()

    rows = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    out_text = stdout.getvalue()
    assert out_text.count("must be a literal substring") >= 1
    assert out_text.count("Justification cannot be empty") >= 1
    raw = _read_output_raw(output)
    assert raw[0]["justification"] == valid_quote
    assert raw[0]["review_action"] == "human-overridden"
    assert raw[0]["category"] == 2


# ---------------------------------------------------------------------------
# Invalid action re-prompts
# ---------------------------------------------------------------------------


def test_invalid_action_reprompts(tmp_path):
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    for ocid in ("ocid-EX-002", "ocid-EX-003"):
        (diagnostic_dir / f"{ocid}.bundle.json").unlink()
    _write_agent_sheet(agent_sheet, [("ocid-EX-001", 1, "a")])

    stdin = io.StringIO(
        "x\n"  # invalid
        "A\n"  # uppercase a — accepted (we .lower())
    )
    stdout = io.StringIO()
    rows = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    assert "Invalid action" in stdout.getvalue()


# ---------------------------------------------------------------------------
# Startup validation: agent sheet covers bundles 1:1
# ---------------------------------------------------------------------------


def test_session_stops_when_agent_sheet_missing_an_ocid(tmp_path):
    """Agent sheet missing a bundle OCID → STOP with a clear error
    BEFORE any prompting. Validates the AI-first protocol's coverage
    invariant: agent must have coded every record."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    # Agent has only 2 of 3 OCIDs.
    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
        ],
    )

    with pytest.raises(RubricSchemaError) as excinfo:
        run_review_session(
            agent_sheet_path=agent_sheet,
            diagnostic_dir=diagnostic_dir,
            inverted_spec_path=SPEC_PATH,
            output_path=output,
            arm="diagnostic_claude",
            coder="sam",
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
        )
    assert "ocid-EX-003" in str(excinfo.value)
    assert "diagnostic-dir but not in agent sheet" in str(excinfo.value)
    # Nothing should have been written to the output sheet.
    assert not output.exists()


def test_session_stops_when_agent_sheet_has_extra_ocid(tmp_path):
    """Agent sheet contains an OCID not in the diagnostic dir → STOP."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
            ("ocid-EX-999", 1, "a4"),  # not in diagnostic dir
        ],
    )

    with pytest.raises(RubricSchemaError) as excinfo:
        run_review_session(
            agent_sheet_path=agent_sheet,
            diagnostic_dir=diagnostic_dir,
            inverted_spec_path=SPEC_PATH,
            output_path=output,
            arm="diagnostic_claude",
            coder="sam",
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
        )
    assert "ocid-EX-999" in str(excinfo.value)
    assert "agent sheet but not in diagnostic-dir" in str(excinfo.value)


def test_session_stops_on_duplicate_agent_sheet_row(tmp_path):
    """Duplicate (ocid, arm) row in agent sheet → STOP."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-001", 3, "a1-dup"),  # duplicate
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
        ],
    )

    with pytest.raises(RubricSchemaError, match="duplicate row"):
        run_review_session(
            agent_sheet_path=agent_sheet,
            diagnostic_dir=diagnostic_dir,
            inverted_spec_path=SPEC_PATH,
            output_path=output,
            arm="diagnostic_claude",
            coder="sam",
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
        )


def test_session_ignores_agent_sheet_rows_for_other_arms(tmp_path):
    """Agent sheet may contain rows for diagnostic_primary too; the
    review walks only the arm under review. Cross-arm rows are quietly
    ignored, not flagged."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    # claude arm: covers the three bundles. primary arm: extra noise
    # that's ignored under --arm diagnostic_claude.
    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "a1"),
            ("ocid-EX-002", 2, "a2"),
            ("ocid-EX-003", 1, "a3"),
        ],
        arm="diagnostic_claude",
    )
    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 1, "primary-a1"),
            ("ocid-EX-777", 1, "primary-extra"),
        ],
        arm="diagnostic_primary",
    )

    stdin = io.StringIO("a\n" "a\n" "a\n")
    stdout = io.StringIO()
    rows = run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    raw = _read_output_raw(output)
    # Agent identity / agent category come from the claude arm rows.
    by_ocid = {r["ocid"]: r for r in raw}
    assert by_ocid["ocid-EX-001"]["agent_category"] == 2
    assert by_ocid["ocid-EX-001"]["agent_justification"] == "a1"


# ---------------------------------------------------------------------------
# Schema-superset claim: output loadable by score_rubric.read_sheet
# ---------------------------------------------------------------------------


def test_output_sheet_loadable_by_score_rubric_read_sheet(tmp_path):
    """The AI-first reviewed output sheet is a CodedEntry SUPERSET — it
    has all six locked CodedEntry fields plus the four audit fields. The
    schema-superset claim must hold so ``score_rubric.read_sheet`` (and
    therefore ``--compare-with`` for κ computation) loads the output
    unchanged.

    If this test fails, downstream κ tooling can't operate against
    AI-first reviewed sheets without modification — STOP and surface."""
    diagnostic_dir = _copy_bundles(tmp_path)
    agent_sheet = tmp_path / "agent.jsonl"
    output = tmp_path / "reviewed.jsonl"

    _write_agent_sheet(
        agent_sheet,
        [
            ("ocid-EX-001", 2, "agent quote 1"),
            ("ocid-EX-002", 2, "agent quote 2"),
            ("ocid-EX-003", 1, "agent quote 3"),
        ],
    )

    bundle2_payload = json.loads(
        (FIXTURE_DIR / "ocid-EX-002.bundle.json").read_text(encoding="utf-8")
    )
    override_quote = bundle2_payload["agent"]["reasoning"][:30].strip()

    stdin = io.StringIO(
        "a\n"
        "o\n"
        "3\n"
        f"{override_quote}\n"
        "a\n"
    )
    run_review_session(
        agent_sheet_path=agent_sheet,
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        output_path=output,
        arm="diagnostic_claude",
        coder="sam",
        stdin=stdin,
        stdout=io.StringIO(),
    )

    # The crucial assertion: read_sheet (CodedEntry-only) loads the
    # output sheet without error.
    coded_entries = read_sheet(output)
    assert len(coded_entries) == 3

    # All entries have the six locked fields populated.
    for entry in coded_entries:
        assert entry.arm == "diagnostic_claude"
        assert entry.coder == "sam"
        assert entry.category in {1, 2, 3}
        assert entry.justification != ""
        assert entry.coded_at.endswith("Z")
        assert entry.ocid.startswith("ocid-EX-")

    # The accepted row's category matches the agent's; the overridden
    # row's category is the reviewer's (3, not the agent's 2).
    by_ocid = {e.ocid: e for e in coded_entries}
    assert by_ocid["ocid-EX-001"].category == 2  # agent-accepted
    assert by_ocid["ocid-EX-002"].category == 3  # human-overridden
    assert by_ocid["ocid-EX-003"].category == 1  # agent-accepted
