from collections import defaultdict
from datetime import datetime, timedelta, timezone


def compute_topic_momentum(signals: list[dict]):
    """
    Compute topic momentum statistics.

    Output:
    {
        "AI_Agents": {
            "7d": 4,
            "30d": 10,
            "momentum": "Rising"
        }
    }
    """

    topic_counts_7d = defaultdict(int)
    topic_counts_30d = defaultdict(int)

    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    for s in signals:
        topic = (s.get("topic") or "").strip().replace(" ", "_")
        if not topic:
            continue

        dt_raw = s.get("collected_at") or s.get("published_at")
        if not dt_raw:
            continue

        try:
            dt = datetime.fromisoformat(dt_raw)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

        except Exception as e:
            print(f"Skip bad datetime '{dt_raw}': {e}")
            continue

        if dt >= d30:
            topic_counts_30d[topic] += 1

        if dt >= d7:
            topic_counts_7d[topic] += 1

    topic_momentum = {}
    topics = set(topic_counts_30d.keys()) | set(topic_counts_7d.keys())

    for t in topics:
        c7 = topic_counts_7d.get(t, 0)
        c30 = topic_counts_30d.get(t, 0)

        if c7 >= 3:
            label = "Rising"
        elif c7 == 0 and c30 > 0:
            label = "Cooling"
        else:
            label = "Stable"

        topic_momentum[t] = {
            "7d": c7,
            "30d": c30,
            "momentum": label,
        }

    return topic_momentum