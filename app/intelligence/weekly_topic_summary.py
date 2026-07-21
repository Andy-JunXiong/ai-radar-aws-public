import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def build_daily_history_file(output_dir: Path, date_str: str) -> Path:
    return output_dir / "history" / "daily" / date_str / "daily_radar.json"


def load_topic_counts_for_date(output_dir: Path, date_str: str) -> dict[str, int]:
    file_path = build_daily_history_file(output_dir, date_str)

    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    topic_trends = data.get("topic_trends", {})
    if not isinstance(topic_trends, dict):
        return {}

    topic_counts = topic_trends.get("topic_counts", {})
    if not isinstance(topic_counts, dict):
        return {}

    cleaned: dict[str, int] = {}
    for k, v in topic_counts.items():
        try:
            cleaned[k] = int(v)
        except Exception:
            continue

    return cleaned


def compute_weekly_topic_summary(output_dir: Path, current_date: str, days: int = 7) -> dict[str, Any]:
    """
    Aggregate topic counts across the last N days including current_date.

    Output:
    - weekly_topic_counts
    - top_weekly_topics
    - daily_snapshots
    """
    try:
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    except Exception:
        return {
            "weekly_topic_counts": {},
            "top_weekly_topics": [],
            "daily_snapshots": [],
        }

    total_counter = Counter()
    daily_snapshots: list[dict[str, Any]] = []

    for i in range(days):
        dt = current_dt - timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        topic_counts = load_topic_counts_for_date(output_dir, date_str)

        if topic_counts:
            total_counter.update(topic_counts)

        daily_snapshots.append(
            {
                "date": date_str,
                "topic_counts": topic_counts,
            }
        )

    top_weekly_topics = sorted(
        total_counter.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return {
        "weekly_topic_counts": dict(total_counter),
        "top_weekly_topics": top_weekly_topics[:10],
        "daily_snapshots": daily_snapshots,
    }