# Runner — Procurement-Context-Disambiguation (E3)

> Python harness that drives the procurement-context-disambiguation
> experiment runs across the L3 decomposition arms (A/B/C), the
> L4-without-nudge variant, the scaled Permuted-Policy diagnostic
> (primary + Claude), and the carry-forward L0 baseline.

## Provenance

This package was **forked from `procurement-context-gradient/runner/`**
(E2) at commit `9644bac`, with the pre-registration tag
**`v0.3-predictions-locked`** binding the locked content (prompts,
rubric, predictions, design parameters). Why fork rather than share:

- E2 is the published artefact; modifying its runner post-publication
  is uncomfortable.
- Forking surfaces the duplication that will inform the eventual
  `methodology/` extraction.
- Provenance is preserved via `decision_log.md` + the run manifest's
  `runner_git_commit` + the `prereg_tag` stamped into every receipt's
  integrity payload.

E3 diverges from E2 in one structural place:

**The ladder is gone.** E2 ladders L0 → L1 → L2 → L3 → L4 additively.
E3 doesn't. Every E3 arm is an independent probe, designed to *isolate*
what E2's additive L3 conflated (volume vs concreteness vs verdict
exemplars). The runner replaces E2's level-batched outer loop with a
flat arm-keyed dispatch (`meshqu_runner.arms`).

The byte-identical core — `agent.py`, `meshqu_client.py`,
`substrate.py`, `substrate_cache.py`, `precedent_archive.py`,
`precedent_selector.py`, `system_prompt.md` — is forked verbatim and
guarded by a SHA-comparison test (`tests/test_fork_parity.py`). If you
edit any of those files, that test will fail and the cross-experiment
integrity claim is broken; surface to Sam before continuing.

## The arms

