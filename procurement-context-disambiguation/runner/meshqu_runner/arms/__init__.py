"""Arm-aware handler registry — the heart of the E3 runner.

E2 ladders L0 → L1 → L2 → L3 → L4 additively. E3 does not. Each E3
**arm** is an independent probe — a self-contained handler that takes a
target record and returns a fully rendered prompt string. There is no
cross-arm composition, no L_{k-1} prefix; an arm is what it is.

## Why an arm-keyed registry (and not E2's level-handler protocol)

E2's `LevelHandler` Protocol assumed every handler was a strict subset
of every higher level (the additivity invariant). E3 breaks that
invariant by design: Arm A and Arm B render *different* precedent
formats, Arm C renders no precedents at all, L4-without-nudge is a
*surgical* excision of one clause from E2's L4 envelope, etc. Layering
them additively would either undo each variant's distinguishing edit or
re-introduce the very confound E3 is built to slice apart.

Flat dispatch by arm name keeps each arm's rendering self-contained.
Subsequent build packages (E3-002..E3-006) replace placeholders here
via `arms.register(...)` without touching the runner orchestration.

## Receipt integrity payload — arm-aware

`inject_arm_fields` extends `context.fields` with the seven new
E3-specific integrity fields. These ride into the MeshQu integrity hash
the same way E2's `agent_*` fields do (canonical-JSON serialisation
inside MeshQu's `fields` map). No upstream `@meshqu/core` change is
required; the bundle envelope version stays at 1. The seven fields:

- ``l3_arm``: ``"A"``, ``"B"``, ``"C"``, or ``None`` for non-L3 arms.
  Distinguishes the three L3 decomposition probes.
- ``nudge_excised``: ``True`` only for the ``l4_without_nudge`` arm.
- ``model_id``: defaults to ``gpt-5.4-2026-03-05``; set per arm. The
  Claude diagnostic arm carries ``claude-opus-4-7``.
- ``model_sampling``: full per-arm sampling block. The primary agent
  emits ``{"temperature": 0}``; Opus 4.7 emits
  ``{"temperature": None, "effort": "low"}`` (Opus 4.7 removed the
  ``temperature`` parameter — see ``planning/feasibility_spike_claude.md``).
- ``diagnostic``: ``True`` only for the Permuted-Policy diagnostic
  arms (``diagnostic_primary``, ``diagnostic_claude``).
- ``policy_permutation_seed``: integer seed identifying which
  permutation of the policy text the diagnostic ran against. ``None``
  for non-diagnostic arms.
- ``runner_git_commit``: SHA of the runner code at run time.
- ``prereg_tag``: literal ``"v0.3-predictions-locked"``.

## Arm enumeration

The package spec §"Definition of done" says "at least a placeholder
no-op handler registered for each of the 7 arm names". The package's
§2 enumerates eight: ``arm_a``, ``arm_b``, ``arm_c``, ``l4_with_nudge``,
``l4_without_nudge``, ``l0_baseline``, ``diagnostic_primary``,
``diagnostic_claude``. We register all eight — under-registering would
leave gaps when E3-008 (diagnostic) and any sanity-check runs dispatch.
The "7 vs 8" discrepancy is surfaced in the PR body for Sam.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


# ---------------------------------------------------------------------------
# Pre-registration constants
# ---------------------------------------------------------------------------

PREREG_TAG = "v0.3-predictions-locked"
"""The git tag that binds E3's locked content (prompts, rubric,
predictions, design parameters). Stamped into every receipt's integrity
payload so a verifier can audit which pre-registration applies."""

DEFAULT_MODEL_ID = "gpt-5.4-2026-03-05"
"""The primary agent's model id. Inherited unchanged from E1/E2; pinned
across all main-grid arms (Arms A/B/C, L4-with/without-nudge, L0
baseline, diagnostic_primary)."""

DEFAULT_MODEL_SAMPLING: dict[str, Any] = {"temperature": 0}
"""Primary agent's sampling block. Locked at temperature 0 since E1.

