"""
Deterministic run-manifest writer.

The manifest is the first artefact a run produces and the LAST line of
the experiment's reproducibility chain. It captures every input that
could produce a different output, hashed where appropriate, so a
reproducibility-rerun can prove byte-identical inputs.

Captured per Brief #2's discipline:

- `runner_git_commit`     — sha of meshqu-research at run start
- `meshqu_api_url`        — endpoint hit
- `meshqu_tenant_label`   — human label (e.g. "experiment-procurement")
- `policy_snapshot_id`    — uuid (resolved from the policy code via the
                            API after the first record; runs that fail
                            before a single receipt lands record
                            `policy_snapshot_id` as None)
- `agent_model_id`        — locked OpenAI model id
- `agent_temperature`     — locked temperature (0.0)
- `agent_prompt_sha256`   — hash of the system prompt
- `substrate_adapter_version` — substrate.py ADAPTER_VERSION
- `substrate_source`      — feed URL + slice parameters
- `run_phase`             — dry-run / full-run / reproducibility-rerun
- `record_target_count`   — N records the run intends to evaluate
- `run_id`                — uuid for this run
- `started_at`            — ISO-8601 UTC

After the run completes (or aborts), the same module is used to write
a closing JSON line capturing run_end status + counts.

File layout:
    results/runs/<run_id>/manifest.json          (run start, one object)
    results/runs/<run_id>/run_end.json           (run end, one object)
    results/runs/<run_id>/decision_traces.jsonl  (one row per record)
    results/runs/<run_id>/agent_outputs/<dec>.json (raw agent text)

Writes are atomic (write to temp, then rename) so a crash mid-write
never produces a half-written manifest a reproducibility-rerun could
misinterpret.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


RunPhase = Literal["dry-run", "full-run", "reproducibility-rerun"]


# ---------------------------------------------------------------------------
# Manifest dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunManifest:
    """Open-of-run manifest. All fields known at run start go here."""

    run_id: str
    run_phase: RunPhase
    started_at: str  # ISO-8601 UTC, with timezone suffix
    runner_git_commit: str
    runner_git_dirty: bool  # True if working tree had uncommitted changes
    meshqu_api_url: str
    meshqu_tenant_label: str
    agent_model_id: str
    agent_temperature: float
    agent_max_completion_tokens: int
    agent_prompt_sha256: str
    substrate_adapter_version: str
    substrate_source: dict[str, Any]
    record_target_count: int
    # Resolved after the first successful receipt; None at run-start.
    policy_snapshot_id: str | None = None
    # Optional: pin the policy code if known up-front (it usually is).
    policy_code: str | None = None
    # Optional structured tags for the writeup to filter on.
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunEnd:
    """Close-of-run summary. Written when the eval loop completes —
    success OR controlled abort. A crash that bypasses this writer
    means the run is unfinished; the absence of `run_end.json` is the
    signal."""

    run_id: str
    ended_at: str
    status: Literal["completed", "aborted_by_anomaly", "aborted_by_signal", "aborted_by_error"]
    records_attempted: int
    records_with_receipt: int
    records_with_agent_parse_failure: int
    records_with_meshqu_error: int
    # Resolved at first successful receipt; persisted here for convenience
    # so post-run scripts don't need to open the manifest separately.
    policy_snapshot_id: str | None = None
    abort_reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """UTC timestamp in ISO-8601 with explicit timezone suffix. The runner
    is timezone-agnostic by policy — every timestamp is UTC, full stop."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_git_commit(repo_dir: Path) -> tuple[str, bool]:
    """Returns (sha, dirty). `sha` is the full HEAD sha; `dirty` is True
    if `git status --porcelain` returns anything.

    Failures (no git, not a repo) return ("unknown", False) — the writer
    persists `unknown` so the run can still proceed. The writeup will
    flag any manifest with `runner_git_commit == 'unknown'` as
    non-reproducible."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ("unknown", False)

    try:
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        dirty = bool(porcelain.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        dirty = False

    return (sha, dirty)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to `path` atomically: write to `path.tmp`, fsync, rename.
    The rename is atomic on POSIX. A crash mid-write leaves either the
    pre-existing file or the new file — never a torn write.

    Indent=2 + sort_keys=True so manifest diffs across runs are
    line-oriented and reviewer-friendly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True, default=_json_default)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)


def _json_default(value: Any) -> Any:
    """Last-ditch encoder for values json.dumps can't handle natively.
    We don't expect to hit this in practice — the manifest dataclass
    fields are all JSON-native — but the fallback prevents a crash if
    a caller threads through something odd in `notes`."""
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Public writers — used by the eval loop
# ---------------------------------------------------------------------------


def manifest_path(run_dir: Path) -> Path:
    """Where the manifest lives for a given run directory."""
    return run_dir / "manifest.json"


def run_end_path(run_dir: Path) -> Path:
    return run_dir / "run_end.json"


def write_manifest(run_dir: Path, manifest: RunManifest) -> Path:
    """Persist the run manifest. Returns the written path."""
    path = manifest_path(run_dir)
    _atomic_write_json(path, asdict(manifest))
    return path


def update_manifest_policy_snapshot_id(
    run_dir: Path,
    policy_snapshot_id: str,
) -> None:
    """After the first successful receipt, patch the manifest with the
    resolved policy_snapshot_id. Done as a full atomic rewrite — the
    manifest is small (<2 KB) so there's no need for partial-update
    machinery, and the atomic-rename gives us crash safety for free.

    Idempotent: calling this twice with the same id is a no-op write."""
    path = manifest_path(run_dir)
    with path.open("r", encoding="utf-8") as fp:
        current = json.load(fp)
    if current.get("policy_snapshot_id") == policy_snapshot_id:
        return
    current["policy_snapshot_id"] = policy_snapshot_id
    _atomic_write_json(path, current)


def write_run_end(run_dir: Path, run_end: RunEnd) -> Path:
    """Persist the run-end summary. Returns the written path."""
    path = run_end_path(run_dir)
    _atomic_write_json(path, asdict(run_end))
    return path


# ---------------------------------------------------------------------------
# Convenience constructors — keep eval-loop call sites tight
# ---------------------------------------------------------------------------


def build_manifest(
    *,
    run_id: str,
    run_phase: RunPhase,
    repo_dir: Path,
    meshqu_api_url: str,
    meshqu_tenant_label: str,
    agent_model_id: str,
    agent_temperature: float,
    agent_max_completion_tokens: int,
    agent_prompt_sha256: str,
    substrate_adapter_version: str,
    substrate_source: dict[str, Any],
    record_target_count: int,
    policy_code: str | None = None,
    notes: dict[str, Any] | None = None,
) -> RunManifest:
    """Pull `runner_git_commit` + `started_at` from the runtime and bundle
    everything else the caller supplies into a frozen RunManifest. The
    eval loop calls this once at run start."""

    sha, dirty = resolve_git_commit(repo_dir)
    return RunManifest(
        run_id=run_id,
        run_phase=run_phase,
        started_at=_utc_now_iso(),
        runner_git_commit=sha,
        runner_git_dirty=dirty,
        meshqu_api_url=meshqu_api_url,
        meshqu_tenant_label=meshqu_tenant_label,
        agent_model_id=agent_model_id,
        agent_temperature=agent_temperature,
        agent_max_completion_tokens=agent_max_completion_tokens,
        agent_prompt_sha256=agent_prompt_sha256,
        substrate_adapter_version=substrate_adapter_version,
        substrate_source=substrate_source,
        record_target_count=record_target_count,
        policy_code=policy_code,
        notes=notes or {},
    )


def build_run_end(
    *,
    run_id: str,
    status: Literal["completed", "aborted_by_anomaly", "aborted_by_signal", "aborted_by_error"],
    records_attempted: int,
    records_with_receipt: int,
    records_with_agent_parse_failure: int,
    records_with_meshqu_error: int,
    policy_snapshot_id: str | None,
    abort_reason: str | None = None,
) -> RunEnd:
    """Constructor that stamps `ended_at` from the runtime."""

    return RunEnd(
        run_id=run_id,
        ended_at=_utc_now_iso(),
        status=status,
        records_attempted=records_attempted,
        records_with_receipt=records_with_receipt,
        records_with_agent_parse_failure=records_with_agent_parse_failure,
        records_with_meshqu_error=records_with_meshqu_error,
        policy_snapshot_id=policy_snapshot_id,
        abort_reason=abort_reason,
    )
