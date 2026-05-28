"""L4_PERMUTED handler — the Permuted-Policy diagnostic L4 pass.

Wraps E2-005's `L4PolicyEnvelopeHandler` rendering primitive with a
permuted policy instead of the ratified one. The handler is opt-in:
the multi-pass orchestrator's default registry does NOT carry it (see
`level_handlers.default_main_handlers()` — the diagnostic is wired up
separately via `diagnostic_handlers()` in
`meshqu_runner/diagnostic/runner.py`).

## Why subclass rather than extend in-place

The build package spec is explicit:

  > DO NOT modify E2-005's L4 handler — extend via wrapper / subclass,
  > or reuse the exported `render_l4_envelope` primitive with permuted
  > bytes.

So this class is a strict subclass of `L4PolicyEnvelopeHandler` that
overrides only `render()` to substitute permuted policy bytes, and
declares its `level` as `"L4_PERMUTED"` so the bundle wrapper picks
up the distinct marker. Everything else — cache-friendly composition,
the LevelHandler Protocol surface, `compose_full_message` — is
inherited verbatim.

## Integrity-hash binding

The diagnostic receipt must be cryptographically distinguishable from
the main-run L4 receipt for the same OCID. Two distinct mechanisms
contribute:

1. **`governance_context_level` field**: already carried into the
   integrity hash via the `context.fields` injection point (see
   `multi_pass._process_pass`). Main run injects `"L4"`; diagnostic
   injects `"L4_PERMUTED"`. Different value → different hash.

2. **`policy_permutation_seed` field**: the diagnostic driver
   additionally injects `policy_permutation_seed: 0` into the fields
   map BEFORE posting. This binds the seed (and, more importantly,
   the *fact* of permutation) into the integrity hash and lets a
   future stochastic-variant land without a shape change.

3. **`l4_envelope_sha256` field**: the diagnostic driver also injects
   the SHA-256 of the rendered permuted envelope. Two reasons:
   - independent provenance — a verifier can recompute and confirm
     the inverted policy bytes match what was rendered;
   - distinct value from the main-run L4 (which would inject the
     same field with the unperturbed envelope SHA), forcing the
     integrity hash to differ even if `governance_context_level`
     were ever conflated.

The Stage A L4 envelope SHA (unperturbed rendering, locked at PR #48)
is `9821bc3167e0412d4f8c54961c8b0545eb062b0db53b7d2cda2dc3cd4dd9bcc7`.
The permuted rendering MUST produce a different SHA — verified at
construction time, fail-loud if not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import the permutation primitives via the submodule directly (NOT
# `..diagnostic`) to avoid a circular import: `diagnostic/__init__.py`
# eagerly imports `diagnostic.runner`, which in turn imports this
# module. Going through the submodule bypasses the package init.
from ..diagnostic.permute_policy import (  # noqa: I100 — see comment above
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    permute_policy,
)
from ..level_handlers import GovernanceContextLevel
from ..prompt_loader import LevelPrompt, LoadedPrompts
from .level_l4 import (
    L4PolicyEnvelopeHandler,
    load_policy_snapshot,
    render_l4_envelope,
    sha256_rendered_envelope,
)


# ---------------------------------------------------------------------------
# Locked SHA — the unperturbed L4 envelope rendering (Stage A + Phase 0 lock)
# ---------------------------------------------------------------------------

UNPERTURBED_L4_RENDERED_SHA256 = (
    "9821bc3167e0412d4f8c54961c8b0545eb062b0db53b7d2cda2dc3cd4dd9bcc7"
)
"""The SHA-256 of the L4 envelope rendered against the UNPERTURBED
policy. Locked at v0.2 — confirmed in the build-package brief. If the
permuted rendering ever collides with this value the inverter has
silently no-op'd; we assert against it in `render()`."""


# ---------------------------------------------------------------------------
# Field names the diagnostic binds into the integrity hash
# ---------------------------------------------------------------------------

POLICY_PERMUTATION_SEED_FIELD = "policy_permutation_seed"
"""Integrity-bound field carrying the permutation seed. Locked at 0
for E2; future stochastic variants may carry other integers. Always
present (never absent) on a diagnostic receipt."""

