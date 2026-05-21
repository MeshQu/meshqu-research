"""
Receipt-orphan recovery script.

An orphaned receipt is a MeshQu /v1/decisions/record call that succeeded
remotely but whose local post-receipt write failed (sidecar / manifest
patch / decision_traces row). The eval loop catches these and emits a
`receipt_orphaned` anomaly carrying enough metadata for this script to
reconcile: decision_id, policy_snapshot_id, integrity_hash, and — most
importantly — idempotency_key.

Recovery strategy:

  1. Walk `anomalies.jsonl` for the run; collect every
     `category=receipt_orphaned` entry.
  2. For each orphan, re-POST /v1/decisions/record with the same
     idempotency_key. MeshQu's idempotency cache returns the original
     receipt without re-evaluating policies — no double-charge, no
     duplicate row.
  3. Read the agent-output sidecar at
     `run_dir/agent_outputs/<decision_id>.json` if it exists (sidecar
     write may have been the very thing that failed; tolerate missing).
  4. Build a decision_traces row from the fetched receipt + the sidecar.
     Fields the sidecar doesn't cover (agent_retry_count etc. when the
     sidecar itself was the write that failed) are recorded as null,
     and an `is_recovered: true` marker is added so post-run analysis
     can exclude or flag them.
  5. Append to `recovered_traces.jsonl` (a SEPARATE file — the original
     `decision_traces.jsonl` stays as-written so the audit trail of
     "what actually happened during the live run" remains pure).
  6. Write `recovery_summary.json` capturing per-orphan outcome.

Idempotent: re-running this script on a run-dir is safe. The recovered
trace file is rewritten from scratch each run; the summary captures the
latest pass.

CLI:

    python -m meshqu_runner.recover_orphans <run_dir>
        [--base-url URL] [--api-key KEY] [--dry-run]

Env fallback for credentials:
    MESHQU_API_URL
    MESHQU_EXPERIMENT_PROCUREMENT_API_KEY
    MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID  (tenant UUID)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .meshqu_client import MeshQuClient, MeshQuClientError, ReceiptSummary


# ---------------------------------------------------------------------------
# Outcome types
# ---------------------------------------------------------------------------


@dataclass
class OrphanRecord:
    """An orphan as extracted from anomalies.jsonl. Mirrors the
    `context` dict the eval loop attaches."""

    anomaly_id: str
    ts: str
    record_index: int | None
    ocid: str | None
    decision_id: str
    policy_snapshot_id: str | None
    integrity_hash: str | None
    idempotency_key: str
    summary: str
    detail: str
    raw: dict[str, Any]  # full anomaly row, for the summary


@dataclass
class RecoveryOutcome:
    """Per-orphan outcome from a single recovery pass."""

    anomaly_id: str
    decision_id: str
    record_index: int | None
    status: str  # "recovered" | "refetch_failed" | "dry_run"
    detail: str = ""
    fetched_meshqu_verdict: str | None = None
    sidecar_found: bool = False


@dataclass
class RecoverySummary:
    """Persisted to recovery_summary.json."""

    run_dir: str
    started_at: str
    finished_at: str
    orphans_total: int
    recovered: int
    refetch_failed: int
    dry_run: bool
    outcomes: list[RecoveryOutcome] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Anomaly parsing
# ---------------------------------------------------------------------------


def parse_orphans(anomalies_path: Path) -> list[OrphanRecord]:
    """Scan anomalies.jsonl and return every receipt_orphaned entry.

    Tolerates missing file (returns []) — a run with zero orphans never
    creates anomalies.jsonl. Skips malformed lines with a warning to
    stderr rather than aborting the whole recovery pass."""

    if not anomalies_path.exists():
        return []

    orphans: list[OrphanRecord] = []
    for line_no, line in enumerate(anomalies_path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            print(
                f"warning: skipping malformed anomalies.jsonl line {line_no}: {err}",
                file=sys.stderr,
            )
            continue
        if row.get("category") != "receipt_orphaned":
            continue

        ctx = row.get("context") or {}
        decision_id = ctx.get("decision_id")
        idempotency_key = ctx.get("idempotency_key")
        if not decision_id or not idempotency_key:
            # An orphan anomaly without these two fields can't be
            # reconciled — log + skip rather than crash.
            print(
                f"warning: orphan anomaly missing decision_id/idempotency_key "
                f"(anomaly_id={row.get('anomaly_id')}); skipping",
                file=sys.stderr,
            )
            continue

        orphans.append(
            OrphanRecord(
                anomaly_id=row.get("anomaly_id", ""),
                ts=row.get("ts", ""),
                record_index=ctx.get("record_index"),
                ocid=ctx.get("ocid"),
                decision_id=decision_id,
                policy_snapshot_id=ctx.get("policy_snapshot_id"),
                integrity_hash=ctx.get("integrity_hash"),
                idempotency_key=idempotency_key,
                summary=row.get("summary", ""),
                detail=row.get("detail", ""),
                raw=row,
            )
        )
    return orphans


# ---------------------------------------------------------------------------
# Sidecar tolerance — agent fields are best-effort
# ---------------------------------------------------------------------------


def load_agent_sidecar(run_dir: Path, decision_id: str) -> dict[str, Any] | None:
    """Read `run_dir/agent_outputs/<decision_id>.json` if it exists.

    Returns the inner `agent` dict (matches the AgentResponse fields).
    Returns None when missing — the orphan may have happened DURING
    sidecar write, in which case the file is absent or partial.

    A partial-write that produced invalid JSON is treated as missing
    (warn to stderr); the recovery row gets null agent fields."""

    path = run_dir / "agent_outputs" / f"{decision_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        print(
            f"warning: agent sidecar for {decision_id} is unreadable ({err}); "
            "treating as missing",
            file=sys.stderr,
        )
        return None
    agent = payload.get("agent")
    return agent if isinstance(agent, dict) else None


# ---------------------------------------------------------------------------
# Trace row construction
# ---------------------------------------------------------------------------


def build_recovered_trace(
    *,
    orphan: OrphanRecord,
    receipt: ReceiptSummary,
    agent_sidecar: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compose a decision_traces row from the fetched receipt + the
    (possibly absent) agent sidecar.

    Marked with `is_recovered: true` and `recovery_anomaly_id` so the
    writeup can statistically isolate recovered records from live ones
    (e.g. retry-count distributions exclude recovered rows where the
    sidecar was unavailable)."""

    def maybe(field_name: str) -> Any:
        return (agent_sidecar or {}).get(field_name)

    agent_verdict = maybe("verdict")
    meshqu_verdict = receipt.decision
    agreement: bool | None
    if agent_verdict in {"ALLOW", "DENY", "REVIEW"} and meshqu_verdict in {"ALLOW", "DENY", "REVIEW"}:
        agreement = agent_verdict == meshqu_verdict
    else:
        agreement = None

    return {
        "is_recovered": True,
        "recovery_anomaly_id": orphan.anomaly_id,
        "record_index": orphan.record_index,
        "ocid": orphan.ocid,
        "decision_id": receipt.decision_id,
        "policy_snapshot_id": receipt.policy_snapshot_id,
        "meshqu_verdict": meshqu_verdict,
        "agent_verdict": agent_verdict,
        "agreement": agreement,
        "reasoning_sha256": maybe("reasoning_sha256"),
        "agent_recommended_action": maybe("recommended_action"),
        "integrity_hash": receipt.integrity_hash,
        "evaluated_rules_hash": receipt.evaluated_rules_hash,
        "policy_snapshot_digest": receipt.policy_snapshot_digest,
        "signature_kid": receipt.signature_kid,
        "receipt_timestamp": receipt.timestamp,
        "violations": [v.get("rule_code") for v in (receipt.violations or [])],
        "agent_output_mode": maybe("output_mode"),
        "agent_parse_status": maybe("parse_status"),
        "agent_latency_ms": maybe("latency_ms"),
        "agent_retry_count": maybe("retry_count"),
        "substrate_summary": None,  # not in anomaly; live row only
    }


