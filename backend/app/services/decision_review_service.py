from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.decision_card_service import list_decision_cards


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
INDEX_PATH = DATA_DIR / "index.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _review_path(review_id: str) -> Path:
    safe = str(review_id).replace("/", "_").replace("\\", "_")
    return DATA_DIR / f"{safe}.json"


def _load_index() -> list[dict[str, Any]]:
    _ensure_data_dir()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass
    return []


def _save_index(items: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def build_review_record(
    *,
    decision_card_id: str,
    review_date: str | None = None,
    outcome: str = "unclear",
    what_happened: str = "",
    confidence_adjustment: int = 0,
    notes: str = "",
    status: str = "draft",
) -> dict[str, Any]:
    review_id = f"rv_{uuid.uuid4().hex[:12]}"
    created_at = _utc_now_iso()
    return {
        "id": review_id,
        "decision_card_id": decision_card_id,
        "review_date": review_date or created_at,
        "outcome": outcome,
        "what_happened": what_happened.strip(),
        "confidence_adjustment": confidence_adjustment,
        "notes": notes.strip(),
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
    }


def save_review_record(review: dict[str, Any]) -> dict[str, Any]:
    _ensure_data_dir()
    _review_path(review["id"]).write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    items = [item for item in _load_index() if item.get("id") != review["id"]]
    items.append(
        {
            "id": review["id"],
            "decision_card_id": review.get("decision_card_id"),
            "review_date": review.get("review_date"),
            "status": review.get("status"),
            "updated_at": review.get("updated_at"),
        }
    )
    _save_index(sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return review


def get_review_record(review_id: str) -> dict[str, Any] | None:
    path = _review_path(review_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def list_due_reviews(*, due_before: str | None = None) -> list[dict[str, Any]]:
    cutoff = due_before or _utc_now_iso()
    items: list[dict[str, Any]] = []
    for item in _load_index():
        review = get_review_record(str(item.get("id") or ""))
        if not review:
            continue
        if str(review.get("status") or "") == "completed":
            continue
        if str(review.get("review_date") or "") <= cutoff:
            items.append(review)
    return items


def ensure_due_review_drafts(*, due_before: str | None = None) -> list[dict[str, Any]]:
    cutoff = due_before or _utc_now_iso()
    existing_reviews = list_reviews()
    open_review_ids = {
        str(review.get("decision_card_id") or "")
        for review in existing_reviews
        if str(review.get("status") or "") != "completed"
    }

    created: list[dict[str, Any]] = []
    for card in list_decision_cards():
        card_id = str(card.get("id") or "")
        review_at = str(card.get("review_at") or "")
        status = str(card.get("status") or "")
        if not card_id or not review_at:
            continue
        if review_at > cutoff:
            continue
        if status == "reviewed":
            continue
        if card_id in open_review_ids:
            continue

        review = build_review_record(
            decision_card_id=card_id,
            review_date=review_at,
            outcome="unclear",
            what_happened="",
            confidence_adjustment=0,
            notes="",
            status="draft",
        )
        save_review_record(review)
        created.append(review)
        open_review_ids.add(card_id)

    return created


def list_reviews(
    *,
    decision_card_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in _load_index():
        review = get_review_record(str(item.get("id") or ""))
        if not review:
            continue
        if decision_card_id and str(review.get("decision_card_id") or "") != decision_card_id:
            continue
        if status and str(review.get("status") or "") != status:
            continue
        items.append(review)
    return sorted(items, key=lambda review: str(review.get("updated_at") or ""), reverse=True)


def complete_review(
    *,
    review_id: str,
    outcome: str,
    what_happened: str,
    confidence_adjustment: int,
    notes: str,
) -> dict[str, Any]:
    review = get_review_record(review_id)
    if not review:
        raise ValueError("Review record not found.")
    review["outcome"] = outcome
    review["what_happened"] = what_happened.strip()
    review["confidence_adjustment"] = confidence_adjustment
    review["notes"] = notes.strip()
    review["status"] = "completed"
    review["updated_at"] = _utc_now_iso()
    return save_review_record(review)
