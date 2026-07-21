from collections import Counter
from typing import Any


def compute_rising_topics(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute a simple rising-topic score from the current signal batch.

    Logic:
    - topic_count measures how often a topic appears
    - high_importance_count measures concentration of important signals
    - rising_score = topic_count + high_importance_count * 2

    This is a within-batch momentum proxy, not a true historical delta yet.
    """

    if not signals:
        return {
            "topic_scores": {},
            "rising_topics": [],
        }

    topic_counter = Counter()
    high_importance_counter = Counter()

    for signal in signals:
        topic = signal.get("topic", "General AI")
        importance_level = signal.get("importance_level", "low")

        topic_counter[topic] += 1

        if importance_level == "high":
            high_importance_counter[topic] += 1

    topic_scores = {}

    for topic, count in topic_counter.items():
        high_count = high_importance_counter.get(topic, 0)
        rising_score = count + high_count * 2

        topic_scores[topic] = {
            "topic_count": count,
            "high_importance_count": high_count,
            "rising_score": rising_score,
        }

    rising_topics = sorted(
        [
            {
                "topic": topic,
                "topic_count": values["topic_count"],
                "high_importance_count": values["high_importance_count"],
                "rising_score": values["rising_score"],
            }
            for topic, values in topic_scores.items()
        ],
        key=lambda x: x["rising_score"],
        reverse=True,
    )

    return {
        "topic_scores": topic_scores,
        "rising_topics": rising_topics[:5],
    }