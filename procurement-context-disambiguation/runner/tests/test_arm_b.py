"""E3-003 Arm B handler tests — the contamination check is load-bearing.

Arm B's job is to render the same nearest-neighbour precedents Arm A
would render, but with the verdict signal redacted. If verdict
substrings (``"ALLOW"`` / ``"REVIEW"`` / ``"DENY"``), the word
``violation``, or substrings of any E1 agent reasoning text leak into
the rendered output, the arm is contaminated and the A−B contrast
measures nothing.

These tests are the empirical guarantee that the redaction holds. They
run against:

  - A small synthetic archive (so the tests are hermetic — no
    dependence on the 283-record frozen archive being extracted on the
    test runner).
  - Synthetic target records whose feature vectors trigger known
    nearest neighbours, so we can prove "same kNN as Arm A" without
    needing to import or duplicate the Arm A handler (which lives in a
    sibling worktree this redispatch can't see).

All contamination assertions run on the **post-strip rendered output**
— the bytes the LLM would actually receive after the Wave 2
HTML-comment-strip transform. That's the surface that matters for
"did verdict signal leak into the prompt the model saw".
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from meshqu_runner import arms
from meshqu_runner.arms.arm_b import (
    ARM_B_ALLOWED_FIELDS,
    ARM_B_REDACTED_FIELDS,
    ARM_B_SECTION_HEADER,
    ARM_B_TEMPLATE_PATH,
    arm_b_handler,
    load_arm_b_template,
    project_precedent_fields,
    render_precedents_redacted,
    strip_leading_html_comment,
)
from meshqu_runner.precedent_archive import PrecedentRecord
from meshqu_runner.precedent_selector import select_precedents


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# Three verdict strings that MUST NOT appear (case-sensitive AND
# case-insensitive — the package spec calls these literal). Cased
# variants too because the precedent records carry "DENY" / "REVIEW"
# verbatim from the archive.
VERDICT_TOKENS: tuple[str, ...] = ("ALLOW", "DENY", "REVIEW")


def _make_precedent(
    *,
    ocid: str,
    decision_id: str,
    contract_value: float,
    governed_by_pa23: str,
    procurement_method_open_flag: str | None,
    verdict: str,
    violations: tuple[str, ...] = (),
    reasoning: str = "(synthetic reasoning text)",
    recommended_action: str | None = None,
    publication_delay_days: int | None = 14,
    award_date: str = "2025-06-01",
) -> PrecedentRecord:
    """Build a synthetic ``PrecedentRecord``. The defaults give a clean
    'PA23, method-open, mid-band' record; tests override what matters."""
    return PrecedentRecord(
        ocid=ocid,
        decision_id=decision_id,
        award_date=award_date,
        contract_value=contract_value,
        governed_by_pa23=governed_by_pa23,
        procurement_method_open_flag=procurement_method_open_flag,
        publication_delay_days=publication_delay_days,
        meshqu_verdict=verdict,
        violations=violations,
        agent_reasoning=reasoning,
        agent_recommended_action=recommended_action,
    )


@pytest.fixture
def synthetic_archive() -> dict[str, PrecedentRecord]:
    """A 6-record archive seeded with VERDICT signal and verdict-laden
    reasoning text. The whole point of Arm B is that NONE of this leaks
    into the rendered output even though it's all present in the
    PrecedentRecords.

    Records 01..04 are crafted to be the nearest neighbours of the
    target record (same regime, same value band, same method flag).
    Records 05 + 06 differ on regime or value band so they sort later
    under the kNN tie-break — they exist to prove the selector is
    being exercised, not bypassed.
    """
    return {
        "ocds-test-001": _make_precedent(
            ocid="ocds-test-001",
            decision_id="decision-001",
            contract_value=800_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="DENY",
            violations=("DUP-001", "DUP-002"),
            reasoning=(
                "DENY-worthy: the procurement record indicates a serious "
                "violation of PA23 §16 because publication delay was 41 days."
            ),
            recommended_action="block contract execution",
        ),
        "ocds-test-002": _make_precedent(
            ocid="ocds-test-002",
            decision_id="decision-002",
            contract_value=850_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="REVIEW",
            violations=("DUP-001",),
            reasoning="REVIEW-warranted because evidence is ambiguous on supplier identity.",
        ),
        "ocds-test-003": _make_precedent(
            ocid="ocds-test-003",
            decision_id="decision-003",
            contract_value=900_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="DENY",
            violations=("RULE-X",),
            reasoning="Material breach justifies DENY; the precedent makes it clear.",
        ),
        "ocds-test-004": _make_precedent(
            ocid="ocds-test-004",
            decision_id="decision-004",
            contract_value=950_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="ALLOW",
            violations=(),
            reasoning="No violation found; ALLOW is appropriate per §3.",
        ),
        # Different regime → distance 1
        "ocds-test-005": _make_precedent(
            ocid="ocds-test-005",
            decision_id="decision-005",
            contract_value=800_000,
            governed_by_pa23="false",
            procurement_method_open_flag="true",
            verdict="DENY",
            violations=("PCR-2015-99",),
            reasoning="Under PCR_2015 this was a clear DENY.",
        ),
        # Different value band → distance 1
        "ocds-test-006": _make_precedent(
            ocid="ocds-test-006",
            decision_id="decision-006",
            contract_value=20_000_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="REVIEW",
            violations=(),
            reasoning="REVIEW per high-value escalation; verdict-laden text.",
        ),
    }


@pytest.fixture
def target_record() -> dict[str, Any]:
    """A target whose feature vector triggers ocds-test-001..004 as the
    4 nearest neighbours (all distance 0; OCID-ascending tie-break)."""
    return {
        "ocid": "ocds-test-target",
        "decision_type": "procurement_decision",
        "fields": {
            "contract_value": 875_000,
            "governed_by_pa23": "true",
            "procurement_method_open_flag": "true",
            "publication_delay_days": 14,
        },
        "substrate_notes": {},
        "metadata": {"ocid": "ocds-test-target"},
    }


@pytest.fixture
def three_smoke_records() -> list[dict[str, Any]]:
    """Three smoke records — same shape as the live smoke fixture.
    Used to assert "same OCIDs as Arm A would select" across more than
    one target."""
    return [
        {
            "ocid": "smoke-001-pa23-mid",
            "decision_type": "procurement_decision",
            "fields": {
                "contract_value": 875_000,
                "governed_by_pa23": "true",
                "procurement_method_open_flag": "true",
                "publication_delay_days": 14,
            },
            "substrate_notes": {},
            "metadata": {"ocid": "smoke-001-pa23-mid"},
        },
        {
            "ocid": "smoke-002-pcr-mid",
            "decision_type": "procurement_decision",
            "fields": {
                "contract_value": 850_000,
                "governed_by_pa23": "false",
                "procurement_method_open_flag": "true",
                "publication_delay_days": 41,
            },
            "substrate_notes": {},
            "metadata": {"ocid": "smoke-002-pcr-mid"},
        },
        {
            "ocid": "smoke-003-pa23-high",
            "decision_type": "procurement_decision",
            "fields": {
                "contract_value": 22_000_000,
                "governed_by_pa23": "true",
                "procurement_method_open_flag": "true",
                "publication_delay_days": 7,
            },
            "substrate_notes": {},
            "metadata": {"ocid": "smoke-003-pa23-high"},
        },
    ]


# ---------------------------------------------------------------------------
# §1 — Handler registration
# ---------------------------------------------------------------------------


def test_arm_b_handler_registered_in_arms_handlers():
    """Importing ``meshqu_runner.arms.arm_b`` (which the package
    ``__init__`` does at import time) overwrites the foundation
    placeholder at ``arms.HANDLERS["arm_b"]`` with the real handler."""
    assert arms.HANDLERS["arm_b"] is arm_b_handler


def test_arm_b_profile_carries_l3_arm_letter_B():
    """Arm B's integrity-payload profile must carry ``l3_arm: "B"``.
    This is set by the E3-001 foundation; we re-assert here so a
    regression in either layer surfaces in the Arm B PR's test suite."""
    profile = arms.ARM_PROFILES["arm_b"]
    assert profile.l3_arm == "B"
    assert profile.nudge_excised is False
    assert profile.diagnostic is False
    assert profile.model_id == "gpt-5.4-2026-03-05"


