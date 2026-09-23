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

---

## 10. `direct_award_justification_present` is `"false"` on every row

**What happens.** A categorical test on this field returns one category, so it
cannot be used as a variable and any drift or association test on it is
vacuous.

**Why.** The value is not a measured finding that no direct-award
justifications exist. The substrate derives the field by looking for a linked
s.41 transparency notice in the OCDS `relatedProcesses` array. UK Contracts
Finder does not populate that array for these releases, so the detector never
finds a link and returns `"false"` every time. The substrate records the
derivation honestly — `status: "derived"`, `confidence: "low"`, with the detail
*"known false-negative mode — notice may exist but not be linked"*. You can see
it per record:

```python
import json

with open("data/source_records.json") as fh:
    records = json.load(fh)["records"]

note = records[0]["substrate_notes"]["direct_award_justification_present"]
print(note["status"], note["confidence"])
print(note["detail"])
```

**Do instead.** Read the value as *"no direct-award justification was detectable
in this substrate"*, not as *"no direct-award justification exists"*. Write it up
as an excluded variable on those grounds — not measurable here — rather than as
a finding about UK procurement.

If what you actually need is to identify direct awards, do not use this field.
Use the recovered `tender.procurementMethod` from §8, which distinguishes
`direct` and `limited` from `open` and `selective`.

---

## 11. Every bundle in `corpus.tar` fails `approval_lineage` — the bundles are sound

**What happens.** Verify any bundle from any of the three `corpus.tar` archives
and you get an overall verdict of **`invalid`** and **exit code 5**, with
`approval_lineage` reported as the failing claim. It looks like the corpus is
corrupt or the signatures are bad. It is neither.

**What is actually true.** Measured 2026-09-01 against a bundle from
`procurement-decisions/results/corpus.tar`, using the shipped verifier with the
default trusted keys and the default Rekor roots:

| claim | status |
|---|---|
| `bundle_manifest` | valid |
| `integrity` | valid |
| `signature` | **valid** |
| `transparency` | **valid** |
| `canonicalization` | valid |
| `approval_lineage` | **invalid** |
| `key_lifecycle` | not_checked |

Every claim about the receipt's content, its signature and its public
transparency anchor passes. **The receipts are unchanged and remain sound.**
One claim about the *bundle wrapper* fails.

**Why.** A bundle can carry a `policy_approval_receipts.json` file recording the
approval lineage of the policy version that governed the decision. **No bundle
in this corpus has that file** — 0 of 283 in E1, 0 of 1,429 in E2, 0 of 1,332 in
E3. That is not a packaging accident: the exporter could not emit it. Approval
bundling was unreachable from its first release, because one migration treated
the policy-version identifier as input-only while the next joined exclusively on
it. The exporter was later repaired; these archives were exported before that.

The verifier now checks for the file. The exporter that produced these archives
never could ship it. That mismatch is the whole failure.

**What to do.** Read the verdict claim-by-claim rather than by exit code. For
questions about the data — did the decision happen, was it signed, is it
anchored, can it be reproduced — `signature`, `integrity`, `transparency` and
`canonicalization` are the claims that answer them, and all four pass. Treat
`approval_lineage` here as **not established**, not as a failure of the receipt.

**What we are not doing, and why.** Re-exporting the wrappers would change the
bytes of every `corpus.tar`, and therefore every SHA-256 in
[`DATA_MANIFEST.json`](DATA_MANIFEST.json) — which currently match, and which
published work cites. **We are not doing that.** The original `corpus.tar`
archives stay byte-identical and their digests keep verifying under
`corpora` in `DATA_MANIFEST.json`. The repair below shipped as an additional
artefact alongside them, not as a replacement.

*Filed 2026-09-01. Tracked as CCR-002 in the MeshQu remediation register.*

---

### 11a. Repaired copies: `corpus-v2.tar`

Each of the three results directories now also carries `corpus-v2.tar`,
alongside the untouched original `corpus.tar`:

