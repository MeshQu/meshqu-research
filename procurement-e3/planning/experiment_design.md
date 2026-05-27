# Experiment 3 (E3) — experiment design

**Status**: placeholder. Pre-registration lock has not happened.

This document will hold E3's locked design at the pre-registration boundary. Until then it is a working scratchpad for scope decisions.

## Open scope decisions (must close before lock)

The carry-forward design asks from E2 (§8, §11) form a menu, not a commitment. Pick a coherent subset for E3:

- [ ] **L3.5 receipts-only variant** — central disambiguator for E2's Reading A vs Reading B (precedent-rung anchoring vs L4-nudge-load-bearing)
- [ ] **Larger Permuted-Policy diagnostic** (target n ≥ 100, hand-coded reasoning rubric)
- [ ] **Authoritative-vs-hypothetical framing axis** — isolates the "authority-conditioned" qualifier
- [ ] **Cross-model replication** — adds at least one of Claude / Gemini
- [ ] **Investigative-agent variant** — the bigger leap (per §11)
- [ ] **L4-without-nudge variant** — disambiguates Framing A.1 vs A.2 from E2 §5

A defensible E3 covers some subset of the first four (static-record format, sharpens E2's open readings). The fifth — investigative-agent — is a format shift and probably warrants its own paper (E3.5 or E4).

## Substrate decision

- [ ] **Same 283-record corpus** (closes the substrate-variable confound; lets E3 cleanly compare against E2)
- [ ] **Expanded corpus** (e.g. add direct-award records, which E1 noted were under-represented)
- [ ] **New substrate domain** (e.g. AML/KYC/clinical-decision — the cross-domain generalisation called out in E2 §10/§11)

Cross-domain replication is a strong contribution but doubles the methodology overhead (new substrate adapter + new policy authoring pass). May be E4-shaped rather than E3.

## Model decision (cross-model replication)

- [ ] Stick with the locked agent `gpt-5.4-2026-03-05` for direct comparability with E1+E2
- [ ] Add **Claude** (which version?) as second model
- [ ] Add **Gemini** as second model
- [ ] Both

Cross-model replication is the cleanest test of whether E2's findings are model-property or task-class-property. But two models = ~2x the corpus collection cost.

## Pre-registration lock checklist (per PROCESS.md gate)

When ready to lock:

- [ ] Predictions specified at segment level (per E2 retrospective — not aggregate-trend like P1/P2)
- [ ] Falsification criteria numeric and specific
- [ ] Disposition vocabulary locked (Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested)
- [ ] All prompts SHA-bound and committed
- [ ] Policy snapshot SHA-bound
- [ ] Adversarial diagnostic spec'd
- [ ] Working title committed (or placeholder with intent)
- [ ] Git tag created: `v0.X-predictions-locked`

## Architectural carry-forwards (defaults from E2; revisit per E3 scope)

- Strict additivity if E3 includes a ladder
- Level-batching execution order
- Frozen-archive isolation for any precedent material
- Permuted-Policy diagnostic format (or scaled version)
- Bundle envelope schema (likely BUNDLE_ENVELOPE_VERSION=1 still, or bumped if E3 adds fields)
