"""Permuted-Policy diagnostic — E2-006.

The 5% adversarial-control pass that disambiguates "agent reasons with
context" from "agent agreement-sycophancises against L4 policy" (see
`planning/experiment_design.md` §"Diagnostic Controls").

A deterministic 14-record subset of the 283-record corpus gets an
auxiliary L4 pass with the policy's per-rule primary operators
inverted. The receipt carries `governance_context_level=L4_PERMUTED`
and binds a `policy_permutation_seed` into the integrity hash. Output
is isolated under `results/runs/<run_id>/diagnostic/` so it never
mixes with main-run L4 receipts.

## Import layering

`permute_policy.py` and `subset.py` have NO downstream dependencies
on the runner-level orchestrator or the L4 handler subclass. They are
re-exported here as the small, dependency-light public surface.

`runner.py` (the diagnostic driver) and the `L4PermutedPolicyHandler`
both live one ring out — they pull in `multi_pass`, `agent`,
`meshqu_client`, etc. Importing them is OPT-IN via the dedicated
submodule path (`meshqu_runner.diagnostic.runner` and
`meshqu_runner.context_levels.level_l4_permuted`). This split exists
to avoid a circular-import trap: `level_l4_permuted` needs the
permutation primitives from this package, and pulling them through
`__init__.py` would force-import the runner module which itself
imports `level_l4_permuted`. Keeping `__init__.py` to the
dependency-free primitives keeps the cycle broken cleanly.

Convenience re-exports from `runner.py` are exposed via the
`__getattr__` proxy below so callers can still write
`from meshqu_runner.diagnostic import run_permuted_diagnostic`
without paying the import-cycle cost at module import time.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


# Names re-exported lazily from `.runner`. Listed here so static
# analysers and IDE auto-complete still see them.
_RUNNER_RE_EXPORTS: frozenset[str] = frozenset(
    {
        "DIAGNOSTIC_LEVEL",
        "DIAGNOSTIC_SUBDIR",
        "DiagnosticSummary",
        "PERMUTATION_LOG_FILENAME",
        "diagnostic_handlers",
        "run_permuted_diagnostic",
    }
)


def __getattr__(name: str) -> Any:  # PEP 562 lazy module attribute
    if name in _RUNNER_RE_EXPORTS:
        from . import runner as _runner

        return getattr(_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:  # pragma: no cover — type-checker visibility only
    from .runner import (  # noqa: F401 — re-export for static analysis
        DIAGNOSTIC_LEVEL,
        DIAGNOSTIC_SUBDIR,
        DiagnosticSummary,
        PERMUTATION_LOG_FILENAME,
        diagnostic_handlers,
        run_permuted_diagnostic,
    )


__all__ = [
    "DIAGNOSTIC_LEVEL",
    "DIAGNOSTIC_SUBDIR",
    "DiagnosticSummary",
    "LOCKED_PERMUTATION_SEED",
    "PERMUTATION_LOG_FILENAME",
    "PERMUTATION_LOG_KEY",
    "PERMUTED_SUBSET_DIVISOR",
    "PolicyPermutationError",
    "diagnostic_handlers",
    "is_in_permuted_subset",
    "permute_policy",
    "pick_permuted_subset",
    "run_permuted_diagnostic",
]
