# meshqu-research

Public research surface for [MeshQu](https://meshqu.com).

This repository carries applied research on AI-assisted decision-making in regulated contexts. Each piece is a worked application of an audit-grade decision-receipt methodology to a specific public-record substrate. The methodology layer is reusable across pieces and across future client engagements.

## What's here

```
meshqu-research/
├── procurement-decisions/   # First worked application: AI-assisted UK procurement compliance review
└── methodology/             # Reusable components shared across pieces
    ├── substrate-adapter/   # Source-agnostic ingestion abstraction
    ├── evaluation-pipeline/ # Inspect AI integration + receipt production
    └── policy-authoring/    # Playbook for going from named regulatory frameworks to ratified MeshQu policy snapshots
```

## What this repo is

A public, MIT- or Apache-2.0-licensed research surface. Each piece is published with:

- A pre-registered set of predictions, committed before the experiment runs, with the commit hash linked from the writeup.
- A documented methodology covering substrate, agent, evaluation pipeline, and limitations.
- A signed receipt corpus that readers can verify offline at [verify.meshqu.com](https://verify.meshqu.com).
- A long-form writeup published at `meshqu.com/research/<slug>/`.
- An open repository (this one) carrying the harness, sample-selection criteria, system prompts, and the receipt corpus.

The methodology is intentionally public. The components under `methodology/` are reusable. Client engagements applying this methodology to private data live in separate, client-specific repositories that import the methodology as a dependency. The techniques are auditable; the engagements are confidential.

## What this repo is NOT

- Not a product changelog. MeshQu's product changes ship through other channels.
- Not a customer case study collection. Each piece is the experimenter's good-faith application of public regulatory frameworks to public data, not a vendor demonstration.
- Not a peer-reviewed academic publication. It is engineering-credible research published under the [Stripe-style commercial research convention](https://stripe.com/blog).

## Pieces in this repo

### procurement-decisions

An LLM agent reviews 300 public UK procurement filings and proposes compliance verdicts. MeshQu evaluates each decision against a documented policy synthesised from the UK Procurement Act 2023, the Procurement Regulations 2024, EU Directive 2014/24/EU, and US FAR. One rule is a faithful implementation of PA23 s.53 (30-day Contract Details Notice publication obligation); the other five are illustrative composites with per-rule framework provenance. Every decision produces a signed receipt anchored to Sigstore Rekor and verifiable offline at verify.meshqu.com.

Status: planning + pre-registration. See [`procurement-decisions/`](procurement-decisions/) for the full planning harness and methodology documentation.

## Methodology lineage

The first version of this methodology was developed inside MeshQu's monorepo as a planning harness, then extracted to this public repo before predictions lock so the pre-registration commit is publicly auditable from the moment it lands. The lineage trail and decision history live in [`procurement-decisions/planning/decision_log.md`](procurement-decisions/planning/decision_log.md).

## Licence

TBD — MIT or Apache-2.0. To be added before initial commit.
