"""Load + SHA-256-hash the Stage A level-addendum prompts at run start.

The four Stage A prompt files at `runner/prompts/L{1,2,3,4}_*.md` are
locked content (their SHA-256 is captured in the run manifest and bound
into every receipt's integrity hash via the level handlers). This module
reads them, computes the SHAs once at startup, and surfaces both for the
multi-pass orchestrator.

Empty-file handling. The package prompt explicitly required graceful
no-op behaviour when a Stage A file is empty / whitespace-only — for the
E2-001 done criteria, the runner must be invocable even before Stage A
content lands. After Stage A merged (PR #48) the real prompts are in
place, but this module preserves the empty-file contract so the test
harness can swap in empty fixtures and the orchestration loop still
emits 15 receipts without raising.

A missing file is a hard error — that's a configuration mistake (the
prompts directory should always contain all four files, even if their
contents are TODO stubs).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


LevelKey = Literal["L1", "L2", "L3", "L4"]

# Order matters for the additivity invariant (context_ladder_design.md §
# "Additivity invariant"). L1 + L2 + L3 + L4 are read in this sequence
# and concatenated by the level handlers when building the prompt
# addendum at each level.
LEVEL_PROMPT_FILES: tuple[tuple[LevelKey, str], ...] = (
    ("L1", "L1_governance_context.md"),
    ("L2", "L2_named_rules.md"),
    ("L3", "L3_precedent_block_format.md"),
    ("L4", "L4_policy_envelope.md"),
)


@dataclass(frozen=True)
class LevelPrompt:
    """One Stage A prompt file, loaded + hashed."""

    level: LevelKey
    path: Path
    content: str
    sha256: str

    @property
    def is_empty(self) -> bool:
        """True when the file is empty or whitespace-only.

        Empty files are a valid no-op contribution — the level still
        runs, the addendum it produces is just the empty string, and
        the SHA is still bound into the manifest so the empty state
        is itself cryptographically attested."""
        return not self.content.strip()


@dataclass(frozen=True)
class LoadedPrompts:
    """All four Stage A prompts, keyed by level."""

    prompts: dict[LevelKey, LevelPrompt]

    def get(self, level: LevelKey) -> LevelPrompt:
        return self.prompts[level]

    def sha_map(self) -> dict[str, str]:
        """SHA-256 by level — written into the run manifest as
        `prompt_template_sha256.L1`..`L4` so a reproducibility-rerun
        can prove byte-identical Stage A content."""
        return {lp.level: lp.sha256 for lp in self.prompts.values()}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_level_prompts(prompts_dir: Path) -> LoadedPrompts:
    """Read L1..L4 from `prompts_dir`, compute SHA-256 over the raw bytes
    of each file (no normalisation — the manifest SHA must match what
    `sha256sum` reports on disk so the planning artefacts and the run
    manifest agree).

    Raises FileNotFoundError if any of the four files is absent.
    Empty / whitespace-only files are tolerated (see module docstring).
    """
    out: dict[LevelKey, LevelPrompt] = {}
    for level, filename in LEVEL_PROMPT_FILES:
        path = prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Stage A prompt missing: {path}. "
                "The four L1..L4 files must always exist (TODO stubs are fine); "
                "absence is a configuration error, not a no-op."
            )
        raw = path.read_bytes()
        out[level] = LevelPrompt(
            level=level,
            path=path,
            content=raw.decode("utf-8"),
            sha256=_sha256_bytes(raw),
        )
    return LoadedPrompts(prompts=out)
