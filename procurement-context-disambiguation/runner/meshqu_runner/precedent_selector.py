"""Deterministic kNN precedent selector for L3.

Given a target procurement record + the loaded frozen E1 archive, returns
the k nearest-neighbour precedent records. "Nearest" is Hamming distance
over a small, locked categorical feature vector. Tie-break is OCID
ascending — this is what guarantees the function is deterministic
across re-runs (`select_precedents(t, archive, k=4)` returns the same
list of OCIDs every time).

Feature vector (LOCKED at Stage A — see
`planning/context_ladder_design.md` §L3 and `decision_log.md`):

  1. **contract_value_band** — 4 bands:
       <£100k / £100k–£500k / £500k–£10M / >£10M
  2. **procurement_method_open_flag** — categorical:
       "true" / "false" / None (None covers the "absent" status that
       264 of 283 archive records carry; only 19 records have
       "true" and zero have explicit "false")
  3. **regime** — categorical:
       "PA23" (post 24 Feb 2025) / "PCR_2015"

The vector is small on purpose. Adding numeric features (publication
delay, contract-value distance) would make the function non-Hamming
and require careful normalisation; the writeup defends the locked shape
as the minimum that captures comparable-context similarity. Any change
must surface in `decision_log.md` BEFORE altering this code.

Self-exclusion is mandatory: the target record cannot be its own
precedent. Comparison is by OCID.

The function does NOT make any HTTP calls. Everything operates on the
in-memory archive dict. Tests assert no transport is touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .precedent_archive import PrecedentRecord


# ---------------------------------------------------------------------------
# Stage A — locked k value
# ---------------------------------------------------------------------------

DEFAULT_PRECEDENT_COUNT = 4
"""Stage A authoring (§3) allowed 3–5 precedents per record; the build
package signature defaults k=4. Locked at run time via the L3 handler
(see `level_l3.py`). The full grid budget assumed k=4 when estimating
~1,500 tokens added at L3."""


# ---------------------------------------------------------------------------
# Target record adaptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetFeatures:
    """The feature-vector projection of a target record.

    Targets come from E2 substrate (the runner records) and carry the
    same field set as the archive — but they're plain dicts, not
    PrecedentRecord. This dataclass normalises them onto the same
    categorical feature space the archive records expose."""

    ocid: str | None
    contract_value_band: str
    procurement_method_open_flag: str | None
    regime: str

    @classmethod
    def from_target(cls, target_record: Mapping[str, object]) -> "TargetFeatures":
        """Project a target record onto the locked feature vector.

        Two record shapes are supported:

          1. E2 smoke fixture: `{ocid, fields: {...}, ...}` — the same
             shape `multi_pass.py` consumes.
          2. PrecedentRecord — for self-similarity / round-trip tests.

        The selector is intentionally tolerant of missing fields:
        contract_value defaults to 0 (lands in the <£100k band) and
        procurement_method_open_flag to None (the "absent" category).
        governed_by_pa23 is treated as PA23 by default — the same
        post-PA23-commencement assumption E1 used."""
        if isinstance(target_record, PrecedentRecord):
            return cls(
                ocid=target_record.ocid,
                contract_value_band=target_record.contract_value_band,
                procurement_method_open_flag=target_record.procurement_method_open_flag,
                regime=target_record.regime_proxy,
            )

        ocid = _extract_ocid(target_record)
        fields = _extract_fields(target_record)

        contract_value = fields.get("contract_value", 0)
        try:
            contract_value = float(contract_value)
        except (TypeError, ValueError):
            contract_value = 0.0

        governed_by_pa23 = fields.get("governed_by_pa23")
        regime = "PA23" if governed_by_pa23 == "true" else "PCR_2015"

        method_flag = fields.get("procurement_method_open_flag")
        if method_flag is not None and not isinstance(method_flag, str):
            method_flag = str(method_flag)

        return cls(
            ocid=ocid,
            contract_value_band=_band_for_value(contract_value),
            procurement_method_open_flag=method_flag,
            regime=regime,
        )


# ---------------------------------------------------------------------------
# Selector — the public entry point
# ---------------------------------------------------------------------------


def select_precedents(
    target_record: Mapping[str, object],
    archive: Mapping[str, PrecedentRecord],
    k: int = DEFAULT_PRECEDENT_COUNT,
) -> list[PrecedentRecord]:
    """Return up to k nearest-neighbour precedents from `archive`.

    Algorithm:

      1. Project the target onto the locked feature vector.
      2. For every archive entry except the target itself (by OCID),
         compute Hamming distance over the feature vector (0 = perfect
         match, 3 = all categorical features differ).
      3. Sort by (distance asc, OCID asc). The OCID tie-break is what
         makes the function deterministic across re-runs even when
         many archive entries share the same distance.
      4. Return the top k.

    Determinism contract: same `(target_record, archive, k)` → same
    list, byte-identical, across processes and Python interpreters.
    Tested explicitly in `tests/test_precedent_selector.py`.

    If the archive has fewer than k candidates after self-exclusion,
    returns all of them and the caller's L3 handler is responsible for
    deciding whether a sub-k precedent block is acceptable. (For the
    283-record archive against any of the 283 OCIDs, k=4 always returns
    exactly 4.)

    Self-exclusion is by OCID only — two records with the same OCID
    cannot exist in a valid archive (the loader raises on duplicates),
    so this is single-pass safe.
    """
    if k <= 0:
        return []

    target_features = TargetFeatures.from_target(target_record)
    target_ocid = target_features.ocid

    scored: list[tuple[int, str, PrecedentRecord]] = []
    for ocid, record in archive.items():
        if target_ocid is not None and ocid == target_ocid:
            # Self-exclusion. The target record CAN appear in the
            # archive (e.g. when E2 re-evaluates an E1 record at a
            # higher level); it MUST NOT be its own precedent.
            continue
        distance = _hamming_distance(target_features, record)
        scored.append((distance, ocid, record))

    # Sort: distance ascending, OCID ascending. OCID tie-break is the
    # entire determinism guarantee.
    scored.sort(key=lambda item: (item[0], item[1]))

    return [record for _distance, _ocid, record in scored[:k]]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _hamming_distance(
    target: TargetFeatures, candidate: PrecedentRecord
) -> int:
    """Categorical Hamming over the locked 3-dim feature vector.

    Each mismatch adds 1. Missing/None values compare equal to other
    missing values (None == None is treated as a match) — this lets a
    procurement-method-absent target match procurement-method-absent
    archive records, which is the desired behaviour given the archive
    has 264/283 records with the flag absent."""
    distance = 0
    if target.contract_value_band != candidate.contract_value_band:
        distance += 1
    if target.procurement_method_open_flag != candidate.procurement_method_open_flag:
        distance += 1
    if target.regime != candidate.regime_proxy:
        distance += 1
    return distance


def _band_for_value(value: float) -> str:
    """Mirror of PrecedentRecord.contract_value_band — used when the
    target is a plain dict, not a PrecedentRecord. Bands locked at
    Stage A; do not edit without a decision_log entry."""
    if value < 100_000:
        return "<100k"
    if value < 500_000:
        return "100k-500k"
    if value < 10_000_000:
        return "500k-10M"
    return ">10M"


def _extract_ocid(record: Mapping[str, object]) -> str | None:
    """OCID extraction mirrors `multi_pass._extract_ocid` — top-level
    `ocid` then `metadata.ocid`. Kept duplicated rather than imported
    to avoid pulling the orchestrator into the selector's surface."""
    ocid = record.get("ocid")
    if isinstance(ocid, str):
        return ocid
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        meta_ocid = metadata.get("ocid")
        if isinstance(meta_ocid, str):
            return meta_ocid
    return None


def _extract_fields(record: Mapping[str, object]) -> Mapping[str, object]:
    """Tolerant fields extractor for target records. E2's per-record
    shape carries a top-level `fields` dict (smoke fixture pattern); a
    PrecedentRecord is handled by `TargetFeatures.from_target` before
    this is reached."""
    fields = record.get("fields")
    if isinstance(fields, dict):
        return fields
    return {}
