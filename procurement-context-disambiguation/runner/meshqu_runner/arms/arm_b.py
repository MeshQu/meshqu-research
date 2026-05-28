"""Arm B handler — precedents, verdict-signal redacted.

Arm B is the **verdict-exemplar disambiguator** in the L3 decomposition.
It uses the *same* kNN selection as Arm A (same 4 precedents per target,
same OCIDs, same archive) but renders those precedents through the
locked ``armB_precedent_no_verdict_format.md`` template — the one with
``meshqu_verdict`` / ``violations`` / ``e1_agent_reasoning_text`` fields
removed.

The contrast (Arm A) minus (Arm B), against the same target records, is
the empirical isolation of the verdict-exemplar effect. The §10
governance-memory reading from E2 predicts a real A−B gap; Reading B
("any sufficient content drives the L3 break") predicts ~zero gap.

## Architectural contract

- **No precedent-selector changes.** Imports
  ``meshqu_runner.precedent_selector.select_precedents`` and uses it
  verbatim. The selector is in the byte-identical-from-E2 set (asserted
  by ``tests/test_fork_parity.py``); touching it would invalidate the
  isolation. Same kNN, same archive, same target ⇒ same OCIDs as Arm A.
  Tested explicitly.
- **Locked template is read but NEVER mutated.**
  ``armB_precedent_no_verdict_format.md`` is bound by
  ``v0.3-predictions-locked``. The handler reads the file bytes
  verbatim, then applies one deterministic transform before rendering:
  it strips a leading HTML comment header (the Wave 2 convention — see
  the build package "Convention from Wave 2 chaos" paragraph). The
  on-disk bytes do not change; only the bytes sent to the LLM differ.
  The contamination check runs on the **post-strip** rendered output
  (the LLM-effective bytes), which is the surface that matters for
  "did verdict signal leak into the prompt the model saw".
- **Defence-in-depth field projection.** The template doesn't reference
  ``meshqu_verdict`` / ``violations`` / ``e1_agent_reasoning_text`` /
  ``e1_agent_recommended_action``, but we don't trust the template to
  carry the whole contract. The renderer explicitly projects each
  ``PrecedentRecord`` onto the **allowed field set** before calling
  ``str.format_map``. If the template ever references a redacted field
  (a regression), ``format_map`` raises ``KeyError`` — loud failure,
  not silent leak.

## Where this lives — the ``arms/`` subpackage

E3-002 (PR #92) refactored ``meshqu_runner.arms`` from a flat module to
a subpackage. The handler-per-file convention is: every arm handler
lives at ``meshqu_runner/arms/<arm_name>.py`` and is imported by
``arms/__init__.py`` at the bottom of the file (after ``register`` /
``ARM_NAMES`` / ``HANDLERS`` are defined). Registration is via the
``@register("arm_b")`` decorator on the handler; the import in
``arms/__init__.py`` is the side effect that wires it into
``HANDLERS``, overwriting the placeholder entry the foundation lays
down for the ``arm_b`` slot.

## Receipt integrity

Default profile (set by ``arms.ARM_PROFILES["arm_b"]``):
``l3_arm: "B"``, ``nudge_excised: False``, ``model_id: gpt-5.4-2026-03-05``,
``diagnostic: False``. ``inject_arm_fields`` binds these into the
integrity hash via ``context.fields``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from . import register
from ..eval_loop import build_user_message
from ..precedent_archive import PrecedentRecord
from ..precedent_selector import DEFAULT_PRECEDENT_COUNT, select_precedents


# ---------------------------------------------------------------------------
# Locked template — resolved relative to the runner package
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parents[2]
"""``procurement-context-disambiguation/runner/`` — the runner root.

