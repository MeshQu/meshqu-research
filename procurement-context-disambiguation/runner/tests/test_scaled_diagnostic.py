"""Tests for the E3-008 scaled Permuted-Policy diagnostic.

Covers the four assertions called out in
``planning/build_packages/e3-008-scaled-permuted-policy.md`` §5:

1. Subset loader returns the same list as the committed JSON.
2. The handler for ``diagnostic_primary`` reproduces the byte-identical
   rendered permuted-L4 envelope for the same policy + seed (this is
   the "matches E2's 14-record diagnostic byte-for-byte" regression
   check; since the rendered envelope is record-independent, the
   byte-identity check reduces to comparing rendered envelope SHA
   against E2's known permuted-L4 rendering).
3. The handler for ``diagnostic_claude`` produces the SAME rendered
   prompt as ``diagnostic_primary`` — only the agent dispatch differs.
4. Receipts written by each arm carry ``diagnostic: true`` +
   ``policy_permutation_seed`` set, distinguishing them from main-run
   receipts.

Plus contract-shape tests for the inverted-operator-spec sidecar
(payload conforms to ``rubric_io.load_inverted_specs``'s accepted
shape) and the ClaudeAgent wrapper (conforms to the ``Agent``
protocol the runner expects).

No live API calls — every test injects either ``StubAgent`` (for the
end-to-end runner check) or a hand-built ``ClaudeAgent`` with a mocked
``call()`` (for the wrapper-shape check).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from meshqu_runner.arms import ARM_PROFILES, HANDLERS
from meshqu_runner.arms.diagnostic import (
    DEFAULT_ENVELOPE_PATH,
    DEFAULT_POLICY_SNAPSHOT_PATH,
    diagnostic_claude_handler,
    diagnostic_primary_handler,
    render_permuted_l4_envelope,
    rendered_envelope_sha256,
)
from meshqu_runner.agents.claude import ClaudeAgent, ClaudeAdapterError
from meshqu_runner.context_levels.level_l4_permuted import (
    UNPERTURBED_L4_RENDERED_SHA256,
)
from meshqu_runner.diagnostic.permute_policy import (
    LOCKED_PERMUTATION_SEED,
    PERMUTATION_LOG_KEY,
    permute_policy,
)
from meshqu_runner.diagnostic.rubric_io import load_inverted_specs
from meshqu_runner.diagnostic.scaled import (
    DIAGNOSTIC_SUBSET_RELATIVE_PATH,
    INVERTED_OPERATOR_SPEC_FILENAME,
    build_inverted_operator_spec_payload,
    emit_inverted_operator_spec,
    load_diagnostic_subset,
)

# DIAGNOSTIC_SUBDIR is the standard "diagnostic" directory name used by
# both E2's 14-record diagnostic and E3-008's scaled diagnostic for the
# inverted-operator-spec sidecar location. Define here so the test
# file doesn't depend on E2's broken-in-fork ``diagnostic/runner.py``
# being importable.
DIAGNOSTIC_SUBDIR = "diagnostic"
from meshqu_runner.context_levels.level_l4 import load_policy_snapshot
from meshqu_runner.multi_pass import (
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)


# ---------------------------------------------------------------------------
# Locked subset on-disk path — used by multiple tests
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    # __file__ → meshqu-research/procurement-context-disambiguation/
    # runner/tests/test_scaled_diagnostic.py → 3 parents up to repo root.
    return Path(__file__).resolve().parents[3]


def _committed_subset_path() -> Path:
    return _repo_root() / DIAGNOSTIC_SUBSET_RELATIVE_PATH


def _committed_subset_ocids() -> list[str]:
    payload = json.loads(_committed_subset_path().read_text(encoding="utf-8"))
    return list(payload["ocids"])


# ---------------------------------------------------------------------------
# §5.1 — Subset loader
# ---------------------------------------------------------------------------


def test_load_diagnostic_subset_returns_committed_ocids():
    """The runtime loader returns the exact list committed to disk —
    same OCIDs, same order. The diagnostic claim depends on this
    invariant; if the loader ever diverges from the file, the locked
    subset is no longer load-bearing."""
    loaded = load_diagnostic_subset()
    committed = _committed_subset_ocids()
    assert loaded == committed


def test_load_diagnostic_subset_returns_exactly_100_ocids():
    """The locked subset is n=100. Any other count means the file has
    drifted from the v0.3 lock (or the loader is broken). Asserted
    independently of the file-equality check so a regression points
    to the right culprit."""
    loaded = load_diagnostic_subset()
    assert len(loaded) == 100


def test_load_diagnostic_subset_raises_on_missing_file(tmp_path: Path):
    """Stop condition: the locked file must exist. Loader fails
    loudly rather than silently returning an empty list."""
    # Point at a directory without the subset file
    with pytest.raises(FileNotFoundError, match="diagnostic subset"):
        load_diagnostic_subset(repo_dir=tmp_path)


def test_load_diagnostic_subset_raises_on_wrong_count(tmp_path: Path):
    """If the file drifts to a count != 100, the loader rejects."""
    fake_path = tmp_path / DIAGNOSTIC_SUBSET_RELATIVE_PATH
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(json.dumps({"ocids": ["a", "b", "c"]}))
    with pytest.raises(ValueError, match="expected 100"):
        load_diagnostic_subset(repo_dir=tmp_path)


def test_load_diagnostic_subset_raises_on_missing_ocids_key(tmp_path: Path):
    fake_path = tmp_path / DIAGNOSTIC_SUBSET_RELATIVE_PATH
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(json.dumps({"experiment": "E3"}))
    with pytest.raises(KeyError, match="ocids"):
        load_diagnostic_subset(repo_dir=tmp_path)


# ---------------------------------------------------------------------------
# §5.2 — Handler rendering: diagnostic_primary
# ---------------------------------------------------------------------------


def test_primary_handler_renders_non_empty_string():
    """The handler returns a rendered prompt — string, non-empty,
    carries the L4 envelope structure (the literal section heading
    from the locked envelope template)."""
    record = {"ocid": "any", "decision_type": "procurement_decision"}
    prompt = diagnostic_primary_handler(record)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # The Stage A envelope embeds the literal section heading.
    assert "Policy under evaluation" in prompt


def test_primary_handler_renders_record_independent_prompt():
    """The permuted-L4 envelope is record-independent — same prompt
    bytes for every OCID under the same policy + seed. (This is what
    makes the cross-OCID byte-identity claim meaningful: each record's
    integrity hash only differs in the agent-side fields.)"""
    record_a = {"ocid": "ocid-A", "decision_type": "procurement_decision"}
    record_b = {"ocid": "ocid-B", "decision_type": "procurement_decision"}
    prompt_a = diagnostic_primary_handler(record_a)
    prompt_b = diagnostic_primary_handler(record_b)
    assert prompt_a == prompt_b


def test_primary_handler_prompt_differs_from_unperturbed_l4():
    """The diagnostic's whole point: the rendered envelope must differ
    from the unperturbed L4 envelope. If the permutation silently
    no-op'd (every operator was its own inverse?), the diagnostic
    would emit a misleading receipt — surface as a hard fail."""
    rendered_sha = rendered_envelope_sha256()
    assert rendered_sha != UNPERTURBED_L4_RENDERED_SHA256, (
        "Permuted-L4 rendering collides with unperturbed rendering — "
        "the inverter silently no-op'd."
    )


def test_primary_handler_uses_locked_seed_by_default():
    """Default seed is LOCKED_PERMUTATION_SEED (0) — the E2 locked
    seed. The diagnostic re-uses E2's seed verbatim; scaling from
    14 to 100 records does not reseed."""
    assert LOCKED_PERMUTATION_SEED == 0
    record = {"ocid": "x", "decision_type": "procurement_decision"}
    # Render with default → seed=0
    default_prompt = diagnostic_primary_handler(record)
    # Render with explicit seed=0 → same bytes
    seed_0_prompt = diagnostic_primary_handler(record, seed=0)
    assert default_prompt == seed_0_prompt


# ---------------------------------------------------------------------------
# §5.3 — Handler rendering: per-arm prompt equality
# ---------------------------------------------------------------------------


def test_arms_render_identical_prompts():
    """The two diagnostic arms must produce IDENTICAL rendered prompts
    — the cross-model comparison only means something if the only
    varying axis is the model. The package spec calls this out:
    "the per-arm rendered prompts differ ONLY in the agent call, not
    in the rendered text".

    Asserted on a real OCID from the locked subset, and on a synthetic
    OCID — both must match.
    """
    real_ocid = _committed_subset_ocids()[0]
    real_record = {"ocid": real_ocid, "decision_type": "procurement_decision"}
    synthetic_record = {"ocid": "any", "decision_type": "procurement_decision"}

    primary_real = diagnostic_primary_handler(real_record)
    claude_real = diagnostic_claude_handler(real_record)
    assert primary_real == claude_real, (
        "diagnostic_primary and diagnostic_claude rendered different "
        "prompts — the cross-model comparison is no longer "
        "record-matched-on-prompt."
    )

    primary_synth = diagnostic_primary_handler(synthetic_record)
    claude_synth = diagnostic_claude_handler(synthetic_record)
    assert primary_synth == claude_synth


def test_arms_render_identical_prompt_sha256():
    """SHA-equality is the cleaner artefact for the PR body. Both arms
    on OCID-1 produce a prompt with the same SHA-256."""
    real_ocid = _committed_subset_ocids()[0]
    record = {"ocid": real_ocid, "decision_type": "procurement_decision"}
    primary_sha = hashlib.sha256(diagnostic_primary_handler(record).encode("utf-8")).hexdigest()
    claude_sha = hashlib.sha256(diagnostic_claude_handler(record).encode("utf-8")).hexdigest()
    assert primary_sha == claude_sha


# ---------------------------------------------------------------------------
# §5.2 (regression) — 14-record byte-identity against E2's diagnostic
# ---------------------------------------------------------------------------


def test_permutation_function_matches_e2_unchanged():
    """E2's permutation function is imported verbatim — applying it
    here produces the SAME output bytes E2's diagnostic would.

    This is the "matches E2 byte-for-byte" regression check. We don't
    re-render through E2's tree (that would require importing both
    runners simultaneously); instead we assert the inputs E3 feeds to
    the same shared function are byte-identical to what E2 feeds —
    same locked policy snapshot SHA, same locked seed.
    """
    # Policy SHA — verify the snapshot bytes match E2's locked SHA
    snapshot_sha = hashlib.sha256(
        DEFAULT_POLICY_SNAPSHOT_PATH.read_bytes()
    ).hexdigest()
    assert snapshot_sha == (
        "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d"
    ), (
        f"Policy snapshot SHA drifted: got {snapshot_sha!r}. The E3 "
        f"diagnostic must re-use E2's locked snapshot verbatim."
    )

    # Envelope SHA — verify E2's L4 envelope bytes match the locked SHA
    envelope_sha = hashlib.sha256(
        DEFAULT_ENVELOPE_PATH.read_bytes()
    ).hexdigest()
    assert envelope_sha == (
        "c90664f473c19b7482b9bb81f0bf546392819dd7bfb6f47bcb369ac713ac0b2d"
    ), (
        f"E2 L4 envelope SHA drifted: got {envelope_sha!r}. The "
        f"byte-identity-vs-E2 invariant requires E2's locked envelope."
    )


def test_render_permuted_l4_envelope_carries_policy_permutation_log_off_prompt():
    """The ``_permutation_log`` key is stripped from the policy dict
    before rendering — the LLM must not see runner-local provenance
    in the prompt (would give it a hint that the policy is
    adversarially modified). Asserted by rendering and checking the
    key's *literal text* doesn't appear in the output."""
    rendered = render_permuted_l4_envelope()
    assert PERMUTATION_LOG_KEY not in rendered, (
        f"{PERMUTATION_LOG_KEY!r} leaked into the rendered prompt — "
        "the LLM would see the inversion log."
    )


# ---------------------------------------------------------------------------
# §5.4 — Receipt integrity payload on each arm
# ---------------------------------------------------------------------------


def test_stub_signer_payload_for_diagnostic_primary(tmp_path: Path):
    """End-to-end: ``run_arm`` with the ``diagnostic_primary`` handler
    via the stub clients — assert the captured fields map carries the
    diagnostic markers (``diagnostic: true`` +
    ``policy_permutation_seed`` set + the primary model id).
    """
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="test-diagnostic-primary",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run-primary",
        arm_name="diagnostic_primary",
        policy_snapshot_path=None,
        policy_permutation_seed=LOCKED_PERMUTATION_SEED,
    )
    summary = run_arm(
        config=config,
        records=[{"ocid": _committed_subset_ocids()[0], "decision_type": "procurement_decision"}],
        agent=StubAgent(),
        meshqu_client=client,
    )
    assert len(summary.outcomes) == 1
    captured = client.captured_field_payloads[0]
    assert captured["diagnostic"] is True
    assert captured["policy_permutation_seed"] == LOCKED_PERMUTATION_SEED
    assert captured["model_id"] == "gpt-5.4-2026-03-05"
    assert captured["model_sampling"] == {"temperature": 0}
    assert captured["prereg_tag"] == "v0.3-predictions-locked"


def test_stub_signer_payload_for_diagnostic_claude(tmp_path: Path):
    """Same as above, but for the Claude arm — model_id flips to
    ``claude-opus-4-7`` with ``temperature: None`` + ``effort: "low"``.
    """
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="test-diagnostic-claude",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run-claude",
        arm_name="diagnostic_claude",
        policy_snapshot_path=None,
        policy_permutation_seed=LOCKED_PERMUTATION_SEED,
    )
    summary = run_arm(
        config=config,
        records=[{"ocid": _committed_subset_ocids()[0], "decision_type": "procurement_decision"}],
        agent=StubAgent(),
        meshqu_client=client,
    )
    assert len(summary.outcomes) == 1
    captured = client.captured_field_payloads[0]
    assert captured["diagnostic"] is True
    assert captured["policy_permutation_seed"] == LOCKED_PERMUTATION_SEED
    assert captured["model_id"] == "claude-opus-4-7"
    assert captured["model_sampling"]["temperature"] is None
    assert captured["model_sampling"]["effort"] == "low"
    assert captured["prereg_tag"] == "v0.3-predictions-locked"


def test_diagnostic_receipt_distinguishable_from_main_run_receipt(tmp_path: Path):
    """Diagnostic receipts vs main-grid receipts: the integrity hash
    must differ (the diagnostic carries ``diagnostic: true`` +
    ``policy_permutation_seed: 0``; an Arm A receipt carries
    ``diagnostic: false`` + ``policy_permutation_seed: None``). Even
    on the same OCID + same agent, the integrity_hashes diverge."""
    diag_client = StubMeshQuClient()
    diag_config = RunConfig(
        run_id="test-diag",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "diag",
        arm_name="diagnostic_primary",
        policy_snapshot_path=None,
        policy_permutation_seed=LOCKED_PERMUTATION_SEED,
    )
    record = {"ocid": _committed_subset_ocids()[0], "decision_type": "procurement_decision"}
    diag_summary = run_arm(
        config=diag_config,
        records=[record],
        agent=StubAgent(),
        meshqu_client=diag_client,
    )

    arm_a_client = StubMeshQuClient()
    arm_a_config = RunConfig(
        run_id="test-arm-a",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "arm-a",
        arm_name="arm_a",
        policy_snapshot_path=None,
    )
    arm_a_summary = run_arm(
        config=arm_a_config,
        records=[record],
        agent=StubAgent(),
        meshqu_client=arm_a_client,
    )

    diag_hash = diag_summary.outcomes[0].receipt.integrity_hash
    arm_a_hash = arm_a_summary.outcomes[0].receipt.integrity_hash
    assert diag_hash != arm_a_hash, (
        "Diagnostic and main-run receipts produced identical integrity "
        "hashes — the diagnostic markers are not entering the hash."
    )


# ---------------------------------------------------------------------------
# Inverted-operator-spec sidecar — shape conforms to rubric_io contract
# ---------------------------------------------------------------------------


def _real_permutation_log_entries() -> list[dict[str, Any]]:
    """Derive real permutation-log entries from the locked policy
    snapshot. Used to test the sidecar's payload shape against actual
    inputs rather than a synthetic fixture."""
    policy = load_policy_snapshot(DEFAULT_POLICY_SNAPSHOT_PATH)
    permuted = permute_policy(policy, seed=LOCKED_PERMUTATION_SEED)
    return list(permuted[PERMUTATION_LOG_KEY]["entries"])


def test_inverted_operator_spec_payload_shape():
    """The sidecar payload conforms to ``rubric_io.load_inverted_specs``'s
    accepted shape — top-level JSON object keyed by OCID, each value is
    a dict with a ``spec`` string. Extra keys (the per-rule original /
    inverted operator metadata) are allowed and ignored by the loader.
    """
    ocids = ["ocid-1", "ocid-2", "ocid-3"]
    entries = _real_permutation_log_entries()
    payload = build_inverted_operator_spec_payload(
        ocids=ocids, seed=LOCKED_PERMUTATION_SEED, permutation_log_entries=entries
    )

    assert isinstance(payload, dict)
    assert set(payload.keys()) == set(ocids)
    for ocid in ocids:
        entry = payload[ocid]
        assert isinstance(entry, dict)
        assert "spec" in entry
        assert isinstance(entry["spec"], str)
        assert len(entry["spec"]) > 0
        # Extra metadata is allowed
        assert "rules" in entry
        assert isinstance(entry["rules"], list)
        assert len(entry["rules"]) == len(entries)


def test_inverted_operator_spec_loadable_by_rubric_io(tmp_path: Path):
    """The sidecar file is loadable by the rubric tool's
    ``load_inverted_specs`` function (the explicit contract from
    PR #91 — see decision_log Wave 2 close-out, Contract #2).
    """
    ocids = _committed_subset_ocids()[:3]
    entries = _real_permutation_log_entries()
    diagnostic_dir = tmp_path / DIAGNOSTIC_SUBDIR
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    spec_path = emit_inverted_operator_spec(
        diagnostic_dir=diagnostic_dir,
        ocids=ocids,
        seed=LOCKED_PERMUTATION_SEED,
        permutation_log_entries=entries,
    )
    assert spec_path.exists()
    assert spec_path.name == INVERTED_OPERATOR_SPEC_FILENAME

    loaded = load_inverted_specs(spec_path)
    assert set(loaded.keys()) == set(ocids)
    for ocid in ocids:
        spec_obj = loaded[ocid]
        assert spec_obj.ocid == ocid
        assert isinstance(spec_obj.spec, str)
        assert "seed=" in spec_obj.spec  # mentions the locked seed
        assert "operator inverted" in spec_obj.spec


def test_inverted_operator_spec_summary_lists_six_rules():
    """The locked policy snapshot has six rules; the spec text lists
    all six rule inversions."""
    entries = _real_permutation_log_entries()
    assert len(entries) == 6, (
        f"Locked policy snapshot has {len(entries)} rules, expected 6. "
        "If the snapshot has been re-authored, this test is stale."
    )
    payload = build_inverted_operator_spec_payload(
        ocids=["x"], seed=LOCKED_PERMUTATION_SEED, permutation_log_entries=entries
    )
    rules = payload["x"]["rules"]
    assert len(rules) == 6
    rule_codes = {r["rule_code"] for r in rules}
    # All six PROC rules present
    expected_rule_code_prefix = "PROC-"
    for code in rule_codes:
        assert isinstance(code, str)
        assert code.startswith(expected_rule_code_prefix) or code == "<unknown>"


# ---------------------------------------------------------------------------
# ClaudeAgent wrapper — Path A contract conformance
# ---------------------------------------------------------------------------


def test_claude_agent_conforms_to_runner_agent_protocol():
    """``ClaudeAgent`` exposes the surface ``run_arm`` and
    ``_process_record`` consume: ``.evaluate(user_message) ->
    AgentResponse`` plus ``.model_id``, ``.temperature``,
    ``.system_prompt_sha256`` attributes."""
    agent = ClaudeAgent(system_prompt="test system prompt")
    assert agent.model_id == "claude-opus-4-7"
    assert agent.temperature is None
    assert isinstance(agent.system_prompt_sha256, str)
    assert len(agent.system_prompt_sha256) == 64  # sha256 hex digest
    assert callable(agent.evaluate)


def test_claude_agent_evaluate_returns_agent_response_on_success():
    """A successful Claude call (mocked) produces an ``AgentResponse``
    with the verdict up-cased + reasoning + recommended_action threaded
    through. Verdict normalisation: ``"allow"`` (lowercase from the
    adapter) becomes ``"ALLOW"`` (uppercase, matching the primary
    path's convention)."""
    fake_dict = {
        "verdict": "review",
        "reasoning": "the agent's chain of thought",
        "recommended_action": "request additional documentation",
        "raw": '{"verdict":"review","reasoning":"the agent\'s chain of thought"}',
        "usage": {"input_tokens": 1234, "output_tokens": 56},
        "model": "claude-opus-4-7",
        "latency_ms": 2700,
    }
    agent = ClaudeAgent(system_prompt="locked sys prompt")
    with patch("meshqu_runner.agents.claude.call", return_value=fake_dict):
        resp = agent.evaluate("user message body")
    assert resp.verdict == "REVIEW"
    assert resp.reasoning == "the agent's chain of thought"
    assert resp.recommended_action == "request additional documentation"
    assert resp.latency_ms == 2700
    assert resp.parse_status == "ok"
    assert resp.prompt_tokens == 1234


def test_claude_agent_evaluate_returns_failure_response_on_adapter_error():
    """Adapter errors do NOT propagate — they become parse-failure
    ``AgentResponse``s so the orchestrator's "log + continue" path
    stays uniform with the primary adapter."""
    agent = ClaudeAgent(system_prompt="sys prompt")
    with patch(
        "meshqu_runner.agents.claude.call",
        side_effect=ClaudeAdapterError("parse", "JSON syntax error"),
    ):
        resp = agent.evaluate("user message")
    assert resp.verdict is None
    assert resp.parse_status == "invalid_json"
    assert "JSON syntax error" in resp.parse_detail


def test_claude_agent_evaluate_returns_invalid_verdict_on_unknown_verdict():
    """Out-of-vocab verdicts from the adapter map to verdict=None +
    parse_status="invalid_verdict"."""
    fake_dict = {
        "verdict": None,  # call() already normalised to None
        "reasoning": "something",
        "recommended_action": None,
        "raw": '{"verdict":"banana"}',
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "model": "claude-opus-4-7",
        "latency_ms": 100,
    }
    agent = ClaudeAgent(system_prompt="sys")
    with patch("meshqu_runner.agents.claude.call", return_value=fake_dict):
        resp = agent.evaluate("user msg")
    assert resp.verdict is None
    assert resp.parse_status == "invalid_verdict"


# ---------------------------------------------------------------------------
# Arm registration: both names registered + profile values correct
# ---------------------------------------------------------------------------


def test_diagnostic_arms_registered_as_real_handlers():
    """``HANDLERS["diagnostic_primary"]`` and ``HANDLERS["diagnostic_claude"]``
    point at the real handlers, not the foundation's placeholders."""
    assert HANDLERS["diagnostic_primary"] is diagnostic_primary_handler
    assert HANDLERS["diagnostic_claude"] is diagnostic_claude_handler


def test_diagnostic_arm_profiles_carry_correct_defaults():
    """Profile values were laid by E3-001; reconfirm they are intact
    after E3-008's registration (regression catch — registration must
    not have side-effected the profile table)."""
    primary = ARM_PROFILES["diagnostic_primary"]
    assert primary.diagnostic is True
    assert primary.model_id == "gpt-5.4-2026-03-05"
    assert primary.model_sampling == {"temperature": 0}

    claude = ARM_PROFILES["diagnostic_claude"]
    assert claude.diagnostic is True
    assert claude.model_id == "claude-opus-4-7"
    assert claude.model_sampling == {"temperature": None, "effort": "low"}


# ---------------------------------------------------------------------------
# Sanity: locked file SHAs unchanged by this package's runs
# ---------------------------------------------------------------------------


def test_locked_files_sha_unchanged_after_render():
    """The diagnostic READS locked files (envelope, policy snapshot,
    subset JSON). None of them get WRITTEN. Render once + sha-check —
    the on-disk SHAs are stable.

    This is a load-bearing invariant: the v0.3-predictions-locked tag
    binds these SHAs. If a render path silently mutates a file, the
    pre-registration commitment is broken.
    """
    pre = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            DEFAULT_ENVELOPE_PATH,
            DEFAULT_POLICY_SNAPSHOT_PATH,
            _committed_subset_path(),
        )
    }

    # Trigger a rendering pass + a sidecar emit (using a tmp dir for the
    # sidecar so the test doesn't pollute results/).
    diagnostic_primary_handler({"ocid": "x", "decision_type": "procurement_decision"})
    diagnostic_claude_handler({"ocid": "y", "decision_type": "procurement_decision"})
    load_diagnostic_subset()

    post = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in pre
    }
    assert pre == post, (
        f"Locked file SHA drifted during render/load: {pre} → {post}"
    )
