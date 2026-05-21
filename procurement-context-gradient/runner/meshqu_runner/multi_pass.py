"""Multi-pass orchestrator — level-batched execution over L0..L4.

This is the new layer E2 adds on top of E1's per-record eval loop. For
each of the five governance-context levels (L0..L4), it processes all
records in OCID-ascending order, producing one signed Decision Receipt
per (record, level) pair. The full grid is 283 records × 5 levels =
1,415 receipts; the smoke fixture is 3 × 5 = 15.

## Level-batching

Execution order is LOCKED to level-batching (see
`planning/experiment_design.md` §"Multi-pass runner"). The loop walks
the outer level dimension first:

    for level in [L0, L1, L2, L3, L4]:
        for record in records_sorted_by_ocid:
            evaluate(record, level)

Not record-cycled. Two reasons:

1. **Prompt-cache preservation at L4.** Keeps the ~4,500-token policy
   block at the cache head across N consecutive L4 calls.
2. **Comparability.** Within a level, every record sees the same
   prompt scaffolding — no temporal-locality variance.

## Local bundle envelope (NOT a MeshQu receipt-schema bump)

This orchestrator persists each (record, level) result as a local
bundle file at `results/runs/<run_id>/<level>/<decision_id>.bundle.json`.
The bundle is a runner-local artefact — a wrapper around the
MeshQu-issued receipt — and carries `bundle_envelope_version: 1`
(its own versioning, distinct from the MeshQu product's receipt
schema). The MeshQu receipt inside the wrapper retains whatever
`receipt_schema_version` the API returned (currently 2 in the product).

The wrapper adds:

- `governance_context_level` (L0..L4, or L4_PERMUTED for the diagnostic)
- `context_fields_canonical_json` — the exact bytes MeshQu hashed
- `is_stub` — true when StubMeshQuClient was used
- `record_index`, `ocid`, `timestamp` — operational indexing fields

The level marker is bound into MeshQu's integrity hash via the
`context.fields` injection point — the same pattern E1 uses for
`agent_*` fields. The MeshQu API canonicalises the fields map and
hashes it; the policy never references `governance_context_level`, so
this is audit-only-but-hash-bound. **No upstream @meshqu/core change is
required, and the MeshQu receipt schema itself is unchanged.**

## Run manifest extensions

Records (in addition to E1's manifest fields):

- `levels: ["L0", "L1", "L2", "L3", "L4"]`
- `level_batched: true`
- `prompt_template_sha256: { L1: ..., L2: ..., L3: ..., L4: ... }`
- `policy_snapshot_sha256: <sha of policy/policy-snapshot-cbf12348.json>`
- `runner_git_commit: <inherited from build_manifest>`
- `bundle_envelope_version: 1`

## Stub mode

Tests + the `--stub` CLI flag inject a `StubAgent` and `StubMeshQuClient`
so the orchestration runs end-to-end without OpenAI or MeshQu
credentials. Stub bundles carry `is_stub: true` so they cannot be
confused with live receipts; they will NOT verify at verify.meshqu.com.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .agent import (
    Agent,
    AgentResponse,
    LOCKED_MODEL_ID,
    LOCKED_TEMPERATURE,
    sha256_reasoning,
)
from .audit import AuditWriter
from .eval_loop import build_user_message
from .level_handlers import (
    GovernanceContextLevel,
    LevelHandler,
    MAIN_LEVELS,
    compose_user_message,
    default_main_handlers,
)
from .meshqu_client import (
    MeshQuClient,
    ReceiptSummary,
    inject_agent_fields,
)
from .prompt_loader import LoadedPrompts, load_level_prompts
from .run_manifest import RunPhase, resolve_git_commit


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUNDLE_ENVELOPE_VERSION = 1
"""Version of the E2-local bundle wrapper at
`results/runs/<run_id>/<level>/<decision_id>.bundle.json`. This is a
NEW envelope introduced by E2 — it wraps a MeshQu-issued receipt with
additional fields the multi-pass orchestrator needs for the cross-level
analysis (level marker, canonical-JSON bytes, run metadata).

