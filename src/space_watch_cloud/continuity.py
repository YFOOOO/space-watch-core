"""Offline continuity candidate. Pure transitions; callers own atomic persistence/CAS.

No acquisition, transport, project truth, or Human acceptance occurs here. Each
transition requires a version. A storage integration MUST atomically compare and
replace that version, or use one writer; these pure functions are not a lock.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
import re
from typing import Any

from .canonical import canonical_digest

ID = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"}
HASH = {"type": "string", "pattern": r"^[0-9a-f]{64}$"}
TEXT = {"type": "string", "minLength": 1}
TIMESTAMP = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$", "format": "date-time"}
NULL_HASH = {"anyOf": [HASH, {"type": "null"}]}
RESERVED = ["observed_at", "fetched_at", "limitations", "raw_sha256"]
FACTS = {"type": "object", "minProperties": 1,
         "propertyNames": {"not": {"enum": RESERVED}},
         "additionalProperties": {"type": ["string", "number", "boolean", "null"]}}

def obj(properties: dict, **extra: Any) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False, **extra}

def mapping(value: dict, **extra: Any) -> dict:
    return {"type": "object", "propertyNames": ID, "additionalProperties": value, **extra}

ATTEMPT = obj({"observed_at": TIMESTAMP, "status": {"enum": ["available", "unavailable"]},
               "raw_sha256": NULL_HASH,
               "limitations": {"type": "array", "items": TEXT}})
VALID = obj({"observed_at": TIMESTAMP, "raw_sha256": HASH, "facts": FACTS, "facts_sha256": HASH})
OBSERVATION_SCHEMA = obj({"mission_id": ID, "source_id": ID, **ATTEMPT["properties"],
                          "facts": {"anyOf": [FACTS, {"type": "null"}]}},
    allOf=[{"if": {"properties": {"status": {"const": "available"}}},
            "then": {"properties": {"facts": FACTS, "raw_sha256": HASH}},
            "else": {"properties": {"facts": {"type": "null"}}}}])
CANDIDATE_SCHEMA = obj({"mission_id": ID, "candidate_id": HASH,
    "source_basis": mapping(HASH, minProperties=1), "facts_sha256": HASH,
    "accepted": {"const": False}, "project_truth": {"const": False}})
DELIVERY = obj({"candidate": CANDIDATE_SCHEMA, "destination": TEXT,
    "attempt_id": HASH, "status": {"enum": ["pending", "unknown", "acked"]},
    "receipt": {"anyOf": [TEXT, {"type": "null"}]}},
    allOf=[{"if": {"properties": {"status": {"const": "acked"}}},
            "then": {"properties": {"receipt": TEXT}},
            "else": {"properties": {"receipt": {"type": "null"}}}}])
STATE_SCHEMA = obj({"schema_version": {"const": 1}, "mission_id": ID,
    "version": {"type": "integer", "minimum": 0},
    "sources": mapping(obj({"last_attempt": {"anyOf": [ATTEMPT, {"type": "null"}]},
                            "last_valid": {"anyOf": [VALID, {"type": "null"}]}}), minProperties=1),
    "deliveries": {"type": "object", "propertyNames": HASH, "additionalProperties": DELIVERY},
    "accepted": {"const": False}, "project_truth": {"const": False}})


OBSERVATION_SCHEMA["$id"] = "space-watch-continuity-observation-v0.1"
CANDIDATE_SCHEMA["$id"] = "space-watch-continuity-candidate-v0.1"
STATE_SCHEMA["$id"] = "space-watch-continuity-state-v0.1"

def _check(value: Any, schema: dict) -> None:
    """Validate the deliberately small JSON Schema vocabulary used above."""
    if "anyOf" in schema:
        for choice in schema["anyOf"]:
            try:
                _check(value, choice)
                return
            except ValueError:
                pass
        raise ValueError("no allowed shape matched")
    if "not" in schema:
        try:
            _check(value, schema["not"])
        except ValueError:
            pass
        else:
            raise ValueError("forbidden value")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError("constant mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("enum mismatch")
    types = schema.get("type", [])
    if isinstance(types, str):
        types = [types]
    predicates = {"object": lambda: type(value) is dict, "array": lambda: type(value) is list,
                  "string": lambda: type(value) is str, "integer": lambda: type(value) is int,
                  "number": lambda: type(value) in (int, float) and math.isfinite(value),
                  "boolean": lambda: type(value) is bool, "null": lambda: value is None}
    if types and not any(predicates[t]() for t in types):
        raise ValueError("type mismatch")
    if isinstance(value, str):
        if schema.get("format") == "date-time":
            _timestamp(value)
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
            raise ValueError("invalid string")
    if type(value) is int and value < schema.get("minimum", value):
        raise ValueError("below minimum")
    if type(value) is list:
        for item in value:
            _check(item, schema.get("items", {}))
    if type(value) is dict:
        if len(value) < schema.get("minProperties", 0) or any(k not in value for k in schema.get("required", [])):
            raise ValueError("missing properties")
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _check(key, schema.get("propertyNames", {}))
            properties = schema.get("properties", {})
            if key in properties:
                _check(item, properties[key])
            elif schema.get("additionalProperties") is False:
                raise ValueError("unexpected property")
            else:
                _check(item, schema.get("additionalProperties", {}))
    for clause in schema.get("allOf", []):
        try:
            _check(value, clause["if"])
        except ValueError:
            _check(value, clause.get("else", {}))
        else:
            _check(value, clause["then"])


def _candidate(mission_id: str, sources: dict) -> dict | None:
    # Incomplete observations cannot claim a complete mission snapshot.
    if any(source["last_valid"] is None or source["last_attempt"] is None
           or source["last_attempt"]["status"] != "available" for source in sources.values()):
        return None
    basis = {key: source["last_valid"]["facts_sha256"] for key, source in sources.items()}
    facts_hash = canonical_digest({key: source["last_valid"]["facts"] for key, source in sources.items()})
    identity = {"mission_id": mission_id, "source_basis": basis, "facts_sha256": facts_hash}
    return {**identity, "candidate_id": canonical_digest(identity), "accepted": False, "project_truth": False}


def delivery_key(candidate: dict, destination: str) -> str:
    _check(candidate, CANDIDATE_SCHEMA)
    _check(destination, TEXT)
    return canonical_digest({"mission_id": candidate["mission_id"], "candidate_id": candidate["candidate_id"],
                             "destination": destination})


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed


def validate_state(state: dict) -> None:
    _check(state, STATE_SCHEMA)
    for source in state["sources"].values():
        valid = source["last_valid"]
        attempt = source["last_attempt"]
        if attempt:
            _timestamp(attempt["observed_at"])
        if valid:
            _timestamp(valid["observed_at"])
            if attempt is None or _timestamp(valid["observed_at"]) > _timestamp(attempt["observed_at"]):
                raise ValueError("valid observation ahead of attempt")
        if attempt and attempt["status"] == "available":
            if valid is None or any(attempt[k] != valid[k] for k in ("observed_at", "raw_sha256")):
                raise ValueError("available attempt must bind latest valid observation")
        if valid and valid["facts_sha256"] != canonical_digest(valid["facts"]):
            raise ValueError("fact digest mismatch")
    receipts = set()
    for key, delivery in state["deliveries"].items():
        if delivery["receipt"] is not None:
            binding = (delivery["destination"], delivery["receipt"])
            if binding in receipts:
                raise ValueError("receipt reused across candidates")
            receipts.add(binding)
        candidate = delivery["candidate"]
        identity = {k: candidate[k] for k in ("mission_id", "source_basis", "facts_sha256")}
        if candidate["mission_id"] != state["mission_id"] or candidate["candidate_id"] != canonical_digest(identity):
            raise ValueError("candidate binding mismatch")
        if set(candidate["source_basis"]) != set(state["sources"]):
            raise ValueError("candidate sources mismatch")
        if key != delivery_key(candidate, delivery["destination"]):
            raise ValueError("delivery key mismatch")


def initial_state(mission_id: str, source_ids: list[str]) -> dict:
    if type(source_ids) is not list or len(set(source_ids)) != len(source_ids):
        raise ValueError("unique source list required")
    state = {"schema_version": 1, "mission_id": mission_id, "version": 0,
             "sources": {s: {"last_attempt": None, "last_valid": None} for s in source_ids},
             "deliveries": {}, "accepted": False, "project_truth": False}
    validate_state(state)
    return state


def _transition(state: dict, expected_version: int) -> dict:
    validate_state(state)
    if type(expected_version) is not int or expected_version != state["version"]:
        raise ValueError("version conflict")
    result = deepcopy(state)
    result["version"] += 1
    return result


def apply_observation(state: dict, observation: dict, *, expected_version: int) -> tuple[dict, dict | None]:
    _check(observation, OBSERVATION_SCHEMA)
    result = _transition(state, expected_version)
    if observation["mission_id"] != state["mission_id"] or observation["source_id"] not in state["sources"]:
        raise ValueError("observation identity mismatch")
    source = result["sources"][observation["source_id"]]
    observed_time = _timestamp(observation["observed_at"])
    if source["last_attempt"] and observed_time < _timestamp(source["last_attempt"]["observed_at"]):
        raise ValueError("observation time moved backwards")
    source["last_attempt"] = {k: deepcopy(observation[k]) for k in ATTEMPT["properties"]}
    if observation["status"] == "available":
        source["last_valid"] = {"observed_at": observation["observed_at"], "raw_sha256": observation["raw_sha256"],
                                "facts": deepcopy(observation["facts"]), "facts_sha256": canonical_digest(observation["facts"])}
    validate_state(result)
    # A failed fetch never produces a candidate using stale facts.
    candidate = _candidate(result["mission_id"], result["sources"]) if observation["status"] == "available" else None
    return result, candidate


def candidate_is_current(state: dict, candidate: dict) -> bool:
    validate_state(state)
    _check(candidate, CANDIDATE_SCHEMA)
    return candidate == _candidate(state["mission_id"], state["sources"])


def prepare_delivery(state: dict, candidate: dict, destination: str, *, expected_version: int) -> tuple[dict, str, str]:
    """Return state, key, action: send, reconcile, or skip. No send occurs."""
    result = _transition(state, expected_version)
    if not candidate_is_current(state, candidate):
        raise ValueError("stale candidate basis")
    key = delivery_key(candidate, destination)
    existing = result["deliveries"].get(key)
    if existing:
        action = "skip" if existing["status"] == "acked" else "reconcile"
    else:
        result["deliveries"][key] = {"candidate": deepcopy(candidate), "destination": destination,
                                     "attempt_id": canonical_digest({"key": key, "version": result["version"]}),
                                     "status": "pending", "receipt": None}
        action = "send"
    validate_state(result)
    return result, key, action


def reconcile_delivery(state: dict, key: str, outcome: str, *, expected_version: int, attempt_id: str, receipt: str | None = None) -> tuple[dict, str]:
    """Only verified not_found permits a resend; unknown remains reconciliation-only.

    outcome is caller-supplied transport evidence, not proof produced by this core.
    A pending intent may already have been sent before a crash, so it also requires
    reconciliation. An ack is immutable and never becomes resendable.
    """
    result = _transition(state, expected_version)
    if key not in result["deliveries"] or outcome not in ("acked", "not_found", "unknown"):
        raise ValueError("invalid reconciliation")
    delivery = result["deliveries"][key]
    if attempt_id != delivery["attempt_id"]:
        raise ValueError("delivery attempt mismatch")
    if delivery["status"] == "acked":
        if outcome != "acked" or receipt != delivery["receipt"]:
            raise ValueError("ack is immutable")
        return result, "skip"
    if outcome == "acked":
        _check(receipt, TEXT)
        delivery.update(status="acked", receipt=receipt)
        action = "skip"
    else:
        if receipt is not None:
            raise ValueError("receipt only belongs to ack")
        delivery.update(status="unknown" if outcome == "unknown" else "pending", receipt=None)
        action = "reconcile"
        if outcome == "not_found" and candidate_is_current(state, delivery["candidate"]):
            delivery["attempt_id"] = canonical_digest({"key": key, "version": result["version"]})
            action = "send"
    validate_state(result)
    return result, action


def ack_delivery(state: dict, key: str, receipt: str, *, expected_version: int, attempt_id: str) -> dict:
    return reconcile_delivery(state, key, "acked", expected_version=expected_version, attempt_id=attempt_id, receipt=receipt)[0]
