"""Reconciliation tool for rubric-coding disagreements between two coders.

This is a RECONCILIATION tool, NOT blind re-coding. The human reviewer
sees both their first-pass call AND the second-coder's call at each
disagreement record, alongside the rubric's default rule. The output
sheet is the human reviewer's final adjudication; the per-record
``reconciliation_action`` field captures whether each call was a kept
agreement, kept first-pass, adopted second-coder, or human override.

## Methods-section description (verbatim from Sam, 2026-05-30)

    "First pass: human coder coded blind. Second pass: AI second-coder
    coded blind. κ check surfaced systematic disagreement at the
    missing-evidence/rule-itself boundary. Reconciliation: human coder
    re-examined the 79 disagreement records with both calls visible
    alongside the rubric's default rule, applied the rule explicitly,
    and produced the final coding sheet."

The writeup methods section should lift this paragraph verbatim. Don't
describe the reconciled sheet as "blind re-coded" — that would mis-
characterise the protocol.

## What the script does

1. Loads the first-pass and second-coder sheets.
2. For every OCID that BOTH sheets coded (intersection on (ocid, arm)):
   - If the two coders AGREE on category, the row is copied verbatim
     from the first-pass with ``coder`` rewritten to the reconciliation
     identity and ``reconciliation_action = "agreement-kept"``. These
     records are NOT shown to the reviewer; the agreement IS the
     reconciliation outcome.
   - If they DISAGREE, the reviewer is presented with both calls plus
     the LLM reasoning, the inverted-operator spec entry, and the
     rubric's one-line per-category refresher plus the verbatim default
     rule about missing-evidence vs rule-itself hedges. The reviewer
     picks: keep first-pass, adopt second-coder, override (new
     category + new justification quote), back, or quit-save.
3. The output sheet is the reconciled coding sheet — the same JSONL
   schema as the rest of the rubric tooling, plus three audit fields:
   ``reconciliation_action``, ``first_pass_category``,
   ``second_coder_category``.

OCIDs present in only ONE sheet are reported to stderr at start-up but
NOT written to the output sheet — the human reviewer should re-run the
first-pass tool or the second-coder pipeline to cover any gaps before
reconciling.

## Audit-trail fields

Every row in the output sheet carries the three reconciliation fields
so the analysis-markdown follow-up can break down "where did the final
calls come from":

- ``reconciliation_action``: one of
    * ``"agreement-kept"``        — both coders agreed; no human review
    * ``"first-pass-kept"``       — disagreement; reviewer kept first-pass
    * ``"second-coder-adopted"``  — disagreement; reviewer adopted second-coder
    * ``"override"``              — disagreement; reviewer wrote a new call
- ``first_pass_category``:   the integer category from the first-pass sheet
- ``second_coder_category``: the integer category from the second-coder sheet

## Offline by design

NO model calls. NO API calls. NO MeshQu interactions. The reconciler
surfaces locked content + two existing coding sheets to a human; it
does not generate, paraphrase, or rewrite anything other than the
``coder`` and ``coded_at`` fields on the agreement-kept rows.

## Usage

    python -m meshqu_runner.diagnostic.review_disagreements \\
        --first-pass results/rubric_coding_primary_first_pass.jsonl \\
        --second-coder results/rubric_coding_primary_blind_agent.jsonl \\
        --diagnostic-dir results/runs/<run_id>/diagnostic_primary \\
        --inverted-spec results/runs/<run_id>/inverted_operator_spec.json \\
        --output results/rubric_coding_primary.jsonl \\
        [--arm diagnostic_primary]   # default: diagnostic_primary
        [--rubric-doc <path>]        # defaults to planning/diagnostic_rubric.md
        [--coder <name>]             # defaults to "$USER-reconciled"
        [--resume]                   # implicit by default

Resume is implicit: on a second invocation, OCIDs already in the
output sheet are skipped. Ctrl-C / EOF preserves on-disk progress
(same idiom as ``code_rubric.py``).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import IO, Iterable

from .rubric_io import (
    CATEGORY_LABELS,
    CodedEntry,
    DiagnosticBundle,
    InvertedSpec,
    RubricSchemaError,
    VALID_ARMS,
    VALID_CATEGORIES,
    load_diagnostic_bundles,
    load_inverted_specs,
    read_sheet,
)


# ---------------------------------------------------------------------------
# Rubric one-line refresher + verbatim default rule
# ---------------------------------------------------------------------------
#
# These strings are PARAPHRASES for quick reviewer recall — the
# source-of-truth is ``planning/diagnostic_rubric.md``. The default
# rule sentence, on the other hand, is QUOTED VERBATIM from the locked
# rubric. If the rubric is ever edited, ``test_rubric_default_rule_
# matches_rubric_doc`` will fail loud.

CATEGORY_REFRESHER: dict[int, str] = {
    1: (
        "Cat 1 (names the inversion): reasoning explicitly registers that "
        "the rule is inverted / contradictory / backwards."
    ),
    2: (
        "Cat 2 (reasons solely against intent): reasoning argues against the "
        "rule's semantic intent and never engages the literal inverted operator."
    ),
    3: (
        "Cat 3 (partial): reasoning hedges or notes the rule is unusual but "
        "does not clearly name the inversion."
    ),
}

# Verbatim default-rule sentence from
# planning/diagnostic_rubric.md §"Coding procedure" §2. Quoting it here
# keeps the reviewer's eyes on the locked content; the test suite
# enforces equality with the rubric doc so this string can't drift.
RUBRIC_DEFAULT_RULE: str = (
    "default to 3 only if there is an explicit hedge about the rule itself "
    "(not merely about missing evidence — missing-evidence hedging is the "
    "normal nudge behaviour and is not inversion-recognition)"
)


# ---------------------------------------------------------------------------
# Audit fields + reconciled entry wrapper
# ---------------------------------------------------------------------------
#
# The brief is explicit: DO NOT modify the CodedEntry dataclass. The
# new audit fields live on a wrapper that composes CodedEntry plus the
# three reconciliation audit fields. Downstream code can either read
# the raw JSONL (the three fields are top-level keys alongside the
# original six) or use the helper read_reconciled_sheet() below if it
# wants the typed view.

# Locked vocabulary for reconciliation_action. Anchored as a constant
# so the analysis-markdown follow-up can import it for the same vocab.
RECONCILIATION_ACTIONS: frozenset[str] = frozenset(
    {
        "agreement-kept",
        "first-pass-kept",
        "second-coder-adopted",
        "override",
    }
)


@dataclass(frozen=True)
class ReconciledEntry:
    """One row in the reconciled coding sheet.

    Wraps CodedEntry's six locked fields and adds three audit fields.
    The on-disk shape is a single flat JSON object — the three extra
    keys appear at top level alongside the original six so the file
    stays readable as one JSONL row per record.
    """

    # CodedEntry fields (same names, same semantics).
    ocid: str
    arm: str
    category: int
    justification: str
    coded_at: str
    coder: str

    # Reconciliation audit fields.
    reconciliation_action: str
    first_pass_category: int
    second_coder_category: int

    def to_json_line(self) -> str:
        if self.reconciliation_action not in RECONCILIATION_ACTIONS:
            raise RubricSchemaError(
                f"Invalid reconciliation_action {self.reconciliation_action!r}; "
                f"expected one of {sorted(RECONCILIATION_ACTIONS)}."
            )
        if self.category not in VALID_CATEGORIES:
            raise RubricSchemaError(
                f"Invalid category {self.category!r}; expected one of "
                f"{sorted(VALID_CATEGORIES)}."
            )
        return json.dumps(asdict(self), sort_keys=True)


def append_reconciled_entry(sheet_path: Path, entry: ReconciledEntry) -> None:
    """Append-only write; creates the parent dir if needed.

    Mirrors ``rubric_io.append_entry`` — the reconciled sheet is the
    sibling artefact of the per-arm coding sheets and inherits the
    same append-only contract."""
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    with sheet_path.open("a", encoding="utf-8") as f:
        f.write(entry.to_json_line() + "\n")


def read_reconciled_sheet(sheet_path: Path) -> list[ReconciledEntry]:
    """Read a reconciled coding sheet into typed rows. Returns ``[]``
    for a missing file (cold start)."""
    if not sheet_path.exists():
        return []
    out: list[ReconciledEntry] = []
    with sheet_path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RubricSchemaError(
                    f"Reconciled sheet {sheet_path}:{lineno} is not valid JSON: "
                    f"{exc}"
                )
            try:
                out.append(
                    ReconciledEntry(
                        ocid=str(raw["ocid"]),
                        arm=str(raw["arm"]),
                        category=int(raw["category"]),
                        justification=str(raw["justification"]),
                        coded_at=str(raw["coded_at"]),
                        coder=str(raw["coder"]),
                        reconciliation_action=str(raw["reconciliation_action"]),
                        first_pass_category=int(raw["first_pass_category"]),
                        second_coder_category=int(raw["second_coder_category"]),
                    )
                )
            except KeyError as exc:
                raise RubricSchemaError(
                    f"Reconciled sheet {sheet_path}:{lineno} missing required "
                    f"key: {exc}"
                )
    return out


# ---------------------------------------------------------------------------
# Time helper (mirrors code_rubric._utc_now_iso for byte-stable timestamps)
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with Z suffix — matches the bundle
    timestamp convention from ``multi_pass._utc_now_iso``."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


# ---------------------------------------------------------------------------
# Prompts (constants so tests can assert on them)
# ---------------------------------------------------------------------------


ACTION_PROMPT = (
    "Action? [k=keep first-pass / s=second-coder / o=override "
    "/ b=back / q=quit-save]: "
)
OVERRIDE_CATEGORY_PROMPT = (
    "Override category? [1=names inversion / 2=reasons against intent / "
    "3=partial]: "
)
OVERRIDE_JUSTIFICATION_PROMPT = (
    "Override justification (must be a literal substring of the reasoning "
    "text above): "
)
ACTION_REPROMPT = "  ⚠  Invalid action — enter k, s, o, b, or q.\n"
OVERRIDE_CATEGORY_REPROMPT = "  ⚠  Invalid — enter 1, 2, or 3.\n"
OVERRIDE_JUSTIFICATION_NOT_SUBSTRING = (
    "  ⚠  Justification must be a literal substring of the reasoning text. "
    "Try copy-paste.\n"
)
OVERRIDE_JUSTIFICATION_EMPTY = (
    "  ⚠  Justification cannot be empty.\n"
)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def _render_disagreement(
    *,
    idx: int,
    total: int,
    bundle: DiagnosticBundle,
    spec: InvertedSpec,
    first_pass: CodedEntry,
    second_coder: CodedEntry,
    arm: str,
) -> str:
    """Format the side-by-side reconciliation display block for one
    disagreement record.

    Mirrors ``code_rubric._render_record_header``'s plain-text shape
    (no ANSI) so the CLI is paste-friendly into a reconciliation log."""
    bar = "═" * 78
    thin = "─" * 78
    short_ocid = bundle.ocid[-12:] if len(bundle.ocid) > 12 else bundle.ocid
    lines = [
        "",
        bar,
        f"Disagreement {idx} of {total} — {arm} — OCID …{short_ocid}",
        f"  (full OCID: {bundle.ocid})",
        bar,
        "INVERTED-OPERATOR SPEC",
        _indent(spec.spec, "  "),
        "",
        "REASONING TEXT",
        _indent(bundle.reasoning, "  "),
        thin,
        "RUBRIC REFRESHER",
        _indent(CATEGORY_REFRESHER[1], "  "),
        _indent(CATEGORY_REFRESHER[2], "  "),
        _indent(CATEGORY_REFRESHER[3], "  "),
        "",
        "  DEFAULT RULE (verbatim from diagnostic_rubric.md):",
        _indent(RUBRIC_DEFAULT_RULE, "    "),
        thin,
        "TWO CODER CALLS",
        f"  [k] First-pass     : category {first_pass.category} "
        f"({CATEGORY_LABELS[first_pass.category]})",
        f"      justification  : {first_pass.justification}",
        f"      coder          : {first_pass.coder}",
        f"  [s] Second-coder   : category {second_coder.category} "
        f"({CATEGORY_LABELS[second_coder.category]})",
        f"      justification  : {second_coder.justification}",
        f"      coder          : {second_coder.coder}",
        bar,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def _prompt_action(
    *,
    stdin: IO[str],
    stdout: IO[str],
    has_previous: bool,
) -> str:
    """Prompt for the reviewer's action. Returns one of:
    'k', 's', 'o', 'b', 'q'. Raises EOFError on closed stdin.

    ``has_previous`` controls whether 'b' (back) is accepted — if there
    is no previously-reconciled record in this session, 'b' is treated
    as invalid (re-prompt). This avoids confusing fallthrough on the
    first record."""
    while True:
        stdout.write(ACTION_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before action was provided")
        raw = line.strip().lower()
        if raw in {"k", "s", "o", "q"}:
            return raw
        if raw == "b":
            if has_previous:
                return raw
            stdout.write(
                "  ⚠  No previous record to go back to.\n"
            )
            stdout.flush()
            continue
        stdout.write(ACTION_REPROMPT)
        stdout.flush()


def _prompt_override(
    *,
    stdin: IO[str],
    stdout: IO[str],
    reasoning_text: str,
) -> tuple[int, str]:
    """Prompt for the override (category + justification).

    The justification must be a literal substring of the reasoning
    text — the rubric requires a one-line quote, and on override the
    integrity check is even more important because the reviewer is
    not picking from either coder's existing justification."""
    while True:
        stdout.write(OVERRIDE_CATEGORY_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before override category was provided")
        raw = line.strip()
        if raw.isdigit() and int(raw) in VALID_CATEGORIES:
            cat = int(raw)
            break
        stdout.write(OVERRIDE_CATEGORY_REPROMPT)
        stdout.flush()

    while True:
        stdout.write(OVERRIDE_JUSTIFICATION_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before override justification was provided")
        text = line.strip()
        if not text:
            stdout.write(OVERRIDE_JUSTIFICATION_EMPTY)
            stdout.flush()
            continue
        if text not in reasoning_text:
            stdout.write(OVERRIDE_JUSTIFICATION_NOT_SUBSTRING)
            stdout.flush()
            continue
        return cat, text


# ---------------------------------------------------------------------------
# Pairing logic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pair:
    """Internal pairing of (ocid -> first_pass, second_coder).

    Carries pre-computed agreement so the main loop doesn't recompute
    on every iteration."""

    ocid: str
    first_pass: CodedEntry
    second_coder: CodedEntry

    @property
    def agreed(self) -> bool:
        return self.first_pass.category == self.second_coder.category


def _pair_sheets(
    first_pass: list[CodedEntry],
    second_coder: list[CodedEntry],
    arm: str,
) -> tuple[list[_Pair], list[str], list[str]]:
    """Build the pairing list for one arm + report unmatched OCIDs.

    Returns ``(pairs, first_pass_only_ocids, second_coder_only_ocids)``.
    Pairs are in sorted-OCID order so the reconciliation walk is
    deterministic. Duplicate (ocid, arm) rows in either input sheet
    raise — same invariant the ``compare_sheets`` helper enforces."""
    def _index(entries: list[CodedEntry], label: str) -> dict[str, CodedEntry]:
        out: dict[str, CodedEntry] = {}
        for e in entries:
            if e.arm != arm:
                continue
            if e.ocid in out:
                raise RubricSchemaError(
                    f"{label} sheet contains duplicate row for OCID "
                    f"{e.ocid!r} on arm {arm!r}; reconciliation requires "
                    "an unambiguous sheet."
                )
            out[e.ocid] = e
        return out

    fp_idx = _index(first_pass, "first-pass")
    sc_idx = _index(second_coder, "second-coder")
    fp_ocids = set(fp_idx.keys())
    sc_ocids = set(sc_idx.keys())

    shared = sorted(fp_ocids & sc_ocids)
    pairs = [_Pair(ocid=o, first_pass=fp_idx[o], second_coder=sc_idx[o]) for o in shared]
    fp_only = sorted(fp_ocids - sc_ocids)
    sc_only = sorted(sc_ocids - fp_ocids)
    return pairs, fp_only, sc_only


# ---------------------------------------------------------------------------
# Main reconciliation loop
# ---------------------------------------------------------------------------


def run_reconciliation_session(
    *,
    first_pass_path: Path,
    second_coder_path: Path,
    diagnostic_dir: Path,
    inverted_spec_path: Path,
    output_path: Path,
    arm: str,
    coder: str,
    stdin: IO[str],
    stdout: IO[str],
) -> int:
    """Drive the reconciliation end-to-end. Returns the number of rows
    written to the output sheet in this session (agreement-kept rows
    are counted).

    Pure function over its IO arguments — no module-level state.
    Resume is implicit: OCIDs already in ``output_path`` are skipped."""
    if arm not in VALID_ARMS:
        raise SystemExit(
            f"--arm must be one of {sorted(VALID_ARMS)}; got {arm!r}"
        )

    first_pass = read_sheet(first_pass_path)
    second_coder = read_sheet(second_coder_path)
    bundles = load_diagnostic_bundles(diagnostic_dir)
    specs = load_inverted_specs(inverted_spec_path)

    pairs, fp_only, sc_only = _pair_sheets(first_pass, second_coder, arm)

    # Resume: skip OCIDs already in the output sheet (for this arm).
    existing = read_reconciled_sheet(output_path)
    already = {e.ocid for e in existing if e.arm == arm}

    pairs_to_process = [p for p in pairs if p.ocid not in already]

    bundles_by_ocid = {b.ocid: b for b in bundles}

    # Pre-check: every disagreement OCID must have a bundle + spec.
    for pair in pairs_to_process:
        if pair.agreed:
            continue
        if pair.ocid not in bundles_by_ocid:
            raise RubricSchemaError(
                f"No diagnostic bundle for disagreement OCID {pair.ocid!r}; "
                f"the reconciliation tool requires the reasoning text "
                f"for the side-by-side display. Check --diagnostic-dir."
            )
        if pair.ocid not in specs:
            raise RubricSchemaError(
                f"No inverted-operator spec for disagreement OCID "
                f"{pair.ocid!r}; the rubric requires the spec for the "
                f"side-by-side display."
            )

    disagreements = [p for p in pairs_to_process if not p.agreed]
    agreements = [p for p in pairs_to_process if p.agreed]

    stdout.write(
        f"\nReconciliation session — arm={arm}, coder={coder}\n"
        f"  first-pass sheet      : {first_pass_path}\n"
        f"  second-coder sheet    : {second_coder_path}\n"
        f"  output sheet          : {output_path}\n"
        f"  shared OCIDs (pair-able): {len(pairs)}\n"
        f"  already reconciled    : {len(already)}\n"
        f"  agreements to copy    : {len(agreements)}\n"
        f"  disagreements to walk : {len(disagreements)}\n"
    )
    if fp_only:
        stdout.write(
            f"  ⚠  {len(fp_only)} OCID(s) in first-pass only "
            "(NOT written to output): "
            f"{', '.join(fp_only[:5])}{'…' if len(fp_only) > 5 else ''}\n"
        )
    if sc_only:
        stdout.write(
            f"  ⚠  {len(sc_only)} OCID(s) in second-coder only "
            "(NOT written to output): "
            f"{', '.join(sc_only[:5])}{'…' if len(sc_only) > 5 else ''}\n"
        )

    if len(disagreements) == 0 and len(agreements) == 0:
        stdout.write("\nNothing to reconcile this session.\n")
        return 0

    stdout.write(
        "\nThis is a RECONCILIATION tool. You see BOTH calls plus the "
        "rubric's default rule.\nQuit at any time with q — every "
        "reconciled record is on disk before the next prompt.\n"
    )

    rows_written = 0

    # First, copy agreements verbatim from the first-pass with coder
    # rewritten. They don't go through the prompt — the agreement IS the
    # reconciliation outcome.
    for pair in agreements:
        entry = ReconciledEntry(
            ocid=pair.ocid,
            arm=arm,
            category=pair.first_pass.category,
            justification=pair.first_pass.justification,
            coded_at=_utc_now_iso(),
            coder=coder,
            reconciliation_action="agreement-kept",
            first_pass_category=pair.first_pass.category,
            second_coder_category=pair.second_coder.category,
        )
        append_reconciled_entry(output_path, entry)
        rows_written += 1
    if agreements:
        stdout.write(
            f"\n✓ {len(agreements)} agreement(s) copied verbatim to "
            f"{output_path} (action=agreement-kept).\n"
        )

    # Then walk disagreements with the reviewer.
    total = len(disagreements)
    idx = 0
    previous_ocid: str | None = None  # for the 'back' action

    try:
        while idx < total:
            pair = disagreements[idx]
            bundle = bundles_by_ocid[pair.ocid]
            spec = specs[pair.ocid]

            stdout.write(
                _render_disagreement(
                    idx=idx + 1,
                    total=total,
                    bundle=bundle,
                    spec=spec,
                    first_pass=pair.first_pass,
                    second_coder=pair.second_coder,
                    arm=arm,
                )
            )
            stdout.write("\n")
            stdout.flush()

            action = _prompt_action(
                stdin=stdin,
                stdout=stdout,
                has_previous=previous_ocid is not None,
            )

            if action == "q":
                stdout.write(
                    f"\nQuit. {rows_written} record(s) written this session; "
                    f"sheet at {output_path} preserved.\n"
                )
                return rows_written

            if action == "b":
                # Rewind: the previous record was written to disk; we
                # rewrite the sheet without it and re-prompt for it.
                if previous_ocid is None:
                    # Defensive: _prompt_action shouldn't return 'b'
                    # without a previous, but belt-and-braces.
                    continue
                _rewind_one_row(output_path, previous_ocid, arm)
                idx -= 1
                previous_ocid = None
                rows_written = max(0, rows_written - 1)
                continue

            if action == "k":
                entry = ReconciledEntry(
                    ocid=pair.ocid,
                    arm=arm,
                    category=pair.first_pass.category,
                    justification=pair.first_pass.justification,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                    reconciliation_action="first-pass-kept",
                    first_pass_category=pair.first_pass.category,
                    second_coder_category=pair.second_coder.category,
                )
            elif action == "s":
                entry = ReconciledEntry(
                    ocid=pair.ocid,
                    arm=arm,
                    category=pair.second_coder.category,
                    justification=pair.second_coder.justification,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                    reconciliation_action="second-coder-adopted",
                    first_pass_category=pair.first_pass.category,
                    second_coder_category=pair.second_coder.category,
                )
            else:  # action == "o"
                cat, just = _prompt_override(
                    stdin=stdin, stdout=stdout, reasoning_text=bundle.reasoning
                )
                entry = ReconciledEntry(
                    ocid=pair.ocid,
                    arm=arm,
                    category=cat,
                    justification=just,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                    reconciliation_action="override",
                    first_pass_category=pair.first_pass.category,
                    second_coder_category=pair.second_coder.category,
                )

            append_reconciled_entry(output_path, entry)
            rows_written += 1
            previous_ocid = pair.ocid
            stdout.write(
                f"  ✓ recorded: action={entry.reconciliation_action}, "
                f"category={entry.category} "
                f"({CATEGORY_LABELS[entry.category]})\n"
            )
            stdout.flush()
            idx += 1
    except KeyboardInterrupt:
        stdout.write(
            f"\n\nInterrupted. {rows_written} record(s) written this "
            f"session; sheet at {output_path} preserved.\n"
        )
        return rows_written
    except EOFError:
        stdout.write(
            f"\n\nEOF on stdin. {rows_written} record(s) written this "
            f"session; sheet at {output_path} preserved.\n"
        )
        return rows_written

    stdout.write(
        f"\nSession complete. {rows_written} row(s) written to {output_path}.\n"
    )
    return rows_written


def _rewind_one_row(sheet_path: Path, ocid: str, arm: str) -> None:
    """Remove the LAST row matching (ocid, arm) from the reconciled
    sheet. Used by the 'b' (back) action.

    Reads the sheet, drops the last matching row, rewrites. This is
    the ONE place the reconciliation sheet is non-append-only —
    deliberately scoped to the 'back' action and unit-tested."""
    if not sheet_path.exists():
        return
    lines = sheet_path.read_text(encoding="utf-8").splitlines()
    # Walk from the end; drop the first match.
    drop_idx: int | None = None
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if raw.get("ocid") == ocid and raw.get("arm") == arm:
            drop_idx = i
            break
    if drop_idx is None:
        return
    new_lines = lines[:drop_idx] + lines[drop_idx + 1:]
    # Preserve trailing newline if the file had one.
    text = "\n".join(new_lines)
    if new_lines:
        text += "\n"
    sheet_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Argument parsing + entry point
# ---------------------------------------------------------------------------


def _default_rubric_doc_path() -> Path:
    """Path to ``planning/diagnostic_rubric.md`` relative to this file.

    Mirrors ``score_rubric.DEFAULT_PREDICTIONS_PATH`` — three parents
    up lands at ``procurement-context-disambiguation/``, then into
    ``planning/``."""
    return (
        Path(__file__).resolve().parents[3]
        / "planning"
        / "diagnostic_rubric.md"
    )


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.diagnostic.review_disagreements",
        description=(
            "Interactive RECONCILIATION tool for rubric-coding "
            "disagreements between a first-pass coding sheet and a "
            "second-coder sheet. NOT blind re-coding — the reviewer "
            "sees BOTH calls plus the rubric's default rule. Offline; "
            "no model calls."
        ),
    )
    parser.add_argument(
        "--first-pass",
        required=True,
        type=Path,
        help="First-pass coding sheet (JSONL produced by code_rubric.py).",
    )
    parser.add_argument(
        "--second-coder",
        required=True,
        type=Path,
        help="Second-coder coding sheet (JSONL).",
    )
    parser.add_argument(
        "--diagnostic-dir",
        required=True,
        type=Path,
        help=(
            "Directory containing the diagnostic bundle JSONs. Same "
            "directory the first-pass coder used."
        ),
    )
    parser.add_argument(
        "--inverted-spec",
        required=True,
        type=Path,
        help="Inverted-operator-spec JSON map (OCID → spec text).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help=(
            "Output reconciled coding sheet (JSON-lines, append-only "
            "except for the 'back' action's targeted row removal)."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=sorted(VALID_ARMS),
        default="diagnostic_primary",
        help=(
            "Which arm to reconcile. Defaults to diagnostic_primary "
            "(the most common single-arm reconciliation pass)."
        ),
    )
    parser.add_argument(
        "--rubric-doc",
        type=Path,
        default=_default_rubric_doc_path(),
        help=(
            "Path to diagnostic_rubric.md. Defaults to the in-repo "
            "locked file. The default-rule sentence shown to the "
            "reviewer is enforced against this file at test time."
        ),
    )
    parser.add_argument(
        "--coder",
        default=None,
        help=(
            "Reconciliation coder identifier. Defaults to "
            "'$USER-reconciled'."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Skip OCIDs already in the output sheet. (This is the "
            "DEFAULT behaviour — the flag is accepted for explicitness.)"
        ),
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_argparser().parse_args(list(argv) if argv is not None else None)
    coder = args.coder
    if coder is None:
        coder = f"{os.environ.get('USER', 'anonymous')}-reconciled"

    try:
        run_reconciliation_session(
            first_pass_path=args.first_pass,
            second_coder_path=args.second_coder,
            diagnostic_dir=args.diagnostic_dir,
            inverted_spec_path=args.inverted_spec,
            output_path=args.output,
            arm=args.arm,
            coder=coder,
            stdin=sys.stdin,
            stdout=sys.stdout,
        )
    except (RubricSchemaError, FileNotFoundError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
