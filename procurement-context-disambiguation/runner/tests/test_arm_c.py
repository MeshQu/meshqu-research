"""E3-004 — Arm C handler tests.

Mirrors the §4 contract in
``planning/build_packages/e3-004-arm-c-density-control.md``:

1. The HTML neutrality-contract comment is stripped from the rendered
   output (substring check).
2. The four ``## Reference N:`` sections appear in the rendered output.
3. Token-parity check: on a 10-record deterministic sample, the mean
   Arm C / Arm A token-count ratio is within ``[0.95, 1.05]``. If the
   parity is bad, the test FAILS and the PR body documents the gap
   (this is decision point 3 in the master plan; failure is by design,
   not a defect).
4. No live model call (tokenizer is local; no Arm A handler import).
5. The receipt payload sets ``l3_arm: "C"``.

The parity test depends on a precedent archive. The canonical frozen
E1 archive lives at
``procurement-decisions/results/runs/dry-run-7ddf7274-…/`` — it is
locally present in development checkouts but not git-tracked. The
``ParityArchive`` fixture below tries the canonical path first; if
absent, the parity test SKIPS with a clear message. This keeps CI
green when the archive isn't around (e.g. cold clone) while still
running the substantive parity check locally and in any environment
where the archive is staged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from meshqu_runner import arms
from meshqu_runner.arms import arm_c
from meshqu_runner.arms.arm_c import (
    ARM_C_SECTION_HEADER,
    ARM_C_TEMPLATE_RELATIVE_PATH,
    DEFAULT_PARITY_SAMPLE_SIZE,
    ParityRecord,
    ParityReport,
    deterministic_sample,
    load_locked_arm_c_template,
    measure_token_parity,
    render_arm_c_block,
    render_arm_c_prompt,
    strip_leading_html_comment_block,
)
from meshqu_runner.arms import ARM_PROFILES, HANDLERS
from meshqu_runner.multi_pass import (
    RunConfig,
    StubAgent,
    StubMeshQuClient,
    run_arm,
)


# ---------------------------------------------------------------------------
# Filesystem anchors
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent.parent
"""``procurement-context-disambiguation/runner/`` — anchor for the
locked template + the prompts subtree."""

E3_DIR = RUNNER_DIR.parent
REPO_DIR = E3_DIR.parent

LOCKED_TEMPLATE_PATH = RUNNER_DIR / ARM_C_TEMPLATE_RELATIVE_PATH

# The canonical frozen E1 archive — used as the precedent source when
# rendering an L3-shape Arm A prompt for the parity comparison. The
# directory is locally present in dev checkouts but not git-tracked, so
# parity tests SKIP if absent (see module docstring).
#
# Two paths are probed: the current REPO_DIR (a normal checkout) and the
# ``PROCUREMENT_ARCHIVE_DIR`` env var (Wave 2 dispatch in a git worktree
# clones only tracked files — the worktree itself does not carry the
# archive, but the user can point a test run at the host checkout).
import os as _os

_ARCHIVE_RELATIVE_SUBPATH = (
    Path("procurement-decisions")
    / "results"
    / "runs"
    / "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
)


def _resolve_frozen_archive_path() -> Path | None:
    """Return the first frozen-archive path that exists, or None."""
    candidates = [REPO_DIR / _ARCHIVE_RELATIVE_SUBPATH]
    env_root = _os.environ.get("PROCUREMENT_ARCHIVE_REPO_DIR")
    if env_root:
        candidates.append(Path(env_root) / _ARCHIVE_RELATIVE_SUBPATH)
    for cand in candidates:
        if cand.is_dir():
            return cand
    return None


def _resolve_e2_l3_template_path() -> Path | None:
    """Return the first E2 L3 template path that exists, or None."""
    candidates = [
        REPO_DIR
        / "procurement-context-gradient"
        / "runner"
        / "prompts"
        / "L3_precedent_block_format.md"
    ]
    env_root = _os.environ.get("PROCUREMENT_ARCHIVE_REPO_DIR")
    if env_root:
        candidates.append(
            Path(env_root)
            / "procurement-context-gradient"
            / "runner"
            / "prompts"
            / "L3_precedent_block_format.md"
        )
    for cand in candidates:
        if cand.is_file():
            return cand
    return None

# Locked SHA-256 of ``armC_density_control.md`` at v0.3-predictions-locked.
# The test compares against this to verify Wave 2 dispatch hasn't drifted
# the file. Recompute on disk and assert byte-identity.
LOCKED_ARM_C_TEMPLATE_SHA256 = (
    "07abb32fc97418d2fc327c7db235b73ab3d9ae67ec7842ff609fdfd0c1824134"
)


# ---------------------------------------------------------------------------
# Locked-content invariants
# ---------------------------------------------------------------------------


def test_locked_template_file_exists():
    """The locked file must exist where ``load_locked_arm_c_template``
    expects it. Absence is the package-spec stop condition."""
    assert LOCKED_TEMPLATE_PATH.is_file(), (
        f"Locked Arm C template missing at {LOCKED_TEMPLATE_PATH}. "
        "v0.3-predictions-locked SHA contract broken."
    )


def test_locked_template_sha256_matches_v03_tag():
    """SHA-256 of the on-disk locked file must match the
    v0.3-predictions-locked-bound hash. Any drift means the file has
    been mutated (or the tag has been rewritten) and Arm C's
    neutrality-reviewed content is no longer the content under test."""
    actual = hashlib.sha256(LOCKED_TEMPLATE_PATH.read_bytes()).hexdigest()
    assert actual == LOCKED_ARM_C_TEMPLATE_SHA256, (
        f"Locked Arm C template SHA drift: expected "
        f"{LOCKED_ARM_C_TEMPLATE_SHA256!r}, got {actual!r}. "
        "The file is bound by v0.3-predictions-locked and must not change."
    )


# ---------------------------------------------------------------------------
# HTML-comment strip (§4 test 1)
# ---------------------------------------------------------------------------


def test_strip_leading_html_comment_removes_authoring_metadata():
    """Locked file starts with ``<!--`` … ``-->``; the strip removes it.
    Sanity-check by feeding the real on-disk content."""
    raw = load_locked_arm_c_template(LOCKED_TEMPLATE_PATH)
    assert raw.lstrip().startswith("<!--"), (
        "Locked Arm C template no longer starts with an HTML comment. "
        "Either the file was edited (SHA test will also fire) or the "
        "strip-convention is no longer needed for this file."
    )
    stripped = strip_leading_html_comment_block(raw)
    # The neutrality-contract metadata in the leading comment includes
    # phrases we can probe for. None of them must survive the strip.
    assert "Neutrality contract" not in stripped
    assert "LOCKED CONTENT" not in stripped
    assert "<!--" not in stripped[:10], (
        "Leading HTML comment survived the strip — the model would "
        "see authoring metadata it has no business seeing."
    )


def test_strip_leading_html_comment_is_noop_on_clean_input():
    """If the locked file is ever re-saved without the leading
    inspector comment (or a test feeds a clean string), the strip
    must return the string unchanged."""
    clean = "## Reference 1: ...\n\nbody"
    assert strip_leading_html_comment_block(clean) == clean


def test_strip_leading_html_comment_only_strips_leading():
    """A buried HTML comment must NOT be removed — the strip is
    anchored to start-of-string by design."""
    with_buried = "## Reference 1: ...\n\n<!-- buried -->\n## Reference 2: ..."
    assert strip_leading_html_comment_block(with_buried) == with_buried


# ---------------------------------------------------------------------------
# Reference sections survive (§4 test 2)
# ---------------------------------------------------------------------------


def test_rendered_block_contains_all_four_reference_sections():
    """The four ``## Reference N: record-structure note`` headers must
    survive the strip. They are what gets rendered to the model."""
    block = render_arm_c_block(LOCKED_TEMPLATE_PATH)
    for n in (1, 2, 3, 4):
        assert f"## Reference {n}: record-structure note" in block, (
            f"Reference {n} section missing after strip"
        )


def test_rendered_block_carries_no_verdict_words():
    """Defence-in-depth: re-verifies Sam's pre-lock neutrality review
    (i) — no verdict / decision words. Catches any future mutation that
    silently introduces one (the SHA test fires first; this is the
    semantic backup)."""
    block = render_arm_c_block(LOCKED_TEMPLATE_PATH).lower()
    banned_verdicts = (
        " allow ",
        " review ",
        " deny ",
        " violation",
        " breach",
        " pass ",
        " fail ",
    )
    for word in banned_verdicts:
        assert word not in block, (
            f"Banned verdict word {word!r} appears in Arm C block — "
            "neutrality contract violated."
        )


def test_rendered_block_carries_no_high_alert_imperatives():
    """Defence-in-depth: re-verifies Sam's pre-lock neutrality review
    (ii) — no high-alert compliance imperatives."""
    block = render_arm_c_block(LOCKED_TEMPLATE_PATH).lower()
    banned_imperatives = (
        "must enforce",
        "material failure",
        "severe risk",
        "severe compliance",
        "non-compliance",
        "mandatory",
        "penalty",
    )
    for phrase in banned_imperatives:
        assert phrase not in block, (
            f"Banned compliance-alert phrase {phrase!r} appears in Arm C "
            "block — neutrality contract violated."
        )


# ---------------------------------------------------------------------------
# Handler registration + receipt payload (§4 test 5)
# ---------------------------------------------------------------------------


def test_handler_registered_against_arm_c():
    """Importing ``arm_c`` registers the live handler against
    ``HANDLERS['arm_c']``, overwriting the foundation's placeholder."""
    # The import happened at module load. Verify the entry exists and is
    # NOT the foundation placeholder (which would have a different
    # qualified name).
    assert "arm_c" in HANDLERS
    # The real handler is defined in arm_c.py — qualname check.
    handler = HANDLERS["arm_c"]
    qualname = f"{handler.__module__}.{handler.__name__}"
    assert qualname.endswith("arm_c.arm_c_handler") or qualname.endswith(
        ".arm_c_handler"
    ), f"Unexpected handler bound to arm_c: {qualname}"


