"""
Eval loop — Inspect-AI-style orchestrator wiring the substrate adapter,
the locked-model agent, and the MeshQu /v1/decisions/record endpoint.

For each record in the corpus:

    1. substrate.ocds_to_decision_context(record)
         → AdaptedRecord(context, substrate_notes)

    2. Build the agent user message:
         canonical-JSON of {context.fields, substrate_notes (status+detail)}.
       Substrate-honesty disclosures are surfaced TO the agent so its
       reasoning can reference proxy status (e.g. "award date as
       signature-date proxy"). This is itself a substrate-honesty move:
       we don't hide the derivation chain from the model.

    3. agent.evaluate(user_message) → AgentResponse
       - On parse failure: write anomaly, skip record. NO decision_traces
         row, NO MeshQu call.

    4. inject_agent_fields(context, …agent outputs) → enriched context

    5. meshqu_client.record_decision(context, idempotency_key=…) → ReceiptSummary
       - On client error: write anomaly, skip record. (Same atomicity rule.)
       - Idempotency key = sha256("{run_id}/{ocid|record_index}")
         so a resume after partial-run never produces a duplicate row.

    6. Write decision_traces.jsonl row + agent-output sidecar at
       results/runs/<run_id>/agent_outputs/<decision_id>.json so the
       writeup can quote reasoning verbatim without bloating trace rows.

       **Atomicity caveat**: the MeshQu receipt is already created
       before step 6 runs. If any local write fails after the API call,
       the remote receipt exists but the local trace row is missing —
       this is NOT a fully atomic commit (cross-system 2PC isn't
       available). The loop catches such failures and emits a
       `receipt_orphaned` anomaly carrying the decision_id +
       idempotency_key so a recovery script can fetch the cached
       receipt and complete the local writes. The record is NOT
       counted in `records_with_receipt` — orphans are counted
       separately in `records_with_orphaned_receipt`.

    7. On the FIRST successful receipt, patch the run manifest with the
       resolved policy_snapshot_id.

    8. RunController hooks fire per existing screenshot/checkpoint cadence.

At run end, write_run_end() captures counts + status, including which
records were skipped and why. A reproducibility-rerun consumes the
manifest to rebuild the substrate corpus + replay against the same
policy_snapshot_id.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .agent import (
    Agent,
    AgentCallError,
    AgentResponse,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    load_system_prompt,
    projects_to_agreement,
)
from .audit import AnomalyEvent, AuditWriter
from .meshqu_client import (
    CANONICAL_AGENT_FIELD_KEYS,  # noqa: F401  (re-export for tests/manifest)
    MeshQuClient,
    MeshQuClientError,
    ReceiptSummary,
    inject_agent_fields,
)
from .run_manifest import (
    RunPhase,
    build_manifest,
    build_run_end,
    update_manifest_policy_snapshot_id,
    write_manifest,
    write_run_end,
)


# Imported lazily so the eval-loop module is importable in test envs that
# don't have substrate.py present yet (it's a sibling PR — until merged,
# the module just isn't available). The caller passes a
# `substrate_callable` so the loop never hard-binds to a specific adapter.
SubstrateCallable = Callable[[Mapping[str, Any]], "AdaptedRecordProtocol"]


class AdaptedRecordProtocol:  # documentation-only structural type
    ocid: str | None
    context: dict[str, Any]
    substrate_notes: dict[str, Any]


# ---------------------------------------------------------------------------
# Per-record outcome — used internally + for tests
# ---------------------------------------------------------------------------


@dataclass
class RecordOutcome:
    """What happened for one record. The eval-loop returns these so a
    smoke-test or test harness can assert per-record behaviour without
    re-reading the JSONL files."""

    record_index: int
    ocid: str | None
    outcome: str  # "receipt" | "skip_agent_parse" | "skip_agent_call" | "skip_meshqu" | "orphaned_receipt"
    detail: str = ""
    decision_id: str | None = None
    agent_verdict: str | None = None
    meshqu_verdict: str | None = None
    agreement: bool | None = None


@dataclass
class RunSummary:
    """Aggregate of all RecordOutcomes for the run. Mirrors what gets
    written into run_end.json."""

    run_id: str
    records_attempted: int = 0
    records_with_receipt: int = 0
    records_with_agent_parse_failure: int = 0
    records_with_agent_call_error: int = 0
    records_with_meshqu_error: int = 0
    # Receipt landed at MeshQu but a local post-receipt write failed.
    # NOT counted as a successful record — the local trace is missing.
    # See AnomalyCategory `receipt_orphaned` for the reconciliation
    # path. Surfaces into run_end.json so the writeup's headline
    # counts stay honest.
    records_with_orphaned_receipt: int = 0
    policy_snapshot_id: str | None = None
    outcomes: list[RecordOutcome] = field(default_factory=list)


# ---------------------------------------------------------------------------
# User-message builder — what the agent sees per record
# ---------------------------------------------------------------------------


def build_user_message(
    *,
    context: Mapping[str, Any],
    substrate_notes: Mapping[str, Any],
) -> str:
    """Render the agent's per-record user message as canonical JSON.

    The agent sees BOTH the substrate-derived fields AND each field's
    provenance (status + detail). Surfacing provenance is a deliberate
    substrate-honesty move — the writeup analyses whether the agent
    appropriately discounts low-confidence / proxy derivations in its
    reasoning.

    Canonical JSON: sort_keys=True, ensure_ascii=False, separators=(',', ':').
    Same canonicalisation as MeshQu's receipt-bytes — gives identical
    inputs → identical bytes → identical sha256 across rerun."""

    payload: dict[str, Any] = {
        "decision_type": context.get("decision_type"),
        "fields": context.get("fields") or {},
        "substrate_notes": _serialise_substrate_notes(substrate_notes),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _serialise_substrate_notes(substrate_notes: Mapping[str, Any]) -> dict[str, Any]:
    """FieldProvenance has status / confidence / detail / value. Render
    them as plain dicts so the agent sees structured data without
    needing to know about substrate.py's dataclass shape."""
    out: dict[str, Any] = {}
    for name, fp in substrate_notes.items():
        if hasattr(fp, "status"):
            out[name] = {
                "status": getattr(fp, "status", None),
                "confidence": getattr(fp, "confidence", None),
                "detail": getattr(fp, "detail", None),
            }
            value = getattr(fp, "value", None)
            if value is not None:
                out[name]["value"] = value
        elif isinstance(fp, dict):
            out[name] = dict(fp)
        else:
            out[name] = {"detail": str(fp)}
    return out


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def _idempotency_key(run_id: str, record_index: int, ocid: str | None) -> str:
    """Stable key per (run, record). A resumed run reuses the same key so
    MeshQu's idempotency cache returns the prior receipt instead of
    double-charging the policy evaluator.

    Uses ocid when available so it survives reordering of the input
    corpus; falls back to record_index for records the substrate can't
    identify."""
    discriminator = ocid or f"record-{record_index}"
    raw = f"{run_id}/{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Decision trace row — written when both agent + MeshQu succeed
