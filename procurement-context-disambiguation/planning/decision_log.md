# Experiment 3 (E3) — decision log

Reverse-chronological. Most recent decision at the top. Each entry: date, decision, why, what's next.

---

## 2026-06-07 — Phase 2.5 closed: diagnostic_claude via AI-first; P5 Confirmed on both arms; cross-model rubric-axis finding

**Decision**: `diagnostic_claude` coded via AI-first + human review-and-adjudication protocol (PR #110's `review_all.py`). Blind agent pass (PR #111) produced 0/100/0 distribution. Reviewer walked all 100 records with agent's call + rubric refresher + default-rule sentence visible per record; accepted agent's call on all 100 (`review_action`: 100 `agent-accepted`, 0 `human-overridden`). κ between blind agent and final = +1.0000. Final canonical sheet: 0 Cat 1 / 100 Cat 2 / 0 Cat 3 → **P5 Confirmed**.

**Cross-model rubric-axis finding** (the substantive cross-arm observation):

| Arm | Model | Cat 1 | Cat 2 | Cat 3 |
|---|---|---:|---:|---:|
| `diagnostic_primary` | GPT-5.4 | **7 (7.0%)** | 93 (93.0%) | 0 (0.0%) |
| `diagnostic_claude` | Opus 4.7 | **0 (0.0%)** | 100 (100.0%) | 0 (0.0%) |

Both models predominantly inversion-blind. **GPT-5.4 occasionally names the inversion (7%); Opus never does (0%).** Coherent with the cross-model verdict-axis finding from Phase 2 (2026-05-29 decision_log entry): Opus 80% decisive vs GPT-5.4 23% decisive. Confident application of the rule-as-stated IS Cat 2 inversion-blindness; Opus's verdict decisiveness translates to rubric Cat 2 thoroughness. **Direction of effect is cross-axis-consistent at n=100.** Real cross-model contribution for the writeup.

**Methodological framing — important to preserve verbatim**. The claude arm's protocol is **AI-first + human review-and-adjudication**, NOT blind first pass (Sam saw the agent's call per record), NOT reconciliation-with-rubric-anchor (Sam reviewed all 100 records, not just disagreements between two prior coders). PR #110's `review_all.py` enforces this framing via a docstring test that fails if "blind first pass" appears outside negative framings. The verbatim methods-section sentence (lifted from Sam, 2026-06-07) lives at `results/rubric_inter_coder_analysis_claude.md`. Don't drift on this in the writeup.

**Why the protocol differed between arms (honest disclosure for the methods section)**. Primary used blind first pass + blind AI second-coder + reconciliation. Primary's first pass drifted off-rubric due to coder fatigue (2026-06-07 prior entry); reconciliation under fresh eyes produced 79/79 second-coder-adopted on contested records. The drift observation motivated the protocol change for claude — AI-first + human review-and-adjudication eliminates the fatigue vector (categorisation from memory under cognitive load) while preserving human final adjudication. The change is documented end-to-end via the per-record `review_action` audit field on the canonical sheet.

