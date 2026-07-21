from __future__ import annotations

from typing import Any

from app.services.project_calibration_event_service import (
    list_project_calibration_events,
    summarize_project_calibration_events,
)
from app.services.project_review_record_service import (
    list_project_review_records,
    summarize_project_review_records,
)
from app.services.project_takeaway_constants import (
    PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
    REVIEW_OUTCOME_ACTION,
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_OUTCOME_WATCH,
)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _top_counts(counts: dict[str, int], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"key": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if count > 0
    ]


def _recent_review_records(records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    recent = sorted(records, key=lambda item: _safe_text(item.get("reviewed_at") or item.get("updated_at")), reverse=True)
    return [
        {
            "id": record.get("id"),
            "project_id": record.get("project_id"),
            "signal_id": record.get("signal_id"),
            "signal_title": record.get("signal_title"),
            "outcome": record.get("outcome"),
            "source_type": record.get("source_type"),
            "verification_status": record.get("verification_status"),
            "confidence_label": record.get("confidence_label"),
            "blocked_downstream_actions": record.get("blocked_downstream_actions") if isinstance(record.get("blocked_downstream_actions"), list) else [],
            "reason": record.get("reason"),
            "reviewed_at": record.get("reviewed_at"),
            "updated_at": record.get("updated_at"),
        }
        for record in recent[:limit]
    ]


def _recent_calibration_events(events: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    recent = sorted(events, key=lambda item: _safe_text(item.get("created_at") or item.get("updated_at")), reverse=True)
    return [
        {
            "id": event.get("id"),
            "project_id": event.get("project_id"),
            "signal_id": event.get("signal_id"),
            "event_type": event.get("event_type"),
            "outcome": event.get("outcome"),
            "source_type": event.get("source_type"),
            "verification_status": event.get("verification_status"),
            "blocked_downstream_actions": event.get("blocked_downstream_actions") if isinstance(event.get("blocked_downstream_actions"), list) else [],
            "review_record_id": event.get("review_record_id"),
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
        }
        for event in recent[:limit]
    ]


def _build_learning_signals(
    *,
    review_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
) -> dict[str, Any]:
    actionable_count = _safe_int(review_summary.get("actionable_count"))
    watch_count = _safe_int(review_summary.get("watch_count"))
    caution_count = _safe_int(review_summary.get("rejected_or_dismissed_count"))
    blocked_count = _safe_int(review_summary.get("records_with_action_blocked")) + _safe_int(
        calibration_summary.get("events_with_action_blocked")
    )
    manual_count = _safe_int(review_summary.get("manual_record_count")) + _safe_int(
        calibration_summary.get("manual_event_count")
    )
    gate_conflict_count = _safe_int(review_summary.get("gate_conflict_record_count")) + _safe_int(
        calibration_summary.get("gate_conflict_event_count")
    )

    return {
        "actionable_count": actionable_count,
        "watch_count": watch_count,
        "caution_count": caution_count,
        "blocked_action_context_count": blocked_count,
        "manual_source_context_count": manual_count,
        "gate_conflict_context_count": gate_conflict_count,
        "has_actionable_memory": actionable_count > 0,
        "has_watch_memory": watch_count > 0 or _safe_int(calibration_summary.get("watch_event_count")) > 0,
        "has_caution_memory": caution_count > 0 or _safe_int(calibration_summary.get("rejected_or_dismissed_event_count")) > 0,
        "has_gate_risk": blocked_count > 0 or gate_conflict_count > 0,
        "has_manual_source_learning": manual_count > 0,
    }


def _build_next_focus(learning_signals: dict[str, Any], review_summary: dict[str, Any]) -> list[str]:
    if _safe_int(review_summary.get("total_records")) == 0:
        return ["Create ReviewRecords through the Project Review flow before treating this profile as meaningful."]

    focus: list[str] = []
    if learning_signals.get("has_gate_risk"):
        focus.append("Review blocked-action and gate-conflict records before treating outcomes as low-risk action memory.")
    if learning_signals.get("has_watch_memory"):
        focus.append("Review Watch outcomes for follow-up evidence before promoting them to stronger project memory.")
    if learning_signals.get("has_caution_memory"):
        focus.append("Use rejected and dismissed records as caution context, not factual evidence.")
    if learning_signals.get("has_manual_source_learning"):
        focus.append("Inspect manual-source records separately so user-provided material keeps clear provenance.")
    if not focus:
        focus.append("Maintain this profile as read-only project learning context and continue collecting review outcomes.")
    return focus


def build_project_learning_profile(
    *,
    project_id: str | None = None,
    recent_limit: int = 5,
) -> dict[str, Any]:
    review_summary = summarize_project_review_records(project_id=project_id)
    calibration_summary = summarize_project_calibration_events(project_id=project_id)
    review_records = list_project_review_records(project_id=project_id)
    calibration_events = list_project_calibration_events(project_id=project_id)
    learning_signals = _build_learning_signals(
        review_summary=review_summary,
        calibration_summary=calibration_summary,
    )

    return {
        "schema_version": 1,
        "profile_type": "project_learning_profile",
        "scope": {
            "project_id": project_id or "all_projects",
            "recent_limit": recent_limit,
        },
        "context_role": "read_only_project_learning_context",
        "evidence_boundary": "review_and_calibration_history_not_external_claim_evidence",
        "review_summary": review_summary,
        "calibration_summary": calibration_summary,
        "learning_signals": learning_signals,
        "outcome_profile": {
            "top_review_outcomes": _top_counts(review_summary.get("outcome_counts") or {}),
            "top_calibration_outcomes": _top_counts(calibration_summary.get("outcome_counts") or {}),
            "actionable_outcomes": [
                REVIEW_OUTCOME_CONFIRMED,
                REVIEW_OUTCOME_ACTION,
                PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
            ],
            "caution_outcomes": [REVIEW_OUTCOME_REJECTED, REVIEW_OUTCOME_DISMISSED],
            "watch_outcome": REVIEW_OUTCOME_WATCH,
        },
        "risk_profile": {
            "top_blocked_actions": _top_counts(review_summary.get("blocked_action_counts") or {}),
            "verification_status_mix": _top_counts(review_summary.get("verification_status_counts") or {}),
            "calibration_verification_status_mix": _top_counts(calibration_summary.get("verification_status_counts") or {}),
            "blocked_action_rate": review_summary.get("blocked_action_rate", 0),
            "unsupported_claim_count": _safe_int(review_summary.get("unsupported_claim_count"))
            + _safe_int(calibration_summary.get("unsupported_claim_count")),
            "inferred_claim_count": _safe_int(review_summary.get("inferred_claim_count"))
            + _safe_int(calibration_summary.get("inferred_claim_count")),
        },
        "source_profile": {
            "review_source_type_mix": _top_counts(review_summary.get("source_type_counts") or {}),
            "calibration_source_type_mix": _top_counts(calibration_summary.get("source_type_counts") or {}),
            "manual_record_count": review_summary.get("manual_record_count", 0),
            "manual_event_count": calibration_summary.get("manual_event_count", 0),
        },
        "recent_review_records": _recent_review_records(review_records, limit=recent_limit),
        "recent_calibration_events": _recent_calibration_events(calibration_events, limit=recent_limit),
        "next_focus": _build_next_focus(learning_signals, review_summary),
    }
