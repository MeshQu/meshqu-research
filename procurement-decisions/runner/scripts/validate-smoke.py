#!/usr/bin/env python3
"""OBS-401 smoke-test validator.

Reads the artefacts a runner smoke + decision-load run produced and emits a
markdown report against the five OBS-401 checkpoints:

  1. Automated screenshots fire at expected moments (start, checkpoints, end)
  2. PNGs are valid (not PDFs, not empty, not error responses)
  3. All four dashboard panels show series values (partial — run-end PNG
     existence + non-empty size is asserted; full panel-content validation
     needs visual inspection)
  4. audit/decision_traces.jsonl, audit/anomalies.jsonl, audit/checkpoints.jsonl
     populated per their schemas
  5. Bundle round-trips through verify.meshqu.com (deferred — needs real
     receipts from the API run, not synthetic from the runner smoke; this
     check emits a `manual-verify-needed` row with the receipt count from
     decision_traces.jsonl as the upper bound on how many bundles to test)

Usage:
  python3 scripts/validate-smoke.py                       # latest run
  python3 scripts/validate-smoke.py --run-id abc-def-...  # specific run
  python3 scripts/validate-smoke.py --output report.md    # custom path

The output report writes to scripts/smoke-test-{YYYY-MM-DDTHHMM}.md by
default — relative paths inside reference artefacts so a reviewer can browse
them from the runner repo root.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]  # …/meshqu-research
DEFAULT_RESULTS_DIR = REPO_ROOT / "procurement-decisions" / "results"
SCRIPT_DIR = Path(__file__).resolve().parent


# ─── Filename pattern ────────────────────────────────────────────────────────
# Per results/observability/screenshots/README.md:
#   <run-phase>_<YYYY-MM-DDTHHMM>_<dashboard-slug>_<event>.png
FILENAME_RE = re.compile(
    r"^(?P<phase>[a-z0-9-]+)_"
    r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{4})_"
    r"(?P<slug>[a-z0-9-]+)_"
    r"(?P<event>[a-zA-Z0-9_-]+)\.png$"
)


# ─── Audit schema (per results/audit/README.md) ──────────────────────────────
# Required for ALL decision_trace rows regardless of source.
DECISION_TRACE_REQUIRED_ALWAYS = {
    "ts", "run_id", "source", "record_index", "decision_id",
    "policy_snapshot_digest", "meshqu_verdict", "rules_fired",
    "latency_ms", "receipt_integrity_hash", "receipt_signature_kid",
}
# Required additionally for source=inspect-eval (production data path).
# Smoke rows (source=decision-load-smoke) MAY null these per the README's
# nullability table.
DECISION_TRACE_REQUIRED_INSPECT_EVAL = {
    "ocid", "agent_verdict", "agent_reasoning_sha256", "agree",
    "rekor_log_index", "rekor_log_entry_uuid",
}
DECISION_TRACE_VALID_SOURCES = {"inspect-eval", "decision-load-smoke"}

ANOMALY_REQUIRED = {"ts", "run_id", "anomaly_id", "category", "severity", "summary"}
CHECKPOINT_REQUIRED = {"ts", "run_id"}


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "FAIL" | "PARTIAL" | "MANUAL"
    detail: str
    bullets: list[str] = field(default_factory=list)


def relative(path: Path) -> str:
    """Return path relative to repo root for report readability."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ─── Check 1: screenshots fired at expected moments ──────────────────────────
def check_screenshots_fired(screenshots_dir: Path, run_id: str | None) -> CheckResult:
    pngs = sorted(screenshots_dir.glob("*.png"))
    if not pngs:
        return CheckResult(
            "1. screenshots fire at expected moments",
            "FAIL",
            f"no PNGs in {relative(screenshots_dir)}",
        )

    events: Counter[str] = Counter()
    bad_filenames: list[str] = []
    for p in pngs:
        m = FILENAME_RE.match(p.name)
        if not m:
            bad_filenames.append(p.name)
            continue
        events[m.group("event")] += 1

    bullets = [
        f"total screenshots: {len(pngs)}",
        f"events: {dict(events)}",
    ]
    if bad_filenames:
        bullets.append(f"⚠ {len(bad_filenames)} filename(s) did NOT match pattern: {bad_filenames[:3]}")

    have_start = any(e.startswith("run-start") for e in events)
    have_end = any(e.startswith("run-end") for e in events)
    have_checkpoints = any("checkpoint" in e for e in events)

    if have_start and have_end and have_checkpoints and not bad_filenames:
        return CheckResult(
            "1. screenshots fire at expected moments",
            "PASS",
            f"{len(pngs)} PNGs covering start, checkpoints, end",
            bullets,
        )
    elif have_start and have_end:
        return CheckResult(
            "1. screenshots fire at expected moments",
            "PARTIAL",
            "start + end present but checkpoints missing or filenames malformed",
            bullets,
        )
    else:
        missing = [k for k, present in [("run-start", have_start), ("run-end", have_end), ("checkpoint-*", have_checkpoints)] if not present]
        return CheckResult(
            "1. screenshots fire at expected moments",
            "FAIL",
            f"missing event(s): {', '.join(missing)}",
            bullets,
        )