| Arm name | Purpose | Origin |
|---|---|---|
| `arm_a` | Precedents only (E2's L3 block, no L1/L2) — isolates the precedent effect | E3-002 |
| `arm_b` | Precedents-no-verdict — concreteness without verdict signal | E3-003 |
| `arm_c` | Density control — length-matched neutral prose, no concrete cases | E3-004 |
| `l4_with_nudge` | E2's L4 envelope retained for sanity checks | inherited; nominal name change |
| `l4_without_nudge` | L4 minus the anti-sycophancy nudge clause | E3-005 |
| `l0_baseline` | L0 freshness check for dry-runs | inherited |
| `diagnostic_primary` | Scaled Permuted-Policy diagnostic on the primary model | E3-008 |
| `diagnostic_claude` | Scaled Permuted-Policy diagnostic on Claude (Opus 4.7) | E3-006 + E3-008 |

Eight arms total. The full main-grid sweep is `arm_a + arm_b + arm_c +
l4_without_nudge` over the 283-record corpus; the diagnostic sweep is
the locked n=100 subset against `diagnostic_primary` and
`diagnostic_claude`. `l4_with_nudge` and `l0_baseline` are not part of
the main reportable matrix — they exist for sanity / freshness checks.

## Receipt integrity payload

Every E3 receipt carries seven new integrity fields beyond E2's
`agent_*` fields. These ride into MeshQu's integrity hash via the
canonical-JSON serialisation of the `context.fields` map (same
audit-only-but-hash-bound channel E2 uses):

| Field | Type | Notes |
|---|---|---|
| `l3_arm` | `"A"`, `"B"`, `"C"`, or `null` | L3 decomposition arm letter; `null` for non-L3 arms |
| `nudge_excised` | bool | `true` only for `l4_without_nudge` |
| `model_id` | str | `gpt-5.4-2026-03-05` for primary; `claude-opus-4-7` for Claude |
| `model_sampling` | object | Per-arm sampling block (e.g. `{"temperature": 0}`; Opus is `{"temperature": null, "effort": "low"}`) |
| `diagnostic` | bool | `true` only for `diagnostic_*` arms |
| `policy_permutation_seed` | int / null | Required (and non-null) for diagnostic arms; rejected for non-diagnostic |
| `runner_git_commit` | str | SHA of the runner code at run time |
| `prereg_tag` | str | Literal `"v0.3-predictions-locked"` |

These are *additive*. Every E2-receipt field (`agent_*`, the substrate
fields) is preserved unchanged. The bundle envelope version remains v1
— no upstream `@meshqu/core` change is required.

## Language and runtime

Python 3.11+. Dependencies pinned in `requirements.txt`. Standard-
library modules cover most of the surface.

## Layout

```
runner/
├── README.md                              (this file)
├── requirements.txt                       (pinned third-party deps)
├── pyproject.toml                         (pytest + package metadata)
├── system_prompt.md                       (locked agent system prompt — byte-identical to E2)
├── prompts/                               (locked level content — SHA-bound at v0.3-predictions-locked)
│   ├── armB_precedent_no_verdict_format.md
│   ├── armC_density_control.md
│   └── L4_without_nudge.md
├── meshqu_runner/
│   ├── arms.py                            ARM REGISTRY — the foundation's entry point
│   ├── cli.py                             python -m meshqu_runner.cli --arm <name> --dry
│   ├── multi_pass.py                      RunConfig + run_arm — single-arm dispatch
│   ├── agent.py / meshqu_client.py / substrate.py / ...    (byte-identical to E2)
│   ├── level_handlers.py                  (vestigial — empty shell; see module docstring)
│   ├── context_levels/                    (E2's L1/L2/L3/L4 live handlers — dormant in E3, available for reuse by arm packages)
│   └── diagnostic/                        (E2's permuted-policy machinery — used by E3-008)
├── spike/
│   └── claude_spike.py                    (Phase-0 feasibility spike for Claude swap; preserved untouched)
├── contracts/
│   └── decision_context.schema.json       (inherited; will be extended per E3-006 if needed)
└── tests/
    ├── test_arm_registry.py               foundation: registry, integrity payload, CLI dispatch
    ├── test_fork_parity.py                foundation: byte-identical core files
    └── (inherited tests for agent / meshqu_client / substrate / audit / run_manifest)
```

## Quick start

```bash
cd procurement-context-disambiguation/runner
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest -q

# Foundation smoke: one stub record through Arm A, no live API calls
python -m meshqu_runner.cli --arm arm_a --records 1 --dry
```

## How to add a new arm

Subsequent packages plug in here without touching the orchestration:

```python
# In your new package's handler module:
from meshqu_runner import arms

@arms.register("arm_a")  # overwrites the placeholder
def arm_a_handler(record, *, precedent_selector, **kwargs) -> str:
    """Render Arm A's prompt: E2's L3 block, no L1/L2 prefix."""
    ...
```

The arm name must be in `arms.ARM_NAMES`. If you're adding a new arm
that's not yet enumerated, append to `ARM_NAMES` and add an
`ArmProfile` entry in `arms.py` (and update `tests/test_arm_registry.py`).

The arm handler receives the record dict + arbitrary kwargs (the
runner forwards `handler_kwargs` from `run_arm` verbatim). Return the
fully rendered user-message string the agent will see. There is no
additive composition — the string you return is the string the agent
sees.

## How to invoke each arm via the CLI

```bash
# Default (Arm A, 1 stub record)
python -m meshqu_runner.cli --arm arm_a --records 1 --dry

# Specific arm against an OCID list
python -m meshqu_runner.cli --arm arm_b \
    --ocid-list ../planning/diagnostic_subset.json \
    --dry

# Diagnostic arm — seed required
python -m meshqu_runner.cli --arm diagnostic_primary \
    --records 100 \
    --policy-permutation-seed 42 \
    --dry

# Override the model id (lands in receipt integrity payload)
python -m meshqu_runner.cli --arm arm_a --records 1 --dry \
    --model gpt-5.4-2026-03-05-canary
```

The foundation only supports `--dry`. Live mode wiring (real OpenAI /
Anthropic + real MeshQu API) lands in E3-002..006.

## Execution order — OCID-ascending within each arm

Within a single-arm run, records are processed in OCID-ascending order
for determinism. The "level-batching" rationale from E2 (prompt-cache
preservation at L4) no longer applies in the same way — E3 is one arm
per run, so each arm-run is naturally batched by the arm's prompt
shape. Cache preservation is still desirable for the L4 variants and
the diagnostic, but it's a per-arm concern (the L4-without-nudge
package will land cache-preserving prompt-prefix ordering inside
`l4_without_nudge`'s handler, not as runner-orchestration policy).

## Stub mode

`multi_pass.run_arm` accepts an injected fake `Agent` and fake
`MeshQuClient`. The `--dry` CLI flag wires `StubAgent` +
`StubMeshQuClient`. The fake clients synthesise deterministic
`ReceiptSummary` instances with integrity hashes computed locally from
canonical-JSON of the fields map — structurally identical to live-mode
bundles (same v1 envelope, same arm-aware integrity fields) but
unsigned and unanchored. Stub bundles carry `is_stub: true` and will
**not** verify at `verify.meshqu.com`.

## Tests

```bash
pytest -q
```

The E3-001 foundation tests are `test_arm_registry.py` (registry,
integrity payload, CLI dispatch) and `test_fork_parity.py` (byte-
identical core files). Inherited tests for `agent`, `meshqu_client`,
`substrate`, `audit`, `run_manifest`, `recover_orphans`,
`dashboard_mirror`, `screenshots`, `eval_loop` cover modules that
were forked verbatim and remain on their original contracts.