# ---------------------------------------------------------------------------
# §2 — Locked template (READ-ONLY) — preflight checks
# ---------------------------------------------------------------------------


def test_arm_b_template_file_exists():
    """The handler resolves the template path lazily; this test asserts
    the locked file actually lives where the design says it does."""
    assert ARM_B_TEMPLATE_PATH.is_file(), (
        f"Locked Arm B template missing at {ARM_B_TEMPLATE_PATH}. "
        "STOP condition (build-package spec)."
    )


def test_arm_b_template_does_not_reference_redacted_fields():
    """The locked template body MUST NOT carry ``{meshqu_verdict}`` /
    ``{violations}`` / ``{e1_agent_reasoning_text}`` placeholders.

    If it did, ``str.format_map`` against the Arm B projection (which
    omits these keys) would raise ``KeyError`` at first render. We
    assert at the bytes level too so the contract is doubly enforced."""
    template = load_arm_b_template()
    for redacted in ARM_B_REDACTED_FIELDS:
        assert f"{{{redacted}}}" not in template, (
            f"Locked Arm B template references {{{redacted}}} — "
            "redaction is broken at the bytes level. STOP."
        )


# ---------------------------------------------------------------------------
# §3 — HTML-comment strip (Wave 2 convention)
# ---------------------------------------------------------------------------


