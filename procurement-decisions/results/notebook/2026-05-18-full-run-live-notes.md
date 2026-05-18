# 2026-05-18 — Live observations during the full corpus run

> Contemporaneous notes captured during `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`
> (300-record full corpus run). Append-only. The post-run notebook entry
> (`2026-05-18-full-run.md`) draws on this file rather than reconstructing.
>
> Records here are by hand pick — Sam noticed them and called them out during
> the run. The full corpus is in `decision_traces.jsonl`; this file is the
> curated highlight reel for the writeup's worked-example slots.

---

## Pattern emerging: above-threshold + late publication + missing open-flag → triple critical, agent REVIEWs

Two records pasted in real time during the run, same structural shape:

### Record 36 — £57M contract, 33-day delay

- **OCID**: `ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/36`
- **Timestamp**: 2026-05-18T10:42:19Z
- **Substrate**: `contract_value=57,000,000`, `publication_delay_days=33`, `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED (substrate honestly absent — OCDS didn't say "open"), `direct_award_justification_present=false`
- **MeshQu**: DENY (4 evaluated, 2 NA). Violations:
  - **PROC-001-S53** — `publication_delay_days=33` > 30 (`VALUE_ABOVE_MAX`)
  - **PROC-002-AUTHORITY** — `contract_value=£57M` > £500k (`VALUE_ABOVE_MAX`)
  - **PROC-005-OPEN-TENDER** — `procurement_method_open_flag` missing (`FIELD_MISSING`)
- **Agent**: `REVIEW` with `recommended_action="Obtain procedure rationale and notice trail"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677a25bce5f8d63511fc7f9ef20c50ec0299d8cce4dd9908545d04c9e7af27a35364`, `log_index=1566819550`

**Why it matters for the writeup**:
- First record (in our real-time view) where **PROC-002-AUTHORITY fires** — the £500k authority threshold is much harder to hit on the OCDS substrate's lower-value records, so seeing it on a £57M public contract is the rule working as designed.
- The agent's `recommended_action` text **maps directly onto two of the three MeshQu violations**: "procedure rationale" → PROC-005, "notice trail" → PROC-001-S53. The agent **sees** the structural issues and **names** them — but still chooses REVIEW over DENY.

### Record 61 — £3.3M contract, 119-day delay

- **OCID**: `ocds-b5fd17-536c115b-55f7-49c0-83d8-d21788b3f872`
- **correlation_id**: `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d/61`
- **Timestamp**: 2026-05-18T10:44:54Z
- **Substrate**: `contract_value=3,335,171.93`, `publication_delay_days=119` (≈4× the 30-day limit), `above_threshold=true`, `governed_by_pa23=true`, `procurement_method_open_flag` OMITTED, `direct_award_justification_present=false`
- **MeshQu**: DENY (4 evaluated, 2 NA). Same three violations as record 36:
  - PROC-001-S53 — `publication_delay_days=119` > 30
  - PROC-002-AUTHORITY — `contract_value=£3.3M` > £500k
  - PROC-005-OPEN-TENDER — `procurement_method_open_flag` missing
- **Agent**: `REVIEW` with `recommended_action="Verify procedure basis and publication compliance"`
- **Rekor anchor**: `entry_uuid=108e9186e8c5677a548c2425092f1447fe178b8cc97ef80ddf03121ad336a94c5aa165a131581179`, `log_index=1566824794`

**Why it matters for the writeup**:
- 119-day publication delay is **way past** the s.53 30-day window. Real-world record of a public contract whose details notice landed nearly 4 months late.
- Same agent pattern as record 36: `REVIEW` verdict + a recommended_action that **names the specific rule territories** in plain English ("procedure basis" → PROC-005, "publication compliance" → PROC-001-S53). Two-record streak is the start of a pattern — flag for the writeup's drift framing (the agent reasons toward the right concerns but doesn't commit to a verdict that names them as violations).

## Cross-record observations (early-run, may shift as more records land)

- **PROC-004-COI**: consistently NA on both records (`when: exists: true` gate working as designed; substrate honestly omits the field). This is yesterday's [F002 clarification](findings/002-proc-004-coi-absence-clarification.md) doing its job — without it both these records would have a fourth `PROC-004-COI` violation that adds nothing.
- **PROC-006-MOD-CAP**: consistently NA on non-modification records. Working.
- **Agent REVIEW-by-default pattern (suspected at 10-record dry-run scale)**: still holds at ~60-record scale. Agent is reasoning about specific compliance issues — not generic "needs review" — but never escalating to DENY. Watch how this holds across the full 300. P1 (agreement rate) and P6 (direct-award disagreement cluster) both have something to say about this if the pattern persists.
- **Substrate behaviour**: `procurement_method_open_flag` is omitted in both records (consistent with the schema's `enum: ["true"]` shape — only emitted when method was open). This is the rule's by-design absence-fires logic working: when the field is absent + the `when` clause matches (above-threshold + no direct-award justification), PROC-005 fires.

## Open watching briefs (not findings yet)

- **Will any record produce agent=DENY?** As of record 61, 0 / ~60 records have agent DENY. Hypothesis: the foundation model under temperature 0 is structurally cautious on compliance verdicts. Falsified if even one record produces agent DENY before the run ends.
- **PROC-002-AUTHORITY firing rate**: 2/2 of the multi-violation records have it. What fraction of the full corpus exceeds £500k? Substrate provenance summary at run-end will tell.
- **Multi-violation vs single-violation distribution**: how often does a record violate multiple rules vs just one? Worth a post-run breakdown for the writeup.