# ---------------------------------------------------------------------------
# Main recovery pass
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def recover_orphans(
    *,
    run_dir: Path,
    client: MeshQuClient | None = None,
    dry_run: bool = False,
) -> RecoverySummary:
    """Run a recovery pass on `run_dir`. Returns RecoverySummary; also
    writes `recovered_traces.jsonl` + `recovery_summary.json` as side
    effects (unless dry_run, in which case nothing is written).

    `client` is required unless dry_run=True."""

    if not dry_run and client is None:
        raise ValueError("client is required unless dry_run=True")

    started_at = _utc_now_iso()
    anomalies_path = run_dir / "anomalies.jsonl"
    orphans = parse_orphans(anomalies_path)
    outcomes: list[RecoveryOutcome] = []

    # Rewrite recovered_traces.jsonl from scratch each pass — the script
    # is idempotent. Live decision_traces.jsonl is never touched.
    recovered_path = run_dir / "recovered_traces.jsonl"
    rows_to_write: list[dict[str, Any]] = []

    for orphan in orphans:
        if dry_run:
            outcomes.append(
                RecoveryOutcome(
                    anomaly_id=orphan.anomaly_id,
                    decision_id=orphan.decision_id,
                    record_index=orphan.record_index,
                    status="dry_run",
                    detail="would re-POST with captured idempotency_key",
                    sidecar_found=(run_dir / "agent_outputs" / f"{orphan.decision_id}.json").exists(),
                )
            )
            continue

        assert client is not None  # narrowed by dry_run branch above
        try:
            # Re-POST is intentionally minimal — MeshQu's idempotency
            # cache keys on `idempotency_key` alone, so an empty context
            # is fine. The cached receipt is returned verbatim.
            receipt = client.record_decision(
                context={"decision_type": "procurement_decision", "fields": {}},
                idempotency_key=orphan.idempotency_key,
            )
        except MeshQuClientError as err:
            outcomes.append(
                RecoveryOutcome(
                    anomaly_id=orphan.anomaly_id,
                    decision_id=orphan.decision_id,
                    record_index=orphan.record_index,
                    status="refetch_failed",
                    detail=str(err),
                )
            )
            continue

        sidecar = load_agent_sidecar(run_dir, receipt.decision_id)
        trace = build_recovered_trace(
            orphan=orphan, receipt=receipt, agent_sidecar=sidecar
        )
        rows_to_write.append(trace)

        outcomes.append(
            RecoveryOutcome(
                anomaly_id=orphan.anomaly_id,
                decision_id=receipt.decision_id,
                record_index=orphan.record_index,
                status="recovered",
                fetched_meshqu_verdict=receipt.decision,
                sidecar_found=sidecar is not None,
            )
        )

    if not dry_run:
        _write_recovered_traces(recovered_path, rows_to_write)

    summary = RecoverySummary(
        run_dir=str(run_dir),
        started_at=started_at,
        finished_at=_utc_now_iso(),
        orphans_total=len(orphans),
        recovered=sum(1 for o in outcomes if o.status == "recovered"),
        refetch_failed=sum(1 for o in outcomes if o.status == "refetch_failed"),
        dry_run=dry_run,
        outcomes=outcomes,
    )

    if not dry_run:
        _write_recovery_summary(run_dir / "recovery_summary.json", summary)

    return summary


