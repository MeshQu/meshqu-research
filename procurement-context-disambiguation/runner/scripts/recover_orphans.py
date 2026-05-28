#!/usr/bin/env python3
"""Thin shim around ``meshqu_runner.recover_orphans`` so the spec's
literal CLI invocation works:

    python3 scripts/recover_orphans.py <run_dir> [--base-url …] [--api-key …] [--dry-run]

The actual orphan-recovery logic lives at
``procurement-context-disambiguation/runner/meshqu_runner/recover_orphans.py``
(ported from E2 to track E3's arm-keyed subdir layout via the
``anomalies.jsonl`` channel — orphan records carry the decision_id /
idempotency_key the recovery POST needs, not the arm name, so the E2
adapter generalises cleanly).

Why a shim instead of pointing the operator at the module form
(``python3 -m meshqu_runner.recover_orphans``):

  - The E3-011 dry-run package spec (§4) names the file
    ``recover_orphans.py`` in ``scripts/``. Inheriting that exact
    name keeps the docs + the shell command Sam runs identical.
  - The other E3 driver scripts (``smoke_e3.py``, ``dry_run_e3.py``,
    ``verify_smoke_e3.py``, ``verify_dry_run_e3.py``) all live in
    ``scripts/``. Sibling placement keeps the operator-facing surface
    coherent.

The shim itself contains no orphan-recovery logic — it only adds the
runner-dir to ``sys.path`` and forwards argv to the module's ``main``."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SCRIPT_DIR.parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

from meshqu_runner.recover_orphans import main as _main  # noqa: E402


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(_main(sys.argv[1:]))
