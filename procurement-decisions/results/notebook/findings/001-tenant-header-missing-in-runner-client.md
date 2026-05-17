# Finding 001 — Tenant-isolation header was missing in the runner's MeshQu client; smoke caught it before the corpus run

**Created:** 2026-05-17
**Status:** stable
**Bears on:** methodology

## The claim

The first staging smoke run produced 3/3 `HTTP 400 MISSING_TENANT_ID` failures because the runner's `MeshQuClient` was sending only the bearer token (the API requires `x-meshqu-tenant-id` in addition; see [`apps/meshqu-api/src/middleware/tenant.ts`](https://github.com/MeshQu/tradequ/blob/main/apps/meshqu-api/src/middleware/tenant.ts) in the monorepo). The docstring of the runner's client incorrectly claimed the bearer token alone scoped the tenant. The bug was caught + fixed within the smoke loop in a single session; no corpus data was produced under the broken client. This is the canonical demonstration of why the smoke exists: integration assumptions that look correct in isolation can fail end-to-end, and the smoke is the cheap place to find that out.

## Evidence

- Pre-fix smoke run: `smoke-d3afabff-a6a7-4108-9a61-5b25ad9f2ff7`. All three records: `outcome=skip_meshqu`, `status_code=400`, response body `{"error":{"code":"MISSING_TENANT_ID","message":"Missing required header: x-meshqu-tenant-id"}, ...}`. Captured in that run's `anomalies.jsonl`.
- Fix shipped as [PR #23 `b864f7f` "fix(runner): send x-meshqu-tenant-id header (smoke caught this)"](https://github.com/MeshQu/meshqu-research/pull/23). 2 regression tests added (`test_tenant_header_sent_even_without_correlation_id`, `test_rejects_empty_tenant_id`); 1 existing test extended to assert the header value.
- Post-fix smoke run with correct API key for the experiment tenant: `smoke-0507305a-ed44-4882-b455-a720fee8e603`. 3/3 receipts, `policy_snapshot_id=c6256a8e-55ae-41ba-a265-2d61211e0ca9` (pre-clarification snapshot — see [F002](002-proc-004-coi-absence-clarification.md)).

## Caveats

- The fix is purely additive: a new required constructor parameter (`tenant_id`) on `MeshQuClient`. Constructor guard rejects empty values. No silent fallback.
- The tenant UUID is now required configuration for any runner invocation (`MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID` env var); operator checklists must include it.
- The earlier docstring's "the bearer token resolves the tenant" claim is now annotated in the file with a reference to this incident.

## What this changes about the writeup

Section 7 (limitations / what we'd do differently) gains a paragraph: "the runner client's tenant-isolation header was missing on its first integration with staging — caught + fixed within the smoke loop before any corpus data was produced." The point is not the bug; the point is that the methodology surfaced it cheaply and resolved it inside its own validation step. A reader's takeaway should be that smoke + dry-run discipline is load-bearing for trustworthy corpus collection, not optional ceremony.
