"""AI-first review-and-adjudication tool for E3 rubric coding.

This tool implements an AI-FIRST PROTOCOL where:
  1. A blind AI agent codes all N records first (separate dispatch;
     see the dispatch protocol in the diagnostic_primary blind-agent
     PR #107 for the hard rails: strict file allowlist, no access to
     predictions or prior analyses).
  2. The human reviewer walks ALL N records with the agent's call,
     the agent's justification, the reasoning text, the inverted-
     operator spec, and the locked rubric (refresher + default rule)
     visible per record.
  3. The human accepts the agent's call (recorded as ``agent-accepted``)
     or overrides with explicit justification (recorded as
     ``human-overridden``).

This is NOT blind first-pass coding (the human sees the agent's call).
This is NOT reconciliation-with-rubric-anchor (the human reviews ALL
records, not just disagreements between two prior coders).

## Protocol disclosure (verbatim from Sam, 2026-06-07)

    "diagnostic_primary was coded via blind human first pass + blind
    AI second-coder + reconciliation; diagnostic_claude was coded via
    AI-first + human review-and-adjudication of all 100 records with
    rubric visible. The protocol change for claude was made in
    response to a methodological observation surfaced during primary's
    reconciliation (see decision_log entry 2026-06-07)."

The writeup methods section MUST lift this paragraph verbatim. Don't
describe the AI-first reviewed sheet as "blind first pass" or as
"reconciliation" — both would mis-characterise the protocol.

## Why this protocol exists

This tool was added in response to a methodological observation during
primary's reconciliation (PR #109): the blind-human-first-pass protocol
produced systematic drift due to coder fatigue across 100 records. The
human reviewer adopted the AI's call on 79/79 contested records during
primary's reconciliation. AI-first + human review-and-adjudication more
accurately reflects the human reviewer's working pattern and removes
the drift vector (categorisation from memory under fatigue).

## What the script does

1. Loads the agent's coded sheet (``--agent-sheet``) — every OCID in the
   diagnostic directory MUST be present (validated at startup; mismatch
   STOPs before any prompting).
2. Loads bundles for each OCID → extracts ``agent.reasoning``. Loads the
   inverted-operator-spec sidecar → looks up each OCID's entry.
3. For each record in OCID-ascending order (same deterministic sort
   ``code_rubric.py`` uses), presents the reviewer:
     - Header (OCID + record index).
     - The inverted-operator spec.
     - The reasoning text under the permuted policy.
     - The AI agent's call (category + justification + identity).
     - The rubric one-line refresher per category + the verbatim
       default-rule sentence from ``planning/diagnostic_rubric.md``.
4. Prompts:
     - ``a`` (accept agent's call) → records ``review_action="agent-accepted"``.
     - ``o`` (override) → prompts for new category (1/2/3) + new
       justification quote (must be a literal substring of the
       reasoning text). Records ``review_action="human-overridden"``.
     - ``b`` (back) → revisit the previous record.
     - ``q`` (quit-save) → write progress + exit (resume-able).
5. The output sheet is a JSON-lines file. Each row carries the six
   ``CodedEntry`` locked fields PLUS four audit-trail fields:
   ``review_action``, ``agent_category``, ``agent_justification``,
   ``agent_identity``. The locked fields make the sheet a
   ``CodedEntry`` SUPERSET — ``score_rubric.read_sheet`` loads it for κ
   computation without modification.

## Offline by design

NO model calls. NO API calls. NO MeshQu interactions. The "AI" referenced
here is whoever produced the input agent sheet (Sam orchestrates that
dispatch separately, same protocol as the blind-agent dispatch for
primary). This tool only surfaces locked content + an existing coding
sheet to a human; it does not generate, paraphrase, or rewrite anything.

## Usage

    python -m meshqu_runner.diagnostic.review_all \\
        --agent-sheet results/rubric_coding_claude_blind_agent.jsonl \\
        --diagnostic-dir results/runs/<run_id>/diagnostic_claude \\
        --inverted-spec results/runs/<run_id>/inverted_operator_spec.json \\
        --output results/rubric_coding_claude.jsonl \\
        [--arm diagnostic_claude]    # default: diagnostic_claude
        [--rubric-doc <path>]        # defaults to planning/diagnostic_rubric.md
        [--coder <name>]             # defaults to $USER
        [--resume]                   # implicit by default

Resume is implicit: on a second invocation, OCIDs already in the
output sheet are skipped. Ctrl-C / EOF preserves on-disk progress
(same idiom as ``code_rubric.py`` / ``review_disagreements.py``).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import asdict, dataclass
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
# Mirrored from ``review_disagreements.py`` so the per-record display is
# byte-identical across the two human-review tools. The default-rule
# sentence is QUOTED VERBATIM from the locked rubric; the test suite
# enforces equality with ``planning/diagnostic_rubric.md`` so this
# string can't drift.

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
# Audit fields + AI-first reviewed entry wrapper
# ---------------------------------------------------------------------------
#
# The brief is explicit: DO NOT modify CodedEntry or ReconciledEntry.
# The AI-first protocol has its own audit vocabulary — only two
# review_action values (vs reconciliation's four), plus per-record
# agent-side provenance (category + justification + identity). A new
# wrapper composes CodedEntry's six locked fields with the AI-first
# audit fields. Downstream code can either read the raw JSONL (the new
# fields are top-level keys alongside the original six) or use the
# helper ``read_ai_first_reviewed_sheet()`` below for the typed view.

# Locked vocabulary for review_action. Anchored as a constant so the
# analysis-markdown follow-up can import it for the same vocab.
REVIEW_ACTIONS: frozenset[str] = frozenset(
    {
        "agent-accepted",
        "human-overridden",
    }
)


@dataclass(frozen=True)
class AIFirstReviewedEntry:
    """One row in the AI-first reviewed coding sheet.

    Wraps CodedEntry's six locked fields and adds four audit fields.
    The on-disk shape is a single flat JSON object — the four extra
    keys appear at top level alongside the original six so the file
    stays readable as one JSONL row per record AND so that
    ``score_rubric.read_sheet`` (which reads only the six locked
    fields) can load this output unchanged for κ computation.
    """

    # CodedEntry fields (same names, same semantics).
    ocid: str
    arm: str
    category: int
    justification: str
    coded_at: str
    coder: str

    # AI-first review audit fields.
    review_action: str
    agent_category: int
    agent_justification: str
    agent_identity: str

    def to_json_line(self) -> str:
        if self.review_action not in REVIEW_ACTIONS:
            raise RubricSchemaError(
                f"Invalid review_action {self.review_action!r}; "
                f"expected one of {sorted(REVIEW_ACTIONS)}."
            )
        if self.category not in VALID_CATEGORIES:
            raise RubricSchemaError(
                f"Invalid category {self.category!r}; expected one of "
                f"{sorted(VALID_CATEGORIES)}."
            )
        if self.agent_category not in VALID_CATEGORIES:
            raise RubricSchemaError(
                f"Invalid agent_category {self.agent_category!r}; expected "
                f"one of {sorted(VALID_CATEGORIES)}."
            )
        return json.dumps(asdict(self), sort_keys=True)


def append_ai_first_reviewed_entry(
    sheet_path: Path, entry: AIFirstReviewedEntry
) -> None:
    """Append-only write; creates the parent dir if needed.

    Mirrors ``rubric_io.append_entry`` — the reviewed sheet is the
    sibling artefact of the per-arm coding sheets and inherits the
    same append-only contract (modulo the 'back' action's targeted
    row removal, which is the one exception)."""
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    with sheet_path.open("a", encoding="utf-8") as f:
        f.write(entry.to_json_line() + "\n")


def read_ai_first_reviewed_sheet(sheet_path: Path) -> list[AIFirstReviewedEntry]:
    """Read an AI-first reviewed coding sheet into typed rows. Returns
    ``[]`` for a missing file (cold start)."""
    if not sheet_path.exists():
        return []
    out: list[AIFirstReviewedEntry] = []
    with sheet_path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RubricSchemaError(
                    f"Reviewed sheet {sheet_path}:{lineno} is not valid JSON: "
                    f"{exc}"
                )
            try:
                out.append(
                    AIFirstReviewedEntry(
                        ocid=str(raw["ocid"]),
                        arm=str(raw["arm"]),
                        category=int(raw["category"]),
                        justification=str(raw["justification"]),
                        coded_at=str(raw["coded_at"]),
                        coder=str(raw["coder"]),
                        review_action=str(raw["review_action"]),
                        agent_category=int(raw["agent_category"]),
                        agent_justification=str(raw["agent_justification"]),
                        agent_identity=str(raw["agent_identity"]),
                    )
                )
            except KeyError as exc:
                raise RubricSchemaError(
                    f"Reviewed sheet {sheet_path}:{lineno} missing required "
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
    "Action? [a=accept agent's call / o=override / b=back / q=quit-save]: "
)
OVERRIDE_CATEGORY_PROMPT = (
    "Override category? [1=names inversion / 2=reasons against intent / "
    "3=partial]: "
)
OVERRIDE_JUSTIFICATION_PROMPT = (
    "Override justification (must be a literal substring of the reasoning "
    "text above): "
)
ACTION_REPROMPT = "  ⚠  Invalid action — enter a, o, b, or q.\n"
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


def _render_record(
    *,
    idx: int,
    total: int,
    bundle: DiagnosticBundle,
    spec: InvertedSpec,
    agent_entry: CodedEntry,
    arm: str,
) -> str:
    """Format the per-record review display block.

    Mirrors ``review_disagreements._render_disagreement``'s plain-text
    shape (no ANSI) so the CLI is paste-friendly into a review log.

    Layout:

        ════ Record i of N — arm — OCID …last12 ════
        INVERTED-OPERATOR SPEC
            <spec.spec>

        REASONING TEXT
            <bundle.reasoning>
        ─────────────────────────────────────────────
        RUBRIC REFRESHER
            <cat 1, 2, 3 one-liners>

            DEFAULT RULE (verbatim from diagnostic_rubric.md):
                <RUBRIC_DEFAULT_RULE>
        ─────────────────────────────────────────────
        AI AGENT'S CALL
            [a] category N (label)
                justification : <quote>
                agent         : <identity>
        ═════════════════════════════════════════════
    """
    bar = "═" * 78
    thin = "─" * 78
    short_ocid = bundle.ocid[-12:] if len(bundle.ocid) > 12 else bundle.ocid
    lines = [
        "",
        bar,
        f"Record {idx} of {total} — {arm} — OCID …{short_ocid}",
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
        "AI AGENT'S CALL",
        f"  [a] category {agent_entry.category} "
        f"({CATEGORY_LABELS[agent_entry.category]})",
        f"      justification : {agent_entry.justification}",
        f"      agent         : {agent_entry.coder}",
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
    """Prompt for the reviewer's action. Returns one of 'a', 'o', 'b', 'q'.
    Raises EOFError on closed stdin.

    ``has_previous`` controls whether 'b' (back) is accepted — if there
    is no previously-reviewed record in this session, 'b' is treated as
    invalid (re-prompt). Avoids confusing fallthrough on the first record.
    """
    while True:
        stdout.write(ACTION_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before action was provided")
        raw = line.strip().lower()
        if raw in {"a", "o", "q"}:
            return raw
        if raw == "b":
            if has_previous:
                return raw
            stdout.write("  ⚠  No previous record to go back to.\n")
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
    text — same machinery as ``review_disagreements._prompt_override``.
    The rubric requires a one-line quote from the reasoning; on
    override the integrity check is even more important because the
    reviewer is not picking from the agent's existing justification."""
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
# Agent-sheet / diagnostic-dir cross-check
# ---------------------------------------------------------------------------


