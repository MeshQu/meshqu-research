# Experiment 3 (E3) — results

**Status**: empty. No corpus collected yet.

Once a run completes, results live here per the convention:

```
results/
├── runs/
│   └── phase-X-YYYYMMDD-HHMMSS-Z/    (one directory per run)
│       ├── L0/                        (or whatever rungs E3 uses)
│       ├── L1/
│       ├── ...
│       ├── diagnostic/                (Permuted-Policy or equivalent)
│       ├── observability/
│       │   └── screenshots/           (Grafana captures)
│       ├── manifest.json
│       ├── audit/
│       │   └── checkpoints.jsonl
│       └── cache_telemetry.jsonl
├── notebook/
│   └── cross_level_analysis/          (or equivalent; analysis notebooks)
├── writeup-DRAFT.md                   (the publication source)
├── figures-spec.md                    (hand-off spec for iko-tools)
└── reader-briefing.md                 (for the independent reader)
```

Per `programme/PROCESS.md`:
- Corpus is the load-bearing artefact. Treat as read-only after collection.
- Bundle envelope is signed (Ed25519) and anchored (Rekor).
- Every claim in `writeup-DRAFT.md` must be re-derivable from on-disk bundles.
