"""Pure adapter for caller-supplied research snapshots; no filesystem or network I/O."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import ipaddress
import re
from urllib.parse import urlsplit

from .canonical import canonical_digest

VERSION = "space-watch-research-task-v0.1"
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
TIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
URL_PATTERN = r"^https?://(?![^/]*@)(?!localhost(?:[:/]|$))(?!127\.)(?!10\.)(?!192\.168\.)(?!172\.(?:1[6-9]|2[0-9]|3[01])\.)(?!169\.254\.)(?!\[)[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[^?#\s]*)?$"


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _rows(value, label):
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be an object list")
    return value


def _strings(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a string list")
    for item in value:
        _text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"duplicate {label}")
    return value


def _public_url(value):
    _text(value, "carrier_url")
    if not re.fullmatch(URL_PATTERN, value):
        raise ValueError("invalid portable carrier_url")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("carrier_url must be public HTTP(S) without user information")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local")) or "." not in host:
        raise ValueError("local carrier_url is not portable")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("nonpublic carrier_url")
    # Public carriers are locators, never credential-bearing acquisition instructions.
    if parsed.query or parsed.fragment:
        raise ValueError("carrier_url query/fragment requires explicit sanitization by caller")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("invalid carrier_url port") from error
    return value


def adapt_research_readout(snapshot: dict, *, mission_id: str) -> dict:
    """Export minimal evidence/decision layers without promoting prior review or claims."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") not in ("research-readout-v1", "research-readout-v2"):
        raise ValueError("unsupported research readout version")
    mission = snapshot.get("mission")
    if not isinstance(mission, dict) or mission.get("id") != _text(mission_id, "mission_id"):
        raise ValueError("mission identity mismatch")
    aliases = _strings(mission.get("aliases"), "aliases")
    if mission_id not in aliases or type(mission.get("record_available")) is not bool:
        raise ValueError("mission identity/record availability invalid")
    _text(mission.get("name"), "mission.name")
    as_of = _text(snapshot.get("as_of"), "as_of")
    if not re.fullmatch(TIME_PATTERN, as_of):
        raise ValueError("invalid as_of timestamp")
    try:
        parsed_time = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            raise ValueError()
    except ValueError as error:
        raise ValueError("as_of must be timezone-aware ISO timestamp") from error
    sources, source_ids = [], set()
    for row in _rows(snapshot.get("sources"), "sources"):
        sid = _text(row.get("source_id"), "source_id")
        if sid in source_ids:
            raise ValueError("duplicate source_id")
        source_ids.add(sid)
        out = {"source_id": sid}
        for key in ("observed_at", "limitation"):
            if row.get(key) is not None:
                out[key] = _text(row[key], key)
        if row.get("carrier_url"):
            out["carrier_url"] = _public_url(row["carrier_url"])
        sources.append(out)
    claims, evaluations, claim_ids, open_questions = [], [], set(), []
    for row in _rows(snapshot.get("claims"), "claims"):
        cid = _text(row.get("claim_id"), "claim_id")
        if cid in claim_ids or cid in source_ids or cid in aliases:
            raise ValueError("duplicate or colliding claim_id")
        claim_ids.add(cid)
        refs = _strings(row.get("evidence_refs"), "evidence_refs")
        if set(refs) - source_ids:
            raise ValueError("claim references missing source")
        state = _text(row.get("evaluation_state"), "evaluation_state")
        out = {"claim_id": cid, "evidence_refs": list(refs)}
        for key in ("family", "text", "object", "action", "authority", "limitation"):
            if row.get(key) is not None:
                out[key] = _text(row[key], key)
        claims.append(out)
        evaluations.append({"claim_id": cid, "evaluation_state": state, "accepted": False})
        if row.get("open") is True or state == "candidate":
            open_questions.append({"claim_id": cid, "limitation": row.get("limitation", "")})
    if source_ids.intersection(aliases):
        raise ValueError("source_id collides with mission identity")
    basis = []
    for row in _rows(snapshot.get("basis"), "basis"):
        ref = _text(row.get("ref"), "basis.ref")
        kind = row.get("kind")
        expected = "claim" if ref in claim_ids else "source" if ref in source_ids else "explicit_identity" if ref in aliases else "unresolved"
        if kind != expected:
            raise ValueError("basis kind/reference mismatch")
        if any(existing["ref"] == ref for existing in basis):
            raise ValueError("duplicate basis reference")
        basis.append({"ref": ref, "kind": kind})
    facts = snapshot.get("facts")
    if not isinstance(facts, dict) or set(facts) - {"window", "status", "confidence"}:
        raise ValueError("unsupported fact projection")
    attention = snapshot.get("attention")
    if not isinstance(attention, dict):
        raise ValueError("attention must be an object")
    tracking, reviews = [], []
    for item in _rows(attention.get("items"), "attention.items"):
        if item.get("id", mission_id) != mission_id:
            raise ValueError("tracking mission mismatch")
        tracking.append({k: deepcopy(item[k]) for k in ("state", "priority", "headline", "next_signal", "why_track", "updated_at") if k in item})
        if item.get("review"):
            if not isinstance(item["review"], dict):
                raise ValueError("review must be object")
            reviews.append({k: deepcopy(item["review"][k]) for k in ("checked_at", "review_after", "summary") if k in item["review"]})
    result = {"schema_version": VERSION, "input_schema_version": snapshot["schema_version"],
              "mission": {k: deepcopy(mission[k]) for k in ("id", "name", "record_available", "aliases")}, "snapshot": {"as_of": as_of, "source_last_updated": snapshot.get("source_last_updated"),
              "external_verification": False, "origin": "local_research_snapshot"},
              "facts": deepcopy(facts), "sources": sources, "claims": claims,
              "evaluations": evaluations, "basis": basis, "tracking": tracking, "reviews": reviews,
              "open_questions": open_questions,
              "limitations": list(_strings(snapshot.get("limitations"), "limitations")) + ["Snapshot import is not a new external verification; review is not source evidence."],
              "accepted": False, "project_truth": False}
    # Finite, JSON-compatible input only; catches unsupported nested values and NaN.
    validate_task(result)
    return result