def test_arm_c_profile_carries_l3_arm_c():
    """ARM_PROFILES['arm_c'].l3_arm must read ``'C'`` — the integrity
    payload's distinguishing marker for Arm C receipts."""
    profile = ARM_PROFILES["arm_c"]
    assert profile.l3_arm == "C"
    assert profile.nudge_excised is False
    assert profile.diagnostic is False


def test_arm_c_receipt_payload_sets_l3_arm_to_C(tmp_path: Path):
    """End-to-end: dispatch Arm C through ``run_arm`` and verify the
    captured integrity payload binds ``l3_arm: "C"`` (§4 test 5)."""
    client = StubMeshQuClient()
    config = RunConfig(
        run_id="arm-c-receipt-test",
        run_phase="dry-run",
        repo_dir=tmp_path,
        run_dir=tmp_path / "run",
        arm_name="arm_c",
        policy_snapshot_path=None,
    )
    summary = run_arm(
        config=config,
        records=[
            {
                "ocid": "stub-arm-c-001",
                "decision_type": "procurement_decision",
                "fields": {"contract_value": 100_000},
                "substrate_notes": {},
            }
        ],
        agent=StubAgent(),
        meshqu_client=client,
    )
    assert len(summary.outcomes) == 1
    captured = client.captured_field_payloads[0]
    assert captured["l3_arm"] == "C"
    assert captured["nudge_excised"] is False
    assert captured["diagnostic"] is False
    assert captured["model_id"] == "gpt-5.4-2026-03-05"
    # And the model received the locked block — verify the rendered
    # prompt the stub agent hashed contains the section header.
    # (StubAgent's reasoning carries the hash, not the message; we
    # re-render directly here to assert the wire shape.)
    rendered = render_arm_c_prompt(
        {
            "ocid": "stub-arm-c-001",
            "decision_type": "procurement_decision",
            "fields": {"contract_value": 100_000},
            "substrate_notes": {},
        }
    )
    assert ARM_C_SECTION_HEADER in rendered
    assert "## Reference 1:" in rendered
    assert "## Reference 4:" in rendered


