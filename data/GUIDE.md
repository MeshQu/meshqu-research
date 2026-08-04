# Data guide

This guide is for anyone analysing the MeshQu research corpora. It assumes you can read a parquet file and nothing else about this repository.

## The data in plain terms

When a UK public body buys goods or services (a council resurfacing roads, an NHS trust buying software, a ministry hiring consultants), it must publish the contract award on Contracts Finder, the UK government's public procurement portal. Those published awards are the raw material of this dataset. Each award record says, roughly: who bought, from which supplier, for how much, and when the award notice was published. The records are open data, published in the Open Contracting Data Standard (OCDS) and licensed under the Open Government Licence.

The experiments took 283 such award records and had two very different reviewers judge each one for compliance:

- An LLM agent reads the record and recommends a verdict: ALLOW, REVIEW, or DENY.
- MeshQu's rule engine evaluates the same record against a written policy of six rules drawn from the UK Procurement Act 2023 and related frameworks, and produces its own verdict: ALLOW or DENY.

Two real records show the shape of the data. Record `ocds-b5fd17-d2f1100a-...` is a £165,000 contract whose award notice was published 68 days after the award. The Procurement Act gives public bodies 30 days, so the rule engine fires PROC-001-S53 and says DENY. The agent, reading the same record, said REVIEW and asked to verify the notice trail. Record `ocds-b5fd17-28aab079-...` is a £45,000 contract published after 21 days. No rule fires; the engine says ALLOW. The agent still said REVIEW. That pattern is the story of the whole corpus: on E1's 283 records the cautious agent said REVIEW 276 times and never DENY, while the decisive rule engine said DENY 139 times on the same evidence.

E1 established that baseline gap. E2 asked whether showing the agent more governance context (policy text, precedent receipts, structured decision context, in five increasing rungs) closes it. E3 pulled apart which ingredient of that context actually drives the change. Every one of the 3,044 decisions across all three experiments produced a cryptographically signed receipt, so every number in the writeups can be re-derived from the files in this repository.

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
# Requires Python 3.10 or newer (pyarrow 25.0.0 does not install on 3.9).
# Tested with Python 3.12 and 3.14.
# pip install pyarrow==25.0.0 pandas
import pyarrow.parquet as pq

receipts = pq.read_table("data/receipts.parquet").to_pandas()
violations = pq.read_table("data/violations.parquet").to_pandas()

