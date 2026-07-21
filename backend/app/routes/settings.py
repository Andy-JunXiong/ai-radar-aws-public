import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.context_bridge import (
    get_context_scope,
    load_personal_context_data,
    save_personal_context_data,
)
from app.services.admin_guard import require_admin_auth
from app.services.model_router_service import router_startup_diagnostics
from app.services.model_router_telemetry_service import load_route_summary
from app.services.request_identity import resolve_request_user_id
from app.services.s3_reader import load_radar
from app.reflection.settings_store import (
    get_reflection_settings_status,
    load_reflection_settings,
    save_reflection_settings,
)
from app.services.subscription_settings_service import (
    get_subscription_settings_status,
    import_legacy_rss_sources,
    load_subscription_settings,
    save_subscription_settings_with_status,
    suggest_source_from_url,
)
from app.services.source_health_service import check_subscription_source_health


router = APIRouter()


def _subscription_runtime_snapshot() -> dict[str, Any]:
    try:
        radar = load_radar()
    except Exception:
        return {}

    if not isinstance(radar, dict):
        return {}

    subscription_summary = radar.get("subscription_summary", {})
    runtime_summary = (
        subscription_summary.get("source_runtime_summary", {})
        if isinstance(subscription_summary, dict)
        else {}
    )
    source_stats = radar.get("source_stats", {}) if isinstance(radar.get("source_stats"), dict) else {}

    runtime_signal_sources = (
        runtime_summary.get("runtime_signal_sources") if isinstance(runtime_summary, dict) else None
    )
    if not isinstance(runtime_signal_sources, list) or not runtime_signal_sources:
        runtime_signal_sources = list(source_stats.keys())

    configured_source_count = (
        subscription_summary.get("source_count") if isinstance(subscription_summary, dict) else None
    )
    configured_active_source_count = (
        runtime_summary.get("configured_active_source_count") if isinstance(runtime_summary, dict) else None
    )
    if configured_active_source_count is None:
        configured_active_source_count = configured_source_count

    matched_subscription_source_count = (
        runtime_summary.get("matched_subscription_source_count") if isinstance(runtime_summary, dict) else None
    )
    if matched_subscription_source_count is None:
        matched_subscription_source_count = len(runtime_signal_sources) if runtime_signal_sources else 0

    return {
        "date": radar.get("date"),
        "generated_at": radar.get("generated_at"),
        "subscription_scope": radar.get("subscription_scope"),
        "configured_source_count": configured_source_count,
        "matched_subscription_source_count": matched_subscription_source_count,
        "configured_active_source_count": configured_active_source_count,
        "runtime_signal_sources": runtime_signal_sources,
    }


class PersonalContextUpdateRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class SubscriptionSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class SourceAssistantRequest(BaseModel):
    url: str = ""
    extra_context: str = ""


class SourceHealthRequest(BaseModel):
    sources: list[dict[str, Any]] = Field(default_factory=list)


class LegacyImportRequest(BaseModel):
    confirm: bool = True


class ReflectionSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


@router.get("/settings/context")
def get_personal_context(request: Request):
    user_id = resolve_request_user_id(request)
    context = load_personal_context_data(user_id)

    return {
        "user_id": user_id,
        "scope": get_context_scope(user_id),
        "context": context,
    }


@router.post("/settings/context", dependencies=[Depends(require_admin_auth)])
def save_personal_context(payload: PersonalContextUpdateRequest, request: Request):
    user_id = resolve_request_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="A user id header is required to save personal context.",
        )

    saved_path = save_personal_context_data(user_id, payload.context)

    return {
        "message": "Personal context saved successfully.",
        "user_id": user_id,
        "scope": "user_specific",
        "path": str(saved_path),
    }


@router.get("/settings/subscriptions")
def get_subscription_settings(request: Request):
    user_id = resolve_request_user_id(request)
    settings = load_subscription_settings(user_id)
    status = get_subscription_settings_status(user_id)
    runtime = _subscription_runtime_snapshot()

    return {
        "user_id": user_id,
        "scope": get_context_scope(user_id),
        "settings": settings,
        "status": status,
        "runtime": runtime,
    }


@router.get("/settings/model-routing")
def get_model_routing_status():
    diagnostics = router_startup_diagnostics()
    return {
        "message": "model routing diagnostics loaded successfully",
        "telemetry": load_route_summary(),
        **diagnostics,
    }


@router.get("/settings/reflection")
def get_reflection_settings(request: Request):
    user_id = resolve_request_user_id(request)
    settings = load_reflection_settings(user_id)
    status = get_reflection_settings_status(user_id)
    return {
        "user_id": user_id or "admin_default",
        "scope": get_context_scope(user_id),
        "settings": settings,
        "status": status,
    }


@router.post("/settings/reflection", dependencies=[Depends(require_admin_auth)])
def save_reflection_settings_route(payload: ReflectionSettingsUpdateRequest, request: Request):
    user_id = resolve_request_user_id(request)
    saved_path = save_reflection_settings(user_id, payload.settings)
    return {
        "message": "Reflection settings saved successfully.",
        "user_id": user_id or "admin_default",
        "scope": get_context_scope(user_id),
        "path": str(saved_path),
    }


@router.post("/settings/subscriptions", dependencies=[Depends(require_admin_auth)])
def save_subscriptions(payload: SubscriptionSettingsUpdateRequest, request: Request):
    user_id = resolve_request_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="A user id header is required to save subscription settings.",
        )

    print(
        "===== SETTINGS ROUTE: save_subscriptions "
        f"user_id={user_id!r} "
        f"source_count={len(payload.settings.get('sources', [])) if isinstance(payload.settings, dict) else 0} ====="
    )
    save_result = save_subscription_settings_with_status(user_id, payload.settings)
    saved_path = save_result.get("path")

    return {
        "message": "Subscription settings saved successfully.",
        "user_id": user_id,
        "scope": "user_specific",
        "path": str(saved_path),
        "local_saved": bool(save_result.get("local_saved")),
        "source_count": save_result.get("source_count"),
        "s3_sync": save_result.get("s3_sync"),
        "s3_bucket": save_result.get("s3_bucket"),
        "s3_key": save_result.get("s3_key"),
        "s3_error_type": save_result.get("s3_error_type"),
    }


@router.post("/settings/subscriptions/source-assistant", dependencies=[Depends(require_admin_auth)])
def source_assistant(payload: SourceAssistantRequest, request: Request):
    user_id = resolve_request_user_id(request)
    context = load_personal_context_data(user_id)
    suggestion = suggest_source_from_url(
        payload.url,
        user_context=jsonable_context(context),
        extra_context=payload.extra_context,
    )

    return {
        "user_id": user_id,
        "scope": get_context_scope(user_id),
        "suggestion": suggestion,
    }


@router.post("/settings/subscriptions/source-health", dependencies=[Depends(require_admin_auth)])
def source_health(payload: SourceHealthRequest):
    return check_subscription_source_health(payload.sources)


@router.post("/settings/subscriptions/import-legacy-rss", dependencies=[Depends(require_admin_auth)])
def import_legacy_sources(payload: LegacyImportRequest, request: Request):
    user_id = resolve_request_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="A user id header is required to import legacy sources.",
        )
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Legacy import confirmation is required.")

    result = import_legacy_rss_sources(user_id)
    return {
        "user_id": user_id,
        "scope": get_context_scope(user_id),
        **result,
    }


def jsonable_context(context: dict[str, Any]) -> str:
    try:
        return json.dumps(context, ensure_ascii=False, indent=2)
    except Exception:
        return ""
