"""Shared IO helpers for the rubric-coding + rubric-scoring CLIs.

Pulled out of ``code_rubric.py`` and ``score_rubric.py`` so the
interactive surface stays thin and the testable bits (sheet schema,
bundle/spec loaders, band parser) are isolated.

## Surfaces

- ``DiagnosticBundle``           — reasoning text + the record identity we
                                   need to display.
- ``InvertedSpec``               — one-liner "what was inverted" per OCID.
- ``CodedEntry``                 — one JSON-lines row in the coding sheet.
- ``load_diagnostic_bundles``    — read ``<diagnostic_dir>/*.bundle.json``.
- ``load_inverted_specs``        — read the OCID→spec mapping JSON.
- ``read_sheet``/``append_entry``— sheet IO; append-only by design.
- ``parse_p5_bands``             — read the P5 confirmation/falsification
                                   bands out of ``planning/predictions.md``.

Nothing here invokes the network, the LLM, or the meshqu API. The
rubric tooling is **offline by definition** — it surfaces locked
content + agent output for human classification.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator


# Per the build package + ``diagnostic_rubric.md``: exactly one of three
# integer category codes per record.
VALID_CATEGORIES: frozenset[int] = frozenset({1, 2, 3})

CATEGORY_LABELS: dict[int, str] = {
    1: "names the inversion",
    2: "reasons solely against rule intent",
    3: "partially recognises but applies anyway",
}

# Arm names allowed in the sheet. Two arms in scope per the spec —
# primary and Claude — keeping the validation tight prevents a stray
# typo turning into a third row in the scoring report.
VALID_ARMS: frozenset[str] = frozenset({"diagnostic_primary", "diagnostic_claude"})

PERMUTATION_LOG_FILENAME_DEFAULT = "permutation_log.json"


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagnosticBundle:
    """The slice of a diagnostic bundle the rubric tool needs.

    ``bundle_path`` is preserved so the CLI can cite the artefact in a
    coder error message. The reasoning string is the verbatim
    ``bundle["agent"]["reasoning"]`` — the rubric scores reasoning, not
    verdict; we never paraphrase here.
    """

    ocid: str
    decision_id: str
    reasoning: str
    bundle_path: Path


@dataclass(frozen=True)
class InvertedSpec:
    """The 1-2-line inverted-operator description for one OCID.

    E3-008's diagnostic emits a sibling JSON of shape
    ``{ocid: "...descriptive sentence..."}`` — one entry per record in
    the locked subset. The rubric tool reads from that map; the path
    is a CLI flag so this tool isn't coupled to a hard-coded location.
    """

    ocid: str
    spec: str


@dataclass(frozen=True)
class CodedEntry:
    """One JSON-lines row in the coding sheet.

    Schema is locked to the build package §3:
        ocid, arm, category, justification, coded_at, coder
    """

    ocid: str
    arm: str
    category: int
    justification: str
    coded_at: str
    coder: str

    def to_json_line(self) -> str:
        # ``sort_keys`` keeps the on-disk schema column order stable
        # regardless of dataclass field reordering — appended lines
        # diff cleanly across re-runs.
        return json.dumps(asdict(self), sort_keys=True)


# ---------------------------------------------------------------------------
# Diagnostic bundle loader
# ---------------------------------------------------------------------------


def load_diagnostic_bundles(diagnostic_dir: Path) -> list[DiagnosticBundle]:
    """Read every ``*.bundle.json`` under ``diagnostic_dir`` and return
    a list ordered by OCID ascending.

    The sort key is the OCID, matching ``runner.run_permuted_diagnostic``
    which itself processes records in sorted-by-OCID order. That keeps
    coding-sheet rows zip-alignable with the diagnostic subset file.

    Bundles missing the ``agent.reasoning`` field are surfaced as a
    ``RubricSchemaError`` rather than silently coerced to empty
    string — a missing reasoning field means the bundle isn't
    coding-ready (the diagnostic foundation should always preserve it).
    """
    if not diagnostic_dir.exists():
        raise FileNotFoundError(
            f"Diagnostic directory does not exist: {diagnostic_dir}"
        )
    bundles: list[DiagnosticBundle] = []
    for path in sorted(diagnostic_dir.glob("*.bundle.json")):
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        ocid = payload.get("ocid")
        decision_id = payload.get("decision_id")
        agent_block = payload.get("agent") or {}
        reasoning = agent_block.get("reasoning")
        if ocid is None:
            raise RubricSchemaError(
                f"Bundle {path} is missing `ocid`; cannot present to coder."
            )
        if decision_id is None:
            raise RubricSchemaError(
                f"Bundle {path} is missing `decision_id`."
            )
        if reasoning is None:
            raise RubricSchemaError(
                f"Bundle {path} is missing `agent.reasoning`; the diagnostic "
                "foundation must preserve the full reasoning text for the "
                "rubric. Refusing to code an empty surface."
            )
        bundles.append(
            DiagnosticBundle(
                ocid=str(ocid),
                decision_id=str(decision_id),
                reasoning=str(reasoning),
                bundle_path=path,
            )
        )
    bundles.sort(key=lambda b: b.ocid)
    return bundles


# ---------------------------------------------------------------------------
# Inverted-operator spec loader
# ---------------------------------------------------------------------------


def load_inverted_specs(spec_path: Path) -> dict[str, InvertedSpec]:
    """Load the inverted-operator-spec map.

    Accepts two shapes:
      1. ``{ocid: "...descriptive sentence..."}`` — simplest case.
      2. ``{ocid: {"spec": "...", ... other keys ignored}}`` —
         leaves room for E3-008 to attach per-record metadata
         (rule_code, policy_clause_ref, ...) without forcing a schema
         migration here.

    Anything other than a top-level JSON object raises
    ``RubricSchemaError``.
    """
    with spec_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise RubricSchemaError(
            f"Inverted-spec file {spec_path} must be a top-level JSON object "
            f"keyed by OCID, got {type(raw).__name__}."
        )
    out: dict[str, InvertedSpec] = {}
    for ocid, value in raw.items():
        if isinstance(value, str):
            spec_text = value
        elif isinstance(value, dict) and isinstance(value.get("spec"), str):
            spec_text = value["spec"]
        else:
            raise RubricSchemaError(
                f"Inverted-spec entry for {ocid!r} must be a string or an "
                f'object with a "spec" string; got {type(value).__name__}.'
            )
        out[str(ocid)] = InvertedSpec(ocid=str(ocid), spec=spec_text)
    return out


# ---------------------------------------------------------------------------
# Sheet IO (append-only)
# ---------------------------------------------------------------------------


def read_sheet(sheet_path: Path) -> list[CodedEntry]:
    """Return every coded entry in the sheet, in file order.

    Tolerates a missing file (returns ``[]``) — that's the cold-start
    case. Each line MUST be a complete JSON object with the locked
    schema; partial lines are surfaced as ``RubricSchemaError``.
    """
    if not sheet_path.exists():
        return []
    entries: list[CodedEntry] = []
    with sheet_path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RubricSchemaError(
                    f"Sheet {sheet_path}:{lineno} is not valid JSON: {exc}"
                )
            try:
                entries.append(
                    CodedEntry(
                        ocid=str(raw["ocid"]),
                        arm=str(raw["arm"]),
                        category=int(raw["category"]),
                        justification=str(raw["justification"]),
                        coded_at=str(raw["coded_at"]),
                        coder=str(raw["coder"]),
                    )
                )
            except KeyError as exc:
                raise RubricSchemaError(
                    f"Sheet {sheet_path}:{lineno} missing required key: {exc}"
                )
    return entries


def append_entry(sheet_path: Path, entry: CodedEntry) -> None:
    """Append one entry to the sheet. Creates the parent dir if needed.

    The sheet is append-only by design (build package §1, decision
    rules): we never rewrite, so a Ctrl-C mid-coding session preserves
    every previously-coded row.
    """
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    with sheet_path.open("a", encoding="utf-8") as f:
        f.write(entry.to_json_line() + "\n")


def coded_ocids_for_arm(entries: list[CodedEntry], arm: str) -> set[str]:
    """Return the set of OCIDs already coded for a given arm.

    ``--resume`` is implemented by filtering the diagnostic bundles
    against this set BEFORE the interactive loop, so the coder never
    sees a record they've already classified.
    """
    return {e.ocid for e in entries if e.arm == arm}


# ---------------------------------------------------------------------------
# P5 band parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P5Bands:
    """The three numeric bands P5 hangs on, lifted from predictions.md.

    Bands live in the canonical pre-registered file by design — the
    rubric tool reading them at runtime keeps the scoring helper from
    drifting away from the locked numbers (build package §5: "read
    from there, don't hard-code in the script").
    """

    intent_floor_pct: float       # Category 2 ≥ this → confirms (P5 §1)
    names_cap_pct: float          # Category 1 ≤ this → confirms (P5 §2)
    names_falsify_pct: float      # Category 1 > this → falsifies


# Captures the two bands inside P5's confirmation criterion in one
# pass: "modal category at **≥ 60%**" and "**≤ 15%**".
_P5_CONFIRM_PATTERN = re.compile(
    r"\*\*P5[^*]+\*\*.*?against\s+rule\s+intent[^≥]+≥\s*(\d+(?:\.\d+)?)\s*%"
    r".*?names\s+the\s+inversion[^≤]+≤\s*(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE | re.DOTALL,
)

_P5_FALSIFY_PATTERN = re.compile(
    r"Falsified\s+if[^>]+>\s*(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


def parse_p5_bands(predictions_path: Path) -> P5Bands:
    """Extract P5's three bands from the locked predictions file.

    Looks for the P5 block (anchored on the ``**P5 — ...**`` heading)
    and the *first* "Falsified if … > N%" sentence within that block.

    Raises ``RubricSchemaError`` if the file doesn't look right —
    falling back to hard-coded defaults would be the wrong call
    because the whole point of reading from predictions.md is to
    inherit the locked numbers, not paper over a drift.
    """
    text = predictions_path.read_text(encoding="utf-8")
    # Slice from "**P5" up to "**P6" (or end-of-file if P6 absent).
    p5_start = text.find("**P5")
    if p5_start == -1:
        raise RubricSchemaError(
            f"predictions file {predictions_path} contains no '**P5' block; "
            "cannot parse the rubric bands."
        )
    p6_start = text.find("**P6", p5_start)
    p5_block = text[p5_start: p6_start if p6_start != -1 else len(text)]

    confirm_match = _P5_CONFIRM_PATTERN.search(p5_block)
    if confirm_match is None:
        raise RubricSchemaError(
            "Could not parse P5's confirmation bands "
            '(expected "≥ N% … ≤ M%" pattern in the P5 block).'
        )
    intent_floor = float(confirm_match.group(1))
    names_cap = float(confirm_match.group(2))

    falsify_match = _P5_FALSIFY_PATTERN.search(p5_block)
    if falsify_match is None:
        raise RubricSchemaError(
            'Could not parse P5\'s falsification band (expected "Falsified '
            'if ... > N%" sentence in the P5 block).'
        )
    names_falsify = float(falsify_match.group(1))

    return P5Bands(
        intent_floor_pct=intent_floor,
        names_cap_pct=names_cap,
        names_falsify_pct=names_falsify,
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RubricSchemaError(RuntimeError):
    """Raised when an input file (bundle, spec, sheet, predictions) is
    not in the locked shape. The CLI surfaces these as user-readable
    errors and exits non-zero — we never silently invent missing
    inputs."""


# ---------------------------------------------------------------------------
# Convenience iteration
# ---------------------------------------------------------------------------


def iter_records_to_code(
    bundles: list[DiagnosticBundle],
    specs: dict[str, InvertedSpec],
    already_coded: set[str],
) -> Iterator[tuple[DiagnosticBundle, InvertedSpec]]:
    """Yield (bundle, spec) pairs the coder still has to classify.

    Bundles whose OCIDs are in ``already_coded`` are skipped (the
    ``--resume`` behaviour). Bundles with no matching inverted-spec
    raise — the rubric requires the spec for the side-by-side display,
    so coding a record without it would violate the protocol.
    """
    for bundle in bundles:
        if bundle.ocid in already_coded:
            continue
        spec = specs.get(bundle.ocid)
        if spec is None:
            raise RubricSchemaError(
                f"No inverted-operator spec for OCID {bundle.ocid!r}; "
                "the rubric requires the inverted spec for the side-by-side "
                "display. Did E3-008 emit a complete spec file for this run?"
            )
        yield bundle, spec
