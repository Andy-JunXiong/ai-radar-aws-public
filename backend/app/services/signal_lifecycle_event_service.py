from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.model_provenance_service import normalize_model_provenance
from app.services.verification_metadata_reader import (
    get_allowed_downstream_actions,
    get_blocked_downstream_actions,
    get_claim_support_summary,
    get_confidence_label,
    get_confidence_score,
    get_model_provenance,
    get_verification_status,
)


SCHEMA_VERSION = 1
LIFECYCLE_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "signal_lifecycle"
LIFECYCLE_S3_PREFIX = os.getenv("SIGNAL_LIFECYCLE_S3_PREFIX") or "signal_lifecycle"
HARD_ENFORCEMENT_CANDIDATE_PATH = "/signals/update-status"
HARD_ENFORCEMENT_CANDIDATE_EVENT_TYPE = "signal_status_changed"
HARD_ENFORCEMENT_FLAG_ENV = "AI_RADAR_SIGNAL_STATUS_HARD_ENFORCEMENT"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_generate_insight_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str = "",
    status_after: str = "analyzed",
    verification: dict[str, Any] | None = None,
    produced_by_model: dict[str, Any] | None = None,
    preexisting_fingerprint: str = "",
    generated_fingerprint: str = "",
    stored_fingerprint: str = "",
    fingerprint_changed: bool | None = None,
    event_time: str | None = None,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    event_time = event_time or utc_now_iso()
    recorded_at = recorded_at or event_time
    verification_metadata = verification if isinstance(verification, dict) else {}
    model_provenance = _model_provenance_reference(produced_by_model, verification_metadata)

    base = _base_event(
        signal_id=signal_id,
        event_time=event_time,
        recorded_at=recorded_at,
        source_record_family=source_record_family,
        source_record_id=source_record_id,
        status_before=status_before,
        status_after=status_after,
    )
    insight_event = {
        **base,
        "event_type": "insight_generated",
        "model_provenance_ref": model_provenance,
        "support": _fingerprint_support(
            preexisting_fingerprint=preexisting_fingerprint,
            generated_fingerprint=generated_fingerprint,
            stored_fingerprint=stored_fingerprint,
            fingerprint_changed=fingerprint_changed,
        ),
    }
    insight_event["event_id"] = _event_id(insight_event)

    events = [insight_event]
    if verification_metadata:
        verification_event = {
            **base,
            "event_type": "verification_completed",
            "support": build_verification_support_snapshot(verification_metadata),
            "model_provenance_ref": model_provenance,
        }
        verification_event["event_id"] = _event_id(verification_event)
        events.append(verification_event)

    return events


def build_signal_completion_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str = "",
    status_after: str = "completed",
    verification: dict[str, Any] | None = None,
    workspace_file_name: str = "",
    workspace_saved_at: str = "",
    project_improvements: list[dict[str, Any]] | None = None,
    event_time: str | None = None,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    event_time = event_time or utc_now_iso()
    recorded_at = recorded_at or event_time
    verification_metadata = verification if isinstance(verification, dict) else {}

    base = _base_event(
        signal_id=signal_id,
        event_time=event_time,
        recorded_at=recorded_at,
        source_record_family=source_record_family,
        source_record_id=source_record_id,
        status_before=status_before,
        status_after=status_after,
        route="/signals/complete",
    )
    completion_event = {
        **base,
        "event_type": "workspace_completed",
        "support": _completion_support(
            workspace_file_name=workspace_file_name,
            workspace_saved_at=workspace_saved_at,
            project_improvements=project_improvements,
            verification=verification_metadata,
        ),
    }
    completion_event["event_id"] = _event_id(completion_event)

    events = [completion_event]
    for improvement in project_improvements or []:
        if not isinstance(improvement, dict):
            continue

        project_event = {
            **base,
            "event_type": "project_candidate_created",
            "project_ref": {
                "project_id": str(improvement.get("project_id") or "").strip(),
                "record_family": "project_improvement",
                "record_id": _project_record_id(improvement),
                "outcome": str(improvement.get("status") or "").strip(),
            },
            "support": _project_candidate_support(improvement),
            "model_provenance_ref": _model_provenance_reference(
                improvement.get("produced_by_model") if isinstance(improvement.get("produced_by_model"), dict) else None,
                improvement.get("verification_metadata") if isinstance(improvement.get("verification_metadata"), dict) else None,
            ),
        }
        project_event["event_id"] = _event_id(project_event)
        events.append(project_event)

    return events


