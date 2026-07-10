# Data dictionary

This file documents the structure of the exported bundles and every column in the two parquet files. The parquet files are built from the three canonical `corpus.tar` files by [`build_export.py`](build_export.py). Digests and row counts live in [`DATA_MANIFEST.json`](DATA_MANIFEST.json).

Full receipt field documentation lives at <https://docs.meshqu.com/concepts/receipt-reference>.

## The two JSON layers of an exported bundle

Each `corpus.tar` contains `bundles/<decision_id>.bundle.json`. Each bundle is a JSON document with two layers.

Layer 1 is the envelope:

```json
{
  "manifest": { "decision_id": "...", "files": [ ... ], "manifest_digest": "..." },
  "files": {
    "bundle_manifest.json": "<JSON string>",
    "receipt.json": "<JSON string>",
    "policy_snapshot.json": "<JSON string>",
    "transparency_proof.json": "<JSON string>",
    "trusted_keys.json": "<JSON string>"
  }
}
```

Layer 2 is inside `files`. Every value there is a complete JSON document serialised as a string. You must parse it again:

```python
bundle = json.load(open(path))
receipt = json.loads(bundle["files"]["receipt.json"])
```

The receipt has two top-level objects. `context` is what was submitted for evaluation. It holds `fields` (the decision inputs, including the agent's recommendation) and `metadata` (correlation id, OCID, substrate). `result` is what the policy engine produced. It holds the verdict, violations, snapshot binding, signature, and the Rekor transparency anchor.

## receipts.parquet

One row per canonical receipt. 3,044 rows: 283 E1, 1,429 E2, 1,332 E3.

| Column | Type | Source | Notes |
|---|---|---|---|
| `experiment` | string | assigned by exporter | `E1`, `E2`, or `E3` |
| `condition` | string | derived, see below | normalised experimental condition |
| `decision_id` | string | `files.bundle_manifest.json` → `decision_id` | also the bundle filename |
| `ocid` | string | `receipt.context.metadata.ocid` | UK Contracts Finder OCDS release id |
| `ai_verdict` | string | `receipt.context.fields.agent_recommended_verdict` | ALLOW / REVIEW / DENY |
| `policy_verdict` | string | `receipt.result.decision` | ALLOW / DENY |
| `violation_codes` | list of string | `receipt.result.violations[].rule_code` | empty list when no violations |
| `violations_count` | int32 | length of `receipt.result.violations` | |
| `policy_snapshot_id` | string | `receipt.result.policy_snapshot_id` | same value on all 3,044 rows |
| `policy_snapshot_digest` | string | `receipt.result.policy_snapshot_digest` | same value on all 3,044 rows |
| `timestamp` | string | `receipt.result.timestamp` | ISO 8601, UTC |
| `model_id` | string | `receipt.context.fields.agent_model_id`, else `context.fields.model_id` | E3 carries both; they agree |

### The condition column

- E1 has a single condition. Every row is `baseline`.
- E2 uses `receipt.context.fields.governance_context_level` as-is: `L0` to `L4` (283 rows each) plus `L4_PERMUTED` (14 rows). `L4_PERMUTED` is the Permuted-Policy diagnostic, not a sixth ladder rung.
- E3 derives six arms from three flags. `l3_arm` = `A`/`B`/`C` gives `arm_a`/`arm_b`/`arm_c`. `nudge_excised` = true gives `l4_without_nudge`. `diagnostic` = true gives `diagnostic_claude` when `model_id` starts with `claude`, else `diagnostic_primary`.

### policy_verdict vs ai_verdict

These are two different actors and must not be conflated.

- `ai_verdict` is the LLM agent's recommendation. It is an input to the evaluation. It lives in `context.fields` because the agent's recommendation is part of what was submitted. Its range is ALLOW / REVIEW / DENY.
- `policy_verdict` is MeshQu's deterministic rule-engine verdict over the same evidence. It is the output of the evaluation. The experiment policy is binary, so its range is ALLOW / DENY. There is no REVIEW.

Agreement between the two columns is a research question, not a data quality check. E1's headline finding was exactly their divergence.

### String booleans

Boolean-shaped values in `context.fields` are JSON strings, not JSON booleans. `above_threshold`, `governed_by_pa23`, `is_modification`, and `direct_award_justification_present` hold the strings `"true"` and `"false"`. This is the wire format of the evaluation API and is preserved in the receipts. Compare against the string, or cast explicitly. Exception: the E3 flags `diagnostic` and `nudge_excised` are real JSON booleans.

### Deliberate sparsity: procurement_method_open_flag

`procurement_method_open_flag` is present on only 19 of 283 E1 records. The source OCDS releases publish the procurement method inconsistently, and the substrate adapter passes through only what the source record states. The sparsity carries into E2 (95 of 1,429 rows) and E3 (90 of 1,332 rows) because both reuse E1's 283 records. This is a property of the public data, not an export defect. The field is not a parquet column; you will meet it if you parse `context.fields` yourself. Rule PROC-005-OPEN-TENDER treats its absence as evidence missing, which is part of the evidence-sparsity story in the writeups.

## violations.parquet

One row per policy violation. 2,740 rows.

| Column | Type | Source | Notes |
|---|---|---|---|
| `experiment` | string | assigned by exporter | convenience copy from receipts.parquet |
| `condition` | string | derived | convenience copy from receipts.parquet |
| `decision_id` | string | `files.bundle_manifest.json` → `decision_id` | join key to receipts.parquet |
| `ocid` | string | `receipt.context.metadata.ocid` | |
| `rule_code` | string | `receipt.result.violations[].rule_code` | e.g. `PROC-001-S53` |
| `severity` | string | `receipt.result.violations[].severity` | `critical` on every rule in this policy |
| `field` | string | `receipt.result.violations[].field` | the evidence field the rule fired on |
| `reason_code` | string | `receipt.result.violations[].reason_code` | e.g. `VALUE_ABOVE_MAX` |

Receipts with `violations_count` = 0 have no rows here. The violation objects in the receipts carry further detail (`actual_value`, `expected_value`, `reason`, `policy_id`, `is_shadow`) that is not exported. Read the bundle directly if you need it.

## Reproducing the export

```
pip install pyarrow
python data/build_export.py
```

The script asserts the row counts, the condition counts, and the shared policy snapshot, and rewrites `DATA_MANIFEST.json`. The build is deterministic. A clean re-run produces byte-identical parquet files.
