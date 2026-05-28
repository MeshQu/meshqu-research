"""
OCDS → MeshQu DecisionContext substrate adapter.

Transforms UK Contracts Finder OCDS records into the DecisionContext shape
the ratified experiment policy expects (policy 900996de-… on staging,
tenant experiment-procurement 243f19a5-…, 6 rules signed under
meshqu-experiment-procurement-2026-05).

**Canonical contract**: `runner/contracts/decision_context.schema.json`.
This module is the authoritative producer; the Inspect AI eval loop is
the verbatim consumer.

Per-field provenance envelope (per planning brief's "field confidence /
derivation integrity" requirement): every emitted field carries a
status ∈ {direct_ocds, derived, proxy, absent} and a confidence ∈
{high, medium, low}. Aggregated per record into substrate_notes for
decision_traces.jsonl, so the writeup can statistically analyse
"disagreement rate on direct fields vs disagreement rate on proxy
fields".

No-silent-defaults rule: if a field cannot be derived from this record,
it is emitted as `absent` in the provenance envelope and OMITTED from
DecisionContext.fields entirely. We never coerce missing data into
"safe" defaults — doing so destroys the substrate-honesty claim.

Deterministic normalisation:
- ISO dates parsed to UTC before arithmetic
- Numeric fields emitted as JSON numbers (never strings)
- Optional absent fields emitted as null in the provenance envelope
  (omitted from DecisionContext.fields)
- String booleans emitted lowercase EXACTLY: "true" / "false"
- String identifiers (supplier_id) trimmed, original casing preserved
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Mapping

# ---------------------------------------------------------------------------
# Constants. Pinned here so the writeup can quote them; bumping requires
# explicit code change + ADAPTER_VERSION bump.
# ---------------------------------------------------------------------------

PA23_THRESHOLD_GBP_DEFAULT = 139_000.0
"""Sub-central services threshold under PA23 Schedule 1. Used as the
conservative-default above-threshold proxy because the OCDS records don't
consistently expose contracting-authority tier or works-vs-services in a
way the adapter can trust on every record. The writeup's substrate-
honesty subsection notes this conservative choice."""

PA23_COMMENCEMENT_DATE = date(2025, 2, 24)
"""Date PA23 took effect for new procurements. Used as the regime-via-
award-date proxy: awards[0].date > this date is treated as PA23-governed."""

ADAPTER_VERSION = "0.1.0"
"""Bumped on substantive derivation changes. Bound into the receipt's
metadata so the writeup can cite which adapter version produced the corpus."""

DECISION_TYPE = "procurement_decision"
"""Locked at the contract — every record uses the same decision_type.
Selects the experiment policy from the tenant's policy set."""


# ---------------------------------------------------------------------------
# Per-field provenance envelope
# (matches FieldProvenance in contracts/decision_context.schema.json)
# ---------------------------------------------------------------------------

ProvenanceStatus = Literal["direct_ocds", "derived", "proxy", "absent"]
ProvenanceConfidence = Literal["high", "medium", "low"]


@dataclass
class FieldProvenance:
    """Per-field provenance envelope. The substrate adapter produces one
    of these per derivable field for every record (including fields that
    are absent for THIS record — `status='absent'` makes coverage
    computable across the corpus).

    `value` is the emitted value as it appears in DecisionContext.fields.
    Omitted (set to None) when status='absent'.
    """

    status: ProvenanceStatus
    confidence: ProvenanceConfidence
    detail: str
    value: Any = None


@dataclass
class AdaptedRecord:
    """The substrate adapter's per-record output.

    `context` is passed verbatim to MeshQu /v1/decisions/record as the
    request body's `context` field. `substrate_notes` is logged into the
    decision_traces.jsonl row's `substrate_notes` field, providing the
    audit trail for derivation provenance.
    """

    ocid: str | None
    context: dict[str, Any]
    substrate_notes: dict[str, FieldProvenance] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers — deterministic normalisation
# ---------------------------------------------------------------------------


def _parse_iso_date(value: Any) -> date | None:
    """Tolerant ISO-8601 date parse. Always UTC; the s.53 timing math
    operates on dates not datetimes, so timezone is collapsed before
    extracting the date component.

    Returns `None` for any input we can't confidently parse. Caller
    treats None as 'field absent' — never coerces to a sentinel date."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Strip trailing Z so fromisoformat (Py 3.10) handles it; 3.11+
    # accepts Z natively but the explicit strip is harmless.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        # Normalise to UTC before taking the date component so date math
        # is stable across publishers that may report in local timezones.
        if dt.tzinfo is None:
            return dt.date()
        return dt.astimezone(timezone.utc).date()
    except ValueError:
        # Bare date fallback — OCDS occasionally has YYYY-MM-DD strings
        # in award.date without a time component.
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def _canonicalise_supplier_id(value: Any) -> str | None:
    """Trim outer whitespace; preserve original casing (OCDS supplier IDs
    are typically Companies House numbers or scheme-prefixed identifiers
    where case can be load-bearing — `GB-COH-12345678` is not equivalent
    to `gb-coh-12345678` in some publisher schemes)."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