def build_signal_status_change_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str = "",
    status_after: str = "",
    saved_reason: str | None = None,
    decision_trace_event: str = "",
    updated_keys: list[str] | None = None,
    event_time: str | None = None,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    event_time = event_time or utc_now_iso()
    recorded_at = recorded_at or event_time
    base = _base_event(
        signal_id=signal_id,
        event_time=event_time,
        recorded_at=recorded_at,
        source_record_family=source_record_family,
        source_record_id=source_record_id,
        status_before=status_before,
        status_after=status_after,
        route="/signals/update-status",
    )
    event = {
        **base,
        "event_type": "signal_status_changed",
        "support": _status_change_support(
            saved_reason=saved_reason,
            decision_trace_event=decision_trace_event,
            updated_keys=updated_keys,
        ),
    }
    event["event_id"] = _event_id(event)
    return [event]


def build_project_review_attached_events(
    *,
    signal_id: str,
    review_records: list[dict[str, Any]] | None = None,
    calibration_events: list[dict[str, Any]] | None = None,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    """Build non-persisted lifecycle attachments from project-side records."""

    recorded_at = recorded_at or utc_now_iso()
    events: list[dict[str, Any]] = []

    for record in review_records or []:
        if not isinstance(record, dict):
            continue
        event = _project_attachment_event(
            signal_id=signal_id,
            record=record,
            source_record_family="project_review_record",
            route="project_review_records",
            event_time=_safe_text(record.get("reviewed_at") or record.get("updated_at") or record.get("created_at")),
            recorded_at=recorded_at,
            outcome=_safe_text(record.get("outcome") or record.get("review_outcome")),
        )
        if event:
            events.append(event)

    for event_record in calibration_events or []:
        if not isinstance(event_record, dict):
            continue
        event = _project_attachment_event(
            signal_id=signal_id,
            record=event_record,
            source_record_family="project_calibration_event",
            route="project_calibration_events",
            event_time=_safe_text(event_record.get("created_at") or event_record.get("updated_at")),
            recorded_at=recorded_at,
            outcome=_safe_text(event_record.get("outcome") or event_record.get("event_type")),
        )
        if event:
            events.append(event)

    return events


def append_signal_lifecycle_events(signal_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_events = [event for event in events if isinstance(event, dict)]
    if not normalized_events:
        return load_signal_lifecycle_events(signal_id)

    existing = load_signal_lifecycle_events(signal_id)
    merged_events = _dedupe_events(existing + normalized_events)
    payload = {
        "signal_id": str(signal_id or "").strip(),
        "updated_at": utc_now_iso(),
        "events": merged_events,
    }
    path = lifecycle_event_file_path(signal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        _write_s3_lifecycle_payload(signal_id, payload)
    except Exception:
        pass
    return payload["events"]


def load_signal_lifecycle_events(signal_id: str) -> list[dict[str, Any]]:
    s3_payload = _read_s3_lifecycle_payload(signal_id)
    s3_events = _events_from_payload(s3_payload)

    path = lifecycle_event_file_path(signal_id)
    local_events: list[dict[str, Any]] = []
    if not path.exists():
        if s3_events:
            _cache_lifecycle_payload_local(signal_id, s3_payload)
        return s3_events

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return s3_events

    local_events = _events_from_payload(payload)
    merged = _dedupe_events(s3_events + local_events)
    if s3_events:
        _cache_lifecycle_payload_local(signal_id, {"signal_id": signal_id, "events": merged})
    return merged


def summarize_signal_lifecycle_store(*, recent_limit: int = 10) -> dict[str, Any]:
    files = sorted(LIFECYCLE_DATA_DIR.glob("*.json")) if LIFECYCLE_DATA_DIR.exists() else []
    events: list[dict[str, Any]] = []
    malformed_files: list[str] = []
    s3_payload_count = 0
    s3_malformed_keys: list[str] = []

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            malformed_files.append(path.name)
            continue

        payload_signal_id = ""
        payload_events: list[Any] | None = None
        if isinstance(payload, dict):
            payload_signal_id = str(payload.get("signal_id") or "").strip()
            payload_events = payload.get("events") if isinstance(payload.get("events"), list) else None
        elif isinstance(payload, list):
            payload_events = payload

        if payload_events is None:
            malformed_files.append(path.name)
            continue

        for event in payload_events:
            if not isinstance(event, dict):
                continue
            normalized = dict(event)
            if not str(normalized.get("signal_id") or "").strip():
                normalized["signal_id"] = payload_signal_id or path.stem
            events.append(normalized)

    s3_payloads, s3_bad_keys = _list_s3_lifecycle_payloads()
    s3_payload_count = len(s3_payloads)
    s3_malformed_keys = s3_bad_keys
    for key, payload in s3_payloads:
        payload_signal_id = ""
        if isinstance(payload, dict):
            payload_signal_id = str(payload.get("signal_id") or "").strip() or Path(key).stem
        for event in _events_from_payload(payload):
            normalized = dict(event)
            if not str(normalized.get("signal_id") or "").strip():
                normalized["signal_id"] = payload_signal_id
            events.append(normalized)

    return summarize_signal_lifecycle_events(
        _dedupe_events(events),
        file_count=len(files),
        malformed_files=malformed_files,
        recent_limit=recent_limit,
        s3_file_count=s3_payload_count,
        s3_malformed_keys=s3_malformed_keys,
    )


def summarize_signal_lifecycle_events(
    events: list[dict[str, Any]],
    *,
    file_count: int = 0,
    malformed_files: list[str] | None = None,
    recent_limit: int = 10,
    s3_file_count: int = 0,
    s3_malformed_keys: list[str] | None = None,
) -> dict[str, Any]:
    normalized_events = [event for event in events if isinstance(event, dict)]
    recent_limit = max(0, min(int(recent_limit or 0), 50))

    event_types: Counter[str] = Counter()
    provenance_classes: Counter[str] = Counter()
    source_record_families: Counter[str] = Counter()
    routes: Counter[str] = Counter()
    state_transitions: Counter[str] = Counter()
    signal_ids: set[str] = set()
    latest_recorded_at = ""
    latest_event_time = ""

    for event in normalized_events:
        event_types[_clean_counter_key(event.get("event_type"), "unknown")] += 1
        provenance_classes[_clean_counter_key(event.get("provenance_class"), "unknown")] += 1
        routes[_clean_counter_key(event.get("route"), "unknown")] += 1

        signal_id = str(event.get("signal_id") or "").strip()
        if signal_id:
            signal_ids.add(signal_id)

        source_ref = event.get("source_ref") if isinstance(event.get("source_ref"), dict) else {}
        source_record_families[_clean_counter_key(source_ref.get("record_family"), "unknown")] += 1

        state = event.get("state") if isinstance(event.get("state"), dict) else {}
        before = str(state.get("before") or "").strip() or "unknown"
        after = str(state.get("after") or "").strip() or "unknown"
        state_transitions[f"{before}->{after}"] += 1

        recorded_at = str(event.get("recorded_at") or "").strip()
        event_time = str(event.get("event_time") or "").strip()
        if recorded_at > latest_recorded_at:
            latest_recorded_at = recorded_at
        if event_time > latest_event_time:
            latest_event_time = event_time

    recent_events = sorted(
        normalized_events,
        key=lambda event: str(event.get("recorded_at") or event.get("event_time") or ""),
        reverse=True,
    )[:recent_limit]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "storage": _storage_descriptor(s3_file_count=s3_file_count),
        "authoritative": False,
        "summary_scope": "soft_recorded_lifecycle_events",
        "file_count": file_count,
        "s3_file_count": s3_file_count,
        "malformed_file_count": len(malformed_files or []),
        "malformed_files": sorted(malformed_files or []),
        "s3_malformed_key_count": len(s3_malformed_keys or []),
        "s3_malformed_keys": sorted(s3_malformed_keys or []),
        "signal_count": len(signal_ids),
        "event_count": len(normalized_events),
        "event_types": _sorted_counter_dict(event_types),
        "provenance_classes": _sorted_counter_dict(provenance_classes),
        "source_record_families": _sorted_counter_dict(source_record_families),
        "routes": _sorted_counter_dict(routes),
        "state_transitions": _sorted_transition_counts(state_transitions),
        "latest_recorded_at": latest_recorded_at or None,
        "latest_event_time": latest_event_time or None,
        "recent_events": [_compact_event_summary(event) for event in recent_events],
        "hard_enforcement_readiness": build_lifecycle_hard_enforcement_readiness(normalized_events),
        "warnings": [
            "This summary covers soft-recorded lifecycle events only.",
            "It is not authoritative lifecycle history and does not include legacy inferred events.",
        ],
    }


def build_lifecycle_hard_enforcement_readiness(events: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_events = [event for event in events if isinstance(event, dict)]
    flag = signal_status_hard_enforcement_flag()
    atomicity_preflight = build_update_status_atomicity_preflight()
    path_events = [
        event
        for event in normalized_events
        if _safe_text(event.get("route")) == HARD_ENFORCEMENT_CANDIDATE_PATH
        and _safe_text(event.get("event_type")) == HARD_ENFORCEMENT_CANDIDATE_EVENT_TYPE
    ]
    direct_events = [
        event for event in path_events if _safe_text(event.get("provenance_class")) == "direct"
    ]
    incomplete_events = [
        {
            "event_id": _safe_text(event.get("event_id")),
            "signal_id": _safe_text(event.get("signal_id")),
            "missing_fields": _missing_hard_enforcement_fields(event),
        }
        for event in direct_events
        if _missing_hard_enforcement_fields(event)
    ]

    blocking_gaps: list[str] = []
    warnings = [
        "Readiness report only; hard enforcement is not enabled.",
        "Rollback remains soft-mode behavior: lifecycle write failure should not corrupt signal/project records.",
    ]
    if flag["status"] == "enforce_requested":
        warnings.append("Hard enforcement was requested by flag, but mutation blocking is not wired in this release.")
    elif flag["status"] == "invalid":
        warnings.append(f"Invalid {HARD_ENFORCEMENT_FLAG_ENV} value; effective mode remains off.")
    if not atomicity_preflight["atomicity_ready"]:
        warnings.append("Atomicity preflight is not ready; do not enable mutation blocking for update-status.")
    if not path_events:
        blocking_gaps.append("No /signals/update-status lifecycle events were found.")
    if path_events and not direct_events:
        blocking_gaps.append("Update-status events exist, but none are direct lifecycle events.")
    if incomplete_events:
        blocking_gaps.append("One or more direct update-status events are missing required envelope fields.")
    non_direct_count = len(path_events) - len(direct_events)
    if non_direct_count > 0:
        warnings.append(f"{non_direct_count} update-status event(s) are non-direct and cannot support hard enforcement.")

    checks = [
        {
            "id": "selected_path",
            "label": "Selected path",
            "status": "ready",
            "detail": HARD_ENFORCEMENT_CANDIDATE_PATH,
        },
        {
            "id": "direct_event_coverage",
            "label": "Direct event coverage",
            "status": "ready" if direct_events else "not_ready",
            "detail": f"{len(direct_events)} direct / {len(path_events)} total update-status event(s).",
        },
        {
            "id": "event_envelope",
            "label": "Event envelope",
            "status": "ready" if direct_events and not incomplete_events else "not_ready",
            "detail": "Required lifecycle fields are present."
            if direct_events and not incomplete_events
            else "Required lifecycle fields are missing or no direct events exist.",
        },
        {
            "id": "rollback",
            "label": "Rollback",
            "status": "ready",
            "detail": "Current path remains soft-recorded; disabling future enforcement would leave existing records intact.",
        },
        {
            "id": "verification_invariants",
            "label": "Verification invariants",
            "status": "ready",
            "detail": "This candidate path does not change Project Takeaway gates, override routes, or Reflection evidence boundaries.",
        },
        {
            "id": "enforcement_mode",
            "label": "Enforcement mode",
            "status": "ready" if flag["status"] in {"off", "report_only"} else "warning",
            "detail": f"Flag {HARD_ENFORCEMENT_FLAG_ENV} is {flag['status']}; effective mode is {flag['effective_mode']}.",
        },
        {
            "id": "atomicity_preflight",
            "label": "Atomicity preflight",
            "status": "ready" if atomicity_preflight["atomicity_ready"] else "not_ready",
            "detail": atomicity_preflight["summary"],
        },
    ]

    return {
        "selected_path": HARD_ENFORCEMENT_CANDIDATE_PATH,
        "event_type": HARD_ENFORCEMENT_CANDIDATE_EVENT_TYPE,
        "flag": flag,
        "atomicity_preflight": atomicity_preflight,
        "status": "not_ready" if blocking_gaps else "ready",
        "event_count": len(path_events),
        "direct_event_count": len(direct_events),
        "complete_event_count": len(direct_events) - len(incomplete_events),
        "incomplete_events": incomplete_events[:10],
        "checks": checks,
        "blocking_gaps": blocking_gaps,
        "warnings": warnings,
        "next_action": "Generate or update a signal status to create a direct lifecycle event."
        if not path_events
        else (
            "Repair missing lifecycle envelope fields before considering enforcement."
            if incomplete_events
            else (
                "Do not enable blocking until atomicity preflight is ready."
                if not atomicity_preflight["atomicity_ready"]
                else "Candidate path is ready for a separate hard-enforcement implementation slice."
            )
        ),
    }


def signal_status_hard_enforcement_flag() -> dict[str, Any]:
    raw_value = _safe_text(os.getenv(HARD_ENFORCEMENT_FLAG_ENV))
    normalized = raw_value.lower()
    defaulted = raw_value == ""

    if normalized in {"", "0", "false", "no", "off", "disabled"}:
        status = "off"
        effective_mode = "off"
        reason = "Default-safe mode. Lifecycle readiness is report-only and does not block mutations."
    elif normalized in {"report", "report_only", "dry_run", "observe"}:
        status = "report_only"
        effective_mode = "report_only"
        reason = "Explicit report-only mode. Readiness is visible, but mutations are not blocked."
    elif normalized in {"1", "true", "yes", "on", "enforce", "hard"}:
        status = "enforce_requested"
        effective_mode = "report_only"
        reason = "Enforcement was requested, but mutation blocking is intentionally not wired until a separate enforcement slice."
    else:
        status = "invalid"
        effective_mode = "off"
        reason = "Unrecognized flag value. Falling back to off."

    return {
        "env_var": HARD_ENFORCEMENT_FLAG_ENV,
        "configured_value": raw_value if raw_value else "off",
        "defaulted": defaulted,
        "status": status,
        "effective_mode": effective_mode,
        "enforcement_active": False,
        "blocks_mutations": False,
        "reason": reason,
    }


def build_update_status_atomicity_preflight() -> dict[str, Any]:
    return {
        "path": HARD_ENFORCEMENT_CANDIDATE_PATH,
        "status": "not_ready",
        "atomicity_ready": False,
        "current_order": "mutation_then_lifecycle_append",
        "safe_to_block_mutation": False,
        "blocking_recommendation": "keep_report_only",
        "summary": "Current update-status code mutates the signal/manual session before lifecycle append.",
        "checked_subpaths": [
            {
                "id": "manual_session",
                "owner": "manual_upload_session",
                "current_order": [
                    "load manual session",
                    "mutate session status fields",
                    "save session detail",
                    "upsert session index",
                    "soft-record signal_status_changed lifecycle event",
                ],
                "atomicity_ready": False,
                "risk": "If lifecycle append fails, the manual session status may already be saved.",
            },
            {
                "id": "automatic_signal_by_id",
                "owner": "signal_store",
                "current_order": [
                    "read current signal for status_before",
                    "update signal status by signal_id",
                    "soft-record signal_status_changed lifecycle event",
                ],
                "atomicity_ready": False,
                "risk": "If lifecycle append fails, the automatic signal status may already be saved.",
            },
            {
                "id": "automatic_signal_by_identity",
                "owner": "signal_store",
                "current_order": [
                    "update signal status by title/source/date identity",
                    "soft-record signal_status_changed lifecycle event",
                ],
                "atomicity_ready": False,
                "risk": "Identity fallback has no pre-mutation event commit point and may save status before lifecycle append.",
            },
        ],
        "required_before_blocking": [
            "Choose an explicit transaction strategy for status mutation plus lifecycle append.",
            "Return a clear lifecycle_event_required error before any status mutation when enforcement cannot be satisfied.",
            "Split automatic signal and manual session enforcement readiness if their atomicity differs.",
            "Keep rollback as flag-only and never require deleting already-written lifecycle events.",
        ],
    }


def lifecycle_event_file_path(signal_id: str) -> Path:
    return LIFECYCLE_DATA_DIR / f"{_safe_file_stem(signal_id)}.json"


def lifecycle_event_s3_key(signal_id: str) -> str:
    safe_name = _safe_file_stem(signal_id)
    return f"{LIFECYCLE_S3_PREFIX.strip('/')}/{safe_name}.json"


def _s3_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_LIFECYCLE_S3_ENABLED", "")).strip().lower()
    if value in {"0", "false", "no", "off", "local"}:
        return False
    if value in {"1", "true", "yes", "on", "s3"}:
        return bool(_s3_bucket())
    return bool(_s3_bucket())


def _s3_bucket() -> str:
    return str(os.getenv("AI_RADAR_S3_BUCKET") or os.getenv("S3_BUCKET") or "").strip()


def _s3_client():
    if not _s3_enabled():
        return None
    try:
        import boto3

        return boto3.client("s3")
    except Exception:
        return None


def _read_s3_lifecycle_payload(signal_id: str) -> dict[str, Any] | list[Any] | None:
    client = _s3_client()
    bucket = _s3_bucket()
    if client is None or not bucket:
        return None
    try:
        response = client.get_object(Bucket=bucket, Key=lifecycle_event_s3_key(signal_id))
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _write_s3_lifecycle_payload(signal_id: str, payload: dict[str, Any]) -> None:
    client = _s3_client()
    bucket = _s3_bucket()
    if client is None or not bucket:
        return
    client.put_object(
        Bucket=bucket,
        Key=lifecycle_event_s3_key(signal_id),
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def _list_s3_lifecycle_payloads() -> tuple[list[tuple[str, dict[str, Any] | list[Any]]], list[str]]:
    client = _s3_client()
    bucket = _s3_bucket()
    if client is None or not bucket:
        return [], []

    payloads: list[tuple[str, dict[str, Any] | list[Any]]] = []
    malformed_keys: list[str] = []
    prefix = f"{LIFECYCLE_S3_PREFIX.strip('/')}/"
    try:
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    except Exception:
        return [], []

    for page in pages:
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "").strip()
            if not key.endswith(".json"):
                continue
            try:
                response = client.get_object(Bucket=bucket, Key=key)
                raw = response["Body"].read().decode("utf-8")
                payload = json.loads(raw)
                if _events_from_payload(payload):
                    payloads.append((key, payload))
                else:
                    malformed_keys.append(key)
            except Exception:
                malformed_keys.append(key)

    return payloads, malformed_keys


def _events_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        return [event for event in payload["events"] if isinstance(event, dict)]
    if isinstance(payload, list):
        return [event for event in payload if isinstance(event, dict)]
    return []


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id") or "").strip()
        if event_id:
            key = event_id
        else:
            key = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def _cache_lifecycle_payload_local(signal_id: str, payload: Any) -> None:
    events = _events_from_payload(payload)
    if not events:
        return
    normalized_payload = {
        "signal_id": str(signal_id or "").strip(),
        "updated_at": utc_now_iso(),
        "events": events,
    }
    path = lifecycle_event_file_path(signal_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _storage_descriptor(*, s3_file_count: int = 0) -> str:
    if _s3_enabled():
        return "s3_with_local_cache" if s3_file_count else "s3_enabled_with_local_fallback"
    return "local_file"


def build_verification_support_snapshot(verification: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(verification, dict) or not verification:
        return {}

    support = {
        "verification_status": get_verification_status(verification),
        "allowed_downstream_actions": get_allowed_downstream_actions(verification),
        "blocked_downstream_actions": get_blocked_downstream_actions(verification),
        "claim_support_summary": get_claim_support_summary(verification),
        "confidence_label": get_confidence_label(verification),
        "confidence_score": get_confidence_score(verification),
        "review_priority": str(verification.get("review_priority") or "").strip(),
        "evaluation_summary": _evaluation_summary(verification),
    }
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None, {}, [])
    }


def _base_event(
    *,
    signal_id: str,
    event_time: str,
    recorded_at: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str,
    status_after: str,
    route: str = "/signals/generate-insight",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": "",
        "signal_id": str(signal_id or "").strip(),
        "event_time": event_time,
        "recorded_at": recorded_at,
        "actor": {
            "type": "system",
            "id": "ai-radar-backend",
        },
        "route": route,
        "provenance_class": "direct",
        "source_ref": {
            "record_family": str(source_record_family or "").strip() or "signal",
            "record_id": str(source_record_id or "").strip() or str(signal_id or "").strip(),
        },
        "state": {
            "before": str(status_before or "").strip(),
            "after": str(status_after or "").strip() or "analyzed",
        },
        "project_ref": None,
        "model_provenance_ref": None,
        "support": {},
    }


def _fingerprint_support(
    *,
    preexisting_fingerprint: str,
    generated_fingerprint: str,
    stored_fingerprint: str,
    fingerprint_changed: bool | None,
) -> dict[str, Any]:
    support = {
        "preexisting_fingerprint": str(preexisting_fingerprint or "").strip(),
        "generated_fingerprint": str(generated_fingerprint or "").strip(),
        "stored_fingerprint": str(stored_fingerprint or "").strip(),
        "fingerprint_changed": fingerprint_changed,
    }
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None)
    }


def _completion_support(
    *,
    workspace_file_name: str,
    workspace_saved_at: str,
    project_improvements: list[dict[str, Any]] | None,
    verification: dict[str, Any],
) -> dict[str, Any]:
    support = {
        "workspace_file_name": str(workspace_file_name or "").strip(),
        "workspace_saved_at": str(workspace_saved_at or "").strip(),
        "project_improvements_written": len([item for item in project_improvements or [] if isinstance(item, dict)]),
    }
    if verification:
        support["verification"] = build_verification_support_snapshot(verification)
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None, {}, [])
    }