This is NOT a MeshQu-product receipt-schema bump. The MeshQu receipt
schema itself is unchanged (the product is currently at v2; that
remains the version of the receipt nested inside this wrapper). The
governance_context_level field rides into the MeshQu integrity hash
via the existing canonical-JSON envelope — no upstream change needed.

E1 never wrote local bundle files at all; it fetched
`/v1/decisions/<id>/bundle` on demand. So there's no prior version of
THIS file format to bump from. v1 == this is the first."""

GOVERNANCE_CONTEXT_LEVEL_FIELD = "governance_context_level"
"""The key under `context.fields` that carries the level marker. The
ratified policy never references this key — it rides along as audit-only
metadata bound into the integrity hash. Same pattern as `agent_*`."""


# ---------------------------------------------------------------------------
# Per-(record, level) outcome
# ---------------------------------------------------------------------------


@dataclass
class PassOutcome:
    """What the orchestrator produced for one (record, level) pair."""

    record_index: int
    level: GovernanceContextLevel
    ocid: str | None
    decision_id: str
    bundle_path: Path
    receipt: ReceiptSummary
    agent: AgentResponse
    timestamp: str  # ISO-8601 UTC seconds
    is_stub: bool


@dataclass
class MultiPassSummary:
    """All PassOutcomes for the run."""

    run_id: str
    run_dir: Path
    levels: tuple[GovernanceContextLevel, ...]
    outcomes: list[PassOutcome] = field(default_factory=list)

    def for_level(self, level: GovernanceContextLevel) -> list[PassOutcome]:
        return [o for o in self.outcomes if o.level == level]


# ---------------------------------------------------------------------------
# Stub Agent + MeshQuClient — enable hermetic tests + --stub CLI mode
# ---------------------------------------------------------------------------


@dataclass
class StubAgent:
    """Deterministic stand-in for Agent. Produces a fixed REVIEW verdict
    with a reasoning string keyed off the user_message hash. Lets the
    multi-pass orchestrator run end-to-end without OpenAI.

    Mirrors the public surface of `Agent` that the orchestrator touches
    (model_id, temperature, system_prompt_sha256, evaluate)."""

    model_id: str = LOCKED_MODEL_ID
    temperature: float = LOCKED_TEMPERATURE
    system_prompt_sha256: str = "0" * 64
    fixed_verdict: str = "REVIEW"

    def evaluate(self, user_message: str) -> AgentResponse:
        digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()
        reasoning = f"[stub] verdict={self.fixed_verdict} user_message_sha256={digest[:16]}"
        return AgentResponse(
            verdict=self.fixed_verdict,  # type: ignore[arg-type]
            reasoning=reasoning,
            reasoning_sha256=sha256_reasoning(reasoning),
            recommended_action=None,
            raw_response=json.dumps({"verdict": self.fixed_verdict.lower(), "reasoning": reasoning}),
            latency_ms=0,
            output_mode="plain_text",
            parse_status="ok",
            retry_count=0,
        )


@dataclass
class StubMeshQuClient:
    """Deterministic stand-in for MeshQuClient. Computes integrity_hash
    locally from canonical-JSON of the fields map, returns a synthesised
    ReceiptSummary.

    The integrity hash binding here is INTENTIONALLY equivalent in
    structure to what MeshQu's real API does (canonical-JSON of the
    fields map, SHA-256), so test assertions about which fields are
    hash-bound are meaningful. The key difference: stub receipts are
    NOT signed and NOT anchored to Rekor — they would never verify at
    verify.meshqu.com. The bundle's `is_stub: true` flag makes this
    explicit."""

    tenant_id: str = "stub-tenant"
    policy_snapshot_id: str = "stub-policy-snapshot"
    fixed_decision: str = "REVIEW"

    def record_decision(
        self,
        *,
        context: Mapping[str, Any],
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> ReceiptSummary:
        fields = dict(context.get("fields") or {})
        canonical = canonical_json_bytes(fields)
        integrity_hash = hashlib.sha256(canonical).hexdigest()
        evaluated_rules_hash = hashlib.sha256(b"stub-evaluated-rules").hexdigest()
        timestamp = _utc_now_iso()

        # Decision id derives deterministically from idempotency_key so
        # repeated calls with the same key produce the same decision_id —
        # mirroring MeshQu's idempotency-cache behaviour.
        if idempotency_key:
            decision_id = "stub-" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]
        else:
            decision_id = "stub-" + uuid.uuid4().hex[:32]

        return ReceiptSummary(
            decision_id=decision_id,
            decision=self.fixed_decision,  # type: ignore[arg-type]
            policy_snapshot_id=self.policy_snapshot_id,
            integrity_hash=integrity_hash,
            evaluated_rules_hash=evaluated_rules_hash,
            timestamp=timestamp,
            signature_kid=None,
            signature=None,
            policy_snapshot_digest=None,
            transparency_anchor=None,
            violations=[],
            raw_response={"stub": True},
            retry_count=0,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Canonical-JSON serialisation matching MeshQu's wire format:
    sort_keys=True, ensure_ascii=False, separators=(',', ':'). Returns
    UTF-8 bytes ready for SHA-256."""
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic write: temp file + fsync + rename. Crash-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True, default=_json_default)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _idempotency_key(run_id: str, record_index: int, ocid: str | None, level: str) -> str:
    """Per-(run, record, level) idempotency. The level is part of the
    key so MeshQu's cache doesn't conflate a record's L0 evaluation
    with its L1 evaluation."""
    discriminator = ocid or f"record-{record_index}"
    raw = f"{run_id}/{level}/{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    with path.open("rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


