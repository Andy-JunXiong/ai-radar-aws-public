USE_LOCAL_DEBUG = False

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Request
from pydantic import BaseModel

from app.routes.manual import (
    build_session_summary,
    ensure_uploaded_file_local,
    extract_text_from_file,
    load_session_detail,
    save_session_detail,
    upsert_session_index_item,
    utc_now_iso,
)
from app.services.request_identity import resolve_request_user_id
from app.services.admin_guard import require_admin_auth
from app.services.manual_source_link_service import apply_manual_source_url_metadata
from app.services.signal_insight_service import (
    build_insight_fingerprint,
    generate_signal_insight,
    write_signal_insight_debug_record,
)
from app.services.deep_project_match_analysis_service import generate_deep_project_match_analysis
from app.services.subscription_settings_service import (
    apply_subscription_settings_to_signals,
    load_subscription_settings,
)
from app.routes.workspace import SaveReflectionRequest, save_reflection_to_file
from app.services.reflection_service import find_related_reflections_for_signal
from app.services.project_intelligence_service import add_signal_to_project_improvements
from app.services.project_calibration_event_service import list_project_calibration_events
from app.services.project_review_record_service import list_project_review_records
from app.services.s3_reader import (
    build_signal_identity,
    get_last_signal_load_diagnostic,
    get_signal_by_id,
    load_signals,
    update_signal_insight_by_signal_id,
    update_signal_star_by_identity,
    update_signal_star_by_signal_id,
    update_signal_status_by_identity,
    update_signal_status_by_signal_id,
)
from app.services.metrics_event_service import record_signal_timeline_load
from app.services.signal_decision_trace_service import (
    append_decision_trace_event,
    build_decision_trace_event,
    status_event_type,
)
from app.services.signal_lifecycle_event_service import (
    append_signal_lifecycle_events,
    build_generate_insight_events,
    build_project_review_attached_events,
    build_signal_completion_events,
    build_signal_status_change_events,
    load_signal_lifecycle_events,
    summarize_signal_lifecycle_store,
)
from app.services.signal_lifecycle_probe_service import build_signal_lifecycle_probe
from app.services.signal_near_duplicate_service import build_signal_near_duplicate_report

router = APIRouter()

DEFAULT_COLLECTED_AT = datetime.now(timezone.utc).isoformat()
ALLOWED_STATUSES = {"pending", "saved", "analyzed", "completed", "rejected"}
MAX_MANUAL_SOURCE_EXCERPT_CHARS = 6000

MANUAL_SESSIONS_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "manual_uploads" / "sessions"
)
MANUAL_SESSIONS_INDEX_PATH = MANUAL_SESSIONS_DIR / "index.json"


def _current_insight_payload(signal: dict) -> dict:
    return {
        "why_it_matters": signal.get("why_it_matters") or signal.get("insight", ""),
        "relevance_to_projects": signal.get("relevance_to_projects", ""),
        "relevance_to_career": signal.get("relevance_to_career", ""),
        "synthesized_insight": signal.get("synthesized_insight") or signal.get("strategy", ""),
    }


class SignalStatusUpdate(BaseModel):
    signal_id: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = ""
    collected_at: Optional[str] = ""
    status: str
    saved_reason: Optional[str] = None


class SignalStarUpdate(BaseModel):
    signal_id: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = ""
    collected_at: Optional[str] = ""
    starred: bool


class GenerateInsightRequest(BaseModel):
    signal_id: str
    selected_model: Optional[str] = "chatgpt"


class DeepMatchAnalysisRequest(BaseModel):
    signal_id: str
    selected_model: Optional[str] = "chatgpt"
    signal_snapshot: Optional[dict] = None
    deep_match_review: Optional[dict] = None
    source_depth_tier: Optional[str] = "metadata"
    source_text: Optional[str] = ""


class CompleteSignalRequest(BaseModel):
    signal_id: str
    signal_title: Optional[str] = None
    topic: Optional[str] = None
    selected_model: Optional[str] = None
    user_input: Optional[str] = None
    ai_response: Optional[str] = None
    final_reflection: str
    signal_summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    relevance_to_projects: Optional[str] = None
    relevance_to_career: Optional[str] = None
    synthesized_insight: Optional[str] = None
    verification_metadata: Optional[dict] = None
    subscription_project_links: Optional[list[dict]] = None


def _insight_generation_config_error_detail(message: str) -> str:
    if "ANTHROPIC_API_KEY not found" in message:
        return (
            "Claude insight generation is not configured in this local backend. "
            "Set ANTHROPIC_API_KEY, then restart the backend."
        )
    if "OPENAI_API_KEY not found" in message:
        return (
            "ChatGPT insight generation is not configured in this local backend. "
            "Set OPENAI_API_KEY, then restart the backend."
        )
    if "No supported LLM API key" in message:
        return (
            "Insight generation is not configured in this local backend. "
            "Set a supported OpenAI or Anthropic API key, then restart the backend."
        )
    return ""


def _soft_record_generate_insight_lifecycle_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str,
    status_after: str,
    verification: Optional[dict],
    produced_by_model: Optional[dict],
    preexisting_fingerprint: str,
    generated_fingerprint: str,
    stored_fingerprint: str,
    fingerprint_changed: bool,
    event_time: Optional[str] = None,
) -> None:
    try:
        events = build_generate_insight_events(
            signal_id=signal_id,
            source_record_family=source_record_family,
            source_record_id=source_record_id,
            status_before=status_before,
            status_after=status_after,
            verification=verification,
            produced_by_model=produced_by_model,
            preexisting_fingerprint=preexisting_fingerprint,
            generated_fingerprint=generated_fingerprint,
            stored_fingerprint=stored_fingerprint,
            fingerprint_changed=fingerprint_changed,
            event_time=event_time,
        )
        append_signal_lifecycle_events(signal_id, events)
    except Exception as exc:
        print(f"[WARN] signal lifecycle soft recording failed for {signal_id}: {exc}")


def _soft_record_signal_completion_lifecycle_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str,
    verification: Optional[dict],
    workspace_file_name: str,
    workspace_saved_at: str,
    project_improvements: list[dict],
    event_time: Optional[str] = None,
) -> None:
    try:
        events = build_signal_completion_events(
            signal_id=signal_id,
            source_record_family=source_record_family,
            source_record_id=source_record_id,
            status_before=status_before,
            status_after="completed",
            verification=verification,
            workspace_file_name=workspace_file_name,
            workspace_saved_at=workspace_saved_at,
            project_improvements=project_improvements,
            event_time=event_time,
        )
        append_signal_lifecycle_events(signal_id, events)
    except Exception as exc:
        print(f"[WARN] signal completion lifecycle soft recording failed for {signal_id}: {exc}")


def _soft_record_signal_status_lifecycle_events(
    *,
    signal_id: str,
    source_record_family: str,
    source_record_id: str,
    status_before: str,
    status_after: str,
    saved_reason: Optional[str],
    decision_trace_event: str,
    updated_keys: Optional[list[str]] = None,
    event_time: Optional[str] = None,
) -> None:
    try:
        events = build_signal_status_change_events(
            signal_id=signal_id,
            source_record_family=source_record_family,
            source_record_id=source_record_id,
            status_before=status_before,
            status_after=status_after,
            saved_reason=saved_reason,
            decision_trace_event=decision_trace_event,
            updated_keys=updated_keys,
            event_time=event_time,
        )
        append_signal_lifecycle_events(signal_id, events)
    except Exception as exc:
        print(f"[WARN] signal status lifecycle soft recording failed for {signal_id}: {exc}")


def _normalized_status(value: Optional[str], default: str = "pending") -> str:
    status = (value or default).lower()
    if status not in ALLOWED_STATUSES:
        return default
    return status