# ---------------------------------------------------------------------------


def _build_decision_trace(
    *,
    record_index: int,
    ocid: str | None,
    receipt: ReceiptSummary,
    agent: AgentResponse,
    substrate_summary: Mapping[str, int],
) -> dict[str, Any]:
    """Compose the decision_traces.jsonl row.

    Schema (consumed by post-run analysis scripts):
      - record_index
      - ocid
      - decision_id
      - policy_snapshot_id
      - meshqu_verdict
      - agent_verdict (normalised uppercase or null)
      - agreement (true/false/null — null on parse failure, excluded
        from agreement stats)
      - reasoning_sha256
      - integrity_hash / evaluated_rules_hash / policy_snapshot_digest
      - signature_kid
      - violations (list of rule_codes only — full violation objects
        live in the receipt API, we just need the codes for analysis)
      - agent_output_mode / agent_parse_status / agent_latency_ms
      - substrate_summary (status counts per provenance bucket)
    """

    return {
        "record_index": record_index,
        "ocid": ocid,
        "decision_id": receipt.decision_id,
        "policy_snapshot_id": receipt.policy_snapshot_id,
        "meshqu_verdict": receipt.decision,
        "agent_verdict": agent.verdict,
        "agreement": projects_to_agreement(agent.verdict, receipt.decision),  # type: ignore[arg-type]
        "reasoning_sha256": agent.reasoning_sha256,
        "agent_recommended_action": agent.recommended_action,
        "integrity_hash": receipt.integrity_hash,
        "evaluated_rules_hash": receipt.evaluated_rules_hash,
        "policy_snapshot_digest": receipt.policy_snapshot_digest,
        "signature_kid": receipt.signature_kid,
        "receipt_timestamp": receipt.timestamp,
        "violations": [v.get("rule_code") for v in (receipt.violations or [])],
        "agent_output_mode": agent.output_mode,
        "agent_parse_status": agent.parse_status,
        "agent_latency_ms": agent.latency_ms,
        "agent_retry_count": agent.retry_count,
        "meshqu_retry_count": receipt.retry_count,
        "substrate_summary": dict(substrate_summary),
    }


