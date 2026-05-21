# Runner — Procurement-Context-Gradient (E2)

> Python harness that drives the procurement-context-gradient experiment
> runs across five governance-context levels (L0..L4) plus the
> Permuted-Policy diagnostic, and emits the machine-readable evidence
> the writeup depends on.

## Provenance

This package was **forked from `procurement-decisions/runner/`** at
`10f5475d9efa8c4682ac73b6956e3aeb46854e70` (the E1 runner that produced
MRP-2026-02). Why fork rather than share:

- E1 is the published artefact for MRP-2026-02; modifying its runner
  post-publication is uncomfortable.
- Forking surfaces the duplication that informs the eventual
  `methodology/` extraction (Phase 4, post-publish).
- Provenance is preserved via `decision_log.md` + the run-manifest's
  `runner_git_commit`.

E2 diverges from E1 in three structural places:

1. **Multi-pass orchestration** (`meshqu_runner/multi_pass.py`) wraps E1's
   per-record eval loop with a level-batched outer loop over L0..L4.
2. **New E2-local bundle envelope (v1)** — the file persisted at
   `results/runs/<run_id>/<level>/<decision_id>.bundle.json` carries
   `bundle_envelope_version: 1` and wraps the MeshQu-issued receipt
   alongside a new `governance_context_level` field. This is NOT a
   MeshQu receipt-schema bump — the MeshQu product schema is unchanged
   (currently v2). The level marker rides into MeshQu's integrity hash
   via the `context.fields` injection point (the same
   audit-only-but-hash-bound pattern E1 uses for `agent_*` fields).
   **No upstream `@meshqu/core` change required.** E1 never persisted
   local bundle files at all, so v1 == this is the first version of
   the wrapper format.
3. **Per-level handlers** (`meshqu_runner/level_handlers.py`) plug into
   the multi-pass loop so E2-003..005 fill in level-specific prompt
   addenda without touching the orchestration layer.

The OBS-205 / OBS-206 screenshot + dashboard mirror machinery is
inherited unchanged.

## Language and runtime

Python 3.11+. Dependencies pinned in `requirements.txt` (`requests`,
plus `openai` at runtime when not in stub mode). Standard-library modules
cover most of the surface.

## Layout

```
runner/
├── README.md                              (this file)
├── requirements.txt                       (pinned third-party deps)
├── pyproject.toml                         (pytest + package metadata)
├── system_prompt.md                       (locked agent system prompt — inherited from E1)
├── prompts/                               (Stage A locked level addenda — SHA-bound at startup)
│   ├── L1_governance_context.md
│   ├── L2_named_rules.md
│   ├── L3_precedent_block_format.md
│   └── L4_policy_envelope.md
├── meshqu_runner/
│   ├── agent.py / audit.py / ... (inherited from E1)
│   ├── multi_pass.py                      MultiPassController — level-batched orchestration
│   ├── level_handlers.py                  L0..L4 + L4_PERMUTED handler stubs (E2-002..006 extend)
│   └── prompt_loader.py                   SHA-256 of each level addendum at startup
├── contracts/
│   └── decision_context.schema.json       Inherited; extended with governance_context_level field
└── tests/
    ├── fixtures/smoke_records.json        3-record smoke fixture (E2-001 done criteria)
    ├── test_multi_pass.py                 Verifies 15 v3 receipts on 3-record × 5-level smoke
    ├── test_level_handlers.py
    ├── test_prompt_loader.py
    └── (E1 inherited tests — kept; will be triaged as E2-002..006 land)
```

## Quick start

```bash
cd procurement-context-gradient/runner
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest -q

# Stub end-to-end: 3 records × 5 levels → 15 receipts under results/runs/<run_id>/
python -m meshqu_runner.multi_pass --stub --records tests/fixtures/smoke_records.json
```

## Execution order — level-batched, not record-cycled

The runner processes **all N records at L0**, then all N at L1, then L2,
L3, L4. Rationale in `planning/experiment_design.md` §"Multi-pass
runner":

1. **Prompt-cache preservation at L4** — keeping the static `## Policy`
   block at the cache head across N consecutive L4 calls delivers the
   50–80% input-token reduction the cost model assumes.
2. **Comparability** — within a level, all records are evaluated under
   identical prompt scaffolding; cycling levels per record would mix
   in temporal-locality variance.

Within a level, records are processed in OCID-ascending order for
further determinism.

## Stub mode

`multi_pass.py` accepts an injected fake `Agent` and fake `MeshQuClient`.
This lets tests (and the `--stub` CLI flag) drive the orchestration
end-to-end without OpenAI or MeshQu credentials. The fake clients
synthesise deterministic ReceiptSummaries with hashes computed locally
from canonical-JSON of the fields map — the produced bundles are
structurally identical to live-mode bundles (same v3 schema, same
governance_context_level binding) but the integrity hash is local-only.
Stub bundles will NOT verify at `verify.meshqu.com` and carry
`is_stub: true` in the bundle envelope so they cannot be confused with
real receipts.

## Tests

```bash
pytest -q
```

The E2-001 acceptance test is `test_multi_pass.py::test_smoke_produces_15_v3_receipts`.

## Environment variables (live mode)

Same as E1 plus:

| Env var | Default | Notes |
|---|---|---|
| `MESHQU_RUNNER_RESULTS_DIR` | `<repo-root>/procurement-context-gradient/results` | Parent of `runs/`. |
| `MESHQU_RUNNER_PROMPTS_DIR` | `<runner-dir>/prompts` | Where L1..L4 addendum markdowns live. |
| `MESHQU_RUNNER_POLICY_SNAPSHOT_PATH` | `<repo-root>/procurement-context-gradient/policy/policy-snapshot-cbf12348.json` | The locked policy snapshot; its SHA is captured in the run manifest. |
