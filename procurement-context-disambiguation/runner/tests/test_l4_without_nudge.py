"""Tests for the E3-005 L4-without-nudge handler.

The package spec calls out four assertions; this file exercises all
four plus the byte-identity invariant for the strip-and-render path:

1. The rendered prompt contains the policy-independence sentence
   (the clause that was KEPT).
2. The rendered prompt does NOT contain the nudge sentence (case-
   insensitive — assert that neither
   "If a rule cannot be confidently evaluated" nor
   "explicitly name that uncertainty" appears).
3. The receipt integrity payload sets ``nudge_excised: true`` for
   the ``l4_without_nudge`` arm and ``False`` for ``l4_with_nudge``.
4. The rendered L4-without-nudge prompt is byte-identical to E2's
   rendered L4 prompt EXCEPT for the missing nudge sentence
   ("render both, diff, assert the diff is exactly the nudge sentence
   and nothing else").

Plus the locked-bytes invariant: ``L4_without_nudge.md`` is READ
during rendering, never WRITTEN — its SHA-256 before and after a
render call is unchanged. This is the file-level corollary of Sam's
2026-05-28 resolution.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

import pytest

from meshqu_runner import arm_handlers  # noqa: F401 -- ensure registration
from meshqu_runner.arms import ARM_PROFILES, HANDLERS, inject_arm_fields
from meshqu_runner.arm_handlers.l4_without_nudge import (
    DEFAULT_ENVELOPE_PATH,
    DEFAULT_L4_WITH_NUDGE_PATH,
    DEFAULT_POLICY_SNAPSHOT_PATH,
    render_l4_with_nudge,
    render_l4_without_nudge,
)
from meshqu_runner.multi_pass import (
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)


# ---------------------------------------------------------------------------
# Locked sentences — exact bytes from the locked envelopes
# ---------------------------------------------------------------------------

INDEPENDENCE_SENTENCE = (
    "You are not required to mirror MeshQu's verdict; you are "
    "required to produce your own verdict based on the policy as "
    "authored."
)
"""The sentence that was KEPT in L4-without-nudge — the policy-
independence assertion."""

NUDGE_SENTENCE_TAIL = (
    " If a rule cannot be confidently evaluated because evidence is "
    "missing or ambiguous, explicitly name that uncertainty in your "
    "reasoning."
)
"""The sentence that was EXCISED. In E2's file it lives on the same
line as the independence sentence, separated by a single space — so
the "diff" between the two rendered envelopes is exactly this string
appended at the end of line 9."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Spec §3 assertion 1 — independence sentence preserved
# ---------------------------------------------------------------------------


def test_rendered_prompt_contains_policy_independence_sentence():
    rendered = render_l4_without_nudge()
    assert INDEPENDENCE_SENTENCE in rendered, (
        "the policy-independence sentence must be preserved in the "
        "L4-without-nudge rendering — only the nudge clause was meant "
        "to be excised."
    )


# ---------------------------------------------------------------------------
# Spec §3 assertion 2 — nudge sentence is gone
# ---------------------------------------------------------------------------


def test_rendered_prompt_does_not_contain_nudge_sentence_case_insensitive():
    rendered = render_l4_without_nudge().lower()
    # Both substrings from the package spec — checked case-insensitive
    # so a future author can't sneak the nudge back in by changing
    # capitalisation.
    assert "if a rule cannot be confidently evaluated" not in rendered
    assert "explicitly name that uncertainty" not in rendered


def test_rendered_prompt_does_not_contain_html_comment_header():
    """The methodological header is documentation for humans reviewing
    the locked file — the LLM must never see it (and in particular
    must never see the verbatim nudge sentence the header quotes)."""
    rendered = render_l4_without_nudge()
    assert "<!--" not in rendered
    assert "-->" not in rendered
    assert "LOCKED CONTENT" not in rendered  # text from inside the comment
    # Also: the strip + render must produce something that STARTS at the
    # first real heading, not at a stray blank line.
    assert rendered.startswith("## Policy under evaluation")


