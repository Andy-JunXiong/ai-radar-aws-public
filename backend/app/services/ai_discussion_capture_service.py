from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 1
CAPTURE_RECORD_TYPE = "ai_discussion_capture"
CAPTURE_AUDIT_EVENT_RECORD_TYPE = "ai_discussion_capture_audit_event"

CAPTURE_MODE_SELECTED_EXCERPT = "selected_excerpt"
CAPTURE_MODES = frozenset({CAPTURE_MODE_SELECTED_EXCERPT})

SOURCE_TYPE_AI_DISCUSSION_SESSION = "ai_discussion_session"
SOURCE_TYPES = frozenset({SOURCE_TYPE_AI_DISCUSSION_SESSION})

AUDIT_ACTION_CREATED = "created"
AUDIT_ACTION_METADATA_UPDATED = "metadata_updated"
AUDIT_ACTIONS = frozenset({AUDIT_ACTION_CREATED, AUDIT_ACTION_METADATA_UPDATED})

MAX_MESSAGE_EXCERPT_CHARS = 1200
MAX_DISCUSSION_EXCERPT_CHARS = 4000

BOUNDARY_EVIDENCE_BOUNDARY = "discussion_context_not_external_evidence"
REQUIRED_BOUNDARY = {
    "evidence_boundary": BOUNDARY_EVIDENCE_BOUNDARY,
    "external_fact_evidence": False,
    "full_transcript": False,
    "automatic_import": False,
}

FORBIDDEN_SOURCE_TYPES = frozenset(
    {
        "codex_session",
        "claude_session",
        "chatgpt_session",
        "manual_note",
        "other_ai_discussion",
    }
)

SECRET_LIKE_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
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


def _validate_enum(value: str, allowed: frozenset[str], field: str) -> str:
    normalized = _safe_text(value)
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return normalized


def _has_secret_like_text(value: str) -> bool:
    text = _safe_text(value)
    return any(pattern.search(text) for pattern in SECRET_LIKE_PATTERNS)


def _validate_bounded_text(value: Any, *, field: str, max_chars: int, required: bool = False) -> str:
    text = _safe_text(value)
    if required:
        _require(bool(text), f"{field} is required.")
    _require(len(text) <= max_chars, f"{field} must be at most {max_chars} normalized characters.")
    _require(not _has_secret_like_text(text), f"{field} must not include secret-like text.")
    return text


def _validate_source(value: Any) -> dict[str, Any]:
    source = _json_object_snapshot(value)
    _require(bool(source), "source is required.")
    raw_source_type = _safe_text(source.get("source_type"))
    _require(raw_source_type not in FORBIDDEN_SOURCE_TYPES, "source.source_type must not encode vendor or manual-note sources.")
    source["source_type"] = _validate_enum(raw_source_type, SOURCE_TYPES, "source.source_type")
    for field in ("source_label", "source_url", "provider", "captured_from"):
        source[field] = _safe_text(source.get(field))
    return source


def _validate_boundary(value: Any) -> dict[str, Any]:
    boundary = _json_object_snapshot(value)
    _require(bool(boundary), "boundary is required.")
    for key, required_value in REQUIRED_BOUNDARY.items():
        _require(boundary.get(key) == required_value, f"boundary.{key} must be {required_value!r}.")
    return boundary


def _validate_message_refs(value: Any) -> list[dict[str, Any]]:
    refs = _json_list_snapshot(value)
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(refs):
        ref = _json_object_snapshot(item)
        _require(bool(ref), f"message_refs[{index}] must be an object.")
        ref["message_id"] = _safe_text(ref.get("message_id"))
        _require(bool(ref["message_id"]), f"message_refs[{index}].message_id is required.")
        ref["role"] = _safe_text(ref.get("role"))
        ref["sequence"] = ref.get("sequence")
        ref["content_excerpt"] = _validate_bounded_text(
            ref.get("content_excerpt"),
            field=f"message_refs[{index}].content_excerpt",
            max_chars=MAX_MESSAGE_EXCERPT_CHARS,
            required=True,
        )
        ref["content_fingerprint"] = _safe_text(ref.get("content_fingerprint"))
        validated.append(ref)
    return validated


def _has_created_audit_ref(audit_refs: list[Any]) -> bool:
    for item in audit_refs:
        if not isinstance(item, dict):
            continue
        if (
            _safe_text(item.get("record_family")) == CAPTURE_AUDIT_EVENT_RECORD_TYPE
            and _safe_text(item.get("action")) == AUDIT_ACTION_CREATED
        ):
            return True
    return False


def _audit_ref(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_family": CAPTURE_AUDIT_EVENT_RECORD_TYPE,
        "record_id": _safe_text(event.get("id")),
        "action": _safe_text(event.get("action")),
        "recorded_at": _safe_text(event.get("recorded_at")),
    }