def _signal_identity(signal: dict, fallback_id: str) -> str:
    return str(signal.get("signal_id") or signal.get("id") or fallback_id)


def _signal_title(signal: dict, fallback_title: str) -> str:
    return signal.get("title") or signal.get("signal_title") or fallback_title


def _signal_summary(signal: dict) -> str:
    summary = (
        signal.get("summary")
        or signal.get("signal_summary")
        or signal.get("description")
        or signal.get("content")
        or signal.get("notes")
        or ""
    )
    summary_text = str(summary or "").strip()
    if summary_text:
        return summary_text[:320].rstrip() + ("..." if len(summary_text) > 320 else "")

    title = str(signal.get("title") or signal.get("signal_title") or "").strip()
    source = str(signal.get("source") or "").strip()
    topic = str(signal.get("topic") or "").strip()
    if title and source:
        topic_suffix = f" in {topic}" if topic else ""
        return f"{title} from {source}{topic_suffix}. Raw source summary was unavailable, so this working summary is title-based."
    return title or ""


def _signal_published_at(signal: dict) -> Optional[str]:
    return (
        signal.get("published_at")
        or signal.get("publish_time")
        or signal.get("published_time")
    )


def _signal_collected_at(signal: dict) -> str:
    return signal.get("collected_at") or signal.get("created_at") or DEFAULT_COLLECTED_AT


def _signal_source_url(signal: dict) -> str:
    return (
        signal.get("url")
        or signal.get("link")
        or signal.get("source_url")
        or signal.get("article_url")
        or signal.get("post_url")
        or signal.get("canonical_url")
        or ""
    )


def _signal_score(signal: dict):
    score_raw = signal.get("score")
    try:
        return float(score_raw) if score_raw is not None else None
    except Exception:
        return None


def _signal_response_payload(normalized: dict) -> dict:
    policy_metadata = normalized.get("policy_metadata")
    return {
        "id": normalized.get("signal_id"),
        "signal_id": normalized.get("signal_id"),
        "title": normalized.get("title"),
        "summary": normalized.get("summary"),
        "source": normalized.get("source"),
        "published_at": normalized.get("published_at"),
        "collected_at": normalized.get("collected_at"),
        "status": normalized.get("status"),
        "saved_reason": normalized.get("saved_reason"),
        "starred": bool(normalized.get("starred")),
        "starred_at": normalized.get("starred_at"),
        "url": normalized.get("url", ""),
        "link": normalized.get("link", ""),
        "source_url": normalized.get("source_url", ""),
        "source_excerpt": normalized.get("source_excerpt", ""),
        "source_excerpt_length": normalized.get("source_excerpt_length", 0),
        "source_stated_limits": normalized.get("source_stated_limits", ""),
        "source_stated_confidence": normalized.get("source_stated_confidence"),
        "source_stated_limits_not_applicable": bool(
            normalized.get("source_stated_limits_not_applicable")
        ),
        "source_stated_limits_status": normalized.get("source_stated_limits_status", ""),
        "topic": normalized.get("topic", "General AI"),
        "score": normalized.get("score"),
        "insight_status": normalized.get("insight_status", "unknown"),
        "insight_status_label": normalized.get("insight_status_label", "Status unknown"),
        "why_it_matters": normalized.get("why_it_matters", ""),
        "relevance_to_projects": normalized.get("relevance_to_projects", ""),
        "relevance_to_career": normalized.get("relevance_to_career", ""),
        "synthesized_insight": normalized.get("synthesized_insight", ""),
        "insight": normalized.get("insight", ""),
        "strategy": normalized.get("strategy", ""),
        "subscription_score_percent": normalized.get("subscription_score_percent"),
        "subscription_topic_priority": normalized.get("subscription_topic_priority", "normal"),
        "auto_action_hint": normalized.get("auto_action_hint", ""),
        "model_used": normalized.get("model_used", ""),
        "produced_by_model": normalized.get("produced_by_model"),
        "generation_mode": normalized.get("generation_mode", ""),
        "requested_provider": normalized.get("requested_provider", ""),
        "policy_metadata": policy_metadata,
        "verification": normalized.get("verification") or (policy_metadata or {}).get("verification"),
        "verified_insight_id": (
            (normalized.get("verification") or {}).get("verified_insight_id")
            or ((policy_metadata or {}).get("verification") or {}).get("verified_insight_id")
        ),
        "evidence_pack": normalized.get("evidence_pack"),
        "decision_trace": normalized.get("decision_trace", []),
    }


def _compact_signal_list_item(normalized: dict) -> dict:
    item = _signal_response_payload(normalized)
    item.pop("subscription_project_links", None)
    item.pop("why_it_matters", None)
    item.pop("relevance_to_projects", None)
    item.pop("relevance_to_career", None)
    item.pop("synthesized_insight", None)
    item.pop("evidence_pack", None)
    item.pop("policy_metadata", None)
    return item


def _detail_signal_payload(normalized: dict) -> dict:
    item = _signal_response_payload(normalized)
    item["subscription_project_links"] = normalized.get("subscription_project_links", [])
    return item


def _manual_session_identity(session: dict, fallback_id: str) -> str:
    return str(session.get("session_id") or session.get("id") or fallback_id)


def _manual_session_id_from_signal_id(signal_id: str) -> str:
    return signal_id[len("manual_") :] if signal_id.startswith("manual_") else signal_id


def _manual_signal_response_payload(normalized: dict) -> dict:
    payload = _signal_response_payload(normalized)
    payload.update(
        {
            "is_manual": True,
            "manual_session_id": normalized.get("manual_session_id"),
            "upload_reason": normalized.get("upload_reason", ""),
            "intended_use": normalized.get("intended_use", ""),
            "cognitive_layer": normalized.get("cognitive_layer", "unclassified"),
            "source_stated_limits": normalized.get("source_stated_limits", ""),
            "source_stated_confidence": normalized.get("source_stated_confidence"),
            "source_stated_limits_not_applicable": bool(
                normalized.get("source_stated_limits_not_applicable")
            ),
            "source_stated_limits_status": normalized.get("source_stated_limits_status", ""),
            "file_count": normalized.get("file_count"),
            "file_types": normalized.get("file_types", []),
            "files": normalized.get("files", []),
            "analysis_status": normalized.get("analysis_status"),
            "workspace_saved": normalized.get("workspace_saved", False),
            "workspace_file_name": normalized.get("workspace_file_name"),
            "workspace_saved_at": normalized.get("workspace_saved_at"),
            "provider_used": normalized.get("provider_used"),
            "model_used": normalized.get("model_used"),
            "produced_by_model": normalized.get("produced_by_model"),
            "generation_mode": normalized.get("generation_mode"),
            "requested_provider": normalized.get("requested_provider"),
            "verification": normalized.get("verification")
            or ((normalized.get("policy_metadata") or {}).get("verification")),
        }
    )
    return payload


def _manual_signal_detail_payload(manual: dict, request: Request | None = None) -> dict:
    user_id = resolve_request_user_id(request) or "demo_default"
    subscription_settings = load_subscription_settings(user_id)
    enriched = apply_subscription_settings_to_signals([manual], subscription_settings)
    if enriched:
        manual = enriched[0]
    payload = _manual_signal_response_payload(manual)
    payload["subscription_project_links"] = manual.get("subscription_project_links", [])
    return payload


def _has_manual_insight_content(normalized: dict) -> bool:
    return any(
        str(normalized.get(key) or "").strip()
        for key in [
            "why_it_matters",
            "relevance_to_projects",
            "relevance_to_career",
            "synthesized_insight",
        ]
    )


