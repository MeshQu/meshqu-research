# Licensing for the data exports

Different layers of this repository carry different licences. This file states which applies where.

## Code

All code in this repository, including `data/build_export.py`, the runners, and the analysis scripts, is MIT licensed. See the repository [`LICENSE`](../LICENSE).

## Writeups

The long-form writeups under each experiment's `writeup/` directory are licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). You may share and adapt them with attribution.

## Source records

The procurement records underlying every receipt derive from the UK Contracts Finder OCDS feed, published by the UK Government under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

Required attribution:

> Contains public sector information licensed under the Open Government Licence v3.0.

The corpus does not redistribute raw full OCDS releases. Each receipt references its source record by OCID and carries only the extracted evidence fields the policy evaluated.

Retrieving full releases needs care. The Contracts Finder Search API does not support lookup by OCID: it silently strips an `?ocid=` parameter and returns the latest releases site-wide, so that pattern hands back unrelated records without any error. Two routes work. Paginate the publication-window feed (`publishedFrom` / `publishedTo` plus `links.next`) and filter by OCID client-side, or open a known notice directly at `https://www.contractsfinder.service.gov.uk/Notice/<release_id>`. See `procurement-decisions/planning/substrate.md` for the sample windows E1 used.

## Receipts and parquet exports

The receipt corpora (`corpus.tar`) and the derived parquet files in this directory combine MIT-licensed tooling output with OGL-derived evidence fields. Treat them as OGL v3.0 derived data: reuse freely, keep the attribution line above, and cite the repository.

## Suggested citation

> Carter, S. (2026). MeshQu Research: Receipt-Anchored Evaluation corpora E1, E2, E3 (MRP-2026-02, MRP-2026-03, MRP-2026-04). MeshQu Ltd. https://github.com/MeshQu/meshqu-research

When citing a single experiment, cite its MRP identifier and release tag. E1 is MRP-2026-02. E2 is MRP-2026-03. E3 is MRP-2026-04, tag `v1.0-mrp-2026-04`.
