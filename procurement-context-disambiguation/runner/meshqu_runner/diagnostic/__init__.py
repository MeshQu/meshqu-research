"""Permuted-Policy diagnostic — primitives + the scaled E3 surface.

E2 introduced this package as the 5% adversarial-control pass that
disambiguates "agent reasons with context" from "agent agreement-
sycophancises against L4 policy" (see `planning/experiment_design.md`
§"Diagnostic Controls"). E3 scales it from 14 records to n=100 across
two model arms (primary + Claude) on the locked OCID subset; the new
surface lives in `scaled.py` + `meshqu_runner/arms/diagnostic.py`.

## Import layering

`permute_policy.py` and `subset.py` have NO downstream dependencies on
the runner-level orchestrator or the L4 handler subclass. They are
re-exported here as the small, dependency-light public surface that
`scaled.py`, `arms/diagnostic.py`, and
`context_levels/level_l4_permuted.py` all consume.

`L4PermutedPolicyHandler` (in `meshqu_runner.context_levels.level_l4_permuted`)
lives one ring out — it pulls in `multi_pass`, `agent`, `meshqu_client`,
etc. Importing it is OPT-IN via that dedicated submodule path. This
split exists to avoid a circular-import trap: `level_l4_permuted`
needs the permutation primitives from this package, and pulling it
through `__init__.py` would force-import its dependencies. Keeping
`__init__.py` to the dependency-free primitives keeps the cycle
broken cleanly.

`scaled.py` is the E3 diagnostic runtime surface — `load_diagnostic_subset`,
`emit_inverted_operator_spec`, and the inverted-operator-spec payload
builder. `arms/diagnostic.py` is the arm-handler entry point that the
runner's registry dispatches to.

## Removed from E2

E2's `runner.py` driver (`run_permuted_diagnostic`) was retired in the
E3-008 cleanup — it imported `GOVERNANCE_CONTEXT_LEVEL_FIELD` from
`multi_pass`, a symbol E3-001 retired when it gutted the additive
ladder. The E2 source is preserved in the published artefact at
`procurement-context-gradient/runner/meshqu_runner/diagnostic/runner.py`.
E3's diagnostic runtime is `scaled.py` + `arms/diagnostic.py`, dispatched
via the standard arm registry; the legacy single-purpose driver is no
longer needed.
"""
from __future__ import annotations

from .permute_policy import (
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    PolicyPermutationError,
    permute_policy,
)
from .subset import (
    PERMUTED_SUBSET_DIVISOR,
    is_in_permuted_subset,
    pick_permuted_subset,
)
from .rubric_io import (
    CATEGORY_LABELS,
    CodedEntry,
    DiagnosticBundle,
    InvertedSpec,
    P5Bands,
    RubricSchemaError,
    VALID_ARMS,
    VALID_CATEGORIES,
    parse_p5_bands,
)
from .scaled import (
    DIAGNOSTIC_SUBSET_RELATIVE_PATH,
    INVERTED_OPERATOR_SPEC_FILENAME,
    build_inverted_operator_spec_payload,
    emit_inverted_operator_spec,
    load_diagnostic_subset,
)


__all__ = [
    "CATEGORY_LABELS",
    "CodedEntry",
    "DIAGNOSTIC_SUBSET_RELATIVE_PATH",
    "DiagnosticBundle",
    "INVERTED_OPERATOR_SPEC_FILENAME",
    "InvertedSpec",
    "LOCKED_PERMUTATION_SEED",
    "P5Bands",
    "PERMUTATION_LOG_KEY",
    "PERMUTED_SUBSET_DIVISOR",
    "PolicyPermutationError",
    "RubricSchemaError",
    "VALID_ARMS",
    "VALID_CATEGORIES",
    "build_inverted_operator_spec_payload",
    "emit_inverted_operator_spec",
    "is_in_permuted_subset",
    "load_diagnostic_subset",
    "parse_p5_bands",
    "permute_policy",
    "pick_permuted_subset",
]
