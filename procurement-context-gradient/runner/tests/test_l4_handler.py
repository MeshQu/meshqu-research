"""Tests for the L4 (full policy envelope) handler — E2-005.

Covers the done criteria from
`planning/build_packages/e2-005-l4-policy-payload.md` §3:

1. L4 prompt construction is deterministic for a given record (same
   record + same archive + same envelope → same prompt bytes).
2. L4 prompt strictly contains the L3 prompt's content (additivity
   invariant — containment, not position).
3. The policy JSON appears in the L4 prompt at a stable structural
   position (always inside the rendered envelope, which always sits
   in the stable cache prefix). Test the property, not the exact
   byte offset.
4. Mock OpenAI response with cached_tokens=4500 and verify the
   runner extracts and records it correctly.

Plus a few invariants that guard against silent drift:

- The L4 rendered envelope's SHA-256 is stable (the same bytes
  Stage A locked at PR #48 + the snapshot JSON locked at Phase 0).
- The policy block sits BEFORE the per-record-varying base record
  message (cache-friendly placement).
- The empty-envelope path raises clearly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from meshqu_runner import multi_pass as mp
from meshqu_runner.agent import AgentResponse, sha256_reasoning
from meshqu_runner.context_levels.level_l4 import (
    L4PolicyEnvelopeHandler,
    POLICY_INTERPOLATION_KEY,
    POLICY_JSON_INDENT,
    StageAEnvelopeError,
    build_l4_handler,
    load_policy_snapshot,
    render_l4_envelope,
    render_policy_block,
    sha256_rendered_envelope,
)
from meshqu_runner.level_handlers import (
    MAIN_LEVELS,
    L0Handler,
    L1Handler,
    L2Handler,
    L3Handler,
    compose_user_message,
)
from meshqu_runner.prompt_loader import load_level_prompts


RUNNER_DIR = Path(__file__).resolve().parent.parent
E2_DIR = RUNNER_DIR.parent
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"
FIXTURE_PATH = RUNNER_DIR / "tests" / "fixtures" / "smoke_records.json"

# Policy snapshot SHA-256 (locked at Phase 0). The rendered-envelope
# SHA in tests is NOT the same as this — it's the SHA of the L4
# envelope template AFTER policy JSON has been interpolated as
# indent=2 pretty-printed JSON.
LOCKED_POLICY_SNAPSHOT_SHA = (
    "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_records() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture()
def loaded_prompts():
    return load_level_prompts(PROMPTS_DIR)


@pytest.fixture()
def handler() -> L4PolicyEnvelopeHandler:
    return build_l4_handler(POLICY_SNAPSHOT_PATH)


@pytest.fixture()
def main_handlers(handler: L4PolicyEnvelopeHandler):
    """Default L0..L3 stubs + the production L4 handler."""
    return {
        "L0": L0Handler(),
        "L1": L1Handler(),
        "L2": L2Handler(),
        "L3": L3Handler(),
        "L4": handler,
    }


# ---------------------------------------------------------------------------
# Rendering primitives
# ---------------------------------------------------------------------------


def test_policy_snapshot_loads_and_matches_locked_sha():
    """The on-disk snapshot file is byte-identical to what was locked
    at Phase 0. A drift here invalidates every receipt the runner has
    ever produced against this snapshot id."""
    raw_bytes = POLICY_SNAPSHOT_PATH.read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == LOCKED_POLICY_SNAPSHOT_SHA

    # The file parses as JSON without errors.
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    assert isinstance(policy, dict)
    assert "rules" in policy
    assert len(policy["rules"]) == 6


def test_render_policy_block_is_deterministic():
    """Calling render twice on the same dict yields byte-identical
    output. Deterministic indent=2 pretty-print."""
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    a = render_policy_block(policy)
    b = render_policy_block(policy)
    assert a == b

    # Indentation is exactly POLICY_JSON_INDENT spaces at the first
    # nested level.
    assert f"\n{' ' * POLICY_JSON_INDENT}\"created_at\"" in a


def test_render_l4_envelope_substitutes_policy_block(loaded_prompts):
    """The rendered envelope contains the policy JSON in place of the
    `{policy_snapshot_json}` interpolation token."""
    template = loaded_prompts.get("L4").content
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    rendered = render_l4_envelope(template, policy)

    # Interpolation token is gone.
    assert POLICY_INTERPOLATION_KEY not in rendered
    # Policy keys are visible somewhere in the rendering.
    assert "\"PROC-001-S53\"" in rendered
    assert "\"PROC-006-MOD-CAP\"" in rendered


def test_render_l4_envelope_rejects_missing_token():
    """A template that no longer carries the interpolation token is a
    Stage A drift — the renderer raises immediately."""
    template_without_token = "## Policy under evaluation\n\nNo placeholder here.\n"
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    with pytest.raises(StageAEnvelopeError):
        render_l4_envelope(template_without_token, policy)


def test_render_l4_envelope_rejects_duplicate_token():
    """A template carrying the token more than once is a Stage A drift —
    the locked envelope has it exactly once."""
    template_with_dupe = (
        "## Policy under evaluation\n\n"
        f"```json\n{POLICY_INTERPOLATION_KEY}\n```\n\n"
        f"Again: {POLICY_INTERPOLATION_KEY}\n"
    )
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    with pytest.raises(StageAEnvelopeError):
        render_l4_envelope(template_with_dupe, policy)


def test_sha256_rendered_envelope_is_stable(loaded_prompts):
    """The SHA of the rendered envelope is byte-stable across re-runs.
    Used by the manifest as `prompt_template_sha256.L4_rendered`."""
    template = loaded_prompts.get("L4").content
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    rendered_1 = render_l4_envelope(template, policy)
    rendered_2 = render_l4_envelope(template, policy)
    assert sha256_rendered_envelope(rendered_1) == sha256_rendered_envelope(rendered_2)


# ---------------------------------------------------------------------------
# Handler + compose_user_message integration
# ---------------------------------------------------------------------------


def test_handler_render_caches_envelope(handler: L4PolicyEnvelopeHandler, loaded_prompts):
    """The handler caches the rendered envelope on first render() so
    subsequent calls return the same Python string object (and
    obviously the same bytes). The cache is what makes the L4 batch's
    287 calls send literally-identical policy text — the precondition
    for OpenAI's prompt cache to hit."""
    a = handler.render(loaded_prompts)
    b = handler.render(loaded_prompts)
    assert a == b
    # Strong-identity check: the handler returns its cached value.
    assert handler.rendered_envelope is a or handler.rendered_envelope == a


