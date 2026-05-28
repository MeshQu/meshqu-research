"""E3-001 fork-parity tests — bytes-identical core files vs E2.

The agent prompt, MeshQu client, substrate adapter, substrate cache,
precedent archive, precedent selector, and system prompt are the
cross-experiment integrity contract. The fork is supposed to be a
*fork* not a *rewrite*: these files must match E2 byte-for-byte so
that any cross-experiment claim ("the runner produced identical
substrate bytes for the same OCID in E2 and E3") is checkable by
SHA against the source tree.

If a file drifts, the fork is broken. The package's "Stop conditions"
explicitly calls this out — drift means provenance is in question.

This test asserts byte-identity by computing the SHA-256 of each
covered file in both E2 and E3 trees and demanding equality. If the
test fails, ask:

1. Did E2's runner change post-publication? (If yes: that violates the
   "frozen artefact" contract; surface to Sam, do NOT update E3.)
2. Did E3-001 accidentally touch a forked-verbatim file? (If yes: roll
   back the edit in E3; the byte-identity contract is the foundation
   of the cross-experiment integrity claim.)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# The set of files that must be byte-identical between E2 and E3
# ---------------------------------------------------------------------------
#
# Names match the package spec §6 exactly:
#
#   agent.py, meshqu_client.py, substrate.py, substrate_cache.py,
#   precedent_archive.py, precedent_selector.py, system_prompt.md
#
# Layout is identical in both trees:
#   <experiment>/runner/meshqu_runner/<file>.py  (or system_prompt.md)

REPO_ROOT = Path(__file__).resolve().parents[3]
E2_RUNNER = REPO_ROOT / "procurement-context-gradient" / "runner"
E3_RUNNER = REPO_ROOT / "procurement-context-disambiguation" / "runner"

BYTE_IDENTICAL_FILES: tuple[str, ...] = (
    "meshqu_runner/agent.py",
    "meshqu_runner/meshqu_client.py",
    "meshqu_runner/substrate.py",
    "meshqu_runner/substrate_cache.py",
    "meshqu_runner/precedent_archive.py",
    "meshqu_runner/precedent_selector.py",
    "system_prompt.md",
)


def _sha256(path: Path) -> str:
    with path.open("rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


@pytest.mark.parametrize("rel_path", BYTE_IDENTICAL_FILES)
def test_e3_file_byte_identical_to_e2(rel_path: str) -> None:
    """SHA-256 of E2's file == SHA-256 of E3's file.

    The package spec §6 enumerates this exact set as the cross-
    experiment integrity contract. Drift here means a stop condition
    fired and was not surfaced. See module docstring for the
    decision tree.
    """
    e2_path = E2_RUNNER / rel_path
    e3_path = E3_RUNNER / rel_path
    assert e2_path.exists(), f"E2 source missing: {e2_path}"
    assert e3_path.exists(), f"E3 fork missing: {e3_path}"
    e2_sha = _sha256(e2_path)
    e3_sha = _sha256(e3_path)
    assert e2_sha == e3_sha, (
        f"fork-parity broken for {rel_path!r}: "
        f"E2={e2_sha[:16]}... E3={e3_sha[:16]}.... "
        f"See test_fork_parity module docstring for the decision tree."
    )


def test_byte_identical_set_matches_package_spec() -> None:
    """Belt-and-braces — the parametrised set above is exactly the
    seven files the package spec §6 enumerates. A drift here would
    mean someone added or removed a file from the fork-parity
    contract; that needs to be a deliberate decision, not a
    quiet edit."""
    assert BYTE_IDENTICAL_FILES == (
        "meshqu_runner/agent.py",
        "meshqu_runner/meshqu_client.py",
        "meshqu_runner/substrate.py",
        "meshqu_runner/substrate_cache.py",
        "meshqu_runner/precedent_archive.py",
        "meshqu_runner/precedent_selector.py",
        "system_prompt.md",
    )
