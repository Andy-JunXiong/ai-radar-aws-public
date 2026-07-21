KEYWORDS = [
    "agent",
    "ai system",
    "ai systems",
    "memory",
    "trajectory",
    "reasoning",
    "decision",
    "governance",
    "workflow",
    "retrieval",
    "evaluation",
    "multi agent",
    "ai infrastructure"
]


def compute_keyword_relevance(signal: dict) -> float:
    """
    Compute keyword relevance score for a signal.
    """

    text = (
        signal.get("title", "") + " " +
        signal.get("summary", "") + " " +
        signal.get("content", "")
    ).lower()

    matches = 0

    for kw in KEYWORDS:
        if kw in text:
            matches += 1

    if matches == 0:
        return 0.0

    score = min(matches / 5, 1.0)

    return round(score, 2)