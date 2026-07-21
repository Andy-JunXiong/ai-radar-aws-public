from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.project_calibration_event_service import append_project_calibration_event, list_project_calibration_events
from app.services.project_takeaway_constants import (
    PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
    REVIEW_OUTCOME_ACTION,
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_OUTCOME_WATCH,
)
from app.services.verification_metadata_reader import (
    build_action_eligibility_summary,
    get_allowed_downstream_actions,
    get_blocked_downstream_actions,
    get_claim_support_summary,
    get_confidence_label,
    get_confidence_score,
    get_model_provenance,
    get_verification_status,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "project_review_records"
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
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value if _safe_text(item)]


def _deep_project_match_review(verification_metadata: dict[str, Any]) -> dict[str, Any]:
    payload = verification_metadata.get("deep_project_match_review")
    return payload if isinstance(payload, dict) else {}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _record_path(record_id: str) -> Path:
    safe = _safe_text(record_id).replace("/", "_").replace("\\", "_")
    return DATA_DIR / f"{safe}.json"


def _load_index() -> list[dict[str, Any]]:
    _ensure_data_dir()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass
    return []


def _save_index(items: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def build_project_review_record(
    *,
    project_id: str,
    signal_id: str,
    outcome: str,
    reason: str = "",
    source_status: str = "",
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = _utc_now_iso()
    item = item or {}
    verification_metadata = item.get("verification_metadata") if isinstance(item.get("verification_metadata"), dict) else {}
    claim_support_summary = get_claim_support_summary(verification_metadata)
    source_type = _safe_text(item.get("source_type")) or (
        "manual_upload" if _safe_text(item.get("signal_id") or signal_id).startswith(("manual_", "manual-")) else "signal"
    )
    manual_session_id = _safe_text(item.get("manual_session_id"))
    if not manual_session_id and source_type == "manual_upload":
        source_signal_id = _safe_text(item.get("signal_id") or signal_id)
        manual_session_id = source_signal_id[len("manual_") :] if source_signal_id.startswith("manual_") else source_signal_id
    upload_reason = _safe_text(item.get("upload_reason") or verification_metadata.get("upload_reason"))
    intended_use = _safe_text(item.get("intended_use") or verification_metadata.get("intended_use"))
    cognitive_layer = _safe_text(item.get("cognitive_layer") or verification_metadata.get("cognitive_layer") or "unclassified")
    manual_project_takeaway_override = bool(verification_metadata.get("manual_project_takeaway_override"))
    deep_project_match_review = _deep_project_match_review(verification_metadata)
    return {
        "id": f"prv_{uuid.uuid4().hex[:12]}",
        "record_type": "project_takeaway_review",
        "project_id": _safe_text(project_id),
        "project_name": _safe_text(item.get("project_name")),
        "signal_id": _safe_text(signal_id),
        "signal_title": _safe_text(item.get("signal_title")),
        "source_type": source_type,
        "manual_session_id": manual_session_id,
        "is_manual_source": source_type == "manual_upload",
        "upload_reason": upload_reason,
        "intended_use": intended_use,
        "cognitive_layer": cognitive_layer,
        "outcome": _safe_text(outcome),
        "reason": _safe_text(reason),
        "source_status": _safe_text(source_status),
        "candidate_source": _safe_text(item.get("candidate_source")),
        "produced_by_model": item.get("produced_by_model") or get_model_provenance(verification_metadata),
        "manual_project_takeaway_override": manual_project_takeaway_override,
        "manual_override_note": _safe_text(verification_metadata.get("manual_override_note")),
        "deep_project_match_required": bool(deep_project_match_review.get("required")),
        "deep_project_match_status": _safe_text(deep_project_match_review.get("status")),
        "deep_project_match_posture": _safe_text(deep_project_match_review.get("posture")),
        "deep_project_match_review_note": _safe_text(deep_project_match_review.get("review_note")),
        "deep_project_match_review_note_effect": _safe_text(deep_project_match_review.get("review_note_effect") or "review_context_only"),
        "deep_project_match_matched_projects": _safe_text_list(deep_project_match_review.get("matched_projects")),
        "deep_project_match_relevant_modules": _safe_text_list(deep_project_match_review.get("relevant_modules")),
        "deep_project_match_match_type": _safe_text(deep_project_match_review.get("match_type")),
        "deep_project_match_evidence_boundary": _safe_text(deep_project_match_review.get("evidence_boundary")),
        "deep_project_match_downstream_posture": _safe_text(deep_project_match_review.get("downstream_posture")),
        "verification_status": get_verification_status(verification_metadata),
        "claim_support_summary": claim_support_summary,
        "unsupported_claim_count": safe_int(claim_support_summary.get("unsupported"))
        + safe_int(claim_support_summary.get("contradicted")),
        "inferred_claim_count": safe_int(claim_support_summary.get("inferred")),
        "allowed_downstream_actions": get_allowed_downstream_actions(verification_metadata),
        "blocked_downstream_actions": get_blocked_downstream_actions(verification_metadata),
        "action_eligibility": build_action_eligibility_summary(verification_metadata),
        "confidence_score": get_confidence_score(verification_metadata),
        "confidence_label": get_confidence_label(verification_metadata),
        "reviewed_at": created_at,
        "created_at": created_at,
        "updated_at": created_at,
    }


def save_project_review_record(record: dict[str, Any]) -> dict[str, Any]:
    _ensure_data_dir()
    _record_path(str(record["id"])).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    items = [item for item in _load_index() if item.get("id") != record["id"]]
    items.append(
        {
            "id": record["id"],
            "project_id": record.get("project_id"),
            "signal_id": record.get("signal_id"),
            "outcome": record.get("outcome"),
            "reviewed_at": record.get("reviewed_at"),
            "updated_at": record.get("updated_at"),
        }
    )
    _save_index(sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return record


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_low_risk_action_blocked(record: dict[str, Any]) -> bool:
    action_eligibility = record.get("action_eligibility")
    if isinstance(action_eligibility, dict):
        low_risk_action = action_eligibility.get("low_risk_action_candidate")
        if isinstance(low_risk_action, dict) and low_risk_action.get("allowed") is False:
            return True

    blocked_actions = record.get("blocked_downstream_actions")
    if isinstance(blocked_actions, list):
        return any(_safe_text(action) == "low_risk_action_candidate" for action in blocked_actions)
    return False


def append_project_review_record(
    *,
    project_id: str,
    signal_id: str,
    outcome: str,
    reason: str = "",
    source_status: str = "",
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = save_project_review_record(
        build_project_review_record(
            project_id=project_id,
            signal_id=signal_id,
            outcome=outcome,
            reason=reason,
            source_status=source_status,
            item=item,
        )
    )
    append_project_calibration_event(
        event_type="review_record_created",
        project_id=project_id,
        signal_id=signal_id,
        outcome=outcome,
        source_status=source_status,
        review_record_id=_safe_text(record.get("id")),
        item=item,
    )
    return record


def list_project_review_records(
    *,
    project_id: str | None = None,
    signal_id: str | None = None,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _load_index():
        record = get_project_review_record(str(item.get("id") or ""))
        if not record:
            continue
        if project_id and str(record.get("project_id") or "") != project_id:
            continue
        if signal_id and str(record.get("signal_id") or "") != signal_id:
            continue
        if outcome and str(record.get("outcome") or "") != outcome:
            continue
        records.append(record)
    return sorted(records, key=lambda record: str(record.get("updated_at") or ""), reverse=True)


def summarize_project_review_records(
    *,
    project_id: str | None = None,
    signal_id: str | None = None,
) -> dict[str, Any]:
    records = list_project_review_records(project_id=project_id, signal_id=signal_id)
    outcome_counts: dict[str, int] = {}
    project_counts: dict[str, int] = {}
    verification_status_counts: dict[str, int] = {}
    blocked_action_counts: dict[str, int] = {}
    confidence_label_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    manual_outcome_counts: dict[str, int] = {}
    latest_reviewed_at = ""
    unsupported_claim_count = 0
    inferred_claim_count = 0
    low_confidence_count = 0
    records_with_blocked_actions = 0
    records_with_action_blocked = 0
    action_outcomes_with_blocked_gate = 0
    manual_overrides_with_blocked_action = 0
    watch_outcomes_with_action_blocked = 0
    gate_conflict_record_count = 0
    manual_record_count = 0

    for record in records:
        outcome = _safe_text(record.get("outcome") or "unknown") or "unknown"
        project = _safe_text(record.get("project_id") or "unknown") or "unknown"
        verification_status = _safe_text(record.get("verification_status") or "unknown") or "unknown"
        confidence_label = _safe_text(record.get("confidence_label") or "unknown").lower() or "unknown"
        source_type = _safe_text(record.get("source_type") or "signal") or "signal"
        is_manual_source = bool(record.get("is_manual_source")) or source_type == "manual_upload"
        is_manual_override = bool(record.get("manual_project_takeaway_override"))
        blocked_actions = record.get("blocked_downstream_actions")
        low_risk_action_blocked = _is_low_risk_action_blocked(record)
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        project_counts[project] = project_counts.get(project, 0) + 1
        verification_status_counts[verification_status] = verification_status_counts.get(verification_status, 0) + 1
        confidence_label_counts[confidence_label] = confidence_label_counts.get(confidence_label, 0) + 1
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        if is_manual_source:
            manual_record_count += 1
            manual_outcome_counts[outcome] = manual_outcome_counts.get(outcome, 0) + 1
        unsupported_claim_count += safe_int(record.get("unsupported_claim_count"))
        inferred_claim_count += safe_int(record.get("inferred_claim_count"))
        if confidence_label == "low":
            low_confidence_count += 1
        if isinstance(blocked_actions, list) and blocked_actions:
            records_with_blocked_actions += 1
            for action in blocked_actions:
                normalized_action = _safe_text(action) or "unknown"
                blocked_action_counts[normalized_action] = blocked_action_counts.get(normalized_action, 0) + 1
        if low_risk_action_blocked:
            records_with_action_blocked += 1
            if outcome in {REVIEW_OUTCOME_ACTION, PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED}:
                action_outcomes_with_blocked_gate += 1
            if outcome == REVIEW_OUTCOME_WATCH:
                watch_outcomes_with_action_blocked += 1
            if is_manual_override:
                manual_overrides_with_blocked_action += 1
            if outcome in {REVIEW_OUTCOME_ACTION, PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED} or is_manual_override:
                gate_conflict_record_count += 1
        reviewed_at = _safe_text(record.get("reviewed_at") or record.get("updated_at"))
        if reviewed_at and reviewed_at > latest_reviewed_at:
            latest_reviewed_at = reviewed_at

    total = len(records)
    return {
        "total_records": total,
        "outcome_counts": outcome_counts,
        "project_counts": project_counts,
        "latest_reviewed_at": latest_reviewed_at,
        "actionable_count": outcome_counts.get(REVIEW_OUTCOME_CONFIRMED, 0)
        + outcome_counts.get(REVIEW_OUTCOME_ACTION, 0)
        + outcome_counts.get(PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED, 0),
        "watch_count": outcome_counts.get(REVIEW_OUTCOME_WATCH, 0),
        "rejected_or_dismissed_count": outcome_counts.get(REVIEW_OUTCOME_REJECTED, 0)
        + outcome_counts.get(REVIEW_OUTCOME_DISMISSED, 0),
        "verification_status_counts": verification_status_counts,
        "blocked_action_counts": blocked_action_counts,
        "confidence_label_counts": confidence_label_counts,
        "source_type_counts": source_type_counts,
        "manual_record_count": manual_record_count,
        "manual_record_rate": round(manual_record_count / total, 4) if total else 0,
        "manual_outcome_counts": manual_outcome_counts,
        "manual_actionable_count": manual_outcome_counts.get(REVIEW_OUTCOME_CONFIRMED, 0)
        + manual_outcome_counts.get(REVIEW_OUTCOME_ACTION, 0)
        + manual_outcome_counts.get(PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED, 0),
        "manual_watch_count": manual_outcome_counts.get(REVIEW_OUTCOME_WATCH, 0),
        "unsupported_claim_count": unsupported_claim_count,
        "inferred_claim_count": inferred_claim_count,
        "low_confidence_count": low_confidence_count,
        "records_with_blocked_actions": records_with_blocked_actions,
        "records_with_action_blocked": records_with_action_blocked,
        "action_outcomes_with_blocked_gate": action_outcomes_with_blocked_gate,
        "manual_overrides_with_blocked_action": manual_overrides_with_blocked_action,
        "watch_outcomes_with_action_blocked": watch_outcomes_with_action_blocked,
        "gate_conflict_record_count": gate_conflict_record_count,
        "blocked_action_rate": round(records_with_blocked_actions / total, 4) if total else 0,
    }


def get_project_review_record(record_id: str) -> dict[str, Any] | None:
    path = _record_path(record_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def build_project_review_record_detail(record_id: str) -> dict[str, Any] | None:
    record = get_project_review_record(record_id)
    if not record:
        return None

    calibration_events = list_project_calibration_events(
        project_id=_safe_text(record.get("project_id")),
        signal_id=_safe_text(record.get("signal_id")),
    )
    current_record_id = _safe_text(record.get("id"))
    related_events = [
        {
            "id": event.get("id"),
            "event_type": event.get("event_type"),
            "outcome": event.get("outcome"),
            "source_status": event.get("source_status"),
            "review_record_id": event.get("review_record_id"),
            "is_current_review_record_event": _safe_text(event.get("review_record_id")) == current_record_id,
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
        }
        for event in calibration_events
    ]
    related_events = sorted(
        related_events,
        key=lambda event: (
            bool(event.get("is_current_review_record_event")),
            _safe_text(event.get("updated_at") or event.get("created_at")),
        ),
        reverse=True,
    )[:20]
    matching_review_record_event_count = sum(
        1 for event in related_events if _safe_text(event.get("review_record_id")) == current_record_id
    )
    return {
        "item": record,
        "related_calibration_events": related_events,
        "audit_summary": {
            "event_count": len(related_events),
            "has_review_record_created": any(
                event.get("event_type") == "review_record_created" for event in related_events
            ),
            "has_outcome_event": any(
                event.get("event_type") != "review_record_created" for event in related_events
            ),
            "matching_review_record_event_count": matching_review_record_event_count,
        },
        "message": "project review record loaded successfully",
    }
