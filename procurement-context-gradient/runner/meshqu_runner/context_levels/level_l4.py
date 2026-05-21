"""L4 (Full policy envelope) prompt-payload generator.

Per `planning/context_ladder_design.md` §L4, the L4 prompt is the L3
prompt plus the full ratified policy JSON for snapshot `cbf12348-…`,
formatted as a structured `## Policy under evaluation` block.

## Cache-preservation placement

OpenAI's prompt cache hits on a *stable prefix* of the user message
(combined with the unchanged system prompt). For the L4 batch — 283
records all paired with the same ~4,500-token policy block — the
realised input-token cost is dominated by whether that policy block
sits inside the cached prefix or after a per-call-varying section.

The naive composition produced by `compose_user_message` is

    L0_addendum + L1_addendum + L2_addendum + L3_addendum + L4_addendum + base_record

That puts the policy AFTER L3 (which becomes per-record-varying once
E2-004 lands the nearest-neighbour selector). The policy text is then
re-uploaded on every L4 call and the cache never helps.

The L4 handler here overrides composition via `compose_full_message`
(an optional Protocol extension on `LevelHandler` introduced for
exactly this case). It produces a re-ordered message:

    L4_policy_envelope + L1_addendum + L2_addendum + L3_addendum + base_record
    \\__________________ stable prefix _________________/   \\__ varying ___/

The L1 + L2 sections are stable across the L4 batch too, so the cache
prefix extends through them. The break point is wherever the first
per-record-varying content begins (today: base_record; after E2-004:
L3_addendum's precedent block). Either way, the ~4,500-token policy
block is fully cached after the first L4 call.

## Additivity trade-off — surfaced for the record

The lock-spec invariant in `context_ladder_design.md` §"Additivity
invariant" reads: "Each level adds to the previous, never replaces.
The L0 prompt is the floor. Every higher-level prompt contains it
verbatim."

CONTAINMENT survives the reorder — every L3-level character is still
present inside the L4 composition. POSITION does not — L3's section
no longer sits at the same offset in the L4 message that it does in
the L3 message. The package prompt's test spec §3 phrases the
invariant as "L4 prompt strictly contains the L3 prompt's content
(additivity invariant)" — containment, not position. We honour the
design intent and the package test spec; we relax the legacy substring
assertion in `test_multi_pass.test_user_message_composition_is_additive`
(the E2-001 stub-era test that pinned positional ordering when no
level was yet moving content for cache reasons).

The trade-off is recorded in `decision_log.md` so reviewers see the
move explicitly.

## E2-006 hook

The Permuted-Policy diagnostic (E2-006) needs to swap the policy bytes
without re-implementing the envelope rendering. `render_l4_envelope`
exposes the rendering primitive — E2-006 calls it with a permuted
policy dict and gets a structurally-identical envelope back. The
handler's `compose_full_message` accepts the rendered envelope from
`render(prompts)`; E2-006 can subclass / wrap to swap in its permuted
rendering.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..level_handlers import (
    MAIN_LEVELS,
    GovernanceContextLevel,
    LevelHandler,
)
from ..prompt_loader import LevelPrompt, LoadedPrompts


# ---------------------------------------------------------------------------
# Locked rendering constants
# ---------------------------------------------------------------------------

POLICY_INTERPOLATION_KEY = "{policy_snapshot_json}"
"""The placeholder string in the Stage A envelope template that we
substitute with the rendered policy JSON. Locked at Stage A — if the
envelope file ever stops carrying this exact string the L4 handler
fails loudly."""

POLICY_JSON_INDENT = 2
"""Pretty-print indent for the policy JSON when interpolated into the
envelope. Locked — the SHA-256 of the rendered envelope is computed
against THIS rendering, and downstream verifiers re-render with the
same indent to recompute. Do not change without a new
predictions-lock tag."""

ENVELOPE_TEMPLATE_FILENAME = "L4_policy_envelope.md"
"""Stage A file path under prompts/. Locked at PR #48."""


# ---------------------------------------------------------------------------
# Policy + envelope loading
# ---------------------------------------------------------------------------


class StageAEnvelopeError(RuntimeError):
    """Raised when the L4 envelope template has drifted from the locked
    Stage A spec — missing interpolation token, duplicated token, or
    structurally incompatible with the L4 handler's contract."""


