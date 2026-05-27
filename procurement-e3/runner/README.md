# Experiment 3 (E3) — runner

**Status**: empty scaffolding. No code yet.

Once E3 scope locks, this directory will hold the runner — likely a fork of `procurement-context-gradient/runner/` (E2) with adaptations for whatever variants E3 commits to.

## Likely shape (based on E2)

```
runner/
├── README.md                       (this file — will be replaced)
├── pyproject.toml
├── requirements.txt
├── meshqu_runner/                  (the runner package)
│   ├── multi_pass.py               (or single-pass if E3 doesn't ladder)
│   ├── level_handlers.py           (if E3 ladders)
│   ├── context_levels.py
│   └── substrate_cache.py
├── prompts/                        (locked content; SHA-bound into receipts)
│   ├── L1_*.md
│   ├── L2_*.md
│   ├── L3_*.md
│   └── L4_*.md
├── scripts/
│   └── phase_X_live.py             (driver scripts for each run phase)
├── system_prompt.md                (agent scaffold; SHA-bound)
├── contracts/                      (JSON schemas for bundle envelope)
└── tests/
    └── fixtures/                   (substrate fixtures)
```

## Carry-forward defaults from E2

- Substrate adapter pattern (reads frozen fixture; no live API at substrate boundary)
- Bundle envelope versioning (`BUNDLE_ENVELOPE_VERSION`)
- Ed25519 signing + Rekor anchoring per receipt
- Level-batching execution order if E3 retains the ladder format
- Frozen-archive isolation for any precedent material (per E2 L3 pattern)

## What changes for E3 (placeholder)

To be specified once scope locks. Specific likely items:

- **L3.5 variant** (if included): new level handler that mounts precedents without L4 policy text
- **Larger Permuted-Policy diagnostic** (if included): scale from 14 to ≥100 records; add hand-coded rubric output to the bundle
- **Cross-model replication** (if included): adapter layer that swaps the model API client
- **Investigative-agent variant** (if included): substantial format change — agent invokes tools, retrieves linked notices, emits multi-step traces. Probably warrants its own runner subdir.
