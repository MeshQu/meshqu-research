"""Per-level handler implementations.

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
- `level_l1`, `level_l2` — E2-003. (Future.)
- `level_l3` — E2-004. (Future.)
- `level_l4` — E2-005. (Future.)
- `level_l4_permuted` — E2-006. (Future.)

This `__init__` deliberately does NOT eagerly import every submodule.
Parallel build packages add modules independently — keeping imports
explicit at call sites means a missing/broken sibling cannot break L0
consumers.
"""
