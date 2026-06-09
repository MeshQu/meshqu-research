#!/usr/bin/env python3
"""
build_corpus_tar.py — assemble the canonical corpus.tar for an MRP experiment

Fetches the exported v2 Verification Bundle for every receipt produced during
the experiment's Phase-2 run, then packs them into a single corpus.tar with a
README that matches the convention used for MRP-2026-02 (E1).

The exported bundle is canonically assembled by the meshqu-api public
endpoint:

    GET https://meshqu-api-staging.up.railway.app/v1/receipts/<decision_id>/bundle

The endpoint is public (no auth), rate-limited per IP, and gated by
MESHQU_BUNDLE_EXPORT_ENABLED on the API service. It reads the receipt + the
stored DSSE envelope + the policy snapshot + the trusted keys from the
staging DB and calls @meshqu/core's exportBundle() to produce the v2
wrapper that ships transparency_proof.json bound to the on-log Rekor entry.

The in-repo pre-export run-dir bundles (results/runs/.../<id>.bundle.json)
are the runner's emission artefacts, NOT the canonical exported form — they
have a flat schema and carry transparency_anchor: null because the anchor
metadata is captured at anchor time but only assembled into a v2 bundle on
export. This script reads the decision IDs from those pre-export files and
fetches the canonical exported form for each.

Usage:
    # Probe one decision_id — verify the endpoint works and the bundle has
    # the transparency_proof.json populated. Use this before running the full
    # corpus build.
    python build_corpus_tar.py --probe 54d702ac-8c51-4d59-948f-76293f731fa0

    # Build the full corpus.tar for E2 or E3.
    python build_corpus_tar.py --experiment e2
    python build_corpus_tar.py --experiment e3

    # Test with a small limit before going for the full corpus.
    python build_corpus_tar.py --experiment e3 --limit 5

Output: written to <experiment-root>/results/corpus.tar
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
API_BASE = "https://meshqu-api-staging.up.railway.app"

# Per-call sleep — be polite to the public endpoint's rate limiter
SLEEP_BETWEEN_CALLS_SECONDS = 0.2

# Retry policy on transient failures (network blips, 5xx)
MAX_RETRIES_PER_BUNDLE = 3
RETRY_BACKOFF_SECONDS = 2

EXPERIMENTS = {
    "e2": {
        "id": "MRP-2026-03",
        "title": "Context-gradient corpus",
        "directory": "procurement-context-gradient",
        "run_dir": "procurement-context-gradient/results/runs/phase-2-20260522-101324-Z",
        "run_id": "phase-2-20260522-101324-Z",
        "predictions_lock_tag": "v0.2-predictions-locked",
        "policy_snapshot_id": "cbf12348-6248-48f7-a06f-4e0304cc237e",
        "policy_snapshot_digest": "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d",
        "signing_kid": "meshqu-experiment-procurement-2026-05",
        "agent": "gpt-5.4-2026-03-05 at temperature 0",
        "out_path": "procurement-context-gradient/results/corpus.tar",
    },
    "e3": {
        "id": "MRP-2026-04",
        "title": "Context-disambiguation corpus",
        "directory": "procurement-context-disambiguation",
        "run_dir": "procurement-context-disambiguation/results/runs/phase-2-20260529T092611-Z",
        "run_id": "phase-2-20260529T092611-Z",
        "predictions_lock_tag": "v0.3-predictions-locked",
        "policy_snapshot_id": "cbf12348-6248-48f7-a06f-4e0304cc237e",
        "policy_snapshot_digest": "5d7d800186d4eda4a05f926bcaa34b23d56b31d923016cc6467952ee8fc0cc9d",
        "signing_kid": "meshqu-experiment-procurement-2026-05",
        "agent": "gpt-5.4-2026-03-05 at temperature 0; diagnostic_claude on claude-opus-4-7 (effort: low, no temperature)",
        "out_path": "procurement-context-disambiguation/results/corpus.tar",
    },
}


def enumerate_decision_ids(run_dir: Path) -> list[str]:
    """Walk the experiment's run dir for *.bundle.json files.

    Each filename's stem (minus the .bundle suffix) is the decision_id UUID.
    De-duplicate in case the same decision appears in multiple arm sub-dirs.
    """
    ids: set[str] = set()
    for bundle_path in run_dir.rglob("*.bundle.json"):
        stem = bundle_path.name.removesuffix(".bundle.json")
        if len(stem) == 36 and stem.count("-") == 4:
            ids.add(stem)
    return sorted(ids)


def fetch_bundle(decision_id: str) -> bytes:
    """GET the exported v2 bundle for one decision. Returns raw JSON bytes.

    Retries on transient failures (timeout, 5xx) with backoff; raises after
    MAX_RETRIES_PER_BUNDLE failed attempts.
    """
    url = f"{API_BASE}/v1/receipts/{decision_id}/bundle"
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES_PER_BUNDLE + 1):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/x.meshqu.bundle+json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 422):
                raise RuntimeError(f"HTTP {e.code}") from e
            last_error = e
        except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
            last_error = e
        if attempt < MAX_RETRIES_PER_BUNDLE:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(
        f"Failed to fetch after {MAX_RETRIES_PER_BUNDLE} attempts: {last_error}"
    )


def build_readme(exp: dict, n_bundles: int) -> str:
    """README mirroring E1's corpus.tar convention."""
    return f"""# {exp['directory']} corpus — {exp['id']}

> {n_bundles} cryptographically-verifiable MeshQu receipts on real UK public-procurement records from the Contracts Finder OCDS feed.
> Every bundle in this archive is independently verifiable at <https://verify.meshqu.com> or via the `@meshqu/verifier` CLI.
> See the full writeup at `{exp['directory']}/writeup/writeup.md` in the parent repository.

## What's in this archive

```
bundles/
├── <decision_id>.bundle.json    × {n_bundles}
└── (no other files)
README.md                        ← this file
```

Each `<decision_id>.bundle.json` is a complete v2 receipt bundle (`application/x.meshqu.bundle+json`) carrying:

- `files.receipt.json` — the signed receipt (Ed25519 signature, integrity hash, transparency anchor)
- `files.policy_snapshot.json` — the policy snapshot the receipt evaluated against
- `files.trusted_keys.json` — the public key for the signing kid
- `files.transparency_proof.json` — the Rekor inclusion proof
- `files.bundle_manifest.json` — the bundle's own manifest hash
- `manifest` — top-level integrity envelope

## Run metadata

| | |
|---|---|
| Run ID | `{exp['run_id']}` |
| Predictions lock | `{exp['predictions_lock_tag']}` |
| `policy_snapshot_id` (all bundles) | `{exp['policy_snapshot_id']}` |
| `policy_snapshot_digest` (all bundles) | `{exp['policy_snapshot_digest']}` |
| `signature_kid` (all bundles) | `{exp['signing_kid']}` |
| Agent | {exp['agent']} |

## How to verify

### Option A — verify.meshqu.com (in-browser, recommended for spot checks)

1. Open <https://verify.meshqu.com>
2. Drop any `bundles/<decision_id>.bundle.json` into the verifier
3. Expected: **"Bundle Verified with Caveats — Schema v2"** with all cryptographic checks (integrity / signature / transparency / canonicalization) passing

### Option B — @meshqu/verifier CLI (for bulk verification)

```bash
for f in bundles/*.bundle.json; do
  meshqu-verifier verify "$f" || echo "FAILED: $f"
done
```

### Option C — Independent Rekor lookup (for transparency anchor verification)

Every receipt carries a `transparency_anchor.rekor_public_url` pointing at a sigstore.dev entry. The receipt's integrity hash is bound to that entry's DSSE envelope. Independent verification path that doesn't trust the MeshQu API at all.

## Provenance

This corpus is the empirical artefact of the {exp['directory']} experiment, retrieved from the canonical exported form via the public bundle endpoint. Authoritative sources in the parent repository:

- Pre-registered predictions: `{exp['directory']}/planning/predictions.md` (tag `{exp['predictions_lock_tag']}`)
- Decision log: `{exp['directory']}/planning/decision_log.md`
- Writeup: `{exp['directory']}/writeup/writeup.md`
- Phase-2 run dir (pre-export source): `{exp['run_dir']}`
"""