# ---------------------------------------------------------------------------
# Cache telemetry (E2-005)
# ---------------------------------------------------------------------------


CACHE_TELEMETRY_FILENAME = "cache_telemetry.jsonl"
"""Sidecar filename relative to <run_dir>. One JSONL line per (record,
level) capturing cached_tokens + prompt_tokens. Consumed by
`scripts/cache_summary.py`."""


def _append_cache_telemetry(
    *,
    run_dir: Path,
    run_id: str,
    level: GovernanceContextLevel,
    record_index: int,
    ocid: str | None,
    decision_id: str,
    timestamp: str,
    cached_tokens: int | None,
    prompt_tokens: int | None,
    is_stub: bool,
) -> Path:
    """Append one cache-telemetry row to
    <run_dir>/cache_telemetry.jsonl. Best-effort: open in append mode,
    write a single line, close. No fsync — the file is observational
    telemetry, not part of the audit trail. A torn write at process
    crash leaves a corrupt line; the summary script tolerates missing
    rows.

    Returns the path written to (for tests).
    """
    path = run_dir / CACHE_TELEMETRY_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": run_id,
        "level": level,
        "record_index": record_index,
        "ocid": ocid,
        "decision_id": decision_id,
        "timestamp": timestamp,
        "cached_tokens": cached_tokens,
        "prompt_tokens": prompt_tokens,
        "is_stub": is_stub,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        fp.write("\n")
    return path


# ---------------------------------------------------------------------------
# Bundle writer — the v1 bundle envelope (E2-local wrapper around v2 MeshQu receipts)
# ---------------------------------------------------------------------------


def write_bundle(
    *,
    run_dir: Path,
    level: GovernanceContextLevel,
    decision_id: str,
    record_index: int,
    ocid: str | None,
    receipt: ReceiptSummary,
    agent: AgentResponse,
    context_fields_canonical: bytes,
    timestamp: str,
    is_stub: bool,
) -> Path:
    """Persist the v1 bundle file for one (record, level) pair.

    Layout:
        <run_dir>/<level>/<decision_id>.bundle.json

    The bundle carries everything a future verifier needs to recompute
    the integrity hash:

    - `bundle_envelope_version: 1` (THIS wrapper's version, NOT the
      MeshQu receipt-schema version — the wrapped receipt carries its
      own schema marker via the API)
    - `governance_context_level`
    - `context_fields_canonical_json` (the bytes MeshQu hashed)
    - `receipt` (the MeshQu-issued ReceiptSummary)
    - `agent` (the AgentResponse; reasoning hash mirrors receipt binding)

    Plus operational fields (`is_stub`, `record_index`, `ocid`,
    `timestamp`) for indexing.
    """
    bundle_path = run_dir / level / f"{decision_id}.bundle.json"
    payload: dict[str, Any] = {
        "bundle_envelope_version": BUNDLE_ENVELOPE_VERSION,
        "governance_context_level": level,
        "is_stub": is_stub,
        "record_index": record_index,
        "ocid": ocid,
        "decision_id": decision_id,
        "timestamp": timestamp,
        "context_fields_canonical_json": context_fields_canonical.decode("utf-8"),
        "receipt": _serialise_receipt(receipt),
        "agent": _serialise_agent(agent),
    }
    _atomic_write_json(bundle_path, payload)
    return bundle_path


