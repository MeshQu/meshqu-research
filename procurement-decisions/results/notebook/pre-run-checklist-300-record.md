# Pre-run checklist — 300-record full run

> Run this checklist start-to-finish before kicking off the 300-record full run on 2026-05-18.
> If any item fails, stop. The smoke + dry-run discipline existed exactly so we'd catch issues
> here, not mid-corpus.

Target window: `2024-12-01` → `2026-04-30` (straddles PA23 commencement on 2025-02-24).
Target snapshot: `cbf12348-6248-48f7-a06f-4e0304cc237e` (post-clarification).

---

## A. Repository state

- [ ] `meshqu-research/main` clean (`git status` empty). All today's PRs merged: #15, #17, #18, #20, #21, #22, #23, #24, #25, #26, #27, plus today's notebook/findings PR.
- [ ] `git log --oneline -1` shows the most recent main HEAD.
- [ ] Local checkout up-to-date (`git pull --ff-only`).

## B. Configuration

- [ ] `OPENAI_API_KEY` available in Doppler `shared/stg` (no rotation needed).
- [ ] `MESHQU_EXPERIMENT_PROCUREMENT_API_KEY` ready (pasted at run time or added to Doppler under that exact name — see [decision log](../../planning/decision_log.md) for the operator notes).
- [ ] Staging MeshQu API reachable: `curl -sS https://meshqu-api-staging.up.railway.app/health` returns 200.
- [ ] Staging Grafana reachable: `curl -sS -u admin:$GPASS https://grafana-meshqu-staging.up.railway.app/api/dashboards/uid/experiment-tenant-observability` returns the dashboard JSON with `dashboard.title="Experiment Tenant Observability"`.
- [ ] Grafana renderer returns PNG bytes (not HTML): `curl -sS -u admin:$GPASS '<grafana>/render/d/experiment-tenant-observability?from=now-1h&to=now&width=400&height=200&kiosk=tv&tz=UTC&var-tenant=243f19a5-4d4f-4070-9ec1-8170e8260e26' | file -` reports `PNG image data`.

## C. Policy state

- [ ] Staging policy `policy_snapshot_id` is `cbf12348-6248-48f7-a06f-4e0304cc237e`. Confirm via console — the policy's current published snapshot should match.
- [ ] PROC-001-S53 unchanged (the rule actually under test — verify via console UI that `when` is the original `all: [governed_by_pa23=true, above_threshold=true]` and the condition is `publication_delay_days at_most 30`).
- [ ] PROC-004-COI carries the new `when: {field: 'conflict_of_interest_declaration', exists: true}` gate.

## D. Verifier sanity-check

- [ ] Verify ONE receipt from the most recent clean dry-run via the bundle path (download the bundle, paste at verify.meshqu.com). Expected: "Bundle Verified with Caveats" — pass on integrity / signature / transparency / canonicalization. Warnings for snapshot_replay + approval_lineage are acceptable (see [F003](003-bundle-is-canonical-verifier-path.md)).
- [ ] Do NOT use the raw-receipt-paste path to verify — it will warn "Tampered" (false positive, see F003).

## E. Run kick-off

The full run is the same `dry_run_eval_loop.py` script with adjusted `--limit` and `--since/--until`. Authoritative invocation:

```bash
cd procurement-decisions/runner

# Railway service link should be on grafana-meshqu (so the variables CLI
# resolves the renderer password). Re-link if cwd changed:
railway link --project meshqu --environment staging --service grafana-meshqu

GPASS=$(railway variables --json | python3 -c "import json,sys; print(json.load(sys.stdin)['GF_SECURITY_ADMIN_PASSWORD'])")

doppler run --project shared --config stg --command "
  OPENAI_API_KEY=\"\$OPENAI_API_KEY\" \
  MESHQU_API_URL=https://meshqu-api-staging.up.railway.app \
  MESHQU_EXPERIMENT_PROCUREMENT_API_KEY=<paste-here> \
  MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID=243f19a5-4d4f-4070-9ec1-8170e8260e26 \
  MESHQU_RUNNER_GRAFANA_URL=https://grafana-meshqu-staging.up.railway.app \
  MESHQU_RUNNER_GRAFANA_USER=admin \
  MESHQU_RUNNER_GRAFANA_PASSWORD='${GPASS}' \
    python3 scripts/dry_run_eval_loop.py \
      --limit 300 \
      --since 2024-12-01 \
      --until 2026-04-30
"
```

