def compute_final_signal_score(item: dict, source_stats: dict) -> float:

    source_quality = source_stats.get(
        item.get("source", "unknown"), {}
    ).get("quality_score", 0)

    source_weight = item.get("source_weight", 0.5)

    recency_score = item.get("recency_score", 0.5)

    keyword_relevance = item.get("keyword_relevance", 0.0)

    novelty_score = item.get("novelty_score", 0.0)

    score = (
        source_quality * 0.3
        + source_weight * 0.2
        + recency_score * 0.2
        + keyword_relevance * 0.15
        + novelty_score * 0.15
    )

    return round(score, 4)