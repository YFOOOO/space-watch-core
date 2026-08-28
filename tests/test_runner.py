from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.model import ContractError, validate_source_input  # noqa: E402
from space_watch_cloud.runner import run  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RunnerTests(unittest.TestCase):
    def test_synthetic_run_is_self_contained_and_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            paths = run(
                input_path=ROOT / "fixtures" / "synthetic-source-input.json",
                baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
                baseline_designation_path=ROOT / "fixtures" / "synthetic-baseline-designation.json",
                standalone_root=ROOT,
                output_dir=output,
                attempt_id="synthetic-local-freeze-01",
                executed_at="2026-01-01T00:01:00Z",
                actual_command="synthetic test command",
                working_directory="standalone repository root",
            )
            candidates = load(paths["candidates"])
            receipt = load(paths["receipt"])
            self.assertEqual(candidates["allowlist_coverage_verdict"], "partial")
            self.assertEqual([item["comparison"] for item in candidates["candidates"]], ["changed", "unavailable"])
            self.assertFalse(candidates["accepted"])
            self.assertFalse(candidates["project_truth"])
            self.assertFalse(receipt["source_acquisition_effect"])
            self.assertEqual(receipt["project_effect"], "none")
            self.assertEqual(receipt["stop_reason"], "human_review_gate")
            self.assertEqual(receipt["actual_command"], "synthetic test command")
            self.assertEqual(len(receipt["read_paths"]), 3)
            for name in ("attachment", "cloud_root_created", "cloud_command_executed"):
                self.assertEqual(receipt["external_execution_effect"][name], {"status": "unavailable", "reason": "not_observed_by_runner"})

    def test_non_synthetic_mode_fails_closed(self) -> None:
        document = load(ROOT / "fixtures" / "synthetic-source-input.json")
        document["acquisition_mode"] = "live"
        with self.assertRaisesRegex(ContractError, "only synthetic_fixture"):
            validate_source_input(document)

    def test_duplicate_source_identity_fails_closed(self) -> None:
        document = load(ROOT / "fixtures" / "synthetic-source-input.json")
        document["attempts"].append(dict(document["attempts"][0]))
        with self.assertRaisesRegex(ContractError, "duplicate source identity"):
            validate_source_input(document)

    def test_output_directory_must_be_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ContractError, "must not already exist"):
                run(
                    input_path=ROOT / "fixtures" / "synthetic-source-input.json",
                    baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
                    baseline_designation_path=ROOT / "fixtures" / "synthetic-baseline-designation.json",
                    standalone_root=ROOT,
                    output_dir=Path(temp),
                    attempt_id="synthetic-local-freeze-02",
                    executed_at="2026-01-01T00:01:00Z",
                    actual_command="synthetic test command",
                    working_directory="standalone repository root",
                )

    def test_baseline_hash_mismatch_fails_closed(self) -> None:
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        designation["baseline_file_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            designation_path = Path(temp) / "designation.json"
            designation_path.write_text(json.dumps(designation), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "does not match independent designation"):
                run(
                    input_path=ROOT / "fixtures" / "synthetic-source-input.json",
                    baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
                    baseline_designation_path=designation_path,
                    standalone_root=ROOT,
                    output_dir=Path(temp) / "output",
                    attempt_id="synthetic-local-freeze-03",
                    executed_at="2026-01-01T00:01:00Z",
                    actual_command="synthetic test command",
                    working_directory="standalone repository root",
                )

    def assert_rejected_before_output(self, source: dict, baseline: dict, designation: dict, baseline_path: Path | None = None) -> str:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "input.json"
            actual_baseline = baseline_path or (temp_path / "baseline.json")
            designation_path = temp_path / "designation.json"
            input_path.write_text(json.dumps(source), encoding="utf-8")
            if baseline_path is None:
                actual_baseline.write_text(json.dumps(baseline), encoding="utf-8")
            designation_path.write_text(json.dumps(designation), encoding="utf-8")
            output = temp_path / "output"
            with self.assertRaises(ContractError) as caught:
                run(input_path=input_path, baseline_path=actual_baseline, baseline_designation_path=designation_path,
                    standalone_root=ROOT, output_dir=output, attempt_id="adversarial", executed_at="2026-01-01T00:01:00Z",
                    actual_command="test", working_directory="test")
            self.assertFalse(output.exists())
            return str(caught.exception)

    def test_unknown_authority_fields_fail_before_output_creation(self) -> None:
        source = load(ROOT / "fixtures" / "synthetic-source-input.json")
        baseline = load(ROOT / "fixtures" / "synthetic-baseline.json")
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        for target, field in ((source, "accepted"), (baseline, "authority"), (designation, "publication_authority")):
            target[field] = True
            self.assertIn("schema-forbidden fields", self.assert_rejected_before_output(source, baseline, designation))
            del target[field]

    def test_baseline_identity_mismatch_fails_before_output_creation(self) -> None:
        source = load(ROOT / "fixtures" / "synthetic-source-input.json")
        baseline = load(ROOT / "fixtures" / "synthetic-baseline.json")
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        designation["baseline_file"] = "fixtures/other-baseline.json"
        self.assertIn("identity does not match", self.assert_rejected_before_output(source, baseline, designation, ROOT / "fixtures" / "synthetic-baseline.json"))

    def test_nonexistent_baseline_fails_before_output_creation(self) -> None:
        source = load(ROOT / "fixtures" / "synthetic-source-input.json")
        baseline = load(ROOT / "fixtures" / "synthetic-baseline.json")
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        self.assertIn("does not exist", self.assert_rejected_before_output(source, baseline, designation, ROOT / "fixtures" / "missing.json"))

    def test_escaping_baseline_identity_fails_before_output_creation(self) -> None:
        source = load(ROOT / "fixtures" / "synthetic-source-input.json")
        baseline = load(ROOT / "fixtures" / "synthetic-baseline.json")
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        designation["baseline_file"] = "../synthetic-baseline.json"
        self.assertIn("non-escaping", self.assert_rejected_before_output(source, baseline, designation, ROOT / "fixtures" / "synthetic-baseline.json"))

    def test_invalid_rfc3339_source_and_execution_times_fail_before_output(self) -> None:
        invalid = ["2026-01-01Z", "2026-01-01 00:00:00Z", "2026-01-01T00:00Z", "2026-02-30T00:00:00Z", "2026-01-01T00:00:00+24:00"]
        baseline = load(ROOT / "fixtures" / "synthetic-baseline.json")
        designation = load(ROOT / "fixtures" / "synthetic-baseline-designation.json")
        for value in invalid:
            source = load(ROOT / "fixtures" / "synthetic-source-input.json")
            source["attempts"][0]["attempted_at"] = value
            self.assertIn("RFC 3339", self.assert_rejected_before_output(source, baseline, designation, ROOT / "fixtures" / "synthetic-baseline.json"))
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "output"
                with self.assertRaisesRegex(ContractError, "RFC 3339"):
                    run(input_path=ROOT / "fixtures" / "synthetic-source-input.json", baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
                        baseline_designation_path=ROOT / "fixtures" / "synthetic-baseline-designation.json", standalone_root=ROOT,
                        output_dir=output, attempt_id="invalid-time", executed_at=value, actual_command="test", working_directory="test")
                self.assertFalse(output.exists())

    def test_valid_rfc3339_z_and_offset_outputs_validate_against_schemas(self) -> None:
        source_schema = load(ROOT / "schemas" / "source-attempt-input.schema.json")
        receipt_schema = load(ROOT / "schemas" / "execution-receipt.schema.json")
        checker = jsonschema.FormatChecker()
        for value in ["2026-01-01T00:00:00Z", "2026-01-01T08:00:00+08:00"]:
            with tempfile.TemporaryDirectory() as temp:
                temp_path = Path(temp)
                source = load(ROOT / "fixtures" / "synthetic-source-input.json")
                source["attempts"][0]["attempted_at"] = value
                input_path = temp_path / "input.json"
                input_path.write_text(json.dumps(source), encoding="utf-8")
                paths = run(input_path=input_path, baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
                    baseline_designation_path=ROOT / "fixtures" / "synthetic-baseline-designation.json", standalone_root=ROOT,
                    output_dir=temp_path / "output", attempt_id="valid-time", executed_at=value, actual_command="test", working_directory="test")
                jsonschema.Draft202012Validator(source_schema, format_checker=checker).validate(load(paths["input"]))
                jsonschema.Draft202012Validator(receipt_schema, format_checker=checker).validate(load(paths["receipt"]))


if __name__ == "__main__":
    unittest.main()
