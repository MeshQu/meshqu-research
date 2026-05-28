"""E3-007 — Diagnostic subset selector (n=100).

Returns the 100 OCIDs whose ``sha256(ocid)`` hex digests sort lowest over
the frozen 283-record E1 corpus. Same 100 records run on the primary
arm AND on the Claude cross-model arm (record-matched, per the
experiment design's "Locked parameters" section).

## Why this rule

We need a deterministic, reproducible 100-record subset. The whole
diagnostic claim ("primary vs Claude agree on X / disagree on Y") is
only meaningful if the *same* records are scored on both arms across
re-runs, on Sam's laptop, in CI, and six months from now in the
post-hoc audit pass.

Three properties the rule has to deliver:

1. **Independent of any verdict.** No filtering by E1's MeshQu output
   would risk picking records that already favour one arm; the subset
   must be carved purely from input identity.
2. **Independent of tenant / policy.** OCIDs are externally-supplied
   identifiers; the subset must remain valid even if the policy is
   re-locked or a different tenant is run.
3. **Byte-stable across Python versions, platforms, and processes.**
   ``hash()`` is salt-randomised (PYTHONHASHSEED); ``random.sample``
   needs a seed and even then differs across Python minor releases.
   ``hashlib.sha256`` is platform-stable, language-stable, and
   FIPS-locked.

The locked rule (see ``planning/experiment_design.md`` §"Locked
parameters → Diagnostic subset selection rule"):

    > "the 100 records whose sha256(ocid) hex digests sort lowest,
    >  over the frozen 283-corpus. Deterministic, reproducible, no
    >  selection bias, and independent of any verdict."

## Why sort by hex string, not int

``sha256(b).hexdigest()`` returns a 64-char lowercase hex string. We
sort that string ascending (lexicographic). We deliberately do NOT
convert to int and sort numerically, because:

- For a fixed-width hex string of equal length on every record (64
  chars), lex sort over [0-9a-f] is identical in *ordering* to int
  comparison. So in practice both produce the same 100 picks.
- But the locked artifact records the digest as a string ("0006…"),
  and the audit story is cleaner if "sort the strings" is what the
  selector literally does — no int round-trip the auditor has to
  trust.

If you ever change the digest serialisation (e.g. raw bytes vs hex),
re-check this — leading-zero bytes/strings sort differently in the two
representations.

## Output order is part of the artifact

The returned list is in sha256-digest-ascending order — *not* OCID-
ascending. Downstream consumers (E3-008's diagnostic runner) can rely
on this order; shuffling it would invalidate any pre-computed
record-by-record cross-arm join.

## Stop conditions

- Corpus size != 283 — STOP. The frozen archive has drifted.
- Duplicate OCID in the input list — STOP. Cache adapter promises
  uniqueness; a duplicate is a bug upstream, not something to silently
  de-dup here.
- Two OCIDs at positions n-1 and n share the same sha256 hex digest —
  STOP. 256-bit collision is astronomically unlikely but worth
  catching: the cut-off would be ambiguous.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from meshqu_runner.substrate_cache import EXPECTED_RECORD_COUNT, load_cached_records


# ---------------------------------------------------------------------------
# Locked constants. Bumping any of these would change the 100 records
# selected and would invalidate the v0.3-predictions-locked tag.
# ---------------------------------------------------------------------------

DIAGNOSTIC_SUBSET_SIZE = 100
"""Locked at the design's "Locked parameters" section. The diagnostic
runs the same 100 records on the primary arm and on Claude. Expansion
is a tag amendment, not a code change."""

SELECTION_RULE = "lowest-100 by sha256(ocid) over the frozen 283-corpus"
"""The literal phrasing committed into ``planning/diagnostic_subset.json``.
Quoted verbatim from ``planning/experiment_design.md`` §"Locked
parameters" so audit can grep for it across artifacts."""

CORPUS_SOURCE = "procurement-decisions/results/runs/dry-run-7ddf7274-.../decision_traces.jsonl"
"""Frozen E1 archive path, relative to the repo root. Same archive E2
and E3 both bind against (see ``substrate_cache.E1_ARCHIVE_RUN_ID``)."""

