# E3-009 — Rubric-coding tool

You are a background agent. Offline tool — no model calls, no API. Reads the diagnostic receipts (after Phase 2 runs them) and presents each reasoning text + the record's inverted-operator spec side-by-side for a human coder, who assigns one of three categories per record. Outputs a structured coding sheet.

## Inherit first

- `procurement-context-disambiguation/planning/phase_1_build_plan.md`
- `procurement-context-disambiguation/planning/diagnostic_rubric.md` — **the locked coding protocol**; the three categories, the procedure, the inter-coder check. Read in full.
- `procurement-context-disambiguation/planning/diagnostic_subset.json` — the OCID list
- `procurement-context-disambiguation/runner/meshqu_runner/diagnostic/` (after E3-008 merges) — for context on the receipt schema your tool will read

**Hard dependencies**: E3-001 merged. (E3-008 doesn't need to be merged for *building* the tool — your tool can be built and tested with fixture receipts; it just won't have real data to code until Phase 2 runs the diagnostic.)

## Goal

A CLI tool that walks through diagnostic receipts (primary or Claude arm) one at a time, presents the agent's reasoning text and the inverted-operator spec the record was scored against, prompts the human coder for a category (1/2/3) and a one-line justification quote, and writes the result to a structured coding sheet.

## Scope

### 1. CLI

`meshqu_runner/diagnostic/code_rubric.py`:

```
$ python -m meshqu_runner.diagnostic.code_rubric \
    --arm diagnostic_primary \
    --sheet results/rubric_coding_primary.jsonl \
    [--resume]
```

Flags:
- `--arm {diagnostic_primary|diagnostic_claude}` — which arm's receipts to code.
- `--sheet <path>` — output JSON-lines file. One entry per OCID coded.
- `--resume` — skip OCIDs already coded in the sheet. Default behaviour resumes from where left off.
- `--inverted-spec <path>` — JSON file mapping OCID → inverted-operator description (one-liner per record, lifted from the policy permutation rule applied at run time). Defaults to a path emitted alongside the diagnostic receipts by E3-008.

### 2. Interactive flow per record

For each OCID in the locked subset (in subset-file order):

1. Print the OCID.
2. Print the inverted-operator spec for this record (1-2 lines: "Rule N normally fires when X; permuted to fire when not-X").
3. Print the agent's reasoning text from the receipt (the full `reasoning` field).
4. Prompt: "Category? [1=names inversion / 2=reasons against intent / 3=partial]"
5. Prompt: "One-line justification quote from the reasoning text:"
6. Append to the sheet:

```json
{"ocid": "...", "arm": "diagnostic_primary", "category": 2, "justification": "...the policy requires publication within 30 days...", "coded_at": "<iso8601>"}
```

7. Move to the next OCID.

The coder can quit at any time with Ctrl-C; the sheet is appended to per-record so progress is preserved.

### 3. Sheet schema

JSON-lines, one record per line:

```json
{"ocid": "<string>", "arm": "diagnostic_primary|diagnostic_claude", "category": 1|2|3, "justification": "<string>", "coded_at": "<ISO-8601>", "coder": "<string from $USER>"}
```

If the coder enters anything other than 1/2/3, re-prompt. If the justification is empty, re-prompt. The rubric specifies a quote — surface this constraint.

### 4. Inter-coder helper (optional, behind a flag)

If `--double-code-subset <n>` is passed, after the main pass, present the first N OCIDs again for double-coding (the rubric's inter-coder check, n=20 by default). Output the double-coded entries with `coder: "<second user>"` so Cohen's κ can be computed offline against the first pass.

The rubric says "single-coder is acceptable for E3"; this flag is for the optional kappa check.

### 5. Reporting helper

`meshqu_runner/diagnostic/score_rubric.py`:

```
$ python -m meshqu_runner.diagnostic.score_rubric --sheet results/rubric_coding_primary.jsonl
```

Outputs:

```
Arm:                    diagnostic_primary
N records coded:        100 / 100
Category 1 (names):     8  (8.0%)
Category 2 (intent):    71 (71.0%)
Category 3 (partial):   21 (21.0%)

P5 evaluation:
  Confirmed: Cat 2 >= 60% AND Cat 1 <= 15%? YES  -> P5 CONFIRMED.
  Falsified: Cat 1 > 25%?                    NO.
  Reported disposition: <pre-registered>
```

The pre-registered bands (60% for confirmation, 15% for the names-cap, 25% for falsification) live in `predictions.md` — read from there, don't hard-code in the script.

### 6. Tests

`tests/test_rubric_tool.py`:

- Given a fixture receipts file (3 synthetic records) + a fixture inverted-spec file, the CLI walks all three, prompts, and writes 3 entries to the sheet (use a stdin/stdout mock for the interactive prompts).
- `--resume` skips OCIDs already in the sheet.
- Invalid category input re-prompts.
- Scoring helper math is correct on a constructed sheet.

### 7. PR body must answer

- A worked example: the rubric tool walking through one fixture record, with the prompts and the sheet entry produced.
- The scoring helper's output for a fixture sheet of 10 entries (6 Cat 2, 2 Cat 1, 2 Cat 3).
- Confirmation that the script reads bands from `predictions.md`, not hard-coded.

## Decision rules

- **Single-coder is the default** per the locked rubric. Double-coding is opt-in via flag.
- **Justification must be a quote.** The rubric specifies "a one-line justification quote per record" — the prompt enforces this.
- **Sheet is append-only.** Don't rewrite; resume by skipping coded OCIDs.

## Out of scope

- Computing Cohen's κ (the optional double-code subset is collected; κ computation can be a separate script later).
- Visualisations / writeup charts (Phase 3).
- Automated coding (the whole point is human-coded — this rubric replaces E2's failed lexicon).

## Definition of done

- Branch `feat/e3-009-rubric-coding-tool`.
- `code_rubric.py` and `score_rubric.py` exist; tests pass with mocked stdin/stdout.
- PR body shows the worked example + scoring helper output.

## Stop conditions

- The receipt schema doesn't expose a `reasoning` field as the tool expects → STOP. The foundation should preserve it; if not, the diagnostic isn't coding-ready.
- The inverted-operator spec emit path from E3-008 is unclear → write the tool to take it as a CLI flag (don't hard-code a path), surface to Sam that E3-008 should produce a sibling JSON alongside the receipts.
