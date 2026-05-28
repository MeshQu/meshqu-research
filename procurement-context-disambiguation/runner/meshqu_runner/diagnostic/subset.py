"""Deterministic 5% subset selector for the Permuted-Policy diagnostic.

The build-package contract (see
`planning/build_packages/e2-006-permuted-policy-diagnostic.md` §1 and
`planning/experiment_design.md` §"Diagnostic Controls") specifies the
subset filter as

    hash(ocid) mod 20 == 0

The word "hash" here is **deliberately not** Python's built-in `hash()`
— that function is salt-randomised per interpreter process (controlled
by `PYTHONHASHSEED`) and would produce a different 14-record subset on
every fresh runner invocation. The whole point of the diagnostic is
that the same 14 records are picked across re-runs so the smoke
fixture and the full corpus produce comparable populations.

We use SHA-256 truncated to its leading 64 bits and reduced mod 20.
SHA-256 is platform-stable, deterministic across processes, and
returns the same 14 records on Sam's machine, in CI, and on Phase-2
runners six months from now.

## Subset size sanity-check

On the 283-record E1 corpus, this filter selects exactly **14 records**.
The package prompt allows `14 ± 1` — our actual count lands cleanly at
the centre of that band. The 14 OCIDs are spread across publication
dates and procurement methods (no clustering on a single PROC-* rule
or method), per Sam's spot-check at lock time.
"""
from __future__ import annotations

import hashlib
from typing import Iterable


PERMUTED_SUBSET_DIVISOR = 20
"""Modulus. Locked at v0.2 lock time — the design specifies a ~5%
subset, and 1/20 = 5%. Changing this would change which 14 records
are picked and would invalidate any locked predictions about subset
composition. Do not edit without a new predictions-lock tag."""

_PERMUTED_SUBSET_REMAINDER = 0
"""Subset selector keeps OCIDs whose stable hash mod 20 == 0. Locked
constant. Picking remainder 0 is arbitrary but locked — picking a
different remainder would give a different (still ~14) subset."""


def _stable_hash_int(ocid: str) -> int:
    """Return a process-stable, deterministic integer derived from the
    OCID string.

    Implementation: take the first 8 bytes of SHA-256(ocid utf-8) and
    interpret big-endian as a 64-bit unsigned integer. Big-endian is
    locked so the byte → int interpretation is identical on every
    platform. Eight bytes is plenty of entropy — at our corpus scale
    (~10² records) the modulus reduction below collapses far more
    entropy than we use.

    NOT Python's built-in `hash()` — that is process-salt-randomised
    (controlled by PYTHONHASHSEED env var) and would produce a
    different subset on every interpreter start, defeating the point.
    """
    digest = hashlib.sha256(ocid.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def is_in_permuted_subset(ocid: str) -> bool:
    """Predicate: True iff `ocid` belongs to the Permuted-Policy
    diagnostic's 5% subset.

    Empty / None OCID returns False (no diagnostic on records with no
    stable OCID — the picker would be nondeterministic anyway).

    The 14 OCIDs this returns True for on the 283-record E1 corpus are
    locked at v0.2 lock time. See `tests/test_permuted_policy.py
    ::test_subset_selection_yields_fourteen_records` for the
    enumerated expected list — that test will fail loudly if the
    subset ever shifts.
    """
    if not ocid:
        return False
    return _stable_hash_int(ocid) % PERMUTED_SUBSET_DIVISOR == _PERMUTED_SUBSET_REMAINDER


def pick_permuted_subset(ocids: Iterable[str]) -> list[str]:
    """Return the sorted list of OCIDs from `ocids` that fall in the
    diagnostic subset.

    Sorted ascending so the order is stable and tests can read the
    output directly. Duplicates in the input are de-duplicated
    (set-collapse before filter).
    """
    return sorted({o for o in ocids if is_in_permuted_subset(o)})