LOCKED_TAG = "v0.3-predictions-locked"
"""The tag this artifact binds into. If the v0.3 tag is amended, this
constant gets bumped as part of the amendment."""

ARTIFACT_RELATIVE_PATH = "procurement-context-disambiguation/planning/diagnostic_subset.json"
"""Committed-artifact path, relative to the repo root."""


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------


class DiagnosticSubsetError(RuntimeError):
    """A stop-condition fired during subset selection.

    Raised rather than silently coercing — selection-bias-free is a
    load-bearing methodological claim and we don't want a fallback path
    that quietly papers over a drifted corpus."""


def _digest(ocid: str) -> str:
    """sha256 hex digest of the UTF-8 bytes of ``ocid``.

    Encoding is explicit so the locked rule "sha256 of UTF-8 bytes"
    can never silently become "sha256 of platform default encoding"
    on a future Python.
    """
    return hashlib.sha256(ocid.encode("utf-8")).hexdigest()


def select_diagnostic_subset(
    corpus_ocids: Iterable[str],
    n: int = DIAGNOSTIC_SUBSET_SIZE,
) -> list[str]:
    """Return the ``n`` OCIDs whose sha256 hex digests sort lowest.

    Deterministic and reproducible: same input multiset → same output
    list (order included).

    Parameters
    ----------
    corpus_ocids:
        Iterable of OCID strings. Must contain no duplicates (the
        substrate cache promises this on the 283-corpus); a duplicate
        triggers ``DiagnosticSubsetError``.
    n:
        Subset size. Defaults to ``DIAGNOSTIC_SUBSET_SIZE`` (100).
        Must be ``<= len(corpus_ocids)``.

    Returns
    -------
    list[str]
        OCIDs in *hash-ascending* order (not OCID-ascending). The
        order is itself part of the locked artifact.

    Raises
    ------
    DiagnosticSubsetError
        On duplicate OCIDs, on ``n`` larger than the corpus, or on a
        hash collision at the cut-off boundary (positions ``n-1`` and
        ``n`` share a digest — astronomically unlikely at sha256, but
        worth catching so the cut isn't ambiguous).
    """
    ocids = list(corpus_ocids)

    # Duplicate guard. Upstream (substrate_cache) already promises
    # unique OCIDs; this is a defence-in-depth check so the selector
    # cannot silently shadow an upstream bug.
    if len(set(ocids)) != len(ocids):
        seen: set[str] = set()
        dups: list[str] = []
        for o in ocids:
            if o in seen:
                dups.append(o)
            seen.add(o)
        raise DiagnosticSubsetError(
            f"Duplicate OCID(s) in input corpus: {dups[:5]}"
            + (" (and more)" if len(dups) > 5 else "")
            + ". The selector assumes unique OCIDs."
        )

    if n > len(ocids):
        raise DiagnosticSubsetError(
            f"Requested subset size n={n} exceeds corpus size {len(ocids)}."
        )

    # Sort by sha256 hex digest ascending. Stable ordering — Python's
    # sort is Timsort, which is stable; identical keys would preserve
    # input order, but we expressly fail below if any tie exists at
    # the cut boundary, so stability never has a chance to leak
    # input-order dependence into the artifact.
    keyed = [(_digest(o), o) for o in ocids]
    keyed.sort(key=lambda t: t[0])

    # Collision guard at the cut boundary. Two distinct OCIDs at
    # positions n-1 and n with the same hash would make the cut
    # ambiguous (which one is "the 100th"?). Astronomically unlikely
    # at sha256 over 283 inputs — but the test exists to make the
    # claim falsifiable.
    if n < len(keyed) and keyed[n - 1][0] == keyed[n][0]:
        raise DiagnosticSubsetError(
            f"sha256 collision at cut-off boundary: positions {n - 1} and {n} "
            f"share digest {keyed[n - 1][0]!r}. Ambiguous cut — surface."
        )

    return [ocid for _, ocid in keyed[:n]]


