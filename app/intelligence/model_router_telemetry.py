import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.intelligence.model_router import ModelRoute


TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "output"
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

TELEMETRY_EVENTS_PATH = TELEMETRY_DIR / "model_router_usage.jsonl"
TELEMETRY_SUMMARY_PATH = TELEMETRY_DIR / "model_router_usage_summary.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_route_event(*, route: ModelRoute, mode: str) -> None:
    event = {
        "timestamp": _utc_now_iso(),
        "task_type": route.task_type,
        "tier": route.tier,
        "provider": route.provider,
        "model": route.model,
        "source": route.source,
        "mode": mode,
    }

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
    last_event_at = None
    total_events = 0

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
            provider_counts[str(payload.get("provider") or "unknown")] += 1
            tier_counts[str(payload.get("tier") or "unknown")] += 1
            task_counts[str(payload.get("task_type") or "unknown")] += 1
            mode_counts[str(payload.get("mode") or "unknown")] += 1
            model_counts[str(payload.get("model") or "unknown")] += 1
            last_event_at = payload.get("timestamp") or last_event_at

    summary = {
        "total_events": total_events,
        "last_event_at": last_event_at,
        "providers": dict(provider_counts),
        "tiers": dict(tier_counts),
        "tasks": dict(task_counts),
        "modes": dict(mode_counts),
        "models": dict(model_counts),
    }

    TELEMETRY_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
