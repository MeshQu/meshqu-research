# Run trail. Not analysis input.

This directory is the pre-export execution trail for E2. It holds smoke runs, dry runs, superseded runs, and raw runner emissions. The raw bundles here use the flat pre-export schema and carry `transparency_anchor: null` by design. They are preserved for auditability.

Do not analyse from this directory. The canonical dataset is [`../corpus.tar`](../corpus.tar): 1,429 exported v2 bundles with signatures and Rekor transparency proofs.

For orientation only:

- `SUPERSEDED-*` directories are failed or aborted runs, kept as audit trail.
- `smoke-*` and `dry-run-*` are pre-production shakedowns.
- `phase-2-20260522-101324-Z` is the production run. Its export became `../corpus.tar`. Receipt correlation ids in the corpus point back to this run id.
