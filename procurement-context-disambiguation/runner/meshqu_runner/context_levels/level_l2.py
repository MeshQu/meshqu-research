"""L2 (Named rules) prompt-payload generator.

Per `planning/context_ladder_design.md` §L2, the L2 prompt is the L1
prompt plus a section naming the six rule codes (no thresholds, no
`when` clauses). The locked content lives at
`runner/prompts/L2_named_rules.md` (SHA bound into the run manifest at
`prompt_template_sha256.L2`).

## Additivity invariant — the load-bearing test

The L2 *addendum* contains only the named-rules block; the L2 *prompt*
(what the agent actually sees) is L0 + L1 + L2. We rely on
`compose_user_message` in `level_handlers.py` to concatenate L0..Lk in
order. The test
`tests/test_l1_l2_generators.py::TestAdditivityInvariant::test_l2_user_message_strictly_contains_l1_user_message`
asserts that the composed L2 prompt strictly contains the composed L1
prompt as a verbatim substring (modulo the per-record base message,
which is the same at every level). If that test ever fails, the
ladder semantics in the experiment design break.

## Why the L2 file has its own `## Rules in force` header (and L1 does not)

The authored Stage A files reflect this asymmetry on purpose:

- `L1_governance_context.md` is the prose itself; we add the
  `## Governance context` H2 in code so the prose can be re-read in
  isolation when authoring.
- `L2_named_rules.md` opens with `## Rules in force` already, because
  the file IS a structured rule list and the header is part of the
  authored content.

The L2 handler therefore emits the L2 file content **verbatim** — no
extra header wrapping. This preserves the authored bytes; if Sam edits
the file to change the header, the change is visible in the diff (and
will fail the SHA pin in `test_multi_pass.py`).

The E2-001 stub `L2Handler` in `level_handlers.py` wrapped the L2
content in a second `## Rules in force` header, producing a doubled
heading in the rendered prompt. E2-003 fixes that by emitting verbatim.

## Rendered example (L2 level, smoke fixture record 1)

```
## Governance context

You are reviewing this procurement record ... [L1 prose] ...

## Rules in force

- PROC-001-S53 — Publication-delay timing
- PROC-002-AUTHORITY — Contract-value authority threshold
- PROC-003-DEBARMENT — Supplier exclusion list
- PROC-004-COI — Conflict-of-interest disclosure
- PROC-005-OPEN-TENDER — Open-procedure or justified-direct-award
- PROC-006-MOD-CAP — Modification-value cap

The rule codes are the canonical identifiers. Each rule applies binary
judgement based on the record's field values. The agent does not see
the thresholds or applicability conditions.

{"decision_type":"procurement_decision","fields":{...record JSON...}}
```

## Empty-content contract

Same as L1: empty file → empty addendum (no-op); TODO stub →
StageAContentError at first use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..level_handlers import GovernanceContextLevel
from ..prompt_loader import LoadedPrompts
from .stage_a import assert_stage_a_content_usable


def build_l2_addendum(prompts: LoadedPrompts) -> str:
    """Return the L2 addendum text — the L2 file content verbatim,
    with one trailing newline so it concatenates cleanly above the
    record JSON or any future L3 block.

    Returns "" when the L2 file is empty (E2-001 no-op contract);
    raises StageAContentError when it's a TODO stub.

    Note: this function does NOT include the L1 content. The
    additivity composition happens in `compose_user_message`, which
    calls L0.build_addendum + L1.build_addendum + L2.build_addendum
    and concatenates. Keeping each handler responsible only for its
    own marginal contribution means the additivity invariant is
    enforced by the orchestrator, not duplicated in each handler.
    """
    prompt = prompts.get("L2")
    assert_stage_a_content_usable(prompt)

    content = prompt.content.strip()
    if not content:
        return ""

    # The L2 file already carries its own `## Rules in force` header
    # as authored. Emit verbatim + single trailing newline.
    return f"{content}\n"


@dataclass
class L2ContextHandler:
    """LevelHandler implementation for L2.

    Replaces the stub `L2Handler` from `level_handlers.py`. Returns
    the L2 file content verbatim (no wrapper header). Additivity with
    L1 is the orchestrator's responsibility, not this handler's.
    """

    level: GovernanceContextLevel = "L2"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        # record + ocid unused: L2 named-rule list is record-invariant.
        del record, ocid
        return build_l2_addendum(prompts)
