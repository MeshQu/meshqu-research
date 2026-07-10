# Data guide

This guide is for anyone analysing the MeshQu research corpora. It assumes you can read a parquet file and nothing else about this repository.

## What this dataset is

Three pre-registered experiments studied how an LLM agent reviews UK public procurement records, and how a deterministic policy engine judges the same records. Every decision produced a cryptographically signed receipt anchored to a public transparency log. The receipts are the dataset.

| Experiment | Directory | Receipts | What it varies |
|---|---|---|---|
| E1 (MRP-2026-02) | `procurement-decisions/` | 283 | nothing; baseline agent vs policy |
| E2 (MRP-2026-03) | `procurement-context-gradient/` | 1,429 | governance context shown to the agent, L0 to L4 |
| E3 (MRP-2026-04) | `procurement-context-disambiguation/` | 1,332 | which component of the context drives the effect |

All three experiments evaluate the same 283 procurement records against the same policy snapshot. E2 and E3 re-run those records under different conditions. That design makes per-record comparison across conditions the central analytical move.

One boundary to hold on to: there are no human verdicts in this dataset. Every row pairs an AI recommendation (`ai_verdict`) with a deterministic rule-engine verdict (`policy_verdict`). No human ever judged the 283 procurements. E3's rubric coding sheets are human and AI classifications of model reasoning text, not human decisions about the procurements. If you want a human comparator, that is a separate dataset you would have to build, and it lives outside this canonical corpus.

## Start here

```python
# pip install pyarrow==25.0.0
import pyarrow.parquet as pq

receipts = pq.read_table("data/receipts.parquet").to_pandas()
violations = pq.read_table("data/violations.parquet").to_pandas()

receipts.groupby(["experiment", "condition"]).size()
```

Column definitions are in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md). Row counts and file digests are in [`DATA_MANIFEST.json`](DATA_MANIFEST.json). Licensing and the required attribution line are in [`DATA_LICENSE.md`](DATA_LICENSE.md). If parquet is not convenient, [`receipts.csv`](receipts.csv) holds the same rows; the parquet is the typed, canonical copy.

The two verdict columns are different actors. `ai_verdict` is the LLM's recommendation (ALLOW / REVIEW / DENY). `policy_verdict` is the rule engine's verdict over the same evidence (ALLOW / DENY only). Their divergence is the subject of the research, so never treat disagreement as an error.

Join the two tables on `decision_id`. Join across experiments and conditions on `ocid`. The `ocid` identifies the underlying procurement record and is stable across all 3,044 rows.

## Facts that will save you a bad afternoon

1. E1 attempted 300 records but the corpus holds 283. An OCID identifies a contracting process, and OCDS lets a publisher issue multiple releases for the same process. The feed returned 12 OCIDs more than once and the duplicates deduplicated on ingest. Use 283 as the denominator everywhere.
2. E2's `L4_PERMUTED` condition is a 14-record adversarial diagnostic, not a sixth ladder rung. Exclude it from ladder-trend analysis unless you are studying the diagnostic itself.
3. E3's `diagnostic_primary` and `diagnostic_claude` arms cover a selected 100-record subset, not the full 283. Do not compare their rates directly against the 283-record arms without accounting for the subset selection rule (documented in E3's planning directory).
4. Every observed policy verdict is binary ALLOW or DENY, and every violation in the corpus is `severity: critical`. That is observed behaviour, not the whole authored policy: the snapshot also contains two high-severity rules (PROC-004-COI, PROC-006-MOD-CAP) that never fired on this corpus. The agent reasons in three verdicts. Naive verdict-equality agreement is therefore mechanically low and mostly meaningless. Read E1's finding 006 before computing agreement statistics.
5. Boolean-shaped evidence fields inside the receipts are strings (`"true"` / `"false"`), not booleans. The parquet columns are already typed, but this matters the moment you parse bundles yourself.
6. `procurement_method_open_flag` is present on only 19 of the 283 underlying records. That sparsity is a property of the public source data and it is analytically load-bearing for rule PROC-005-OPEN-TENDER.

## Going deeper than the parquet files

The parquet files carry the analysis-ready core. The full evidence lives in the bundles.

Each experiment's canonical corpus is `<experiment>/results/corpus.tar`. Unpack it and parse `bundles/<decision_id>.bundle.json`. The bundle format has two JSON layers; see the dictionary for the parsing pattern. Bundles carry the full evidence fields, the agent's recommended action, hashes of the agent's prompt and reasoning, the policy snapshot, the Ed25519 signature, and the Rekor transparency anchor.

The E1 tar also contains 285 AppleDouble `._` sidecar members (macOS metadata written at export time). They are binary, not JSON, and parsing one raises a UnicodeDecodeError. Skip any member whose name starts with `._`. macOS `tar -tf` hides these members while Python's `tarfile` shows them, so do not be surprised when the two report different counts.

Ignore any `results/runs/` directory. Those are pre-export execution trails kept for audit. They contain smoke runs, aborted runs, and superseded data. They are not analysis input.

## Verifying what you were given

You do not have to trust this export. Every receipt is independently verifiable.

- Recompute the tar and parquet digests and compare against `DATA_MANIFEST.json`.
- Re-run `python data/build_export.py`. It re-reads the tars, re-asserts the counts, and reproduces the parquet files byte for byte.
- Drop any single bundle JSON into <https://verify.meshqu.com>. The verifier checks the signature and the public Rekor log entry offline from this repository.

## Reading order for context

1. Each experiment's `README.md`, for what was run and why.
2. Each experiment's `planning/predictions.md`, for what was predicted before the run. Each is anchored to a lock tag (`v0.1`, `v0.2`, `v0.3-predictions-locked`) and the tagged content is the pre-registration record. See the note beside E3's copy about its stale status line.
3. Each experiment's `writeup/`, for the published findings.
4. `methodology/receipt-anchored-evaluation.md`, for the method itself.
