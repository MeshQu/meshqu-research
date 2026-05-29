"""Lock-in test — every diagnostic-arm-touching driver MUST emit the
inverted-operator-spec sidecar after the diagnostic arms complete.

## What this locks in

A contract-drift bug between sibling drivers:

  - PR #95 (E3-008) shipped ``scripts/run_scaled_diagnostic.py`` which
    emitted the inverted-operator-spec sidecar via
    ``meshqu_runner.diagnostic.scaled.emit_inverted_operator_spec(...)``
    after the diagnostic arms completed.
  - PR #91 (E3-009) shipped the rubric tool at
    ``meshqu_runner.diagnostic.code_rubric`` which requires that sidecar
    (the ``--inverted-spec`` flag is mandatory; the CLI docstring points
    at ``results/runs/<run_id>/inverted_operator_spec.json``).
  - PR #96 (E3-010) shipped ``scripts/smoke_e3.py`` as a fresh driver
    pattern; sidecar emission was NOT carried over.
  - PR #99 (E3-011) shipped ``scripts/dry_run_e3.py`` by extending the
    smoke driver pattern; sidecar emission was still NOT carried over.

Phase 2 fired via ``dry_run_e3.py --scale phase-2`` on 2026-05-29 and
produced 1,332 cryptographically-verified bundles plus summaries plus
observability captures — but NO inverted-operator-spec sidecar. The
user caught the drift when trying to start Phase 2.5 hand-coding via
``python -m meshqu_runner.diagnostic.code_rubric --inverted-spec
results/runs/phase-2-20260529T092611-Z/inverted_operator_spec.json``
and discovered the path didn't resolve.

The receipts themselves are uncompromised — the bundles' canonical-JSON
payload + Ed25519 signature are independent of the sidecar. The sidecar
is metadata *about* the policy permutation, derivable deterministically
from the v0.3-tagged inputs. The Phase 2 sidecar is reconstructed
post-hoc by ``scripts/generate_inverted_spec_post_hoc.py``. This test
prevents the same drift recurring on any future driver fork.

## The discipline pattern

Same shape as ``tests/test_handler_record_composition.py`` (PR #97's
record-composition lock-in) and
``tests/test_observability_wiring.py::test_phase_2_missing_grafana_env_fails_loud_at_gate``
(PR #103's observability fail-loud follow-up): every driver that touches
sidecar emission MUST include an assertion against the artefact's
existence and shape. Sibling-driver contract drift caught Phase 2 once;
this test prevents it from happening again.

## The assertions

For each of the two supported scales:

1. Drive ``dry_run_e3.main`` in ``--dry`` mode + ``--no-observability``
   at the scale.
2. Assert ``<run_dir>/inverted_operator_spec.json`` exists at the
   run-dir root — the path
   ``meshqu_runner.diagnostic.code_rubric``'s CLI documents.
3. Assert the JSON payload is a top-level object keyed by OCID with the
   correct entry count (10 OCIDs for dry-run; 100 OCIDs for phase-2 —
   matches ``RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE``).
4. Roundtrip through
   ``meshqu_runner.diagnostic.rubric_io.load_inverted_specs`` — locks
   the producer/consumer contract end-to-end (a structural drift in
   either side trips the test).
5. Assert the spec sentence mentions the locked seed + the rule count
   so a future stochastic-variant driver can't silently emit empty
   stubs.

No live API calls. Stubbed end-to-end via the autouse fixture that
swaps in fixture-backed records when the E1 archive is absent (see
``conftest.py``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RUNNER_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _RUNNER_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

import dry_run_e3  # noqa: E402

from meshqu_runner.diagnostic.permute_policy import (  # noqa: E402
    LOCKED_PERMUTATION_SEED,
)
from meshqu_runner.diagnostic.rubric_io import load_inverted_specs  # noqa: E402
from meshqu_runner.diagnostic.scaled import (  # noqa: E402
    INVERTED_OPERATOR_SPEC_FILENAME,
)


SIDECAR_FILENAME = INVERTED_OPERATOR_SPEC_FILENAME
"""Locked by the producer module — the consumer's CLI documents the
same name at the run-dir root."""


def _dispatch_dry(
    tmp_path: Path, *, scale: str, run_id: str
) -> Path:
    """Drive ``dry_run_e3.main`` in ``--dry`` mode at the given scale.
    Returns the run directory.

    ``--no-observability`` is passed unconditionally because these
    tests assert sidecar emission, not OBS-205/206 wiring (see
    ``tests/test_observability_wiring.py`` for that). Under the
    post-2026-05-28 policy split, ``--scale phase-2`` without Grafana
    env vars fail-louds at the gate; these tests run in environments
    where those vars aren't set, so the opt-out keeps the focus on the
    sidecar-emission contract this test owns."""
    rc = dry_run_e3.main(
        [
            "--scale", scale,
            "--dry",
            "--no-observability",
            "--results-dir", str(tmp_path),
            "--run-id", run_id,
            "--inter-request-pause-seconds", "0.0",
        ]
    )
    assert rc == 0, f"driver returned {rc} for --scale {scale}"
    return tmp_path / "runs" / run_id


@pytest.mark.parametrize(
    "scale,n_expected",
    [
        ("dry-run", 10),
        ("phase-2", 100),
    ],
    ids=["scale=dry-run (n=10)", "scale=phase-2 (n=100)"],
)
def test_dry_run_e3_emits_inverted_operator_spec_sidecar(
    scale: str, n_expected: int, tmp_path: Path
):
    """Lock-in: ``dry_run_e3.py`` MUST emit ``inverted_operator_spec.json``
    at the run-dir root after the diagnostic arms complete, regardless of
    scale.

    The rubric tool's CLI (``meshqu_runner.diagnostic.code_rubric``)
    points ``--inverted-spec`` at
    ``results/runs/<run_id>/inverted_operator_spec.json`` — Sam's
    Phase 2.5 hand-coding invocation. Drift between sibling drivers
    (``run_scaled_diagnostic.py`` had this emission; ``smoke_e3.py`` and
    ``dry_run_e3.py`` forked without it) caused the Phase 2 corpus to
    land without the sidecar. This test prevents the recurrence.

    The discipline pattern mirrors the per-record SHA-distinctness
    lock-in in ``test_handler_record_composition.py`` and the
    fail-loud precondition lock-in in
    ``test_observability_wiring.py::test_phase_2_missing_grafana_env_fails_loud_at_gate``:
    contract drift caught the methodologically required artefact once;
    the lock-in test bounds the failure mode going forward."""
    run_dir = _dispatch_dry(
        tmp_path, scale=scale, run_id=f"inverted-spec-{scale}"
    )

    # (1) The sidecar lands at the run-dir root — same path the rubric
    # tool's CLI documents.
    sidecar = run_dir / SIDECAR_FILENAME
    assert sidecar.exists(), (
        f"--scale {scale}: inverted-operator-spec sidecar must land at "
        f"{sidecar}. Drift between sibling drivers (run_scaled_diagnostic.py "
        f"had this emission; smoke_e3.py + dry_run_e3.py forked without it) "
        f"caused Phase 2 to land without the sidecar. The rubric tool "
        f"(meshqu_runner.diagnostic.code_rubric) reads from this exact "
        f"path."
    )

    # (2) The payload is a top-level object keyed by OCID with the
    # right entry count for the scale.
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), (
        f"--scale {scale}: sidecar must be a top-level JSON object keyed "
        f"by OCID; got {type(payload).__name__}."
    )
    assert len(payload) == n_expected, (
        f"--scale {scale}: sidecar must contain {n_expected} OCID entries "
        f"(matches RECORDS_PER_DIAGNOSTIC_ARM_BY_SCALE[{scale!r}]); "
        f"got {len(payload)}."
    )

    # (3) Roundtrip through the consumer — locks the producer/consumer
    # contract end-to-end. A structural drift in either side trips here.
    specs = load_inverted_specs(sidecar)
    assert len(specs) == n_expected, (
        f"--scale {scale}: load_inverted_specs returned {len(specs)} "
        f"entries; expected {n_expected}. Producer/consumer schema drift."
    )

    # (4) Spec sentence mentions the locked seed + rule count — a future
    # stochastic-variant driver can't silently emit empty stubs.
    for ocid, spec in specs.items():
        assert f"seed={LOCKED_PERMUTATION_SEED}" in spec.spec, (
            f"--scale {scale}: spec for OCID {ocid!r} must mention the "
            f"locked seed (seed={LOCKED_PERMUTATION_SEED}); got: "
            f"{spec.spec!r}"
        )
        assert "operator inverted" in spec.spec, (
            f"--scale {scale}: spec for OCID {ocid!r} must describe the "
            f"operator inversion; got: {spec.spec!r}"
        )


def test_sidecar_ocids_match_diagnostic_arm_records(tmp_path: Path):
    """The sidecar's OCID keys exactly match the diagnostic-arm record
    set at each scale. This catches the failure mode where the sidecar
    is emitted but with the wrong record slice (e.g. main-arm OCIDs
    instead of diagnostic-arm OCIDs).

    Tests at dry-run scale only — the assertion shape is identical at
    phase-2, but at phase-2 the diagnostic-arm OCID set IS the locked
    100-OCID subset, which is covered by the scale-parametrized test
    above."""
    run_dir = _dispatch_dry(
        tmp_path, scale="dry-run", run_id="inverted-spec-ocid-match"
    )

    sidecar = run_dir / SIDECAR_FILENAME
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    sidecar_ocids = set(payload.keys())

    # Diagnostic arm bundles for the same run — every bundle's filename
    # is "<decision_id>.bundle.json" but the payload carries an "ocid"
    # field that's the source of truth.
    bundle_dir = run_dir / "diagnostic_primary"
    bundle_ocids: set[str] = set()
    for bundle_path in sorted(bundle_dir.glob("*.bundle.json")):
        with bundle_path.open("r", encoding="utf-8") as fp:
            bundle = json.load(fp)
        bundle_ocids.add(str(bundle["ocid"]))

    assert sidecar_ocids == bundle_ocids, (
        f"sidecar OCIDs and diagnostic_primary bundle OCIDs must match.\n"
        f"  in sidecar but not in bundles: "
        f"{sorted(sidecar_ocids - bundle_ocids)!r}\n"
        f"  in bundles but not in sidecar: "
        f"{sorted(bundle_ocids - sidecar_ocids)!r}"
    )