def test_arm_c_handler_ignores_extra_kwargs():
    """The dispatcher may pass kwargs intended for Arms A/B (e.g.
    ``precedent_selector``). Arm C is static — it must accept and
    discard them rather than raising."""
    record = {
        "ocid": "stub",
        "decision_type": "procurement_decision",
        "fields": {},
        "substrate_notes": {},
    }
    out = arms.dispatch(
        "arm_c",
        record,
        precedent_selector="ignored",
        random_kwarg=42,
    )
    assert ARM_C_SECTION_HEADER in out


# ---------------------------------------------------------------------------
# L0 baseline composition
# ---------------------------------------------------------------------------


def test_rendered_prompt_includes_l0_baseline_canonical_json():
    """The L0 baseline (canonical-JSON of decision_type+fields+
    substrate_notes) must appear at the head of the prompt — the agent
    sees the target record first, the reference block second."""
    record = {
        "ocid": "stub-baseline-001",
        "decision_type": "procurement_decision",
        "fields": {"contract_value": 250_000, "governed_by_pa23": "true"},
        "substrate_notes": {},
    }
    out = render_arm_c_prompt(record)
    # The canonical JSON head should be a strict prefix terminated by
    # the section-header separator.
    head, sep, tail = out.partition(f"\n\n{ARM_C_SECTION_HEADER}\n\n")
    assert sep, "Section header separator missing — prompt malformed"
    assert head.startswith('{"decision_type":"procurement_decision"')
    assert '"contract_value":250000' in head
    assert tail.startswith("## Reference 1:")


