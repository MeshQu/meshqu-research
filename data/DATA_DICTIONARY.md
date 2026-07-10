# Data dictionary

This file documents the structure of the exported bundles and every column in the exported tables (two parquet files, one CSV, one source-record JSON). All are built from the three canonical `corpus.tar` files by [`build_export.py`](build_export.py). Digests and row counts live in [`DATA_MANIFEST.json`](DATA_MANIFEST.json).

Full receipt field documentation lives at <https://docs.meshqu.com/concepts/receipt-reference>.

## The two JSON layers of an exported bundle

Each `corpus.tar` contains `bundles/<decision_id>.bundle.json`. Each bundle is a JSON document with two layers.

One tar-level trap first. The E1 tar contains 570 members: 285 real members (README, the bundles directory, 283 bundles) plus 285 AppleDouble `._` sidecar members written by macOS at export time. The sidecars are 163-byte binary metadata, not bundles. Parsing one as JSON raises a UnicodeDecodeError. Skip any member whose basename starts with `._`, as `build_export.py` does. Be aware that macOS `tar -tf` hides the sidecars from listings while Python's `tarfile` shows them, so the two tools report different member counts for the same file. The E2 and E3 tars contain no sidecars.

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
| `ocid` | string | `receipt.context.metadata.ocid` | OCDS contracting-process identifier, see below |
| `ai_verdict` | string | `receipt.context.fields.agent_recommended_verdict` | ALLOW / REVIEW / DENY |
| `policy_verdict` | string | `receipt.result.decision` | ALLOW / DENY |
| `violation_codes` | list of string | `receipt.result.violations[].rule_code` | empty list when no violations |
| `violations_count` | int32 | length of `receipt.result.violations` | |
| `policy_snapshot_id` | string | `receipt.result.policy_snapshot_id` | same value on all 3,044 rows |
| `policy_snapshot_digest` | string | `receipt.result.policy_snapshot_digest` | same value on all 3,044 rows |
| `timestamp` | string | `receipt.result.timestamp` | ISO 8601, UTC |
| `model_id` | string | `receipt.context.fields.agent_model_id`, else `context.fields.model_id` | E3 carries both; they agree |
| `contract_value` | float64 | `receipt.context.fields.contract_value` | GBP; source mixes int and float, exported as float |
| `publication_delay_days` | int64 | `receipt.context.fields.publication_delay_days` | days from award to Contract Details Notice |
| `above_threshold` | string | `receipt.context.fields.above_threshold` | string boolean, `"true"` / `"false"` |
| `governed_by_pa23` | string | `receipt.context.fields.governed_by_pa23` | string boolean |
| `is_modification` | string | `receipt.context.fields.is_modification` | string boolean |
| `direct_award_justification_present` | string | `receipt.context.fields.direct_award_justification_present` | string boolean |
| `procurement_method_open_flag` | string | `receipt.context.fields.procurement_method_open_flag` | sparse; null when the source record is silent, see below |
| `supplier_id` | string | `receipt.context.fields.supplier_id` | e.g. `GB-COH-...` (Companies House) or `GB-CFS-...` |

The last eight columns are the per-record evidence fields the policy evaluated, exported with wire values preserved: string booleans stay strings and absent fields land as null, never a default. Agent-side fields (`agent_prompt_sha256`, `agent_reasoning_sha256`, `agent_recommended_action`, `agent_temperature`) and experiment plumbing (`prereg_tag`, `runner_git_commit`, `model_sampling`, `policy_permutation_seed`, `l4_envelope_sha256`) are not exported; read the bundles if you need them. `model_sampling` is the one non-flat field in `context.fields` and stays in the bundles.

### The ocid column

An OCID identifies a contracting process, not a release. OCDS permits a publisher to issue multiple releases for the same process, and the UK Contracts Finder feed does. That is exactly why E1's 300 attempted releases collapse to 283 unique decisions: 12 OCIDs appeared more than once in the sample window, and the idempotency cache returned the same receipt for each repeat. Use `ocid` to join the same procurement record across experiments and conditions.

One join caveat follows from those duplicates. When a process has multiple releases, the releases can carry different values. E1's receipt binds the release its run evaluated; E2 and E3 evaluated the normalised source table (`source_records.json`), which resolved 5 of the 12 duplicated OCIDs to a different release. On those 5 OCIDs the evidence columns differ between E1 and E2/E3, and on two of them `above_threshold` flips. The 5 OCIDs: `ocds-b5fd17-f5052bc7-...`, `ocds-b5fd17-963c1afb-...`, `ocds-b5fd17-692f6806-...`, `ocds-b5fd17-6bb11187-...`, `ocds-b5fd17-2d7dff2e-...`. E2 and E3 always agree with each other and with `source_records.json`. If your analysis joins evidence across E1 and the later experiments, handle these 5 explicitly. Background: E1 finding 005.

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