def test_strip_leading_html_comment_removes_single_block():
    """The strip function pulls out the FIRST leading HTML comment."""
    sample = "<!-- header -->\n\nbody"
    post, stripped = strip_leading_html_comment(sample)
    assert post.strip() == "body"
    assert stripped is not None
    assert "header" in stripped


def test_strip_leading_html_comment_idempotent_when_none_present():
    """When the template has no leading HTML comment, the function is
    a no-op and ``stripped_comment`` is ``None``."""
    sample = "## body text only\n"
    post, stripped = strip_leading_html_comment(sample)
    assert post == sample
    assert stripped is None


def test_strip_leading_html_comment_handles_multi_line():
    """The Wave 2 convention is that locked files MAY carry multi-line
    comment headers documenting the surgical change. The strip must
    cover the entire block including newlines."""
    sample = "<!--\nMulti\nline\ncomment\n-->\n\nactual content"
    post, _ = strip_leading_html_comment(sample)
    assert "Multi" not in post
    assert "actual content" in post.strip()


def test_locked_template_has_leading_html_comment_per_wave2_convention():
    """The locked Arm B file is known (at lock time) to carry an HTML
    comment header documenting that it's the redacted variant of E2's
    L3 template. This test pins that convention — if a future amendment
    elides the header, the strip becomes a no-op and the test still
    passes (because the strip is idempotent when no comment is present),
    so this assertion is what catches the regression in the other
    direction (header *unexpectedly* introduced post-strip-removal)."""
    template = load_arm_b_template()
    _, stripped = strip_leading_html_comment(template)
    # The locked file SHOULD carry the leading comment at v0.3.
    assert stripped is not None, (
        "Locked Arm B template no longer carries its leading HTML "
        "comment header. Either the lock was amended (update this "
        "test) or the strip is being applied to the wrong file."
    )


def test_locked_template_bytes_not_mutated_on_render():
    """The on-disk locked template MUST NOT change as a side effect of
    rendering. Compute the SHA before + after a render call and assert
    equality."""
    sha_before = hashlib.sha256(ARM_B_TEMPLATE_PATH.read_bytes()).hexdigest()
    # Drive a full render against a tiny precedent set.
    precedents = [
        _make_precedent(
            ocid="ocds-x-001",
            decision_id="d-001",
            contract_value=500_000,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            verdict="REVIEW",
            reasoning="text",
        )
    ]
    template = load_arm_b_template()
    _ = render_precedents_redacted(template, precedents)
    sha_after = hashlib.sha256(ARM_B_TEMPLATE_PATH.read_bytes()).hexdigest()
    assert sha_before == sha_after, (
        "Rendering Arm B mutated the locked template file. "
        "The render path is required to be read-only."
    )


