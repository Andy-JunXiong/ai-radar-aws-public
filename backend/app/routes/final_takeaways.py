from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.admin_guard import require_admin_auth
from app.services import final_takeaway_artifact_service as artifact_service


router = APIRouter()


class ReviewBundleSnapshotRequest(BaseModel):
    signal_id: str
    source_text: str
    source_file: str = ""
    source_kind: str = "external_md"
    snapshot_reason: str = "final_takeaway_review_bundle"
    used_by: str = "confirmed_final_takeaway"
    created_by: str = "Andy"
    conversation_refs: list[Any] = []
    metadata: dict[str, Any] = {}


class ConfirmFinalTakeawayRequest(BaseModel):
    signal_id: str
    confirmed_text: str
    review_bundle_snapshot_id: str
    source_completion_note: str = ""
    confirmed_by: str = "Andy"
    provenance: dict[str, Any] = {}
    source_signal_id: str = ""


class ExternalSynthesisSourceRequest(BaseModel):
    signal_id: str
    source_text: str
    source_file: str = ""
    source_kind: str = "paste"
    content_type: str = ""
    created_by: str = "Andy"
    metadata: dict[str, Any] = {}


@router.post("/final-takeaways/external-synthesis-sources", dependencies=[Depends(require_admin_auth)])
def create_external_synthesis_source(payload: ExternalSynthesisSourceRequest):
    try:
        source = artifact_service.create_external_synthesis_source(
            signal_id=payload.signal_id,
            source_text=payload.source_text,
            source_file=payload.source_file,
            source_kind=payload.source_kind,
            content_type=payload.content_type,
            created_by=payload.created_by,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "source": source,
        "message": "external synthesis source saved successfully",
    }


@router.get("/final-takeaways/external-synthesis-sources", dependencies=[Depends(require_admin_auth)])
def list_external_synthesis_sources(signal_id: str = Query(default="")):
    return {
        "items": artifact_service.list_external_synthesis_sources(signal_id=signal_id),
        "message": "external synthesis sources loaded successfully",
    }


@router.get("/final-takeaways/external-synthesis-sources/{source_id}", dependencies=[Depends(require_admin_auth)])
def get_external_synthesis_source(source_id: str):
    source = artifact_service.get_external_synthesis_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="external synthesis source not found")
    return {
        "source": source,
        "message": "external synthesis source loaded successfully",
    }


@router.post("/final-takeaways/review-bundle-snapshots", dependencies=[Depends(require_admin_auth)])
def create_review_bundle_snapshot(payload: ReviewBundleSnapshotRequest):
    try:
        snapshot = artifact_service.create_review_bundle_snapshot(
            signal_id=payload.signal_id,
            source_text=payload.source_text,
            source_file=payload.source_file,
            source_kind=payload.source_kind,
            snapshot_reason=payload.snapshot_reason,
            used_by=payload.used_by,
            created_by=payload.created_by,
            conversation_refs=payload.conversation_refs,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "snapshot": snapshot,
        "message": "review bundle snapshot created successfully",
    }


@router.get("/final-takeaways/review-bundle-snapshots", dependencies=[Depends(require_admin_auth)])
def list_review_bundle_snapshots(signal_id: str = Query(default="")):
    return {
        "items": artifact_service.list_review_bundle_snapshots(signal_id=signal_id),
        "message": "review bundle snapshots loaded successfully",
    }


@router.get("/final-takeaways/review-bundle-snapshots/{snapshot_id}", dependencies=[Depends(require_admin_auth)])
def get_review_bundle_snapshot(snapshot_id: str):
    snapshot = artifact_service.get_review_bundle_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="review bundle snapshot not found")
    return {
        "snapshot": snapshot,
        "message": "review bundle snapshot loaded successfully",
    }


@router.post("/final-takeaways/confirm", dependencies=[Depends(require_admin_auth)])
def confirm_final_takeaway(payload: ConfirmFinalTakeawayRequest):
    try:
        final_takeaway = artifact_service.confirm_final_takeaway(
            signal_id=payload.signal_id,
            confirmed_text=payload.confirmed_text,
            review_bundle_snapshot_id=payload.review_bundle_snapshot_id,
            source_completion_note=payload.source_completion_note,
            confirmed_by=payload.confirmed_by,
            provenance=payload.provenance,
            source_signal_id=payload.source_signal_id,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        "final_takeaway": final_takeaway,
        "message": "final takeaway confirmed successfully",
    }


@router.get("/final-takeaways", dependencies=[Depends(require_admin_auth)])
def list_final_takeaways(signal_id: str = Query(default="")):
    return {
        "items": artifact_service.list_final_takeaways(signal_id=signal_id),
        "message": "final takeaways loaded successfully",
    }


@router.get("/final-takeaways/{final_takeaway_id}", dependencies=[Depends(require_admin_auth)])
def get_final_takeaway(final_takeaway_id: str):
    final_takeaway = artifact_service.get_final_takeaway(final_takeaway_id)
    if not final_takeaway:
        raise HTTPException(status_code=404, detail="final takeaway not found")
    return {
        "final_takeaway": final_takeaway,
        "message": "final takeaway loaded successfully",
    }
