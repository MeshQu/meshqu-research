"""E3-005 — L4-without-nudge handler.

A surgical fork of E2's L4 envelope handler. Renders the locked
``L4_without_nudge.md`` envelope (everything that E2's L4 envelope had,
minus the closing anti-sycophancy nudge sentence) with the same locked
policy snapshot, then returns the fully assembled user message.

## Why this arm exists

E2's L3 → L4 transition flipped overall agreement-with-MeshQu rates in
a way the writeup attributed to the anti-sycophancy nudge ("If a rule
cannot be confidently evaluated…"). E3 Framing A asks whether that
attribution is right:

  A.1 — the nudge alone drove the L3 → L4 movement (then this arm
        should look more like L3 than like E2's L4)
  A.2 — the policy text alone drove it (then this arm should look just
        like E2's L4, and the nudge was decorative)

By rendering the SAME envelope as E2's L4 minus the single nudge
sentence and re-evaluating the same record set, the comparison
isolates the nudge clause as the independent variable.

## The HTML-comment-strip resolution (Sam, 2026-05-28)

The locked ``L4_without_nudge.md`` file on disk opens with a
multi-line HTML comment that quotes the nudge sentence verbatim —
methodological documentation aimed at human reviewers of the locked
content. From the LLM's perspective the "excised" nudge is still in
the prompt (inside the comment), and the file is longer than E2's
``L4_policy_envelope.md`` because of the comment. The raw-file
byte-identity-minus-the-nudge claim is therefore false.

Resolution: the locked file's bytes stay untouched on disk (the
``v0.3-predictions-locked`` SHA continues to bind the file), and the
renderer strips leading HTML comments before substituting the policy
JSON and sending the prompt to the LLM. The byte-identity invariant
test compares ``strip(L4_without_nudge.md) -> render(policy)`` to
E2's ``L4_policy_envelope.md -> render(policy)`` and asserts the
diff is exactly the nudge sentence.

The strip utility lives at the prompt-loader level
(``meshqu_runner.prompt_loader.strip_leading_html_comments``) so any
future arm whose locked content carries a leading methodological
header can reuse it.

## Composition layout

The handler returns the FULL user message — per ``multi_pass.py:588-592``
arm handlers are self-contained ("Arm handler returns the FULLY
rendered user message — no additive composition, no level prefix.").
Layout:

    <L4-without-nudge envelope>     ← record-independent, cache-friendly
    \\n
    <base user message JSON>        ← record-varying

The envelope-first / record-trailing order mirrors E2's
``level_l4.compose_full_message`` policy-at-head ordering and is
**load-bearing for OpenAI prompt caching** (the longest stable prefix
wins cache hits). DO NOT reorder.

## What this handler does NOT do (out of scope)

- It does not add L0..L3 prefixes the way E2's L4 user message did.
  E3's arm-keyed dispatch model treats each arm as a self-contained
  probe (see ``meshqu_runner.arms`` module docstring); there is no
  cross-level addendum. E2's L4 handler's ``compose_full_message``
  re-ordered with L1..L3 in tow for prompt-cache reasons; that
  re-ordering is a cross-level concern E3 has deliberately retired.
  E3 keeps the same envelope-first cache-friendly ordering by
  trailing the per-record base message AFTER the envelope.
- It does not mutate ``L4_without_nudge.md``. The locked file stays
  byte-for-byte the same; the strip happens on the in-memory copy.
- It does not re-author the policy snapshot. The same locked snapshot
  E2's L4 used (``policy-snapshot-cbf12348.json``, SHA
  ``5d7d8001…``) feeds in here — that is the load-bearing point of
  the comparison.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import register
from ..context_levels.level_l4 import (
    POLICY_INTERPOLATION_KEY,
    load_policy_snapshot,
    render_l4_envelope,
)
from ..eval_loop import build_user_message
from ..prompt_loader import strip_leading_html_comments


# ---------------------------------------------------------------------------
# Locked paths
# ---------------------------------------------------------------------------

# Resolve paths relative to the E3 runner package so the handler works
# regardless of the caller's current working directory. Layout:
#
#   procurement-context-disambiguation/
#       runner/
#           meshqu_runner/
#               arms/l4_without_nudge.py           <-- this file
#               context_levels/level_l4.py
#           prompts/
#               L4_without_nudge.md                <-- locked envelope
#   procurement-context-gradient/
#       policy/
#           policy-snapshot-cbf12348.json          <-- locked snapshot
#                                                       (reused from E2)
#
# The locked snapshot lives in E2's directory tree because it IS E2's
# snapshot — re-using the same bytes (and therefore the same SHA) is
# the only way the Framing A.1-vs-A.2 comparison is meaningful. We do
# NOT copy the file into E3; we read from E2's locked location.

_RUNNER_DIR = Path(__file__).resolve().parent.parent.parent
"""``procurement-context-disambiguation/runner``."""

_E3_REPO_DIR = _RUNNER_DIR.parent
"""``procurement-context-disambiguation``."""

_MONOREPO_DIR = _E3_REPO_DIR.parent
"""The repository root — both ``procurement-context-disambiguation`` and
``procurement-context-gradient`` live here as siblings."""

DEFAULT_ENVELOPE_PATH = _RUNNER_DIR / "prompts" / "L4_without_nudge.md"
"""Locked L4-without-nudge envelope. SHA-bound by
``v0.3-predictions-locked``. Read-only at run time."""

DEFAULT_POLICY_SNAPSHOT_PATH = (
    _MONOREPO_DIR / "procurement-context-gradient" / "policy" / "policy-snapshot-cbf12348.json"
)
"""E2's locked policy snapshot. Reused VERBATIM — same bytes, same
SHA — so the nudge-vs-no-nudge comparison isolates the nudge clause
as the only independent variable."""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_l4_without_nudge(
    *,
    envelope_path: Path = DEFAULT_ENVELOPE_PATH,
    policy_snapshot_path: Path = DEFAULT_POLICY_SNAPSHOT_PATH,
) -> str:
    """Render the L4-without-nudge user message.

    Steps:

    1. Read the locked ``L4_without_nudge.md`` envelope from disk.
       The file is NOT mutated.
    2. Strip the leading HTML comment (the methodological header) via
       ``strip_leading_html_comments`` — the LLM must not see the
       header bytes, and in particular must not see the verbatim
       nudge sentence quoted inside the comment.
    3. Sanity-check that the policy interpolation token survived the
       strip (it must, because the token lives well after the leading
       comment). If somehow the strip removed it, we raise the same
       error class E2's renderer uses.
    4. Load the locked policy snapshot and interpolate it via E2's
       ``render_l4_envelope`` — reusing the rendering primitive,
       including its locked ``indent=2, sort_keys=True,
       ensure_ascii=False`` JSON serialisation contract, guarantees
       byte-identity with E2's rendered envelope wherever the source
       text matches.

    Returns the rendered user message string.
    """
    raw = envelope_path.read_text(encoding="utf-8")
    stripped = strip_leading_html_comments(raw)
    if POLICY_INTERPOLATION_KEY not in stripped:
        # render_l4_envelope would surface this too, but raising here
        # gives a clearer message — the strip ate the token, which
        # would only happen if a future edit puts the token inside a
        # leading comment block.
        from ..context_levels.level_l4 import StageAEnvelopeError

        raise StageAEnvelopeError(
            f"After stripping leading HTML comments from {envelope_path}, "
            f"the {POLICY_INTERPOLATION_KEY!r} interpolation token is "
            f"missing. The strip must not consume the policy placeholder."
        )
    policy = load_policy_snapshot(policy_snapshot_path)
    return render_l4_envelope(stripped, policy)


# ---------------------------------------------------------------------------
# Arm registration
# ---------------------------------------------------------------------------


def _compose_base_user_message(record: Mapping[str, Any]) -> str:
    """Render the per-record base user message via E1/E2's canonical
    serialiser.

    See ``eval_loop.build_user_message`` for the canonical-JSON
    serialisation contract (``sort_keys=True``, ``ensure_ascii=False``,
    ``separators=(',', ':')``). Mirrors the equivalent helper in
    ``arms/diagnostic.py``.
    """
    return build_user_message(
        context={
            "decision_type": record.get("decision_type", "procurement_decision"),
            "fields": record.get("fields") or {},
            "metadata": dict(record.get("metadata") or {}),
        },
        substrate_notes=record.get("substrate_notes") or {},
    )


@register("l4_without_nudge")
def l4_without_nudge_handler(
    record: Mapping[str, Any],
    *,
    envelope_path: Path | None = None,
    policy_snapshot_path: Path | None = None,
    **_ignored: Any,
) -> str:
    """Handler entrypoint — registered against the arm name
    ``l4_without_nudge``.

    Returns the FULL user message: the L4-without-nudge envelope
    (record-independent — every record sees the same policy block)
    followed by the per-record base user message (record-varying —
    carries the substrate-derived ``fields`` + ``substrate_notes``).
    Layout matches ``arms/diagnostic.py``'s ``<envelope>\\n<base>``.

    Per ``multi_pass.py:588-592`` the handler is self-contained — the
    orchestrator does NOT compose any additional prefix. If this
    handler returned envelope-only the agent would see no record
    fields and refuse on "no procurement record provided" (the
    2026-05-28 smoke read; fixed by composing the base message in
    this handler).

    Keyword arguments give tests a way to swap in alternative locked
    paths without monkey-patching. Production code calls this with no
    kwargs and gets the locked defaults.

    ``**_ignored`` swallows kwargs the dispatcher may forward for
    other arms (e.g. a precedent selector).
    """
    rendered_envelope = render_l4_without_nudge(
        envelope_path=envelope_path if envelope_path is not None else DEFAULT_ENVELOPE_PATH,
        policy_snapshot_path=(
            policy_snapshot_path
            if policy_snapshot_path is not None
            else DEFAULT_POLICY_SNAPSHOT_PATH
        ),
    )
    base_user_message = _compose_base_user_message(record)
    return rendered_envelope + "\n" + base_user_message


# ---------------------------------------------------------------------------
# Sanity register the l4_with_nudge arm too — same renderer minus the
# strip, pointed at E2's L4 envelope. Convenient for in-runner head-to-
# head comparison in smoke / dry-run; the canonical L4-with-nudge data
# is E2's already-shipped corpus.
# ---------------------------------------------------------------------------

DEFAULT_L4_WITH_NUDGE_PATH = (
    _MONOREPO_DIR
    / "procurement-context-gradient"
    / "runner"
    / "prompts"
    / "L4_policy_envelope.md"
)
"""E2's L4 envelope, read-only. The l4_with_nudge handler reads from
here so a sanity-check dry-run can dispatch both arms against the
same record and observe the diff inside the runner."""


def render_l4_with_nudge(
    *,
    envelope_path: Path = DEFAULT_L4_WITH_NUDGE_PATH,
    policy_snapshot_path: Path = DEFAULT_POLICY_SNAPSHOT_PATH,
) -> str:
    """Render E2's L4 envelope. No leading-comment strip — E2's file
    has no leading comment to strip (the strip is idempotent on it).
    Same policy snapshot, same rendering primitive."""
    raw = envelope_path.read_text(encoding="utf-8")
    # Idempotent for E2's file but applied uniformly so a future edit
    # adding a leading comment to E2's file would not silently bleed
    # into the rendered prompt.
    stripped = strip_leading_html_comments(raw)
    policy = load_policy_snapshot(policy_snapshot_path)
    return render_l4_envelope(stripped, policy)


@register("l4_with_nudge")
def l4_with_nudge_handler(
    record: Mapping[str, Any],
    *,
    envelope_path: Path | None = None,
    policy_snapshot_path: Path | None = None,
    **_ignored: Any,
) -> str:
    """Sanity-comparison handler — renders E2's L4 envelope through
    the same renderer the L4-without-nudge handler uses (modulo the
    surgical strip).

    The canonical L4-with-nudge data set lives in E2's already-shipped
    corpus; this handler exists for in-runner sanity-checks during
    E3 smoke runs (e.g. head-to-head ``l4_with_nudge`` vs
    ``l4_without_nudge`` on one record), not for re-running the corpus.

    Composes the rendered envelope at the head and the record's
    ``build_user_message`` at the tail — same shape as
    ``l4_without_nudge_handler``. The fix from the 2026-05-28
    decision-point #5 read applies here too: this arm is not on the
    smoke / dry-run / full-run matrices, but is registered and could be
    invoked ad-hoc; leaving it envelope-only would silently produce a
    degenerate sanity comparison.
    """
    rendered_envelope = render_l4_with_nudge(
        envelope_path=envelope_path if envelope_path is not None else DEFAULT_L4_WITH_NUDGE_PATH,
        policy_snapshot_path=(
            policy_snapshot_path
            if policy_snapshot_path is not None
            else DEFAULT_POLICY_SNAPSHOT_PATH
        ),
    )
    base_user_message = _compose_base_user_message(record)
    return rendered_envelope + "\n" + base_user_message