# ---------------------------------------------------------------------------
# Spec §3 assertion 4 + Sam 2026-05-28 — post-strip byte-identity
# ---------------------------------------------------------------------------


def test_post_strip_diff_against_e2_l4_is_exactly_the_nudge_sentence():
    """The load-bearing invariant. Render BOTH envelopes (E2's L4 and
    E3's L4-without-nudge) through the same primitive on the same
    policy snapshot, then diff the two rendered strings. The only
    difference must be the nudge sentence.

    If this test fails, the locked content has drifted from intent
    in some other way (or E2's L4 has been edited, which it must not
    be). Surface immediately."""
    with_nudge = render_l4_with_nudge()
    without_nudge = render_l4_without_nudge()

    # Re-attaching the nudge to the without-nudge rendering must
    # reproduce the with-nudge rendering byte-for-byte.
    assert without_nudge != with_nudge, (
        "the two renderings must differ — otherwise the surgical "
        "excision did not actually remove anything."
    )

    reconstructed = without_nudge.replace(
        INDEPENDENCE_SENTENCE,
        INDEPENDENCE_SENTENCE + NUDGE_SENTENCE_TAIL,
    )
    assert reconstructed == with_nudge, (
        "post-strip L4-without-nudge + the nudge sentence MUST reproduce "
        "E2's L4 byte-for-byte. If they don't, the locked content has "
        "drifted beyond just the nudge — stop and surface."
    )

    # Spelled out as a unified diff for the PR body's reviewer eye —
    # the diff must touch exactly one line, and the only difference
    # on that line is the nudge tail.
    diff_lines = list(
        difflib.unified_diff(
            with_nudge.splitlines(keepends=True),
            without_nudge.splitlines(keepends=True),
            lineterm="",
            n=0,
        )
    )
    # Header (---, +++) + one hunk header (@@) + one '-' line + one
    # '+' line = 5 entries. Anything more means the diff spans
    # multiple regions (it must not).
    minus_lines = [line for line in diff_lines if line.startswith("-") and not line.startswith("---")]
    plus_lines = [line for line in diff_lines if line.startswith("+") and not line.startswith("+++")]
    assert len(minus_lines) == 1, f"expected exactly 1 '-' line, got {len(minus_lines)}: {minus_lines!r}"
    assert len(plus_lines) == 1, f"expected exactly 1 '+' line, got {len(plus_lines)}: {plus_lines!r}"
    # The '-' line (E2) ends with the nudge tail; the '+' line (E3)
    # is the same line minus the nudge tail.
    assert minus_lines[0].rstrip("\n").endswith(
        "explicitly name that uncertainty in your reasoning."
    )
    assert "explicitly name that uncertainty" not in plus_lines[0]


# ---------------------------------------------------------------------------
# Locked-bytes invariant — file is READ, never WRITTEN
# ---------------------------------------------------------------------------


def test_l4_without_nudge_file_sha256_unchanged_by_render():
    """Sam's resolution: the locked file bytes stay intact. Any render
    operation must be read-only — confirmed by SHA-256 comparison
    before and after a render call."""
    before = _sha256_file(DEFAULT_ENVELOPE_PATH)
    render_l4_without_nudge()  # discard output; we care about the file
    after = _sha256_file(DEFAULT_ENVELOPE_PATH)
    assert before == after, (
        "L4_without_nudge.md was modified by the render call. The "
        "renderer must be read-only — Sam's 2026-05-28 resolution "
        "binds the file's SHA to v0.3-predictions-locked."
    )
    # Same for E2's envelope — the l4_with_nudge handler reads it too.
    e2_before = _sha256_file(DEFAULT_L4_WITH_NUDGE_PATH)
    render_l4_with_nudge()
    e2_after = _sha256_file(DEFAULT_L4_WITH_NUDGE_PATH)
    assert e2_before == e2_after, "E2's L4 envelope must not be mutated by E3."


