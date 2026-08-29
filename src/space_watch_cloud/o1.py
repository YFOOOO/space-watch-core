"""O1 pilot orchestration, state transition, and repeat suppression."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from .canonical import canonical_digest, file_digest
from .model import require, require_exact_keys, require_nonempty_string, validate_rfc3339_datetime
from .runner import load_json, write_json

HEX64 = set("0123456789abcdef")
STATE_KEYS = {
    "schema_version", "repository_commit", "repository_tree", "last_run_id",
    "last_candidate_bundle_sha256", "last_reported_changed_sha256",
    "consecutive_capability_failure_count", "invocation_count",
}
BundleProducer = Callable[[Path], Path]


def _oid(value: Any, field: str) -> str:
    require(isinstance(value, str) and len(value) == 40 and set(value) <= HEX64, f"{field} must be a lowercase Git object ID")
    return value


def initial_state(repository_commit: str, repository_tree: str) -> dict[str, Any]:
    return {
        "schema_version": "space-watch-o1-pilot-state-v0.1",
        "repository_commit": _oid(repository_commit, "repository_commit"),
        "repository_tree": _oid(repository_tree, "repository_tree"),
        "last_run_id": None,
        "last_candidate_bundle_sha256": None,
        "last_reported_changed_sha256": None,
        "consecutive_capability_failure_count": 0,
        "invocation_count": 0,
    }


def validate_state(state: dict[str, Any]) -> None:
    require_exact_keys(state, STATE_KEYS, "O1 state")
    require(state["schema_version"] == "space-watch-o1-pilot-state-v0.1", "unsupported O1 state")
    _oid(state["repository_commit"], "repository_commit")
    _oid(state["repository_tree"], "repository_tree")
    require(state["last_run_id"] is None or isinstance(state["last_run_id"], str), "invalid O1 last_run_id")
    for field in ("last_candidate_bundle_sha256", "last_reported_changed_sha256"):
        value = state[field]
        require(value is None or (isinstance(value, str) and len(value) == 64 and set(value) <= HEX64), f"invalid O1 {field}")
    require(isinstance(state["consecutive_capability_failure_count"], int) and state["consecutive_capability_failure_count"] >= 0, "invalid O1 failure count")
    require(isinstance(state["invocation_count"], int) and 0 <= state["invocation_count"] <= 3, "invalid O1 invocation count")


def evaluate_run(*, state: dict[str, Any], run_id: str, bundle: dict[str, Any], repository_commit: str, repository_tree: str) -> tuple[str, dict[str, Any]]:
    """Validate one completed D1 bundle and derive the next non-authoritative O1 state."""
    validate_state(state)
    require(state["repository_commit"] == _oid(repository_commit, "repository_commit") and state["repository_tree"] == _oid(repository_tree, "repository_tree"), "O1 exact repository basis mismatch")
    require_nonempty_string(run_id, "run_id")
    require(run_id != state["last_run_id"], "O1 scheduled run ID already completed")
    require(isinstance(state["invocation_count"], int) and 0 <= state["invocation_count"] < 3, "O1 pilot invocation budget exhausted")
    require_exact_keys(bundle, {"schema_version", "packet_id", "mission_id", "baseline_sha256", "candidates", "accepted", "project_truth", "project_effect", "next_authority"}, "O1 D1 bundle")
    require(bundle["schema_version"] == "space-watch-d1-observation-candidate-bundle-v0.1" and bundle["mission_id"] == "starship-ift14", "O1 D1 bundle mismatch")
    require(bundle["accepted"] is False and bundle["project_truth"] is False and bundle["project_effect"] == "none" and bundle["next_authority"] == "Human Observation Review", "O1 bundle crossed Human authority boundary")
    require(isinstance(bundle["candidates"], list) and len(bundle["candidates"]) == 3, "O1 requires exactly three D1 candidates")
    comparisons = []
    for candidate in bundle["candidates"]:
        require(isinstance(candidate, dict), "O1 candidate must be an object")
        require(candidate.get("accepted") is False and candidate.get("project_truth") is False and candidate.get("next_authority") == "Human Observation Review", "O1 candidate crossed Human authority boundary")
        comparison = candidate.get("comparison")
        require(comparison in {"new", "changed", "duplicate", "unavailable"}, "invalid O1 candidate comparison")
        comparisons.append(comparison)

    bundle_sha = canonical_digest(bundle)
    changed_sha = canonical_digest([candidate for candidate in bundle["candidates"] if candidate["comparison"] in {"new", "changed"}]) if any(item in {"new", "changed"} for item in comparisons) else None
    if changed_sha is not None:
        verdict = "REPEAT_SUPPRESSED" if changed_sha == state["last_reported_changed_sha256"] else "HUMAN_REVIEW_CANDIDATE"
    elif "unavailable" in comparisons:
        verdict = "COVERAGE_LIMITATION"
    else:
        verdict = "NO_MATERIAL_DELTA"

    next_state = dict(state)
    next_state.update({
        "last_run_id": run_id,
        "last_candidate_bundle_sha256": bundle_sha,
        "last_reported_changed_sha256": changed_sha if verdict == "HUMAN_REVIEW_CANDIDATE" else state["last_reported_changed_sha256"],
        "consecutive_capability_failure_count": state["consecutive_capability_failure_count"] + 1 if verdict == "COVERAGE_LIMITATION" else 0,
        "invocation_count": state["invocation_count"] + 1,
    })
    return verdict, next_state


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    require(path.parent.exists() and path.parent.is_dir(), "O1 state parent must exist")
    temporary = path.with_name(f".{path.name}.tmp")
    require(not temporary.exists(), "O1 state temporary path already exists")
    write_json(temporary, value)
    os.replace(temporary, path)


def run_o1(
    *,
    state_path: Path,
    output_dir: Path,
    run_id: str,
    scheduled_occurrence: str,
    executed_at: str,
    repository_commit: str,
    repository_tree: str,
    runtime_budget_seconds: int,
    maximum_output_bytes: int,
    run_kind: str,
    producer: BundleProducer,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Path]:
    """Run one producer, evaluate its bundle, persist a receipt, then atomically advance state."""
    require(run_kind in {"synthetic_test", "scheduled_live"}, "invalid O1 run kind")
    require(isinstance(runtime_budget_seconds, int) and runtime_budget_seconds > 0, "O1 runtime budget must be positive")
    require(isinstance(maximum_output_bytes, int) and maximum_output_bytes > 0, "O1 output budget must be positive")
    validate_rfc3339_datetime(scheduled_occurrence, "scheduled_occurrence")
    validate_rfc3339_datetime(executed_at, "executed_at")
    require(not output_dir.exists(), "O1 output directory must not already exist")
    state = load_json(state_path)
    validate_state(state)
    require(state["repository_commit"] == repository_commit and state["repository_tree"] == repository_tree, "O1 exact repository basis mismatch")
    require(run_id != state["last_run_id"], "O1 scheduled run ID already completed")
    require(state["invocation_count"] < 3, "O1 pilot invocation budget exhausted")

    started = clock()
    output_dir.mkdir()
    producer_dir = output_dir / "producer"
    producer_dir.mkdir()
    bundle_path = producer(producer_dir)
    require(bundle_path.is_file() and bundle_path.parent == producer_dir, "O1 producer bundle path mismatch")
    require(clock() - started <= runtime_budget_seconds, "O1 total runtime budget exhausted")
    bundle = load_json(bundle_path)
    verdict, next_state = evaluate_run(
        state=state,
        run_id=run_id,
        bundle=bundle,
        repository_commit=repository_commit,
        repository_tree=repository_tree,
    )
    elapsed = clock() - started
    require(elapsed <= runtime_budget_seconds, "O1 total runtime budget exhausted")

    state_before_sha256 = file_digest(state_path)
    state_after_path = output_dir / "o1-state-after.json"
    write_json(state_after_path, next_state)
    state_after_sha256 = file_digest(state_after_path)
    receipt = {
        "schema_version": "space-watch-o1-execution-receipt-v0.1",
        "run_id": run_id,
        "run_kind": run_kind,
        "scheduled_occurrence": scheduled_occurrence,
        "executed_at": executed_at,
        "repository_commit": repository_commit,
        "repository_tree": repository_tree,
        "runtime_budget_seconds": runtime_budget_seconds,
        "maximum_output_bytes": maximum_output_bytes,
        "elapsed_seconds": elapsed,
        "candidate_bundle_path": "producer/observation-candidates.json",
        "candidate_bundle_sha256": file_digest(bundle_path),
        "state_before_sha256": state_before_sha256,
        "state_after_sha256": state_after_sha256,
        "invocation_count_before": state["invocation_count"],
        "invocation_count_after": next_state["invocation_count"],
        "verdict": verdict,
        "source_acquisition": run_kind == "scheduled_live",
        "network_access": run_kind == "scheduled_live",
        "workspace_write": True,
        "notification_sent": False,
        "accepted": False,
        "project_truth": False,
        "next_authority": "Human O1 Review",
    }
    receipt_path = output_dir / "o1-execution-receipt.json"
    write_json(receipt_path, receipt)
    output_bytes = sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file())
    require(output_bytes <= maximum_output_bytes, "O1 output budget exhausted")
    _atomic_write_json(state_path, next_state)
    return {"output": output_dir, "bundle": bundle_path, "receipt": receipt_path, "state_after": state_after_path, "state": state_path}
