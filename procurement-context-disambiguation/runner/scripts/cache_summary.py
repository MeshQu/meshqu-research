"""Post-run cache-telemetry summary (E2-005).

Reads `<run_dir>/cache_telemetry.jsonl` and prints per-level
cache-hit fraction + mean cached_tokens. Doubles as a quick
preservation check after a smoke run.

## What it reports

For each level present in the telemetry file:

- `n` — number of calls observed at that level
- `n_hits` — calls with cached_tokens > 0
- `hit_fraction` — n_hits / n
- `cached_tokens_mean` — mean across all calls (zeros included)
- `cached_tokens_p50` / `p95` — distribution sketch
- `prompt_tokens_mean` — for sanity (and to compute the realised
  per-call billed-input baseline)

The numbers at L4 are the load-bearing ones for E2-005 — they
empirically confirm whether the cache-friendly placement is working.

## Expected shape (after the smoke run)

A 3-record stub smoke produces 15 rows (3 × 5) but ALL with
`cached_tokens=None` (stub mode). The script reports
`n_hits=0, hit_fraction=0.0, observed=False`.

A 3-record LIVE smoke at L4 produces 3 rows; we expect rows 2 and 3
to carry `cached_tokens > 0` (the second and third L4 calls should
hit the cache on the policy + L1 + L2 prefix). The script then
reports `hit_fraction >= 2/3 = 0.667` at L4.

## Usage

    python -m scripts.cache_summary <path-to-run-dir>
    # OR
    python procurement-context-gradient/runner/scripts/cache_summary.py <run_dir>

The script exits 0 even when no hits are observed — the writeup
needs the numbers either way. CI failure on hit_fraction == 0 is a
job for the live smoke test, not this script.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


CACHE_TELEMETRY_FILENAME = "cache_telemetry.jsonl"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    """Read the JSONL file. Skips blank lines and malformed lines
    (with a warning to stderr) so a torn write doesn't crash the
    summary."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fp:
        for lineno, raw in enumerate(fp, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as err:
                print(
                    f"warn: {path}:{lineno} skipped — malformed JSON: {err}",
                    file=sys.stderr,
                )
    return rows


def _percentile(values: list[int], pct: float) -> float | None:
    """Lightweight percentile (no numpy dependency). pct in [0, 100]."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return s[f] + (s[c] - s[f]) * (k - f)


def summarise_by_level(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate cache telemetry by level. Rows with cached_tokens=None
    are counted as observed=False (model didn't return usage info);
    they are excluded from hit_fraction's denominator. Rows with
    cached_tokens=0 ARE counted (cache miss observed)."""
    by_level: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        level = str(row.get("level") or "UNKNOWN")
        by_level.setdefault(level, []).append(row)

    summary: dict[str, dict[str, Any]] = {}
    for level, level_rows in sorted(by_level.items()):
        observed = [r for r in level_rows if r.get("cached_tokens") is not None]
        cached = [int(r["cached_tokens"]) for r in observed]
        prompts = [
            int(r["prompt_tokens"])
            for r in level_rows
            if r.get("prompt_tokens") is not None
        ]
        hits = [c for c in cached if c > 0]
        summary[level] = {
            "n_total": len(level_rows),
            "n_observed": len(observed),
            "n_hits": len(hits),
            "hit_fraction": (len(hits) / len(observed)) if observed else None,
            "cached_tokens_mean": (statistics.mean(cached) if cached else None),
            "cached_tokens_p50": _percentile(cached, 50) if cached else None,
            "cached_tokens_p95": _percentile(cached, 95) if cached else None,
            "prompt_tokens_mean": statistics.mean(prompts) if prompts else None,
        }
    return summary


def render_summary(summary: dict[str, dict[str, Any]]) -> str:
    """Render the summary as a small fixed-width text table."""
    if not summary:
        return "(no cache telemetry rows found)"

    header = (
        f"{'level':<8} {'n':>5} {'n_obs':>6} {'n_hits':>7} "
        f"{'hit_frac':>9} {'cached_mean':>12} {'cached_p50':>11} "
        f"{'cached_p95':>11} {'prompt_mean':>12}"
    )
    lines = [header, "-" * len(header)]
    for level in sorted(summary):
        s = summary[level]

        def _fmt(value: Any, spec: str) -> str:
            if value is None:
                return "—"
            try:
                return format(value, spec)
            except (TypeError, ValueError):
                return str(value)

        lines.append(
            f"{level:<8} {s['n_total']:>5} {s['n_observed']:>6} "
            f"{s['n_hits']:>7} {_fmt(s['hit_fraction'], '.3f'):>9} "
            f"{_fmt(s['cached_tokens_mean'], '.1f'):>12} "
            f"{_fmt(s['cached_tokens_p50'], '.1f'):>11} "
            f"{_fmt(s['cached_tokens_p95'], '.1f'):>11} "
            f"{_fmt(s['prompt_tokens_mean'], '.1f'):>12}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to a run directory containing cache_telemetry.jsonl",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the per-level summary as JSON (for downstream parsing)",
    )
    args = parser.parse_args(argv)

    telemetry_path = args.run_dir / CACHE_TELEMETRY_FILENAME
    rows = _load_rows(telemetry_path)
    summary = summarise_by_level(rows)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"# cache telemetry summary — {telemetry_path}")
        print(f"# rows loaded: {len(rows)}")
        print()
        print(render_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
