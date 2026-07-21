from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METRICS_PATH = Path(__file__).resolve().parents[2] / "data" / "output" / "execution_policy_usage_summary.json"


def _default_payload() -> dict[str, Any]:
    return {
        "total_events": 0,
        "by_mode": {"fast": 0, "guarded": 0, "critical": 0},
        "escalations": 0,
        "validation_failures": 0,
        "last_event": None,
        "recent": [],
    }


def _load_metrics() -> dict[str, Any]:
    if not METRICS_PATH.exists():
        return _default_payload()
    try:
        payload = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {**_default_payload(), **payload}
    except Exception:
        pass
    return _default_payload()


def record_policy_event(event: dict[str, Any]) -> None:
    payload = _load_metrics()
    mode = str(event.get("mode") or "").strip().lower()

    payload["total_events"] = int(payload.get("total_events") or 0) + 1
    if mode in payload["by_mode"]:
        payload["by_mode"][mode] = int(payload["by_mode"].get(mode) or 0) + 1
    if event.get("escalation_used"):
        payload["escalations"] = int(payload.get("escalations") or 0) + 1
    if event.get("validation_failed"):
        payload["validation_failures"] = int(payload.get("validation_failures") or 0) + 1

    payload["last_event"] = event
    recent = list(payload.get("recent") or [])
    recent.append(event)
    payload["recent"] = recent[-20:]

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
