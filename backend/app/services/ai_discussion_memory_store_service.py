from __future__ import annotations

import copy
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import ai_discussion_capture_service as capture_service
from app.services import governed_claim_service


SCHEMA_VERSION = 1
WRITE_BATCH_RECORD_TYPE = "ai_discussion_memory_write_batch"
INDEX_RECORD_TYPE = "ai_discussion_memory_index"
WRITE_BATCH_STATUS_COMMITTED = "committed"
OPERATION_CREATE_CAPTURE_WITH_GOVERNED_CLAIMS = "create_capture_with_governed_claims"
SURFACE_AI_DISCUSSION = "ai_discussion"

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "ai_discussion_memory"

FORBIDDEN_BATCH_KEYS = frozenset(
    {
        "evidence_pack",
        "raw_private_payload",
        "private_payload",
        "full_transcript_text",
        "external_evidence_blob",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _json_object_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return copy.deepcopy(json.loads(json.dumps(value, ensure_ascii=False)))


def _json_list_snapshot(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return copy.deepcopy(json.loads(json.dumps(value, ensure_ascii=False)))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _safe_file_stem(value: str) -> str:
    safe = _safe_text(value).replace("/", "_").replace("\\", "_")
    return safe or f"missing_{uuid.uuid4().hex[:12]}"


def _write_batches_dir() -> Path:
    return DATA_DIR / "write_batches"


def _captures_dir() -> Path:
    return DATA_DIR / "captures"


def _governed_claims_dir() -> Path:
    return DATA_DIR / "governed_claims"


def _audit_events_dir() -> Path:
    return DATA_DIR / "audit_events"


def _index_path() -> Path:
    return DATA_DIR / "index.json"


def _batch_path(batch_id: str) -> Path:
    return _write_batches_dir() / f"{_safe_file_stem(batch_id)}.json"


def _capture_path(capture_id: str) -> Path:
    return _captures_dir() / f"{_safe_file_stem(capture_id)}.json"


def _governed_claim_path(governed_claim_id: str) -> Path:
    return _governed_claims_dir() / f"{_safe_file_stem(governed_claim_id)}.json"


def _audit_event_path(event_id: str) -> Path:
    return _audit_events_dir() / f"{_safe_file_stem(event_id)}.json"


def _ensure_data_dirs() -> None:
    for path in (_write_batches_dir(), _captures_dir(), _governed_claims_dir(), _audit_events_dir()):
        path.mkdir(parents=True, exist_ok=True)


def _write_json_file_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _contains_forbidden_batch_content(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = _safe_text(key)
            if key_text in FORBIDDEN_BATCH_KEYS:
                return key_text
            if key_text == "full_transcript" and child is True:
                return key_text
            if key_text == "automatic_import" and child is True:
                return key_text
            nested = _contains_forbidden_batch_content(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _contains_forbidden_batch_content(child)
            if nested:
                return nested
    return None


def _event_key(event: dict[str, Any]) -> tuple[str, str]:
    return (_safe_text(event.get("record_type")), _safe_text(event.get("id")))


def _audit_ref_key(ref: dict[str, Any]) -> tuple[str, str]:
    return (_safe_text(ref.get("record_family")), _safe_text(ref.get("record_id")))


def _created_audit_ref(record: dict[str, Any], *, family: str) -> tuple[str, str] | None:
    for item in _json_list_snapshot(record.get("audit_refs")):
        if not isinstance(item, dict):
            continue
        if _safe_text(item.get("record_family")) == family and _safe_text(item.get("action")) == "created":
            return _audit_ref_key(item)
    return None


def _validate_capture_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    return capture_service.validate_ai_discussion_capture_audit_event(event)


def _validate_governed_claim_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object_snapshot(event)
    _require(payload.get("schema_version") == SCHEMA_VERSION, "governed audit schema_version must be 1.")
    _require(
        payload.get("record_type") == governed_claim_service.AUDIT_EVENT_RECORD_TYPE,
        f"governed audit record_type must be {governed_claim_service.AUDIT_EVENT_RECORD_TYPE}.",
    )
    _require(bool(_safe_text(payload.get("id"))), "governed audit id is required.")
    _require(bool(_safe_text(payload.get("governed_claim_id"))), "governed audit governed_claim_id is required.")
    _require(_safe_text(payload.get("action")) == governed_claim_service.AUDIT_ACTION_CREATED, "v1 governed audit action must be created.")
    _require(bool(_safe_text(payload.get("recorded_at"))), "governed audit recorded_at is required.")
    return payload


def _validate_audit_events(events: list[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for event in events:
        payload = _json_object_snapshot(event)
        record_type = _safe_text(payload.get("record_type"))
        if record_type == capture_service.CAPTURE_AUDIT_EVENT_RECORD_TYPE:
            validated.append(_validate_capture_audit_event(payload))
        elif record_type == governed_claim_service.AUDIT_EVENT_RECORD_TYPE:
            validated.append(_validate_governed_claim_audit_event(payload))
        else:
            raise ValueError(f"unsupported audit event record_type: {record_type}")
    return validated


def list_committed_write_batches() -> list[dict[str, Any]]:
    _ensure_data_dirs()
    batches: list[dict[str, Any]] = []
    for path in sorted(_write_batches_dir().glob("*.json")):
        payload = _read_json_object(path)
        if not payload:
            continue
        try:
            batches.append(validate_memory_write_batch(payload))
        except ValueError:
            continue
    return sorted(batches, key=lambda item: _safe_text(item.get("created_at")))


def _existing_capture_ids_from_batches() -> set[str]:
    capture_ids: set[str] = set()
    for batch in list_committed_write_batches():
        for capture in batch.get("captures", []):
            capture_ids.add(_safe_text(capture.get("id")))
    return {item for item in capture_ids if item}


def _find_committed_capture_by_fingerprint(fingerprint: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    normalized = _safe_text(fingerprint)
    if not normalized:
        return None
    for batch in list_committed_write_batches():
        for capture in batch.get("captures", []):
            if _safe_text(capture.get("discussion_fingerprint")) == normalized:
                return batch, capture
    return None


def _governed_claim_ids_for_capture(capture_id: str) -> set[str]:
    result: set[str] = set()
    for batch in list_committed_write_batches():
        for claim in batch.get("governed_claims", []):
            discussion_ref = claim.get("discussion_ref") if isinstance(claim.get("discussion_ref"), dict) else {}
            if _safe_text(discussion_ref.get("record_id")) == _safe_text(capture_id):
                result.add(_safe_text(claim.get("id")))
    return {item for item in result if item}


def _intended_materialized_paths(batch: dict[str, Any]) -> list[str]:
    paths: list[str] = [str(_batch_path(str(batch.get("id"))).relative_to(DATA_DIR))]
    for capture in batch.get("captures", []):
        paths.append(str(_capture_path(str(capture.get("id"))).relative_to(DATA_DIR)))
    for claim in batch.get("governed_claims", []):
        paths.append(str(_governed_claim_path(str(claim.get("id"))).relative_to(DATA_DIR)))
    for event in batch.get("audit_events", []):
        paths.append(str(_audit_event_path(str(event.get("id"))).relative_to(DATA_DIR)))
    paths.append(str(_index_path().relative_to(DATA_DIR)))
    return paths


def build_memory_write_batch(
    *,
    capture: dict[str, Any],
    governed_claims: list[dict[str, Any]] | None = None,
    audit_events: list[dict[str, Any]] | None = None,
    actor: dict[str, Any] | None = None,
    created_at: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    created = _safe_text(created_at) or _utc_now_iso()
    batch = {
        "id": _safe_text(batch_id) or f"aimb_{uuid.uuid4().hex[:12]}",
        "schema_version": SCHEMA_VERSION,
        "record_type": WRITE_BATCH_RECORD_TYPE,
        "status": WRITE_BATCH_STATUS_COMMITTED,
        "actor": _json_object_snapshot(actor or {"type": "human_or_agent", "id": ""}),
        "created_at": created,
        "source": {
            "operation": OPERATION_CREATE_CAPTURE_WITH_GOVERNED_CLAIMS,
            "surface": SURFACE_AI_DISCUSSION,
        },
        "audit_events": _json_list_snapshot(audit_events or []),
        "captures": [_json_object_snapshot(capture)],
        "governed_claims": _json_list_snapshot(governed_claims or []),
        "materialized_paths": [],
    }
    batch["materialized_paths"] = _intended_materialized_paths(batch)
    return validate_memory_write_batch(batch)


def validate_memory_write_batch(
    batch: dict[str, Any],
    *,
    existing_capture_ids: set[str] | None = None,
) -> dict[str, Any]:
    _require(isinstance(batch, dict), "batch must be a JSON object.")
    payload = _json_object_snapshot(batch)
    forbidden = _contains_forbidden_batch_content(payload)
    if forbidden:
        raise ValueError(f"write batch must not include {forbidden}.")

    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.")
    _require(payload.get("record_type") == WRITE_BATCH_RECORD_TYPE, f"record_type must be {WRITE_BATCH_RECORD_TYPE}.")
    _require(payload.get("status") == WRITE_BATCH_STATUS_COMMITTED, "status must be committed.")
    _require(bool(_safe_text(payload.get("id"))), "id is required.")
    _require(bool(_safe_text(payload.get("created_at"))), "created_at is required.")
    source = _json_object_snapshot(payload.get("source"))
    _require(source.get("operation") == OPERATION_CREATE_CAPTURE_WITH_GOVERNED_CLAIMS, "unsupported write operation.")
    _require(source.get("surface") == SURFACE_AI_DISCUSSION, "write surface must be ai_discussion.")
    payload["source"] = source

    captures = [capture_service.validate_ai_discussion_capture_record(item) for item in _json_list_snapshot(payload.get("captures"))]
    _require(len(captures) == 1, "v1 write batches require exactly one capture.")
    payload["captures"] = captures
    capture_ids = {_safe_text(item.get("id")) for item in captures}

    audit_events = _validate_audit_events(_json_list_snapshot(payload.get("audit_events")))
    payload["audit_events"] = audit_events
    audit_event_keys = {_event_key(event) for event in audit_events}

    for capture in captures:
        created_ref = _created_audit_ref(capture, family=capture_service.CAPTURE_AUDIT_EVENT_RECORD_TYPE)
        _require(created_ref is not None and created_ref in audit_event_keys, "capture records require matching creation audit events.")

    existing_capture_ids = existing_capture_ids or set()
    governed_claims = [governed_claim_service.validate_governed_claim_record(item) for item in _json_list_snapshot(payload.get("governed_claims"))]
    for claim in governed_claims:
        discussion_ref = claim.get("discussion_ref") if isinstance(claim.get("discussion_ref"), dict) else {}
        ref_family = _safe_text(discussion_ref.get("record_family"))
        ref_id = _safe_text(discussion_ref.get("record_id"))
        _require(ref_family == capture_service.CAPTURE_RECORD_TYPE, "governed claims must reference ai_discussion_capture.")
        _require(
            ref_id in capture_ids or ref_id in existing_capture_ids,
            "governed claims must reference a capture in the batch or committed ledger.",
        )
        created_ref = _created_audit_ref(claim, family=governed_claim_service.AUDIT_EVENT_RECORD_TYPE)
        _require(created_ref is not None and created_ref in audit_event_keys, "governed claims require matching creation audit events.")
    payload["governed_claims"] = governed_claims
    payload["actor"] = _json_object_snapshot(payload.get("actor"))
    payload["materialized_paths"] = [_safe_text(path) for path in _json_list_snapshot(payload.get("materialized_paths")) if _safe_text(path)]
    return payload


def commit_memory_write_batch(batch: dict[str, Any], *, materialize: bool = True) -> dict[str, Any]:
    _ensure_data_dirs()
    payload = validate_memory_write_batch(batch, existing_capture_ids=_existing_capture_ids_from_batches())
    capture = payload["captures"][0]
    duplicate = _find_committed_capture_by_fingerprint(str(capture.get("discussion_fingerprint")))
    if duplicate:
        existing_batch, existing_capture = duplicate
        incoming_claim_ids = {_safe_text(claim.get("id")) for claim in payload.get("governed_claims", []) if _safe_text(claim.get("id"))}
        existing_claim_ids = _governed_claim_ids_for_capture(str(existing_capture.get("id")))
        if incoming_claim_ids.issubset(existing_claim_ids):
            return existing_batch
        raise ValueError("duplicate discussion_fingerprint cannot create a second authoritative capture.")

    _write_json_file_atomic(_batch_path(str(payload["id"])), payload)
    if materialize:
        _materialize_batch(payload)
    return payload


def create_capture_with_governed_claims(
    *,
    capture: dict[str, Any],
    capture_audit_event: dict[str, Any],
    governed_claims: list[dict[str, Any]] | None = None,
    governed_claim_audit_events: list[dict[str, Any]] | None = None,
    actor: dict[str, Any] | None = None,
    created_at: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    batch = build_memory_write_batch(
        capture=capture,
        governed_claims=governed_claims or [],
        audit_events=[capture_audit_event, *(governed_claim_audit_events or [])],
        actor=actor,
        created_at=created_at,
        batch_id=batch_id,
    )
    return commit_memory_write_batch(batch)


def _materialize_batch(batch: dict[str, Any]) -> None:
    for capture in batch.get("captures", []):
        _write_json_file_atomic(_capture_path(str(capture.get("id"))), capture)
    for claim in batch.get("governed_claims", []):
        _write_json_file_atomic(_governed_claim_path(str(claim.get("id"))), claim)
    for event in batch.get("audit_events", []):
        _write_json_file_atomic(_audit_event_path(str(event.get("id"))), event)
    rebuild_memory_index()


def materialize_committed_write_batches() -> dict[str, Any]:
    for batch in list_committed_write_batches():
        _materialize_batch(batch)
    return rebuild_memory_index()


def _verification_status_from_claim(claim: dict[str, Any]) -> str:
    verification_ref = claim.get("verification_ref") if isinstance(claim.get("verification_ref"), dict) else {}
    snapshot = verification_ref.get("verification_snapshot") if isinstance(verification_ref.get("verification_snapshot"), dict) else {}
    return _safe_text(snapshot.get("verification_status"))


def build_memory_index_from_batches(batches: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    committed = batches if batches is not None else list_committed_write_batches()
    captures: dict[str, dict[str, Any]] = {}
    claims: dict[str, dict[str, Any]] = {}
    batch_entries: dict[str, dict[str, Any]] = {}

    for batch in committed:
        batch_entries[_safe_text(batch.get("id"))] = {
            "id": _safe_text(batch.get("id")),
            "record_type": _safe_text(batch.get("record_type")),
            "status": _safe_text(batch.get("status")),
            "created_at": _safe_text(batch.get("created_at")),
            "operation": _safe_text((batch.get("source") or {}).get("operation") if isinstance(batch.get("source"), dict) else ""),
        }
        for capture in batch.get("captures", []):
            captures[_safe_text(capture.get("id"))] = {
                "id": _safe_text(capture.get("id")),
                "record_type": _safe_text(capture.get("record_type")),
                "created_at": _safe_text(capture.get("created_at")),
                "updated_at": _safe_text(capture.get("updated_at")),
                "source_type": _safe_text((capture.get("source") or {}).get("source_type") if isinstance(capture.get("source"), dict) else ""),
                "discussion_fingerprint": _safe_text(capture.get("discussion_fingerprint")),
            }
        for claim in batch.get("governed_claims", []):
            subject = claim.get("asserted_subject") if isinstance(claim.get("asserted_subject"), dict) else {}
            discussion_ref = claim.get("discussion_ref") if isinstance(claim.get("discussion_ref"), dict) else {}
            boundary_review = claim.get("boundary_review") if isinstance(claim.get("boundary_review"), dict) else {}
            salience = claim.get("salience") if isinstance(claim.get("salience"), dict) else {}
            claims[_safe_text(claim.get("id"))] = {
                "id": _safe_text(claim.get("id")),
                "record_type": _safe_text(claim.get("record_type")),
                "created_at": _safe_text(claim.get("created_at")),
                "updated_at": _safe_text(claim.get("updated_at")),
                "capture_id": _safe_text(discussion_ref.get("record_id")),
                "claim_posture": _safe_text(claim.get("claim_posture")),
                "subject_type": _safe_text(subject.get("subject_type")),
                "subject_label": _safe_text(subject.get("label")),
                "boundary_review_status": _safe_text(boundary_review.get("status")),
                "salience_label": _safe_text(salience.get("label")),
                "verification_status": _verification_status_from_claim(claim),
            }

    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": INDEX_RECORD_TYPE,
        "updated_at": _utc_now_iso(),
        "captures": sorted(captures.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True),
        "governed_claims": sorted(claims.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True),
        "write_batches": sorted(batch_entries.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True),
    }


def rebuild_memory_index() -> dict[str, Any]:
    index = build_memory_index_from_batches()
    _write_json_file_atomic(_index_path(), index)
    return index


def load_memory_index() -> dict[str, Any]:
    payload = _read_json_object(_index_path())
    if payload:
        return payload
    return rebuild_memory_index()