```
procurement-decisions/results/corpus-v2.tar              (283 bundles)
procurement-context-gradient/results/corpus-v2.tar       (1,429 bundles)
procurement-context-disambiguation/results/corpus-v2.tar (1,332 bundles)
```

**What it is.** The same 3,044 signed receipts as `corpus.tar` (per
experiment: its own count), re-exported on 2026-09-23 from the public bundle
endpoint after the exporter fix in TradeQu/tradequ#1156. `receipt.json`,
`policy_snapshot.json`, `transparency_proof.json` and `trusted_keys.json` are
byte-identical to the corresponding bundle in `corpus.tar` — this is asserted,
not just claimed: `data/build_export.py` reads every bundle in both tars and
`sys.exit`s naming the bundle if any of the four differ, if the decision-ID
sets differ, or if the new file is missing or holds the wrong receipt. See
`corpora_v2` in [`DATA_MANIFEST.json`](DATA_MANIFEST.json) for the resulting
digests. The one addition is `policy_approval_receipts.json`, the signed
approval record for the policy version every receipt evaluated against, which
the original exporter could not include (§11 above explains why).
`bundle_manifest.json` differs from `corpus.tar`'s only in `exported_at`, the
new file's entry, and the resulting `manifest_digest`.

Built and reproducible via
[`scripts/build_corpus_v2_tar.py`](../scripts/build_corpus_v2_tar.py).

**How to verify — only as a reader can actually do it today.** On
<https://verify.meshqu.com>, a `corpus-v2.tar` bundle headlines **"Bundle Not
Fully Checked"**: no cryptographic check fails, and approval lineage reads
"Not checked (nothing anchors which tenant these approvals belong to)". A
bundle cannot vouch for its own tenant, and the web verifier has no way to be
told one — that is a narrower, more accurate headline than the original
archive's, which fails outright (§11 above: **"Bundle Failed Verification"**,
exit 5, `approval_lineage` invalid).

The expected tenant for every receipt in all three corpora is:

```
243f19a5-4d4f-4070-9ec1-8170e8260e26
```

Measured 2026-09-23 against the shipped verifier library with default trust,
legacy approval trust and Rekor roots:

| | original `corpus.tar` | `corpus-v2.tar`, no tenant | `corpus-v2.tar`, expected tenant `243f19a5-4d4f-4070-9ec1-8170e8260e26` |
|---|---|---|---|
| all 3,044 | invalid, exit 5 | indeterminate, exit 7 | warn, exit 0 (approval lineage valid; only `key_lifecycle` not checked) |

A verifier given the expected tenant reports approval lineage **valid**. **A
publicly available verifier that accepts an expected tenant is not yet
available.** Do not run `@meshqu/verifier` or any `meshqu-verify` /
`meshqu-verifier` CLI against these bundles expecting this check — the
published `@meshqu/verifier` npm package is a `0.0.0` placeholder with no
binary, and no public CLI can perform this check today. This applies equally
to the original archives: their READMEs' "Option B" CLI instruction
(`meshqu-verifier verify "$f"`) cannot be followed. The command name is wrong
and no public CLI implementing it exists. The independent Rekor lookup route
(Option C in each archive's README) is unaffected by any of this and works
identically for both archives.

**The approval record, stated honestly.** `policy_approval_receipts.json`'s
contents are inside the signed bytes and cannot be edited:

- `ratifier_id` and `ratifier_role` are both `staging-console-experiment-procurement` — a staging console credential, not a named individual.
- `approval_authority` is `unspecified`.
- `workflow_state` is `ratified`.
- Ratified 2026-05-17, **before** this corpus froze on 2026-05-29.
- No individual approver is named anywhere in the record.

**What we are still not doing.** The original `corpus.tar` archives remain
untouched and byte-identical; every digest under `corpora` in
`DATA_MANIFEST.json` is unchanged by this repair. The repair ships only as the
additional `corpus-v2.tar` artefact and the additive `corpora_v2` manifest
section, not as a replacement for anything published before it.

*Filed 2026-09-23.*
