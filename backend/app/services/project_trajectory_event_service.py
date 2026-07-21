from __future__ import annotations

from typing import Any


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def derive_trajectory_risk_level(event: dict[str, Any]) -> str:
    unsupported_count = _safe_int(event.get("unsupported_claim_count"))
    inferred_count = _safe_int(event.get("inferred_claim_count"))
    blocked_actions = event.get("blocked_downstream_actions") if isinstance(event.get("blocked_downstream_actions"), list) else []
    confidence_label = _safe_text(event.get("confidence_label")).lower()
    verification_status = _safe_text(event.get("verification_status")).lower()

    if unsupported_count > 0 or blocked_actions or verification_status in {"not_verifiable", "weakly_supported"}:
        return "high"
    if inferred_count > 0 or confidence_label == "low" or verification_status == "partially_verified":
        return "medium"
    return "low"


def derive_trajectory_signal_type(event: dict[str, Any], *, event_kind: str) -> str:
    if bool(event.get("is_manual_source")) or event.get("source_type") == "manual_upload":
        return "manual_judgment"
    if derive_trajectory_risk_level(event) != "low":
        return "verification_risk"
    if event_kind == "calibration":
        return "calibration_learning"
    return "review_decision"


def with_trajectory_derivatives(event: dict[str, Any], *, event_kind: str) -> dict[str, Any]:
    risk_level = derive_trajectory_risk_level(event)
    return {
        **event,
        "risk_level": risk_level,
        "trajectory_signal_type": derive_trajectory_signal_type({**event, "risk_level": risk_level}, event_kind=event_kind),
    }


def trajectory_event_from_review_record(record: dict[str, Any]) -> dict[str, Any]:
    event = {
        "id": record.get("id") or "",
        "event_kind": "review",
        "timestamp": record.get("reviewed_at") or record.get("updated_at") or record.get("created_at") or "",
        "project_id": record.get("project_id") or "",
        "project_name": record.get("project_name") or "",
        "signal_id": record.get("signal_id") or "",
        "signal_title": record.get("signal_title") or "",
        "outcome": record.get("outcome") or "review_recorded",
        "reason": record.get("reason") or "",
        "source_type": record.get("source_type") or "signal",
        "manual_session_id": record.get("manual_session_id") or "",
        "is_manual_source": bool(record.get("is_manual_source")) or record.get("source_type") == "manual_upload",
        "upload_reason": record.get("upload_reason") or "",
        "intended_use": record.get("intended_use") or "",
        "cognitive_layer": record.get("cognitive_layer") or "unclassified",
        "verification_status": record.get("verification_status") or "unknown",
        "confidence_label": record.get("confidence_label") or "",
        "confidence_score": record.get("confidence_score"),
        "unsupported_claim_count": _safe_int(record.get("unsupported_claim_count")),
        "inferred_claim_count": _safe_int(record.get("inferred_claim_count")),
        "blocked_downstream_actions": record.get("blocked_downstream_actions") if isinstance(record.get("blocked_downstream_actions"), list) else [],
        "deep_project_match_required": bool(record.get("deep_project_match_required")),
        "deep_project_match_status": record.get("deep_project_match_status") or "",
        "deep_project_match_posture": record.get("deep_project_match_posture") or "",
        "deep_project_match_review_note": record.get("deep_project_match_review_note") or "",
        "deep_project_match_review_note_effect": record.get("deep_project_match_review_note_effect") or "",
        "deep_project_match_matched_projects": record.get("deep_project_match_matched_projects")
        if isinstance(record.get("deep_project_match_matched_projects"), list)
        else [],
        "deep_project_match_relevant_modules": record.get("deep_project_match_relevant_modules")
        if isinstance(record.get("deep_project_match_relevant_modules"), list)
        else [],
        "deep_project_match_match_type": record.get("deep_project_match_match_type") or "",
        "deep_project_match_evidence_boundary": record.get("deep_project_match_evidence_boundary") or "",
        "deep_project_match_downstream_posture": record.get("deep_project_match_downstream_posture") or "",
    }
    return with_trajectory_derivatives(event, event_kind="review")