def build_ai_discussion_capture_audit_event(
    *,
    capture_id: str,
    action: str,
    actor: dict[str, Any] | None = None,
    source_ref: dict[str, Any] | None = None,
    note: str = "",
    recorded_at: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    normalized_capture_id = _safe_text(capture_id)
    _require(bool(normalized_capture_id), "capture_id is required.")
    normalized_action = _validate_enum(action, AUDIT_ACTIONS, "action")
    recorded = _safe_text(recorded_at) or _utc_now_iso()

    return {
        "id": _safe_text(event_id) or f"aida_{uuid.uuid4().hex[:12]}",
        "schema_version": SCHEMA_VERSION,
        "record_type": CAPTURE_AUDIT_EVENT_RECORD_TYPE,
        "capture_id": normalized_capture_id,
        "action": normalized_action,
        "actor": _json_object_snapshot(actor or {"type": "human", "id": ""}),
        "recorded_at": recorded,
        "source_ref": _json_object_snapshot(
            source_ref or {"record_family": CAPTURE_RECORD_TYPE, "record_id": normalized_capture_id}
        ),
        "note": _safe_text(note),
    }


def validate_ai_discussion_capture_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(event, dict), "audit event must be a JSON object.")
    payload = _json_object_snapshot(event)
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.")
    _require(
        payload.get("record_type") == CAPTURE_AUDIT_EVENT_RECORD_TYPE,
        f"record_type must be {CAPTURE_AUDIT_EVENT_RECORD_TYPE}.",
    )
    _require(bool(_safe_text(payload.get("id"))), "id is required.")
    _require(bool(_safe_text(payload.get("capture_id"))), "capture_id is required.")
    payload["action"] = _validate_enum(_safe_text(payload.get("action")), AUDIT_ACTIONS, "action")
    _require(bool(_safe_text(payload.get("recorded_at"))), "recorded_at is required.")
    return payload


def validate_ai_discussion_capture_record(record: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(record, dict), "record must be a JSON object.")
    payload = _json_object_snapshot(record)

    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.")
    _require(payload.get("record_type") == CAPTURE_RECORD_TYPE, f"record_type must be {CAPTURE_RECORD_TYPE}.")
    _require(bool(_safe_text(payload.get("id"))), "id is required.")
    payload["capture_mode"] = _validate_enum(_safe_text(payload.get("capture_mode")), CAPTURE_MODES, "capture_mode")
    payload["source"] = _validate_source(payload.get("source"))
    payload["captured_at"] = _safe_text(payload.get("captured_at"))
    _require(bool(payload["captured_at"]), "captured_at is required.")
    payload["captured_by"] = _safe_text(payload.get("captured_by")) or "human_or_agent"
    payload["selection_reason"] = _safe_text(payload.get("selection_reason"))
    payload["message_refs"] = _validate_message_refs(payload.get("message_refs"))
    payload["discussion_excerpt"] = _validate_bounded_text(
        payload.get("discussion_excerpt"),
        field="discussion_excerpt",
        max_chars=MAX_DISCUSSION_EXCERPT_CHARS,
    )
    _require(
        bool(payload["message_refs"]) or bool(payload["discussion_excerpt"]),
        "capture records require at least one selected excerpt or message ref.",
    )
    payload["discussion_fingerprint"] = _safe_text(payload.get("discussion_fingerprint"))
    _require(bool(payload["discussion_fingerprint"]), "discussion_fingerprint is required.")
    payload["boundary"] = _validate_boundary(payload.get("boundary"))
    audit_refs = _json_list_snapshot(payload.get("audit_refs"))
    _require(_has_created_audit_ref(audit_refs), "capture records must include a created audit ref.")
    payload["audit_refs"] = audit_refs
    payload["created_at"] = _safe_text(payload.get("created_at"))
    payload["updated_at"] = _safe_text(payload.get("updated_at"))
    return payload


def build_ai_discussion_capture_record(
    *,
    message_refs: list[dict[str, Any]] | None = None,
    discussion_excerpt: str = "",
    source: dict[str, Any] | None = None,
    captured_by: str = "human_or_agent",
    selection_reason: str = "",
    captured_at: str | None = None,
    discussion_fingerprint: str = "",
    record_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    captured = _safe_text(captured_at) or _utc_now_iso()
    capture_id = _safe_text(record_id) or f"aid_{uuid.uuid4().hex[:12]}"
    source_payload = _json_object_snapshot(
        source
        or {
            "source_type": SOURCE_TYPE_AI_DISCUSSION_SESSION,
            "source_label": "",
            "source_url": "",
            "provider": "",
            "captured_from": "",
        }
    )
    audit_event = build_ai_discussion_capture_audit_event(
        capture_id=capture_id,
        action=AUDIT_ACTION_CREATED,
        actor={"type": _safe_text(captured_by) or "human_or_agent", "id": ""},
        recorded_at=captured,
    )

    payload = {
        "id": capture_id,
        "schema_version": SCHEMA_VERSION,
        "record_type": CAPTURE_RECORD_TYPE,
        "capture_mode": CAPTURE_MODE_SELECTED_EXCERPT,
        "source": source_payload,
        "captured_at": captured,
        "captured_by": _safe_text(captured_by) or "human_or_agent",
        "selection_reason": _safe_text(selection_reason),
        "message_refs": _json_list_snapshot(message_refs or []),
        "discussion_excerpt": _safe_text(discussion_excerpt),
        "discussion_fingerprint": _safe_text(discussion_fingerprint),
        "boundary": copy.deepcopy(REQUIRED_BOUNDARY),
        "audit_refs": [_audit_ref(audit_event)],
        "created_at": captured,
        "updated_at": captured,
    }

    return validate_ai_discussion_capture_record(payload), audit_event
