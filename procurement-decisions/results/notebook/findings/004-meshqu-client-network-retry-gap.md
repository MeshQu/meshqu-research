# Finding 004 — `meshqu_client.py` has no bounded retry; TCP resets surface as permanent corpus loss

**Created:** 2026-05-18
**Status:** draft (promotion gated on the retry patch shipping + a re-run confirming the keep-alive hypothesis)
**Bears on:** methodology

## The claim

The runner's `MeshQuClient.record_decision` has no per-record retry on transient network errors. TCP resets (`ConnectionResetError`, `'Connection aborted.'`) surface immediately as `MeshQuClientError(kind='network')`, the eval loop logs an anomaly with category `unexpected` / severity `warn`, and the record is **permanently skipped** — no receipt is produced, no idempotency-key probe is attempted, no retry is issued. This is a deviation from the bounded-retry pattern already shipped on `agent.py` for OpenAI calls (added 2026-05-17 in PR #20). The first attempt at the 300-record corpus run (`dry-run-5ac1e02c-b4ec-4409-ba81-2066d3b8e16b`, 2026-05-18) hit two such resets in the first 17 records (records 8 and 17, ~9 records apart). The run was killed per the pre-run checklist's >5% skip threshold; the corpus run is rescheduled after a bounded-retry patch lands on `meshqu_client.py`.

## Evidence

- Aborted run `dry-run-5ac1e02c-b4ec-4409-ba81-2066d3b8e16b` final counters: 54 records attempted, 52 decision_traces written, 2 anomalies (indices 8 and 17). Both anomalies identical shape:

```
category: unexpected
severity: warn
summary:  meshqu record failed: network
detail:   network: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))
status_code: null
response_body: null
```

- `status_code` and `response_body` both null indicates the TCP connection died before any HTTP reply arrived — distinct from the `MISSING_TENANT_ID` 400 shape (which carries a JSON body) and distinct from receipt-orphan anomalies (which carry a remote `decision_id`).
- Cross-reference `runner/meshqu_runner/agent.py`'s `_call_with_retry` (yesterday's PR #20, `3dc1a79`): bounded backoff with retryable kinds `{network, timeout, server, rate_limit}` and terminal kinds `{auth, unsupported_param, unknown}`. The same pattern is missing on `runner/meshqu_runner/meshqu_client.py`.
- Companion observation: SIGTERM landed during an agent call (zero orphans found by `recover_orphans.py` post-kill). The orphan-recovery tool's current scope is "remote receipt landed + local write failed" — it does NOT probe `unexpected: network` anomalies by idempotency key to check whether MeshQu actually committed. That's a separate gap (out of scope for this finding; flagged in the notebook entry for future hardening).

## Why the gap matters at the 300-record scale

Two records skipped out of 54 at this kill point is 3.7% (headline) but 11.8% in the first 17 (early-window). Indices 8 and 17 are ~9 records apart — the clustering shape is consistent with a periodic keep-alive lifecycle event (Railway worker recycling, or `requests.Session` connection-pool entries going stale on a similar cadence) rather than independent Bernoulli failures. If the cadence holds, an unmitigated 300-record run would see ~25–35 resets, well above the pre-set threshold and a meaningful chunk of corpus loss.

The methodologically defensible response is to add the retry — not to widen the threshold or accept the skip rate. The retry brings the runner's posture toward MeshQu in line with its posture toward OpenAI; the asymmetry yesterday was a real gap that the early-window dry-run + smoke didn't surface because the smoke's 3 records were too few to hit it and the dry-run's 10 records cleared the keep-alive window by luck.

## Caveats

- The "keep-alive lifecycle" explanation is a hypothesis, not confirmed. Two data points is enough to flag a structural shape but not to prove the mechanism. Post-retry-merge re-run will either confirm (retries absorb resets cleanly, run completes) or refute (resets persist even with retry, escalate to Railway-side diagnosis).
- The retry patch must mirror the agent's discipline: bounded attempts, exponential backoff with cap, `Retry-After` honored for rate-limit kind, `retry_count` threaded into the trace row, terminal kinds NOT retried. See [F002's docstring on `agent.py`'s `_call_with_retry`](../../runner/meshqu_runner/agent.py).
- Belt-and-braces option: bump `inter_request_pause_seconds` default 0.25 → 1.0 to reduce keep-alive idle pressure. The retry patch is the primary fix; pacing tweak is secondary and should be data-driven (don't tune unless the retry-only patch still shows resets).

## What this changes about the writeup

Section 7 (limitations / methodology in action) gains a worked example: the aborted run was an instance of pre-registered discipline catching a real apparatus gap before it corrupted the corpus. The kill decision was costlier in the short term (re-run, ~$5–15 extra OpenAI spend, half a day of slippage) and cheaper in the long term (corpus completeness + a published case study of the discipline working as designed). The point the writeup gets to make is **not that the runner is perfect** — it's that the methodology surfaces apparatus gaps quickly enough to fix them before they corrupt the audit trail.

Promotion to `Status: stable` is gated on:

1. The retry patch shipping in a fresh session (mirroring `agent.py`'s pattern).
2. The corpus re-run completing with skip rate well below the 5% threshold AND no `meshqu record failed: network` anomalies that exhausted retries.
3. If the keep-alive theory holds, a sentence-level confirmation in the post-rerun notebook entry that retries absorbed N reset events with no permanent skips.
