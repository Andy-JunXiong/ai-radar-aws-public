import re

NOVELTY_KEYWORDS = [
    "introduce",
    "introducing",
    "new",
    "launch",
    "release",
    "first",
    "novel",
    "breakthrough",
    "research",
    "paper",
    "framework",
    "architecture",
]


def compute_novelty_score(signal: dict) -> float:
    text = (
        signal.get("title", "")
        + " "
        + signal.get("summary", "")
        + " "
        + signal.get("content", "")
    ).lower()

    score = 0

    for kw in NOVELTY_KEYWORDS:
        if re.search(rf"\b{kw}\b", text):
            score += 1

    score = min(score / 5, 1.0)

    return round(score, 2)