# 2026-05-18 — Aborted first attempt at 300-record full run (TCP-reset clustering)

First attempt at the 300-record corpus run kicked off cleanly, surfaced a structural connection-stability issue at ~12% skip rate within the first 17 records, was killed by Sam per the pre-run checklist's >5% threshold. Aborted-run artefacts preserved; corpus run rescheduled after a bounded-retry patch lands on `meshqu_client.py`. The kill itself created zero orphans (SIGTERM landed during an agent call, not a MeshQu POST).

Companion: stub finding draft [F004](findings/004-meshqu-client-network-retry-gap.md). Pre-run preflight (sections A–D) all passed earlier in the day — see prompt handoff in conversation context.

---

## 09:59 — preflight green

Section A: `main` clean, HEAD = `8e54281`. Section B: API healthy `1.2.0`, Grafana 10-panel dashboard live, renderer returns PNG for `var-tenant=243f19a5-…`, Doppler/Railway credentials all resolve. Section C: confirmed `policy_snapshot_id = cbf12348-…` live by submitting one preflight decision (`decision_id = 392e88b2-854c-45a0-a4a1-87cbeaea57b2`, MeshQu verdict ALLOW, 4 rules evaluated + 2 NA, schema v2). Section D: bundle endpoint serves a JSON bundle with all 5 expected files; verify.meshqu.com round-trip deferred to Sam's manual check pre-run.

OCDS window confirmed has data (sample award 2026-04-29 in the response). Vestigial `PROC-2026-EXPERIMENT` policy (`a0e7540d-…`) noted alongside the real `PROC-2026-EXP` (`900996de-…`) — engine binds to the correct one; cleanup is post-experiment hygiene.

Linked: preflight decision `392e88b2-854c-45a0-a4a1-87cbeaea57b2`.

## 10:11 — run kick-off

Fresh session kicked off the 300-record run via the standard invocation. `run_id = dry-run-5ac1e02c-b4ec-4409-ba81-2066d3b8e16b`. Manifest correct: snapshot `cbf12348-…`, tenant `experiment-procurement`, target 300, runner SHA `8e54281`, agent `gpt-5.4-2026-03-05` @ temp 0.0. Mirror gate passed. Initial screenshot captured.

Linked: run `dry-run-5ac1e02c-…`.

## 10:13 — first connection reset at record 8

`anomalies.jsonl` line 1: `category=unexpected severity=warn summary="meshqu record failed: network" detail="network: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))"`. `status_code` and `response_body` both null — the TCP connection died before any HTTP reply landed. NOT the smoke's `MISSING_TENANT_ID` shape (which returns 400 with a JSON body). This is a request that never reached MeshQu's application layer, or whose response never returned.

Could be Railway worker recycling an idle keep-alive, or our `requests.Session` connection pool serving a dead-but-cached socket. No retry in `meshqu_client.py` to absorb it — record 8 is a permanent skip.

Linked: aborted run records 8 (one of two skipped indices); `results/runs/dry-run-5ac1e02c-…/anomalies.jsonl`.

## 10:15 — second reset at record 17 (~9 records after the first)

Same anomaly shape. Indices 8 and 17 are ~9 records apart. If this were random Bernoulli noise we'd expect more variance; the rough periodicity is consistent with a keep-alive lifecycle event (Railway worker re-cycle every N seconds, or a connection-pool entry going stale on a similar cadence). Not proof, but a real shape.

Skip rate now 2/17 = 11.8% — above the pre-set 5% kill threshold from the pre-run checklist.

Linked: aborted run records 8, 17.

## 10:15 — kill decision

Three options weighed:

- **Let it ride.** Tempting on small sample but accepts whatever rate the run lands at + commits OpenAI cost.
- **Kill, investigate, re-run.** Adds 30–60 min for a `meshqu_client` retry patch + re-run. Protects the corpus.
- **Let it finish silently.** Implicitly the same as let-it-ride; no upside.

Killed. The methodology pre-committed to a >5% threshold; honoring it is part of the discipline. Even if the rate flattened, the runner has zero per-record retry on MeshQu network errors — every reset is permanent corpus loss. Adding retry is the obvious fix and matches the bounded-retry pattern already in `agent.py` for OpenAI calls.

Linked: F004 (draft).

## 10:17 — final counters at kill

```
decision_traces:   52
agent_outputs:     52
anomalies:          2  (indices 8, 17)
checkpoints:       27  (dry-run cadence = 2, so 54 attempted / 2 = 27)
screenshots:       28  (27 checkpoints + 1 run-start; no run-end because abort)
records attempted: 54
skip rate at kill: 2/54 = 3.7%
```

The 3.7% headline understates the early-window 11.8% but doesn't refute the clustering hypothesis — it just means the next reset would have landed somewhere around records 25–35 (roughly 9 after 17), which we killed before reaching.

Linked: aborted run dir `results/runs/dry-run-5ac1e02c-b4ec-4409-ba81-2066d3b8e16b/`.

## 10:18 — orphan reconcile (no-op)

Ran `python3 -m meshqu_runner.recover_orphans` against the aborted dir as a one-shot reconcile. **Zero orphans found.** SIGTERM landed during an agent call rather than a MeshQu POST (statistically expected — agent calls dominate per-record wall time, ~2–5s vs ~500ms for MeshQu).

But also worth flagging: `recover_orphans.py`'s scope is **"remote receipt landed + local write failed"**. Records 8 and 17 are NEITHER orphans nor recoverable — they're a different failure mode (request died before reaching MeshQu, no server-side commitment to fetch). The orphan-recovery tool does not currently probe `unexpected: meshqu record failed: network` anomalies by idempotency key to test whether MeshQu actually committed. If we ever care about that case — a request that died on the response after the server committed — we'd need to extend orphan recovery to probe-by-idempotency-key. Not in scope today; noted for future hardening.

Linked: `recovery_summary.json` in the aborted dir (orphans_total=0, recovered=0, refetch_failed=0).

## End-of-day status

- Aborted run dir preserved at `results/runs/dry-run-5ac1e02c-…/`. Forensics-friendly; not part of the corpus.
- Code change required before re-run: bounded retry on `meshqu_client.py`'s `record_decision`, mirroring `agent.py`'s `_call_with_retry`. Deliberately deferred to a fresh session (not this run-day session) per the audit-runtime principle — fresh agent re-reads `agent.py` from disk rather than relying on session memory of yesterday's shape.
- Hypothesis to confirm post-retry-merge: TCP resets are absorbed cleanly by one retry; the keep-alive theory holds. If retries don't absorb them, escalate to a separate diagnosis (Railway-side capacity, requests.Session pool tuning, switch to a streamed-keep-alive session).
- Corpus re-run scheduled for after the retry PR ships. Same OCDS window (`2024-12-01 → 2026-04-30`), same snapshot (`cbf12348-…`), same agent config. Fresh `run_id` — won't collide with this aborted run's traces.
- No corpus data exists yet. Predictions remain locked at `v0.1-predictions-locked`, untouched. PROC-001-S53 untouched. Substrate adapter untouched.

## Bears on (writeup)

- **Section 7 (limitations / methodology in action)**: this aborted run is illustrative of why the pre-set thresholds matter. The decision to kill at 11.8% (early-window) rather than wait for the final rate to settle is exactly the kind of discipline pre-registration is supposed to enforce. The methodology says we honor the threshold *especially* when it's inconvenient.
- **P5 (bundle round-trip)**: unaffected. Bundle endpoint verified live during preflight on a representative receipt.
