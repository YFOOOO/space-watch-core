"""Effect-free O1 pilot state and repeat-suppression evaluation."""

from __future__ import annotations

from typing import Any

from .canonical import canonical_digest
from .model import require, require_exact_keys, require_nonempty_string

HEX64 = set("0123456789abcdef")
STATE_KEYS = {
    "schema_version", "repository_commit", "repository_tree", "last_run_id",
    "last_candidate_bundle_sha256", "last_reported_changed_sha256",
    "consecutive_capability_failure_count", "invocation_count",
}


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


def evaluate_run(*, state: dict[str, Any], run_id: str, bundle: dict[str, Any], repository_commit: str, repository_tree: str) -> tuple[str, dict[str, Any]]:
    """Validate one completed D1 bundle and derive the next non-authoritative O1 state."""
    require_exact_keys(state, STATE_KEYS, "O1 state")
    require(state["schema_version"] == "space-watch-o1-pilot-state-v0.1", "unsupported O1 state")
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
