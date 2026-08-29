#!/usr/bin/env python3
"""Run one repository-owned O1 synthetic test or scheduled live invocation."""

from __future__ import annotations

import argparse
import contextlib
import signal
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.d1 import run_d1  # noqa: E402
from space_watch_cloud.http_adapter import ExactHttpAdapter  # noqa: E402
from space_watch_cloud.o1 import run_o1  # noqa: E402


@contextlib.contextmanager
def hard_deadline(seconds: int):
    def timeout_handler(signum, frame):
        raise TimeoutError("O1 total wall-clock runtime budget exhausted")

    previous = signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def git_basis() -> tuple[str, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise RuntimeError("O1 exact repository basis requires a clean working tree")
    commit = subprocess.run(["git", "rev-parse", "HEAD^{commit}"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return commit, tree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("synthetic", "d1"), required=True)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scheduled-occurrence", required=True)
    parser.add_argument("--executed-at", required=True)
    parser.add_argument("--runtime-budget-seconds", required=True, type=int)
    parser.add_argument("--maximum-output-bytes", required=True, type=int)
    parser.add_argument("--d1-packet", type=Path)
    args = parser.parse_args()
    commit, tree = git_basis()

    if args.mode == "synthetic":
        if args.d1_packet is not None:
            parser.error("--d1-packet is forbidden in synthetic mode")

        def producer(output: Path) -> Path:
            target = output / "observation-candidates.json"
            shutil.copyfile(ROOT / "fixtures/o1-synthetic-d1-bundle.json", target)
            return target

        run_kind = "synthetic_test"
    else:
        if args.d1_packet is None:
            parser.error("--d1-packet is required in d1 mode")

        def producer(output: Path) -> Path:
            paths = run_d1(
                root=ROOT,
                packet_path=args.d1_packet,
                profile_path=ROOT / "config/d1-flight14-mission-profile.json",
                policy_path=ROOT / "config/d1-flight14-source-policy.json",
                baseline_path=ROOT / "fixtures/d1-flight14-baseline.json",
                designation_path=ROOT / "fixtures/d1-flight14-baseline-designation.json",
                acquirer=ExactHttpAdapter(),
                basis_reader=git_basis,
                executed_at=args.executed_at,
            )
            source = paths["observation_candidates"]
            target = output / "observation-candidates.json"
            shutil.copyfile(source, target)
            return target

        run_kind = "scheduled_live"

    with hard_deadline(args.runtime_budget_seconds):
        run_o1(
            state_path=args.state_file,
            output_dir=args.output_dir,
            run_id=args.run_id,
            scheduled_occurrence=args.scheduled_occurrence,
            executed_at=args.executed_at,
            repository_commit=commit,
            repository_tree=tree,
            runtime_budget_seconds=args.runtime_budget_seconds,
            maximum_output_bytes=args.maximum_output_bytes,
            run_kind=run_kind,
            producer=producer,
        )


if __name__ == "__main__":
    main()
