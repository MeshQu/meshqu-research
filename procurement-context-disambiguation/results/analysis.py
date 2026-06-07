"""E3 — Phase 3 analysis.

Loads the merged Phase 2 artifacts (signed receipt bundles, reconciled rubric
sheets, dry-run baselines) and computes every canonical number the writeup
references. The file is laid out as Jupytext "percent" cells so it opens as a
notebook in VSCode / Jupyter, but it also runs as a plain script:

    python procurement-context-disambiguation/results/analysis.py

Outputs:
  - Tables printed to stdout
  - Charts written to ./analysis_charts/ as PNG
  - results/analysis_outputs.json with every canonical number for round-tripping

Read-only against data. Does not modify receipts or rubric sheets.

Anchors from prior in-session analysis are embedded as SANITY_ANCHORS — if any
computed number drifts > 1% from an anchor, the script emits a DRIFT WARNING
rather than silently report a fresh number.
"""

# %% [markdown]
# # E3 — Phase 3 analysis notebook
#
# Pre-registered experiment: **Precedents, policy, and commitment** (E3).
# Locked predictions: `procurement-context-disambiguation/planning/predictions.md`.
# Phase 2 run: `phase-2-20260529T092611-Z` (1,332 signed Ed25519 receipts).
#
# Sections
# 1. Setup + sanity checks
# 2. Verdict distributions per arm
# 3. Rubric distributions per arm (reconciled sheets)
# 4. Cross-experiment comparisons (E3 vs E2)
# 5. Inter-coder Cohen's κ
# 6. P1–P6 disposition table
# 7. Cost-accuracy table (dry-run → Phase 2)
# 8. Charts

# %%
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# %% [markdown]
# ## 1. Setup

# %%
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]  # .../meshqu-research/
E3_RESULTS = HERE
E3_PHASE2 = E3_RESULTS / "runs" / "phase-2-20260529T092611-Z"
E3_DRY_RUN = E3_RESULTS / "runs" / "dry-run-20260528T164807-Z"
E2_PHASE2 = REPO_ROOT / "procurement-context-gradient" / "results" / "runs" / "phase-2-20260522-101324-Z"

CHARTS_DIR = E3_RESULTS / "analysis_charts"
CHARTS_DIR.mkdir(exist_ok=True)

EXPECTED_COUNTS = {
    "arm_a": 283,
    "arm_b": 283,
    "arm_c": 283,
    "l4_without_nudge": 283,
    "diagnostic_primary": 100,
    "diagnostic_claude": 100,
}

SANITY_ANCHORS: dict[str, Any] = {
    "verdict_counts": {
        "arm_a": {"ALLOW": 34, "REVIEW": 239, "DENY": 10},
        "arm_b": {"ALLOW": 9, "REVIEW": 274, "DENY": 0},
        "arm_c": {"ALLOW": 10, "REVIEW": 273, "DENY": 0},
        "l4_without_nudge": {"ALLOW": 0, "REVIEW": 206, "DENY": 77},
        "diagnostic_primary": {"ALLOW": 0, "REVIEW": 77, "DENY": 23},
        "diagnostic_claude": {"ALLOW": 35, "REVIEW": 20, "DENY": 45},
    },
    "e2_l4_verdict_counts": {"ALLOW": 0, "REVIEW": 210, "DENY": 73},
    "l4_without_nudge_retention_of_e2_l3_deny": (65, 107, 60.7),
    "diagnostic_primary_same_as_e2_l4": (88, 100, 88.0),
    "dry_run_prompt_tokens_per_record": {
        "arm_a": 1843.0,
        "arm_b": 1443.2,
        "arm_c": 1626.4,
        "l4_without_nudge": 2577.4,
        "diagnostic_primary": 2599.5,
        "diagnostic_claude": 3943.6,
    },
}

OUTPUTS: dict[str, Any] = {}
WARNINGS: list[str] = []


def _within_1pct(observed: float, anchor: float) -> bool:
    if anchor == 0:
        return abs(observed - anchor) < 1e-9
    return abs(observed - anchor) / abs(anchor) <= 0.01


def drift_check(label: str, observed: float, anchor: float) -> None:
    if not _within_1pct(observed, anchor):
        msg = f"DRIFT WARNING — {label}: observed={observed!r} anchor={anchor!r}"
        print(msg)
        WARNINGS.append(msg)


