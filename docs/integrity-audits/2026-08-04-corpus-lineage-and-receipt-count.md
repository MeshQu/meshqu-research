# Integrity Audit IA-2026-02 — Programme receipt count and E1 corpus lineage

**Date:** 2026-08-04
**Auditor:** Sam Carter (MeshQu)
**Affects:** MM-2026-01 (methods note), MRP-2026-02 (E1), MRP-2026-03 (E2), MRP-2026-04 (E3)
**Claims under audit:**
1. *"Across the programme, ~3,061 signed decisions were emitted and independently anchored to the public Rekor log."* (methods note §6.1)
2. *E2 and E3 re-ran over the same frozen 283-record corpus as E1* — read strictly, that the per-record evidence evaluated is identical across the three experiments.

**Disposition:** **Refuted** (the 3,061 count; the programme emitted **3,044** distinct signed decisions) · **Discovered** (an E1 archive lineage defect: for 12 OCIDs the archived agent-output sidecar does not correspond to the receipt signed for that OCID) · **Confirmed** (both published MeshQu verdict splits — E1's 144/139 and E2/E3's 146/137 — are correct for the evidence each run actually evaluated and signed)

> This audit was prompted by a discrepancy a reader can see without any private artefact: E1 publishes a MeshQu verdict split of 144 ALLOW / 139 DENY over 283 records, and E2 publishes 146 ALLOW / 137 DENY over what it describes as the same frozen corpus. Both numbers are re-derivable from `data/receipts.parquet`. The audit establishes that neither number is wrong, identifies the two records that differ and why, and — following the same evidence — retracts a separate, genuinely incorrect count in the methods note. No published verdict, receipt, or signature is revised by this audit.

## 1 · What was audited, and why

Two counts in the programme's public record did not reconcile.

**The receipt count.** The methods note stated ~3,061 signed decisions; the data export states 3,044 (`data/DATA_MANIFEST.json`, `data/DATA_DICTIONARY.md`). The two differ by exactly 17.

**The verdict split.** MRP-2026-02 §5.1 reports MeshQu verdicts of 144 ALLOW / 139 DENY across 283 unique decisions. MRP-2026-03 §1.4 reports {ALLOW: 146, DENY: 137} across what §1.5 describes as E1's frozen corpus, and MRP-2026-04 reports the same 146/137. The difference is two records.

Both discrepancies trace to one previously documented substrate behaviour — [F005: the Contracts Finder OCDS feed publishes multiple releases per OCID](../../procurement-decisions/results/notebook/findings/005-ocds-feed-publishes-multiple-releases-per-ocid.md) — but they are different consequences of it, and only one of them is an error.

## 2 · Evidence

### (a) The verdict splits are both real, and both re-derivable from the public export

From `data/receipts.parquet` (public, 3,044 rows), grouping `policy_verdict` by experiment and condition:

| Experiment | Condition | ALLOW | DENY |
|---|---|---|---|
| E1 | `baseline` | **144** | **139** |
| E2 | `L0`–`L4` (each) | **146** | **137** |
| E3 | `arm_a` / `arm_b` / `arm_c` / `l4_without_nudge` (each) | **146** | **137** |

Joining E1 to E2 on `ocid` (283 / 283 join, no unmatched rows on either side) yields exactly **two** records whose `policy_verdict` differs. Both are among the 5 OCIDs the data dictionary already flags as carrying different evidence between E1 and E2/E3.

### (b) The two records that differ

| | `ocds-b5fd17-692f6806-c7ee-4115-b82f-76d0b6afde77` | `ocds-b5fd17-6bb11187-ac69-45a7-8246-73ce1b53100d` |
|---|---|---|
| E1 `decision_id` | `d88c6f1b-5d77-49b8-b4e0-432c79918d5c` | `f818d518-af56-4c03-a1d7-2de30f408d0e` |
| E1 verdict | **DENY** — `PROC-005-OPEN-TENDER` | **DENY** — `PROC-001-S53`, `PROC-002-AUTHORITY` |
| E1 `contract_value` / `above_threshold` | 147,870 / `"true"` | 6,264,658 / `"true"` |
| E2 `L0` `decision_id` | `bf6f5321-9eca-4d6f-b4e7-175b8e5492e8` | `1676a33c-3811-41b1-b961-f489f7bdeed9` |
| E3 `arm_a` `decision_id` | `81796aa5-1b75-448d-90cf-c5e3610baaad` | `601075d6-8beb-4a3e-a7e5-2080f5e1949d` |
| E2 / E3 verdict | **ALLOW** — no violations | **ALLOW** — no violations |
| E2 / E3 `contract_value` / `above_threshold` | 118,296 / `"false"` | 0 / `"false"` |

