# Project Context — Agentic Procurement Experiment

> Orientation for a fresh agent (or future-self) picking this up.
> Read this before reading any other file in the harness.

## The one-sentence summary

We are designing an experiment where an LLM agent reviews real public procurement filings, MeshQu enforces a policy snapshot against each agent decision, and the resulting corpus of signed receipts becomes the centrepiece of a public writeup demonstrating what an AI-assisted decision's audit trail actually looks like.

## What success looks like

A reader who is an engineer at a regulated firm can:

1. Read the title plus opening section and decide whether to keep reading. ~60 seconds.
2. Read the methodology and rebuild it themselves. ~3 minutes to scan, ~1 evening to run.
3. Verify the receipt corpus offline. ~2 minutes.
4. Forward it internally to their compliance partner with a one-line summary.
5. Cite the experiment in their own work.

If those five hold for a handful of readers at MeshQu's target firms, the artefact has done its job.

The audience priority is engineer-first. Engineers read it, forward it to compliance. Writing to compliance leads as the primary reader drifts the voice into consultant-register and breaks engineering credibility.

## What failure looks like (so we can design against it)

| Failure mode | Why it matters | Pre-mitigation |
|---|---|---|
| MeshQu catches nothing interesting | The corpus is dull; no story to tell | Design the agent loop so it has natural reasons to want to take actions the policy would catch. don't sanitise the inputs |
| The writeup reads as a benchmark of the LLM | Makes the LLM the protagonist, not MeshQu | Frame: "what does a defensible audit trail of an AI decision look like". never "how accurate is the AI" |
| Results can't be reproduced | Credibility collapses | Pin the agent model + version, freeze the policy snapshot, publish the inputs |
| Substrate has hidden PII / sensitive content | Reputational and legal risk | Use only data already published under open-data licences; document the licences |
| Predictions cherry-picked after running | The whole experimental shape collapses | Pre-register publicly, with timestamps, before any run |

## What MeshQu primitives we lean on (all already shipped)

- **Policy versions + ratification** — author a policy with documented severity tiers, ratify a version, freeze a snapshot.
- **Decision evaluation** (`POST /v1/decisions/record`) — agent proposes a decision; MeshQu evaluates against the snapshot.
- **Receipts** — v2 envelope with `policy_snapshot_digest`, ed25519 signature, integrity hash.
- **Decision chains** — when an agent's reasoning involves multiple steps, chain the receipts.
- **Verification bundle** (`GET /v1/receipts/:id/bundle?format=tar`) — self-contained archive for offline verification.
- **verify.meshqu.com** — public offline verifier.

What's intentionally NOT used yet (deferred to the AARM roadmap):

- **C1 classification** — would let us label rules as `forbidden | context_deny | context_defer`. Useful but the experiment can read four severity tiers without it.
- **C5 identity binding** — would put `model_id` + `model_version` into the receipt context cryptographically. We'll record them in `metadata` instead until C5 ships; the writeup notes this as "today's posture vs near-future".
- **C2/C3 MODIFY/DEFER verdicts** — would split today's `REVIEW` more cleanly. Not needed for the experiment.

## What's open data we can lean on

Three primary candidates, in rough order of preference. See `substrate.md` for the full sourcing plan.

1. **UK Contracts Finder + Find a Tender** — the UK government's published procurement records. Daily-updated, open license (OGL v3.0), CSV + API. Probably the cleanest first option.
2. **EU TED (Tenders Electronic Daily)** — pan-EU procurement, structured XML, open. Higher complexity but much larger corpus.
3. **US SAM.gov** — federal procurement records. Open API, less clean schema, US-specific terminology.

Avoid datasets that mix in PII, classified content, or restricted-use clauses.

## What policies we author for the experiment

**One faithful rule, five composites.** The policy under test mixes a single faithful implementation of a named UK statute with five composites synthesised across named regimes. This is a deliberate credibility move: a single real-regulation worked example anchors the writeup against actual statutory text, while the composites stay broad enough to fire across the full 300-record corpus.

- **`PROC-001-S53` — 30-day Contract Details Notice publication** (threshold + when, critical). **Faithful implementation** of Procurement Act 2023 s.53 + Procurement Regulations 2024. When a contract is PA23-governed and a Contract Details Notice exists, the publication delay (notice publication date minus contract award date) must be ≤ 30 days. Evaluated against the proxy-identified PA23 subset of the corpus (contract award date after 2025-02-24). Pivoted from the original `PROC-001-S44` after Phase 0 / Phase 0.5 spikes; rationale in `decision_log.md`.
- **`PROC-002-AUTHORITY` — Award-threshold authority** (threshold, critical). *Composite.* UK PA23 delegated-authority frameworks; EU 2014/24/EU Art. 4.
- **`PROC-003-DEBARMENT` — Sanctions / debarment check** (list, critical). *Composite.* UK PA23 Schedule 6; EU 2014/24/EU Art. 57; FAR 9.4.
- **`PROC-004-COI` — Conflict-of-interest disclosure** (presence, high). *Composite.* UK PA23 s.81; EU 2014/24/EU Art. 24; FAR 3.101.
- **`PROC-005-OPEN-TENDER` — Open-competition requirement** (threshold + when, critical). *Composite.* UK PA23 default-competition principle; EU 2014/24/EU thresholds.
- **`PROC-006-MOD-CAP` — Modification cap** (threshold + when, high). *Composite.* UK PA23 s.74; EU 2014/24/EU Art. 72.

