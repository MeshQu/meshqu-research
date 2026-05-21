"""L1 (Domain summary) prompt-payload generator.

Per `planning/context_ladder_design.md` §L1, the L1 prompt is the L0
prompt plus a one-paragraph prose description of the policy territory.
The prose itself is locked Stage A content at
`runner/prompts/L1_governance_context.md` (SHA bound into the run
manifest at `prompt_template_sha256.L1`).

## Where the L1 content lives in the prompt

The L1 content sits at the **top of the user message**, above the
record's canonical-JSON payload, under a `## Governance context` H2
header. We deliberately keep it OUT of the system message because:

1. The agent's system prompt is invariant across L0..L4 — that
   invariance is bound into every receipt via `agent_prompt_sha256`
   (see `eval_loop.inject_agent_fields`). If we slid L1 prose into
   the system message, the system-prompt SHA would drift between
   levels and the receipt-integrity story would lose its "same agent,
   different context" framing.
2. The additivity-by-concatenation contract that
   `compose_user_message` already implements assumes each level's
   addendum lives in the user message. Putting L1 in the system
   message would require a parallel composition path with no upside.
3. The L1 file as authored is a single paragraph; user-message
   placement makes it visually adjacent to the record-under-review
   without inflating the system contract.

## Rendered example (L1 level, smoke fixture record 1)

```
## Governance context

You are reviewing this procurement record under a compliance policy
applied by the buyer organisation. The policy governs UK public-sector
procurement in two regimes — the Procurement Act 2023 ... [full L1
prose] ... you do not have the rule definitions themselves.

{"decision_type":"procurement_decision","fields":{...record JSON...}}
```

The header line + blank line + L1 content + trailing newline is the
addendum's complete contribution. Concatenated above the base record
message (which is canonical JSON, no leading newline), this produces a
human-readable preamble followed by the structured payload.

## Empty-content contract

If `prompts/L1_governance_context.md` is truly empty (E2-001 still
needs to run with empty Stage A fixtures), the handler returns the
empty string. The composed L1 user message equals the L0 user message
in that case — the level marker still rides into the integrity hash
via `context.fields.governance_context_level` (see `multi_pass.py`),
but the agent sees no additional context.

If the file is a TODO stub (e.g. starts with `TODO:`), the handler
raises `StageAContentError` at first use. This is the E2-003 stop
condition fired loudly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..level_handlers import GovernanceContextLevel
from ..prompt_loader import LoadedPrompts
from .stage_a import assert_stage_a_content_usable


L1_SECTION_HEADER = "## Governance context"
"""H2 header prepended to the L1 prose. Matches the example in
`planning/context_ladder_design.md` §L1."""


def build_l1_addendum(prompts: LoadedPrompts) -> str:
    """Pure function — returns the L1 addendum text (no record context
    needed; L1 is record-invariant prose).

    Returns the empty string when the L1 file is empty (E2-001 no-op
    contract); raises StageAContentError when it's a TODO stub.

    The L1 manifest SHA was computed over the raw bytes by
    `load_level_prompts`; this function does NOT re-hash. Callers that
    need the SHA read it from `prompts.get('L1').sha256`. SHA
    verification at runtime is the orchestrator's responsibility via
    the manifest-write path.
    """
    prompt = prompts.get("L1")
    assert_stage_a_content_usable(prompt)

    content = prompt.content.strip()
    if not content:
        # Empty L1 → contribute nothing. This preserves the E2-001
        # graceful-no-op test path (`test_empty_prompts_handled_gracefully`).
        return ""

    # Header + blank line + content + trailing newline. The trailing
    # newline gives a clean separation from the next addendum (L2) or
    # from the base record message.
    return f"{L1_SECTION_HEADER}\n\n{content}\n"


@dataclass
class L1ContextHandler:
    """LevelHandler implementation for L1.

    Replaces the stub `L1Handler` from `level_handlers.py`. The contract
    is identical (the LevelHandler Protocol), only the implementation
    is real now: we wrap the locked prose under `## Governance context`
    rather than the stub's generic section header, and we fail-fast on
    TODO stubs.
    """

    level: GovernanceContextLevel = "L1"

    def build_addendum(
        self,
        *,
        record: Mapping[str, object],
        ocid: str | None,
        prompts: LoadedPrompts,
    ) -> str:
        # record + ocid are unused at L1 — L1 prose is record-invariant
        # (the same paragraph for every record). We accept them per the
        # Protocol so the orchestrator can call all handlers
        # polymorphically.
        del record, ocid
        return build_l1_addendum(prompts)
