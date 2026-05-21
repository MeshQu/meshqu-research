"""Stage A content guard rails — shared by the L1..L4 payload generators.

The E2-003 / E2-004 / E2-005 package prompts each say the same thing:

  > Empty Stage A content (placeholder TODO strings) should raise a clear
  > error at startup so misconfiguration is caught.

That requirement coexists with E2-001's test
`test_empty_prompts_handled_gracefully`, which asserts that *truly empty*
files behave as a no-op (the orchestrator must still emit 15 bundles
with correct level markers). The two contracts resolve cleanly:

- **Truly empty content** (`""` / whitespace-only) — no-op. The agent's
  user message at L_k equals L_{k-1}'s message. The level marker still
  rides into the integrity hash. This is the E2-001 invariant.
- **TODO-stub content** (a string that LOOKS like a placeholder — e.g.
  starts with `TODO`, or contains `TODO: Stage A content`) — fail loudly
  at startup. This is the E2-003 stop condition: "Stage A content is
  the placeholder stub (`TODO: Stage A content`) → STOP."

The detection is intentionally conservative: we only flag content that
explicitly screams "placeholder". Real Stage A prose can mention the
word "TODO" inside a sentence and that's fine — the heuristic looks for
the stub patterns Sam actually uses when scaffolding ("TODO:" at the
start of a line, or any line that is exactly the `TODO: Stage A
content` literal).
"""
from __future__ import annotations

import re

from ..prompt_loader import LevelPrompt


class StageAContentError(RuntimeError):
    """Raised when a Stage A prompt file still carries placeholder/stub
    content that the runner must not silently send to the agent.

    Distinct from FileNotFoundError (handled by prompt_loader) — that
    case means the file is missing entirely; this case means the file
    exists but its content is the not-yet-authored marker."""


# Patterns that indicate a placeholder. Conservative: each line must
# match in entirety after stripping leading whitespace, OR the whole
# file must be the literal sentinel. Authored prose mentioning "TODO"
# parenthetically will NOT match.
_TODO_LINE_PATTERN = re.compile(r"^\s*TODO\b[: ]?.*$", re.IGNORECASE)
_TODO_SENTINEL_LITERALS = frozenset(
    {
        "TODO: Stage A content",
        "TODO: Stage A content.",
        "TODO",
    }
)


def looks_like_todo_stub(content: str) -> bool:
    """True iff `content` looks like an un-authored Stage A placeholder.

    Detection rules (all evaluated against the stripped, normalised text):

    1. The whole content (trimmed) is one of the known sentinel
       literals — `TODO`, `TODO: Stage A content`, etc.
    2. Every non-blank line begins with `TODO` followed by `:` or
       whitespace. This catches multi-line stubs like:

           TODO: Add governance context here
           TODO: Mention PA23 vs PCR2015

    A non-empty file whose content has at least one substantive
    (non-TODO) line passes — Sam can write "TODO follow up later" as a
    parenthetical inside real prose without tripping the guard.
    """
    if not content or not content.strip():
        # Empty / whitespace-only is the E2-001 graceful-no-op case, NOT
        # a TODO stub. Caller decides whether empty is acceptable for
        # the current level (it is for L1/L2 per the E2-001 contract).
        return False

    trimmed = content.strip()
    if trimmed in _TODO_SENTINEL_LITERALS:
        return True

    non_blank_lines = [line for line in trimmed.splitlines() if line.strip()]
    if not non_blank_lines:
        return False
    # Every non-blank line is a TODO line → placeholder.
    return all(_TODO_LINE_PATTERN.fullmatch(line) for line in non_blank_lines)


def assert_stage_a_content_usable(prompt: LevelPrompt) -> None:
    """Fail-fast guard called at handler construction time / first use.

    Raises StageAContentError when `prompt.content` is a TODO stub.
    Silently passes when `prompt.content` is either empty (E2-001
    no-op contract) or substantive prose.
    """
    if looks_like_todo_stub(prompt.content):
        raise StageAContentError(
            f"Stage A prompt at {prompt.path} is still a placeholder stub "
            f"(content begins with TODO). Author the content before running "
            f"E2 — the runner refuses to send placeholder text to the agent."
        )
