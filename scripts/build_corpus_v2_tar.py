#!/usr/bin/env python3
"""
build_corpus_v2_tar.py — assemble the repaired corpus-v2.tar for an experiment

Companion to build_corpus_tar.py. Where that script builds the original
corpus.tar from the pre-export run-dir bundles, this one rebuilds a second
archive, corpus-v2.tar, alongside each original: the same decision IDs,
re-exported after the bundle exporter was fixed (TradeQu/tradequ#1156) to
include policy_approval_receipts.json, the signed approval record for the
policy version every receipt evaluated against.

Decision IDs are read from the PUBLISHED corpus.tar (not the run dir), via
Python's tarfile module. macOS bsdtar hides AppleDouble ._ sidecar members
from listings; Python's tarfile does not, so this script explicitly skips any
member whose basename starts with "._" (see data/build_export.py, which
applies the same skip when reading these tars downstream).

Each bundle is re-fetched from the same public endpoint, header and pacing
convention as build_corpus_tar.py:

    GET https://meshqu-api-staging.up.railway.app/v1/receipts/<decision_id>/bundle
    Accept: application/x.meshqu.bundle+json

receipt.json, policy_snapshot.json, transparency_proof.json and
trusted_keys.json inside each v2 bundle are expected to be byte-identical to
the v1 bundle for the same decision_id — the exporter fix only added the one
new file and updated exported_at / manifest_digest in bundle_manifest.json.
This script does not itself assert that (data/build_export.py does, for the
files it reads); it only fetches and packs.

Usage:
    # Fetch from the live endpoint (subject to the same rate limit as
    # build_corpus_tar.py).
    python build_corpus_v2_tar.py --experiment e1
    python build_corpus_v2_tar.py --experiment e2 --limit 5

    # Build from bundles already fetched and saved as
    # <from-dir>/<decision_id>.bundle.json (no fetching, no network calls).
    # This is how corpus-v2.tar was actually built for the PR that
    # introduced this script: bundles were fetched once by an orchestrator
    # and verified, then packed from disk.
    python build_corpus_v2_tar.py --experiment e1 --from-dir /path/to/e1/bundles

Output: written to <experiment-root>/results/corpus-v2.tar
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tarfile
import time
from pathlib import Path

# Reuse the fetch machinery and pacing/429 handling from build_corpus_tar.py
# rather than duplicating it. Both scripts live in the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_corpus_tar import (  # noqa: E402
    MAX_RETRIES_PER_BUNDLE,
    RATE_LIMIT_FLOOR_REMAINING,
    SLEEP_BETWEEN_CALLS_SECONDS,
    fetch_bundle,
)

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

APPROVAL_RECEIPT_ID = "4bb13cfb-cefa-43d5-bddc-64c7884a0776"
APPROVAL_RECEIPT_DIGEST = (
    "e7081f5e7aaf54b5202503ce36a8f3bad0b0c5424dbeda02fe9102a490a0e58e"
)
EXPECTED_TENANT_ID = "243f19a5-4d4f-4070-9ec1-8170e8260e26"

EXPERIMENTS = {
    "e1": {
        "id": "MRP-2026-02",
        "title": "procurement-decisions",
        "directory": "procurement-decisions",
        "n_bundles": 283,
        "corpus_v1_path": "procurement-decisions/results/corpus.tar",
        "out_path": "procurement-decisions/results/corpus-v2.tar",
    },
    "e2": {
        "id": "MRP-2026-03",
        "title": "procurement-context-gradient",
        "directory": "procurement-context-gradient",
        "n_bundles": 1429,
        "corpus_v1_path": "procurement-context-gradient/results/corpus.tar",
        "out_path": "procurement-context-gradient/results/corpus-v2.tar",
    },
    "e3": {
        "id": "MRP-2026-04",
        "title": "procurement-context-disambiguation",
        "directory": "procurement-context-disambiguation",
        "n_bundles": 1332,
        "corpus_v1_path": "procurement-context-disambiguation/results/corpus.tar",
        "out_path": "procurement-context-disambiguation/results/corpus-v2.tar",
    },
}


def enumerate_decision_ids_from_tar(tar_path: Path) -> list[str]:
    """Read decision IDs from the published corpus.tar, skipping AppleDouble
    sidecars (see data/build_export.py for the same skip on the read side).
    """
    ids: set[str] = set()
    with tarfile.open(tar_path) as tf:
        for member in tf.getmembers():
            basename = member.name.rsplit("/", 1)[-1]
            if basename.startswith("._"):
                continue
            if not basename.endswith(".bundle.json"):
                continue
            stem = basename.removesuffix(".bundle.json")
            if len(stem) == 36 and stem.count("-") == 4:
                ids.add(stem)
    return sorted(ids)


def extract_run_metadata_table(original_readme_text: str) -> str:
    """Pull the "## Run metadata" table out of the original corpus.tar's
    README.md verbatim, so the v2 README carries it forward exactly rather
    than re-typing it (and risking drift).
    """
    match = re.search(
        r"## Run metadata\n\n(.*?)\n\n##", original_readme_text, re.S
    )
    if not match:
        raise ValueError("Could not find '## Run metadata' table in original README")
    return match.group(1)


def read_original_readme(corpus_v1_path: Path) -> str:
    with tarfile.open(corpus_v1_path) as tf:
        member = tf.extractfile("README.md")
        if member is None:
            raise ValueError(f"No README.md in {corpus_v1_path}")
        return member.read().decode("utf-8")


def build_v2_readme(exp: dict, run_metadata_table: str) -> str:
    n = exp["n_bundles"]
    directory = exp["directory"]
    return f"""# {directory} corpus-v2 — repaired copy of `corpus.tar` ({exp['id']})