The writeup is explicit: `PROC-001-S53` is a faithful implementation of a specific named UK statutory time-window; the other five are illustrative composites with per-rule framework provenance shown in `experiment_design.md`. This converts the artefact from "interesting composite study" to "study with one real-regulation worked example, plus illustrative composites."

## Methodology reusability

The methodology developed here is intentionally public. The substrate adapter pattern, evaluation pipeline built on Inspect AI, policy authoring playbook, and pre-registration discipline are reusable components published under `meshqu-research/methodology/` in the same repo as this experiment. They are the credibility layer.

Client engagements applying this methodology to private data live in separate, client-specific repositories that import the methodology as a dependency. That separation matters: the techniques are auditable, the engagements are confidential. A prospective client engaging MeshQu can read the methodology, audit the code, see the published worked example on public data, and engage MeshQu to apply the methodology to their archive with the confidence that the methodology has survived public scrutiny.

The procurement-decisions piece is the first worked application. It also serves as MeshQu's first public proof of production-scale operation (see [experiment_design.md](experiment_design.md), "The experiment as MeshQu product proof"). The spike-before-commit discipline that produced this design is part of what generalises — feasibility analysis precedes pre-registration in any future application of this methodology, not just this experiment.

This experiment makes no claim about specific future applications. Adjacent domains are mentioned generically in the writeup's "what's next" section; no specific engagements are named anywhere in this harness.

## What's a "MeshQu catch" and what isn't

The experiment's signal lives in the receipt corpus. A "catch" is a decision where:

- The agent recommended ALLOW
- MeshQu's evaluator returned DENY or REVIEW based on the snapshot's rules
- A human reviewing the receipt afterward can validate the rule fired correctly

The experiment will also surface:

- **False positives** — MeshQu DENY where a human reviewer agrees the agent's ALLOW was actually correct. Reported honestly; this is the trade-off of any rule-based system.
- **Drift** — when the agent's reasoning narrative diverges from what the policy enforces. This is more interesting than pure violations because it's the case where the agent confidently rationalises past the rule.
- **Reproducibility** — same input + same snapshot = same decision. Demonstrated by re-running a subset.

All findings — from anomalies to drift cases to reproducibility numbers — accumulate in [`procurement-decisions/results/`](../results/README.md) under the execution-capture and notebook discipline committed at revision brief 10. Per-decision audit traces live in `results/audit/`; observations and findings live in `results/notebook/`; the writeup quotes from this directory rather than reconstructing.

## What's explicitly NOT in scope

- No customer data. No customer commitments.
- No production data. The experiment runs in a dedicated MeshQu tenant on the staging environment, fully isolated from any production tenants.
- The methodology developed here is intentionally generalisable, but this experiment makes no claim about specific future applications. Any future client engagement using this methodology will be its own separately-scoped piece of work.
- No claim that this experiment validates MeshQu for any specific regulator's compliance framework. The experiment is informed by UK Procurement Act 2023, Procurement Regulations 2024, PPN 02/24, PPN 017, and the UK Government AI Playbook, but does not claim compliance certification under any of these instruments. The writeup positions the experiment as illustrative, not certificatory.
- No claim that the AI agent is fit for production procurement decisions. The agent is a substrate for generating decisions to record, not the protagonist.
- No new product features. This is a pure use of shipped primitives.

## Branch / commit conventions

- Branch: `agentic-procurement-experiment/<phase>` if any code lands in the monorepo. Most of this experiment lives in a separate public repo (to be created when execution starts).
- Task ID prefix (when execution starts): `APE-`.

## When to refer to this harness vs the main roadmap

- **This harness**: anything related to running and publishing the experiment.
- **`.harness/aarm-roadmap/`**: anything related to MeshQu's product capability roadmap. The experiment is read-only on that roadmap; it doesn't reshape it.
- **`MESHQU_AARM_FEATURE_ANALYSIS.md`**: the underlying analysis the roadmap is built on.

## References

- [README.md](README.md) — top-level summary, why-procurement reasoning
- [experiment_design.md](experiment_design.md) — methodology
- [predictions.md](predictions.md) — pre-registered predictions (to be filled in BEFORE any runs)
- [substrate.md](substrate.md) — data sourcing
- [writeup_outline.md](writeup_outline.md) — the artefact, with Sam's locked voice-calibration reference
- [`.harness/aarm-roadmap/`](../aarm-roadmap/) — the broader product roadmap this experiment doesn't depend on
- [verify.meshqu.com](https://verify.meshqu.com) — where readers will verify the receipt corpus
