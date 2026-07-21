from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.ai_discussion_capture_service import CAPTURE_RECORD_TYPE
from app.services.verification_metadata_reader import build_verification_contract_snapshot


SCHEMA_VERSION = 1
GOVERNED_CLAIM_RECORD_TYPE = "ai_discussion_governed_claim"
AUDIT_EVENT_RECORD_TYPE = "governed_claim_audit_event"

CLAIM_POSTURE_DISCUSSION_JUDGMENT = "discussion_judgment"
CLAIM_POSTURE_PENDING_VERIFICATION = "pending_verification_judgment"
CLAIM_POSTURES = frozenset(
    {
        CLAIM_POSTURE_DISCUSSION_JUDGMENT,
        CLAIM_POSTURE_PENDING_VERIFICATION,
    }
)

SUBJECT_TYPES = frozenset(
    {
        "external_source",
        "repo",
        "project",
        "product",
        "concept",
        "ai_radar_design",
        "unknown",
    }
)

SUPPORT_BOUNDARY_DISCUSSION_CONTEXT = "discussion_context"
SUPPORT_BOUNDARIES = frozenset({SUPPORT_BOUNDARY_DISCUSSION_CONTEXT})

BOUNDARY_REVIEW_NOT_REQUIRED = "not_required"
BOUNDARY_REVIEW_PENDING_HUMAN_CHECK = "pending_human_check"
BOUNDARY_REVIEW_CHECKED = "boundary_checked"
BOUNDARY_REVIEW_ISSUE = "boundary_issue"
BOUNDARY_REVIEW_STATUSES = frozenset(
    {
        BOUNDARY_REVIEW_NOT_REQUIRED,
        BOUNDARY_REVIEW_PENDING_HUMAN_CHECK,
        BOUNDARY_REVIEW_CHECKED,
        BOUNDARY_REVIEW_ISSUE,
    }
)

SALIENCE_LABELS = frozenset({"low", "normal", "high"})

AUDIT_ACTION_CREATED = "created"
AUDIT_ACTION_ATTRIBUTE_UPDATED = "attribute_updated"
AUDIT_ACTION_RE_REFERENCE = "re_reference"
AUDIT_ACTIONS = frozenset(
    {
        AUDIT_ACTION_CREATED,
        AUDIT_ACTION_ATTRIBUTE_UPDATED,
        AUDIT_ACTION_RE_REFERENCE,
    }
)

FORBIDDEN_AUDIT_SNAPSHOT_KEYS = frozenset({"evidence_pack", "verification_snapshot"})


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


def _validate_enum(value: str, allowed: frozenset[str], field: str) -> str:
    normalized = _safe_text(value)
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return normalized


