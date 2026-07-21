from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.relationship_annotation_service import normalize_relationship_annotation


SCHEMA_VERSION = 1
RECORD_TYPE = "signal_claim_review_feedback"

REASON_SLOT_STALE_INPUT = "stale_input"
REASON_SLOT_NOT_ME = "not_me"
REASON_SLOT_REASONING_GAP = "reasoning_gap"
REASON_SLOT_BLIND_SPOT = "blind_spot"

REASON_SLOTS: frozenset[str] = frozenset(
    {
        REASON_SLOT_STALE_INPUT,
        REASON_SLOT_NOT_ME,
        REASON_SLOT_REASONING_GAP,
        REASON_SLOT_BLIND_SPOT,
    }
)

DISTORTION_TAGS: frozenset[str] = frozenset(
    {
        "fabricated_attribution",
        "source_asserted_but_unsubstantiated",
        "pseudo_precision",
        "juxtaposition_fusion",
        "causal_overreach",
        "caveat_stripping",
        "category_collapse",
        "context_drift",
        "personal_context_mismatch",
    }
)

DOWNSTREAM_EFFECT_NONE = "none"
EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE = "not_external_claim_evidence"
BACKGROUND_UPDATE_CANDIDATE_RECORD_TYPE = "background_update_candidate"
BACKGROUND_UPDATE_CANDIDATE_STATUS = "inactive_review_only"
BACKGROUND_UPDATE_DECISION_RECORD_TYPE = "background_update_candidate_decision"
BACKGROUND_UPDATE_DECISION_CONFIRM = "confirmed"
BACKGROUND_UPDATE_DECISION_DISMISS = "dismissed"
BACKGROUND_UPDATE_DECISIONS: frozenset[str] = frozenset(
    {
        BACKGROUND_UPDATE_DECISION_CONFIRM,
        BACKGROUND_UPDATE_DECISION_DISMISS,
    }
)
BACKGROUND_UPDATE_REASON_SLOTS: frozenset[str] = frozenset(
    {
        REASON_SLOT_NOT_ME,
        REASON_SLOT_BLIND_SPOT,
    }
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "signal_review_feedback"
INDEX_PATH = DATA_DIR / "index.json"


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


def _clean_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = _safe_text(item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _json_object_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return {}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _record_path(record_id: str) -> Path:
    safe = _safe_text(record_id).replace("/", "_").replace("\\", "_")
    return DATA_DIR / f"{safe}.json"


def _decision_data_dir() -> Path:
    return DATA_DIR / "background_update_candidate_decisions"


def _decision_index_path() -> Path:
    return _decision_data_dir() / "index.json"


def _decision_record_path(record_id: str) -> Path:
    safe = _safe_text(record_id).replace("/", "_").replace("\\", "_")
    return _decision_data_dir() / f"{safe}.json"


def _load_index() -> list[dict[str, Any]]:
    _ensure_data_dir()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save_index(items: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_decision_data_dir() -> None:
    _decision_data_dir().mkdir(parents=True, exist_ok=True)
    if not _decision_index_path().exists():
        _decision_index_path().write_text("[]", encoding="utf-8")


def _load_decision_index() -> list[dict[str, Any]]:
    _ensure_decision_data_dir()
    try:
        payload = json.loads(_decision_index_path().read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save_decision_index(items: list[dict[str, Any]]) -> None:
    _ensure_decision_data_dir()
    _decision_index_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_reason_slot(reason_slot: str) -> str:
    normalized = _safe_text(reason_slot).lower()
    if normalized not in REASON_SLOTS:
        raise ValueError(f"reason_slot must be one of: {', '.join(sorted(REASON_SLOTS))}.")
    return normalized


def _validate_distortion_tags(tags: Any) -> list[str]:
    cleaned = _clean_text_list(tags)
    unknown = [tag for tag in cleaned if tag not in DISTORTION_TAGS]
    if unknown:
        raise ValueError(f"Unknown distortion_tags: {', '.join(unknown)}.")
    return cleaned


def _validate_background_update_decision(decision: str) -> str:
    normalized = _safe_text(decision).lower()
    if normalized not in BACKGROUND_UPDATE_DECISIONS:
        raise ValueError(
            "decision must be one of: "
            f"{', '.join(sorted(BACKGROUND_UPDATE_DECISIONS))}."
        )
    return normalized


def build_signal_review_feedback_record(
    *,
    signal_id: str,
    claim_id: str,
    reason_slot: str,
    note: str,
    insight_id: str = "",
    content_fingerprint: str = "",
    claim_text_snapshot: str = "",
    claim_source_field: str = "",
    distortion_tags: list[str] | None = None,
    verification_snapshot: dict[str, Any] | None = None,
    input_provenance_snapshot: dict[str, Any] | None = None,
    relationship_annotation: dict[str, Any] | None = None,
    created_by: str = "human",
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_signal_id = _safe_text(signal_id)
    normalized_claim_id = _safe_text(claim_id)
    normalized_note = _safe_text(note)
    if not normalized_signal_id:
        raise ValueError("signal_id is required.")
    if not normalized_claim_id:
        raise ValueError("claim_id is required.")
    if not normalized_note:
        raise ValueError("note is required.")

    created = _safe_text(created_at) or _utc_now_iso()
    normalized_reason_slot = _validate_reason_slot(reason_slot)
    normalized_distortion_tags = _validate_distortion_tags(distortion_tags or [])
    normalized_relationship_annotation = normalize_relationship_annotation(relationship_annotation or {})

    return {
        "id": f"srf_{uuid.uuid4().hex[:12]}",
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "signal_id": normalized_signal_id,
        "insight_id": _safe_text(insight_id),
        "content_fingerprint": _safe_text(content_fingerprint),
        "claim_id": normalized_claim_id,
        "claim_text_snapshot": _safe_text(claim_text_snapshot),
        "claim_source_field": _safe_text(claim_source_field),
        "reason_slot": normalized_reason_slot,
        "distortion_tags": normalized_distortion_tags,
        "note": normalized_note,
        "verification_snapshot": _json_object_snapshot(verification_snapshot or {}),
        "input_provenance_snapshot": _json_object_snapshot(input_provenance_snapshot or {}),
        "relationship_annotation": normalized_relationship_annotation,
        "downstream_effect": DOWNSTREAM_EFFECT_NONE,
        "evidence_boundary": EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE,
        "background_update_candidate_id": "",
        "created_by": _safe_text(created_by) or "human",
        "created_at": created,
        "updated_at": created,
    }


def save_signal_review_feedback_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object.")
    record_id = _safe_text(record.get("id"))
    if not record_id:
        raise ValueError("record id is required.")

    _ensure_data_dir()
    payload = _json_object_snapshot(record)
    _record_path(record_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    items = [item for item in _load_index() if item.get("id") != record_id]
    items.append(
        {
            "id": record_id,
            "record_type": payload.get("record_type"),
            "signal_id": payload.get("signal_id"),
            "claim_id": payload.get("claim_id"),
            "reason_slot": payload.get("reason_slot"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
        }
    )
    _save_index(sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return payload


def append_signal_review_feedback_record(
    *,
    signal_id: str,
    claim_id: str,
    reason_slot: str,
    note: str,
    insight_id: str = "",
    content_fingerprint: str = "",
    claim_text_snapshot: str = "",
    claim_source_field: str = "",
    distortion_tags: list[str] | None = None,
    verification_snapshot: dict[str, Any] | None = None,
    input_provenance_snapshot: dict[str, Any] | None = None,
    relationship_annotation: dict[str, Any] | None = None,
    created_by: str = "human",
) -> dict[str, Any]:
    return save_signal_review_feedback_record(
        build_signal_review_feedback_record(
            signal_id=signal_id,
            insight_id=insight_id,
            content_fingerprint=content_fingerprint,
            claim_id=claim_id,
            claim_text_snapshot=claim_text_snapshot,
            claim_source_field=claim_source_field,
            reason_slot=reason_slot,
            distortion_tags=distortion_tags,
            note=note,
            verification_snapshot=verification_snapshot,
            input_provenance_snapshot=input_provenance_snapshot,
            relationship_annotation=relationship_annotation,
            created_by=created_by,
        )
    )


def get_signal_review_feedback_record(record_id: str) -> dict[str, Any] | None:
    path = _record_path(record_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def list_signal_review_feedback_records(
    *,
    signal_id: str | None = None,
    claim_id: str | None = None,
    reason_slot: str | None = None,
) -> list[dict[str, Any]]:
    normalized_signal_id = _safe_text(signal_id)
    normalized_claim_id = _safe_text(claim_id)
    normalized_reason_slot = _safe_text(reason_slot).lower()
    records: list[dict[str, Any]] = []

    for item in _load_index():
        record = get_signal_review_feedback_record(str(item.get("id") or ""))
        if not record:
            continue
        if normalized_signal_id and _safe_text(record.get("signal_id")) != normalized_signal_id:
            continue
        if normalized_claim_id and _safe_text(record.get("claim_id")) != normalized_claim_id:
            continue
        if normalized_reason_slot and _safe_text(record.get("reason_slot")).lower() != normalized_reason_slot:
            continue
        records.append(record)

    return sorted(records, key=lambda record: str(record.get("updated_at") or ""), reverse=True)


def _background_candidate_id(feedback_id: str) -> str:
    normalized = _safe_text(feedback_id)
    if normalized.startswith("srf_"):
        normalized = normalized[4:]
    return f"buc_{normalized}"


def _background_candidate_type(reason_slot: str) -> str:
    if reason_slot == REASON_SLOT_NOT_ME:
        return "user_context_alignment"
    if reason_slot == REASON_SLOT_BLIND_SPOT:
        return "user_attention_calibration"
    return "not_background_update_candidate"


def _background_review_focus(reason_slot: str) -> str:
    if reason_slot == REASON_SLOT_NOT_ME:
        return "Review whether AI Radar's understanding of the user's priorities or project context is stale or mismatched."
    if reason_slot == REASON_SLOT_BLIND_SPOT:
        return "Review whether this feedback should become user-confirmed attention or interpretation context."
    return "This feedback reason is not eligible for the background update candidate queue."


def _freshness_summary(record: dict[str, Any]) -> dict[str, Any]:
    provenance = record.get("input_provenance_snapshot")
    if not isinstance(provenance, dict):
        return {"summary": "", "stale_flags": [], "freshness_penalty": 0}
    freshness = provenance.get("freshness")
    if not isinstance(freshness, dict):
        return {"summary": "", "stale_flags": [], "freshness_penalty": 0}
    return {
        "summary": _safe_text(freshness.get("summary")),
        "stale_flags": _clean_text_list(freshness.get("stale_flags")),
        "freshness_penalty": freshness.get("freshness_penalty") if isinstance(freshness.get("freshness_penalty"), (int, float)) else 0,
    }


def build_background_update_candidate(record: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    reason_slot = _safe_text(record.get("reason_slot")).lower()
    if reason_slot not in BACKGROUND_UPDATE_REASON_SLOTS:
        return None

    verification_snapshot = record.get("verification_snapshot")
    if not isinstance(verification_snapshot, dict):
        verification_snapshot = {}

    feedback_id = _safe_text(record.get("id"))
    created_at = _safe_text(record.get("created_at"))
    updated_at = _safe_text(record.get("updated_at")) or created_at

    return {
        "id": _background_candidate_id(feedback_id),
        "schema_version": SCHEMA_VERSION,
        "record_type": BACKGROUND_UPDATE_CANDIDATE_RECORD_TYPE,
        "candidate_status": BACKGROUND_UPDATE_CANDIDATE_STATUS,
        "candidate_scope": "user_or_system_understanding_context",
        "candidate_type": _background_candidate_type(reason_slot),
        "suggested_review_focus": _background_review_focus(reason_slot),
        "source_feedback_id": feedback_id,
        "source_signal_id": _safe_text(record.get("signal_id")),
        "source_insight_id": _safe_text(record.get("insight_id")),
        "source_claim_id": _safe_text(record.get("claim_id")),
        "source_claim_text_snapshot": _safe_text(record.get("claim_text_snapshot")),
        "reason_slot": reason_slot,
        "distortion_tags": _clean_text_list(record.get("distortion_tags")),
        "note_snapshot": _safe_text(record.get("note")),
        "feedback_created_at": created_at,
        "updated_at": updated_at,
        "verification_snapshot_summary": {
            "verification_status": _safe_text(verification_snapshot.get("verification_status")),
            "confidence_label": _safe_text(verification_snapshot.get("confidence_label")),
            "blocked_downstream_actions": _clean_text_list(verification_snapshot.get("blocked_downstream_actions")),
        },
        "input_freshness_summary": _freshness_summary(record),
        "downstream_effect": "candidate_only",
        "evidence_boundary": EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE,
        "review_boundary": {
            "requires_explicit_confirmation": True,
            "mutates_context": False,
            "mutates_verification_status": False,
            "mutates_project_takeaway_gate": False,
            "mutates_action_gate": False,
            "external_claim_evidence": False,
        },
        "latest_decision": None,
    }


def list_background_update_candidates(
    *,
    signal_id: str | None = None,
    reason_slot: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    normalized_reason_slot = _safe_text(reason_slot).lower()
    records = list_signal_review_feedback_records(signal_id=signal_id)
    candidates: list[dict[str, Any]] = []

    for record in records:
        candidate = build_background_update_candidate(record)
        if not candidate:
            continue
        if normalized_reason_slot and candidate.get("reason_slot") != normalized_reason_slot:
            continue
        candidates.append(candidate)

    capped_limit = max(1, min(int(limit or 50), 100))
    sorted_candidates = sorted(candidates, key=lambda item: str(item.get("updated_at") or ""), reverse=True)[:capped_limit]
    for candidate in sorted_candidates:
        latest_decision = get_latest_background_update_candidate_decision(str(candidate.get("id") or ""))
        candidate["latest_decision"] = summarize_background_update_candidate_decision(latest_decision)
    return sorted_candidates


def find_background_update_candidate(candidate_id: str) -> dict[str, Any] | None:
    normalized_candidate_id = _safe_text(candidate_id)
    if not normalized_candidate_id:
        return None
    for record in list_signal_review_feedback_records():
        candidate = build_background_update_candidate(record)
        if candidate and candidate.get("id") == normalized_candidate_id:
            latest_decision = get_latest_background_update_candidate_decision(normalized_candidate_id)
            candidate["latest_decision"] = summarize_background_update_candidate_decision(latest_decision)
            return candidate
    return None


def summarize_background_update_candidate_decision(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(decision, dict):
        return None
    return {
        "id": _safe_text(decision.get("id")),
        "decision": _safe_text(decision.get("decision")),
        "note": _safe_text(decision.get("note")),
        "created_by": _safe_text(decision.get("created_by")),
        "created_at": _safe_text(decision.get("created_at")),
        "downstream_effect": _safe_text(decision.get("downstream_effect")) or "decision_record_only",
        "evidence_boundary": _safe_text(decision.get("evidence_boundary")) or EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE,
    }


def build_background_update_candidate_decision_record(
    *,
    candidate_id: str,
    source_feedback_id: str,
    decision: str,
    note: str = "",
    candidate_snapshot: dict[str, Any] | None = None,
    created_by: str = "human",
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_candidate_id = _safe_text(candidate_id)
    normalized_source_feedback_id = _safe_text(source_feedback_id)
    if not normalized_candidate_id:
        raise ValueError("candidate_id is required.")
    if not normalized_source_feedback_id:
        raise ValueError("source_feedback_id is required.")

    created = _safe_text(created_at) or _utc_now_iso()
    normalized_decision = _validate_background_update_decision(decision)

    return {
        "id": f"bucd_{uuid.uuid4().hex[:12]}",
        "schema_version": SCHEMA_VERSION,
        "record_type": BACKGROUND_UPDATE_DECISION_RECORD_TYPE,
        "candidate_id": normalized_candidate_id,
        "source_feedback_id": normalized_source_feedback_id,
        "decision": normalized_decision,
        "note": _safe_text(note),
        "candidate_snapshot": _json_object_snapshot(candidate_snapshot or {}),
        "downstream_effect": "decision_record_only",
        "evidence_boundary": EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE,
        "review_boundary": {
            "records_human_decision": True,
            "mutates_context": False,
            "mutates_verification_status": False,
            "mutates_project_takeaway_gate": False,
            "mutates_action_gate": False,
            "external_claim_evidence": False,
        },
        "created_by": _safe_text(created_by) or "human",
        "created_at": created,
        "updated_at": created,
    }


def save_background_update_candidate_decision_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object.")
    record_id = _safe_text(record.get("id"))
    if not record_id:
        raise ValueError("record id is required.")

    _ensure_decision_data_dir()
    payload = _json_object_snapshot(record)
    _decision_record_path(record_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    items = [item for item in _load_decision_index() if item.get("id") != record_id]
    items.append(
        {
            "id": record_id,
            "record_type": payload.get("record_type"),
            "candidate_id": payload.get("candidate_id"),
            "source_feedback_id": payload.get("source_feedback_id"),
            "decision": payload.get("decision"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
        }
    )
    _save_decision_index(sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return payload


def append_background_update_candidate_decision(
    *,
    candidate_id: str,
    source_feedback_id: str,
    decision: str,
    note: str = "",
    candidate_snapshot: dict[str, Any] | None = None,
    created_by: str = "human",
) -> dict[str, Any]:
    return save_background_update_candidate_decision_record(
        build_background_update_candidate_decision_record(
            candidate_id=candidate_id,
            source_feedback_id=source_feedback_id,
            decision=decision,
            note=note,
            candidate_snapshot=candidate_snapshot,
            created_by=created_by,
        )
    )


def get_background_update_candidate_decision(record_id: str) -> dict[str, Any] | None:
    path = _decision_record_path(record_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def list_background_update_candidate_decisions(
    *,
    candidate_id: str | None = None,
    source_feedback_id: str | None = None,
    decision: str | None = None,
) -> list[dict[str, Any]]:
    normalized_candidate_id = _safe_text(candidate_id)
    normalized_source_feedback_id = _safe_text(source_feedback_id)
    normalized_decision = _safe_text(decision).lower()
    records: list[dict[str, Any]] = []

    for item in _load_decision_index():
        record = get_background_update_candidate_decision(str(item.get("id") or ""))
        if not record:
            continue
        if normalized_candidate_id and _safe_text(record.get("candidate_id")) != normalized_candidate_id:
            continue
        if normalized_source_feedback_id and _safe_text(record.get("source_feedback_id")) != normalized_source_feedback_id:
            continue
        if normalized_decision and _safe_text(record.get("decision")).lower() != normalized_decision:
            continue
        records.append(record)

    return sorted(records, key=lambda record: str(record.get("updated_at") or ""), reverse=True)


def get_latest_background_update_candidate_decision(candidate_id: str) -> dict[str, Any] | None:
    decisions = list_background_update_candidate_decisions(candidate_id=candidate_id)
    return decisions[0] if decisions else None
