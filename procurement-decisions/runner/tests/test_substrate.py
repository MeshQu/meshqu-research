"""
Substrate adapter unit tests.

Synthetic OCDS-shaped fixtures exercise every derivation function +
the main adapter. We deliberately use synthetic data rather than the
sanity_check_12_ocids.jsonl exclusion list — that data is reserved per
the conservative-read exclusion discipline.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from meshqu_runner.substrate import (
    ADAPTER_VERSION,
    AdaptedRecord,
    DECISION_TYPE,
    FieldProvenance,
    PA23_THRESHOLD_GBP_DEFAULT,
    derive_above_threshold,
    derive_conflict_of_interest_declaration,
    derive_contract_value,
    derive_direct_award_justification_present,
    derive_governed_by_pa23,
    derive_is_modification,
    derive_modification_value_ratio,
    derive_procurement_method_open_flag,
    derive_publication_delay_days,
    derive_supplier_id,
    ocds_to_decision_context,
    provenance_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ocds_record(**overrides: Any) -> dict[str, Any]:
    """A minimally valid OCDS release dict. Tests spread overrides to
    exercise specific derivation paths."""
    base: dict[str, Any] = {
        "ocid": "ocds-test-0001",
        "tag": ["award"],
        "tender": {
            "procurementMethod": "open",
            "value": {"amount": 250_000, "currency": "GBP"},
        },
        "awards": [
            {
                "id": "award-001",
                "date": "2026-01-15T00:00:00Z",
                "datePublished": "2026-01-25T00:00:00Z",
                "value": {"amount": 250_000, "currency": "GBP"},
                "suppliers": [{"id": "GB-COH-12345678", "name": "Example Ltd"}],
            }
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# publication_delay_days
# ---------------------------------------------------------------------------


class TestPublicationDelayDays:
    def test_happy_path(self):
        fp = derive_publication_delay_days(_ocds_record())
        assert fp.status == "proxy"
        assert fp.confidence == "medium"
        assert fp.value == 10
        # The proxy must be flagged in the detail — load-bearing for
        # substrate-honesty disclosure
        assert "signature" in fp.detail.lower() or "proxy" in fp.detail.lower()

    def test_absent_when_no_awards(self):
        fp = derive_publication_delay_days({"ocid": "x"})
        assert fp.status == "absent"
        assert fp.value is None

    def test_absent_when_datepublished_missing(self):
        fp = derive_publication_delay_days(
            _ocds_record(awards=[{"date": "2026-01-15"}])
        )
        assert fp.status == "absent"
        assert fp.value is None

    def test_handles_bare_date_strings(self):
        fp = derive_publication_delay_days(
            _ocds_record(
                awards=[
                    {
                        "date": "2026-01-01",
                        "datePublished": "2026-01-31",
                    }
                ]
            )
        )
        assert fp.value == 30

    def test_normalises_timezone_before_arithmetic(self):
        # Same UTC date but reported in different zones; the day-count
        # math should be identical.
        fp_utc = derive_publication_delay_days(
            _ocds_record(
                awards=[
                    {
                        "date": "2026-01-15T00:00:00Z",
                        "datePublished": "2026-01-25T00:00:00Z",
                    }
                ]
            )
        )
        fp_offset = derive_publication_delay_days(
            _ocds_record(
                awards=[
                    {
                        # 2026-01-15 14:00 UTC = 2026-01-15 in UTC after normalisation
                        "date": "2026-01-15T14:00:00+01:00",
                        "datePublished": "2026-01-25T14:00:00+01:00",
                    }
                ]
            )
        )
        # Both should produce 10 — TZ normalisation collapses to UTC date.
        assert fp_utc.value == fp_offset.value == 10


# ---------------------------------------------------------------------------
# governed_by_pa23
# ---------------------------------------------------------------------------


class TestGovernedByPa23:
    def test_post_commencement_returns_true_string(self):
        fp = derive_governed_by_pa23(_ocds_record())  # 2026-01-15 is post-PA23
        assert fp.value == "true"
        assert fp.status == "proxy"
        assert fp.confidence == "medium"

    def test_pre_commencement_returns_false_string(self):
        fp = derive_governed_by_pa23(
            _ocds_record(awards=[{"date": "2024-06-01", "datePublished": "2024-06-15"}])
        )
        assert fp.value == "false"

    def test_exactly_on_commencement_date_is_false(self):
        # Strict > comparison: same-day award is NOT PA23-governed (PA23
        # took effect FOR procurements started after 2025-02-24)
        fp = derive_governed_by_pa23(
            _ocds_record(awards=[{"date": "2025-02-24", "datePublished": "2025-03-01"}])
        )
        assert fp.value == "false"

    def test_emits_lowercase_string_never_boolean(self):
        fp = derive_governed_by_pa23(_ocds_record())
        # Critical regression test for F13 — F13 cross-over finding
        # depends on the substrate emitting STRINGS not JSON booleans
        assert isinstance(fp.value, str)
        assert fp.value in {"true", "false"}

    def test_absent_when_no_awards(self):
        fp = derive_governed_by_pa23({"ocid": "x"})
        assert fp.status == "absent"
        assert fp.value is None


# ---------------------------------------------------------------------------
# above_threshold
# ---------------------------------------------------------------------------


class TestAboveThreshold:
    def test_above_default_threshold(self):
        # 250k > 139k
        fp = derive_above_threshold(_ocds_record())
        assert fp.value == "true"
        assert fp.status == "proxy"

    def test_below_default_threshold(self):
        fp = derive_above_threshold(
            _ocds_record(tender={"value": {"amount": 50_000}})
        )
        assert fp.value == "false"

    def test_exactly_at_threshold_is_false(self):
        # Strict > — at-threshold contracts are NOT above-threshold
        fp = derive_above_threshold(
            _ocds_record(tender={"value": {"amount": PA23_THRESHOLD_GBP_DEFAULT}})
        )
        assert fp.value == "false"

    def test_fallback_to_award_value_when_tender_value_missing(self):
        record = _ocds_record(tender={"procurementMethod": "open"})  # no value
        fp = derive_above_threshold(record)
        assert fp.value == "true"  # falls back to awards[0].value.amount = 250k
        assert "awards[0].value.amount" in fp.detail

    def test_absent_when_no_amount_anywhere(self):
        fp = derive_above_threshold({"ocid": "x"})
        assert fp.status == "absent"
        assert fp.value is None

    def test_custom_threshold_knob(self):
        fp = derive_above_threshold(_ocds_record(), threshold_gbp=1_000_000)
        assert fp.value == "false"


# ---------------------------------------------------------------------------
# contract_value
# ---------------------------------------------------------------------------


class TestContractValue:
    def test_direct_ocds_path(self):
        fp = derive_contract_value(_ocds_record())
        assert fp.value == 250_000.0
        assert fp.status == "direct_ocds"
        assert fp.confidence == "high"

    def test_emits_float_not_string(self):
        # Numeric fields emitted as numbers — never strings (deterministic
        # normalisation requirement)
        fp = derive_contract_value(_ocds_record())
        assert isinstance(fp.value, float)

    def test_absent_when_value_missing(self):
        fp = derive_contract_value(_ocds_record(awards=[{"id": "x"}]))
        assert fp.status == "absent"
        assert fp.value is None

    def test_absent_when_non_numeric_value(self):
        fp = derive_contract_value(
            _ocds_record(awards=[{"value": {"amount": "not-a-number"}}])
        )
        assert fp.status == "absent"


# ---------------------------------------------------------------------------
# supplier_id
# ---------------------------------------------------------------------------


class TestSupplierId:
    def test_direct_ocds(self):
        fp = derive_supplier_id(_ocds_record())
        assert fp.value == "GB-COH-12345678"
        assert fp.status == "direct_ocds"

    def test_trims_whitespace(self):
        fp = derive_supplier_id(
            _ocds_record(awards=[{"suppliers": [{"id": "  GB-COH-12345678  "}]}])
        )
        assert fp.value == "GB-COH-12345678"

    def test_preserves_case(self):
        # Scheme prefixes are case-load-bearing in some publisher conventions
        fp = derive_supplier_id(
            _ocds_record(awards=[{"suppliers": [{"id": "GB-coh-12345678"}]}])
        )
        assert fp.value == "GB-coh-12345678"

    def test_absent_when_empty_string_after_trim(self):
        fp = derive_supplier_id(
            _ocds_record(awards=[{"suppliers": [{"id": "   "}]}])
        )
        assert fp.status == "absent"


# ---------------------------------------------------------------------------
# conflict_of_interest_declaration
# ---------------------------------------------------------------------------


class TestCOI:
    def test_always_absent(self):
        fp = derive_conflict_of_interest_declaration(_ocds_record())
        assert fp.status == "absent"
        assert fp.value is None
        # The detail should name PROC-004 so future readers grep their way
        # back to the rule this affects
        assert "PROC-004" in fp.detail


# ---------------------------------------------------------------------------
# procurement_method_open_flag
# ---------------------------------------------------------------------------


class TestProcurementMethodOpenFlag:
    def test_emitted_when_open(self):
        fp = derive_procurement_method_open_flag(_ocds_record())
        assert fp.value == "true"
        assert fp.status == "derived"

    def test_absent_when_method_not_open(self):
        # Absent here is the rule-fires-when-when-matches state
        fp = derive_procurement_method_open_flag(
            _ocds_record(tender={"procurementMethod": "direct"})
        )
        assert fp.status == "absent"
        assert fp.value is None

    def test_absent_when_method_missing(self):
        fp = derive_procurement_method_open_flag(_ocds_record(tender={}))
        assert fp.status == "absent"


# ---------------------------------------------------------------------------
# direct_award_justification_present
# ---------------------------------------------------------------------------


class TestDirectAwardJustificationPresent:
    def test_true_when_transparency_relationship(self):
        fp = derive_direct_award_justification_present(
            _ocds_record(
                relatedProcesses=[{"id": "rel-1", "relationship": "transparency"}]
            )
        )
        assert fp.value == "true"
        # Heuristic — confidence='low' because of known false-negative mode
        assert fp.confidence == "low"

    def test_true_when_relationship_array_contains_directAward(self):
        fp = derive_direct_award_justification_present(
            _ocds_record(
                relatedProcesses=[
                    {"id": "rel-1", "relationship": ["framework", "directAward"]}
                ]
            )
        )
        assert fp.value == "true"

    def test_false_when_no_related_processes(self):
        fp = derive_direct_award_justification_present(_ocds_record())
        assert fp.value == "false"

    def test_false_when_unrelated_relationships(self):
        fp = derive_direct_award_justification_present(
            _ocds_record(relatedProcesses=[{"relationship": "planning"}])
        )
        assert fp.value == "false"


# ---------------------------------------------------------------------------
# is_modification
# ---------------------------------------------------------------------------


class TestIsModification:
    def test_true_on_contractAmendment_tag(self):
        fp = derive_is_modification(_ocds_record(tag=["contractAmendment"]))
        assert fp.value == "true"

    def test_true_on_awardAmendment_tag(self):
        fp = derive_is_modification(_ocds_record(tag=["awardAmendment"]))
        assert fp.value == "true"

    def test_false_on_standard_award_tag(self):
        fp = derive_is_modification(_ocds_record(tag=["award"]))
        assert fp.value == "false"

    def test_handles_string_tag_not_array(self):
        # OCDS allows tag to be a scalar string in some shapes
        fp = derive_is_modification(_ocds_record(tag="contractAmendment"))
        assert fp.value == "true"


# ---------------------------------------------------------------------------
# modification_value_ratio
# ---------------------------------------------------------------------------


class TestModificationValueRatio:
    def test_ratio_from_previousValue(self):
        fp = derive_modification_value_ratio(
            _ocds_record(
                amendments=[
                    {
                        "value": {"amount": 150_000},
                        "previousValue": {"amount": 300_000},
                    }
                ]
            )
        )
        assert fp.value == pytest.approx(0.5)
        assert fp.status == "derived"

    def test_ratio_from_contracts_fallback(self):
        fp = derive_modification_value_ratio(
            _ocds_record(
                amendments=[{"value": {"amount": 100_000}}],
                contracts=[{"value": {"amount": 1_000_000}}],
            )
        )
        assert fp.value == pytest.approx(0.1)

    def test_absent_when_no_amendments(self):
        fp = derive_modification_value_ratio(_ocds_record())
        assert fp.status == "absent"
        assert fp.value is None

    def test_absent_when_original_unknown(self):
        fp = derive_modification_value_ratio(
            _ocds_record(amendments=[{"value": {"amount": 100_000}}])
        )
        assert fp.status == "absent"


# ---------------------------------------------------------------------------
# Main adapter — DecisionContext + SubstrateProvenance together
# ---------------------------------------------------------------------------


class TestOcdsToDecisionContext:
    def test_emits_canonical_decision_type(self):
        adapted = ocds_to_decision_context(_ocds_record())
        assert adapted.context["decision_type"] == DECISION_TYPE

    def test_no_silent_defaults_for_absent_fields(self):
        # Minimal record — most fields should be absent
        adapted = ocds_to_decision_context({"ocid": "ocds-test-empty"})
        # No-silent-defaults rule: absent fields must NOT appear in
        # DecisionContext.fields. They must appear in provenance with
        # status='absent' so coverage is computable.
        for fp in adapted.substrate_notes.values():
            if fp.status == "absent":
                # The field's key must not be in DecisionContext.fields
                # (provenance keys match field keys verbatim)
                key = next(
                    k for k, v in adapted.substrate_notes.items() if v is fp
                )
                assert key not in adapted.context["fields"], (
                    f"Field {key!r} was absent but leaked into "
                    f"DecisionContext.fields — silent default detected"
                )

    def test_full_record_emits_all_derivable_fields(self):
        record = _ocds_record(
            tag=["contractAmendment"],
            amendments=[
                {"value": {"amount": 50_000}, "previousValue": {"amount": 200_000}}
            ],
            relatedProcesses=[{"relationship": "transparency"}],
        )
        adapted = ocds_to_decision_context(record)
        fields_emitted = set(adapted.context["fields"].keys())
        # COI is never derivable from OCDS
        assert "conflict_of_interest_declaration" not in fields_emitted
        # Everything else should be derivable from this fixture
        expected = {
            "publication_delay_days",
            "governed_by_pa23",
            "above_threshold",
            "contract_value",
            "supplier_id",
            "procurement_method_open_flag",
            "direct_award_justification_present",
            "is_modification",
            "modification_value_ratio",
        }
        assert fields_emitted == expected

    def test_metadata_carries_ocid_and_adapter_version(self):
        adapted = ocds_to_decision_context(_ocds_record())
        meta = adapted.context["metadata"]
        assert meta["ocid"] == "ocds-test-0001"
        assert meta["adapter_version"] == ADAPTER_VERSION
        assert meta["experiment_substrate"] == "uk_contracts_finder_ocds"

    def test_provenance_contains_every_canonical_field(self):
        # Even on a minimal record, the provenance dict has every field
        # (with status='absent' where applicable) so coverage statistics
        # are computable across the corpus.
        adapted = ocds_to_decision_context({"ocid": "ocds-test-min"})
        expected_keys = {
            "publication_delay_days",
            "governed_by_pa23",
            "above_threshold",
            "contract_value",
            "supplier_id",
            "conflict_of_interest_declaration",
            "procurement_method_open_flag",
            "direct_award_justification_present",
            "is_modification",
            "modification_value_ratio",
        }
        assert set(adapted.substrate_notes.keys()) == expected_keys

    def test_booleans_always_strings_in_emitted_fields(self):
        # F13 regression — every boolean-shaped field comes out as a
        # lowercase "true"/"false" string, never a JSON boolean
        adapted = ocds_to_decision_context(_ocds_record())
        boolean_fields = {
            "governed_by_pa23",
            "above_threshold",
            "direct_award_justification_present",
            "is_modification",
        }
        for field_name in boolean_fields:
            v = adapted.context["fields"].get(field_name)
            if v is not None:
                assert isinstance(v, str), f"{field_name}={v!r} should be a string"
                assert v in {"true", "false"}, f"{field_name}={v!r}"

    def test_above_threshold_knob_propagates(self):
        adapted = ocds_to_decision_context(
            _ocds_record(),
            above_threshold_gbp=1_000_000,
        )
        # 250k > 1M is false
        assert adapted.context["fields"]["above_threshold"] == "false"


# ---------------------------------------------------------------------------
# Coverage summary
# ---------------------------------------------------------------------------


class TestProvenanceSummary:
    def test_aggregates_status_counts(self):
        adapted = ocds_to_decision_context(_ocds_record())
        summary = provenance_summary(adapted.substrate_notes)
        # All four buckets should be present (zero-valued ones too) so
        # downstream stats arithmetic doesn't need defensive defaulting
        assert set(summary.keys()) == {"direct_ocds", "derived", "proxy", "absent"}
        # Sum must equal total field count
        assert sum(summary.values()) == len(adapted.substrate_notes)


# ---------------------------------------------------------------------------
# Contract conformance — the emitted DecisionContext matches the schema
# ---------------------------------------------------------------------------


class TestContractConformance:
    def test_contract_schema_file_exists(self):
        # The canonical contract must be on disk where the brief promises
        contract = Path(__file__).resolve().parents[1] / "contracts" / "decision_context.schema.json"
        assert contract.exists(), f"Canonical contract missing at {contract}"
        # And parses as valid JSON
        data = json.loads(contract.read_text())
        assert "DecisionContext" in data["$defs"]
        assert "FieldProvenance" in data["$defs"]

    def test_emitted_fields_match_contract_keys(self):
        # The contract enumerates the canonical field set. The adapter
        # must never emit a field outside that set (would mean schema drift).
        contract = Path(__file__).resolve().parents[1] / "contracts" / "decision_context.schema.json"
        data = json.loads(contract.read_text())
        contract_field_keys = set(
            data["$defs"]["DecisionContext"]["properties"]["fields"]["properties"].keys()
        )

        adapted = ocds_to_decision_context(_ocds_record())
        emitted_keys = set(adapted.context["fields"].keys())

        # Emitted keys must be a subset of contract keys (no rogue fields)
        rogue = emitted_keys - contract_field_keys
        assert not rogue, f"Adapter emitted fields not in the contract: {rogue}"