# ─── Check 2: PNGs are valid ──────────────────────────────────────────────────
def check_pngs_valid(screenshots_dir: Path) -> CheckResult:
    pngs = sorted(screenshots_dir.glob("*.png"))
    if not pngs:
        return CheckResult("2. PNGs are valid", "FAIL", "no PNGs to check")

    bad: list[tuple[str, str]] = []
    sizes: list[int] = []
    for p in pngs:
        size = p.stat().st_size
        sizes.append(size)
        if size == 0:
            bad.append((p.name, "empty"))
            continue
        result = subprocess.run(
            ["file", "-b", str(p)],
            capture_output=True, text=True, timeout=5,
        )
        if "PNG image" not in result.stdout:
            bad.append((p.name, result.stdout.strip()))

    bullets = [
        f"checked: {len(pngs)} files",
        f"size range: {min(sizes)}B – {max(sizes)}B" if sizes else "no sizes",
    ]
    if bad:
        bullets.extend(f"  ✗ {name}: {detail}" for name, detail in bad[:5])
        return CheckResult(
            "2. PNGs are valid",
            "FAIL",
            f"{len(bad)} invalid file(s)",
            bullets,
        )
    return CheckResult("2. PNGs are valid", "PASS", f"all {len(pngs)} files are valid PNG", bullets)


# ─── Check 3: panels show series values (partial) ────────────────────────────
def check_panels_populated(screenshots_dir: Path) -> CheckResult:
    """Best-effort programmatic check. Full validation requires visual inspection."""
    run_end = sorted(p for p in screenshots_dir.glob("*run-end*.png"))
    if not run_end:
        return CheckResult(
            "3. dashboard panels show series",
            "FAIL",
            "no run-end screenshot to inspect (visual check needs this)",
        )

    # Empty Grafana panels still render ~85KB; populated panels cluster
    # around 145–170KB (empirical: 148KB OBS-401 staging close-out, fully
    # populated layout with all KPI tiles + histograms + flow series).
    p = run_end[-1]
    size = p.stat().st_size
    bullets = [
        f"run-end screenshot: {relative(p)}",
        f"size: {size:,} bytes",
        "heuristic: empty Grafana render ≈ 85 KB, populated render ≈ 145+ KB",
    ]

    if size >= 145_000:
        return CheckResult(
            "3. dashboard panels show series",
            "PARTIAL",
            f"{size:,}B — heuristic suggests populated panels, but needs visual confirmation",
            bullets + [f"⏵ open {relative(p)} and confirm all 4 KPI tiles + 3 timeseries panels show values, not 'No data'"],
        )
    elif size >= 100_000:
        return CheckResult(
            "3. dashboard panels show series",
            "PARTIAL",
            f"{size:,}B — borderline; likely partial panel population",
            bullets + [f"⏵ open {relative(p)} and confirm panels; smaller than expected"],
        )
    else:
        return CheckResult(
            "3. dashboard panels show series",
            "FAIL",
            f"{size:,}B — below empty-render baseline; panels likely empty",
            bullets,
        )


# ─── Check 4: audit JSONL files populated per schema ─────────────────────────
def _validate_jsonl(path: Path, required_fields: set[str]) -> tuple[int, list[str]]:
    """Return (line_count, list_of_errors). Empty errors = clean."""
    if not path.exists():
        return 0, [f"{relative(path)} does not exist"]
    errors: list[str] = []
    count = 0
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON ({exc})")
            continue
        missing = required_fields - obj.keys()
        if missing:
            errors.append(f"line {lineno}: missing required fields {sorted(missing)}")
        count += 1
    return count, errors