> The same {n} cryptographically-verifiable MeshQu receipts as `corpus.tar`,
> re-exported on 2026-09-23 after the bundle-export fix in
> TradeQu/tradequ#1156. Receipts, policy snapshots, transparency proofs and
> trusted keys are byte-identical to the original. The one addition is
> `policy_approval_receipts.json`, the signed approval record for the policy
> version every receipt evaluated against, which the original exporter could
> not include.
>
> See [`data/KNOWN_ISSUES.md`](../../data/KNOWN_ISSUES.md) §11 for the full
> account of what the original archive's `approval_lineage` failure meant and
> what this archive does and does not resolve.

## What this archive is

This is a *repair*, not a replacement. `corpus.tar` in this same directory is
untouched and remains the archive that published results and `DATA_MANIFEST.json`
digests cite. `corpus-v2.tar` carries the identical {n} decisions, the identical
signed receipts, policy snapshots, transparency proofs and trusted keys —
verified byte-for-byte identical to `corpus.tar` — plus the one file the
original exporter could not emit.

## What's in this archive

```
bundles/
├── <decision_id>.bundle.json    × {n}
└── (no other files)
README.md                        ← this file
```

Each `<decision_id>.bundle.json` is a complete v2 receipt bundle (`application/x.meshqu.bundle+json`) carrying:

- `files.receipt.json` — the signed receipt (Ed25519 signature, integrity hash, transparency anchor) — byte-identical to `corpus.tar`
- `files.policy_snapshot.json` — the policy snapshot the receipt evaluated against — byte-identical to `corpus.tar`
- `files.trusted_keys.json` — the public key for the signing kid — byte-identical to `corpus.tar`
- `files.transparency_proof.json` — the Rekor inclusion proof — byte-identical to `corpus.tar`
- `files.policy_approval_receipts.json` — **new**: the signed approval record for the policy version this receipt evaluated against (see below)
- `files.bundle_manifest.json` — the bundle's own manifest hash; differs from `corpus.tar` only in `exported_at`, the new file's entry, and the resulting `manifest_digest`
- `manifest` — top-level integrity envelope

## Run metadata

