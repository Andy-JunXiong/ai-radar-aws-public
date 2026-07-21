import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_manual_sessions(manual_session_file: Path) -> list[dict[str, Any]]:
    if not manual_session_file.exists():
        return []

    try:
        with open(manual_session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        sessions = data.get("sessions", [])
        if isinstance(sessions, list):
            return sessions

    return []


def promote_manual_sessions_to_signals(
    manual_sessions: list[dict[str, Any]],
    today: str,
) -> list[dict[str, Any]]:
    """
    Convert manual research sessions into radar-style signals.

    Accepted example fields in one manual session:
    - title
    - summary
    - insight
    - source
    - tags
    - content
    """

    promoted = []

    for idx, session in enumerate(manual_sessions, start=1):
        title = (
            session.get("title")
            or session.get("topic")
            or f"Manual Research Signal {idx}"
        )

        summary = (
            session.get("summary")
            or session.get("insight")
            or session.get("content")
            or ""
        )

        if not summary:
            continue

        promoted.append(
            {
                "title": title,
                "summary": summary,
                "url": session.get("url", ""),
                "author": session.get("author", "Manual Workspace"),
                "source": "manual_workspace",
                "category": session.get("category", "Manual Research"),
                "published_at": session.get("published_at", datetime.now().isoformat()),
                "collected_at": datetime.now().isoformat(),
                "source_weight": 0.95,
                "quality_level": "high",
                "promotion_type": "manual_signal",
                "promotion_date": today,
                "tags": session.get("tags", []),
            }
        )

    return promoted


def load_and_promote_manual_signals(
    manual_session_file: Path,
    today: str,
) -> list[dict[str, Any]]:
    manual_sessions = load_manual_sessions(manual_session_file)
    return promote_manual_sessions_to_signals(manual_sessions, today)