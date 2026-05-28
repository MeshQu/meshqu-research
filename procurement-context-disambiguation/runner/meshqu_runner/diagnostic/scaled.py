"""E3-008 — Scaled Permuted-Policy diagnostic surface.

Three pieces that the driver script (``scripts/run_scaled_diagnostic.py``)
and the rubric tool (``meshqu_runner.diagnostic.code_rubric``) consume:

1. ``load_diagnostic_subset()`` — read the **locked** n=100 OCID list
   from ``planning/diagnostic_subset.json``. The runtime path NEVER
   regenerates the subset (Contract #3 from the Wave-2 close-out
   decision log); the selector at
   ``meshqu_runner.diagnostic.subset_selector`` is for re-verification
   + one-time re-emit only.

2. ``build_inverted_operator_spec_payload(...)`` /
   ``emit_inverted_operator_spec(...)`` — produce the
   **inverted-operator-spec** sidecar at
   ``<run_dir>/diagnostic/inverted_operator_spec.json``. This is the
   sibling artefact required by the E3-009 rubric tool — see
   ``meshqu_runner.diagnostic.rubric_io.load_inverted_specs`` for the
   shape contract (PR #91 / decision-log Wave 2 Contract #2).

## Why these live in their own module, not ``diagnostic/runner.py``

The existing ``diagnostic/runner.py`` is E2's 14-record diagnostic
driver — inherited verbatim from the E2 fork and **not** functional in
the E3 fork (it imports ``GOVERNANCE_CONTEXT_LEVEL_FIELD`` from
``multi_pass``, which E3 retired in favour of per-arm receipt fields).
Treating it as the home for E3-008's new surface would either require
fixing that broken import (touching E2-inherited code) or accepting
that import errors during pytest collection.

The Wave-2 lesson is to treat E2-inherited modules as a preserve
bucket — they may carry orphan code from the fork but they shouldn't
be edited to accommodate new functionality. So E3-008's scaled-
diagnostic surface lands in this new sibling module instead. The
``diagnostic/runner.py`` E2 inheritor stays untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Locked paths + filenames
# ---------------------------------------------------------------------------


DIAGNOSTIC_SUBSET_RELATIVE_PATH = (
    "procurement-context-disambiguation/planning/diagnostic_subset.json"
)
"""Path to the locked subset artifact, relative to the repo root. Same
constant as ``subset_selector.ARTIFACT_RELATIVE_PATH``; re-declared
here so the runtime loader is self-contained and doesn't drag the
selector module's substrate-cache import into the diagnostic-arm hot
path."""


INVERTED_OPERATOR_SPEC_FILENAME = "inverted_operator_spec.json"
"""Sibling-artefact filename inside ``<run_dir>/diagnostic/``.

The E3-009 rubric-coding tool (``meshqu_runner.diagnostic.code_rubric``)
expects this file alongside each diagnostic run so the coder can see
"what was inverted for this OCID" without re-deriving the inversion
from scratch. The file is produced once per run, NOT signed (it is
metadata about the policy permutation, not a per-record receipt).

Shape — accepted by ``rubric_io.load_inverted_specs``:

    {
      "<ocid>": {
        "spec": "Permuted policy (seed=0): every rule's primary "
                "condition operator inverted uniformly across all 6 "
                "rules. Inversions: PROC-001-S53: max → min (publication"
                "_delay_days); ...",
        "rules": [
          {"rule_code": "PROC-001-S53", "field": "publication_delay_days",
           "original_operator": "max", "inverted_operator": "min"},
          ...
        ]
      },
      ...
    }

