"""Lock-in test — every promoted E3 arm handler MUST compose record
content into its rendered prompt.

## What this locks in

The 2026-05-28 smoke run produced 14/14 cryptographically-verified
receipts but the substantive experimental signal was empty: all six
arms produced "no procurement record provided" / "record contains no
fields" refusals. Root cause: ``l4_without_nudge``, ``diagnostic_primary``
and ``diagnostic_claude`` handlers returned an envelope-only string and
ignored the ``record`` argument — the per-record base user message was
never composed in. ``l4_with_nudge`` (the in-runner sanity-comparison
baseline, off the smoke matrix but registered) had the identical broken
shape and was folded into the same fix on inspection. (``arm_a`` /
``arm_b`` / ``arm_c`` were always record-composing; they were never
broken. They are parametrised here as regression sentinels — if one of
them ever drifts to envelope-only, this test fires.)

See ``arms/diagnostic.py``, ``arms/l4_without_nudge.py``, and
``multi_pass.py:588-592`` ("Arm handler returns the FULLY rendered user
message — no additive composition, no level prefix. The handler is
self-contained.") for the contract this test enforces.

## The assertions

For each of the seven promoted arms (``arm_a``, ``arm_b``, ``arm_c``,
``l4_without_nudge``, ``l4_with_nudge``, ``diagnostic_primary``,
``diagnostic_claude``) the test:

1. Renders the same arm against two records whose field content carries
   distinctive markers (``DISTINCTIVE-MARKER-ALPHA-12345`` /
   ``DISTINCTIVE-MARKER-BRAVO-67890``).
2. Asserts the marker for each record appears verbatim in that record's
   rendered prompt (and the OTHER record's marker does NOT appear).
3. Asserts the two rendered prompts have distinct SHA-256s — a
   record-independent handler would produce identical bytes.

## Out-of-scope arms

``l0_baseline`` is NOT on the smoke matrix or the planned dry-run /
full-run; it's retained for the dry-run freshness check. It is excluded
from the parametrize because it doesn't ride on Phase-1 experimental
data. If it ever gets promoted to the experimental grid, add it to
``PROMOTED_ARMS`` below.

``l4_with_nudge`` is included here even though it's off the smoke /
dry-run / full-run matrices — it's the in-runner sanity-comparison
baseline for ``l4_without_nudge``, and a future ad-hoc invocation (head-
to-head comparison, Phase-3 re-analysis) shouldn't be able to silently
produce a degenerate result. The lock-in discipline covers every
registered arm that touches experimental substance, not just arms on
the current grid.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

import pytest

from meshqu_runner.arms import HANDLERS


PROMOTED_ARMS: tuple[str, ...] = (
    "arm_a",
    "arm_b",
    "arm_c",
    "l4_without_nudge",
    "l4_with_nudge",
    "diagnostic_primary",
    "diagnostic_claude",
)
"""The seven arms that touch Phase-1 experimental substance. Six of
them ride on the smoke matrix (``scripts/smoke_e3.py:MAIN_ARMS +
DIAGNOSTIC_ARMS``) + the planned dry-run + full-run matrices in the
E3 package spec. ``l4_with_nudge`` is off those matrices but is
registered as the in-runner sanity-comparison baseline for
``l4_without_nudge`` — held to the same composition contract here so
ad-hoc invocations can't silently degrade."""


_MARKER_ALPHA = "DISTINCTIVE-MARKER-ALPHA-12345"
_MARKER_BRAVO = "DISTINCTIVE-MARKER-BRAVO-67890"


def _make_record(*, ocid: str, marker: str, supplier: str, note_tag: str) -> dict[str, Any]:
    """Build a minimal record carrying ``marker`` somewhere the
    composition path is guaranteed to touch.

    ``build_user_message`` serialises ``fields`` + ``substrate_notes``
    into canonical JSON, so putting the marker inside ``fields`` is the
    most direct way to assert "the record was composed in". The
    substrate_notes carry a secondary tag for completeness.
    """
    return {
        "ocid": ocid,
        "decision_type": "procurement_decision",
        "fields": {
            "contract_value": marker,
            "supplier_id": supplier,
        },
        "substrate_notes": {
            "contract_value": {"status": "parsed", "detail": note_tag},
        },
        "metadata": {"ocid": ocid},
    }


def _call_handler(arm_name: str, record: Mapping[str, Any]) -> str:
    """Call ``HANDLERS[arm_name](record, ...)`` tolerantly across the
    arm-handler signature variants.

    ``arm_a``/``arm_b`` take an ``archive=`` kwarg (the precedent
    archive); ``arm_c`` and the L4/diagnostic arms don't. The empty
    archive is fine because ``arm_a``/``arm_b`` fall back to an empty
    L3 block on empty input — but they STILL compose the record content
    into the user message, which is what we assert here.
    """
    handler = HANDLERS[arm_name]
    try:
        return handler(record, archive={})
    except TypeError:
        return handler(record)


@pytest.mark.parametrize("arm_name", PROMOTED_ARMS)
def test_handler_composes_record_content(arm_name: str) -> None:
    """Different records MUST produce different rendered prompts.

    Locks in the fix from the 2026-05-28 smoke read where
    ``l4_without_nudge`` + ``diagnostic_primary`` + ``diagnostic_claude``
    were discovered to ignore the ``record`` argument. ``arm_a``,
    ``arm_b``, ``arm_c`` are included as regression sentinels — they
    were never broken, but if one ever drifts to envelope-only this
    test fires.
    """
    rec_alpha = _make_record(
        ocid="STUB-OCID-ALPHA",
        marker=_MARKER_ALPHA,
        supplier="SUPPLIER-ALPHA",
        note_tag="TAG-ALPHA",
    )
    rec_bravo = _make_record(
        ocid="STUB-OCID-BRAVO",
        marker=_MARKER_BRAVO,
        supplier="SUPPLIER-BRAVO",
        note_tag="TAG-BRAVO",
    )

    p_alpha = _call_handler(arm_name, rec_alpha)
    p_bravo = _call_handler(arm_name, rec_bravo)

    assert _MARKER_ALPHA in p_alpha, (
        f"arm {arm_name!r} did not include alpha record field content in "
        f"its rendered prompt — handler is envelope-only / record-independent"
    )
    assert _MARKER_BRAVO in p_bravo, (
        f"arm {arm_name!r} did not include bravo record field content in "
        f"its rendered prompt — handler is envelope-only / record-independent"
    )
    assert _MARKER_BRAVO not in p_alpha, (
        f"arm {arm_name!r}: bravo marker bled into the alpha prompt — "
        f"handler is leaking state between calls"
    )
    assert _MARKER_ALPHA not in p_bravo, (
        f"arm {arm_name!r}: alpha marker bled into the bravo prompt — "
        f"handler is leaking state between calls"
    )

    sha_alpha = hashlib.sha256(p_alpha.encode("utf-8")).hexdigest()
    sha_bravo = hashlib.sha256(p_bravo.encode("utf-8")).hexdigest()
    assert sha_alpha != sha_bravo, (
        f"arm {arm_name!r} produced identical SHA-256 across two distinct "
        f"records ({sha_alpha}) — the handler is record-independent. "
        f"See arms/diagnostic.py + arms/l4_without_nudge.py for the "
        f"composition contract."
    )
