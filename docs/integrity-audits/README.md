# Integrity Audits

Dated, public records of cryptographic and methodological audits of the MeshQu
Research Programme (MRP) corpus and its claims. Each audit treats a load-bearing
claim as **falsifiable**: it specifies a check that could resolve the claim in
either direction, runs the check against an independent source of truth (the
public transparency log, the on-disk artefacts, the production code path), and
records the result — **whether or not it found a problem**. Publishing the check
is the discipline; an audit that confirms a claim is as much a part of the record
as one that overturns it.

Audits follow the F-series register shape used across the programme: a status
disposition from the locked vocabulary, an evidence block with denominators,
explicit anti-claims, and a forward/closure track.

| ID | Date | Subject | Disposition |
|----|------|---------|-------------|
| [IA-2026-01](2026-06-09-rekor-anchoring-scope.md) | 2026-06-09 | Rekor anchoring across E1 / E2 / E3 | **Confirmed** (anchoring) · **Discovered** (reproducibility-instruction gap) |
| [IA-2026-02](2026-08-04-corpus-lineage-and-receipt-count.md) | 2026-08-04 | Programme receipt count and E1 corpus lineage | **Refuted** (the ~3,061 count; 3,044 is correct) · **Discovered** (agent-output sidecar overwritten on repeat OCDS releases) · **Confirmed** (both published verdict splits) |
| [IA-2026-03](2026-08-04-when-gate-case-blast-radius.md) | 2026-08-04 | When-gate case-sensitivity (tradequ #761) blast radius over E1 / E2 / E3 | **Confirmed** (CLEAN — zero collisions across 3,044 receipts; null delta proven; pinned by `scripts/check_gate_case_collisions.py`) |