def research_observation(task: dict) -> dict:
    """Continuity input bound to the supplied snapshot, never fresh acquisition."""
    validate_task(task)
    facts = {}

    def flatten(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or not key or "." in key:
                    raise ValueError("ambiguous fact path")
                flatten(child, f"{path}.{key}" if path else key)
        elif value is None or type(value) in (str, int, float, bool):
            facts[path] = value
        else:
            raise ValueError("fact projection must contain objects and scalars only")

    flatten(task["facts"], "")
    available = bool(facts)
    return {"mission_id": task["mission"]["id"], "source_id": "research-snapshot",
            "observed_at": task["snapshot"]["as_of"],
            "status": "available" if available else "unavailable",
            "raw_sha256": canonical_digest(task) if available else None,
            "facts": facts if available else None,
            "limitations": ["Caller-supplied local research snapshot; not new external verification.",
                            "raw_sha256 binds the adapted snapshot JSON, not fetched source bytes.",
                            "Claims, tracking, and review are excluded from the fact projection."]}


def validate_task(task: dict) -> None:
    """Validate the portable artifact without third-party runtime dependencies."""
    fields = {"schema_version", "input_schema_version", "mission", "snapshot", "facts", "sources", "claims", "evaluations", "basis", "tracking", "reviews", "open_questions", "limitations", "accepted", "project_truth"}
    if not isinstance(task, dict) or set(task) != fields or task.get("schema_version") != VERSION:
        raise ValueError("invalid research task fields/version")
    if task["accepted"] is not False or task["project_truth"] is not False:
        raise ValueError("snapshot cannot confer acceptance")
    meta = task["snapshot"]
    if not isinstance(meta, dict) or set(meta) != {"as_of", "source_last_updated", "external_verification", "origin"} or meta["external_verification"] is not False or meta["origin"] != "local_research_snapshot":
        raise ValueError("invalid snapshot provenance")
    def scalar(value):
        return value is None or type(value) in (str, int, float, bool)
    facts = task["facts"]
    if not isinstance(facts, dict) or set(facts) - {"window", "status", "confidence"}:
        raise ValueError("invalid facts")
    fact_keys = {"status": {"id", "name", "abbrev", "description"},
                 "window": {"net", "start", "end", "window_start", "window_end", "precision", "date", "timezone", "status"}}
    for key, value in facts.items():
        if isinstance(value, dict):
            if key not in fact_keys or set(value) - fact_keys[key] or not all(scalar(v) for v in value.values()):
                raise ValueError("unsupported nested fact fields")
        elif not scalar(value):
            raise ValueError("invalid fact value")
    for layer, allowed in (("tracking", {"state", "priority", "headline", "next_signal", "why_track", "updated_at"}),
                           ("reviews", {"checked_at", "review_after", "summary"})):
        for row in _rows(task[layer], layer):
            if set(row) - allowed or not all(scalar(v) for v in row.values()):
                raise ValueError("invalid decision metadata")
    mission = task["mission"]
    if not isinstance(mission, dict) or set(mission) != {"id", "name", "record_available", "aliases"}:
        raise ValueError("invalid mission fields")
    if task["input_schema_version"] not in ("research-readout-v1", "research-readout-v2"):
        raise ValueError("invalid input version")
    _text(mission["id"], "mission.id"); _text(mission["name"], "mission.name")
    if not re.fullmatch(ID_PATTERN, mission["id"]):
        raise ValueError("invalid mission ID")
    aliases = _strings(mission["aliases"], "aliases")
    if mission["id"] not in aliases or type(mission["record_available"]) is not bool:
        raise ValueError("invalid mission identity")
    if not re.fullmatch(TIME_PATTERN, _text(meta["as_of"], "as_of")):
        raise ValueError("invalid snapshot timestamp")
    parsed = datetime.fromisoformat(meta["as_of"].replace("Z", "+00:00"))
    if parsed.tzinfo is None or (meta["source_last_updated"] is not None and not isinstance(meta["source_last_updated"], str)):
        raise ValueError("invalid snapshot date")
    ids = set(aliases)
    source_ids, claim_ids = set(), set()
    for row in _rows(task["sources"], "sources"):
        if set(row) - {"source_id", "carrier_url", "observed_at", "limitation"}:
            raise ValueError("invalid source fields")
        sid = _text(row.get("source_id"), "source_id")
        if sid in ids: raise ValueError("colliding source identity")
        ids.add(sid); source_ids.add(sid)
        for key, value in row.items(): _text(value, key)
        if "carrier_url" in row: _public_url(row["carrier_url"])
    for row in _rows(task["claims"], "claims"):
        if set(row) - {"claim_id", "evidence_refs", "family", "text", "object", "action", "authority", "limitation"}:
            raise ValueError("invalid claim fields")
        cid = _text(row.get("claim_id"), "claim_id")
        if cid in ids: raise ValueError("colliding claim identity")
        ids.add(cid); claim_ids.add(cid)
        if set(_strings(row.get("evidence_refs"), "evidence_refs")) - source_ids: raise ValueError("missing source")
        for key, value in row.items():
            if key != "evidence_refs": _text(value, key)
    seen = set()
    for row in _rows(task["basis"], "basis"):
        if set(row) != {"ref", "kind"}: raise ValueError("invalid basis fields")
        ref = _text(row["ref"], "ref")
        expected = "claim" if ref in claim_ids else "source" if ref in source_ids else "explicit_identity" if ref in aliases else "unresolved"
        if row["kind"] != expected or ref in seen: raise ValueError("invalid basis")
        seen.add(ref)
    seen = set()
    for row in _rows(task["evaluations"], "evaluations"):
        if set(row) != {"claim_id", "evaluation_state", "accepted"} or row["accepted"] is not False or row["claim_id"] not in claim_ids or row["claim_id"] in seen:
            raise ValueError("invalid evaluation")
        _text(row["evaluation_state"], "evaluation_state"); seen.add(row["claim_id"])
    if seen != claim_ids: raise ValueError("incomplete evaluations")
    for row in _rows(task["open_questions"], "open_questions"):
        if set(row) != {"claim_id", "limitation"} or row["claim_id"] not in claim_ids or not isinstance(row["limitation"], str): raise ValueError("invalid open question")
    _strings(task["limitations"], "limitations")
    canonical_digest(task)
