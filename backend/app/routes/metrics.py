import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.admin_guard import require_admin_auth
from app.services.metrics_summary_service import load_daily_metrics_summary
from app.services.metrics_summary_service import load_metrics_summaries
from app.services.metrics_summary_service import load_metrics_status


router = APIRouter()


@router.get("/metrics/daily-summary", dependencies=[Depends(require_admin_auth)])
def get_metrics_daily_summary(date: str | None = Query(default=None)):
    if date is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format.")

    payload = load_daily_metrics_summary(date)
    if payload is None:
        raise HTTPException(status_code=404, detail="Metrics daily summary not found.")

    return {
        **payload,
        "message": "metrics daily summary loaded successfully",
    }


@router.get("/metrics/status", dependencies=[Depends(require_admin_auth)])
def get_metrics_status():
    return {
        **load_metrics_status(),
        "message": "metrics status loaded successfully",
    }


@router.get("/metrics/summaries", dependencies=[Depends(require_admin_auth)])
def get_metrics_summaries(
    category: str = Query(default="daily_summary"),
    through_date: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=366),
):
    if category not in {"daily_summary", "weekly_summary", "monthly_summary"}:
        raise HTTPException(
            status_code=400,
            detail="category must be daily_summary, weekly_summary, or monthly_summary.",
        )
    if through_date is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", through_date):
        raise HTTPException(status_code=400, detail="through_date must use YYYY-MM-DD format.")

    return {
        "category": category,
        "through_date": through_date,
        "limit": limit,
        "summaries": load_metrics_summaries(
            category,
            through_date=through_date,
            limit=limit,
        ),
        "message": "metrics summaries loaded successfully",
    }
