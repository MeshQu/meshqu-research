"""Vestigial — E2's level-handler ladder no longer dispatches in E3.

E2's runner ladders L0 → L1 → L2 → L3 → L4 additively. E3 does not.
Every E3 arm is independent (see ``meshqu_runner.arms`` for the new
dispatch idiom). The orchestrator no longer composes addenda
additively — it asks the arm registry for a fully rendered prompt.

This module is preserved as a **type-surface stub**: the symbols E2's
code-base imports (``GovernanceContextLevel``, ``LevelHandler``,
``MAIN_LEVELS``) keep existing so the inherited ``context_levels`` and
``diagnostic`` subpackages stay importable. The behavioural functions
``compose_user_message`` and ``default_main_handlers`` raise
``RuntimeError`` if invoked — calling them in E3 is a programming
mistake.

Why keep the surface at all (and not just delete ``context_levels``)?
Subsequent arm packages (E3-002..E3-005) plan to reuse rendering
helpers that live in ``context_levels`` (e.g. the policy-envelope
loader for L4-without-nudge, the precedent-block renderer for Arm A).
Forcing those packages to either fork those helpers a second time or
revive a deleted subpackage would cost engineering time without
buying any clarity. Keeping the type surface importable is the
minimum intervention.

If you're authoring a new E3 arm and find yourself reaching into this
module for behaviour, stop — you almost certainly want
``meshqu_runner.arms`` instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol


# ---------------------------------------------------------------------------
# Retained type-surface — for ``context_levels`` and ``diagnostic``
# ---------------------------------------------------------------------------


GovernanceContextLevel = Literal["L0", "L1", "L2", "L3", "L4", "L4_PERMUTED"]
"""Inherited from E2. E3 keys dispatch on arm name (a free string;
see ``meshqu_runner.arms.ARM_NAMES``), not on this literal."""

MAIN_LEVELS: tuple[GovernanceContextLevel, ...] = ("L0", "L1", "L2", "L3", "L4")
"""Inherited from E2. Kept so ``context_levels.level_l4`` and the
``diagnostic`` subpackage can import the symbol without modification."""


class LevelHandler(Protocol):
    """Per-level prompt-addendum producer. Vestigial in E3.

    In E2 this was THE dispatch protocol. In E3 it is retained only as
    a structural type for any inherited subpackage that still
    type-annotates against it. New E3 arms do NOT implement this
    Protocol — they register against ``meshqu_runner.arms.HANDLERS``
    instead.
    """

    level: GovernanceContextLevel

    def build_addendum(self, *args: Any, **kwargs: Any) -> str:
        ...


# ---------------------------------------------------------------------------
# Behavioural shims — raise if anyone tries to call them
# ---------------------------------------------------------------------------


def compose_user_message(*_args: Any, **_kwargs: Any) -> str:
    """Vestigial. E2's additive composition. Raises in E3.

    Why a raise rather than a silent no-op: E3 arms are designed
    *specifically* to break E2's additivity invariant. A silent no-op
    here would mask a programming mistake — code that thought it was
    additively composing addenda would just see no addendum at all and
    the arm would silently lose its prompt content. Loud failure is
    safer.
    """
    raise RuntimeError(
        "compose_user_message() is E2's additive-ladder composition "
        "and is removed in E3. Use meshqu_runner.arms.dispatch(arm_name, record) "
        "to render an arm's fully-formed user message."
    )


def default_main_handlers() -> dict[GovernanceContextLevel, LevelHandler]:
    """Vestigial. E2's main-grid handler registry. Raises in E3."""
    raise RuntimeError(
        "default_main_handlers() is E2's level-keyed registry and is "
        "removed in E3. Use meshqu_runner.arms.HANDLERS (an arm-keyed "
        "registry) instead."
    )


# ---------------------------------------------------------------------------
# Inert handler classes — keep instantiation working for inherited tests
# ---------------------------------------------------------------------------
#
# E2 exposed L0Handler / L1Handler / L2Handler / L3Handler / L4Handler
# as concrete classes; some inherited modules type-instantiate them
# (or pickle-roundtrip equivalent). Keeping a minimal class hierarchy
# preserves the import surface without resurrecting the ladder logic.


@dataclass
class _InertHandler:
    """Base for the vestigial concrete handlers. ``build_addendum``
    returns the empty string — matches E2's empty-prompt-file no-op
    contract. New code should not be using these."""

    level: GovernanceContextLevel = "L0"

    def build_addendum(self, **_kwargs: Any) -> str:
        return ""


@dataclass
class L0Handler(_InertHandler):
    level: GovernanceContextLevel = "L0"


@dataclass
class L1Handler(_InertHandler):
    level: GovernanceContextLevel = "L1"


@dataclass
class L2Handler(_InertHandler):
    level: GovernanceContextLevel = "L2"


@dataclass
class L3Handler(_InertHandler):
    level: GovernanceContextLevel = "L3"


@dataclass
class L4Handler(_InertHandler):
    level: GovernanceContextLevel = "L4"