Carried forward verbatim from `corpus.tar`'s README — nothing about the
underlying run changed:

{run_metadata_table}

## How to verify — only as a reader can actually do it today

On <https://verify.meshqu.com>, a `corpus-v2.tar` bundle headlines
**"Bundle Not Fully Checked"** — no cryptographic check failed. Approval
lineage reads **"Not checked (nothing anchors which tenant these approvals
belong to)"**. That is because a bundle cannot vouch for its own tenant, and
the web verifier has no way to be told one to check against. This is a
different, narrower headline than the original `corpus.tar`, whose bundles
verify with an overall verdict of **"Bundle Failed Verification"** (see
[`data/KNOWN_ISSUES.md`](../../data/KNOWN_ISSUES.md) §11).

To anchor the tenant yourself, the expected tenant for every receipt in this
corpus is:

```
243f19a5-4d4f-4070-9ec1-8170e8260e26
```

A verifier given this expected tenant reports approval lineage **valid** (see
the verdict table in §11 of `KNOWN_ISSUES.md`). **A publicly available
verifier that accepts an expected tenant is not yet available** — do not run
`@meshqu/verifier` or any `meshqu-verify` / `meshqu-verifier` CLI against
these bundles expecting that check: the published `@meshqu/verifier` npm
package is a `0.0.0` placeholder with no binary, and no public CLI can
perform this check today.

### Independent Rekor lookup (for transparency anchor verification — unaffected by any of the above)

Every receipt carries a `transparency_anchor.rekor_public_url` pointing at a
sigstore.dev entry. The receipt's integrity hash is bound to that entry's
DSSE envelope. This path does not depend on MeshQu, on the bundle wrapper, or
on the tenant question above, and works identically for `corpus.tar` and
`corpus-v2.tar`.

## The approval record, stated honestly

`policy_approval_receipts.json` is a signed record, and its contents cannot
be edited — they are exactly what was ratified. Read plainly:

- `ratifier_id` and `ratifier_role` are both `staging-console-experiment-procurement` — a staging console credential, not a named individual.
- `approval_authority` is `unspecified`.
- `workflow_state` is `ratified`.
- The record was ratified on 2026-05-17, **before** this corpus froze on 2026-05-29.
- No individual approver is named anywhere in the record.

This is what the signed approval bytes say. It establishes that the policy
version was ratified, by whom the system was told to trust to ratify it in
this staging environment, and when — no more and no less.

## Provenance

Re-exported by [`scripts/build_corpus_v2_tar.py`](../../scripts/build_corpus_v2_tar.py)
from the public bundle endpoint:

    GET https://meshqu-api-staging.up.railway.app/v1/receipts/<decision_id>/bundle

following the exporter fix in TradeQu/tradequ#1156. Decision IDs were taken
from `corpus.tar` in this same directory, so the set is identical.

- Original archive: `{exp['directory']}/results/corpus.tar`
- Known issue this repairs: [`data/KNOWN_ISSUES.md`](../../data/KNOWN_ISSUES.md) §11
"""


def build_corpus_v2_tar(exp: dict, readme_text: str, bundles: dict[str, bytes], out_path: Path) -> None:
    """Write corpus-v2.tar using the same writer convention as
    build_corpus_tar.build_corpus_tar(): README.md at root first, then
    bundles/<decision_id>.bundle.json in sorted order, USTAR, mode 0644,
    mtime 0. No AppleDouble sidecars.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    readme_bytes = readme_text.encode("utf-8")

    with tarfile.open(out_path, "w", format=tarfile.USTAR_FORMAT) as tar:
        readme_info = tarfile.TarInfo("README.md")
        readme_info.size = len(readme_bytes)
        readme_info.mode = 0o644
        readme_info.mtime = 0
        tar.addfile(readme_info, io.BytesIO(readme_bytes))

        for decision_id in sorted(bundles):
            content = bundles[decision_id]
            info = tarfile.TarInfo(f"bundles/{decision_id}.bundle.json")
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(content))