def trajectory_event_from_calibration_event(event: dict[str, Any]) -> dict[str, Any]:
    trajectory_event = {
        "id": event.get("id") or "",
        "event_kind": "calibration",
        "timestamp": event.get("created_at") or event.get("updated_at") or "",
        "project_id": event.get("project_id") or "",
        "project_name": event.get("project_name") or "",
        "signal_id": event.get("signal_id") or "",
        "signal_title": event.get("signal_title") or "",
        "outcome": event.get("event_type") or event.get("outcome") or "calibration_event",
        "reason": "",
        "followup_result": event.get("followup_result") or "",
        "review_note": event.get("review_note") or "",
        "evidence_update": event.get("evidence_update") or "",
        "next_review_date": event.get("next_review_date") or "",
        "expected_outcome": event.get("expected_outcome") or "",
        "source_type": event.get("source_type") or "signal",
        "manual_session_id": event.get("manual_session_id") or "",
        "is_manual_source": bool(event.get("is_manual_source")) or event.get("source_type") == "manual_upload",
        "upload_reason": event.get("upload_reason") or "",
        "intended_use": event.get("intended_use") or "",
        "cognitive_layer": event.get("cognitive_layer") or "unclassified",
        "verification_status": event.get("verification_status") or "unknown",
        "confidence_label": event.get("confidence_label") or "",
        "confidence_score": event.get("confidence_score"),
        "unsupported_claim_count": _safe_int(event.get("unsupported_claim_count")),
        "inferred_claim_count": _safe_int(event.get("inferred_claim_count")),
        "blocked_downstream_actions": event.get("blocked_downstream_actions") if isinstance(event.get("blocked_downstream_actions"), list) else [],
        "deep_project_match_required": bool(event.get("deep_project_match_required")),
        "deep_project_match_status": event.get("deep_project_match_status") or "",
        "deep_project_match_posture": event.get("deep_project_match_posture") or "",
        "deep_project_match_review_note": event.get("deep_project_match_review_note") or "",
        "deep_project_match_review_note_effect": event.get("deep_project_match_review_note_effect") or "",
        "deep_project_match_matched_projects": event.get("deep_project_match_matched_projects")
        if isinstance(event.get("deep_project_match_matched_projects"), list)
        else [],
        "deep_project_match_relevant_modules": event.get("deep_project_match_relevant_modules")
        if isinstance(event.get("deep_project_match_relevant_modules"), list)
        else [],
        "deep_project_match_match_type": event.get("deep_project_match_match_type") or "",
        "deep_project_match_evidence_boundary": event.get("deep_project_match_evidence_boundary") or "",
        "deep_project_match_downstream_posture": event.get("deep_project_match_downstream_posture") or "",
    }
    return with_trajectory_derivatives(trajectory_event, event_kind="calibration")


def _increment_count(counts: dict[str, int], key: str) -> None:
    normalized = _safe_text(key) or "unknown"
    counts[normalized] = counts.get(normalized, 0) + 1


def _top_counts(counts: dict[str, int], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[:limit]
    ]


