from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


AGENT_HEATING_METRIC_DELTA = 50
FRICTION_HEATING_METRIC_DELTA = 10
HEATING_SCORE_DELTA = 0.08
DROPPED_AFTER_MISSED_DAYS = 3


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


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


def _parse_dt(value: object) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_between(later: object, earlier: object) -> int:
    later_dt = _parse_dt(later)
    earlier_dt = _parse_dt(earlier)
    if not later_dt or not earlier_dt:
        return 0
    return max(0, (later_dt.date() - earlier_dt.date()).days)


def _normalize_url(value: object) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    try:
        parts = urlsplit(text)
        if not parts.scheme or not parts.netloc:
            return text.lower().rstrip("/")
        path = parts.path.rstrip("/")
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                path,
                "",
                "",
            )
        )
    except Exception:
        return text.lower().rstrip("/")


def _payload_items(payload_or_items: Any, *, item_key: str) -> list[dict[str, Any]]:
    if isinstance(payload_or_items, dict):
        items = payload_or_items.get(item_key)
        if not isinstance(items, list):
            items = payload_or_items.get("signals")
    else:
        items = payload_or_items
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _previous_items_by_id(previous_state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    items = _payload_items(previous_state or {}, item_key="items")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        entity_id = _safe_text(item.get("entity_id"))
        if entity_id:
            result[entity_id] = item
    return result


def _ranked_items(items: list[dict[str, Any]], *, score_field: str) -> list[tuple[int, dict[str, Any]]]:
    def sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        return (
            _safe_float(item.get(score_field) or item.get("score")),
            _safe_float(item.get("signal_score")),
            _safe_text(item.get("published_at")),
        )

    return list(enumerate(sorted(items, key=sort_key, reverse=True), start=1))


def _metric_delta(current: int, previous: int) -> int:
    return current - previous


def _score_delta(current: float, previous: float) -> float:
    return round(current - previous, 4)


def _active_status(
    *,
    previous: dict[str, Any] | None,
    generated_at: str,
    metric_delta_1d: int,
    score_delta_1d: float,
    heating_metric_delta: int,
) -> str:
    if not previous:
        return "new"

    gap_days = _days_between(generated_at, previous.get("last_seen_at"))
    if gap_days > 1:
        return "revived"
    if metric_delta_1d >= heating_metric_delta or score_delta_1d >= HEATING_SCORE_DELTA:
        return "heating"
    return "sustained"


def _inactive_status(*, generated_at: str, previous: dict[str, Any]) -> str:
    missed_days = max(1, _days_between(generated_at, previous.get("last_seen_at")))
    if missed_days >= DROPPED_AFTER_MISSED_DAYS:
        return "dropped"
    return "cooling"


def _momentum_score(
    *,
    current_score: float,
    metric_delta_1d: int,
    status: str,
    metric_scale: int,
) -> float:
    metric_boost = min(0.35, max(0, metric_delta_1d) / float(metric_scale))
    status_boost = {
        "new": 0.18,
        "revived": 0.16,
        "heating": 0.22,
        "sustained": 0.08,
        "cooling": -0.05,
        "dropped": -0.15,
    }.get(status, 0.0)
    return round(max(0.0, min(1.0, current_score * 0.55 + metric_boost + status_boost)), 4)


def _base_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(_safe_text(item.get("status")) for item in items).items()))


def _top_items(items: list[dict[str, Any]], *, status: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    candidates = [item for item in items if not status or item.get("status") == status]
    return sorted(
        candidates,
        key=lambda item: (
            _safe_float(item.get("momentum_score")),
            _safe_int(item.get("metric_delta_1d")),
            _safe_float(item.get("current_score")),
        ),
        reverse=True,
    )[:limit]


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": item.get("entity_id"),
        "title": item.get("title"),
        "canonical_url": item.get("canonical_url"),
        "status": item.get("status"),
        "momentum_score": item.get("momentum_score"),
        "metric_name": item.get("metric_name"),
        "current_metric": item.get("current_metric"),
        "metric_delta_1d": item.get("metric_delta_1d"),
        "current_score": item.get("current_score"),
        "score_delta_1d": item.get("score_delta_1d"),
        "first_seen_at": item.get("first_seen_at"),
        "last_seen_at": item.get("last_seen_at"),
        "seen_days": item.get("seen_days"),
        "source": item.get("source"),
        "source_type": item.get("source_type"),
        "friction_subtopic": item.get("friction_subtopic"),
    }


def _agent_metric(item: dict[str, Any]) -> tuple[str, int]:
    if item.get("repo_stars") is not None:
        return "repo_stars", _safe_int(item.get("repo_stars"))
    if item.get("hn_points") is not None:
        return "hn_points", _safe_int(item.get("hn_points"))
    if item.get("product_hunt_votes") is not None:
        return "product_hunt_votes", _safe_int(item.get("product_hunt_votes"))
    return "traction", 0


