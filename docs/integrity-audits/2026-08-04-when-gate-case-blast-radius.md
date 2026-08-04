# Integrity Audit IA-2026-03 — When-gate case-sensitivity blast radius over the published E1–E3 corpus

**Verdict: CLEAN — pinned by test.** Zero case-variant, whitespace-variant, or type-variant
values exist between any gate literal in the ratified pack and any value at a gated field
path across all 3,044 published receipts, and the published outcomes are byte-identical to
what the case-folded (fixed) gate semantics would have produced. No published E1–E3 result
was affected by the defect. The scan is committed as a mechanical pin
([`scripts/check_gate_case_collisions.py`](../../scripts/check_gate_case_collisions.py))
that fails on any future corpus introducing a collision.

**Date:** 2026-08-04
**Auditor:** investigative agent session, commissioned and reviewed by Sam Carter (MeshQu)
**Affects:** MRP-2026-02 (E1), MRP-2026-03 (E2), MRP-2026-04 (E3)
**Defect under audit:** tradequ #761 — the engine's `when`-gate comparisons are strict
(`value === when.equals` and `when.in.includes(value)` in
`packages/meshqu-core/src/rules/when.ts`, lines 27 and 31; no case folding). A case or
whitespace mismatch between a gate literal and a record value silently disqualifies the
rule (NA), producing **fewer** violations and possibly a silent ALLOW.
**Question:** could that defect have affected any published E1–E3 result?
**Disposition:** **Confirmed** (published violation counts and verdicts are exactly what
the intended rule applicability produces; the defect had zero blast radius on this corpus)

> The defect's direction is one-way: any impact means published violation counts are
> **understated**. Because re-evaluation today shares the same strict semantics
> (`evaluatePure` gates through the same `evaluateWhen`), the corpus reproducing today
> proves nothing about this question. The audit therefore does not ask "do the numbers
> reproduce" — it asks "did any rule the ratified pack *intended* to fire silently never
> fire because of casing," and answers it by exhaustive enumeration, not sampling.

## 1 · Scope and pins

### (a) The pack — one ratified snapshot binds all three experiments

The three experiments did not ratify three packs. Every one of the 3,044 published
bundles embeds a `policy_snapshot.json` that is **byte-identical** (SHA-256-identical)
to the committed snapshot, and every signed result binds the same digest in its
`policy_snapshot_digest` field:

| Pin | Value |
|---|---|
| Snapshot id | `cbf12348-6248-48f7-a06f-4e0304cc237e` |
| Snapshot file | [`procurement-context-gradient/policy/policy-snapshot-cbf12348.json`](../../procurement-context-gradient/policy/policy-snapshot-cbf12348.json) |
| Snapshot SHA-256 | `5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d` |
| `policy_rules_hash` (= `evaluated_rules_hash` in every signed result) | `1c16d2f4bc19aea799bd4e646109bce78b354b6f6d0900058c4c6341b173163c` |
| Ratification (`approval_receipt_digest`) | `e7081f5e7aaf54b5202503ce36a8f3bad0b0c5424dbeda02fe9102a490a0e58e` |
| Embedded-snapshot byte-identity | E1 283/283 · E2 1,429/1,429 · E3 1,332/1,332 |
| Signing key (`signature_kid`, all receipts) | `meshqu-experiment-procurement-2026-05` |

Per-experiment provenance of the same pack: E1 records it in every bundle (its `policy/`
directory is empty by design); E2 commits the snapshot file itself; E3's
[`policy/README.md`](../../procurement-context-disambiguation/policy/README.md) points
back to E2's snapshot and digest. `data/DATA_MANIFEST.json` states the same digest for
all 3,044 receipts. All four sources agree.

### (b) The corpora — published files, re-hashed at audit time

All digests below were recomputed during the audit and match `data/DATA_MANIFEST.json`:

| Artefact | SHA-256 | Contents |
|---|---|---|
| `procurement-decisions/results/corpus.tar` (E1) | `1b6192df6eb5d3c38738b6abc5cea82c92d99d53ae890308569a4c240c232be0` | 283 receipts |
| `procurement-context-gradient/results/corpus.tar` (E2) | `2c77dac05b329c20d2d2cada22a54dc96f00f39e2ae3b46c14ffe10d4c0bcf36` | 1,429 receipts |
| `procurement-context-disambiguation/results/corpus.tar` (E3) | `96ca50d8e9f8f61b38032d1dcc4a18c95ed9d150215b3e0354761b423da5dda0` | 1,332 receipts |
| `data/source_records.json` | `0bf225b8e5260bb76b954e3fafd60f132c163b643213b60b4926b855fb64ed6b` | 283 records |

The scan reads the evaluated contexts (`receipt.json → context.fields`) out of the
bundles — the values the engine actually gated on — with `data/source_records.json`
enumerated as an upstream cross-check. Tar listing uses Python `tarfile` (bsdtar hides
the 285 AppleDouble sidecars in the E1 tar).

### (c) Engine semantics at the run commits — identical to today's, three ways

1. **Git history.** The strict comparisons were introduced with the `when`-gating
   feature itself (tradequ `2d50b732`, `334055dd`, both 2026-02-09) and have never been
   modified since — the only subsequent touches are `c9f0d86a` (2026-02-11) and the
   package rename `3f78139e` (2026-05-09), neither changing a comparison. `when.ts` at
   tradequ `origin/main` (`b22c97bf`) hashes to
   `c1390eba283ddc9272f6c9656814afedfeed3bcfef333d324c726699bd143c96`. Every deployable
   commit between the feature's birth and today therefore carries the same gate
   semantics; the three evaluation windows — E1 2026-05-18, E2 2026-05-22, E3
   2026-05-29 (signed `result.timestamp` ranges) — all fall inside that span. **The
   semantics did not differ across the three runs.**
2. **Version pin.** Every bundle manifest records `evaluator_version: 1.2.0`, which is
   `@meshqu/core`'s version at audit time.
3. **Behavioural pin.** For all 3,044 receipts, the recorded `result.na_rules` set
   equals the NA set predicted by applying today's strict semantics to the receipt's
   own `context.fields` (0 mismatches). The published corpus behaves exactly as the
   pinned code reads.

The server-side `evaluate()` that minted the receipts shares its verdict loop — rule
iteration and `when`-gating included — with the browser-safe `evaluatePure()`
(single source of truth, `packages/meshqu-core/src/evaluator.ts`), both routing gate
checks through `evaluateWhen`.

## 2 · Gate inventory

The ratified pack contains **five `equals` gate literals across four field paths, and
zero `in` gates**. All five literals are lowercase strings:

| Rule | Gate |
|---|---|
| PROC-001-S53 | `governed_by_pa23 equals "true"` **and** `above_threshold equals "true"` |
| PROC-005-OPEN-TENDER | `above_threshold equals "true"` **and** `direct_award_justification_present equals "false"` |
| PROC-006-MOD-CAP | `is_modification equals "true"` |

PROC-004-COI carries an `exists` gate (no literal — no case exposure; included in the
§4 behavioural check, NA on every record because UK Contracts Finder OCDS has no COI
field). PROC-002-AUTHORITY and PROC-003-DEBARMENT have no `when` gate and are always
applicable. PROC-003's condition-level list is Appendix A — different semantics,
never mixed into this analysis.

## 3 · Collision table

Every distinct raw value at every gated field path, across every published receipt,
classified against the gate literal (`n` = receipt occurrences; distinct-value sets
shown exhaustively — there are exactly two distinct values per field, both lowercase
strings, in every experiment):

