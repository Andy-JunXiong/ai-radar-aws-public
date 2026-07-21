from collections import Counter

TREND_KEYWORDS = [
    "agent",
    "agents",
    "ai system",
    "ai systems",
    "memory",
    "retrieval",
    "architecture",
    "framework",
    "model",
    "reasoning",
]


def detect_trends(signals):

    counter = Counter()

    for s in signals:

        text = (
            s.get("title", "").lower()
            + " "
            + s.get("summary", "").lower()
        )

        for kw in TREND_KEYWORDS:
            if kw in text:
                counter[kw] += 1

    return dict(counter.most_common(5))