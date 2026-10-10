#!/usr/bin/env python3
"""Adapt a supplied snapshot or replay offline continuity with synthetic transport."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from space_watch_cloud.continuity import (ack_delivery, apply_observation, initial_state,
                                         prepare_delivery, reconcile_delivery, validate_state)
from space_watch_cloud.research_adapter import adapt_research_readout, research_observation


def replay(snapshot: dict) -> dict:
    task = adapt_research_readout(snapshot, mission_id=snapshot["mission"]["id"])
    observation = research_observation(task)
    state = initial_state(task["mission"]["id"], ["research-snapshot"])
    state, candidate = apply_observation(state, observation, expected_version=state["version"])
    if candidate is None:
        raise ValueError("demo requires a synthetic snapshot with facts")
    state, key, first = prepare_delivery(state, candidate, "synthetic-room", expected_version=state["version"])
    state, unknown = reconcile_delivery(state, key, "unknown", expected_version=state["version"],
                                       attempt_id=state["deliveries"][key]["attempt_id"])
    # JSON round-trip represents persistence/reload, not a cross-day scheduler test.
    state = json.loads(json.dumps(state))
    validate_state(state)
    state, _, pending = prepare_delivery(state, candidate, "synthetic-room", expected_version=state["version"])
    state = ack_delivery(state, key, "synthetic-receipt", expected_version=state["version"],
                         attempt_id=state["deliveries"][key]["attempt_id"])
    state, _, duplicate = prepare_delivery(state, candidate, "synthetic-room", expected_version=state["version"])
    failed = deepcopy(observation)
    failed.update(status="unavailable", facts=None, raw_sha256=None, limitations=["synthetic read failure"])
    previous = deepcopy(state["sources"]["research-snapshot"]["last_valid"])
    state, failure_candidate = apply_observation(state, failed, expected_version=state["version"])
    retained = state["sources"]["research-snapshot"]["last_valid"] == previous
    state, restored = apply_observation(state, observation, expected_version=state["version"])
    state, _, recovery = prepare_delivery(state, restored, "synthetic-room", expected_version=state["version"])
    state, _, other_room = prepare_delivery(state, restored, "synthetic-other-room", expected_version=state["version"])
    expected = ("send", "reconcile", "reconcile", "skip", "skip", "send")
    actual = (first, unknown, pending, duplicate, recovery, other_room)
    if actual != expected or not retained or failure_candidate is not None:
        raise ValueError("continuity replay violated expected transitions")
    return {"mission_id": task["mission"]["id"], "actions": list(actual),
            "last_valid_retained": retained, "task": task, "state": state,
            "transport": "synthetic_only", "notification_sent": False,
            "external_verification": False, "accepted": False, "project_truth": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    adapt = commands.add_parser("adapt", help="read one caller-supplied JSON snapshot from stdin")
    adapt.add_argument("--mission", required=True)
    demo = commands.add_parser("demo", help="offline synthetic replay, no files or real sends")
    demo.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "adapt":
            result = adapt_research_readout(json.load(sys.stdin), mission_id=args.mission)
        else:
            result = replay(json.loads(args.fixture.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"research continuity failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