def load_bundle_verdicts(arm_dir: Path) -> list[tuple[str, str]]:
    """Return list of (ocid, agent_recommended_verdict) from *.bundle.json files."""
    out: list[tuple[str, str]] = []
    for bundle_path in sorted(arm_dir.glob("*.bundle.json")):
        with bundle_path.open() as fh:
            bundle = json.load(fh)
        ctx_raw = bundle.get("context_fields_canonical_json")
        if ctx_raw is None:
            continue
        ctx = json.loads(ctx_raw)
        verdict = ctx.get("agent_recommended_verdict")
        ocid = bundle.get("ocid")
        if verdict is None or ocid is None:
            continue
        out.append((ocid, verdict))
    return out


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


# %% [markdown]
# ## 1a. Sanity-check Phase 2 artifact counts

# %%
phase2_summary = json.loads((E3_PHASE2 / "phase-2-summary.json").read_text())
dry_run_summary = json.loads((E3_DRY_RUN / "dry-run-summary.json").read_text())

print("E3 Phase 2 run id:", phase2_summary.get("run_id"))
print("E3 Phase 2 prereg_tag:", phase2_summary.get("prereg_tag"))
print("E3 Phase 2 total_receipts_written:", phase2_summary.get("total_receipts_written"))
print("E3 Phase 2 finished_at:", phase2_summary.get("finished_at"))
print()

# Count *.bundle.json files per arm and cross-check against expectation.
print(f"{'arm':<22} {'bundles':>8} {'expected':>10} {'match':>6}")
counts_observed = {}
for arm, expected in EXPECTED_COUNTS.items():
    n = len(list((E3_PHASE2 / arm).glob("*.bundle.json")))
    counts_observed[arm] = n
    print(f"{arm:<22} {n:>8} {expected:>10} {'OK' if n == expected else 'FAIL':>6}")
    if n != expected:
        WARNINGS.append(f"Bundle count mismatch for {arm}: {n} vs expected {expected}")

OUTPUTS["bundle_counts"] = counts_observed
OUTPUTS["phase2_total_receipts"] = phase2_summary.get("total_receipts_written")

# %% [markdown]
# ## 2. Verdict distributions per arm

# %%
print("\n=== Verdict distributions per arm (E3 Phase 2) ===\n")

verdict_rows: dict[str, dict[str, int]] = {}
arm_verdict_by_ocid: dict[str, dict[str, str]] = {}

for arm in EXPECTED_COUNTS:
    pairs = load_bundle_verdicts(E3_PHASE2 / arm)
    arm_verdict_by_ocid[arm] = dict(pairs)
    counter = Counter(v for _, v in pairs)
    # Always carry the three canonical verdict keys even if zero so writeup tables align.
    row = {k: counter.get(k, 0) for k in ("ALLOW", "REVIEW", "DENY")}
    verdict_rows[arm] = row

    n = sum(row.values())
    pct = {k: (100.0 * v / n) if n else 0.0 for k, v in row.items()}
    print(f"  {arm:<22} n={n:>3}  ALLOW {row['ALLOW']:>3} ({pct['ALLOW']:5.1f}%)  "
          f"REVIEW {row['REVIEW']:>3} ({pct['REVIEW']:5.1f}%)  "
          f"DENY {row['DENY']:>3} ({pct['DENY']:5.1f}%)")

    anchor = SANITY_ANCHORS["verdict_counts"][arm]
    for verdict in ("ALLOW", "REVIEW", "DENY"):
        drift_check(f"{arm} {verdict} count", row[verdict], anchor[verdict])

OUTPUTS["verdict_counts"] = verdict_rows

# %% [markdown]
# ## 3. Rubric distributions (reconciled sheets, diagnostic_primary + diagnostic_claude)

# %%
print("\n=== Rubric distributions (reconciled sheets) ===\n")

rubric_primary = load_jsonl(E3_RESULTS / "rubric_coding_primary.jsonl")
rubric_claude = load_jsonl(E3_RESULTS / "rubric_coding_claude.jsonl")
rubric_primary_first = load_jsonl(E3_RESULTS / "rubric_coding_primary_first_pass.jsonl")
rubric_primary_blind = load_jsonl(E3_RESULTS / "rubric_coding_primary_blind_agent.jsonl")
rubric_claude_blind = load_jsonl(E3_RESULTS / "rubric_coding_claude_blind_agent.jsonl")


