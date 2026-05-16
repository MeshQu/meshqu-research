"""Minimal CLI for manual operations and smoke testing.

  python -m meshqu_runner.cli mirror              # OBS-206 standalone
  python -m meshqu_runner.cli capture --phase dry-run --event manual-test
  python -m meshqu_runner.cli smoke               # full lifecycle dry run
"""
from __future__ import annotations

import argparse
import sys

from .config import RunnerConfig
from .dashboard_mirror import MirrorError, mirror_and_verify
from .runner import RunController


def _cmd_mirror(args: argparse.Namespace) -> int:
    config = RunnerConfig.from_env()
    try:
        result = mirror_and_verify(config)
    except MirrorError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: source_of_truth={result.source_of_truth}")
    print(f"    mirror_path={result.mirror_path}")
    print(f"    canonical_sha256={result.canonical_sha256}")
    print(f"    live_grafana_sha256={result.live_grafana_sha256}")
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    config = RunnerConfig.from_env()
    controller = RunController(config=config, run_phase=args.phase, total_records=0)
    # Skip OBS-206 verification on standalone captures — manual captures
    # are explicitly outside the run-start contract.
    controller._capturer.render_height = controller._capturer.render_height or 1200
    result = controller._capturer.capture(
        run_phase=args.phase,
        event=args.event,
    )
    if result.ok:
        print(
            f"OK: wrote {result.bytes_written}B in {result.duration_seconds:.2f}s → "
            f"{result.path}"
        )
        return 0
    print(f"FAIL: {result.error} (status={result.status_code} ct={result.content_type})", file=sys.stderr)
    return 1


def _cmd_smoke(args: argparse.Namespace) -> int:
    """Simulate a tiny dry-run: run-start, 5 records (2 checkpoints), 1 anomaly, run-end."""
    config = RunnerConfig.from_env()
    controller = RunController(
        config=config,
        run_phase="dry-run",
        total_records=5,
    )

    print("==> run_start")
    try:
        mirror_result, capture = controller.run_start()
    except MirrorError as exc:
        print(f"FAIL run_start: {exc}", file=sys.stderr)
        return 1
    print(f"    mirror ok ({mirror_result.source_of_truth}); capture ok={capture.ok}")

    for record_index in range(5):
        print(f"==> after_record({record_index})")
        capture = controller.after_record(record_index)
        if capture is not None:
            print(f"    checkpoint capture ok={capture.ok}")

    print("==> on_anomaly(rekor_anchor_slow, record_index=3)")
    anomaly_id, capture = controller.on_anomaly(
        category="rekor_anchor_slow",
        summary="(smoke) synthetic anomaly to exercise capture path",
        severity="warn",
        record_index=3,
    )
    print(f"    anomaly_id={anomaly_id}; capture ok={(capture and capture.ok)}")

    print("==> run_end")
    capture = controller.run_end()
    print(f"    run-end capture ok={capture.ok}")

    print(f"\nrun_id={controller.run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meshqu_runner.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_mirror = subparsers.add_parser("mirror", help="OBS-206 mirror + verify against live Grafana")
    p_mirror.set_defaults(func=_cmd_mirror)

    p_capture = subparsers.add_parser("capture", help="OBS-205 fire a single capture")
    p_capture.add_argument("--phase", required=True, choices=["dry-run", "full-run", "reproducibility-rerun"])
    p_capture.add_argument("--event", required=True, help="e.g. manual-test, run-start, checkpoint-005")
    p_capture.set_defaults(func=_cmd_capture)

    p_smoke = subparsers.add_parser("smoke", help="Full-lifecycle dry run for local validation")
    p_smoke.set_defaults(func=_cmd_smoke)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