# ---------------------------------------------------------------------------
# Field derivations — pure functions, easy to test.
# Each returns FieldProvenance with status + confidence + detail + value.
# ---------------------------------------------------------------------------


def derive_publication_delay_days(
    record: Mapping[str, Any],
) -> FieldProvenance:
    """awards[0].datePublished − awards[0].date in days. status='proxy'
    because the award date is a documented substrate proxy for contract
    signature date (the actual statutory reference point per PA23 s.53(1))."""

    awards = record.get("awards") or []
    if not awards:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail="no awards[] in record",
        )

    award = awards[0]
    published = _parse_iso_date(award.get("datePublished"))
    awarded = _parse_iso_date(award.get("date"))

    if published is None or awarded is None:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=(
                f"datePublished={award.get('datePublished')!r} "
                f"date={award.get('date')!r} — both required, at least one unparseable"
            ),
        )

    delta_days = (published - awarded).days
    return FieldProvenance(
        status="proxy",
        confidence="medium",
        detail=(
            f"(awards[0].datePublished − awards[0].date) = "
            f"({published.isoformat()} − {awarded.isoformat()}) = {delta_days} days "
            f"[award date as signature-date proxy per substrate-honesty disclosure]"
        ),
        value=delta_days,
    )


def derive_governed_by_pa23(record: Mapping[str, Any]) -> FieldProvenance:
    """`'true'` if awards[0].date > 2025-02-24 (PA23 commencement), else
    `'false'`. status='proxy' — 96% of OCDS records carry no regime marker;
    award-date-after-commencement is the only reliable proxy."""

    awards = record.get("awards") or []
    if not awards:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail="no awards[] in record — cannot apply award-date proxy",
        )

    awarded = _parse_iso_date(awards[0].get("date"))
    if awarded is None:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=f"awards[0].date={awards[0].get('date')!r} unparseable",
        )

    in_pa23 = awarded > PA23_COMMENCEMENT_DATE
    return FieldProvenance(
        status="proxy",
        confidence="medium",
        detail=(
            f"awards[0].date={awarded.isoformat()} {'>' if in_pa23 else '≤'} "
            f"PA23 commencement {PA23_COMMENCEMENT_DATE.isoformat()}"
        ),
        value="true" if in_pa23 else "false",
    )


def derive_above_threshold(
    record: Mapping[str, Any],
    threshold_gbp: float = PA23_THRESHOLD_GBP_DEFAULT,
) -> FieldProvenance:
    """`'true'` if tender.value.amount > sub-central-services threshold,
    else `'false'`. status='proxy' — single-threshold conservative choice
    documented in the module docstring."""

    amount: float | int | None = None
    source = ""

    tender = record.get("tender")
    if isinstance(tender, Mapping):
        tv = tender.get("value")
        if isinstance(tv, Mapping):
            candidate = tv.get("amount")
            if isinstance(candidate, (int, float)):
                amount = candidate
                source = "tender.value.amount"

    if amount is None:
        # Fallback to awards[0].value.amount — some OCDS publishers
        # populate the awarded value but leave tender value blank.
        awards = record.get("awards") or []
        if awards and isinstance(awards[0].get("value"), Mapping):
            candidate = awards[0]["value"].get("amount")
            if isinstance(candidate, (int, float)):
                amount = candidate
                source = "awards[0].value.amount (tender value absent)"

    if amount is None:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=(
                "neither tender.value.amount nor awards[0].value.amount populated "
                "— cannot determine threshold status"
            ),
        )

    above = amount > threshold_gbp
    return FieldProvenance(
        status="proxy",
        confidence="medium",
        detail=(
            f"{source}={amount} {'>' if above else '≤'} £{threshold_gbp:,.0f} "
            f"(PA23 Schedule 1 sub-central services threshold, conservative default)"
        ),
        value="true" if above else "false",
    )