def _friction_metric(item: dict[str, Any]) -> tuple[str, int]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if metadata.get("comments") is not None:
        return "comments", _safe_int(metadata.get("comments"))
    if metadata.get("hn_comments") is not None:
        return "hn_comments", _safe_int(metadata.get("hn_comments"))
    return "traction", 0


def _friction_cluster_key(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    subtopic = _safe_text(item.get("friction_subtopic")) or "general_friction"
    repo_name = _safe_text(metadata.get("repo_name")).lower()
    search_term = _safe_text(metadata.get("search_term")).lower()
    if repo_name:
        return f"{subtopic}:{repo_name}"
    if search_term:
        return f"{subtopic}:{search_term}"
    return subtopic


def build_agent_watch_tracking_state(
    current_snapshots: Any,
    previous_state: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    current_items = _payload_items(current_snapshots, item_key="items")
    previous_by_id = _previous_items_by_id(previous_state)
    seen_ids: set[str] = set()
    tracked_items: list[dict[str, Any]] = []

    for rank, item in _ranked_items(current_items, score_field="agent_watch_score"):
        canonical_url = _normalize_url(item.get("canonical_url") or item.get("url"))
        entity_id = _safe_text(item.get("entity_id")) or canonical_url
        if not entity_id:
            continue
        entity_id = entity_id.lower()
        seen_ids.add(entity_id)
        previous = previous_by_id.get(entity_id)
        metric_name, current_metric = _agent_metric(item)
        previous_metric = _safe_int((previous or {}).get("current_metric"))
        current_score = _safe_float(item.get("agent_watch_score") or item.get("signal_score") or item.get("score"))
        previous_score = _safe_float((previous or {}).get("current_score"))
        metric_delta_1d = _metric_delta(current_metric, previous_metric)
        score_delta_1d = _score_delta(current_score, previous_score)
        status = _active_status(
            previous=previous,
            generated_at=generated_at,
            metric_delta_1d=metric_delta_1d,
            score_delta_1d=score_delta_1d,
            heating_metric_delta=AGENT_HEATING_METRIC_DELTA,
        )
        same_seen_day = previous and _days_between(generated_at, previous.get("last_seen_at")) == 0
        seen_days = _safe_int((previous or {}).get("seen_days")) if same_seen_day else _safe_int((previous or {}).get("seen_days")) + 1
        first_seen_at = _safe_text((previous or {}).get("first_seen_at")) or generated_at
        momentum_metric = metric_delta_1d if previous else current_metric
        momentum_score = _momentum_score(
            current_score=current_score,
            metric_delta_1d=momentum_metric,
            status=status,
            metric_scale=250,
        )

        tracked_items.append(
            {
                "entity_id": entity_id,
                "kind": "agent_watch",
                "title": item.get("title", ""),
                "canonical_url": canonical_url,
                "source": item.get("source", ""),
                "source_type": item.get("source_type", ""),
                "agent_subtopic": item.get("agent_subtopic"),
                "published_at": item.get("published_at", ""),
                "first_seen_at": first_seen_at,
                "last_seen_at": generated_at,
                "seen_days": seen_days,
                "missed_days": 0,
                "status": status,
                "current_rank": rank,
                "previous_rank": (previous or {}).get("current_rank"),
                "rank_delta": _safe_int((previous or {}).get("current_rank")) - rank if previous else None,
                "metric_name": metric_name,
                "current_metric": current_metric,
                "previous_metric": previous_metric if previous else None,
                "metric_delta_1d": metric_delta_1d if previous else None,
                "current_score": current_score,
                "previous_score": previous_score if previous else None,
                "score_delta_1d": score_delta_1d if previous else current_score,
                "momentum_score": momentum_score,
                "repo_name": item.get("repo_name"),
                "language": item.get("language"),
                "matched_keywords": item.get("matched_keywords", []),
                "tags": item.get("tags", []),
            }
        )

    for entity_id, previous in previous_by_id.items():
        if entity_id in seen_ids:
            continue
        status = _inactive_status(generated_at=generated_at, previous=previous)
        missed_days = max(1, _days_between(generated_at, previous.get("last_seen_at")))
        current_score = _safe_float(previous.get("current_score"))
        tracked_items.append(
            {
                **previous,
                "status": status,
                "last_seen_at": previous.get("last_seen_at"),
                "missed_days": missed_days,
                "previous_score": current_score,
                "score_delta_1d": 0.0,
                "previous_metric": previous.get("current_metric"),
                "metric_delta_1d": 0,
                "momentum_score": _momentum_score(
                    current_score=current_score,
                    metric_delta_1d=0,
                    status=status,
                    metric_scale=250,
                ),
            }
        )

    tracked_items = sorted(
        tracked_items,
        key=lambda item: (
            _safe_float(item.get("momentum_score")),
            _safe_int(item.get("metric_delta_1d")),
            _safe_float(item.get("current_score")),
        ),
        reverse=True,
    )

    return {
        "generated_at": generated_at,
        "kind": "agent_watch_tracking_state",
        "count": len(tracked_items),
        "counts_by_status": _base_counts(tracked_items),
        "items": tracked_items,
        "report": {
            "new_today": [_compact_item(item) for item in _top_items(tracked_items, status="new")],
            "heating": [_compact_item(item) for item in _top_items(tracked_items, status="heating")],
            "fastest_growing": [_compact_item(item) for item in _top_items(tracked_items)],
            "cooling_or_dropped": [
                _compact_item(item)
                for item in sorted(
                    [item for item in tracked_items if item.get("status") in {"cooling", "dropped"}],
                    key=lambda value: _safe_int(value.get("missed_days")),
                    reverse=True,
                )[:5]
            ],
        },
    }


def build_friction_tracking_state(
    current_signals: Any,
    previous_state: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    current_items = _payload_items(current_signals, item_key="signals")
    previous_by_id = _previous_items_by_id(previous_state)
    seen_ids: set[str] = set()
    tracked_items: list[dict[str, Any]] = []

    for rank, item in _ranked_items(current_items, score_field="friction_score"):
        canonical_url = _normalize_url(item.get("url"))
        entity_id = canonical_url or _safe_text(item.get("title")).lower()
        if not entity_id:
            continue
        seen_ids.add(entity_id)
        previous = previous_by_id.get(entity_id)
        metric_name, current_metric = _friction_metric(item)
        previous_metric = _safe_int((previous or {}).get("current_metric"))
        current_score = _safe_float(item.get("friction_score") or item.get("score"))
        previous_score = _safe_float((previous or {}).get("current_score"))
        metric_delta_1d = _metric_delta(current_metric, previous_metric)
        score_delta_1d = _score_delta(current_score, previous_score)
        status = _active_status(
            previous=previous,
            generated_at=generated_at,
            metric_delta_1d=metric_delta_1d,
            score_delta_1d=score_delta_1d,
            heating_metric_delta=FRICTION_HEATING_METRIC_DELTA,
        )
        same_seen_day = previous and _days_between(generated_at, previous.get("last_seen_at")) == 0
        seen_days = _safe_int((previous or {}).get("seen_days")) if same_seen_day else _safe_int((previous or {}).get("seen_days")) + 1
        first_seen_at = _safe_text((previous or {}).get("first_seen_at")) or generated_at
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        cluster_key = _friction_cluster_key(item)
        momentum_metric = metric_delta_1d if previous else current_metric
        momentum_score = _momentum_score(
            current_score=current_score,
            metric_delta_1d=momentum_metric,
            status=status,
            metric_scale=50,
        )

        tracked_items.append(
            {
                "entity_id": entity_id,
                "kind": "friction_signal",
                "title": item.get("title", ""),
                "canonical_url": canonical_url,
                "source": item.get("source", ""),
                "source_type": item.get("source_type", ""),
                "published_at": item.get("published_at", ""),
                "first_seen_at": first_seen_at,
                "last_seen_at": generated_at,
                "seen_days": seen_days,
                "missed_days": 0,
                "status": status,
                "current_rank": rank,
                "previous_rank": (previous or {}).get("current_rank"),
                "rank_delta": _safe_int((previous or {}).get("current_rank")) - rank if previous else None,
                "metric_name": metric_name,
                "current_metric": current_metric,
                "previous_metric": previous_metric if previous else None,
                "metric_delta_1d": metric_delta_1d if previous else None,
                "current_score": current_score,
                "previous_score": previous_score if previous else None,
                "score_delta_1d": score_delta_1d if previous else current_score,
                "momentum_score": momentum_score,
                "friction_subtopic": item.get("friction_subtopic"),
                "pain_severity_score": item.get("pain_severity_score"),
                "ecosystem_relevance_score": item.get("ecosystem_relevance_score"),
                "pain_cluster_key": cluster_key,
                "repo_name": metadata.get("repo_name"),
                "matched_keywords": metadata.get("matched_keywords", []),
            }
        )

    for entity_id, previous in previous_by_id.items():
        if entity_id in seen_ids:
            continue
        status = _inactive_status(generated_at=generated_at, previous=previous)
        missed_days = max(1, _days_between(generated_at, previous.get("last_seen_at")))
        current_score = _safe_float(previous.get("current_score"))
        tracked_items.append(
            {
                **previous,
                "status": status,
                "last_seen_at": previous.get("last_seen_at"),
                "missed_days": missed_days,
                "previous_score": current_score,
                "score_delta_1d": 0.0,
                "previous_metric": previous.get("current_metric"),
                "metric_delta_1d": 0,
                "momentum_score": _momentum_score(
                    current_score=current_score,
                    metric_delta_1d=0,
                    status=status,
                    metric_scale=50,
                ),
            }
        )

    tracked_items = sorted(
        tracked_items,
        key=lambda item: (
            _safe_float(item.get("momentum_score")),
            _safe_int(item.get("metric_delta_1d")),
            _safe_float(item.get("current_score")),
        ),
        reverse=True,
    )
    cluster_counts = Counter(_safe_text(item.get("pain_cluster_key")) for item in tracked_items if item.get("status") not in {"cooling", "dropped"})

    return {
        "generated_at": generated_at,
        "kind": "friction_tracking_state",
        "count": len(tracked_items),
        "counts_by_status": _base_counts(tracked_items),
        "items": tracked_items,
        "report": {
            "new_today": [_compact_item(item) for item in _top_items(tracked_items, status="new")],
            "heating": [_compact_item(item) for item in _top_items(tracked_items, status="heating")],
            "fastest_growing": [_compact_item(item) for item in _top_items(tracked_items)],
            "recurring_pain_clusters": [
                {"pain_cluster_key": cluster_key, "active_signal_count": count}
                for cluster_key, count in cluster_counts.most_common(8)
            ],
            "cooling_or_dropped": [
                _compact_item(item)
                for item in sorted(
                    [item for item in tracked_items if item.get("status") in {"cooling", "dropped"}],
                    key=lambda value: _safe_int(value.get("missed_days")),
                    reverse=True,
                )[:5]
            ],
        },
    }


def build_agent_friction_tracking_report(
    agent_tracking_state: dict[str, Any],
    friction_tracking_state: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    agent_items = _payload_items(agent_tracking_state, item_key="items")
    friction_items = _payload_items(friction_tracking_state, item_key="items")
    active_agents = [item for item in agent_items if item.get("status") in {"new", "heating", "revived", "sustained"}]
    active_friction = [item for item in friction_items if item.get("status") in {"new", "heating", "revived", "sustained"}]

    friction_topics = {
        _safe_text(item.get("friction_subtopic")).lower()
        for item in active_friction
        if _safe_text(item.get("friction_subtopic"))
    }
    convergence_candidates: list[dict[str, Any]] = []
    for agent in active_agents:
        searchable_terms = {
            _safe_text(agent.get("agent_subtopic")).lower(),
            *[_safe_text(tag).lower() for tag in agent.get("tags", []) if _safe_text(tag)],
            *[_safe_text(keyword).lower() for keyword in agent.get("matched_keywords", []) if _safe_text(keyword)],
        }
        overlapping_terms = sorted(term for term in searchable_terms if term and term in friction_topics)
        if not overlapping_terms:
            continue
        convergence_candidates.append(
            {
                "agent": _compact_item(agent),
                "overlapping_friction_topics": overlapping_terms,
                "candidate_reason": "Agent Watch momentum overlaps with an active friction topic.",
            }
        )

    return {
        "generated_at": generated_at,
        "kind": "agent_friction_tracking_report",
        "agent_watch": {
            "counts_by_status": agent_tracking_state.get("counts_by_status", {}),
            "new_today": agent_tracking_state.get("report", {}).get("new_today", []),
            "heating": agent_tracking_state.get("report", {}).get("heating", []),
            "sustained": [_compact_item(item) for item in _top_items(agent_items, status="sustained")],
            "fastest_growing": agent_tracking_state.get("report", {}).get("fastest_growing", []),
            "cooling_or_dropped": agent_tracking_state.get("report", {}).get("cooling_or_dropped", []),
        },
        "friction_signals": {
            "counts_by_status": friction_tracking_state.get("counts_by_status", {}),
            "new_today": friction_tracking_state.get("report", {}).get("new_today", []),
            "heating": friction_tracking_state.get("report", {}).get("heating", []),
            "sustained": [_compact_item(item) for item in _top_items(friction_items, status="sustained")],
            "fastest_growing": friction_tracking_state.get("report", {}).get("fastest_growing", []),
            "recurring_pain_clusters": friction_tracking_state.get("report", {}).get("recurring_pain_clusters", []),
            "cooling_or_dropped": friction_tracking_state.get("report", {}).get("cooling_or_dropped", []),
        },
        "convergence_candidates": convergence_candidates[:5],
    }
