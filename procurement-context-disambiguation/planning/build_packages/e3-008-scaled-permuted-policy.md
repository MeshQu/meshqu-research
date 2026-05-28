# E3-008 — Scaled Permuted-Policy diagnostic (primary + Claude)

You are a background agent. This package extends E2's Permuted-Policy diagnostic from 14 records to 100 records (the locked subset), and adds the cross-model arm — same 100 records, primary and Claude, record-matched.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/experiment_design.md` § Piece 3
- `procurement-context-disambiguation/planning/diagnostic_rubric.md` — the locked 3-category hand-coding protocol (your work emits the reasoning texts that will be coded later)
- `procurement-context-disambiguation/planning/diagnostic_subset.json` — **the locked OCID list** (output of E3-007). MUST exist when you run.
- `procurement-context-gradient/runner/meshqu_runner/diagnostic/` — E2's Permuted-Policy diagnostic implementation (forked); the permutation function, the policy_permutation_seed handling, the receipt schema for diagnostic receipts
- `procurement-context-gradient/runner/prompts/L4_policy_envelope.md` — E2's L4 envelope (the diagnostic uses the L4 envelope with permuted operators; this is byte-identical to E2's diagnostic, just over more records)
- `procurement-context-disambiguation/runner/meshqu_runner/agents/claude.py` — the Claude adapter from E3-006

**Hard dependencies**: E3-006 merged AND E3-007 merged (this package coordinates both).

## Goal

Run the Permuted-Policy diagnostic over the locked 100-OCID subset on both the primary model and Claude. Same operator-permutation, same policy snapshot, same seed; the only varying axis is the model. Emit two arms of receipts: `diagnostic_primary` and `diagnostic_claude`.

## Scope

### 1. Subset loader

`meshqu_runner/diagnostic/runner.py`:

```python
import json
from pathlib import Path

def load_diagnostic_subset() -> list[str]:
    path = Path("procurement-context-disambiguation/planning/diagnostic_subset.json")
    return json.loads(path.read_text())["ocids"]
```

Always loads from the committed artifact, never recomputes. If the file is missing or its contents differ from what the selector would produce now, that's an integrity failure — fail loudly.

### 2. Primary-model diagnostic arm

Register `diagnostic_primary` against `arms.HANDLERS`. The handler:

- Loads the 100 OCIDs from the locked subset.
- For each OCID, loads the target record from the frozen corpus.
- Applies E2's operator-permutation function (reused unchanged from the fork) with the same `policy_permutation_seed` E2 used for its 14-record diagnostic. **Match the seed.** The seed is part of the locked diagnostic protocol; scaling from 14 to 100 doesn't reseed.
- Renders the L4 envelope (E2's `L4_policy_envelope.md`, byte-identical) with the permuted policy.
- Calls the primary agent (`gpt-5.4-2026-03-05`, `temperature=0`) via the existing primary adapter.
- Signs a receipt with: `l3_arm: null`, `nudge_excised: false`, `model_id: "gpt-5.4-2026-03-05"`, `diagnostic: true`, `policy_permutation_seed: <the locked seed>`.

### 3. Claude diagnostic arm

Register `diagnostic_claude`. Identical to `diagnostic_primary` except:

- Calls the Claude adapter (`claude-opus-4-7`, no `temperature`, `effort: low`) via the dispatcher from E3-006.
- Sign with: `model_id: "claude-opus-4-7"`, `model_sampling: {"temperature": null, "effort": "low", "max_tokens": 1024}`, `model_provider: "anthropic"`.
- All other fields identical to the primary arm. The OCID list and the permutation seed are the same.

### 4. Record-matched coordination

The two arms must run on the **same 100 OCIDs in the same order** (the order from `diagnostic_subset.json`). This makes per-record cross-model comparison clean (the rubric coder reads the primary's reasoning for OCID-N alongside Claude's for OCID-N).

The driver script `scripts/run_scaled_diagnostic.py`:

- Accepts `--arm {diagnostic_primary|diagnostic_claude}`, `--smoke` (3 records only), `--dry-run` (10 records only), or no flag (full 100).
- Iterates the locked OCID list, calls the registered handler per record, signs the receipt, persists to the run-manifest path.
- Honours rate-limiting / pacing for both providers (use existing pacing logic; both providers benefit).

### 5. Tests

`tests/test_scaled_diagnostic.py`:

- Subset loader returns the same list as the committed JSON.
- The handler for `diagnostic_primary` matches E2's 14-record diagnostic byte-for-byte when restricted to the 14 records E2 used (regression check: if our 14 of the 100 produce different rendered prompts than E2 did, the diagnostic has drifted).
- The handler for `diagnostic_claude` produces the same rendered prompt as `diagnostic_primary` — only the agent dispatch differs. Verified via stub-signer capture.
- The receipts written by each arm carry the correct integrity fields per the foundation schema.
- No live API calls in unit tests; smoke/dry-run scripts cover the live path.

### 6. PR body must answer

- The path to the locked subset file + first/last OCID (sanity).
- The locked policy-permutation seed (lift from E2's diagnostic).
- The 3 records the `--smoke` flag would run on (deterministic — first 3 in the subset list).
- Confirmation that the per-arm rendered prompts differ only in the agent call, not in the rendered text (paste the SHA of the rendered prompt for OCID-1 under both arms — they must match).

## Decision rules

- **Same OCIDs, same seed, same permutation function, same policy snapshot.** The cross-model comparison only means something if the only varying axis is the model.
- **The locked subset file is the source of truth, not the selector.** If the file and the selector disagree, fail loudly — don't silently regenerate.
- **Diagnostic receipts are cryptographically distinguishable from main-run receipts** by `diagnostic: true` + `policy_permutation_seed` set. Verify this in the receipt-schema test.

## Out of scope

- The rubric-coding tool itself (E3-009) — your job is to emit the *reasoning texts*; coding happens later.
- The full run (Phase 2) — your job is to make the runner *capable* of the full run, smoke/dry-run by E3-010/011 prove it.
- Reseeding or changing the permutation function (locked).

## Definition of done

- Branch `feat/e3-008-scaled-permuted-policy`.
- Two arm handlers registered.
- `scripts/run_scaled_diagnostic.py` driver works with `--smoke` and `--dry-run` flags.
- Tests pass; per-arm rendered-prompt SHA equality verified.
- PR body lists seed, smoke OCIDs, and prompt-SHA equality.

## Stop conditions

- The locked subset file is missing → STOP. E3-007 must merge first.
- E2's permutation function has drifted from what the diagnostic schema expects → STOP. The 14-record regression check fails; surface.
- Claude adapter is not importable / not registered → STOP. E3-006 must merge first.
- Rendered prompts differ between the two arms → STOP. Only the agent should vary.