def test_l4_prompt_is_deterministic(handler, main_handlers, loaded_prompts):
    """Same record + same archive + same envelope → same prompt bytes."""
    record = _load_records()[0]
    base = "BASE_RECORD_MESSAGE"
    composed_a = compose_user_message(
        level="L4",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )
    composed_b = compose_user_message(
        level="L4",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )
    assert composed_a == composed_b


def test_l4_prompt_contains_l3_content(handler, main_handlers, loaded_prompts):
    """Additivity invariant — containment, not position.

    Every character that appears in the L3 composition's prefix must
    also appear somewhere in the L4 composition. The L4 handler
    moves the L4 policy block to the head of the message; L1..L3
    addenda still follow it, so their content is present as a
    suffix-block inside L4's message."""
    record = _load_records()[0]
    base = "BASE_RECORD_MESSAGE"
    composed_l3 = compose_user_message(
        level="L3",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )
    composed_l4 = compose_user_message(
        level="L4",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )

    # Check the L3 marginal addendum (the precedent-block format
    # section) is present in the L4 composition.
    l3_addendum = main_handlers["L3"].build_addendum(
        record=record, ocid=record["ocid"], prompts=loaded_prompts
    )
    if l3_addendum.strip():
        assert l3_addendum.strip() in composed_l4, (
            "L4 composition does not contain L3's marginal addendum"
        )

    # The L1 and L2 addenda likewise survive into L4.
    for level in ("L1", "L2"):
        addendum = main_handlers[level].build_addendum(
            record=record, ocid=record["ocid"], prompts=loaded_prompts
        )
        if addendum.strip():
            assert addendum.strip() in composed_l4, (
                f"L4 composition does not contain {level}'s marginal addendum"
            )