# ---------------------------------------------------------------------------
# Deterministic sampling
# ---------------------------------------------------------------------------


def test_deterministic_sample_is_reproducible():
    """Same input list → same sample. Two calls must return identical
    OCID ordering."""
    records = [{"ocid": f"ocid-{i:03d}"} for i in range(50)]
    s1 = deterministic_sample(records, n=10)
    s2 = deterministic_sample(records, n=10)
    assert [r["ocid"] for r in s1] == [r["ocid"] for r in s2]
    assert len(s1) == 10


def test_deterministic_sample_independent_of_input_order():
    """Sampling sorts by ``sha256(ocid)`` — input order must not
    matter. Reverse the input and the sample must be unchanged."""
    records = [{"ocid": f"ocid-{i:03d}"} for i in range(50)]
    s_forward = deterministic_sample(records, n=10)
    s_reverse = deterministic_sample(list(reversed(records)), n=10)
    assert [r["ocid"] for r in s_forward] == [r["ocid"] for r in s_reverse]


# ---------------------------------------------------------------------------
# Parity report formatting
# ---------------------------------------------------------------------------


def test_parity_record_ratio_and_delta():
    r = ParityRecord(ocid="ocid-x", arm_a_tokens=1000, arm_c_tokens=950)
    assert r.ratio == pytest.approx(0.95)
    assert r.delta_pct == pytest.approx(-5.0)


def test_parity_report_aggregates_correctly():
    records = (
        ParityRecord(ocid="a", arm_a_tokens=100, arm_c_tokens=98),
        ParityRecord(ocid="b", arm_a_tokens=100, arm_c_tokens=102),
        ParityRecord(ocid="c", arm_a_tokens=100, arm_c_tokens=100),
    )
    report = ParityReport(records=records)
    assert report.mean_ratio == pytest.approx(1.0)
    assert report.min_ratio == pytest.approx(0.98)
    assert report.max_ratio == pytest.approx(1.02)
    assert report.within_design_band is True


def test_parity_report_markdown_table_renders():
    records = (
        ParityRecord(ocid="a", arm_a_tokens=100, arm_c_tokens=98),
        ParityRecord(ocid="b", arm_a_tokens=100, arm_c_tokens=102),
    )
    md = ParityReport(records=records).to_markdown_table()
    assert "| OCID |" in md
    assert "`a`" in md
    assert "`b`" in md
    assert "**Mean**" in md


# ---------------------------------------------------------------------------
# Token-parity check — the core (§4 test 3)
# ---------------------------------------------------------------------------


class _CharLenEncoder:
    """Fake tokenizer used by the unit-level parity test. ``encode``
    returns one element per character so token counts equal char
    counts — keeps the test independent of tiktoken while still
    exercising the parity arithmetic."""

    def encode(self, text: str) -> list[int]:
        return [0] * len(text)


def test_measure_token_parity_with_injected_renderer_and_tokenizer():
    """Unit-level parity test: inject a fake Arm A renderer and a
    char-length tokenizer to verify the helper's arithmetic without
    pulling in tiktoken OR the frozen archive."""

    def fake_arm_a(record):
        # A canned Arm A-shape rendering ~1000 chars long.
        return "X" * 1000

    records = [
        {"ocid": f"ocid-{i:03d}", "decision_type": "x", "fields": {}, "substrate_notes": {}}
        for i in range(3)
    ]
    report = measure_token_parity(
        records,
        render_arm_a_prompt=fake_arm_a,
        tokenizer=_CharLenEncoder(),
    )
    assert len(report.records) == 3
    # Each parity record carries arm_a_tokens=1000 and arm_c_tokens =
    # len(L0-canonical-json + "\n\n## Reference notes\n\n" + arm_c_stripped).
    # Concrete number depends on the locked block; just sanity-check
    # the shape.
    for rec in report.records:
        assert rec.arm_a_tokens == 1000
        assert rec.arm_c_tokens > 0