| Corpus | Rule | Field | Literal | Value | Type | n | Class |
|---|---|---|---|---|---|---|---|
| E1 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"false"` | str | 10 | NO |
| E1 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"true"` | str | 273 | EXACT |
| E1 | PROC-001-S53 | above_threshold | `"true"` | `"false"` | str | 141 | NO |
| E1 | PROC-001-S53 | above_threshold | `"true"` | `"true"` | str | 142 | EXACT |
| E1 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"false"` | str | 141 | NO |
| E1 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"true"` | str | 142 | EXACT |
| E1 | PROC-005-OPEN-TENDER | direct_award_justification_present | `"false"` | `"false"` | str | 283 | EXACT |
| E1 | PROC-006-MOD-CAP | is_modification | `"true"` | `"false"` | str | 283 | NO |
| E2 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"false"` | str | 50 | NO |
| E2 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"true"` | str | 1379 | EXACT |
| E2 | PROC-001-S53 | above_threshold | `"true"` | `"false"` | str | 722 | NO |
| E2 | PROC-001-S53 | above_threshold | `"true"` | `"true"` | str | 707 | EXACT |
| E2 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"false"` | str | 722 | NO |
| E2 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"true"` | str | 707 | EXACT |
| E2 | PROC-005-OPEN-TENDER | direct_award_justification_present | `"false"` | `"false"` | str | 1429 | EXACT |
| E2 | PROC-006-MOD-CAP | is_modification | `"true"` | `"false"` | str | 1429 | NO |
| E3 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"false"` | str | 52 | NO |
| E3 | PROC-001-S53 | governed_by_pa23 | `"true"` | `"true"` | str | 1280 | EXACT |
| E3 | PROC-001-S53 | above_threshold | `"true"` | `"false"` | str | 674 | NO |
| E3 | PROC-001-S53 | above_threshold | `"true"` | `"true"` | str | 658 | EXACT |
| E3 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"false"` | str | 674 | NO |
| E3 | PROC-005-OPEN-TENDER | above_threshold | `"true"` | `"true"` | str | 658 | EXACT |
| E3 | PROC-005-OPEN-TENDER | direct_award_justification_present | `"false"` | `"false"` | str | 1332 | EXACT |
| E3 | PROC-006-MOD-CAP | is_modification | `"true"` | `"false"` | str | 1332 | NO |

**Class totals over all gate × receipt occurrences: EXACT 8,990 · NO 6,230 ·
CASE-VARIANT 0 · WHITESPACE-VARIANT 0 · TYPE-VARIANT 0 · ABSENT 0.** Every `NO` is a
clean opposite (`"false"` against `"true"` or vice versa) — the intended NA, not a
casing artefact. `data/source_records.json` enumerates identically: only `"true"` /
`"false"` strings at all four gated field paths across all 283 records.

This emptiness is by construction, not by luck: the substrate adapter string-encodes
every gated flag as lowercase `"true"`/`"false"` (visible in each record's
`substrate_notes`), and the pack's literals were written to match.

## 4 · Null delta, proven directly

Although the empty collision table already resolves the question, the fixed semantics
were run anyway. For every one of the 3,044 receipts, rule applicability was computed
two ways from the receipt's own `context.fields`: (a) strict, mirroring
`evaluateWhen` today, and (b) case- and whitespace-folded on strings only, mirroring
the approved #761 fix direction. Results:

- **(a) vs recorded:** predicted NA set equals the receipt's signed `na_rules` on
  **3,044 / 3,044** receipts.
- **(b) vs (a):** identical NA sets on **3,044 / 3,044** receipts — the folded engine
  gates nothing differently, so it fires the same rules, finds the same violations,
  and reaches the same verdicts.
- **Violation count re-derived from receipts: 2,740** — equal to
  `violations.parquet`'s row count in `data/DATA_MANIFEST.json`.
- **Verdict totals re-derived:** E1 144 ALLOW / 139 DENY; E2 737 / 692; E3 688 / 644 —
  consistent with the splits IA-2026-02 confirmed (E1 144/139; E2/E3 146/137 per
  283-record condition).

The delta between published results and case-folded results is therefore **zero
records, zero violations, zero verdicts** — measured, not inferred. Steps 3–4 of the
audit method (impact re-evaluation and published-claims trace) are closed with nothing
to trace; the IA-2026-02 correction playbook is **not** invoked.