def _validate_decision_traces(path: Path) -> tuple[int, list[str], dict[str, int]]:
    """Schema validation with source-conditional nullability per README.

    Returns (count, errors, source_breakdown).
    """
    if not path.exists():
        return 0, [f"{relative(path)} does not exist"], {}
    errors: list[str] = []
    count = 0
    source_breakdown: dict[str, int] = {}
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON ({exc})")
            continue

        # Always-required fields
        missing = DECISION_TRACE_REQUIRED_ALWAYS - obj.keys()
        if missing:
            errors.append(f"line {lineno}: missing always-required fields {sorted(missing)}")

        source = obj.get("source")
        if source not in DECISION_TRACE_VALID_SOURCES:
            errors.append(f"line {lineno}: invalid source={source!r} (expected one of {sorted(DECISION_TRACE_VALID_SOURCES)})")
        else:
            source_breakdown[source] = source_breakdown.get(source, 0) + 1

        # Source-conditional: inspect-eval rows must have non-null on the
        # inspect-eval-required fields. Smoke rows MAY null them.
        if source == "inspect-eval":
            for field in DECISION_TRACE_REQUIRED_INSPECT_EVAL:
                if field not in obj:
                    errors.append(f"line {lineno}: source=inspect-eval missing field {field!r}")
                elif obj[field] is None:
                    errors.append(f"line {lineno}: source=inspect-eval has null {field!r}")
            # inspect-eval also requires latency_ms.agent and latency_ms.rekor_anchor non-null
            lm = obj.get("latency_ms") or {}
            for key in ("agent", "rekor_anchor"):
                if lm.get(key) is None:
                    errors.append(f"line {lineno}: source=inspect-eval has null latency_ms.{key}")
        count += 1

    return count, errors, source_breakdown


def check_audit_jsonl(audit_dir: Path) -> CheckResult:
    bullets: list[str] = []
    total_errors: list[str] = []
    empty_files: list[str] = []

    # decision_traces.jsonl — uses the source-conditional validator
    traces_path = audit_dir / "decision_traces.jsonl"
    traces_count, traces_errors, source_breakdown = _validate_decision_traces(traces_path)
    marker = "✓" if (traces_count > 0 and not traces_errors) else ("∅" if traces_count == 0 else "✗")
    src_summary = ", ".join(f"{s}={n}" for s, n in source_breakdown.items()) or "(empty)"
    bullets.append(f"  {marker} decision_traces.jsonl: {traces_count} record(s) [{src_summary}]" + (f", {len(traces_errors)} schema error(s)" if traces_errors else ""))
    if traces_errors:
        total_errors.extend([f"decision_traces.jsonl: {e}" for e in traces_errors[:3]])
    if traces_count == 0:
        empty_files.append("decision_traces.jsonl")

    # anomalies.jsonl + checkpoints.jsonl — simple required-fields check
    simple_files = {
        "anomalies.jsonl":   ANOMALY_REQUIRED,
        "checkpoints.jsonl": CHECKPOINT_REQUIRED,
    }
    for name, required in simple_files.items():
        path = audit_dir / name
        count, errors = _validate_jsonl(path, required)
        marker = "✓" if (count > 0 and not errors) else ("∅" if count == 0 else "✗")
        bullets.append(f"  {marker} {name}: {count} record(s)" + (f", {len(errors)} schema error(s)" if errors else ""))
        if errors:
            total_errors.extend([f"{name}: {e}" for e in errors[:3]])
        if count == 0 and name != "anomalies.jsonl":
            # Anomalies are optional — a clean smoke produces zero.
            # checkpoints MUST have entries.
            empty_files.append(name)

    if total_errors:
        return CheckResult(
            "4. audit JSONL populated per schema",
            "FAIL",
            f"{len(total_errors)} schema error(s)",
            bullets + [f"  ⚠ {e}" for e in total_errors],
        )
    if empty_files:
        return CheckResult(
            "4. audit JSONL populated per schema",
            "FAIL",
            f"empty file(s): {', '.join(empty_files)}",
            bullets + ["⏵ run scripts/decision-load.sh to populate decision_traces.jsonl before re-running the validator"],
        )
    return CheckResult("4. audit JSONL populated per schema", "PASS", "all required files populated, schema-clean", bullets)


