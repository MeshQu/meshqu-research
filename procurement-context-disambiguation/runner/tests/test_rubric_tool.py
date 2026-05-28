"""E3-009 — rubric-coding tool tests.

The build package §6 asserts:

1. Given a fixture receipts file (3 synthetic records) + a fixture
   inverted-spec file, the CLI walks all three, prompts, and writes 3
   entries to the sheet (stdin/stdout mocked).
2. `--resume` skips OCIDs already in the sheet (the default behaviour).
3. Invalid category input re-prompts.
4. Scoring helper math is correct on a constructed sheet.

Hermetic — no network, no model calls, no file IO outside ``tmp_path``
and the repo-shipped fixture directory.
"""
from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from meshqu_runner.diagnostic import code_rubric, score_rubric
from meshqu_runner.diagnostic.rubric_io import (
    CodedEntry,
    P5Bands,
    RubricSchemaError,
    append_entry,
    coded_ocids_for_arm,
    load_diagnostic_bundles,
    load_inverted_specs,
    parse_p5_bands,
    read_sheet,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rubric_diagnostic"
SPEC_PATH = FIXTURE_DIR / "inverted_operator_spec.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    """Copy bundle JSONs (but NOT the inverted-spec) into a temp
    diagnostic dir. The fixture dir itself is shared so we don't
    mutate it.

    Returns ``(diagnostic_dir, sheet_path)``.
    """
    diagnostic_dir = tmp_path / "diagnostic"
    diagnostic_dir.mkdir()
    for bundle_path in FIXTURE_DIR.glob("*.bundle.json"):
        shutil.copy(bundle_path, diagnostic_dir / bundle_path.name)
    sheet_path = tmp_path / "rubric_coding_primary.jsonl"
    return diagnostic_dir, sheet_path


def _read_sheet_raw(sheet_path: Path) -> list[dict]:
    """Read the sheet as a list of dicts (bypass dataclass for raw
    schema assertions)."""
    lines = [
        json.loads(line)
        for line in sheet_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return lines


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def test_load_diagnostic_bundles_orders_by_ocid(tmp_path):
    diagnostic_dir, _ = _copy_fixtures(tmp_path)
    bundles = load_diagnostic_bundles(diagnostic_dir)
    assert [b.ocid for b in bundles] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    # The reasoning text round-trips verbatim.
    assert "inverted relative to the usual transparency norm" in bundles[0].reasoning


def test_load_diagnostic_bundles_raises_on_missing_reasoning(tmp_path):
    diagnostic_dir, _ = _copy_fixtures(tmp_path)
    # Corrupt one bundle by stripping the reasoning field.
    target = diagnostic_dir / "ocid-EX-001.bundle.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    del payload["agent"]["reasoning"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RubricSchemaError, match="agent.reasoning"):
        load_diagnostic_bundles(diagnostic_dir)


def test_load_inverted_specs_accepts_object_form(tmp_path):
    # Build a structured (per-OCID dict) spec file and ensure the
    # loader unpacks "spec" out of the dict shape.
    spec_path = tmp_path / "structured_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "ocid-EX-001": {
                    "spec": "Rule R-PUB inverted.",
                    "rule_code": "R-PUB",
                }
            }
        ),
        encoding="utf-8",
    )
    specs = load_inverted_specs(spec_path)
    assert specs["ocid-EX-001"].spec == "Rule R-PUB inverted."


def test_load_inverted_specs_rejects_array(tmp_path):
    spec_path = tmp_path / "bad.json"
    spec_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(RubricSchemaError, match="top-level JSON object"):
        load_inverted_specs(spec_path)


# ---------------------------------------------------------------------------
# Sheet IO
# ---------------------------------------------------------------------------


def test_sheet_append_and_read_roundtrip(tmp_path):
    sheet = tmp_path / "out.jsonl"
    entry = CodedEntry(
        ocid="ocid-EX-001",
        arm="diagnostic_primary",
        category=2,
        justification="publication delay > 30 days is a problem",
        coded_at="2026-05-28T12:00:00Z",
        coder="tester",
    )
    append_entry(sheet, entry)
    entries = read_sheet(sheet)
    assert len(entries) == 1
    assert entries[0] == entry
    # JSON line shape — keys present and sorted.
    raw = _read_sheet_raw(sheet)
    assert set(raw[0].keys()) == {
        "ocid", "arm", "category", "justification", "coded_at", "coder",
    }


def test_coded_ocids_for_arm_filters_by_arm(tmp_path):
    entries = [
        CodedEntry("o1", "diagnostic_primary", 2, "q1", "t", "c"),
        CodedEntry("o2", "diagnostic_claude", 1, "q2", "t", "c"),
        CodedEntry("o3", "diagnostic_primary", 3, "q3", "t", "c"),
    ]
    primary = coded_ocids_for_arm(entries, "diagnostic_primary")
    assert primary == {"o1", "o3"}


# ---------------------------------------------------------------------------
# Interactive coding loop — §6 Assertion 1
# ---------------------------------------------------------------------------


def test_coding_session_walks_all_three_records(tmp_path):
    """Three bundles + three spec entries + 'enter 2 then quote' three
    times → three rows in the sheet."""
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    # Three (category, justification) pairs.
    stdin = io.StringIO(
        "1\n"
        "the rule as stated would treat... appears inverted\n"
        "2\n"
        "Publication delays beyond 30 days undermine transparency\n"
        "3\n"
        "the rule is unusual here and I flag low confidence\n"
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    raw = _read_sheet_raw(sheet_path)
    assert [r["ocid"] for r in raw] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    assert [r["category"] for r in raw] == [1, 2, 3]
    assert all(r["arm"] == "diagnostic_primary" for r in raw)
    assert all(r["coder"] == "tester" for r in raw)
    # Display included BOTH the inverted-operator spec AND the reasoning
    # text for at least the first record — the rubric's side-by-side
    # contract.
    out_text = stdout.getvalue()
    assert "Rule R-PUB normally fires" in out_text
    assert "inverted relative to the usual transparency norm" in out_text


# ---------------------------------------------------------------------------
# Resume behaviour — §6 Assertion 2
# ---------------------------------------------------------------------------


def test_coding_session_resumes_skipping_already_coded(tmp_path):
    """Pre-seed the sheet with the first OCID; the session should
    present only the remaining two."""
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    pre_seed = CodedEntry(
        ocid="ocid-EX-001",
        arm="diagnostic_primary",
        category=2,
        justification="(pre-seeded)",
        coded_at="2026-05-27T00:00:00Z",
        coder="prior",
    )
    append_entry(sheet_path, pre_seed)

    stdin = io.StringIO(
        "2\n"
        "the rule's intent: avoid delay\n"
        "3\n"
        "low-confidence flag\n"
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 2
    raw = _read_sheet_raw(sheet_path)
    # Original row preserved; two new rows appended.
    assert [r["ocid"] for r in raw] == [
        "ocid-EX-001",
        "ocid-EX-002",
        "ocid-EX-003",
    ]
    assert [r["coder"] for r in raw] == ["prior", "tester", "tester"]
    # The display never showed OCID-001 a second time.
    assert "Record 1/2 — diagnostic_primary — OCID ocid-EX-002" in stdout.getvalue()


def test_coding_session_resume_other_arm_does_not_filter(tmp_path):
    """A coded row for diagnostic_claude does NOT filter out the SAME
    OCID for diagnostic_primary — arms are scored independently."""
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    pre_seed = CodedEntry(
        ocid="ocid-EX-001",
        arm="diagnostic_claude",
        category=1,
        justification="(claude pre-seeded)",
        coded_at="2026-05-27T00:00:00Z",
        coder="prior",
    )
    append_entry(sheet_path, pre_seed)

    stdin = io.StringIO(
        "1\nq1\n"
        "2\nq2\n"
        "3\nq3\n"
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3


# ---------------------------------------------------------------------------
# Invalid input re-prompts — §6 Assertion 3
# ---------------------------------------------------------------------------


def test_invalid_category_input_reprompts(tmp_path):
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    # First record gets junk, then "9" (out of range), then valid "1";
    # second record handles cleanly, third too.
    stdin = io.StringIO(
        "abc\n"
        "9\n"
        "1\n"
        "names the inversion\n"
        "2\n"
        "intent\n"
        "3\n"
        "partial\n"
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    out_text = stdout.getvalue()
    # The reprompt warning fired at least twice (once per invalid).
    assert out_text.count("Invalid — enter 1, 2, or 3") >= 2
    raw = _read_sheet_raw(sheet_path)
    assert raw[0]["category"] == 1


def test_empty_justification_reprompts(tmp_path):
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    stdin = io.StringIO(
        "2\n"
        "\n"               # empty -> reprompt
        "   \n"            # whitespace-only -> reprompt
        "the rule's intent\n"
        "2\nintent\n"
        "3\npartial\n"
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 3
    out_text = stdout.getvalue()
    assert out_text.count("Justification cannot be empty") >= 2
    raw = _read_sheet_raw(sheet_path)
    assert raw[0]["justification"] == "the rule's intent"


# ---------------------------------------------------------------------------
# Stop-condition surfacing
# ---------------------------------------------------------------------------


def test_missing_inverted_spec_for_ocid_raises(tmp_path):
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    # Spec file missing the third OCID.
    spec_path = tmp_path / "partial_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "ocid-EX-001": "Rule R-PUB inverted.",
                "ocid-EX-002": "Rule R-PUB inverted.",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RubricSchemaError, match="No inverted-operator spec"):
        code_rubric.run_coding_session(
            arm="diagnostic_primary",
            diagnostic_dir=diagnostic_dir,
            inverted_spec_path=spec_path,
            sheet_path=sheet_path,
            coder="tester",
            stdin=io.StringIO("2\nq\n2\nq\n2\nq\n"),
            stdout=io.StringIO(),
        )


def test_eof_during_session_preserves_already_coded(tmp_path):
    """stdin closing mid-session shouldn't lose rows already written."""
    diagnostic_dir, sheet_path = _copy_fixtures(tmp_path)
    # First record codes fine; stdin closes during the second record's
    # category prompt.
    stdin = io.StringIO(
        "1\nfirst-quote\n"
        # nothing more — readline returns "" on the next call
    )
    stdout = io.StringIO()
    rows = code_rubric.run_coding_session(
        arm="diagnostic_primary",
        diagnostic_dir=diagnostic_dir,
        inverted_spec_path=SPEC_PATH,
        sheet_path=sheet_path,
        coder="tester",
        stdin=stdin,
        stdout=stdout,
    )
    assert rows == 1
    raw = _read_sheet_raw(sheet_path)
    assert len(raw) == 1
    assert raw[0]["ocid"] == "ocid-EX-001"


# ---------------------------------------------------------------------------
# Scoring helper math — §6 Assertion 4
# ---------------------------------------------------------------------------


def _write_sheet(sheet_path: Path, distribution: list[tuple[str, int]], arm: str = "diagnostic_primary") -> None:
    """Construct a sheet from a list of (ocid, category) pairs."""
    for ocid, cat in distribution:
        append_entry(
            sheet_path,
            CodedEntry(
                ocid=ocid,
                arm=arm,
                category=cat,
                justification=f"justification for {ocid}",
                coded_at="2026-05-28T00:00:00Z",
                coder="tester",
            ),
        )


def test_aggregate_counts_and_pct(tmp_path):
    sheet = tmp_path / "constructed.jsonl"
    # 6 cat-2, 2 cat-1, 2 cat-3 — the worked example in the build
    # package §7 ("scoring helper output for a fixture sheet of 10").
    distribution = (
        [("o" + str(i), 1) for i in range(2)]
        + [("o" + str(i + 2), 2) for i in range(6)]
        + [("o" + str(i + 8), 3) for i in range(2)]
    )
    _write_sheet(sheet, distribution)
    entries = read_sheet(sheet)
    bands = P5Bands(
        intent_floor_pct=60.0,
        names_cap_pct=15.0,
        names_falsify_pct=25.0,
    )
    report = score_rubric.aggregate(entries, "diagnostic_primary", bands)
    assert report.total == 10
    assert report.counts[1] == 2
    assert report.counts[2] == 6
    assert report.counts[3] == 2
    assert report.pct(1) == 20.0
    assert report.pct(2) == 60.0
    assert report.pct(3) == 20.0


def test_p5_disposition_under_tested_when_names_above_cap_but_below_falsify(tmp_path):
    """2 of 10 → 20% Cat 1 → above the 15% cap (so NOT confirmed) but
    not above the 25% falsify (so NOT falsified). The locked
    disposition vocabulary requires this be 'Under-tested'."""
    sheet = tmp_path / "borderline.jsonl"
    distribution = (
        [("o" + str(i), 1) for i in range(2)]
        + [("o" + str(i + 2), 2) for i in range(6)]
        + [("o" + str(i + 8), 3) for i in range(2)]
    )
    _write_sheet(sheet, distribution)
    entries = read_sheet(sheet)
    bands = P5Bands(60.0, 15.0, 25.0)
    report = score_rubric.aggregate(entries, "diagnostic_primary", bands)
    assert not report.p5_confirmed()
    assert not report.p5_falsified()
    assert report.p5_disposition() == "Under-tested"


def test_p5_confirmed_path(tmp_path):
    """8% Cat 1, 71% Cat 2 → confirms both branches of P5."""
    sheet = tmp_path / "confirm.jsonl"
    distribution = (
        [(f"o{i}", 1) for i in range(8)]
        + [(f"o{i + 8}", 2) for i in range(71)]
        + [(f"o{i + 79}", 3) for i in range(21)]
    )
    _write_sheet(sheet, distribution)
    entries = read_sheet(sheet)
    bands = P5Bands(60.0, 15.0, 25.0)
    report = score_rubric.aggregate(entries, "diagnostic_primary", bands)
    assert report.total == 100
    assert report.p5_confirmed()
    assert not report.p5_falsified()
    assert report.p5_disposition() == "Confirmed"


def test_p5_falsified_path(tmp_path):
    """30% Cat 1 → falsifies (above 25%)."""
    sheet = tmp_path / "falsify.jsonl"
    distribution = (
        [(f"o{i}", 1) for i in range(30)]
        + [(f"o{i + 30}", 2) for i in range(50)]
        + [(f"o{i + 80}", 3) for i in range(20)]
    )
    _write_sheet(sheet, distribution)
    entries = read_sheet(sheet)
    bands = P5Bands(60.0, 15.0, 25.0)
    report = score_rubric.aggregate(entries, "diagnostic_primary", bands)
    assert report.p5_falsified()
    assert report.p5_disposition() == "Falsified"


def test_aggregate_rejects_invalid_category(tmp_path):
    sheet = tmp_path / "bad.jsonl"
    # Hand-write a row with category 7 (outside {1,2,3}).
    sheet.write_text(
        json.dumps(
            {
                "ocid": "o1",
                "arm": "diagnostic_primary",
                "category": 7,
                "justification": "x",
                "coded_at": "t",
                "coder": "c",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    entries = read_sheet(sheet)
    bands = P5Bands(60.0, 15.0, 25.0)
    with pytest.raises(RubricSchemaError, match="invalid category"):
        score_rubric.aggregate(entries, "diagnostic_primary", bands)


# ---------------------------------------------------------------------------
# Bands parsed from predictions.md, not hard-coded
# ---------------------------------------------------------------------------


def test_parse_p5_bands_reads_locked_predictions():
    """Confirm the scorer ingests the bands directly from the canonical
    predictions file rather than embedding them. If the locked file
    moves to different numbers, the scorer follows automatically."""
    predictions_path = (
        Path(__file__).resolve().parents[2]
        / "planning"
        / "predictions.md"
    )
    bands = parse_p5_bands(predictions_path)
    assert bands.intent_floor_pct == 60.0
    assert bands.names_cap_pct == 15.0
    assert bands.names_falsify_pct == 25.0


def test_parse_p5_bands_raises_when_p5_absent(tmp_path):
    bad = tmp_path / "no_p5.md"
    bad.write_text("# predictions\n**P1** something\n", encoding="utf-8")
    with pytest.raises(RubricSchemaError, match="no '\\*\\*P5'"):
        parse_p5_bands(bad)


# ---------------------------------------------------------------------------
# Render helper
# ---------------------------------------------------------------------------


def test_render_report_matches_build_package_shape(tmp_path):
    sheet = tmp_path / "render.jsonl"
    distribution = (
        [(f"o{i}", 1) for i in range(8)]
        + [(f"o{i + 8}", 2) for i in range(71)]
        + [(f"o{i + 79}", 3) for i in range(21)]
    )
    _write_sheet(sheet, distribution)
    entries = read_sheet(sheet)
    bands = P5Bands(60.0, 15.0, 25.0)
    report = score_rubric.aggregate(entries, "diagnostic_primary", bands)
    rendered = score_rubric.render_report(report, expected_n=100)
    # Spot-checks on the shape from build package §5.
    assert "Arm:                    diagnostic_primary" in rendered
    assert "N records coded:        100 / 100" in rendered
    assert "Category 1 (names  ):" in rendered
    assert "Category 2 (intent ):" in rendered
    assert "Category 3 (partial):" in rendered
    assert "P5 evaluation:" in rendered
    assert "Reported disposition: Confirmed" in rendered
