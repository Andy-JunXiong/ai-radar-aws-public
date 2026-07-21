from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


INPUT_PROVENANCE_SCHEMA_VERSION = 1
DEFAULT_PROJECT_CONTEXT_CACHE_TTL_HOURS = 12
DEFAULT_PROJECT_REPO_SNAPSHOT_TTL_HOURS = 168
DEFAULT_SIGNAL_STALE_AFTER_DAYS = 30
STALE_FLAG_PENALTY = 0.1
MAX_FRESHNESS_PENALTY = 0.4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now(value: Any) -> datetime:
    parsed = _parse_datetime(value)
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def _source_excerpt_length(signal: dict[str, Any]) -> int:
    explicit = _safe_int(signal.get("source_excerpt_length"))
    if explicit:
        return explicit
    source_excerpt = _safe_text(signal.get("source_excerpt"))
    return len(source_excerpt) if source_excerpt else 0


def _append_age_flag(
    stale_flags: list[str],
    *,
    value: Any,
    now: datetime,
    max_age: timedelta,
    stale_flag: str,
    missing_flag: str = "",
    invalid_flag: str = "",
) -> None:
    text = _safe_text(value)
    if not text:
        if missing_flag:
            stale_flags.append(missing_flag)
        return

    parsed = _parse_datetime(text)
    if parsed is None:
        if invalid_flag:
            stale_flags.append(invalid_flag)
        return

    if parsed < now - max_age:
        stale_flags.append(stale_flag)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _safe_text(value)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _freshness_summary(stale_flags: list[str]) -> str:
    if not stale_flags:
        return "No stale input detected."
    return f"Stale input detected: {', '.join(stale_flags)}."


def _freshness_penalty(stale_flags: list[str]) -> float:
    return round(min(MAX_FRESHNESS_PENALTY, len(stale_flags) * STALE_FLAG_PENALTY), 3)


def build_input_provenance_snapshot(
    *,
    signal: dict[str, Any] | None = None,
    context_scope: str = "",
    user_context_captured_at: str = "",
    project_repo_snapshot: dict[str, Any] | None = None,
    project_context_cache: dict[str, Any] | None = None,
    project_context_cache_ttl_hours: int | float | str = DEFAULT_PROJECT_CONTEXT_CACHE_TTL_HOURS,
    captured_at: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    signal_payload = dict(signal) if isinstance(signal, dict) else {}
    repo_snapshot = dict(project_repo_snapshot) if isinstance(project_repo_snapshot, dict) else {}
    context_cache = dict(project_context_cache) if isinstance(project_context_cache, dict) else {}

    effective_now = _now(now or captured_at)
    captured = _safe_text(captured_at) or effective_now.replace(microsecond=0).isoformat()
    ttl_hours = _safe_float(project_context_cache_ttl_hours, DEFAULT_PROJECT_CONTEXT_CACHE_TTL_HOURS)
    if ttl_hours <= 0:
        ttl_hours = DEFAULT_PROJECT_CONTEXT_CACHE_TTL_HOURS

    published_at = _safe_text(signal_payload.get("published_at"))
    collected_at = _safe_text(signal_payload.get("collected_at"))
    repo_scanned_at = _safe_text(repo_snapshot.get("scanned_at"))
    repo_status = _safe_text(repo_snapshot.get("status"))
    cache_fetched_at = _safe_text(context_cache.get("fetched_at"))

    stale_flags: list[str] = []
    signal_timestamp = published_at or collected_at
    _append_age_flag(
        stale_flags,
        value=signal_timestamp,
        now=effective_now,
        max_age=timedelta(days=DEFAULT_SIGNAL_STALE_AFTER_DAYS),
        stale_flag="signal_timestamp_stale",
        invalid_flag="signal_timestamp_invalid",
    )
    if repo_status.lower() == "stale":
        stale_flags.append("project_repo_snapshot_status_stale")
    _append_age_flag(
        stale_flags,
        value=repo_scanned_at,
        now=effective_now,
        max_age=timedelta(hours=DEFAULT_PROJECT_REPO_SNAPSHOT_TTL_HOURS),
        stale_flag="project_repo_snapshot_stale",
        invalid_flag="project_repo_snapshot_timestamp_invalid",
    )
    _append_age_flag(
        stale_flags,
        value=cache_fetched_at,
        now=effective_now,
        max_age=timedelta(hours=ttl_hours),
        stale_flag="project_context_cache_stale",
        invalid_flag="project_context_cache_timestamp_invalid",
    )

    stale_flags = _dedupe(stale_flags)

    return {
        "schema_version": INPUT_PROVENANCE_SCHEMA_VERSION,
        "captured_at": captured,
        "signal": {
            "published_at": published_at,
            "collected_at": collected_at,
            "source_excerpt_length": _source_excerpt_length(signal_payload),
        },
        "user_context": {
            "context_scope": _safe_text(context_scope),
            "captured_at": _safe_text(user_context_captured_at),
        },
        "project_context": {
            "repo_snapshot_scanned_at": repo_scanned_at,
            "repo_snapshot_status": repo_status,
        },
        "project_context_cache": {
            "fetched_at": cache_fetched_at,
            "ttl_hours": ttl_hours,
        },
        "freshness": {
            "stale_flags": stale_flags,
            "freshness_penalty": _freshness_penalty(stale_flags),
            "summary": _freshness_summary(stale_flags),
        },
    }
