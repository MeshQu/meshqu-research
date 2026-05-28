"""Arm-keyed orchestrator — flat dispatch over E3's independent probe arms.

This module is the structural rewrite of E2's level-batched
multi-pass orchestrator. E2 ladders L0 → L1 → L2 → L3 → L4 additively;
E3 doesn't (the design's whole point is to *disambiguate* what L3 was
doing by isolating the three properties E2's L3 conflated). Here, each
arm is independent — there's no outer level dimension, no cumulative
prefix. The orchestrator just walks the record list, dispatches the
requested arm against each record, and signs the resulting receipt.

## What changed from E2 (concretely)

- ``MultiPassConfig.levels`` → ``RunConfig.arm``: a single arm name
  identifies the run condition. A full E3 sweep is N independent
  arm-runs, not one ladder-run.
- ``compose_user_message(level, ...)`` + ``default_main_handlers()``
  removed. The arm registry in ``meshqu_runner.arms`` is now the only
  composition path: ``arms.dispatch(arm_name, record)`` returns the
  fully rendered user message.
- ``GOVERNANCE_CONTEXT_LEVEL_FIELD`` (the L0..L4 marker E2 injected
  into ``context.fields``) is gone. The arm name and the seven
  arm-aware integrity fields (``l3_arm``, ``nudge_excised``,
  ``model_id``, ``model_sampling``, ``diagnostic``,
  ``policy_permutation_seed``, ``runner_git_commit``, ``prereg_tag``)
  ride into the integrity hash via ``arms.inject_arm_fields`` —
  same audit-only-but-hash-bound pattern.

## What didn't change

- The per-(record, arm) bundle envelope is still v1. The fields the
  envelope carries shift slightly (no ``governance_context_level``;
  instead ``arm_name``), but the envelope's *format* is unchanged so
  that downstream verifiers and the writeup's analysis layer can be
  carried forward.
- ``StubAgent`` + ``StubMeshQuClient`` are unchanged surface-wise:
  they still emit deterministic ReceiptSummaries with
  locally-computed integrity hashes. Stub bundles still carry
  ``is_stub: true`` and will not verify at verify.meshqu.com.
- Idempotency-key derivation still includes the run condition (the
  arm name now instead of the level); MeshQu's idempotency cache
  treats ``arm_a`` and ``arm_b`` for the same OCID as distinct runs.

## Bundle envelope version

Still v1. The added integrity fields are *additive* — every existing
field is preserved, the wrapper format is the same — so no bump is
required. (See ``planning/build_packages/e3-001-runner-foundation.md``
§"Stop conditions": if the envelope rule conflicts with the added
fields, stop and surface; the foundation does not silently bump.)
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
from .arms import (
    ARM_NAMES,
    PREREG_TAG,
    ArmProfile,
    dispatch as arm_dispatch,
    get_profile as arm_profile,
    inject_arm_fields,
)
from .audit import AuditWriter
from .eval_loop import build_user_message
from .meshqu_client import (
    MeshQuClient,
    ReceiptSummary,
    inject_agent_fields,
)
from .run_manifest import RunPhase, resolve_git_commit


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUNDLE_ENVELOPE_VERSION = 1
"""Version of the bundle wrapper at
``results/runs/<run_id>/<arm_name>/<decision_id>.bundle.json``.
Unchanged from E2 — the wrapper format is structurally identical, the
arm-aware integrity fields ride in via ``context.fields``."""


# ---------------------------------------------------------------------------
# Per-(record, arm) outcome
# ---------------------------------------------------------------------------


@dataclass
class PassOutcome:
    """What the orchestrator produced for one (record, arm) pair."""

    record_index: int
    arm_name: str
    ocid: str | None
    decision_id: str
    bundle_path: Path
    receipt: ReceiptSummary
    agent: AgentResponse
    timestamp: str  # ISO-8601 UTC seconds
    is_stub: bool


@dataclass
class ArmRunSummary:
    """All PassOutcomes for a single-arm run."""

    run_id: str
    run_dir: Path
    arm_name: str
    outcomes: list[PassOutcome] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stub Agent + MeshQuClient — enable hermetic tests + --dry CLI mode
# ---------------------------------------------------------------------------


@dataclass
class StubAgent:
    """Deterministic stand-in for Agent. Produces a fixed REVIEW verdict
    with a reasoning string keyed off the user_message hash. Lets the
    orchestrator run end-to-end without OpenAI."""

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

    The integrity-hash binding is structurally equivalent to MeshQu's
    real API (canonical-JSON of the fields map, SHA-256) so test
    assertions about which fields are hash-bound are meaningful. Stub
    receipts are NOT signed and NOT anchored to Rekor — they would
    never verify at verify.meshqu.com. The bundle's ``is_stub: true``
    flag makes this explicit."""

    tenant_id: str = "stub-tenant"
    policy_snapshot_id: str = "stub-policy-snapshot"
    fixed_decision: str = "REVIEW"

    # Captured payloads — test hook. Each record_decision call appends
    # the *fields* mapping the stub hashed, so tests can assert "this
    # arm's receipt carried the seven E3-specific integrity fields".
    captured_field_payloads: list[dict[str, Any]] = field(default_factory=list)

    def record_decision(
        self,
        *,
        context: Mapping[str, Any],
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> ReceiptSummary:
        fields = dict(context.get("fields") or {})
        self.captured_field_payloads.append(dict(fields))
        canonical = canonical_json_bytes(fields)
        integrity_hash = hashlib.sha256(canonical).hexdigest()
        evaluated_rules_hash = hashlib.sha256(b"stub-evaluated-rules").hexdigest()
        timestamp = _utc_now_iso()

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


def _idempotency_key(run_id: str, record_index: int, ocid: str | None, arm_name: str) -> str:
    """Per-(run, record, arm) idempotency. The arm name is part of the
    key so MeshQu's cache doesn't conflate Arm A's evaluation of an
    OCID with Arm B's."""
    discriminator = ocid or f"record-{record_index}"
    raw = f"{run_id}/{arm_name}/{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_ocid(record: Mapping[str, Any]) -> str | None:
    """Pull the OCID out of a record. Records carry it under ``ocid``
    (smoke fixture pattern) or under ``metadata.ocid`` (substrate
    output shape). Falls back to None when neither is present."""
    if "ocid" in record and isinstance(record["ocid"], str):
        return record["ocid"]
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("ocid"), str):
        return metadata["ocid"]
    return None


