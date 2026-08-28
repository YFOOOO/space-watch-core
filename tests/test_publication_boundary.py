from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import zipfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicationBoundaryTests(unittest.TestCase):
    def test_release_inventory_is_self_contained(self) -> None:
        inventory = json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))
        files = inventory["files"]
        self.assertEqual(files, sorted(files))
        self.assertEqual(len(files), len(set(files)))
        for relative in files:
            path = Path(relative)
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertTrue((ROOT / path).is_file(), relative)

    def test_release_has_no_historical_or_private_carriers(self) -> None:
        files = json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))["files"]
        forbidden_parts = {"observations", "receipts", "validation", "dist", "baseline", "architecture", "cloud-state", "local-freeze", "governance", "__pycache__"}
        for relative in files:
            self.assertTrue(forbidden_parts.isdisjoint(Path(relative).parts), relative)
            self.assertFalse(Path(relative).name.startswith(".env"), relative)
            self.assertFalse((ROOT / relative).is_symlink(), relative)

    def test_release_text_has_no_url_or_local_absolute_path(self) -> None:
        files = json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))["files"]
        url = re.compile(r"https?://(?!json-schema\.org/)")
        local = re.compile(r"/(Users|home)/")
        exemptions = {"schemas/source-attempt-input.schema.json", "schemas/comparison-baseline.schema.json", "schemas/observation-candidate-bundle.schema.json", "schemas/execution-receipt.schema.json", "schemas/external-interaction-receipt.schema.json"}
        for relative in files:
            text = (ROOT / relative).read_text(encoding="utf-8")
            if relative not in exemptions:
                self.assertIsNone(url.search(text), relative)
            self.assertIsNone(local.search(text), relative)

    def test_standalone_readme_references_only_present_release_paths(self) -> None:
        files = set(json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))["files"])
        for required in ("README.md", "CONTRACT.md", "DEPENDENCIES.md", "pyproject.toml", "release-files.json", "tools/build_release.py", "tools/run_shadow.py"):
            self.assertIn(required, files)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("WORK_BOUNDARY.json", readme)
        self.assertNotIn("PUBLICATION_CONTRACT.md", readme)

    def test_release_build_is_reproducible_and_manifest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            command = [sys.executable, str(ROOT / "tools" / "build_release.py"), "--output-dir"]
            subprocess.run(command + [str(first)], cwd=ROOT, check=True)
            subprocess.run(command + [str(second)], cwd=ROOT, check=True)
            first_zip = first / "space-watch-core-v0.2.0.zip"
            second_zip = second / "space-watch-core-v0.2.0.zip"
            self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
            manifest = json.loads((first / "release-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_basis"]["type"], "release_file_set_sha256")
            self.assertEqual(manifest["source_basis"]["file_count"], len(json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))["files"]))
            self.assertFalse(manifest["build_binding"]["network_required"])
            with zipfile.ZipFile(first_zip) as archive:
                self.assertEqual(set(archive.namelist()), set(json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))["files"]) | {"release-manifest.json"})


if __name__ == "__main__":
    unittest.main()