Every rule in the ratified policy is threshold-gated. Of the 284 rows carrying `above_threshold == "false"` across E1 `baseline` and E2 `L0` (141 + 143), **none receives DENY**. A change in `above_threshold` is therefore sufficient on its own to account for both flips; no other field needs to be invoked.

The `above_threshold` value is a derived proxy, and each release states its own provenance. The two releases evaluated for `692f6806…` differ in the tender value they publish (147,870 vs 118,296) either side of the £139,000 PA23 Schedule 1 sub-central services threshold the programme adopts as a conservative default. For `6bb11187…`, the later release omits the tender value entirely and the adapter falls back to `awards[0].value.amount = 0`, recorded verbatim in the substrate note: `awards[0].value.amount (tender value absent)=0 ≤ £139,000`.

### (c) Mechanism — the receipt and the archived sidecar bind different release events

E1's runner processed **300 release events**, one substrate-adapter pass per event. Two archive-writing behaviours diverge on a repeated OCID:

- **The evaluator POST is OCID-keyed and content-blind.** `_idempotency_key(run_id, record_index, ocid)` in [`procurement-decisions/runner/meshqu_runner/eval_loop.py`](../../procurement-decisions/runner/meshqu_runner/eval_loop.py) hashes `f"{run_id}/{ocid}"`. The second POST for a repeated OCID therefore returned the **cached receipt minted at the first release event**, regardless of whether the later release carried different values.
- **The agent-output sidecar is `decision_id`-keyed and last-write-wins.** `_write_agent_output_sidecar` in the same module writes `agent_outputs/{decision_id}.json` via `os.replace`. The second pass overwrote the first, so the surviving file holds the **last** release event's adapter output. The archive contains **283 sidecar files for 300 events**.

The trace rows show the idempotency leg directly. Both events for each OCID carry the same `decision_id` and the same `integrity_hash`, and — decisively — the same `receipt_timestamp`, which precedes the second event's POST time:

```
OCID ocds-b5fd17-692f6806-c7ee-4115-b82f-76d0b6afde77
  record_index=100  decision_id=d88c6f1b-5d77-49b8-b4e0-432c79918d5c
      integrity_hash    = 194cdb1cc9f1c6ac3fa7a45bdf22f30a7581500d2a2e2c4013921cd7598dca13
      receipt_timestamp = 2026-05-18T10:49:11.741Z   POST ts = 2026-05-18T10:49:12.198Z
  record_index=105  decision_id=d88c6f1b-5d77-49b8-b4e0-432c79918d5c
      integrity_hash    = 194cdb1cc9f1c6ac3fa7a45bdf22f30a7581500d2a2e2c4013921cd7598dca13
      receipt_timestamp = 2026-05-18T10:49:11.741Z   POST ts = 2026-05-18T10:49:46.408Z

OCID ocds-b5fd17-6bb11187-ac69-45a7-8246-73ce1b53100d
  record_index=212  decision_id=f818d518-af56-4c03-a1d7-2de30f408d0e
      integrity_hash    = 1654c41a34e317a268f238e4b81dd6d561f363d49f69b244bb73f596170be15d
      receipt_timestamp = 2026-05-18T11:01:33.152Z   POST ts = 2026-05-18T11:01:33.694Z
  record_index=214  decision_id=f818d518-af56-4c03-a1d7-2de30f408d0e
      integrity_hash    = 1654c41a34e317a268f238e4b81dd6d561f363d49f69b244bb73f596170be15d
      receipt_timestamp = 2026-05-18T11:01:33.152Z   POST ts = 2026-05-18T11:01:46.596Z
```

One receipt per OCID, minted at the first event and returned unchanged at the second. The second event produced **no new decision, no new signature, and no new Rekor entry**.

