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

import argparse
import json
import os
import random
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

# CLI args parsed up-front so the rest of the file can branch on them.
# Jupyter / VSCode notebook execution passes no args, so parse_known_args
# tolerates unknown ipykernel flags too.
_ARG_PARSER = argparse.ArgumentParser(
    description="E3 Phase 3 analysis — canonical computations + optional signature spot-check.",
    add_help=False,
)
_ARG_PARSER.add_argument(
    "--verify-sample",
    type=int,
    default=0,
    metavar="N",
    help=(
        "Optional: cryptographically verify N randomly-sampled bundles "
        "from the Phase 2 corpus using runner/scripts/verify_smoke_e3.py's "
        "Ed25519 verifier. Skipped if 0 (default) or if the verifier "
        "module isn't importable. Result lands in OUTPUTS JSON."
    ),
)
_ARG_PARSER.add_argument(
    "--verify-seed",
    type=int,
    default=0,
    help="Deterministic seed for --verify-sample random selection.",
)
_ARG_PARSER.add_argument("-h", "--help", action="help")
_ARGS, _ = _ARG_PARSER.parse_known_args()

EXPECTED_COUNTS = {
    "arm_a": 283,
    "arm_b": 283,
    "arm_c": 283,
    "l4_without_nudge": 283,
    "diagnostic_primary": 100,
    "diagnostic_claude": 100,
}

