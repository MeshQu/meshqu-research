"""Permuted-Policy diagnostic driver — runs the 14-record auxiliary
L4 pass and writes bundles under `<run_dir>/diagnostic/`.

## Contract

- INPUT: the same sorted-by-OCID record sequence the main run sees,
  plus the agent + meshqu_client (stub or live), prompts, and run_dir.
- FILTER: only records whose OCID satisfies
  `is_in_permuted_subset(ocid)` are processed (14 of 283 on the E1
  corpus). Records with no OCID are skipped (we can't deterministically
  subset them).
- COMPUTE: one L4_PERMUTED pass per subset record. Reuses E2-005's
  cache-friendly composition.
- BIND: the receipt's `fields` map carries three diagnostic-specific
  keys before hashing —
    - `governance_context_level: "L4_PERMUTED"` (the level marker)
    - `policy_permutation_seed: 0`
    - `l4_envelope_sha256: <sha of permuted rendering>`
  All three ride into the integrity hash via the same canonical-JSON
  injection point main-run levels use.
- WRITE: bundles land at `<run_dir>/diagnostic/<decision_id>.bundle.json`
  (NOT `<run_dir>/L4_PERMUTED/...`). The diagnostic directory is
  isolated so corpus-level analyses can skip it with a single glob.
- SIDECAR: the rendered permuted policy's `_permutation_log` is also
  written once to `<run_dir>/diagnostic/permutation_log.json` so a
  verifier can pin which exact inversion was applied without
  re-deriving it.

## What this driver does NOT do

- It does not write its own manifest. The diagnostic is auxiliary to
  the main multi-pass run; the parent manifest's `levels` field gains
  `"L4_PERMUTED"` only if the caller chooses to advertise it.
- It does not append to `cache_telemetry.jsonl`. The diagnostic is too
  small (14 calls) to skew the main-run telemetry distribution and we
  don't want it conflated with L4 cache stats.
- It does not call the audit writer. Anomaly behaviour for the
  diagnostic is intentionally light — if a Permuted-Policy call fails
  the orchestrator records the error in the returned summary and the
  caller decides whether to escalate.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..agent import Agent, AgentResponse, LOCKED_MODEL_ID, LOCKED_TEMPERATURE
from ..eval_loop import build_user_message
from ..level_handlers import (
    GovernanceContextLevel,
    LevelHandler,
    compose_user_message,
    default_main_handlers,
)
from ..meshqu_client import MeshQuClient, ReceiptSummary, inject_agent_fields
from ..multi_pass import (
    BUNDLE_ENVELOPE_VERSION,
    GOVERNANCE_CONTEXT_LEVEL_FIELD,
    PassOutcome,
    StubAgent,
    StubMeshQuClient,
    _atomic_write_json,
    _extract_ocid,
    _idempotency_key,
    _serialise_agent,
    _serialise_receipt,
    _utc_now_iso,
    canonical_json_bytes,
)
from ..prompt_loader import LoadedPrompts
from ..context_levels.level_l4_permuted import (
    L4_ENVELOPE_SHA256_FIELD,
    L4PermutedPolicyHandler,
    POLICY_PERMUTATION_SEED_FIELD,
    build_l4_permuted_handler,
)
from .permute_policy import LOCKED_PERMUTATION_SEED, PERMUTATION_LOG_KEY
from .subset import is_in_permuted_subset


DIAGNOSTIC_SUBDIR = "diagnostic"
"""The subdirectory under `<run_dir>/` where Permuted-Policy receipts
land. Locked — verifiers and analysers identify the diagnostic
population by this exact path component."""

DIAGNOSTIC_LEVEL: GovernanceContextLevel = "L4_PERMUTED"

PERMUTATION_LOG_FILENAME = "permutation_log.json"
"""Sidecar inside `<run_dir>/diagnostic/` recording the exact per-rule
inversion that the diagnostic applied. Written once per run."""


@dataclass
class DiagnosticSummary:
    """All outcomes from a single Permuted-Policy diagnostic pass."""

    run_id: str
    diagnostic_dir: Path
    subset_ocids: list[str]
    outcomes: list[PassOutcome] = field(default_factory=list)
    skipped_ocids: list[str | None] = field(default_factory=list)


def diagnostic_handlers(
    *,
    policy_path: Path,
    seed: int = LOCKED_PERMUTATION_SEED,
    main_handlers: Mapping[GovernanceContextLevel, LevelHandler] | None = None,
) -> dict[GovernanceContextLevel, LevelHandler]:
    """Build a handler registry that adds an `"L4_PERMUTED"` slot
    holding a permuted-policy L4 handler.

    L0..L3 are taken from the supplied `main_handlers` (defaults to
    the production main registry). The original `"L4"` slot is
    preserved verbatim — it carries the unperturbed handler — because
    callers may run the diagnostic in the SAME session as the main
    multi-pass and we don't want to silently corrupt the main run by
    overwriting its L4 slot.

    The orchestrator's `compose_user_message(level="L4_PERMUTED", ...)`
    looks up the target handler by the input level (`handlers["L4_PERMUTED"]`)
    and detects its `compose_full_message`. The lower-level addenda
    (L0..L3) come from `MAIN_LEVELS` iteration inside
    `compose_full_message`, which never touches the `"L4"` slot —
    so the permuted handler being absent from the `"L4"` slot is
    irrelevant for diagnostic composition.
    """
    base = dict(main_handlers) if main_handlers is not None else default_main_handlers()
    permuted_handler = build_l4_permuted_handler(policy_path, seed=seed)
    base[DIAGNOSTIC_LEVEL] = permuted_handler
    return base


def _write_diagnostic_bundle(
    *,
    diagnostic_dir: Path,
    decision_id: str,
    record_index: int,
    ocid: str | None,
    receipt: ReceiptSummary,
    agent: AgentResponse,
    context_fields_canonical: bytes,
    timestamp: str,
    is_stub: bool,
) -> Path:
    """Persist a Permuted-Policy bundle. Layout mirrors the main-run
    bundle (`bundle_envelope_version: 1`, same field set, same
    serialisation) except:

    - Path is `<run_dir>/diagnostic/<decision_id>.bundle.json` (NOT
      `<run_dir>/L4_PERMUTED/...`).
    - `governance_context_level` is `"L4_PERMUTED"`.

    The same `_atomic_write_json` is used so crash-safety is identical
    to the main path.
    """
    bundle_path = diagnostic_dir / f"{decision_id}.bundle.json"
    payload: dict[str, Any] = {
        "bundle_envelope_version": BUNDLE_ENVELOPE_VERSION,
        "governance_context_level": DIAGNOSTIC_LEVEL,
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


def _write_permutation_log_sidecar(
    *,
    diagnostic_dir: Path,
    permuted_policy: Mapping[str, Any],
    envelope_sha256: str,
) -> Path:
    """Write the permutation log + envelope SHA sidecar.

    The receipt itself binds the envelope SHA into its integrity hash;
    this sidecar gives an offline analyst (or a future
    independent-verifier script) the *log entries* without having to
    re-run `permute_policy(...)` and recompute. The log is a function
    of (policy snapshot, seed) so the sidecar is also a function of
    those two inputs — deterministic and re-creatable.
    """
    log_entry = permuted_policy.get(PERMUTATION_LOG_KEY)
    if log_entry is None:
        raise RuntimeError(
            "Permuted policy is missing its _permutation_log key; cannot "
            "write the diagnostic sidecar."
        )
    sidecar_path = diagnostic_dir / PERMUTATION_LOG_FILENAME
    payload = {
        "diagnostic": "permuted-policy",
        "seed": log_entry["seed"],
        "permuted_envelope_sha256": envelope_sha256,
        "permutation_log": log_entry["entries"],
    }
    _atomic_write_json(sidecar_path, payload)
    return sidecar_path


def run_permuted_diagnostic(
    *,
    run_id: str,
    run_dir: Path,
    prompts: LoadedPrompts,
    policy_path: Path,
    records: Sequence[Mapping[str, Any]],
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    handlers: Mapping[GovernanceContextLevel, LevelHandler] | None = None,
    seed: int = LOCKED_PERMUTATION_SEED,
    is_stub: bool | None = None,
    inter_request_pause_seconds: float = 0.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> DiagnosticSummary:
    """Drive the Permuted-Policy diagnostic pass.

    Returns a DiagnosticSummary; also writes:
      - <run_dir>/diagnostic/<decision_id>.bundle.json  (one per subset record)
      - <run_dir>/diagnostic/permutation_log.json       (one per run)

    `handlers` defaults to `diagnostic_handlers(policy_path=..., seed=...)`.
    Callers that want to swap the L0..L3 handlers (e.g. tests using
    stub-shaped handlers) can pass a pre-built registry; it MUST carry
    the `L4_PERMUTED` slot set to a permuted handler bound to the same
    policy_path + seed.

    `is_stub` defaults to True when both clients are stubs; explicit
    override available for tests that mix.

    OCID-less records in `records` are skipped (we can't deterministically
    subset them); their OCIDs (None) are accumulated in
    `summary.skipped_ocids` so the caller can audit.
    """
    if handlers is None:
        handlers = diagnostic_handlers(policy_path=policy_path, seed=seed)

    if DIAGNOSTIC_LEVEL not in handlers:
        raise RuntimeError(
            f"diagnostic handlers registry is missing the {DIAGNOSTIC_LEVEL!r} slot"
        )
    permuted_handler = handlers[DIAGNOSTIC_LEVEL]
    if not isinstance(permuted_handler, L4PermutedPolicyHandler):
        raise RuntimeError(
            f"diagnostic handlers' {DIAGNOSTIC_LEVEL!r} slot must be an "
            f"L4PermutedPolicyHandler instance (got {type(permuted_handler).__name__})"
        )

    if is_stub is None:
        is_stub = isinstance(agent, StubAgent) and isinstance(meshqu_client, StubMeshQuClient)

    # Eagerly render so we have the envelope SHA available for the
    # integrity-bound fields and so the collision-with-main-L4 check
    # runs before we touch the network.
    permuted_handler.render(prompts)
    envelope_sha256 = permuted_handler.rendered_sha256
    permuted_policy = permuted_handler.permuted_policy

    diagnostic_dir = run_dir / DIAGNOSTIC_SUBDIR
    diagnostic_dir.mkdir(parents=True, exist_ok=True)

    # Write the sidecar once. Idempotent — the permutation is a pure
    # function of (policy, seed) so re-runs overwrite with identical
    # bytes.
    _write_permutation_log_sidecar(
        diagnostic_dir=diagnostic_dir,
        permuted_policy=permuted_policy,
        envelope_sha256=envelope_sha256,
    )

    # Sort the input records by OCID, the same way the main multi-pass
    # orchestrator does. The diagnostic processes its 14-record subset
    # in this same ascending OCID order so cross-run analyses can
    # zip-align by index.
    sorted_records = sorted(
        list(records),
        key=lambda r: (_extract_ocid(r) is None, _extract_ocid(r) or ""),
    )

    subset_ocids = [
        _extract_ocid(r)
        for r in sorted_records
        if _extract_ocid(r) and is_in_permuted_subset(_extract_ocid(r) or "")
    ]
    subset_ocids = [o for o in subset_ocids if o is not None]

    skipped: list[str | None] = []
    summary = DiagnosticSummary(
        run_id=run_id,
        diagnostic_dir=diagnostic_dir,
        subset_ocids=list(subset_ocids),
        outcomes=[],
        skipped_ocids=skipped,
    )

    # Subset-aware index: counter for records we actually process. The
    # bundle's record_index reflects the position WITHIN THE
    # DIAGNOSTIC SUBSET (not the position in the parent corpus), so
    # cross-run alignment stays stable if the parent corpus ever
    # changes size.
    diagnostic_index = -1
    first = True

    for record in sorted_records:
        ocid = _extract_ocid(record)
        if ocid is None:
            skipped.append(None)
            continue
        if not is_in_permuted_subset(ocid):
            continue

        diagnostic_index += 1
        if not first and inter_request_pause_seconds > 0:
            sleep_fn(inter_request_pause_seconds)
        first = False

        outcome = _process_diagnostic_pass(
            run_id=run_id,
            diagnostic_dir=diagnostic_dir,
            prompts=prompts,
            record_index=diagnostic_index,
            record=record,
            ocid=ocid,
            handlers=handlers,
            agent=agent,
            meshqu_client=meshqu_client,
            envelope_sha256=envelope_sha256,
            seed=seed,
            is_stub=is_stub,
        )
        summary.outcomes.append(outcome)

    return summary


def _process_diagnostic_pass(
    *,
    run_id: str,
    diagnostic_dir: Path,
    prompts: LoadedPrompts,
    record_index: int,
    record: Mapping[str, Any],
    ocid: str,
    handlers: Mapping[GovernanceContextLevel, LevelHandler],
    agent: Agent | StubAgent,
    meshqu_client: MeshQuClient | StubMeshQuClient,
    envelope_sha256: str,
    seed: int,
    is_stub: bool,
) -> PassOutcome:
    """Single (record, L4_PERMUTED) pass.

    Mirrors `multi_pass._process_pass` step-for-step except:
      - composes against the L4_PERMUTED level (uses the diagnostic
        handler registry's permuted handler);
      - injects three diagnostic-specific fields into context.fields
        BEFORE the MeshQu call so they bind into the integrity hash:
          governance_context_level, policy_permutation_seed,
          l4_envelope_sha256.
    """
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
        level=DIAGNOSTIC_LEVEL,
        record=record,
        ocid=ocid,
        prompts=prompts,
        handlers=handlers,
        base_message=base_user_message,
    )

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

    enriched_fields = dict(enriched_context["fields"])
    enriched_fields[GOVERNANCE_CONTEXT_LEVEL_FIELD] = DIAGNOSTIC_LEVEL
    enriched_fields[POLICY_PERMUTATION_SEED_FIELD] = int(seed)
    enriched_fields[L4_ENVELOPE_SHA256_FIELD] = envelope_sha256
    enriched_context["fields"] = enriched_fields

    # Idempotency key includes the diagnostic level marker AND the seed
    # so a future stochastic-variant run never collides with this
    # seed-0 run for the same record.
    idempotency_key = _idempotency_key(
        run_id, record_index, ocid, f"{DIAGNOSTIC_LEVEL}-seed{seed}"
    )
    receipt = meshqu_client.record_decision(
        context=enriched_context,
        idempotency_key=idempotency_key,
        correlation_id=f"{run_id}/{DIAGNOSTIC_LEVEL}/{record_index}",
    )

    canonical = canonical_json_bytes(enriched_context["fields"])
    timestamp = _utc_now_iso()
    bundle_path = _write_diagnostic_bundle(
        diagnostic_dir=diagnostic_dir,
        decision_id=receipt.decision_id,
        record_index=record_index,
        ocid=ocid,
        receipt=receipt,
        agent=agent_response,
        context_fields_canonical=canonical,
        timestamp=timestamp,
        is_stub=is_stub,
    )

    return PassOutcome(
        record_index=record_index,
        level=DIAGNOSTIC_LEVEL,
        ocid=ocid,
        decision_id=receipt.decision_id,
        bundle_path=bundle_path,
        receipt=receipt,
        agent=agent_response,
        timestamp=timestamp,
        is_stub=is_stub,
    )
