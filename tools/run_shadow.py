#!/usr/bin/env python3
"""Run the generic, offline, synthetic-only comparison transform."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.runner import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--baseline-designation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--executed-at", required=True)
    args = parser.parse_args()
    command = "python3 tools/run_shadow.py " + " ".join(sys.argv[1:])
    run(input_path=args.input, baseline_path=args.baseline, baseline_designation_path=args.baseline_designation, standalone_root=ROOT, output_dir=args.output_dir, attempt_id=args.attempt_id, executed_at=args.executed_at, actual_command=command, working_directory=str(Path.cwd()))


if __name__ == "__main__":
    main()
