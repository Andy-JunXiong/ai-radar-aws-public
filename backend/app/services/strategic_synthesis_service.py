from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "may",
    "more",
    "not",
    "of",
    "on",
    "or",
    "state",
    "states",
    "that",
    "the",
    "this",
    "to",
    "with",
    "without",
    "yet",
    "ai",
    "agent",
    "agents",
    "build",
    "building",
    "candidate",
    "context",
    "current",
    "data",
    "analysis",
    "development",
    "everyone",
    "generation",
    "github",
    "high",
    "hn",
    "intelligence",
    "latest",
    "launch",
    "multi",
    "open",
    "pain",
    "platform",
    "product",
    "project",
    "projects",
    "review",
    "signal",
    "signals",
    "source",
    "sources",
    "system",
    "systems",
    "team",
    "teams",
    "tool",
    "tools",
    "traction",
    "user",
    "users",
    "visible",
    "yc",
}

_TOPIC_ALIASES = {
    "auth": "security",
    "code": "developer tooling",
    "coding": "developer tooling",
    "cost": "cost control",
    "developer": "developer tooling",
    "devtools": "developer tooling",
    "eval": "evaluation",
    "evals": "evaluation",
    "evaluations": "evaluation",
    "framework": "infrastructure",
    "frameworks": "infrastructure",
    "memory": "memory",
    "observability": "monitoring",
    "orchestration": "infrastructure",
    "pricing": "cost control",
    "rag": "retrieval",
    "reliability": "evaluation",
    "retrieval": "retrieval",
    "runtime": "infrastructure",
    "security": "security",
    "tooling": "developer tooling",
    "workflow": "workflow",
    "workflows": "workflow",
}