# ---------------------------------------------------------------------------
# §4 — Field projection (defence in depth)
# ---------------------------------------------------------------------------


def test_projection_only_carries_allowed_fields():
    """``project_precedent_fields`` projects each PrecedentRecord onto
    the Arm B allowed surface — every key in the result is in
    ``ARM_B_ALLOWED_FIELDS``, and EVERY redacted-field name is absent
    from the dict's keys."""
    precedent = _make_precedent(
        ocid="ocds-proj-001",
        decision_id="dproj-001",
        contract_value=1_234_000,
        governed_by_pa23="true",
        procurement_method_open_flag="true",
        verdict="DENY",
        violations=("V-001",),
        reasoning="explosive DENY reasoning",
        recommended_action="block",
    )
    projection = project_precedent_fields(precedent, n=7)
    assert set(projection.keys()).issubset(ARM_B_ALLOWED_FIELDS)
    for redacted in ARM_B_REDACTED_FIELDS:
        assert redacted not in projection


def test_projection_preserves_concrete_fields():
    """The projection carries OCID, value, dates, regime, method flag,
    delay — the fields the Arm B template references. Spot-check each."""
    precedent = _make_precedent(
        ocid="ocds-proj-002",
        decision_id="dproj-002",
        contract_value=2_500_000,
        governed_by_pa23="true",
        procurement_method_open_flag=None,
        verdict="DENY",
        reasoning="text",
        publication_delay_days=21,
        award_date="2025-09-15",
    )
    p = project_precedent_fields(precedent, n=3)
    assert p["ocid"] == "ocds-proj-002"
    assert p["contract_value"] == 2_500_000
    assert p["contract_value_formatted"] == "£2,500,000"
    assert p["award_date"] == "2025-09-15"
    assert p["regime_proxy"] == "PA23"
    assert p["procurement_method_open_flag"] == "(absent in source record)"
    assert p["publication_delay_days"] == 21
    assert p["n"] == 3


def test_projection_method_flag_passthrough_when_present():
    p = project_precedent_fields(
        _make_precedent(
            ocid="x",
            decision_id="d",
            contract_value=100_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="ALLOW",
        ),
        n=1,
    )
    assert p["procurement_method_open_flag"] == "true"


def test_projection_publication_delay_none_becomes_na():
    p = project_precedent_fields(
        _make_precedent(
            ocid="x",
            decision_id="d",
            contract_value=100_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="ALLOW",
            publication_delay_days=None,
        ),
        n=1,
    )
    assert p["publication_delay_days"] == "n/a"


# ---------------------------------------------------------------------------
# §5 — Selector parity vs "what Arm A would pick"
# ---------------------------------------------------------------------------


def test_arm_b_uses_same_selector_as_arm_a_for_smoke_records(
    synthetic_archive, three_smoke_records
):
    """The package spec: "same kNN as Arm A". We don't have Arm A's
    handler in this worktree (sibling agent E3-002), but Arm B feeds the
    SAME precedent_selector with the SAME archive — so the OCIDs Arm B
    would render MUST match the OCIDs select_precedents returns directly.

    This is the structural guarantee: as long as Arm B doesn't filter,
    re-sort, or rewrite the selector output, the kNN parity holds by
    construction. The test asserts the construction is honoured."""
    for record in three_smoke_records:
        from_selector = select_precedents(record, synthetic_archive, k=4)
        # Drive the handler with the same archive; capture which OCIDs
        # ended up in the rendered output via the projection helper.
        rendered = arm_b_handler(record, archive=synthetic_archive, k=4)
        for precedent in from_selector:
            assert precedent.ocid in rendered, (
                f"Arm B failed to render precedent {precedent.ocid} for "
                f"target {record['ocid']} — the selector picked it, but "
                f"the rendered output omitted it."
            )


