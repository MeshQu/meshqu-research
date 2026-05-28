"""E3-002 — Arm A (precedents-only) handler tests.

The build package's "Definition of done" pivots on one assertion:
**byte-identity** between Arm A's rendered L3 precedent block and
E2's ``L3LiveHandler.build_addendum`` output, for the same target
record + same precedent set, on ≥3 record + precedent-set pairs.

This file exercises that assertion in two complementary ways:

  1. **In-tree byte-identity**: Arm A calls into E3's
     ``meshqu_runner.context_levels.level_l3.L3LiveHandler``. The L3
     portion of Arm A's output must equal what ``L3LiveHandler``
     produces directly for the same archive + same target. (This
     keeps Arm A from ever drifting from the L3 renderer.)

  2. **Cross-tree byte-identity**: E2's ``level_l3.py`` and E3's are
     supposed to be byte-identical. To prove the byte-identity claim
     in the build-package spec really crosses the experiment boundary,
     this file ALSO loads E2's ``L3LiveHandler`` directly from the
     E2 source tree via ``importlib`` and asserts its output equals
     Arm A's L3 portion. If E2's ``level_l3.py`` ever drifts from
     E3's, this assertion fires.

Both assertions are computed via SHA-256 over the rendered bytes —
the test logs each SHA so the PR body can quote them verbatim
(matches the build-package's "paste the SHA of the rendered prompt
for one record, computed by both renderers" requirement).

## Synthetic archive

The canonical frozen E1 archive lives at
``procurement-decisions/results/runs/dry-run-7ddf7274-…/``, which is
gitignored (it's a published artefact, not a checked-in fixture).
A worktree / CI runner doesn't carry it. So this file constructs a
small synthetic in-memory archive (5 ``PrecedentRecord`` entries) and
runs both renderers against it. The byte-identity claim is about
renderer LOGIC; the archive content is independent of that claim.

The synthetic records cover the three feature-vector axes the kNN
selector uses (contract_value_band × regime × method_flag) so the
3-smoke-record × 4-precedent picks span comparable + non-comparable
neighbours.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest

from meshqu_runner import arms
from meshqu_runner.arms.arm_a import (
    _resolve_e2_template_path,
    render_arm_a,
)
from meshqu_runner.context_levels.level_l3 import (
    L3LiveHandler,
    L3_SECTION_HEADER,
)
from meshqu_runner.precedent_archive import PrecedentRecord


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent.parent
E3_DIR = RUNNER_DIR.parent
REPO_ROOT = E3_DIR.parent
SMOKE_FIXTURE = RUNNER_DIR / "tests" / "fixtures" / "smoke_records.json"

E2_RUNNER_DIR = REPO_ROOT / "procurement-context-gradient" / "runner"
E2_LEVEL_L3_PATH = E2_RUNNER_DIR / "meshqu_runner" / "context_levels" / "level_l3.py"


# ---------------------------------------------------------------------------
# Synthetic archive — covers the feature-vector axes the kNN selector uses
# ---------------------------------------------------------------------------


def _make_precedent(
    *,
    ocid: str,
    decision_id: str,
    contract_value: float,
    governed_by_pa23: str,
    procurement_method_open_flag: str | None,
    publication_delay_days: int | None,
    award_date: str,
    meshqu_verdict: str,
    violations: tuple[str, ...],
    agent_reasoning: str,
    agent_recommended_action: str | None = None,
) -> PrecedentRecord:
    """One synthetic archive row — same shape ``precedent_archive``
    would produce from the real frozen corpus."""
    return PrecedentRecord(
        ocid=ocid,
        decision_id=decision_id,
        award_date=award_date,
        contract_value=contract_value,
        governed_by_pa23=governed_by_pa23,
        procurement_method_open_flag=procurement_method_open_flag,
        publication_delay_days=publication_delay_days,
        meshqu_verdict=meshqu_verdict,
        violations=violations,
        agent_reasoning=agent_reasoning,
        agent_recommended_action=agent_recommended_action,
    )


@pytest.fixture(scope="module")
def synthetic_archive() -> dict[str, PrecedentRecord]:
    """5 deterministic precedent records spanning the locked feature
    vector (contract_value_band × regime × method_flag). The kNN
    selector picks 4 deterministically; the 5th provides a non-trivial
    sort surface.

    OCIDs are chosen so the tie-break-by-OCID-ascending behaviour
    surfaces in the picks (e.g. records A and B both at distance 0
    will sort A → B by OCID)."""
    records = [
        _make_precedent(
            ocid="ocds-syn-001-pa23-100k-500k-methodtrue",
            decision_id="dec-syn-001",
            contract_value=300_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag="true",
            publication_delay_days=12,
            award_date="2025-06-12",
            meshqu_verdict="ALLOW",
            violations=(),
            agent_reasoning=(
                "Award above PA23 commencement; open-method declared; "
                "publication delay within tolerance band — clean."
            ),
            agent_recommended_action=None,
        ),
        _make_precedent(
            ocid="ocds-syn-002-pa23-500k-10M-methodnone",
            decision_id="dec-syn-002",
            contract_value=4_200_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            publication_delay_days=28,
            award_date="2025-08-04",
            meshqu_verdict="REVIEW",
            violations=("publication_delay_exceeded",),
            agent_reasoning=(
                "Publication delay of 28 days exceeds the 21-day threshold; "
                "REVIEW recommended."
            ),
            agent_recommended_action="follow up with contracting authority",
        ),
        _make_precedent(
            ocid="ocds-syn-003-pcr2015-500k-10M-methodnone",
            decision_id="dec-syn-003",
            contract_value=2_400_000.0,
            governed_by_pa23="false",
            procurement_method_open_flag=None,
            publication_delay_days=41,
            award_date="2024-09-10",
            meshqu_verdict="DENY",
            violations=("publication_delay_exceeded", "modification_disclosure_missing"),
            agent_reasoning=(
                "Pre-PA23; PCR 2015 in force. Publication delay of 41 days plus "
                "missing modification disclosure → DENY."
            ),
            agent_recommended_action="escalate to procurement review board",
        ),
        _make_precedent(
            ocid="ocds-syn-004-pa23-aboveband-methodnone",
            decision_id="dec-syn-004",
            contract_value=57_000_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            publication_delay_days=18,
            award_date="2025-11-30",
            meshqu_verdict="REVIEW",
            violations=(),
            agent_reasoning=(
                "Very high contract value (>£10M); no open-method flag; "
                "borderline publication delay — REVIEW for proportionality."
            ),
            agent_recommended_action="value-band escalation review",
        ),
        _make_precedent(
            ocid="ocds-syn-005-pa23-100k-500k-methodnone",
            decision_id="dec-syn-005",
            contract_value=460_000.0,
            governed_by_pa23="true",
            procurement_method_open_flag=None,
            publication_delay_days=7,
            award_date="2025-07-01",
            meshqu_verdict="ALLOW",
            violations=(),
            agent_reasoning=(
                "PA23 regime; mid-band value; rapid publication — clean award."
            ),
        ),
    ]
    return {r.ocid: r for r in records}


@pytest.fixture(scope="module")
def smoke_records() -> list[dict]:
    """The 3 smoke target records — same fixture the multi_pass tests
    use. Listed in fixture order (not OCID-sorted) so test cases that
    refer to "smoke record 1/2/3" map deterministically to the file."""
    with SMOKE_FIXTURE.open("r", encoding="utf-8") as fp:
        records = json.load(fp)
    assert len(records) == 3, "smoke fixture is supposed to carry 3 records"
    return records


@pytest.fixture(scope="module")
def locked_l3_template() -> str:
    """E2's locked L3 precedent block template — read once for the
    whole module so the SHA is computed against one well-defined
    set of bytes."""
    path = _resolve_e2_template_path()
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Cross-tree E2 importer — used to prove byte-identity isn't tautological
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def e2_level_l3_module() -> ModuleType:
    """Dynamically load E2's ``level_l3.py`` as a standalone module.

    E2's tree isn't on ``sys.path`` — and we don't want it to be, because
    that would conflate the two ``meshqu_runner`` package roots at
    import time. ``importlib.util.spec_from_file_location`` loads the
    file under a synthetic module name (``_e2_l3_under_test``) so its
    symbols don't collide with E3's.

    E2's ``level_l3.py`` uses RELATIVE imports
    (``from ..level_handlers import ...``). For the dynamic load we
    have to register stand-in parent packages so the relative imports
    resolve. The stand-ins point at E2's actual modules — so the dynamic
    import truly exercises E2's source tree, not E3's. If E2's
    ``level_l3.py`` ever drifts from E3's, this fixture STILL loads
    cleanly (the drift just shows up later in the SHA comparison).
    """
    pkg_name = "_e2_pkg_for_arm_a_test"
    sub_pkg_name = f"{pkg_name}.context_levels"

    # Synthetic top-level package whose path points at E2's
    # `meshqu_runner/` directory. We register it on sys.modules so
    # the relative-import chain `from .. import …` resolves up to it.
    e2_meshqu_runner_dir = E2_RUNNER_DIR / "meshqu_runner"
    top_pkg = ModuleType(pkg_name)
    top_pkg.__path__ = [str(e2_meshqu_runner_dir)]  # type: ignore[attr-defined]
    sys.modules[pkg_name] = top_pkg

    # Sub-package for `context_levels`.
    sub_pkg = ModuleType(sub_pkg_name)
    sub_pkg.__path__ = [str(e2_meshqu_runner_dir / "context_levels")]  # type: ignore[attr-defined]
    sys.modules[sub_pkg_name] = sub_pkg

    # Pre-load the sibling modules `level_l3` imports from. Each is
    # loaded from E2's source and registered under the synthetic
    # package name. The relative-import machinery then finds them
    # by `sys.modules` lookup.
    sibling_files = {
        f"{pkg_name}.level_handlers": e2_meshqu_runner_dir / "level_handlers.py",
        f"{pkg_name}.prompt_loader": e2_meshqu_runner_dir / "prompt_loader.py",
        f"{pkg_name}.precedent_archive": e2_meshqu_runner_dir / "precedent_archive.py",
        f"{pkg_name}.precedent_selector": e2_meshqu_runner_dir / "precedent_selector.py",
    }
    for full_name, path in sibling_files.items():
        spec = importlib.util.spec_from_file_location(full_name, path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = mod
        spec.loader.exec_module(mod)

    # Load level_l3 itself.
    target_name = f"{sub_pkg_name}.level_l3"
    spec = importlib.util.spec_from_file_location(target_name, E2_LEVEL_L3_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[target_name] = mod
    spec.loader.exec_module(mod)

    yield mod

    # Tidy up so a later test importing `meshqu_runner.*` isn't
    # shadowed by our synthetic packages.
    for name in list(sys.modules):
        if name == pkg_name or name.startswith(pkg_name + "."):
            del sys.modules[name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_base_user_message(rendered_arm_a: str) -> str:
    """Pull the L3-block portion out of Arm A's full rendered prompt.

    Arm A composes as ``<L3 block>\\n<base user message>`` (canonical
    JSON for the base). We split at the FIRST ``\\n{`` boundary — the
    base user message always begins with ``{`` (canonical JSON).
    """
    # The split point: the literal "\n{" that introduces the canonical
    # JSON base message. Use `rsplit` with maxsplit=1 keyed off "\n{"
    # so multi-line precedent text inside the L3 block can carry "\n{"
    # only if a precedent reasoning string contains JSON-shaped text
    # (none of the synthetic fixtures do).
    idx = rendered_arm_a.rfind("\n{")
    assert idx >= 0, "no base user message JSON boundary found in Arm A output"
    return rendered_arm_a[:idx]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_arm_a_registered():
    """The Arm A handler is in the registry; it's the real one, not
    the placeholder."""
    handler = arms.HANDLERS["arm_a"]
    assert handler.__name__ == "arm_a_handler"
    assert handler.__module__ == "meshqu_runner.arms.arm_a"


def test_arm_a_output_contains_l3_section_header(synthetic_archive, smoke_records):
    """Every smoke record renders the locked L3 section header — the
    bridge between Arm A's L3 block and the precedent renderings."""
    for record in smoke_records:
        out = render_arm_a(record, archive=synthetic_archive)
        assert L3_SECTION_HEADER in out


def test_arm_a_output_omits_l1_l2_section_headers(synthetic_archive, smoke_records):
    """Arm A's rendered prompt MUST NOT carry L1 or L2's section
    framing. The whole methodological commitment of Arm A is "no L1,
    no L2, only L3 precedents". A regression here means the renderer
    accidentally folded in another level."""
    for record in smoke_records:
        out = render_arm_a(record, archive=synthetic_archive)
        assert "## Governance context" not in out, (
            "Arm A rendered L1 section header — methodological violation"
        )
        assert "## Rules in force" not in out, (
            "Arm A rendered L2 section header — methodological violation"
        )


def test_arm_a_renders_four_precedent_headers(synthetic_archive, smoke_records):
    """k=4 against a 5-record archive must return exactly 4 precedents
    — one ``## Precedent N: comparable record`` header for each."""
    for record in smoke_records:
        out = render_arm_a(record, archive=synthetic_archive, k=4)
        for n in range(1, 5):
            assert f"## Precedent {n}: comparable record" in out, (
                f"missing precedent {n} header for {record['ocid']}"
            )
        # No literal `{ocid}` etc. left over — all template placeholders
        # interpolated.
        assert "{ocid}" not in out
        assert "{e1_agent_reasoning_text}" not in out


def test_arm_a_carries_base_user_message_after_l3_block(
    synthetic_archive, smoke_records
):
    """Arm A's L3 block is followed by the base user message, which
    is the canonical JSON of {decision_type, fields, substrate_notes}.
    Composition shape: ``<L3 block>\\n<JSON>``."""
    for record in smoke_records:
        out = render_arm_a(record, archive=synthetic_archive)
        # The base message is canonical JSON beginning with `{`.
        assert "\n{" in out, "base user message JSON envelope not present"
        # Decision type is one stable token in the base message.
        assert "procurement_decision" in out
        # The contract_value from the record's fields shows up in the
        # base JSON.
        cv = record["fields"]["contract_value"]
        assert str(cv) in out


def test_arm_a_deterministic_across_invocations(synthetic_archive, smoke_records):
    """Determinism contract: same record + same archive + same k →
    byte-identical output. Repeat 3× per record; SHA must match."""
    for record in smoke_records:
        shas = {
            _sha256(render_arm_a(record, archive=synthetic_archive)) for _ in range(3)
        }
        assert len(shas) == 1, (
            f"Arm A output non-deterministic for {record['ocid']}: {shas}"
        )


def test_arm_a_byte_identical_to_e3_l3_live_handler(
    synthetic_archive, smoke_records, locked_l3_template, capsys
):
    """In-tree byte-identity: Arm A's L3-block portion equals what
    ``L3LiveHandler.build_addendum`` produces for the same archive +
    same target. Arm A delegates to ``L3LiveHandler`` directly so this
    is the "no drift in the wrapper" assertion.

    Logs the SHA per record for the PR body.
    """
    print("\n=== In-tree byte-identity: Arm A L3-block vs E3 L3LiveHandler ===")
    e3_handler = L3LiveHandler(
        archive=synthetic_archive, k=4, template_content=locked_l3_template
    )

    for record in smoke_records:
        arm_a_full = render_arm_a(record, archive=synthetic_archive, k=4)
        arm_a_l3_block = _strip_base_user_message(arm_a_full)

        e3_addendum = e3_handler.build_addendum(
            record=record,
            ocid=record["ocid"],
            prompts=None,  # type: ignore[arg-type]
        )

        # The L3 block Arm A emits is `e3_addendum` MINUS the trailing
        # newline that compose_user_message-style concatenation would
        # carry. Compare verbatim.
        assert arm_a_l3_block.rstrip("\n") == e3_addendum.rstrip("\n"), (
            f"Arm A L3 block drifted from E3 L3LiveHandler for {record['ocid']}"
        )

        sha = _sha256(arm_a_l3_block.rstrip("\n"))
        print(f"  {record['ocid']}: sha256 = {sha}")

    captured = capsys.readouterr()
    print(captured.out, end="")  # surface to pytest -s output


def test_arm_a_byte_identical_to_e2_l3_live_handler(
    synthetic_archive,
    smoke_records,
    locked_l3_template,
    e2_level_l3_module,
    capsys,
):
    """Cross-tree byte-identity: Arm A's L3-block portion equals what
    E2's ``L3LiveHandler`` (loaded dynamically from
    ``procurement-context-gradient/runner/.../level_l3.py``) produces
    for the same archive + same target.

    This is the test the build-package spec calls "non-negotiable" —
    if it fails, either:

      - The fork-parity layer drifted (somebody touched a "frozen-from-E2"
        module), or
      - E2's renderer was non-deterministic in a way nobody noticed.

    Either way, the prescribed reaction is to STOP and surface to Sam.

    The synthetic archive is used by both renderers — the byte-identity
    claim is about renderer logic, independent of archive content.

    Logs the SHA per record for the PR body.
    """
    print("\n=== Cross-tree byte-identity: Arm A L3-block vs E2 L3LiveHandler ===")
    E2L3 = e2_level_l3_module.L3LiveHandler

    # E2's PrecedentRecord (loaded via the cross-tree importer) is a
    # different class object from E3's PrecedentRecord, even though
    # they're byte-identical dataclasses. Build an E2-typed archive
    # so the e2-side type system + dataclass field access work
    # cleanly.
    e2_archive_pkg = sys.modules["_e2_pkg_for_arm_a_test.precedent_archive"]
    E2PrecedentRecord = e2_archive_pkg.PrecedentRecord

    def _coerce_to_e2(record: PrecedentRecord) -> object:
        return E2PrecedentRecord(
            ocid=record.ocid,
            decision_id=record.decision_id,
            award_date=record.award_date,
            contract_value=record.contract_value,
            governed_by_pa23=record.governed_by_pa23,
            procurement_method_open_flag=record.procurement_method_open_flag,
            publication_delay_days=record.publication_delay_days,
            meshqu_verdict=record.meshqu_verdict,
            violations=record.violations,
            agent_reasoning=record.agent_reasoning,
            agent_recommended_action=record.agent_recommended_action,
        )

    e2_archive = {ocid: _coerce_to_e2(r) for ocid, r in synthetic_archive.items()}

    e2_handler = E2L3(
        archive=e2_archive, k=4, template_content=locked_l3_template
    )

    for record in smoke_records:
        arm_a_full = render_arm_a(record, archive=synthetic_archive, k=4)
        arm_a_l3_block = _strip_base_user_message(arm_a_full)

        e2_addendum = e2_handler.build_addendum(
            record=record,
            ocid=record["ocid"],
            prompts=None,
        )

        arm_a_sha = _sha256(arm_a_l3_block.rstrip("\n"))
        e2_sha = _sha256(e2_addendum.rstrip("\n"))

        print(f"  {record['ocid']}:")
        print(f"    Arm A L3 block sha256 = {arm_a_sha}")
        print(f"    E2 L3 block sha256    = {e2_sha}")

        assert arm_a_sha == e2_sha, (
            f"CROSS-TREE BYTE-IDENTITY BROKEN for {record['ocid']}: "
            f"Arm A produced {arm_a_sha} but E2 produced {e2_sha}. "
            "See build-package §3 'Tests' — STOP and surface to Sam."
        )

    captured = capsys.readouterr()
    print(captured.out, end="")  # surface to pytest -s output


def test_arm_a_picks_exactly_k_precedents(synthetic_archive, smoke_records):
    """``k=4`` against a 5-record archive must produce 4 precedent
    blocks (one per pick). Per the build-package "stop conditions":
    if any of the 3 smoke records selects fewer than 4 precedents,
    surface to Sam — this is an E2 drift to record, not an Arm A bug.
    Caught here by counting ``## Precedent N: comparable record``
    occurrences."""
    for record in smoke_records:
        out = render_arm_a(record, archive=synthetic_archive, k=4)
        count = out.count("comparable record")
        assert count == 4, (
            f"Arm A selected {count} precedents for {record['ocid']} (expected 4). "
            "Stop condition: surface as a frozen-archive drift."
        )


def test_arm_a_empty_archive_returns_only_base_message(smoke_records):
    """No archive → no precedents → no L3 block → agent sees only the
    base user message. Same graceful no-op contract E2's
    ``L3LiveHandler`` carries (the build-package spec §"Decision rules"
    treats this as acceptable for ``--dry`` invocation in a checkout
    without the frozen E1 corpus).
    """
    for record in smoke_records:
        out = render_arm_a(record, archive={})
        assert L3_SECTION_HEADER not in out
        # The base user message is canonical JSON beginning with `{`.
        assert out.startswith("{"), (
            f"Expected base JSON; got {out[:60]!r}"
        )


def test_arm_a_dispatch_through_registry(synthetic_archive, smoke_records):
    """End-to-end: ``arms.dispatch('arm_a', record, archive=...)``
    routes to the real handler and produces the same output as the
    direct ``render_arm_a`` call. Verifies the orchestrator-callable
    path the multi_pass loop will use."""
    record = smoke_records[0]
    direct = render_arm_a(record, archive=synthetic_archive, k=4)
    dispatched = arms.dispatch("arm_a", record, archive=synthetic_archive, k=4)
    assert dispatched == direct


def test_arm_a_locked_template_path_resolves():
    """The locked E2 path is reachable from the worktree — guards
    against the path going stale if either tree is restructured.
    Failing here means the build-package "use E2's locked L3 prompt
    by reference" decision needs revisiting."""
    path = _resolve_e2_template_path()
    assert path.exists(), f"Locked E2 L3 template not found at {path}"
    # Locked content starts with the per-precedent header — guards
    # against an accidental rewrite of E2's prompt.
    assert path.read_text(encoding="utf-8").startswith(
        "## Precedent {n}: comparable record"
    )