Currently the diagnostic permutes the policy uniformly (every rule's
primary operator flipped) — so every OCID in the subset gets the same
six-rule inversion. We emit one entry per OCID anyway (keyed by OCID
to match the rubric tool's lookup) carrying a per-OCID-stable spec
describing the locked inversion. Future stochastic-variant runs (a
non-zero seed flipping only some rules) would emit per-OCID-distinct
specs naturally with no shape change here.
"""


# ---------------------------------------------------------------------------
# Subset loader — runtime path reads the locked JSON
# ---------------------------------------------------------------------------


def load_diagnostic_subset(repo_dir: Path | None = None) -> list[str]:
    """Return the **locked** n=100 OCID list, in selection order.

    Reads from ``planning/diagnostic_subset.json`` — the committed
    artefact bound by ``v0.3-predictions-locked``. Does NOT call the
    selector module at runtime; the JSON is the canonical source so
    the subset is deterministically auditable from the committed file
    alone (no corpus-cache dependency at dispatch time).

    Stop conditions:

    - Missing file → ``FileNotFoundError`` (the v0.3 tag promises it
      exists; absence indicates a checkout problem).
    - Malformed JSON → ``json.JSONDecodeError`` (the file should
      always parse).
    - Missing ``ocids`` key → ``KeyError`` (the artefact is malformed).
    - ``len(ocids) != 100`` → ``ValueError`` (the locked subset is
      n=100; any other count means the file has drifted from the
      v0.3 lock).

    Parameters
    ----------
    repo_dir:
        Repo root override. Defaults to auto-resolution from this file
        (``meshqu-research/`` — same convention as
        ``subset_selector._resolve_repo_dir``).
    """
    if repo_dir is None:
        # __file__ → meshqu-research/procurement-context-disambiguation
        # /runner/meshqu_runner/diagnostic/scaled.py → 5 parents up.
        repo_dir = Path(__file__).resolve().parents[4]
    subset_path = repo_dir / DIAGNOSTIC_SUBSET_RELATIVE_PATH
    if not subset_path.exists():
        raise FileNotFoundError(
            f"Locked diagnostic subset file is missing: {subset_path}. "
            "E3-007 must have emitted it before E3-008 runs. Tag "
            "v0.3-predictions-locked binds this file."
        )
    payload = json.loads(subset_path.read_text(encoding="utf-8"))
    if "ocids" not in payload:
        raise KeyError(
            f"Locked diagnostic subset file {subset_path} is missing the "
            "'ocids' key. File has drifted from the v0.3 lock."
        )
    ocids = list(payload["ocids"])
    if len(ocids) != 100:
        raise ValueError(
            f"Locked diagnostic subset has n={len(ocids)} entries; "
            f"expected 100. File has drifted from the v0.3 lock at "
            f"{subset_path}."
        )
    return ocids


# ---------------------------------------------------------------------------
# Inverted-operator-spec sidecar
# ---------------------------------------------------------------------------


def build_inverted_operator_spec_payload(
    *,
    ocids: Sequence[str],
    seed: int,
    permutation_log_entries: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the inverted-operator-spec sidecar payload.

    One entry per OCID — same six-rule inversion repeated across the
    subset (because the diagnostic permutes the *policy*, not the
    record). The text in the ``spec`` field is the human-readable
    sentence the rubric coder sees in the side-by-side display.

    Returns a dict matching the shape ``rubric_io.load_inverted_specs``
    accepts: keys are OCIDs, values are objects with at least a
    ``spec`` string. Extra metadata (per-rule original/inverted
    operator pairs) lives alongside ``spec`` so the rubric tool can
    surface it if it wants — the loader ignores unknown keys per the
    documented contract.

    ``permutation_log_entries`` is the ``permuted_policy[
    PERMUTATION_LOG_KEY]['entries']`` array from
    ``permute_policy(...)`` — one entry per rule, carrying the
    original and inverted condition dicts. We summarise it into a
    practitioner-legible sentence.
    """
    # Build the human-readable summary string once — same for every OCID.
    rule_lines: list[str] = []
    rule_specs: list[dict[str, Any]] = []
    for entry in permutation_log_entries:
        rule_code = entry.get("rule_code") or "<unknown>"
        original = entry.get("original_condition") or {}
        inverted = entry.get("inverted_condition") or {}
        # Each condition block has exactly one operator key + one
        # 'field' key per the locked schema (see
        # permute_policy._invert_condition).
        original_op = next(
            (k for k in original.keys() if k != "field"), "?"
        )
        inverted_op = next(
            (k for k in inverted.keys() if k != "field"), "?"
        )
        field_name = original.get("field") or inverted.get("field") or "?"
        rule_lines.append(
            f"{rule_code}: {original_op} → {inverted_op} ({field_name})"
        )
        rule_specs.append(
            {
                "rule_code": rule_code,
                "field": field_name,
                "original_operator": original_op,
                "inverted_operator": inverted_op,
            }
        )

    rules_summary = "; ".join(rule_lines)
    spec_sentence = (
        f"Permuted policy (seed={seed}): every rule's primary condition "
        f"operator inverted uniformly across all {len(rule_specs)} rules. "
        f"Inversions: {rules_summary}."
    )

    payload: dict[str, dict[str, Any]] = {}
    for ocid in ocids:
        payload[ocid] = {
            "spec": spec_sentence,
            "rules": rule_specs,
        }
    return payload


def emit_inverted_operator_spec(
    *,
    diagnostic_dir: Path,
    ocids: Sequence[str],
    seed: int,
    permutation_log_entries: Sequence[Mapping[str, Any]],
) -> Path:
    """Write the inverted-operator-spec sidecar to
    ``<diagnostic_dir>/inverted_operator_spec.json``.

    Idempotent — same inputs produce byte-identical output (and the
    diagnostic permutation is a pure function of policy + seed, so
    re-running with the same locked subset always emits the same
    bytes).

    Atomic-write idiom (write to ``.tmp`` and ``os.replace``) — mirrors
    ``multi_pass._atomic_write_json`` so crash-safety is identical to
    the bundle-write path.

    Returns the path written.
    """
    payload = build_inverted_operator_spec_payload(
        ocids=ocids,
        seed=seed,
        permutation_log_entries=permutation_log_entries,
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    spec_path = diagnostic_dir / INVERTED_OPERATOR_SPEC_FILENAME
    tmp_path = spec_path.with_suffix(spec_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True, ensure_ascii=False)
        fp.write("\n")
        fp.flush()
    import os

    os.replace(tmp_path, spec_path)
    return spec_path


__all__ = [
    "DIAGNOSTIC_SUBSET_RELATIVE_PATH",
    "INVERTED_OPERATOR_SPEC_FILENAME",
    "build_inverted_operator_spec_payload",
    "emit_inverted_operator_spec",
    "load_diagnostic_subset",
]