def test_policy_snapshot_is_e2s_locked_snapshot():
    """The comparison only works if both arms see byte-identical
    policy JSON. The handler's default policy path MUST point at E2's
    locked snapshot — any drift here would confound the Framing A
    test."""
    e2_policy_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "procurement-context-gradient"
        / "policy"
        / "policy-snapshot-cbf12348.json"
    )
    assert DEFAULT_POLICY_SNAPSHOT_PATH.resolve() == e2_policy_path.resolve(), (
        "L4-without-nudge must reuse E2's locked policy snapshot."
    )
    # And the file must actually exist (no symlink rot etc.).
    assert DEFAULT_POLICY_SNAPSHOT_PATH.exists()


# ---------------------------------------------------------------------------
# Spec §3 assertion 3 — integrity payload carries nudge_excised
# ---------------------------------------------------------------------------


def test_inject_arm_fields_sets_nudge_excised_true_for_l4_without_nudge():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="l4_without_nudge",
        runner_git_commit="commit-sha",
    )
    assert new["fields"]["nudge_excised"] is True
    # And the L3-arm letter is None — this is not an L3 arm.
    assert new["fields"]["l3_arm"] is None


def test_inject_arm_fields_sets_nudge_excised_false_for_l4_with_nudge():
    new = inject_arm_fields(
        {"fields": {}},
        arm_name="l4_with_nudge",
        runner_git_commit="commit-sha",
    )
    assert new["fields"]["nudge_excised"] is False


def test_arm_profile_for_l4_without_nudge_marks_nudge_excised():
    assert ARM_PROFILES["l4_without_nudge"].nudge_excised is True


def test_arm_profile_for_l4_with_nudge_does_not_mark_nudge_excised():
    assert ARM_PROFILES["l4_with_nudge"].nudge_excised is False


# ---------------------------------------------------------------------------
# Registration — the handler overrides the placeholder
# ---------------------------------------------------------------------------


def test_l4_without_nudge_handler_replaces_placeholder():
    """Importing ``arm_handlers`` (done at module top) wires the real
    handler into ``arms.HANDLERS`` via the ``@register`` decorator.
    The handler we see should produce a non-stub prompt — i.e. it
    contains the policy-independence sentence and the rendered policy
    JSON, not the placeholder's ``[arm:l4_without_nudge]`` marker."""
    record = {"ocid": "test-ocid", "decision_type": "procurement_decision"}
    prompt = HANDLERS["l4_without_nudge"](record)
    assert INDEPENDENCE_SENTENCE in prompt
    assert "[arm:l4_without_nudge]" not in prompt


def test_l4_with_nudge_handler_replaces_placeholder():
    record = {"ocid": "test-ocid", "decision_type": "procurement_decision"}
    prompt = HANDLERS["l4_with_nudge"](record)
    assert INDEPENDENCE_SENTENCE in prompt
    assert "If a rule cannot be confidently evaluated" in prompt
    assert "[arm:l4_with_nudge]" not in prompt


# ---------------------------------------------------------------------------
# End-to-end through the stub runner — receipt integrity payload check
# ---------------------------------------------------------------------------


def test_stub_signer_binds_nudge_excised_true_for_l4_without_nudge_arm(tmp_path: Path):
    """End-to-end: dispatch a record through the runner against the
    L4-without-nudge handler with the stub client. The captured
    integrity-hash payload must carry ``nudge_excised: true`` so a
    verifier downstream can attribute the receipt to the no-nudge
    condition."""
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="test-l4-without-nudge",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run",
        arm_name="l4_without_nudge",
        policy_snapshot_path=None,
    )
    summary = run_arm(
        config=config,
        records=[
            {"ocid": "stub-ocid-001", "decision_type": "procurement_decision"}
        ],
        agent=StubAgent(),
        meshqu_client=client,
    )
    assert len(summary.outcomes) == 1
    captured = client.captured_field_payloads[0]
    assert captured["nudge_excised"] is True
    # Sanity: model_id is the primary, not Claude — this is not the
    # cross-model diagnostic arm.
    assert captured["model_id"] == "gpt-5.4-2026-03-05"


