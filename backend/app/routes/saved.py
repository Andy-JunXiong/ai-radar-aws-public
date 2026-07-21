from fastapi import APIRouter
from app.services.s3_reader import load_signals

router = APIRouter(prefix="/saved", tags=["saved"])


@router.get("")
def get_saved_signals():
    try:
        signals = load_signals()
    except Exception as e:
        return {
            "items": [],
            "summary": {
                "count": 0,
                "error": str(e),
            },
        }

    if not isinstance(signals, list):
        signals = []

    saved_items = []

    for item in signals:
        status = (item.get("status") or "pending").lower()
        if status == "saved":
            saved_items.append(
                {
                    "id": item.get("id") or item.get("url") or item.get("title"),
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("published_at"),
                    "collected_at": item.get("collected_at"),
                    "saved_reason": item.get("saved_reason", ""),
                    "status": status,
                    "topic": item.get("topic", ""),
                    "importance_level": item.get("importance_level", ""),
                }
            )

    saved_items = sorted(
        saved_items,
        key=lambda x: x.get("collected_at") or "",
        reverse=True,
    )

    return {
        "items": saved_items,
        "summary": {
            "count": len(saved_items),
        },
    }