# SANITY_ANCHORS are sourced from the in-session decision_log entries — NOT
# from prior runs of this script. The point of an anchor is to give drift a
# chance to bite: if the canonical re-tally from signed receipts disagrees
# with the figure quoted in `planning/decision_log.md`, we want a warning,
# not silent reconciliation. Each anchor below cites the decision_log entry
# it was copied from.
#
# Known anchor drift (intentional — surfaces in WARNINGS at first run):
#   - `arm_c` "commits" (ALLOW+DENY) — decision_log 2026-05-29 entry's
#     Piece 1 table reports `arm_c (precedents-no-verdict): 13 commits`.
#     The canonical re-tally from the 283 signed receipts is ALLOW=10,
#     DENY=0 → 10 commits. We anchor to the decision_log figure (13) so the
#     drift fires and the writeup honestly carries the correction.
#   - `diagnostic_claude` verdict mix — the 2026-05-29 decision_log entry's
#     "Cross-model verdict-style divergence" table reports ALLOW=35,
#     REVIEW=20, DENY=45 for diagnostic_claude. The canonical re-tally is
#     ALLOW=36, REVIEW=20, DENY=44 (PR #114 first-commit notes both numbers).
#     We anchor to the decision_log figure so the drift fires.
SANITY_ANCHORS: dict[str, Any] = {
    "verdict_counts": {
        # Source: decision_log 2026-05-29 "Substantive verdict distributions
        # — Piece 1" table.
        #   arm_a: 44 commits (ALLOW+DENY) / 239 REVIEW
        #   arm_b: 9 commits / 274 REVIEW
        #   arm_c: 13 commits / 270 REVIEW   <-- canonical is 10 commits / 273 REVIEW
        # The table is rendered as "agent commits (ALLOW + DENY)" so the
        # split between ALLOW and DENY is not given in the decision_log;
        # we anchor ALLOW counts to the decision_log totals minus the DENY
        # counts where DENY is unambiguous from the canonical sheet, and
        # explicitly drift-check the REVIEW total because that IS quoted.
        # The arm_a DENY=10 figure traces to the same entry's prose
        # ("Arm A commits ~3.4× more than Arms B/C") + the canonical
        # re-tally; the explicit decision_log Piece-1 row only quotes
        # totals.
        "arm_a": {"ALLOW": 34, "REVIEW": 239, "DENY": 10},
        "arm_b": {"ALLOW": 9, "REVIEW": 274, "DENY": 0},
        # arm_c: decision_log says 13 commits / 270 REVIEW. Canonical sheet
        # carries 10 ALLOW + 0 DENY = 10 commits. Anchor to decision_log;
        # the drift WILL fire and the writeup must acknowledge the
        # correction.
        "arm_c": {"ALLOW": 13, "REVIEW": 270, "DENY": 0},
        # Source: decision_log 2026-05-29 "Piece 2 — L4 decomposition"
        # table — 77 DENY / 206 REVIEW.
        "l4_without_nudge": {"ALLOW": 0, "REVIEW": 206, "DENY": 77},
        # Source: decision_log 2026-05-29 "Piece 3 — Inversion-blindness at
        # scale" + "Cross-model verdict-style divergence" tables.
        #   diagnostic_primary: ALLOW=0, REVIEW=77, DENY=23 (matches canonical)
        #   diagnostic_claude:  ALLOW=35, REVIEW=20, DENY=45 (decision_log)
        #                       canonical sheet says 36/20/44 → drift fires.
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
    """Three-band classification per `predictions.md` P5 (locked 2026-05-27).

    Locked bands (predictions.md:48-49):
      - Confirmation: Cat 2 ≥ 60% AND Cat 1 ≤ 15%
      - Falsification: Cat 1 > 25% ("names the inversion" > 25%)

    Anything between is **Under-tested** per the locked disposition
    vocabulary at predictions.md:68 (and inherited from E1/E2).

    Concretely this means diagnostic_primary first-pass (Cat1=8%, Cat2=25%)
    lands at Under-tested — Cat 2 is well below the 60% confirmation floor
    but Cat 1 is also well below the 25% falsification ceiling. The
    reconciled sheets (Cat1=7%, Cat2=93% for primary; 0/100 for claude)
    still hit Confirmed.
    """
    if n == 0:
        return "n/a"
    cat1_pct = 100.0 * cat_counts.get(1, 0) / n
    cat2_pct = 100.0 * cat_counts.get(2, 0) / n
    if cat1_pct > 25.0:
        return "Falsified"
    if cat2_pct >= 60.0 and cat1_pct <= 15.0:
        return "Confirmed"
    return "Under-tested"


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
# Set-intersection auditing: surface any E2-L3-DENY OCIDs missing from
# the E3 l4_without_nudge corpus before we compute the retention rate.
missing_from_e3_l4_no_nudge = sorted(e2_l3_deny_ocids - set(e3_l4_no_nudge_by_ocid))
if missing_from_e3_l4_no_nudge:
    msg = (
        f"E2 L3-DENY OCIDs missing from E3 l4_without_nudge: "
        f"{len(missing_from_e3_l4_no_nudge)} record(s) — first few: "
        f"{missing_from_e3_l4_no_nudge[:5]}"
    )
    print(f"  WARNING: {msg}")
    WARNINGS.append(msg)
assert len(e2_l3_deny_ocids) == 107, (
    f"E2 L3-DENY set size {len(e2_l3_deny_ocids)} != 107 expected — "
    f"retention denominator drift"
)
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
# Surface OCIDs in diagnostic_primary that don't have an E2 L4 partner —
# the denominator would otherwise be silently shrunk by missing records.
missing_diag_primary = sorted(set(e3_diag_by_ocid) - set(e2_l4_verdicts))
if missing_diag_primary:
    msg = (
        f"diagnostic_primary OCIDs missing from E2 L4 corpus: "
        f"{len(missing_diag_primary)} record(s) — first few: "
        f"{missing_diag_primary[:5]}"
    )
    print(f"  WARNING: {msg}")
    WARNINGS.append(msg)
assert len(diag_ocids) >= 100, (
    f"diagnostic_primary ∩ E2 L4 = {len(diag_ocids)} (expected ≥ 100); "
    f"missing: {missing_diag_primary}"
)
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
missing_diag_claude = sorted(set(e3_diag_claude_by_ocid) - set(e2_l4_verdicts))
if missing_diag_claude:
    msg = (
        f"diagnostic_claude OCIDs missing from E2 L4 corpus: "
        f"{len(missing_diag_claude)} record(s) — first few: "
        f"{missing_diag_claude[:5]}"
    )
    print(f"  WARNING: {msg}")
    WARNINGS.append(msg)
assert len(diag_claude_ocids) >= 100, (
    f"diagnostic_claude ∩ E2 L4 = {len(diag_claude_ocids)} (expected ≥ 100); "
    f"missing: {missing_diag_claude}"
)
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


def pairs_by_ocid(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    label: str = "",
) -> list[tuple[int, int]]:
    """Pair coder-A and coder-B categories by OCID; warn on any silent drops.

    A non-empty symmetric difference between the two coders' OCID sets is
    a methodological smell — the κ reported below will silently ignore the
    dropped records. Surface it in WARNINGS so the writeup carries the
    honest n alongside the κ value.
    """
    a_by = {r["ocid"]: int(r["category"]) for r in a}
    b_by = {r["ocid"]: int(r["category"]) for r in b}
    only_a = sorted(set(a_by) - set(b_by))
    only_b = sorted(set(b_by) - set(a_by))
    if only_a or only_b:
        msg = (
            f"κ pair-by-ocid drift ({label or 'unlabelled'}): "
            f"|only-a|={len(only_a)} |only-b|={len(only_b)} "
            f"(common n={len(set(a_by) & set(b_by))})"
        )
        print(f"  WARNING: {msg}")
        WARNINGS.append(msg)
    common = sorted(set(a_by) & set(b_by))
    return [(a_by[ocid], b_by[ocid]) for ocid in common]


print("\n=== Inter-coder Cohen's κ ===\n")

kappa_rows: list[dict[str, Any]] = []
kappa_table = [
    ("primary  first-pass ↔ blind-agent",
     pairs_by_ocid(rubric_primary_first, rubric_primary_blind,
                   "primary first-pass ↔ blind-agent")),
    ("primary  first-pass ↔ reconciled",
     pairs_by_ocid(rubric_primary_first, rubric_primary,
                   "primary first-pass ↔ reconciled")),
    ("primary  reconciled ↔ blind-agent",
     pairs_by_ocid(rubric_primary, rubric_primary_blind,
                   "primary reconciled ↔ blind-agent")),
    ("claude   reconciled ↔ blind-agent",
     pairs_by_ocid(rubric_claude, rubric_claude_blind,
                   "claude reconciled ↔ blind-agent")),
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

# ---------------------------------------------------------------------------
# Disposition discipline (locked 2026-06-07 during Phase 3 analysis review).
#
# Apply this rule everywhere a disposition is computed:
#   1. If observed values meet the locked confirmation band → "Confirmed".
#   2. If predictions.md registers an EXPLICIT falsification band and the
#      observed values meet it → "Falsified".
#   3. Otherwise → "Under-tested" (per the locked disposition vocabulary at
#      predictions.md:68 — Confirmed / Falsified / Inverted / Refuted /
#      Deferred / Under-tested).
#
# This discipline means the script never invents a falsification rule
# where predictions.md is silent. Any deviation (e.g. P1's Arm A 3.5%
# observed value being so far below the 20% confirmation band that calling
# it Falsified is defensible) is a SCRIPT-TIME JUDGMENT and must be
# disclosed in the disposition_methodology block below.
#
# Locked bands (predictions.md, 2026-05-27 calibration):
#   P1 — Confirm:   Arm A DENY ≥ 20% AND Arm C DENY ≤ 12%.
#        Falsify:   Arm C ≥ 20%  OR  Arm A < 20%.
#   P2 — Confirm:   |Arm A − Arm B| ≥ 15pp.
#        Falsify:   (none registered.)
#   P3 — Confirm:   L4-no-nudge retention of E2 L3-DENY ≥ 80%.
#        Falsify:   retention ≤ 65%.
#   P4 — Confirm:   diagnostic_primary same-as-L4 ≥ 90%.
#        Falsify:   (none registered.)
#   P5 — Confirm:   Cat 2 ≥ 60% AND Cat 1 ≤ 15%.
#        Falsify:   Cat 1 > 25%.
#   P6 — Confirm:   |primary same% − claude same%| ≤ 15pp.
#        Falsify:   gap > 15pp. (Explicit per predictions.md:53.)
#
# Note that P2 and P4 do not register a falsification band. The honest
# disposition for observed values outside the confirmation band on those
# predictions is Under-tested.
# ---------------------------------------------------------------------------

# Track disposition methodology so the OUTPUTS JSON and the writeup
# carry the honest disclosure forward.
disposition_methodology: dict[str, dict[str, str]] = {}

# P1 — predictions.md locks BOTH a confirmation band AND a falsification
# band ("Arm C ≥ 20% OR Arm A < 20% → Falsified"). So the locked rule is:
if arm_a_deny < 20.0 or arm_c_deny >= 20.0:
    p1_disposition = "Falsified"
elif arm_a_deny >= 20.0 and arm_c_deny <= 12.0:
    p1_disposition = "Confirmed"
else:
    p1_disposition = "Under-tested"
# P1 IS using the explicit pre-registered falsification band. The
# observed Arm A = 3.5% is dramatically outside the 20-30% anticipated
# directional range from predictions.md:25 ("accumulation amplifies"),
# and trips the locked "Arm A < 20%" falsification clause. So this is
# Falsified by locked spec, not script judgment.
disposition_methodology["P1"] = {
    "rule_source": "locked",
    "confirmation_band": "Arm A DENY >= 20% AND Arm C DENY <= 12%",
    "falsification_band": "Arm A DENY < 20% OR Arm C DENY >= 20%",
    "note": (
        "Observed Arm A 3.5% trips locked falsification clause "
        "'Arm A < 20%'. predictions.md:25 anticipated 20-30% as the "
        "directional-confirm range; 3.5% is so far below that range "
        "the falsification is unambiguous."
    ),
}

# P2 — predictions.md locks ONLY the confirmation band (|A−B| ≥ 15pp).
# No falsification band is registered. Honest disposition for observed
# values outside the confirmation band is Under-tested.
# Observed |3.5 − 0.0| = 3.5pp, well below 15pp confirm.
p2_gap = arm_a_deny - arm_b_deny
if abs(p2_gap) >= 15.0:
    p2_disposition = "Confirmed"
else:
    p2_disposition = "Under-tested"
disposition_methodology["P2"] = {
    "rule_source": "locked",
    "confirmation_band": "|Arm A DENY - Arm B DENY| >= 15pp",
    "falsification_band": "(none registered in predictions.md)",
    "note": (
        "predictions.md only locks the confirmation band. Observed gap "
        "+3.5pp is well below 15pp confirm and there is no falsification "
        "band to trigger; honest disposition is Under-tested. The earlier "
        "script-introduced '|A−B| < 5pp → Falsified' rule was post-hoc "
        "and has been removed."
    ),
}

# P3 — predictions.md locks BOTH bands explicitly (Confirm ≥ 80%,
# Falsify ≤ 65%). Locked rule.
if retention_pct >= 80.0:
    p3_disposition = "Confirmed"
elif retention_pct <= 65.0:
    p3_disposition = "Falsified"
else:
    p3_disposition = "Under-tested"
disposition_methodology["P3"] = {
    "rule_source": "locked",
    "confirmation_band": "retention >= 80%",
    "falsification_band": "retention <= 65%",
    "note": (
        "Observed retention 60.7% trips the explicit falsification band. "
        "predictions.md:37 locks both bands; this is a clean locked-spec "
        "disposition."
    ),
}

# P4 — predictions.md locks ONLY the confirmation band (≥ 90%).
# Observed 88% is 2pp below the confirmation floor; no falsification
# band registered. Honest disposition is Under-tested.
if sv_pct >= 90.0:
    p4_disposition = "Confirmed"
else:
    p4_disposition = "Under-tested"
disposition_methodology["P4"] = {
    "rule_source": "locked",
    "confirmation_band": "same-as-L4 >= 90%",
    "falsification_band": "(none registered in predictions.md)",
    "note": (
        "Observed 88% is 2pp below the 90% confirmation floor. "
        "predictions.md does not register a falsification band for P4; "
        "honest disposition is Under-tested. The earlier "
        "script-introduced 'else: Falsified' rule was post-hoc and has "
        "been removed. Methods-note discipline refinement: future "
        "predictions for 'robustness at scale' claims should "
        "pre-register both confirm and falsify bands."
    ),
}

# P5 — three-band classification, locked. Delegated to p5_disposition().
p5_primary = rubric_summary["diagnostic_primary_reconciled"]["p5_disposition"]
p5_claude = rubric_summary["diagnostic_claude_reconciled"]["p5_disposition"]
p5_primary_first_pass = rubric_summary["diagnostic_primary_first_pass"]["p5_disposition"]
disposition_methodology["P5"] = {
    "rule_source": "locked",
    "confirmation_band": "Cat 2 >= 60% AND Cat 1 <= 15%",
    "falsification_band": "Cat 1 > 25%",
    "note": (
        "Three-band classifier per predictions.md:48-49. Reconciled "
        "sheets confirm both arms (P5a 7%/93%, P5b 0%/100%). "
        "First-pass primary (Cat1=8%, Cat2=25%) lands at Under-tested — "
        "well below confirm, well below the 25% Cat-1 falsification "
        "ceiling."
    ),
}

# P6 — predictions.md:52-53 locks BOTH a confirmation band (≤ 15pp) AND
# an explicit falsification band ("Falsified if the gap > 15pp"). Locked.
if p6_gap <= 15.0:
    p6_disposition = "Confirmed"
else:
    p6_disposition = "Falsified"
disposition_methodology["P6"] = {
    "rule_source": "locked",
    "confirmation_band": "|primary same% - claude same%| <= 15pp",
    "falsification_band": "gap > 15pp (explicit, predictions.md:53)",
    "note": (
        "Observed 46pp gap is far outside the explicit 15pp "
        "falsification band. predictions.md:53 pre-registered this "
        "outcome as 'a strong finding, not a failure' — the model-"
        "specific behaviour is substantively interesting."
    ),
}

disposition_table = [
    ("P1", "Confirm: Arm A DENY ≥ 20% AND Arm C DENY ≤ 12%; Falsify: Arm A < 20% OR Arm C ≥ 20%",
     f"Arm A {arm_a_deny:.1f}%, Arm C {arm_c_deny:.1f}%", p1_disposition),
    ("P2", "Confirm: |Arm A − Arm B| ≥ 15pp; Falsify: (none registered)",
     f"gap = {p2_gap:+.1f}pp (A={arm_a_deny:.1f}%, B={arm_b_deny:.1f}%)", p2_disposition),
    ("P3", "Confirm: retention ≥ 80%; Falsify: retention ≤ 65%",
     f"retention = {retention_pct:.1f}% ({retained_deny}/{retention_n})", p3_disposition),
    ("P4", "Confirm: same-as-L4 ≥ 90%; Falsify: (none registered)",
     f"same = {sv_pct:.1f}% ({same_verdict}/{sv_n})", p4_disposition),
    ("P5a", "Confirm: Cat 2 ≥ 60% AND Cat 1 ≤ 15%; Falsify: Cat 1 > 25% (diagnostic_primary reconciled)",
     f"Cat1 {rubric_summary['diagnostic_primary_reconciled']['cat_1_pct']:.1f}%, "
     f"Cat2 {rubric_summary['diagnostic_primary_reconciled']['cat_2_pct']:.1f}%", p5_primary),
    ("P5b", "Confirm: Cat 2 ≥ 60% AND Cat 1 ≤ 15%; Falsify: Cat 1 > 25% (diagnostic_claude reconciled)",
     f"Cat1 {rubric_summary['diagnostic_claude_reconciled']['cat_1_pct']:.1f}%, "
     f"Cat2 {rubric_summary['diagnostic_claude_reconciled']['cat_2_pct']:.1f}%", p5_claude),
    ("P5-fp", "Same as P5 (diagnostic_primary first-pass — methods-disclosure row, not a separate prediction)",
     f"Cat1 {rubric_summary['diagnostic_primary_first_pass']['cat_1_pct']:.1f}%, "
     f"Cat2 {rubric_summary['diagnostic_primary_first_pass']['cat_2_pct']:.1f}%", p5_primary_first_pass),
    ("P6", "Confirm: |primary − claude| ≤ 15pp; Falsify: gap > 15pp (explicit)",
     f"gap = {p6_gap:.1f}pp (primary {sv_pct:.1f}%, claude {sc_pct:.1f}%)", p6_disposition),
]

print(f"  {'ID':<6} {'Locked threshold':<90} {'Observed':<48} {'Disposition':<14}")
print("  " + "-" * 160)
for pid, threshold, observed, disp in disposition_table:
    print(f"  {pid:<6} {threshold:<90} {observed:<48} {disp:<14}")

OUTPUTS["disposition_table"] = [
    {"id": pid, "threshold": threshold, "observed": observed, "disposition": disp}
    for pid, threshold, observed, disp in disposition_table
]
OUTPUTS["disposition_methodology"] = disposition_methodology

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
# ## 8a. Optional Ed25519 signature spot-check (`--verify-sample N`)
#
# Closes the loop on the methodology paper's "every receipt verifiable"
# claim. Selects N randomly-sampled bundles across the six Phase 2 arm
# directories and runs them through `runner/scripts/verify_smoke_e3.py`'s
# `verify_bundle` (Ed25519 against the experiment-tenant pinned public
# key). Skipped if N=0 (default) or if the verifier module isn't
# importable from the script's path. Result lands in OUTPUTS JSON.

# %%
def _maybe_load_verifier() -> Any:
    """Import verify_smoke_e3 from the runner scripts dir. Returns the
    module or None if the import fails."""
    verifier_path = (
        REPO_ROOT
        / "procurement-context-disambiguation"
        / "runner"
        / "scripts"
        / "verify_smoke_e3.py"
    )
    if not verifier_path.exists():
        return None
    sys.path.insert(0, str(verifier_path.parent))
    try:
        import verify_smoke_e3  # type: ignore[import-not-found]
        return verify_smoke_e3
    except Exception as exc:
        print(f"  signature verify: importing verify_smoke_e3 failed ({exc!r}); skipping.")
        return None


verify_sample_n = int(_ARGS.verify_sample)
verify_result: dict[str, Any] = {
    "enabled": verify_sample_n > 0,
    "n_requested": verify_sample_n,
}

if verify_sample_n > 0:
    print("\n=== Signature spot-check ===\n")
    verifier_mod = _maybe_load_verifier()
    if verifier_mod is None:
        verify_result["status"] = "skipped"
        verify_result["reason"] = (
            "verify_smoke_e3 module not importable from "
            "procurement-context-disambiguation/runner/scripts/. "
            "Likely missing PyNaCl/cryptography deps in the runtime "
            "venv. Run analysis.py from the runner venv to enable."
        )
        msg = (
            f"signature spot-check requested (N={verify_sample_n}) but "
            "verifier module not importable; result deferred"
        )
        print(f"  {verify_result['reason']}")
        WARNINGS.append(msg)
    else:
        # Build the population: every (arm, bundle_path) across the six
        # Phase 2 arm subdirs.
        population: list[tuple[str, Path]] = []
        for arm in EXPECTED_COUNTS:
            for bundle_path in sorted((E3_PHASE2 / arm).glob("*.bundle.json")):
                population.append((arm, bundle_path))
        rng = random.Random(int(_ARGS.verify_seed))
        sample_n = min(verify_sample_n, len(population))
        sample = rng.sample(population, sample_n)
        passed = 0
        failures: list[dict[str, Any]] = []
        for arm, bundle_path in sample:
            try:
                report = verifier_mod.verify_bundle(bundle_path, arm)
                ok = getattr(report, "passed", None)
                # BundleReport.passed is a property in verify_smoke_e3; in
                # case of API shift, fall back to "no errors recorded".
                if ok is None:
                    ok = not getattr(report, "errors", ["unknown"])
                if ok:
                    passed += 1
                else:
                    failures.append({
                        "arm": arm,
                        "bundle": str(bundle_path.relative_to(REPO_ROOT)),
                        "errors": list(getattr(report, "errors", [])),
                    })
            except Exception as exc:
                failures.append({
                    "arm": arm,
                    "bundle": str(bundle_path.relative_to(REPO_ROOT)),
                    "errors": [f"verifier raised: {exc!r}"],
                })
        verify_result["status"] = "ran"
        verify_result["seed"] = int(_ARGS.verify_seed)
        verify_result["n_population"] = len(population)
        verify_result["n_sampled"] = sample_n
        verify_result["n_passed"] = passed
        verify_result["n_failed"] = sample_n - passed
        verify_result["failures"] = failures
        print(
            f"  sampled {sample_n} of {len(population)} bundles (seed={_ARGS.verify_seed}): "
            f"passed={passed}  failed={sample_n - passed}"
        )
        if failures:
            msg = f"signature spot-check: {len(failures)} failure(s) of {sample_n}"
            print(f"  {msg}")
            WARNINGS.append(msg)
            for failure in failures[:5]:
                print(f"    - {failure['bundle']}: {failure['errors']}")
else:
    verify_result["status"] = "not_requested"

OUTPUTS["signature_spot_check"] = verify_result

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
    # Default is fatal so CI / `python analysis.py` surfaces drift loudly.
    # Set E3_DRIFT_FATAL=0 in interactive sessions to keep iterating
    # despite known/expected drift (e.g. while updating anchors).
    fatal = os.environ.get("E3_DRIFT_FATAL", "1") not in ("0", "false", "False", "")
    sys.exit(1 if fatal else 0)
else:
    print("\nAll computed numbers within 1% of sanity anchors.")
