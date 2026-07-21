import json
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.model_router_service import ModelRoute


TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "data" / "output"
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

TELEMETRY_EVENTS_PATH = TELEMETRY_DIR / "model_router_usage.jsonl"
TELEMETRY_SUMMARY_PATH = TELEMETRY_DIR / "model_router_usage_summary.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_summary() -> dict:
    return {
        "total_events": 0,
        "last_event_at": None,
        "providers": {},
        "tiers": {},
        "tasks": {},
        "modes": {},
        "models": {},
        "outcomes": {},
        "fallback_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "success_rate": 0.0,
        "failure_rate": 0.0,
        "recent_window_size": 0,
        "recent_providers": {},
        "recent_models": {},
        "recent_tasks": {},
        "time_windows": {
            "24h": _window_summary(),
            "7d": _window_summary(),
        },
    }


def _window_summary() -> dict:
    return {
        "total_events": 0,
        "last_event_at": None,
        "providers": {},
        "models": {},
        "tasks": {},
        "outcomes": {},
        "fallback_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "success_rate": 0.0,
        "failure_rate": 0.0,
    }


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _build_window_summary(events: list[dict], *, now: datetime, delta: timedelta) -> dict:
    cutoff = now - delta
    filtered = [
        event for event in events
        if (timestamp := _parse_timestamp(str(event.get("timestamp") or ""))) is not None
        and timestamp >= cutoff
    ]

    if not filtered:
        return _window_summary()

    provider_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    fallback_count = 0
    success_count = 0
    failure_count = 0
    last_event_at = None

    for payload in filtered:
        provider_counts[str(payload.get("provider") or "unknown")] += 1
        model_counts[str(payload.get("model") or "unknown")] += 1
        task_counts[str(payload.get("task_type") or "unknown")] += 1
        outcome = str(payload.get("outcome") or "unknown")
        outcome_counts[outcome] += 1
        if payload.get("fallback_used"):
            fallback_count += 1
        if outcome == "success":
            success_count += 1
        elif outcome == "failure":
            failure_count += 1
        last_event_at = payload.get("timestamp") or last_event_at

    total_events = len(filtered)
    return {
        "total_events": total_events,
        "last_event_at": last_event_at,
        "providers": dict(provider_counts),
        "models": dict(model_counts),
        "tasks": dict(task_counts),
        "outcomes": dict(outcome_counts),
        "fallback_count": fallback_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / total_events, 3) if total_events else 0.0,
        "failure_rate": round(failure_count / total_events, 3) if total_events else 0.0,
    }


def record_route_event(
    *,
    route: ModelRoute,
    mode: str,
    outcome: str = "success",
    fallback_used: bool = False,
    error_type: str | None = None,
) -> None:
    event = {
        "timestamp": _utc_now_iso(),
        "task_type": route.task_type,
        "tier": route.tier,
        "provider": route.provider,
        "model": route.model,
        "source": route.source,
        "mode": mode,
        "outcome": outcome,
        "fallback_used": fallback_used,
    }
    if error_type:
        event["error_type"] = error_type

    try:
        with TELEMETRY_EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        return

    try:
        _refresh_summary()
    except Exception:
        return


def _refresh_summary() -> None:
    if not TELEMETRY_EVENTS_PATH.exists():
        return

    provider_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    recent_provider_counts: Counter[str] = Counter()
    recent_model_counts: Counter[str] = Counter()
    recent_task_counts: Counter[str] = Counter()
    recent_events: deque[dict] = deque(maxlen=20)
    last_event_at = None
    total_events = 0
    fallback_count = 0
    success_count = 0
    failure_count = 0
    all_events: list[dict] = []

    with TELEMETRY_EVENTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            total_events += 1
            all_events.append(payload)
            provider_counts[str(payload.get("provider") or "unknown")] += 1
            tier_counts[str(payload.get("tier") or "unknown")] += 1
            task_counts[str(payload.get("task_type") or "unknown")] += 1
            mode_counts[str(payload.get("mode") or "unknown")] += 1
            model_counts[str(payload.get("model") or "unknown")] += 1
            outcome = str(payload.get("outcome") or "unknown")
            outcome_counts[outcome] += 1
            if payload.get("fallback_used"):
                fallback_count += 1
            if outcome == "success":
                success_count += 1
            elif outcome == "failure":
                failure_count += 1
            last_event_at = payload.get("timestamp") or last_event_at
            recent_events.append(payload)

    for payload in recent_events:
        recent_provider_counts[str(payload.get("provider") or "unknown")] += 1
        recent_model_counts[str(payload.get("model") or "unknown")] += 1
        recent_task_counts[str(payload.get("task_type") or "unknown")] += 1

    success_rate = round(success_count / total_events, 3) if total_events else 0.0
    failure_rate = round(failure_count / total_events, 3) if total_events else 0.0

    summary = {
        "total_events": total_events,
        "last_event_at": last_event_at,
        "providers": dict(provider_counts),
        "tiers": dict(tier_counts),
        "tasks": dict(task_counts),
        "modes": dict(mode_counts),
        "models": dict(model_counts),
        "outcomes": dict(outcome_counts),
        "fallback_count": fallback_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "recent_window_size": len(recent_events),
        "recent_providers": dict(recent_provider_counts),
        "recent_models": dict(recent_model_counts),
        "recent_tasks": dict(recent_task_counts),
        "time_windows": {
            "24h": _build_window_summary(all_events, now=datetime.now(timezone.utc), delta=timedelta(hours=24)),
            "7d": _build_window_summary(all_events, now=datetime.now(timezone.utc), delta=timedelta(days=7)),
        },
    }

    TELEMETRY_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_route_summary() -> dict:
    if not TELEMETRY_SUMMARY_PATH.exists():
        return _default_summary()

    try:
        payload = json.loads(TELEMETRY_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _default_summary()

    if not isinstance(payload, dict):
        return _default_summary()

    summary = _default_summary()
    summary.update(payload)
    return summary