def _project_candidate_support(improvement: dict[str, Any]) -> dict[str, Any]:
    verification = improvement.get("verification_metadata") if isinstance(improvement.get("verification_metadata"), dict) else {}
    support = {
        "candidate_source": str(improvement.get("candidate_source") or "").strip(),
        "source_type": str(improvement.get("source_type") or "").strip(),
        "manual_session_id": str(improvement.get("manual_session_id") or "").strip(),
        "upload_reason": str(improvement.get("upload_reason") or verification.get("upload_reason") or "").strip(),
        "intended_use": str(improvement.get("intended_use") or verification.get("intended_use") or "").strip(),
        "cognitive_layer": str(improvement.get("cognitive_layer") or verification.get("cognitive_layer") or "").strip(),
        "verification": build_verification_support_snapshot(verification),
    }
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None, {}, [])
    }


def _project_record_id(improvement: dict[str, Any]) -> str:
    project_id = str(improvement.get("project_id") or "").strip()
    signal_id = str(improvement.get("signal_id") or "").strip()
    if project_id and signal_id:
        return f"{project_id}:{signal_id}"
    return signal_id or project_id


def _project_attachment_event(
    *,
    signal_id: str,
    record: dict[str, Any],
    source_record_family: str,
    route: str,
    event_time: str,
    recorded_at: str,
    outcome: str,
) -> dict[str, Any] | None:
    record_id = _safe_text(record.get("id") or record.get("review_record_id"))
    project_id = _safe_text(record.get("project_id"))
    if not record_id and not project_id:
        return None

    status_after = outcome or _safe_text(record.get("event_type")) or "recorded"
    base = _base_event(
        signal_id=signal_id,
        event_time=event_time or recorded_at,
        recorded_at=recorded_at,
        source_record_family=source_record_family,
        source_record_id=record_id,
        status_before=_safe_text(record.get("source_status")),
        status_after=status_after,
        route=route,
    )
    event = {
        **base,
        "event_type": "project_review_attached",
        "provenance_class": "derived",
        "actor": {
            "type": "system",
            "id": "signal_lifecycle_probe",
        },
        "project_ref": {
            "project_id": project_id,
            "project_name": _safe_text(record.get("project_name")),
            "record_family": source_record_family,
            "record_id": record_id,
            "outcome": outcome,
        },
        "support": _project_attachment_support(record),
        "model_provenance_ref": _model_provenance_reference(
            record.get("produced_by_model") if isinstance(record.get("produced_by_model"), dict) else None,
            {
                "verification_status": record.get("verification_status"),
                "claim_support_summary": record.get("claim_support_summary"),
                "confidence_label": record.get("confidence_label"),
                "confidence_score": record.get("confidence_score"),
            },
        ),
    }
    event["event_id"] = _derived_event_id(
        "project_review_attached",
        signal_id,
        source_record_family,
        record_id,
        project_id,
        outcome,
    )
    return event