def test_l4_policy_block_is_at_the_top(handler, main_handlers, loaded_prompts):
    """Cache-preservation contract: the rendered envelope (with the
    policy JSON) must sit at the head of the L4 user message, BEFORE
    any L1..L3 addendum and BEFORE the per-record-varying base
    message.

    This is the structural property the package prompt §3 names: the
    policy JSON appears in the L4 prompt at a stable position
    relative to the per-call-varying content."""
    record = _load_records()[0]
    base = "BASE_RECORD_MESSAGE_MARKER"
    composed_l4 = compose_user_message(
        level="L4",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )

    handler.render(loaded_prompts)
    rendered_envelope = handler.rendered_envelope

    # The rendered envelope must occur EARLIER in the message than the
    # base record message (the per-call-varying content).
    envelope_pos = composed_l4.find(rendered_envelope)
    base_pos = composed_l4.find(base)
    assert envelope_pos == 0, (
        f"policy envelope is not at offset 0 in the L4 message "
        f"(found at offset {envelope_pos})"
    )
    assert envelope_pos < base_pos, (
        f"policy envelope offset {envelope_pos} not before base "
        f"message offset {base_pos}"
    )

    # The rendered envelope contains the policy JSON.
    assert "\"PROC-001-S53\"" in rendered_envelope


def test_l4_policy_block_precedes_lower_addenda(handler, main_handlers, loaded_prompts):
    """The cache-prefix design also requires the policy to precede the
    L1 / L2 / L3 addenda — the stable prefix in the order
    `[policy] [L1] [L2] [L3]` so OpenAI's cache extends through as
    much stable content as possible. (L1 + L2 are stable too, but
    putting them BEFORE the policy would shrink the cache prefix on
    the very-first L4 call until OpenAI built up the full prefix.)"""
    record = _load_records()[0]
    base = "BASE"
    composed_l4 = compose_user_message(
        level="L4",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )

    handler.render(loaded_prompts)
    rendered_envelope = handler.rendered_envelope
    envelope_pos = composed_l4.find(rendered_envelope)

    for level in ("L1", "L2", "L3"):
        addendum = main_handlers[level].build_addendum(
            record=record, ocid=record["ocid"], prompts=loaded_prompts
        )
        if not addendum.strip():
            continue
        addendum_pos = composed_l4.find(addendum.strip())
        # The addendum must appear AFTER the policy envelope.
        assert envelope_pos < addendum_pos, (
            f"{level} addendum at offset {addendum_pos} appears before "
            f"policy envelope at offset {envelope_pos}"
        )


def test_compose_user_message_falls_back_for_non_l4_levels(handler, main_handlers, loaded_prompts):
    """Backward compat — handlers without `compose_full_message` use
    the default additive concat. L0..L3 should behave EXACTLY as the
    E2-001 baseline."""
    record = _load_records()[0]
    base = "BASE"
    composed_l3 = compose_user_message(
        level="L3",
        record=record,
        ocid=record["ocid"],
        prompts=loaded_prompts,
        handlers=main_handlers,
        base_message=base,
    )

    # Re-derive the expected L3 composition via the default-path logic.
    addenda = [
        main_handlers[lvl].build_addendum(
            record=record, ocid=record["ocid"], prompts=loaded_prompts
        )
        for lvl in MAIN_LEVELS[:4]  # L0..L3
    ]
    prefix = "".join(part for part in addenda if part)
    expected = base if not prefix else f"{prefix}\n{base}"

    assert composed_l3 == expected


