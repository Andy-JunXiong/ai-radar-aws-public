from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.project_takeaway_constants import (
    ACTION_STATE_COMPLETED,
    EVENT_TYPE_BY_ACTION_STATE,
    EVENT_TYPE_BY_REVIEW_OUTCOME,
    PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
    REVIEW_OUTCOME_ACTION,
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_OUTCOME_WATCH,
)
from app.services.verification_metadata_reader import (
    build_action_eligibility_summary,
    get_blocked_downstream_actions,
    get_claim_support_summary,
    get_confidence_label,
    get_confidence_score,
    get_model_provenance,
    get_verification_status,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "project_calibration_events"
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


def _event_path(event_id: str) -> Path:
    safe = _safe_text(event_id).replace("/", "_").replace("\\", "_")
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


def append_project_calibration_event(
    *,
    event_type: str,
    project_id: str = "",
    signal_id: str = "",
    outcome: str = "",
    source_status: str = "",
    review_record_id: str = "",
    item: dict[str, Any] | None = None,
    followup_result: str = "",
    review_note: str = "",
    evidence_update: str = "",
    next_review_date: str = "",
    expected_outcome: str = "",
) -> dict[str, Any]:
    _ensure_data_dir()
    normalized_event_type = _safe_text(event_type)
    normalized_review_record_id = _safe_text(review_record_id)
    if normalized_review_record_id:
        for existing in list_project_calibration_events(event_type=normalized_event_type):
            if _safe_text(existing.get("review_record_id")) == normalized_review_record_id:
                return existing

    now = _utc_now_iso()
    item = item or {}
    verification_metadata = item.get("verification_metadata") if isinstance(item.get("verification_metadata"), dict) else {}
    claim_support_summary = get_claim_support_summary(verification_metadata)
    source_signal_id = _safe_text(signal_id or item.get("signal_id"))
    source_type = _safe_text(item.get("source_type")) or (
        "manual_upload" if source_signal_id.startswith(("manual_", "manual-")) else "signal"
    )
    manual_session_id = _safe_text(item.get("manual_session_id"))
    if not manual_session_id and source_type == "manual_upload":
        manual_session_id = source_signal_id[len("manual_") :] if source_signal_id.startswith("manual_") else source_signal_id
    upload_reason = _safe_text(item.get("upload_reason") or verification_metadata.get("upload_reason"))
    intended_use = _safe_text(item.get("intended_use") or verification_metadata.get("intended_use"))
    cognitive_layer = _safe_text(item.get("cognitive_layer") or verification_metadata.get("cognitive_layer") or "unclassified")
    manual_project_takeaway_override = bool(verification_metadata.get("manual_project_takeaway_override"))
    deep_project_match_review = _deep_project_match_review(verification_metadata)
    event = {
        "id": f"pce_{uuid.uuid4().hex[:12]}",
        "event_type": normalized_event_type,
        "project_id": _safe_text(project_id or item.get("project_id")),
        "project_name": _safe_text(item.get("project_name")),
        "signal_id": source_signal_id,
        "signal_title": _safe_text(item.get("signal_title")),
        "source_type": source_type,
        "manual_session_id": manual_session_id,
        "is_manual_source": source_type == "manual_upload",
        "upload_reason": upload_reason,
        "intended_use": intended_use,
        "cognitive_layer": cognitive_layer,
        "outcome": _safe_text(outcome),
        "followup_result": _safe_text(followup_result or item.get("watch_followup_result") or item.get("action_completion_result")),
        "review_note": _safe_text(review_note or item.get("watch_review_note") or item.get("action_completion_note")),
        "evidence_update": _safe_text(evidence_update or item.get("watch_evidence_update") or item.get("action_completion_evidence_update")),
        "next_review_date": _safe_text(next_review_date or item.get("watch_next_review_date") or item.get("action_next_review_date")),
        "expected_outcome": _safe_text(expected_outcome or item.get("action_expected_outcome") or item.get("manual_override_expected_outcome")),
        "source_status": _safe_text(source_status),
        "review_record_id": normalized_review_record_id,
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
        "blocked_downstream_actions": get_blocked_downstream_actions(verification_metadata),
        "action_eligibility": build_action_eligibility_summary(verification_metadata),
        "confidence_score": get_confidence_score(verification_metadata),
        "confidence_label": get_confidence_label(verification_metadata),
        "created_at": now,
        "updated_at": now,
    }
    _event_path(event["id"]).write_text(json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8")
    items = [index_item for index_item in _load_index() if index_item.get("id") != event["id"]]
    items.append(
        {
            "id": event["id"],
            "event_type": event["event_type"],
            "project_id": event["project_id"],
            "signal_id": event["signal_id"],
            "outcome": event["outcome"],
            "review_record_id": event["review_record_id"],
            "created_at": event["created_at"],
            "updated_at": event["updated_at"],
        }
    )
    _save_index(sorted(items, key=lambda index_item: str(index_item.get("updated_at") or ""), reverse=True))
    return event


def get_project_calibration_event(event_id: str) -> dict[str, Any] | None:
    path = _event_path(event_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def list_project_calibration_events(
    *,
    project_id: str | None = None,
    signal_id: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index_item in _load_index():
        event = get_project_calibration_event(str(index_item.get("id") or ""))
        if not event:
            continue
        if project_id and str(event.get("project_id") or "") != project_id:
            continue
        if signal_id and str(event.get("signal_id") or "") != signal_id:
            continue
        if event_type and str(event.get("event_type") or "") != event_type:
            continue
        events.append(event)
    return sorted(events, key=lambda event: str(event.get("updated_at") or ""), reverse=True)


def summarize_project_calibration_events(
    *,
    project_id: str | None = None,
    signal_id: str | None = None,
) -> dict[str, Any]:
    events = list_project_calibration_events(project_id=project_id, signal_id=signal_id)
    event_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    verification_status_counts: dict[str, int] = {}
    blocked_action_counts: dict[str, int] = {}
    confidence_label_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    manual_event_counts: dict[str, int] = {}
    manual_outcome_counts: dict[str, int] = {}
    latest_event_at = ""
    unsupported_claim_count = 0
    inferred_claim_count = 0
    low_confidence_event_count = 0
    events_with_blocked_actions = 0
    events_with_action_blocked = 0
    action_events_with_blocked_gate = 0
    manual_overrides_with_blocked_action = 0
    watch_events_with_action_blocked = 0
    gate_conflict_event_count = 0
    manual_event_count = 0

    for event in events:
        event_type = _safe_text(event.get("event_type") or "unknown") or "unknown"
        outcome = _safe_text(event.get("outcome") or "").lower()
        verification_status = _safe_text(event.get("verification_status") or "unknown") or "unknown"
        confidence_label = _safe_text(event.get("confidence_label") or "unknown").lower() or "unknown"
        source_type = _safe_text(event.get("source_type") or "signal") or "signal"
        is_manual_source = bool(event.get("is_manual_source")) or source_type == "manual_upload"
        is_manual_override = bool(event.get("manual_project_takeaway_override"))
        blocked_actions = event.get("blocked_downstream_actions")
        low_risk_action_blocked = _is_low_risk_action_blocked(event)
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        verification_status_counts[verification_status] = verification_status_counts.get(verification_status, 0) + 1
        confidence_label_counts[confidence_label] = confidence_label_counts.get(confidence_label, 0) + 1
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        if is_manual_source:
            manual_event_count += 1
            manual_event_counts[event_type] = manual_event_counts.get(event_type, 0) + 1
            if outcome and event_type != "review_record_created":
                manual_outcome_counts[outcome] = manual_outcome_counts.get(outcome, 0) + 1
        unsupported_claim_count += safe_int(event.get("unsupported_claim_count"))
        inferred_claim_count += safe_int(event.get("inferred_claim_count"))
        if confidence_label == "low":
            low_confidence_event_count += 1
        if isinstance(blocked_actions, list) and blocked_actions:
            events_with_blocked_actions += 1
            for action in blocked_actions:
                normalized_action = _safe_text(action) or "unknown"
                blocked_action_counts[normalized_action] = blocked_action_counts.get(normalized_action, 0) + 1
        if low_risk_action_blocked:
            events_with_action_blocked += 1
            if _is_action_event(event_type, outcome):
                action_events_with_blocked_gate += 1
            if _is_watch_event(event_type, outcome):
                watch_events_with_action_blocked += 1
            if is_manual_override:
                manual_overrides_with_blocked_action += 1
            if _is_action_event(event_type, outcome) or is_manual_override:
                gate_conflict_event_count += 1
        if outcome and event_type != "review_record_created":
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        created_at = _safe_text(event.get("created_at") or event.get("updated_at"))
        if created_at and created_at > latest_event_at:
            latest_event_at = created_at

    accepted = event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_CONFIRMED], 0)
    action_created = event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_ACTION], 0)
    action_completed = event_counts.get(EVENT_TYPE_BY_ACTION_STATE[ACTION_STATE_COMPLETED], 0)
    watch_reviewed = event_counts.get("watch_item_reviewed", 0)
    watch_created = event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_WATCH], 0)
    rejected_or_dismissed = event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_REJECTED], 0) + event_counts.get(
        EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_DISMISSED], 0
    )
    candidate_outcomes = accepted + action_created + event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_WATCH], 0) + rejected_or_dismissed

    return {
        "total_events": len(events),
        "event_counts": event_counts,
        "outcome_counts": outcome_counts,
        "latest_event_at": latest_event_at,
        "actionable_event_count": accepted + action_created + action_completed,
        "watch_event_count": watch_created,
        "watch_reviewed_event_count": watch_reviewed,
        "rejected_or_dismissed_event_count": rejected_or_dismissed,
        "candidate_review_event_count": candidate_outcomes,
        "candidate_to_actionable_rate": round((accepted + action_created) / candidate_outcomes, 4)
        if candidate_outcomes
        else 0,
        "takeaway_rejection_rate": round(rejected_or_dismissed / candidate_outcomes, 4)
        if candidate_outcomes
        else 0,
        "watch_review_completion_rate": round(watch_reviewed / watch_created, 4)
        if watch_created
        else 0,
        "verification_status_counts": verification_status_counts,
        "blocked_action_counts": blocked_action_counts,
        "confidence_label_counts": confidence_label_counts,
        "source_type_counts": source_type_counts,
        "manual_event_count": manual_event_count,
        "manual_event_rate": round(manual_event_count / len(events), 4) if events else 0,
        "manual_event_counts": manual_event_counts,
        "manual_outcome_counts": manual_outcome_counts,
        "manual_actionable_event_count": manual_event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_CONFIRMED], 0)
        + manual_event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_ACTION], 0)
        + manual_event_counts.get(EVENT_TYPE_BY_ACTION_STATE[ACTION_STATE_COMPLETED], 0),
        "manual_watch_event_count": manual_event_counts.get(EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_WATCH], 0),
        "unsupported_claim_count": unsupported_claim_count,
        "inferred_claim_count": inferred_claim_count,
        "low_confidence_event_count": low_confidence_event_count,
        "events_with_blocked_actions": events_with_blocked_actions,
        "events_with_action_blocked": events_with_action_blocked,
        "action_events_with_blocked_gate": action_events_with_blocked_gate,
        "manual_overrides_with_blocked_action": manual_overrides_with_blocked_action,
        "watch_events_with_action_blocked": watch_events_with_action_blocked,
        "gate_conflict_event_count": gate_conflict_event_count,
        "blocked_action_rate": round(events_with_blocked_actions / len(events), 4) if events else 0,
    }


