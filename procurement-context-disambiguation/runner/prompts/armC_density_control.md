<!--
E3 Arm C — density-control payload. LOCKED CONTENT (SHA-bound at pre-registration).

Purpose: a volume-matched control for the L3 decomposition. It occupies the same
prompt slot as E2's 4-precedent block and carries comparable token count and the same
number of discrete units (4), but contains NO concrete prior records, NO verdicts, and
NO compliance-alert tone. It adds *volume*, not *signal* and not *threat*.

Neutrality contract (inspected before lock):
  (i)  no verdict / decision words (ALLOW / REVIEW / DENY / violation / breach / pass / fail)
  (ii) no high-alert compliance imperatives (must enforce / material failure / severe risk /
       non-compliance / mandatory / penalty)
  (iii) dry, structural, administrative register only — describes the data format and generic
        process, never assesses the record above.
Matched to E2's L3 precedent payload on: 4 discrete units · comparable token count · same slot.
Exact token-count parity is verified against the rendered E2 precedent payload at build time.
-->

## Reference 1: record-structure note

- **Field group**: award identifiers
- **Schema source**: OCDS 1.1 release package
- **Cardinality**: one award block per contracting process
- **Population stage**: completed at the award stage of the process
- **Encoding**: ISO 8601 dates, ISO 4217 currency codes
- **Typical contents**: buyer identifier, supplier identifier, award value, award date
- **Cross-references**: links to the planning and tender stages of the same process
- **Provenance**: published by the contracting authority to the national contracts register
- This reference describes the data format only and carries no assessment of the record above.

## Reference 2: record-structure note

- **Field group**: supplier and party records
- **Schema source**: OCDS 1.1 parties array
- **Cardinality**: one entry per distinct party (buyer, supplier, tenderer)
- **Population stage**: accumulated across the planning, tender, and award stages
- **Encoding**: organisation identifiers follow the org-id scheme prefix convention
- **Typical contents**: legal name, registered identifier, role array, address block
- **Cross-references**: party `id` values are referenced from award and contract blocks
- **Provenance**: drawn from the contracting authority's submitted release
- This reference describes the data format only and carries no assessment of the record above.

## Reference 3: record-structure note

- **Field group**: timing and milestone fields
- **Schema source**: OCDS 1.1 tender and award date fields
- **Cardinality**: one tender period and one award date per process
- **Population stage**: set at tender publication and at award
- **Encoding**: date-time values in ISO 8601; durations as start/end pairs
- **Typical contents**: tender period start and end, award date, contract period
- **Cross-references**: tender period and award date appear within the tender and award blocks respectively
- **Provenance**: recorded by the contracting authority at each process stage
- This reference describes the data format only and carries no assessment of the record above.

## Reference 4: record-structure note

- **Field group**: procedure and method descriptors
- **Schema source**: OCDS 1.1 tender procurement-method fields
- **Cardinality**: one method descriptor per process
- **Population stage**: declared at tender publication
- **Encoding**: method drawn from the open / selective / limited codelist
- **Typical contents**: procurement method, method rationale, framework indicator
- **Cross-references**: method descriptor appears alongside the award and party blocks within the release structure
- **Provenance**: declared by the contracting authority in the tender notice
- This reference describes the data format only and carries no assessment of the record above.
