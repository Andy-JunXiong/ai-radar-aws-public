from typing import Any


STRATEGIC_TOPICS = {
    "AI Agents",
    "AI Infrastructure",
    "AI Models",
    "AI Research",
}


def compute_importance_level(signal: dict[str, Any]) -> tuple[str, list[str]]:
    """
    Compute a human-readable importance level for one signal.

    Inputs expected in signal:
    - score
    - topic
    - quality_level
    - source_weight
    - keyword_relevance
    - novelty_score
    """

    score = float(signal.get("score", 0.0) or 0.0)
    topic = signal.get("topic", "General AI")
    quality_level = signal.get("quality_level", "unknown")
    source_weight = float(signal.get("source_weight", 0.0) or 0.0)
    keyword_relevance = float(signal.get("keyword_relevance", 0.0) or 0.0)
    novelty_score = float(signal.get("novelty_score", 0.0) or 0.0)

    reasons: list[str] = []

    if score >= 0.75:
        reasons.append("high_final_score")
    elif score >= 0.55:
        reasons.append("moderate_final_score")

    if topic in STRATEGIC_TOPICS:
        reasons.append("strategic_topic")

    if quality_level == "high":
        reasons.append("strong_source_quality")

    if source_weight >= 0.8:
        reasons.append("high_source_weight")

    if keyword_relevance >= 0.6:
        reasons.append("high_keyword_relevance")

    if novelty_score >= 0.6:
        reasons.append("high_novelty")

    # importance level logic
    if score >= 0.75 and (
        topic in STRATEGIC_TOPICS or quality_level == "high"
    ):
        level = "high"
    elif score >= 0.55:
        level = "medium"
    else:
        level = "low"

    return level, reasons


def attach_importance_to_signal(signal: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(signal)
    level, reasons = compute_importance_level(enriched)
    enriched["importance_level"] = level
    enriched["importance_reason"] = reasons
    return enriched


def attach_importance_to_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not signals:
        return []

    return [attach_importance_to_signal(signal) for signal in signals]