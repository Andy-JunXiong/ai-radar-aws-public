from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.admin_guard import require_admin_auth
from app.services import signal_review_feedback_service as feedback_service


router = APIRouter()


class CreateSignalReviewFeedbackRequest(BaseModel):
    signal_id: str
    claim_id: str
    reason_slot: str
    note: str
    insight_id: str = ""
    content_fingerprint: str = ""
    claim_text_snapshot: str = ""
    claim_source_field: str = ""
    distortion_tags: list[str] = Field(default_factory=list)
    verification_snapshot: dict[str, Any] = Field(default_factory=dict)
    input_provenance_snapshot: dict[str, Any] = Field(default_factory=dict)
    relationship_annotation: dict[str, Any] = Field(default_factory=dict)


class BackgroundUpdateCandidateDecisionRequest(BaseModel):
    decision: str
    note: str = ""


def _validate_reason_slot_filter(reason_slot: str | None) -> str | None:
    if reason_slot is None:
        return None
    normalized = reason_slot.strip().lower()
    if not normalized:
        return None
    if normalized not in feedback_service.REASON_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"reason_slot must be one of: {', '.join(sorted(feedback_service.REASON_SLOTS))}.",
        )
    return normalized


def _validate_background_candidate_reason_slot_filter(reason_slot: str | None) -> str | None:
    normalized = _validate_reason_slot_filter(reason_slot)
    if normalized is None:
        return None
    if normalized not in feedback_service.BACKGROUND_UPDATE_REASON_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "background update candidates can only be filtered by: "
                f"{', '.join(sorted(feedback_service.BACKGROUND_UPDATE_REASON_SLOTS))}."
            ),
        )
    return normalized


@router.get("/signal-review-feedback", dependencies=[Depends(require_admin_auth)])
def get_signal_review_feedback_records(
    signal_id: str | None = Query(default=None),
    claim_id: str | None = Query(default=None),
    reason_slot: str | None = Query(default=None),
):
    normalized_reason_slot = _validate_reason_slot_filter(reason_slot)
    records = feedback_service.list_signal_review_feedback_records(
        signal_id=signal_id,
        claim_id=claim_id,
        reason_slot=normalized_reason_slot,
    )
    return {"records": records, "count": len(records)}


@router.get("/signal-review-feedback/background-update-candidates", dependencies=[Depends(require_admin_auth)])
def get_background_update_candidates(
    signal_id: str | None = Query(default=None),
    reason_slot: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    normalized_reason_slot = _validate_background_candidate_reason_slot_filter(reason_slot)
    candidates = feedback_service.list_background_update_candidates(
        signal_id=signal_id,
        reason_slot=normalized_reason_slot,
        limit=limit,
    )
    return {
        "schema_version": 1,
        "queue_type": "background_update_candidate_queue",
        "candidate_status": feedback_service.BACKGROUND_UPDATE_CANDIDATE_STATUS,
        "evidence_boundary": feedback_service.EVIDENCE_BOUNDARY_NOT_EXTERNAL_CLAIM_EVIDENCE,
        "allowed_reason_slots": sorted(feedback_service.BACKGROUND_UPDATE_REASON_SLOTS),
        "records": candidates,
        "count": len(candidates),
        "message": "Background update candidates are inactive until explicit human confirmation.",
    }


@router.post("/signal-review-feedback/background-update-candidates/{candidate_id}/decision", dependencies=[Depends(require_admin_auth)])
def post_background_update_candidate_decision(candidate_id: str, payload: BackgroundUpdateCandidateDecisionRequest):
    candidate = feedback_service.find_background_update_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="background update candidate not found.")

    try:
        decision = feedback_service.append_background_update_candidate_decision(
            candidate_id=candidate_id,
            source_feedback_id=str(candidate.get("source_feedback_id") or ""),
            decision=payload.decision,
            note=payload.note,
            candidate_snapshot=candidate,
            created_by="human",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": "background update candidate decision recorded successfully",
        "record": decision,
        "candidate": {
            **candidate,
            "latest_decision": feedback_service.summarize_background_update_candidate_decision(decision),
        },
    }


@router.post("/signal-review-feedback", dependencies=[Depends(require_admin_auth)])
def post_signal_review_feedback_record(payload: CreateSignalReviewFeedbackRequest):
    try:
        record = feedback_service.append_signal_review_feedback_record(
            signal_id=payload.signal_id,
            insight_id=payload.insight_id,
            content_fingerprint=payload.content_fingerprint,
            claim_id=payload.claim_id,
            claim_text_snapshot=payload.claim_text_snapshot,
            claim_source_field=payload.claim_source_field,
            reason_slot=payload.reason_slot,
            distortion_tags=payload.distortion_tags,
            note=payload.note,
            verification_snapshot=payload.verification_snapshot,
            input_provenance_snapshot=payload.input_provenance_snapshot,
            relationship_annotation=payload.relationship_annotation,
            created_by="human",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "signal review feedback recorded successfully", "record": record}