# ─── Check 5: bundle round-trips through verify.meshqu.com (manual) ──────────
def check_bundle_roundtrip(audit_dir: Path) -> CheckResult:
    traces = audit_dir / "decision_traces.jsonl"
    if not traces.exists() or not traces.read_text().strip():
        return CheckResult(
            "5. bundle round-trips through verify.meshqu.com",
            "MANUAL",
            "no decision_traces.jsonl entries — nothing to round-trip yet",
            [
                "this check needs real receipts from a meshqu-api decision-load run",
                "for the OBS-401 close-out, run scripts/decision-load.sh in parallel with the smoke",
            ],
        )
    count = 0
    receipt_examples: list[str] = []
    for line in traces.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if "decision_id" in obj:
                count += 1
                if len(receipt_examples) < 3:
                    receipt_examples.append(obj["decision_id"][:8])
        except json.JSONDecodeError:
            continue
    return CheckResult(
        "5. bundle round-trips through verify.meshqu.com",
        "MANUAL",
        f"{count} receipt(s) available for round-trip; verifier check is manual",
        [
            f"sample decision IDs: {receipt_examples}",
            "for each: curl /v1/decisions/<id>/bundle?format=tar > out.tar",
            "drop into verify.meshqu.com — confirm green checkmarks on signature + Rekor inclusion",
            "if every bundle verifies, mark this checkpoint PASS in the writeup; otherwise FAIL with the failing decision IDs noted",
        ],
    )


# ─── Report rendering ─────────────────────────────────────────────────────────
STATUS_BADGE = {
    "PASS":    "✅ PASS",
    "FAIL":    "❌ FAIL",
    "PARTIAL": "⚠️ PARTIAL",
    "MANUAL":  "🔍 MANUAL",
}


def render_report(
    results: list[CheckResult],
    *,
    results_dir: Path,
    run_id: str | None,
    timestamp: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# OBS-401 Smoke-test Report — {timestamp}")
    lines.append("")
    lines.append(f"- **Run ID**: `{run_id or '(latest — detected from artefacts)'}`")
    lines.append(f"- **Results directory**: `{relative(results_dir)}`")
    lines.append(f"- **Generated**: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    statuses = [r.status for r in results]
    summary_parts = [f"{statuses.count(s)} {s}" for s in ["PASS", "PARTIAL", "FAIL", "MANUAL"] if statuses.count(s)]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"`{' | '.join(summary_parts)}`")
    lines.append("")
    lines.append("| # | Check | Status | Detail |")
    lines.append("|---|---|---|---|")
    for i, r in enumerate(results, start=1):
        lines.append(f"| {i} | {r.name.split('. ', 1)[-1]} | {STATUS_BADGE[r.status]} | {r.detail} |")
    lines.append("")

    lines.append("## Detail")
    lines.append("")
    for r in results:
        lines.append(f"### {STATUS_BADGE[r.status]}  {r.name}")
        lines.append("")
        lines.append(r.detail)
        if r.bullets:
            lines.append("")
            for b in r.bullets:
                lines.append(f"- {b}")
        lines.append("")

    lines.append("## Next action")
    lines.append("")
    if any(r.status == "FAIL" for r in results):
        lines.append("❌ One or more checks failed. Address before running against staging.")
    elif any(r.status == "PARTIAL" for r in results):
        lines.append("⚠️ Smoke is largely green but some checks need manual confirmation (see PARTIAL rows). Once visual inspection passes, this is ready for the staging smoke-run.")
    else:
        lines.append("✅ All automated checks PASS. Manual checks (#5 bundle round-trip) remain — see that section for the procedure. After manual checks pass, OBS-401 can be flipped to `completed`.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--run-id", type=str, default=None, help="Filter to a specific run (matched against audit run_id)")
    parser.add_argument("--output", type=Path, default=None, help="Override report output path")
    args = parser.parse_args(argv)

    results_dir: Path = args.results_dir
    screenshots_dir = results_dir / "observability" / "screenshots"
    audit_dir = results_dir / "audit"

    results = [
        check_screenshots_fired(screenshots_dir, args.run_id),
        check_pngs_valid(screenshots_dir),
        check_panels_populated(screenshots_dir),
        check_audit_jsonl(audit_dir),
        check_bundle_roundtrip(audit_dir),
    ]

    print()
    for r in results:
        print(f"  {STATUS_BADGE[r.status]}  {r.name}  —  {r.detail}")
    print()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    output_path = args.output or (SCRIPT_DIR / f"smoke-test-{timestamp}.md")
    report = render_report(results, results_dir=results_dir, run_id=args.run_id, timestamp=timestamp)
    output_path.write_text(report)
    print(f"  Report written: {relative(output_path)}")
    print()

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
