"""Rubric-scoring helper — E3-009.

Reads a JSON-lines coding sheet produced by ``code_rubric.py`` and
reports the per-category counts + percentages alongside P5's
pre-registered confirmation / falsification verdicts.

## Offline by design

Same as ``code_rubric.py`` — pure local file IO, no network, no
model calls. The whole point of the rubric is HUMAN coding; this
helper just aggregates the human's outputs.

## Bands come from predictions.md

Build package §5: "read from there, don't hard-code in the script."
We parse the P5 line of ``planning/predictions.md`` at runtime so a
band edit in the locked predictions file is the single source of
truth. A drift between predictions.md and the helper output would
fire ``RubricSchemaError`` rather than silently coerce to defaults.

## Usage

    python -m meshqu_runner.diagnostic.score_rubric \\
        --sheet results/rubric_coding_primary.jsonl \\
        [--predictions <path>]   # defaults to repo predictions.md
        [--arm diagnostic_primary | diagnostic_claude]   # filter
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable

from .rubric_io import (
    CATEGORY_LABELS,
    CodedEntry,
    P5Bands,
    RubricSchemaError,
    VALID_ARMS,
    VALID_CATEGORIES,
    parse_p5_bands,
    read_sheet,
)


# ---------------------------------------------------------------------------
# Default predictions.md location
# ---------------------------------------------------------------------------
#
# The helper lives at ``meshqu_runner/diagnostic/score_rubric.py``;
# walking up four parents lands at the repo root, where the locked
# predictions file lives at
# ``procurement-context-disambiguation/planning/predictions.md``.
# A CLI flag overrides this for tests + adversarial runs.

_THIS_FILE = Path(__file__).resolve()
DEFAULT_PREDICTIONS_PATH = (
    _THIS_FILE.parents[3]  # runner/ -> procurement-context-disambiguation/
    / "planning"
    / "predictions.md"
)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmReport:
    """Per-arm aggregation result, ready for printing."""

    arm: str
    counts: Counter
    total: int
    bands: P5Bands

    def pct(self, category: int) -> float:
        if self.total == 0:
            return 0.0
        return (self.counts.get(category, 0) / self.total) * 100.0

    def p5_confirmed(self) -> bool:
        """P5 confirmation: Cat 2 ≥ floor AND Cat 1 ≤ cap."""
        return (
            self.pct(2) >= self.bands.intent_floor_pct
            and self.pct(1) <= self.bands.names_cap_pct
        )

    def p5_falsified(self) -> bool:
        """P5 falsification: Cat 1 strictly greater than the falsify band."""
        return self.pct(1) > self.bands.names_falsify_pct

    def p5_disposition(self) -> str:
        """One of the locked disposition vocab terms.

        Vocabulary anchor (from predictions.md §"Definition of 'report
        honestly'"): {Confirmed, Falsified, Inverted, Refuted, Deferred,
        Under-tested}. We only emit the three that the bands can speak
        to mechanically — a coder reviewing the report decides if a
        "neither confirmed nor falsified" result deserves Inverted /
        Refuted / Deferred narratively.
        """
        confirmed = self.p5_confirmed()
        falsified = self.p5_falsified()
        # Bands are constructed so confirm and falsify don't overlap
        # (cap=15, falsify=25 — Cat 1 ≤ 15 and Cat 1 > 25 are disjoint).
        # If both somehow fire (caller edited predictions.md to overlap),
        # falsification wins — surfacing the contradiction explicitly.
        if falsified:
            return "Falsified"
        if confirmed:
            return "Confirmed"
        return "Under-tested"


def aggregate(
    entries: list[CodedEntry], arm: str, bands: P5Bands
) -> ArmReport:
    """Aggregate a coding sheet into per-arm counts.

    Filters to entries matching ``arm`` and counts categories. Any
    category outside the locked {1, 2, 3} set raises — the sheet
    writer enforces validity on the way in, so a stray category here
    means the sheet was hand-edited and we should fail loud.
    """
    filtered = [e for e in entries if e.arm == arm]
    counts: Counter = Counter()
    for entry in filtered:
        if entry.category not in VALID_CATEGORIES:
            raise RubricSchemaError(
                f"Sheet contains invalid category {entry.category!r} for "
                f"OCID {entry.ocid!r} — expected one of "
                f"{sorted(VALID_CATEGORIES)}."
            )
        counts[entry.category] += 1
    return ArmReport(arm=arm, counts=counts, total=len(filtered), bands=bands)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_report(report: ArmReport, *, expected_n: int | None = None) -> str:
    """Format a single arm's report. Mirrors the build-package §5
    example output."""
    lines = []
    lines.append(f"Arm:                    {report.arm}")
    if expected_n is not None:
        lines.append(
            f"N records coded:        {report.total} / {expected_n}"
        )
    else:
        lines.append(f"N records coded:        {report.total}")

    for cat in sorted(VALID_CATEGORIES):
        n = report.counts.get(cat, 0)
        pct = report.pct(cat)
        # Keep the label aligned with the build-package example's
        # short forms — "names", "intent", "partial".
        short = {1: "names", 2: "intent", 3: "partial"}[cat]
        lines.append(
            f"Category {cat} ({short:<7}): {n:<4} ({pct:5.1f}%)"
        )

    lines.append("")
    lines.append("P5 evaluation:")
    confirm_ok = report.p5_confirmed()
    falsify_fired = report.p5_falsified()
    bands = report.bands
    lines.append(
        f"  Confirmed: Cat 2 >= {bands.intent_floor_pct:g}% AND "
        f"Cat 1 <= {bands.names_cap_pct:g}%? "
        f"{'YES' if confirm_ok else 'NO'}"
    )
    lines.append(
        f"  Falsified: Cat 1 > {bands.names_falsify_pct:g}%?"
        f"                    "
        f"{'YES' if falsify_fired else 'NO'}"
    )
    lines.append(f"  Reported disposition: {report.p5_disposition()}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.diagnostic.score_rubric",
        description=(
            "Aggregate a rubric coding sheet into per-arm category "
            "counts + P5 disposition. Bands read from predictions.md."
        ),
    )
    parser.add_argument(
        "--sheet",
        required=True,
        type=Path,
        help="Coding sheet (JSON-lines) produced by code_rubric.py.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=DEFAULT_PREDICTIONS_PATH,
        help=(
            "Path to predictions.md (defaults to the in-repo locked "
            "file). Bands are parsed from this file at runtime."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=sorted(VALID_ARMS),
        default=None,
        help=(
            "If set, only report this arm. Default: report every arm "
            "with at least one coded row in the sheet."
        ),
    )
    parser.add_argument(
        "--expected-n",
        type=int,
        default=None,
        help=(
            "Expected sample size per arm (for the 'N records coded: M "
            "/ EXPECTED-N' display). Defaults to omitting the expected."
        ),
    )
    return parser


def _arms_to_report(entries: list[CodedEntry], arm_filter: str | None) -> list[str]:
    if arm_filter is not None:
        return [arm_filter]
    # Report every arm with any coded row, in deterministic order.
    seen = {e.arm for e in entries}
    return sorted(seen)


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_argparser().parse_args(list(argv) if argv is not None else None)
    try:
        entries = read_sheet(args.sheet)
        bands = parse_p5_bands(args.predictions)
    except (RubricSchemaError, FileNotFoundError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    arms_in_scope = _arms_to_report(entries, args.arm)
    if not arms_in_scope:
        sys.stderr.write(
            f"error: sheet {args.sheet} contains no coded rows.\n"
        )
        return 2

    out: IO[str] = sys.stdout
    for idx, arm in enumerate(arms_in_scope):
        if idx > 0:
            out.write("\n" + ("=" * 60) + "\n\n")
        report = aggregate(entries, arm, bands)
        out.write(render_report(report, expected_n=args.expected_n))
        out.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