**Audit observation on claude's 100% acceptance rate** — could in principle signal reviewer over-acceptance under cognitive load on an AI-first walk where every suggestion is Cat 2 ("just `a` enter through"). Two pieces of evidence against that reading: (1) the agent's regex sweep for inversion-naming vocabulary (PR #111 body) found zero matches across all 100 reasoning texts, corroborating Cat 1 absence orthogonally; (2) the 6 borderlines the agent flagged each genuinely contain missing-evidence hedging (COI field absent etc.) which the rubric default rule unambiguously excludes from Cat 3. Orchestrator audited the 6 borderlines independently and concurs. The 100% acceptance is rubric-aligned.

**P5 verdict on both diagnostic arms: Confirmed.** Cross-model robustness with the cross-axis-coherent direction-of-effect (Opus more thorough inversion-blindness on both rubric axis and verdict axis) strengthens P5 evidence beyond what a single-arm replication would provide.

**What's next**: **Phase 2.5 is closed.** Phase 3 (analysis notebook + writeup) is the next phase. Methods section lifts the two verbatim protocol-disclosure sentences (one per arm) plus a sentence explaining why the protocols differ. Results section is anchored by per-arm verdict-axis distributions (Phase 2 receipts), per-arm rubric-axis distributions (the two canonical sheets), and the cross-model comparison on both axes. The methodologically meaningful arcs to surface in the methods note are catalogued in this log: record-composition fix (PR #97), rubric drift caught by κ check on primary (PR #109), AI-first protocol introduced for claude (PR #110 + this entry).

---

## 2026-06-07 — Phase 2.5 diagnostic_primary: drift, reconciliation, P5 Confirmed

**Decision**: first-pass coding of 100 `diagnostic_primary` reasoning texts (2026-05-29) yielded distribution 8/25/67 → Under-tested. Blind AI second-coder pass via PR #107 surfaced κ = −0.0369 against the first pass — concentrated at the missing-evidence/rule-itself rubric boundary (66 of 79 disagreements at Sam=3 / Agent=2). Sam's own characterisation: *"I misinterpreted the categories first pass and was fatigued."* Reconciled 2026-06-07 via PR #108's `review_disagreements` tool: on all 79 contested records, fresh-eyes Sam adopted the agent's call (0 `first-pass-kept`, 0 `override`). Reconciled sheet distribution: 7/93/0 → **Confirmed**. P5 verdict for `diagnostic_primary`: **Confirmed**.

**Process working as designed**. The κ check protocol was a coder-hygiene measure (single-coder is explicitly allowed by the locked rubric); the blind second-coder pass caught drift before the writeup committed to the wrong disposition. The reconciliation tool documents per-record `reconciliation_action` (`agreement-kept` / `first-pass-kept` / `second-coder-adopted` / `override`) plus `first_pass_category` and `second_coder_category` — the canonical sheet is auditable end-to-end.

**Methodological framing — important to preserve verbatim**. The reconciliation step is **reconciliation with rubric anchor**, NOT blind re-coding. The reviewer saw both the first-pass call AND the second-coder's call alongside the rubric's default rule. This mirrors formal multi-coder reconciliation protocols. PR #108's `review_disagreements.py` enforces this framing via a docstring test that fails if "blind re-coding" appears outside negative framings. Don't drift on this in the writeup.

The verbatim methods-section sentence (lifted from Sam, 2026-05-30) lives at `results/rubric_inter_coder_analysis_primary.md`. The writeup methods note should lift it directly without paraphrase.

**What's next**: `diagnostic_claude` (n=100) under the same protocol — first pass blind via `code_rubric.py`, then blind AI second-coder via fresh agent dispatch (same hard rails), then `score_rubric.py --compare-with` for κ, then `review_disagreements.py` for reconciliation IF disagreements warrant. The primary arm's 100% adoption of the agent's calls under fresh-eyes review is direction-of-signal that claude may follow a similar pattern — but a different model's reasoning produces a different disagreement structure regardless. The κ check is the empirical question.

**Post-Phase-2 cleanup todo** (still pending; folds into the docs-cleanup PR after Phase 3 starts): unchanged from the prior entry, plus a sentence in the smoke / dry-run brief recommending `python3 -u` when piping through `tee`.

---

## 2026-05-29 — Phase 2 complete: 1,332 receipts, all five gates PASS, $25.23

**Decision**: E3 Phase 2 fired and completed cleanly. Canonical run at `results/runs/phase-2-20260529T092611-Z` (committed to git in PR #104 alongside three SUPERSEDED- audit-trail runs from the abort-and-recover arc). All five operational gates passed; substantive verdict distributions across the locked corpus available for Phase 2.5 rubric coding and Phase 3 analysis.

**Wall-clock**: 09:26:18 → 10:46:51 UTC = **80 min 33 sec** (faster than the 90–110 min pre-fire estimate). Pacing held at 0.5s/call throughout; no 429 recovery events; no errors.

### Five-gate sign-off

| Gate | Result |
|---|---|
| Cost ±15% accuracy | **Within 0.4% on all six arms** (worst arm_a ratio 1.004; best arm_c ratio 1.000). Total actual $25.23 vs $25.21 projection — two cents off on a $25 run. Extrapolation as accurate as the underlying data permits. |
| Verifier integrity | **1,332 / 1,332 PASS, exit 0**. All Ed25519 signatures, all per-arm integrity markers, aggregate completeness — all pass. Kid `meshqu-experiment-procurement-2026-05` confirmed. |
| Unrecovered 429s | **Zero**. Pacing at 0.5s held both providers comfortably; no retry events visible in tick stream. |
| Orphan-recovery scan | **Empty** (`orphans: 0  recovered: 0  failed: 0`). Every server-side signed receipt matched a local bundle. |
| Observability captures | **run-start + run-end PNGs both present** under `observability/screenshots/`, matching E2's `full-run_<UTC-timestamp>_<dashboard>_<event>.png` filename pattern. Cross-trilogy artefact parity confirmed. PR #103's gap-fill verified working at scale. |

### Substantive verdict distributions

**Piece 1 — L3 decomposition (arms A/B/C, n=283 each)** — points to *"verdict exemplars load-bearing"* (the sharpest row of the design's 4-outcome interpretation table):

| | agent commits (ALLOW + DENY) | hedges to REVIEW |
|---|---:|---:|
| arm_a (precedents-only) | 44 (**15.5%**) | 239 (84.5%) |
| arm_b (precedents-no-verdict) | 9 (3.2%) | 274 (96.8%) |
| arm_c (density-control) | 13 (4.6%) | 270 (95.4%) |

Arm A commits ~3.4× more than Arms B/C; arms B and C are near-identical in commit rate. **Qualified by the documented Arm C asymmetric-control caveat** (-16.43% token parity from PR #93): a critic can argue *"Arm C didn't commit because it had less volume, not because verdicts/concreteness matter."* The writeup methods section needs to disclose this asymmetry; the verdict-exemplars-load-bearing reading cannot be presented as sharp on this evidence alone.

**Piece 2 — L4 decomposition (l4_without_nudge, n=283)** — direction-of-signal evidence that the nudge wasn't load-bearing:

| | count | % |
|---|---:|---:|
| agent commits (DENY) | 77 | **27.2%** |
| hedges to REVIEW | 206 | 72.8% |

l4_without_nudge commits MORE often than arm_a (27.2% vs 15.5%). The L3→L4 backoff E2 observed appears to have NOT re-emerged here without the nudge. **Final read requires the E2 L4-with-nudge baseline** from the published artefact at `procurement-context-gradient/` — the comparison answers Framing A.1 vs A.2 cleanly. This data is half the comparison; the other half is in E2's published corpus.

**Piece 3 — Inversion-blindness at scale (diagnostic_primary + diagnostic_claude, n=100 each)** — robust P5 verdict-axis evidence:

| arm | engine=ALLOW (52 records) | engine=DENY (48 records) |
|---|---|---|
| diagnostic_primary | REVIEW=52, ALLOW=0, DENY=0 | REVIEW=25, ALLOW=0, DENY=23 |
| diagnostic_claude | ALLOW=35, REVIEW=17, DENY=0 | DENY=44, REVIEW=3, ALLOW=1 |

Cross-model + cross-evaluator directional alignment at n=100:
- **Engine-ALLOW records**: 100% LLM-non-DENY (52/52 GPT-5.4, 52/52 Opus)
- **Engine-DENY records**: 99.0% LLM-non-ALLOW (GPT-5.4 0/48 ALLOW, Opus 1/48 ALLOW)

The dry-run's 10/10 finding holds at 10× scale. Single exception: one OCID where Opus said ALLOW but engine said DENY — worth examining as a worked-example outlier in the writeup. **Verdict-axis P5 evidence is now robust at scale.** Rubric-axis confirmation comes via Phase 2.5 hand-coding (200 reasoning texts × locked 3-category rubric).

**Cross-model verdict-style divergence — definitive at n=100**:

| arm | ALLOW | REVIEW | DENY | decisive rate |
|---|---:|---:|---:|---:|
| diagnostic_primary (GPT-5.4) | 0 | 77 | 23 | **23%** |
| diagnostic_claude (Opus 4.7) | 35 | 20 | 45 | **80%** |

Opus uses ALLOW/DENY 80% of the time; GPT-5.4 uses ALLOW/DENY 23%. The dry-run's n=10 finding (8/10 vs 2/10) now has 10× the evidence at n=100. Methods caveat empirically locked: verdict distributions and rubric distributions must be analysed independently for the cross-model arm; pooling would conflate model output-style preferences with substantive policy engagement. Belongs alongside the locked "no temperature on Opus 4.7" sampling caveat as documented cross-model arm disclosure.

### Process texture — three honest items for future-Sam

**(a) Buffering / `python -u` operational lesson.** First two Phase-2 fires from the orchestrator session appeared to "hang" after the urllib3 import warning — no banner, no ticks visible in `/tmp/phase-2-stdout.log` after 60–90 seconds. Halted both for investigation. The hang was 100% **stdout block-buffering when piped through `tee`**: Python's stdout buffers to 8KB when output goes to a pipe vs. line-buffering to a TTY. The dry-run's 9-minute, 140-tick run accumulated enough output to flush the buffer multiple times; Phase 2 at minute 1 hadn't. **Fix**: `python3 -u` forces unbuffered output regardless of pipe destination — used on the successful third fire. Worth a one-line docs-cleanup note in the smoke + dry-run + phase-2 invocation briefs: "when piping through `tee` for live monitoring, use `python3 -u` to defeat block-buffering."

**(b) Honest sunk-cost correction.** I told Sam *"zero spend on the aborts"* twice during the buffering investigation. Wrong twice. The two aborted Phase 2 fires actually signed **77 + 41 = 118 receipts** before halt — stdout buffering masked file I/O state from my log peeks, not just the tick output. Actual sunk cost on the aborts: ~118 receipts × ~$0.006 = **~$0.70 OpenAI**, $0 staging MeshQu (free), $0 Anthropic (both aborts halted within arm_a; no Claude calls fired). Small in absolute terms but: those receipts exist server-side in the staging tenant's signed-receipts log regardless of whether the orchestrator session noticed them. Committed as SUPERSEDED- runs in PR #104 to preserve the audit chain — anyone reading the kid + tenant log later can match each signed receipt to a committed bundle, including the aborted ones.

**(c) Readiness-item-14 caveat (PR #100 ↔ PR #103 ↔ PR #104).** The readiness checklist's item 14 ("Monitoring dashboards configured (reuse the Grafana captures from E2)") was marked PASS on availability grounds — the dashboards exist, per E2's setup. The user-caught gap (*"will the Grafana screen grabs work as exp 1 and 2 did?"*) revealed that PR #101's `--scale phase-2` extension hadn't inherited E2's `phase_2_live.py` observability wiring. PR #103 closed the gap; the Phase 2 fire that produced the canonical run had captured-at-runtime parity confirmed. **Item 14's claim is now strongly true** (dashboards configured AND captured at runtime), not just availability-inferred. The lesson for future readiness audits: "configured" and "captured at runtime" are separate claims; the readiness checklist should distinguish them at item-level granularity.

### Auto-mode classifier authorisation history (process texture)

For trilogy methods-note material: the orchestrator session's authorisation pattern for live calls evolved over E3-010, E3-011, and Phase 2.

- E3-010 (smoke) — Sam fired in own shell per the original "I hold the keys" rule
- E3-011 (dry-run) — Sam authorised orchestrator-fires; orchestrator fired in background; classifier denied initially but allowed after explicit grant
- Phase 2 — orchestrator fires (with explicit go) became the default after Sam asked *"in exp 1 and 2 the agent ran the experiment, why can't we do that?"* — surfacing that the "Sam fires" model was an inherited assumption rather than a structural constraint. Phase 2 authorisation stood through the OBS gap halt, the buffering halt, and the successful third fire.

The pattern: each step expanded the orchestrator's authorised action surface as the trust-and-tooling alignment proved out. Same shape as the classic CI/CD progression from "human presses deploy" → "human approves PR which deploys" → "tests pass which deploys." The chain-of-custody concern (receipts get signed under the experiment kid regardless of who triggered the python script) was the key methodological observation that unlocked the shift.

### What's next

**Phase 2.5** — 200 reasoning texts × locked 3-category rubric (100 from `diagnostic_primary` + 100 from `diagnostic_claude`). Run via PR #91's `code_rubric.py`. Estimated 3–4 hours of human-judgment work; can be one sitting or paced. Substrate for the rubric-axis P5 confirmation; the verdict-axis evidence (above) is already strong.

**Phase 3** — analysis notebook + writeup. The Methods section will lift: the record-composition fix arc (PR #97), the dispatch-architecture lesson (Wave 2 worktree isolation), the cross-model verdict-style divergence as documented disclosure, the Arm C asymmetric-control caveat, the OBS-gap halt-and-fix arc (PR #103), and the buffering / `python -u` operational lesson. The Results section is anchored by the verdict distributions above plus the rubric distributions from Phase 2.5.

**Phase 4** — methodology extraction to the trilogy capstone. Receipt-Anchored Evaluation as a discipline across three experiments. The cross-trilogy artefact parity (now confirmed via PR #103 + #104) is what makes this writeable as one coherent methods note rather than three separate ones.

### Post-Phase-2 cleanup todo (folds into the single docs-cleanup PR after Phase 3 starts)

Adds two items to the existing batch:

- `python3 -u` recommended invocation note in the smoke / dry-run / phase-2 briefs (the buffering lesson)
- Readiness-item-14 caveat addendum: claim was PASS-on-availability-grounds at PR #100 authoring time; strongly-true after PR #103 + #104 confirmed captured-at-runtime parity. Worth a one-line footnote in the readiness report so future readers see the lineage.

Plus the items from the earlier batch (stale docstring refs, `$RUN_DIR` UX trap, Py3.14 dataclass error in `test_claude_adapter.py`, conftest fixture pattern extension, driver rename if Sam wants it).

---

## 2026-05-28 — Phase 1 close-out: 12 build packages + the methodologically meaningful arcs

**Decision**: Phase 1 of the E3 (Experiment 3 — *Precedents, policy, and commitment*) build complete. Pre-Phase-2 readiness signed off at PR #100 (`9852c07`); driver-extension follow-up (`--scale phase-2` flag) at PR #101 (`3254cca`) is the final piece between readiness and Phase-2 launch. The runner now fires either the 140-receipt dry-run matrix or the 1,332-receipt full corpus matrix from the same driver, with scale-keyed summary artefacts and a parametrized matrix-shape lock-in test. Phase 2 is fireable from Sam's shell whenever his energy permits.

**Twelve build packages shipped in a single working session** (2026-05-28):

| Pkg | Title | PR | Merge SHA | Key outcome |
|---|---|---|---|---|
| E3-001 | Runner foundation | #85 | `e50030f` | Forked from E2; arm-keyed registry; receipt-payload extended with 7 E3-specific fields |
| E3-002 | Arm A — precedents-only | #92 | `1c6e1c2` | Byte-identical to E2's L3 renderer verified via cross-tree `importlib` fixture; anchored the `arms/<arm_name>.py` subpackage layout convergence |
| E3-003 | Arm B — precedents-no-verdict | #89 | `fc1387f` | Defence-in-depth field projection (whitelist before `str.format_map`); contamination check 0 verdict/violation/E1-reasoning substrings across N=3 × 4 precedents |
| E3-004 | Arm C — density-control | #93 | `e4f32c2` | Token parity -16.43% → accepted as asymmetric-control methods caveat per Decision Point #3 |
| E3-005 | L4-without-nudge | #90 | `e09f82a` | HTML-comment-strip convention at renderer layer (Sam's resolution); post-strip diff = exactly the nudge sentence |
| E3-006 | Claude cross-model swap | #88 | `d484892` | `ClaudeAgent` wrapper bridging `dict ↔ Agent` protocol; pin `claude-opus-4-7`, no `temperature`, `effort: "low"` |
| E3-007 | Diagnostic subset selector | #87 | `2ce306e` | Deterministic `sha256(ocid)` sort; 100 OCIDs locked to v0.3 tag |
| E3-008 | Scaled Permuted-Policy diagnostic | #95 | `9e5bc65` | `diagnostic_primary` + `diagnostic_claude` arms (initially envelope-only — see PR #97 for the fix) |
| E3-009 | Rubric-coding tool | #91 | `a40371e` | Offline CLI walker at `diagnostic/code_rubric.py`; P5 bands parsed from `predictions.md` at runtime |
| E3-010 | Smoke + verifier | #96 | `600d2ac` | 14-receipt smoke; Ed25519 + integrity-marker verification; live MeshQu wiring (additive at driver layer) |
| E3-011 | Dry-run + verifier + orphan shim | #99 | `7c222cd` | 140-receipt dry-run scripts; smoke→dry-run ±15% accuracy check; orphan-recovery CLI shim |
| E3-012 | Pre-Phase-2 readiness checklist | #100 | `9852c07` | 15 PASS / 1 FLAGGED / 0 FAIL → READY FOR PHASE 2 |

Plus: **PR #97** (`0c4ce13`) — the bug-discovery + lock-in-test fix arc (record-composition; see prior entry for full detail). **PR #101** (`3254cca`) — driver extension for `--scale phase-2`; the formally-recorded "one piece of build still due between Phase 1 readiness and Phase 2 launch" (filed AFTER the readiness checklist signed off, on purpose; the readiness applied to the corpus-collection infrastructure, the extension is its scale-aware invocation).

### The two methodologically meaningful arcs

**Arc 1 — Wave-2 dispatch-architecture failure → per-agent worktree isolation.** First Wave 2 dispatch had 7 background agents working in a single shared working directory at `/Users/sam/Projects/meshqu-research`. The agents raced on git state, switched branches mid-work, contaminated each other's untracked files. One errored at the end; five were stopped before push; only E3-007 committed cleanly and was salvaged (PR #87). **Resolution**: redispatch with `git worktree add /private/tmp/wt-e3-XXX -b feat/e3-XXX main` per agent — physical isolation prevents cross-agent racing. Six redispatched agents landed cleanly with that discipline. The dispatch-architecture lesson now carries forward as the new primitive for any parallel-dispatch wave.

**Arc 2 — Record-composition bug caught at decision-point #5; lock-in test now a wave-1 expectation.** The first smoke verified cryptographically clean (14/14) but produced "no procurement record provided" refusals across all six arms. Substantive read on the Claude diagnostic verdict shape (DP#5 v1) surfaced a cross-arm pattern. Root cause: three handlers (`l4_without_nudge`, `diagnostic_primary`, `diagnostic_claude`) returned envelope-only; smoke driver fabricated empty-fields records, hiding the handler bug. PR #97 — three commits: test-first lock-in (3 PASS / 3 FAIL pre-fix, locked-in evidence), handler-and-driver fix (6 PASS), `l4_with_nudge` fold-in (7 PASS). Smoke v2 read clean across all six arms; DP#5 v2 captured Opus's worked-example quote ("Open-competition rule does not trigger below threshold" under permuted policy) — locked rubric category 2 ("reasons solely against rule intent") confirmed direction-of-signal at n=1. **Method-note carry-forward**: every arm-handler PR must include the parametrized "record A and record B render to distinct prompts containing their respective markers" assertion at the wave-1 expectation level. The discipline is now in the codebase as `tests/test_handler_record_composition.py` parametrized across 7 arms — including `l4_with_nudge` (off the smoke/dry-run/full-run matrices but registered, held to the same composition contract per Sam's call).

### The verdict-axis inversion-blindness finding (dry-run, 2026-05-28)

10/10 cross-model + cross-evaluator directional verdict alignment under the permuted policy:
- 4 records where the MeshQu engine reaches ALLOW: both LLM diagnostic arms reach ALLOW or REVIEW (never DENY)
- 6 records where the engine reaches DENY: both reach DENY or REVIEW (never ALLOW)

This is **P5 evidence at the verdict-axis** complementary to the locked rubric-axis (category 2 reasoning) evidence — and methodologically stronger than expected at n=10. The MeshQu engine isn't checking semantics; it's mechanically applying the rules as-stated. The LLMs aren't checking either. They're both inversion-blind in the same direction. **Worked-example anchor for the writeup**: "the cross-model + cross-evaluator alignment on directional verdict tells you the inversion-blindness pattern isn't model-personality dependent — it's a property of how the prompt is being read across capable models AND mechanical evaluators." (Lifted verbatim from Sam's 2026-05-28 read.) N=10 is direction-of-signal; the locked rubric across n=100 in Phase 2/2.5 is what confirms or falsifies P5.

### Cross-model verdict-style divergence — empirically grounded at n=10

The DP#5 v2 finding (Opus compact-decisive vs GPT-5.4 hedging-toward-REVIEW) reproduces at n=10: Opus is decisive on 8/10 diagnostic records (2 ALLOW + 6 DENY + 2 REVIEW); GPT-5.4 is REVIEW-heavy on 8/10 (2 DENY + 8 REVIEW). Same prompts, same records, same model-keyed personality split. Methods-section caveat empirically grounded: **verdict distributions and rubric distributions must be analysed independently in the writeup, not pooled across the cross-model arm**. Belongs alongside the "no temperature on Opus 4.7" sampling caveat as documented cross-model arm disclosure.

### Process texture worth recording for future-Sam

Two procedural items worth a sentence each:

**(a)** **The auto-mode classifier denied re-firing the offline verifier** during E3-012's read-only audit — the agent's substitution was a **direct marker-matrix scan + signature kid check** across all 154 live bundles' canonical-JSON payloads. This is at least equivalent to running the verifier and arguably stronger: it inspects the bytes that get hashed and signed, bypassing any parser-layer risk. Combined with the kid-locked signature check (which got verified separately), the two layers together cover what the verifier would have done. Sam's read: methodologically interesting process texture; future-Sam-reading-the-log understands what happened.

**(b)** **PR #101 (driver extension) is the formally-recorded "one piece of build still due between Phase 1 readiness and Phase 2 launch"** — not a Phase-1-incomplete signal. The readiness checklist (PR #100) applied to the corpus-collection infrastructure (handlers, signing, verifier, lock-in tests, cost projection). The extension parameterizes the dry-run driver with a `--scale phase-2` flag so the same driver fires either the dry-run (140 receipts) or the Phase-2 full corpus (1,332 receipts). Filed AFTER readiness on purpose; the discipline distinction is "ready" (infrastructure) vs "fire" (invocation). The `dry_run_e3.py` filename is deliberately NOT renamed despite being slightly misleading for Phase 2; honest naming would require chasing imports across tests + docs + decision_log references — deferred to docs-cleanup batch per "do not endlessly edit."

### Cost projection — **no credit top-up required**

Phase 2 projected at **$25.21 base** + buffer (re-runs / orphans / one accidental re-fire) = **realistic ceiling ~$30–40**. Conservative pre-flight estimate ($50–130) hedged against unknown per-call overhead + worst-case prompt-token assumptions; the dry-run nailed the actual rates across all six arms (smoke→dry-run accuracy within 1.2% — extrapolation is exact at this scale). Most of the cost is Claude diagnostic ($13.31 single biggest line item); main grid totals ~$10.60. **Phase 2 fires on current credit; no top-up needed.**

### What's next

Phase 2 fires from Sam's shell at his energy moment of choice — tonight, tomorrow morning, whenever. Same operational pattern as smoke + dry-run (chain-of-custody preserved through Sam's authenticated environment; brief is verbatim-fireable from the orchestrator's drafted form). After Phase 2 returns clean, Phase 2.5 = the 100 × 2 = 200 reasoning-text hand-codings against the locked rubric (PR #91's `code_rubric.py`). Phase 3 = analysis notebook + writeup. Phase 4 = methodology extraction to the trilogy capstone.

**Post-Phase-1 cleanup todo** (single docs-cleanup PR after Phase 2 returns):
- Stale docstring references to the deleted E2 `diagnostic/runner.py` in `scaled.py` / `level_l4_permuted.py` / `run_scaled_diagnostic.py` / `select_dry_run_records.py` / `validate_smoke_run.py`
- Smoke / dry-run driver `$RUN_DIR` UX trap (banner doesn't auto-export the run dir as a shell var for the verifier-call convenience)
- Py3.14 dataclass error in `test_claude_adapter.py`
- Extend `tests/conftest.py` autouse fixture pattern (from PR #101) to `test_precedent_selector.py` + `test_diagnostic_subset.py` — the longest-standing environmental fragility in the runner, with a worked-example fix shape now in-codebase
- Driver rename (`dry_run_e3.py` → `run_e3.py` or `run_corpus.py`) if Sam wants the honest filename later
- Honest summary filename for Phase 2 already handled in PR #101 (`phase-2-summary.md` per scale)

---

## 2026-05-28 — Smoke read v2 + handler record-composition fix (PR #97, merge `0c4ce13`)

**Decision**: smoke v1 (run `smoke-20260528T152346-Z`) passed cryptographic verification cleanly (14/14, Ed25519 + integrity markers all correct) but the substantive experimental signal was empty — every arm returned a "no procurement record provided" refusal. Decision-point #5 read on the diagnostic shapes surfaced a cross-arm pattern, root-caused to a bug not in the diagnostic alone but in three arm handlers plus the smoke driver. Fixed in PR #97 (`0c4ce13`); smoke re-fired (`smoke-20260528T161121-Z`) reads clean across all six arms.

**The bug cluster** (one root cause + a triggering condition):

| # | Location | Behaviour |
|---|---|---|
| A | `arms/l4_without_nudge.py:l4_without_nudge_handler` | Returned only the L4 envelope; `record` arg ignored |
| A′ | `arms/l4_without_nudge.py:l4_with_nudge_handler` | Same shape (sanity-comparison baseline; off-grid, in-runner only — folded into the fix per Sam's 2026-05-28 call to hold every registered arm to the composition contract regardless of grid status) |
| B | `arms/diagnostic.py:diagnostic_primary_handler` + `diagnostic_claude_handler` | Returned only the permuted L4 envelope; `record` arg ignored. Module docstring falsely claimed `multi_pass._process_record` composes the base user message — `multi_pass.py:588-592` explicitly says the opposite ("Arm handler returns the FULLY rendered user message — no additive composition, no level prefix. The handler is self-contained.") |
| C | `scripts/smoke_e3.py:_build_records` | Intentionally fabricated minimal-shape records with `fields={}` and `substrate_notes={}`, on the assumption that "smoke is an integration probe, not a substrate test." This *hid* bugs A+B — every arm was receiving empty records anyway, so the missing-record-composition didn't surface visibly; the smoke completed and verified, leaving the substantive engagement question untested. |

**Empirical confirmation** (lifted from PR #97):

| Arm | Record A (marker ALPHA-12345) | Record B (marker BRAVO-67890) | Prompt-SHA distinct? | Markers in prompt? |
|---|---|---|---|---|
| arm_a / arm_b / arm_c | distinct | distinct | ✓ | ✓ |
| l4_without_nudge | identical | identical | ✗ | ✗ |
| diagnostic_primary / diagnostic_claude | identical | identical | ✗ | ✗ |

**The fix** (PR #97, three commits):

1. `0854787` — Test-first: `tests/test_handler_record_composition.py` parametrized across the 6 grid arms. Pre-fix: 3 PASS (arm_a/b/c), 3 FAIL (l4_without_nudge + both diagnostics). Locked-in evidence.
2. `5e5f913` — Compose `base_user_message` at the tail of the rendered envelope in `arms/diagnostic.py` (both handlers via shared `_compose_base_user_message` helper) and `arms/l4_without_nudge.py:l4_without_nudge_handler`. Envelope-first / record-trailing order mirrors E2's `level_l4.compose_full_message` — load-bearing for OpenAI prompt-cache prefix preservation. Smoke driver swapped to `substrate_cache.load_cached_records(repo_dir)` filtered to the smoke OCIDs.
3. `70c40bf` — Extended `l4_with_nudge_handler` with the identical compose pattern; lock-in test parametrize extended from 6 to 7 arms (`l4_with_nudge` included despite being off the smoke / dry-run / full-run matrices — the discipline is "every registered arm that touches Phase-1 experimental substance," not "every arm on the current grid"). Post-fix: 7/7 PASS.

**Method-note carry-forward**: every arm-handler PR going forward MUST include a parametrized "record A and record B render to distinct prompts containing their respective markers" assertion at the wave-1 expectation level. This locks the property; a future agent "simplifying" the renderer back to envelope-only trips the test. Worth a sentence in the eventual receipt-anchored-evaluation methods note — "lock-in tests on per-record prompt distinctness" is a small but real piece of the discipline.

**Smoke v2 — decision-point #5 read (the load-bearing finding)**

Re-fired smoke `smoke-20260528T161121-Z` against the real substrate (3 OCIDs × 4 main arms + 2 diagnostic arms = 14 receipts; 51.4s wall-clock; 14/14 verifier PASS; no errors).

All six arms now substantively engage with the OCID 0 record (`contract_value: 40000.0`, `supplier_id: GB-CFS-321175`, `publication_delay_days: 29`, `governed_by_pa23: true`, `above_threshold: false`). Per-arm prompt-token growth confirms record content reaching the model (arm_a +38%, l4_without_nudge +26%, diagnostic_primary +26%, diagnostic_claude +28% vs the pre-fix smoke).

**The Claude verdict-shape question (DP#5 the load-bearing item)**:

| Axis | Result |
|---|---|
| JSON parsing | Clean. `parse_status: ok` on both diagnostic bundles. No fence wrapping. Spike's claim holds at real-corpus scale. |
| Field shape | `verdict` / `reasoning` / `recommended_action` — same three-field shape as the primary agent. |
| Inversion-blindness signal at n=1 | **Both models inversion-blind on OCID 0.** Neither names the inversion; both apply the policy as-stated. Locked rubric category 2 ("reasons solely against rule intent") on this record, both arms. |

**Worked-example anchor (the smoking quote)**: under the permuted policy (LOCKED_PERMUTATION_SEED=0, operators flipped), Opus 4.7 wrote:

> *"Below-threshold (£40k) PA23 contract, not a modification, supplier not on listed sanctions IDs, publication within 29 days. Open-competition rule does not trigger below threshold. COI field absent from substrate but rule's when-clause requires its existence to fire."*

This is the **unperturbed** semantic interpretation of the rules. Under the permuted policy, "below threshold" should TRIGGER the (inverted) authority/open-competition rule. Opus reads the permuted policy text, then applies the rule's *intent* — exactly category 2 in the locked rubric. This is the inversion-blindness behaviour P5 predicts, captured on first contact with a real corpus record. (n=1 is direction-of-signal only; P5 confirmation/falsification requires the locked rubric across n=100 in Phase 2.)

GPT-5.4's `diagnostic_primary` reasoning shows the same applies-as-stated pattern with hedging language; verdict-axis style differs (REVIEW vs Opus's decisive ALLOW), reasoning-axis behaviour is identical.

**Methodological caveat for the writeup (track separately)**: Opus's compact-decisive vs GPT-5.4's hedging-toward-REVIEW on identical inputs is a real per-model behavioural axis. Verdict distributions will diverge between the two diagnostic arms even when rubric distributions agree. Belongs in the Methods section alongside the "no temperature on Opus 4.7" sampling caveat — same input class, different output style. Analysis notebook should track verdict distributions and rubric distributions independently; don't try to flatten them.

**Other smoke v2 observations** (not load-bearing but worth recording):

- All six arms got `meshqu_decision: ALLOW` with `violations_count: 0` on OCID 0 — with real fields the FIELD_MISSING violations from smoke v1 are gone. (Some records in dry-run / Phase 2 will trigger violations under their fields' actual values — expected; not a bug.)
- The three L3 decomposition arms (Arm A / B / C) all produced REVIEW with similar "audit trail incomplete / direct-award justification low-confidence" reasoning at n=1 — expected, the L3 decomposition signal needs the n=283 distribution to read.
- L4-without-nudge reasoning explicitly walked each rule (threshold, sanctions, publication delay, COI) — confirms the handler is now actually testing Framing A.1 vs A.2.

**What's next**: Wave 5 — E3-011 (dry-run, 140 receipts) dispatched as the next agent. Scripts mock-tested in PR; Sam fires the live dry-run after merge. Cost projection sanity-check (±15% of smoke extrapolation). Receipt-orphan recovery is already in the fork at `meshqu_runner/recover_orphans.py` (with `tests/test_recover_orphans.py`); E3-011 added `scripts/recover_orphans.py` as a thin CLI shim so the spec's literal invocation form works. **Not a Phase-2 blocker.** (An earlier note in the build-package brief flagged the script as missing — that was based on a `scripts/` directory grep; the module-form recovery was always present. Corrected here.)

---

## 2026-05-28 — Wave 2 close-out: arm handlers, Claude swap, rubric tool

**Decision**: six Wave 2 PRs merged. Runner now has working arm handlers for the three L3 decomposition arms (Arm A precedents-only, Arm B precedents-no-verdict, Arm C density-control), the L4-without-nudge surgical variant, the Claude cross-model adapter, and the offline rubric-coding tool. Layout convergence on `meshqu_runner/arms/<arm_name>.py` subpackage with imports landing in `arms/__init__.py`.

**Merged PRs (in merge order)**:

| PR | Merge SHA | Package | Notes |
|---|---|---|---|
| #88 | `d484892` | E3-006 Claude cross-model swap | Anthropic SDK adapter at `agents/claude.py`; model-id-keyed `DISPATCH`; receipt schema extended in place (no envelope v2 bump). Pin: `claude-opus-4-7`, no `temperature`, `effort: "low"`. System prompt SHA `db60d6f2…` unchanged. |
| #91 | `a40371e` | E3-009 rubric-coding tool | Offline CLI walker at `diagnostic/code_rubric.py`. `diagnostic_rubric.md` SHA `f162953e…` unchanged. P5 bands parsed from `predictions.md` at runtime, not hard-coded. |
| #92 | `1c6e1c2` | E3-002 Arm A — precedents-only | **Anchor PR for the layout convergence**: refactored foundation's `arms.py` → `arms/__init__.py` package. Byte-identity invariant verified against E2's `L3LiveHandler` on 3 smoke records via cross-tree `importlib`-loaded fixture. |
| #89 | `fc1387f` | E3-003 Arm B — precedents-no-verdict | HTML-comment-strip applied at renderer. Contamination check empirically passes: 0 verdict/violation/E1-reasoning substrings across N=3 × 4 precedents = 12 precedent renders. Defence-in-depth field projection (whitelist before `str.format_map`). |
| #93 | `e4f32c2` | E3-004 Arm C — density-control + token parity | **Asymmetric-control caveat resolved** (see below). HTML-comment-strip applied. Locked SHA `07abb32f…` unchanged. |
| #90 | `e09f82a` | E3-005 L4-without-nudge | `strip_leading_html_comments` utility at `prompt_loader.py` (renderer layer). Post-strip diff against E2's `L4_policy_envelope.md` = exactly the nudge sentence and nothing else. Both `l4_with_nudge` (sanity baseline) and `l4_without_nudge` (load-bearing) registered from the same module. |

**Process lessons captured (load-bearing for future waves)**:

1. **Dispatch-architecture failure → per-agent git worktree isolation.** First Wave 2 dispatch had all 7 background agents working in a single shared working directory at `/Users/sam/Projects/meshqu-research`. The agents raced on git state, switched branches mid-work, and contaminated each other's untracked files (E3-009 found "orphan `test_arm_b.py` from a stash" leaked from E3-003; E3-006 misread cross-agent contention as a "system reminder" about a pinned file). One agent (E3-002) errored out at the end; five were stopped before push. Only E3-007 committed cleanly and was salvaged (became PR #87). **Resolution**: redispatch with `git worktree add /private/tmp/wt-e3-XXX -b feat/e3-XXX main` per agent — physical isolation prevents cross-agent racing on working tree state. Every parallel-dispatch wave from here on uses isolated worktrees, no exceptions. This is the dispatch-architecture lesson — bake it into Wave 3+ orchestration.

2. **Layout convergence on `arms/<arm_name>.py` subpackage.** Six redispatched agents independently picked three different layout patterns (flat `arm_b.py`, sibling `arm_handlers/`, subpackage `arms/`). Anchor decision: **PR #92's `arms/__init__.py` subpackage is canonical.** The other three arm-handler PRs (#89 Arm B, #93 Arm C, #90 L4) rebased and `git mv`-ed into `arms/`, deleting the divergent locations. Convention now: each new arm lands as `meshqu_runner/arms/<arm_name>.py` and is imported at the bottom of `arms/__init__.py` with the idiom `from . import <arm_name> as _<arm_name>  # noqa: F401, E402  (<description> — E3-XXX)`. Wave 3+ agents follow this without question.

3. **HTML-comment-strip convention** for locked-content files. **E3-005's discovery**: the locked `L4_without_nudge.md` (v0.3-bound) starts with an HTML comment header that quotes the nudge sentence verbatim. From the LLM's perspective, the "excised" text was still in the prompt (inside `<!-- ... -->`). **Sam's resolution (2026-05-28)**: strip leading HTML comments at the renderer layer before sending to the LLM. Locked file bytes (and SHA) stay untouched on disk. `_strip_leading_html_comments` lives at `meshqu_runner/prompt_loader.py` so any arm with a leading methodological comment in its locked content can reuse it (Arm B did, in PR #89). Convention: leading HTML comments in locked prompt files are documentation; the renderer strips them; on-disk file is the v0.3-bound source of truth; the LLM sees the stripped form.

4. **`test_arm_registry.py` `placeholder_arms` tuple-exclusion idiom is canonical.** Three rebase agents independently picked three different shapes (`promoted_arms` set / `ARMS_WITH_REAL_HANDLER` set / extended `placeholder_arms` tuple). Convergence (merge order #89 → #93 → #90): `placeholder_arms = tuple(arm for arm in ARM_NAMES if arm not in ("arm_a", "arm_b", "arm_c", "l4_with_nudge", "l4_without_nudge"))`. Variable name is somewhat misleading (it actually means "arms whose handler is still a placeholder"); current shape preserved for stability rather than renaming.

**Decision Point #3 resolved — Arm C asymmetric-control caveat (PR #93)**

Realised token-count parity vs E2's L3 payload (n=10 records): **mean ratio 0.8357 (-16.43%)**, range 0.8089–0.8572. Below both the design's ±5% band and the orchestrator's ±10% buffer; below the spec's "wildly off (< 0.85)" threshold by a hair. Locked Arm C content (`armC_density_control.md`, SHA `07abb32f…c1824134`) **NOT modified**.

**Verdict**: accept as documented methods caveat. Do NOT retag. Pre-registration commitment (`v0.3-predictions-locked`) unchanged.

**Asymmetric-control disclosure language** (lifted from PR #93 body, for the writeup methods section):

The gap rules out *one* family of confounds and introduces *another*:

| Confound | Direction of Arm C gap | Status |
|---|---|---|
| "Arm C shouted louder than precedents" (excess volume drove commitment) | Arm C is **shorter** than Arm A | ✓ Precluded |
| "Arm C didn't have enough volume to commit" (insufficient volume left a confound) | Arm C is **shorter** than Arm A | ✗ Introduced, not precluded |

How this constrains the four-outcome interpretation table at results-time:

- **A commits, B doesn't, C doesn't → verdict exemplars load-bearing.** *Sharpest result.* **Qualified**: with Arm C ~16% short, a critic can argue "Arm C didn't commit because it had less volume, not because verdicts/concreteness matter." Disclosure required at results-time; the claim cannot be presented as sharp on this evidence alone.
- **A commits, B commits, C doesn't → concreteness matters.** Same critic, same gap. Qualified.
- **All three commit → volume drives it (Reading B / deflationary).** The gap actually *strengthens* this claim — even less-volume Arm C triggered commitment, so volume-or-less is sufficient.
- **Only C fails to match** — collapses to one of the above.

**Why not commission a v0.3.1 post-tag top-up**: retagging an authored amendment for an integrity issue surfaced during build, before any corpus run has been read, would set a precedent that any pre-registration imperfection warrants a retag. That cost the integrity narrative of the methodology more than disclosure does. A documented caveat is the honest path; the asymmetry is real and we say so.

**Receipt schema impact resolved (PR #88)**: extend in place. Bundle envelope rule (verified at `multi_pass.py:91` showing `BUNDLE_ENVELOPE_VERSION = 1`) does NOT force a v2 bump for cross-model metadata addition. E3-001's additive integrity-payload pattern accommodates `model_id` + `model_sampling` values (`claude-opus-4-7`, `{"temperature": None, "effort": "low"}`) for the Claude arm without schema mutation.

**Post-Wave-2 cleanups filed (non-blocking, not Wave-2 scope)**:

1. **`prompt_loader.py` vs `arm_b.py` strip duplication** — PR #89 (Arm B) landed before #90's `prompt_loader.py` strip utility existed; arm_b's renderer may carry its own ad-hoc strip implementation. Worth a quick refactor to use the centralised utility if it does.
2. **Py3.14 dataclass error in `test_claude_adapter.py`** — pre-existing on main since #88 merged. Mutable-default-collection issue (observed by both the #93 and #89 rebase agents during full-suite sweeps). Small fix; doesn't block Wave 3 (the test passes on the Python version the agents ran in).
3. **8 `test_precedent_selector.py` archive-dependent failures** — depend on a `procurement-decisions/results/runs/dry-run-7ddf7274-…` directory that isn't in git. Replace with synthetic fixture or `skipif`. Doesn't block Wave 3.

**Three downstream contracts the next package (E3-008) inherits from Wave 2**:

1. **Claude adapter contract** (from PR #88): `agents/claude.py:call()` returns a dict, NOT an `AgentResponse`. E3-008 either wraps it in a `ClaudeAgent` class implementing the existing `Agent` protocol, or routes the diagnostic_claude arm via a dict-consuming orchestration path. Adapter contract is the dict shape; runner-protocol wrapping is E3-008's call.
2. **Inverted-operator-spec sibling artifact** (from PR #91): the rubric-coding tool requires E3-008 to emit `<run_dir>/diagnostic/inverted_operator_spec.json` alongside the diagnostic bundles. Shape is documented in `meshqu_runner/diagnostic/rubric_io.py:load_inverted_specs`'s docstring (the rubric tool reads it from there).
3. **Subset selector contract** (from PR #87 / E3-007): E3-008 reads OCIDs from `planning/diagnostic_subset.json`, does NOT regenerate. The selector module exists at `meshqu_runner/diagnostic/subset_selector.py` for re-verification, but the runtime read is from the committed JSON file (so a corpus enumeration anywhere in the codebase doesn't accidentally produce a different subset).

**What's next**: Wave 3 — E3-008 (scaled Permuted-Policy diagnostic, primary + Claude on the locked n=100 subset). **Blocked on PR #87 (E3-007 subset selector) merging into main** — E3-008 reads `planning/diagnostic_subset.json` which lives in PR #87. Once PR #87 merges, dispatch E3-008 in its own isolated worktree per the dispatch-architecture lesson above.

---

## 2026-05-28 — E3-006 — Claude cross-model swap (Anthropic SDK adapter)

**Decision**: added the second-model adapter at `meshqu_runner/agents/claude.py` plus a model-id-keyed `DISPATCH` table at `meshqu_runner/agents/__init__.py`. The cross-model diagnostic arm now has a real SDK adapter behind it. Primary-path callers are unaffected — `Agent.evaluate(...)` is untouched, the runner's existing `run_arm` orchestration still drives it directly.

**SDK call shape** (locked by `v0.3-predictions-locked`):
- `model="claude-opus-4-7"`
- NO `temperature` kwarg (Opus 4.7 removed it; sending it returns HTTP 400 — feasibility-spike headline finding)
- `output_config={"effort": "low"}`
- `max_tokens=1024`
- `system=<verbatim E2 system_prompt.md>` (SHA `db60d6f297b0a97ab43988bdd8163a49c6e050afb81ff7379c8a1ff4fd932aa2` before + after this change)

**Schema-impact decision (decision-point in the package spec)**: extend in place. The Claude arm's new receipt fields (`model_id`, `model_sampling`) were already added additively to `context.fields` by E3-001's foundation. The runner's bundle envelope v1 (`BUNDLE_ENVELOPE_VERSION = 1`) is preserved — every added field is additive, no existing field's semantics shift. The pre-existing `BUNDLE_ENVELOPE_VERSION` constant was inspected; no contract forces a v2 bump for the cross-model arm. Per the package spec's default recommendation, this is metadata addition, not a semantic shift.

**Fence-strip shim**: lifted verbatim from `runner/spike/claude_spike.py` into `parse_verdict_json`. Opus parses clean (no fence — spike confirmed); the shim is a defensive no-op on Opus's output that would only matter under a future Sonnet fallback. Keeping it now avoids a code change later if the pin is ever revisited via a tag amendment.

**Exception handling**: SDK typed errors (`NotFoundError`, `AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, `APIError`) are wrapped into a single `ClaudeAdapterError` with a classified `kind` (`not_found`, `auth`, `permission`, `bad_request`, `api`). Mirrors `meshqu_runner.agent.AgentCallError`'s shape so the eval loop's catch + log path stays uniform across the two adapters.

**Receipt integrity payload — Claude arm sets**:
- `model_id: "claude-opus-4-7"`
- `model_sampling: {"temperature": None, "effort": "low"}` (from `CLAUDE_MODEL_SAMPLING` in `arms.py`)
- `diagnostic: True`
- `policy_permutation_seed: <int>` (required for diagnostic arms — `inject_arm_fields` enforces)
- `runner_git_commit`, `prereg_tag` per E3-001 foundation

**Tests**: 24 mock-based tests in `tests/test_claude_adapter.py`. All pass (`pytest -v` → 24 passed). No live API calls. Coverage includes: SDK call shape (no temperature, effort low, max tokens, verbatim system), verdict-JSON parsing (clean + fenced + bare-backticks + invalid + non-object), out-of-vocab verdict normalisation, uppercase normalisation, typed exception wrapping for all five Anthropic error classes, `make_client()` env-var precondition, DISPATCH table wiring, stub-signer receipt payload assertions.

**Out of scope (not touched)**: substrate adapter, substrate cache, precedent selector, precedent archive, agent prompt scaffold, meshqu client, `system_prompt.md`, the spike directory, `agent.py` (primary OpenAI Agent), `arms.py` (foundation laid the model_id + model_sampling fields already), `multi_pass.py`.

**Stop conditions**: none fired. Anthropic SDK version installed (0.104.1) accepts `output_config` as a top-level kwarg on `messages.create`. The spike's verdict-JSON parse behaviour translated cleanly. The "Locked parameters → Second model" pin matched the spike report verbatim.

**Decisions / surprises future agents need to know (E3-008 runs the diagnostic on this arm)**:
1. The adapter's `call()` returns a dict, not an `AgentResponse`. The `run_arm` orchestrator still expects an object with `.evaluate(user_message) -> AgentResponse`. E3-008's diagnostic runner will need either to (a) wrap `call()` in a small `ClaudeAgent` class with the `Agent` protocol, or (b) take a different orchestration path that consumes the dict. Either is fine — the adapter's contract is the spec-defined dict shape, the runner-protocol wrapping is an E3-008 concern.
2. Anthropic's typed exception classes require a real `httpx.Response` in their constructor (they call `response.request` in `__init__`). Tests construct a minimal `httpx.Response(status_code=400, request=httpx.Request("POST", url))`. If E3-008 needs additional exception scenarios, follow the same pattern.
3. `output_config` is on the installed SDK (verified at 0.104.1) — no beta header needed. If a future bump moves it under a beta namespace, the adapter will need a small update; current code path is GA-stable.

**What's next**: E3-008 (scaled diagnostic) can now consume the Claude adapter once E3-007 (subset selector) also lands. Smoke (E3-010) is the first time the cross-model arm runs against a real corpus record — surface any verdict-shape surprises there per master plan decision-point 5.

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