def derive_contract_value(record: Mapping[str, Any]) -> FieldProvenance:
    """awards[0].value.amount as a JSON number. status='direct_ocds'."""

    awards = record.get("awards") or []
    if not awards:
        return FieldProvenance(
            status="absent", confidence="high", detail="no awards[] in record"
        )

    value_obj = awards[0].get("value") or {}
    amount = value_obj.get("amount") if isinstance(value_obj, Mapping) else None

    if not isinstance(amount, (int, float)):
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=f"awards[0].value.amount={amount!r} not numeric",
        )

    return FieldProvenance(
        status="direct_ocds",
        confidence="high",
        detail=f"awards[0].value.amount = {amount}",
        value=float(amount),
    )


def derive_supplier_id(record: Mapping[str, Any]) -> FieldProvenance:
    """awards[0].suppliers[0].id, trimmed. status='direct_ocds'."""

    awards = record.get("awards") or []
    if not awards:
        return FieldProvenance(
            status="absent", confidence="high", detail="no awards[] in record"
        )

    suppliers = awards[0].get("suppliers") or []
    if not suppliers:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail="no awards[0].suppliers[] in record",
        )

    canonical = _canonicalise_supplier_id(suppliers[0].get("id"))
    if canonical is None:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=(
                f"awards[0].suppliers[0].id={suppliers[0].get('id')!r} "
                "not a non-empty string after trimming"
            ),
        )

    return FieldProvenance(
        status="direct_ocds",
        confidence="high",
        detail=f"awards[0].suppliers[0].id = {canonical!r} (trimmed; case preserved)",
        value=canonical,
    )


def derive_conflict_of_interest_declaration(
    _record: Mapping[str, Any],
) -> FieldProvenance:
    """Always absent. OCDS does not expose COI declarations in any standard
    field. PROC-004 cannot fire from this substrate alone — disclosed in
    the writeup's substrate-honesty subsection as a class of rule that
    requires a richer substrate to evaluate."""

    return FieldProvenance(
        status="absent",
        confidence="high",
        detail=(
            "not in OCDS schema for this substrate — PROC-004 (COI presence) "
            "cannot fire on UK Contracts Finder data. A richer substrate would "
            "be needed to evaluate this rule empirically."
        ),
    )


def derive_procurement_method_open_flag(
    record: Mapping[str, Any],
) -> FieldProvenance:
    """`'true'` when tender.procurementMethod == 'open'. Absent otherwise
    (PROC-005 is a presence rule — absence is the rule-fires state when
    the when clause matches). status='derived' — straightforward boolean
    check on a direct OCDS field."""

    tender = record.get("tender") or {}
    method = (
        tender.get("procurementMethod") if isinstance(tender, Mapping) else None
    )

    if method == "open":
        return FieldProvenance(
            status="derived",
            confidence="high",
            detail="tender.procurementMethod == 'open' → presence flag emitted",
            value="true",
        )

    return FieldProvenance(
        status="absent",
        confidence="high",
        detail=(
            f"tender.procurementMethod == {method!r} (not 'open') → "
            "flag deliberately omitted so PROC-005's presence check can fire "
            "if the when clause matches"
        ),
    )


def derive_direct_award_justification_present(
    record: Mapping[str, Any],
) -> FieldProvenance:
    """`'true'` if a related s.41 transparency notice is linked via OCDS
    relatedProcesses, else `'false'`. status='derived' but confidence='low'
    — known false-negative mode where the notice exists but isn't linked
    via relatedProcesses (different publisher conventions)."""

    related = record.get("relatedProcesses") or []
    for rel in related:
        if not isinstance(rel, Mapping):
            continue
        relationships = rel.get("relationship") or []
        if isinstance(relationships, str):
            relationships = [relationships]
        if any(
            isinstance(r, str)
            and ("transparency" in r.lower() or "direct" in r.lower())
            for r in relationships
        ):
            return FieldProvenance(
                status="derived",
                confidence="low",
                detail=(
                    f"relatedProcesses contains transparency/direct-award "
                    f"relationship: {relationships}"
                ),
                value="true",
            )

    return FieldProvenance(
        status="derived",
        confidence="low",
        detail=(
            "no transparency/direct-award relatedProcess link found "
            "(known false-negative mode — notice may exist but not be linked)"
        ),
        value="false",
    )


def derive_is_modification(record: Mapping[str, Any]) -> FieldProvenance:
    """`'true'` if OCDS tag includes a modification marker, else `'false'`.
    status='derived' direct from the OCDS release tag."""

    tags = record.get("tag") or []
    if isinstance(tags, str):
        tags = [tags]

    mod_markers = {"contractAmendment", "awardAmendment", "modification"}
    matched = [t for t in tags if isinstance(t, str) and t in mod_markers]

    if matched:
        return FieldProvenance(
            status="derived",
            confidence="high",
            detail=f"tag={tags} contains modification marker(s) {matched}",
            value="true",
        )

    return FieldProvenance(
        status="derived",
        confidence="high",
        detail=f"tag={tags} contains no modification marker",
        value="false",
    )