def _serialise_receipt(receipt: ReceiptSummary) -> dict[str, Any]:
    """Flatten ReceiptSummary into the bundle envelope. The raw_response
    is omitted by default — it's bulky and the parsed fields cover what
    a verifier needs."""
    return {
        "decision_id": receipt.decision_id,
        "decision": receipt.decision,
        "policy_snapshot_id": receipt.policy_snapshot_id,
        "integrity_hash": receipt.integrity_hash,
        "evaluated_rules_hash": receipt.evaluated_rules_hash,
        "timestamp": receipt.timestamp,
        "signature_kid": receipt.signature_kid,
        "signature": receipt.signature,
        "policy_snapshot_digest": receipt.policy_snapshot_digest,
        "transparency_anchor": receipt.transparency_anchor,
        "violations": list(receipt.violations or []),
        "retry_count": receipt.retry_count,
    }


def _serialise_agent(agent: AgentResponse) -> dict[str, Any]:
    """Capture the agent's per-record output. The verdict + reasoning
    hash are what the writeup's analysis layer consumes; the raw
    response sits in the agent_outputs sidecar for quote-by-decision-id
    lookups."""
    payload = asdict(agent)
    # Trim raw_response to keep bundle files small; the sidecar carries the full text.
    payload["raw_response"] = (payload.get("raw_response") or "")[:512]
    return payload


# ---------------------------------------------------------------------------
# Manifest writer (E2 extension)
# ---------------------------------------------------------------------------


def write_e2_manifest(
    *,
    run_dir: Path,
    run_id: str,
    run_phase: RunPhase,
    levels: Sequence[GovernanceContextLevel],
    prompt_shas: Mapping[str, str],
    policy_snapshot_path: Path | None,
    repo_dir: Path,
    meshqu_api_url: str,
    meshqu_tenant_label: str,
    agent_model_id: str,
    agent_temperature: float,
    agent_prompt_sha256: str,
    substrate_adapter_version: str,
    substrate_source: Mapping[str, Any],
    record_target_count: int,
    is_stub: bool,
) -> Path:
    """Persist the E2 run manifest. Same shape as E1's manifest plus the
    level-batched fields the package prompt requires."""
    sha, dirty = resolve_git_commit(repo_dir)
    policy_sha = _sha256_file(policy_snapshot_path) if policy_snapshot_path else None

    manifest = {
        "run_id": run_id,
        "run_phase": run_phase,
        "started_at": _utc_now_iso(),
        "runner_git_commit": sha,
        "runner_git_dirty": dirty,
        "meshqu_api_url": meshqu_api_url,
        "meshqu_tenant_label": meshqu_tenant_label,
        "agent_model_id": agent_model_id,
        "agent_temperature": agent_temperature,
        "agent_prompt_sha256": agent_prompt_sha256,
        "substrate_adapter_version": substrate_adapter_version,
        "substrate_source": dict(substrate_source),
        "record_target_count": record_target_count,
        "is_stub": is_stub,
        # E2 extensions
        "bundle_envelope_version": BUNDLE_ENVELOPE_VERSION,
        "levels": list(levels),
        "level_batched": True,
        "prompt_template_sha256": dict(prompt_shas),
        "policy_snapshot_sha256": policy_sha,
        "policy_snapshot_path": str(policy_snapshot_path) if policy_snapshot_path else None,
    }
    path = run_dir / "manifest.json"
    _atomic_write_json(path, manifest)
    return path


