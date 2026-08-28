"""Offline transformation from frozen synthetic input to review artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_digest, file_digest
from .model import ContractError, identity, validate_baseline, validate_baseline_designation, validate_rfc3339_datetime, validate_source_input


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"required JSON file does not exist: {path}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path.name}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def content_envelope(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "projection_schema": item["projection_schema"],
        "source_id": item["source_id"],
        "claim_family": item["claim_family"],
        "typed_content": item.get("typed_content"),
    }


def standalone_identity(path: Path, standalone_root: Path) -> str:
    try:
        resolved_root = standalone_root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
        relative = resolved_path.relative_to(resolved_root)
    except FileNotFoundError as exc:
        raise ContractError(f"baseline file does not exist: {path}") from exc
    except ValueError as exc:
        raise ContractError("baseline file escapes standalone repository root") from exc
    require_file = resolved_path.is_file()
    if not require_file:
        raise ContractError(f"baseline file does not exist: {path}")
    return relative.as_posix()


def run(*, input_path: Path, baseline_path: Path, baseline_designation_path: Path, standalone_root: Path, output_dir: Path, attempt_id: str, executed_at: str, actual_command: str, working_directory: str) -> dict[str, Path]:
    if output_dir.exists():
        raise ContractError("output directory must not already exist")
    validate_rfc3339_datetime(executed_at, "executed_at")
    source_input = load_json(input_path)
    baseline = load_json(baseline_path)
    designation = load_json(baseline_designation_path)
    validate_source_input(source_input)
    validate_baseline(baseline, source_input["mission_id"])
    validate_baseline_designation(designation, source_input["mission_id"])
    if designation["baseline_file"] != standalone_identity(baseline_path, standalone_root):
        raise ContractError("baseline file identity does not match independent designation")
    if designation["baseline_file_sha256"] != file_digest(baseline_path):
        raise ContractError("baseline file hash does not match independent designation")
    previous = {identity(item): item for item in baseline["candidates"]}
    output_dir.mkdir(parents=True)
    copied_input = output_dir / "source-attempt-input.json"
    copied_baseline = output_dir / "comparison-baseline.json"
    copied_designation = output_dir / "comparison-baseline-designation.json"
    write_json(copied_input, source_input)
    write_json(copied_baseline, baseline)
    write_json(copied_designation, designation)
    candidates: list[dict[str, Any]] = []
    coverage: list[str] = []
    for attempt in source_input["attempts"]:
        key = identity(attempt)
        coverage.append(attempt["status"])
        old = previous.get(key)
        current_digest = canonical_digest(content_envelope(attempt)) if attempt.get("typed_content") is not None else None
        previous_digest = canonical_digest(content_envelope(old)) if old and old.get("typed_content") is not None else None
        if attempt["status"] == "unavailable" or attempt.get("typed_content") is None:
            comparison = "unavailable"
        elif previous_digest is None:
            comparison = "new"
        elif current_digest == previous_digest:
            comparison = "duplicate"
        else:
            comparison = "changed"
        candidates.append({
            "candidate_id": f'{source_input["mission_id"]}:{key}',
            "source_id": attempt["source_id"],
            "claim_family": attempt["claim_family"],
            "availability": attempt["status"],
            "projection_schema": attempt["projection_schema"],
            "typed_content": attempt.get("typed_content"),
            "canonical_content_sha256": current_digest,
            "previous_canonical_content_sha256": previous_digest,
            "comparison": comparison,
            "limitations": attempt["limitations"],
            "accepted": False,
            "project_truth": False,
            "next_authority": "Human Review",
        })
    coverage_verdict = "complete" if all(item == "available" for item in coverage) else ("partial" if any(item in {"available", "partial"} for item in coverage) else "none")
    bundle = {
        "schema_version": "space-watch-observation-candidate-bundle-v0.2",
        "attempt_id": attempt_id,
        "mission_id": source_input["mission_id"],
        "baseline_file_sha256": file_digest(copied_baseline),
        "baseline_designation_file_sha256": file_digest(copied_designation),
        "acquisition_path_verdict": "PASS_SYNTHETIC_ONLY",
        "allowlist_coverage_verdict": coverage_verdict,
        "candidates": candidates,
        "accepted": False,
        "project_truth": False,
        "project_effect": "none",
        "next_authority": "Human Review",
    }
    candidate_path = output_dir / "observation-candidates.json"
    write_json(candidate_path, bundle)
    unavailable = {"status": "unavailable", "reason": "not_observed_by_runner"}
    receipt = {
        "schema_version": "space-watch-execution-receipt-v0.2",
        "attempt_id": attempt_id,
        "executed_at": executed_at,
        "run_kind": "synthetic_fixture",
        "actual_command": actual_command,
        "working_directory": working_directory,
        "read_paths": [str(input_path), str(baseline_path), str(baseline_designation_path)],
        "write_paths": [str(copied_input), str(copied_baseline), str(copied_designation), str(output_dir / "observation-candidates.json"), str(output_dir / "execution-receipt.json")],
        "input_sha256": file_digest(copied_input),
        "baseline_sha256": file_digest(copied_baseline),
        "candidate_bundle_sha256": file_digest(candidate_path),
        "candidate_count": len(candidates),
        "external_execution_effect": {
            "authority_owner": "executor_or_external_interaction_receipt",
            "runner_observation": "not_observed_by_runner",
            "attachment": dict(unavailable),
            "cloud_root_created": dict(unavailable),
            "cloud_command_executed": dict(unavailable),
        },
        "effect_reconciliation_required": True,
        "effect_reconciliation_owner": "closeout",
        "source_acquisition_effect": False,
        "project_effect": "none",
        "accepted": False,
        "project_truth": False,
        "notification_sent": False,
        "project_written": False,
        "routine_created": False,
        "stop_reason": "human_review_gate",
        "next_authority": "Human Review",
    }
    receipt_path = output_dir / "execution-receipt.json"
    write_json(receipt_path, receipt)
    return {"input": copied_input, "baseline": copied_baseline, "baseline_designation": copied_designation, "candidates": candidate_path, "receipt": receipt_path}