def derive_modification_value_ratio(
    record: Mapping[str, Any],
) -> FieldProvenance:
    """(amendments[0].value.amount / original contract value). status='derived'
    when computable, 'absent' otherwise. PROC-006 doesn't fire on non-
    modifications — that's expected, not a derivation failure."""

    amendments = record.get("amendments") or []
    if not amendments:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail="no amendments[] in record (PROC-006 doesn't fire on non-modifications)",
        )

    amendment = amendments[0]
    new_amount = (
        amendment.get("value", {}).get("amount")
        if isinstance(amendment.get("value"), Mapping)
        else None
    )

    original: float | None = None
    prev_value = (
        amendment.get("previousValue", {}).get("amount")
        if isinstance(amendment.get("previousValue"), Mapping)
        else None
    )
    if isinstance(prev_value, (int, float)) and prev_value > 0:
        original = float(prev_value)
        original_source = "amendments[0].previousValue.amount"
    elif isinstance(record.get("contracts"), list) and record["contracts"]:
        cv = (
            record["contracts"][0].get("value", {}).get("amount")
            if isinstance(record["contracts"][0].get("value"), Mapping)
            else None
        )
        if isinstance(cv, (int, float)) and cv > 0:
            original = float(cv)
            original_source = "contracts[0].value.amount"
        else:
            original_source = "(none)"
    else:
        original_source = "(none)"

    if not isinstance(new_amount, (int, float)) or original is None:
        return FieldProvenance(
            status="absent",
            confidence="high",
            detail=(
                f"amendment value={new_amount!r} original={original!r} "
                f"(from {original_source}) — ratio not computable"
            ),
        )

    ratio = float(new_amount) / original
    return FieldProvenance(
        status="derived",
        confidence="medium",
        detail=(
            f"amendments[0].value.amount {new_amount} ÷ original {original} "
            f"(from {original_source}) = {ratio:.4f}"
        ),
        value=ratio,
    )


# ---------------------------------------------------------------------------
# Main adapter — produces both DecisionContext + SubstrateProvenance
# ---------------------------------------------------------------------------


# Canonical field order. Substrate adapter emits provenance entries in
# this order for every record so the audit row's substrate_notes is
# deterministic + diff-friendly across the corpus.
_FIELD_ORDER: tuple[str, ...] = (
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
)

_DERIVERS = {
    "publication_delay_days": derive_publication_delay_days,
    "governed_by_pa23": derive_governed_by_pa23,
    "above_threshold": derive_above_threshold,
    "contract_value": derive_contract_value,
    "supplier_id": derive_supplier_id,
    "conflict_of_interest_declaration": derive_conflict_of_interest_declaration,
    "procurement_method_open_flag": derive_procurement_method_open_flag,
    "direct_award_justification_present": derive_direct_award_justification_present,
    "is_modification": derive_is_modification,
    "modification_value_ratio": derive_modification_value_ratio,
}


def ocds_to_decision_context(
    record: Mapping[str, Any],
    *,
    above_threshold_gbp: float = PA23_THRESHOLD_GBP_DEFAULT,
) -> AdaptedRecord:
    """Transform one OCDS record into a MeshQu DecisionContext payload.

    Returns (DecisionContext, SubstrateProvenance) bundled into AdaptedRecord.

    NO-SILENT-DEFAULTS rule (load-bearing for substrate honesty):
    if a field's derivation returns status='absent', it is OMITTED from
    DecisionContext.fields entirely. We never coerce missing data into
    `false` / 0 / "" / null — doing so would silently misrepresent what
    the substrate actually carries.
    """

    provenance: dict[str, FieldProvenance] = {}
    fields_out: dict[str, Any] = {}

    for name in _FIELD_ORDER:
        deriver = _DERIVERS[name]
        # The above_threshold deriver takes the threshold knob; all others
        # don't. Branch on the one special case rather than thread it
        # through every signature.
        if name == "above_threshold":
            fp = derive_above_threshold(record, threshold_gbp=above_threshold_gbp)
        else:
            fp = deriver(record)  # type: ignore[arg-type]
        provenance[name] = fp
        # No-silent-defaults: only emit fields that derived to a concrete
        # value. Absent fields stay out of DecisionContext.fields.
        if fp.status != "absent" and fp.value is not None:
            fields_out[name] = fp.value

    context = {
        "decision_type": DECISION_TYPE,
        "fields": fields_out,
        "metadata": {
            "ocid": record.get("ocid"),
            "experiment_substrate": "uk_contracts_finder_ocds",
            "adapter_version": ADAPTER_VERSION,
        },
    }

    return AdaptedRecord(
        ocid=record.get("ocid"),
        context=context,
        substrate_notes=provenance,
    )


