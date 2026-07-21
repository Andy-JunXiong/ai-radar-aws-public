from typing import Any


def compute_topic_evolution(
    current_topic_trends: dict[str, Any],
    previous_topic_trends: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare current topic counts with previous topic counts.

    Output example:
    {
        "AI Agents": {
            "previous_count": 2,
            "current_count": 5,
            "delta": 3,
            "status": "rising"
        }
    }
    """

    current_counts = current_topic_trends.get("topic_counts", {})
    previous_counts = previous_topic_trends.get("topic_counts", {})

    all_topics = set(current_counts.keys()) | set(previous_counts.keys())

    evolution = {}

    for topic in all_topics:
        previous_count = previous_counts.get(topic, 0)
        current_count = current_counts.get(topic, 0)
        delta = current_count - previous_count

        if delta >= 2:
            status = "rising"
        elif delta <= -2:
            status = "falling"
        else:
            status = "stable"

        evolution[topic] = {
            "previous_count": previous_count,
            "current_count": current_count,
            "delta": delta,
            "status": status,
        }

    ranked_evolution = sorted(
        [
            {
                "topic": topic,
                "previous_count": values["previous_count"],
                "current_count": values["current_count"],
                "delta": values["delta"],
                "status": values["status"],
            }
            for topic, values in evolution.items()
        ],
        key=lambda x: abs(x["delta"]),
        reverse=True,
    )

    return {
        "topic_evolution": evolution,
        "ranked_topic_evolution": ranked_evolution,
    }