from typing import Any


STRATEGIC_TOPICS = {
    "AI Agents",
    "AI Infrastructure",
    "AI Models",
    "AI Research",
}


def _normalize_topic_trend_count(topic_trends: dict[str, Any], topic: str) -> int:
    topic_counts = topic_trends.get("topic_counts", {})
    if not isinstance(topic_counts, dict):
        return 0
    value = topic_counts.get(topic, 0)
    try:
        return int(value)
    except Exception:
        return 0


def _normalize_high_importance_topic_count(topic_trends: dict[str, Any], topic: str) -> int:
    high_importance_topics = topic_trends.get("high_importance_topics", {})
    if not isinstance(high_importance_topics, dict):
        return 0
    value = high_importance_topics.get(topic, 0)
    try:
        return int(value)
    except Exception:
        return 0


def _normalize_weekly_momentum_delta(weekly_momentum: dict[str, Any], topic: str) -> int:
    topic_momentum = weekly_momentum.get("topic_momentum", {})
    if not isinstance(topic_momentum, dict):
        return 0

    topic_data = topic_momentum.get(topic, {})
    if not isinstance(topic_data, dict):
        return 0

    value = topic_data.get("momentum_delta", 0)
    try:
        return int(value)
    except Exception:
        return 0


def _normalize_rising_score(rising_topics: dict[str, Any], topic: str) -> int:
    topic_scores = rising_topics.get("topic_scores", {})
    if not isinstance(topic_scores, dict):
        return 0

    topic_data = topic_scores.get(topic, {})
    if not isinstance(topic_data, dict):
        return 0

    value = topic_data.get("rising_score", 0)
    try:
        return int(value)
    except Exception:
        return 0


def compute_strategic_priority_topics(
    topic_trends: dict[str, Any],
    rising_topics: dict[str, Any],
    weekly_momentum: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a strategic priority layer by combining:
    - current topic frequency
    - high-importance concentration
    - rising score
    - weekly momentum
    - strategic topic bonus
    """

    topic_counts = topic_trends.get("topic_counts", {})
    if not isinstance(topic_counts, dict):
        return {
            "strategic_priority_topics": [],
            "priority_topic_map": {},
        }

    results = []

    for topic in topic_counts.keys():
        topic_count = _normalize_topic_trend_count(topic_trends, topic)
        high_importance_count = _normalize_high_importance_topic_count(topic_trends, topic)
        rising_score = _normalize_rising_score(rising_topics, topic)
        weekly_momentum_delta = _normalize_weekly_momentum_delta(weekly_momentum, topic)

        strategic_bonus = 2 if topic in STRATEGIC_TOPICS else 0

        priority_score = (
            topic_count * 1.0
            + high_importance_count * 2.0
            + rising_score * 0.8
            + weekly_momentum_delta * 1.2
            + strategic_bonus
        )

        reasons = []

        if topic in STRATEGIC_TOPICS:
            reasons.append("strategic_topic")

        if high_importance_count >= 2:
            reasons.append("high_importance_concentration")
        elif high_importance_count >= 1:
            reasons.append("some_high_importance_signals")

        if rising_score >= 5:
            reasons.append("strong_rising_score")
        elif rising_score >= 3:
            reasons.append("moderate_rising_score")

        if weekly_momentum_delta >= 2:
            reasons.append("positive_weekly_momentum")
        elif weekly_momentum_delta <= -2:
            reasons.append("negative_weekly_momentum")

        if topic_count >= 4:
            reasons.append("high_topic_frequency")

        results.append(
            {
                "topic": topic,
                "topic_count": topic_count,
                "high_importance_count": high_importance_count,
                "rising_score": rising_score,
                "weekly_momentum_delta": weekly_momentum_delta,
                "priority_score": round(priority_score, 2),
                "reason": reasons,
            }
        )

    results = sorted(results, key=lambda x: x["priority_score"], reverse=True)

    priority_map = {item["topic"]: item for item in results}

    return {
        "strategic_priority_topics": results[:10],
        "priority_topic_map": priority_map,
    }