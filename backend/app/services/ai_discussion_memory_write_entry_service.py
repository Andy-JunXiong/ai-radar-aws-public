from __future__ import annotations

import json
from typing import Any

from app.services import ai_discussion_capture_service as capture_service
from app.services import ai_discussion_memory_store_service as store_service
from app.services import governed_claim_service


CALLER_EXPLICIT_SELECTION = "explicit_human_or_agent_selection"
ADMITTED_CALLER_TYPES = frozenset({CALLER_EXPLICIT_SELECTION})
REJECTED_CALLER_TYPES = frozenset(
    {
        "automatic_transcript_capture",
        "reflection_import",
        "workspace_chat_import",
        "manual_upload_import",
        "signal_import",
        "external_memory_import",
        "project_takeaway_action",
    }
)

REJECTED_SOURCE_TYPES = frozenset(
    {
        "reflection",
        "reflection_import",
        "workspace_chat",
        "workspace_chat_import",
        "manual_upload",
        "manual_upload_import",
        "signal",
        "signal_import",
        "codex_session",
        "claude_session",
        "chatgpt_session",
    }
)

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "evidence_pack",
        "raw_private_payload",
        "private_payload",
        "full_transcript_text",
        "external_evidence_blob",
    }
)


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
    return json.loads(json.dumps(value, ensure_ascii=False))