## Appendix A · Condition-level list rules (different semantics — not part of the finding)

Condition-level list rules case-fold **by default** (`case_sensitive ?? false`,
`@meshqu/core` `rules/list.ts`) — the opposite default from gates, and not the #761
defect class. Reported separately for completeness:

- **PROC-003-DEBARMENT** (`supplier_id` against a 3-entry sanctions/debarment list):
  237 distinct `supplier_id` values per experiment, `supplier_id` present on every
  record, **zero matches under folded or strict comparison** — the rule never fired
  and no near-miss exists in either semantics.

## Anti-claims — what this audit does not establish

- It does **not** cover the S1 pack, workbench, or any non-E-series corpus. E-series only.
- It does **not** clear future corpora — that is the pin test's job, at ingestion, every time.
- It does **not** pin which git commit of the API was deployed during each run; no
  public artefact records that. What is pinned instead (§1c) is stronger for this
  question: the comparison semantics never changed over the file's entire history, the
  bundles record the evaluator version, and all 3,044 recorded NA sets match today's
  semantics exactly.
- It does **not** revise, or call for revising, any receipt, signature, verdict, pack,
  paper, or export. Zero published artefacts were modified.
- It does **not** take a position on whether string-encoded booleans (`"true"` /
  `"false"`) are the right substrate encoding — only that the encoding is uniform and
  collision-free in this corpus. A future substrate emitting real booleans against
  string literals would surface as TYPE-VARIANT in the pin test.

## Going forward (closure track)

- **Pin test** — [`scripts/check_gate_case_collisions.py`](../../scripts/check_gate_case_collisions.py)
  re-runs this scan mechanically: corpora and digests from `data/DATA_MANIFEST.json`,
  gate inventory from each bundle's own embedded snapshot (future packs covered
  automatically), full distinct-value enumeration, exit 1 on any CASE / WHITESPACE /
  CASE+WS / TYPE variant. Run it on every corpus addition before regenerating
  exports; a failure means a new collision entered at ingestion. Classifier
  self-test: `--self-test`. *(Closed — this change.)*
- **#761 fix interaction.** The approved fix is an opt-in `case_sensitive` key on
  gates with absent-means-strict semantics, so the ratified pack's behaviour — and
  this CLEAN verdict — is unchanged on both sides of the fix landing. No pack edit,
  re-ratification, or erratum is required. *(Closed — no action.)*

## Audit trail

- Gate semantics: tradequ `packages/meshqu-core/src/rules/when.ts` lines 27 (`===`)
  and 31 (`includes`); history via `git log --follow -p` (commits `2d50b732`,
  `334055dd`, `c9f0d86a`, `3f78139e`); `origin/main` = `b22c97bf` at audit time.
  Shared verdict loop: `packages/meshqu-core/src/evaluator.ts` (comment at the loop),
  `evaluate-pure.ts` line 268. List-rule folding: `packages/meshqu-core/src/rules/list.ts`.
- Pack: snapshot file at §1(a) path; digest recomputed with `shasum -a 256`;
  per-bundle byte-identity by SHA-256 of the embedded `files["policy_snapshot.json"]`
  string across all 3,044 bundles; `result.policy_snapshot_digest` and
  `result.evaluated_rules_hash` read from every signed receipt.
- Corpora: the three `corpus.tar` files and `data/source_records.json`, digests at
  §1(b), iterated with Python `tarfile`, skipping `._*` AppleDouble members;
  contexts parsed from `files["receipt.json"]`.
- Collision scan and null-delta check: exactly the committed
  `scripts/check_gate_case_collisions.py` (collision half) plus the §4 folded/strict
  NA-set comparison; both re-runnable from a clean checkout with stdlib Python.
- Published-figure cross-checks: `data/DATA_MANIFEST.json` (receipts 283/1,429/1,332,
  violations 2,740); IA-2026-02 §2(a) (verdict splits).
