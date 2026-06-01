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
        [--compare-with <other.jsonl>]   # inter-coder κ + confusion matrix
        [--json]                         # emit structured JSON payload

## --compare-with semantics

When a second coding sheet is supplied, the helper additionally emits
a 3x3 confusion matrix (rows = --sheet's categories, cols =
--compare-with's), Cohen's κ with a Landis-Koch interpretation, and
the observed/expected agreement totals. The κ is computed by hand
from raw counts — no sklearn dependency.

Only OCIDs present in BOTH sheets feed the κ + matrix. Records that
appear in just one sheet are reported separately so a partial-overlap
double-coding pass doesn't silently bias the agreement statistic.

The single-sheet output path (no --compare-with) is unchanged.
"""
from __future__ import annotations

import argparse
import json as _json
import sys
from collections import Counter
from dataclasses import dataclass, field
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
# Inter-coder comparison (--compare-with)
# ---------------------------------------------------------------------------
#
# κ is computed by hand to keep the diagnostic module lightweight (no
# sklearn). The formula matches the orchestrator's hand computation
# against the 2026-05-29 inter-coder pass:
#
#   p_o   = sum_diagonal / total
#   p_e   = Σ_k (row_marginal_k * col_marginal_k) / total**2
#   κ     = (p_o - p_e) / (1 - p_e)
#
# Landis-Koch interpretation thresholds (1977) are the canonical
# qualitative banding for κ. They're an interpretive convenience, not
# load-bearing for any pre-registered prediction.


LANDIS_KOCH_THRESHOLDS: tuple[tuple[float, str], ...] = (
    # Ordered low → high. First band whose upper bound >= κ wins.
    (0.0, "Less than chance"),
    (0.20, "Slight"),
    (0.40, "Fair"),
    (0.60, "Moderate"),
    (0.80, "Substantial"),
    (1.0001, "Almost perfect"),  # 1.0001 so κ == 1.0 lands here
)


def landis_koch_label(kappa: float) -> str:
    """Return the Landis-Koch qualitative band for a κ value.

    κ < 0 → "Less than chance" (worse than random agreement).
    κ ∈ [0, 0.2)  → "Slight"
    κ ∈ [0.2, 0.4) → "Fair"
    κ ∈ [0.4, 0.6) → "Moderate"
    κ ∈ [0.6, 0.8) → "Substantial"
    κ ∈ [0.8, 1.0] → "Almost perfect"
    """
    if kappa < 0:
        return "Less than chance"
    for upper, label in LANDIS_KOCH_THRESHOLDS:
        if kappa < upper:
            return label
    # Unreachable given the 1.0001 sentinel, but keep belt-and-braces.
    return "Almost perfect"  # pragma: no cover


@dataclass(frozen=True)
class ComparisonReport:
    """Inter-coder agreement aggregation, ready for printing or JSON.

    ``matrix[i][j]`` is the count of records where the --sheet coder
    assigned category ``categories[i]`` and the --compare-with coder
    assigned category ``categories[j]``. The category axis is sorted
    ascending so the matrix shape is deterministic regardless of which
    categories actually appeared.
    """

    sheet_label: str            # display name for --sheet (e.g. file basename)
    compare_label: str          # display name for --compare-with
    categories: tuple[int, ...]  # axis order (typically (1, 2, 3))
    matrix: tuple[tuple[int, ...], ...]
    total: int                  # records in the intersection
    sheet_only_ocids: tuple[str, ...]   # in --sheet but not --compare-with
    compare_only_ocids: tuple[str, ...]  # in --compare-with but not --sheet
    p_o: float                  # observed agreement
    p_e: float                  # expected agreement under independence
    kappa: float                # Cohen's κ
    arm: str                    # arm scope this comparison was filtered to

    @property
    def disagreement_count(self) -> int:
        """Off-diagonal sum — records where the two coders disagreed."""
        diag = sum(self.matrix[i][i] for i in range(len(self.categories)))
        return self.total - diag

    @property
    def landis_koch(self) -> str:
        return landis_koch_label(self.kappa)


def _index_by_ocid(entries: list[CodedEntry], arm: str) -> dict[str, CodedEntry]:
    """Build {ocid -> entry} for one arm; raises on duplicate OCID.

    Duplicate (ocid, arm) pairs in a single sheet mean a coder coded the
    same record twice without going through the resume path — surface
    that loudly rather than silently picking last-write-wins, since
    inter-coder κ is meaningless on an ambiguous sheet.
    """
    out: dict[str, CodedEntry] = {}
    for entry in entries:
        if entry.arm != arm:
            continue
        if entry.ocid in out:
            raise RubricSchemaError(
                f"Sheet contains duplicate row for OCID {entry.ocid!r} on arm "
                f"{arm!r}; cannot compute inter-coder κ on an ambiguous sheet."
            )
        out[entry.ocid] = entry
    return out


def compare_sheets(
    *,
    sheet_entries: list[CodedEntry],
    compare_entries: list[CodedEntry],
    arm: str,
    sheet_label: str,
    compare_label: str,
) -> ComparisonReport:
    """Compute the 3x3 confusion matrix + Cohen's κ between two sheets.

    Only OCIDs present in BOTH sheets (for the given ``arm``) feed the
    κ. OCIDs in one sheet only are reported separately. The category
    axis is the sorted VALID_CATEGORIES tuple (i.e. (1, 2, 3)).

    κ is computed manually:

        p_o = diagonal / total
        p_e = Σ_k (row_marginal_k * col_marginal_k) / total**2
        κ   = (p_o - p_e) / (1 - p_e)

    With ``total == 0`` (no overlap) we return κ = 0.0 — undefined-but-
    reported, since the caller already has the sheet-only OCID lists to
    explain the empty intersection.
    """
    sheet_idx = _index_by_ocid(sheet_entries, arm)
    compare_idx = _index_by_ocid(compare_entries, arm)
    sheet_ocids = set(sheet_idx.keys())
    compare_ocids = set(compare_idx.keys())
    shared = sorted(sheet_ocids & compare_ocids)
    sheet_only = sorted(sheet_ocids - compare_ocids)
    compare_only = sorted(compare_ocids - sheet_ocids)

    categories = tuple(sorted(VALID_CATEGORIES))
    n_cats = len(categories)
    matrix: list[list[int]] = [[0] * n_cats for _ in range(n_cats)]
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    for ocid in shared:
        a = sheet_idx[ocid]
        b = compare_idx[ocid]
        if a.category not in cat_to_idx or b.category not in cat_to_idx:
            raise RubricSchemaError(
                f"Sheet contains invalid category for OCID {ocid!r}: "
                f"sheet={a.category!r}, compare={b.category!r}."
            )
        matrix[cat_to_idx[a.category]][cat_to_idx[b.category]] += 1

    total = len(shared)
    if total == 0:
        p_o = 0.0
        p_e = 0.0
        kappa = 0.0
    else:
        diag = sum(matrix[i][i] for i in range(n_cats))
        p_o = diag / total
        row_marginals = [sum(matrix[i]) for i in range(n_cats)]
        col_marginals = [sum(matrix[i][j] for i in range(n_cats)) for j in range(n_cats)]
        p_e = sum(
            row_marginals[k] * col_marginals[k] for k in range(n_cats)
        ) / (total * total)
        if p_e >= 1.0:
            # Both coders assigned every record to the same single category
            # — the denominator collapses. By convention κ = 1.0 only if
            # they also agree on every record (p_o == 1), else κ = 0.
            kappa = 1.0 if p_o == 1.0 else 0.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

    return ComparisonReport(
        sheet_label=sheet_label,
        compare_label=compare_label,
        categories=categories,
        matrix=tuple(tuple(row) for row in matrix),
        total=total,
        sheet_only_ocids=tuple(sheet_only),
        compare_only_ocids=tuple(compare_only),
        p_o=p_o,
        p_e=p_e,
        kappa=kappa,
        arm=arm,
    )


def render_comparison(report: ComparisonReport) -> str:
    """Format the comparison block. Mirrors the orchestrator's manual
    confusion-matrix shape from the 2026-05-29 inter-coder analysis."""
    cat_short = {1: "names", 2: "intent", 3: "partial"}
    cats = report.categories

    lines: list[str] = []
    lines.append(f"Inter-coder comparison — arm={report.arm}")
    lines.append(f"  --sheet         : {report.sheet_label}")
    lines.append(f"  --compare-with  : {report.compare_label}")
    lines.append(f"  shared OCIDs    : {report.total}")
    if report.sheet_only_ocids:
        lines.append(
            f"  sheet-only      : {len(report.sheet_only_ocids)} "
            f"(NOT counted in κ)"
        )
    if report.compare_only_ocids:
        lines.append(
            f"  compare-only    : {len(report.compare_only_ocids)} "
            f"(NOT counted in κ)"
        )
    lines.append("")

    # 3x3 confusion matrix. Rows = --sheet category, cols = --compare-with.
    header_cells = " ".join(f"{cat_short[c]:>7}" for c in cats)
    lines.append("  Confusion matrix (rows=--sheet, cols=--compare-with):")
    lines.append(f"                  {header_cells}    row_total")
    for i, row_cat in enumerate(cats):
        row_cells = " ".join(f"{report.matrix[i][j]:>7d}" for j in range(len(cats)))
        row_total = sum(report.matrix[i])
        lines.append(
            f"    {cat_short[row_cat]:<7} (cat {row_cat}): "
            f"{row_cells}    {row_total:>5d}"
        )
    col_totals = [sum(report.matrix[i][j] for i in range(len(cats))) for j in range(len(cats))]
    col_total_cells = " ".join(f"{c:>7d}" for c in col_totals)
    lines.append(f"    col_total       : {col_total_cells}    {report.total:>5d}")
    lines.append("")

    # Disagreement structure.
    lines.append(
        f"  Disagreements: {report.disagreement_count} of {report.total} "
        f"records ({(report.disagreement_count / report.total * 100.0) if report.total else 0.0:.1f}%)"
    )
    lines.append("")

    # κ + interpretation.
    lines.append(f"  Observed agreement (p_o): {report.p_o:.4f}")
    lines.append(f"  Expected agreement (p_e): {report.p_e:.4f}")
    lines.append(
        f"  Cohen's κ              : {report.kappa:+.4f}  "
        f"({report.landis_koch})"
    )
    return "\n".join(lines)


def comparison_to_json_payload(report: ComparisonReport) -> dict:
    """Serialise a ComparisonReport into a JSON-ready dict. Categories
    are surfaced as a string-keyed nested dict so the matrix is human-
    readable in a JSON dump."""
    cats = report.categories
    matrix_dict = {
        str(cats[i]): {str(cats[j]): report.matrix[i][j] for j in range(len(cats))}
        for i in range(len(cats))
    }
    return {
        "arm": report.arm,
        "sheet_label": report.sheet_label,
        "compare_label": report.compare_label,
        "categories": list(cats),
        "matrix": matrix_dict,
        "total": report.total,
        "sheet_only_ocids": list(report.sheet_only_ocids),
        "compare_only_ocids": list(report.compare_only_ocids),
        "disagreement_count": report.disagreement_count,
        "p_o": report.p_o,
        "p_e": report.p_e,
        "kappa": report.kappa,
        "landis_koch": report.landis_koch,
    }


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
    parser.add_argument(
        "--compare-with",
        type=Path,
        default=None,
        metavar="OTHER_SHEET",
        help=(
            "Optional second coding sheet (JSON-lines). When supplied, "
            "the helper additionally emits a 3x3 confusion matrix + "
            "Cohen's κ (with Landis-Koch interpretation) between the "
            "two sheets for each arm in scope. Only OCIDs present in "
            "BOTH sheets feed the κ; sheet-only OCIDs are reported "
            "separately."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Emit a structured JSON payload to stdout instead of plain "
            "text. Includes per-arm aggregation + (if --compare-with is "
            "given) the comparison block. The plain-text default stays "
            "the human-readable shape."
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
        compare_entries: list[CodedEntry] | None = None
        if args.compare_with is not None:
            compare_entries = read_sheet(args.compare_with)
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

    if args.json:
        # Structured payload: one entry per arm. Comparison block (if
        # any) lives under "comparison" — mirrors verify_dry_run_e3.py's
        # pattern of plain-text-by-default, --json for machine-readable.
        payload: dict = {"arms": []}
        for arm in arms_in_scope:
            report = aggregate(entries, arm, bands)
            arm_entry: dict = {
                "arm": arm,
                "total": report.total,
                "counts": {str(c): report.counts.get(c, 0) for c in sorted(VALID_CATEGORIES)},
                "pct": {str(c): report.pct(c) for c in sorted(VALID_CATEGORIES)},
                "p5_confirmed": report.p5_confirmed(),
                "p5_falsified": report.p5_falsified(),
                "p5_disposition": report.p5_disposition(),
                "bands": {
                    "intent_floor_pct": bands.intent_floor_pct,
                    "names_cap_pct": bands.names_cap_pct,
                    "names_falsify_pct": bands.names_falsify_pct,
                },
            }
            if compare_entries is not None:
                cmp = compare_sheets(
                    sheet_entries=entries,
                    compare_entries=compare_entries,
                    arm=arm,
                    sheet_label=args.sheet.name,
                    compare_label=args.compare_with.name,
                )
                arm_entry["comparison"] = comparison_to_json_payload(cmp)
            payload["arms"].append(arm_entry)
        out.write(_json.dumps(payload, indent=2, sort_keys=True))
        out.write("\n")
        return 0

    for idx, arm in enumerate(arms_in_scope):
        if idx > 0:
            out.write("\n" + ("=" * 60) + "\n\n")
        report = aggregate(entries, arm, bands)
        out.write(render_report(report, expected_n=args.expected_n))
        out.write("\n")
        if compare_entries is not None:
            cmp = compare_sheets(
                sheet_entries=entries,
                compare_entries=compare_entries,
                arm=arm,
                sheet_label=args.sheet.name,
                compare_label=args.compare_with.name,
            )
            out.write("\n" + ("-" * 60) + "\n\n")
            out.write(render_comparison(cmp))
            out.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
