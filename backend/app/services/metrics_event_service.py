from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRICS_DIR = Path(__file__).resolve().parents[3] / "data" / "output" / "metrics"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _event_date(event: dict[str, Any]) -> str:
    raw = str(
        event.get("date")
        or event.get("started_at")
        or event.get("created_at")
        or utc_now_iso()
    )
    return raw[:10]


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def append_jsonl_event(
    category: str,
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    root = metrics_dir or METRICS_DIR
    date = _event_date(event)
    event_dir = root / category
    event_dir.mkdir(parents=True, exist_ok=True)
    event_path = event_dir / f"{date}.jsonl"
    normalized = {
        "created_at": utc_now_iso(),
        **event,
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, default=_json_default))
        handle.write("\n")
    return event_path


def append_pipeline_run(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    root = metrics_dir or METRICS_DIR
    date = _event_date(event)
    event_dir = root / "pipeline_runs"
    event_dir.mkdir(parents=True, exist_ok=True)
    event_path = event_dir / f"{date}.json"

    existing: list[dict[str, Any]] = []
    if event_path.exists():
        try:
            payload = json.loads(event_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                existing = [item for item in payload if isinstance(item, dict)]
            elif isinstance(payload, dict):
                existing = [payload]
        except json.JSONDecodeError:
            existing = []

    normalized = {
        "created_at": utc_now_iso(),
        **event,
    }
    existing.append(normalized)
    event_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return event_path


def record_collector_run(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    return append_jsonl_event("collector_runs", event, metrics_dir=metrics_dir)


def record_artifact_write(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    return append_jsonl_event("artifact_writes", event, metrics_dir=metrics_dir)


def record_llm_call(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    return append_jsonl_event("llm_calls", event, metrics_dir=metrics_dir)


def record_verification_event(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    return append_jsonl_event("verification_events", event, metrics_dir=metrics_dir)


def record_signal_timeline_load(
    event: dict[str, Any],
    *,
    metrics_dir: Path | None = None,
) -> Path:
    return append_jsonl_event("signal_timeline_loads", event, metrics_dir=metrics_dir)