def _project_attachment_support(record: dict[str, Any]) -> dict[str, Any]:
    support = {
        "source_type": _safe_text(record.get("source_type")),
        "manual_session_id": _safe_text(record.get("manual_session_id")),
        "is_manual_source": record.get("is_manual_source") if isinstance(record.get("is_manual_source"), bool) else None,
        "upload_reason": _safe_text(record.get("upload_reason")),
        "intended_use": _safe_text(record.get("intended_use")),
        "cognitive_layer": _safe_text(record.get("cognitive_layer")),
        "review_record_id": _safe_text(record.get("review_record_id")),
        "project_event_type": _safe_text(record.get("event_type")),
        "verification_status": _safe_text(record.get("verification_status")),
        "claim_support_summary": record.get("claim_support_summary") if isinstance(record.get("claim_support_summary"), dict) else {},
        "unsupported_claim_count": record.get("unsupported_claim_count"),
        "inferred_claim_count": record.get("inferred_claim_count"),
        "allowed_downstream_actions": record.get("allowed_downstream_actions") if isinstance(record.get("allowed_downstream_actions"), list) else [],
        "blocked_downstream_actions": record.get("blocked_downstream_actions") if isinstance(record.get("blocked_downstream_actions"), list) else [],
        "action_eligibility": record.get("action_eligibility") if isinstance(record.get("action_eligibility"), dict) else {},
        "confidence_label": _safe_text(record.get("confidence_label")),
        "confidence_score": record.get("confidence_score"),
        "manual_project_takeaway_override": record.get("manual_project_takeaway_override")
        if isinstance(record.get("manual_project_takeaway_override"), bool)
        else None,
    }
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None, {}, [])
    }