def load_policy_snapshot(policy_path: Path) -> dict[str, Any]:
    """Read the locked policy snapshot file.

    The file is persisted as a single-line compact JSON document
    (see `policy/policy-snapshot-cbf12348.json` — committed at Phase 0).
    We parse it back into a Python dict for `render_policy_block` to
    pretty-print. Key ordering in the on-disk file is already sorted
    (verified at Phase 0); pretty-printing with sort_keys=True is
    therefore byte-identical to sort_keys=False, so re-serialisation
    is deterministic.

    Raises FileNotFoundError if the snapshot is missing.
    Raises json.JSONDecodeError if the file is malformed.
    """
    raw = policy_path.read_text(encoding="utf-8")
    return json.loads(raw)


def render_policy_block(policy: Mapping[str, Any]) -> str:
    """Render the policy dict as pretty-printed JSON for embedding into
    the envelope template.

    Locked rendering: `indent=2`, `ensure_ascii=False`, `sort_keys=True`.
    The locked snapshot's keys are already in sorted order so
    sort_keys=True is a fixed point. ensure_ascii=False preserves any
    non-ASCII glyphs in the policy (e.g. en-dash in rule descriptions)
    rather than escaping them; the SHA-256 binds against the literal
    Unicode rendering.
    """
    return json.dumps(
        policy,
        indent=POLICY_JSON_INDENT,
        ensure_ascii=False,
        sort_keys=True,
    )


def render_l4_envelope(envelope_template: str, policy: Mapping[str, Any]) -> str:
    """Substitute the policy JSON into the Stage A envelope template.

    The template MUST contain the literal token `{policy_snapshot_json}`
    exactly once. If it appears zero times — Stage A drift — we raise.
    If it appears more than once — also raise; the locked envelope at
    PR #48 has it once and only once.

    Exposed as a public function so the Permuted-Policy diagnostic
    (E2-006) can reuse the rendering on a permuted policy dict without
    re-implementing the envelope.
    """
    occurrences = envelope_template.count(POLICY_INTERPOLATION_KEY)
    if occurrences == 0:
        raise StageAEnvelopeError(
            f"L4 envelope is missing the {POLICY_INTERPOLATION_KEY!r} "
            f"interpolation token. Stage A content has drifted from the "
            f"locked v0.2 spec."
        )
    if occurrences > 1:
        raise StageAEnvelopeError(
            f"L4 envelope contains {POLICY_INTERPOLATION_KEY!r} "
            f"{occurrences} times — expected exactly 1."
        )
    policy_block = render_policy_block(policy)
    return envelope_template.replace(POLICY_INTERPOLATION_KEY, policy_block)


def sha256_rendered_envelope(rendered: str) -> str:
    """SHA-256 of the rendered L4 envelope (utf-8 bytes).

    This is the artefact bound into the run manifest as
    `prompt_template_sha256.L4_rendered` so a re-run can prove the
    policy JSON it embedded matches what the locked Stage A run saw.
    """
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


