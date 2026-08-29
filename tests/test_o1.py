from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.model import ContractError  # noqa: E402
from space_watch_cloud.o1 import evaluate_run, initial_state, run_o1  # noqa: E402

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

    def test_full_synthetic_orchestration_writes_receipt_and_advances_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            state_path = root / "state.json"
            state_path.write_text(json.dumps(initial_state(COMMIT, TREE), sort_keys=True, indent=2) + "\n")

            def producer(output):
                target = output / "observation-candidates.json"
                target.write_text(json.dumps(bundle(["duplicate", "unavailable", "duplicate"])))
                return target

            ticks = iter((0.0, 0.5, 0.75))
            paths = run_o1(
                state_path=state_path, output_dir=root / "run", run_id="scheduled-1",
                scheduled_occurrence="2026-08-29T19:00:00+08:00", executed_at="2026-08-29T19:01:00+08:00",
                repository_commit=COMMIT, repository_tree=TREE, runtime_budget_seconds=60,
                maximum_output_bytes=100000, run_kind="synthetic_test", producer=producer,
                clock=lambda: next(ticks),
            )
            receipt = json.loads(paths["receipt"].read_text())
            state = json.loads(state_path.read_text())
            self.assertEqual(receipt["verdict"], "COVERAGE_LIMITATION")
            self.assertFalse(receipt["source_acquisition"])
            self.assertFalse(receipt["network_access"])
            self.assertEqual(state["invocation_count"], 1)
            self.assertEqual(state["last_run_id"], "scheduled-1")

    def test_runtime_or_output_budget_failure_does_not_advance_state(self):
        import tempfile
        for failure in ("runtime", "output"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as name:
                root = Path(name); state_path = root / "state.json"
                original = initial_state(COMMIT, TREE)
                state_path.write_text(json.dumps(original) + "\n")
                def producer(output):
                    target = output / "observation-candidates.json"
                    target.write_text(json.dumps(bundle(["duplicate"] * 3)))
                    return target
                ticks = iter((0.0, 2.0)) if failure == "runtime" else iter((0.0, 0.1, 0.2))
                with self.assertRaisesRegex(ContractError, "runtime budget|output budget"):
                    run_o1(
                        state_path=state_path, output_dir=root / "run", run_id="scheduled-1",
                        scheduled_occurrence="2026-08-29T19:00:00+08:00", executed_at="2026-08-29T19:01:00+08:00",
                        repository_commit=COMMIT, repository_tree=TREE, runtime_budget_seconds=1,
                        maximum_output_bytes=1 if failure == "output" else 100000,
                        run_kind="synthetic_test", producer=producer, clock=lambda: next(ticks),
                    )
                self.assertEqual(json.loads(state_path.read_text()), original)

    def test_d1_output_must_be_contained_by_o1_output(self):
        import tempfile
        spec = importlib.util.spec_from_file_location("run_o1_tool", ROOT / "tools/run_o1.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            producer = root / "o1" / "producer"
            producer.mkdir(parents=True)
            packet_path = root / "packet.json"
            packet_path.write_text(json.dumps({
                "disposable_root": str(producer / "d1"),
                "output_directory": str(producer / "d1" / "output"),
            }))
            self.assertEqual(module.prepare_d1_root(packet_path, producer), producer / "d1")
            outside = root / "outside"
            packet_path.write_text(json.dumps({
                "disposable_root": str(outside),
                "output_directory": str(outside / "output"),
            }))
            with self.assertRaisesRegex(ContractError, "inside the O1 output tree"):
                module.prepare_d1_root(packet_path, producer)


if __name__ == "__main__":
    unittest.main()
