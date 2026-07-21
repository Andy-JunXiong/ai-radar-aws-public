from typing import Any


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def compute_agent_relevance_score(signal: dict[str, Any]) -> float:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
    tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
    keywords = metadata.get("matched_keywords") if isinstance(metadata.get("matched_keywords"), list) else []
    summary = str(signal.get("summary") or "").lower()
    title = str(signal.get("title") or "").lower()

    score = 0.2

    strong_terms = [
        "agent framework",
        "multi agent",
        "multi-agent",
        "autonomous agent",
        "agentic",
        "ai agent",
    ]

    if any(term in title or term in summary for term in strong_terms):
        score += 0.35

    if len(tags) >= 2:
        score += 0.15
    elif len(tags) == 1:
        score += 0.08

    if len(keywords) >= 2:
        score += 0.2
    elif len(keywords) == 1:
        score += 0.12

    if "framework" in summary or "framework" in title:
        score += 0.1

    return round(min(score, 1.0), 2)


def compute_buildability_score(signal: dict[str, Any]) -> float:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
    language = str(metadata.get("language") or "").strip().lower()
    stars = _safe_int(metadata.get("repo_stars"))
    summary = str(signal.get("summary") or "").lower()
    title = str(signal.get("title") or "").lower()

    score = 0.25

    if language:
        score += 0.15

    if any(term in title or term in summary for term in ["framework", "sdk", "toolkit", "runtime", "orchestration"]):
        score += 0.2

    if stars >= 1000:
        score += 0.25
    elif stars >= 200:
        score += 0.18
    elif stars >= 50:
        score += 0.1

    return round(min(score, 1.0), 2)


def compute_strategic_relevance_score(signal: dict[str, Any]) -> float:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
    stars = _safe_int(metadata.get("repo_stars"))
    summary = str(signal.get("summary") or "").lower()
    title = str(signal.get("title") or "").lower()

    score = 0.2

    strategic_terms = [
        "framework",
        "platform",
        "infrastructure",
        "orchestration",
        "developer tool",
        "workflow",
        "agentic",
    ]

    if any(term in title or term in summary for term in strategic_terms):
        score += 0.25

    if stars >= 1000:
        score += 0.35
    elif stars >= 200:
        score += 0.22
    elif stars >= 50:
        score += 0.12

    if "open source" in summary or "open-source" in summary:
        score += 0.08

    return round(min(score, 1.0), 2)


def compute_agent_watch_score(signal: dict[str, Any]) -> float:
    agent_relevance = compute_agent_relevance_score(signal)
    buildability = compute_buildability_score(signal)
    strategic_relevance = compute_strategic_relevance_score(signal)

    score = (
        agent_relevance * 0.4
        + buildability * 0.25
        + strategic_relevance * 0.35
    )
    return round(min(score, 1.0), 4)


def attach_agent_scores(signal: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(signal)
    enriched["agent_relevance_score"] = compute_agent_relevance_score(signal)
    enriched["buildability_score"] = compute_buildability_score(signal)
    enriched["strategic_relevance_score"] = compute_strategic_relevance_score(signal)
    enriched["agent_watch_score"] = compute_agent_watch_score(signal)
    return enriched


def attach_agent_scores_to_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not signals:
        return []
    return [attach_agent_scores(signal) for signal in signals]
