from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.admin_guard import require_admin_auth
from app.services import dev_inbox_draft_service as draft_service


router = APIRouter()


class DevInboxDraftRequest(BaseModel):
    id: str = ""
    repo: str = ""
    branch: str = ""
    requestType: str = "bug"
    priority: str = "normal"
    surface: str = ""
    task: str
    savedAt: str = ""
    status: str = "open"


class DevInboxDraftStatusRequest(BaseModel):
    status: str


@router.get("/dev-inbox/drafts", dependencies=[Depends(require_admin_auth)])
def get_dev_inbox_drafts():
    try:
        drafts = draft_service.list_dev_inbox_drafts()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "drafts": drafts,
        "count": len(drafts),
        "storage": draft_service.get_dev_inbox_storage_status(),
    }


@router.post("/dev-inbox/drafts", dependencies=[Depends(require_admin_auth)])
def post_dev_inbox_draft(payload: DevInboxDraftRequest):
    try:
        draft_payload = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        draft = draft_service.upsert_dev_inbox_draft(draft_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "message": "dev inbox draft saved successfully",
        "draft": draft,
        "storage": draft_service.get_dev_inbox_storage_status(),
    }


@router.patch("/dev-inbox/drafts/{draft_id}", dependencies=[Depends(require_admin_auth)])
def patch_dev_inbox_draft(draft_id: str, payload: DevInboxDraftStatusRequest):
    try:
        draft = draft_service.update_dev_inbox_draft_status(draft_id, payload.status)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "draft not found." else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "message": "dev inbox draft updated successfully",
        "draft": draft,
        "storage": draft_service.get_dev_inbox_storage_status(),
    }


@router.delete("/dev-inbox/drafts/{draft_id}", dependencies=[Depends(require_admin_auth)])
def delete_dev_inbox_draft(draft_id: str) -> dict[str, Any]:
    try:
        deleted = draft_service.delete_dev_inbox_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="draft not found.")
    return {
        "message": "dev inbox draft deleted successfully",
        "deleted": True,
        "storage": draft_service.get_dev_inbox_storage_status(),
    }
