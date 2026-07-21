from datetime import datetime, timezone
from typing import Any, Dict

from app.services.manual_cache import build_session_analysis_hash


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_session_analysis(
    session: Dict[str, Any],
    analysis: Dict[str, Any],
    provider_used: str,
    fallback_used: bool,
    analysis_model: str,
) -> Dict[str, Any]:
    session["analysis"] = analysis
    session["analysis_status"] = "completed"
    session["analysis_hash"] = build_session_analysis_hash(session)
    session["analysis_cached"] = False
    session["provider_used"] = provider_used
    session["fallback_used"] = fallback_used
    session["analysis_model"] = analysis_model
    session["analysis_updated_at"] = utc_now_iso()
    return session

def mark_session_analysis_failed(session: Dict[str, Any], message: str):
    session["analysis_status"] = "failed"
    session["analysis_error"] = message
    session["analysis_cached"] = False
    session["analysis_updated_at"] = utc_now_iso()
    return session