@dataclass
class L4PolicyEnvelopeHandler:
    """The production L4 handler.

    Reads the locked policy snapshot once at construction time and
    caches the rendered envelope text. The same rendered string is
    therefore sent on every L4 call in the batch — which is exactly
    what makes OpenAI's prompt cache hit on the policy block.

    Replaces the E2-001 stub `L4Handler` in
    `level_handlers.default_main_handlers()` via the registry
    replacement pattern:

        handlers = default_main_handlers()
        handlers["L4"] = L4PolicyEnvelopeHandler(
            policy_path=POLICY_SNAPSHOT_PATH,
        )
        # pass `handlers` to run_multi_pass(...)
    """

    policy_path: Path
    level: GovernanceContextLevel = "L4"
    # Cached rendering — populated on first build_addendum / compose call.
    _rendered_envelope: str | None = field(default=None, init=False, repr=False)
    _rendered_sha256: str | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Public surface — rendering + cache placement
    # ------------------------------------------------------------------

    @property
    def rendered_envelope(self) -> str:
        """The L4 envelope with the policy JSON interpolated. Cached so
        the SHA stays stable for the lifetime of the handler instance."""
        if self._rendered_envelope is None:
            raise RuntimeError(
                "rendered_envelope accessed before render(); call render(prompts) first"
            )
        return self._rendered_envelope

    @property
    def rendered_sha256(self) -> str:
        if self._rendered_sha256 is None:
            raise RuntimeError(
                "rendered_sha256 accessed before render(); call render(prompts) first"
            )
        return self._rendered_sha256

    def render(self, prompts: LoadedPrompts) -> str:
        """Eagerly render the envelope and cache. Idempotent — repeated
        calls with the same prompts produce the same bytes."""
        envelope_prompt: LevelPrompt = prompts.get("L4")
        policy = load_policy_snapshot(self.policy_path)
        rendered = render_l4_envelope(envelope_prompt.content, policy)
        self._rendered_envelope = rendered
        self._rendered_sha256 = sha256_rendered_envelope(rendered)
        return rendered

    # ------------------------------------------------------------------
    # LevelHandler protocol — backward-compat surface (build_addendum)
    # ------------------------------------------------------------------

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        """Return the L4 addendum — the rendered envelope wrapped in a
        trailing newline so it concatenates cleanly with sibling
        addenda.

        This method is used by `compose_user_message` ONLY as a
        fallback for callers that don't honour `compose_full_message`
        (the Protocol extension that this handler also implements).
        Today the compose function in `level_handlers.py` checks for
        `compose_full_message` first; this addendum path is therefore
        the non-cache-friendly composition — kept for backward compat
        and so the same handler can be inspected by tests that examine
        just the marginal contribution.
        """
        if self._rendered_envelope is None:
            self.render(prompts)
        assert self._rendered_envelope is not None  # for type-checker
        # The rendered envelope already includes the section header
        # ("## Policy under evaluation") from the Stage A template, so
        # no additional wrapping is needed.
        return self._rendered_envelope + "\n"

    # ------------------------------------------------------------------
    # Cache-friendly composition — the load-bearing override
    # ------------------------------------------------------------------

    def compose_full_message(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
        handlers: Mapping[GovernanceContextLevel, LevelHandler],
        base_message: str,
    ) -> str:
        """Produce the full L4 user message with the policy block
        FIRST in the stable prefix.

        Layout:

            <L4 policy envelope>            <-- stable, ~4,500 tokens
            <L1 addendum>                   <-- stable, ~150 tokens
            <L2 addendum>                   <-- stable, ~250 tokens
            <L3 addendum>                   <-- per-record-varying after E2-004
            <base_message>                  <-- per-record-varying

        Why policy first (rather than L1 + L2 + policy + L3 + base):

        OpenAI's cache match is *prefix*-based. The longest stable
        prefix wins. Putting the policy first guarantees the largest
        single contributor to the prefix length is cached from the
        first call onward. L1 + L2 sit immediately after, also stable,
        so the cached prefix grows to include them too. The first
        per-call-varying byte ends the cache prefix; everything after
        is billed at full rate.

        This is the explicit composition path the package prompt
        requires; `level_handlers.compose_user_message` detects the
        presence of this method on the L4 handler and delegates to it
        instead of running the default additive concat.
        """
        if self._rendered_envelope is None:
            self.render(prompts)
        assert self._rendered_envelope is not None  # for type-checker

        # Pull the L0..L3 addenda from the sibling handlers. The L4
        # block we add at the TOP; the L1..L3 blocks follow, then the
        # base record message.
        lower_addenda: list[str] = []
        for lower_level in MAIN_LEVELS[: MAIN_LEVELS.index("L4")]:
            lower_addenda.append(
                handlers[lower_level].build_addendum(
                    record=record, ocid=ocid, prompts=prompts
                )
            )

        # The policy envelope at the head. Trailing newline ensures the
        # L1 header (if any) starts on its own line, matching the
        # additive-concat spacing of the default path.
        head = self._rendered_envelope + "\n"
        tail = "".join(part for part in lower_addenda if part)
        if tail:
            return f"{head}{tail}\n{base_message}"
        # No lower addenda (e.g. all Stage A prompts empty) — preserve
        # the single-newline gap between head and base_message.
        return f"{head}\n{base_message}"


# ---------------------------------------------------------------------------
# Convenience factory — used by tests + the multi_pass wiring
# ---------------------------------------------------------------------------


def build_l4_handler(policy_path: Path) -> L4PolicyEnvelopeHandler:
    """Construct an L4 handler bound to the given policy snapshot.

    Typical wiring (in the multi_pass driver):

        from meshqu_runner.level_handlers import default_main_handlers
        from meshqu_runner.context_levels.level_l4 import build_l4_handler

        handlers = default_main_handlers()
        handlers["L4"] = build_l4_handler(policy_snapshot_path)
    """
    return L4PolicyEnvelopeHandler(policy_path=policy_path)
