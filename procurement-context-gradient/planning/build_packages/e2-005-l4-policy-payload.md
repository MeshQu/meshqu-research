# E2-005 — L4 full policy payload + cache preservation

You are a background agent. This package injects the full policy JSON into L4 prompts and verifies that level-batching execution order actually preserves the OpenAI prompt cache.

## Inherit first

- `procurement-context-gradient/planning/context_ladder_design.md` §L4 + §"Token-cost projection"
- `procurement-context-gradient/planning/experiment_design.md` §"Multi-pass runner" (level-batching rationale)
- `procurement-context-gradient/planning/stage_a_content_authoring.md` §4 (`L4_policy_envelope.md`)
- `procurement-context-gradient/runner/prompts/L4_policy_envelope.md` — locked Stage A envelope
- `procurement-context-gradient/policy/policy-snapshot-cbf12348.json` — the locked policy snapshot

**Hard dependencies**: E2-001..004 merged; Stage A L4 envelope committed.

## Goal

Build the L4 prompt handler that injects the locked policy snapshot into the prompt, and verify (via OpenAI's cached-token usage telemetry) that level-batching actually preserves the cache prefix.

## Scope

### 1. L4 prompt handler

`meshqu_runner/context_levels/level_l4.py`:

- Reads `runner/prompts/L4_policy_envelope.md` (the Stage A envelope template).
- Reads `policy/policy-snapshot-cbf12348.json` (the locked snapshot).
- Renders the envelope with `{policy_snapshot_json}` interpolated. The interpolated JSON should be pretty-printed (indent=2) for the agent's readability — the SHA-256 binding is computed against the rendered string, so the indentation choice is locked.
- Constructs the L4 prompt: L0 + L1 + L2 + L3 + `\n\n` + rendered L4 envelope.
- **Crucial for cache preservation**: the policy text must be at the *top* of the per-call user message (or whichever message gets cached by OpenAI). The per-call-varying content (record + L3 precedents) must appear *after* the policy block. This is what makes the cache prefix stable across all 283 L4 calls.

### 2. Cache-preservation verification

OpenAI's API response includes a `cached_tokens` count when prompt caching is in effect. The runner already logs response metadata (or extend it to do so). Add to the runner:

- Per-call `cached_tokens` recorded in the receipt or in a separate `cache_telemetry.jsonl` file.
- A post-run summary script `scripts/cache_summary.py` that computes per-level cache-hit fraction.

### 3. Tests

`tests/test_l4_handler.py`:

- L4 prompt construction is deterministic for a given record (same record + same archive + same envelope → same prompt bytes).
- L4 prompt strictly contains the L3 prompt's content (additivity invariant).
- The policy JSON appears in the L4 prompt at a stable position (e.g. always before the `## Record under review` section). Test the structural property, not the exact byte position.
- Mock OpenAI response with `cached_tokens=4500` (the policy block size) and verify the runner extracts and records it correctly.

`tests/test_cache_preservation_smoke.py`:

- A 3-record smoke that actually calls OpenAI. (Or skipped by default with `pytest -m live`.) Verifies that the second L4 call's response has `cached_tokens > 0`. If the cache is NOT hitting, the level-batching order is wrong or the prompt structure is fighting it.

### 4. PR body must answer

- Where in the L4 prompt does the policy JSON live? Show a structured outline of the L4 prompt (without dumping the full text).
- What's the SHA-256 of the rendered L4 envelope (with the locked policy interpolated)? It must match `prompt_template_sha256.L4_rendered` in the manifest.
- Did the smoke-live test show cached_tokens > 0 on at least the second L4 call? If not, why?

## Decision rules

- **Policy block at the top.** Per-call variation lives below it. Otherwise the cache breaks.
- **Pretty-printed (indent=2).** Locked. SHA-256 is computed against this rendering.
- **The locked policy is byte-for-byte the snapshot file.** Do not re-serialise or normalise. Read raw, embed verbatim.

## Out of scope

- Permuted-Policy diagnostic (E2-006) — note that E2-006 needs L4's policy-rendering logic; design L4 so E2-006 can replace the policy bytes without re-implementing the envelope.
- The L4 envelope content itself (Stage A).

## Definition of done

- Branch `feat/e2-005-l4-policy-payload`.
- L4 handler + cache telemetry + tests.
- PR body documents prompt structure + cached-tokens result.

## Stop conditions

- Stage A L4 envelope content is empty/stub → STOP.
- Cached_tokens stays 0 across consecutive L4 calls → cache isn't working. Investigate: prompt structure, message-role placement, model's caching policy. Fix or surface.
- If implementing cache-friendly placement requires moving L0/L1/L2/L3 content around in a way that breaks additivity invariant → STOP and surface; the trade-off needs Sam's call.
- If the policy JSON's pretty-print produces different bytes than what's persisted at `policy/policy-snapshot-cbf12348.json` (e.g. JSON serialiser reorders keys) → STOP; the locked SHA must match.