def load_corpus_ocids(repo_dir: Path) -> list[str]:
    """Enumerate the 283-corpus OCIDs via the substrate cache.

    Pure disk read (the cache reader is read-only by contract). Returns
    OCIDs in the order the cache exposes them — irrelevant to the
    selector, which re-sorts by digest. We re-export this as a separate
    function so tests can construct the same input the CLI uses without
    going through ``main()``.
    """
    records = load_cached_records(repo_dir)
    if len(records) != EXPECTED_RECORD_COUNT:
        # substrate_cache already enforces this, but the duplicate
        # check is cheap and the diagnostic-specific message helps the
        # audit story.
        raise DiagnosticSubsetError(
            f"Frozen corpus returned {len(records)} records; "
            f"expected {EXPECTED_RECORD_COUNT}. The frozen archive may have "
            f"drifted from the v0.3-predictions-locked state."
        )
    return [r.ocid for r in records]


# ---------------------------------------------------------------------------
# Artifact emission
# ---------------------------------------------------------------------------


def build_artifact(
    ocids: list[str],
    *,
    generated_at: str | None = None,
) -> dict:
    """Build the JSON-serialisable artifact payload.

    Separated from emission so tests can assert on the payload shape
    without depending on stdout / file IO.

    ``generated_at`` is overridable so tests can pin a deterministic
    timestamp; production CLI uses ``datetime.now(timezone.utc)``.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment": "E3",
        "selection_rule": SELECTION_RULE,
        "corpus_source": CORPUS_SOURCE,
        "n": len(ocids),
        "tag": LOCKED_TAG,
        "generated_at": generated_at,
        "ocids": list(ocids),
    }


def emit_artifact_json(artifact: dict) -> str:
    """Serialise the artifact to the canonical-on-disk JSON form.

    Two reasons we use ``indent=2`` + trailing newline + ``sort_keys=False``:

    - **Indent**: the file is human-readable in PR diffs (auditors
      grep the OCID list).
    - **Trailing newline**: POSIX text-file convention; avoids "no
      newline at end of file" diffs.
    - **No sort_keys**: the top-level key order ("experiment",
      "selection_rule", ...) is hand-chosen to read narratively. We
      do NOT sort because that would put "generated_at" before
      "n" before "ocids" — auditors expect to see the rule and corpus
      source first.

    The OCID list itself is in selection order (hash-ascending), which
    matters and is enforced by the selector.
    """
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_repo_dir() -> Path:
    """Walk up from this file to the repo root.

    Layout:
        meshqu-research/                                       <- repo_dir
          procurement-context-disambiguation/
            runner/
              meshqu_runner/
                diagnostic/
                  subset_selector.py                           <- __file__

    Same convention as ``cli.py`` (see ``cli.py:_resolve_repo_dir``-ish
    block at the bottom of that file).
    """
    return Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m meshqu_runner.diagnostic.subset_selector --emit``.

    With ``--emit`` writes the artifact JSON to stdout (suitable for
    ``> planning/diagnostic_subset.json`` redirection per the package
    spec).

    Returns a process exit code. Non-zero on any stop-condition trip.
    """
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.diagnostic.subset_selector",
        description=(
            "E3-007 diagnostic subset selector. Emit the locked n=100 "
            "subset over the frozen 283-corpus."
        ),
    )
    parser.add_argument(
        "--emit",
        action="store_true",
        help="Write the diagnostic_subset.json artifact to stdout.",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=None,
        help=(
            "Repo root override (defaults to auto-resolution from this "
            "file's path). Mostly for tests."
        ),
    )
    args = parser.parse_args(argv)

    if not args.emit:
        parser.print_help(sys.stderr)
        return 2

    repo_dir = args.repo_dir or _resolve_repo_dir()
    try:
        corpus_ocids = load_corpus_ocids(repo_dir)
        subset = select_diagnostic_subset(corpus_ocids)
    except DiagnosticSubsetError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1

    artifact = build_artifact(subset)
    sys.stdout.write(emit_artifact_json(artifact))
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