Expected wall clock: ~20–25 min (300 records × ~2–5s OpenAI + ~0.5s MeshQu + 0.25s pacing + 32 Grafana checkpoints).
Expected cost: ~$5–15 in OpenAI API.

The run script's name is currently `dry_run_eval_loop.py` — works fine for the full run too (it accepts `--limit 300`). If we want a separate `full_run_eval_loop.py` for clarity in the writeup, that's cosmetic; the current script does the job.

## F. During the run

- Watch the terminal for per-record progress lines. Don't intervene.
- Don't switch Doppler / Railway env mid-run.
- If a Ctrl-C is needed (network outage etc.), the run_end.json will record `status=aborted_by_signal`. The orphan-recovery script ([`runner.meshqu_runner.recover_orphans`](../../runner/meshqu_runner/recover_orphans.py)) can rebuild any receipt-orphaned rows after, but a clean re-run from scratch is usually preferable to recovery for an experiment corpus.

## G. After the run

1. **Headline counters from `run_end.json`:**
   - `records_attempted` should equal 300 (or whatever the OCDS feed returned; will be <300 if the window has fewer awards).
   - `records_with_receipt` ≈ `records_attempted`. Subtract: parse-failure + agent-call-error + meshqu-error + orphaned-receipt counters.
   - Note any non-zero anomaly counters — they belong in tomorrow's notebook entry.
2. **Eyeball the verdict distribution.** A `jq` one-liner against `decision_traces.jsonl`:
   ```bash
   jq -r '.meshqu_verdict' results/runs/<run_id>/decision_traces.jsonl | sort | uniq -c
   jq -r '.agent_verdict'  results/runs/<run_id>/decision_traces.jsonl | sort | uniq -c
   ```
3. **Bundle-verify ONE receipt** via verify.meshqu.com. Confirms corpus integrity is intact.
4. **Write a per-day notebook entry** at `results/notebook/2026-05-18-full-run.md` summarising what landed. Anything surprising goes in. Findings docs come later (after analysis).

## H. If something goes wrong

| Symptom | First check | Fallback |
|---|---|---|
| `MISSING_TENANT_ID` 400s | API key mismatch (different tenant) — confirm `MESHQU_EXPERIMENT_PROCUREMENT_API_KEY` matches `MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID=243f19a5-…` | Mint a fresh key for the experiment tenant via the staging console |
| `FORBIDDEN: API key does not belong to this tenant` | Same as above — wrong-tenant key | Same |
| Mirror drift error at run start | Someone edited the staging dashboard since the committed mirror JSON | Pass `--skip-mirror-check` for the run + open a separate PR to refresh `results/observability/dashboards/experiment-tenant-observability.json` |
| All records DENY on PROC-004 | Policy didn't actually re-ratify with the `exists` gate, OR the run is pointing at the wrong snapshot | Confirm `manifest.json`'s `policy_snapshot_id` is `cbf12348-…`; re-check the policy in the console |
| OpenAI rate-limiting (429s) | The agent's bounded retry should absorb transient 429s. If you see persistent 429s in anomalies.jsonl, OpenAI account-side limit hit | Wait + re-run; or bump `inter_request_pause_seconds` higher than 0.25 |
| Receipt-orphaned anomalies in the run | Local disk hiccup mid-write | Run the recovery script: `python3 -m meshqu_runner.recover_orphans results/runs/<run_id>/ --base-url <url> --api-key <key> --tenant-id 243f19a5-…` |
| Verifier shows "Tampered" on a raw-receipt paste | Expected (see F003) — use the bundle | Download the bundle from `/v1/receipts/<decision_id>/bundle` and verify that |
