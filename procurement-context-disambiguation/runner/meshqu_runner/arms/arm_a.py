"""Arm A — precedents-only.

The most conservative of the three L3 decomposition arms (see
``planning/experiment_design.md`` §"Piece 1 — L3 decomposition"):

    Arm A = L0 baseline + E2's full L3 precedent block, L1/L2 stripped.

If the L3 commitment effect E2 observed survives here, the effect is
attributable to precedents-plus-verdicts alone — neither domain prose
(L1) nor named rules (L2) are present to confound. Arms B and C peel
back further (verdict redaction; concrete precedents replaced with
density-matched filler) to slice the precedent block itself apart.

## How Arm A reuses E2

Arm A is locked to reproduce E2's L3 precedent block **byte-identically**
for the same target record + same precedent set. That is the core
methodological commitment for the cross-experiment comparison: if Arm
A's L3 block ever drifts from E2's, we lose the ability to say "the
only thing we changed was removing L1/L2".

The runner foundation forked ``meshqu_runner.context_levels.level_l3``
byte-identically from E2 (verified by ``tests/test_fork_parity.py`` for
the underlying precedent selector + archive; ``level_l3.py`` itself is
byte-identical between the two trees — confirmed by ``test_arm_a``'s
cross-tree SHA assertion). Arm A delegates the L3 block rendering to
``L3LiveHandler.build_addendum`` directly so any future renderer fix
in E2 (none expected post-publication) would surface as a drift here
before the byte-identity test even runs.

## What Arm A composes

The agent sees:

    <L3 block: rendered precedents from MRP-2026-02>
    \n
    <base user message: canonical-JSON of {decision_type, fields,
                         substrate_notes}>

That is E2's ``compose_user_message(level="L3", ...)`` output for a
target record where L1's and L2's addenda happen to be empty. Arm A
does not load L1/L2 at all — the "happen to be empty" framing is
purely a way of describing the byte equivalence.

If the L3 block comes back empty (empty archive after self-exclusion,
or empty template — both unreachable in production), Arm A returns
the base user message alone. This is the same graceful-no-op contract
E2's ``L3LiveHandler`` carries.

## Archive resolution (and the ``--dry`` fallback)

Production callers pass ``archive`` explicitly (loaded once at startup
via ``precedent_archive.load_frozen_archive``). Tests pass a synthetic
in-memory dict so they don't depend on the frozen archive being on
disk.

The CLI's ``--dry`` mode invokes ``arms.dispatch`` without an
``archive`` kwarg. To keep the dry run executable, this handler:

  1. Tries ``load_frozen_archive(default_frozen_archive_dir(repo_root))``.
  2. On ``ArchiveLoadError`` (archive not on disk — the common case
     in CI / a worktree without the frozen E1 corpus), falls back to
     an empty archive. The handler still runs end-to-end; the L3
     block is empty (which is exactly the "graceful no-precedents"
     contract above), and the agent sees just the base user message.

That choice is deliberate — the alternative (raise from inside the
handler) would block ``--dry`` smoke checks every time someone tries
to exercise the CLI in a fresh checkout. The PR body documents this
decision so a future "Arm A produced an empty L3 block" report doesn't
look like a bug.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import register
from ..context_levels.level_l3 import L3LiveHandler
from ..eval_loop import build_user_message
from ..precedent_archive import (
    ArchiveLoadError,
    PrecedentRecord,
    default_frozen_archive_dir,
    load_frozen_archive,
)
from ..precedent_selector import DEFAULT_PRECEDENT_COUNT


# Locked path of E2's L3 precedent block template. Arm A references E2's
# bytes directly — copying the file into E3's prompts/ dir would create
# a second SHA for the same locked content, introducing the very drift
# risk the byte-identity test exists to catch.
#
# Relative to the repo root (two parents up from ``runner/``). The
# helper ``_resolve_e2_template_path`` does the resolution from this
# module's __file__ so callers don't have to thread a repo root in.
_E2_L3_TEMPLATE_RELATIVE = (
    "procurement-context-gradient/runner/prompts/L3_precedent_block_format.md"
)


def _repo_root() -> Path:
    """Walk up from this file to the monorepo root.

    Layout: ``<repo>/procurement-context-disambiguation/runner/
    meshqu_runner/arms/arm_a.py`` → repo is the file's 5th parent.
    """
    return Path(__file__).resolve().parents[4]


def _resolve_e2_template_path() -> Path:
    return _repo_root() / _E2_L3_TEMPLATE_RELATIVE


def _load_template(*, template_path: Path | None, template_content: str | None) -> str:
    """Resolve the L3 template bytes.

    Precedence:
      1. ``template_content`` if provided (used by tests).
      2. ``template_path`` if provided.
      3. The locked E2 path.
    """
    if template_content is not None:
        return template_content
    path = template_path or _resolve_e2_template_path()
    return path.read_text(encoding="utf-8")


def _resolve_archive(
    *,
    archive: Mapping[str, PrecedentRecord] | None,
    archive_dir: Path | None,
) -> Mapping[str, PrecedentRecord]:
    """Resolve the precedent archive.

    Precedence:
      1. ``archive`` if provided (production + test path).
      2. ``archive_dir`` if provided.
      3. ``default_frozen_archive_dir(repo_root)`` — soft-fails to ``{}``
         on ``ArchiveLoadError`` so the CLI's ``--dry`` mode still
         executes end-to-end in a checkout without the frozen E1 corpus.
    """
    if archive is not None:
        return archive
    target = archive_dir or default_frozen_archive_dir(_repo_root())
    try:
        return load_frozen_archive(target)
    except ArchiveLoadError:
        # No archive on disk — the dry-run fallback. The L3 block will
        # be empty for this invocation; the agent sees only the base
        # user message. Documented in the module docstring.
        return {}


def _extract_ocid(record: Mapping[str, Any]) -> str | None:
    """Same OCID extraction the orchestrator uses. Duplicated here so
    Arm A can be invoked directly in tests without the orchestrator."""
    raw = record.get("ocid")
    if isinstance(raw, str):
        return raw
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("ocid"), str):
        return metadata["ocid"]
    return None


def render_arm_a(
    record: Mapping[str, Any],
    *,
    archive: Mapping[str, PrecedentRecord] | None = None,
    archive_dir: Path | None = None,
    k: int = DEFAULT_PRECEDENT_COUNT,
    template_path: Path | None = None,
    template_content: str | None = None,
) -> str:
    """Render Arm A for one target record.

    Splitting this out from the registered handler lets tests invoke
    the rendering pipeline directly without going through the
    ``arms.dispatch`` signature-filtering machinery.
    """
    resolved_archive = _resolve_archive(archive=archive, archive_dir=archive_dir)
    resolved_template = _load_template(
        template_path=template_path, template_content=template_content
    )

    handler = L3LiveHandler(
        archive=dict(resolved_archive),
        k=k,
        template_content=resolved_template,
    )
    l3_addendum = handler.build_addendum(
        record=record,
        ocid=_extract_ocid(record),
        prompts=None,  # type: ignore[arg-type]
    )

    base_user_message = build_user_message(
        context={
            "decision_type": record.get("decision_type", "procurement_decision"),
            "fields": record.get("fields") or {},
        },
        substrate_notes=record.get("substrate_notes") or {},
    )

    if not l3_addendum:
        # No precedents (empty archive / empty template). The agent
        # sees the base user message alone — same graceful no-op
        # contract E2's compose_user_message follows when its prefix
        # collapses to empty string.
        return base_user_message

    # Same composition shape E2's compose_user_message produces at
    # level=L3 when L1/L2 addenda are empty: `<prefix>\n<base>`.
    return f"{l3_addendum}\n{base_user_message}"


@register("arm_a")
def arm_a_handler(
    record: Mapping[str, Any],
    *,
    archive: Mapping[str, PrecedentRecord] | None = None,
    archive_dir: Path | None = None,
    k: int = DEFAULT_PRECEDENT_COUNT,
    template_path: Path | None = None,
    template_content: str | None = None,
    **_extra: Any,  # tolerate orchestrator-passed kwargs unrelated to Arm A
) -> str:
    """Registered Arm A handler. Thin wrapper over ``render_arm_a``.

    ``**_extra`` absorbs orchestrator-supplied kwargs that other arms
    consume (e.g. ``policy_snapshot`` for L4 variants, ``permutation_seed``
    for diagnostics). Without this, ``arms.dispatch``'s signature-filter
    would drop unrecognised kwargs silently; explicit absorption is
    clearer when one looks at this module in isolation.
    """
    return render_arm_a(
        record,
        archive=archive,
        archive_dir=archive_dir,
        k=k,
        template_path=template_path,
        template_content=template_content,
    )
