#!/usr/bin/env python3
"""Build a deterministic, allowlist-only release ZIP and manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit("output directory must not already exist")
    inventory = json.loads((ROOT / "release-files.json").read_text(encoding="utf-8"))
    files = inventory["files"]
    if files != sorted(set(files)):
        raise SystemExit("release file list must be sorted and unique")
    entries = []
    payloads: dict[str, bytes] = {}
    for relative in files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe release path: {relative}")
        data = (ROOT / path).read_bytes()
        payloads[relative] = data
        entries.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    file_set_bytes = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest = {
        "schema_version": "space-watch-release-manifest-v0.2",
        "package_id": "space-watch-core-v0.2.0",
        "source_basis": {
            "type": "release_file_set_sha256",
            "sha256": digest(file_set_bytes),
            "file_count": len(entries),
        },
        "build_binding": {
            "builder": "tools/build_release.py",
            "builder_sha256": next(item["sha256"] for item in entries if item["path"] == "tools/build_release.py"),
            "python_requirement": ">=3.11",
            "observed_python": ".".join(str(part) for part in sys.version_info[:3]),
            "network_required": False,
        },
        "files": entries,
        "license": {
            "spdx": "MIT",
            "file": "LICENSE",
            "copyright": "Copyright (c) 2026 YF0000",
        },
        "network_required": False,
        "source_acquisition_effect": False,
        "project_effect": "none",
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_dir.mkdir(parents=True)
    manifest_path = args.output_dir / "release-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    zip_path = args.output_dir / "space-watch-core-v0.2.0.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payloads[relative])
        info = zipfile.ZipInfo("release-manifest.json", FIXED_ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, manifest_bytes)
    result = {
        "manifest_sha256": digest(manifest_bytes),
        "package_sha256": digest(zip_path.read_bytes()),
        "file_count": len(files),
    }
    (args.output_dir / "build-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
