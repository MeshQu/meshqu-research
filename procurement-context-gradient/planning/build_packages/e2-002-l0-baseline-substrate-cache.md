# E2-002 — L0 baseline + substrate cache reader

You are a background agent. This package wires L0 (the E1 reproducibility baseline) into the multi-pass runner and adds the substrate cache reader.

## Inherit first

- `procurement-context-gradient/planning/phase_1_build_plan.md`
- `procurement-context-gradient/planning/experiment_design.md` §"Comparison to E1" and §"Substrate posture"
- `procurement-context-gradient/planning/substrate.md`
- `procurement-decisions/results/runs/dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/` — the frozen E1 archive

**Hard dependency: E2-001 must be merged.**

## Goal

Implement the L0 baseline pass: a re-run of the same prompt structure E1 used, but reading the OCDS records from E1's frozen cache rather than fetching from Contracts Finder.

## Scope

### 1. Substrate cache reader

Add `meshqu_runner/substrate_cache.py`. The module:

- Reads OCDS records from `procurement-decisions/results/runs/dry-run-7ddf7274-…/decision_traces.jsonl`. (Or wherever E1 persisted the substrate-adapter output — check the existing runner code.)
- Returns 283 unique records keyed by OCID, in OCID-ascending order.
- Each record carries the same per-field provenance envelope E1 produced (direct_ocds / derived / proxy / absent).
- **No network calls.** Pure disk read. If any code path tries to hit Contracts Finder's API, fail loudly.
- Tests: 283 records loaded, OCIDs deterministic across re-runs, provenance envelope intact.

### 2. L0 prompt generation

Add `meshqu_runner/context_levels/level_l0.py`. The module:

- Returns the same prompt structure E1 used — base system prompt + the record + provenance envelope. NO context addition.
- Reuses E1's prompt scaffold verbatim. If the scaffold is in E1's runner, import it cleanly (re-implement if import isn't clean; document the decision).
- The L0 prompt template file (`runner/prompts/L1_governance_context.md` etc.) is NOT read at L0 — L0 is the baseline by definition.

### 3. L0-vs-E1 reproducibility comparator

Add `scripts/compare_l0_to_e1.py`. The script:

- Takes a list of OCIDs (default: the 3 smoke records).
- For each OCID: load E2's L0 receipt + E1's receipt from the frozen archive. Compare verdicts. Print a diff table.
- Returns exit code 0 if verdicts match on all OCIDs; 1 otherwise.
- Intended to be invoked manually after smoke and dry-run; not part of the runner.

### 4. Tests

- `tests/test_l0_baseline.py`:
  - Substrate cache loads 283 records.
  - L0 prompt for OCID `ocds-b5fd17-…ca19e737-…` (the worked-example record) matches E1's prompt byte-for-byte (modulo any whitespace normalisation E1 applied).
  - L0 receipts produced for the 3 smoke records have the same `agent_verdict` as E1's receipts for those records — **assuming the OpenAI backend's temp=0 reproducibility holds.** Document in the test that verdict-mismatch on 1 of 3 records is within noise.
- All tests pass.

### 5. PR body must answer

- Where does the substrate cache read from?
- Did the 3-smoke-record L0-vs-E1 comparison pass? Print the diff table in the PR body.
- If verdicts mismatched on ≥1 smoke record: name the record, name the divergence, suggest whether it's noise or a bug.

## Decision rules

- **No network calls.** The substrate cache is the ONLY way records enter the runner. If E1's runner did anything online, replicate the disk-only behaviour cleanly.
- **OCID order is deterministic.** Tests pin the order.
- **Prompt byte-for-byte match is the gold standard.** Verdict reproducibility within OpenAI's temp=0 noise is the practical target.

## Out of scope

- L1..L4 level handlers (E2-003..005).
- Diagnostic Controls (E2-006).
- Cost analysis (E2-007/008).

## Definition of done

- Branch `feat/e2-002-l0-baseline-substrate-cache`.
- 3-record smoke produces 3 L0 receipts; comparator passes (or documents the divergence with reasoning).
- Tests passing.
- PR body shows the verdict-comparison table.

## Stop conditions

- If E1's frozen archive is missing fields the runner needs (e.g. provenance envelope was stripped post-publication), STOP and surface — the experiment design assumed the archive is rich enough.
- If L0-vs-E1 verdicts mismatch on **all 3 smoke records**, that's not noise — it's a substrate-loading or prompt-construction bug. Stop and surface; do not paper over.
- If E1's runner imports cleanly but the import path requires modifying E1's code, STOP — E1's code stays archival. Reimplement if needed.
