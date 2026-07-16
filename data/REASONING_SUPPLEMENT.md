# Verified reasoning-text supplement

The canonical Decision Receipts bind a SHA-256 hash of the agent's reasoning text (`context.fields.agent_reasoning_sha256`), not the text itself. This supplement publishes the texts for every receipt where the text could be extracted from the production run and verified against that bound hash.

## The integrity rule

A text ships here only if the SHA-256 of its UTF-8 bytes equals the `agent_reasoning_sha256` in its canonical receipt from `corpus.tar`. That check is what makes it legitimate to publish material from the non-canonical run directories at all. Texts that fail the check are excluded and recorded in `DATA_MANIFEST.json` under `reasoning_supplement.hash_failures` (currently none). Receipts with no production text are recorded as missing. Nothing is ever edited to make a hash pass.

You can verify any row yourself in three lines:

```python
import hashlib, pyarrow.parquet as pq
row = pq.read_table("data/reasoning_texts.parquet").to_pylist()[0]
assert hashlib.sha256(row["reasoning_text"].encode("utf-8")).hexdigest() == row["reasoning_sha256"]
```

To verify against the receipt rather than this file's own column, open `bundles/<decision_id>.bundle.json` in the experiment's `corpus.tar`, parse the two-layer JSON, and compare the same digest to `context.fields.agent_reasoning_sha256`. The hash rule is plain SHA-256 over the UTF-8 bytes of the text. No normalisation is applied.

## Coverage

| Experiment | Canonical receipts | Texts found | Verified | Failed | Missing |
|---|---|---|---|---|---|
| E1 | 283 | 0 | 0 | 0 | 283 |
| E2 | 1,429 | 1,429 | 1,429 | 0 | 0 |
| E3 | 1,332 | 1,332 | 1,332 | 0 | 0 |

Total: 2,761 verified texts in `reasoning_texts.parquet` and `reasoning_texts.csv`.

## The E1 situation

E1 has no reasoning texts and cannot get them from this repository. E1's production run (`dry-run-7ddf7274-...`, production despite the name) wrote its artefacts to the operator's disk and they were deliberately never committed; the repository's `procurement-decisions/results/runs/` holds only a README. The receipts bind the hashes, so if the off-repository artefacts are ever published, each text can be verified then by exactly the rule above. Until that happens, all 283 E1 receipts are recorded as missing. Do not use E1 smoke or rehearsal outputs as substitutes; they are different runs.

## Provenance

These texts come from the pre-export production run directories: `procurement-context-gradient/results/runs/phase-2-20260522-101324-Z/` for E2 and `procurement-context-disambiguation/results/runs/phase-2-20260529T092611-Z/` for E3. Each row's `source_run_path` names the exact file it came from. The run directories remain non-canonical for everything else: verdicts, violations, and evidence come from `corpus.tar` and the exports built from it, never from the run trail. The only thing this supplement takes from the runs is the text, and only because each text is verified against its canonical receipt.

## Columns

| Column | Meaning |
|---|---|
| `decision_id` | joins to `receipts.parquet` |
| `ocid` | the contracting process |
| `experiment`, `condition` | same normalisation as `receipts.parquet` |
| `model_id` | the model that wrote the reasoning |
| `reasoning_sha256` | the receipt-bound hash the text was verified against |
| `reasoning_text` | the verified text, byte-exact |
| `source_run_path` | repo-relative path of the run bundle the text came from |
| `verified` | always true; unverified rows are never included |

## Rebuilding

```
# Requires Python 3.10 or newer
pip install pyarrow==25.0.0
python data/build_reasoning_supplement.py
```

The build is deterministic: two runs produce byte-identical outputs. It reads only the two production run directories and the three corpus tars. Coverage counts and output digests live in `DATA_MANIFEST.json` under `reasoning_supplement` and `outputs`.
