# Pending corrections to `data/DATA_DICTIONARY.md`

**Status: Edits 1-3 APPLIED. Edit 4 DEFERRED, held for the erratum.**

This file exists so that one deferred edit survives until the erratum lands. It
is a work record, not a public description of the corpus — `DATA_DICTIONARY.md`
and `KNOWN_ISSUES.md` are the surfaces a reader should use. **Delete this file
once Edit 4 has been applied.**

Four edits. Two table-row notes and one prose section rewritten (applied), plus
one new prose section (deferred). No number, digest, signature or other file
changes.

**Sequencing decision, founder call:** Edits 1-3 are pure fact-fixing and landed
immediately — they were actively misleading an external replicator. Edit 4
states a consequence about the PROC-005 `when` gate, which is the erratum's
central finding. Landing it standalone first would frame the material finding as
a documentation tweak and force the erratum to re-state it. Edit 4 lands with or
after the erratum, and points at it.

---

## Edit 1 — line 60, table row · APPLIED

**Current**

```
| `direct_award_justification_present` | string | `receipt.context.fields.direct_award_justification_present` | string boolean |
```

**Proposed**

```
| `direct_award_justification_present` | string | `receipt.context.fields.direct_award_justification_present` | string boolean; `"false"` on every row — not measurable in this substrate, see below |
```

---

## Edit 2 — line 61, table row · APPLIED

**Current**

```
| `procurement_method_open_flag` | string | `receipt.context.fields.procurement_method_open_flag` | sparse; null when the source record is silent, see below |
```

**Proposed**

```
| `procurement_method_open_flag` | string | `receipt.context.fields.procurement_method_open_flag` | sparse presence flag; null means the method was not `open`, see below |
```

---

## Edit 3 — line 97, prose section rewritten · APPLIED

**Current**

> ### Deliberate sparsity: procurement_method_open_flag
>
> `procurement_method_open_flag` is present on only 19 of 283 E1 records. The
> source OCDS releases publish the procurement method inconsistently, and the
> substrate adapter passes through only what the source record states. The
> sparsity carries into E2 (95 of 1,429 rows) and E3 (90 of 1,332 rows) because
> both reuse E1's 283 records. This is a property of the public data, not an
> export defect. In the parquet it is a nullable column: null means the source
> record was silent, and no default was filled. The 19-of-283 absence rate is
> itself meaningful. Rule PROC-005-OPEN-TENDER treats absence as evidence
> missing, which is part of the evidence-sparsity story in the writeups.

The two sentences to remove are *"the substrate adapter passes through only what
the source record states"* and *"null means the source record was silent"*. Both
are wrong for 227 of the 264 null records.

**Proposed**

> ### Deliberate sparsity: procurement_method_open_flag
>
> `procurement_method_open_flag` is present on only 19 of 283 E1 records. The
> sparsity carries into E2 (95 of 1,429 rows) and E3 (90 of 1,332 rows) because
> both reuse E1's 283 records. In the parquet it is a nullable column and no
> default was filled.
>
> The column is a presence flag, not a boolean. The substrate adapter emits
> `"true"` when the source record's `tender.procurementMethod` is `open`, and
> emits nothing otherwise; there is no code path that produces `"false"`. Null
> therefore does not mean the source record was silent. It means the procurement
> method was something other than `open` — most often `selective` — or, in a
> minority of records, that the source stated no method at all. Of the 264 null
> records, 227 state a method (207 `selective`, 15 `direct`, 5 `limited`) and 37
> are genuinely silent.
>
> Rule PROC-005-OPEN-TENDER treats the absence as the violation state, which is
> part of the evidence-sparsity story in the writeups. Note when reading that
> story that for 86% of the null records the absence reflects a non-open
> procurement route rather than an unpublished one.
>
> The underlying five-class `tender.procurementMethod` is not exported as a
> column, but it is preserved verbatim in `source_records.json` under
> `substrate_notes.procurement_method_open_flag.detail` and can be recovered —
> see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) §8.

---

## Edit 4 — new prose section, immediately after Edit 3 · DEFERRED

**Do not land this until the erratum is ready.** It goes in at the same time as
the erratum or after it, with the erratum reference filled in below.

**Proposed (new)**

> ### Uniformly false: direct_award_justification_present
>
> `direct_award_justification_present` is `"false"` on every row of the corpus.
> This is not a measured finding that no direct-award justifications exist.
>
> The substrate derives the field by looking for a linked s.41 transparency
> notice in the OCDS `relatedProcesses` array. UK Contracts Finder does not
> populate that array for these releases, so the detector never finds a link and
> always returns `"false"`. The substrate records the derivation as
> `status: "derived"`, `confidence: "low"`, with the detail *"known false-negative
> mode — notice may exist but not be linked"*, visible per record in
> `source_records.json`.
>
> Read the value as *"no direct-award justification was detectable in this
> substrate"*, not as *"no direct-award justification exists"*. The distinction
> matters because this field is the second conjunct of PROC-005-OPEN-TENDER's
> `when` clause. Because it never varies, that clause never excludes a record,
> and PROC-005 reduces in practice to its first conjunct, `above_threshold`.
> Fifteen records in the corpus state `tender.procurementMethod == "direct"`.
>
> Because the column holds a single value it cannot be used as a variable, and a
> categorical test on it is not meaningful.
>
> This is the subject of [ERRATUM REFERENCE — fill in before landing], which
> records the divergence between PROC-005's specification and its
> implementation.

---

## Resolved

The sequencing question is settled: Edit 4 waits for the erratum and carries a
pointer to it. The placeholder `[ERRATUM REFERENCE — fill in before landing]`
in Edit 4 must be replaced before this section is added.

Remaining action: apply Edit 4 when the erratum lands.