# ---------------------------------------------------------------------------
# Multi-pass controller
# ---------------------------------------------------------------------------


@dataclass
class MultiPassConfig:
    """All config the orchestrator needs.

    `levels` defaults to the full main grid; tests can pass a subset.

    `agent` + `meshqu_client` are pluggable so a test or `--stub` CLI
    can inject StubAgent / StubMeshQuClient. When None, the live OpenAI
    + MeshQu clients are constructed from `agent_api_key` +
    `meshqu_api_key` (NOT in scope for E2-001 — full live wiring lands
    in E2-002..006).

    `cache_telemetry_enabled` (E2-005): when True, the orchestrator
    appends one JSONL line per (record, level) to
    `<run_dir>/cache_telemetry.jsonl` capturing the agent's
    cached_tokens + prompt_tokens. The post-run summary script
    `scripts/cache_summary.py` consumes that file. Defaults to True so
    every E2 run picks up the telemetry; tests that don't care can flip
    it off."""

    run_id: str
    run_phase: RunPhase
    repo_dir: Path
    run_dir: Path
    prompts_dir: Path
    policy_snapshot_path: Path | None
    levels: tuple[GovernanceContextLevel, ...] = MAIN_LEVELS
    meshqu_api_url: str = "https://api.meshqu.com"
    meshqu_tenant_label: str = "experiment-procurement"
    substrate_adapter_version: str = "0.0-stub"
    substrate_source: Mapping[str, Any] = field(default_factory=dict)
    # Pause between calls. Smoke / tests can set to 0.
    inter_request_pause_seconds: float = 0.0
    # E2-005: cache telemetry sidecar at <run_dir>/cache_telemetry.jsonl.
    cache_telemetry_enabled: bool = True


def run_multi_pass(
    *,
    config: MultiPassConfig,
    records: Sequence[Mapping[str, Any]],
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    audit_writer: AuditWriter | None = None,
    handlers: Mapping[GovernanceContextLevel, LevelHandler] | None = None,
    is_stub: bool | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> MultiPassSummary:
    """Drive the level-batched multi-pass run.

    Returns a MultiPassSummary; also writes:
      - <run_dir>/manifest.json
      - <run_dir>/<level>/<decision_id>.bundle.json for every (record, level)
      - <run_dir>/audit/ via the optional AuditWriter (anomaly trail)

    `handlers` defaults to the main-grid stubs (L0..L4). Tests and the
    permuted-policy diagnostic (E2-006) pass a custom registry.

    `is_stub` defaults to True when both clients are stubs; explicit
    override available for tests that mix stub and live."""
    if handlers is None:
        handlers = default_main_handlers()

    if is_stub is None:
        is_stub = isinstance(agent, StubAgent) and isinstance(meshqu_client, StubMeshQuClient)

    prompts = load_level_prompts(config.prompts_dir)

    # Records are processed in OCID-ascending order within a level. Sort
    # once, before the outer loop. Records missing an OCID sort to the
    # end (str(None) → "None") — deterministic and surfaces missing
    # OCIDs as anomalies in downstream auditing.
    sorted_records = sorted(
        list(records),
        key=lambda r: (_extract_ocid(r) is None, _extract_ocid(r) or ""),
    )

    config.run_dir.mkdir(parents=True, exist_ok=True)

    # Manifest first — every later artefact references run_id.
    write_e2_manifest(
        run_dir=config.run_dir,
        run_id=config.run_id,
        run_phase=config.run_phase,
        levels=config.levels,
        prompt_shas=prompts.sha_map(),
        policy_snapshot_path=config.policy_snapshot_path,
        repo_dir=config.repo_dir,
        meshqu_api_url=config.meshqu_api_url,
        meshqu_tenant_label=config.meshqu_tenant_label,
        agent_model_id=getattr(agent, "model_id", LOCKED_MODEL_ID),
        agent_temperature=getattr(agent, "temperature", LOCKED_TEMPERATURE),
        agent_prompt_sha256=getattr(agent, "system_prompt_sha256", "0" * 64),
        substrate_adapter_version=config.substrate_adapter_version,
        substrate_source=config.substrate_source,
        record_target_count=len(sorted_records),
        is_stub=is_stub,
    )

    summary = MultiPassSummary(
        run_id=config.run_id, run_dir=config.run_dir, levels=tuple(config.levels)
    )

    # Level-batched outer loop. ALL records at L0 before any record at L1.
    for level in config.levels:
        for record_index, record in enumerate(sorted_records):
            if (record_index > 0 or level != config.levels[0]) and config.inter_request_pause_seconds > 0:
                sleep_fn(config.inter_request_pause_seconds)

            outcome = _process_pass(
                config=config,
                record_index=record_index,
                record=record,
                level=level,
                handlers=handlers,
                prompts=prompts,
                agent=agent,
                meshqu_client=meshqu_client,
                is_stub=is_stub,
            )
            summary.outcomes.append(outcome)

    return summary


def _extract_ocid(record: Mapping[str, Any]) -> str | None:
    """Pull the OCID out of a record. Records carry it under `ocid` (the
    smoke fixture pattern) or under `metadata.ocid` (E1's substrate
    output shape). Falls back to None when neither is present."""
    if "ocid" in record and isinstance(record["ocid"], str):
        return record["ocid"]
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("ocid"), str):
        return metadata["ocid"]
    return None


