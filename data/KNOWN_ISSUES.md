# Known issues and traps

Properties of this corpus that look like data-quality problems, behave like
them under ordinary cleaning, and are not. Each entry says what happens, why,
and what to do instead.

Read this before you clean anything. Most of these fail silently — you get a
plausible wrong number rather than an error.

Run [`check_pipeline.py`](check_pipeline.py) against your dataframe after every
step that drops rows, fills values, joins a table, or changes a dtype. It
asserts the invariants below and names whichever one broke.

```
python data/check_pipeline.py                    # smoke-test the shipped corpus
python data/check_pipeline.py path/to/yours.csv  # check your own export
```

---

## 1. Do not fill or drop nulls in `procurement_method_open_flag`

**What happens.** You lose roughly 94.9% of the DENY signal. Nothing errors.

**Why.** The column is null on 2,840 of 3,044 rows, which looks like missing
data and is not. It is an *open-detected* flag, not an open/closed boolean: the
substrate adapter writes `"true"` when the source record's procurement method is
`open` and writes nothing otherwise. There is no code path anywhere that
produces `false`. A null means "the method was something other than open" —
usually `selective` — and in a minority of cases "the source did not state a
method".

This is what the boolean was hiding. The 283 source records break down by the
procurement method the source actually states:

| `tender.procurementMethod` | records | `procurement_method_open_flag` |
|---|---|---|
| `selective` | 207 | null |
| *not stated* | 37 | null |
| `open` | **19** | `"true"` |
| `direct` | 15 | null |
| `limited` | 5 | null |

Only 37 of the 264 null records are ones where the source was silent. The other
227 state a method that simply is not `open`. Recovering that variable as a real
five-class column is §8.

Rule `PROC-005-OPEN-TENDER` treats that absence as the violation state. It
accounts for 1,400 of 2,740 violations and 94.9% of all DENY verdicts. Fill the
nulls and the rule's input disappears; drop the null rows and you keep 204 of
3,044.

**Do instead.** Leave the nulls. Treat the column as two-state — open versus
not-open — and it becomes a testable variable:

```python
receipts["is_open"] = receipts["procurement_method_open_flag"].notna()
```

If you want the real multi-class procurement method, see §8.

---

## 2. Do not inner-join receipts to reasoning texts

**What happens.** You silently lose exactly 283 rows — the entire E1 arm.

**Why.** `reasoning_texts.parquet` covers E2 (1,429) and E3 (1,332) only. E1's
production run is not in the repository, so E1 has no reasoning texts at all. An
inner join on `decision_id` leaves 2,761 rows and no baseline arm. If you are
doing anything text-based, your comparison group vanishes without a warning.

**Do instead.** Left-join, and check for nulls:

```python
merged = receipts.merge(texts, on="decision_id", how="left")
assert len(merged) == 3044
```

Then decide explicitly whether E1 belongs in your analysis, rather than having
the join decide for you.

---

## 3. Do not analyse `severity`

**What happens.** Every breakdown returns one category.

**Why.** All 2,740 rows in `violations.parquet` have `severity = "critical"`.
The policy defines two `high` rules — `PROC-004-COI` and `PROC-006-MOD-CAP` —
and neither can fire (§4). So the only violations that exist are the critical
ones, and the column carries no information.

**Do instead.** Nothing — drop the variable. If you need a seriousness axis, use
the rule code.

---

## 4. The policy has six rules; three cannot fire

**What happens.** You report rule coverage over six rules and three are
structurally impossible, not merely rare.

**Why.**

| Rule | Why it cannot fire |
|---|---|
| `PROC-003-DEBARMENT` | Its forbidden list holds three synthetic supplier IDs (`SUPPLIER-OFAC-001` and similar). Every real supplier is `GB-COH-*` or `GB-CFS-*`, so no value can ever match. |
| `PROC-004-COI` | Gated on `conflict_of_interest_declaration` existing. UK Contracts Finder OCDS does not carry that field, so it is absent on all 283 records and the gate is never satisfied. |
| `PROC-006-MOD-CAP` | Gated on `is_modification == "true"`. That field is `"false"` on all 283 records. |

