# 2026-05-17 — Build completion + smoke + dry-run

Session covers the runner's end-to-end completion: substrate adapter merge → eval loop → smoke against staging → post-smoke policy clarification → dry-run against live OCDS → cleanups. Full run held over to 2026-05-18 to land everything documented first.

Companion entries:
- Findings: [001 (tenant header)](findings/001-tenant-header-missing-in-runner-client.md), [002 (PROC-004 clarification)](findings/002-proc-004-coi-absence-clarification.md), [003 (verifier paths)](findings/003-bundle-is-canonical-verifier-path.md).
- Decision log: 2026-05-17 "Post-smoke policy clarification" + 2026-05-17 "Foundation model locked".
- Pre-run checklist for the 300-record full run: [`pre-run-checklist-300-record.md`](pre-run-checklist-300-record.md).

---

## 13:50 — runner pipeline merge train

Five PRs landed on `meshqu-research/main` in sequence: substrate adapter (#17, `7acbc65`), Inspect-AI eval loop (#18, `ddebb2a`), retry + inter-request pacing (#20, `3dc1a79`), receipt-orphan recovery (#21, `4979eab`), end-to-end smoke script (#22, `93cb726`). 161 → 176 runner tests after orphan recovery; 192 after the dry-run + cleanups.

Choices that turned out to matter later:
- The eval loop takes `substrate_callable` and `provenance_summary_callable` as injected dependencies rather than importing `substrate.py` directly. That decoupling let #18 ship while #17 was still in review without #18's tests depending on substrate's presence. Same pattern proved useful again in the orphan recovery #21 (no substrate import needed at all).
- The agent's `_call_with_format` was built with a json_object → plain_text fallback even though gpt-5.4 supports `response_format: json_object`. Defensive: if OpenAI ever changes the rules under the locked model id, the fallback recovers automatically. Same retry path discovered a real bug under review (PR #19) — retry_count was being silently discarded across the mode switch.

Linked: PRs #15, #17, #18, #20, #21, #22 (all on `meshqu-research`).

## 14:40 — first staging smoke: tenant-header bug caught

Smoke run `smoke-d3afabff-…` returned 3/3 `outcome=skip_meshqu`, HTTP 400 `MISSING_TENANT_ID` on every record. The MeshQu API requires `x-meshqu-tenant-id` in addition to the bearer token (the four-layer tenant isolation model in the monorepo's CLAUDE.md is real — request header is one of those layers). The runner client wasn't sending it.

Fixed in PR #23 (`b864f7f`). Re-ran the smoke under `smoke-4943fd10-…` → got past `MISSING_TENANT_ID` but hit `FORBIDDEN: API key does not belong to this tenant` — `MESHQU_API_KEY` in Doppler `shared/stg` is for a different staging tenant. Sam pasted the experiment-procurement key inline; third run `smoke-0507305a-…` produced 3/3 receipts.

This is a methodology finding worth filing in its own right — see [F001](findings/001-tenant-header-missing-in-runner-client.md). The argument the writeup will make: the smoke exists to surface integration gaps before the corpus run, and it did exactly that, twice.

Linked: smoke runs `smoke-d3afabff-…`, `smoke-4943fd10-…`, `smoke-0507305a-…`; PR #23.

## 15:30 — third smoke surfaced PROC-004 policy/substrate mismatch

3/3 receipts under `smoke-0507305a-0…` came back DENY: record A `['PROC-004-COI']`, record B `['PROC-001-S53', 'PROC-004-COI']`, record C `['PROC-004-COI']`. PROC-001-S53 fired correctly on B's 35-day delay. But PROC-004-COI fired on all three.

The schema docstring already documented intent ("Today: omitted, PROC-004 cannot fire") — but the wiring fired on absence. Every OCDS-substrate record will trip PROC-004 uniformly because OCDS doesn't carry COI declarations. That collapses the MeshQu headline verdict to a constant DENY, destroying the agreement projection at scale.

The methodological question was whether editing the policy after seeing data violates pre-registration discipline. Wrote the analysis in `planning/decision_log.md` ("Post-smoke policy clarification" entry). Key arguments for defensibility:
- No corpus exists yet — edits cannot be reverse-engineered to favour a result.
- PROC-001-S53 (the rule actually under test) stays frozen.
- Authorial intent ("PROC-004 cannot fire today") was documented BEFORE the smoke.
- The alternative (leave + document) makes the experiment LESS interpretable.

Filed as F002. Full reasoning in the decision log entry. Sam re-ratified PROC-004 with `when: {field: 'conflict_of_interest_declaration', exists: true}` via the v2 console editor. New `policy_snapshot_id`: `cbf12348-6248-48f7-a06f-4e0304cc237e`. Re-ran the smoke: A=ALLOW, B=DENY, C=ALLOW — design spec verdicts.

Linked: smoke runs `smoke-0507305a-…` (pre-clarification) → `smoke-d5787f81-…` (post-clarification); PR #24, #25; F002.

## 17:00 — first dry-run against live Contracts Finder OCDS

PR #26 fixed a real bug found by inspection: `fetch_ocds_records` was written speculatively with `since/until/cursor` params, but the live Contracts Finder API uses `publishedFrom/publishedTo` and provides a full `links.next` URL for pagination. Verified the live API shape by probe before writing the fix; 12 fetcher tests added.

Dry-run `dry-run-adfc2109-…` (10 records, 2025-08-01 → 2025-08-15 window): 10/10 receipts, 0 errors, 0 orphans, mirror passed.

Substrate provenance across 10 records × 10 fields = 100 cells:
- direct_ocds: 20
- derived: 21
- proxy: 30
- absent: 29

~30% absent is the substrate-honesty signal the smoke fixtures couldn't show. The writeup's substrate-honesty subsection writes itself from numbers like this.

Agent verdict pattern at 10 records: 10/10 → REVIEW. 9 of those against MeshQu ALLOW, 1 against MeshQu DENY. **The agent never said ALLOW and never said DENY across the whole batch — even on the record MeshQu DENY-d.** Foundation-model-on-compliance-tasks pattern surfacing at scale. Too thin to file (10 records); revisit at 300.

One finding from a specific record: `ocds-b5fd17-57746fba-…` had `publication_delay_days: -10` — publication date BEFORE award date. Real-world OCDS data-quality artifact. Substrate adapter computed faithfully. The policy doesn't currently treat negative delays as anomalies (just numeric). Substrate-honesty callout for the writeup. The agent flagged it specifically: `recommended_action: "Verify award timeline and route-to-market record"`.

Linked: PR #26; dry-run `dry-run-adfc2109-…`; record `ocds-b5fd17-57746fba-…`.

## 17:30 — one screenshot timed out + audit trail was split

Mid-run, checkpoint-006 capture failed: `screenshot_capture_failed: render request failed: ReadTimeout`. 6/7 PNGs landed. Render timeout default was 10s — Railway-renderer cold-start latency spikes past that. Cleanup PR #27 bumped default to 30s and added one retry on ReadTimeout/ConnectionError.

Also surfaced (audit-trail hygiene): two `AuditWriter` instances were writing to two different trees — eval loop's anomalies under `results/runs/<id>/`, RunController's anomalies + checkpoints under `results/audit/`. Logically the same run, physically split. Same PR added `audit_dir_override` + `screenshots_dir_override` to RunnerConfig + routes every per-run artefact under `results/runs/<run_id>/`.

Linked: PR #27; dry-run `dry-run-adfc2109-…` checkpoint-006 anomaly.

## 18:00 — verifier "Tampered" panic, then bundle verification confirmed

Sam pasted one of the dry-run receipts into verify.meshqu.com → "Tampered" verdict. Integrity hash recompute didn't match stored. Looked alarming because if the 300-record corpus shows the same, the writeup's verifiability claim collapses.

Sam then downloaded the same receipt's bundle and verified via the bundle path → "Bundle Verified". Every cryptographic check passed: integrity, signature, transparency (DSSE + Rekor binding), canonicalization. The bundle path is the canonical verification artefact; the raw-receipt-paste UX is a known v2 limitation that warns falsely on receipts whose envelope includes server-injected metadata (e.g. `correlation_id`).

Filed as F003 — methodology + P5. The writeup's verifier-instructions section needs to direct auditors to the bundle, not the raw receipt.

Linked: dry-run `dry-run-adfc2109-…` records; F003; PHASE-2 PR #493 in tradequ (the bundle affordance work).

## 18:45 — clean dry-run #2 after cleanups

`dry-run-0223ad77-…` with cleanups merged: 10/10 receipts, 7/7 screenshots (checkpoint-006 landed this time — retry + bumped timeout did the job), every artefact co-located under `results/runs/<run_id>/`. Zero anomalies. Same `policy_snapshot_id=cbf12348-…`, same agent REVIEW-by-default pattern.

Runner is now ready for the 300-record full run. Hold over to 2026-05-18 to get notebook + findings squared away first.

Linked: dry-run `dry-run-0223ad77-…`; PR #27; pre-run checklist for 2026-05-18.

## End-of-day status

- Runner: shipped, 192 tests, validated end-to-end against staging twice
- Policy: re-ratified, `policy_snapshot_id = cbf12348-6248-48f7-a06f-4e0304cc237e`
- Verifier path: confirmed via bundle on one decision; raw-receipt-paste warns falsely (documented)
- Observability: Grafana + renderer wired, 7/7 screenshots last run, mirror gate passing
- Decision log: current
- Memory: current
- Notebook: current as of this entry
- Findings: F001-F003 filed
- Tomorrow: kick off 300-record full run, OCDS window 2024-12-01 → 2026-04-30 (straddles PA23 commencement)