receipts.groupby(["experiment", "condition"]).size()
```

Column definitions are in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md). Row counts and file digests are in [`DATA_MANIFEST.json`](DATA_MANIFEST.json). Licensing and the required attribution line are in [`DATA_LICENSE.md`](DATA_LICENSE.md). If parquet is not convenient, [`receipts.csv`](receipts.csv) holds the same rows; the parquet is the typed, canonical copy.

The two verdict columns are different actors. `ai_verdict` is the LLM's recommendation (ALLOW / REVIEW / DENY). `policy_verdict` is the rule engine's verdict over the same evidence (ALLOW / DENY only). Their divergence is the subject of the research, so never treat disagreement as an error.

Join the two tables on `decision_id`. Join across experiments and conditions on `ocid`. The `ocid` identifies the underlying procurement record and is stable across all 3,044 rows.

## Which layer to use

The data exists in four layers. Use the highest one that answers your question.

1. `data/receipts.parquet` is the analysis layer and the default for everything. It now carries the evidence fields as columns, so evidence-conditioned analysis does not need the tars.
2. `data/source_records.json` is the normalised 283-record source table, one entry per OCID with per-field provenance notes. Use it for substrate-level joins and provenance questions. It is a verbatim, hash-verified copy of the E2/E3 runner fixtures; the originals remain in place under each runner's `tests/fixtures/`.
3. Live Contracts Finder is for provenance checking only. The corpus is frozen; the live service may since have published new releases for the same OCIDs, so live data can differ from the substrate the receipts were evaluated against. Never substitute live data for the in-repo table.
4. `results/runs/` directories are never analysis input. They are the pre-export execution trail, kept for audit.

## Facts that will save you a bad afternoon

1. E1 attempted 300 records but the corpus holds 283. An OCID identifies a contracting process, and OCDS lets a publisher issue multiple releases for the same process. The feed returned 12 OCIDs more than once; those repeats were not filtered before evaluation, they were POSTed and answered from the evaluator's OCID-keyed idempotency cache, so they produced no additional receipts. Use 283 as the denominator everywhere. If you join evidence columns across E1 and E2/E3, read the `ocid` caveat in the data dictionary first — for those 12 OCIDs the two sides bind different releases, which is why the published MeshQu verdict splits differ by two records ([IA-2026-02](../docs/integrity-audits/2026-08-04-corpus-lineage-and-receipt-count.md)).
2. E2's `L4_PERMUTED` condition is a 14-record adversarial diagnostic, not a sixth ladder rung. Exclude it from ladder-trend analysis unless you are studying the diagnostic itself.
3. E3's `diagnostic_primary` and `diagnostic_claude` arms cover a selected 100-record subset, not the full 283. Do not compare their rates directly against the 283-record arms without accounting for the subset selection rule (documented in E3's planning directory).
4. Every observed policy verdict is binary ALLOW or DENY, and every violation in the corpus is `severity: critical`. That is observed behaviour, not the whole authored policy: the snapshot also contains two high-severity rules (PROC-004-COI, PROC-006-MOD-CAP) that never fired on this corpus. The agent reasons in three verdicts. Naive verdict-equality agreement is therefore mechanically low and mostly meaningless. Read E1's finding 006 before computing agreement statistics.
5. Boolean-shaped evidence fields inside the receipts are strings (`"true"` / `"false"`), not booleans. The parquet columns are already typed, but this matters the moment you parse bundles yourself.
6. `procurement_method_open_flag` is present on only 19 of the 283 underlying records. In the parquet it is null where absent; no default was filled. That sparsity is a property of the public source data and it is analytically load-bearing for rule PROC-005-OPEN-TENDER.
7. On 5 of the 12 duplicated OCIDs, E1's evidence differs from E2/E3's because the feed's multiple releases carried different values and the two pipelines resolved them differently. E2 and E3 always agree with each other and with `source_records.json`. The dictionary lists the 5 OCIDs. Handle them explicitly in any cross-experiment evidence join.

## Going deeper than the parquet files

The parquet files carry the analysis-ready core, including the evidence fields. What stays in the bundles is the cryptographic material and the agent surface.

Each experiment's canonical corpus is `<experiment>/results/corpus.tar`. Unpack it and parse `bundles/<decision_id>.bundle.json`. The bundle format has two JSON layers; see the dictionary for the parsing pattern. Bundles carry the agent's recommended action, hashes of the agent's prompt and reasoning, the full policy snapshot, the Ed25519 signature, and the Rekor transparency anchor.

The receipts bind SHA-256 hashes of the agent's reasoning, not the reasoning texts. The texts now ship as a verified supplement: [`reasoning_texts.parquet`](reasoning_texts.parquet) (with a CSV copy) holds 2,761 texts, every one checked against the `agent_reasoning_sha256` its canonical receipt binds. Coverage is complete for E2 and E3. E1's texts were never committed to the repository, so its 283 receipts have no texts here; [`REASONING_SUPPLEMENT.md`](REASONING_SUPPLEMENT.md) explains. Verify any row yourself in one line: `hashlib.sha256(row["reasoning_text"].encode("utf-8")).hexdigest() == row["reasoning_sha256"]`. Do not go looking for texts in `results/runs/` directly; the supplement exists so the audit-trail rule can hold.

The E1 tar also contains 285 AppleDouble `._` sidecar members (macOS metadata written at export time). They are binary, not JSON, and parsing one raises a UnicodeDecodeError. Skip any member whose basename starts with `._` (the receipt sidecars are named `bundles/._<decision_id>.bundle.json`, so test the filename part, not the full path). macOS `tar -tf` hides these members while Python's `tarfile` shows them, so do not be surprised when the two report different counts.

Ignore any `results/runs/` directory. Those are pre-export execution trails kept for audit. They contain smoke runs, aborted runs, and superseded data. They are not analysis input.

## Verifying what you were given

You do not have to trust this export. Every receipt is independently verifiable.

- Recompute the tar and output digests and compare against `DATA_MANIFEST.json`.
- Re-run `python data/build_export.py` under the pinned pyarrow. It re-reads the tars, re-asserts the counts, re-verifies that the two source-record fixtures still match, and reproduces every output byte for byte.
- Drop any single bundle JSON into <https://verify.meshqu.com/bundle>, the dedicated bundle verifier. The main page at verify.meshqu.com expects a bare receipt and rejects an exported bundle as an invalid receipt. The bundle verifier checks the signature and the public Rekor log entry offline from this repository.

## Reading order for context

1. Each experiment's `README.md`, for what was run and why.
2. Each experiment's `planning/predictions.md`, for what was predicted before the run. Each is anchored to a lock tag (`v0.1`, `v0.2`, `v0.3-predictions-locked`) and the tagged content is the pre-registration record. See the note beside E3's copy about its stale status line.
3. Each experiment's `writeup/`, for the published findings.
4. `methodology/receipt-anchored-evaluation.md`, for the method itself.