def _validate_agent_sheet_covers_bundles(
    *,
    agent_entries: list[CodedEntry],
    bundles: list[DiagnosticBundle],
    arm: str,
) -> dict[str, CodedEntry]:
    """Validate the agent sheet exactly covers the diagnostic-dir bundles.

    Returns ``{ocid: agent_entry}`` for the in-scope arm. STOP condition
    (raises ``RubricSchemaError``) if:
      - Any OCID is in the agent sheet but not in the bundles, or
      - Any OCID is in the bundles but not in the agent sheet, or
      - The agent sheet has duplicate (ocid, arm) rows.

    This pre-check fires BEFORE any prompting so the reviewer doesn't
    walk a partial sheet and discover the mismatch 80 records in."""
    bundle_ocids = {b.ocid for b in bundles}

    arm_entries: dict[str, CodedEntry] = {}
    for entry in agent_entries:
        if entry.arm != arm:
            continue
        if entry.ocid in arm_entries:
            raise RubricSchemaError(
                f"Agent sheet contains duplicate row for OCID "
                f"{entry.ocid!r} on arm {arm!r}; the AI-first protocol "
                "requires an unambiguous one-row-per-OCID sheet."
            )
        arm_entries[entry.ocid] = entry

    sheet_ocids = set(arm_entries.keys())
    in_sheet_not_bundles = sorted(sheet_ocids - bundle_ocids)
    in_bundles_not_sheet = sorted(bundle_ocids - sheet_ocids)
    if in_sheet_not_bundles or in_bundles_not_sheet:
        parts = []
        if in_bundles_not_sheet:
            parts.append(
                f"{len(in_bundles_not_sheet)} OCID(s) in diagnostic-dir but "
                f"not in agent sheet (e.g. "
                f"{', '.join(in_bundles_not_sheet[:3])}"
                f"{'…' if len(in_bundles_not_sheet) > 3 else ''})"
            )
        if in_sheet_not_bundles:
            parts.append(
                f"{len(in_sheet_not_bundles)} OCID(s) in agent sheet but "
                f"not in diagnostic-dir (e.g. "
                f"{', '.join(in_sheet_not_bundles[:3])}"
                f"{'…' if len(in_sheet_not_bundles) > 3 else ''})"
            )
        raise RubricSchemaError(
            "Agent sheet does not cover diagnostic-dir bundles 1:1 for "
            f"arm {arm!r}. The AI-first protocol requires the agent to have "
            "coded every record before human review begins. "
            + "; ".join(parts)
            + ". STOP — re-dispatch the blind agent over the missing OCIDs "
            "before starting review."
        )

    return arm_entries


