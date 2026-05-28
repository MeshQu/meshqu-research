"""L3 live handler — nearest-neighbour precedent block.

Reads the locked Stage A template at `runner/prompts/L3_precedent_block_format.md`
and renders 4 nearest-neighbour precedents per target record. Precedents
are selected by `precedent_selector.select_precedents` over the frozen E1
archive loaded by `precedent_archive.load_frozen_archive`.

The addendum produced at L3 strictly adds content on top of L0 + L1 + L2
(the additivity invariant). Composition is owned by `level_handlers.compose_user_message`;
this handler only produces its marginal contribution.

Architecture: registry-replacement
---------------------------------

The E2-001 `level_handlers.L3Handler` stub emits the L3 template
verbatim (the precedent BLOCK FORMAT) — no actual precedents. This live
handler replaces that stub in the registry the multi-pass orchestrator
consumes:

    from meshqu_runner.level_handlers import default_main_handlers
    from meshqu_runner.context_levels.level_l3 import install_live_l3

    handlers = install_live_l3(
        default_main_handlers(),
        archive=load_frozen_archive(default_frozen_archive_dir(repo_root)),
    )
    run_multi_pass(..., handlers=handlers)

The archive is loaded once at startup and passed in — no per-record
disk I/O, no late surprises about missing files.

Template handling
-----------------

The Stage A template uses `{ocid}`, `{contract_value_formatted}`, etc.
as placeholders. The handler:

  - Reads the template ONCE per `build_addendum` call from
    `prompts.get("L3").content` (or from `template_content` if the
    handler was constructed with an explicit override — used by tests).
  - Strips a leading `## Precedent {n}: comparable record` header from
    the template if present — the handler emits its own per-precedent
    headers with the correct {n} substituted.
  - Renders each precedent by `str.format_map`-ing a dict carrying every
    template placeholder.
  - Concatenates the rendered blocks under a single
    `## Precedents from MRP-2026-02` section header so the L3 contribution
    reads as one structural block in the composed user message.

The `## Precedents from MRP-2026-02` framing is the locked section
header the build package requires (mirrors the way L1/L2 use
`## Governance context` / `## Rules in force`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from ..level_handlers import GovernanceContextLevel, LevelHandler
from ..prompt_loader import LoadedPrompts
from ..precedent_archive import PrecedentRecord
from ..precedent_selector import (
    DEFAULT_PRECEDENT_COUNT,
    select_precedents,
)


# Match the optional leading header in the Stage A template — we
# strip it because the handler emits its own headers with the running
# precedent index substituted in.
_LEADING_HEADER_RE = re.compile(
    r"^\s*##\s+Precedent\s+\{n\}[^\n]*\n",
    flags=re.IGNORECASE,
)

# The L3 section framing — quoted from `context_ladder_design.md`.
L3_SECTION_HEADER = "## Precedents from MRP-2026-02"


@dataclass
class L3LiveHandler:
    """Live L3 handler: reads precedents from the frozen E1 archive,
    selects k via deterministic kNN, and renders each into the Stage A
    template.

    The handler is constructed with the loaded archive (so disk I/O
    happens once at startup, not per record). `k` defaults to
    `DEFAULT_PRECEDENT_COUNT` (Stage A locked value).

    If the archive is empty OR the target record's selection comes back
    with zero precedents (would require an empty archive), the handler
    returns an empty addendum so the multi-pass orchestrator can still
    proceed — but in practice this can't happen with the 283-record
    archive. The empty-archive case is exercised in tests for robustness.
    """

    archive: dict[str, PrecedentRecord]
    k: int = DEFAULT_PRECEDENT_COUNT
    level: GovernanceContextLevel = "L3"

    # Optional pre-loaded template content. When None, the handler reads
    # `prompts.get("L3").content` at every call. Setting an explicit
    # template_content lets tests bypass the prompt_loader.
    template_content: str | None = None

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        """Produce the L3 marginal addition for one target record.

        Empty addendum is returned when:
          - The L3 template is empty / whitespace-only (empty-file
            contract — same as the stub).
          - The archive is empty (zero candidates).

        Otherwise: the section header + N rendered precedent blocks,
        each with the running 1-indexed `{n}` substituted."""
        template = (
            self.template_content
            if self.template_content is not None
            else prompts.get("L3").content
        )
        template = template or ""
        if not template.strip():
            return ""
        if not self.archive:
            return ""

        # Strip the optional leading per-precedent header from the
        # template (we emit it ourselves with the running n).
        body_template = _LEADING_HEADER_RE.sub("", template, count=1)
        body_template = body_template.strip("\n")

        precedents = select_precedents(record, self.archive, k=self.k)
        if not precedents:
            return ""

        rendered_blocks: list[str] = []
        for index, precedent in enumerate(precedents, start=1):
            rendered_blocks.append(
                _render_precedent(
                    n=index,
                    body_template=body_template,
                    precedent=precedent,
                )
            )

        return (
            f"{L3_SECTION_HEADER}\n\n"
            + "\n\n".join(rendered_blocks)
            + "\n"
        )


def install_live_l3(
    handlers: dict[GovernanceContextLevel, LevelHandler],
    *,
    archive: dict[str, PrecedentRecord],
    k: int = DEFAULT_PRECEDENT_COUNT,
    template_content: str | None = None,
) -> dict[GovernanceContextLevel, LevelHandler]:
    """Swap the L3 stub for the live L3 handler in the given registry.

    Mirrors `install_live_l0`'s idiom. The archive must be pre-loaded
    by the caller via `precedent_archive.load_frozen_archive` — this
    function does no disk I/O itself.

    Returns the same dict mutated in place AND as a return value (for
    chaining)."""
    handlers["L3"] = L3LiveHandler(
        archive=archive,
        k=k,
        template_content=template_content,
    )
    return handlers


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_precedent(
    *,
    n: int,
    body_template: str,
    precedent: PrecedentRecord,
) -> str:
    """Render one precedent block by string-interpolating the template
    with the precedent's fields, then prepending the `## Precedent {n}`
    header.

    Uses `str.format_map(dict)` semantics — unknown placeholders in the
    template raise KeyError. We want unknown placeholders to be loud at
    integration time, not silently produce `{foo}` literals in the
    agent prompt."""
    values = {
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
        "meshqu_verdict": precedent.meshqu_verdict,
        "violations_list": _format_violations(precedent.violations),
        "e1_agent_reasoning_text": precedent.agent_reasoning.strip(),
        "e1_agent_recommended_action": (
            precedent.agent_recommended_action
            or "(no recommended action recorded)"
        ),
    }
    body = body_template.format_map(values)
    header = f"## Precedent {n}: comparable record"
    return f"{header}\n\n{body.strip()}"


def _format_currency(value: float) -> str:
    """£-prefixed integer currency with comma thousands. Values <£1k
    fall through with no decimals for the same reason."""
    return f"£{int(round(value)):,}"


def _format_method_flag(value: str | None) -> str:
    """Stable surface for the procurement-method-open flag in the
    rendered template. 264 of 283 archive records have this absent;
    showing `(absent)` rather than the Python `None` keeps the agent's
    prompt readable."""
    if value is None:
        return "(absent in source record)"
    return value


def _format_violations(violations: tuple[str, ...]) -> str:
    """Comma-separated violation codes; explicit `(none)` when the
    archive record had a clean verdict — keeping the field present
    rather than rendering an empty placeholder."""
    if not violations:
        return "(none)"
    return ", ".join(violations)