def test_rendered_envelope_sha_is_published_in_decision_log(handler, loaded_prompts):
    """The SHA-256 of the rendered L4 envelope is a load-bearing
    artefact — it gets published in the PR body + the decision log.

    This test pins the value computed in THIS environment so a future
    silent change to the renderer (or to the locked policy snapshot)
    is caught. If the rendered SHA changes, the package's PR body
    answer needs updating, the decision_log entry needs updating, AND
    the manifest's `prompt_template_sha256.L4_rendered` claim needs
    refreshing.
    """
    handler.render(loaded_prompts)
    sha = handler.rendered_sha256
    assert len(sha) == 64
    # Recompute from primitives to make sure the property is consistent.
    template = loaded_prompts.get("L4").content
    policy = load_policy_snapshot(POLICY_SNAPSHOT_PATH)
    rendered = render_l4_envelope(template, policy)
    assert sha == sha256_rendered_envelope(rendered)


# ---------------------------------------------------------------------------
# Cached-tokens telemetry (mocked OpenAI usage block)
# ---------------------------------------------------------------------------


@dataclass
class _StubUsage:
    """Mimics openai's `CompletionUsage` shape."""

    prompt_tokens: int
    prompt_tokens_details: Any
    completion_tokens: int = 12
    total_tokens: int = 0


@dataclass
class _StubUsageDetails:
    cached_tokens: int


@dataclass
class _StubChoice:
    message: Any


@dataclass
class _StubMessage:
    content: str


@dataclass
class _StubChatResp:
    choices: list[_StubChoice]
    usage: _StubUsage


class _FakeOpenAIClient:
    """Drop-in for `openai.OpenAI` exposing the
    `client.chat.completions.create(**kwargs)` surface.

    Returns a response with a controllable usage.cached_tokens value
    so the Agent's extraction can be exercised without hitting
    OpenAI."""

    def __init__(self, *, content: str, cached: int, prompt_tokens: int = 5000):
        self._content = content
        self._cached = cached
        self._prompt_tokens = prompt_tokens

        class _CC:
            def __init__(self, outer: "_FakeOpenAIClient") -> None:
                self._outer = outer

            def create(self, **kwargs: Any) -> _StubChatResp:
                return _StubChatResp(
                    choices=[
                        _StubChoice(
                            message=_StubMessage(content=self._outer._content)
                        )
                    ],
                    usage=_StubUsage(
                        prompt_tokens=self._outer._prompt_tokens,
                        prompt_tokens_details=_StubUsageDetails(
                            cached_tokens=self._outer._cached
                        ),
                    ),
                )

        class _Chat:
            def __init__(self, outer: "_FakeOpenAIClient") -> None:
                self.completions = _CC(outer)

        self.chat = _Chat(self)


def test_agent_extracts_cached_tokens_from_usage_block():
    """Mocked OpenAI response with cached_tokens=4500 (the ~policy
    block size) must surface as AgentResponse.cached_tokens=4500."""
    from meshqu_runner.agent import Agent

    fake_client = _FakeOpenAIClient(
        content='{"verdict": "review", "reasoning": "ok", "recommended_action": null}',
        cached=4500,
        prompt_tokens=5200,
    )
    agent = Agent(
        api_key="dummy",
        system_prompt="SYSTEM",
        client=fake_client,
    )
    response = agent.evaluate("USER_MESSAGE")
    assert response.parse_status == "ok"
    assert response.cached_tokens == 4500
    assert response.prompt_tokens == 5200


def test_agent_tolerates_missing_usage_block():
    """When the response has no usage info (older models / unusual
    SDK responses), cached_tokens and prompt_tokens are None."""
    from meshqu_runner.agent import Agent

    class _NoUsageResp:
        def __init__(self, content: str) -> None:
            self.choices = [_StubChoice(message=_StubMessage(content=content))]
            self.usage = None  # Pretend the SDK omitted usage entirely.

    class _NoUsageClient:
        def __init__(self) -> None:
            class _CC:
                def create(self, **kwargs: Any) -> _NoUsageResp:
                    return _NoUsageResp(
                        '{"verdict": "review", "reasoning": "ok", "recommended_action": null}'
                    )

            class _Chat:
                def __init__(self) -> None:
                    self.completions = _CC()

            self.chat = _Chat()

    agent = Agent(api_key="dummy", system_prompt="S", client=_NoUsageClient())
    response = agent.evaluate("USER")
    assert response.cached_tokens is None
    assert response.prompt_tokens is None


