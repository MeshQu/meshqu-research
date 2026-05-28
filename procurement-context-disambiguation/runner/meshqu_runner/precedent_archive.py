"""Frozen-archive reader for L3 precedent selection.

L3 of the procurement-context-gradient experiment shows the agent 3–5
Decision Receipts from MeshQu-evaluated comparable records. The
**load-bearing methodological constraint** (see
`planning/context_ladder_design.md` §L3) is that those precedents are
drawn **exclusively from the frozen Experiment 1 archive** at:

    procurement-decisions/results/runs/dry-run-7ddf7274-…/

This module is the read-only loader for that archive. It walks two files
per record:

  1. `decision_traces.jsonl` — one row per (record, MeshQu evaluation),
     carrying OCID, decision_id, meshqu_verdict, violations, and the
     E1-agent's recommended_action.
  2. `agent_outputs/<decision_id>.json` — the per-record sidecar
     carrying the agent's full reasoning text and the `user_message`
     (which contains the substrate-projected `fields` map and
     `substrate_notes`).

The archive contains 300 trace lines but only 283 unique decision_ids /
OCIDs (E1's writer re-emitted some traces during checkpoint replays).
This loader de-duplicates by decision_id and keys the result by OCID,
yielding 283 PrecedentRecord entries.

Hard constraints
----------------

- **Read-only.** No method here writes anywhere.
- **No network.** All data comes from disk under `procurement-decisions/`.
  Tests assert no HTTP transport is touched.
- **No live MeshQu lookups.** A live lookup would change over time as
  policy snapshots evolve; precedents must be deterministically
  reproducible from the published E1 corpus.
- **Frozen-archive paths only.** The directory under
  `procurement-decisions/results/runs/<dry-run-7ddf7274-…>/` is the
  one canonical source. This module deliberately does not search any
  E2-in-flight output directory (which would create a runtime feedback
  loop).

Field map for the L3 template
-----------------------------

The Stage A template at `runner/prompts/L3_precedent_block_format.md`
references 9 fields per precedent. They come from the archive as:

  - `ocid`                           → trace row
  - `award_date`                     → regex over substrate_notes detail
  - `contract_value` (formatted)     → user_message fields
  - `regime_proxy` (PA23 / PCR_2015) → derived from `governed_by_pa23`
  - `procurement_method_open_flag`   → user_message fields (None when absent)
  - `publication_delay_days`         → user_message fields
  - `meshqu_verdict`                 → trace row
  - `violations_list`                → trace row
  - `e1_agent_reasoning_text`        → agent_outputs sidecar

Stop condition (per the build package): if the archive is missing a
required field for any record, raise `ArchiveLoadError` with the OCID
named — the L3 runner cannot render precedents cleanly without complete
field coverage.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


# Frozen-archive path resolved relative to the repo root. The
# 7ddf7274-… directory is the *only* sanctioned source for L3
# precedents; see planning/context_ladder_design.md §L3.
FROZEN_ARCHIVE_RELATIVE_PATH = (
    "procurement-decisions/results/runs/"
    "dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d"
)
"""Path (relative to the repo root) of the locked E1 archive. The
directory is treated as a static, post-publication corpus — no writes,
no patches, no fresh fetches against a live MeshQu instance."""

DECISION_TRACES_FILENAME = "decision_traces.jsonl"
AGENT_OUTPUTS_DIRNAME = "agent_outputs"

# Regex used to lift the award date out of the substrate_notes
# `governed_by_pa23.detail` string. The string has the form:
#   "awards[0].date=2026-03-27 > PA23 commencement 2025-02-24"
# All 283 records in the archive carry this — verified at load time.
_AWARD_DATE_RE = re.compile(r"awards\[0\]\.date=(\d{4}-\d{2}-\d{2})")


class ArchiveLoadError(RuntimeError):
    """Raised when the frozen archive is missing data the L3 selector
    needs. Surfaces a specific OCID + missing field so the runner stops
    cleanly rather than silently rendering a malformed precedent block."""


@dataclass(frozen=True)
class PrecedentRecord:
    """One record from the frozen E1 archive, projected onto the fields
    the L3 selector + template both need.

    Field types are deliberately conservative — they round-trip back into
    the Stage A template as strings (numeric fields via `format`)."""

    ocid: str
    decision_id: str
    award_date: str  # ISO YYYY-MM-DD
    contract_value: float
    governed_by_pa23: str  # "true" / "false"
    procurement_method_open_flag: str | None  # "true" / "false" / None
    publication_delay_days: int | None
    meshqu_verdict: str  # "ALLOW" / "REVIEW" / "DENY"
    violations: tuple[str, ...]
    agent_reasoning: str
    agent_recommended_action: str | None

    @property
    def regime_proxy(self) -> str:
        """Stage A's locked regime label. `governed_by_pa23 == "true"`
        means awarded after 24 Feb 2025 (PA23 commencement); else
        PCR_2015. The proxy is the same one E1 used at substrate."""
        return "PA23" if self.governed_by_pa23 == "true" else "PCR_2015"

    @property
    def contract_value_band(self) -> str:
        """The 4-band categorical feature used by the kNN selector
        (locked at Stage A — see planning/stage_a_content_authoring.md).
        Bands: <£100k / £100k–£500k / £500k–£10M / >£10M."""
        v = self.contract_value
        if v < 100_000:
            return "<100k"
        if v < 500_000:
            return "100k-500k"
        if v < 10_000_000:
            return "500k-10M"
        return ">10M"


# ---------------------------------------------------------------------------
# Loader — the only public entry point besides the dataclass
# ---------------------------------------------------------------------------


def load_frozen_archive(
    archive_dir: Path,
    *,
    require_award_date: bool = True,
) -> dict[str, PrecedentRecord]:
    """Read the frozen E1 archive at `archive_dir` and return a dict
    keyed by OCID.

    `archive_dir` should be the run directory itself, i.e. the
    `dry-run-7ddf7274-…/` folder containing `decision_traces.jsonl` +
    `agent_outputs/`. Tests construct a smaller archive_dir with the
    same shape; production usage points at the canonical frozen path
    via `default_frozen_archive_dir(repo_root)`.

    `require_award_date=True` is the production setting: an unparseable
    `governed_by_pa23.detail` string → `ArchiveLoadError`. Tests pass
    `False` when constructing minimal fixtures.

    The function returns a fresh dict on every call (no caching) so the
    determinism contract is owned entirely by the selector, not by
    archive-side memoisation.
    """
    archive_dir = Path(archive_dir)
    if not archive_dir.is_dir():
        raise ArchiveLoadError(
            f"Frozen archive directory not found: {archive_dir}. "
            "The L3 selector reads exclusively from the E1 archive; "
            "no live lookup is performed."
        )

    traces_path = archive_dir / DECISION_TRACES_FILENAME
    outputs_dir = archive_dir / AGENT_OUTPUTS_DIRNAME

    if not traces_path.is_file():
        raise ArchiveLoadError(
            f"Missing {DECISION_TRACES_FILENAME} under {archive_dir}."
        )
    if not outputs_dir.is_dir():
        raise ArchiveLoadError(
            f"Missing {AGENT_OUTPUTS_DIRNAME}/ under {archive_dir}."
        )

    # Pass 1: stream decision_traces.jsonl, de-dup by decision_id (the
    # archive contains 300 lines for 283 unique decisions; some were
    # re-written during E1 checkpoint replays). Keeping the first
    # occurrence per decision_id is deterministic and matches the order
    # E1 emitted them.
    traces_by_decision: dict[str, dict] = {}
    with traces_path.open("r", encoding="utf-8") as fp:
        for line_number, raw in enumerate(fp, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ArchiveLoadError(
                    f"Malformed JSON at {traces_path}:{line_number}: {e}"
                ) from e
            decision_id = row.get("decision_id")
            if not isinstance(decision_id, str):
                raise ArchiveLoadError(
                    f"Trace row at {traces_path}:{line_number} is missing decision_id."
                )
            traces_by_decision.setdefault(decision_id, row)

    # Pass 2: for each unique decision, load the agent_outputs sidecar
    # and project everything onto a PrecedentRecord. Records are keyed
    # by OCID; duplicate OCIDs (different decision_ids on the same
    # record — shouldn't happen given decision_id de-dup above, but
    # guarded for) raise.
    archive: dict[str, PrecedentRecord] = {}
    for decision_id, trace in traces_by_decision.items():
        ocid = trace.get("ocid")
        if not isinstance(ocid, str):
            raise ArchiveLoadError(
                f"Trace for decision {decision_id} is missing ocid."
            )

        sidecar_path = outputs_dir / f"{decision_id}.json"
        if not sidecar_path.is_file():
            raise ArchiveLoadError(
                f"Agent-output sidecar missing for decision {decision_id} "
                f"(expected {sidecar_path}). OCID: {ocid}."
            )

        with sidecar_path.open("r", encoding="utf-8") as fp:
            sidecar = json.load(fp)

        record = _project_record(
            ocid=ocid,
            decision_id=decision_id,
            trace=trace,
            sidecar=sidecar,
            require_award_date=require_award_date,
        )

        if ocid in archive:
            raise ArchiveLoadError(
                f"Duplicate OCID after decision_id de-dup: {ocid}. "
                f"Existing decision={archive[ocid].decision_id} new={decision_id}."
            )
        archive[ocid] = record

    return archive


def default_frozen_archive_dir(repo_root: Path) -> Path:
    """Compose the canonical frozen-archive path relative to the repo
    root. Production code always uses this; tests point at fixture
    directories that mimic the layout."""
    return Path(repo_root) / FROZEN_ARCHIVE_RELATIVE_PATH


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _project_record(
    *,
    ocid: str,
    decision_id: str,
    trace: Mapping[str, object],
    sidecar: Mapping[str, object],
    require_award_date: bool,
) -> PrecedentRecord:
    """Build a PrecedentRecord from one trace row + its sidecar.

    The split between trace and sidecar mirrors what E1 actually
    persisted; this function is the only place that names the join."""
    user_message_raw = sidecar.get("user_message")
    if not isinstance(user_message_raw, str):
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} missing user_message (OCID {ocid})."
        )
    try:
        user_message = json.loads(user_message_raw)
    except json.JSONDecodeError as e:
        raise ArchiveLoadError(
            f"Sidecar user_message for {decision_id} is not JSON: {e}"
        ) from e

    fields = user_message.get("fields") or {}
    notes = user_message.get("substrate_notes") or {}
    if not isinstance(fields, dict) or not isinstance(notes, dict):
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} has malformed fields/substrate_notes (OCID {ocid})."
        )

    # Required numeric / categorical fields. Missing contract_value is a
    # stop condition; missing publication_delay_days is tolerated (Stage A
    # template can render "n/a"). governed_by_pa23 is always present in
    # the archive (every record carries the PA23-vs-PCR2015 proxy).
    if "contract_value" not in fields:
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} missing contract_value (OCID {ocid})."
        )
    contract_value = float(fields["contract_value"])

    governed_by_pa23 = fields.get("governed_by_pa23")
    if governed_by_pa23 not in ("true", "false"):
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} missing/unknown governed_by_pa23 "
            f"({governed_by_pa23!r}) (OCID {ocid})."
        )

    procurement_method_open_flag = fields.get("procurement_method_open_flag")
    # "absent" semantics: when the field is not in the fields map at all
    # OR when it's explicitly null. The substrate_notes records "absent"
    # status for ~264 of 283 records — this is a known E1 property and
    # the L3 template handles None by emitting "(field absent)".
    if procurement_method_open_flag is not None and not isinstance(
        procurement_method_open_flag, str
    ):
        procurement_method_open_flag = str(procurement_method_open_flag)

    publication_delay_days_raw = fields.get("publication_delay_days")
    if isinstance(publication_delay_days_raw, (int, float)):
        publication_delay_days = int(publication_delay_days_raw)
    elif publication_delay_days_raw is None:
        publication_delay_days = None
    else:
        try:
            publication_delay_days = int(publication_delay_days_raw)
        except (TypeError, ValueError):
            publication_delay_days = None

    # Award date — extracted from substrate_notes detail. All 283
    # records carry the regex-matched form; absence is a stop condition
    # (the L3 template references award_date and we will not synthesise).
    pa23_note = notes.get("governed_by_pa23") if isinstance(notes, dict) else {}
    pa23_detail = ""
    if isinstance(pa23_note, dict):
        pa23_detail = pa23_note.get("detail") or ""
    match = _AWARD_DATE_RE.search(pa23_detail or "")
    if match is None:
        if require_award_date:
            raise ArchiveLoadError(
                f"Sidecar for {decision_id} (OCID {ocid}) does not carry "
                "an award date in substrate_notes['governed_by_pa23']['detail']. "
                "The L3 template references award_date — refusing to synthesise."
            )
        award_date = "unknown"
    else:
        award_date = match.group(1)

    # MeshQu verdict + violations come from the trace row (the
    # canonical record of what MeshQu actually returned at evaluate
    # time). The sidecar's `agent.verdict` is the AGENT's verdict,
    # which is a different thing and used at "agreement" analysis.
    meshqu_verdict = trace.get("meshqu_verdict")
    if not isinstance(meshqu_verdict, str):
        raise ArchiveLoadError(
            f"Trace for {decision_id} (OCID {ocid}) missing meshqu_verdict."
        )

    violations_raw = trace.get("violations") or []
    if not isinstance(violations_raw, list):
        raise ArchiveLoadError(
            f"Trace for {decision_id} (OCID {ocid}) has malformed violations."
        )
    violations: tuple[str, ...] = tuple(str(v) for v in violations_raw)

    # E1 agent reasoning lives in the sidecar's `agent.reasoning`.
    # Empty reasoning is a stop condition — the L3 template references
    # it and an empty string would silently strip a precedent block of
    # its most informative line.
    agent_block = sidecar.get("agent") or {}
    if not isinstance(agent_block, dict):
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} (OCID {ocid}) has malformed agent block."
        )
    reasoning = agent_block.get("reasoning") or ""
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ArchiveLoadError(
            f"Sidecar for {decision_id} (OCID {ocid}) has empty agent.reasoning. "
            "The L3 template references e1_agent_reasoning_text — refusing to "
            "render an empty precedent."
        )

    recommended_action_raw = agent_block.get("recommended_action")
    if isinstance(recommended_action_raw, str) and recommended_action_raw.strip():
        recommended_action: str | None = recommended_action_raw
    else:
        # 7 of 283 records have empty recommended_action — this is a
        # known E1 property (some "review" verdicts didn't carry an
        # explicit action). The template handles None with a fallback.
        recommended_action = None

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
        agent_reasoning=reasoning,
        agent_recommended_action=recommended_action,
    )