def _process_pass(
    *,
    config: MultiPassConfig,
    record_index: int,
    record: Mapping[str, Any],
    level: GovernanceContextLevel,
    handlers: Mapping[GovernanceContextLevel, LevelHandler],
    prompts: LoadedPrompts,
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    is_stub: bool,
) -> PassOutcome:
    """Single (record, level) pass. Extracted so tests can call it
    deterministically without driving the outer loop."""
    ocid = _extract_ocid(record)

    # `record` is the smoke-fixture shape: { ocid, decision_type, fields,
    # substrate_notes }. The substrate.ocds_to_decision_context wiring
    # for live mode lands in E2-002.
    decision_type = record.get("decision_type", "procurement_decision")
    fields = dict(record.get("fields") or {})
    substrate_notes = dict(record.get("substrate_notes") or {})

    context: dict[str, Any] = {
        "decision_type": decision_type,
        "fields": fields,
        "metadata": dict(record.get("metadata") or {"ocid": ocid}),
    }
    base_user_message = build_user_message(
        context=context,
        substrate_notes=substrate_notes,
    )

    user_message = compose_user_message(
        level=level,
        record=record,
        ocid=ocid,
        prompts=prompts,
        handlers=handlers,
        base_message=base_user_message,
    )

    agent_response = agent.evaluate(user_message)

    # E2-001 contract: stub mode tolerates a non-OK parse_status (the
    # stub always emits ok). Live mode will land per-record skip
    # behaviour in E2-002..005 — out of scope here.

    enriched_context = inject_agent_fields(
        context,
        agent_model_id=getattr(agent, "model_id", LOCKED_MODEL_ID),
        agent_temperature=getattr(agent, "temperature", LOCKED_TEMPERATURE),
        agent_prompt_sha256=getattr(agent, "system_prompt_sha256", "0" * 64),
        agent_reasoning_sha256=agent_response.reasoning_sha256,
        agent_recommended_verdict=agent_response.verdict or "REVIEW",
        agent_recommended_action=agent_response.recommended_action,
    )

    # The hash-binding contract: inject governance_context_level INTO
    # context.fields BEFORE posting to MeshQu. The API canonicalises
    # the fields map and binds it into the integrity hash. Policy never
    # references this key.
    enriched_fields = dict(enriched_context["fields"])
    enriched_fields[GOVERNANCE_CONTEXT_LEVEL_FIELD] = level
    enriched_context["fields"] = enriched_fields

    idempotency_key = _idempotency_key(config.run_id, record_index, ocid, level)
    receipt = meshqu_client.record_decision(
        context=enriched_context,
        idempotency_key=idempotency_key,
        correlation_id=f"{config.run_id}/{level}/{record_index}",
    )

    # Persist the canonical bytes the integrity hash was computed over,
    # so a verifier can recompute. In stub mode this matches what the
    # StubMeshQuClient actually hashed; in live mode it matches what
    # the server hashed (modulo MeshQu's own canonicalisation, which
    # this runner replicates faithfully).
    canonical = canonical_json_bytes(enriched_context["fields"])

    timestamp = _utc_now_iso()
    bundle_path = write_bundle(
        run_dir=config.run_dir,
        level=level,
        decision_id=receipt.decision_id,
        record_index=record_index,
        ocid=ocid,
        receipt=receipt,
        agent=agent_response,
        context_fields_canonical=canonical,
        timestamp=timestamp,
        is_stub=is_stub,
    )

    # E2-005: cache telemetry sidecar. One JSONL line per (record,
    # level) capturing cached_tokens + prompt_tokens from the agent
    # response. The post-run summary script computes per-level
    # cache-hit fraction from this file. Loop semantics (level-batching
    # order, sleep, idempotency) are unchanged — this is purely an
    # additive write.
    if config.cache_telemetry_enabled:
        _append_cache_telemetry(
            run_dir=config.run_dir,
            run_id=config.run_id,
            level=level,
            record_index=record_index,
            ocid=ocid,
            decision_id=receipt.decision_id,
            timestamp=timestamp,
            cached_tokens=getattr(agent_response, "cached_tokens", None),
            prompt_tokens=getattr(agent_response, "prompt_tokens", None),
            is_stub=is_stub,
        )

    return PassOutcome(
        record_index=record_index,
        level=level,
        ocid=ocid,
        decision_id=receipt.decision_id,
        bundle_path=bundle_path,
        receipt=receipt,
        agent=agent_response,
        timestamp=timestamp,
        is_stub=is_stub,
    )


