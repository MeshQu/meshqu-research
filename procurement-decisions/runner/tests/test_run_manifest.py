"""
Tests for run_manifest — atomic-write discipline, build helpers,
and the policy_snapshot_id late-patch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from meshqu_runner.run_manifest import (
    RunManifest,
    build_manifest,
    build_run_end,
    manifest_path,
    resolve_git_commit,
    run_end_path,
    update_manifest_policy_snapshot_id,
    write_manifest,
    write_run_end,
)


def _new_git_repo(path: Path) -> str:
    """Init a tiny git repo for testing resolve_git_commit. Returns the sha."""
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "x@y"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "f.txt").write_text("hi")
    subprocess.run(["git", "add", "f.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=path, check=True)
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()
    return sha


class TestResolveGitCommit:
    def test_clean_repo(self, tmp_path: Path) -> None:
        sha = _new_git_repo(tmp_path)
        got_sha, dirty = resolve_git_commit(tmp_path)
        assert got_sha == sha
        assert dirty is False

    def test_dirty_repo(self, tmp_path: Path) -> None:
        _new_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("changed")
        _, dirty = resolve_git_commit(tmp_path)
        assert dirty is True

    def test_non_repo_returns_unknown(self, tmp_path: Path) -> None:
        sha, dirty = resolve_git_commit(tmp_path)
        assert sha == "unknown"
        assert dirty is False


class TestBuildManifest:
    def test_required_fields_populated(self, tmp_path: Path) -> None:
        _new_git_repo(tmp_path)
        m = build_manifest(
            run_id="rid",
            run_phase="dry-run",
            repo_dir=tmp_path,
            meshqu_api_url="https://x/",
            meshqu_tenant_label="experiment-procurement",
            agent_model_id="gpt-5.4-2026-03-05",
            agent_temperature=0.0,
            agent_max_completion_tokens=500,
            agent_prompt_sha256="prompthash",
            substrate_adapter_version="0.1.0",
            substrate_source={"feed": "x", "since": "2025-01-01"},
            record_target_count=10,
        )
        assert m.run_id == "rid"
        assert m.run_phase == "dry-run"
        assert m.agent_model_id == "gpt-5.4-2026-03-05"
        assert m.agent_temperature == 0.0
        assert m.runner_git_commit  # non-empty
        assert m.policy_snapshot_id is None  # patched later
        assert m.started_at.endswith("+00:00") or m.started_at.endswith("Z")


class TestWriteManifestAtomic:
    def test_writes_canonical_json(self, tmp_path: Path) -> None:
        m = RunManifest(
            run_id="rid",
            run_phase="dry-run",
            started_at="2026-05-16T00:00:00+00:00",
            runner_git_commit="abc",
            runner_git_dirty=False,
            meshqu_api_url="https://x/",
            meshqu_tenant_label="t",
            agent_model_id="m",
            agent_temperature=0.0,
            agent_max_completion_tokens=500,
            agent_prompt_sha256="ph",
            substrate_adapter_version="0.1.0",
            substrate_source={},
            record_target_count=10,
        )
        run_dir = tmp_path / "runs" / "rid"
        path = write_manifest(run_dir, m)
        assert path == manifest_path(run_dir)
        body = json.loads(path.read_text())
        assert body["run_id"] == "rid"
        assert body["agent_temperature"] == 0.0

    def test_no_tmp_left_behind(self, tmp_path: Path) -> None:
        m = RunManifest(
            run_id="rid", run_phase="dry-run", started_at="t",
            runner_git_commit="abc", runner_git_dirty=False,
            meshqu_api_url="x", meshqu_tenant_label="t",
            agent_model_id="m", agent_temperature=0.0,
            agent_max_completion_tokens=1, agent_prompt_sha256="p",
            substrate_adapter_version="v", substrate_source={},
            record_target_count=1,
        )
        run_dir = tmp_path / "runs" / "rid"
        write_manifest(run_dir, m)
        # No `.tmp` sibling should exist after atomic rename completes.
        assert not (run_dir / "manifest.json.tmp").exists()


class TestUpdatePolicySnapshotId:
    def test_patches_field(self, tmp_path: Path) -> None:
        m = RunManifest(
            run_id="rid", run_phase="dry-run", started_at="t",
            runner_git_commit="abc", runner_git_dirty=False,
            meshqu_api_url="x", meshqu_tenant_label="t",
            agent_model_id="m", agent_temperature=0.0,
            agent_max_completion_tokens=1, agent_prompt_sha256="p",
            substrate_adapter_version="v", substrate_source={},
            record_target_count=1,
        )
        run_dir = tmp_path / "runs" / "rid"
        write_manifest(run_dir, m)
        update_manifest_policy_snapshot_id(run_dir, "snap-uuid")
        body = json.loads(manifest_path(run_dir).read_text())
        assert body["policy_snapshot_id"] == "snap-uuid"

    def test_idempotent(self, tmp_path: Path) -> None:
        m = RunManifest(
            run_id="rid", run_phase="dry-run", started_at="t",
            runner_git_commit="abc", runner_git_dirty=False,
            meshqu_api_url="x", meshqu_tenant_label="t",
            agent_model_id="m", agent_temperature=0.0,
            agent_max_completion_tokens=1, agent_prompt_sha256="p",
            substrate_adapter_version="v", substrate_source={},
            record_target_count=1,
        )
        run_dir = tmp_path / "runs" / "rid"
        write_manifest(run_dir, m)
        update_manifest_policy_snapshot_id(run_dir, "snap-uuid")
        first_mtime = manifest_path(run_dir).stat().st_mtime_ns
        update_manifest_policy_snapshot_id(run_dir, "snap-uuid")
        # No-op write: mtime should not change
        assert manifest_path(run_dir).stat().st_mtime_ns == first_mtime


class TestRunEnd:
    def test_build_and_write(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "rid"
        run_dir.mkdir(parents=True)
        end = build_run_end(
            run_id="rid",
            status="completed",
            records_attempted=10,
            records_with_receipt=7,
            records_with_agent_parse_failure=1,
            records_with_agent_call_error=1,
            records_with_meshqu_error=0,
            records_with_orphaned_receipt=1,
            policy_snapshot_id="snap-uuid",
        )
        write_run_end(run_dir, end)
        body = json.loads(run_end_path(run_dir).read_text())
        assert body["status"] == "completed"
        assert body["records_attempted"] == 10
        assert body["records_with_receipt"] == 7
        assert body["records_with_agent_call_error"] == 1
        assert body["records_with_orphaned_receipt"] == 1
        assert body["policy_snapshot_id"] == "snap-uuid"
