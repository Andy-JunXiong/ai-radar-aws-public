from pathlib import Path
import json

from fastapi import APIRouter
from app.config import BASE_DIR

router = APIRouter(prefix="/feed", tags=["feed"])

OUTPUT_DIR = BASE_DIR / "data" / "output"
FEED_ACTIVITY_FILE = OUTPUT_DIR / "feed_activity.json"


@router.get("/activity")
def get_feed_activity():
    if not FEED_ACTIVITY_FILE.exists():
        return {
            "items": [],
            "summary": {
                "total_days": 0,
                "total_rss_fetched": 0,
                "total_new_signals": 0,
                "latest_date": None,
            },
        }

    try:
        with open(FEED_ACTIVITY_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)

        if not isinstance(items, list):
            items = []

    except Exception as e:
        return {
            "items": [],
            "summary": {
                "total_days": 0,
                "total_rss_fetched": 0,
                "total_new_signals": 0,
                "latest_date": None,
                "error": str(e),
            },
        }

    # Deduplicate by retaining only the last item for each day.
    deduped = {}
    for item in items:
        date = item.get("date")
        if date:
            deduped[date] = {
                "date": date,
                "rss_fetched": int(item.get("rss_fetched", 0) or 0),
                "new_signals": int(item.get("new_signals", 0) or 0),
            }

    sorted_items = sorted(
        deduped.values(),
        key=lambda x: x["date"],
        reverse=True,
    )

    summary = {
        "total_days": len(sorted_items),
        "total_rss_fetched": sum(x["rss_fetched"] for x in sorted_items),
        "total_new_signals": sum(x["new_signals"] for x in sorted_items),
        "latest_date": sorted_items[0]["date"] if sorted_items else None,
    }

    return {
        "items": sorted_items,
        "summary": summary,
    }
