# Finding 002 — PROC-004-COI was firing on field absence; gated behind `exists: true` after the smoke

**Created:** 2026-05-17
**Status:** stable
**Bears on:** methodology, P2

## The claim

The originally-ratified policy (`policy_snapshot_id = c6256a8e-…`) fired PROC-004-COI on every record produced by the OCDS substrate, because OCDS does not carry `conflict_of_interest_declaration` and PROC-004 was a presence-rule that fired on field absence. This collapsed the MeshQu headline verdict to a constant DENY across the 3-record smoke and would have made the agreement projection degenerate at the 300-record full-run scale. The policy was clarified with a `when: {field: 'conflict_of_interest_declaration', exists: true}` gate so PROC-004 evaluates only when the field is present, NA otherwise. A new snapshot was ratified (`cbf12348-…`); the post-clarification smoke produced the design-spec verdicts.

The clarification is methodologically defensible (not pre-registration goalpost-moving) because: (a) no corpus data existed at the time of the edit, (b) PROC-001-S53 — the rule actually under test — was untouched, (c) the absence-doesn't-fire intent was already documented in the schema docstring before the smoke, and (d) the alternative (leave + document) would have made the experiment LESS interpretable, not more.

## Evidence

- Pre-clarification snapshot `c6256a8e-55ae-41ba-a265-2d61211e0ca9` referenced by smoke run `smoke-0507305a-ed44-4882-b455-a720fee8e603`. Verdicts: A=DENY (PROC-004-COI only), B=DENY (PROC-001-S53 + PROC-004-COI), C=DENY (PROC-004-COI only). PROC-001-S53 fired correctly on B's 35-day delay; PROC-004-COI fired uniformly across all three.
- Documented authorial intent (before smoke): `runner/contracts/decision_context.schema.json` line for `conflict_of_interest_declaration` carried the line *"Today: omitted, PROC-004 cannot fire."* The behaviour-vs-intent gap is what the smoke surfaced.
- Decision: [`planning/decision_log.md`](../../planning/decision_log.md) entry "Post-smoke policy clarification: gate PROC-004-COI behind `exists`" (PR #24, `5ba137c`). PR #25 (`f9acc57`) filled the post-clarification snapshot id.
- Editor knob used: v2 console editor's operator dropdown labelled "exists" ([`apps/meshqu-console/src/components/policies/rule-editor-v2/inline-editor.tsx:1263`](https://github.com/MeshQu/tradequ/blob/main/apps/meshqu-console/src/components/policies/rule-editor-v2/inline-editor.tsx#L1263)). Backed by [`packages/meshqu-core/src/rules/when.ts:34-37`](https://github.com/MeshQu/tradequ/blob/main/packages/meshqu-core/src/rules/when.ts#L34-L37); NA-reason formatter renders "conflict of interest declaration is missing".
- Post-clarification snapshot `cbf12348-6248-48f7-a06f-4e0304cc237e`. Smoke run `smoke-d5787f81-18a8-448e-981a-a54398f0ab25`: A=ALLOW, B=DENY (PROC-001-S53 only), C=ALLOW. Design-spec verdicts. Confirmed at 10-record scale by dry-run `dry-run-0223ad77-01e6-40e0-ada7-0cbf9da4a491`.

## Caveats

- This is an edit to the ratified policy AFTER predictions were locked (`v0.1-predictions-locked`, 2026-05-15) but BEFORE any corpus data was collected (first corpus run begins 2026-05-18). The decision-log entry argues the defensibility case in full and reserves the pre-clarification snapshot id forever as audit trail.
- Out-of-scope edits explicitly NOT made: PROC-001-S53 stays frozen (it is the rule under test); PROC-002 / PROC-003 / PROC-005 / PROC-006 stay frozen (smoke surfaced no behaviour mismatches on them; absence of evidence is not licence to edit); the substrate adapter stays frozen (its honest-omission of COI is correct — OCDS doesn't carry it).
- The 3 receipts under the pre-clarification snapshot stand as audit evidence of why the clarification was made. They are NOT discarded — they form the empirical record. Receipts in the full-run corpus all bind to `cbf12348-…`; pre-clarification receipts are trivially distinguishable by `policy_snapshot_id`.
- For PROC-004 to ever fire on the OCDS substrate, the substrate adapter would need to be extended (a future-variant move per the schema docstring). That extension is out of scope for this experiment.

## What this changes about the writeup

P2 (rule-firing distribution) needs a callout that PROC-004 is structurally NA across this corpus, not absent because no record violated it. Section 7 (limitations) gets a paragraph on the substrate-policy alignment gap and how the smoke surfaced it before corpus collection. Methodology section can cite this as an example of the smoke/dry-run-then-corpus discipline working as designed — the predictions-lock principle requires the rules to be fixed in advance, but it does NOT require shipping known mis-wirings through to the corpus when the smoke catches them.

## Full-scale empirical confirmation — 2026-05-18 corpus run (n=283 unique decisions)

The 300-record corpus run (`dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`, effective n=283 after OCDS dedup) produced **zero PROC-004-COI firings**. Confirmed by the in-app analytics dashboard (PROC-004-COI count = 3 across all-time tenant evaluations, which exactly matches the 3 pre-clarification smoke records under snapshot `c6256a8e-…`) and by direct query of the corpus:

```
$ jq -s 'unique_by(.decision_id) | map(.violations // []) | add | sort \
    | group_by(.) | map({rule: .[0], n: length})' decision_traces.jsonl
[
  { "rule": "PROC-001-S53",         "n": 54 },
  { "rule": "PROC-002-AUTHORITY",   "n": 74 },
  { "rule": "PROC-005-OPEN-TENDER", "n": 131 }
]
```

*[Numbers corrected 2026-05-18 during writeup cross-reference verification. The original `uniq -c` counts (38/43/78) recorded here had inherited from a mid-run dashboard read at ~T+5min (~176 evaluations); the deduped final-corpus counts (54/74/131) are computed via the jq above. The headline finding — PROC-004-COI fires zero times across all 283 post-clarification records — is unchanged and is the load-bearing claim of F002.]*

PROC-004-COI is absent from the violation list across all 283 post-clarification decisions. The `when: {field: 'conflict_of_interest_declaration', exists: true}` gate fires NA on every OCDS-sourced record (because OCDS doesn't carry the field), exactly as designed.

The finding is empirically confirmed at full scale. The clarification has prevented 283 spurious DENYs in this single corpus alone; the proportion would scale linearly with any corpus drawn from this substrate.
