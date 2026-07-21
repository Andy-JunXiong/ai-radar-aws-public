from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.admin_guard import require_admin_auth
from app.services.decision_card_service import attach_review_to_decision
from app.services.decision_memory_service import get_learning_summary, refresh_learning_summary
from app.services.decision_review_service import (
    build_review_record,
    complete_review,
    ensure_due_review_drafts,
    list_reviews,
    list_due_reviews,
    save_review_record,
)


router = APIRouter()


class CreateReviewRequest(BaseModel):
    decision_card_id: str
    review_date: str | None = None
    outcome: str = "unclear"
    what_happened: str = ""
    confidence_adjustment: int = 0
    notes: str = ""


class CompleteReviewRequest(BaseModel):
    outcome: str
    what_happened: str
    confidence_adjustment: int = 0
    notes: str = ""


@router.get("/reviews/due", dependencies=[Depends(require_admin_auth)])
def get_due_reviews(due_before: str | None = Query(default=None)):
    ensure_due_review_drafts(due_before=due_before)
    items = list_due_reviews(due_before=due_before)
    return {"items": items, "count": len(items)}


@router.get("/reviews", dependencies=[Depends(require_admin_auth)])
def get_reviews(
    decision_card_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    items = list_reviews(decision_card_id=decision_card_id, status=status)
    return {"items": items, "count": len(items)}


@router.get("/reviews/learning-summary", dependencies=[Depends(require_admin_auth)])
def get_reviews_learning_summary():
    return {"summary": get_learning_summary()}


@router.post("/reviews", dependencies=[Depends(require_admin_auth)])
def post_create_review(payload: CreateReviewRequest):
    review = build_review_record(
        decision_card_id=payload.decision_card_id,
        review_date=payload.review_date,
        outcome=payload.outcome,
        what_happened=payload.what_happened,
        confidence_adjustment=payload.confidence_adjustment,
        notes=payload.notes,
        status="draft",
    )
    saved = save_review_record(review)
    return {"message": "review created successfully", "review": saved}


@router.post("/reviews/{review_id}/complete", dependencies=[Depends(require_admin_auth)])
def post_complete_review(review_id: str, payload: CompleteReviewRequest):
    try:
        review = complete_review(
            review_id=review_id,
            outcome=payload.outcome,
            what_happened=payload.what_happened,
            confidence_adjustment=payload.confidence_adjustment,
            notes=payload.notes,
        )
        attach_review_to_decision(
            review["decision_card_id"],
            review["id"],
            review_date=review["updated_at"],
        )
        summary = refresh_learning_summary()
        return {"message": "review completed successfully", "review": review, "summary": summary}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
