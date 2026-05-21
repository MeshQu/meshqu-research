"""Per-level handlers — L0..L4 + L4_PERMUTED.

Each handler is responsible for producing the level-specific addendum
that the multi-pass orchestrator prepends to the per-record user message
before calling the agent. Subsequent build packages fill in the
level-specific behaviour:

  - L0  (this module)        — baseline (no addition)
  - L1  (E2-003)             — domain summary prose
  - L2  (E2-003)             — named rules block
  - L3  (E2-004)             — nearest-neighbour precedent selector
  - L4  (E2-005)             — full policy envelope + cache-friendly prefix
  - L4_PERMUTED (E2-006)     — adversarial-permutation diagnostic

E2-001's done criteria only requires stubs that produce a valid v1
bundle envelope (wrapping a v2 MeshQu receipt) with the correct
`governance_context_level` marker. The stub
implementations here read the loaded Stage A prompt content verbatim
and prepend it as a section header — enough to verify additivity and
the SHA-binding contract without committing to the level-specific
prompt shape that E2-003..006 will land.

## Additivity invariant

Each level **adds** to the previous, never replaces (see
`planning/context_ladder_design.md`). The orchestrator calls handlers
in order and concatenates their addenda: L0 -> L0+L1 -> L0+L1+L2 -> ...
The handlers here do not enforce this directly — they each return
their own marginal contribution. The multi-pass orchestrator composes.

## Empty-file contract

If a Stage A prompt file is empty (the package prompt's pre-Stage-A
contract), the handler returns an empty string. The orchestrator
treats this as a valid no-op addition — the receipt still binds the
level marker into its integrity hash; only the prompt addendum is
empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol

from .prompt_loader import LoadedPrompts


# Distinct from the agent's NormalisedVerdict — this is the context-level
# enum. L4_PERMUTED is the adversarial diagnostic; it sits OUTSIDE the
# main 5-level grid (see experiment_design.md §"Diagnostic Controls").
GovernanceContextLevel = Literal["L0", "L1", "L2", "L3", "L4", "L4_PERMUTED"]

MAIN_LEVELS: tuple[GovernanceContextLevel, ...] = ("L0", "L1", "L2", "L3", "L4")
"""The 5 levels of the main run. L4_PERMUTED is OUT — diagnostic only."""


class LevelHandler(Protocol):
    """Per-level prompt-addendum producer.

    A handler returns the MARGINAL contribution this level adds on top
    of all lower levels. The orchestrator concatenates additively
    (L0 + L1 + ... + Lk) before calling the agent.
    """

    level: GovernanceContextLevel

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        """Return the level-specific text to prepend to the user message.
        Empty string is a valid no-op (L0 always; other levels when the
        Stage A prompt file is empty)."""
        ...


# ---------------------------------------------------------------------------
# Stub handlers — replaced in scope by E2-002..006
# ---------------------------------------------------------------------------


@dataclass
class L0Handler:
    """Baseline. NEVER adds anything — L0 is E1's prompt verbatim.

    E2-002 will replace this stub with the substrate-cache-reader that
    feeds the same record bytes E1 saw at L0 (the reproducibility
    check). For E2-001's done criteria, the stub is sufficient: an L0
    bundle still carries `governance_context_level=L0` in its integrity
    payload."""

    level: GovernanceContextLevel = "L0"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        return ""


@dataclass
class L1Handler:
    """Domain summary. Stub for E2-001 — emits the L1 prompt verbatim as
    a `## Governance context` section header.

    E2-003 will land the locked-prose wiring; this stub returns the
    content of `prompts/L1_governance_context.md` if non-empty, else
    empty string (empty-file contract)."""

    level: GovernanceContextLevel = "L1"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        return _wrap_section(prompts.get("L1"), header="## Governance context")


@dataclass
class L2Handler:
    """Named rules. Stub for E2-001 — emits the L2 prompt verbatim.

    E2-003 will land the named-rules wiring; this stub returns the
    content of `prompts/L2_named_rules.md` if non-empty."""

    level: GovernanceContextLevel = "L2"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        return _wrap_section(prompts.get("L2"), header="## Rules in force")


@dataclass
class L3Handler:
    """Precedent block format. Stub for E2-001.

    E2-004 lands the deterministic nearest-neighbour selector reading
    from the frozen E1 archive. The stub emits the L3 prompt verbatim
    (the precedent block FORMAT) so the integrity hash is bound, but
    no actual precedents are interpolated yet."""

    level: GovernanceContextLevel = "L3"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        return _wrap_section(prompts.get("L3"), header="## Precedent receipts")


@dataclass
class L4Handler:
    """Full policy envelope. Stub for E2-001.

    E2-005 lands the policy-snapshot interpolation + cache-friendly
    prefix ordering. The stub emits the L4 prompt verbatim (the
    envelope template) — the actual policy JSON is not interpolated
    yet."""

    level: GovernanceContextLevel = "L4"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        return _wrap_section(prompts.get("L4"), header="## Policy")


def _wrap_section(prompt, *, header: str) -> str:
    """Wrap a non-empty prompt in a section header so the additivity
    pattern reads naturally in the composed user message. Empty prompts
    pass through as empty string — the section header is suppressed too,
    keeping the L_k addendum a strict subset of L_{k+1}."""
    content = prompt.content.strip()
    if not content:
        return ""
    return f"{header}\n\n{content}\n"


# ---------------------------------------------------------------------------
# Registry — multi_pass.py uses this to look up handlers by level
# ---------------------------------------------------------------------------


def default_main_handlers() -> dict[GovernanceContextLevel, LevelHandler]:
    """The five handlers for the main run (L0..L4).

    L4_PERMUTED is deliberately absent — it's the diagnostic, registered
    separately by E2-006 to avoid mixing into the main grid.

    E2-003 swaps the L1 and L2 stubs for the live implementations in
    `meshqu_runner.context_levels` (registry-replacement pattern per
    the build package contract — the Protocol + orchestrator core are
    untouched). L0, L3, L4 are still the stubs in this module; E2-002,
    E2-004, E2-005 will replace them via the same pattern."""
    # Local import keeps level_handlers importable without a top-level
    # cycle: `context_levels.level_l1` imports
    # `GovernanceContextLevel` from this module.
    from .context_levels.level_l1 import L1ContextHandler
    from .context_levels.level_l2 import L2ContextHandler

    return {
        "L0": L0Handler(),
        "L1": L1ContextHandler(),
        "L2": L2ContextHandler(),
        "L3": L3Handler(),
        "L4": L4Handler(),
    }


def compose_user_message(
    *,
    level: GovernanceContextLevel,
    record: Mapping[str, object],
    ocid: str | None,
    prompts: LoadedPrompts,
    handlers: Mapping[GovernanceContextLevel, LevelHandler],
    base_message: str,
) -> str:
    """Compose the per-record user message at `level`.

    Additivity invariant: for level Lk, concatenate addenda from L0..Lk
    in order, then append the base record message. L4_PERMUTED composes
    L0..L3 from the main handlers plus the permuted L4 (E2-006 supplies
    that handler in its own registry; the orchestrator does not branch
    on L4_PERMUTED here).
    """
    addenda: list[str] = []
    if level == "L4_PERMUTED":
        # Diagnostic composes L0..L4 from the registry the caller passed
        # in (E2-006 substitutes a permuted L4 entry). This module does
        # not own the substitution.
        sequence = MAIN_LEVELS
    else:
        # Main-grid level: take L0..Lk inclusive (additivity invariant).
        cutoff = MAIN_LEVELS.index(level)
        sequence = MAIN_LEVELS[: cutoff + 1]

    for main_level in sequence:
        addenda.append(
            handlers[main_level].build_addendum(
                record=record, ocid=ocid, prompts=prompts
            )
        )

    prefix = "".join(part for part in addenda if part)
    if not prefix:
        return base_message
    return f"{prefix}\n{base_message}"
