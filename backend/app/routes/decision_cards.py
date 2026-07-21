from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.admin_guard import require_admin_auth
from app.services.decision_card_service import (
    generate_decision_card_from_context,
    get_decision_card,
    list_decision_cards,
    update_decision_feedback,
)


router = APIRouter()


class DecisionCardGenerateRequest(BaseModel):
    title: str
    signal_refs: list[str] = []
    project_refs: list[str] = []
    importance_score: float | None = None
    source_context: str | None = None
    context_payload: dict


class DecisionFeedbackRequest(BaseModel):
    user_action: str
    action_notes: str = ""


@router.get("/decision-cards", dependencies=[Depends(require_admin_auth)])
def get_decision_cards(
    status: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    source_context: str | None = Query(default=None),
):
    items = list_decision_cards(
        status=status,
        signal_id=signal_id,
        project_id=project_id,
        source_context=source_context,
    )
    return {"items": items, "count": len(items)}


@router.post("/decision-cards/generate", dependencies=[Depends(require_admin_auth)])
def post_generate_decision_card(payload: DecisionCardGenerateRequest):
    try:
        card = generate_decision_card_from_context(
            title=payload.title,
            signal_refs=payload.signal_refs,
            project_refs=payload.project_refs,
            context_payload=payload.context_payload,
            importance_score=payload.importance_score,
            source_context=payload.source_context,
        )
        return {"message": "decision card generated successfully", "card": card}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate decision card: {exc}") from exc


@router.get("/decision-cards/{card_id}", dependencies=[Depends(require_admin_auth)])
def get_decision_card_detail(card_id: str):
    card = get_decision_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Decision card not found.")
    return {"card": card}


@router.post("/decision-cards/{card_id}/feedback", dependencies=[Depends(require_admin_auth)])
def post_decision_feedback(card_id: str, payload: DecisionFeedbackRequest):
    try:
        updated = update_decision_feedback(
            card_id=card_id,
            feedback_id=f"fb_{card_id}",
            user_action=payload.user_action,
            action_notes=payload.action_notes,
            updated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        return {"message": "decision feedback saved successfully", "card": updated}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
