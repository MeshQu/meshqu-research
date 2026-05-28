# Experiment 3 (E3) — decision log

Reverse-chronological. Most recent decision at the top. Each entry: date, decision, why, what's next.

---

## 2026-05-28 — E3-001 (PR #85, merge `e50030f`) — runner foundation shipped

**Decision**: forked E2's runner into `procurement-context-disambiguation/runner/`; gutted the additive-ladder logic; introduced an arm-keyed handler registry (`meshqu_runner/arms.py`) + receipt-integrity-payload extension; CLI `--arm <name>` dispatch surface. Foundation for Wave 2's seven parallel agents.

**Key resolutions during build/review**:
1. **8 arm placeholders registered, not 7.** The package's "Definition of done" said 7 but §2 enumerated 8 (`arm_a`, `arm_b`, `arm_c`, `l4_with_nudge`, `l4_without_nudge`, `l0_baseline`, `diagnostic_primary`, `diagnostic_claude`). Spec typo, not a spec change — `l4_with_nudge` is the E2-L4 baseline against which E3-005's no-nudge variant compares. Under-registering would have forced E3-005 to mutate the registry (wrong place). Approved 8.
2. **Deleted 8 inherited tests, then restored 1** (commit `9e2d07b`). 7 deletions were genuinely ladder-coupled (`test_multi_pass`, `test_l0_baseline`, `test_l1_l2_generators`, `test_l4_handler`, `test_permuted_policy`, `test_cache_preservation_smoke`, `test_phase_2_driver`). `test_precedent_selector.py` was over-pruned — restored 14 of its tests across 5 thematic scenarios (frozen-archive load, selector determinism, self-exclusion, OCID tie-break, k=4), stripped only the L3-handler / additivity-invariant block (imported `L3LiveHandler`, `L1ContextHandler`, `L2ContextHandler`, `compose_user_message`, `install_live_l3`).
3. **Process principle for future Wave 2 agents**: when a module is in the "frozen from E2" bucket (substrate adapter, substrate cache, precedent selector, precedent archive, agent prompt scaffold, meshqu client), its **non-ladder-coupled tests** belong in the same preserve bucket. `test_fork_parity.py` covers source SHAs but not behaviour; behavioural tests of byte-identical modules must also be preserved (modulo ladder-coupled scenarios within them, which are stripped scenario-by-scenario, not file-by-file).

**Fork-parity status**: the 7 SHA-guarded core files (`agent.py`, `meshqu_client.py`, `substrate.py`, `substrate_cache.py`, `precedent_archive.py`, `precedent_selector.py`, `system_prompt.md`) are byte-identical to E2 and asserted in `tests/test_fork_parity.py`. The 14 restored behavioural tests pass against the forked modules, corroborating byte-identity at runtime as well as at the SHA level.

**Receipt integrity payload — new fields**: `l3_arm`, `nudge_excised`, `model_id`, `model_sampling`, `diagnostic`, `policy_permutation_seed`, `runner_git_commit`, `prereg_tag` (set to literal `"v0.3-predictions-locked"`). Backwards compatible with E2's bundle envelope v1 (additive only).

**Test status at merge**: 254 passing (38 foundation + 14 restored + 202 other inherited). CLI smoke `python -m meshqu_runner.cli --arm arm_a --records 1 --dry` exits 0 with all 7 new integrity fields in the canonical bundle JSON.

**Stop conditions**: none fired. No drift in byte-identical core files; arm refactor did not touch substrate/cache/selector/archive; bundle envelope v1 retained; locked content (v0.3 tag) untouched.

**What's next**: Wave 2 dispatch — E3-002 (Arm A), E3-003 (Arm B), E3-004 (Arm C), E3-005 (L4-no-nudge), E3-006 (Claude swap), E3-007 (subset selector), E3-009 (rubric tool) — seven background agents in parallel, all cut from `main` at `e50030f`. E3-008 (scaled diagnostic) holds for Wave 3 pending E3-006 + E3-007 merge.

---

## 2026-05-27 — E3 scope locked: the disambiguation experiment

**Decision**: E3 is the disambiguation experiment. It reuses E1/E2's substrate, the frozen 283-record corpus, the policy snapshot, and the primary agent unchanged, and adds targeted variants to slice the confounds E2 surfaced but could not isolate. No new substrate; no investigative-agent format shift (that is E4).

**Scope cut — in:**
1. **L3 decomposition** — two non-additive probe rungs (L3-precedents-only, L3-density-control) to separate "precedents drove the L3 break" (Reading A) from "any sufficient content density drove it" (Reading B).
2. **L4-without-nudge** — excise the anti-sycophancy nudge clause from the L4 policy rung to separate "the nudge drove the L3→L4 backoff" (Framing A.1) from "the policy text alone drove it" (A.2).
3. **Scaled Permuted-Policy diagnostic (n ≥ 100) + hand-coded rubric + one cross-model arm** — establish inversion-blindness at scale (vs the 14-record signal) and test model-property vs task-class. Asymmetric: full diagnostic on the primary model, same diagnostic on one second model — no full second-model corpus.

**Scope cut — deferred:**
- Authoritative-vs-hypothetical framing axis (isolates the "authority-conditioned" qualifier) — secondary to establishing the effect at scale; revisit for E3.1 or E4.
- Cross-domain substrate (AML/KYC/clinical) — needs a new substrate adapter + policy authoring pass; E4-shaped.

**Alternatives considered**: a full cross-model corpus across all rungs (rejected — ~2x collection cost for marginal gain over the diagnostic-only arm); a fresh substrate (rejected — would reintroduce the substrate variable E3 holds fixed); folding the investigative-agent variant in (rejected — format shift, scoped as E4).

**Why**: E3 sharpens E2's findings into attributions. The two structural results (L3 break, inversion-blindness) are real but unattributed; the value of E3 is converting "we observed X" into "X is caused by Y / holds at scale / is/ isn't model-specific." Three completed experiments also become the triangulation base for the Receipt-Anchored Evaluation methods note (deferred to post-E3 as the trilogy capstone).

**Design decisions resolved (2026-05-27)**:
1. **L3 decomposition = 3 arms** — precedents-only (A) / precedents-no-verdict (B) / density-control (C). The 3rd arm isolates the verdict-exemplar signal, directly testing the §10 governance-memory interpretation (do *prior verdicts* anchor, or just prior cases?). Arm C matched on token count + discrete-unit count + prompt position; inspected for verdict-signal contamination before lock.
2. **Second model = Claude** (key available); diagnostic-only cross-model arm.
3. **Scaled-diagnostic n = pre-registered subset, target 100**; same 100 records on both models (record-matched); expandable later.
4. **L4-without-nudge = in scope.**

**What's next**: predictions drafted at segment level (`predictions.md`, pre-lock) — P1/P2 (L3 decomposition), P3 (L4 nudge), P4/P5 (scaled diagnostic), P6 (cross-model). Sam calibrates the falsification bands → pre-registration lock at `v0.X-predictions-locked`.

---

*Add new entries at the top of this section, above this line.*