def _contains_forbidden_snapshot_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_AUDIT_SNAPSHOT_KEYS:
                return str(key)
            nested = _contains_forbidden_snapshot_key(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _contains_forbidden_snapshot_key(child)
            if nested:
                return nested
    return None


def _validate_audit_snapshot(value: Any, field: str) -> dict[str, Any]:
    snapshot = _json_object_snapshot(value)
    forbidden = _contains_forbidden_snapshot_key(snapshot)
    if forbidden:
        raise ValueError(f"{field} must not embed {forbidden}.")
    return snapshot


def _audit_ref(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_family": AUDIT_EVENT_RECORD_TYPE,
        "record_id": _safe_text(event.get("id")),
        "action": _safe_text(event.get("action")),
        "recorded_at": _safe_text(event.get("recorded_at")),
    }


def build_governed_claim_audit_event(
    *,
    governed_claim_id: str,
    action: str,
    actor: dict[str, Any] | None = None,
    changed_fields: list[str] | None = None,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    source_ref: dict[str, Any] | None = None,
    note: str = "",
    recorded_at: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    normalized_claim_id = _safe_text(governed_claim_id)
    _require(bool(normalized_claim_id), "governed_claim_id is required.")
    normalized_action = _validate_enum(action, AUDIT_ACTIONS, "action")
    recorded = _safe_text(recorded_at) or _utc_now_iso()

    return {
        "id": _safe_text(event_id) or f"gca_{uuid.uuid4().hex[:12]}",
        "schema_version": SCHEMA_VERSION,
        "record_type": AUDIT_EVENT_RECORD_TYPE,
        "governed_claim_id": normalized_claim_id,
        "action": normalized_action,
        "actor": _json_object_snapshot(actor or {"type": "human", "id": ""}),
        "recorded_at": recorded,
        "changed_fields": [_safe_text(item) for item in (changed_fields or []) if _safe_text(item)],
        "before_snapshot": _validate_audit_snapshot(before_snapshot or {}, "before_snapshot"),
        "after_snapshot": _validate_audit_snapshot(after_snapshot or {}, "after_snapshot"),
        "source_ref": _json_object_snapshot(source_ref or {"record_family": CAPTURE_RECORD_TYPE, "record_id": ""}),
        "note": _safe_text(note),
    }


def build_verification_ref(
    *,
    verification: dict[str, Any],
    verified_insight_id: str = "",
    signal_id: str = "",
    content_fingerprint: str = "",
    claim_id: str = "",
    as_of: str | None = None,
    ref_type: str = "verified_insight",
) -> dict[str, Any]:
    normalized_as_of = _safe_text(as_of) or _utc_now_iso()
    _require(isinstance(verification, dict) and bool(verification), "verification is required.")

    return {
        "ref_type": _safe_text(ref_type) or "verified_insight",
        "verified_insight_id": _safe_text(verified_insight_id),
        "signal_id": _safe_text(signal_id),
        "content_fingerprint": _safe_text(content_fingerprint),
        "claim_id": _safe_text(claim_id),
        "as_of": normalized_as_of,
        "verification_snapshot": build_verification_contract_snapshot(verification),
    }


def _validate_verification_ref(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    ref = _json_object_snapshot(value)
    _require(bool(ref), "verification_ref must be an object when present.")
    _require(bool(_safe_text(ref.get("as_of"))), "verification_ref.as_of is required.")
    _require(isinstance(ref.get("verification_snapshot"), dict), "verification_ref.verification_snapshot is required.")
    _require("evidence_pack" not in ref, "verification_ref must not include evidence_pack contents.")
    _require(
        "verification_status" in ref["verification_snapshot"],
        "verification_ref.verification_snapshot.verification_status is required.",
    )
    _require(
        "blocked_downstream_actions" in ref["verification_snapshot"],
        "verification_ref.verification_snapshot.blocked_downstream_actions is required.",
    )
    return ref


def _validate_claim_snapshot(value: Any, *, verification_ref: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        _require(verification_ref is None, "claim_snapshot is required when verification_ref is present.")
        return None
    snapshot = _json_object_snapshot(value)
    if verification_ref is not None:
        _require(bool(snapshot), "claim_snapshot is required when verification_ref is present.")
    return snapshot


def _validate_asserted_subject(value: Any) -> dict[str, Any]:
    subject = _json_object_snapshot(value)
    _require(bool(subject), "asserted_subject is required.")
    subject_type = _validate_enum(_safe_text(subject.get("subject_type")), SUBJECT_TYPES, "asserted_subject.subject_type")
    subject["subject_type"] = subject_type
    return subject


def _validate_boundary_review(value: Any, *, subject_type: str) -> dict[str, Any]:
    review = _json_object_snapshot(value)
    _require(bool(review), "boundary_review is required.")
    status = _validate_enum(_safe_text(review.get("status")), BOUNDARY_REVIEW_STATUSES, "boundary_review.status")
    if subject_type == "external_source":
        _require(
            status != BOUNDARY_REVIEW_NOT_REQUIRED,
            "external_source governed claims must not use boundary_review.status=not_required.",
        )
    review["status"] = status
    return review


def _validate_salience(value: Any) -> dict[str, Any]:
    salience = _json_object_snapshot(value or {"label": "normal", "score": None, "reason": []})
    label = _validate_enum(_safe_text(salience.get("label") or "normal"), SALIENCE_LABELS, "salience.label")
    salience["label"] = label
    reason = salience.get("reason")
    salience["reason"] = [_safe_text(item) for item in reason] if isinstance(reason, list) else []
    return salience


def _has_created_audit_ref(audit_refs: list[Any]) -> bool:
    for item in audit_refs:
        if not isinstance(item, dict):
            continue
        if _safe_text(item.get("record_family")) == AUDIT_EVENT_RECORD_TYPE and _safe_text(item.get("action")) == AUDIT_ACTION_CREATED:
            return True
    return False


def validate_governed_claim_record(record: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(record, dict), "record must be a JSON object.")
    payload = _json_object_snapshot(record)

    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.")
    _require(payload.get("record_type") == GOVERNED_CLAIM_RECORD_TYPE, f"record_type must be {GOVERNED_CLAIM_RECORD_TYPE}.")
    _require(bool(_safe_text(payload.get("id"))), "id is required.")
    _require(bool(_safe_text(payload.get("claim_text"))), "claim_text is required.")

    payload["claim_posture"] = _validate_enum(_safe_text(payload.get("claim_posture")), CLAIM_POSTURES, "claim_posture")
    payload["support_boundary"] = _validate_enum(
        _safe_text(payload.get("support_boundary")),
        SUPPORT_BOUNDARIES,
        "support_boundary",
    )
    payload["discussion_ref"] = _json_object_snapshot(payload.get("discussion_ref"))
    _require(bool(payload["discussion_ref"]), "discussion_ref is required.")
    _require(
        _safe_text(payload["discussion_ref"].get("record_family")) == CAPTURE_RECORD_TYPE,
        f"discussion_ref.record_family must be {CAPTURE_RECORD_TYPE}.",
    )
    _require(bool(_safe_text(payload["discussion_ref"].get("record_id"))), "discussion_ref.record_id is required.")
    _require(bool(_safe_text(payload["discussion_ref"].get("captured_at"))), "discussion_ref.captured_at is required.")

    asserted_subject = _validate_asserted_subject(payload.get("asserted_subject"))
    payload["asserted_subject"] = asserted_subject
    payload["boundary_review"] = _validate_boundary_review(
        payload.get("boundary_review"),
        subject_type=asserted_subject["subject_type"],
    )

    verification_ref = _validate_verification_ref(payload.get("verification_ref"))
    payload["verification_ref"] = verification_ref
    payload["claim_snapshot"] = _validate_claim_snapshot(payload.get("claim_snapshot"), verification_ref=verification_ref)
    payload["salience"] = _validate_salience(payload.get("salience"))

    audit_refs = _json_list_snapshot(payload.get("audit_refs"))
    _require(_has_created_audit_ref(audit_refs), "governed claims must include a created audit ref.")
    payload["audit_refs"] = audit_refs

    return payload


def build_governed_claim_record(
    *,
    claim_text: str,
    asserted_subject: dict[str, Any],
    discussion_ref: dict[str, Any],
    claim_posture: str = CLAIM_POSTURE_DISCUSSION_JUDGMENT,
    boundary_review: dict[str, Any] | None = None,
    verification_ref: dict[str, Any] | None = None,
    claim_snapshot: dict[str, Any] | None = None,
    salience: dict[str, Any] | None = None,
    created_by: str = "human_or_agent",
    created_at: str | None = None,
    record_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    created = _safe_text(created_at) or _utc_now_iso()
    governed_claim_id = _safe_text(record_id) or f"gc_{uuid.uuid4().hex[:12]}"
    subject_type = _safe_text(asserted_subject.get("subject_type") if isinstance(asserted_subject, dict) else "")
    review = boundary_review
    if review is None:
        review = {
            "status": (
                BOUNDARY_REVIEW_PENDING_HUMAN_CHECK
                if subject_type == "external_source"
                else BOUNDARY_REVIEW_NOT_REQUIRED
            ),
            "reviewed_by": "",
            "reviewed_at": "",
            "note": "",
        }

    audit_event = build_governed_claim_audit_event(
        governed_claim_id=governed_claim_id,
        action=AUDIT_ACTION_CREATED,
        actor={"type": _safe_text(created_by) or "human_or_agent", "id": ""},
        changed_fields=["record"],
        before_snapshot={},
        after_snapshot={"id": governed_claim_id, "record_type": GOVERNED_CLAIM_RECORD_TYPE},
        source_ref=discussion_ref,
        recorded_at=created,
    )

    payload = {
        "id": governed_claim_id,
        "schema_version": SCHEMA_VERSION,
        "record_type": GOVERNED_CLAIM_RECORD_TYPE,
        "discussion_ref": _json_object_snapshot(discussion_ref),
        "claim_text": _safe_text(claim_text),
        "claim_posture": _safe_text(claim_posture),
        "asserted_subject": _json_object_snapshot(asserted_subject),
        "support_boundary": SUPPORT_BOUNDARY_DISCUSSION_CONTEXT,
        "boundary_review": _json_object_snapshot(review),
        "verification_ref": _json_object_snapshot(verification_ref) if verification_ref is not None else None,
        "claim_snapshot": _json_object_snapshot(claim_snapshot) if claim_snapshot is not None else None,
        "salience": _json_object_snapshot(salience or {"label": "normal", "score": None, "reason": []}),
        "audit_refs": [_audit_ref(audit_event)],
        "created_by": _safe_text(created_by) or "human_or_agent",
        "created_at": created,
        "updated_at": created,
    }

    return validate_governed_claim_record(payload), audit_event
