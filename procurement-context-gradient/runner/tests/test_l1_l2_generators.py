"""Tests for E2-003 — L1 + L2 prompt-payload generators.

Covers the four package-prompt requirements:

1. L1 prompt = L0 + L1 content (verbatim substring check).
2. L2 prompt = L1 prompt + L2 content (verbatim substring check) —
   THE LOAD-BEARING ADDITIVITY INVARIANT.
3. Empty Stage A content (TODO stubs) raises a clear error at startup.
   (Truly-empty files remain a no-op per the E2-001 contract.)
4. Prompt SHAs in receipts match `prompt_template_sha256.L1` / `.L2`
   in the run manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from meshqu_runner import multi_pass as mp

# Import per-level modules directly. The `context_levels` subpackage's
# __init__ may or may not eagerly re-export (the convention is
# established across parallel build packages) — direct submodule
# imports are the safe form that works regardless.
from meshqu_runner.context_levels.level_l1 import (
    L1ContextHandler,
    build_l1_addendum,
)
from meshqu_runner.context_levels.level_l2 import (
    L2ContextHandler,
    build_l2_addendum,
)
from meshqu_runner.context_levels.stage_a import (
    StageAContentError,
    looks_like_todo_stub,
)
from meshqu_runner.level_handlers import (
    MAIN_LEVELS,
    compose_user_message,
    default_main_handlers,
)
from meshqu_runner.prompt_loader import LEVEL_PROMPT_FILES, load_level_prompts


RUNNER_DIR = Path(__file__).resolve().parent.parent
E2_DIR = RUNNER_DIR.parent
REPO_DIR = E2_DIR.parent
PROMPTS_DIR = RUNNER_DIR / "prompts"
POLICY_SNAPSHOT_PATH = E2_DIR / "policy" / "policy-snapshot-cbf12348.json"
FIXTURE_PATH = RUNNER_DIR / "tests" / "fixtures" / "smoke_records.json"


# Expected SHAs — pinned literal values, matching `test_multi_pass.py`'s
# `test_prompt_shas_match_locked_values`. If Stage A content drifts,
# BOTH tests fail — making the drift visible at two test sites.
EXPECTED_L1_SHA = "19b9863905593756b583bdc4b39998f143ba14c63fa1cebe90295d6e76f90acf"
EXPECTED_L2_SHA = "d24847ed1eef3c4d87b725195d0313449398e2a467c7de4bf0cd6a9e93c11174"


def _load_records() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _handler_registry():
    """Return a handler registry with E2-003 L1+L2 swapped in.

    The shared `default_main_handlers()` may or may not have been
    updated to point to the live implementations by the time these
    tests run (depends on which parallel build packages have merged).
    For test determinism we ALWAYS swap in our own handlers here, so
    these tests exercise the E2-003 implementation regardless of the
    current state of the registry."""
    handlers = default_main_handlers()
    handlers["L1"] = L1ContextHandler()
    handlers["L2"] = L2ContextHandler()
    return handlers


# ---------------------------------------------------------------------------
# Stage A content guard rails
# ---------------------------------------------------------------------------


class TestStageATodoDetection:
    """Empty-content contract — the package prompt is explicit:

      > Empty Stage A content (placeholder TODO strings) should raise
      > a clear error at startup so misconfiguration is caught.

    This MUST coexist with E2-001's `test_empty_prompts_handled_gracefully`
    which expects truly-empty files to behave as a no-op. The resolution:
    only TODO-stub content raises; pure empty stays a no-op."""

    def test_pure_empty_is_not_a_todo_stub(self):
        """E2-001 graceful no-op preserved: empty / whitespace-only
        content does NOT trip the guard."""
        assert looks_like_todo_stub("") is False
        assert looks_like_todo_stub("   \n  \n") is False

    @pytest.mark.parametrize(
        "stub_content",
        [
            "TODO: Stage A content",
            "TODO: Stage A content.",
            "TODO",
            "  TODO: write this later  ",  # leading whitespace tolerated
            "TODO: domain summary\nTODO: link to PA23 regs",  # multi-line stub
            "todo: case-insensitive",
        ],
    )
    def test_todo_stub_variants_detected(self, stub_content: str):
        assert looks_like_todo_stub(stub_content) is True

    def test_authored_prose_with_parenthetical_todo_passes(self):
        """A real authored paragraph that mentions "TODO" parenthetically
        must NOT trip the guard. The detection is line-based."""
        prose = (
            "The policy governs UK public-sector procurement. "
            "(TODO follow-up: clarify the SME exemption in a future revision.) "
            "Six rules are in force."
        )
        assert looks_like_todo_stub(prose) is False


# ---------------------------------------------------------------------------
# L1 addendum
# ---------------------------------------------------------------------------


class TestL1Addendum:
    """L1 handler reads `runner/prompts/L1_governance_context.md` and
    wraps it under `## Governance context`."""

    def test_l1_addendum_contains_the_locked_prose_verbatim(self):
        prompts = load_level_prompts(PROMPTS_DIR)
        addendum = build_l1_addendum(prompts)
        # The raw Stage A content (stripped) must appear verbatim
        # inside the addendum.
        raw = prompts.get("L1").content.strip()
        assert raw, "Stage A L1 file is empty — test fixture mismatch"
        assert raw in addendum, "L1 addendum dropped or mutated the locked prose"

    def test_l1_addendum_wraps_in_section_header(self):
        prompts = load_level_prompts(PROMPTS_DIR)
        addendum = build_l1_addendum(prompts)
        assert addendum.startswith("## Governance context\n\n"), (
            f"L1 addendum must open with the H2 header; got prefix "
            f"{addendum[:48]!r}"
        )

    def test_l1_handler_matches_pure_function(self):
        """The dataclass handler is a thin wrapper around the pure
        function — they should produce identical output."""
        prompts = load_level_prompts(PROMPTS_DIR)
        handler = L1ContextHandler()
        records = _load_records()
        for record in records:
            assert handler.build_addendum(
                record=record, ocid=record["ocid"], prompts=prompts
            ) == build_l1_addendum(prompts)

    def test_l1_addendum_record_invariant(self):
        """L1 prose is the same paragraph for every record. The
        addendum must not vary with record content."""
        prompts = load_level_prompts(PROMPTS_DIR)
        handler = L1ContextHandler()
        records = _load_records()
        outputs = {
            handler.build_addendum(
                record=record, ocid=record["ocid"], prompts=prompts
            )
            for record in records
        }
        assert len(outputs) == 1, (
            "L1 addendum varies per record — should be invariant"
        )


# ---------------------------------------------------------------------------
# L2 addendum
# ---------------------------------------------------------------------------


class TestL2Addendum:
    """L2 handler reads `runner/prompts/L2_named_rules.md` and emits
    verbatim. The file already carries its own `## Rules in force`
    header."""

    def test_l2_addendum_contains_the_locked_rules_verbatim(self):
        prompts = load_level_prompts(PROMPTS_DIR)
        addendum = build_l2_addendum(prompts)
        raw = prompts.get("L2").content.strip()
        assert raw, "Stage A L2 file is empty — test fixture mismatch"
        assert raw in addendum, "L2 addendum dropped or mutated the locked rule list"

    def test_l2_addendum_contains_all_six_rule_codes(self):
        prompts = load_level_prompts(PROMPTS_DIR)
        addendum = build_l2_addendum(prompts)
        for code in (
            "PROC-001-S53",
            "PROC-002-AUTHORITY",
            "PROC-003-DEBARMENT",
            "PROC-004-COI",
            "PROC-005-OPEN-TENDER",
            "PROC-006-MOD-CAP",
        ):
            assert code in addendum, f"L2 addendum missing rule code {code}"

    def test_l2_addendum_record_invariant(self):
        prompts = load_level_prompts(PROMPTS_DIR)
        handler = L2ContextHandler()
        records = _load_records()
        outputs = {
            handler.build_addendum(
                record=record, ocid=record["ocid"], prompts=prompts
            )
            for record in records
        }
        assert len(outputs) == 1

    def test_l2_addendum_does_not_duplicate_rules_in_force_header(self):
        """The L2 Stage A file opens with `## Rules in force`. The
        handler emits verbatim, so the composed prompt must contain
        EXACTLY ONE `## Rules in force` heading — not two (which
        would indicate a wrapping bug like E2-001's stub)."""
        prompts = load_level_prompts(PROMPTS_DIR)
        addendum = build_l2_addendum(prompts)
        assert addendum.count("## Rules in force") == 1


# ---------------------------------------------------------------------------
# Additivity invariant — THE load-bearing test
# ---------------------------------------------------------------------------


class TestAdditivityInvariant:
    """The experiment design hinges on each level's prompt strictly
    containing every lower level's content. If L2 doesn't contain L1's
    prose verbatim, the slope from L1 → L2 stops being a marginal-effect
    measurement and becomes a confound."""

    def test_l0_user_message_is_just_the_base(self):
        """L0 contributes no addendum — the composed L0 user message
        equals the base record message exactly."""
        prompts = load_level_prompts(PROMPTS_DIR)
        handlers = _handler_registry()
        record = _load_records()[0]
        base = "BASE_RECORD_MESSAGE_PLACEHOLDER"
        composed = compose_user_message(
            level="L0",
            record=record,
            ocid=record["ocid"],
            prompts=prompts,
            handlers=handlers,
            base_message=base,
        )
        assert composed == base

    def test_l1_user_message_contains_l0_message_and_l1_content(self):
        """L1 = L0 + L1 content (verbatim substring check)."""
        prompts = load_level_prompts(PROMPTS_DIR)
        handlers = _handler_registry()
        record = _load_records()[0]
        base = "BASE_RECORD_MESSAGE_PLACEHOLDER"

        l0 = compose_user_message(
            level="L0", record=record, ocid=record["ocid"],
            prompts=prompts, handlers=handlers, base_message=base,
        )
        l1 = compose_user_message(
            level="L1", record=record, ocid=record["ocid"],
            prompts=prompts, handlers=handlers, base_message=base,
        )

        # 1. L1 still contains the base record message.
        assert base in l1
        # 2. L1 contains the L0 message (which is just the base here).
        assert l0 in l1
        # 3. L1 contains the L1 Stage A prose verbatim.
        raw_l1 = prompts.get("L1").content.strip()
        assert raw_l1 in l1, "L1 composed message dropped the L1 prose"

    def test_l2_user_message_strictly_contains_l1_user_message(self):
        """THE additivity test from the package prompt:

          > An L2 prompt MUST strictly contain the L1 prompt's content
          > as a substring.

        We check the composed user messages (what the agent actually
        sees) for the verbatim-substring property. This is the test
        that would fail if a future change broke ladder additivity.
        """
        prompts = load_level_prompts(PROMPTS_DIR)
        handlers = _handler_registry()
        record = _load_records()[0]
        base = "BASE_RECORD_MESSAGE_PLACEHOLDER"

        l1 = compose_user_message(
            level="L1", record=record, ocid=record["ocid"],
            prompts=prompts, handlers=handlers, base_message=base,
        )
        l2 = compose_user_message(
            level="L2", record=record, ocid=record["ocid"],
            prompts=prompts, handlers=handlers, base_message=base,
        )

        # The L1 composed message must appear inside the L2 composed
        # message MINUS the per-level base-suffix delimiter — at L1 the
        # message ends with "\n{base}", at L2 it ends with
        # "<L2 content>\n\n{base}". The L1 ADDENDUM (everything up to
        # but not including the base) must be a prefix of L2.
        l1_prefix = l1.removesuffix(base).rstrip("\n")
        l2_prefix = l2.removesuffix(base).rstrip("\n")

        assert l1_prefix, "L1 composed message has no addendum — Stage A fixture broken"
        assert l1_prefix in l2_prefix, (
            "ADDITIVITY VIOLATED: L2 composed user message does not "
            "contain the L1 composed user message as a substring. "
            f"L1 prefix:\n{l1_prefix!r}\nL2 prefix:\n{l2_prefix!r}"
        )

        # And L2 must additionally contain the L2 Stage A content.
        raw_l2 = prompts.get("L2").content.strip()
        assert raw_l2 in l2, "L2 composed message dropped the L2 named-rules block"

    def test_additivity_holds_for_every_smoke_record(self):
        """The additivity invariant is record-independent (L1/L2 prose
        is the same for every record). Sanity-check across all three
        smoke fixtures so the property holds in batch."""
        prompts = load_level_prompts(PROMPTS_DIR)
        handlers = _handler_registry()
        base = "BASE"
        for record in _load_records():
            l1 = compose_user_message(
                level="L1", record=record, ocid=record["ocid"],
                prompts=prompts, handlers=handlers, base_message=base,
            )
            l2 = compose_user_message(
                level="L2", record=record, ocid=record["ocid"],
                prompts=prompts, handlers=handlers, base_message=base,
            )
            l1_prefix = l1.removesuffix(base).rstrip("\n")
            l2_prefix = l2.removesuffix(base).rstrip("\n")
            assert l1_prefix in l2_prefix, (
                f"additivity broken for OCID {record['ocid']}"
            )


# ---------------------------------------------------------------------------
# Empty / TODO-stub content contract
# ---------------------------------------------------------------------------


class TestStubContentRaises:
    """Per the package prompt:

      > Empty Stage A content (placeholder TODO strings) should raise
      > a clear error at startup so misconfiguration is caught.

    Note: truly-empty (`""`) is NOT a TODO stub — see
    `TestStageATodoDetection` and `test_multi_pass.test_empty_prompts_handled_gracefully`.
    The check fires only for placeholder text that looks unauthored."""

    @pytest.fixture
    def todo_stub_prompts(self, tmp_path: Path) -> Path:
        """Build a prompts dir where L1 + L2 are TODO stubs."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "L1_governance_context.md").write_text(
            "TODO: Stage A content\n", encoding="utf-8"
        )
        (prompts_dir / "L2_named_rules.md").write_text(
            "TODO: Stage A content\n", encoding="utf-8"
        )
        # L3 + L4 still need to exist for prompt_loader; copy the real
        # content so the fixture only exercises the L1/L2 guard.
        (prompts_dir / "L3_precedent_block_format.md").write_text(
            (PROMPTS_DIR / "L3_precedent_block_format.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (prompts_dir / "L4_policy_envelope.md").write_text(
            (PROMPTS_DIR / "L4_policy_envelope.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return prompts_dir

    def test_l1_todo_stub_raises(self, todo_stub_prompts: Path):
        prompts = load_level_prompts(todo_stub_prompts)
        with pytest.raises(StageAContentError, match="placeholder stub"):
            build_l1_addendum(prompts)

    def test_l2_todo_stub_raises(self, todo_stub_prompts: Path):
        prompts = load_level_prompts(todo_stub_prompts)
        with pytest.raises(StageAContentError, match="placeholder stub"):
            build_l2_addendum(prompts)

    def test_handlers_raise_on_first_use(self, todo_stub_prompts: Path):
        """The dataclass handlers must surface the same error when
        called via the LevelHandler Protocol."""
        prompts = load_level_prompts(todo_stub_prompts)
        record = _load_records()[0]
        with pytest.raises(StageAContentError):
            L1ContextHandler().build_addendum(
                record=record, ocid=record["ocid"], prompts=prompts
            )
        with pytest.raises(StageAContentError):
            L2ContextHandler().build_addendum(
                record=record, ocid=record["ocid"], prompts=prompts
            )

    def test_empty_files_still_noop(self, tmp_path: Path):
        """E2-001 contract preserved: truly-empty L1/L2 files produce
        empty addenda (no exception)."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        for _level, filename in LEVEL_PROMPT_FILES:
            (prompts_dir / filename).write_text("", encoding="utf-8")
        prompts = load_level_prompts(prompts_dir)
        assert build_l1_addendum(prompts) == ""
        assert build_l2_addendum(prompts) == ""


# ---------------------------------------------------------------------------
# SHA round-trip from Stage A files → run manifest → bundle outputs
# ---------------------------------------------------------------------------


class TestPromptShaBindingThroughRunManifest:
    """The package prompt:

      > Verify SHAs match by hashing the prompt content at runtime and
      > comparing to the manifest values.
      > Prompt SHAs in receipts match `prompt_template_sha256.L1` and
      > `.L2` in the manifest.

    The manifest is written by `write_e2_manifest`, which calls
    `prompts.sha_map()`. We assert the round trip:

        file bytes → SHA-256 → manifest field → expected literal
    """

    def test_runtime_sha_matches_expected_literal_l1(self):
        """Hash the file on disk; assert it matches the SHA pinned in
        E2-001's manifest test (and in this test module)."""
        actual = _sha256_file(PROMPTS_DIR / "L1_governance_context.md")
        assert actual == EXPECTED_L1_SHA, (
            f"L1 Stage A file SHA drifted: got {actual}, "
            f"expected {EXPECTED_L1_SHA}. The Stage A content was modified "
            f"without re-locking the predictions tag."
        )

    def test_runtime_sha_matches_expected_literal_l2(self):
        actual = _sha256_file(PROMPTS_DIR / "L2_named_rules.md")
        assert actual == EXPECTED_L2_SHA, (
            f"L2 Stage A file SHA drifted: got {actual}, "
            f"expected {EXPECTED_L2_SHA}."
        )

    def test_prompt_loader_sha_matches_runtime_hash(self):
        """The SHA the prompt loader records must equal the SHA computed
        directly over the file bytes (no normalisation drift)."""
        prompts = load_level_prompts(PROMPTS_DIR)
        assert prompts.get("L1").sha256 == _sha256_file(PROMPTS_DIR / "L1_governance_context.md")
        assert prompts.get("L2").sha256 == _sha256_file(PROMPTS_DIR / "L2_named_rules.md")

    def test_manifest_records_l1_and_l2_shas(self, tmp_path: Path):
        """End-to-end: drive a stub multi-pass run with the real Stage
        A prompts and confirm the manifest's `prompt_template_sha256.L1`
        and `.L2` match the runtime hashes."""
        records = _load_records()
        run_dir = tmp_path / "runs" / "e2-003-sha-binding"
        config = mp.MultiPassConfig(
            run_id="e2-003-sha-binding",
            run_phase="dry-run",
            repo_dir=REPO_DIR,
            run_dir=run_dir,
            prompts_dir=PROMPTS_DIR,
            policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        )
        mp.run_multi_pass(
            config=config,
            records=records,
            agent=mp.StubAgent(),
            meshqu_client=mp.StubMeshQuClient(),
        )

        with (run_dir / "manifest.json").open("r", encoding="utf-8") as fp:
            manifest = json.load(fp)

        assert manifest["prompt_template_sha256"]["L1"] == EXPECTED_L1_SHA
        assert manifest["prompt_template_sha256"]["L2"] == EXPECTED_L2_SHA

    def test_bundle_l1_and_l2_contain_stage_a_content(self, tmp_path: Path):
        """3-record smoke produces L1 and L2 bundles containing the
        Stage A content verbatim — the DoD criterion for E2-003:

          > 3-record smoke produces L1 and L2 receipts that contain the
          > Stage A content verbatim in the prompt-replay output.

        The runner-local bundles do not currently persist the composed
        user message verbatim (only the canonical-JSON fields map). So
        we verify the property at the composition layer using the same
        registry the orchestrator uses, for the same records the
        orchestrator processed."""
        records = _load_records()
        run_dir = tmp_path / "runs" / "e2-003-smoke-verbatim"
        config = mp.MultiPassConfig(
            run_id="e2-003-smoke-verbatim",
            run_phase="dry-run",
            repo_dir=REPO_DIR,
            run_dir=run_dir,
            prompts_dir=PROMPTS_DIR,
            policy_snapshot_path=POLICY_SNAPSHOT_PATH,
        )
        # Run with our explicit registry so the test is deterministic
        # regardless of whether the shared registry was updated.
        handlers = _handler_registry()
        mp.run_multi_pass(
            config=config,
            records=records,
            agent=mp.StubAgent(),
            meshqu_client=mp.StubMeshQuClient(),
            handlers=handlers,
        )

        # Bundles exist for every record at L1 and L2.
        l1_bundles = list((run_dir / "L1").glob("*.bundle.json"))
        l2_bundles = list((run_dir / "L2").glob("*.bundle.json"))
        assert len(l1_bundles) == 3
        assert len(l2_bundles) == 3

        # Recompose the user message at L1 and L2 for each record and
        # check the Stage A content is verbatim.
        prompts = load_level_prompts(PROMPTS_DIR)
        raw_l1 = prompts.get("L1").content.strip()
        raw_l2 = prompts.get("L2").content.strip()

        for record in records:
            base = "BASE"
            l1 = compose_user_message(
                level="L1", record=record, ocid=record["ocid"],
                prompts=prompts, handlers=handlers, base_message=base,
            )
            l2 = compose_user_message(
                level="L2", record=record, ocid=record["ocid"],
                prompts=prompts, handlers=handlers, base_message=base,
            )
            assert raw_l1 in l1
            assert raw_l1 in l2  # additivity
            assert raw_l2 in l2
