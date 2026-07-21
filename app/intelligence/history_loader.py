import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def build_daily_history_file(output_dir: Path, date_str: str) -> Path:
    """
    Build dated daily radar history path.

    Example:
    data/output/history/daily/2026-03-26/daily_radar.json
    """
    return output_dir / "history" / "daily" / date_str / "daily_radar.json"


def save_dated_daily_radar(output_dir: Path, date_str: str, daily_radar: dict[str, Any]) -> Path:
    """
    Save current daily_radar into dated history path.
    """
    history_file = build_daily_history_file(output_dir, date_str)
    history_file.parent.mkdir(parents=True, exist_ok=True)

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(daily_radar, f, ensure_ascii=False, indent=2)

    return history_file


def load_previous_topic_trends(output_dir: Path, current_date: str) -> dict[str, Any]:
    """
    Load previous day's topic_trends from dated history file.

    Fallback:
    {"topic_counts": {}}
    """
    try:
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    except Exception:
        return {"topic_counts": {}}

    previous_dt = current_dt - timedelta(days=1)
    previous_date = previous_dt.strftime("%Y-%m-%d")

    previous_file = build_daily_history_file(output_dir, previous_date)

    if not previous_file.exists():
        return {"topic_counts": {}}

    try:
        with open(previous_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"topic_counts": {}}

    topic_trends = data.get("topic_trends", {})
    if not isinstance(topic_trends, dict):
        return {"topic_counts": {}}

    topic_counts = topic_trends.get("topic_counts", {})
    if not isinstance(topic_counts, dict):
        return {"topic_counts": {}}

    return {
        "topic_counts": topic_counts
    }