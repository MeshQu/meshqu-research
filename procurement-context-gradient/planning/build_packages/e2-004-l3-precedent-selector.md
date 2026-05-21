# E2-004 — L3 nearest-neighbour precedent selector

You are a background agent. This package is the most algorithmically novel piece of Phase 1. It implements the deterministic selector that picks 3–5 Decision Receipts from E1's frozen archive as precedents for the target record at L3.

## Inherit first

- `procurement-context-gradient/planning/context_ladder_design.md` §L3 — **read this entirely; the frozen-archive constraint is load-bearing**
- `procurement-context-gradient/planning/stage_a_content_authoring.md` §3 (`L3_precedent_block_format.md`)
- `procurement-context-gradient/runner/prompts/L3_precedent_block_format.md` — the locked Stage A template
- `procurement-decisions/results/runs/dry-run-7ddf7274-…/decision_traces.jsonl` — the frozen archive
- `procurement-decisions/results/corpus.tar` (extract a bundle to see receipt structure)

**Hard dependencies**: E2-001 merged, Stage A L3 template committed.

## Goal

Build the deterministic kNN precedent selector + the L3 prompt handler that renders the selected precedents using the Stage A template.

## Scope

### 1. Frozen-archive reader

`meshqu_runner/precedent_archive.py`:

- Loads ALL 283 receipts from `procurement-decisions/results/runs/dry-run-7ddf7274-…/decision_traces.jsonl` (or wherever E1 persists per-record data).
- Returns a dict keyed by OCID with the fields required by the Stage A template (contract value, regime proxy, procurement-method-open flag, publication delay, MeshQu verdict, violations, E1 agent reasoning text, E1 recommended action).
- **Hard constraint**: ONLY reads from `procurement-decisions/` paths. NO live MeshQu API calls. NO writes anywhere.
- Tests: 283 records loaded, all keyed by OCID, no network calls (assertable via mock).

### 2. Deterministic kNN function

`meshqu_runner/precedent_selector.py`:

```python
def select_precedents(
    target_record: dict,
    archive: dict[str, dict],
    k: int = 4,
) -> list[dict]:
    """
    Returns k nearest-neighbour records from the archive, excluding the target itself.
    Deterministic: same inputs always produce same output.
    """
```

Feature vector for similarity (locked at Stage A):

1. **Contract value band** (4 bands: <£100k, £100k–£500k, £500k–£10M, >£10M). Categorical.
2. **Procurement-method-open flag** (`true` / `false` / `null`). Categorical.
3. **Governance regime** (`PA23` / `PCR_2015`, by award date relative to 24 Feb 2025). Categorical.

Distance function: Hamming over categorical features (each mismatch = 1, perfect match = 0). Tie-break by OCID ascending — this is what makes the function deterministic.

**Excludes self by OCID.** Target record cannot be its own precedent.

Tests:

- Given a fixed target record, `select_precedents` returns the same list across re-runs.
- Self never appears in returned precedents.
- k=4 produces exactly 4 precedents (or fewer if archive has <4 candidates that match anything — flag that case).
- Tie-break by OCID asc verified with a constructed tie case.

### 3. L3 prompt handler

`meshqu_runner/context_levels/level_l3.py`:

- Reads `runner/prompts/L3_precedent_block_format.md` (the Stage A template).
- For each target record:
  - Calls `select_precedents(target, archive, k=4)` (or whatever k Stage A locks).
  - Renders each precedent through the Stage A template (string interpolation against the precedent's fields).
  - Concatenates rendered precedents as a single L3 addition to the prompt.
- Constructs the L3 prompt: L0 + L1 + L2 + `\n\n## Precedents from MRP-2026-02\n\n` + rendered precedent blocks.
- **Additivity invariant**: L3 prompt strictly contains L2 prompt's content. Test it.

### 4. Tests

`tests/test_precedent_selector.py`:

- Deterministic kNN for the 3 smoke records — for each, the same 4 precedents return across 10 re-runs.
- For the worked-example record (`ca19e737-…`), the 4 precedents are inspected and named in the PR body. Sam wants to see whether the kNN pick "reads right" — comparable value band, same regime, same procurement method.
- No network calls; mock the HTTP transport, assert no calls.
- Self-exclusion: when `ca19e737-…` is the target, none of its 4 precedents have OCID equal to `ca19e737-…`'s OCID.

### 5. PR body must answer

- What k is locked? (Stage A may have specified 3, 4, or 5 — match it.)
- For the worked-example target (`ca19e737-…`, the £57M case), print the 4 precedent OCIDs + their contract values + regime + method flag. Does the picked set "read right" — i.e. is the kNN function picking comparable records or noisy ones?
- If the kNN picks look weird (e.g. all 4 precedents have zero violations when the target has 3), flag it. The kNN may need a better feature vector. Do NOT change the feature vector unilaterally — surface to Sam.

## Decision rules

- **Frozen archive only.** Documented in `context_ladder_design.md` and the project memory note. No live lookups. No E2 in-flight outputs.
- **Determinism is non-negotiable.** Test for it explicitly.
- **Feature vector is locked at Stage A.** Don't change it without a decision-log entry.

## Out of scope

- The L3 prompt content template (Stage A).
- L4 policy injection (E2-005).
- Permuted-Policy diagnostic (E2-006).
- Adaptive precedent count or per-record k tuning — k is fixed.

## Definition of done

- Branch `feat/e2-004-l3-precedent-selector`.
- Selector + handler + tests passing.
- PR body lists precedents picked for the worked-example record.

## Stop conditions

- Frozen archive missing required fields (e.g. E1 agent reasoning text is empty for some records) → STOP. The Stage A template references that field; if it's not in the archive, the runner can't render L3 cleanly.
- Self-exclusion test fails → bug in the OCID match. Fix before merge.
- The kNN picks "feel wrong" for the worked-example record → surface to Sam in the PR body. Don't change the feature vector.
- If `precedent_archive.py` would need to write anywhere or call any API → STOP. Read-only is the design contract.
