from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.admin_guard import require_admin_auth
from app.services.request_identity import resolve_request_user_id
from app.services import ai_discussion_memory_write_entry_service as write_entry_service


router = APIRouter()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AiDiscussionMemorySourceRequest(_StrictModel):
    source_label: str = ""
    source_url: str = ""
    provider: str = ""
    captured_from: str = ""


class AiDiscussionMemoryMessageRefRequest(_StrictModel):
    message_id: str
    role: str = ""
    sequence: Any = None
    content_excerpt: str
    content_fingerprint: str = ""


class AiDiscussionMemoryCaptureRequest(_StrictModel):
    source: AiDiscussionMemorySourceRequest = Field(default_factory=AiDiscussionMemorySourceRequest)
    message_refs: list[AiDiscussionMemoryMessageRefRequest] = Field(default_factory=list)
    discussion_excerpt: str = ""
    discussion_fingerprint: str
    selection_reason: str = ""


class AiDiscussionGovernedClaimRequest(_StrictModel):
    claim_text: str
    claim_posture: str = "discussion_judgment"
    asserted_subject: dict[str, Any] = Field(default_factory=dict)
    boundary_review: dict[str, Any] | None = None
    verification_ref: dict[str, Any] | None = None
    claim_snapshot: dict[str, Any] | None = None
    salience: dict[str, Any] | None = None


class AiDiscussionMemorySelectionRequest(_StrictModel):
    capture: AiDiscussionMemoryCaptureRequest
    governed_claims: list[AiDiscussionGovernedClaimRequest] = Field(default_factory=list)


def _route_actor(request: Request) -> dict[str, str]:
    return {
        "type": "human",
        "id": resolve_request_user_id(request) or "admin_default",
    }


def _service_request(payload: AiDiscussionMemorySelectionRequest, request: Request) -> dict[str, Any]:
    capture = payload.capture
    source = capture.source
    return {
        "caller": {
            "caller_type": write_entry_service.CALLER_EXPLICIT_SELECTION,
            "actor": _route_actor(request),
        },
        "capture": {
            "source": {
                "source_type": "ai_discussion_session",
                "source_label": source.source_label,
                "source_url": source.source_url,
                "provider": source.provider,
                "captured_from": source.captured_from,
            },
            "message_refs": [
                ref.model_dump() for ref in capture.message_refs
            ],
            "discussion_excerpt": capture.discussion_excerpt,
            "discussion_fingerprint": capture.discussion_fingerprint,
            "selection_reason": capture.selection_reason,
        },
        "governed_claims": [
            claim.model_dump() for claim in payload.governed_claims
        ],
    }


@router.post("/ai-discussion-memory/selections", dependencies=[Depends(require_admin_auth)])
def post_ai_discussion_memory_selection(payload: AiDiscussionMemorySelectionRequest, request: Request):
    try:
        record = write_entry_service.create_ai_discussion_memory_from_selection(_service_request(payload, request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "message": "AI Discussion memory selection recorded successfully",
        "record": record,
    }
