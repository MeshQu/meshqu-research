"""Per-arm handler modules — landing pad for the @register(...) calls
that overwrite the placeholder handlers laid down by ``meshqu_runner.arms``.

Each per-arm module in this package registers exactly one arm by
importing ``arms.register`` and decorating its handler. Importing the
sub-module is sufficient to wire it in (the decorator runs at import
time and mutates the ``HANDLERS`` registry).

To activate all real handlers, callers import this package once — the
``__init__`` imports every sub-module here, which fires every
``@register`` decorator. This package is imported eagerly by
``meshqu_runner.cli`` and ``meshqu_runner.multi_pass`` so that the
arm-aware orchestrator sees real handlers rather than the foundation's
placeholders.

Parallel-worktree convention. Sibling build packages (E3-002..E3-006)
each land their own sub-module here. The git-merge resolution is
trivial because each agent appends a single ``from . import …`` line
below; conflicts in this file are line-additions, not edits.

Real handlers registered so far:

- ``l4_without_nudge`` (E3-005)
"""
from __future__ import annotations

# Sub-module imports. Each one registers its arm against
# ``meshqu_runner.arms.HANDLERS`` at import time.

from . import l4_without_nudge  # noqa: F401  -- E3-005