The sidecar leg is visible by comparing the signed receipt in the public `corpus.tar` against the archived sidecar for the same `decision_id`:

```
decision_id d88c6f1b-5d77-49b8-b4e0-432c79918d5c
  receipt (corpus.tar)      contract_value=147870   above_threshold=true
                            agent_reasoning_sha256=5a5141df3074982963d8b960ae6d89cbef55998bb593d53419cbfe54a5e3ff43
  sidecar (agent_outputs)   contract_value=118296   above_threshold=false
                            reasoning_sha256      =363b553019b10f64d37cd13d83694a2adb4ff3942ce9a34ce4a7257271635967

decision_id f818d518-af56-4c03-a1d7-2de30f408d0e
  receipt (corpus.tar)      contract_value=6264658  above_threshold=true
                            agent_reasoning_sha256=e1d4075117805c4995d90c1ae18760f5fe841445b8890f4c35613dcf81d80d58
  sidecar (agent_outputs)   contract_value=0        above_threshold=false
                            reasoning_sha256      =78e6cbef0f1aa4c9661c55401818c80de2728a708c048283aa6ea71a6335c310
```

Across all **12** duplicated OCIDs the sidecar's agent-reasoning hash differs from the one its receipt binds — the overwrite is uniform, not selective. On **5** of the 12 the evidence fields also differ; on **2** of those 5 the difference crosses the threshold and flips the verdict:

| OCID | E1 → E2 verdict | Field difference (E1 receipt → E2/E3 record) |
|---|---|---|
| `ocds-b5fd17-692f6806-…` | DENY → **ALLOW** | `contract_value` 147,870 → 118,296; `above_threshold` `true` → `false` |
| `ocds-b5fd17-6bb11187-…` | DENY → **ALLOW** | `contract_value` 6,264,658 → 0; `above_threshold` `true` → `false` |
| `ocds-b5fd17-963c1afb-…` | DENY → DENY | `contract_value` 1,200,000 → 336,000 (both above threshold) |
| `ocds-b5fd17-2d7dff2e-…` | ALLOW → ALLOW | `contract_value` 88,188 → 0 (both below threshold) |
| `ocds-b5fd17-f5052bc7-…` | ALLOW → ALLOW | `supplier_id` `GB-CFS-334107` → `GB-CFS-334085` |

E2 and E3 rebuilt their corpus from those sidecars — `load_cached_records` in [`procurement-context-gradient/runner/meshqu_runner/substrate_cache.py`](../../procurement-context-gradient/runner/meshqu_runner/substrate_cache.py) reads `agent_outputs/{decision_id}.json` and parses `user_message` back into the record shape. `data/source_records.json` is the same 283 records by the same path. So E2 and E3 inherited last-release evidence for those 12 OCIDs, not by a normalisation rule, but because the surviving sidecar was the only copy left on disk.

### (d) The receipt count

3,044 is the count of **distinct signed receipts**: 283 (E1) + 1,429 (E2) + 1,332 (E3), matching `data/DATA_MANIFEST.json` and the row count of `data/receipts.parquet`.

3,061 is 300 + 1,429 + 1,332 — E1's **attempted release-event POSTs** rather than the receipts they produced. The 17-event difference is exactly the duplicate release events of §2(c), every one of which was answered from the evaluator's idempotency cache. They produced no additional signed decisions and no additional Rekor entries, so they cannot be counted as either. **3,044 is the defensible figure; 3,061 is retracted.**

## 3 · Conclusion

- The programme emitted **3,044** distinct signed decisions. The methods note's ~3,061 is **Refuted** and corrected in this change.
- E1's **144 ALLOW / 139 DENY** is correct for the 283 receipts E1 signed, each bound to the first OCDS release evaluated for its contracting process.
- E2's and E3's **146 ALLOW / 137 DENY** is correct for the 283 records those experiments evaluated and signed, reconstructed from E1's archived adapter output, which for 12 OCIDs holds the last release.
- Both splits are therefore **Confirmed** on their own basis. The papers' prose is under-specified rather than arithmetically wrong: neither states which release its per-record evidence binds, and MRP-2026-03 §1.5 additionally directs readers to MRP-2026-02 for "the MeshQu verdict distribution" while publishing a different one in its own §1.4. An erratum for that sentence is on the closure track below.

