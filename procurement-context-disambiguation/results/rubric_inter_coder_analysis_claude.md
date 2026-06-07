# E3 diagnostic_claude — AI-first review-and-adjudication analysis (n=100)

**Dates**
- Blind AI agent coded: 2026-06-07 (PR #111)
- AI-first human review-and-adjudication: 2026-06-07 (this PR)

**Coders**
- Blind first coder: Claude Opus 4.7 dispatched as fresh agent with strict file allowlist — saw only the locked rubric, the 100 reasoning texts, the inverted-operator spec sidecar; did NOT see the primary arm's coding sheets, primary's analytical artefact, the pre-registered P5 bands, the decision_log, the experiment design, the `review_all.py` or `review_disagreements.py` source (which contain protocol-framing language), or Phase 2 verdict distributions
- Reviewer (final adjudicator): Sam, walking all 100 records via `review_all.py` with agent's call + agent's justification + reasoning text + inverted-operator spec + rubric category refresher + default-rule sentence visible per record

## Methods-section disclosure language (verbatim from Sam, 2026-06-07)

> "diagnostic_primary was coded via blind human first pass + blind AI second-coder + reconciliation; diagnostic_claude was coded via AI-first + human review-and-adjudication of all 100 records with rubric visible. The protocol change for claude was made in response to a methodological observation surfaced during primary's reconciliation (see decision_log entry 2026-06-07)."

The writeup methods section MUST lift this paragraph verbatim. The protocol is **AI-first + human review-and-adjudication**, NOT blind first pass, NOT reconciliation-with-rubric-anchor. Both characterisations would mis-describe what happened.

## Per-coder category distributions

| Coder | Cat 1 (names) | Cat 2 (intent) | Cat 3 (partial) | P5 disposition |
|---|---:|---:|---:|---|
| Claude Opus — blind first-pass agent | 0 (0.0%) | 100 (100.0%) | 0 (0.0%) | Confirmed |
| Sam — AI-first reviewed (canonical) | 0 (0.0%) | 100 (100.0%) | 0 (0.0%) | **Confirmed** |

P5 verdict reported in the writeup for `diagnostic_claude`: **Confirmed** (Cat 2 = 100%, Cat 1 = 0%, satisfying both Confirmed thresholds with margin).

The canonical analytical sheet is `rubric_coding_claude.jsonl`. The blind agent's sheet (`rubric_coding_claude_blind_agent.jsonl`) is preserved as the AI-first anchor input, already on main from PR #111.

## Inter-coder agreement (Cohen's κ)

| Comparison | κ | Landis-Koch |
|---|---:|---|
| Blind agent ↔ final (this arm) | **+1.0000** | Almost perfect |

The reviewer accepted the agent's call on all 100 records; the final sheet is byte-equivalent in category assignments to the blind agent's pass.

## Review action breakdown

The AI-first protocol's 2-value `review_action` enum captures what the reviewer did per record:

| Action | Count | What it means |
|---|---:|---|
| `agent-accepted` | **100** | Reviewer accepted the blind agent's call after re-reading reasoning + spec + rubric refresher + default-rule sentence |
| `human-overridden` | 0 | Reviewer did not override any agent call |

## The 6 borderlines flagged by the agent

The blind-coder agent flagged six records as borderline (kept Cat 2 because the hedging was missing-evidence type, not rule-itself type, per the default rule):

**Positions in OCID-sorted order: #19, #36, #50, #56, #91, #97.**

The reviewer accepted Cat 2 on all 6. The orchestrator independently audited the 6 records under strict rubric application and concurs:

| # | LLM reasoning summary | Hedge type | Strict rubric call |
|---|---|---|---|
| 19 | "67 days breaches the 30-day requirement" | None (pure rule application) | Cat 2 |
| 36 | "29 days is within s.53 window; COI declaration absent" | Missing evidence (COI field) | Cat 2 |
| 50 | "Below-threshold, published within 1 day, well under £500k" | None (pure rule application) | Cat 2 |
| 56 | "Don't strictly bind at this threshold; missing governance evidence" | Threshold scope + missing evidence | Cat 2 |
| 91 | "COI field absent, preventing evaluation" | Missing evidence | Cat 2 |
| 97 | "COI declaration field not present; COI evidence is missing" | Missing evidence | Cat 2 |

Every borderline's hedging is about missing evidence (COI field absent, substrate doesn't carry the field, etc.) — explicitly excluded from Cat 3 by the rubric's default rule:

> *"missing-evidence hedging is the normal nudge behaviour and is not inversion-recognition."*

