# E3 Phase 3 analysis — how to re-run

The Phase 3 writeup pulls every number from `results/analysis.py`. This README
is the one-page operator guide for re-executing it against the signed receipts
on `main`.

## What it computes

1. Sanity-checks bundle counts per arm (`arm_a/b/c`, `l4_without_nudge`,
   `diagnostic_primary`, `diagnostic_claude`).
2. Verdict distributions per arm (parsed from each bundle's
   `context_fields_canonical_json.agent_recommended_verdict`).
3. Reconciled-rubric category distributions for both diagnostic arms +
   P5 disposition per arm.
4. Cross-experiment comparisons against E2 (`procurement-context-gradient/results/runs/phase-2-20260522-101324-Z/`):
   - E3 `l4_without_nudge` retention of E2's L3-DENY set (the P3 metric).
   - E3 `diagnostic_primary` same-verdict rate per OCID vs E2 L4 (the P4 metric).
   - E3 `diagnostic_claude`  same-verdict rate per OCID vs E2 L4 (the P6 anchor).
5. Cohen's kappa (with Landis-Koch banding) for first-pass / blind-agent /
   reconciled pairings on both diagnostic arms.
6. P1-P6 disposition table — locked thresholds from `planning/predictions.md`,
   disposition vocabulary from `programme/PROCESS.md`.
7. Cost-accuracy table — dry-run baseline tokens/record vs Phase 2 actuals.
8. Four PNG charts under `results/analysis_charts/`.

## Inputs (all on `main`, read-only)

- Phase 2 bundles: `results/runs/phase-2-20260529T092611-Z/{arm_a,arm_b,arm_c,l4_without_nudge,diagnostic_primary,diagnostic_claude}/*.bundle.json`
- Phase 2 summary: `results/runs/phase-2-20260529T092611-Z/phase-2-summary.json`
- Dry-run summary: `results/runs/dry-run-20260528T164807-Z/dry-run-summary.json`
- Reconciled rubric sheets: `results/rubric_coding_{primary,claude}.jsonl`
- First-pass and blind-agent sheets: `results/rubric_coding_primary_first_pass.jsonl`, `results/rubric_coding_{primary,claude}_blind_agent.jsonl`
- E2 Phase 2 bundles (for cross-experiment): `../procurement-context-gradient/results/runs/phase-2-20260522-101324-Z/{L3,L4}/*.bundle.json`

## Outputs

- stdout: tables for every section
- `results/analysis_outputs.json` — canonical numbers for round-tripping into
  the writeup (the writeup MAY import this file directly)
- `results/analysis_charts/*.png` — four reproducible figures

## Running it

The script is laid out as Jupytext "percent" cells so it opens as a notebook
in VSCode / Jupyter, but it also runs as a plain script.

### As a script (recommended)

Requires Python 3.10+ and `matplotlib` (only needed for the chart cell — every
number is computed without it).

The repo's runner venv already has everything it needs:

```bash
# matplotlib is installed on demand; everything else is stdlib.
procurement-context-disambiguation/runner/.venv/bin/pip install matplotlib
procurement-context-disambiguation/runner/.venv/bin/python \
  procurement-context-disambiguation/results/analysis.py
```

Or with any Python 3.10+:

```bash
python3 -m pip install matplotlib  # one-time
python3 procurement-context-disambiguation/results/analysis.py
```

If matplotlib is unavailable the chart section prints a notice and exits 0 —
every number above is still written to `analysis_outputs.json`.

### As a notebook

```bash
pip install jupytext jupyterlab matplotlib
jupytext --to ipynb procurement-context-disambiguation/results/analysis.py
jupyter lab procurement-context-disambiguation/results/analysis.ipynb
```

(The `.ipynb` is intentionally not committed — `analysis.py` is the source of
truth, and Jupytext can regenerate the notebook on demand.)

## Sanity anchors and drift warnings

`SANITY_ANCHORS` near the top of `analysis.py` is the cross-validation table
of numbers from the prior in-session analysis. If any computed number drifts
more than 1% from an anchor, the script prints a `DRIFT WARNING` line and
records the warning in `analysis_outputs.json` (`warnings` field).

Set `E3_DRIFT_FATAL=1` to make drift warnings exit non-zero (useful in CI).

### Known drift at first commit

- **`diagnostic_claude` verdict mix**: the script computes
  `ALLOW=36, REVIEW=20, DENY=44`; the prior in-session anchor was `35/20/45`.
  Direct re-count of the 100 bundles confirms the script's number. The
  writeup should use **36/20/44** — the signed receipts are canonical.

## Don't touch

- Signed receipt bundles
- Reconciled rubric sheets (`rubric_coding_primary.jsonl`, `rubric_coding_claude.jsonl`)
- `phase-2-summary.json` / `dry-run-summary.json`

If you find yourself wanting to edit any of those, stop and ask — they are
SHA-bound to the locked predictions tag `v0.3-predictions-locked`.
