"""Fail-closed D1 acquisition orchestration with an injected one-shot adapter."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from .canonical import canonical_digest, file_digest
from .model import ContractError, require, require_exact_keys, require_nonempty_string, validate_rfc3339_datetime, validate_standalone_identity
from .runner import load_json, write_json

HEX64 = set("0123456789abcdef")
Acquirer = Callable[[str, str, float], dict[str, Any]]
BasisReader = Callable[[], tuple[str, str]]


def _digest(value: Any, field: str) -> str:
    require(isinstance(value, str) and len(value) == 64 and set(value) <= HEX64, f"{field} must be lowercase SHA-256")
    return value


def _git_oid(value: Any, field: str) -> str:
    require(isinstance(value, str) and len(value) == 40 and set(value) <= HEX64, f"{field} must be a lowercase 40-character Git object ID")
    return value


def validate_profile(value: dict[str, Any]) -> None:
    require_exact_keys(value, {"schema_version", "state", "mission_id", "mission_name", "claim_families", "semantic_guards", "accepted", "project_truth", "project_effect", "next_authority"}, "D1 mission profile")
    require(value["schema_version"] == "space-watch-d1-mission-profile-v0.1", "unsupported D1 mission profile")
    require(value["state"] == "FROZEN", "D1 mission profile must be frozen")
    require_nonempty_string(value["mission_id"], "mission_id")
    require_nonempty_string(value["mission_name"], "mission_name")
    require(isinstance(value["claim_families"], list) and value["claim_families"], "claim families required")
    require(len(value["claim_families"]) == len(set(value["claim_families"])), "duplicate claim family")
    require(isinstance(value["semantic_guards"], list) and value["semantic_guards"], "semantic guards required")
    require(value["accepted"] is False and value["project_truth"] is False and value["project_effect"] == "none", "D1 profile cannot claim authority or effect")
    require(value["next_authority"] == "Human Observation Review", "invalid D1 next authority")


def validate_policy(value: dict[str, Any], profile: dict[str, Any]) -> None:
    require_exact_keys(value, {"schema_version", "state", "mission_id", "acquisition_mode", "global_policy", "sources", "on_unavailable", "accepted", "project_truth", "project_effect", "next_authority"}, "D1 source policy")
    require(value["schema_version"] == "space-watch-d1-source-policy-v0.1", "unsupported D1 source policy")
    require(value["state"] == "FROZEN" and value["mission_id"] == profile["mission_id"], "D1 source policy basis mismatch")
    require(value["acquisition_mode"] == "supervised_exact_public_carrier_one_shot", "invalid D1 acquisition mode")
    policy = value["global_policy"]
    require_exact_keys(policy, {"login_allowed", "search_allowed", "alternate_carrier_allowed", "retry_allowed", "per_source_attempt_limit", "fail_closed"}, "D1 global policy")
    require(policy == {"login_allowed": False, "search_allowed": False, "alternate_carrier_allowed": False, "retry_allowed": False, "per_source_attempt_limit": 1, "fail_closed": True}, "D1 global policy is not fail-closed")
    sources = value["sources"]
    require(isinstance(sources, list) and len(sources) == 3, "D1 requires exactly three sources")
    seen: set[str] = set()
    for source in sources:
        require_exact_keys(source, {"source_id", "exact_uri", "source_role", "claim_family", "projection_schema", "authority_limit"}, "D1 source")
        for field in source:
            require_nonempty_string(source[field], field)
        require(source["source_id"] not in seen, "duplicate D1 source_id")
        seen.add(source["source_id"])
        require(source["claim_family"] in profile["claim_families"], "source claim family outside profile")
        require(source["exact_uri"].startswith("https://"), "D1 exact URI must use HTTPS")
    require(value["on_unavailable"] == "record_unavailable_without_retry_or_substitution", "invalid unavailable policy")
    require(value["accepted"] is False and value["project_truth"] is False and value["project_effect"] == "none", "D1 policy cannot claim authority or effect")
    require(value["next_authority"] == "Human Observation Review", "invalid D1 next authority")


def validate_baseline(value: dict[str, Any], designation: dict[str, Any], profile: dict[str, Any], policy: dict[str, Any], baseline_path: Path) -> None:
    require_exact_keys(value, {"schema_version", "mission_id", "source_project_basis", "candidates", "accepted", "project_truth", "project_effect", "next_authority"}, "D1 baseline")
    require(value["schema_version"] == "space-watch-d1-comparison-baseline-v0.1" and value["mission_id"] == profile["mission_id"], "D1 baseline mismatch")
    require(value["accepted"] is False and value["project_truth"] is False and value["project_effect"] == "none", "D1 baseline cannot claim authority")
    require(value["next_authority"] == "Human Observation Review", "invalid D1 baseline next authority")
    require_exact_keys(value["source_project_basis"], {"commit", "tree", "truth_carrier_sha256"}, "source project basis")
    _git_oid(value["source_project_basis"]["commit"], "source project commit"); _git_oid(value["source_project_basis"]["tree"], "source project tree"); _digest(value["source_project_basis"]["truth_carrier_sha256"], "truth carrier SHA-256")
    expected = [(item["source_id"], item["claim_family"], item["projection_schema"]) for item in policy["sources"]]
    actual = []
    require(isinstance(value["candidates"], list) and len(value["candidates"]) == 3, "D1 baseline requires exactly three candidates")
    for item in value["candidates"]:
        require_exact_keys(item, {"source_id", "claim_family", "projection_schema", "typed_content"}, "D1 baseline candidate")
        require(isinstance(item["typed_content"], dict), "D1 baseline typed content required")
        actual.append((item["source_id"], item["claim_family"], item["projection_schema"]))
    require(actual == expected, "D1 baseline coverage or order mismatch")
    require_exact_keys(designation, {"schema_version", "designation_id", "mission_id", "baseline_file", "baseline_file_sha256", "accepted_as_comparison_baseline", "project_truth", "historical_artifact_modified"}, "D1 baseline designation")
    require(designation["schema_version"] == "space-watch-d1-comparison-baseline-designation-v0.1" and designation["mission_id"] == profile["mission_id"], "D1 baseline designation mismatch")
    require(designation["baseline_file"] == "fixtures/d1-flight14-baseline.json" and designation["baseline_file_sha256"] == file_digest(baseline_path), "D1 baseline designation mismatch")
    require(designation["accepted_as_comparison_baseline"] is True and designation["project_truth"] is False and designation["historical_artifact_modified"] is False, "D1 baseline designation authority mismatch")


def validate_packet(value: dict[str, Any], root: Path, profile_path: Path, policy_path: Path, baseline_path: Path, designation_path: Path) -> None:
    require_exact_keys(value, {"schema_version", "packet_id", "repository_basis", "mission_id", "profile_file", "profile_sha256", "source_policy_file", "source_policy_sha256", "baseline_file", "baseline_sha256", "baseline_designation_file", "baseline_designation_sha256", "disposable_root", "output_directory", "total_attempt_budget", "per_source_timeout_seconds", "runtime_budget_seconds", "requested_artifacts", "accepted", "project_truth", "project_effect", "stop_reason", "next_authority"}, "D1 effect packet")
    require(value["schema_version"] == "space-watch-d1-effect-packet-v0.1", "unsupported D1 effect packet")
    require_nonempty_string(value["packet_id"], "packet_id")
    basis = value["repository_basis"]
    require_exact_keys(basis, {"repository", "commit", "tree"}, "repository basis")
    require(basis["repository"] == "https://github.com/YFOOOO/space-watch-core", "unexpected repository")
    _git_oid(basis["commit"], "repository commit"); _git_oid(basis["tree"], "repository tree")
    bindings = (("profile_file", "profile_sha256", profile_path), ("source_policy_file", "source_policy_sha256", policy_path), ("baseline_file", "baseline_sha256", baseline_path), ("baseline_designation_file", "baseline_designation_sha256", designation_path))
    for file_field, hash_field, actual in bindings:
        require(value[file_field] == validate_standalone_identity(value[file_field], file_field), "invalid file identity")
        require((root / value[file_field]).resolve() == actual.resolve(), f"{file_field} path mismatch")
        require(_digest(value[hash_field], hash_field) == file_digest(actual), f"{hash_field} mismatch")
    disposable = Path(value["disposable_root"])
    output = Path(value["output_directory"])
    require(disposable.is_absolute() and output.is_absolute(), "D1 disposable and output paths must be absolute")
    require(output.parent == disposable, "D1 output must be a direct child of disposable root")
    require(disposable.exists() and disposable.is_dir(), "D1 disposable root must already exist")
    require(not output.exists(), "D1 output directory must not already exist")
    require(value["total_attempt_budget"] == 3, "D1 total attempt budget must equal source count")
    require(isinstance(value["per_source_timeout_seconds"], int) and value["per_source_timeout_seconds"] > 0, "D1 per-source timeout must be bound")
    require(isinstance(value["runtime_budget_seconds"], int) and value["runtime_budget_seconds"] >= value["per_source_timeout_seconds"] * 3, "D1 runtime budget is insufficient")
    expected = ["basis-preflight-receipt.json", "source-attempt-ledger.json", "source-attempt-input.json", "comparison-baseline.json", "comparison-baseline-designation.json", "observation-candidates.json", "execution-receipt.json", "external-interaction-receipt.json", "artifact-manifest.json"]
    require(value["requested_artifacts"] == expected, "D1 requested artifact allowlist mismatch")
    require(value["accepted"] is False and value["project_truth"] is False and value["project_effect"] == "none", "D1 packet cannot claim authority or project effect")
    require(value["stop_reason"] == "d1_human_observation_review" and value["next_authority"] == "Human Observation Review", "invalid D1 stop")


def run_d1(*, root: Path, packet_path: Path, profile_path: Path, policy_path: Path, baseline_path: Path, designation_path: Path, acquirer: Acquirer, basis_reader: BasisReader, executed_at: str, clock: Callable[[], float] = time.monotonic) -> dict[str, Path]:
    validate_rfc3339_datetime(executed_at, "executed_at")
    packet, profile, policy = load_json(packet_path), load_json(profile_path), load_json(policy_path)
    validate_profile(profile); validate_policy(policy, profile)
    validate_packet(packet, root, profile_path, policy_path, baseline_path, designation_path)
    require(packet["mission_id"] == profile["mission_id"], "D1 packet mission mismatch")
    baseline, designation = load_json(baseline_path), load_json(designation_path)
    validate_baseline(baseline, designation, profile, policy, baseline_path)
    actual_commit, actual_tree = basis_reader()
    require((actual_commit, actual_tree) == (packet["repository_basis"]["commit"], packet["repository_basis"]["tree"]), "D1 exact repository basis mismatch")
    output = Path(packet["output_directory"])
    started = clock()
    attempts: list[dict[str, Any]] = []
    for source in policy["sources"]:
        require(clock() - started < packet["runtime_budget_seconds"], "D1 runtime budget exhausted before acquisition")
        result = acquirer(source["source_id"], source["exact_uri"], float(packet["per_source_timeout_seconds"]))
        require_exact_keys(result, {"status", "attempted_at", "final_uri", "redirect_count", "login_used", "search_used", "alternate_carrier_used", "retry_used", "typed_content", "limitations"}, "D1 acquisition result")
        require(result["status"] in {"available", "partial", "unavailable"}, "invalid D1 source status")
        validate_rfc3339_datetime(result["attempted_at"], "attempted_at")
        require(result["final_uri"] == source["exact_uri"] and result["redirect_count"] == 0, "redirect or URI substitution forbidden")
        for field in ("login_used", "search_used", "alternate_carrier_used", "retry_used"):
            require(result[field] is False, f"{field} forbidden")
        require(isinstance(result["limitations"], list) and all(isinstance(item, str) for item in result["limitations"]), "limitations must be strings")
        require((result["status"] == "unavailable" and result["typed_content"] is None) or (result["status"] != "unavailable" and isinstance(result["typed_content"], dict)), "typed content/status mismatch")
        attempts.append({**source, **result, "attempt_count": 1})
    require(clock() - started <= packet["runtime_budget_seconds"], "D1 runtime budget exhausted")
    output.mkdir()
    ledger = {"schema_version": "space-watch-d1-attempt-ledger-v0.1", "packet_id": packet["packet_id"], "attempt_budget": 3, "attempts_consumed": 3, "sources": attempts, "retry_count": 0, "alternate_carrier_count": 0, "stop_reason": "d1_human_observation_review"}
    preflight = {"schema_version": "space-watch-d1-basis-preflight-receipt-v0.1", "packet_id": packet["packet_id"], "repository_commit": actual_commit, "repository_tree": actual_tree, "profile_sha256": file_digest(profile_path), "source_policy_sha256": file_digest(policy_path), "baseline_sha256": file_digest(baseline_path), "baseline_designation_sha256": file_digest(designation_path), "verdict": "PASS"}
    write_json(output / "basis-preflight-receipt.json", preflight); write_json(output / "source-attempt-ledger.json", ledger)
    previous = {(item["source_id"], item["claim_family"]): item for item in baseline["candidates"]}
    source_input = {"schema_version": "space-watch-d1-source-attempt-input-v0.1", "packet_id": packet["packet_id"], "mission_id": profile["mission_id"], "acquisition_mode": policy["acquisition_mode"], "source_acquisition_effect": True, "project_effect": "none", "attempts": attempts}
    candidates = []
    for item in attempts:
        old = previous.get((item["source_id"], item["claim_family"]))
        current_digest = canonical_digest(item["typed_content"]) if item["typed_content"] is not None else None
        old_digest = canonical_digest(old["typed_content"]) if old and old["typed_content"] is not None else None
        comparison = "unavailable" if current_digest is None else ("new" if old_digest is None else ("duplicate" if current_digest == old_digest else "changed"))
        candidates.append({"candidate_id": f'{profile["mission_id"]}:{item["source_id"]}:{item["claim_family"]}', "source_id": item["source_id"], "claim_family": item["claim_family"], "availability": item["status"], "projection_schema": item["projection_schema"], "typed_content": item["typed_content"], "comparison": comparison, "authority_limit": item["authority_limit"], "limitations": item["limitations"], "accepted": False, "project_truth": False, "next_authority": "Human Observation Review"})
    bundle = {"schema_version": "space-watch-d1-observation-candidate-bundle-v0.1", "packet_id": packet["packet_id"], "mission_id": profile["mission_id"], "baseline_sha256": file_digest(baseline_path), "candidates": candidates, "accepted": False, "project_truth": False, "project_effect": "none", "next_authority": "Human Observation Review"}
    write_json(output / "source-attempt-input.json", source_input)
    write_json(output / "comparison-baseline.json", baseline)
    write_json(output / "comparison-baseline-designation.json", designation)
    write_json(output / "observation-candidates.json", bundle)
    external = {"schema_version": "space-watch-d1-external-interaction-receipt-v0.1", "packet_id": packet["packet_id"], "repository_read": True, "source_acquisition": True, "source_attempt_count": 3, "login_used": False, "search_used": False, "retry_used": False, "alternate_carrier_used": False, "repository_write": False, "project_write": False, "routine_created": False, "notification_sent": False, "accepted": False, "project_truth": False}
    write_json(output / "external-interaction-receipt.json", external)
    receipt = {"schema_version": "space-watch-d1-execution-receipt-v0.1", "packet_id": packet["packet_id"], "executed_at": executed_at, "repository_commit": actual_commit, "repository_tree": actual_tree, "source_attempt_count": 3, "runtime_budget_seconds": packet["runtime_budget_seconds"], "project_effect": "none", "accepted": False, "project_truth": False, "stop_reason": "d1_human_observation_review", "next_authority": "Human Observation Review"}
    write_json(output / "execution-receipt.json", receipt)
    artifact_names = packet["requested_artifacts"][:-1]
    manifest = {"schema_version": "space-watch-d1-artifact-manifest-v0.1", "packet_id": packet["packet_id"], "artifacts": [{"path": name, "bytes": (output / name).stat().st_size, "sha256": file_digest(output / name)} for name in artifact_names], "manifest_self_hash": "excluded_by_contract", "accepted": False, "project_truth": False}
    write_json(output / "artifact-manifest.json", manifest)
    return {"output": output, **{name.removesuffix(".json").replace("-", "_"): output / name for name in packet["requested_artifacts"]}}