## 4 · Anti-claims — what this audit does not establish

- It does **not** revise any receipt, signature, verdict, or Rekor anchor. Every receipt remains valid for the evidence it binds; nothing in the signed corpus changed, and this audit made no change to any run artefact.
- It does **not** show that any receipt binds evidence it did not evaluate. The reverse: the receipts are the reliable layer here, and the defect is in an unsigned, non-canonical debugging sidecar that was never part of the verification path.
- It does **not** establish that either paper's *findings* change. Both headline results concern agent-versus-policy divergence and the shape of the context ladder; a two-record shift in the policy baseline (0.7% of the corpus) is not tested against, and this audit did not re-run any analysis to claim it is immaterial. Whether any downstream segment statistic moves is **Under-tested** here.
- It does **not** establish which release is the better representation of the underlying procurement. For `6bb11187…` the later release publishes no tender value at all and the adapter's fallback yields 0, which is a weaker evidentiary basis than the earlier release's stated value — but the audit takes no position on which the feed intended as authoritative.
- It does **not** generalise beyond the 12 duplicated OCIDs. The other 271 records join cleanly across all three experiments.
- The mechanism in §2(c) is derived in part from run artefacts that are **not** committed to this repository (`decision_traces.jsonl`, `agent_outputs/`; excluded by `.gitignore`). The quoted rows above are published here precisely so the mechanism is checkable without them; the receipt-side values, the verdict splits, and the 5-OCID divergence table are all independently re-derivable from the public `corpus.tar` files and `data/receipts.parquet`.

## 5 · Going forward (closure track)

- **Methods note** (`methodology/receipt-anchored-evaluation.md` §6.1). Corrected to 3,044 with the idempotency-cache explanation stated inline. *(Closed — this change.)*
- **Data dictionary** (`data/DATA_DICTIONARY.md`, the `ocid` join caveat). Reworded to state the sidecar-overwrite mechanism rather than implying a deliberate normalisation, and to connect the 5-OCID divergence to the published 144/139-vs-146/137 difference. *(Closed — this change.)*
- **MRP-2026-03 erratum.** §1.5's cross-reference to MRP-2026-02 for "the MeshQu verdict distribution" needs a page-level erratum; the paper's own §1.4 is authoritative for its corpus. *(Drafted; pending author review.)*
- **Runner carry-forward.** A debugging sidecar keyed on a *response* identifier cannot faithfully archive a *request* stream when the response is idempotent. Any future runner should either key the sidecar on the request (`record_index`) or dedupe by OCID before evaluation — F005's Option A or C. *(Open; applies to the next corpus run, not retroactively.)*

## 6 · Audit trail

- Verdict splits and the 5-OCID divergence: `data/receipts.parquet` (public) — group `policy_verdict` by `experiment` / `condition`; join `experiment == "E1"` to `experiment == "E2" & condition == "L0"` on `ocid`.
- Signed receipts for the two records: `procurement-decisions/results/corpus.tar → bundles/d88c6f1b-….bundle.json` and `bundles/f818d518-….bundle.json`; parse `files["receipt.json"]` as a JSON string, then read `context.fields`.
- E2 / E3 counterparts: `procurement-context-gradient/results/corpus.tar → bundles/bf6f5321-…`, `bundles/1676a33c-…`; `procurement-context-disambiguation/results/corpus.tar → bundles/81796aa5-…`, `bundles/601075d6-…`.
- Idempotency key and sidecar writer: `procurement-decisions/runner/meshqu_runner/eval_loop.py` (`_idempotency_key`, `_write_agent_output_sidecar`).
- E2 / E3 corpus loader: `procurement-context-gradient/runner/meshqu_runner/substrate_cache.py` (`load_cached_records`); equivalent module in `procurement-context-disambiguation/runner/`.
- Duplicate-release substrate behaviour: [F005](../../procurement-decisions/results/notebook/findings/005-ocds-feed-publishes-multiple-releases-per-ocid.md).
- Non-public inputs (E1 run archive `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`): `decision_traces.jsonl` rows at `record_index` 100, 105, 212, 214; `agent_outputs/d88c6f1b-….json` and `agent_outputs/f818d518-….json`. The values these supply are quoted verbatim in §2(c).
