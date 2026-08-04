# Substrate — Experiment 2

## Posture

The substrate is unchanged from E1. There is no new fetch from UK Contracts Finder. The OCDS records cached during E1's run `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d` are the source-of-truth records for E2.

This is a deliberate experimental-design choice, not a convenience. Reusing the cached records means:

- **Substrate is fixed against re-fetch drift.** Different fetch windows could produce different record sets for the same OCIDs (OCDS publishes multiple releases per procurement — see E1 F005). Reusing the cache removes that variable. It does **not** make E2's records identical to the bit with the evidence E1 signed — see the correction below.
- **The L0 baseline reproduces E1 on 271 of the 283 records.** On those, the agent at L0 in E2 sees exactly what it saw in E1. On the other 12 it does not. Reproducibility-on-cached-corpus is a meaningful (though partial) test of E1's results — see E1 P4 deferral.
- **Row-by-row delta tracking is interpretable.** Each of the 283 records is the same record across all 5 levels. The only thing that changes per pass is the context payload. This is what makes "context moves the agent" a clean claim instead of a noisy correlation.

> **Correction — 2026-08-04, per integrity audit IA-2026-02.** This page originally claimed that reusing the cache "holds the substrate identical to the bit" and that "the agent at L0 in E2 sees exactly what it saw in E1." Both are false for 12 of the 283 OCIDs. E1's runner processed 300 release events. The evaluator POST was OCID-keyed and idempotent, so a repeated OCID returned the receipt minted at its **first** release event; the `agent_outputs/{decision_id}.json` sidecar E2 rebuilt its corpus from was written last-write-wins and survived holding the **last**. Across all 12 duplicated OCIDs the sidecar's agent-reasoning hash differs from the one its receipt binds; on 5 the evidence fields also differ; on 2 the difference crosses the £139,000 threshold and flips the MeshQu verdict — which is why E1 publishes 144 ALLOW / 139 DENY and E2/E3 publish 146 / 137. Both splits are correct for the evidence each run signed, and no receipt, signature, or verdict is revised. Full reconciliation, including the per-record trace: [IA-2026-02](../../docs/integrity-audits/2026-08-04-corpus-lineage-and-receipt-count.md).

## What this means in practice

The runner reads from `procurement-decisions/results/runs/dry-run-7ddf7274-…/` as a read-only data source. No HTTP calls to Contracts Finder. The substrate adapter's job is to load cached JSON and pass it through to the agent, not to fetch.

## Substrate adapter

The full substrate adapter documentation lives at [`../../procurement-decisions/planning/substrate.md`](../../procurement-decisions/planning/substrate.md). It is unchanged for E2. The per-field provenance envelope (direct_ocds / derived / proxy / absent) is unchanged. The OCID-deduplication outcome (300 release events → 283 unique records) is inherited as-is.

## What this rules out

Two findings E2 cannot make:

- **A different OCDS publication window.** E2 cannot say anything about how the agent behaves on a fresh sample. That is a separate experiment.
- **A different substrate altogether.** Cross-domain generalisation (AML, KYC, underwriting) is an explicit deferred follow-up per E1 §9 and MRP-2026-02 §9. E2 confirms or refutes context-driven commitment within the same substrate as E1; cross-substrate generalisation requires its own piece.

## What this preserves

The 7-year retention claim, the regulatory framing (UK PA23 + PCR 2015 dual-regime), the methodological proxies (governance-regime-by-award-date, s.53 30-day clock from `awards[0].date`), and the substrate-honesty fractions (~20% direct OCDS, ~21% derived, ~30% proxy, ~29% absent) all carry over unchanged. E2's writeup §4 will be one paragraph that defers to E1's full substrate documentation rather than restating it.

## Adapter version locked

`substrate_adapter_version = 0.1.0` (the version used by E1's full run). Persisted to the E2 run manifest. Any change to the adapter post-lock invalidates the cross-experiment comparison and would need to be documented in the decision log with the same defensibility analysis as E1's PROC-004-COI clarification.