def summarize_trajectory_events(items: list[dict[str, Any]]) -> dict[str, Any]:
    risk_mix: dict[str, int] = {}
    signal_type_mix: dict[str, int] = {}
    event_kind_mix: dict[str, int] = {}
    source_type_mix: dict[str, int] = {}
    manual_upload_reason_mix: dict[str, int] = {}
    manual_intended_use_mix: dict[str, int] = {}
    manual_cognitive_layer_mix: dict[str, int] = {}
    project_mix: dict[str, dict[str, Any]] = {}
    manual_count = 0
    risk_count = 0
    latest_timestamp = ""

    for item in items:
        risk_level = _safe_text(item.get("risk_level")) or "low"
        signal_type = _safe_text(item.get("trajectory_signal_type")) or "unknown"
        event_kind = _safe_text(item.get("event_kind")) or "unknown"
        source_type = _safe_text(item.get("source_type")) or "signal"
        project_id = _safe_text(item.get("project_id")) or "unknown"
        project_name = _safe_text(item.get("project_name")) or project_id
        timestamp = _safe_text(item.get("timestamp"))

        _increment_count(risk_mix, risk_level)
        _increment_count(signal_type_mix, signal_type)
        _increment_count(event_kind_mix, event_kind)
        _increment_count(source_type_mix, source_type)

        is_manual_source = bool(item.get("is_manual_source")) or source_type == "manual_upload"
        if is_manual_source:
            manual_count += 1
            _increment_count(manual_upload_reason_mix, item.get("upload_reason"))
            _increment_count(manual_intended_use_mix, item.get("intended_use"))
            _increment_count(manual_cognitive_layer_mix, item.get("cognitive_layer") or "unclassified")
        if risk_level != "low":
            risk_count += 1
        if timestamp and timestamp > latest_timestamp:
            latest_timestamp = timestamp

        project_summary = project_mix.get(project_id) or {
            "project_id": project_id,
            "project_name": project_name,
            "event_count": 0,
            "manual_count": 0,
            "risk_count": 0,
            "watch_count": 0,
            "action_count": 0,
            "latest_timestamp": "",
        }
        project_summary["event_count"] += 1
        if is_manual_source:
            project_summary["manual_count"] += 1
        if risk_level != "low":
            project_summary["risk_count"] += 1
        outcome = _safe_text(item.get("outcome")).lower()
        if "watch" in outcome:
            project_summary["watch_count"] += 1
        if "action" in outcome or outcome == "confirmed":
            project_summary["action_count"] += 1
        if timestamp and timestamp > project_summary["latest_timestamp"]:
            project_summary["latest_timestamp"] = timestamp
            project_summary["project_name"] = project_name
        project_mix[project_id] = project_summary

    return {
        "total_events": len(items),
        "manual_count": manual_count,
        "risk_count": risk_count,
        "latest_timestamp": latest_timestamp,
        "risk_mix": risk_mix,
        "signal_type_mix": signal_type_mix,
        "event_kind_mix": event_kind_mix,
        "source_type_mix": source_type_mix,
        "manual_intent_summary": {
            "upload_reason_mix": _top_counts(manual_upload_reason_mix),
            "intended_use_mix": _top_counts(manual_intended_use_mix),
            "cognitive_layer_mix": _top_counts(manual_cognitive_layer_mix),
        },
        "project_mix": sorted(project_mix.values(), key=lambda project: (project["event_count"], str(project["latest_timestamp"])), reverse=True),
    }


def matches_trajectory_filter(item: dict[str, Any], key: str, expected: Any) -> bool:
    if not isinstance(expected, str) or not expected.strip():
        return True
    if key == "risk_level" and _safe_text(expected).lower() in {"risk", "non_low"}:
        return _safe_text(item.get(key)).lower() != "low"
    return _safe_text(item.get(key)).lower() == _safe_text(expected).lower()


def filter_trajectory_events(
    items: list[dict[str, Any]],
    *,
    event_kind: str | None = None,
    risk_level: str | None = None,
    trajectory_signal_type: str | None = None,
    source_type: str | None = None,
) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if matches_trajectory_filter(item, "event_kind", event_kind)
        and matches_trajectory_filter(item, "risk_level", risk_level)
        and matches_trajectory_filter(item, "trajectory_signal_type", trajectory_signal_type)
        and matches_trajectory_filter(item, "source_type", source_type)
    ]


def build_trajectory_events_response(
    review_records: list[dict[str, Any]],
    calibration_events: list[dict[str, Any]],
    *,
    event_kind: str | None = None,
    risk_level: str | None = None,
    trajectory_signal_type: str | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    items = [
        *[trajectory_event_from_review_record(record) for record in review_records],
        *[trajectory_event_from_calibration_event(event) for event in calibration_events],
    ]
    items = filter_trajectory_events(
        items,
        event_kind=event_kind,
        risk_level=risk_level,
        trajectory_signal_type=trajectory_signal_type,
        source_type=source_type,
    )
    items = sorted(items, key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return {
        "items": items,
        "count": len(items),
        "summary": summarize_trajectory_events(items),
    }
