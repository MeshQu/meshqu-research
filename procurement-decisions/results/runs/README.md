# Run trail location. Not analysis input.

This directory is where E1's per-run execution artefacts were written (manifest, run_end, decision traces, checkpoints, agent outputs, screenshots). For E1 they were preserved on the operator's disk and deliberately not committed; the directory is gitignored and this README is the only tracked file in it. The committed execution evidence for E1 lives in [`../audit/`](../audit/), [`../notebook/`](../notebook/), and [`../observability/`](../observability/).

Do not look here for data. The canonical dataset is [`../corpus.tar`](../corpus.tar): 283 exported v2 bundles with signatures and Rekor transparency proofs.

One naming trap is worth stating plainly. E1's production run is named `dry-run-7ddf7274-695f-4b1b-a335-b8ed006cc26d`. Despite the `dry-run` prefix, it is the real 300-record corpus run of 2026-05-18. Its export became `../corpus.tar`, and receipt correlation ids in the corpus point back to this run id. The naming is a historical accident of the runner's defaults and is preserved because the receipts and the notebook already reference it.
