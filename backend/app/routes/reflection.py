from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.admin_guard import require_admin_auth

from app.services.reflection_service import (
    apply_vnext_backfill_to_source,
    create_vnext_backfill_drafts_batch,
    create_vnext_backfill_draft,
    find_related_reflections,
    get_explicit_relationship_index,
    get_explicit_relationships_for_reflection,
    get_reflection_full,
    get_relationship_analytics,
    get_related_manual_sessions,
    get_related_signals,
    get_sync_state,
    get_vnext_backfill_suggestion,
    get_vnext_backfill_preview,
    list_reflections,
    trigger_sync,
)


router = APIRouter(prefix="/reflection", tags=["reflection"])


@router.get("")
def reflection_list(
    q: str = "",
    tags: Annotated[list[str] | None, Query()] = None,
    source: str = "",
    limit: int = 100,
):
    return list_reflections(q=q, tags=tags, source=source, limit=limit)


@router.get("/sync/status")
def reflection_sync_status():
    return get_sync_state()


@router.post("/sync", dependencies=[Depends(require_admin_auth)])
def reflection_sync(force_full: bool = False):
    return trigger_sync(force_full=force_full).model_dump(mode="json")


@router.get("/sync/run")
def reflection_sync_run(force_full: bool = False):
    return trigger_sync(force_full=True if force_full is False else force_full).model_dump(mode="json")


@router.get("/related")
def reflection_related(
    q: str = "",
    topics: Annotated[list[str] | None, Query()] = None,
    limit: int = 5,
):
    return find_related_reflections(q=q, topics=topics, limit=limit)


@router.get("/analytics")
def reflection_analytics(days: int = 30, limit: int = 5):
    return get_relationship_analytics(days=days, limit=limit)


@router.get("/relationships")
def reflection_relationship_index():
    return get_explicit_relationship_index()


@router.get("/backfill-preview")
def reflection_backfill_preview(limit: int = 10):
    return get_vnext_backfill_preview(limit=limit)


@router.get("/{reflection_id}/backfill-preview")
def reflection_backfill_preview_detail(reflection_id: str):
    result = get_vnext_backfill_suggestion(reflection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result


@router.post("/{reflection_id}/backfill-draft", dependencies=[Depends(require_admin_auth)])
def reflection_backfill_draft_create(reflection_id: str):
    result = create_vnext_backfill_draft(reflection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result


@router.post("/{reflection_id}/backfill-apply", dependencies=[Depends(require_admin_auth)])
def reflection_backfill_apply(reflection_id: str):
    result = apply_vnext_backfill_to_source(reflection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result


@router.post("/backfill-drafts/batch", dependencies=[Depends(require_admin_auth)])
def reflection_backfill_draft_batch_create(limit: int = 10):
    return create_vnext_backfill_drafts_batch(limit=limit)


@router.get("/{reflection_id}")
def reflection_detail(reflection_id: str):
    result = get_reflection_full(reflection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result


@router.get("/{reflection_id}/related-signals")
def reflection_related_signals(reflection_id: str, days: int = 30):
    return get_related_signals(reflection_id, days=days)


@router.get("/{reflection_id}/related-manual-sessions")
def reflection_related_manual_sessions(reflection_id: str, limit: int = 10):
    return get_related_manual_sessions(reflection_id, limit=limit)


@router.get("/{reflection_id}/relationships")
def reflection_relationships(reflection_id: str):
    result = get_explicit_relationships_for_reflection(reflection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result
