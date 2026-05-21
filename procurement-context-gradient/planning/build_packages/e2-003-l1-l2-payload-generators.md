# E2-003 — L1 + L2 payload generators

You are a background agent. This package wires L1 (domain summary) and L2 (named rules) into the multi-pass runner. The prompt content is locked at Stage A; this package adds the orchestration.

## Inherit first

- `procurement-context-gradient/planning/context_ladder_design.md` §L1 and §L2
- `procurement-context-gradient/planning/stage_a_content_authoring.md`
- `procurement-context-gradient/runner/prompts/L1_governance_context.md` — the locked Stage A content
- `procurement-context-gradient/runner/prompts/L2_named_rules.md` — the locked Stage A content

**Hard dependencies**: E2-001 merged AND Stage A content committed (L1 + L2 files non-empty).

## Goal

Build the L1 and L2 level handlers that consume Stage A content and inject it into the prompt above the L0 baseline. Verify additivity: an L2 prompt strictly contains the L1 prose verbatim.

## Scope

### 1. L1 handler

`meshqu_runner/context_levels/level_l1.py`:

- Reads `runner/prompts/L1_governance_context.md` at startup.
- Constructs the L1 prompt: `<L0 prompt>` + `\n\n` + `<L1 content>` injected immediately before the user's record-review request, OR appended after the user message — your choice based on what reads naturally. Document the choice in the PR body.
- Hashes the L1 content (SHA-256) and asserts the hash matches the value persisted in the run manifest. Mismatch = fail (Stage A content changed unexpectedly).

### 2. L2 handler

`meshqu_runner/context_levels/level_l2.py`:

- Reads BOTH `runner/prompts/L1_governance_context.md` AND `runner/prompts/L2_named_rules.md`.
- Constructs the L2 prompt as: `<L0 prompt>` + L1 content + `\n\n` + L2 content.
- **The additivity invariant is testable here**: an L2 prompt must strictly contain the L1 prompt's content. Write a test that asserts this.

### 3. Tests

`tests/test_l1_l2_generators.py`:

- L1 prompt = L0 + L1 content (verbatim substring check).
- L2 prompt = L1 prompt + L2 content (verbatim substring check).
- Empty Stage A content (placeholder `TODO:` strings) raises a clear error at startup so the test catches misconfiguration.
- Prompt SHAs in receipts match `prompt_template_sha256.L1` and `.L2` in the run manifest.

### 4. PR body must answer

- Where in the prompt do L1 + L2 content live (system message? user message? both?). Show a rendered example.
- Verify SHAs of both prompt files match the manifest. Print the SHAs in the PR body.

## Decision rules

- **Additivity is the load-bearing invariant.** If L2 prompt doesn't strictly contain L1's content, the experiment design's ladder semantics break.
- **No content authoring.** Stage A content is Sam's. The agent for E2-003 reads the files; it does not modify them. If the L1 or L2 content looks suspect, flag in the PR body — do not edit.
- **Prompt position matters.** System message vs user message changes how the model treats the content. Pick one and document.

## Out of scope

- L3 precedent rendering (E2-004).
- L4 policy envelope (E2-005).
- The L1/L2 prompt content itself (Stage A).

## Definition of done

- Branch `feat/e2-003-l1-l2-payload-generators`.
- Both level handlers implemented; both tests passing.
- 3-record smoke produces L1 and L2 receipts that contain the Stage A content verbatim in the prompt-replay output.

## Stop conditions

- Stage A content is the placeholder stub (`TODO: Stage A content`) → STOP. Cannot proceed without locked content.
- Additivity test fails → bug in prompt construction. Fix before merge, don't paper over.
- Prompt-construction position decision is unclear → open the PR in draft with both options sketched.