def _status_change_support(
    *,
    saved_reason: str | None,
    decision_trace_event: str,
    updated_keys: list[str] | None,
) -> dict[str, Any]:
    support = {
        "saved_reason": str(saved_reason or "").strip(),
        "decision_trace_event": str(decision_trace_event or "").strip(),
        "updated_keys": [str(item).strip() for item in updated_keys or [] if str(item).strip()],
    }
    return {
        key: value
        for key, value in support.items()
        if value not in ("", None, {}, [])
    }


def _model_provenance_reference(
    produced_by_model: dict[str, Any] | None,
    verification: dict[str, Any] | None,
) -> dict[str, Any] | None:
    candidate = produced_by_model if isinstance(produced_by_model, dict) else None
    normalized = normalize_model_provenance(candidate)
    if normalized.get("provenance_schema_version") != 1:
        normalized = get_model_provenance(verification)
    if normalized.get("provenance_schema_version") != 1:
        return None

    fingerprint = str(normalized.get("deterministic_fingerprint") or "").strip()
    return {
        "provider": str(normalized.get("provider") or "").strip(),
        "model_id": str(normalized.get("model_id") or "").strip(),
        "fingerprint_prefix": fingerprint[:8],
        "schema_version": normalized.get("provenance_schema_version"),
    }