Only `PROC-001-S53` (569 firings), `PROC-002-AUTHORITY` (771) and
`PROC-005-OPEN-TENDER` (1,400) ever appear.

**Do instead.** State the effective policy depth as three rules. The E1 writeup
reports the three zero-fire rules honestly — the point here is that they are
structurally impossible rather than empirically absent, which is a stronger
claim and changes how you describe coverage.

---

## 5. `contract_value == 0.0` on 8 OCIDs

**What happens.** Eight procurement records (84 rows across conditions) carry a
contract value of zero, which drags means, breaks log transforms, and lands in
the bottom bucket of any quantile split.

**Why.** Almost certainly an OCDS release that published no award value, with
absence encoded as `0.0`. All eight are `above_threshold = "false"` in
consequence, and they pass `PROC-002-AUTHORITY` trivially.

**Do instead.** Decide explicitly whether zero means free or means unknown, and
say which in your write-up. Do not let it pass through a regression unexamined.
Non-zero values range from £116 to £2.08bn.

---

## 6. E1 says 144/139, E2 and E3 say 146/137 — both are correct

**What happens.** You compute the ALLOW/DENY split on what is described as the
same frozen 283-record corpus and get two different answers. It looks like your
join is wrong. It is not.

**Why.** For 12 OCIDs the Contracts Finder feed returned more than one release.
E1 signed against the first release evaluated for each contracting process; E2
and E3 reconstructed the substrate from E1's archived adapter output, which for
those 12 holds the last release. Two records differ in consequence.

**Do instead.** Read
[`docs/integrity-audits/2026-08-04-corpus-lineage-and-receipt-count.md`](../docs/integrity-audits/2026-08-04-corpus-lineage-and-receipt-count.md).
It identifies the records, explains the mechanism, and confirms both published
splits are correct for the evidence each run actually evaluated. The same audit
retracts a programme-level count of ~3,061 in favour of **3,044**; if you see
3,061 quoted anywhere, 3,044 is the defensible figure.

---

## 7. `violation_codes` in the CSV is a JSON array string

**What happens.** Splitting on commas produces fragments like `["PROC-001-S53`
and rule codes that match nothing.

**Why.** `receipts.csv` serialises everything as strings. `violation_codes`
holds e.g. `["PROC-001-S53","PROC-005-OPEN-TENDER"]`. In
`receipts.parquet` the same column is a real list.

**Do instead.**

```python
import json
receipts["violation_codes"] = receipts["violation_codes"].apply(json.loads)
```

Or use the parquet, which is the canonical typed copy.

---

## 8. Recovering the real procurement method

`procurement_method_open_flag` is a lossy flattening of a five-class variable.
The underlying `tender.procurementMethod` is not exported as a column, but it is
preserved verbatim in the provenance notes of `source_records.json`, which are
populated on all 283 records. You can recover it:

```python
import json, re, collections

with open("data/source_records.json") as fh:
    records = json.load(fh)["records"]

def procurement_method(record):
    note = record["substrate_notes"]["procurement_method_open_flag"]
    if note["status"] == "derived":
        return "open"
    match = re.search(r"procurementMethod == (\S+)", note["detail"])
    value = match.group(1).strip("'") if match else None
    return None if value == "None" else value

methods = {r["ocid"]: procurement_method(r) for r in records}
print(collections.Counter(methods.values()))
# Counter({'selective': 207, None: 37, 'open': 19, 'direct': 15, 'limited': 5})
```

Join it onto the receipts on `ocid`. This gives you a genuine categorical
variable where the boolean gives you a degenerate one, and it makes the
distribution visible: only 37 of the 264 null flags are records where the source
was actually silent. The other 227 state a method that simply is not `open`.

`tender.procurementMethod` is public Contracts Finder data published under the
Open Government Licence, the same provenance as `contract_value` and
`supplier_id`, both already exported. There is no disclosure concern in using
it.

---

## 9. Two verdict columns, two different actors

`policy_verdict` is the deterministic rule engine (ALLOW or DENY only).
`ai_verdict` is the language model's recommendation (ALLOW, REVIEW or DENY).
They disagree constantly, and that disagreement is the subject of the research.
Do not reconcile them, treat one as ground truth, or clean the divergence away.

There are no human verdicts anywhere in this dataset.
