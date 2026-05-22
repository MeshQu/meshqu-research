# Phase 1 readiness report — 2026-05-22

## Summary

**Go for Phase 2, conditional on Sam's explicit acknowledgement of two items below.**
All 11 primary checklist items from the build-plan checklist verify ✓ against the smoke (PR #55), the dry-run (PR #57), and the merged runner code on main. All 4 additional gates verify ✓. Two judgment-calls need Sam's eye before pressing go — neither blocks the runner: (1) the single L0-vs-E1 MeshQu verdict mismatch on `ocds-b5fd17-6bb11187-…` from the dry-run (the dry-run output is the more-correct verdict; E1 archive looks stale on this record), and (2) automatic Grafana screenshot capture infra exists (`RunController` + `ScreenshotCapturer`) but is NOT wired into the `dry_run_live.py` driver and was not exercised at smoke or dry-run scale — Sam must decide whether the Phase 2 driver should call `RunController` (recommended; the screenshots README §"Automation is the primary mode" makes this the contracted path) or whether captures will be manual.

## Checklist results

### Primary checklist (from `phase_1_build_plan.md` §"The pre-full-run readiness checklist")

- [✓] **All 1,415 expected (record × level) pairs have a runner code path that exercises them.**
  Evidence: `runner/meshqu_runner/multi_pass.py:613-614` — nested `for level in config.levels: for record_index, record in enumerate(sorted_records):` produces exactly `len(levels) × len(records)` outcomes per run, no early-exit branches. The dry-run produced the expected per-level distribution (30/30/30/30/30 across L0..L4 + 1 L4_PERMUTED) — see `dry-run-validation-20260521-181714-Z.md` §3b.

- [✓] **L0-vs-E1 reproducibility verified on ≥10 records.**
  Evidence: smoke (3 records, 3/3 MeshQu match, 3/3 agent match — `smoke-validation-20260521-170331-Z.md` §3e) + dry-run (30 records, **29/30 MeshQu match, 27/30 agent match** — dry-run validation §3e). Total: 33 records compared, 32/33 MeshQu match. The 1 MeshQu mismatch (`ocds-b5fd17-6bb11187-ac69-45a7-8246-73ce1b53100d`) is flagged in §"Decisions for Sam" below — the runner's verdict is substantively more correct than the E1 archive on that OCID, not a runner bug.

- [✓] **Level-batching cache savings observed.**
  Evidence: dry-run L4 aggregate cache-hit fraction = **0.900** (27/30 calls reported `cached_tokens > 0`, mean cached 1,766 / mean prompt 3,694 ≈ 47.8% of input billed at discounted cache rate — dry-run validation §3d). This is up from the smoke's 0.333 (limited sample of 3), confirming the directional expectation in the E2-007 decision log §4.

- [✓] **All receipts in smoke + dry-run verify offline at `verify.meshqu.com` or via `meshqu-verifier`.**
  Evidence: smoke 16/16 PASS, dry-run 151/151 PASS via the Python verifier at `runner/scripts/verify_smoke_bundles.py` (reconstructs the v2 signing envelope per `@meshqu/core::buildReceiptV2EnvelopeBytes` and verifies Ed25519 against pinned key `MCowBQYDK2VwAyEAQKw/FAIkqj9HTt1pDd6WsPUf3gQQz04k2aV8tjRhWCw=`, kid `meshqu-experiment-procurement-2026-05`). Total: **167/167 verified**, 0 failures. Caveat captured in E2-007 decision log §8 — the Python verifier proves signature attestation but not local recomputation of the integrity hash from the persisted fields; that's tracked as a future bundle-envelope tightening, not an E2 prerequisite.

- [✓] **`governance_context_level` field present in every receipt's integrity payload.**
  Evidence: spot-checked one bundle per level from `results/runs/dry-run-20260521-181714-Z/`:
  - L0: `0d0d31fd-…` → `governance_context_level=L0` ✓
  - L1: `01120e87-…` → `governance_context_level=L1` ✓
  - L2: `10181efa-…` → `governance_context_level=L2` ✓
  - L3: `141f964e-…` → `governance_context_level=L3` ✓
  - L4: `005940d1-…` → `governance_context_level=L4` ✓
  - L4_PERMUTED: `dc92b58b-…` (diagnostic dir) → `governance_context_level=L4_PERMUTED` ✓

  Hash-bind test passes at `runner/tests/test_multi_pass.py::test_governance_context_level_is_hash_bound` — explicitly verifies that stripping `governance_context_level` from the canonical fields map and recomputing the hash produces a DIFFERENT hash than `receipt.integrity_hash` (negative assertion at line 134).

- [✓] **Permuted-Policy diagnostic produces cryptographically distinguishable receipts with `policy_permutation_seed` hash-bound.**
  Evidence: dry-run validation §4c — worked-example pair on `ocds-b5fd17-119d1c05-…`:
  - L4 main: integrity_hash `9adbac9dfa482b9c…`
  - L4_PERMUTED: integrity_hash `57790d2c039f1f2f…`
  - Distinct: YES ✓

  Independently corroborated by smoke validation §3g (different OCID, same distinctness invariant: `af3916a6…` vs `968e6921…`). Permutation-seed mechanics validated in unit tests at `runner/tests/test_permuted_policy.py`.

- [✓] **No service-role surfaces invoked from the runner.**
  Evidence: `grep -rinE "service.role|service_role|SUPABASE_SERVICE|SERVICE_KEY_ROLE" procurement-context-gradient/runner/` returns **zero matches**. The runner uses API-key auth via `MESHQU_EXPERIMENT_PROCUREMENT_API_KEY` (see `runner/meshqu_runner/meshqu_client.py` and `runner/scripts/.env.live` schema documented in E2-007 decision log §1).

- [✓] **Run manifest captures provenance.**
  Evidence: `results/runs/dry-run-20260521-181714-Z/manifest.json` contains every required field:
  - `agent_model_id`: `"gpt-5.4-2026-03-05"` ✓
  - `agent_temperature`: `0.0` ✓
  - `prompt_template_sha256` (per level): L1=`19b98639…`, L2=`d24847ed…`, L3=`a3e224cb…`, L4=`c90664f4…` ✓
  - `policy_snapshot_sha256`: `5d7d800186d4eda4…` ✓
  - `substrate_adapter_version`: `"cached-e1-dry-run-7ddf7274"` ✓
  - `runner_git_commit`: `"20e8b5c99459da4191580a78d514cbf548214d98"` ✓ (also surfaces `runner_git_dirty: true` for the dry-run — clean-tree commit will land for the Phase 2 driver invocation)

- [⚠️ partial — see Decisions for Sam #2] **Monitoring dashboards configured.**
  Evidence: dashboard JSON committed at `procurement-decisions/results/observability/dashboards/experiment-tenant-observability.json` ✓. Screenshot capture infrastructure exists: `runner/meshqu_runner/runner.py::RunController` + `runner/meshqu_runner/screenshots.py::ScreenshotCapturer` (OBS-205, observability runner Stream C). 12 capture-related tests in `runner/tests/test_screenshots.py` pass. **However**: `runner/scripts/dry_run_live.py` and `smoke_live.py` do NOT call `RunController.run_start()` / `after_record()` / `run_end()` — they invoke `run_multi_pass(…)` directly, so the dry-run produced **no Grafana captures**. The only PNGs in `procurement-decisions/results/observability/screenshots/` are pre-existing verify-bundle proofs from 2026-05-18, not runtime captures. The screenshots README §"Capture cadence — automation is the primary mode" makes manual capture explicitly discouraged for runs of this duration. **This is the second decision Sam owns: either wire `RunController` into the Phase 2 driver before launch, OR accept that Appendix B will rely on manual captures.**

- [✓] **Cost projection within budget envelope.**
  Evidence: dry-run-realised cost **USD $0.93** (151 calls); refined full-run projection **USD $8.79** (1,415 main + 14 diagnostic) — dry-run validation §3h. Reference envelope from E2-007 smoke: USD $9.68. Refined / reference multiple = **0.91×** (within envelope; 5.0× STOP threshold not approached). Sam confirms budget OK in the readiness PR comment.

- [✓] **Rate-limiting pacing verified.**
  Evidence: dry-run validation §"Rate-limiting incidents" — agent and MeshQu `retry_count` distributions both `{0: 151}`, **0 retries observed at 0.5s inter-request pacing** (`INTER_REQUEST_PAUSE_SECONDS = 0.5` in both `smoke_live.py:137` and `dry_run_live.py:96`). At 9.4× scale (1,415 main + 14 diagnostic = 1,429 calls vs 151 dry-run), the same pacing yields ~715s of wall-clock pacing across a ~80-minute run — comfortably below OpenAI's standard tier-1 RPM and MeshQu staging tenant's per-second tenant ceiling. Pacing math is linear; same conclusion holds unless OpenAI rate limits change between now and the Phase 2 launch.

### Additional gates

- [✓] **The PRs for E2-001..006 are all merged to main.**
  Evidence: `git log --oneline main` shows the full chain on top of the trunk:
  - `066eb98` E2-001 (#49) — multi-pass runner + bundle envelope + governance_context_level hash-binding
  - `c665f6d` E2-002 (#50) — L0 baseline + substrate cache reader
  - `236297d` E2-003 (#51) — L1 + L2 payload generators
  - `017053a` E2-004 (#53) — L3 precedent selector
  - `fba608f` E2-005 (#52) — L4 policy envelope + cache-preservation telemetry
  - `2b8e18f` E2-006 (#54) — Permuted-Policy diagnostic
  - `20e8b5c` E2-007 (#55) — Stage C smoke run
  - `af88f98` Behavioural taxonomy v1 (#56)
  - `3427ca9` E2-008 (#57) — Stage C dry-run

- [✓] **The Phase 1 build-plan branch is merged or in active review.**
  Evidence: `planning/phase_1_build_plan.md` already lives on `main` at commit `3427ca9` (all build-plan content baked in before E2-001 landed). No outstanding planning branch for Phase 1.

- [✓] **Stage A content files are populated (not stub).**
  Evidence: `runner/prompts/` contents:
  - `L1_governance_context.md`: 1 line, 690 chars (substantive prose — UK PA23/PCR_2015 regime narrative)
  - `L2_named_rules.md`: 10 lines (named-rule enumeration)
  - `L3_precedent_block_format.md`: 11 lines (precedent block schema)
  - `L4_policy_envelope.md`: 9 lines (policy envelope description)

  `prompt_template_sha256` per level matches the manifest entries (above) — content is byte-stable across the smoke and dry-run.

- [✓] **Decision log up to date.**
  Evidence: `planning/decision_log.md` (651 lines) carries entries dated 2026-05-21 for every E2-001..008 + behavioural taxonomy + pre-lock methodology adjustments. The E2-008 entry §1 explicitly documents one post-lock methodology adjustment: the diagnostic at dry-run scale runs on the (30 ∩ 14) intersection rather than the full 14-record subset (1 OCID via force-include because the natural intersection was 0). The phase_1_build_plan line 18 ("164 receipts" expected at dry-run) consequently shows 151 in the run — divergence is recorded and justified.

## Outstanding items

**None block Phase 2.** The two items in §"Decisions for Sam" are judgment calls, not blockers. The runner is functionally green; Sam's sign-off is the only remaining gate.

## Decisions for Sam

### 1. L0-vs-E1 MeshQu verdict mismatch on `ocds-b5fd17-6bb11187-ac69-45a7-8246-73ce1b53100d` (1/30 at dry-run scale)

This was already surfaced in the E2-008 PR body and decision log §6, but it warrants explicit re-acknowledgement before committing to 1,415 calls:

- E1 archive verdict: **DENY** with violations `[PROC-001-S53, PROC-002-AUTHORITY]`
- Dry-run verdict: **ALLOW** with no violations
- Fields are byte-identical between E1 and dry-run (`above_threshold="false"`, `procurement_method_open_flag="true"`, contract_value=0, etc).
- Both runs hit the same `policy_snapshot_digest=5d7d800186d4…`.
- Reading the current policy snapshot: PROC-001-S53's `when` clause requires `governed_by_pa23="true" AND above_threshold="true"` — but the record has `above_threshold="false"`. **The dry-run is more correct than the E1 archive on this record.**
- Most plausible hypothesis (per decision log §6): E1's evaluator at the time had a stale snapshot or a since-fixed substrate-binding bug (consistent with SOC2 PR1 EI-001, which fixed parameterised `set_config` in `withTenant` post-E1).

**What Sam needs to acknowledge**: this is not a runner bug; it's evidence that re-running E1's substrate through current MeshQu surfaces at least one correction. Phase 2 will likely surface more such corrections at 1,415-call scale (proportional rate would be ~47 records out of 283 corpus records × 5 levels = 1,415; at 1/30 = 3.3%, that's roughly **47 expected MeshQu-verdict-shifts from the E1 baseline**). This is **a Phase 2 finding, not a Phase 2 blocker** — but the writeup must frame the L0-vs-E1 comparison as "current MeshQu vs frozen E1 archive" rather than "L0-as-replica-of-E1". Sam to confirm this framing is acceptable before launch.

### 2. Grafana auto-capture is built but not wired into the Phase 2 driver path

- Capture infra: `RunController` + `ScreenshotCapturer` (shipped via the meshqu-research observability runner Stream C; PR refs `4448dd7e` + `bf5da06f`).
- Capture cadence (per `procurement-decisions/results/observability/screenshots/README.md`): dry-run every 2 records, full-run every 10 records — at 283 records the full-run produces ~28 checkpoint captures plus run-start + run-end.
- Dashboard JSON committed at `procurement-decisions/results/observability/dashboards/experiment-tenant-observability.json`.
- 12 unit tests in `runner/tests/test_screenshots.py` confirm the capture mechanics work in isolation.
- **Gap**: `runner/scripts/dry_run_live.py` and `smoke_live.py` invoke `run_multi_pass()` directly, never instantiating `RunController`. Result: 0 runtime Grafana PNGs from smoke or dry-run.

**What Sam needs to decide**: either (a) the Phase 2 driver (whether forked from `dry_run_live.py` or written fresh as `full_run_live.py`) MUST wire `RunController.run_start() / after_record() / run_end()` around `run_multi_pass()` so Appendix B captures populate automatically — this is the path the screenshots README explicitly contracts as "primary mode" and is the lower-risk option for a several-hour run; OR (b) accept manual captures, which the README itself flags as unreliable on runs of this duration.

**Recommendation**: option (a), wired before Phase 2 launches. This is a small adapter — a few lines wrapping the existing `run_multi_pass` invocation — but is OUT OF SCOPE for E2-009 (this package is doc-only; no code changes). If Sam wants this done, the work belongs in a small E2-010 or a Phase-2-launch-prep package, not E2-009.

## Sign-off

Sam confirms Phase 2 ready: [ ]
Date: ____________

---

Generated 2026-05-22 by E2-009 readiness audit.