def _evaluation_summary(verification: dict[str, Any]) -> str:
    for key in (
        "review_priority_reason",
        "verification_note",
        "evidence_note",
        "summary",
    ):
        value = str(verification.get(key) or "").strip()
        if value:
            return value[:500]
    return ""


def _event_id(event: dict[str, Any]) -> str:
    return f"sig_evt_{uuid.uuid4().hex}"


def _derived_event_id(*parts: Any) -> str:
    source = "|".join(_safe_text(part) for part in parts)
    return f"sig_evt_{uuid.uuid5(uuid.NAMESPACE_URL, source).hex}"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_file_stem(signal_id: str) -> str:
    value = str(signal_id or "").strip() or "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:160]


def _clean_counter_key(value: Any, fallback: str) -> str:
    return str(value or "").strip() or fallback


def _sorted_counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {
        key: count
        for key, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }


def _sorted_transition_counts(counter: Counter[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for transition, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        before, _, after = transition.partition("->")
        rows.append(
            {
                "before": before,
                "after": after,
                "count": count,
            }
        )
    return rows


def _compact_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "signal_id": event.get("signal_id"),
        "event_type": event.get("event_type"),
        "event_time": event.get("event_time"),
        "recorded_at": event.get("recorded_at"),
        "route": event.get("route"),
        "provenance_class": event.get("provenance_class"),
        "source_ref": event.get("source_ref") if isinstance(event.get("source_ref"), dict) else {},
        "state": event.get("state") if isinstance(event.get("state"), dict) else {},
        "project_ref": event.get("project_ref") if isinstance(event.get("project_ref"), dict) else None,
    }


def _missing_hard_enforcement_fields(event: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in (
        "schema_version",
        "event_id",
        "signal_id",
        "event_type",
        "event_time",
        "recorded_at",
        "route",
        "provenance_class",
    ):
        if event.get(field) in ("", None):
            missing.append(field)

    actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
    if not _safe_text(actor.get("type")):
        missing.append("actor.type")
    if not _safe_text(actor.get("id")):
        missing.append("actor.id")

    source_ref = event.get("source_ref") if isinstance(event.get("source_ref"), dict) else {}
    if not _safe_text(source_ref.get("record_family")):
        missing.append("source_ref.record_family")
    if not _safe_text(source_ref.get("record_id")):
        missing.append("source_ref.record_id")

    state = event.get("state") if isinstance(event.get("state"), dict) else {}
    if not _safe_text(state.get("before")):
        missing.append("state.before")
    if not _safe_text(state.get("after")):
        missing.append("state.after")

    return missing
