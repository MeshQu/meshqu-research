"""Per-level handler implementations — live wiring for L0..L4.

The E2-001 stub registry lives in `meshqu_runner.level_handlers`. This
subpackage hosts the LIVE handlers that successive build packages wire
in via the registry-replacement pattern:

    from meshqu_runner.level_handlers import default_main_handlers
    from meshqu_runner.context_levels.level_l0 import L0LiveHandler

    handlers = default_main_handlers()
    handlers["L0"] = L0LiveHandler()
    # run_multi_pass(..., handlers=handlers)

E2-001's `LevelHandler` Protocol is intentionally NOT modified by any
subsequent package — the Protocol is the public contract, the
implementations are swapped underneath.

Modules:

- `level_l0` — E2-002. Baseline (re-runs E1's prompt verbatim — empty
  addendum, the record already carries the E1 substrate envelope).
  NOT re-exported here; used via `install_live_l0()` from
  `level_handlers`.
- `stage_a` — E2-003. Shared content-guard for L1..L4 (TODO-stub
  detection).
- `level_l1` — E2-003. Domain-summary prose, wrapped under
  `## Governance context`.
- `level_l2` — E2-003. Named-rules block, emitted verbatim (file
  already carries its own `## Rules in force` header).
- `level_l3` — E2-004. (Future.)
- `level_l4` — E2-005. (Future.)
- `level_l4_permuted` — E2-006. (Future.)
"""
from __future__ import annotations

# E2-003 — L1, L2, and the shared Stage A content guard.
from .level_l1 import L1ContextHandler, build_l1_addendum
from .level_l2 import L2ContextHandler, build_l2_addendum
from .stage_a import (
    StageAContentError,
    assert_stage_a_content_usable,
    looks_like_todo_stub,
)

__all__ = [
    "L1ContextHandler",
    "L2ContextHandler",
    "StageAContentError",
    "assert_stage_a_content_usable",
    "build_l1_addendum",
    "build_l2_addendum",
    "looks_like_todo_stub",
]