_BROAD_PROJECT_MATCH_TOPICS = {
    "infrastructure",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _items_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
        signals = payload.get("signals")
        if isinstance(signals, list):
            return signals
    return []


def _item_entity_id(item: dict[str, Any], *, signal_type: str) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if signal_type == "agent_watch":
        return _safe_text(metadata.get("repo_url") or item.get("url")).lower()
    return _safe_text(item.get("url") or item.get("title")).lower()


def _keyword_tokens(text: str) -> set[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    tokens: set[str] = set()
    for token in normalized.split():
        if len(token) < 3 or token in _STOP_WORDS:
            continue
        tokens.add(_TOPIC_ALIASES.get(token, token))
    return tokens


def _topic_tokens_from_item(item: dict[str, Any]) -> set[str]:
    profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
    fields = [
        item.get("title"),
        item.get("summary"),
        item.get("agent_subtopic"),
        item.get("friction_subtopic"),
        profile.get("project_fit"),
        profile.get("product_opportunity"),
        profile.get("why_it_matters"),
        profile.get("why_this_matters"),
        profile.get("problem_summary"),
    ]
    tokens: set[str] = set()
    for value in fields:
        tokens.update(_keyword_tokens(_safe_text(value)))
    for keyword in _safe_list(item.get("matched_keywords")):
        tokens.update(_keyword_tokens(_safe_text(keyword)))
    return tokens


def _project_tokens(project: dict[str, Any]) -> set[str]:
    fields = [
        project.get("project_id"),
        project.get("name"),
        project.get("description"),
        project.get("current_state"),
        project.get("roadmap"),
    ]
    tokens: set[str] = set()
    for value in fields:
        tokens.update(_keyword_tokens(_safe_text(value)))
    for topic in _safe_list(project.get("topics")):
        tokens.update(_keyword_tokens(_safe_text(topic)))
    metadata = project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    for value in metadata.values():
        if isinstance(value, (str, int, float)):
            tokens.update(_keyword_tokens(_safe_text(value)))
        elif isinstance(value, list):
            for item in value:
                tokens.update(_keyword_tokens(_safe_text(item)))
    return tokens


def _project_available_for_current_review(project: dict[str, Any]) -> bool:
    if project.get("enabled") is False:
        return False
    status = _safe_text(project.get("status")).lower()
    return status in {"", "active"}


def _project_relevance_matches(
    *,
    shared_topics: list[str],
    agent_item: dict[str, Any],
    friction_item: dict[str, Any],
    projects: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    brief_tokens = set(shared_topics)
    brief_tokens.update(agent_item.get("topic_tokens") or [])
    brief_tokens.update(friction_item.get("topic_tokens") or [])
    matches: list[dict[str, Any]] = []

    for project in projects:
        if not isinstance(project, dict) or not _project_available_for_current_review(project):
            continue
        tokens = _project_tokens(project)
        shared_topic_matches = sorted(tokens & set(shared_topics))
        context_matches = sorted(tokens & brief_tokens)
        broad_shared_only = bool(shared_topic_matches) and set(shared_topic_matches).issubset(_BROAD_PROJECT_MATCH_TOPICS)
        if broad_shared_only and len(context_matches) < 3:
            continue
        if not shared_topic_matches and len(context_matches) < 3:
            continue
        score = len(context_matches) + (len(shared_topic_matches) * 2)
        match_type = "shared_topic" if shared_topic_matches else "context_overlap"
        reason_terms = shared_topic_matches[:3] if shared_topic_matches else context_matches[:3]
        matches.append(
            {
                "project_id": _safe_text(project.get("project_id")),
                "project_name": _safe_text(project.get("name") or project.get("project_id")),
                "status": _safe_text(project.get("status")),
                "matched_topics": context_matches[:6],
                "shared_topic_matches": shared_topic_matches[:6],
                "context_matches": context_matches[:6],
                "match_type": match_type,
                "score": score,
                "reason": (
                    f"Shared convergence topic: {', '.join(reason_terms)}."
                    if shared_topic_matches
                    else f"Context overlap has {len(context_matches)} supporting terms: {', '.join(reason_terms)}."
                ),
            }
        )

    return sorted(matches, key=lambda item: _safe_float(item.get("score")), reverse=True)[:limit]


def _brief_readiness(
    *,
    confidence: str,
    shared_topics: list[str],
    project_matches: list[dict[str, Any]],
    agent_item: dict[str, Any],
    friction_item: dict[str, Any],
) -> dict[str, Any]:
    source_count = int(bool(agent_item.get("entity_id") or agent_item.get("url"))) + int(
        bool(friction_item.get("entity_id") or friction_item.get("url"))
    )
    if confidence == "high" and project_matches and source_count >= 2:
        status = "ready_for_project_review"
        label = "Ready for Project Review"
        reason = "Supply and demand overlap is strong enough to review against matched projects."
    elif confidence in {"high", "medium"}:
        status = "watch_first"
        label = "Watch First"
        reason = "The convergence is visible, but it needs clearer project fit or stronger supporting context before action."
    else:
        status = "needs_more_evidence"
        label = "Needs More Evidence"
        reason = "The pairing is still weak and should stay in Knowledge until more support appears."

    return {
        "status": status,
        "label": label,
        "reason": reason,
        "source_count": source_count,
        "shared_topic_count": len(shared_topics),
        "matched_project_count": len(project_matches),
    }


def _brief_quality(
    *,
    shared_topics: list[str],
    strategic_overlap: list[str],
    project_matches: list[dict[str, Any]],
    review_readiness: dict[str, Any],
    agent_item: dict[str, Any],
    friction_item: dict[str, Any],
) -> dict[str, Any]:
    source_count = _safe_int(review_readiness.get("source_count"))
    shared_topic_count = len(shared_topics)
    project_match_count = len(project_matches)
    strategic_overlap_count = len(strategic_overlap)
    agent_score = _safe_float(agent_item.get("score"))
    friction_score = _safe_float(friction_item.get("score"))
    shared_topic_match_count = sum(
        len(_safe_list(match.get("shared_topic_matches")))
        for match in project_matches
        if isinstance(match, dict)
    )
    context_match_count = sum(
        len(_safe_list(match.get("context_matches")))
        for match in project_matches
        if isinstance(match, dict)
    )
    evidence_score = min(34, source_count * 10 + shared_topic_count * 7)
    fit_score = min(38, project_match_count * 12 + shared_topic_match_count * 5 + context_match_count)
    strategy_score = min(12, strategic_overlap_count * 4)
    signal_score = min(20, round(((agent_score + friction_score) / 2) * 20))
    penalty = 0
    if source_count < 2:
        penalty += 14
    if shared_topic_count == 0:
        penalty += 16
    if project_match_count == 0:
        penalty += 12
    if agent_score < 0.35 or friction_score < 0.35:
        penalty += 8
    raw_score = evidence_score + fit_score + strategy_score + signal_score - penalty
    score = int(max(0, min(100, raw_score)))

    if score >= 70:
        label = "Strong review candidate"
        recommendation = "Prioritize this for Project Takeaway review; confirm only after checking the linked supply and demand sources."
    elif score >= 45:
        label = "Review with caution"
        recommendation = "Use Review Inbox or Watch, but keep the evidence limits visible before confirming."
    else:
        label = "Needs stronger evidence"
        recommendation = "Keep this in Knowledge or Watch until support improves."

    reason_parts = [
        f"{source_count} source{'s' if source_count != 1 else ''}",
        f"{shared_topic_count} shared topic{'s' if shared_topic_count != 1 else ''}",
        f"{project_match_count} project match{'es' if project_match_count != 1 else ''}",
    ]
    if strategic_overlap_count:
        reason_parts.append(f"{strategic_overlap_count} strategic overlap{'s' if strategic_overlap_count != 1 else ''}")
    if penalty:
        reason_parts.append(f"{penalty} point evidence penalty")

    return {
        "score": score,
        "label": label,
        "reason": " / ".join(reason_parts),
        "recommendation": recommendation,
        "factors": {
            "source_count": source_count,
            "shared_topic_count": shared_topic_count,
            "project_match_count": project_match_count,
            "shared_topic_project_match_count": shared_topic_match_count,
            "context_project_match_count": context_match_count,
            "strategic_overlap_count": strategic_overlap_count,
            "agent_watch_score": agent_score,
            "friction_score": friction_score,
            "evidence_score": evidence_score,
            "fit_score": fit_score,
            "strategy_score": strategy_score,
            "signal_score": signal_score,
            "penalty": penalty,
        },
    }


def _topic_label(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, (list, tuple)) and item:
        return _safe_text(item[0])
    if isinstance(item, dict):
        return _safe_text(item.get("topic") or item.get("label") or item.get("name"))
    return ""


def _topic_score(item: Any) -> float:
    if isinstance(item, (list, tuple)) and len(item) > 1:
        return _safe_float(item[1])
    if isinstance(item, dict):
        return max(
            _safe_float(item.get("priority_score")),
            _safe_float(item.get("rising_score")),
            _safe_float(item.get("momentum_delta")),
            _safe_float(item.get("score")),
            _safe_float(item.get("count")),
        )
    return 0.0


def _extract_topic_items(radar_intelligence: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    strategic_items = radar_intelligence.get("strategic_priority")
    rising_items = radar_intelligence.get("rising_topics")
    weekly_items = radar_intelligence.get("weekly_momentum")
    trend_items = radar_intelligence.get("topic_trends")

    if isinstance(strategic_items, dict):
        items = strategic_items.get("items") if isinstance(strategic_items.get("items"), dict) else {}
        candidates.extend(items.get("strategic_priority_topics") or [])
    if isinstance(rising_items, dict):
        items = rising_items.get("items") if isinstance(rising_items.get("items"), dict) else {}
        candidates.extend(items.get("rising_topics") or [])
    if isinstance(weekly_items, dict):
        items = weekly_items.get("items") if isinstance(weekly_items.get("items"), dict) else {}
        candidates.extend(items.get("rising_this_week") or [])
    if isinstance(trend_items, dict):
        items = trend_items.get("items") if isinstance(trend_items.get("items"), dict) else {}
        candidates.extend(items.get("top_topics") or [])

    seen: set[str] = set()
    topics: list[dict[str, Any]] = []
    for item in candidates:
        label = _topic_label(item)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        topics.append(
            {
                "topic": label,
                "score": _topic_score(item),
                "source": "radar_intelligence",
                "reason": _topic_reason(label, len(topics)),
            }
        )

    return sorted(topics, key=lambda item: _safe_float(item.get("score")), reverse=True)[:8]


def _topic_reason(topic: str, index: int) -> str:
    if index == 0:
        return f"{topic} is the strongest current strategic synthesis candidate across the latest radar signals."
    if index <= 2:
        return f"{topic} has enough repeated movement to stay near the top of the watch surface."
    return f"{topic} is present in the current signal environment and should remain visible for follow-up."


def _extract_highlights(payload: Any, *, signal_type: str, limit: int = 4) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    raw_items = summary.get("highlights") if isinstance(summary.get("highlights"), list) else []
    if not raw_items:
        raw_items = payload.get("signals") if isinstance(payload.get("signals"), list) else []

    highlights: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = _safe_text(item.get("title"))
        if not title:
            continue
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
        highlights.append(
            {
                "title": title,
                "summary": _safe_text(
                    profile.get("project_fit")
                    or profile.get("product_opportunity")
                    or profile.get("why_it_matters")
                    or profile.get("why_this_matters")
                    or profile.get("problem_summary")
                    or item.get("summary")
                ),
                "url": _safe_text(item.get("url")),
                "entity_id": _item_entity_id(item, signal_type=signal_type),
                "subtopic": _safe_text(item.get("agent_subtopic") or item.get("friction_subtopic")),
                "topic_tokens": sorted(_topic_tokens_from_item(item))[:12],
                "source": _safe_text(item.get("source")),
                "type": signal_type,
                "score": max(
                    _safe_float(item.get("agent_watch_score")),
                    _safe_float(item.get("friction_score")),
                    _safe_float(item.get("score")),
                ),
            }
        )

    return sorted(highlights, key=lambda item: _safe_float(item.get("score")), reverse=True)[:limit]


def _extract_cluster_candidates(payload: Any, *, signal_type: str, limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw_items = payload.get("signals") if isinstance(payload.get("signals"), list) else []
    if not raw_items:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        raw_items = summary.get("highlights") if isinstance(summary.get("highlights"), list) else []

    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = _safe_text(item.get("title"))
        if not title:
            continue
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
        candidates.append(
            {
                "title": title,
                "summary": _safe_text(
                    profile.get("project_fit")
                    or profile.get("product_opportunity")
                    or profile.get("why_it_matters")
                    or profile.get("why_this_matters")
                    or profile.get("problem_summary")
                    or item.get("summary")
                ),
                "url": _safe_text(item.get("url")),
                "entity_id": _item_entity_id(item, signal_type=signal_type),
                "source": _safe_text(item.get("source")),
                "subtopic": _safe_text(item.get("agent_subtopic") or item.get("friction_subtopic")),
                "type": signal_type,
                "score": max(
                    _safe_float(item.get("agent_watch_score")),
                    _safe_float(item.get("friction_score")),
                    _safe_float(item.get("score")),
                    _safe_float(item.get("ecosystem_relevance_score")),
                ),
                "topic_tokens": sorted(_topic_tokens_from_item(item)),
            }
        )

    return sorted(candidates, key=lambda item: _safe_float(item.get("score")), reverse=True)[:limit]


def _cluster_label(shared_topics: list[str], agent_item: dict[str, Any], friction_item: dict[str, Any]) -> str:
    if shared_topics:
        return shared_topics[0].title()
    agent_subtopic = _safe_text(agent_item.get("subtopic"))
    friction_subtopic = _safe_text(friction_item.get("subtopic"))
    if agent_subtopic and friction_subtopic:
        return f"{agent_subtopic} / {friction_subtopic}"
    return "Supply / demand convergence"


def _cluster_id(agent_item: dict[str, Any], friction_item: dict[str, Any]) -> str:
    raw = "|".join(
        [
            _safe_text(agent_item.get("entity_id") or agent_item.get("url") or agent_item.get("title")).lower(),
            _safe_text(friction_item.get("entity_id") or friction_item.get("url") or friction_item.get("title")).lower(),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"knowledge-convergence-{digest}"


def _item_summary(item: dict[str, Any]) -> str:
    return _safe_text(item.get("summary")) or _safe_text(item.get("title"))


def _format_topic_text(topics: list[str]) -> str:
    clean_topics = [_safe_text(topic) for topic in topics if _safe_text(topic)]
    if not clean_topics:
        return "the current supply/demand pattern"
    if len(clean_topics) == 1:
        return clean_topics[0]
    return ", ".join(clean_topics[:3])


def _build_convergence_rationale(
    *,
    label: str,
    shared_topics: list[str],
    strategic_overlap: list[str],
    agent_item: dict[str, Any],
    friction_item: dict[str, Any],
    exploratory_pair: bool,
) -> dict[str, str]:
    agent_title = _safe_text(agent_item.get("title")) or "The supply-side signal"
    friction_title = _safe_text(friction_item.get("title")) or "The demand-side signal"
    agent_summary = _item_summary(agent_item)
    friction_summary = _item_summary(friction_item)
    topic_text = _format_topic_text(shared_topics or strategic_overlap)

    if exploratory_pair:
        why_paired = (
            f"{agent_title} and {friction_title} are paired as a watch-only supply/demand probe. "
            "The system can see both agent ecosystem movement and user pain in the same cycle, "
            "but the topic overlap is still weak."
        )
    else:
        why_paired = (
            f"{agent_title} is the supply-side movement, while {friction_title} is the demand-side pain. "
            f"They are paired because both point toward {topic_text}, making the combination more useful "
            "for human review than either item alone."
        )

    return {
        "supply_read": (
            f"Supply: {agent_title} shows agent ecosystem capability or tooling movement"
            f"{f' around {topic_text}' if topic_text else ''}."
            f"{f' {agent_summary}' if agent_summary and agent_summary != agent_title else ''}"
        ),
        "demand_read": (
            f"Demand: {friction_title} shows operational pain or unmet need"
            f"{f' around {topic_text}' if topic_text else ''}."
            f"{f' {friction_summary}' if friction_summary and friction_summary != friction_title else ''}"
        ),
        "why_paired": why_paired,
        "review_boundary": (
            "This convergence is review context only. It can prepare Project Takeaway review, "
            "but it does not create verified evidence or low-risk Action readiness by itself."
        ),
    }


def _project_takeaway_map(
    *,
    project_matches: list[dict[str, Any]],
    label: str,
    shared_topics: list[str],
    agent_item: dict[str, Any],
    friction_item: dict[str, Any],
) -> dict[str, str]:
    result: dict[str, str] = {}
    topic_text = ", ".join(shared_topics[:4]) if shared_topics else "supply-demand convergence"
    for project in project_matches:
        project_name = _safe_text(project.get("project_name") or project.get("project_id"))
        if not project_name:
            continue
        result[project_name] = (
            f"Review {label} for this project. Shared topics: {topic_text}. "
            f"Supply signal: {_safe_text(agent_item.get('title'))}. "
            f"Demand signal: {_safe_text(friction_item.get('title'))}."
        )
    return result


def _build_convergence_briefs(
    *,
    agent_watch: dict[str, Any],
    friction_signals: dict[str, Any],
    strategic_topics: list[dict[str, Any]],
    projects: list[dict[str, Any]] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    agent_candidates = _extract_cluster_candidates(agent_watch, signal_type="agent_watch")
    friction_candidates = _extract_cluster_candidates(friction_signals, signal_type="friction_signal")
    if not agent_candidates or not friction_candidates:
        return []

    strategic_tokens: set[str] = set()
    for topic in strategic_topics:
        strategic_tokens.update(_keyword_tokens(_safe_text(topic.get("topic"))))
    projects = projects or []

    pairs: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str]] = set()
    for agent_item in agent_candidates:
        agent_tokens = set(agent_item.get("topic_tokens") or [])
        for friction_item in friction_candidates:
            pair_key = (_safe_text(agent_item.get("entity_id")), _safe_text(friction_item.get("entity_id")))
            if pair_key in used_pairs:
                continue
            friction_tokens = set(friction_item.get("topic_tokens") or [])
            shared = sorted(agent_tokens & friction_tokens)
            strategic_overlap = sorted((agent_tokens | friction_tokens) & strategic_tokens)
            overlap_score = len(shared) * 2 + len(strategic_overlap)
            combined_score = (
                _safe_float(agent_item.get("score")) + _safe_float(friction_item.get("score"))
            ) / 2
            exploratory_pair = (
                not pairs
                and agent_item is agent_candidates[0]
                and friction_item is friction_candidates[0]
                and overlap_score <= 0
            )
            if overlap_score <= 0 and combined_score < 0.75 and not exploratory_pair:
                continue
            used_pairs.add(pair_key)
            confidence = "high" if overlap_score >= 3 else "medium" if overlap_score >= 1 else "low"
            shared_topics = shared[:4] or strategic_overlap[:3]
            label = _cluster_label(shared_topics, agent_item, friction_item)
            project_matches = _project_relevance_matches(
                shared_topics=shared_topics,
                agent_item=agent_item,
                friction_item=friction_item,
                projects=projects,
            )
            review_readiness = _brief_readiness(
                confidence=confidence,
                shared_topics=shared_topics,
                project_matches=project_matches,
                agent_item=agent_item,
                friction_item=friction_item,
            )
            quality = _brief_quality(
                shared_topics=shared_topics,
                strategic_overlap=strategic_overlap,
                project_matches=project_matches,
                review_readiness=review_readiness,
                agent_item=agent_item,
                friction_item=friction_item,
            )
            takeaway_map = _project_takeaway_map(
                project_matches=project_matches,
                label=label,
                shared_topics=shared_topics,
                agent_item=agent_item,
                friction_item=friction_item,
            )
            rationale = _build_convergence_rationale(
                label=label,
                shared_topics=shared_topics,
                strategic_overlap=strategic_overlap,
                agent_item=agent_item,
                friction_item=friction_item,
                exploratory_pair=exploratory_pair,
            )
            pairs.append(
                {
                    "cluster_id": _cluster_id(agent_item, friction_item),
                    "label": label,
                    "confidence": confidence,
                    "pair_type": "exploratory" if exploratory_pair else "topic_overlap",
                    "score": round(combined_score + (overlap_score * 0.1), 3),
                    "shared_topics": shared_topics,
                    "strategic_topic_overlap": strategic_overlap[:4],
                    "agent_watch_item": {
                        key: agent_item.get(key)
                        for key in ("title", "summary", "url", "entity_id", "source", "subtopic", "score")
                    },
                    "friction_item": {
                        key: friction_item.get(key)
                        for key in ("title", "summary", "url", "entity_id", "source", "subtopic", "score")
                    },
                    "brief": (
                        rationale["why_paired"]
                        if not exploratory_pair
                        else rationale["why_paired"]
                    ),
                    "why_it_matters": (
                        "Aligned supply and demand signals are stronger than a repo movement or pain signal by itself."
                        if not exploratory_pair
                        else "This keeps the strongest supply/demand pair visible for human review without treating it as a strong convergence signal."
                    ),
                    "supply_read": rationale["supply_read"],
                    "demand_read": rationale["demand_read"],
                    "why_paired": rationale["why_paired"],
                    "review_boundary": rationale["review_boundary"],
                    "recommended_next_step": (
                        "Review the linked Agent Watch and Friction details, then use the matched project context "
                        "to decide whether this belongs in Project Takeaway review."
                    ),
                    "action_gate": "human_review_required",
                    "review_readiness": review_readiness,
                    "quality": quality,
                    "project_relevance": {
                        "matched_projects": project_matches,
                        "match_count": len(project_matches),
                        "project_takeaway_map": takeaway_map,
                    },
                    "evidence_profile": {
                        "source_count": review_readiness["source_count"],
                        "shared_topic_count": len(shared_topics),
                        "strategic_topic_overlap_count": len(strategic_overlap),
                        "agent_watch_score": _safe_float(agent_item.get("score")),
                        "friction_score": _safe_float(friction_item.get("score")),
                        "quality_score": quality["score"],
                        "quality_label": quality["label"],
                        "quality_reason": quality["reason"],
                        "support_note": (
                            "This brief is based on one supply-side item and one demand-side item. "
                            "It is a review candidate, not verified evidence by itself."
                            if not exploratory_pair
                            else "This is an exploratory pair with weak or missing topic overlap. Treat it as watch-only context until stronger evidence appears."
                        ),
                    },
                }
            )

    return sorted(pairs, key=lambda item: _safe_float(item.get("score")), reverse=True)[:limit]


def _build_ops_summary(
    *,
    topic_count: int,
    agent_count: int,
    friction_count: int,
    review_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
) -> dict[str, list[str]]:
    actionable_count = _safe_int(review_summary.get("actionable_count")) or _safe_int(
        calibration_summary.get("actionable_event_count")
    )
    watch_count = _safe_int(review_summary.get("watch_count")) or _safe_int(
        calibration_summary.get("watch_event_count")
    )
    blocked_rate = _safe_float(review_summary.get("blocked_action_rate")) or _safe_float(
        calibration_summary.get("blocked_action_rate")
    )
    unsupported_claim_count = _safe_int(review_summary.get("unsupported_claim_count")) + _safe_int(
        calibration_summary.get("unsupported_claim_count")
    )
    manual_source_count = _safe_int(review_summary.get("manual_record_count")) + _safe_int(
        calibration_summary.get("manual_event_count")
    )

    achieved = [
        f"{topic_count} strategic topic candidates are visible from the current radar cycle.",
        f"{agent_count} agent-watch items and {friction_count} friction items are available for supply/demand comparison.",
    ]
    if actionable_count:
        achieved.append(f"{actionable_count} review outcomes have reached confirmed/actionable status.")
    if manual_source_count:
        achieved.append(f"{manual_source_count} manual-source review/calibration events preserve user-selected source context.")

    gaps: list[str] = []
    if watch_count:
        gaps.append(f"{watch_count} items remain in watch state and need later review before stronger action.")
    if blocked_rate:
        gaps.append(f"{round(blocked_rate * 100, 1)}% of review records include blocked downstream actions.")
    if unsupported_claim_count:
        gaps.append(f"{unsupported_claim_count} unsupported or contradicted claims remain visible in review/calibration history.")
    if not gaps:
        gaps.append("No major review-quality gap is visible from the current summary data.")

    next_focus = [
        "Compare agent ecosystem movement against friction signals before creating new action commitments.",
        "Promote only verified or partially verified synthesis candidates into Project Takeaway review.",
    ]
    if watch_count:
        next_focus.insert(0, "Review watched items with clear success criteria before converting them into actions.")

    return {
        "achieved": achieved,
        "gaps": gaps,
        "next_focus": next_focus,
    }


def build_strategic_synthesis_response(
    *,
    radar_intelligence: dict[str, Any] | None,
    review_summary: dict[str, Any] | None = None,
    calibration_summary: dict[str, Any] | None = None,
    projects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    radar_intelligence = radar_intelligence or {}
    review_summary = review_summary or {}
    calibration_summary = calibration_summary or {}
    agent_watch = radar_intelligence.get("agent_watch") if isinstance(radar_intelligence.get("agent_watch"), dict) else {}
    friction_signals = (
        radar_intelligence.get("friction_signals")
        if isinstance(radar_intelligence.get("friction_signals"), dict)
        else {}
    )

    topics = _extract_topic_items(radar_intelligence)
    agent_highlights = _extract_highlights(agent_watch, signal_type="agent_watch")
    friction_highlights = _extract_highlights(friction_signals, signal_type="friction_signal")
    convergence_briefs = _build_convergence_briefs(
        agent_watch=agent_watch,
        friction_signals=friction_signals,
        strategic_topics=topics,
        projects=projects or [],
    )
    agent_count = _safe_int(agent_watch.get("count")) or len(_items_from_payload(agent_watch))
    friction_count = _safe_int(friction_signals.get("count")) or len(_items_from_payload(friction_signals))
    ops_summary = _build_ops_summary(
        topic_count=len(topics),
        agent_count=agent_count,
        friction_count=friction_count,
        review_summary=review_summary,
        calibration_summary=calibration_summary,
    )

    return {
        "generated_at": _utc_now_iso(),
        "synthesis_type": "strategic_synthesis_mvp",
        "summary": {
            "strategic_topic_count": len(topics),
            "agent_watch_count": agent_count,
            "friction_signal_count": friction_count,
            "convergence_brief_count": len(convergence_briefs),
            "review_record_count": _safe_int(review_summary.get("total_records")),
            "calibration_event_count": _safe_int(calibration_summary.get("total_events")),
            "manual_source_event_count": _safe_int(review_summary.get("manual_record_count"))
            + _safe_int(calibration_summary.get("manual_event_count")),
            "blocked_action_rate": _safe_float(review_summary.get("blocked_action_rate"))
            or _safe_float(calibration_summary.get("blocked_action_rate")),
            "latest_reviewed_at": _safe_text(review_summary.get("latest_reviewed_at")),
            "latest_calibration_event_at": _safe_text(calibration_summary.get("latest_event_at")),
        },
        "strategic_topics": topics,
        "supply_demand": {
            "agent_watch_highlights": agent_highlights,
            "friction_highlights": friction_highlights,
            "convergence_briefs": convergence_briefs,
            "interpretation": (
                "Agent Watch shows supply-side ecosystem movement; Friction Signals show demand-side pain. "
                "The useful synthesis is where both point toward the same project or product question."
            ),
        },
        "review_quality": {
            "review_summary": review_summary,
            "calibration_summary": calibration_summary,
            "ops_summary": ops_summary,
        },
    }
