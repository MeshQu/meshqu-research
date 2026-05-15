# Agentic Procurement Experiment — Planning Harness

**Status:** `[PLANNING]` (no implementation work; design + pre-registration only)
**Owner:** Sam
**Created:** 2026-05-14
**Public home (post-extraction):** `meshqu-research/procurement-decisions/planning/` on GitHub (public, MIT- or Apache-2.0-licensed, under the `meshqu` org). This planning harness is mirrored to the public repo before predictions lock per revision brief 7, so the pre-registration commit is publicly auditable from the moment it lands. From the extraction commit forward, work happens in the public repo; the monorepo copy is either deleted or replaced with a stub pointer.

## What this is

A Stripe-style commercial research report. The artefact is a long-form research post on `meshqu.com/research`, an open repo, and a downloadable signed receipt corpus that readers verify offline. The piece is engineering-credible because the methodology holds up, the data is real, and the corpus is reproducible.

The methodology developed here is substrate-agnostic and intended to be reusable for future analyses on different historic-decision archives. UK Contracts Finder is the first worked application.

Not a peer-reviewable academic paper. Not a demo. Not a customer case study. A vendor publishing rigorous applied work on its own infrastructure. A known commercial-research category.

> **Premise**: an AI agent reviews real public procurement filings and proposes compliance decisions. MeshQu sits in the loop, enforces a documented policy snapshot, and produces a signed audit-grade receipt for every decision. The corpus of receipts is published. Readers verify it offline at verify.meshqu.com.

The artefact is the written piece. The point is not to ship code into the product. The point is to generate a defensible, reproducible thing engineers at regulated firms can engage with on technical merit and forward to their compliance partner.

## Why an experiment and not a demo

Demos always look like sales fiction. An experiment is the opposite. Pre-register what you expect to see, run it, report what actually happened including misses. The credibility comes from publishing the failures alongside the successes.

The audience for this piece is engineers who support compliance, audit, and procurement teams at regulated firms. They read writeups with this shape and dismiss ones that don't. The compliance lead reads it second, through their engineer's forwarding.

## Why procurement (and not AI in financial advice, AI hiring, etc.)

| Reason | Detail |
|---|---|
| Substrate is open data | UK Contracts Finder, US SAM.gov, EU TED — all public, plentiful, no PII risk. |
| Low political volatility | Procurement compliance isn't a culture-war topic. Engineering audiences can engage without reputational risk. |
| Maps to MeshQu's existing capability mix | Policy versions, snapshots, receipts, bundles, audit trail — all already shipped. No new platform work needed. |
| Buyer story is clean | Compliance, audit, procurement teams at regulated firms + government contractors. Budget exists, narrative is timely. |
| Adjacent angle for free | One paragraph at the end: "the same primitives apply to credit underwriting, customer onboarding, and trade pre-screening." |

Consumer-protection AI (NYC LL144, Colorado AI Act, EU AI Act high-risk consumer provisions) is hotter politically but weaker as a buyer story for MeshQu today — the regulator is the consumer agency, not the firm using MeshQu. Revisit in 12–18 months once enforcement has shape.

## What this harness contains

| File | Purpose |
|---|---|
| [`README.md`](README.md) | This file. Top-level summary and rationale. |
| [`project_context.md`](project_context.md) | Full orientation for a fresh agent picking this up — what's done, what's open, what's intentionally out of scope. |
| [`experiment_design.md`](experiment_design.md) | The methodology — agent loop, policy under test, evaluation pipeline, what counts as "MeshQu caught it". |
| [`predictions.md`](predictions.md) | **Pre-registered predictions.** Filled out BEFORE running. Locks in what the experiment is trying to show; honest writeups report results against these even when wrong. |
| [`substrate.md`](substrate.md) | Data sourcing plan — which datasets, how to access, sampling strategy, ethical / legal posture. |
| [`writeup_outline.md`](writeup_outline.md) | The artefact: blog-post outline, what gets published where, what gets open-sourced. |
| [`spike_brief.md`](spike_brief.md) | Phase 0 feasibility-spike brief. Hand to a coding agent. Five questions, ~200 sacrificial records, sacrificial-data discipline. |
| [`feasibility_spike_report.md`](feasibility_spike_report.md) | The Phase 0 report itself. Template-shaped; agent fills it in; Sam decides GO / NO-GO. |
| [`decision_log.md`](decision_log.md) | Reverse-chronological journal of design decisions made during planning + execution. |

## What this harness does NOT contain

- Implementation code. Nothing under `apps/` or `packages/` is touched by this harness directly.
- Roadmap commitments. This is a side experiment, parallel to the AARM roadmap; it doesn't reshape it.
- Customer commitments. No pilot promises are made on the back of this. The experiment is a public artefact.

## Sequencing

0. **Feasibility spike** (Phase 0). Pull ~200 sacrificial OCDS records and answer the five questions in [`spike_brief.md`](spike_brief.md). Report lands at [`feasibility_spike_report.md`](feasibility_spike_report.md). Half a day to one day of work, Sam-decided GO / GO WITH ADJUSTMENTS / NO-GO. Records pulled here are excluded from the eventual 300-record corpus — they have been seen before pre-registration.
1. **Plan.** Fill out `experiment_design.md`, `predictions.md`, `substrate.md`, `writeup_outline.md`. Apply any design adjustments from the spike. Optionally review with one external advisor.
2. **Pre-register.** Commit the predictions to a public location (GitHub gist, or the repo when it's seeded) BEFORE any runs happen. Without pre-registration, the credibility argument collapses.
3. **Build the runner.** Small repo — agent harness, MeshQu client wiring, evaluation harness. Probably 1–2 weeks.
4. **Run.** Generate the receipt corpus. Bundle. Verify.
5. **Write.** Draft, publish, open-source the runner + corpus.

Total estimated effort: 2–4 weeks of focused work, sized for a solo founder, plus the half-day to one-day Phase 0 spike up front.

## How this slots in

This experiment **does not depend on** Bundle A, C5, or any other AARM-roadmap item. It runs on today's primitives. If C5 (five-dimension identity) ships first, the experiment's writeup can highlight model-provenance in receipts; if not, the writeup just records what's already there (signature kid, snapshot id, etc.).

Worth doing **before** pursuing a pilot — see [`../aarm-roadmap/decision_log.md`](../aarm-roadmap/decision_log.md) for the broader sequencing argument. A pilot needs evaluation-conversation ammunition; this experiment manufactures that ammunition without needing a customer to grant access first.
