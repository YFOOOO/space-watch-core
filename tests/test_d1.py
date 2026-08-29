from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.canonical import file_digest  # noqa: E402
from space_watch_cloud.d1 import run_d1  # noqa: E402
from space_watch_cloud.model import ContractError  # noqa: E402

COMMIT = "1" * 40
TREE = "2" * 40
ARTIFACTS = ["basis-preflight-receipt.json", "source-attempt-ledger.json", "source-attempt-input.json", "comparison-baseline.json", "comparison-baseline-designation.json", "observation-candidates.json", "execution-receipt.json", "external-interaction-receipt.json", "artifact-manifest.json"]


class D1Tests(unittest.TestCase):
    def make_packet(self, temp: Path) -> Path:
        packet = {
            "schema_version": "space-watch-d1-effect-packet-v0.1", "packet_id": "d1-local-test-01",
            "repository_basis": {"repository": "https://github.com/YFOOOO/space-watch-core", "commit": COMMIT, "tree": TREE},
            "mission_id": "starship-ift14", "profile_file": "config/d1-flight14-mission-profile.json",
            "profile_sha256": file_digest(ROOT / "config/d1-flight14-mission-profile.json"),
            "source_policy_file": "config/d1-flight14-source-policy.json", "source_policy_sha256": file_digest(ROOT / "config/d1-flight14-source-policy.json"),
            "baseline_file": "fixtures/d1-flight14-baseline.json", "baseline_sha256": file_digest(ROOT / "fixtures/d1-flight14-baseline.json"),
            "baseline_designation_file": "fixtures/d1-flight14-baseline-designation.json", "baseline_designation_sha256": file_digest(ROOT / "fixtures/d1-flight14-baseline-designation.json"),
            "disposable_root": str(temp), "output_directory": str(temp / "output"), "total_attempt_budget": 3,
            "per_source_timeout_seconds": 5, "runtime_budget_seconds": 30, "requested_artifacts": ARTIFACTS,
            "accepted": False, "project_truth": False, "project_effect": "none", "stop_reason": "d1_human_observation_review", "next_authority": "Human Observation Review"
        }
        path = temp / "packet.json"; path.write_text(json.dumps(packet), encoding="utf-8"); return path

    def execute_d1(self, temp: Path, acquirer, basis=(COMMIT, TREE)):
        return run_d1(root=ROOT, packet_path=self.make_packet(temp), profile_path=ROOT / "config/d1-flight14-mission-profile.json", policy_path=ROOT / "config/d1-flight14-source-policy.json", baseline_path=ROOT / "fixtures/d1-flight14-baseline.json", designation_path=ROOT / "fixtures/d1-flight14-baseline-designation.json", acquirer=acquirer, basis_reader=lambda: basis, executed_at="2026-08-29T01:00:00Z")

    def test_exact_three_source_one_shot_produces_review_only_artifacts(self) -> None:
        calls = []
        def acquire(source_id, uri, timeout):
            calls.append((source_id, uri, timeout))
            return {"status": "unavailable", "attempted_at": "2026-08-29T01:00:00Z", "final_uri": uri, "redirect_count": 0, "login_used": False, "search_used": False, "alternate_carrier_used": False, "retry_used": False, "typed_content": None, "limitations": ["synthetic adapter did not access network"]}
        with tempfile.TemporaryDirectory() as name:
            paths = self.execute_d1(Path(name), acquire)
            self.assertEqual(len(calls), 3)
            self.assertEqual(set(path.name for path in paths["output"].iterdir()), set(ARTIFACTS))
            ledger = json.loads(paths["source_attempt_ledger"].read_text())
            self.assertEqual(ledger["attempts_consumed"], 3); self.assertEqual(ledger["retry_count"], 0)
            external = json.loads(paths["external_interaction_receipt"].read_text())
            self.assertFalse(external["repository_write"]); self.assertFalse(external["notification_sent"])

    def test_basis_mismatch_fails_before_acquisition_or_output(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            with self.assertRaisesRegex(ContractError, "exact repository basis mismatch"):
                self.execute_d1(temp, lambda *args: calls.append(args), basis=("3" * 40, TREE))
            self.assertEqual(calls, []); self.assertFalse((temp / "output").exists())

    def test_redirect_retry_search_login_and_alternate_fail_closed(self) -> None:
        forbidden = [
            ("redirect_count", 1, "redirect"), ("retry_used", True, "retry_used"),
            ("search_used", True, "search_used"), ("login_used", True, "login_used"),
            ("alternate_carrier_used", True, "alternate_carrier_used")]
        for field, value, message in forbidden:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as name:
                temp = Path(name)
                def acquire(source_id, uri, timeout):
                    result = {"status": "unavailable", "attempted_at": "2026-08-29T01:00:00Z", "final_uri": uri, "redirect_count": 0, "login_used": False, "search_used": False, "alternate_carrier_used": False, "retry_used": False, "typed_content": None, "limitations": []}
                    result[field] = value; return result
                with self.assertRaisesRegex(ContractError, message): self.execute_d1(temp, acquire)
                self.assertFalse((temp / "output").exists())

    def test_unbound_or_wrong_budgets_fail_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name); packet_path = self.make_packet(temp); packet = json.loads(packet_path.read_text())
            packet["runtime_budget_seconds"] = 14; packet_path.write_text(json.dumps(packet))
            calls = []
            with self.assertRaisesRegex(ContractError, "runtime budget is insufficient"):
                run_d1(root=ROOT, packet_path=packet_path, profile_path=ROOT / "config/d1-flight14-mission-profile.json", policy_path=ROOT / "config/d1-flight14-source-policy.json", baseline_path=ROOT / "fixtures/d1-flight14-baseline.json", designation_path=ROOT / "fixtures/d1-flight14-baseline-designation.json", acquirer=lambda *args: calls.append(args), basis_reader=lambda: (COMMIT, TREE), executed_at="2026-08-29T01:00:00Z")
            self.assertEqual(calls, [])


if __name__ == "__main__": unittest.main()