def load_bundles_from_dir(from_dir: Path, decision_ids: list[str]) -> dict[str, bytes]:
    bundles: dict[str, bytes] = {}
    missing: list[str] = []
    for decision_id in decision_ids:
        path = from_dir / f"{decision_id}.bundle.json"
        if not path.exists():
            missing.append(decision_id)
            continue
        bundles[decision_id] = path.read_bytes()
    if missing:
        print(
            f"FAIL: {len(missing)} decision_ids missing from {from_dir}: "
            f"{missing[:5]}{'...' if len(missing) > 5 else ''}",
            file=sys.stderr,
        )
        sys.exit(1)
    return bundles


def fetch_bundles(decision_ids: list[str]) -> dict[str, bytes]:
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
                f"({rate:.2f}/s, ETA {eta/60:.1f}min)",
                flush=True,
            )
        try:
            body, remaining = fetch_bundle(decision_id)
            bundles[decision_id] = body
            if remaining is not None and remaining <= RATE_LIMIT_FLOOR_REMAINING:
                print(f"    rate-limit-remaining={remaining}; sleeping 60s", flush=True)
                time.sleep(60)
        except Exception as e:  # noqa: BLE001
            failures.append((decision_id, str(e)))
            print(f"  FAIL {decision_id}: {e}", file=sys.stderr, flush=True)
        time.sleep(SLEEP_BETWEEN_CALLS_SECONDS)

    if failures:
        print(f"\n{len(failures)} failures:")
        for did, reason in failures[:5]:
            print(f"    {did}: {reason}")
        sys.exit(1)
    return bundles


def run(exp_key: str, repo_root: Path, limit: int | None, from_dir: Path | None) -> int:
    exp = EXPERIMENTS[exp_key]
    corpus_v1_path = repo_root / exp["corpus_v1_path"]
    out_path = repo_root / exp["out_path"]

    if not corpus_v1_path.exists():
        print(f"FAIL: original corpus.tar not found: {corpus_v1_path}", file=sys.stderr)
        return 1

    decision_ids = enumerate_decision_ids_from_tar(corpus_v1_path)
    print(f"{exp_key.upper()} ({exp['id']}): {len(decision_ids):,} decision_ids read from {corpus_v1_path}")
    if len(decision_ids) != exp["n_bundles"]:
        print(
            f"FAIL: expected {exp['n_bundles']} decision_ids, found {len(decision_ids)}",
            file=sys.stderr,
        )
        return 1

    if limit:
        decision_ids = decision_ids[:limit]
        print(f"  Limiting to first {len(decision_ids)} for this run")

    if from_dir:
        print(f"  Loading bundles from {from_dir} (no network calls)")
        bundles = load_bundles_from_dir(from_dir, decision_ids)
    else:
        print(f"  Fetching {len(decision_ids)} bundles from the live endpoint")
        bundles = fetch_bundles(decision_ids)

    original_readme = read_original_readme(corpus_v1_path)
    run_metadata_table = extract_run_metadata_table(original_readme)
    v2_readme = build_v2_readme(exp, run_metadata_table)

    print(f"Building {out_path}...")
    build_corpus_v2_tar(exp, v2_readme, bundles, out_path)
    print(f"  {out_path.stat().st_size:,} bytes")
    print(f"  {len(bundles):,} bundles + README")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--experiment", choices=["e1", "e2", "e3"], required=True)
    parser.add_argument("--limit", type=int, help="Limit number of bundles (for testing)")
    parser.add_argument(
        "--from-dir",
        type=Path,
        help="Build from already-fetched bundles at <from-dir>/<decision_id>.bundle.json "
        "instead of hitting the live endpoint",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT_DEFAULT),
        help=f"Path to meshqu-research repo (default: {REPO_ROOT_DEFAULT})",
    )
    args = parser.parse_args()

    return run(args.experiment, Path(args.repo_root), args.limit, args.from_dir)


if __name__ == "__main__":
    sys.exit(main())
