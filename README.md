# meshqu-research

Public research surface for [MeshQu](https://meshqu.com).

This repository carries applied research on AI-assisted decision-making in regulated contexts. Each piece is a worked application of **Receipt-Anchored Evaluation** — an audit-grade, signed-receipt methodology — to a specific public-record substrate. The methodology layer is reusable across pieces and across future client engagements; it is documented in [`methodology/`](methodology/).

## What's here

```
meshqu-research/
├── methodology/                 # The reusable audit-grade decision-receipt method (canonical reference)
├── programme/                   # Research-process discipline: PROCESS.md (gates) + STRUCTURAL-PARITY.md (publication checklist)
├── procurement-decisions/       # E1 — AI-assisted UK procurement compliance review (MRP-2026-02, published)
├── procurement-context-gradient/# E2 — governance-context ladder over E1's corpus (MRP-2026-03, published 2026-05-27)
└── procurement-context-disambiguation/  # E3 — scaffolding only; scope locks at pre-registration
```

## What this repo is

A public, MIT-licensed research surface. Each piece is published with:

- A pre-registered set of predictions, committed before the experiment runs, with the commit hash linked from the writeup.
- A documented methodology covering substrate, agent, evaluation pipeline, and limitations.
- A signed receipt corpus that readers can verify offline at [verify.meshqu.com](https://verify.meshqu.com).
- A long-form writeup published at `meshqu.com/research/<slug>/`.
- An open repository (this one) carrying the harness, sample-selection criteria, system prompts, and the receipt corpus.

The methodology is intentionally public. The abstracted, reusable form now lives in [`methodology/`](methodology/) — extracted once a second worked application (E2 / MRP-2026-03) provided a second anchor point to triangulate the abstraction from. Per-piece methodology detail still lives alongside each experiment trail (e.g. [`procurement-decisions/planning/`](procurement-decisions/planning/) — substrate adapter, evaluation pipeline, policy authoring). The research-process discipline that wraps the method — pre-registration gates, anti-claims, publication-parity checklist — lives in [`programme/`](programme/). Client engagements applying this methodology to private data live in separate, client-specific repositories that import the methodology as a dependency. The techniques are auditable; the engagements are confidential.

## What this repo is NOT

- Not a product changelog. MeshQu's product changes ship through other channels.
- Not a customer case study collection. Each piece is the experimenter's good-faith application of public regulatory frameworks to public data, not a vendor demonstration.
- Not a peer-reviewed academic publication. It is engineering-credible research published under the [Stripe-style commercial research convention](https://stripe.com/blog).

## Pieces in this repo

### procurement-decisions

An LLM agent reviews 300 public UK procurement filings and proposes compliance verdicts. MeshQu evaluates each decision against a documented policy synthesised from the UK Procurement Act 2023, the Procurement Regulations 2024, EU Directive 2014/24/EU, and US FAR. One rule is a faithful implementation of PA23 s.53 (30-day Contract Details Notice publication obligation); the other five are illustrative composites with per-rule framework provenance. Every decision produces a signed receipt anchored to Sigstore Rekor and verifiable offline at verify.meshqu.com.

Status: published as MRP-2026-02 (2026-05-18). Planning trail, methodology documentation, and corpus artefacts in [`procurement-decisions/`](procurement-decisions/); per-piece publication-discipline lineage in [`procurement-decisions/planning/decision_log.md`](procurement-decisions/planning/decision_log.md).

### procurement-context-gradient

The second worked application. Reuses E1's corpus, model, policy snapshot, and substrate adapter unchanged, and varies one thing — the governance context the agent sees — across a strictly additive five-rung ladder (L0 baseline → L4 full policy text). The headline finding is non-monotonic: the precedent-receipt rung (L3) is where the agent's verdicts first commit at scale, and the full-policy rung (L4) partially pulls that commitment back. Two pre-registered predictions were falsified in the inverted direction, and a 14-record adversarial Permuted-Policy diagnostic surfaced inversion-blindness (the agent reasons against a rule's semantic intent rather than the literal inverted operator).

Status: published as MRP-2026-03 (2026-05-27) at `meshqu.com/research/procurement-context-gradient/`. Corpus, analysis notebooks, findings, and writeup in [`procurement-context-gradient/`](procurement-context-gradient/).

## Methodology lineage

The first version of this methodology was developed inside MeshQu's monorepo as a planning harness, then extracted to this public repo before predictions lock so the pre-registration commit is publicly auditable from the moment it lands. The lineage trail and decision history live in [`procurement-decisions/planning/decision_log.md`](procurement-decisions/planning/decision_log.md).

## Licence

MIT — see [`LICENSE`](LICENSE).