# ---------------------------------------------------------------------------
# CLI entry point — minimal; the real CLI lives in cli.py (E2-002+)
# ---------------------------------------------------------------------------


def _main() -> None:  # pragma: no cover — exercised via tests
    import argparse

    parser = argparse.ArgumentParser(description="Multi-pass E2 runner (E2-001 stub mode)")
    parser.add_argument("--records", required=True, help="Path to a JSON array of smoke records")
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use StubAgent + StubMeshQuClient (no OpenAI/MeshQu credentials needed)",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Where to write results/runs/<run_id>/. Defaults to <repo>/procurement-context-gradient/results",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id; defaults to a fresh UUID prefixed by 'e2-001-stub-'",
    )
    args = parser.parse_args()

    if not args.stub:
        raise SystemExit(
            "E2-001 only supports --stub mode. Live mode lands in E2-002..006."
        )

    records_path = Path(args.records).resolve()
    with records_path.open("r", encoding="utf-8") as fp:
        records = json.load(fp)

    runner_dir = Path(__file__).resolve().parent.parent
    repo_dir = runner_dir.parent.parent  # procurement-context-gradient/runner/ -> repo root
    e2_dir = runner_dir.parent  # procurement-context-gradient/
    results_dir = Path(args.results_dir) if args.results_dir else e2_dir / "results"
    run_id = args.run_id or f"e2-001-stub-{uuid.uuid4()}"
    run_dir = results_dir / "runs" / run_id

    config = MultiPassConfig(
        run_id=run_id,
        run_phase="dry-run",
        repo_dir=repo_dir,
        run_dir=run_dir,
        prompts_dir=runner_dir / "prompts",
        policy_snapshot_path=e2_dir / "policy" / "policy-snapshot-cbf12348.json",
    )

    summary = run_multi_pass(
        config=config,
        records=records,
        agent=StubAgent(),
        meshqu_client=StubMeshQuClient(),
    )

    print(
        f"Wrote {len(summary.outcomes)} bundles "
        f"({len(records)} records × {len(config.levels)} levels) "
        f"to {run_dir}"
    )


if __name__ == "__main__":  # pragma: no cover
    _main()