def test_stub_signer_binds_nudge_excised_false_for_l4_with_nudge_arm(tmp_path: Path):
    """Counterpart — the l4_with_nudge sanity-comparison arm must
    NOT mark nudge_excised. Otherwise the two arms' receipts would be
    indistinguishable at audit time."""
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="test-l4-with-nudge",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run",
        arm_name="l4_with_nudge",
        policy_snapshot_path=None,
    )
    run_arm(
        config=config,
        records=[
            {"ocid": "stub-ocid-001", "decision_type": "procurement_decision"}
        ],
        agent=StubAgent(),
        meshqu_client=client,
    )
    captured = client.captured_field_payloads[0]
    assert captured["nudge_excised"] is False


def test_two_arms_produce_different_integrity_hashes(tmp_path: Path):
    """Cryptographic distinguishability — the receipts MUST hash to
    different integrity_hashes. Otherwise the nudge_excised flag is
    not actually binding into the integrity hash and the two
    conditions are indistinguishable at the wire."""
    captured_hashes: dict[str, str] = {}
    for arm in ("l4_with_nudge", "l4_without_nudge"):
        client = StubMeshQuClient()
        config = RunConfig(
            run_id=f"test-distinguish-{arm}",
            run_phase="dry-run",
            repo_dir=tmp_path,
            run_dir=tmp_path / f"run-{arm}",
            arm_name=arm,
            policy_snapshot_path=None,
        )
        summary = run_arm(
            config=config,
            records=[
                {"ocid": "stub-ocid-001", "decision_type": "procurement_decision"}
            ],
            agent=StubAgent(),
            meshqu_client=client,
        )
        captured_hashes[arm] = summary.outcomes[0].receipt.integrity_hash
    assert captured_hashes["l4_with_nudge"] != captured_hashes["l4_without_nudge"]


# ---------------------------------------------------------------------------
# Drift guard — the locked file SHA must match what v0.3 bound
# ---------------------------------------------------------------------------


LOCKED_L4_WITHOUT_NUDGE_SHA256 = (
    "4152247fabc0553e9b28c6204b3c82eddf51e87875e29669e7967b9f6da42cdb"
)
"""SHA-256 of ``L4_without_nudge.md`` as bound by the
``v0.3-predictions-locked`` git tag. The L4-without-nudge arm refuses
to render against a different file — drift would make the comparison
incoherent."""

LOCKED_L4_POLICY_ENVELOPE_SHA256 = (
    "c90664f473c19b7482b9bb81f0bf546392819dd7bfb6f47bcb369ac713ac0b2d"
)
"""SHA-256 of E2's ``L4_policy_envelope.md`` (same file the locked
header inside L4_without_nudge.md references)."""


def test_locked_l4_without_nudge_sha256_matches_prereg():
    assert _sha256_file(DEFAULT_ENVELOPE_PATH) == LOCKED_L4_WITHOUT_NUDGE_SHA256


def test_locked_e2_l4_policy_envelope_sha256_matches_prereg():
    assert _sha256_file(DEFAULT_L4_WITH_NUDGE_PATH) == LOCKED_L4_POLICY_ENVELOPE_SHA256


# ---------------------------------------------------------------------------
# Smoke: rendered prompt contains the policy snapshot (interpolation worked)
# ---------------------------------------------------------------------------


def test_rendered_prompt_contains_interpolated_policy_json():
    rendered = render_l4_without_nudge()
    # The placeholder token must be gone (replaced by JSON)
    assert "{policy_snapshot_json}" not in rendered
    # And a recognisable fragment of the policy snapshot must appear.
    policy = json.loads(DEFAULT_POLICY_SNAPSHOT_PATH.read_text())
    # The locked snapshot has a top-level "snapshot_id" of cbf12348… —
    # pull the literal substring out of the JSON dict to check
    # interpolation rather than guessing structure.
    assert "cbf12348" in rendered, (
        "expected the policy snapshot ID (cbf12348-…) to appear in the "
        "rendered prompt — interpolation may have failed."
    )
    # And the snapshot's keys (e.g. "rules") should appear too.
    for key in policy.keys():
        assert f'"{key}"' in rendered, (
            f"expected policy key {key!r} to appear in rendered JSON"
        )
