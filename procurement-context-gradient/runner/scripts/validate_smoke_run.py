#!/usr/bin/env python3
"""E2-007 smoke run validator — §3a through §3g.

Runs after `scripts/smoke_live.py` produces a run directory and
`scripts/verify_smoke_bundles.py` has confirmed cryptographic integrity.

Validates §3b through §3g of the E2-007 package contract:

  §3b — Level field correctly distributed across the 16 bundles
  §3c — Level-batching observed (max(L0 timestamps) < min(L1), etc)
  §3d — Cache savings observed at L4 (cached_tokens > 0 on 2nd/3rd L4)
  §3e — L0 verdict reproduction vs E1 (3 OCIDs × MeshQu+agent table)
  §3f — Permuted-Policy pilot agent reasoning verbatim
  §3g — Integrity-hash distinctness: worked-example main L4 vs L4_PERMUTED

§3a (offline cryptographic verification) lives in
`scripts/verify_smoke_bundles.py` — run that first and feed its exit
code into the PR-body answers.

## Usage

    python scripts/validate_smoke_run.py <run_dir>

Outputs a Markdown report to stdout. Exits 0 if every check passes,
1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


WORKED_EXAMPLE_OCID = "ocds-b5fd17-282a00c5-37ef-4eed-b308-f2735d803e4f"
WORKED_EXAMPLE_E1_DECISION_ID = "ca19e737-defb-4e5f-b216-ec97d2fe5859"
E1_ARCHIVE_RUN_ID = "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
MAIN_LEVELS = ("L0", "L1", "L2", "L3", "L4")


def load_bundles(run_dir: Path) -> list[dict[str, Any]]:
    """Load every bundle under {L0..L4, diagnostic}/."""
    bundles: list[dict[str, Any]] = []
    for sub in ("L0", "L1", "L2", "L3", "L4", "diagnostic"):
        d = run_dir / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.bundle.json")):
            with p.open("r", encoding="utf-8") as fp:
                bundle = json.load(fp)
            bundle["__path__"] = str(p)
            bundle["__level_dir__"] = sub
            bundles.append(bundle)
    return bundles


def load_e1_traces(repo_dir: Path) -> dict[str, dict[str, Any]]:
    """Read the frozen E1 dry-run decision_traces, indexed by OCID."""
    path = (
        repo_dir
        / "procurement-decisions"
        / "results"
        / "runs"
        / E1_ARCHIVE_RUN_ID
        / "decision_traces.jsonl"
    )
    by_ocid: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ocid = row.get("ocid")
            if ocid and ocid not in by_ocid:
                by_ocid[ocid] = row
    return by_ocid


# ---------------------------------------------------------------------------
# §3b — level field distribution
# ---------------------------------------------------------------------------


def check_3b_level_distribution(bundles: list[dict[str, Any]]) -> tuple[bool, str]:
    by_level: defaultdict[str, int] = defaultdict(int)
    by_level_field_mismatches: list[str] = []
    for b in bundles:
        level = b.get("governance_context_level")
        by_level[level] += 1
        # The level field on the bundle wrapper MUST match the directory it
        # lives in for main-grid bundles (diagnostic lives in `diagnostic/`
        # but carries `L4_PERMUTED`, so its directory name differs by design).
        dir_name = b["__level_dir__"]
        if dir_name == "diagnostic":
            if level != "L4_PERMUTED":
                by_level_field_mismatches.append(
                    f"diagnostic bundle {b['__path__']} has level {level!r} (expected L4_PERMUTED)"
                )
        elif level != dir_name:
            by_level_field_mismatches.append(
                f"{b['__path__']} has level {level!r} but lives in {dir_name!r}/"
            )

    lines = []
    lines.append("### §3b — Level field distribution")
    for level in ("L0", "L1", "L2", "L3", "L4", "L4_PERMUTED"):
        lines.append(f"  {level:<14} {by_level.get(level, 0)} bundle(s)")
    ok = True
    expected = {"L0": 3, "L1": 3, "L2": 3, "L3": 3, "L4": 3, "L4_PERMUTED": 1}
    for k, v in expected.items():
        if by_level.get(k, 0) != v:
            ok = False
            lines.append(f"  MISMATCH: {k} got {by_level.get(k, 0)}, expected {v}")
    if by_level_field_mismatches:
        ok = False
        lines.extend("  " + s for s in by_level_field_mismatches)
    lines.append(f"  Status: {'PASS' if ok else 'FAIL'}")
    return ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# §3c — level batching (max L0 < min L1 < max L1 < min L2 < ...)
# ---------------------------------------------------------------------------


def check_3c_level_batching(bundles: list[dict[str, Any]]) -> tuple[bool, str]:
    main_bundles = [b for b in bundles if b.get("governance_context_level") in MAIN_LEVELS]
    by_level: defaultdict[str, list[str]] = defaultdict(list)
    for b in main_bundles:
        by_level[b["governance_context_level"]].append(b["timestamp"])
    lines = ["### §3c — Level-batching (timestamps progress level-by-level)"]
    ok = True
    prev_max: str | None = None
    prev_level: str | None = None
    for level in MAIN_LEVELS:
        ts = sorted(by_level.get(level, []))
        if not ts:
            ok = False
            lines.append(f"  {level}: NO timestamps observed")
            continue
        mn, mx = ts[0], ts[-1]
        lines.append(f"  {level}: min={mn}  max={mx}")
        if prev_max is not None and prev_level is not None:
            # Allow equal: ISO-8601 seconds may collide on a single second
            if mn < prev_max:
                ok = False
                lines.append(
                    f"    OVERLAP: {level} min ({mn}) < {prev_level} max ({prev_max})"
                )
        prev_max = mx
        prev_level = level
    lines.append(f"  Status: {'PASS' if ok else 'FAIL'}")
    return ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# §3d — cache savings at L4
# ---------------------------------------------------------------------------


def check_3d_cache_savings(run_dir: Path) -> tuple[bool, str]:
    telem_path = run_dir / "cache_telemetry.jsonl"
    lines = ["### §3d — Cache savings observed at L4"]
    if not telem_path.exists():
        return False, "\n".join(lines + ["  NO cache_telemetry.jsonl found — FAIL"])

    rows: list[dict[str, Any]] = []
    with telem_path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    l4_rows = sorted(
        [r for r in rows if r.get("level") == "L4"],
        key=lambda r: r.get("timestamp") or "",
    )
    lines.append(f"  {len(l4_rows)} L4 telemetry rows")
    n_with_observed = 0
    n_hits = 0
    cached_total = 0
    prompt_total = 0
    for i, r in enumerate(l4_rows):
        ct = r.get("cached_tokens")
        pt = r.get("prompt_tokens")
        lines.append(
            f"    call #{i + 1}  ocid={r.get('ocid','?')}  "
            f"cached_tokens={ct}  prompt_tokens={pt}"
        )
        if ct is not None:
            n_with_observed += 1
            cached_total += ct
            if ct > 0:
                n_hits += 1
        if pt is not None:
            prompt_total += pt

    # §3d demand: the 3rd L4 call has cached_tokens > 0; bonus if 2nd does too.
    # Our smoke has exactly 3 records → 3 L4 calls.
    ok = False
    detail: list[str] = []
    if not l4_rows:
        detail.append("no L4 rows — FAIL")
    else:
        # First-call cache miss is expected. Look at calls 2 and 3.
        later_hits = [r for r in l4_rows[1:] if (r.get("cached_tokens") or 0) > 0]
        if later_hits:
            ok = True
            detail.append(
                f"{len(later_hits)}/{len(l4_rows) - 1} post-first L4 calls observed cached_tokens > 0"
            )
        else:
            detail.append(
                "no post-first L4 call observed cached_tokens > 0 — cache preservation FAIL"
            )

    hit_fraction = (n_hits / n_with_observed) if n_with_observed else 0.0
    lines.append(
        f"  L4 cache: n={len(l4_rows)} observed={n_with_observed} "
        f"hits={n_hits} fraction={hit_fraction:.3f} "
        f"mean_cached={cached_total / max(n_with_observed, 1):.1f} "
        f"mean_prompt={prompt_total / max(n_with_observed, 1):.1f}"
    )
    lines.extend("  " + s for s in detail)
    lines.append(f"  Status: {'PASS' if ok else 'FAIL'}")
    return ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# §3e — L0 reproducibility vs E1
# ---------------------------------------------------------------------------


def check_3e_l0_reproducibility(
    bundles: list[dict[str, Any]],
    e1_by_ocid: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    lines = ["### §3e — L0 vs E1 verdict reproducibility"]
    l0_bundles = [
        b for b in bundles if b.get("governance_context_level") == "L0"
    ]
    rows: list[dict[str, Any]] = []
    meshqu_mismatches = 0
    agent_mismatches = 0
    for b in l0_bundles:
        ocid = b.get("ocid")
        e1 = e1_by_ocid.get(ocid) if ocid else None
        e1_meshqu = e1.get("meshqu_verdict") if e1 else None
        e1_agent = e1.get("agent_verdict") if e1 else None
        l0_meshqu = (b.get("receipt") or {}).get("decision")
        l0_agent = (b.get("agent") or {}).get("verdict")
        meshqu_match = e1_meshqu == l0_meshqu
        agent_match = e1_agent == l0_agent
        if not meshqu_match:
            meshqu_mismatches += 1
        if not agent_match:
            agent_mismatches += 1
        rows.append(
            {
                "ocid": ocid,
                "e1_meshqu": e1_meshqu,
                "l0_meshqu": l0_meshqu,
                "e1_agent": e1_agent,
                "l0_agent": l0_agent,
                "meshqu_match": meshqu_match,
                "agent_match": agent_match,
            }
        )

    lines.append("")
    lines.append("| OCID | E1 MeshQu | L0 MeshQu | match | E1 agent | L0 agent | match |")
    lines.append("|------|-----------|-----------|-------|----------|----------|-------|")
    for r in rows:
        lines.append(
            f"| `{(r['ocid'] or '?')[:50]}` | {r['e1_meshqu']} | {r['l0_meshqu']} | "
            f"{'YES' if r['meshqu_match'] else 'NO'} | "
            f"{r['e1_agent']} | {r['l0_agent']} | "
            f"{'YES' if r['agent_match'] else 'NO'} |"
        )

    # Decision rule from the package: MeshQu mismatch on ≥2 of 3 is
    # investigation-worthy; we report but don't fail. MeshQu mismatch on
    # 0 of 3 is the happy path. Agent mismatch is expected drift (P4
    # reproducibility band).
    ok = meshqu_mismatches == 0
    lines.append("")
    lines.append(
        f"  MeshQu mismatches: {meshqu_mismatches}/{len(rows)} "
        f"  Agent mismatches: {agent_mismatches}/{len(rows)} (drift expected per P4 band)"
    )
    lines.append(
        f"  Status: {'PASS' if ok else 'FAIL — investigate substrate or hash binding'}"
    )
    return ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# §3f — Permuted-Policy pilot reasoning verbatim
# ---------------------------------------------------------------------------


def check_3f_permuted_reasoning(bundles: list[dict[str, Any]]) -> tuple[bool, str]:
    lines = ["### §3f — Permuted-Policy pilot agent reasoning (verbatim)"]
    diag = [b for b in bundles if b.get("governance_context_level") == "L4_PERMUTED"]
    if not diag:
        return False, "\n".join(lines + ["  NO L4_PERMUTED bundle found — FAIL"])
    b = diag[0]
    agent = b.get("agent") or {}
    receipt = b.get("receipt") or {}
    reasoning = agent.get("reasoning") or "<no reasoning>"
    lines.append(f"  OCID:        `{b.get('ocid')}`")
    lines.append(f"  Decision id: `{b.get('decision_id')}`")
    lines.append(f"  Agent verdict: {agent.get('verdict')}")
    lines.append(f"  MeshQu decision: {receipt.get('decision')}")
    lines.append("")
    lines.append("  Reasoning (verbatim):")
    lines.append("  ```")
    for raw_line in reasoning.splitlines() or [reasoning]:
        lines.append(f"  {raw_line}")
    lines.append("  ```")
    lines.append("  Status: PASS (qualitative; Sam to read the reasoning above)")
    return True, "\n".join(lines)


# ---------------------------------------------------------------------------
# §3g — integrity-hash distinctness (worked example main L4 vs L4_PERMUTED)
# ---------------------------------------------------------------------------


def check_3g_hash_distinctness(bundles: list[dict[str, Any]]) -> tuple[bool, str]:
    lines = ["### §3g — Integrity-hash distinctness (worked example)"]
    worked_l4 = next(
        (
            b
            for b in bundles
            if b.get("governance_context_level") == "L4"
            and b.get("ocid") == WORKED_EXAMPLE_OCID
        ),
        None,
    )
    worked_permuted = next(
        (
            b
            for b in bundles
            if b.get("governance_context_level") == "L4_PERMUTED"
            and b.get("ocid") == WORKED_EXAMPLE_OCID
        ),
        None,
    )
    if not worked_l4:
        return False, "\n".join(lines + ["  Worked-example L4 main bundle missing — FAIL"])
    if not worked_permuted:
        return False, "\n".join(
            lines + ["  Worked-example L4_PERMUTED bundle missing — FAIL"]
        )
    h_main = (worked_l4.get("receipt") or {}).get("integrity_hash")
    h_perm = (worked_permuted.get("receipt") or {}).get("integrity_hash")
    lines.append(f"  L4 main         integrity_hash: `{h_main}`")
    lines.append(f"  L4_PERMUTED     integrity_hash: `{h_perm}`")
    ok = bool(h_main) and bool(h_perm) and (h_main != h_perm)
    lines.append(f"  Distinct? {'YES' if ok else 'NO'}")
    lines.append(f"  Status: {'PASS' if ok else 'FAIL — policy_permutation_seed not hash-bound'}")
    return ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# Cost projection (§4)
# ---------------------------------------------------------------------------


def projection(run_dir: Path, bundles: list[dict[str, Any]]) -> str:
    """Use the cache_telemetry.jsonl prompt_tokens distribution and a
    reasonable per-call output-token estimate to project a 1,415-main +
    14-diagnostic full run cost.

    Pricing: gpt-5.4-2026-03-05 list pricing (locked in E1 manifest
    notes; if pricing changes, recompute against the current sheet).
    Source: locked at v0.2-model-locked time. Cached input is billed
    at 25% of regular input per OpenAI pricing.
    """
    # These numbers are illustrative — Sam can replace with current
    # rate-card figures if needed. The script's purpose is to surface
    # the per-call token usage so the PR body has a number to anchor on.
    INPUT_USD_PER_1M = 3.00
    OUTPUT_USD_PER_1M = 15.00
    CACHED_INPUT_USD_PER_1M = 0.75  # 25% of input

    telem_path = run_dir / "cache_telemetry.jsonl"
    rows: list[dict[str, Any]] = []
    if telem_path.exists():
        with telem_path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rows.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue

    # Output tokens aren't in cache_telemetry. Estimate from each bundle's
    # agent.raw_response length / 4 (rough chars→tokens). Better than
    # nothing for a smoke-cost projection.
    output_tokens_per_call = []
    for b in bundles:
        raw_resp = (b.get("agent") or {}).get("raw_response") or ""
        output_tokens_per_call.append(max(len(raw_resp) // 4, 1))
    avg_output = sum(output_tokens_per_call) / max(len(output_tokens_per_call), 1)

    # Per-level prompt token aggregates from the telemetry.
    by_level: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_level[r.get("level") or "?"].append(r)

    out_lines = ["### §4 — Cost projection from observed token usage", ""]
    out_lines.append(
        f"  Output-token estimate: ~{avg_output:.0f} tokens / call "
        f"(chars/4 over {len(output_tokens_per_call)} bundles)"
    )
    out_lines.append("")
    total_projected_usd = 0.0
    out_lines.append("| Level | Smoke calls | Mean prompt | Mean cached | Full-run calls |  Projected USD |")
    out_lines.append("|------:|------------:|------------:|------------:|---------------:|---------------:|")
    full_run_counts = {"L0": 283, "L1": 283, "L2": 283, "L3": 283, "L4": 283, "L4_PERMUTED": 14}
    for level in ("L0", "L1", "L2", "L3", "L4", "L4_PERMUTED"):
        level_rows = by_level.get(level, [])
        n_smoke = len(level_rows)
        prompts = [r.get("prompt_tokens") for r in level_rows if r.get("prompt_tokens") is not None]
        cacheds = [r.get("cached_tokens") for r in level_rows if r.get("cached_tokens") is not None]
        mean_prompt = sum(prompts) / max(len(prompts), 1) if prompts else 0
        mean_cached = sum(cacheds) / max(len(cacheds), 1) if cacheds else 0
        regular_input = max(mean_prompt - mean_cached, 0)
        cached_input = mean_cached
        per_call_usd = (
            (regular_input / 1_000_000) * INPUT_USD_PER_1M
            + (cached_input / 1_000_000) * CACHED_INPUT_USD_PER_1M
            + (avg_output / 1_000_000) * OUTPUT_USD_PER_1M
        )
        n_full = full_run_counts.get(level, 0)
        projected = per_call_usd * n_full
        total_projected_usd += projected
        out_lines.append(
            f"| {level:<12} | {n_smoke:>11} | {mean_prompt:>11.0f} | {mean_cached:>11.0f} | "
            f"{n_full:>14} | {projected:>13.4f} |"
        )
    out_lines.append("")
    out_lines.append(
        f"  **Total projected full-run cost: USD ${total_projected_usd:.2f}** "
        f"(1,415 main + 14 diagnostic calls; assumes cache hit rates observed at L4 "
        f"hold at corpus scale)"
    )
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E2-007 smoke run validator")
    parser.add_argument("run_dir", type=Path, help="Path to results/runs/<run_id>/")
    args = parser.parse_args(argv)

    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")

    # repo_dir = <meshqu-research>; run_dir is <repo>/procurement-context-gradient/results/runs/<id>
    repo_dir = run_dir.parents[3]

    bundles = load_bundles(run_dir)
    e1_by_ocid = load_e1_traces(repo_dir)

    print(f"# E2-007 smoke validation — {run_dir.name}")
    print()
    print(f"Run directory: `{run_dir.relative_to(repo_dir)}`")
    print(f"Bundles loaded: {len(bundles)}")
    print()

    checks = [
        ("§3b", check_3b_level_distribution(bundles)),
        ("§3c", check_3c_level_batching(bundles)),
        ("§3d", check_3d_cache_savings(run_dir)),
        ("§3e", check_3e_l0_reproducibility(bundles, e1_by_ocid)),
        ("§3f", check_3f_permuted_reasoning(bundles)),
        ("§3g", check_3g_hash_distinctness(bundles)),
    ]
    all_ok = True
    for tag, (ok, report) in checks:
        print(report)
        print()
        if not ok and tag in ("§3b", "§3c", "§3d", "§3e", "§3g"):
            # §3f is qualitative — never fails the run automatically.
            all_ok = False

    print(projection(run_dir, bundles))
    print()
    print("---")
    print(f"Overall: **{'PASS' if all_ok else 'FAIL'}**")
    return 0 if all_ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