Layout: ``<repo>/procurement-context-disambiguation/runner/
meshqu_runner/arms/arm_b.py`` → runner is the file's 2nd parent
(``arms/`` → ``meshqu_runner/`` → ``runner/``)."""

ARM_B_TEMPLATE_PATH = RUNNER_DIR / "prompts" / "armB_precedent_no_verdict_format.md"
"""Locked Arm B template. SHA-bound by ``v0.3-predictions-locked``.
Read-only at run time. The handler verifies presence at first call;
a missing file is a stop condition (the package spec calls this out)."""


# ---------------------------------------------------------------------------
# Wave 2 chaos convention — strip leading HTML comment
# ---------------------------------------------------------------------------
#
# Locked content files may carry leading HTML comment headers documenting
# what surgical change distinguishes them from E2's equivalent. The
# bytes on disk are bound by the v0.3 tag; we don't mutate them. But the
# comment header should not be sent to the LLM — it would leak meta-
# commentary into the prompt and (worse for Arm B specifically) the
# header text explains what was redacted, which would itself be a
# verdict-signal side channel.
#
# Resolution: strip a *single* leading HTML comment block at render
# time. Locked file SHA stays untouched on disk; only the bytes sent
# to the LLM differ. The contamination check runs on the LLM-effective
# bytes (post-strip), not on the raw file.

_LEADING_HTML_COMMENT_RE = re.compile(
    r"\A\s*<!--.*?-->\s*",
    flags=re.DOTALL,
)


def strip_leading_html_comment(template: str) -> tuple[str, str | None]:
    """Return ``(post_strip, stripped_comment)`` — the template with at
    most one leading HTML comment block removed, and the literal text of
    the comment (or ``None`` if none was present).

    Deterministic: the same input always produces the same output (and
    the same record of what was stripped). Surfaced as a return value
    rather than logged so the PR body can record exactly which comment
    was elided.
    """
    match = _LEADING_HTML_COMMENT_RE.match(template)
    if match is None:
        return template, None
    return template[match.end():], match.group(0).strip()


# ---------------------------------------------------------------------------
# Field projection — defence in depth
# ---------------------------------------------------------------------------

# The fields the Arm B template is allowed to reference. Pulled
# directly from the locked template body (see
# ``runner/prompts/armB_precedent_no_verdict_format.md``):
#
#   {ocid}, {contract_value_formatted}, {award_date}, {regime_proxy},
#   {procurement_method_open_flag}, {publication_delay_days}
#
# Plus ``{n}`` (the running 1-indexed precedent number) which the
# renderer supplies. ``contract_value_formatted`` is derived from the
# raw ``contract_value`` numeric — we keep both in the projection map
# so the same projection can serve future template tweaks within the
# allowed surface.
ARM_B_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "n",
        "ocid",
        "award_date",
        "contract_value",
        "contract_value_formatted",
        "regime_proxy",
        "procurement_method_open_flag",
        "publication_delay_days",
    }
)
"""The whitelist of placeholder names the Arm B renderer will resolve.

If the locked template ever references a name NOT in this set, the
renderer raises ``KeyError`` rather than silently producing a malformed
prompt — the contract is "the template MUST be a subset of the allowed
fields". This is the Stop Condition the package spec calls out:
"The Arm B template references a field the precedent archive doesn't
carry → STOP, surface to Sam."