`procurement_method_open_flag` is present on only 19 of 283 E1 records. The source OCDS releases publish the procurement method inconsistently, and the substrate adapter passes through only what the source record states. The sparsity carries into E2 (95 of 1,429 rows) and E3 (90 of 1,332 rows) because both reuse E1's 283 records. This is a property of the public data, not an export defect. In the parquet it is a nullable column: null means the source record was silent, and no default was filled. The 19-of-283 absence rate is itself meaningful. Rule PROC-005-OPEN-TENDER treats absence as evidence missing, which is part of the evidence-sparsity story in the writeups.

## violations.parquet

One row per policy violation. 2,740 rows.

| Column | Type | Source | Notes |
|---|---|---|---|
| `experiment` | string | assigned by exporter | convenience copy from receipts.parquet |
| `condition` | string | derived | convenience copy from receipts.parquet |
| `decision_id` | string | `files.bundle_manifest.json` → `decision_id` | join key to receipts.parquet |
| `ocid` | string | `receipt.context.metadata.ocid` | |
| `rule_code` | string | `receipt.result.violations[].rule_code` | e.g. `PROC-001-S53` |
| `severity` | string | `receipt.result.violations[].severity` | `critical` on every observed row, see below |
| `field` | string | `receipt.result.violations[].field` | the evidence field the rule fired on |
| `reason_code` | string | `receipt.result.violations[].reason_code` | e.g. `VALUE_ABOVE_MAX` |

Receipts with `violations_count` = 0 have no rows here. The violation objects in the receipts carry further detail (`actual_value`, `expected_value`, `reason`, `policy_id`, `is_shadow`) that is not exported. Read the bundle directly if you need it.

### Severity: authored vs observed

Distinguish the policy as authored from the behaviour observed on this corpus. The shared snapshot authors six rules: four at `severity: critical` (PROC-001-S53, PROC-002-AUTHORITY, PROC-003-DEBARMENT, PROC-005-OPEN-TENDER) and two at `severity: high` (PROC-004-COI, PROC-006-MOD-CAP). Only three rules ever fired on this corpus (PROC-001-S53, PROC-002-AUTHORITY, PROC-005-OPEN-TENDER), all critical. Every one of the 2,740 rows in violations.parquet is therefore `critical`, and every observed `policy_verdict` is binary ALLOW or DENY. Do not conclude from the data that the policy contains only critical rules. The high-severity rules exist in `policy_snapshot.json`; they never fired here.

## receipts.csv

`receipts.csv` is a human-readable convenience copy of receipts.parquet, same rows and columns. The parquet file is the typed, canonical load target. In the CSV everything is a string: `violation_codes` is serialised as a JSON array string, for example `["PROC-001-S53","PROC-005-OPEN-TENDER"]` (parse it with `json.loads`), numbers are plain literals, `timestamp` stays the ISO 8601 string it already was, and a null (such as an absent `procurement_method_open_flag`) becomes an empty cell. There is no CSV for violations.parquet.

## source_records.json

The normalised 283-record source table, one entry per unique OCID in ascending order. Each entry carries `ocid`, `decision_type`, `fields` (the same evidence fields exported to the parquet), and `substrate_notes` (per-field provenance and confidence from the substrate adapter). This is the exact table E2 and E3 evaluated. It is a verbatim copy of the two byte-identical runner fixtures at `procurement-context-gradient/runner/tests/fixtures/full_corpus_records.json` and `procurement-context-disambiguation/runner/tests/fixtures/full_corpus_records.json`; the export verifies the two still match and both originals remain in place. Use it for substrate-level joins and provenance questions without parsing the tars.

## Reproducing the export

```
# Requires Python 3.10 or newer
pip install pyarrow==25.0.0
python data/build_export.py
```

The script asserts the row counts, the condition counts, and the shared policy snapshot, and rewrites `DATA_MANIFEST.json`. The build is deterministic under the pinned pyarrow version: a clean re-run produces byte-identical parquet and CSV files, and the manifest records the version used. A different pyarrow version may serialise the same logical content to different parquet bytes.