@pytest.fixture(scope="module")
def frozen_archive():
    """Load the canonical frozen E1 archive if available. Skips the
    parity test when absent — keeps CI green on cold clones. Honours
    the ``PROCUREMENT_ARCHIVE_REPO_DIR`` env var so a worktree run
    can point at the host's checkout."""
    archive_path = _resolve_frozen_archive_path()
    if archive_path is None:
        pytest.skip(
            "Frozen E1 archive not present. Set "
            "PROCUREMENT_ARCHIVE_REPO_DIR to the host-repo root to "
            "include it, or skip is by design (CI cold clones)."
        )
    from meshqu_runner.precedent_archive import load_frozen_archive

    return load_frozen_archive(archive_path)


@pytest.fixture(scope="module")
def l3_template_content():
    """E2's locked L3 template content. Skips if absent. Honours
    ``PROCUREMENT_ARCHIVE_REPO_DIR`` like ``frozen_archive``."""
    template_path = _resolve_e2_l3_template_path()
    if template_path is None:
        pytest.skip(
            "E2 L3 template not present. Set PROCUREMENT_ARCHIVE_REPO_DIR "
            "to the host-repo root to include it."
        )
    return template_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def full_corpus_records():
    """The 283-record corpus used as the target-record source for
    parity sampling."""
    fixture_path = (
        RUNNER_DIR / "tests" / "fixtures" / "full_corpus_records.json"
    )
    with fixture_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return data["records"]


def _build_arm_a_renderer(archive, l3_template):
    """Return a render function with the Arm A shape (L0 + L3
    addendum). Built here rather than imported from E3-002 because
    that PR is in flight in a sibling worktree."""
    from meshqu_runner.context_levels.level_l3 import L3LiveHandler
    from meshqu_runner.eval_loop import build_user_message

    class _StubPrompts:
        def get(self, level):
            class _P:
                content = ""

            return _P()

    handler = L3LiveHandler(archive=archive, template_content=l3_template)
    stub_prompts = _StubPrompts()

    def render(record: Mapping[str, Any]) -> str:
        ocid = record.get("ocid") or (
            record.get("metadata", {}).get("ocid")
            if isinstance(record.get("metadata"), dict)
            else None
        )
        # E2's compose_user_message prepends addenda to the base message
        # with a single \n separator (see level_handlers.compose_user_message:307).
        base_msg = build_user_message(
            context=record,
            substrate_notes=record.get("substrate_notes") or {},
        )
        addendum = handler.build_addendum(
            record=record, ocid=ocid, prompts=stub_prompts
        )
        if not addendum:
            return base_msg
        return f"{addendum}\n{base_msg}"

    return render


def test_token_parity_mean_within_design_band(
    frozen_archive,
    l3_template_content,
    full_corpus_records,
):
    """The design's ±5% parity claim against E2's L3 payload over the
    same target records (≥5 records sampled; 10 by default).

    NOTE on failure: when this test fails, the FAILURE itself is the
    finding the package spec calls for at §"Decision rules". The PR
    body must surface the parity numbers and the decision branch
    (accept-with-caveat vs commission a planned post-tag top-up). Do
    NOT widen the band silently to make the test pass — that breaks
    the SHA-bound locked-content contract."""
    sample = deterministic_sample(
        full_corpus_records, n=DEFAULT_PARITY_SAMPLE_SIZE
    )
    assert len(sample) >= 5, (
        "Deterministic sample collapsed below the ≥5-record floor — "
        "the parity claim cannot be made."
    )

    render_arm_a = _build_arm_a_renderer(frozen_archive, l3_template_content)
    report = measure_token_parity(
        sample,
        render_arm_a_prompt=render_arm_a,
        template_path=LOCKED_TEMPLATE_PATH,
    )

    # The package-spec assertion. Failure surfaces the locked-content
    # parity gap; the PR body documents the empirical numbers.
    assert report.within_design_band, (
        "Arm C token-count parity outside the ±5% design band.\n\n"
        + report.to_markdown_table()
        + "\n\nThis is decision point 3 in the master plan. The locked "
        "Arm C content is SHA-bound by v0.3-predictions-locked — DO "
        "NOT widen the band or edit the locked file to make this pass. "
        "Surface to Sam: accept as methods caveat (≤±10%) vs commission "
        "a planned post-tag Arm C top-up with a fresh SHA."
    )