Conversely, fields that are in ``PrecedentRecord`` but NOT in this set
are NEVER passed to ``str.format_map``. That's the defence-in-depth
the package spec demands — don't trust the template to elide
``meshqu_verdict`` / ``violations`` / ``agent_reasoning`` /
``agent_recommended_action``; project them out explicitly so even a
template typo or future amendment can't leak verdict signal.
"""

ARM_B_REDACTED_FIELDS: tuple[str, ...] = (
    "meshqu_verdict",
    "violations",
    "violations_list",
    "agent_reasoning",
    "e1_agent_reasoning_text",
    "agent_recommended_action",
    "e1_agent_recommended_action",
)
"""Field names that MUST be absent from the Arm B render map. Used by
``tests/test_arm_b.py`` to assert the projection actually projects out
the verdict-signal fields."""


def project_precedent_fields(
    precedent: PrecedentRecord, *, n: int
) -> dict[str, Any]:
    """Project a ``PrecedentRecord`` onto the Arm B allowed field set.

    Returns a fresh dict carrying ONLY the keys in
    ``ARM_B_ALLOWED_FIELDS``. Tests assert that the redacted fields
    (``meshqu_verdict``, etc.) never appear in the returned dict, even
    though the source ``PrecedentRecord`` carries them.

    ``n`` is the running 1-indexed precedent number (the template's
    ``{n}`` placeholder). Threaded through here rather than appended at
    the call site so the projection is the single source of truth for
    "what the template sees".
    """
    return {
        "n": n,
        "ocid": precedent.ocid,
        "award_date": precedent.award_date,
        "contract_value": precedent.contract_value,
        "contract_value_formatted": _format_currency(precedent.contract_value),
        "regime_proxy": precedent.regime_proxy,
        "procurement_method_open_flag": _format_method_flag(
            precedent.procurement_method_open_flag
        ),
        "publication_delay_days": (
            "n/a"
            if precedent.publication_delay_days is None
            else precedent.publication_delay_days
        ),
    }


def _format_currency(value: float) -> str:
    """Mirror of ``level_l3._format_currency`` — £-prefixed integer with
    comma thousands. Kept duplicated rather than imported so a future
    refactor of the L3 module can't accidentally drift the Arm B
    rendering (which is locked, not free to drift)."""
    return f"£{int(round(value)):,}"


def _format_method_flag(value: str | None) -> str:
    """Mirror of ``level_l3._format_method_flag`` — stable surface for
    the procurement-method-open flag. 264 of 283 archive records carry
    this as absent."""
    if value is None:
        return "(absent in source record)"
    return value


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

ARM_B_SECTION_HEADER = "## Precedents from MRP-2026-02"
"""Same section-header framing E2's L3 used (and Arm A inherits). The
heading is shared across the L3 decomposition arms so the agent sees
the same surrounding scaffold; only the precedent block contents
differ across A / B."""

# Strip an optional leading per-precedent header from the template body
# (``## Precedent {n}: comparable record``). The renderer emits its
# own per-precedent header with the running 1-indexed ``n``
# substituted, so we elide a duplicate from the template body.
_LEADING_PRECEDENT_HEADER_RE = re.compile(
    r"^\s*##\s+Precedent\s+\{n\}[^\n]*\n",
    flags=re.IGNORECASE,
)


def load_arm_b_template(path: Path | None = None) -> str:
    """Read the locked Arm B template from disk.

    Returns the raw file content (no transformation). The HTML-comment
    strip and the per-precedent-header strip are applied by
    ``render_precedents_redacted`` so unit tests can exercise the
    transforms against arbitrary template bytes.

    A missing template is a stop condition (the package spec calls
    this out): ``FileNotFoundError`` is raised with the resolved path.
    """
    resolved = path if path is not None else ARM_B_TEMPLATE_PATH
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Arm B locked template not found: {resolved}. "
            "The handler refuses to substitute or synthesise; the file "
            "must exist where the v0.3 lock placed it."
        )
    return resolved.read_text(encoding="utf-8")


def render_precedents_redacted(
    template: str, precedents: list[PrecedentRecord]
) -> str:
    """Render the Arm B precedent block from a template + a list of
    precedents.

    Transformation pipeline:

      1. Strip a leading HTML comment block from the template (Wave 2
         convention — the comment documents the redaction and would
         leak meta-commentary into the prompt).
      2. Strip a leading ``## Precedent {n}: ...`` header from the
         template body so the renderer can emit its own per-precedent
         header with the running ``n`` substituted.
      3. For each precedent, project onto the Arm B allowed field set
         (see ``project_precedent_fields``).
      4. ``str.format_map`` the projected dict against the template
         body. Missing placeholders raise ``KeyError`` — loud failure
         rather than silent ``{foo}`` literals.
      5. Concatenate per-precedent blocks with double-newline
         separators, exactly like the E2 / Arm A renderer.

    Returns the rendered string (no section header — the caller
    composes the section header in front).
    """
    stripped_template, _ = strip_leading_html_comment(template)
    body_template = _LEADING_PRECEDENT_HEADER_RE.sub("", stripped_template, count=1)
    body_template = body_template.strip("\n")

    rendered_blocks: list[str] = []
    for index, precedent in enumerate(precedents, start=1):
        projection = project_precedent_fields(precedent, n=index)
        body = body_template.format_map(projection)
        header = f"## Precedent {index}: comparable record"
        rendered_blocks.append(f"{header}\n\n{body.strip()}")

    return "\n\n".join(rendered_blocks)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


@register("arm_b")
def arm_b_handler(
    record: Mapping[str, Any],
    *,
    archive: Mapping[str, PrecedentRecord] | None = None,
    k: int = DEFAULT_PRECEDENT_COUNT,
    template: str | None = None,
    **_kwargs: Any,
) -> str:
    """Render the Arm B prompt for one target record.

    Arguments:

      ``record``: the target — the same shape the E2 smoke fixture
        uses (``ocid`` + ``decision_type`` + ``fields`` +
        ``substrate_notes`` + ``metadata``). The precedent selector
        normalises this onto the locked categorical feature space.

      ``archive``: pre-loaded ``{ocid: PrecedentRecord}`` map. The
        handler does NO disk I/O for the archive itself — the caller
        loads it once via
        ``precedent_archive.load_frozen_archive(default_frozen_archive_dir(repo_root))``
        and threads it through ``handler_kwargs`` on each
        ``run_arm`` call. If ``None``, the handler returns the L0
        baseline alone (zero-precedents path — for dry-run/CLI
        smoke probes that don't have the frozen archive available).

      ``k``: number of nearest-neighbour precedents to render.
        Defaults to ``DEFAULT_PRECEDENT_COUNT`` (4, locked at Stage A).

      ``template``: optional override of the on-disk template, for
        tests. ``None`` ⇒ read from ``ARM_B_TEMPLATE_PATH``.

    Returns the fully rendered user message (string the agent receives).

    Composition:

        <L0 baseline>
        \\n\\n
        ## Precedents from MRP-2026-02
        \\n\\n
        <N rendered precedent blocks>

    The L0 baseline is the same canonical-JSON serialisation E1/E2
    sent the agent (``eval_loop.build_user_message``). Arm B does
    NOT add L1/L2 — by design (see ``meshqu_runner.arms`` module
    docstring, "no L_{k-1} prefix").
    """
    l0_baseline = build_user_message(
        context={
            "decision_type": record.get("decision_type", "procurement_decision"),
            "fields": record.get("fields") or {},
        },
        substrate_notes=record.get("substrate_notes") or {},
    )

    if archive is None or not archive:
        # Foundation path: no archive available. The handler returns
        # the L0 baseline alone — Arm B's distinguishing precedent
        # block is empty in that mode, which matches what the E3-001
        # CLI's --dry mode needs to do without a real archive on disk.
        return l0_baseline

    template_content = template if template is not None else load_arm_b_template()
    precedents = select_precedents(record, archive, k=k)
    if not precedents:
        return l0_baseline

    rendered = render_precedents_redacted(template_content, precedents)
    return f"{l0_baseline}\n\n{ARM_B_SECTION_HEADER}\n\n{rendered}\n"
