"""Lock-in test — every promoted E3 arm handler MUST compose record
content into its rendered prompt.

## What this locks in

The 2026-05-28 smoke run produced 14/14 cryptographically-verified
receipts but the substantive experimental signal was empty: all six
arms produced "no procurement record provided" / "record contains no
fields" refusals. Root cause: ``l4_without_nudge``, ``diagnostic_primary``
and ``diagnostic_claude`` handlers returned an envelope-only string and
ignored the ``record`` argument — the per-record base user message was
never composed in. (``arm_a``/``arm_b``/``arm_c`` were always
record-composing; they were never broken. They are parametrised here as
regression sentinels — if one of them ever drifts to envelope-only,
this test fires.)

See ``arms/diagnostic.py``, ``arms/l4_without_nudge.py``, and
``multi_pass.py:588-592`` ("Arm handler returns the FULLY rendered user
message — no additive composition, no level prefix. The handler is
self-contained.") for the contract this test enforces.

## The assertions

For each of the six promoted arms (``arm_a``, ``arm_b``, ``arm_c``,
``l4_without_nudge``, ``diagnostic_primary``, ``diagnostic_claude``) the
test:

1. Renders the same arm against two records whose field content carries
   distinctive markers (``DISTINCTIVE-MARKER-ALPHA-12345`` /
   ``DISTINCTIVE-MARKER-BRAVO-67890``).
2. Asserts the marker for each record appears verbatim in that record's
   rendered prompt (and the OTHER record's marker does NOT appear).
3. Asserts the two rendered prompts have distinct SHA-256s — a
   record-independent handler would produce identical bytes.

## Out-of-scope arms

``l4_with_nudge`` and ``l0_baseline`` are NOT in the promoted-arms list
in the smoke matrix or the planned dry-run / full-run. ``l4_with_nudge``
is a "sanity-comparison" handler kept for in-runner diff observation
(see its docstring in ``arms/l4_without_nudge.py``). ``l0_baseline`` is
retained for the dry-run freshness check. Neither rides on Phase-1
experimental data, so they are excluded here. If either ever gets
promoted to the experimental grid, add them to ``PROMOTED_ARMS`` below.
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
    "diagnostic_primary",
    "diagnostic_claude",
)
"""The six arms that ride on Phase-1 experimental data. Mirrors the
smoke matrix (``scripts/smoke_e3.py:MAIN_ARMS + DIAGNOSTIC_ARMS``) and
the planned dry-run + full-run matrices in the E3 package spec."""


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
