"""meshqu_runner — procurement-context-disambiguation (E3) experiment execution.

Forked from ``procurement-context-gradient/runner/meshqu_runner/`` (E2)
at commit 9644bac (pre-registration tag ``v0.3-predictions-locked``).
The arm-aware dispatch model replaces E2's level-batched ladder; see
``meshqu_runner.arms`` for the new orchestration entry point.

## Eager arm-handler registration

The foundation's ``arms.py`` lays placeholder no-op handlers at import
time. Per-arm modules (``arm_c`` for E3-004, ``arm_a`` for E3-002, etc.)
register their live handlers against ``arms.HANDLERS`` via the
``@register(...)`` decorator at THEIR import time. To guarantee the
CLI's ``--arm arm_c`` dispatch picks up the live handler without the
caller having to import the arm module themselves, the package
imports the per-arm modules eagerly here. Sibling arm packages (E3-002,
E3-003, E3-005, E3-006) will add their own imports below as they
land — the imports are append-only and ordering-independent (each arm
overwrites only its own slot in ``HANDLERS``).
"""

__version__ = "0.3.0"

# Eager arm-handler registration. Importing the module triggers the
# @register(...) decorator, overwriting the foundation's placeholder.
# When a sibling arm PR lands, it appends its own import line below.
from . import arm_c  # noqa: F401  -- side-effect import: registers arm_c handler