def _json_list_snapshot(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return json.loads(json.dumps(value, ensure_ascii=False))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _contains_forbidden_request_content(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = _safe_text(key)
            if key_text in FORBIDDEN_REQUEST_KEYS:
                return key_text
            if key_text == "full_transcript" and child is True:
                return key_text
            nested = _contains_forbidden_request_content(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _contains_forbidden_request_content(child)
            if nested:
                return nested
    return None


def _actor_from_request(request: dict[str, Any]) -> dict[str, Any]:
    caller = _json_object_snapshot(request.get("caller"))
    actor = _json_object_snapshot(caller.get("actor"))
    return actor or {"type": "human_or_agent", "id": ""}


def _validate_caller(request: dict[str, Any]) -> None:
    caller = _json_object_snapshot(request.get("caller"))
    caller_type = _safe_text(caller.get("caller_type"))
    _require(caller_type not in REJECTED_CALLER_TYPES, f"caller_type {caller_type} is not admitted.")
    _require(caller_type in ADMITTED_CALLER_TYPES, "caller.caller_type must be explicit_human_or_agent_selection.")


def _existing_batch_and_capture(fingerprint: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    normalized = _safe_text(fingerprint)
    if not normalized:
        return None
    for batch in store_service.list_committed_write_batches():
        for capture in batch.get("captures", []):
            if _safe_text(capture.get("discussion_fingerprint")) == normalized:
                return batch, capture
    return None


def _governed_claim_ids(batch: dict[str, Any]) -> list[str]:
    return [_safe_text(claim.get("id")) for claim in batch.get("governed_claims", []) if _safe_text(claim.get("id"))]


def _audit_event_ids(batch: dict[str, Any]) -> list[str]:
    return [_safe_text(event.get("id")) for event in batch.get("audit_events", []) if _safe_text(event.get("id"))]


def _response_from_batch(batch: dict[str, Any], *, capture_reused: bool, claims_created: bool) -> dict[str, Any]:
    capture = batch.get("captures", [{}])[0] if isinstance(batch.get("captures"), list) and batch.get("captures") else {}
    return {
        "status": _safe_text(batch.get("status")),
        "write_batch_id": _safe_text(batch.get("id")),
        "capture_id": _safe_text(capture.get("id")),
        "governed_claim_ids": _governed_claim_ids(batch),
        "audit_event_ids": _audit_event_ids(batch),
        "capture_reused": bool(capture_reused),
        "claims_created": bool(claims_created),
    }


def _build_capture(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capture_request = _json_object_snapshot(request.get("capture"))
    source = _json_object_snapshot(capture_request.get("source"))
    source_type = _safe_text(source.get("source_type"))
    _require(source_type not in REJECTED_SOURCE_TYPES, f"capture.source.source_type {source_type} is not admitted.")
    _require(
        source_type == capture_service.SOURCE_TYPE_AI_DISCUSSION_SESSION,
        "capture.source.source_type must be ai_discussion_session.",
    )
    fingerprint = _safe_text(capture_request.get("discussion_fingerprint"))
    _require(bool(fingerprint), "capture.discussion_fingerprint is required.")

    return capture_service.build_ai_discussion_capture_record(
        message_refs=_json_list_snapshot(capture_request.get("message_refs")),
        discussion_excerpt=_safe_text(capture_request.get("discussion_excerpt")),
        source=source,
        captured_by=_safe_text(_actor_from_request(request).get("type")) or "human_or_agent",
        selection_reason=_safe_text(capture_request.get("selection_reason")),
        discussion_fingerprint=fingerprint,
    )


def _validate_governed_claim_request(claim_request: dict[str, Any]) -> dict[str, Any]:
    claim = _json_object_snapshot(claim_request)
    _require("discussion_ref" not in claim, "governed_claims[*].discussion_ref must not be supplied by callers.")
    support_boundary = _safe_text(claim.get("support_boundary"))
    if support_boundary:
        _require(
            support_boundary == governed_claim_service.SUPPORT_BOUNDARY_DISCUSSION_CONTEXT,
            "governed claims must keep support_boundary=discussion_context.",
        )
    subject = _json_object_snapshot(claim.get("asserted_subject"))
    subject_type = _safe_text(subject.get("subject_type"))
    if subject_type == "external_source":
        posture = _safe_text(claim.get("claim_posture")) or governed_claim_service.CLAIM_POSTURE_DISCUSSION_JUDGMENT
        _require(
            posture
            in {
                governed_claim_service.CLAIM_POSTURE_DISCUSSION_JUDGMENT,
                governed_claim_service.CLAIM_POSTURE_PENDING_VERIFICATION,
            },
            "external_source governed claims must use discussion or pending-verification posture.",
        )
        boundary_review = _json_object_snapshot(claim.get("boundary_review"))
        if boundary_review:
            _require(
                _safe_text(boundary_review.get("status")) != governed_claim_service.BOUNDARY_REVIEW_NOT_REQUIRED,
                "external_source governed claims must not use boundary_review.status=not_required.",
            )
    salience = _json_object_snapshot(claim.get("salience"))
    _require("allowed_downstream_actions" not in salience, "salience must not set allowed_downstream_actions.")
    _require("blocked_downstream_actions" not in salience, "salience must not set blocked_downstream_actions.")
    return claim


def _build_governed_claims(
    *,
    request: dict[str, Any],
    capture: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    audit_events: list[dict[str, Any]] = []
    for claim_request in _json_list_snapshot(request.get("governed_claims")):
        claim = _validate_governed_claim_request(claim_request)
        record, audit_event = governed_claim_service.build_governed_claim_record(
            claim_text=_safe_text(claim.get("claim_text")),
            asserted_subject=_json_object_snapshot(claim.get("asserted_subject")),
            discussion_ref={
                "record_family": capture_service.CAPTURE_RECORD_TYPE,
                "record_id": _safe_text(capture.get("id")),
                "message_ids": [
                    _safe_text(item.get("message_id"))
                    for item in _json_list_snapshot(capture.get("message_refs"))
                    if isinstance(item, dict) and _safe_text(item.get("message_id"))
                ],
                "captured_at": _safe_text(capture.get("captured_at")),
            },
            claim_posture=_safe_text(claim.get("claim_posture"))
            or governed_claim_service.CLAIM_POSTURE_DISCUSSION_JUDGMENT,
            boundary_review=claim.get("boundary_review") if isinstance(claim.get("boundary_review"), dict) else None,
            verification_ref=claim.get("verification_ref") if isinstance(claim.get("verification_ref"), dict) else None,
            claim_snapshot=claim.get("claim_snapshot") if isinstance(claim.get("claim_snapshot"), dict) else None,
            salience=claim.get("salience") if isinstance(claim.get("salience"), dict) else None,
            created_by=_safe_text(_actor_from_request(request).get("type")) or "human_or_agent",
        )
        records.append(record)
        audit_events.append(audit_event)
    return records, audit_events


def create_ai_discussion_memory_from_selection(request: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(request, dict), "request must be a JSON object.")
    payload = _json_object_snapshot(request)
    forbidden = _contains_forbidden_request_content(payload)
    if forbidden:
        raise ValueError(f"request must not include {forbidden}.")
    _validate_caller(payload)
    capture_request = _json_object_snapshot(payload.get("capture"))
    fingerprint = _safe_text(capture_request.get("discussion_fingerprint"))
    _require(bool(fingerprint), "capture.discussion_fingerprint is required.")
    capture, capture_audit = _build_capture(payload)
    governed_claims, governed_claim_audits = _build_governed_claims(request=payload, capture=capture)
    existing = _existing_batch_and_capture(fingerprint)
    if existing:
        existing_batch, _capture = existing
        return _response_from_batch(existing_batch, capture_reused=True, claims_created=False)

    batch = store_service.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=governed_claims,
        governed_claim_audit_events=governed_claim_audits,
        actor=_actor_from_request(payload),
    )
    return _response_from_batch(batch, capture_reused=False, claims_created=bool(governed_claims))