def _write_recovered_traces(path: Path, rows: list[dict[str, Any]]) -> None:
    """Rewrite recovered_traces.jsonl from scratch (idempotent recovery).
    Empty list → empty file. Atomic via tmp + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False))
            fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)


def _write_recovery_summary(path: Path, summary: RecoverySummary) -> None:
    """Atomic write of the recovery summary."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        json.dump(asdict(summary), fp, indent=2, sort_keys=True)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m meshqu_runner.recover_orphans",
        description="Reconcile orphaned MeshQu receipts after a partial-write failure.",
    )
    parser.add_argument("run_dir", type=Path, help="results/runs/<run_id>/ directory")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MESHQU_API_URL"),
        help="MeshQu API base URL (default: env MESHQU_API_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("MESHQU_EXPERIMENT_PROCUREMENT_API_KEY"),
        help="API key (default: env MESHQU_EXPERIMENT_PROCUREMENT_API_KEY)",
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID"),
        help="Tenant UUID — sent as x-meshqu-tenant-id (default: env "
        "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan + report orphans without re-POSTing or writing files",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.run_dir.is_dir():
        print(f"error: {args.run_dir} is not a directory", file=sys.stderr)
        return 2

    client: MeshQuClient | None = None
    if not args.dry_run:
        if not args.base_url or not args.api_key or not args.tenant_id:
            print(
                "error: --base-url, --api-key, --tenant-id required (or set "
                "MESHQU_API_URL, MESHQU_EXPERIMENT_PROCUREMENT_API_KEY, and "
                "MESHQU_EXPERIMENT_PROCUREMENT_TENANT_ID)",
                file=sys.stderr,
            )
            return 2
        client = MeshQuClient(
            base_url=args.base_url, api_key=args.api_key, tenant_id=args.tenant_id
        )

    summary = recover_orphans(run_dir=args.run_dir, client=client, dry_run=args.dry_run)

    print(
        f"orphans: {summary.orphans_total} "
        f"recovered: {summary.recovered} "
        f"failed: {summary.refetch_failed} "
        f"{'(dry-run)' if summary.dry_run else ''}".strip()
    )
    # Exit non-zero if any refetch failed so wrapper scripts notice.
    return 1 if summary.refetch_failed > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