def provenance_summary(
    provenance: Mapping[str, FieldProvenance],
) -> dict[str, int]:
    """Aggregate status counts. Used by the runner to log per-record
    derivation coverage and by post-run analysis to compute corpus-level
    statistics for the writeup's substrate-honesty subsection."""

    summary = {"direct_ocds": 0, "derived": 0, "proxy": 0, "absent": 0}
    for fp in provenance.values():
        summary[fp.status] += 1
    return summary


# ---------------------------------------------------------------------------
# Fetcher (Contracts Finder OCDS feed)
# ---------------------------------------------------------------------------


CONTRACTS_FINDER_OCDS_URL = (
    "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
)
"""UK Contracts Finder OCDS Search endpoint. No auth required; OGL-licensed.
Live schema verified 2026-05-17. The post-PA23 successor (UK Find a Tender
Service, https://www.find-tender.service.gov.uk/api/) is the upgrade path
for Follow-up A — see planning/writeup_outline.md."""

CONTRACTS_FINDER_PAGE_LIMIT = 100
"""Page size per request. Real API caps at 100 (confirmed via spike +
2026-05-17 re-probe). Caller-side `limit` is enforced after page
assembly so the loop never fetches more pages than needed."""


def fetch_ocds_records(
    *,
    feed_url: str = CONTRACTS_FINDER_OCDS_URL,
    since: date | None = None,
    until: date | None = None,
    limit: int | None = None,
    stages: str = "award",
    session: Any = None,
) -> list[dict[str, Any]]:
    """Fetch OCDS records from the Contracts Finder OCDS Search endpoint.

    Wire format (verified live 2026-05-17):

      GET <feed_url>?stages=award&publishedFrom=YYYY-MM-DD&publishedTo=YYYY-MM-DD&limit=100
      Response: { "releases": [...], "links": {"next": "<full url>"}, ... }

    Pagination uses `links.next`, which is a **full URL** with all query
    params baked in (NOT a cursor string the caller composes). The
    fetcher follows it verbatim until `links.next` is absent. Passing
    `params=` to the next-page request would APPEND, doubling
    parameters and breaking the cursor — so subsequent requests carry
    no extra params.

    Argument semantics:

      `feed_url` — defaults to CONTRACTS_FINDER_OCDS_URL. Override for
          tests + future Find-a-Tender migration.

      `since` / `until` — translated to `publishedFrom` / `publishedTo`.
          These scope by NOTICE PUBLICATION DATE, not award date.
          Records may have award dates outside the window; that's
          expected, the substrate adapter computes `governed_by_pa23`
          from the award date itself.

      `limit` — truncates the returned list AFTER assembly. The per-
          request page size is fixed at CONTRACTS_FINDER_PAGE_LIMIT;
          the fetcher just stops paginating once `len(out) >= limit`.

      `stages` — defaults to "award" (the experiment cares about
          awarded contracts). Other valid values per the API: "tender"
          (notices), "implementation" (contracts), "planning".

      `session` — requests.Session or test double for network control.

    Returns the flat list of release dicts across all fetched pages,
    optionally truncated to `limit`.
    """

    import requests  # local import — keeps this module importable without requests

    sess = session or requests.Session()
    out: list[dict[str, Any]] = []

    # Initial request — caller-side params.
    initial_params: dict[str, Any] = {
        "stages": stages,
        "limit": CONTRACTS_FINDER_PAGE_LIMIT,
    }
    if since:
        initial_params["publishedFrom"] = since.isoformat()
    if until:
        initial_params["publishedTo"] = until.isoformat()

    next_url: str | None = feed_url
    is_initial = True

    while next_url is not None:
        if is_initial:
            resp = sess.get(next_url, params=initial_params, timeout=30)
            is_initial = False
        else:
            # links.next already encodes every query param — passing
            # `params=` here would double-encode + break pagination.
            resp = sess.get(next_url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        releases = payload.get("releases") or []
        out.extend(releases)

        if limit is not None and len(out) >= limit:
            return out[:limit]

        next_url = (payload.get("links") or {}).get("next")

    return out