def normalize_signal(signal: dict, index: int):
    title = _signal_title(signal, f"Untitled signal {index + 1}")
    summary = _signal_summary(signal)
    source = signal.get("source") or "Unknown"
    published_at = _signal_published_at(signal)
    collected_at = _signal_collected_at(signal)
    status = _normalized_status(signal.get("status"))

    saved_reason = signal.get("saved_reason")
    starred = bool(signal.get("starred"))
    starred_at = signal.get("starred_at")
    signal_id = _signal_identity(signal, str(index + 1))
    source_url = _signal_source_url(signal)

    topic = signal.get("topic") or "General AI"
    insight_status = signal.get("insight_status") or "unknown"
    insight_status_label = signal.get("insight_status_label") or "Status unknown"
    score = _signal_score(signal)
    source_excerpt = str(signal.get("source_excerpt") or "").strip()
    source_excerpt_length = signal.get("source_excerpt_length")
    if source_excerpt and not source_excerpt_length:
        source_excerpt_length = len(source_excerpt)

    return {
        "id": signal_id,
        "signal_id": signal_id,
        "title": title,
        "summary": summary,
        "source": source,
        "published_at": published_at,
        "collected_at": collected_at,
        "status": status,
        "saved_reason": saved_reason,
        "starred": starred,
        "starred_at": starred_at,
        "url": source_url,
        "link": source_url,
        "source_url": source_url,
        "source_excerpt": source_excerpt,
        "source_excerpt_length": source_excerpt_length or 0,
        "source_stated_limits": signal.get("source_stated_limits", ""),
        "source_stated_confidence": signal.get("source_stated_confidence"),
        "source_stated_limits_not_applicable": bool(
            signal.get("source_stated_limits_not_applicable")
        ),
        "source_stated_limits_status": signal.get("source_stated_limits_status", ""),
        "topic": topic,
        "score": score,
        "insight_status": insight_status,
        "insight_status_label": insight_status_label,
        "why_it_matters": signal.get("why_it_matters") or signal.get("insight", ""),
        "relevance_to_projects": signal.get("relevance_to_projects", ""),
        "relevance_to_career": signal.get("relevance_to_career", ""),
        "synthesized_insight": signal.get("synthesized_insight") or signal.get("strategy", ""),
        "insight": signal.get("insight", ""),
        "strategy": signal.get("strategy", ""),
        "provider_used": signal.get("provider_used", ""),
        "model_used": signal.get("model_used", ""),
        "produced_by_model": signal.get("produced_by_model"),
        "generation_mode": signal.get("generation_mode", ""),
        "requested_provider": signal.get("requested_provider", ""),
        "verification": signal.get("verification"),
        "policy_metadata": signal.get("policy_metadata"),
        "evidence_pack": signal.get("evidence_pack"),
        "decision_trace": signal.get("decision_trace", []),
    }


def load_normalized_signals():
    items = load_signals(use_local=USE_LOCAL_DEBUG)
    if not isinstance(items, list):
        items = items.get("items", [])
    return [normalize_signal(item, i) for i, item in enumerate(items)]


