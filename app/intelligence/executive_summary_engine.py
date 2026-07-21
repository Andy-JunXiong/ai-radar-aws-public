from typing import Any


def generate_daily_executive_summary(
    signals_data: list[dict[str, Any]],
    topic_trends: dict[str, Any],
    rising_topics: dict[str, Any],
    weekly_momentum: dict[str, Any],
    strategic_priority: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate a human-readable executive summary payload for daily_radar.
    """

    high_importance_count = sum(
        1 for s in signals_data if s.get("importance_level") == "high"
    )
    medium_importance_count = sum(
        1 for s in signals_data if s.get("importance_level") == "medium"
    )

    top_topics_today = topic_trends.get("top_topics", [])[:5]
    rising_topics_today = rising_topics.get("rising_topics", [])[:5]
    priority_topics = strategic_priority.get("strategic_priority_topics", [])[:5]

    weekly_rising = weekly_momentum.get("rising_this_week", [])[:5]
    weekly_cooling = weekly_momentum.get("cooling_this_week", [])[:5]

    top_priority_topic = priority_topics[0]["topic"] if priority_topics else None
    top_rising_topic = rising_topics_today[0]["topic"] if rising_topics_today else None

    what_matters_parts = []

    if top_priority_topic:
        what_matters_parts.append(
            f"Top strategic topic today is {top_priority_topic}."
        )

    if top_rising_topic and top_rising_topic != top_priority_topic:
        what_matters_parts.append(
            f"Fastest-rising topic in the current batch is {top_rising_topic}."
        )

    if high_importance_count > 0:
        what_matters_parts.append(
            f"There are {high_importance_count} high-importance signals that may deserve immediate attention."
        )

    if weekly_rising:
        rising_names = ", ".join(item["topic"] for item in weekly_rising[:3])
        what_matters_parts.append(
            f"Topics showing weekly momentum include {rising_names}."
        )

    if not what_matters_parts:
        what_matters_parts.append(
            "Signal activity looks relatively balanced today, with no single topic strongly dominating."
        )

    return {
        "top_signal_count": len(signals_data[:5]),
        "high_importance_signal_count": high_importance_count,
        "medium_importance_signal_count": medium_importance_count,
        "top_topics_today": top_topics_today,
        "rising_topics_today": rising_topics_today,
        "strategic_priority_topics": priority_topics,
        "weekly_rising_topics": weekly_rising,
        "weekly_cooling_topics": weekly_cooling,
        "what_matters_today": " ".join(what_matters_parts),
    }