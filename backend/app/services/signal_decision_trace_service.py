from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MAX_DECISION_TRACE_EVENTS = 80


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_decision_trace(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_decision_trace_event(
    *,
    event_type: str,
    actor: str,
    status_before: str | None = None,
    status_after: str | None = None,
    route: str | None = None,
    support: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "timestamp": timestamp or utc_now_iso(),
    }
    if status_before:
        event["status_before"] = status_before
    if status_after:
        event["status_after"] = status_after
    if route:
        event["route"] = route
    if support:
        event["support"] = support
    return event


def append_decision_trace_event(
    record: dict[str, Any],
    event: dict[str, Any],
) -> list[dict[str, Any]]:
    trace = normalize_decision_trace(record.get("decision_trace"))
    trace.append(event)
    if len(trace) > MAX_DECISION_TRACE_EVENTS:
        trace = trace[-MAX_DECISION_TRACE_EVENTS:]
    record["decision_trace"] = trace
    return trace


def status_event_type(new_status: str) -> str:
    normalized = (new_status or "").strip().lower()
    if normalized == "saved":
        return "operator_saved_for_later"
    if normalized == "rejected":
        return "operator_rejected"
    if normalized == "analyzed":
        return "operator_marked_processed"
    if normalized == "completed":
        return "completed_to_workspace"
    return "status_updated"


def verification_support_snapshot(verification: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(verification, dict):
        return {}

    verified_insight = verification.get("verified_insight")
    action_policy = verified_insight.get("action_policy") if isinstance(verified_insight, dict) else {}
    claims = verified_insight.get("claims") if isinstance(verified_insight, dict) else {}
    evidence = verified_insight.get("evidence") if isinstance(verified_insight, dict) else {}

    return {
        "verification_status": verification.get("verification_status")
        or (verified_insight or {}).get("status"),
        "blocked_downstream_actions": verification.get("blocked_downstream_actions")
        or (action_policy or {}).get("blocked")
        or [],
        "allowed_downstream_actions": verification.get("allowed_downstream_actions")
        or (action_policy or {}).get("allowed")
        or [],
        "claim_support_summary": verification.get("claim_support_summary")
        or (claims or {}).get("support_summary")
        or {},
        "evidence_level": (verification.get("evidence_quality") or {}).get("level")
        or (evidence or {}).get("level"),
        "evidence_pack_id": (evidence or {}).get("pack_id"),
    }
