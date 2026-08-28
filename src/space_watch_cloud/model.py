"""Generic synthetic-only input and baseline contract."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
import re
from typing import Any


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    unknown = set(value) - expected
    missing = expected - set(value)
    require(not unknown, f"schema-forbidden fields in {label}: {sorted(unknown)}")
    require(not missing, f"required fields missing from {label}: {sorted(missing)}")


def require_nonempty_string(value: Any, field: str) -> None:
    require(isinstance(value, str) and bool(value), f"{field} must be a non-empty string")


def validate_standalone_identity(value: Any, field: str) -> str:
    require_nonempty_string(value, field)
    require("\\" not in value, f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    require(not path.is_absolute(), f"{field} must be standalone-relative")
    require(all(part not in {"", ".", ".."} for part in path.parts), f"{field} must be normalized and non-escaping")
    require(path.as_posix() == value, f"{field} must be normalized and non-escaping")
    return value


RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


def validate_rfc3339_datetime(value: Any, field: str) -> None:
    require(isinstance(value, str) and RFC3339_DATE_TIME.fullmatch(value) is not None, f"{field} must be RFC 3339 date-time")
    try:
        datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be RFC 3339 date-time") from exc


def identity(item: dict[str, Any]) -> str:
    return f'{item["source_id"]}:{item["claim_family"]}'


def validate_source_input(document: dict[str, Any]) -> None:
    require_exact_keys(document, {"schema_version", "mission_id", "acquisition_mode", "source_acquisition_effect", "project_effect", "attempts"}, "source input")
    require(document.get("schema_version") == "space-watch-source-attempt-input-v0.2", "unsupported input schema")
    require(document.get("acquisition_mode") == "synthetic_fixture", "only synthetic_fixture is permitted")
    require(document.get("source_acquisition_effect") is False, "synthetic input cannot claim source acquisition")
    require(document.get("project_effect") == "none", "project effect is forbidden")
    require(isinstance(document.get("mission_id"), str) and document["mission_id"], "mission_id required")
    attempts = document.get("attempts")
    require(isinstance(attempts, list) and attempts, "at least one source attempt required")
    seen: set[str] = set()
    for attempt in attempts:
        require_exact_keys(attempt, {"source_id", "claim_family", "carrier_class", "status", "attempt_count", "attempted_at", "login_used", "retry_used", "alternate_carrier_used", "projection_schema", "typed_content", "limitations"}, "source attempt")
        require_nonempty_string(attempt.get("source_id"), "source_id")
        require_nonempty_string(attempt.get("claim_family"), "claim_family")
        key = identity(attempt)
        require(key not in seen, f"duplicate source identity: {key}")
        seen.add(key)
        require(attempt.get("carrier_class") == "synthetic_fixture", f"non-synthetic carrier forbidden: {key}")
        require(attempt.get("status") in {"available", "partial", "unavailable"}, f"invalid status: {key}")
        require(attempt.get("attempt_count") == 1, f"attempt_count must be one: {key}")
        require(attempt.get("login_used") is False, f"login forbidden: {key}")
        require(attempt.get("retry_used") is False, f"retry forbidden: {key}")
        require(attempt.get("alternate_carrier_used") is False, f"alternate carrier forbidden: {key}")
        require(isinstance(attempt.get("projection_schema"), str) and attempt["projection_schema"], f"projection_schema required: {key}")
        require(isinstance(attempt.get("limitations"), list) and all(isinstance(item, str) for item in attempt["limitations"]), f"limitations must be strings: {key}")
        validate_rfc3339_datetime(attempt.get("attempted_at"), "attempted_at")
        content = attempt.get("typed_content")
        if attempt["status"] == "available":
            require(isinstance(content, dict), f"typed_content required: {key}")
        elif attempt["status"] == "unavailable":
            require(content is None, f"typed_content must be null for unavailable source: {key}")
        else:
            require(content is None or isinstance(content, dict), f"typed_content must be object or null: {key}")


def validate_baseline(document: dict[str, Any], mission_id: str) -> None:
    require_exact_keys(document, {"schema_version", "mission_id", "project_truth", "candidates"}, "baseline")
    require(document.get("schema_version") == "space-watch-comparison-baseline-v0.2", "unsupported baseline schema")
    require(document.get("mission_id") == mission_id, "baseline mission mismatch")
    require(document.get("project_truth") is False, "baseline cannot claim project truth")
    candidates = document.get("candidates")
    require(isinstance(candidates, list), "baseline candidates required")
    for item in candidates:
        require_exact_keys(item, {"source_id", "claim_family", "projection_schema", "typed_content"}, "baseline candidate")
        require_nonempty_string(item.get("source_id"), "baseline source_id")
        require_nonempty_string(item.get("claim_family"), "baseline claim_family")
        require_nonempty_string(item.get("projection_schema"), "baseline projection_schema")
        require(item.get("typed_content") is None or isinstance(item.get("typed_content"), dict), "baseline typed_content must be object or null")
    keys = [identity(item) for item in candidates]
    require(len(keys) == len(set(keys)), "duplicate baseline identity")


def validate_baseline_designation(document: dict[str, Any], mission_id: str) -> None:
    require_exact_keys(document, {"schema_version", "designation_id", "mission_id", "baseline_file", "baseline_file_sha256", "accepted_as_comparison_baseline", "project_truth", "authority_scope", "historical_artifact_modified"}, "baseline designation")
    require(document.get("schema_version") == "space-watch-comparison-baseline-designation-v0.2", "unsupported baseline designation schema")
    require(document.get("mission_id") == mission_id, "baseline designation mission mismatch")
    require(document.get("accepted_as_comparison_baseline") is True, "baseline designation authority missing")
    require(document.get("project_truth") is False, "baseline designation cannot claim project truth")
    require(document.get("historical_artifact_modified") is False, "baseline designation cannot modify its artifact")
    require_nonempty_string(document.get("designation_id"), "designation_id")
    validate_standalone_identity(document.get("baseline_file"), "baseline_file")
    require(document.get("authority_scope") == "synthetic comparison fixture only", "baseline designation authority_scope is invalid")
    digest = document.get("baseline_file_sha256")
    require(isinstance(digest, str) and len(digest) == 64 and all(character in "0123456789abcdef" for character in digest), "baseline designation SHA-256 required")
