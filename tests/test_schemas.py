from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.runner import run  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def synthetic_run(temp: str, attempt_id: str) -> dict[str, Path]:
    return run(
        input_path=ROOT / "fixtures" / "synthetic-source-input.json",
        baseline_path=ROOT / "fixtures" / "synthetic-baseline.json",
        baseline_designation_path=ROOT / "fixtures" / "synthetic-baseline-designation.json",
        standalone_root=ROOT,
        output_dir=Path(temp) / "output",
        attempt_id=attempt_id,
        executed_at="2026-01-01T00:01:00Z",
        actual_command="synthetic schema test command",
        working_directory="standalone repository root",
    )


class SchemaTests(unittest.TestCase):
    def test_schema_ids_are_unique_and_roots_fail_closed(self) -> None:
        ids = []
        for path in sorted((ROOT / "schemas").glob("*.schema.json")):
            document = load(path)
            self.assertEqual(document["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(document["type"], "object")
            self.assertFalse(document["additionalProperties"], path.name)
            ids.append(document["$id"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 9)

    def test_synthetic_fixtures_validate(self) -> None:
        pairs = [
            ("source-attempt-input.schema.json", "synthetic-source-input.json"),
            ("comparison-baseline.schema.json", "synthetic-baseline.json"),
            ("comparison-baseline-designation.schema.json", "synthetic-baseline-designation.json"),
            ("d1-mission-profile.schema.json", "../config/d1-flight14-mission-profile.json"),
            ("d1-source-policy.schema.json", "../config/d1-flight14-source-policy.json"),
        ]
        for schema_name, fixture_name in pairs:
            fixture_path = ROOT / "fixtures" / fixture_name
            jsonschema.Draft202012Validator(load(ROOT / "schemas" / schema_name), format_checker=jsonschema.FormatChecker()).validate(load(fixture_path.resolve()))

    def test_generated_artifacts_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = synthetic_run(temp, "schema-validation")
            jsonschema.Draft202012Validator(load(ROOT / "schemas" / "observation-candidate-bundle.schema.json")).validate(load(paths["candidates"]))
            jsonschema.Draft202012Validator(load(ROOT / "schemas" / "execution-receipt.schema.json"), format_checker=jsonschema.FormatChecker()).validate(load(paths["receipt"]))

    def test_available_source_requires_typed_content(self) -> None:
        schema = load(ROOT / "schemas" / "source-attempt-input.schema.json")
        instance = load(ROOT / "fixtures" / "synthetic-source-input.json")
        instance["attempts"][0]["typed_content"] = None
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(instance)

    def test_receipt_schema_rejects_extra_authority_fields(self) -> None:
        schema = load(ROOT / "schemas" / "execution-receipt.schema.json")
        with tempfile.TemporaryDirectory() as temp:
            paths = synthetic_run(temp, "closed-schema-validation")
            instance = load(paths["receipt"])
            instance["accepted_by_runner"] = True
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(schema).validate(instance)
            instance = load(paths["receipt"])
            instance["external_execution_effect"]["attachment"]["actual"] = True
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(schema).validate(instance)


if __name__ == "__main__":
    unittest.main()