def _sha256_file(path: Path) -> str:
    with path.open("rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


# ---------------------------------------------------------------------------
# Bundle writer
# ---------------------------------------------------------------------------


def write_bundle(
    *,
    run_dir: Path,
    arm_name: str,
    decision_id: str,
    record_index: int,
    ocid: str | None,
    receipt: ReceiptSummary,
    agent_response: AgentResponse,
    context_fields_canonical: bytes,
    timestamp: str,
    is_stub: bool,
) -> Path:
    """Persist the v1 bundle file for one (record, arm) pair.

    Layout: ``<run_dir>/<arm_name>/<decision_id>.bundle.json``

    The bundle carries everything a verifier needs to recompute the
    integrity hash:

    - ``bundle_envelope_version: 1`` (the wrapper's version; the
      nested MeshQu receipt carries its own ``receipt_schema_version``)
    - ``arm_name`` (replaces E2's ``governance_context_level``)
    - ``context_fields_canonical_json`` (the bytes MeshQu hashed)
    - ``receipt`` (the MeshQu-issued ReceiptSummary)
    - ``agent`` (the AgentResponse; reasoning hash mirrors receipt
      binding)

    Plus operational fields (``is_stub``, ``record_index``, ``ocid``,
    ``timestamp``) for indexing.
    """
    bundle_path = run_dir / arm_name / f"{decision_id}.bundle.json"
    payload: dict[str, Any] = {
        "bundle_envelope_version": BUNDLE_ENVELOPE_VERSION,
        "arm_name": arm_name,
        "is_stub": is_stub,
        "record_index": record_index,
        "ocid": ocid,
        "decision_id": decision_id,
        "timestamp": timestamp,
        "context_fields_canonical_json": context_fields_canonical.decode("utf-8"),
        "receipt": _serialise_receipt(receipt),
        "agent": _serialise_agent(agent_response),
    }
    _atomic_write_json(bundle_path, payload)
    return bundle_path


def _serialise_receipt(receipt: ReceiptSummary) -> dict[str, Any]:
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
    payload = asdict(agent)
    payload["raw_response"] = (payload.get("raw_response") or "")[:512]
    return payload


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------


def write_arm_manifest(
    *,
    run_dir: Path,
    run_id: str,
    run_phase: RunPhase,
    arm_name: str,
    profile: ArmProfile,
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
    """Persist the per-run manifest. Mirrors E2's shape, but the
    level-batched fields are replaced with arm-aware fields."""
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
        # E3 extensions
        "bundle_envelope_version": BUNDLE_ENVELOPE_VERSION,
        "arm_name": arm_name,
        "arm_profile": {
            "l3_arm": profile.l3_arm,
            "nudge_excised": profile.nudge_excised,
            "model_id": profile.model_id,
            "model_sampling": dict(profile.model_sampling),
            "diagnostic": profile.diagnostic,
        },
        "prereg_tag": PREREG_TAG,
        "policy_snapshot_sha256": policy_sha,
        "policy_snapshot_path": str(policy_snapshot_path) if policy_snapshot_path else None,
    }
    path = run_dir / "manifest.json"
    _atomic_write_json(path, manifest)
    return path


# ---------------------------------------------------------------------------
# Run controller — single-arm dispatch
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """All config the arm-aware runner needs.

    One ``RunConfig`` drives one arm-run. A full E3 sweep is N
    independent ``run_arm`` calls (eight if you sweep every arm; in
    practice the dry-run/smoke gating picks a subset).

    ``agent`` + ``meshqu_client`` are pluggable so a test or the
    ``--dry`` CLI flag can inject ``StubAgent`` / ``StubMeshQuClient``.
    When ``None``, the live clients are constructed from
    ``agent_api_key`` + ``meshqu_api_key`` (NOT in scope for E3-001 —
    full live wiring lands in E3-002..006).

    ``policy_permutation_seed`` is required + must be non-None for
    diagnostic arms; must be None for non-diagnostic arms. Enforced
    by ``arms.inject_arm_fields``.
    """

    run_id: str
    run_phase: RunPhase
    repo_dir: Path
    run_dir: Path
    arm_name: str
    policy_snapshot_path: Path | None
    meshqu_api_url: str = "https://api.meshqu.com"
    meshqu_tenant_label: str = "experiment-procurement"
    substrate_adapter_version: str = "0.0-stub"
    substrate_source: Mapping[str, Any] = field(default_factory=dict)
    inter_request_pause_seconds: float = 0.0
    policy_permutation_seed: int | None = None
    # Arm-specific overrides for the receipt integrity payload — fall
    # back to the profile defaults when None. The CLI's ``--model``
    # flag lands here.
    model_id_override: str | None = None
    model_sampling_override: Mapping[str, Any] | None = None


def run_arm(
    *,
    config: RunConfig,
    records: Sequence[Mapping[str, Any]],
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    audit_writer: AuditWriter | None = None,
    is_stub: bool | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    handler_kwargs: Mapping[str, Any] | None = None,
) -> ArmRunSummary:
    """Drive a single-arm run over the record set.

    Returns an ``ArmRunSummary``; also writes:

    - ``<run_dir>/manifest.json``
    - ``<run_dir>/<arm_name>/<decision_id>.bundle.json`` for every
      record
    - ``<run_dir>/audit/`` via the optional ``AuditWriter`` (anomaly
      trail)

    ``handler_kwargs`` is forwarded verbatim to ``arms.dispatch``;
    arm-specific helpers (precedent selector, policy snapshot, etc.)
    land via that map. The foundation's placeholder handlers ignore
    unknown kwargs; later real handlers will require them.

    ``is_stub`` defaults to True when both clients are stubs; explicit
    override available for tests that mix stub and live."""
    if config.arm_name not in ARM_NAMES:
        raise ValueError(
            f"Unknown arm {config.arm_name!r}. Valid arms: {ARM_NAMES!r}"
        )

    if is_stub is None:
        is_stub = isinstance(agent, StubAgent) and isinstance(meshqu_client, StubMeshQuClient)

    profile = arm_profile(config.arm_name)

    # Records are processed in OCID-ascending order for determinism.
    # Records missing an OCID sort to the end — surfaces missing OCIDs
    # in downstream auditing.
    sorted_records = sorted(
        list(records),
        key=lambda r: (_extract_ocid(r) is None, _extract_ocid(r) or ""),
    )

    config.run_dir.mkdir(parents=True, exist_ok=True)

    sha, _dirty = resolve_git_commit(config.repo_dir)

    # Manifest first — every later artefact references run_id.
    write_arm_manifest(
        run_dir=config.run_dir,
        run_id=config.run_id,
        run_phase=config.run_phase,
        arm_name=config.arm_name,
        profile=profile,
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

    summary = ArmRunSummary(
        run_id=config.run_id,
        run_dir=config.run_dir,
        arm_name=config.arm_name,
    )

    for record_index, record in enumerate(sorted_records):
        if record_index > 0 and config.inter_request_pause_seconds > 0:
            sleep_fn(config.inter_request_pause_seconds)

        outcome = _process_record(
            config=config,
            record_index=record_index,
            record=record,
            profile=profile,
            runner_git_commit=sha,
            agent=agent,
            meshqu_client=meshqu_client,
            is_stub=is_stub,
            handler_kwargs=dict(handler_kwargs or {}),
        )
        summary.outcomes.append(outcome)

    return summary


def _process_record(
    *,
    config: RunConfig,
    record_index: int,
    record: Mapping[str, Any],
    profile: ArmProfile,
    runner_git_commit: str,
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    is_stub: bool,
    handler_kwargs: Mapping[str, Any],
) -> PassOutcome:
    """Single (record, arm) pass. Extracted so tests can call it
    deterministically without driving the outer loop."""
    ocid = _extract_ocid(record)

    decision_type = record.get("decision_type", "procurement_decision")
    fields = dict(record.get("fields") or {})
    substrate_notes = dict(record.get("substrate_notes") or {})

    context: dict[str, Any] = {
        "decision_type": decision_type,
        "fields": fields,
        "metadata": dict(record.get("metadata") or {"ocid": ocid}),
    }

    # Arm handler returns the FULLY rendered user message — no
    # additive composition, no level prefix. The handler is
    # self-contained (see ``arms`` module docstring).
    user_message = arm_dispatch(config.arm_name, record, **handler_kwargs)

    # Stub mode tolerates a non-OK parse_status. Live-mode skip
    # behaviour lands in subsequent packages.
    agent_response = agent.evaluate(user_message)

    enriched_context = inject_agent_fields(
        context,
        agent_model_id=getattr(agent, "model_id", LOCKED_MODEL_ID),
        agent_temperature=getattr(agent, "temperature", LOCKED_TEMPERATURE),
        agent_prompt_sha256=getattr(agent, "system_prompt_sha256", "0" * 64),
        agent_reasoning_sha256=agent_response.reasoning_sha256,
        agent_recommended_verdict=agent_response.verdict or "REVIEW",
        agent_recommended_action=agent_response.recommended_action,
    )

    # E3 integrity-payload extension. Adds the seven arm-aware fields
    # to ``context.fields`` so MeshQu binds them into the integrity
    # hash.
    enriched_context = inject_arm_fields(
        enriched_context,
        arm_name=config.arm_name,
        runner_git_commit=runner_git_commit,
        profile=profile,
        policy_permutation_seed=config.policy_permutation_seed,
        model_id=config.model_id_override,
        model_sampling=config.model_sampling_override,
    )

    idempotency_key = _idempotency_key(
        config.run_id, record_index, ocid, config.arm_name
    )
    receipt = meshqu_client.record_decision(
        context=enriched_context,
        idempotency_key=idempotency_key,
        correlation_id=f"{config.run_id}/{config.arm_name}/{record_index}",
    )

    canonical = canonical_json_bytes(enriched_context["fields"])

    timestamp = _utc_now_iso()
    bundle_path = write_bundle(
        run_dir=config.run_dir,
        arm_name=config.arm_name,
        decision_id=receipt.decision_id,
        record_index=record_index,
        ocid=ocid,
        receipt=receipt,
        agent_response=agent_response,
        context_fields_canonical=canonical,
        timestamp=timestamp,
        is_stub=is_stub,
    )

    return PassOutcome(
        record_index=record_index,
        arm_name=config.arm_name,
        ocid=ocid,
        decision_id=receipt.decision_id,
        bundle_path=bundle_path,
        receipt=receipt,
        agent=agent_response,
        timestamp=timestamp,
        is_stub=is_stub,
    )


# ---------------------------------------------------------------------------
# Back-compat shims — eased migration for inherited callers
# ---------------------------------------------------------------------------
#
# E2 callers reach for ``run_multi_pass`` and ``MultiPassConfig`` /
# ``MultiPassSummary``. Those names no longer fit the E3 model (no
# ladder, no level sweep), but to keep diff churn minimal in code
# paths that haven't been migrated yet (e.g. inherited scripts in
# ``scripts/`` that subsequent packages will rewrite), we expose
# thin aliases that route to the arm-aware machinery. Anyone reaching
# for these in E3 code is asked to switch to the arm-aware names.

MultiPassConfig = RunConfig
"""Deprecated alias for ``RunConfig``. Inherited scripts may still
import this name; new E3 code uses ``RunConfig``."""

MultiPassSummary = ArmRunSummary
"""Deprecated alias for ``ArmRunSummary``."""


def run_multi_pass(*args: Any, **kwargs: Any) -> ArmRunSummary:  # pragma: no cover
    """Deprecated. Use ``run_arm`` directly."""
    raise NotImplementedError(
        "run_multi_pass() was E2's level-batched orchestrator and has been "
        "replaced by run_arm() in E3. Update your caller to pass arm_name "
        "via RunConfig and invoke run_arm() instead."
    )
