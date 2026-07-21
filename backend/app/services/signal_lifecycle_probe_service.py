from __future__ import annotations

from typing import Any


PROBE_ADAPTER_NAME = "signal_lifecycle_probe_legacy_adapter_v0"
TRAJECTORY_CONTRACT_VERSION = "trajectory_view_contract_v0"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _verification_metadata(signal: dict[str, Any]) -> dict[str, Any]:
    verification = signal.get("verification")
    if isinstance(verification, dict):
        return verification
    policy_metadata = signal.get("policy_metadata")
    if isinstance(policy_metadata, dict) and isinstance(policy_metadata.get("verification"), dict):
        return policy_metadata["verification"]
    return {}


def _claim_support_summary(verification: dict[str, Any]) -> dict[str, Any]:
    summary = verification.get("claim_support_summary")
    if isinstance(summary, dict):
        return summary
    verified_insight = verification.get("verified_insight")
    if isinstance(verified_insight, dict):
        claims = verified_insight.get("claims")
        if isinstance(claims, dict) and isinstance(claims.get("support_summary"), dict):
            return claims["support_summary"]
    return {}


def _action_policy(verification: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    verified_insight = verification.get("verified_insight")
    action_policy = verified_insight.get("action_policy") if isinstance(verified_insight, dict) else {}
    action_policy = action_policy if isinstance(action_policy, dict) else {}
    allowed = verification.get("allowed_downstream_actions") or action_policy.get("allowed")
    blocked = verification.get("blocked_downstream_actions") or action_policy.get("blocked")
    return _as_list(allowed), _as_list(blocked)


def _event_timestamp(trace: list[dict[str, Any]], event_types: set[str]) -> str:
    for event in reversed(trace):
        if _safe_text(event.get("event_type")) in event_types:
            return _safe_text(event.get("timestamp"))
    return ""


def _event_actor(trace: list[dict[str, Any]], event_types: set[str]) -> str:
    for event in reversed(trace):
        if _safe_text(event.get("event_type")) in event_types:
            return _safe_text(event.get("actor"))
    return ""


def _direct_events(lifecycle_events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [
        event
        for event in lifecycle_events
        if isinstance(event, dict) and _safe_text(event.get("event_type")) == event_type
    ]


def _latest_direct_event(lifecycle_events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    events = _direct_events(lifecycle_events, event_type)
    if not events:
        return {}
    return sorted(
        events,
        key=lambda event: _safe_text(event.get("event_time") or event.get("recorded_at")),
    )[-1]


def _direct_event_timestamp(event: dict[str, Any]) -> str:
    return _safe_text(event.get("event_time") or event.get("recorded_at"))


def _direct_event_actor(event: dict[str, Any]) -> str:
    actor = event.get("actor")
    if not isinstance(actor, dict):
        return ""
    actor_type = _safe_text(actor.get("type"))
    actor_id = _safe_text(actor.get("id"))
    if actor_type and actor_id:
        return f"{actor_type}:{actor_id}"
    return actor_id or actor_type


def _event_support(event: dict[str, Any]) -> dict[str, Any]:
    support = event.get("support")
    return support if isinstance(support, dict) else {}


def _has_insight(signal: dict[str, Any]) -> bool:
    return any(
        _safe_text(signal.get(key))
        for key in (
            "why_it_matters",
            "insight",
            "relevance_to_projects",
            "relevance_to_career",
            "synthesized_insight",
            "strategy",
        )
    )


def _status(signal: dict[str, Any]) -> str:
    return _safe_text(signal.get("status")).lower() or "pending"


def _signal_id(signal: dict[str, Any]) -> str:
    return _safe_text(signal.get("signal_id") or signal.get("id") or signal.get("manual_session_id"))


def _step(
    *,
    step_id: str,
    label: str,
    state: str,
    provenance: str,
    source: str,
    detail: str,
    timestamp: str = "",
    actor: str = "",
    support: dict[str, Any] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "label": label,
        "state": state,
        "provenance": provenance,
        "source": source,
        "timestamp": timestamp,
        "actor": actor,
        "detail": detail,
        "support": support or {},
        "gaps": gaps or [],
    }


def build_signal_lifecycle_probe(
    signal: dict[str, Any],
    *,
    review_records: list[dict[str, Any]] | None = None,
    calibration_events: list[dict[str, Any]] | None = None,
    lifecycle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a temporary trajectory contract from legacy/current storage.

    This is intentionally a probe adapter, not the durable lifecycle source of truth.
    """

    review_records = review_records or []
    calibration_events = calibration_events or []
    lifecycle_events = [event for event in lifecycle_events or [] if isinstance(event, dict)]
    trace = [event for event in _as_list(signal.get("decision_trace")) if isinstance(event, dict)]
    verification = _verification_metadata(signal)
    allowed_actions, blocked_actions = _action_policy(verification)
    claim_support_summary = _claim_support_summary(verification)
    status = _status(signal)
    is_manual = bool(signal.get("is_manual")) or _safe_text(signal.get("source")) == "manual"
    insight_present = _has_insight(signal)
    workspace_saved = bool(signal.get("workspace_saved") or signal.get("completion_saved") or signal.get("workspace_file_name"))
    project_links = _as_list(signal.get("project_links")) or _as_list(signal.get("subscription_project_links"))

    direct_fields: list[str] = []
    service_outputs_not_persisted: list[str] = []
    architecture_gaps: list[str] = []

    def direct(path: str) -> None:
        if path not in direct_fields:
            direct_fields.append(path)

    def service_gap(item: str) -> None:
        if item not in service_outputs_not_persisted:
            service_outputs_not_persisted.append(item)

    def architecture_gap(item: str) -> None:
        if item not in architecture_gaps:
            architecture_gaps.append(item)

    direct("signal.signal_id")
    direct("signal.title")
    if signal.get("published_at") or signal.get("collected_at"):
        direct("signal.published_at_or_collected_at")
    if trace:
        direct("signal.decision_trace")
    if lifecycle_events:
        direct("signal_lifecycle.events")
    if not trace and not lifecycle_events:
        architecture_gap("No authoritative decision_trace/lifecycle event history is attached to this signal.")

    insight_event = _latest_direct_event(lifecycle_events, "insight_generated")
    verification_event = _latest_direct_event(lifecycle_events, "verification_completed")
    status_event = _latest_direct_event(lifecycle_events, "signal_status_changed")
    workspace_event = _latest_direct_event(lifecycle_events, "workspace_completed")
    project_candidate_events = _direct_events(lifecycle_events, "project_candidate_created")
    project_attachment_events = _direct_events(lifecycle_events, "project_review_attached")

    steps = [
        _step(
            step_id="signal_ingested",
            label="Signal Ingested",
            state="observed",
            provenance="direct",
            source="signal_fields",
            timestamp=_safe_text(signal.get("collected_at") or signal.get("published_at")),
            detail=_safe_text(signal.get("source")) or ("manual upload" if is_manual else "source recorded"),
            support={
                "signal_id": _signal_id(signal),
                "title": _safe_text(signal.get("title")),
                "source": _safe_text(signal.get("source")),
            },
        )
    ]

    if insight_present or _safe_text(signal.get("analysis_status")) == "completed":
        direct("signal.insight_fields")
        insight_source = "signal_lifecycle_event" if insight_event else "signal_or_manual_analysis_fields"
        steps.append(
            _step(
                step_id="insight_generated",
                label="Insight Generated",
                state="completed",
                provenance="direct",
                source=insight_source,
                timestamp=_direct_event_timestamp(insight_event) or _event_timestamp(trace, {"insight_generated"}),
                actor=_direct_event_actor(insight_event) or _event_actor(trace, {"insight_generated"}),
                detail=_safe_text(signal.get("generation_mode") or signal.get("insight_status") or "insight available"),
                support=_event_support(insight_event) or {
                    "provider_used": _safe_text(signal.get("provider_used")),
                    "model_used": _safe_text(signal.get("model_used")),
                    "analysis_status": _safe_text(signal.get("analysis_status")),
                },
                gaps=[] if insight_event or trace else ["Insight generation timestamp is not persisted as a lifecycle event."],
            )
        )
        if not insight_event and not trace:
            service_gap("Insight generation can be inferred from persisted fields, but generation transition metadata is incomplete.")
    else:
        steps.append(
            _step(
                step_id="insight_generated",
                label="Insight Generated",
                state="not_reached",
                provenance="missing",
                source="signal_fields",
                detail="No insight or completed manual analysis is attached.",
                gaps=["Cannot render an insight-generation transition from current storage."],
            )
        )

    if verification:
        direct("signal.verification")
        verification_status = _safe_text(verification.get("verification_status"))
        verified_insight = verification.get("verified_insight")
        if not verification_status and isinstance(verified_insight, dict):
            verification_status = _safe_text(verified_insight.get("status"))
        steps.append(
            _step(
                step_id="verification_gate",
                label="Evidence / Verification Gate",
                state="completed",
                provenance="direct",
                source="signal_lifecycle_event" if verification_event else "verification_metadata",
                timestamp=_direct_event_timestamp(verification_event),
                actor=_direct_event_actor(verification_event),
                detail=verification_status or "verification metadata attached",
                support=_event_support(verification_event) or {
                    "verification_status": verification_status,
                    "claim_support_summary": claim_support_summary,
                    "allowed_downstream_actions": allowed_actions,
                    "blocked_downstream_actions": blocked_actions,
                },
                gaps=[] if verification_event or trace else ["Verification completion timestamp is not persisted as a lifecycle event."],
            )
        )
        if not verification_event and not trace:
            service_gap("Verification services produce metadata, but the verification transition timestamp/actor is not persisted.")
    else:
        steps.append(
            _step(
                step_id="verification_gate",
                label="Evidence / Verification Gate",
                state="unknown",
                provenance="missing",
                source="verification_metadata",
                detail="No verification metadata is attached.",
                gaps=["Cannot tell whether verification was skipped, unavailable, or not yet run."],
            )
        )
        architecture_gap("Missing verification metadata cannot distinguish unverified legacy paths from not-yet-reviewed signals.")

    decision_event_types = {
        "operator_saved_for_later",
        "operator_rejected",
        "operator_marked_processed",
        "completed_to_workspace",
    }
    decision_timestamp = _event_timestamp(trace, decision_event_types)
    decision_actor = _event_actor(trace, decision_event_types)
    if status in {"saved", "analyzed", "completed", "rejected"}:
        direct("signal.status")
        direct_status_timestamp = _direct_event_timestamp(status_event)
        provenance = "direct" if direct_status_timestamp or decision_timestamp else "inferred"
        gaps = [] if direct_status_timestamp or decision_timestamp else ["Status exists, but the transition event, actor, and timestamp are missing."]
        if not direct_status_timestamp and not decision_timestamp:
            architecture_gap("Signal status is stored, but status transition history is not authoritative for legacy/current records.")
        steps.append(
            _step(
                step_id="signal_decision",
                label="Signal-Level Decision",
                state=status,
                provenance=provenance,
                source="signal_lifecycle_event" if direct_status_timestamp else ("decision_trace" if decision_timestamp else "signal.status"),
                timestamp=direct_status_timestamp or decision_timestamp,
                actor=_direct_event_actor(status_event) or decision_actor,
                detail=f"Signal is currently {status}.",
                support=_event_support(status_event) or {"saved_reason": _safe_text(signal.get("saved_reason"))},
                gaps=gaps,
            )
        )
    else:
        steps.append(
            _step(
                step_id="signal_decision",
                label="Signal-Level Decision",
                state="waiting",
                provenance="inferred",
                source="signal.status",
                detail="Signal is waiting for an operator decision.",
                gaps=["No durable lifecycle event marks the current wait state."],
            )
        )

    if workspace_saved or status == "completed":
        direct("signal.workspace_saved")
        direct_workspace_timestamp = _direct_event_timestamp(workspace_event)
        provenance = "direct" if direct_workspace_timestamp or workspace_saved else "inferred"
        gaps = []
        if not workspace_saved:
            gaps.append("Completed status exists without workspace_saved metadata.")
            architecture_gap("Completed status and Workspace persistence are not guaranteed to stay aligned.")
        if not direct_workspace_timestamp and not _safe_text(signal.get("workspace_saved_at")):
            gaps.append("Workspace saved timestamp is missing from the signal payload.")
        steps.append(
            _step(
                step_id="workspace_completion",
                label="Workspace Completion",
                state="completed",
                provenance=provenance,
                source="signal_lifecycle_event" if direct_workspace_timestamp else ("workspace_metadata" if workspace_saved else "signal.status"),
                timestamp=direct_workspace_timestamp or _safe_text(signal.get("workspace_saved_at")) or _event_timestamp(trace, {"completed_to_workspace"}),
                actor=_direct_event_actor(workspace_event) or _event_actor(trace, {"completed_to_workspace"}),
                detail="Workspace artifact is linked." if workspace_saved else "Completion is inferred from status.",
                support=_event_support(workspace_event) or {"workspace_file_name": _safe_text(signal.get("workspace_file_name"))},
                gaps=gaps,
            )
        )
    else:
        steps.append(
            _step(
                step_id="workspace_completion",
                label="Workspace Completion",
                state="not_reached",
                provenance="direct",
                source="workspace_metadata",
                detail="No workspace completion metadata is attached.",
            )
        )

    if project_candidate_events:
        direct("signal_lifecycle.project_candidate_created")
        project_refs = [
            event.get("project_ref")
            for event in project_candidate_events
            if isinstance(event.get("project_ref"), dict)
        ]
        steps.append(
            _step(
                step_id="project_fanout",
                label="Project Fan-out",
                state="attached",
                provenance="direct",
                source="signal_lifecycle_event",
                timestamp=max([_direct_event_timestamp(event) for event in project_candidate_events] or [""]),
                actor=_direct_event_actor(project_candidate_events[-1]),
                detail=f"{len(project_candidate_events)} project candidate event(s).",
                support={"project_refs": project_refs},
            )
        )
    elif project_attachment_events:
        direct("signal_lifecycle.project_review_attached")
        project_refs = [
            event.get("project_ref")
            for event in project_attachment_events
            if isinstance(event.get("project_ref"), dict)
        ]
        steps.append(
            _step(
                step_id="project_fanout",
                label="Project Fan-out",
                state="attached",
                provenance="derived",
                source="derived_lifecycle_event",
                timestamp=max([_direct_event_timestamp(event) for event in project_attachment_events] or [""]),
                actor=_direct_event_actor(project_attachment_events[-1]),
                detail=f"{len(project_attachment_events)} derived project attachment event(s).",
                support={"project_refs": project_refs},
                gaps=["Project attachments are derived from project-side records; signal-owned fan-out creation may still be absent."],
            )
        )
        service_gap("Project review/calibration records are exposed as derived lifecycle attachments, not signal-owned mutation history.")
    elif review_records or calibration_events:
        direct("project_review_records")
        if calibration_events:
            direct("project_calibration_events")
        steps.append(
            _step(
                step_id="project_fanout",
                label="Project Fan-out",
                state="attached",
                provenance="derived",
                source="project_review_records_and_calibration_events",
                timestamp=max(
                    [_safe_text(item.get("reviewed_at") or item.get("created_at") or item.get("updated_at")) for item in review_records + calibration_events]
                    or [""]
                ),
                detail=f"{len(review_records)} review record(s), {len(calibration_events)} calibration event(s).",
                support={
                    "review_record_ids": [_safe_text(item.get("id")) for item in review_records],
                    "calibration_event_ids": [_safe_text(item.get("id")) for item in calibration_events],
                    "project_ids": sorted(
                        {
                            _safe_text(item.get("project_id"))
                            for item in review_records + calibration_events
                            if _safe_text(item.get("project_id"))
                        }
                    ),
                },
                gaps=["Candidate creation event may be absent when only review/calibration records are available."],
            )
        )
        service_gap("Project trajectory can be assembled from review/calibration services, but fan-out creation is not a single lifecycle transition.")
    elif project_links:
        direct("signal.project_links")
        steps.append(
            _step(
                step_id="project_fanout",
                label="Project Fan-out",
                state="possible",
                provenance="inferred",
                source="signal.project_links",
                detail=f"{len(project_links)} project relevance link(s) exist, but no review records are attached.",
                support={"project_links_count": len(project_links)},
                gaps=["Project relevance links are not the same as Project Takeaway candidate lifecycle events."],
            )
        )
        architecture_gap("Project relevance links do not prove Project Takeaway candidate creation or review outcome.")
    else:
        steps.append(
            _step(
                step_id="project_fanout",
                label="Project Fan-out",
                state="not_reached",
                provenance="missing",
                source="project_records",
                detail="No project review, calibration, or relevance-link data is attached.",
            )
        )

    attached_outcomes = [
        _safe_text(
            (event.get("project_ref") if isinstance(event.get("project_ref"), dict) else {}).get("outcome")
            or (event.get("state") if isinstance(event.get("state"), dict) else {}).get("after")
        )
        for event in project_attachment_events
        if _safe_text(
            (event.get("project_ref") if isinstance(event.get("project_ref"), dict) else {}).get("outcome")
            or (event.get("state") if isinstance(event.get("state"), dict) else {}).get("after")
        )
    ]
    outcomes = attached_outcomes or [
        _safe_text(item.get("outcome") or item.get("review_outcome") or item.get("event_type"))
        for item in review_records + calibration_events
        if _safe_text(item.get("outcome") or item.get("review_outcome") or item.get("event_type"))
    ]
    if outcomes:
        outcome_source = "derived_lifecycle_event" if attached_outcomes else "project_review_records_and_calibration_events"
        steps.append(
            _step(
                step_id="project_outcomes",
                label="Project Outcomes",
                state="recorded",
                provenance="derived",
                source=outcome_source,
                detail=", ".join(outcomes[:4]),
                support={"outcomes": outcomes},
                gaps=[
                    "Derived outcome attachments mirror project-side records; project services remain the source of truth."
                ]
                if attached_outcomes
                else ["Outcomes are project-side records, not signal-owned lifecycle events yet."],
            )
        )
        if not attached_outcomes:
            architecture_gap("Signal-owned lifecycle history cannot yet show project outcomes without joining project-side records.")
    else:
        steps.append(
            _step(
                step_id="project_outcomes",
                label="Project Outcomes",
                state="not_reached",
                provenance="missing",
                source="project_records",
                detail="No project outcomes are attached.",
            )
        )

    return {
        "adapter": PROBE_ADAPTER_NAME,
        "contract_version": TRAJECTORY_CONTRACT_VERSION,
        "authoritative": False,
        "signal_id": _signal_id(signal),
        "title": _safe_text(signal.get("title")),
        "status": status,
        "is_manual": is_manual,
        "steps": steps,
        "gap_report": {
            "direct_fields": direct_fields,
            "service_outputs_not_persisted": service_outputs_not_persisted,
            "architecture_gaps": architecture_gaps,
        },
        "project_context": {
            "review_records_count": len(review_records),
            "calibration_events_count": len(calibration_events),
        },
    }