def test_arm_b_renders_exactly_k_precedents(synthetic_archive, target_record):
    """k=4 and an archive with 4+ matching candidates ⇒ exactly 4
    rendered precedent blocks. The block headers ``## Precedent 1`` /
    ``## Precedent 2`` etc. are the visible marker we count against."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    block_headers = [
        line for line in rendered.splitlines()
        if line.startswith("## Precedent ") and "comparable record" in line
    ]
    assert len(block_headers) == 4
    # 1-indexed numbering
    for i, h in enumerate(block_headers, start=1):
        assert f"## Precedent {i}:" in h


def test_arm_b_is_deterministic_same_inputs_same_output(
    synthetic_archive, target_record
):
    """The package spec: "Deterministic: same target + archive → same
    prompt every time." Drive the handler twice; assert byte-equal."""
    one = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    two = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    assert one == two


# ---------------------------------------------------------------------------
# §6 — Contamination check — the load-bearing assertions
# ---------------------------------------------------------------------------


def test_no_verdict_tokens_in_rendered_arm_b(synthetic_archive, target_record):
    """The synthetic archive's precedents carry verdict strings ALLOW,
    REVIEW, DENY in their ``meshqu_verdict`` field. After Arm B renders
    them, NONE of those tokens may appear in the rendered output.

    Case-insensitive matching to catch "Deny" / "deny" too — the
    archive's verdicts are upper-case by E1 convention, but the lower-
    case check is defence-in-depth against future archive case drift.
    """
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    lowered = rendered.lower()
    for token in VERDICT_TOKENS:
        assert token.lower() not in lowered, (
            f"Verdict token {token!r} leaked into Arm B rendered output."
        )


