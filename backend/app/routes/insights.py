from fastapi import APIRouter
from datetime import datetime, timezone
from app.services.s3_reader import load_insights

router = APIRouter()

DEFAULT_COLLECTED_AT = datetime.now(timezone.utc).isoformat()

def normalize_insight(insight: dict, index: int):
    signal_title = insight.get("signal_title") or insight.get("title") or f"Untitled signal {index + 1}"
    signal_summary = insight.get("signal_summary") or insight.get("summary") or ""
    source = insight.get("source") or "Unknown"

    published_at = insight.get("published_at") or insight.get("publish_time") or insight.get("published_time")
    collected_at = insight.get("collected_at") or insight.get("created_at") or DEFAULT_COLLECTED_AT
    status = insight.get("status") or "pending"

    why_it_matters = insight.get("why_it_matters") or insight.get("insight") or ""
    synthesized_insight = insight.get("synthesized_insight") or insight.get("strategy") or ""

    return {
        "id": index,
        "signal_title": signal_title,
        "signal_summary": signal_summary,
        "source": source,
        "published_at": published_at,
        "collected_at": collected_at,
        "status": status,
        "why_it_matters": why_it_matters,
        "relevance_to_projects": insight.get("relevance_to_projects", ""),
        "relevance_to_career": insight.get("relevance_to_career", ""),
        "synthesized_insight": synthesized_insight,
        "raw": insight,
    }

@router.get("/insights")
def get_insights():
    items = load_insights()
    if not isinstance(items, list):
        items = items.get("items", [])

    normalized = [normalize_insight(item, i) for i, item in enumerate(items)]
    return {"items": normalized}