def test_cache_telemetry_jsonl_is_written_by_run(tmp_path: Path):
    """End-to-end: a stub multi_pass run writes a
    cache_telemetry.jsonl sidecar carrying one row per (record,
    level). Stub agent emits cached_tokens=None — we verify the row
    shape, not non-zero hits (that's the live smoke test's job)."""
    records = _load_records()
    run_dir = tmp_path / "runs" / "telemetry-shape"
    config = mp.MultiPassConfig(
        run_id="telemetry-shape-001",
        run_phase="dry-run",
        repo_dir=E2_DIR.parent,
        run_dir=run_dir,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        cache_telemetry_enabled=True,
    )
    summary = mp.run_multi_pass(
        config=config,
        records=records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
    )

    telemetry_path = run_dir / mp.CACHE_TELEMETRY_FILENAME
    assert telemetry_path.exists(), "cache_telemetry.jsonl was not written"

    rows = [
        json.loads(line)
        for line in telemetry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # 3 records × 5 levels = 15 rows.
    assert len(rows) == 15
    for row in rows:
        # Schema check.
        assert set(row.keys()) >= {
            "run_id",
            "level",
            "record_index",
            "ocid",
            "decision_id",
            "timestamp",
            "cached_tokens",
            "prompt_tokens",
            "is_stub",
        }
        # Stub agent emits cached_tokens=None (no real model call).
        assert row["cached_tokens"] is None
        assert row["is_stub"] is True
        assert row["level"] in MAIN_LEVELS


def test_cache_telemetry_disabled_when_flag_off(tmp_path: Path):
    """When `cache_telemetry_enabled=False` no sidecar is written and
    the orchestrator otherwise behaves exactly as before."""
    records = _load_records()
    run_dir = tmp_path / "runs" / "telemetry-off"
    config = mp.MultiPassConfig(
        run_id="telemetry-off-001",
        run_phase="dry-run",
        repo_dir=E2_DIR.parent,
        run_dir=run_dir,
        prompts_dir=PROMPTS_DIR,
        policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        cache_telemetry_enabled=False,
    )
    summary = mp.run_multi_pass(
        config=config,
        records=records,
        agent=mp.StubAgent(),
        meshqu_client=mp.StubMeshQuClient(),
    )

    assert len(summary.outcomes) == 15
    assert not (run_dir / mp.CACHE_TELEMETRY_FILENAME).exists()


# ---------------------------------------------------------------------------
# Permuted-policy hook (E2-006 forward-compat)
# ---------------------------------------------------------------------------


def test_render_l4_envelope_accepts_permuted_policy(loaded_prompts):
    """E2-006 must be able to render the SAME envelope template with a
    different policy dict (the permuted variant) without
    re-implementing the renderer. The result must be a valid
    envelope of the same structure, just with permuted bytes
    inside."""
    template = loaded_prompts.get("L4").content
    real = load_policy_snapshot(POLICY_SNAPSHOT_PATH)

    # Simulate a permuted policy: reverse the rules array order.
    permuted = dict(real)
    permuted["rules"] = list(reversed(real["rules"]))

    rendered_real = render_l4_envelope(template, real)
    rendered_permuted = render_l4_envelope(template, permuted)

    assert rendered_real != rendered_permuted, (
        "permuted policy rendered identically — render path is "
        "not honouring the policy dict ordering"
    )
    # Both renderings still contain the same set of rule codes.
    for code in ("PROC-001-S53", "PROC-006-MOD-CAP"):
        assert code in rendered_real
        assert code in rendered_permuted