def test_no_violation_word_in_rendered_arm_b(synthetic_archive, target_record):
    """The literal substring ``violation`` (case-insensitive) must not
    appear in the rendered Arm B output. The synthetic archive seeds
    precedent reasoning text with the word — if the redaction is real,
    none of it survives projection."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    assert "violation" not in rendered.lower()


def test_no_e1_reasoning_substrings_in_rendered_arm_b(
    synthetic_archive, target_record
):
    """For each precedent that the selector picks, take the first 50
    characters of its ``agent_reasoning`` (an unforgeable substring
    drawn directly from the source) and assert it does NOT appear in
    the rendered output.

    This is the substring contamination check the package spec calls
    out. Lower-case substring match (the build package: "Lower-case
    substring match is the right contamination check ... Don't get
    fancy with regex.")."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    lowered = rendered.lower()
    selected = select_precedents(target_record, synthetic_archive, k=4)
    assert len(selected) > 0
    for precedent in selected:
        head = precedent.agent_reasoning[:50].lower().strip()
        assert head, (
            f"Test setup error: precedent {precedent.ocid} has no "
            "reasoning text for the contamination check to assert on."
        )
        assert head not in lowered, (
            f"Substring of {precedent.ocid}'s reasoning leaked into "
            f"Arm B rendered output. Leaked head: {head!r}"
        )


def test_no_recommended_action_in_rendered_arm_b(synthetic_archive, target_record):
    """The MeshQu ``recommended_action`` (E1's ``agent_recommended_action``
    field) must not appear in the rendered output. The synthetic
    archive's record-001 carries ``recommended_action="block contract
    execution"`` — assert that string is absent."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    assert "block contract execution" not in rendered.lower()
    # And the field name itself shouldn't appear either.
    assert "recommended_action" not in rendered
    assert "recommended action" not in rendered.lower()


def test_contamination_check_runs_on_post_strip_output(
    synthetic_archive, target_record
):
    """The Wave 2 convention says: run the contamination check on the
    POST-STRIP rendered output (the LLM-effective bytes), not on the
    raw template file. We assert this by:

      1. Re-asserting the locked template carries a leading HTML
         comment (already tested above).
      2. Asserting the comment's content is NOT in the rendered
         output. If we ran the contamination check pre-strip and the
         comment carried e.g. the word "violation" or "DENY", we'd
         miss a real leak hiding behind a stripped comment.
    """
    template = load_arm_b_template()
    _, stripped_comment = strip_leading_html_comment(template)
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)

    assert stripped_comment is not None
    # Pick a stable token from the comment that wouldn't otherwise be
    # in the rendered output. The locked comment text mentions the
    # E2 SHA prefix; assert that doesn't surface post-strip.
    if "L3_precedent_block_format.md" in stripped_comment:
        assert "L3_precedent_block_format.md" not in rendered
    # The comment explains the redaction; check at least one of its
    # signal phrases doesn't appear post-strip.
    for marker in (
        "verdict-signal",
        "REDACTED",
        "verdict-exemplar",
        "governance-memory",
    ):
        if marker in stripped_comment:
            assert marker not in rendered, (
                f"Stripped-comment marker {marker!r} leaked into rendered output."
            )


# ---------------------------------------------------------------------------
# §7 — Concrete fields the template DOES carry, do survive
# ---------------------------------------------------------------------------


def test_arm_b_rendered_output_contains_section_header(
    synthetic_archive, target_record
):
    """Arm B uses the same ``## Precedents from MRP-2026-02`` section
    header E2's L3 used."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    assert ARM_B_SECTION_HEADER in rendered


def test_arm_b_rendered_output_contains_concrete_case_fields(
    synthetic_archive, target_record
):
    """The concrete-but-non-verdict fields the template references
    SHOULD appear: OCID, formatted contract value, award date, regime,
    method flag, publication delay. Spot-check one of each."""
    rendered = arm_b_handler(target_record, archive=synthetic_archive, k=4)
    # Selected precedents have OCIDs like ocds-test-001..004
    assert "ocds-test-001" in rendered
    # Formatted currency shows up
    assert "£" in rendered
    # Regime
    assert "PA23" in rendered
    # Award date format
    assert "2025-06-01" in rendered or "award date" in rendered.lower()


# ---------------------------------------------------------------------------
# §8 — Empty / sparse archive edge cases
# ---------------------------------------------------------------------------


def test_arm_b_returns_l0_baseline_only_when_archive_is_none(target_record):
    """The handler's ``archive=None`` path is the foundation-compatible
    behaviour: no precedents available ⇒ no precedent block. The
    rendered output is exactly the L0 baseline (the canonical-JSON
    user message E1/E2 sent the agent without any addendum). Used by
    the CLI's --dry mode."""
    rendered = arm_b_handler(target_record, archive=None)
    # No section header, no precedent block headers
    assert ARM_B_SECTION_HEADER not in rendered
    assert "## Precedent 1" not in rendered
    # But the baseline carries the decision_type and fields
    assert "procurement_decision" in rendered


def test_arm_b_returns_l0_baseline_only_when_archive_is_empty(target_record):
    rendered = arm_b_handler(target_record, archive={})
    assert ARM_B_SECTION_HEADER not in rendered


# ---------------------------------------------------------------------------
# §9 — KeyError if template references a non-allowed field (defence in depth)
# ---------------------------------------------------------------------------


def test_render_raises_keyerror_for_unauthorised_template_placeholder(
    synthetic_archive,
):
    """If a future amendment to the template introduces ``{meshqu_verdict}``
    (a redacted-field reference), the renderer MUST raise rather than
    silently producing an empty or wrong field. ``str.format_map``
    against the Arm B projection (which omits the field) raises
    ``KeyError`` — assert that surfaces."""
    bad_template = (
        "## Precedent {n}\n\n"
        "- OCID: {ocid}\n"
        "- Verdict: {meshqu_verdict}\n"  # ← redacted field
    )
    precedents = [
        _make_precedent(
            ocid="x",
            decision_id="d",
            contract_value=100_000,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            verdict="DENY",
        )
    ]
    with pytest.raises(KeyError):
        render_precedents_redacted(bad_template, precedents)


def test_load_arm_b_template_raises_if_file_missing(tmp_path: Path):
    """The package spec's stop condition: template file missing ⇒
    surface, don't synthesise. ``load_arm_b_template`` raises
    ``FileNotFoundError`` so the caller sees a clean stop."""
    missing = tmp_path / "does-not-exist.md"
    with pytest.raises(FileNotFoundError):
        load_arm_b_template(path=missing)
