from __future__ import annotations

from typing import Any


DEFAULT_RELATED_EVENT_LIMIT = 20


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_related_event(record: dict[str, Any], event: dict[str, Any]) -> bool:
    project_id = _safe_text(record.get("project_id"))
    signal_id = _safe_text(record.get("signal_id"))
    return bool(
        project_id
        and signal_id
        and _safe_text(event.get("project_id")) == project_id
        and _safe_text(event.get("signal_id")) == signal_id
    )


def _project_calibration_event(
    event: dict[str, Any],
    *,
    review_record_id: str,
) -> dict[str, Any]:
    event_review_record_id = _safe_text(event.get("review_record_id"))
    return {
        "id": event.get("id"),
        "event_type": event.get("event_type"),
        "outcome": event.get("outcome"),
        "source_status": event.get("source_status"),
        "review_record_id": event.get("review_record_id"),
        "is_current_review_record_event": bool(
            review_record_id and event_review_record_id == review_record_id
        ),
        "created_at": event.get("created_at"),
        "updated_at": event.get("updated_at"),
    }


def _event_sort_key(event: dict[str, Any]) -> tuple[bool, str, str]:
    return (
        bool(event.get("is_current_review_record_event")),
        _safe_text(event.get("updated_at") or event.get("created_at")),
        _safe_text(event.get("id")),
    )


def build_review_record_lineage_projection(
    record: dict[str, Any],
    calibration_events: list[dict[str, Any]],
    *,
    related_event_limit: int = DEFAULT_RELATED_EVENT_LIMIT,
) -> dict[str, Any]:
    """Project related audit events without mutating canonical records."""

    review_record_id = _safe_text(record.get("id"))
    limit = max(0, int(related_event_limit))
    projected_events = [
        _project_calibration_event(event, review_record_id=review_record_id)
        for event in calibration_events
        if isinstance(event, dict) and _is_related_event(record, event)
    ]
    related_events = sorted(projected_events, key=_event_sort_key, reverse=True)[:limit]
    matching_review_record_event_count = sum(
        1
        for event in related_events
        if review_record_id
        and _safe_text(event.get("review_record_id")) == review_record_id
    )

    return {
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
    }
