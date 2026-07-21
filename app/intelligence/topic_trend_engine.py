from collections import Counter
from typing import Any


def compute_topic_trends(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate topic frequency and importance distribution.
    """

    if not signals:
        return {
            "topic_counts": {},
            "top_topics": [],
            "high_importance_topics": {},
        }

    topic_counter = Counter()
    high_importance_counter = Counter()

    for signal in signals:
        topic = signal.get("topic", "General AI")
        importance_level = signal.get("importance_level", "low")

        topic_counter[topic] += 1

        if importance_level == "high":
            high_importance_counter[topic] += 1

    top_topics = sorted(
        topic_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "topic_counts": dict(topic_counter),
        "top_topics": top_topics[:5],
        "high_importance_topics": dict(high_importance_counter),
    }