E2 stored this as a single ``agent_temperature`` field; E3 widens to a
sampling *block* because the cross-model arm (``diagnostic_claude``)
cannot match temperature 0 — Opus 4.7 removed the ``temperature``
parameter. A nested block keeps the schema stable as future models
add or remove knobs."""

CLAUDE_MODEL_ID = "claude-opus-4-7"
"""The cross-model arm's model id. Pinned during the Phase-0 feasibility
spike (see ``planning/feasibility_spike_claude.md``)."""

CLAUDE_MODEL_SAMPLING: dict[str, Any] = {"temperature": None, "effort": "low"}
"""Opus 4.7 cannot accept ``temperature``; ``effort: low`` is the
near-determinism knob the spike confirmed works for classification
diagnostics."""


# ---------------------------------------------------------------------------
# Arm enumeration
# ---------------------------------------------------------------------------

ARM_NAMES: tuple[str, ...] = (
    # L3 decomposition arms (E3-002..E3-004)
    "arm_a",
    "arm_b",
    "arm_c",
    # L4 decomposition (E3-005 + E2's L4 retained for sanity checks)
    "l4_with_nudge",
    "l4_without_nudge",
    # L0 baseline (retained for the dry-run freshness check)
    "l0_baseline",
    # Scaled diagnostic — primary model + Claude (E3-008)
    "diagnostic_primary",
    "diagnostic_claude",
)
"""All arms the runner can dispatch. Add a new arm by:

1. Append its name here (and update tests).
2. ``@register(<arm_name>)`` a handler in the relevant build package.
3. (Optional) add an entry in ``ARM_PROFILES`` if the arm needs
   non-default ``model_id``, ``model_sampling``, ``l3_arm``,
   ``nudge_excised``, or ``diagnostic`` defaults.
"""


@dataclass(frozen=True)
class ArmProfile:
    """Per-arm defaults for the receipt integrity payload.

    Handlers do not have to consult this directly — the runner consults
    it when building the per-receipt fields map. A handler can override
    any of these by passing explicit kwargs to ``inject_arm_fields``.

    ``l3_arm`` is the human-readable letter for L3 decomposition arms
    (``"A"``, ``"B"``, ``"C"``). For everything else it is ``None`` — a
    verifier asking "is this an L3 arm?" gets a clean answer.

    ``nudge_excised`` is True only for ``l4_without_nudge``; False
    everywhere else. (E2's L4 retained the nudge — under the new arm
    name ``l4_with_nudge`` — and that nudge is therefore preserved.)

    ``diagnostic`` flips True for the two ``diagnostic_*`` arms; the
    integrity payload also carries the ``policy_permutation_seed`` for
    those arms (the per-record seed is supplied at dispatch time).
    """

    arm_name: str
    l3_arm: str | None = None
    nudge_excised: bool = False
    model_id: str = DEFAULT_MODEL_ID
    model_sampling: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_MODEL_SAMPLING))
    diagnostic: bool = False


ARM_PROFILES: dict[str, ArmProfile] = {
    "arm_a": ArmProfile(arm_name="arm_a", l3_arm="A"),
    "arm_b": ArmProfile(arm_name="arm_b", l3_arm="B"),
    "arm_c": ArmProfile(arm_name="arm_c", l3_arm="C"),
    "l4_with_nudge": ArmProfile(arm_name="l4_with_nudge", nudge_excised=False),
    "l4_without_nudge": ArmProfile(arm_name="l4_without_nudge", nudge_excised=True),
    "l0_baseline": ArmProfile(arm_name="l0_baseline"),
    "diagnostic_primary": ArmProfile(arm_name="diagnostic_primary", diagnostic=True),
    "diagnostic_claude": ArmProfile(
        arm_name="diagnostic_claude",
        diagnostic=True,
        model_id=CLAUDE_MODEL_ID,
        model_sampling=dict(CLAUDE_MODEL_SAMPLING),
    ),
}


def get_profile(arm_name: str) -> ArmProfile:
    """Look up an arm's default profile. Raises ``KeyError`` (not a
    soft None) so caller mistyping ``arm_d`` is surfaced loudly rather
    than silently treated as a non-L3 arm."""
    return ARM_PROFILES[arm_name]


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

# A handler accepts a record (Mapping) and returns the rendered prompt
# string the agent will receive. Handlers are pure: no side effects,
# no I/O beyond reading the substrate/precedent cache that subsequent
# packages will plumb in. The base record contains everything the arm
# needs (decision_type, fields, substrate_notes); arm-specific helpers
# such as the precedent selector are passed in via closure / kwargs at
# registration time by the package landing each arm.
ArmHandler = Callable[..., str]

HANDLERS: dict[str, ArmHandler] = {}
"""The single source of truth for arm dispatch. Populated at
import time by ``arms.register(...)`` decorators in subsequent packages.
This module pre-populates placeholder no-op handlers so that:

1. The dispatch table is complete from day one (CLI, tests, smoke).
2. Subsequent packages can override entries by re-registering — the
   intentional pattern is ``HANDLERS["arm_a"] = real_handler``, which
   overwrites the placeholder.

Direct mutation is allowed (no immutability ceremony); the registry
is module-state.
"""


def register(arm_name: str) -> Callable[[ArmHandler], ArmHandler]:
    """Decorator: register ``fn`` as the handler for ``arm_name``.

    Subsequent packages use this to plumb their real handler in:

        @register("arm_a")
        def arm_a_handler(record, *, precedent_selector, **kwargs) -> str:
            ...

    Re-registering an arm overwrites silently — the explicit intent of
    "the foundation lays placeholders; later packages overwrite". If
    you want to detect accidental double-registration in tests, assert
    on the identity of ``HANDLERS[arm_name]``.

    Unknown arm names are rejected at registration time — typo'd arm
    keys would silently sit in the registry otherwise, and the CLI
    would happily dispatch to them.
    """

    if arm_name not in ARM_NAMES:
        raise ValueError(
            f"Unknown arm name {arm_name!r}. "
            f"Add it to ARM_NAMES (and ARM_PROFILES if it needs non-default "
            f"integrity-payload values) before registering a handler."
        )

    def wrap(fn: ArmHandler) -> ArmHandler:
        HANDLERS[arm_name] = fn
        return fn

    return wrap


def dispatch(arm_name: str, record: Mapping[str, Any], **kwargs: Any) -> str:
    """Look up ``arm_name``'s handler and call it on ``record``.

    Raises ``KeyError`` if ``arm_name`` is unregistered — same posture as
    ``get_profile``. The CLI catches this and surfaces a clean error.

    ``**kwargs`` is forwarded to the handler verbatim; arm-specific
    helpers (the precedent selector for Arm A, the policy snapshot for
    L4 variants, a permutation seed for the diagnostic) are injected
    this way. The placeholder handlers ignore unknown kwargs.
    """
    if arm_name not in HANDLERS:
        raise KeyError(
            f"No handler registered for arm {arm_name!r}. "
            f"Either the relevant build package hasn't landed, or you "
            f"need to import the module that calls register()."
        )
    handler = HANDLERS[arm_name]
    sig = inspect.signature(handler)
    # Drop kwargs the handler doesn't accept so the foundation's
    # placeholder handlers (which accept only `record`) can coexist
    # with later real handlers that demand a precedent selector. The
    # alternative — requiring every placeholder to take **kwargs — is
    # fine too; this is belt-and-braces for the registry's first life.
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        accepted_kwargs = kwargs
    else:
        accepted_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return handler(record, **accepted_kwargs)


# ---------------------------------------------------------------------------
# Receipt integrity payload extension
# ---------------------------------------------------------------------------


def inject_arm_fields(
    context: Mapping[str, Any],
    *,
    arm_name: str,
    runner_git_commit: str,
    profile: ArmProfile | None = None,
    policy_permutation_seed: int | None = None,
    model_id: str | None = None,
    model_sampling: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fold the seven E3-specific integrity fields into ``context.fields``.

    Returns a new dict — does not mutate ``context``. Mirrors E2's
    ``meshqu_client.inject_agent_fields`` exactly (same audit-only-but-
    hash-bound pattern, same canonical-JSON serialisation contract);
    extending ``meshqu_client.py`` directly would break the byte-
    identity check against E2 (the foundation's fork-parity invariant).

    The seven fields land under ``context.fields`` so MeshQu's
    integrity-hash computation sees them. The policy never references
    them — they are audit-only metadata, just like the inherited
    ``agent_*`` fields.

    ``profile`` defaults to ``get_profile(arm_name)`` — pass explicitly
    only if a test wants to drive a non-default arm-name/profile pair
    (none of the production code paths should).

    ``model_id`` and ``model_sampling`` override the profile's defaults
    — useful when the CLI ``--model`` flag flips the model on the fly,
    or when a test wants to assert that an override propagates.

    ``policy_permutation_seed`` is required (and non-None) when
    ``profile.diagnostic`` is True; the runner refuses to sign a
    diagnostic receipt without a seed. For non-diagnostic arms it
    must be None — passing a seed there is a contract violation.
    """
    if profile is None:
        profile = get_profile(arm_name)
    if profile.arm_name != arm_name:
        raise ValueError(
            f"Profile mismatch: profile.arm_name={profile.arm_name!r} "
            f"but arm_name={arm_name!r}. Pass the matching profile or "
            f"omit it and let get_profile() resolve."
        )

    if profile.diagnostic and policy_permutation_seed is None:
        raise ValueError(
            f"arm {arm_name!r} is diagnostic; policy_permutation_seed "
            "is required (the runner needs to bind WHICH permutation "
            "produced this receipt into the integrity hash)."
        )
    if not profile.diagnostic and policy_permutation_seed is not None:
        raise ValueError(
            f"arm {arm_name!r} is not diagnostic; policy_permutation_seed "
            "must be None (passing one would mis-attribute the receipt "
            "as diagnostic at audit time)."
        )

    resolved_model_id = model_id if model_id is not None else profile.model_id
    resolved_sampling = (
        dict(model_sampling)
        if model_sampling is not None
        else dict(profile.model_sampling)
    )

    fields = dict(context.get("fields") or {})
    fields["l3_arm"] = profile.l3_arm
    fields["nudge_excised"] = profile.nudge_excised
    fields["model_id"] = resolved_model_id
    fields["model_sampling"] = resolved_sampling
    fields["diagnostic"] = profile.diagnostic
    fields["policy_permutation_seed"] = policy_permutation_seed
    fields["runner_git_commit"] = runner_git_commit
    fields["prereg_tag"] = PREREG_TAG

    new_context = dict(context)
    new_context["fields"] = fields
    return new_context