def p5_disposition(cat_counts: dict[int, int], n: int) -> str:
    """≥60% Cat 2 AND ≤15% Cat 1 ⇒ Confirmed (per predictions.md P5)."""
    if n == 0:
        return "n/a"
    cat1_pct = 100.0 * cat_counts.get(1, 0) / n
    cat2_pct = 100.0 * cat_counts.get(2, 0) / n
    confirmed = cat2_pct >= 60.0 and cat1_pct <= 15.0
    return "Confirmed" if confirmed else "Falsified"


def summarize_rubric(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter = Counter(int(r["category"]) for r in rows)
    n = sum(counter.values())
    summary = {
        "n": n,
        "cat_1": counter.get(1, 0),
        "cat_2": counter.get(2, 0),
        "cat_3": counter.get(3, 0),
        "cat_1_pct": round(100.0 * counter.get(1, 0) / n, 2) if n else 0.0,
        "cat_2_pct": round(100.0 * counter.get(2, 0) / n, 2) if n else 0.0,
        "cat_3_pct": round(100.0 * counter.get(3, 0) / n, 2) if n else 0.0,
        "p5_disposition": p5_disposition(counter, n),
    }
    print(
        f"  {name:<46} n={summary['n']:>3}  "
        f"Cat1 {summary['cat_1']:>3} ({summary['cat_1_pct']:5.1f}%)  "
        f"Cat2 {summary['cat_2']:>3} ({summary['cat_2_pct']:5.1f}%)  "
        f"Cat3 {summary['cat_3']:>3} ({summary['cat_3_pct']:5.1f}%)  "
        f"P5={summary['p5_disposition']}"
    )
    return summary


rubric_summary = {
    "diagnostic_primary_reconciled": summarize_rubric("diagnostic_primary  reconciled", rubric_primary),
    "diagnostic_primary_first_pass": summarize_rubric("diagnostic_primary  first-pass", rubric_primary_first),
    "diagnostic_primary_blind_agent": summarize_rubric("diagnostic_primary  blind-agent", rubric_primary_blind),
    "diagnostic_claude_reconciled": summarize_rubric("diagnostic_claude   reconciled", rubric_claude),
    "diagnostic_claude_blind_agent": summarize_rubric("diagnostic_claude   blind-agent", rubric_claude_blind),
}
OUTPUTS["rubric_summary"] = rubric_summary

# %% [markdown]
# ## 4. Cross-experiment comparisons (E3 vs E2)
#
# Two things to compute:
#
# - **Verdict distribution**: E3 `l4_without_nudge` vs E2 L4 (with nudge), both n=283.
# - **Retention of E2's L3-DENY set in E3 L4-without-nudge** (the P3 falsification metric).
# - **Same-verdict rate per OCID**: E3 `diagnostic_primary` (inverted-policy n=100) vs E2 L4 unperturbed (the P4 metric).

# %%
print("\n=== Cross-experiment comparisons (E3 vs E2) ===\n")


def load_e2_l3_verdicts() -> dict[str, str]:
    e2_l3_dir = E2_PHASE2 / "L3"
    if not e2_l3_dir.exists():
        print(f"  (E2 L3 dir missing: {e2_l3_dir})")
        return {}
    return dict(load_bundle_verdicts(e2_l3_dir))


def load_e2_l4_verdicts() -> dict[str, str]:
    e2_l4_dir = E2_PHASE2 / "L4"
    if not e2_l4_dir.exists():
        print(f"  (E2 L4 dir missing: {e2_l4_dir})")
        return {}
    return dict(load_bundle_verdicts(e2_l4_dir))


e2_l3_verdicts = load_e2_l3_verdicts()
e2_l4_verdicts = load_e2_l4_verdicts()

# E2 L4 verdict distribution (n=283).
e2_l4_counter = Counter(e2_l4_verdicts.values())
e2_l4_row = {k: e2_l4_counter.get(k, 0) for k in ("ALLOW", "REVIEW", "DENY")}
print(f"  E2 L4 (n={sum(e2_l4_row.values())}): {e2_l4_row}")
for verdict in ("ALLOW", "REVIEW", "DENY"):
    drift_check(f"E2 L4 {verdict} count", e2_l4_row[verdict], SANITY_ANCHORS["e2_l4_verdict_counts"][verdict])

# E3 L4-without-nudge vs E2 L4 (with nudge) — full distributions side by side.
e3_l4_row = verdict_rows["l4_without_nudge"]
print(f"  E3 l4_without_nudge (n={sum(e3_l4_row.values())}): {e3_l4_row}")

# Retention of E2's L3-DENY set in E3 l4_without_nudge.
e2_l3_deny_ocids = {ocid for ocid, v in e2_l3_verdicts.items() if v == "DENY"}
print(f"  |E2 L3-DENY set| = {len(e2_l3_deny_ocids)} (expected 107)")
e3_l4_no_nudge_by_ocid = arm_verdict_by_ocid["l4_without_nudge"]
retained_deny = sum(1 for ocid in e2_l3_deny_ocids if e3_l4_no_nudge_by_ocid.get(ocid) == "DENY")
retention_n = len(e2_l3_deny_ocids)
retention_pct = (100.0 * retained_deny / retention_n) if retention_n else 0.0
print(f"  E3 l4_without_nudge retention of E2 L3-DENY set: {retained_deny}/{retention_n} = {retention_pct:.1f}%")
anchor_r = SANITY_ANCHORS["l4_without_nudge_retention_of_e2_l3_deny"]
drift_check("retention numerator", retained_deny, anchor_r[0])
drift_check("retention denominator", retention_n, anchor_r[1])
drift_check("retention percent", retention_pct, anchor_r[2])

# Same-verdict rate per OCID: E3 diagnostic_primary vs E2 L4 unperturbed.
e3_diag_by_ocid = arm_verdict_by_ocid["diagnostic_primary"]
diag_ocids = set(e3_diag_by_ocid) & set(e2_l4_verdicts)
same_verdict = sum(1 for ocid in diag_ocids if e3_diag_by_ocid[ocid] == e2_l4_verdicts[ocid])
sv_n = len(diag_ocids)
sv_pct = (100.0 * same_verdict / sv_n) if sv_n else 0.0
print(f"  E3 diagnostic_primary same-as-E2-L4: {same_verdict}/{sv_n} = {sv_pct:.1f}%")
anchor_d = SANITY_ANCHORS["diagnostic_primary_same_as_e2_l4"]
drift_check("diag same-verdict numerator", same_verdict, anchor_d[0])
drift_check("diag same-verdict denominator", sv_n, anchor_d[1])
drift_check("diag same-verdict percent", sv_pct, anchor_d[2])

# Same-verdict rate per OCID: E3 diagnostic_claude vs E2 L4 unperturbed (P6 metric).
e3_diag_claude_by_ocid = arm_verdict_by_ocid["diagnostic_claude"]
diag_claude_ocids = set(e3_diag_claude_by_ocid) & set(e2_l4_verdicts)
same_claude = sum(1 for ocid in diag_claude_ocids if e3_diag_claude_by_ocid[ocid] == e2_l4_verdicts[ocid])
sc_n = len(diag_claude_ocids)
sc_pct = (100.0 * same_claude / sc_n) if sc_n else 0.0
print(f"  E3 diagnostic_claude   same-as-E2-L4: {same_claude}/{sc_n} = {sc_pct:.1f}%")
# Gap for P6 (within 15pp of primary?).
p6_gap = abs(sv_pct - sc_pct)
print(f"  P6 gap |primary - claude| = {p6_gap:.1f} pp (band ≤ 15pp)")

OUTPUTS["cross_experiment"] = {
    "e2_l4_verdicts": e2_l4_row,
    "e3_l4_without_nudge_verdicts": e3_l4_row,
    "e3_retention_of_e2_l3_deny": {
        "numerator": retained_deny,
        "denominator": retention_n,
        "percent": round(retention_pct, 2),
    },
    "diagnostic_primary_same_as_e2_l4": {
        "numerator": same_verdict,
        "denominator": sv_n,
        "percent": round(sv_pct, 2),
    },
    "diagnostic_claude_same_as_e2_l4": {
        "numerator": same_claude,
        "denominator": sc_n,
        "percent": round(sc_pct, 2),
    },
    "p6_gap_pp": round(p6_gap, 2),
}

# %% [markdown]
# ## 5. Inter-coder Cohen's κ (with Landis-Koch banding)
#
# Implementation is inline so the script has no sklearn dependency.

# %%

def cohen_kappa(pairs: list[tuple[Any, Any]]) -> tuple[float, float]:
    """Return (kappa, observed_agreement). Standard Cohen's κ over arbitrary labels."""
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    confusion: dict[tuple[Any, Any], int] = defaultdict(int)
    for a, b in pairs:
        confusion[(a, b)] += 1
    p_o = sum(confusion[(L, L)] for L in labels) / n
    row_totals = {L: sum(confusion[(L, M)] for M in labels) for L in labels}
    col_totals = {L: sum(confusion[(M, L)] for M in labels) for L in labels}
    p_e = sum((row_totals[L] / n) * (col_totals[L] / n) for L in labels)
    if abs(1 - p_e) < 1e-12:
        return 1.0 if p_o == 1.0 else float("nan"), p_o
    kappa = (p_o - p_e) / (1 - p_e)
    return kappa, p_o


def landis_koch(k: float) -> str:
    if k < 0:
        return "Less than chance"
    if k < 0.20:
        return "Slight"
    if k < 0.40:
        return "Fair"
    if k < 0.60:
        return "Moderate"
    if k < 0.80:
        return "Substantial"
    return "Almost perfect"


def pairs_by_ocid(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[tuple[int, int]]:
    a_by = {r["ocid"]: int(r["category"]) for r in a}
    b_by = {r["ocid"]: int(r["category"]) for r in b}
    common = sorted(set(a_by) & set(b_by))
    return [(a_by[ocid], b_by[ocid]) for ocid in common]


print("\n=== Inter-coder Cohen's κ ===\n")

kappa_rows: list[dict[str, Any]] = []
kappa_table = [
    ("primary  first-pass ↔ blind-agent",
     pairs_by_ocid(rubric_primary_first, rubric_primary_blind)),
    ("primary  first-pass ↔ reconciled",
     pairs_by_ocid(rubric_primary_first, rubric_primary)),
    ("primary  reconciled ↔ blind-agent",
     pairs_by_ocid(rubric_primary, rubric_primary_blind)),
    ("claude   reconciled ↔ blind-agent",
     pairs_by_ocid(rubric_claude, rubric_claude_blind)),
]

for label, pairs in kappa_table:
    k, po = cohen_kappa(pairs)
    band = landis_koch(k)
    row = {"comparison": label, "n": len(pairs), "kappa": round(k, 4), "observed_agreement": round(po, 4), "landis_koch": band}
    kappa_rows.append(row)
    print(f"  {label:<42} n={len(pairs):>3}  κ={k:+.4f}  p_o={po:.4f}  ({band})")

OUTPUTS["cohen_kappa"] = kappa_rows

# Cross-check against the published table in rubric_inter_coder_analysis_primary.md
# (first-pass ↔ blind-agent: κ = −0.0369, p_o = 0.21; reconciled ↔ blind-agent: κ = +1.0000).
fp_blind = kappa_rows[0]
recon_blind = kappa_rows[2]
drift_check("primary first-pass↔blind κ", fp_blind["kappa"], -0.0369)
drift_check("primary first-pass↔blind p_o", fp_blind["observed_agreement"], 0.21)
drift_check("primary reconciled↔blind κ", recon_blind["kappa"], 1.0)

# %% [markdown]
# ## 6. P1–P6 disposition table
#
# Locked thresholds from `procurement-context-disambiguation/planning/predictions.md`
# (post-2026-05-27 calibration). Disposition vocabulary from `programme/PROCESS.md`:
# Confirmed / Falsified / Inverted / Refuted / Deferred / Under-tested.

# %%
print("\n=== P1–P6 disposition table ===\n")


def pct(numer: int, denom: int) -> float:
    return (100.0 * numer / denom) if denom else 0.0


arm_a_deny = pct(verdict_rows["arm_a"]["DENY"], sum(verdict_rows["arm_a"].values()))
arm_b_deny = pct(verdict_rows["arm_b"]["DENY"], sum(verdict_rows["arm_b"].values()))
arm_c_deny = pct(verdict_rows["arm_c"]["DENY"], sum(verdict_rows["arm_c"].values()))

# P1: precedents-only DENY ≥ 20% AND density-control DENY ≤ 12%. Falsified if Arm C ≥ 20% or Arm A < 20%.
p1_arm_a_pass = arm_a_deny >= 20.0
p1_arm_c_pass = arm_c_deny <= 12.0
if arm_c_deny >= 20.0 or arm_a_deny < 20.0:
    p1_disposition = "Falsified"
elif p1_arm_a_pass and p1_arm_c_pass:
    p1_disposition = "Confirmed"
else:
    p1_disposition = "Under-tested"

# P2: Arm A DENY − Arm B DENY ≥ 15pp. Falsified if |A−B| < 5pp.
p2_gap = arm_a_deny - arm_b_deny
if abs(p2_gap) < 5.0:
    p2_disposition = "Falsified"
elif p2_gap >= 15.0:
    p2_disposition = "Confirmed"
else:
    p2_disposition = "Under-tested"

# P3: retention of E2 L3-DENY set in L4-without-nudge.
#     Confirmed if retention ≥ 80%; Falsified if retention ≤ 65%; else Under-tested.
if retention_pct >= 80.0:
    p3_disposition = "Confirmed"
elif retention_pct <= 65.0:
    p3_disposition = "Falsified"
else:
    p3_disposition = "Under-tested"

# P4: diagnostic_primary same-verdict rate vs unperturbed-L4 ≥ 90%.
p4_disposition = "Confirmed" if sv_pct >= 90.0 else "Falsified"

# P5: hand-coded rubric — Cat 2 ≥ 60% AND Cat 1 ≤ 15%.
p5_primary = rubric_summary["diagnostic_primary_reconciled"]["p5_disposition"]
p5_claude = rubric_summary["diagnostic_claude_reconciled"]["p5_disposition"]

# P6: Claude diagnostic same-verdict rate within 15pp of primary's same-verdict rate.
p6_disposition = "Confirmed" if p6_gap <= 15.0 else "Falsified"

disposition_table = [
    ("P1", "Arm A DENY ≥ 20% AND Arm C DENY ≤ 12%",
     f"Arm A {arm_a_deny:.1f}%, Arm C {arm_c_deny:.1f}%", p1_disposition),
    ("P2", "Arm A − Arm B DENY gap ≥ 15pp",
     f"gap = {p2_gap:+.1f}pp (A={arm_a_deny:.1f}%, B={arm_b_deny:.1f}%)", p2_disposition),
    ("P3", "L4-no-nudge retention of E2 L3-DENY ≥ 80% (Confirm) / ≤ 65% (Falsify)",
     f"retention = {retention_pct:.1f}% ({retained_deny}/{retention_n})", p3_disposition),
    ("P4", "diagnostic_primary same-as-L4 ≥ 90%",
     f"same = {sv_pct:.1f}% ({same_verdict}/{sv_n})", p4_disposition),
    ("P5a", "diagnostic_primary Cat 2 ≥ 60% AND Cat 1 ≤ 15%",
     f"Cat1 {rubric_summary['diagnostic_primary_reconciled']['cat_1_pct']:.1f}%, "
     f"Cat2 {rubric_summary['diagnostic_primary_reconciled']['cat_2_pct']:.1f}%", p5_primary),
    ("P5b", "diagnostic_claude  Cat 2 ≥ 60% AND Cat 1 ≤ 15%",
     f"Cat1 {rubric_summary['diagnostic_claude_reconciled']['cat_1_pct']:.1f}%, "
     f"Cat2 {rubric_summary['diagnostic_claude_reconciled']['cat_2_pct']:.1f}%", p5_claude),
    ("P6", "|primary same% − claude same%| ≤ 15pp",
     f"gap = {p6_gap:.1f}pp (primary {sv_pct:.1f}%, claude {sc_pct:.1f}%)", p6_disposition),
]

print(f"  {'ID':<4} {'Locked threshold':<60} {'Observed':<48} {'Disposition':<14}")
print("  " + "-" * 130)
for pid, threshold, observed, disp in disposition_table:
    print(f"  {pid:<4} {threshold:<60} {observed:<48} {disp:<14}")

OUTPUTS["disposition_table"] = [
    {"id": pid, "threshold": threshold, "observed": observed, "disposition": disp}
    for pid, threshold, observed, disp in disposition_table
]

# %% [markdown]
# ## 7. Cost-accuracy: dry-run baseline tokens-per-record vs Phase 2 actuals

# %%
print("\n=== Cost-accuracy: dry-run → Phase 2 ===\n")

cost_rows: list[dict[str, Any]] = []
dry_acc = dry_run_summary["accountings"]
p2_acc = phase2_summary["accountings"]

dry_run_total_cost = sum(dry_acc[a]["estimated_usd_cost"] for a in EXPECTED_COUNTS)
phase2_total_cost = sum(p2_acc[a]["estimated_usd_cost"] for a in EXPECTED_COUNTS)
projection_total_cost = sum(e["full_run_usd_cost_projected"] for e in dry_run_summary.get("phase_2_extrapolation", []))

print(f"  {'arm':<22} {'dry tok/rec':>12} {'p2 tok/rec':>12} {'ratio':>8} "
      f"{'dry $':>10} {'projected $':>12} {'actual $':>10}")
for arm in EXPECTED_COUNTS:
    dry = dry_acc[arm]
    p2 = p2_acc[arm]
    dry_tpr = dry["prompt_tokens_mean_per_record"]
    p2_tpr = p2["prompt_tokens_mean_per_record"]
    ratio = (p2_tpr / dry_tpr) if dry_tpr else float("nan")
    projection_arm = next(
        (e for e in dry_run_summary.get("phase_2_extrapolation", []) if e["arm"] == arm),
        {},
    )
    proj_usd = projection_arm.get("full_run_usd_cost_projected", float("nan"))
    cost_rows.append({
        "arm": arm,
        "dry_prompt_tokens_per_record": round(dry_tpr, 2),
        "phase2_prompt_tokens_per_record": round(p2_tpr, 2),
        "ratio_phase2_over_dry": round(ratio, 4),
        "dry_usd": round(dry["estimated_usd_cost"], 4),
        "projected_phase2_usd": round(proj_usd, 4),
        "actual_phase2_usd": round(p2["estimated_usd_cost"], 4),
    })
    print(f"  {arm:<22} {dry_tpr:>12.1f} {p2_tpr:>12.1f} {ratio:>8.4f} "
          f"{dry['estimated_usd_cost']:>10.4f} {proj_usd:>12.4f} {p2['estimated_usd_cost']:>10.4f}")

    anchor_tpr = SANITY_ANCHORS["dry_run_prompt_tokens_per_record"][arm]
    drift_check(f"{arm} dry-run tokens/record", round(dry_tpr, 1), anchor_tpr)

print()
print(f"  Totals: dry-run ${dry_run_total_cost:.4f}  projection ${projection_total_cost:.4f}  "
      f"phase2 actual ${phase2_total_cost:.4f}")

OUTPUTS["cost_table"] = cost_rows
OUTPUTS["cost_totals"] = {
    "dry_run_usd": round(dry_run_total_cost, 4),
    "projection_usd": round(projection_total_cost, 4),
    "actual_phase2_usd": round(phase2_total_cost, 4),
}

# %% [markdown]
# ## 8. Charts
#
# Matplotlib is an optional dependency. If it is not installed the chart cells
# print a notice and continue — every number above is still written to
# `analysis_outputs.json`.

# %%
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception as exc:  # pragma: no cover - env-dependent
    print(f"  matplotlib unavailable ({exc!r}); skipping chart generation.")
    HAVE_MPL = False


def save_chart(name: str) -> None:
    path = CHARTS_DIR / name
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


VERDICT_COLOURS = {"ALLOW": "#3a7d44", "REVIEW": "#c08a2e", "DENY": "#a13b3b"}

if HAVE_MPL:
    # Chart 1 — verdict distribution per arm (grouped bars).
    arms = list(EXPECTED_COUNTS.keys())
    n_arms = len(arms)
    x = list(range(n_arms))
    verdicts = ("ALLOW", "REVIEW", "DENY")
    bar_width = 0.27

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, v in enumerate(verdicts):
        heights = [verdict_rows[arm][v] for arm in arms]
        offsets = [xi + (i - 1) * bar_width for xi in x]
        ax.bar(offsets, heights, width=bar_width, color=VERDICT_COLOURS[v], label=v)
        for xi, h in zip(offsets, heights):
            if h > 0:
                ax.text(xi, h + 3, str(h), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(arms, rotation=20, ha="right")
    ax.set_ylabel("count")
    ax.set_title("E3 Phase 2 — verdict distribution per arm")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    save_chart("verdict_distribution_per_arm.png")

    # Chart 2 — rubric category breakdown for diagnostic arms (stacked).
    diag_arms = [
        ("diagnostic_primary (reconciled)", rubric_summary["diagnostic_primary_reconciled"]),
        ("diagnostic_claude (reconciled)", rubric_summary["diagnostic_claude_reconciled"]),
    ]
    labels = [d[0] for d in diag_arms]
    cat1 = [d[1]["cat_1"] for d in diag_arms]
    cat2 = [d[1]["cat_2"] for d in diag_arms]
    cat3 = [d[1]["cat_3"] for d in diag_arms]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, cat1, color="#6a4c93", label="Cat 1 — names inversion")
    ax.bar(labels, cat2, bottom=cat1, color="#1982c4", label="Cat 2 — reasons-against-intent")
    ax.bar(labels, cat3, bottom=[c1 + c2 for c1, c2 in zip(cat1, cat2)],
           color="#8ac926", label="Cat 3 — partial recognition")
    for idx, d in enumerate(diag_arms):
        s = d[1]
        ax.text(idx, 50, f"Cat1 {s['cat_1_pct']:.0f}%  Cat2 {s['cat_2_pct']:.0f}%",
                ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax.set_ylabel("count (n = 100 per arm)")
    ax.set_title("E3 rubric category breakdown — diagnostic arms")
    ax.legend(loc="lower right")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3)
    save_chart("rubric_category_breakdown.png")

    # Chart 3 — cross-experiment verdict distribution (E2 L4 vs E3 l4_without_nudge).
    arms = ["E2 L4 (with nudge)", "E3 l4_without_nudge"]
    cross_rows = [e2_l4_row, verdict_rows["l4_without_nudge"]]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    x = list(range(len(arms)))
    bar_width = 0.27
    for i, v in enumerate(verdicts):
        heights = [r[v] for r in cross_rows]
        offsets = [xi + (i - 1) * bar_width for xi in x]
        ax.bar(offsets, heights, width=bar_width, color=VERDICT_COLOURS[v], label=v)
        for xi, h in zip(offsets, heights):
            ax.text(xi, h + 3, str(h), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(arms)
    ax.set_ylabel("count")
    ax.set_title("E2 L4 vs E3 L4-without-nudge — verdict distribution (n=283 each)")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    save_chart("cross_experiment_verdict_distribution.png")

    # Chart 4 — same-verdict comparison (P4, P6).
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(
        ["diagnostic_primary vs E2 L4 (P4)", "diagnostic_claude vs E2 L4 (P6 anchor)"],
        [sv_pct, sc_pct],
        color=["#1982c4", "#6a4c93"],
    )
    ax.axhline(90, linestyle="--", color="#3a7d44", label="P4 floor: 90%")
    ax.set_ylim(0, 100)
    ax.set_ylabel("same-verdict rate (%)")
    ax.set_title("Same-verdict rate per OCID vs E2 L4 (n=100 per arm)")
    for bar, pct_ in zip(bars, [sv_pct, sc_pct]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{pct_:.1f}%", ha="center", fontsize=11, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    save_chart("same_verdict_comparison.png")

# %% [markdown]
# ## 9. Persist canonical numbers

# %%
OUTPUTS["warnings"] = WARNINGS
out_path = E3_RESULTS / "analysis_outputs.json"
with out_path.open("w") as fh:
    json.dump(OUTPUTS, fh, indent=2, sort_keys=True)
print(f"\nWrote canonical outputs to {out_path.relative_to(REPO_ROOT)}")

if WARNINGS:
    print(f"\n{'!' * 4} {len(WARNINGS)} drift warning(s) emitted; review above.")
    sys.exit(1 if os.environ.get("E3_DRIFT_FATAL") else 0)
else:
    print("\nAll computed numbers within 1% of sanity anchors.")
