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
import re
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


# ---------------------------------------------------------------------------
# Leading-HTML-comment strip — renderer-level utility
# ---------------------------------------------------------------------------
#
# Some locked prompt files (notably E3's ``L4_without_nudge.md``)
# carry a multi-line HTML comment at the very top of the file as a
# methodological header — what was excised, why, which other file the
# variant is a surgical fork of. The comment is documentation only:
# when the file is sent to an LLM as part of a rendered user message,
# the LLM should not see this header (it would either bias the model
# by telling it which nudge was removed, or — worse — re-introduce the
# excised text verbatim via the body of the comment).
#
# Sam's 2026-05-28 resolution (PR #85 redispatch of E3-005): keep the
# locked file bytes intact on disk (so the v0.3-predictions-locked SHA
# binding stays valid), and have the renderer strip leading HTML
# comments before passing the prompt to the LLM. This utility lives
# at the prompt-loader level so any arm whose locked content carries
# a leading methodological comment can reuse it.
#
# Scope. The strip applies to **leading** comments only — a contiguous
# run of ``<!-- ... -->`` blocks at the very start of the text, plus
# any whitespace separating them from the first non-comment content.
# Comments later in the document (e.g. inline annotations beside a
# rule definition) are preserved verbatim. This is deliberate: the
# locked envelopes' interpolation tokens and section structure must
# survive intact.

_LEADING_HTML_COMMENT_RE = re.compile(
    # One <!-- ... --> block (non-greedy across newlines), then any
    # trailing whitespace before the next character. The ``+`` lets us
    # absorb multiple stacked leading comments in one pass — defensive
    # against future locked files that author the methodological
    # header as two paragraphs of comments rather than one.
    r"\A(?:<!--.*?-->[ \t]*\n?\s*)+",
    re.DOTALL,
)


def strip_leading_html_comments(text: str) -> str:
    """Remove leading ``<!-- ... -->`` blocks (plus trailing whitespace)
    from a prompt body.

    Idempotent — running the strip on already-stripped text returns
    the same text. Non-leading comments (anywhere after the first
    non-comment character) are left untouched.

    Used by the L4-without-nudge handler to honour the locked file's
    methodological header without polluting the rendered LLM prompt.
    See module docstring for the Sam 2026-05-28 resolution context.

    Edge cases tested in ``tests/test_prompt_loader.py``:

    - input with no leading comment → returned unchanged
    - single-line comment at the start → stripped (comment + trailing
      newline)
    - multi-line comment at the start → stripped (whole block)
    - comment followed by blank lines → stripped together
    - comment NOT at the start (e.g. inline mid-document) → preserved
    - text consisting of only a leading comment → empty string returned
    """
    return _LEADING_HTML_COMMENT_RE.sub("", text)


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