The agent flagged them because their surface language ("warrants human review") looks like Cat-3 territory; the actual content is missing-evidence hedging, which the default rule unambiguously excludes from Cat 3. **Reviewer's 100% acceptance is rubric-aligned, not fatigue-driven.**

P5 robustness: even if all 6 borderlines had shifted to Cat 3 in the reviewer's adjudication, the distribution would have been 0/94/6 — still P5 Confirmed.

## Why this distribution is methodologically clean despite 100% acceptance

A 100% acceptance rate on an AI-first protocol could in principle signal reviewer over-acceptance (cognitive load + uniform AI suggestion → `a` enter through). Two pieces of evidence against that reading on this arm:

1. **The agent's regex sweep** (per its PR #111 body) for inversion-naming vocabulary (`invert | backward | reversed | contradict | opposite | flip | as stated | literal reading | seems wrong | …`) found zero matches across all 100 reasoning texts. The Cat 1 absence is corroborated by an orthogonal lexical signal, not just the agent's category judgment.

2. **The reviewer's per-borderline call is independently validatable** (above table). On each of the 6 records the agent flagged, the hedging is genuinely missing-evidence type — the rubric's default rule unambiguously assigns these to Cat 2.

The methodological observation that drove the protocol change (primary's drift on Cat 2/Cat 3 boundary) does NOT re-emerge on claude. Reviewer judgment on the AI-first walk was rubric-aligned.

## Cross-arm comparison — the substantive cross-model finding

Pairing this arm's canonical sheet against `diagnostic_primary`'s (which was finalised under a different protocol — blind first pass + blind AI second-coder + reconciliation; see `rubric_inter_coder_analysis_primary.md`):

| Arm | Model | Cat 1 | Cat 2 | Cat 3 | P5 |
|---|---|---:|---:|---:|---|
| `diagnostic_primary` | GPT-5.4-2026-03-05 | 7 (7.0%) | 93 (93.0%) | 0 (0.0%) | Confirmed |
| `diagnostic_claude` | Claude Opus 4.7 | **0 (0.0%)** | 100 (100.0%) | 0 (0.0%) | Confirmed |

**Both models predominantly inversion-blind. GPT-5.4 occasionally names the inversion (7%); Opus never does (0%).** This is the cross-model rubric-axis observation.

This finding is **coherent with the cross-model verdict-axis observation from Phase 2** (recorded in the 2026-05-29 decision_log entry):

- Phase 2 diagnostic verdicts at n=100: Opus decisive on 80% of records (35 ALLOW + 45 DENY + 20 REVIEW); GPT-5.4 decisive on 23% (0 ALLOW + 23 DENY + 77 REVIEW).
- Rubric-axis Cat 1 rate: Opus 0%, GPT-5.4 7%.

Confident application of the rule-as-stated IS Cat 2 inversion-blindness. Opus's verdict decisiveness translates into rubric Cat 2 thoroughness. GPT-5.4's hedging creates surface area for occasional inversion-registration that Opus's decisiveness eliminates.

This is a substantive cross-model finding for the writeup, not just a within-arm characterisation.

## P5 confirmed on both arms

The pre-registered P5 hypothesis (inversion-blindness at scale via the locked rubric) is **Confirmed** on both diagnostic arms:

- `diagnostic_primary`: Cat 2 = 93%, Cat 1 = 7% → Confirmed
- `diagnostic_claude`: Cat 2 = 100%, Cat 1 = 0% → Confirmed

The cross-model robustness (Confirmed under two model-protocols, with the Cat 1 rate varying by model in the direction the Phase 2 verdict-axis suggested) strengthens P5 evidence beyond what a single-arm replication would provide.

## What's next

Phase 2.5 is closed. Phase 3 (analysis notebook + writeup) is the next phase. The methods section will lift:

- The verbatim AI-first protocol-disclosure sentence (above)
- The verbatim blind-first-pass + reconciliation protocol-disclosure sentence (from `rubric_inter_coder_analysis_primary.md`)
- A sentence explaining why the protocols differ between arms (primary's drift surfaced during reconciliation motivated the AI-first protocol for claude — see decision_log entries 2026-06-07)

The results section is anchored by:

- Verdict-axis distributions per arm (from Phase 2 receipts; see `phase-2-summary.md` in the run dir)
- Rubric-axis distributions per arm (from the two canonical sheets: `rubric_coding_primary.jsonl`, `rubric_coding_claude.jsonl`)
- Cross-model comparison on both axes
- The asymmetric-control caveat for Arm C from PR #93 (the Phase 2 main-grid finding)
- The methodologically meaningful arcs (record-composition fix at PR #97; rubric coder-drift caught by κ check on primary; protocol change for claude)