def event_type_for_review_outcome(outcome: str) -> str:
    normalized = _safe_text(outcome).lower()
    if normalized == PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED:
        return EVENT_TYPE_BY_ACTION_STATE[ACTION_STATE_COMPLETED]
    return EVENT_TYPE_BY_REVIEW_OUTCOME.get(normalized, "")


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_low_risk_action_blocked(event: dict[str, Any]) -> bool:
    action_eligibility = event.get("action_eligibility")
    if isinstance(action_eligibility, dict):
        low_risk_action = action_eligibility.get("low_risk_action_candidate")
        if isinstance(low_risk_action, dict) and low_risk_action.get("allowed") is False:
            return True

    blocked_actions = event.get("blocked_downstream_actions")
    if isinstance(blocked_actions, list):
        return any(_safe_text(action) == "low_risk_action_candidate" for action in blocked_actions)
    return False


def _is_action_event(event_type: str, outcome: str) -> bool:
    if event_type in {EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_ACTION], EVENT_TYPE_BY_ACTION_STATE[ACTION_STATE_COMPLETED]}:
        return True
    return event_type != "review_record_created" and outcome in {REVIEW_OUTCOME_ACTION, PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED}


def _is_watch_event(event_type: str, outcome: str) -> bool:
    if event_type == EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_WATCH]:
        return True
    return event_type != "review_record_created" and outcome == REVIEW_OUTCOME_WATCH