L4_ENVELOPE_SHA256_FIELD = "l4_envelope_sha256"
"""Integrity-bound field carrying the SHA-256 of the rendered L4
envelope. Locked field name; the *value* differs between main-run L4
and L4_PERMUTED because the policy bytes inside the envelope differ.
This is the load-bearing artefact that makes the integrity hashes
diverge even at byte-level."""


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class PermutedEnvelopeCollisionError(RuntimeError):
    """Raised if the permuted L4 rendering happens to produce the same
    bytes as the unperturbed rendering. Indicates the permutation was
    a no-op for every rule — would corrupt the diagnostic's whole
    premise — and we fail loudly rather than silently emit a receipt
    that promises a permutation that didn't happen."""


@dataclass
class L4PermutedPolicyHandler(L4PolicyEnvelopeHandler):
    """Adversarial-control L4 handler.

    Loads the locked policy snapshot, applies `permute_policy(_, seed)`,
    then renders the same Stage A envelope around the permuted policy.
    The level marker is `L4_PERMUTED` so the bundle wrapper and the
    fields injection both pick up the distinct value.

    Cache-friendly composition (the `compose_full_message` override
    that puts the policy block at the head of the user message) is
    inherited from `L4PolicyEnvelopeHandler` verbatim — the diagnostic
    benefits from the same cache prefix layout (though at 14 calls the
    cache uplift is negligible; we keep the inheritance for behavioural
    parity with the main L4 path).
    """

    level: GovernanceContextLevel = "L4_PERMUTED"  # type: ignore[assignment]
    seed: int = LOCKED_PERMUTATION_SEED
    # Cached SHA of the rendered envelope — recomputed lazily.
    _permuted_policy_cache: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def render(self, prompts: LoadedPrompts) -> str:
        """Eagerly render the envelope using the **permuted** policy.

        Idempotent — repeat calls produce the same bytes.

        Asserts the rendering differs from the unperturbed Stage A
        envelope SHA; if the permutation silently no-op'd we raise
        `PermutedEnvelopeCollisionError` rather than emit a misleading
        receipt.
        """
        envelope_prompt: LevelPrompt = prompts.get("L4")
        policy = load_policy_snapshot(self.policy_path)
        permuted = permute_policy(policy, seed=self.seed)
        # We render against the permuted policy WITHOUT the
        # _permutation_log key — the log is runner-local provenance and
        # belongs on the bundle / inside the integrity-bound fields, NOT
        # leaked into the prompt the agent sees. Adding the log to the
        # prompt would give the agent a free hint that the policy has
        # been adversarially modified, defeating the whole point.
        prompt_policy = {k: v for k, v in permuted.items() if k != PERMUTATION_LOG_KEY}
        rendered = render_l4_envelope(envelope_prompt.content, prompt_policy)
        rendered_sha = sha256_rendered_envelope(rendered)
        if rendered_sha == UNPERTURBED_L4_RENDERED_SHA256:
            raise PermutedEnvelopeCollisionError(
                "Permuted L4 envelope SHA collides with the unperturbed "
                "rendering — the permutation produced no change. This "
                "corrupts the diagnostic's premise. Surface to Sam."
            )
        # Stash on the instance so callers can read the permuted policy
        # (for fields-injection) and the rendered SHA (for receipt
        # binding) without re-computing.
        self._rendered_envelope = rendered  # type: ignore[assignment]
        self._rendered_sha256 = rendered_sha  # type: ignore[assignment]
        self._permuted_policy_cache = permuted
        return rendered

    @property
    def permuted_policy(self) -> dict[str, Any]:
        """The permuted policy dict (with `_permutation_log`). Available
        after `render()` has run. Raises if accessed earlier."""
        if self._permuted_policy_cache is None:
            raise RuntimeError(
                "permuted_policy accessed before render(); call render(prompts) first"
            )
        return self._permuted_policy_cache


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def build_l4_permuted_handler(
    policy_path: Path,
    seed: int = LOCKED_PERMUTATION_SEED,
) -> L4PermutedPolicyHandler:
    """Construct a Permuted-Policy L4 handler bound to the given policy
    snapshot and seed.

    Typical wiring (in the diagnostic driver, not the main loop):

        from meshqu_runner.context_levels.level_l4_permuted import (
            build_l4_permuted_handler,
        )
        diagnostic_handler = build_l4_permuted_handler(policy_snapshot_path)
    """
    return L4PermutedPolicyHandler(policy_path=policy_path, seed=seed)