def build_corpus_tar(exp: dict, bundles: dict[str, bytes], out_path: Path) -> None:
    """Write deterministic-ish tar matching E1's layout (README + bundles/)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    readme = build_readme(exp, len(bundles))
    readme_bytes = readme.encode("utf-8")

    with tarfile.open(out_path, "w", format=tarfile.USTAR_FORMAT) as tar:
        # README at root
        readme_info = tarfile.TarInfo("README.md")
        readme_info.size = len(readme_bytes)
        readme_info.mode = 0o644
        readme_info.mtime = 0
        tar.addfile(readme_info, io.BytesIO(readme_bytes))

        # Bundles in sorted order for determinism
        for decision_id in sorted(bundles):
            content = bundles[decision_id]
            info = tarfile.TarInfo(f"bundles/{decision_id}.bundle.json")
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(content))


def probe(decision_id: str) -> int:
    """Fetch one bundle and report its structure. Used before a full run."""
    print(f"Probe: {decision_id}")
    print(f"  URL: {API_BASE}/v1/receipts/{decision_id}/bundle")
    try:
        bundle_bytes = fetch_bundle(decision_id)
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {e}", file=sys.stderr)
        return 1
    print(f"  HTTP 200, {len(bundle_bytes):,} bytes")

    bundle = json.loads(bundle_bytes)
    print(f"  Top-level keys: {sorted(bundle.keys())}")

    files = bundle.get("files", {})
    print(f"  Embedded files: {sorted(files.keys())}")

    has_transparency = "transparency_proof.json" in files
    print(f"  transparency_proof.json present: {has_transparency}")

    if has_transparency:
        proof_str = files["transparency_proof.json"]
        proof = json.loads(proof_str) if isinstance(proof_str, str) else proof_str
        # Show a tiny excerpt — uuid, logIndex if present
        print(f"  transparency_proof keys: {sorted(proof.keys())[:8]}")
        for k in ("entry_uuid", "log_index", "rekor_public_url", "integrated_time"):
            if k in proof:
                v = proof[k]
                if isinstance(v, str) and len(v) > 80:
                    v = v[:77] + "..."
                print(f"    {k}: {v}")

    # Print manifest decision_id for sanity
    manifest = bundle.get("manifest", {})
    print(f"  manifest.decision_id: {manifest.get('decision_id')}")
    print(f"  manifest.canonicalization_profile: {manifest.get('canonicalization_profile')}")
    print(f"  manifest.exported_at: {manifest.get('exported_at')}")

    if not has_transparency:
        print(
            "  WARNING: transparency_proof.json missing — was the DSSE envelope stored?",
            file=sys.stderr,
        )
        return 1
    return 0


def build_full_corpus(exp_key: str, repo_root: Path, limit: int | None = None) -> int:
    exp = EXPERIMENTS[exp_key]
    run_dir = repo_root / exp["run_dir"]
    out_path = repo_root / exp["out_path"]

    if not run_dir.exists():
        print(f"FAIL: run dir not found: {run_dir}", file=sys.stderr)
        return 1

    decision_ids = enumerate_decision_ids(run_dir)
    print(f"{exp_key.upper()} ({exp['id']}): {len(decision_ids):,} unique decision_ids found")

    if limit:
        decision_ids = decision_ids[:limit]
        print(f"  Limiting to first {len(decision_ids)} for this run")

    bundles: dict[str, bytes] = {}
    failures: list[tuple[str, str]] = []
    started = time.time()

    for i, decision_id in enumerate(decision_ids, 1):
        if i % 50 == 0 or i == 1:
            elapsed = time.time() - started
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(decision_ids) - i) / rate if rate > 0 else 0
            print(
                f"  [{i:,}/{len(decision_ids):,}] {decision_id} "
                f"({rate:.1f}/s, ETA {eta/60:.1f}min)"
            )
        try:
            bundles[decision_id] = fetch_bundle(decision_id)
        except Exception as e:  # noqa: BLE001
            failures.append((decision_id, str(e)))
            print(f"  FAIL {decision_id}: {e}", file=sys.stderr)
        time.sleep(SLEEP_BETWEEN_CALLS_SECONDS)

    print()
    print(f"=== Fetch summary ===")
    print(f"  Successes: {len(bundles):,}")
    print(f"  Failures:  {len(failures):,}")
    if failures:
        print("  First 5 failure reasons:")
        for did, reason in failures[:5]:
            print(f"    {did}: {reason}")
        return 1

    # Validate one random bundle has transparency_proof.json populated
    sample_decision_id, sample_bytes = next(iter(bundles.items()))
    sample = json.loads(sample_bytes)
    if "transparency_proof.json" not in sample.get("files", {}):
        print(
            f"FAIL: sample bundle {sample_decision_id} has no transparency_proof.json",
            file=sys.stderr,
        )
        return 1
    print(f"  Sample bundle ({sample_decision_id}): transparency_proof.json present — OK")

    print(f"\nBuilding {out_path}...")
    build_corpus_tar(exp, bundles, out_path)
    print(f"  {out_path.stat().st_size:,} bytes")
    print(f"  {len(bundles):,} bundles + README")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--experiment",
        choices=["e2", "e3"],
        help="Build corpus.tar for this experiment",
    )
    parser.add_argument(
        "--probe",
        metavar="DECISION_ID",
        help="Probe one decision_id and report bundle structure; do not build corpus",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of bundles fetched (for testing)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT_DEFAULT),
        help=f"Path to meshqu-research repo (default: {REPO_ROOT_DEFAULT})",
    )
    args = parser.parse_args()

    if args.probe:
        return probe(args.probe)

    if not args.experiment:
        parser.error("--experiment is required when not using --probe")

    repo_root = Path(args.repo_root)
    return build_full_corpus(args.experiment, repo_root, limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())