# ---------------------------------------------------------------------------
# Placeholder handlers — replaced in scope by E3-002..E3-008
# ---------------------------------------------------------------------------
#
# Each placeholder accepts a record and returns a deterministic stub
# prompt of the shape ``[arm:<name>] <decision_type> ocid=<ocid>``. The
# stub is recognisable in logs ("this run used placeholders, not the
# real handler") and just structured enough that the CLI's --dry path
# (no live API calls) can emit it without raising.
#
# The placeholders take **kwargs so any caller that pre-emptively
# passes e.g. precedent_selector= doesn't crash. The dispatch() helper
# above also filters kwargs by signature, so either pattern is safe.


def _placeholder(arm_name: str) -> ArmHandler:
    """Build a typed placeholder for ``arm_name``. Surfaced as a
    factory so each registration line stays a single readable
    ``@register(...)`` call without copy-pasted bodies."""

    @register(arm_name)
    def handler(record: Mapping[str, Any], **_kwargs: Any) -> str:
        decision_type = record.get("decision_type", "procurement_decision")
        ocid = record.get("ocid") or (
            record.get("metadata", {}).get("ocid")
            if isinstance(record.get("metadata"), Mapping)
            else None
        )
        return f"[arm:{arm_name}] {decision_type} ocid={ocid}"

    return handler


for _arm in ARM_NAMES:
    _placeholder(_arm)

# Sanity check the foundation lays a complete table. If a future edit
# adds an arm to ARM_NAMES but forgets to add it above, this fires at
# import time rather than at first dispatch.
_missing = set(ARM_NAMES) - set(HANDLERS.keys())
if _missing:
    raise RuntimeError(
        f"Arm registry incomplete at import: missing {_missing!r}. "
        f"Update the placeholder loop in arms.py."
    )


# ---------------------------------------------------------------------------
# Real-handler imports — replace placeholder entries
# ---------------------------------------------------------------------------
#
# Each build package (E3-002..E3-006, E3-008) adds a module here whose
# top-level @register(...) call overwrites the placeholder entry for
# that arm. Imports go at the BOTTOM of this file because they depend
# on register / ARM_NAMES / HANDLERS being defined above.
#
# Import side effects only — we don't re-export the handler symbols
# (callers reach them via HANDLERS / dispatch / register, not by name).
#
# Placeholders for arms whose handler module hasn't landed yet remain
# in HANDLERS unchanged.

from . import arm_a as _arm_a  # noqa: F401, E402  (Arm A — E3-002)
from . import arm_b as _arm_b  # noqa: F401, E402  (Arm B — E3-003)
