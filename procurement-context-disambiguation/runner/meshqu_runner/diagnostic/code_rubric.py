"""Interactive rubric-coding CLI — E3-009.

Walks through Permuted-Policy diagnostic receipts one record at a
time, presents the agent's reasoning text + the inverted-operator
spec side-by-side, prompts the human coder for a category (1/2/3)
per ``diagnostic_rubric.md``, and appends a structured row to a
JSON-lines coding sheet.

## Offline by design

NO model calls. NO API calls. NO MeshQu interactions. The rubric is a
human-coding protocol — this CLI is the surface that shows the locked
content to the coder; it does not generate, paraphrase, or rewrite
anything.

## Usage

    python -m meshqu_runner.diagnostic.code_rubric \\
        --arm diagnostic_primary \\
        --diagnostic-dir results/runs/<run_id>/diagnostic \\
        --inverted-spec results/runs/<run_id>/inverted_operator_spec.json \\
        --sheet results/rubric_coding_primary.jsonl \\
        [--resume]                # implicit by default; flag is a no-op alias
        [--double-code-subset 20] # optional inter-coder κ pass
        [--coder <name>]          # defaults to $USER

The sheet is APPEND-ONLY. Ctrl-C is safe — every coded record is on
disk before the next prompt fires.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path
from typing import IO, Iterable

from .rubric_io import (
    CATEGORY_LABELS,
    CodedEntry,
    DiagnosticBundle,
    InvertedSpec,
    PERMUTATION_LOG_FILENAME_DEFAULT,
    RubricSchemaError,
    VALID_ARMS,
    VALID_CATEGORIES,
    append_entry,
    coded_ocids_for_arm,
    iter_records_to_code,
    load_diagnostic_bundles,
    load_inverted_specs,
    read_sheet,
)


# ---------------------------------------------------------------------------
# Prompts (constants so tests can assert on them)
# ---------------------------------------------------------------------------

CATEGORY_PROMPT = (
    "Category? [1=names inversion / 2=reasons against intent / 3=partial]: "
)
JUSTIFICATION_PROMPT = (
    "One-line justification quote from the reasoning text "
    "(must not be empty): "
)
CATEGORY_REPROMPT = (
    "  ⚠  Invalid — enter 1, 2, or 3.\n"
)
JUSTIFICATION_REPROMPT = (
    "  ⚠  Justification cannot be empty — the rubric requires a one-line "
    "quote from the reasoning text.\n"
)


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with Z suffix — matches the bundle
    timestamp convention from ``multi_pass._utc_now_iso``."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def _render_record_header(
    *,
    idx: int,
    total: int,
    bundle: DiagnosticBundle,
    spec: InvertedSpec,
    arm: str,
) -> str:
    """Format the side-by-side display block for one record.

    Layout:

        ─────────── Record i/N — arm — OCID ───────────
        INVERTED-OPERATOR SPEC
            <spec.spec>

        REASONING TEXT
            <bundle.reasoning>

        ───────────────────────────────────────────────

    Intentionally plain (no ANSI colours) so the CLI is paste-friendly
    into a coding notebook / inter-coder review thread.
    """
    bar = "─" * 78
    return "\n".join(
        [
            "",
            bar,
            f"Record {idx}/{total} — {arm} — OCID {bundle.ocid}",
            f"  (bundle: {bundle.bundle_path.name}, decision_id={bundle.decision_id})",
            bar,
            "INVERTED-OPERATOR SPEC",
            _indent(spec.spec, "  "),
            "",
            "REASONING TEXT",
            _indent(bundle.reasoning, "  "),
            bar,
        ]
    )


def _indent(text: str, prefix: str) -> str:
    """Indent each line of ``text`` by ``prefix``. Keeps blank lines
    blank (no trailing whitespace)."""
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


# ---------------------------------------------------------------------------
# Prompt loop (parametrised on streams so tests can inject mocks)
# ---------------------------------------------------------------------------


def prompt_for_category(
    *, stdin: IO[str], stdout: IO[str]
) -> int:
    """Prompt for a category, re-prompting on invalid input.

    Returns the integer category code (one of 1/2/3). Raises
    ``EOFError`` if stdin closes — the CLI catches this and treats it
    as a clean session-end (same as Ctrl-D), preserving everything
    already on disk.
    """
    while True:
        stdout.write(CATEGORY_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before category was provided")
        raw = line.strip()
        if raw.isdigit() and int(raw) in VALID_CATEGORIES:
            return int(raw)
        stdout.write(CATEGORY_REPROMPT)
        stdout.flush()


def prompt_for_justification(
    *, stdin: IO[str], stdout: IO[str]
) -> str:
    """Prompt for a non-empty justification quote, re-prompting on
    empty input. The rubric requires a one-line quote per record —
    empty justification breaks the audit trail."""
    while True:
        stdout.write(JUSTIFICATION_PROMPT)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            raise EOFError("stdin closed before justification was provided")
        text = line.strip()
        if text:
            return text
        stdout.write(JUSTIFICATION_REPROMPT)
        stdout.flush()


# ---------------------------------------------------------------------------
# Main coding loop
# ---------------------------------------------------------------------------


def run_coding_session(
    *,
    arm: str,
    diagnostic_dir: Path,
    inverted_spec_path: Path,
    sheet_path: Path,
    coder: str,
    stdin: IO[str],
    stdout: IO[str],
    double_code_subset: int = 0,
) -> int:
    """Drive the coding session end-to-end. Returns the number of
    rows written to the sheet in this session.

    Pure function over its IO arguments — no module-level globals
    touched. Tests construct a temp dir + StringIO streams and assert
    against the resulting sheet file.
    """
    if arm not in VALID_ARMS:
        raise SystemExit(
            f"--arm must be one of {sorted(VALID_ARMS)}; got {arm!r}"
        )

    bundles = load_diagnostic_bundles(diagnostic_dir)
    specs = load_inverted_specs(inverted_spec_path)
    existing = read_sheet(sheet_path)
    already_coded = coded_ocids_for_arm(existing, arm)

    to_code: list[tuple[DiagnosticBundle, InvertedSpec]] = list(
        iter_records_to_code(bundles, specs, already_coded)
    )

    total = len(to_code)
    if total == 0:
        stdout.write(
            f"\nNothing to code: {len(bundles)} bundle(s) found, "
            f"{len(already_coded)} already in sheet for arm {arm!r}.\n"
        )
        return 0

    stdout.write(
        f"\nCoding session — arm={arm}, coder={coder}\n"
        f"  bundles found:      {len(bundles)}\n"
        f"  already coded:      {len(already_coded)}\n"
        f"  remaining to code:  {total}\n"
        f"  sheet:              {sheet_path}\n"
        f"\nRubric categories:\n"
    )
    for cat in sorted(VALID_CATEGORIES):
        stdout.write(f"  {cat}: {CATEGORY_LABELS[cat]}\n")
    stdout.write(
        "\nQuit at any time with Ctrl-C — each record is persisted before "
        "the next prompt.\n"
    )

    rows_written = 0
    try:
        for idx, (bundle, spec) in enumerate(to_code, start=1):
            stdout.write(_render_record_header(
                idx=idx, total=total, bundle=bundle, spec=spec, arm=arm
            ))
            stdout.write("\n")
            stdout.flush()

            category = prompt_for_category(stdin=stdin, stdout=stdout)
            justification = prompt_for_justification(stdin=stdin, stdout=stdout)

            entry = CodedEntry(
                ocid=bundle.ocid,
                arm=arm,
                category=category,
                justification=justification,
                coded_at=_utc_now_iso(),
                coder=coder,
            )
            append_entry(sheet_path, entry)
            rows_written += 1
            stdout.write(
                f"  ✓ recorded: category={category} "
                f"({CATEGORY_LABELS[category]})\n"
            )
            stdout.flush()
    except KeyboardInterrupt:
        stdout.write(
            f"\n\nInterrupted. {rows_written} record(s) coded this session; "
            f"sheet at {sheet_path} preserved.\n"
        )
        return rows_written
    except EOFError:
        stdout.write(
            f"\n\nEOF on stdin. {rows_written} record(s) coded this session; "
            f"sheet at {sheet_path} preserved.\n"
        )
        return rows_written

    # Optional inter-coder κ pass.
    if double_code_subset > 0:
        stdout.write(
            f"\n--- Double-coding pass ({double_code_subset} record(s)) ---\n"
            "The rubric's optional inter-coder check. Re-coded entries are "
            "written with the SAME coder name; downstream analysis compares "
            "by (ocid, arm) duplicates.\n"
        )
        subset = to_code[:double_code_subset]
        try:
            for idx, (bundle, spec) in enumerate(subset, start=1):
                stdout.write(_render_record_header(
                    idx=idx,
                    total=len(subset),
                    bundle=bundle,
                    spec=spec,
                    arm=arm,
                ))
                stdout.write(" [DOUBLE-CODE]\n")
                stdout.flush()
                category = prompt_for_category(stdin=stdin, stdout=stdout)
                justification = prompt_for_justification(
                    stdin=stdin, stdout=stdout
                )
                entry = CodedEntry(
                    ocid=bundle.ocid,
                    arm=arm,
                    category=category,
                    justification=justification,
                    coded_at=_utc_now_iso(),
                    coder=coder,
                )
                append_entry(sheet_path, entry)
                rows_written += 1
        except (KeyboardInterrupt, EOFError):
            stdout.write(
                f"\n\nDouble-code pass interrupted. {rows_written} total "
                f"row(s) written this session.\n"
            )
            return rows_written

    stdout.write(
        f"\nSession complete. {rows_written} row(s) written to {sheet_path}.\n"
    )
    return rows_written


# ---------------------------------------------------------------------------
# Argument parsing + entry point
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.diagnostic.code_rubric",
        description=(
            "Interactive rubric-coding tool for the Permuted-Policy "
            "diagnostic. Offline — no model calls. Surfaces locked content "
            "to a human coder and writes a structured coding sheet."
        ),
    )
    parser.add_argument(
        "--arm",
        required=True,
        choices=sorted(VALID_ARMS),
        help="Which diagnostic arm's receipts to code.",
    )
    parser.add_argument(
        "--diagnostic-dir",
        required=True,
        type=Path,
        help=(
            "Directory containing the diagnostic bundle JSONs "
            "(`<decision_id>.bundle.json`). Conventionally "
            "`<run_dir>/diagnostic`."
        ),
    )
    parser.add_argument(
        "--inverted-spec",
        required=True,
        type=Path,
        help=(
            "Path to the inverted-operator-spec JSON map "
            "(OCID -> one-line description of the inversion). Emitted by "
            "E3-008 alongside the diagnostic receipts."
        ),
    )
    parser.add_argument(
        "--sheet",
        required=True,
        type=Path,
        help="Output JSON-lines coding sheet (append-only).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Skip OCIDs already coded in the sheet for this arm. (This is "
            "the DEFAULT behaviour — the flag is accepted for explicitness.)"
        ),
    )
    parser.add_argument(
        "--coder",
        default=os.environ.get("USER", "anonymous"),
        help="Coder identifier (defaults to $USER).",
    )
    parser.add_argument(
        "--double-code-subset",
        type=int,
        default=0,
        metavar="N",
        help=(
            "After the main pass, present the first N OCIDs again for "
            "double-coding (the rubric's optional inter-coder κ check). "
            "0 disables (default)."
        ),
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_argparser().parse_args(list(argv) if argv is not None else None)
    try:
        run_coding_session(
            arm=args.arm,
            diagnostic_dir=args.diagnostic_dir,
            inverted_spec_path=args.inverted_spec,
            sheet_path=args.sheet,
            coder=args.coder,
            stdin=sys.stdin,
            stdout=sys.stdout,
            double_code_subset=max(0, args.double_code_subset),
        )
    except (RubricSchemaError, FileNotFoundError) as exc:
        # User-readable; non-zero exit so a wrapping shell script can
        # detect a misconfigured invocation.
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
