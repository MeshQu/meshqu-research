"""E3-008 — Scaled Permuted-Policy diagnostic arms.

Two arms registered here — ``diagnostic_primary`` and
``diagnostic_claude`` — running E2's Permuted-Policy diagnostic over the
**locked n=100 OCID subset** (``planning/diagnostic_subset.json``).

The two arms are **record-matched**: same 100 OCIDs in the same order,
same operator-permutation, same policy snapshot, same seed
(``LOCKED_PERMUTATION_SEED = 0``). The only varying axis is the model.

## What the handlers render

Both handlers render the **L4 envelope with the operator-permuted
policy** — byte-identical to E2's 14-record diagnostic for the same
policy + seed combination. The renderer pipeline is:

    1. Read E2's locked ``L4_policy_envelope.md`` (byte-identical to
       what E2's diagnostic used — same SHA as the on-disk file).
    2. Strip leading HTML comments via
       ``prompt_loader.strip_leading_html_comments`` (idempotent on
       E2's envelope, which has no leading comment; applied uniformly
       so a future edit adding a leading methodological header to E2's
       file would not silently bleed into the rendered prompt).
    3. Load the locked policy snapshot (E2's ``policy-snapshot-cbf12348.json``;
       SHA ``5d7d8001…``, reused verbatim).
    4. Apply ``permute_policy(policy, seed=LOCKED_PERMUTATION_SEED)`` —
       the E2 inverter, unchanged. Every rule's primary operator is
       flipped (max↔min, forbidden↔required, required_fields↔
       forbidden_fields).
    5. Render the envelope around the permuted policy via
       ``render_l4_envelope`` — same indent / sort_keys / ensure_ascii
       locked rendering parameters.

The rendered **envelope** is record-independent (it embeds only the
policy, not record fields). But the handler returns the FULL user
message: ``<permuted L4 envelope> + "\n" + <base_user_message>`` —
the base user message is composed in by the handler itself. That
means:

- The envelope prefix has the same SHA for every OCID within an arm
  (cache-friendly for the model serving infrastructure — longest
  stable prefix wins).
- The trailing per-record JSON varies, so the full user-message SHA
  differs per record (verified in
  ``tests/test_handler_record_composition.py``).
- Across the two diagnostic arms the rendered prompt is byte-identical
  per-record — only the agent dispatch differs (verified in
  ``tests/test_scaled_diagnostic.py::test_arms_render_identical_prompts``).

The composition layout — envelope first, record-trailing — mirrors
E2's ``level_l4.compose_full_message`` ordering policy and is
**load-bearing for OpenAI prompt caching** (cache hits require the
longest stable prefix). DO NOT reorder.

The Wave-2 ``run_arm`` orchestrator does NOT compose the base user
message on the handler's behalf — see ``multi_pass.py:588-592``: the
handler is self-contained, "Arm handler returns the FULLY rendered
user message — no additive composition, no level prefix." The receipt's
integrity hash binds the diagnostic ``policy_permutation_seed`` field
(via ``inject_arm_fields``) plus the record's per-call fields (via the
standard ``agent_*`` fields).

## Composition contract — the handler IS self-contained

The handler accepts ``record`` and uses it to build the per-record
base user message via ``eval_loop.build_user_message`` — the same
canonical-JSON serialisation E1/E2 used. The base user message
trails the rendered envelope.

``**_ignored`` swallows kwargs other arms need (precedent selector,
archive, etc.) without crashing. The diagnostic arm has no per-record
state beyond the record's own fields + substrate_notes.

## Decision Point — Claude adapter contract (Path A taken)

The Claude adapter at ``agents/claude.py`` returns a ``dict``, not an
``AgentResponse`` (see decision_log "Wave 2 close-out" lesson + the
E3-006 entry). The runner's existing ``run_arm`` orchestration
assumes ``agent.evaluate(...) -> AgentResponse``. We bridge the gap by
wrapping ``claude.call()`` in a small ``ClaudeAgent`` class that
implements the ``Agent`` protocol (``.evaluate``, ``.model_id``,
``.temperature``, ``.system_prompt_sha256``).

This keeps ``run_arm`` uniform across primary and Claude arms — no
second orchestration code path for the diagnostic_claude arm. The
wrapper lives next to the Claude adapter at ``agents/claude.py``
(see ``ClaudeAgent`` there).

## Decision Point — Permutation mechanism (locked, inherited from E2)

The permutation is **systematic** (not random): every rule's primary
condition operator is flipped uniformly across all 6 rules. The
``seed`` parameter on ``permute_policy`` is plumbed through but
**unused inside the function body** — reserved for future stochastic
variants. For E2 + E3 it is locked at ``LOCKED_PERMUTATION_SEED = 0``;
scaling from 14 to 100 records does not reseed.

The seed is still bound into every diagnostic receipt's integrity hash
via ``policy_permutation_seed`` so a future variant carrying a non-zero
seed (e.g. "flip a random 3-of-6 operators") would be
cryptographically distinguishable from this seed-0 baseline.

## Hard rails honoured

- E2's permutation function is reused unchanged (imported, not forked).
- E2's L4 envelope is read from E2's tree (no copy into E3 — copying
  would create a second SHA for the same locked content).
- E2's policy snapshot is read from E2's tree (same reasoning).
- The locked subset file is the source of truth — the handler does
  not re-invoke the selector at runtime. The driver script
  ``scripts/run_scaled_diagnostic.py`` reads the JSON via
  ``load_diagnostic_subset``.
- The receipt's integrity payload carries ``diagnostic: true`` +
  ``policy_permutation_seed`` (via ``ArmProfile.diagnostic`` and the
  CLI / driver-script ``--policy-permutation-seed`` plumbing) — the
  Wave-2 foundation already wired these fields.
- The Claude adapter's signature is **not modified**; the ``ClaudeAgent``
  wrapper adapts to the ``Agent`` protocol from the outside.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import register
from ..context_levels.level_l4 import (
    POLICY_INTERPOLATION_KEY,
    StageAEnvelopeError,
    load_policy_snapshot,
    render_l4_envelope,
    sha256_rendered_envelope,
)
from ..diagnostic.permute_policy import (
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    permute_policy,
)
from ..eval_loop import build_user_message
from ..prompt_loader import strip_leading_html_comments


# ---------------------------------------------------------------------------
# Locked paths — same content E2's diagnostic used; re-used verbatim
# ---------------------------------------------------------------------------

_RUNNER_DIR = Path(__file__).resolve().parent.parent.parent
"""``procurement-context-disambiguation/runner``."""

_E3_REPO_DIR = _RUNNER_DIR.parent
"""``procurement-context-disambiguation``."""

_MONOREPO_DIR = _E3_REPO_DIR.parent
"""Repo root — ``procurement-context-disambiguation`` and
``procurement-context-gradient`` are siblings here."""

DEFAULT_ENVELOPE_PATH = (
    _MONOREPO_DIR
    / "procurement-context-gradient"
    / "runner"
    / "prompts"
    / "L4_policy_envelope.md"
)
"""E2's L4 envelope. Read-only at run time. SHA-bound by E2's locked
content set. The diagnostic re-uses the EXACT bytes E2's 14-record
diagnostic used so the 14-record-subset regression check is a real
byte-identity assertion, not an "equivalent rendering" approximation."""

DEFAULT_POLICY_SNAPSHOT_PATH = (
    _MONOREPO_DIR
    / "procurement-context-gradient"
    / "policy"
    / "policy-snapshot-cbf12348.json"
)
"""E2's locked policy snapshot — SHA ``5d7d8001…``. Reused verbatim;
the permuted variant is computed in-memory via ``permute_policy``."""


# ---------------------------------------------------------------------------
# Renderer — record-independent
# ---------------------------------------------------------------------------


def render_permuted_l4_envelope(
    *,
    envelope_path: Path = DEFAULT_ENVELOPE_PATH,
    policy_snapshot_path: Path = DEFAULT_POLICY_SNAPSHOT_PATH,
    seed: int = LOCKED_PERMUTATION_SEED,
) -> str:
    """Render the L4 envelope around the operator-permuted policy.

    Returns the rendered user-message envelope string. The rendering is
    deterministic and record-independent — same envelope + same policy
    + same seed always produces the same bytes (the seed is locked at
    0 for E3; future stochastic variants would vary here).

    Steps mirror the L4PermutedPolicyHandler.render path verbatim so
    the diagnostic's byte-identity claim against E2 holds:

      1. Read E2's envelope template.
      2. Strip leading HTML comments (idempotent on E2's file, which
         carries no leading comment; applied uniformly).
      3. Verify the policy interpolation token survives the strip.
      4. Load + permute the policy snapshot.
      5. Strip the _permutation_log entry from the dict before
         rendering — the log is runner-local provenance; leaking it
         into the prompt would give the agent a hint that the policy
         is adversarially modified (and would defeat the diagnostic).
      6. Render via E2's locked ``render_l4_envelope`` primitive.

    Used by both ``diagnostic_primary`` and ``diagnostic_claude`` — the
    rendered prompt is identical across the two arms (only the agent
    dispatch differs). Verified in
    ``tests/test_scaled_diagnostic.py::test_arms_render_identical_prompts``.
    """
    raw = envelope_path.read_text(encoding="utf-8")
    stripped = strip_leading_html_comments(raw)
    if POLICY_INTERPOLATION_KEY not in stripped:
        raise StageAEnvelopeError(
            f"After stripping leading HTML comments from {envelope_path}, "
            f"the {POLICY_INTERPOLATION_KEY!r} interpolation token is "
            f"missing. The strip must not consume the policy placeholder."
        )

    policy = load_policy_snapshot(policy_snapshot_path)
    permuted = permute_policy(policy, seed=seed)
    # Strip _permutation_log before passing to the envelope renderer —
    # the log is runner-local provenance, not policy text, and must
    # never reach the LLM. Mirrors L4PermutedPolicyHandler.render.
    prompt_policy = {k: v for k, v in permuted.items() if k != PERMUTATION_LOG_KEY}
    return render_l4_envelope(stripped, prompt_policy)


def rendered_envelope_sha256(
    *,
    envelope_path: Path = DEFAULT_ENVELOPE_PATH,
    policy_snapshot_path: Path = DEFAULT_POLICY_SNAPSHOT_PATH,
    seed: int = LOCKED_PERMUTATION_SEED,
) -> str:
    """SHA-256 of the rendered permuted-L4 envelope.

    Exposed so the driver script can stamp the SHA into the
    inverted-operator-spec sidecar header (audit aid — the rubric tool
    + the writeup methods section both want to cite the rendered
    bytes by hash)."""
    return sha256_rendered_envelope(
        render_permuted_l4_envelope(
            envelope_path=envelope_path,
            policy_snapshot_path=policy_snapshot_path,
            seed=seed,
        )
    )


# ---------------------------------------------------------------------------
# Per-record base message composition
# ---------------------------------------------------------------------------


def _compose_base_user_message(record: Mapping[str, Any]) -> str:
    """Render the per-record base user message via E1/E2's canonical
    serialiser.

    The base message is the only record-varying component of the
    diagnostic user message. It carries the substrate-derived
    ``fields`` plus each field's substrate-honesty provenance
    (``substrate_notes``) — same shape E1's main grid + E2's L0/L1/L2/L3
    arms used, so the diagnostic's prompt-side substrate posture
    matches the rest of the experiment programme.

    See ``eval_loop.build_user_message`` for the canonical-JSON
    serialisation contract (``sort_keys=True``, ``ensure_ascii=False``,
    ``separators=(',', ':')``).
    """
    return build_user_message(
        context={
            "decision_type": record.get("decision_type", "procurement_decision"),
            "fields": record.get("fields") or {},
            "metadata": dict(record.get("metadata") or {}),
        },
        substrate_notes=record.get("substrate_notes") or {},
    )


# ---------------------------------------------------------------------------
# Arm registration — diagnostic_primary
# ---------------------------------------------------------------------------


@register("diagnostic_primary")
def diagnostic_primary_handler(
    record: Mapping[str, Any],
    *,
    envelope_path: Path | None = None,
    policy_snapshot_path: Path | None = None,
    seed: int | None = None,
    **_ignored: Any,
) -> str:
    """Render the permuted-L4 envelope + per-record base user message
    for the primary-model diagnostic.

    Composition layout (mirrors E2's ``compose_full_message`` policy-
    at-head ordering for cache-prefix preservation):

        <permuted L4 envelope>      ← record-independent, cache-friendly
        \\n
        <base user message JSON>    ← record-varying

    Both diagnostic arms render identical bytes for the same record —
    only the agent dispatch (primary OpenAI vs Claude) differs.

    Kwargs give tests a way to swap in alternative locked paths or a
    non-zero seed for stochastic-variant smoke tests without
    monkey-patching. Production code calls this with no kwargs and gets
    the locked defaults (E2's L4 envelope, E2's policy snapshot, seed
    0).

    ``**_ignored`` swallows kwargs the dispatcher may forward for other
    arms (e.g. ``precedent_selector``, ``archive``).
    """
    rendered_envelope = render_permuted_l4_envelope(
        envelope_path=envelope_path if envelope_path is not None else DEFAULT_ENVELOPE_PATH,
        policy_snapshot_path=(
            policy_snapshot_path
            if policy_snapshot_path is not None
            else DEFAULT_POLICY_SNAPSHOT_PATH
        ),
        seed=seed if seed is not None else LOCKED_PERMUTATION_SEED,
    )
    base_user_message = _compose_base_user_message(record)
    return rendered_envelope + "\n" + base_user_message


# ---------------------------------------------------------------------------
# Arm registration — diagnostic_claude
# ---------------------------------------------------------------------------


@register("diagnostic_claude")
def diagnostic_claude_handler(
    record: Mapping[str, Any],
    *,
    envelope_path: Path | None = None,
    policy_snapshot_path: Path | None = None,
    seed: int | None = None,
    **_ignored: Any,
) -> str:
    """Render the permuted-L4 envelope + per-record base user message
    for the Claude diagnostic.

    Byte-identical rendering to ``diagnostic_primary_handler`` for the
    same record — the spec requires the cross-model comparison to vary
    only on the model. The agent dispatch (primary OpenAI ``Agent`` vs
    ``ClaudeAgent``) is where the two arms diverge, not here.

    The cross-arm byte-identity property is asserted in
    ``tests/test_scaled_diagnostic.py::test_arms_render_identical_prompts``.
    """
    rendered_envelope = render_permuted_l4_envelope(
        envelope_path=envelope_path if envelope_path is not None else DEFAULT_ENVELOPE_PATH,
        policy_snapshot_path=(
            policy_snapshot_path
            if policy_snapshot_path is not None
            else DEFAULT_POLICY_SNAPSHOT_PATH
        ),
        seed=seed if seed is not None else LOCKED_PERMUTATION_SEED,
    )
    base_user_message = _compose_base_user_message(record)
    return rendered_envelope + "\n" + base_user_message


__all__ = [
    "DEFAULT_ENVELOPE_PATH",
    "DEFAULT_POLICY_SNAPSHOT_PATH",
    "diagnostic_claude_handler",
    "diagnostic_primary_handler",
    "rendered_envelope_sha256",
    "render_permuted_l4_envelope",
]
