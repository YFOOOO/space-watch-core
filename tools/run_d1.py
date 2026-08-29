#!/usr/bin/env python3
"""Run the exact-source D1 path; repository text alone does not authorize this effect."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.d1 import run_d1  # noqa: E402
from space_watch_cloud.http_adapter import ExactHttpAdapter  # noqa: E402


def git_basis() -> tuple[str, str]:
    commit = subprocess.run(["git", "rev-parse", "HEAD^{commit}"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return commit, tree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--executed-at", required=True)
    args = parser.parse_args()
    run_d1(root=ROOT, packet_path=args.packet, profile_path=ROOT / "config/d1-flight14-mission-profile.json", policy_path=ROOT / "config/d1-flight14-source-policy.json", baseline_path=ROOT / "fixtures/d1-flight14-baseline.json", designation_path=ROOT / "fixtures/d1-flight14-baseline-designation.json", acquirer=ExactHttpAdapter(), basis_reader=git_basis, executed_at=args.executed_at)


if __name__ == "__main__":
    main()
