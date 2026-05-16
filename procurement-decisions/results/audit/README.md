# Audit — Machine-Readable Execution Traces

> Per-decision traces, anomaly events, checkpoint markers.
> Written by the harness during execution; append-only at run time.

## What lives here

Three JSONL files, each append-only, one line per event:

| File | Schema | When written |
|---|---|---|
| `decision_traces.jsonl` | Per-decision audit record (see schema below) | One line per decision, written immediately after MeshQu returns the receipt |
| `anomalies.jsonl` | Per-anomaly event with categorisation | One line per anomaly observed, written when detected |
| `checkpoints.jsonl` | Per-checkpoint marker for resume-from-N+1 | One line per checkpoint (typically every record or every 10 records) |

## decision_traces.jsonl schema

One line per processed decision. Required fields:

```json
{
  "ts": "ISO-8601 timestamp (UTC, milliseconds)",
  "run_id": "matches run-manifest.json's run_id",
  "record_index": 147,
  "ocid": "ocds-b5fd17-…",
  "decision_id": "MeshQu decision UUID",
  "policy_snapshot_digest": "sha256 of the policy snapshot",
  "agent_verdict": "ALLOW | DENY | REVIEW",
  "agent_reasoning_sha256": "sha256 of the agent's reasoning text",
  "meshqu_verdict": "ALLOW | DENY | REVIEW",
  "rules_fired": ["PROC-001-S53", "PROC-005-OPEN-TENDER"],
  "agree": true,
  "latency_ms": {
    "agent": 1240,
    "meshqu_evaluate": 87,
    "rekor_anchor": 312,
    "total": 1639
  },
  "receipt_integrity_hash": "sha256",
  "receipt_signature_kid": "meshqu-experiment-procurement-2026",
  "rekor_log_index": 12345678,
  "rekor_log_entry_uuid": "…"
}
```

Optional fields (present when relevant):

- `re_run_of`: if this is a reproducibility re-run, the original `decision_id` it's re-running.
- `anomaly_refs`: array of anomaly event IDs from `anomalies.jsonl` if any fired during this decision.
- `notebook_refs`: array of notebook entry IDs if the researcher explicitly linked a note to this decision.

## anomalies.jsonl schema

One line per anomaly. Required fields:

```json
{
  "ts": "ISO-8601 timestamp (UTC, milliseconds)",
  "run_id": "matches run-manifest.json",
  "anomaly_id": "uuid",
  "category": "see categories below",
  "severity": "info | warn | error",
  "context": {
    "record_index": 147,
    "ocid": "ocds-b5fd17-…",
    "decision_id": "…"
  },
  "summary": "one-line human-readable description",
  "detail": "free-form text with structured fields where relevant"
}
```

### Anomaly categories

| Category | When to use |
|---|---|
| `latency_spike` | Operation took materially longer than the histogram p99 |
| `rekor_anchor_failed` | Sigstore Rekor anchoring did not complete; receipt written without log inclusion |
| `rekor_anchor_slow` | Rekor anchoring succeeded but took >5s; record context for later analysis |
| `verifier_rejected` | Bundle round-trip failed verification on a receipt the run produced |
| `agent_output_malformed` | Agent returned a verdict outside the enumerated set, or non-JSON when JSON expected |
| `agent_timeout` | Agent call exceeded the configured timeout |
| `substrate_record_malformed` | OCDS record had structural issues that required adapter fall-back logic |
| `policy_evaluator_error` | MeshQu policy evaluator returned an error rather than a verdict |
| `db_write_slow` | Receipt write took >1s; capacity signal |
| `db_write_failed` | Receipt write failed entirely (should pause the run) |
| `unexpected` | Catch-all for events that don't fit above categories; surface for taxonomy refinement |

A new category SHOULD only be added when an observed anomaly genuinely doesn't fit. Adding a category is a small documentation update to this README plus the harness's anomaly emission code.

## checkpoints.jsonl schema

One line per checkpoint event. Required fields:

```json
{
  "ts": "ISO-8601 timestamp (UTC, milliseconds)",
  "run_id": "matches run-manifest.json",
  "checkpoint_id": "uuid",
  "last_completed_record_index": 147,
  "next_record_index": 148,
  "decisions_completed": 147,
  "decisions_remaining": 153,
  "resumable": true,
  "notes": "optional free-form text — e.g. 'paused for ops investigation'"
}
```

The harness writes a checkpoint after every successful decision by default (low overhead given the run is sequential). On run start, the harness reads the last checkpoint and resumes from `next_record_index` rather than starting over.

## Discipline rules

1. **Append-only.** Never rewrite past lines. Even corrected interpretations get a new line, not an in-place edit. If a `decision_traces.jsonl` line turns out to have been mis-categorised, write a follow-up line (or a `notebook/findings/` document) explaining the correction.
2. **One line per event.** Multi-line JSON is harder to parse incrementally. Tools like `jq -c` produce the right shape.
3. **Timestamps in UTC, milliseconds, ISO-8601.** No local-timezone confusion.
4. **Reference IDs over inline copies.** If a decision trace references an OCID, write the OCID, not the full OCDS record. The record is reachable via the OCID + `source_url` field on the receipt.
5. **Don't put PII or signing keys in audit files.** Public records carry public signatories; that's fine. The private signing key never appears.

## When the harness writes vs when humans write

Audit files are written by the harness only. Humans don't edit them. If a human observation arises from looking at an audit line, the observation goes in `notebook/` (or a `notebook/findings/` document if substantial) — never in `audit/`.

This separation is what keeps `audit/` reliable as machine-readable evidence.

## Build-phase prerequisites

The harness's execution-capture path (added in build phase per task `OBS-401` in the multi-tenant-observability harness and the substrate adapter implementation) must emit per these schemas. The schemas commit at brief 10 application; the implementation honours them at build-phase time.