# ---------------------------------------------------------------------------
# Sidecar — full agent text per receipt
# ---------------------------------------------------------------------------


def _write_agent_output_sidecar(
    *,
    run_dir: Path,
    decision_id: str,
    agent: AgentResponse,
    user_message: str,
) -> Path:
    """Persist the agent's full reasoning text + raw response next to
    the run's manifest. Keeps decision_traces.jsonl rows small and
    leaves the bulky text in a place reviewers can grep by decision_id.

    Atomic-write so a crash never produces a half-written sidecar that
    a re-run might mistake for completed work."""
    out_dir = run_dir / "agent_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{decision_id}.json"

    payload = {
        "decision_id": decision_id,
        "user_message": user_message,
        "agent": asdict(agent),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True, ensure_ascii=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


@dataclass
class EvalLoopConfig:
    """All config the eval loop needs that isn't already in RunnerConfig.

    Kept separate because RunnerConfig covers screenshot/dashboard
    plumbing, and adding a transitive Agent dependency to it would
    drag the OpenAI SDK into modules that don't need it."""

    run_id: str
    run_phase: RunPhase
    repo_dir: Path  # for git sha resolution
    run_dir: Path  # results/runs/<run_id>/ — manifest + sidecars live here
    meshqu_api_url: str
    meshqu_api_key: str
    # Tenant UUID — sent as `x-meshqu-tenant-id` on every POST. The MeshQu
    # API rejects requests without this header (400 MISSING_TENANT_ID)
    # regardless of the API key. Distinct from `meshqu_tenant_label`, which
    # is the human-readable slug captured in the manifest for the writeup.
    meshqu_tenant_id: str
    meshqu_tenant_label: str
    agent_api_key: str
    substrate_adapter_version: str
    substrate_source: dict[str, Any]
    record_target_count: int
    policy_code: str | None = None
    system_prompt_path: Path | None = None  # default resolved by load_system_prompt
    agent_model_id: str = LOCKED_MODEL_ID
    agent_temperature: float = LOCKED_TEMPERATURE
    agent_max_completion_tokens: int = 500
    # Polite pacing between records. 0 = no pause (use for dry-runs
    # where you want fast iteration). 0.25s default is conservative
    # enough that a 300-record run adds only 75s but keeps us well
    # under OpenAI's typical paid-tier RPM caps. Independent of the
    # agent's own retry-on-rate-limit; this is just back-pressure to
    # avoid hitting that limit in the first place.
    inter_request_pause_seconds: float = 0.25


def run_eval_loop(
    *,
    config: EvalLoopConfig,
    records: Iterable[Mapping[str, Any]],
    substrate_callable: SubstrateCallable,
    provenance_summary_callable: Callable[[Mapping[str, Any]], dict[str, int]],
    audit_writer: AuditWriter,
    meshqu_client: MeshQuClient | None = None,
    agent: Agent | None = None,
    on_after_record: Callable[[int, RecordOutcome], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> RunSummary:
    """Drive the loop. Returns a RunSummary; also writes manifest +
    run_end + decision_traces.jsonl + agent-output sidecars as side
    effects.

    Injection points:
      - `substrate_callable` — `substrate.ocds_to_decision_context`
        (or a fake for tests).
      - `provenance_summary_callable` — `substrate.provenance_summary`
        (or a fake for tests).
      - `meshqu_client` — defaults to MeshQuClient(base_url, api_key).
      - `agent` — defaults to Agent(api_key, system_prompt).
      - `on_after_record` — RunController.after_record hook so the
        existing screenshot/checkpoint cadence stays wired up.

    Substrate import is performed by the caller (eval-loop tests don't
    need substrate.py to be present) — the substrate module is a sibling
    PR; this loop is the consumer."""

    summary = RunSummary(run_id=config.run_id)

    system_prompt = load_system_prompt(config.system_prompt_path)
    if agent is None:
        agent = Agent(
            api_key=config.agent_api_key,
            system_prompt=system_prompt,
            model_id=config.agent_model_id,
            temperature=config.agent_temperature,
            max_completion_tokens=config.agent_max_completion_tokens,
        )
    if meshqu_client is None:
        meshqu_client = MeshQuClient(
            base_url=config.meshqu_api_url,
            api_key=config.meshqu_api_key,
            tenant_id=config.meshqu_tenant_id,
        )

    # Manifest goes down first — every later artefact references run_id.
    manifest = build_manifest(
        run_id=config.run_id,
        run_phase=config.run_phase,
        repo_dir=config.repo_dir,
        meshqu_api_url=config.meshqu_api_url,
        meshqu_tenant_label=config.meshqu_tenant_label,
        agent_model_id=agent.model_id,
        agent_temperature=agent.temperature,
        agent_max_completion_tokens=config.agent_max_completion_tokens,
        agent_prompt_sha256=agent.system_prompt_sha256,
        substrate_adapter_version=config.substrate_adapter_version,
        substrate_source=config.substrate_source,
        record_target_count=config.record_target_count,
        policy_code=config.policy_code,
    )
    write_manifest(config.run_dir, manifest)

    status: str = "completed"
    abort_reason: str | None = None

    try:
        for record_index, record in enumerate(records):
            # Polite pacing: pause BEFORE each record except the first.
            # Pausing before rather than after means a Ctrl-C between
            # records doesn't incur a doomed sleep.
            if record_index > 0 and config.inter_request_pause_seconds > 0:
                sleep_fn(config.inter_request_pause_seconds)
            summary.records_attempted += 1
            outcome = _process_record(
                record_index=record_index,
                record=record,
                config=config,
                substrate_callable=substrate_callable,
                provenance_summary_callable=provenance_summary_callable,
                agent=agent,
                meshqu_client=meshqu_client,
                audit_writer=audit_writer,
                summary=summary,
            )
            summary.outcomes.append(outcome)
            if on_after_record is not None:
                on_after_record(record_index, outcome)
    except KeyboardInterrupt:
        status = "aborted_by_signal"
        abort_reason = "KeyboardInterrupt"
    except Exception as err:  # noqa: BLE001 — must catch to write run_end
        status = "aborted_by_error"
        abort_reason = f"{type(err).__name__}: {err}"
        # Re-raise after run_end is written below so the caller still sees it.
        # Stash the exception via a closure attr to re-raise after finally-equivalent.
        try:
            write_run_end(
                config.run_dir,
                build_run_end(
                    run_id=config.run_id,
                    status=status,  # type: ignore[arg-type]
                    records_attempted=summary.records_attempted,
                    records_with_receipt=summary.records_with_receipt,
                    records_with_agent_parse_failure=summary.records_with_agent_parse_failure,
                    records_with_agent_call_error=summary.records_with_agent_call_error,
                    records_with_meshqu_error=summary.records_with_meshqu_error,
                    records_with_orphaned_receipt=summary.records_with_orphaned_receipt,
                    policy_snapshot_id=summary.policy_snapshot_id,
                    abort_reason=abort_reason,
                ),
            )
        finally:
            raise

    write_run_end(
        config.run_dir,
        build_run_end(
            run_id=config.run_id,
            status=status,  # type: ignore[arg-type]
            records_attempted=summary.records_attempted,
            records_with_receipt=summary.records_with_receipt,
            records_with_agent_parse_failure=summary.records_with_agent_parse_failure,
            records_with_agent_call_error=summary.records_with_agent_call_error,
            records_with_meshqu_error=summary.records_with_meshqu_error,
            records_with_orphaned_receipt=summary.records_with_orphaned_receipt,
            policy_snapshot_id=summary.policy_snapshot_id,
            abort_reason=abort_reason,
        ),
    )

    return summary


def _process_record(
    *,
    record_index: int,
    record: Mapping[str, Any],
    config: EvalLoopConfig,
    substrate_callable: SubstrateCallable,
    provenance_summary_callable: Callable[[Mapping[str, Any]], dict[str, int]],
    agent: Agent,
    meshqu_client: MeshQuClient,
    audit_writer: AuditWriter,
    summary: RunSummary,
) -> RecordOutcome:
    """Single-record path. Extracted from the loop so tests can exercise
    each branch (parse-failure, MeshQu error, success) deterministically."""

    adapted = substrate_callable(record)
    ocid = getattr(adapted, "ocid", None)
    context = adapted.context
    substrate_notes = adapted.substrate_notes
    substrate_summary = provenance_summary_callable(substrate_notes)

    user_message = build_user_message(
        context=context,
        substrate_notes=substrate_notes,
    )

    # ----- Agent call ----------------------------------------------------

    try:
        agent_response = agent.evaluate(user_message)
    except AgentCallError as err:
        audit_writer.write_anomaly(
            AnomalyEvent(
                run_id=config.run_id,
                category="agent_timeout" if err.kind == "timeout" else "agent_output_malformed",
                severity="warn",
                summary=f"agent call failed: {err.kind}",
                detail=err.detail,
                context={"record_index": record_index, "ocid": ocid},
            )
        )
        summary.records_with_agent_call_error += 1
        return RecordOutcome(
            record_index=record_index,
            ocid=ocid,
            outcome="skip_agent_call",
            detail=str(err),
        )

    if agent_response.parse_status != "ok" or agent_response.verdict is None:
        audit_writer.write_anomaly(
            AnomalyEvent(
                run_id=config.run_id,
                category="agent_output_malformed",
                severity="warn",
                summary=f"agent parse failure: {agent_response.parse_status}",
                detail=agent_response.parse_detail,
                context={
                    "record_index": record_index,
                    "ocid": ocid,
                    "raw_response": agent_response.raw_response,
                },
            )
        )
        summary.records_with_agent_parse_failure += 1
        return RecordOutcome(
            record_index=record_index,
            ocid=ocid,
            outcome="skip_agent_parse",
            detail=agent_response.parse_detail,
        )

    # ----- MeshQu call ---------------------------------------------------

    enriched_context = inject_agent_fields(
        context,
        agent_model_id=agent.model_id,
        agent_temperature=agent.temperature,
        agent_prompt_sha256=agent.system_prompt_sha256,
        agent_reasoning_sha256=agent_response.reasoning_sha256,
        agent_recommended_verdict=agent_response.verdict,
        agent_recommended_action=agent_response.recommended_action,
    )

    idempotency_key = _idempotency_key(config.run_id, record_index, ocid)

    try:
        receipt = meshqu_client.record_decision(
            context=enriched_context,
            idempotency_key=idempotency_key,
            correlation_id=f"{config.run_id}/{record_index}",
        )
    except MeshQuClientError as err:
        audit_writer.write_anomaly(
            AnomalyEvent(
                run_id=config.run_id,
                category="db_write_failed" if err.kind == "server_error" else "unexpected",
                severity="error" if err.kind in ("server_error", "auth") else "warn",
                summary=f"meshqu record failed: {err.kind}",
                detail=str(err),
                context={
                    "record_index": record_index,
                    "ocid": ocid,
                    "status_code": err.status_code,
                    "response_body": err.response_body,
                },
            )
        )
        summary.records_with_meshqu_error += 1
        return RecordOutcome(
            record_index=record_index,
            ocid=ocid,
            outcome="skip_meshqu",
            detail=str(err),
        )

    # ----- Post-receipt local writes ------------------------------------
    #
    # NOTE on atomicity: the MeshQu receipt has already been created when
    # we reach here. If any of the three local writes below (sidecar,
    # manifest patch, decision_traces row) fails, the remote receipt
    # still exists but the local trace is incomplete. This is NOT a
    # fully atomic commit — true cross-system atomicity would require
    # a 2-phase commit MeshQu does not offer.
    #
    # Mitigation: catch any failure, emit a `receipt_orphaned` anomaly
    # carrying enough information (decision_id, idempotency_key) for a
    # recovery script to fetch the cached receipt and complete the
    # local writes. The record is NOT counted as a successful receipt.

    try:
        _write_agent_output_sidecar(
            run_dir=config.run_dir,
            decision_id=receipt.decision_id,
            agent=agent_response,
            user_message=user_message,
        )

        if summary.policy_snapshot_id is None:
            # First successful receipt: pin the policy_snapshot_id into the
            # manifest so reproducibility-rerun knows which snapshot to
            # replay against.
            update_manifest_policy_snapshot_id(config.run_dir, receipt.policy_snapshot_id)
            summary.policy_snapshot_id = receipt.policy_snapshot_id

        trace = _build_decision_trace(
            record_index=record_index,
            ocid=ocid,
            receipt=receipt,
            agent=agent_response,
            substrate_summary=substrate_summary,
        )
        audit_writer.write_decision_trace(trace)
    except Exception as err:  # noqa: BLE001 — must catch to record the orphan
        audit_writer.write_anomaly(
            AnomalyEvent(
                run_id=config.run_id,
                category="receipt_orphaned",
                severity="error",
                summary=(
                    "MeshQu receipt landed but local post-receipt write failed; "
                    "remote receipt exists, local trace is incomplete"
                ),
                detail=f"{type(err).__name__}: {err}",
                context={
                    "record_index": record_index,
                    "ocid": ocid,
                    "decision_id": receipt.decision_id,
                    "policy_snapshot_id": receipt.policy_snapshot_id,
                    "integrity_hash": receipt.integrity_hash,
                    # Recovery script needs the idempotency_key to re-fetch
                    # the cached receipt without creating a duplicate.
                    "idempotency_key": _idempotency_key(
                        config.run_id, record_index, ocid
                    ),
                },
            )
        )
        summary.records_with_orphaned_receipt += 1
        return RecordOutcome(
            record_index=record_index,
            ocid=ocid,
            outcome="orphaned_receipt",
            detail=f"{type(err).__name__}: {err}",
            decision_id=receipt.decision_id,
            agent_verdict=agent_response.verdict,
            meshqu_verdict=receipt.decision,
        )

    summary.records_with_receipt += 1

    return RecordOutcome(
        record_index=record_index,
        ocid=ocid,
        outcome="receipt",
        decision_id=receipt.decision_id,
        agent_verdict=agent_response.verdict,
        meshqu_verdict=receipt.decision,
        agreement=projects_to_agreement(agent_response.verdict, receipt.decision),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Convenience: build a fresh run directory + run_id
# ---------------------------------------------------------------------------


def make_run_directory(results_root: Path, run_id: str | None = None) -> tuple[Path, str]:
    """Create `results_root/runs/<run_id>/` and return (path, run_id).
    Use this when the caller doesn't already own a run_id."""
    rid = run_id or str(uuid.uuid4())
    run_dir = results_root / "runs" / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, rid
