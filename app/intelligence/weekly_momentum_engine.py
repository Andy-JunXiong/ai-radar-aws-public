from typing import Any


def _sum_topic_counts(snapshot: dict[str, Any], topic: str) -> int:
    topic_counts = snapshot.get("topic_counts", {})
    if not isinstance(topic_counts, dict):
        return 0

    value = topic_counts.get(topic, 0)
    try:
        return int(value)
    except Exception:
        return 0


def compute_weekly_momentum(weekly_topic_summary: dict[str, Any]) -> dict[str, Any]:
    """
    Compute simple weekly momentum from daily snapshots.

    Logic:
    - Compare recent half vs earlier half of the 7-day window
    - momentum_delta = recent_sum - earlier_sum
    - classify as rising / cooling / stable
    """

    daily_snapshots = weekly_topic_summary.get("daily_snapshots", [])
    if not isinstance(daily_snapshots, list) or not daily_snapshots:
        return {
            "topic_momentum": {},
            "rising_this_week": [],
            "cooling_this_week": [],
            "stable_this_week": [],
        }

    all_topics = set()
    for snapshot in daily_snapshots:
        topic_counts = snapshot.get("topic_counts", {})
        if isinstance(topic_counts, dict):
            all_topics.update(topic_counts.keys())

    # current implementation assumes snapshots are ordered:
    # [today, yesterday, ..., 6 days ago]
    recent_window = daily_snapshots[:3]
    earlier_window = daily_snapshots[3:7]

    topic_momentum = {}

    for topic in all_topics:
        recent_sum = sum(_sum_topic_counts(s, topic) for s in recent_window)
        earlier_sum = sum(_sum_topic_counts(s, topic) for s in earlier_window)

        delta = recent_sum - earlier_sum

        if delta >= 2:
            status = "rising"
        elif delta <= -2:
            status = "cooling"
        else:
            status = "stable"

        topic_momentum[topic] = {
            "recent_3d_count": recent_sum,
            "earlier_4d_count": earlier_sum,
            "momentum_delta": delta,
            "status": status,
        }

    ranked = sorted(
        [
            {
                "topic": topic,
                "recent_3d_count": values["recent_3d_count"],
                "earlier_4d_count": values["earlier_4d_count"],
                "momentum_delta": values["momentum_delta"],
                "status": values["status"],
            }
            for topic, values in topic_momentum.items()
        ],
        key=lambda x: abs(x["momentum_delta"]),
        reverse=True,
    )

    rising_this_week = [x for x in ranked if x["status"] == "rising"][:5]
    cooling_this_week = [x for x in ranked if x["status"] == "cooling"][:5]
    stable_this_week = [x for x in ranked if x["status"] == "stable"][:5]

    return {
        "topic_momentum": topic_momentum,
        "rising_this_week": rising_this_week,
        "cooling_this_week": cooling_this_week,
        "stable_this_week": stable_this_week,
    }