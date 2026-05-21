"""L0 live handler — the E1 reproducibility baseline.

L0 is defined as "what E1 saw at the agent — verbatim". Concretely:

- The user message is `build_user_message(context=..., substrate_notes=...)`
  applied to the record loaded from the E1 frozen archive. That record
  already carries the E1 substrate envelope (status / confidence /
  detail / value for each derived field).
- L0 adds NOTHING to the prompt. No domain summary, no rules, no
  precedents, no policy. The prompt SHA at L0 is whatever E1's prompt
  SHA was, modulo any in-between system-prompt changes (locked at
  E1's `agent_prompt_sha256` per `runner/system_prompt.md` —
  the multi-pass orchestrator checks SHA invariants in the manifest).

This is the "baseline by definition" — the L0 Stage A prompt files
(`runner/prompts/L0_*.md`) are not loaded at L0. There is no L0 prompt
file. The Stage A prompts for L1..L4 are read by their respective live
handlers.

## Why L0 returns empty string

The E2-001 `L0Handler` stub already returns empty string. This live
handler does the SAME — its job is to be the ANCHOR for additivity,
not to add anything itself. The contract is:

    compose_user_message(level="L0", ..., handlers={..."L0": L0LiveHandler()}, ...)
        -> base_message_unchanged

The reproducibility guarantee comes from the SUBSTRATE CACHE READER
feeding the same context + substrate_notes that E1 saw — not from any
prompt addition at L0. See `meshqu_runner.substrate_cache`.

## Why this exists as a separate module from level_handlers.py

Two reasons:

1. The E2-001 stub registry is the public CONTRACT for subsequent
   packages. Replacing the stub with a live implementation in-place
   would mean every other package implicitly inherits the live wiring
   even if their tests want the stub. Keeping live handlers in a
   separate submodule preserves the stub-as-default contract.

2. E2-002's done criteria are about establishing the L0 reproducibility
   baseline. The live handler's empty `build_addendum` is essentially a
   marker — the substantive work is the cache reader (which feeds the
   record) + the comparator script (which validates).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..level_handlers import GovernanceContextLevel, LevelHandler
from ..prompt_loader import LoadedPrompts


@dataclass
class L0LiveHandler:
    """Live L0 handler. Adds NOTHING to the user message.

    The reproducibility guarantee comes from the substrate cache reader
    feeding the same per-record context E1 saw, not from any prompt
    transformation here. See module docstring + `substrate_cache.py`.

    Wire-compatible with `level_handlers.LevelHandler`. Tests assert
    isinstance against the Protocol via duck-typing (the Protocol uses
    structural matching, not nominal subclassing)."""

    level: GovernanceContextLevel = "L0"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        """L0 is the baseline. No addition. Returns empty string."""
        return ""


def install_live_l0(
    handlers: dict[GovernanceContextLevel, LevelHandler],
) -> dict[GovernanceContextLevel, LevelHandler]:
    """Swap the L0 stub for the live L0 handler in the given registry.

    Idiom (callers should use this rather than mutating the registry by
    key directly so the swap is traceable in grep + tests):

        from meshqu_runner.level_handlers import default_main_handlers
        from meshqu_runner.context_levels.level_l0 import install_live_l0

        handlers = install_live_l0(default_main_handlers())
        run_multi_pass(..., handlers=handlers)

    Returns the SAME dict mutated in place AND as a return value (so
    callers can chain swaps for L1..L4 as those land)."""
    handlers["L0"] = L0LiveHandler()
    return handlers
