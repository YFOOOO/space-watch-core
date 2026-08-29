from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.model import ContractError  # noqa: E402
from space_watch_cloud.o1 import evaluate_run, initial_state  # noqa: E402

COMMIT = "a" * 40
TREE = "b" * 40


def bundle(comparisons):
    candidates = []
    for index, comparison in enumerate(comparisons):
        candidates.append({
            "candidate_id": f"candidate-{index}", "source_id": f"source-{index}",
            "claim_family": "mission", "availability": "unavailable" if comparison == "unavailable" else "available",
            "projection_schema": "test-v0.1", "typed_content": None if comparison == "unavailable" else {"value": index},
            "comparison": comparison, "authority_limit": "test", "limitations": [],
            "accepted": False, "project_truth": False, "next_authority": "Human Observation Review",
        })
    return {"schema_version": "space-watch-d1-observation-candidate-bundle-v0.1", "packet_id": "packet", "mission_id": "starship-ift14", "baseline_sha256": "c" * 64, "candidates": candidates, "accepted": False, "project_truth": False, "project_effect": "none", "next_authority": "Human Observation Review"}


class O1Tests(unittest.TestCase):
    def test_duplicate_and_coverage_verdicts(self):
        state = initial_state(COMMIT, TREE)
        verdict, state = evaluate_run(state=state, run_id="run-1", bundle=bundle(["duplicate"] * 3), repository_commit=COMMIT, repository_tree=TREE)
        self.assertEqual(verdict, "NO_MATERIAL_DELTA")
        verdict, state = evaluate_run(state=state, run_id="run-2", bundle=bundle(["duplicate", "unavailable", "duplicate"]), repository_commit=COMMIT, repository_tree=TREE)
        self.assertEqual(verdict, "COVERAGE_LIMITATION")
        self.assertEqual(state["invocation_count"], 2)
        self.assertEqual(state["consecutive_capability_failure_count"], 1)

    def test_changed_candidate_reports_once_then_suppresses(self):
        state = initial_state(COMMIT, TREE)
        changed = bundle(["changed", "duplicate", "duplicate"])
        verdict, state = evaluate_run(state=state, run_id="run-1", bundle=changed, repository_commit=COMMIT, repository_tree=TREE)
        self.assertEqual(verdict, "HUMAN_REVIEW_CANDIDATE")
        verdict, state = evaluate_run(state=state, run_id="run-2", bundle=copy.deepcopy(changed), repository_commit=COMMIT, repository_tree=TREE)
        self.assertEqual(verdict, "REPEAT_SUPPRESSED")

    def test_fail_closed_on_basis_authority_duplicate_run_and_budget(self):
        state = initial_state(COMMIT, TREE)
        with self.assertRaisesRegex(ContractError, "basis mismatch"):
            evaluate_run(state=state, run_id="run-1", bundle=bundle(["duplicate"] * 3), repository_commit="d" * 40, repository_tree=TREE)
        bad = bundle(["duplicate"] * 3); bad["accepted"] = True
        with self.assertRaisesRegex(ContractError, "authority boundary"):
            evaluate_run(state=state, run_id="run-1", bundle=bad, repository_commit=COMMIT, repository_tree=TREE)
        _, state = evaluate_run(state=state, run_id="run-1", bundle=bundle(["duplicate"] * 3), repository_commit=COMMIT, repository_tree=TREE)
        with self.assertRaisesRegex(ContractError, "already completed"):
            evaluate_run(state=state, run_id="run-1", bundle=bundle(["duplicate"] * 3), repository_commit=COMMIT, repository_tree=TREE)
        for run_id in ("run-2", "run-3"):
            _, state = evaluate_run(state=state, run_id=run_id, bundle=bundle(["duplicate"] * 3), repository_commit=COMMIT, repository_tree=TREE)
        with self.assertRaisesRegex(ContractError, "budget exhausted"):
            evaluate_run(state=state, run_id="run-4", bundle=bundle(["duplicate"] * 3), repository_commit=COMMIT, repository_tree=TREE)


if __name__ == "__main__":
    unittest.main()