# ---------------------------------------------------------------------------
# Back-action rewinder
# ---------------------------------------------------------------------------


def _rewind_one_row(sheet_path: Path, ocid: str, arm: str) -> None:
    """Remove the LAST row matching (ocid, arm) from the reviewed sheet.

    Used by the 'b' (back) action. Reads the sheet, drops the last
    matching row, rewrites. This is the ONE place the reviewed sheet is
    non-append-only — deliberately scoped to the 'back' action and
    unit-tested. Mirrors ``review_disagreements._rewind_one_row``."""
    if not sheet_path.exists():
        return
    lines = sheet_path.read_text(encoding="utf-8").splitlines()
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
    text = "\n".join(new_lines)
    if new_lines:
        text += "\n"
    sheet_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main review loop
# ---------------------------------------------------------------------------


def run_review_session(
    *,
    agent_sheet_path: Path,
    diagnostic_dir: Path,
    inverted_spec_path: Path,
    output_path: Path,
    arm: str,
    coder: str,
    stdin: IO[str],
    stdout: IO[str],
) -> int:
    """Drive the AI-first review session end-to-end. Returns the number
    of rows written to the output sheet in this session.

    Pure function over its IO arguments — no module-level state.
    Resume is implicit: OCIDs already in ``output_path`` are skipped.
    Every record receives the prompt (this protocol has no auto-copy)."""
    if arm not in VALID_ARMS:
        raise SystemExit(
            f"--arm must be one of {sorted(VALID_ARMS)}; got {arm!r}"
        )

    agent_entries = read_sheet(agent_sheet_path)
    bundles = load_diagnostic_bundles(diagnostic_dir)
    specs = load_inverted_specs(inverted_spec_path)

    # Validate agent sheet covers bundles 1:1 BEFORE any prompting.
    agent_by_ocid = _validate_agent_sheet_covers_bundles(
        agent_entries=agent_entries,
        bundles=bundles,
        arm=arm,
    )

    # Every bundle OCID must have a spec entry (the rubric needs it
    # for the side-by-side display).
    bundles_by_ocid = {b.ocid: b for b in bundles}
    for ocid in sorted(bundles_by_ocid.keys()):
        if ocid not in specs:
            raise RubricSchemaError(
                f"No inverted-operator spec for OCID {ocid!r}; the rubric "
                "requires the spec for the per-record display. Did E3-008 "
                "emit a complete spec file for this run?"
            )

    # Resume: skip OCIDs already in the output sheet (for this arm).
    existing = read_ai_first_reviewed_sheet(output_path)
    already = {e.ocid for e in existing if e.arm == arm}

    # Records to walk: bundles in OCID-ascending order, skipping
    # already-reviewed.
    walk_order = [b for b in bundles if b.ocid not in already]

    stdout.write(
        f"\nAI-first review session — arm={arm}, coder={coder}\n"
        f"  agent sheet           : {agent_sheet_path}\n"
        f"  diagnostic dir        : {diagnostic_dir}\n"
        f"  output sheet          : {output_path}\n"
        f"  records in scope      : {len(bundles)}\n"
        f"  already reviewed      : {len(already)}\n"
        f"  to review this session: {len(walk_order)}\n"
    )

    if not walk_order:
        stdout.write("\nNothing to review this session.\n")
        return 0

    stdout.write(
        "\nThis is an AI-FIRST review tool. You see the agent's call plus the "
        "rubric's default rule for every record.\nQuit at any time with q — "
        "every reviewed record is on disk before the next prompt.\n"
    )

    rows_written = 0
    total = len(walk_order)
    idx = 0
    previous_ocid: str | None = None  # for the 'back' action

    try:
        while idx < total:
            bundle = walk_order[idx]
            spec = specs[bundle.ocid]
            agent_entry = agent_by_ocid[bundle.ocid]

            stdout.write(
                _render_record(
                    idx=idx + 1,
                    total=total,
                    bundle=bundle,
                    spec=spec,
                    agent_entry=agent_entry,
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
                # Rewind: previous record was written to disk; remove it
                # and re-prompt for it.
                if previous_ocid is None:
                    # Defensive: _prompt_action shouldn't return 'b'
                    # without a previous, but belt-and-braces.
                    continue
                _rewind_one_row(output_path, previous_ocid, arm)
                idx -= 1
                previous_ocid = None
                rows_written = max(0, rows_written - 1)
                continue

            if action == "a":
                entry = AIFirstReviewedEntry(
                    ocid=bundle.ocid,
                    arm=arm,
                    category=agent_entry.category,
                    justification=agent_entry.justification,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                    review_action="agent-accepted",
                    agent_category=agent_entry.category,
                    agent_justification=agent_entry.justification,
                    agent_identity=agent_entry.coder,
                )
            else:  # action == "o"
                cat, just = _prompt_override(
                    stdin=stdin,
                    stdout=stdout,
                    reasoning_text=bundle.reasoning,
                )
                entry = AIFirstReviewedEntry(
                    ocid=bundle.ocid,
                    arm=arm,
                    category=cat,
                    justification=just,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                    review_action="human-overridden",
                    agent_category=agent_entry.category,
                    agent_justification=agent_entry.justification,
                    agent_identity=agent_entry.coder,
                )

            append_ai_first_reviewed_entry(output_path, entry)
            rows_written += 1
            previous_ocid = bundle.ocid
            stdout.write(
                f"  ✓ recorded: action={entry.review_action}, "
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


# ---------------------------------------------------------------------------
# Argument parsing + entry point
# ---------------------------------------------------------------------------


def _default_rubric_doc_path() -> Path:
    """Path to ``planning/diagnostic_rubric.md`` relative to this file.

    Mirrors ``review_disagreements._default_rubric_doc_path`` — three
    parents up lands at ``procurement-context-disambiguation/``, then
    into ``planning/``."""
    return (
        Path(__file__).resolve().parents[3]
        / "planning"
        / "diagnostic_rubric.md"
    )


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.diagnostic.review_all",
        description=(
            "Interactive AI-first + human review-and-adjudication tool "
            "for rubric coding. The human reviewer walks every record "
            "with the AI agent's call + rubric visible, accepting or "
            "overriding per-record. NOT blind first-pass coding, NOT "
            "reconciliation. Offline; no model calls."
        ),
    )
    parser.add_argument(
        "--agent-sheet",
        required=True,
        type=Path,
        help=(
            "AI agent's coded sheet (JSONL produced by code_rubric.py "
            "under the blind-agent dispatch protocol)."
        ),
    )
    parser.add_argument(
        "--diagnostic-dir",
        required=True,
        type=Path,
        help=(
            "Directory containing the diagnostic bundle JSONs. Same "
            "directory the agent coded against."
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
            "Output AI-first reviewed coding sheet (JSON-lines, "
            "append-only except for the 'back' action's targeted "
            "row removal)."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=sorted(VALID_ARMS),
        default="diagnostic_claude",
        help=(
            "Which arm to review. Defaults to diagnostic_claude (the "
            "first arm the AI-first protocol applies to)."
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
            "Reviewer identifier. Defaults to $USER (the AI-first "
            "protocol records the human reviewer as the coder; the "
            "agent's identity is preserved in agent_identity)."
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
        coder = os.environ.get("USER", "anonymous")

    try:
        run_review_session(
            agent_sheet_path=args.agent_sheet,
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