def load_local_manual_sessions() -> list[dict]:
    sessions_by_id: dict[str, dict] = {}

    if not MANUAL_SESSIONS_DIR.exists():
        return []

    for file_path in sorted(MANUAL_SESSIONS_DIR.glob("*.json"), reverse=True):
        if file_path.name == "index.json":
            continue

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        session_id = str(data.get("session_id") or data.get("id") or "").strip()
        if not session_id:
            continue

        sessions_by_id[session_id] = data

    if MANUAL_SESSIONS_INDEX_PATH.exists():
        try:
            index_items = json.loads(MANUAL_SESSIONS_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            index_items = []

        if isinstance(index_items, list):
            for item in index_items:
                if not isinstance(item, dict):
                    continue

                session_id = str(item.get("session_id") or item.get("id") or "").strip()
                if not session_id or session_id in sessions_by_id:
                    continue

                sessions_by_id[session_id] = item

    sessions = list(sessions_by_id.values())
    sessions.sort(
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
        reverse=True,
    )
    return sessions


def extract_manual_analysis_fields(session: dict) -> dict:
    analysis = session.get("analysis")

    summary = str(session.get("summary") or "").strip()
    why_it_matters = session.get("why_it_matters") or ""
    relevance_to_projects = session.get("relevance_to_projects") or ""
    relevance_to_career = session.get("relevance_to_career") or ""
    synthesized_insight = session.get("synthesized_insight") or ""
    topic = session.get("topic") or "Manual Upload"

    if isinstance(analysis, dict):
        summary = summary or str(analysis.get("summary") or "").strip()
        why_it_matters = why_it_matters or analysis.get("why_it_matters") or ""
        relevance_to_projects = (
            relevance_to_projects or analysis.get("relevance_to_projects") or ""
        )
        relevance_to_career = relevance_to_career or analysis.get("relevance_to_career") or ""
        synthesized_insight = (
            synthesized_insight or analysis.get("synthesized_insight") or ""
        )
        topic = analysis.get("topic") or topic
    elif isinstance(analysis, str):
        why_it_matters = why_it_matters or analysis

    return {
        "summary": summary,
        "why_it_matters": why_it_matters,
        "relevance_to_projects": relevance_to_projects,
        "relevance_to_career": relevance_to_career,
        "synthesized_insight": synthesized_insight,
        "topic": topic or "Manual Upload",
    }


def _manual_session_source_excerpt(files: list[dict]) -> str:
    sections: list[str] = []

    for file_info in files:
        if not isinstance(file_info, dict):
            continue

        file_kind = str(file_info.get("file_kind") or "").lower()
        if file_kind not in {"text", "pdf"}:
            continue

        stored_filename = str(file_info.get("stored_filename") or "").strip()
        if not stored_filename:
            continue

        original_filename = str(
            file_info.get("original_filename") or stored_filename
        ).strip()

        try:
            file_path = ensure_uploaded_file_local(stored_filename)
            if not file_path.exists():
                continue
            text = extract_text_from_file(file_path).strip()
        except Exception:
            continue

        if not text:
            continue

        sections.append(
            f"Filename: {original_filename}\n\n{text[:MAX_MANUAL_SOURCE_EXCERPT_CHARS]}"
        )

    return "\n\n---\n\n".join(sections)[:MAX_MANUAL_SOURCE_EXCERPT_CHARS].strip()


def normalize_manual_session(session: dict, index: int) -> dict:
    session = apply_manual_source_url_metadata(dict(session))
    session_id = _manual_session_identity(session, f"manual-{index + 1}")
    title = session.get("title") or "Manual Session"
    created_at = session.get("created_at") or session.get("updated_at") or DEFAULT_COLLECTED_AT
    updated_at = session.get("updated_at") or created_at
    analysis_status = str(session.get("analysis_status") or "not_started").lower()

    files = session.get("files") or []
    file_count = session.get("file_count")
    if file_count is None:
        file_count = len(files) if isinstance(files, list) else 0

    file_types = session.get("file_types") or []
    if not file_types and isinstance(files, list):
        file_types = list(
            {
                f.get("file_kind")
                for f in files
                if isinstance(f, dict) and f.get("file_kind")
            }
        )

    analysis_fields = extract_manual_analysis_fields(session)
    source_excerpt = str(session.get("source_excerpt") or "").strip()
    if not source_excerpt and isinstance(files, list):
        source_excerpt = _manual_session_source_excerpt(files)
    summary = analysis_fields["summary"]
    if not summary:
        if file_count and file_types:
            summary = f"Manual session with {file_count} file(s), including {', '.join(file_types)}."
        elif file_count:
            summary = f"Manual session with {file_count} uploaded file(s)."
        else:
            summary = "Manual session."

    explicit_status = _normalized_status(session.get("status"), default="")
    is_completed = bool(session.get("completion_saved"))
    if explicit_status:
        status = explicit_status
    else:
        status = "completed" if is_completed else ("analyzed" if analysis_status == "completed" else "pending")

    return {
        "id": session_id,
        "signal_id": session_id,
        "title": title,
        "summary": summary,
        "source": "manual",
        "published_at": created_at,
        "collected_at": created_at,
        "status": status,
        "saved_reason": session.get("saved_reason"),
        "starred": bool(session.get("starred")),
        "starred_at": session.get("starred_at"),
        "url": session.get("url", ""),
        "link": session.get("link", ""),
        "source_url": session.get("source_url", ""),
        "source_excerpt": source_excerpt,
        "source_excerpt_length": len(source_excerpt) if source_excerpt else 0,
        "topic": analysis_fields["topic"],
        "score": None,
        "insight_status": "manual_completed" if analysis_status == "completed" else "manual_pending",
        "insight_status_label": "Manual session analyzed" if analysis_status == "completed" else "Manual session pending",
        "why_it_matters": analysis_fields["why_it_matters"],
        "relevance_to_projects": analysis_fields["relevance_to_projects"],
        "relevance_to_career": analysis_fields["relevance_to_career"],
        "synthesized_insight": analysis_fields["synthesized_insight"],
        "insight": analysis_fields["why_it_matters"],
        "strategy": analysis_fields["synthesized_insight"],
        "is_manual": True,
        "manual_session_id": session_id,
        "upload_reason": session.get("upload_reason", ""),
        "intended_use": session.get("intended_use", ""),
        "cognitive_layer": session.get("cognitive_layer", "unclassified"),
        "source_stated_limits": session.get("source_stated_limits", ""),
        "source_stated_confidence": session.get("source_stated_confidence"),
        "source_stated_limits_not_applicable": bool(
            session.get("source_stated_limits_not_applicable")
        ),
        "source_stated_limits_status": session.get("source_stated_limits_status", ""),
        "file_count": file_count,
        "file_types": file_types,
        "analysis_status": analysis_status,
        "workspace_saved": bool(session.get("workspace_saved")),
        "workspace_file_name": session.get("workspace_file_name"),
        "workspace_saved_at": session.get("workspace_saved_at"),
        "provider_used": session.get("provider_used"),
        "model_used": session.get("model_used"),
        "produced_by_model": session.get("produced_by_model"),
        "generation_mode": session.get("generation_mode"),
        "requested_provider": session.get("requested_provider"),
        "verification": session.get("verification"),
        "policy_metadata": session.get("policy_metadata"),
        "evidence_pack": session.get("evidence_pack"),
        "files": files if isinstance(files, list) else [],
        "_sort_updated_at": updated_at,
        "raw": session,
    }


def _normalize_manual_sessions(sessions: list[dict]) -> list[dict]:
    return [
        normalize_manual_session(session, i)
        for i, session in enumerate(sessions)
        if isinstance(session, dict)
    ]


def load_all_normalized_signals() -> list[dict]:
    auto_signals = load_normalized_signals()
    manual_sessions = load_local_manual_sessions()
    manual_signals = _normalize_manual_sessions(manual_sessions)
    return auto_signals + manual_signals


def _manual_signal_aliases(session: dict) -> set[str]:
    aliases: set[str] = set()

    sid = str(session.get("session_id") or session.get("id") or "").strip()
    if sid:
        aliases.add(sid)
        aliases.add(f"manual_{sid}")

    title = session.get("title") or "Manual Session"
    created_at = session.get("created_at") or session.get("updated_at") or ""
    updated_at = session.get("updated_at") or ""
    summary = session.get("summary") or ""
    analysis = session.get("analysis") or ""

    source_variants = [
        "",
        "Unknown",
        "manual",
        "Manual Upload",
        "Manual",
        session.get("source") or "",
    ]

    date_variants = [
        created_at,
        updated_at,
        "",
    ]

    url_variants = [
        "",
        session.get("url") or "",
        session.get("link") or "",
        session.get("source_url") or "",
    ]

    title_variants = [
        title,
        summary or "",
        analysis[:120] if isinstance(analysis, str) and analysis else "",
    ]

    for src in source_variants:
        for dt in date_variants:
            for url in url_variants:
                for t in title_variants:
                    if not t:
                        continue
                    candidate = {
                        "title": t,
                        "source": src,
                        "published_at": dt,
                        "url": url,
                    }
                    try:
                        aliases.add(build_signal_identity(candidate))
                    except Exception:
                        pass

    return {x for x in aliases if x}


def find_manual_signal(signal_id: str):
    target_id = str(signal_id)
    sessions = load_local_manual_sessions()

    print(f"[DEBUG] find_manual_signal target_id = {target_id}")
    print(f"[DEBUG] loaded manual sessions count = {len(sessions)}")

    for idx, s in enumerate(sessions[:10]):
        sid = str(s.get("session_id") or s.get("id") or "")
        title = s.get("title") or ""
        print(f"[DEBUG] sample manual session {idx}: sid={sid}, title={title}")

    for s in sessions:
        aliases = _manual_signal_aliases(s)
        if target_id in aliases:
            print("[DEBUG] exact manual session / alias match found")
            return normalize_manual_session(s, 0)

    print("[DEBUG] manual session not found by signal_id")
    return None


def build_counts(items):
    counts = {
        "all": len(items),
        "pending": 0,
        "saved": 0,
        "analyzed": 0,
        "completed": 0,
        "rejected": 0,
    }

    for item in items:
        status = _normalized_status(item.get("status"))
        counts[status] += 1

    return counts


def _date_prefix(value: object) -> str:
    if not value:
        return ""
    text = str(value)
    return text[:10] if len(text) >= 10 else ""


def _latest_date(items: list[dict], key: str) -> str | None:
    dates = sorted(
        date_key
        for item in items
        if (date_key := _date_prefix(item.get(key)))
    )
    return dates[-1] if dates else None


def _soft_record_signal_timeline_load(event: dict) -> None:
    try:
        record_signal_timeline_load(event)
    except Exception as exc:
        print(f"[WARN] signal timeline load metric recording failed: {exc}")


@router.get("/signals")
def get_signals(request: Request, status: Optional[str] = Query(default="all")):
    started_at = time.time()
    normalized = load_all_normalized_signals()
    user_id = resolve_request_user_id(request) or "demo_default"
    subscription_settings = load_subscription_settings(user_id)
    normalized = apply_subscription_settings_to_signals(normalized, subscription_settings)
    all_items = list(normalized)
    counts = build_counts(normalized)

    selected_status = (status or "all").lower()

    if selected_status != "all":
        normalized = [i for i in normalized if i["status"] == selected_status]

    normalized = sorted(
        normalized,
        key=lambda item: (
            item.get("collected_at")
            or item.get("published_at")
            or item.get("_sort_updated_at")
            or ""
        ),
        reverse=True,
    )

    compact_items = [_compact_signal_list_item(item) for item in normalized]
    load_diagnostic = get_last_signal_load_diagnostic()
    _soft_record_signal_timeline_load(
        {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "route": "/signals",
            "status_filter": selected_status,
            "success": True,
            "duration_ms": round((time.time() - started_at) * 1000, 2),
            "returned_count": len(compact_items),
            "total_count": counts["all"],
            "auto_count": sum(1 for item in all_items if not item.get("is_manual")),
            "manual_count": sum(1 for item in all_items if item.get("is_manual")),
            "latest_published_date": _latest_date(all_items, "published_at"),
            "latest_collected_date": _latest_date(all_items, "collected_at"),
            "load_source": load_diagnostic.get("source"),
            "load_count": load_diagnostic.get("count"),
            "latest_content_at": load_diagnostic.get("latest_content_at"),
            "local_snapshot_status": load_diagnostic.get("local_snapshot_status"),
            "local_snapshot_reason": load_diagnostic.get("local_snapshot_reason"),
            "backend_load_duration_ms": load_diagnostic.get("duration_ms"),
        }
    )

    return {
        "signals": compact_items,
        "counts": counts,
        "selected_status": selected_status,
        "subscription_user_id": user_id,
        "subscription_settings_applied": True,
    }


@router.get("/signals/lifecycle-summary", dependencies=[Depends(require_admin_auth)])
def get_signal_lifecycle_summary(limit: int = Query(default=10, ge=0, le=50)):
    return {
        **summarize_signal_lifecycle_store(recent_limit=limit),
        "message": "signal lifecycle summary loaded successfully",
    }


@router.get("/signals/near-duplicates", dependencies=[Depends(require_admin_auth)])
def get_signal_near_duplicates(summary_only: bool = Query(default=False)):
    return {
        **build_signal_near_duplicate_report(include_records=not summary_only),
        "message": "signal near-duplicate diagnostics loaded successfully",
    }


@router.get("/signals/{signal_id}/related-reflections")
def get_signal_related_reflections(signal_id: str, request: Request = None, limit: int = 3):
    current = get_signal_by_id(
        signal_id,
        use_local=USE_LOCAL_DEBUG,
    )

    if current:
        normalized = normalize_signal(current, 0)
        user_id = resolve_request_user_id(request) or "demo_default"
        subscription_settings = load_subscription_settings(user_id)
        enriched = apply_subscription_settings_to_signals([normalized], subscription_settings)
        if enriched:
            normalized = enriched[0]
        return find_related_reflections_for_signal(normalized, limit=limit)

    manual = find_manual_signal(signal_id)
    if manual:
        user_id = resolve_request_user_id(request) or "demo_default"
        subscription_settings = load_subscription_settings(user_id)
        enriched = apply_subscription_settings_to_signals([manual], subscription_settings)
        if enriched:
            manual = enriched[0]
        return find_related_reflections_for_signal(manual, limit=limit)

    raise HTTPException(status_code=404, detail=f"Signal not found for id: {signal_id}")


@router.get("/signals/{signal_id}/lifecycle-probe", dependencies=[Depends(require_admin_auth)])
def get_signal_lifecycle_probe(signal_id: str, request: Request = None):
    current = get_signal_by_id(
        signal_id,
        use_local=USE_LOCAL_DEBUG,
    )

    if current:
        normalized = normalize_signal(current, 0)
        user_id = resolve_request_user_id(request) or "demo_default"
        subscription_settings = load_subscription_settings(user_id)
        enriched = apply_subscription_settings_to_signals([normalized], subscription_settings)
        signal = enriched[0] if enriched else normalized
    else:
        signal = find_manual_signal(signal_id)

    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal not found for id: {signal_id}")

    signal_aliases = {
        str(value)
        for value in {
            signal_id,
            signal.get("signal_id"),
            signal.get("id"),
            signal.get("manual_session_id"),
            f"manual_{signal.get('manual_session_id')}" if signal.get("manual_session_id") else "",
        }
        if value
    }

    review_records = []
    calibration_events = []
    lifecycle_events_by_id = {}
    for candidate_id in signal_aliases:
        review_records.extend(list_project_review_records(signal_id=candidate_id))
        calibration_events.extend(list_project_calibration_events(signal_id=candidate_id))
        for event in load_signal_lifecycle_events(candidate_id):
            event_key = str(event.get("event_id") or f"{candidate_id}:{len(lifecycle_events_by_id)}")
            lifecycle_events_by_id[event_key] = event

    review_records_by_id = {
        str(record.get("id") or index): record
        for index, record in enumerate(review_records)
        if isinstance(record, dict)
    }
    calibration_events_by_id = {
        str(event.get("id") or index): event
        for index, event in enumerate(calibration_events)
        if isinstance(event, dict)
    }
    review_records = list(review_records_by_id.values())
    calibration_events = list(calibration_events_by_id.values())
    for event in build_project_review_attached_events(
        signal_id=str(signal.get("signal_id") or signal_id),
        review_records=review_records,
        calibration_events=calibration_events,
    ):
        event_key = str(event.get("event_id") or f"derived:{len(lifecycle_events_by_id)}")
        lifecycle_events_by_id[event_key] = event

    return {
        **build_signal_lifecycle_probe(
            signal,
            review_records=review_records,
            calibration_events=calibration_events,
            lifecycle_events=list(lifecycle_events_by_id.values()),
        ),
        "message": "signal lifecycle probe loaded successfully",
    }


@router.get("/signals/{signal_id}")
def get_signal_detail(signal_id: str, request: Request = None):
    print(f"[DEBUG] HIT get_signal_detail: {signal_id}")

    if signal_id.startswith("manual_"):
        manual = find_manual_signal(signal_id)
        if manual:
            print("[DEBUG] matched manual signal before auto lookup")
            return _manual_signal_detail_payload(manual, request)

    current = get_signal_by_id(
        signal_id,
        use_local=USE_LOCAL_DEBUG,
    )

    if current:
        print("[DEBUG] matched auto signal")
        normalized = normalize_signal(current, 0)
        user_id = resolve_request_user_id(request) or "demo_default"
        subscription_settings = load_subscription_settings(user_id)
        enriched = apply_subscription_settings_to_signals([normalized], subscription_settings)
        if enriched:
            normalized = enriched[0]
        return _detail_signal_payload(normalized)

    print("[DEBUG] auto signal not found, trying manual fallback")

    manual = find_manual_signal(signal_id)

    if manual:
        print("[DEBUG] matched manual signal")
        return _manual_signal_detail_payload(manual, request)

    print("[DEBUG] manual fallback not found")
    raise HTTPException(status_code=404, detail=f"Signal not found for id: {signal_id}")


@router.post("/signals/update-status", dependencies=[Depends(require_admin_auth)])
def update_signal_status(payload: SignalStatusUpdate):
    status = (payload.status or "").lower()

    if status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")

    saved_reason = payload.saved_reason if status == "saved" else None

    if payload.signal_id:
        manual_signal = find_manual_signal(payload.signal_id)
        if manual_signal:
            session_id = _manual_session_id_from_signal_id(payload.signal_id)
            session_data = load_session_detail(session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Manual session not found.")

            status_before = _normalized_status(manual_signal.get("status"))
            session_data["status"] = status
            session_data["saved_reason"] = saved_reason
            session_data["updated_at"] = utc_now_iso()
            append_decision_trace_event(
                session_data,
                build_decision_trace_event(
                    event_type=status_event_type(status),
                    actor="admin",
                    route="/signals/update-status",
                    status_before=status_before,
                    status_after=status,
                    support={"saved_reason": saved_reason} if status == "saved" and saved_reason else None,
                ),
            )

            if status == "completed":
                session_data["completion_saved"] = True
                session_data["workspace_saved"] = True
            elif status in {"saved", "rejected", "analyzed", "pending"}:
                session_data["completion_saved"] = False
                if status != "completed":
                    session_data["workspace_saved"] = False
                    session_data["workspace_file_name"] = None
                    session_data["workspace_saved_at"] = None

            if status == "analyzed" and session_data.get("analysis"):
                session_data["analysis_status"] = "completed"

            save_session_detail(session_data)
            upsert_session_index_item(build_session_summary(session_data))

            durable_signal_id = f"manual_{session_id}"
            _soft_record_signal_status_lifecycle_events(
                signal_id=durable_signal_id,
                source_record_family="manual_session",
                source_record_id=session_id,
                status_before=status_before,
                status_after=status,
                saved_reason=saved_reason,
                decision_trace_event=status_event_type(status),
            )

            return {
                "ok": True,
                "manual_session_id": session_id,
                "status": status,
                "saved_reason": saved_reason,
            }
        try:
            current_signal = get_signal_by_id(payload.signal_id, use_local=USE_LOCAL_DEBUG)
            status_before = _normalized_status((current_signal or {}).get("status")) if current_signal else ""
            result = update_signal_status_by_signal_id(
                signal_id=payload.signal_id,
                new_status=status,
                saved_reason=saved_reason,
            )
            _soft_record_signal_status_lifecycle_events(
                signal_id=result.get("signal_id") or payload.signal_id,
                source_record_family="signal",
                source_record_id=payload.signal_id,
                status_before=status_before,
                status_after=status,
                saved_reason=saved_reason,
                decision_trace_event=result.get("decision_trace_event") or status_event_type(status),
                updated_keys=result.get("updated_keys", []),
            )
            return result
        except ValueError:
            if payload.title or payload.source or payload.published_at or payload.collected_at:
                result = update_signal_status_by_identity(
                    target_title=payload.title or "",
                    target_source=payload.source or "",
                    target_published_at=payload.published_at or "",
                    target_collected_at=payload.collected_at or "",
                    new_status=status,
                    saved_reason=saved_reason,
                )
                _soft_record_signal_status_lifecycle_events(
                    signal_id=result.get("signal_id") or payload.signal_id,
                    source_record_family="signal",
                    source_record_id=result.get("signal_id") or payload.signal_id,
                    status_before="",
                    status_after=status,
                    saved_reason=saved_reason,
                    decision_trace_event=result.get("decision_trace_event") or status_event_type(status),
                    updated_keys=result.get("updated_keys", []),
                )
                return result
            raise

    result = update_signal_status_by_identity(
        target_title=payload.title or "",
        target_source=payload.source or "",
        target_published_at=payload.published_at or "",
        target_collected_at=payload.collected_at or "",
        new_status=status,
        saved_reason=saved_reason,
    )
    _soft_record_signal_status_lifecycle_events(
        signal_id=result.get("signal_id") or "",
        source_record_family="signal",
        source_record_id=result.get("signal_id") or "",
        status_before="",
        status_after=status,
        saved_reason=saved_reason,
        decision_trace_event=result.get("decision_trace_event") or status_event_type(status),
        updated_keys=result.get("updated_keys", []),
    )
    return result


@router.post("/signals/update-star", dependencies=[Depends(require_admin_auth)])
def update_signal_star(payload: SignalStarUpdate):
    starred = bool(payload.starred)
    starred_at = utc_now_iso() if starred else None

    if payload.signal_id:
        manual_signal = find_manual_signal(payload.signal_id)
        if manual_signal:
            session_id = _manual_session_id_from_signal_id(payload.signal_id)
            session_data = load_session_detail(session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Manual session not found.")

            session_data["starred"] = starred
            session_data["starred_at"] = starred_at
            session_data["updated_at"] = utc_now_iso()
            save_session_detail(session_data)
            upsert_session_index_item(build_session_summary(session_data))

            return {
                "ok": True,
                "manual_session_id": session_id,
                "signal_id": f"manual_{session_id}",
                "starred": starred,
                "starred_at": starred_at,
            }

        try:
            return update_signal_star_by_signal_id(
                signal_id=payload.signal_id,
                starred=starred,
                starred_at=starred_at,
            )
        except ValueError:
            if payload.title or payload.source or payload.published_at or payload.collected_at:
                return update_signal_star_by_identity(
                    target_title=payload.title or "",
                    target_source=payload.source or "",
                    target_published_at=payload.published_at or "",
                    target_collected_at=payload.collected_at or "",
                    starred=starred,
                    starred_at=starred_at,
                )
            raise

    return update_signal_star_by_identity(
        target_title=payload.title or "",
        target_source=payload.source or "",
        target_published_at=payload.published_at or "",
        target_collected_at=payload.collected_at or "",
        starred=starred,
        starred_at=starred_at,
    )


@router.post("/signals/generate-insight", dependencies=[Depends(require_admin_auth)])
def generate_insight_for_signal(payload: GenerateInsightRequest, request: Request):
    signal_id = str(payload.signal_id or "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required.")

    manual_signal = find_manual_signal(signal_id)
    if manual_signal:
        preexisting_payload = _current_insight_payload(manual_signal)
        preexisting_fingerprint = build_insight_fingerprint(preexisting_payload)

        session_id = _manual_session_id_from_signal_id(signal_id)
        session_data = load_session_detail(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Manual session not found.")

        user_id = resolve_request_user_id(request) or "demo_default"
        subscription_settings = load_subscription_settings(user_id)
        enriched_candidates = apply_subscription_settings_to_signals(
            [manual_signal], subscription_settings
        )
        if enriched_candidates:
            manual_signal = enriched_candidates[0]

        previous_status = _normalized_status(
            session_data.get("status") or manual_signal.get("status"),
            default="pending",
        )

        try:
            generated = generate_signal_insight(
                manual_signal,
                selected_model=payload.selected_model,
                user_id=user_id,
            )
        except ValueError as exc:
            message = str(exc)
            config_error_detail = _insight_generation_config_error_detail(message)
            if config_error_detail:
                raise HTTPException(
                    status_code=503,
                    detail=config_error_detail,
                ) from exc
            raise

        existing_analysis = session_data.get("analysis")
        if not isinstance(existing_analysis, dict):
            existing_analysis = {}

        summary = (
            existing_analysis.get("summary")
            or session_data.get("summary")
            or manual_signal.get("summary")
            or ""
        )
        topic = (
            existing_analysis.get("topic")
            or session_data.get("topic")
            or manual_signal.get("topic")
            or "Manual Upload"
        )

        session_data["analysis"] = {
            **existing_analysis,
            "summary": summary,
            "topic": topic,
            "why_it_matters": generated.get("why_it_matters", ""),
            "relevance_to_projects": generated.get("relevance_to_projects", ""),
            "relevance_to_career": generated.get("relevance_to_career", ""),
            "synthesized_insight": generated.get("synthesized_insight", ""),
        }
        session_data["analysis_status"] = "completed"
        session_data["updated_at"] = utc_now_iso()
        if session_data.get("status") == "pending":
            session_data["status"] = "analyzed"
        session_data["provider_used"] = generated.get("provider_used") or "chatgpt"
        session_data["model_used"] = generated.get("model_used") or ""
        session_data["generation_mode"] = generated.get("generation_mode") or "llm"
        session_data["requested_provider"] = generated.get("requested_provider") or payload.selected_model or "chatgpt"
        session_data["produced_by_model"] = generated.get("produced_by_model")
        session_data["verification"] = generated.get("verification")
        session_data["policy_metadata"] = generated.get("policy_metadata")
        session_data["evidence_pack"] = generated.get("evidence_pack")

        save_session_detail(session_data)
        upsert_session_index_item(build_session_summary(session_data))

        normalized_refreshed = normalize_manual_session(session_data, 0)
        refreshed_payload = _current_insight_payload(normalized_refreshed)
        refreshed_fingerprint = build_insight_fingerprint(refreshed_payload)
        _soft_record_generate_insight_lifecycle_events(
            signal_id=signal_id,
            source_record_family="manual_session",
            source_record_id=session_id,
            status_before=previous_status,
            status_after=_normalized_status(normalized_refreshed.get("status"), default="analyzed"),
            verification=session_data.get("verification")
            or (session_data.get("policy_metadata") or {}).get("verification"),
            produced_by_model=session_data.get("produced_by_model"),
            preexisting_fingerprint=preexisting_fingerprint,
            generated_fingerprint=generated.get("content_fingerprint", ""),
            stored_fingerprint=refreshed_fingerprint,
            fingerprint_changed=preexisting_fingerprint != refreshed_fingerprint,
            event_time=session_data.get("updated_at"),
        )
        debug_file_name = write_signal_insight_debug_record(
            {
                "generated_at": utc_now_iso(),
                "signal_id": signal_id,
                "requested_provider": payload.selected_model,
                "provider_used": session_data.get("provider_used"),
                "actual_provider": generated.get("actual_provider") or session_data.get("provider_used"),
                "model_used": session_data.get("model_used"),
                "produced_by_model": session_data.get("produced_by_model"),
                "generation_mode": session_data.get("generation_mode"),
                "preexisting_fingerprint": preexisting_fingerprint,
                "generated_fingerprint": generated.get("content_fingerprint"),
                "stored_fingerprint": refreshed_fingerprint,
                "fingerprint_changed": preexisting_fingerprint != refreshed_fingerprint,
                "preexisting_payload": preexisting_payload,
                "generated_payload": {
                    "why_it_matters": generated.get("why_it_matters", ""),
                    "relevance_to_projects": generated.get("relevance_to_projects", ""),
                    "relevance_to_career": generated.get("relevance_to_career", ""),
                    "synthesized_insight": generated.get("synthesized_insight", ""),
                },
                "stored_payload": refreshed_payload,
            }
        )
        return {
            "message": "Insight generated and saved successfully.",
            "signal_id": signal_id,
            "id": normalized_refreshed.get("id"),
            "is_manual": True,
            "manual_session_id": normalized_refreshed.get("manual_session_id"),
            "upload_reason": normalized_refreshed.get("upload_reason", ""),
            "intended_use": normalized_refreshed.get("intended_use", ""),
            "cognitive_layer": normalized_refreshed.get("cognitive_layer", "unclassified"),
            "file_count": normalized_refreshed.get("file_count"),
            "file_types": normalized_refreshed.get("file_types", []),
            "files": normalized_refreshed.get("files", []),
            "analysis_status": normalized_refreshed.get("analysis_status"),
            "insight_status": normalized_refreshed.get("insight_status"),
            "insight_status_label": normalized_refreshed.get("insight_status_label"),
            "workspace_saved": normalized_refreshed.get("workspace_saved", False),
            "workspace_file_name": normalized_refreshed.get("workspace_file_name"),
            "workspace_saved_at": normalized_refreshed.get("workspace_saved_at"),
            "topic": normalized_refreshed.get("topic", "Manual Upload"),
            "status": normalized_refreshed.get("status", "analyzed"),
            "summary": normalized_refreshed.get("summary", ""),
            "why_it_matters": normalized_refreshed.get("why_it_matters", ""),
            "relevance_to_projects": normalized_refreshed.get("relevance_to_projects", ""),
            "relevance_to_career": normalized_refreshed.get("relevance_to_career", ""),
            "synthesized_insight": normalized_refreshed.get("synthesized_insight", ""),
            "provider_used": session_data.get("provider_used"),
            "model_used": session_data.get("model_used"),
            "produced_by_model": session_data.get("produced_by_model"),
            "generation_mode": session_data.get("generation_mode"),
            "requested_provider": session_data.get("requested_provider"),
            "actual_provider": generated.get("actual_provider") or session_data.get("provider_used"),
            "content_fingerprint": generated.get("content_fingerprint"),
            "preexisting_fingerprint": preexisting_fingerprint,
            "stored_fingerprint": refreshed_fingerprint,
            "fingerprint_changed": preexisting_fingerprint != refreshed_fingerprint,
            "debug_file_name": debug_file_name,
            "policy_metadata": session_data.get("policy_metadata"),
            "verification": session_data.get("verification") or (session_data.get("policy_metadata") or {}).get("verification"),
            "verified_insight_id": ((session_data.get("verification") or {}).get("verified_insight_id"))
            or (((session_data.get("policy_metadata") or {}).get("verification") or {}).get("verified_insight_id")),
            "evidence_pack": session_data.get("evidence_pack"),
            "execution": (session_data.get("policy_metadata") or {}).get("execution"),
            "updated_keys": [
                "why_it_matters",
                "relevance_to_projects",
                "relevance_to_career",
                "synthesized_insight",
            ],
        }

    current = get_signal_by_id(
        signal_id,
        use_local=USE_LOCAL_DEBUG,
    )

    if not current:
        raise HTTPException(status_code=404, detail=f"Signal not found for id: {signal_id}")

    preexisting_payload = _current_insight_payload(current)
    preexisting_fingerprint = build_insight_fingerprint(preexisting_payload)
    normalized = normalize_signal(current, 0)
    user_id = resolve_request_user_id(request) or "demo_default"
    subscription_settings = load_subscription_settings(user_id)
    enriched_candidates = apply_subscription_settings_to_signals([normalized], subscription_settings)
    if enriched_candidates:
        normalized = enriched_candidates[0]

    try:
        insight = generate_signal_insight(
            normalized,
            selected_model=payload.selected_model,
            user_id=user_id,
        )
    except ValueError as exc:
        message = str(exc)
        config_error_detail = _insight_generation_config_error_detail(message)
        if config_error_detail:
            raise HTTPException(
                status_code=503,
                detail=config_error_detail,
            ) from exc
        raise

    result = update_signal_insight_by_signal_id(
        signal_id=signal_id,
        insight_fields=insight,
        new_status="analyzed",
    )

    refreshed = get_signal_by_id(
        signal_id,
        force_refresh=True,
        use_local=USE_LOCAL_DEBUG,
    )

    normalized_refreshed = normalize_signal(refreshed or current, 0)
    stored_payload = _current_insight_payload(refreshed or result or current)
    stored_fingerprint = build_insight_fingerprint(stored_payload)
    refreshed_or_result = refreshed or result or {}
    _soft_record_generate_insight_lifecycle_events(
        signal_id=signal_id,
        source_record_family="signal",
        source_record_id=signal_id,
        status_before=_normalized_status(current.get("status"), default="pending"),
        status_after=_normalized_status(refreshed_or_result.get("status"), default="analyzed"),
        verification=refreshed_or_result.get("verification")
        or ((refreshed_or_result.get("policy_metadata") or {}).get("verification"))
        or ((insight.get("policy_metadata") or {}).get("verification"))
        or insight.get("verification"),
        produced_by_model=refreshed_or_result.get("produced_by_model") or insight.get("produced_by_model"),
        preexisting_fingerprint=preexisting_fingerprint,
        generated_fingerprint=insight.get("content_fingerprint", ""),
        stored_fingerprint=stored_fingerprint,
        fingerprint_changed=preexisting_fingerprint != stored_fingerprint,
        event_time=utc_now_iso(),
    )
    debug_file_name = write_signal_insight_debug_record(
        {
            "generated_at": utc_now_iso(),
            "signal_id": signal_id,
            "requested_provider": payload.selected_model,
            "provider_used": insight.get("provider_used"),
            "actual_provider": insight.get("actual_provider") or insight.get("provider_used"),
            "model_used": insight.get("model_used"),
            "produced_by_model": insight.get("produced_by_model"),
            "generation_mode": insight.get("generation_mode"),
            "preexisting_fingerprint": preexisting_fingerprint,
            "generated_fingerprint": insight.get("content_fingerprint"),
            "stored_fingerprint": stored_fingerprint,
            "fingerprint_changed": preexisting_fingerprint != stored_fingerprint,
            "preexisting_payload": preexisting_payload,
            "generated_payload": {
                "why_it_matters": insight.get("why_it_matters", ""),
                "relevance_to_projects": insight.get("relevance_to_projects", ""),
                "relevance_to_career": insight.get("relevance_to_career", ""),
                "synthesized_insight": insight.get("synthesized_insight", ""),
            },
            "stored_payload": stored_payload,
        }
    )

    return {
        "message": "Insight generated and saved successfully.",
        "signal_id": signal_id,
        "status": "analyzed",
        "summary": normalized_refreshed.get("summary", "") or normalized.get("summary", ""),
        "why_it_matters": insight.get("why_it_matters", ""),
        "relevance_to_projects": insight.get("relevance_to_projects", ""),
        "relevance_to_career": insight.get("relevance_to_career", ""),
        "synthesized_insight": insight.get("synthesized_insight", ""),
        "provider_used": (refreshed or result).get("provider_used") or insight.get("provider_used"),
        "actual_provider": insight.get("actual_provider") or (refreshed or result).get("provider_used") or insight.get("provider_used"),
        "model_used": (refreshed or result).get("model_used") or insight.get("model_used"),
        "produced_by_model": (refreshed or result).get("produced_by_model") or insight.get("produced_by_model"),
        "generation_mode": (refreshed or result).get("generation_mode") or insight.get("generation_mode"),
        "requested_provider": (refreshed or result).get("requested_provider") or insight.get("requested_provider"),
        "content_fingerprint": insight.get("content_fingerprint"),
        "preexisting_fingerprint": preexisting_fingerprint,
        "stored_fingerprint": stored_fingerprint,
        "fingerprint_changed": preexisting_fingerprint != stored_fingerprint,
        "debug_file_name": debug_file_name,
        "policy_metadata": insight.get("policy_metadata"),
        "verification": (insight.get("policy_metadata") or {}).get("verification") or insight.get("verification"),
        "verified_insight_id": (((insight.get("policy_metadata") or {}).get("verification") or {}).get("verified_insight_id"))
        or ((insight.get("verification") or {}).get("verified_insight_id")),
        "evidence_pack": (refreshed or result).get("evidence_pack") or insight.get("evidence_pack"),
        "execution": (insight.get("policy_metadata") or {}).get("execution"),
        "updated_keys": result.get("updated_keys", []),
    }


@router.post("/signals/actions/deep-match-analysis", dependencies=[Depends(require_admin_auth)])
def generate_deep_match_analysis_for_signal(payload: DeepMatchAnalysisRequest, request: Request):
    signal_id = str(payload.signal_id or "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required.")

    signal = payload.signal_snapshot if isinstance(payload.signal_snapshot, dict) else None
    if not signal:
        signal = find_manual_signal(signal_id) or get_signal_by_id(signal_id)
    if not isinstance(signal, dict):
        raise HTTPException(status_code=404, detail="Signal not found.")

    user_id = resolve_request_user_id(request) or "demo_default"
    try:
        analysis = generate_deep_project_match_analysis(
            signal=signal,
            deep_match_review=payload.deep_match_review if isinstance(payload.deep_match_review, dict) else {},
            selected_model=payload.selected_model,
            user_id=user_id,
            source_depth_tier=payload.source_depth_tier,
            source_text=payload.source_text,
        )
    except ValueError as exc:
        message = str(exc)
        config_error_detail = _insight_generation_config_error_detail(message)
        if config_error_detail:
            raise HTTPException(status_code=503, detail=config_error_detail) from exc
        if "No supported LLM API key" in message:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Deep Match Analysis is not configured in this local backend. "
                    "Set a supported OpenAI or Anthropic API key, then restart the backend."
                ),
            ) from exc
        raise

    return {
        "signal_id": signal_id,
        "generated_at": utc_now_iso(),
        "analysis": analysis,
        "verification_effect": "none",
        "allowed_downstream_effect": "review_context_only",
    }


@router.post("/signals/complete", dependencies=[Depends(require_admin_auth)])
def complete_signal(payload: CompleteSignalRequest):
    signal_id = str(payload.signal_id or "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required.")

    final_reflection = (payload.final_reflection or "").strip()
    if not final_reflection:
        raise HTTPException(status_code=400, detail="final_reflection is required.")

    manual_signal = find_manual_signal(signal_id)
    manual_session_id = ""
    durable_signal_id = signal_id
    source_type = "signal"
    content_type = "signal"
    if manual_signal:
        manual_session_id = _manual_session_id_from_signal_id(signal_id)
        durable_signal_id = f"manual_{manual_session_id}"
        source_type = "manual_upload"
        content_type = "manual_session"

    saved = save_reflection_to_file(
        SaveReflectionRequest(
            source_type=source_type,
            content_type=content_type,
            topic=payload.topic,
            signal_id=durable_signal_id,
            signal_title=payload.signal_title,
            selected_model=payload.selected_model,
            user_input=payload.user_input,
            ai_response=payload.ai_response,
            final_reflection=final_reflection,
            signal_summary=payload.signal_summary,
            why_it_matters=payload.why_it_matters,
            relevance_to_projects=payload.relevance_to_projects,
            relevance_to_career=payload.relevance_to_career,
            synthesized_insight=payload.synthesized_insight,
            verification_metadata=payload.verification_metadata,
        )
    )

    project_improvements = add_signal_to_project_improvements(
        signal_id=durable_signal_id,
        signal_title=payload.signal_title or "",
        signal_summary=payload.signal_summary or "",
        why_it_matters=payload.why_it_matters or "",
        relevance_to_projects=payload.relevance_to_projects or "",
        synthesized_insight=payload.synthesized_insight or "",
        final_reflection=final_reflection,
        subscription_project_links=payload.subscription_project_links or [],
        verification_metadata=payload.verification_metadata,
    )

    if manual_signal:
        session_data = load_session_detail(manual_session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Manual session not found.")

        manual_status_before = _normalized_status(
            session_data.get("status")
            or ("analyzed" if session_data.get("analysis_status") == "completed" else "pending"),
            default="analyzed",
        )
        session_data["workspace_saved"] = True
        session_data["completion_saved"] = True
        session_data["workspace_file_name"] = saved["file_name"]
        session_data["workspace_saved_at"] = saved["record"]["saved_at"]
        session_data["updated_at"] = utc_now_iso()
        save_session_detail(session_data)
        upsert_session_index_item(build_session_summary(session_data))

        _soft_record_signal_completion_lifecycle_events(
            signal_id=durable_signal_id,
            source_record_family="manual_session",
            source_record_id=manual_session_id,
            status_before=manual_status_before,
            verification=payload.verification_metadata,
            workspace_file_name=saved["file_name"],
            workspace_saved_at=saved["record"]["saved_at"],
            project_improvements=project_improvements,
        )

        return {
            "message": "Signal completed successfully.",
            "status": "completed",
            "workspace_saved": True,
            "workspace_file_name": saved["file_name"],
            "workspace_saved_at": saved["record"]["saved_at"],
            "project_improvements_written": len(project_improvements),
        }

    result = update_signal_status_by_signal_id(
        signal_id=signal_id,
        new_status="completed",
        saved_reason=None,
    )

    _soft_record_signal_completion_lifecycle_events(
        signal_id=durable_signal_id,
        source_record_family="signal",
        source_record_id=signal_id,
        status_before="",
        verification=payload.verification_metadata,
        workspace_file_name=saved["file_name"],
        workspace_saved_at=saved["record"]["saved_at"],
        project_improvements=project_improvements,
    )

    return {
        "message": "Signal completed successfully.",
        "status": "completed",
        "workspace_saved": True,
        "workspace_file_name": saved["file_name"],
        "workspace_saved_at": saved["record"]["saved_at"],
        "updated_keys": result.get("updated_keys", []),
        "project_improvements_written": len(project_improvements),
    }