def _has_equivalent_review_outcome_event(
    *,
    event_type: str,
    project_id: str,
    signal_id: str,
    outcome: str,
    review_record_id: str,
) -> bool:
    for event in list_project_calibration_events(event_type=event_type):
        if review_record_id and _safe_text(event.get("review_record_id")) == review_record_id:
            return True
        if (
            _safe_text(event.get("project_id")) == project_id
            and _safe_text(event.get("signal_id")) == signal_id
            and _safe_text(event.get("outcome")) == outcome
        ):
            return True
    return False


def backfill_project_calibration_events_from_review_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    skipped = 0

    for record in records:
        review_record_id = _safe_text(record.get("id"))
        if not review_record_id:
            skipped += 1
            continue

        project_id = _safe_text(record.get("project_id"))
        signal_id = _safe_text(record.get("signal_id"))
        outcome = _safe_text(record.get("outcome"))
        source_status = _safe_text(record.get("source_status"))
        item = {
            "project_id": project_id,
            "project_name": record.get("project_name"),
            "signal_id": signal_id,
            "signal_title": record.get("signal_title"),
            "verification_metadata": {"verification_status": record.get("verification_status")},
        }

        before_count = len(list_project_calibration_events())
        append_project_calibration_event(
            event_type="review_record_created",
            project_id=project_id,
            signal_id=signal_id,
            outcome=outcome,
            source_status=source_status,
            review_record_id=review_record_id,
            item=item,
        )
        outcome_event_type = event_type_for_review_outcome(outcome)
        if outcome_event_type:
            if not _has_equivalent_review_outcome_event(
                event_type=outcome_event_type,
                project_id=project_id,
                signal_id=signal_id,
                outcome=outcome,
                review_record_id=review_record_id,
            ):
                append_project_calibration_event(
                    event_type=outcome_event_type,
                    project_id=project_id,
                    signal_id=signal_id,
                    outcome=outcome,
                    source_status=source_status,
                    review_record_id=review_record_id,
                    item=item,
                )
        else:
            skipped += 1

        after_count = len(list_project_calibration_events())
        created_count = after_count - before_count
        if created_count > 0:
            created.append({"review_record_id": review_record_id, "created_count": created_count})

    return {
        "created_count": sum(int(item.get("created_count") or 0) for item in created),
        "created_items": created,
        "skipped_count": skipped,
        "record_count": len(records),
        "summary": summarize_project_calibration_events(),
    }
