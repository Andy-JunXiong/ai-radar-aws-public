import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[3]
RAW_GITHUB_AGENT_SIGNALS_FILE = BASE_DIR / "data" / "output" / "github_agent_signals.json"
RAW_HN_AGENT_SIGNALS_FILE = BASE_DIR / "data" / "output" / "hackernews_agent_signals.json"
RAW_PRODUCTHUNT_AGENT_SIGNALS_FILE = BASE_DIR / "data" / "output" / "producthunt_agent_signals.json"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "agent_watch_signals.json"


def _load_collector_payload(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
        return [item for item in payload["signals"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_tags(raw_tags: object) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    tags = []
    for tag in raw_tags:
        normalized = _normalize_text(tag).lower()
        if normalized:
            tags.append(normalized)
    return sorted(set(tags))


def normalize_agent_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}

    repo_name = _normalize_text(metadata.get("repo_name")) or _normalize_text(signal.get("title"))
    repo_url = _normalize_text(metadata.get("repo_url")) or _normalize_text(signal.get("url"))
    summary = _normalize_text(signal.get("summary")) or "Emerging AI agent repository detected on GitHub."
    published_at = _normalize_text(signal.get("published_at")) or datetime.now(timezone.utc).isoformat()
    stars_raw = metadata.get("repo_stars")

    try:
        repo_stars = int(stars_raw or 0)
    except Exception:
        repo_stars = 0

    if not repo_name or not repo_url:
        return None

    tags = _normalize_tags(metadata.get("tags"))
    matched_keywords = _normalize_tags(metadata.get("matched_keywords"))
    language = _normalize_text(metadata.get("language"))
    created_at = _normalize_text(metadata.get("created_at")) or published_at

    normalized_summary = summary
    if repo_stars > 0 and language:
        normalized_summary = f"{summary} GitHub traction: {repo_stars} stars, language: {language}."
    elif repo_stars > 0:
        normalized_summary = f"{summary} GitHub traction: {repo_stars} stars."

    return {
        "title": repo_name,
        "summary": normalized_summary,
        "content": _normalize_text(signal.get("content")) or summary,
        "url": repo_url,
        "author": _normalize_text(signal.get("author")),
        "source": "github",
        "source_type": "github_agent",
        "category": "AI Agents",
        "topic": "ai_agents",
        "published_at": published_at,
        "timestamp": _normalize_text(signal.get("timestamp")) or datetime.now(timezone.utc).isoformat(),
        "collected_at": _normalize_text(signal.get("collected_at")) or datetime.now(timezone.utc).isoformat(),
        "source_weight": signal.get("source_weight", 0.75),
        "summary_length": len(normalized_summary),
        "content_length": len(_normalize_text(signal.get("content")) or summary),
        "score": None,
        "metadata": {
            "repo_name": repo_name,
            "repo_url": repo_url,
            "repo_stars": repo_stars,
            "language": language,
            "created_at": created_at,
            "tags": tags,
            "matched_keywords": matched_keywords,
        },
    }


def normalize_hackernews_agent_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}

    title = _normalize_text(signal.get("title"))
    url = _normalize_text(signal.get("url"))
    summary = _normalize_text(signal.get("summary")) or "Emerging AI agent discussion detected on Hacker News."
    published_at = _normalize_text(signal.get("published_at")) or datetime.now(timezone.utc).isoformat()

    try:
        points = int(metadata.get("hn_points") or 0)
    except Exception:
        points = 0
    try:
        comments = int(metadata.get("hn_comments") or 0)
    except Exception:
        comments = 0

    if not title or not url:
        return None

    matched_keywords = _normalize_tags(metadata.get("matched_keywords"))
    search_term = _normalize_text(metadata.get("search_term"))
    normalized_summary = f"{summary} HN traction: {points} points, {comments} comments."

    return {
        "title": title,
        "summary": normalized_summary,
        "content": _normalize_text(signal.get("content")) or summary,
        "url": url,
        "author": _normalize_text(signal.get("author")),
        "source": "hackernews",
        "source_type": "hackernews_agent",
        "category": "AI Agents",
        "topic": "ai_agents",
        "published_at": published_at,
        "timestamp": _normalize_text(signal.get("timestamp")) or datetime.now(timezone.utc).isoformat(),
        "collected_at": _normalize_text(signal.get("collected_at")) or datetime.now(timezone.utc).isoformat(),
        "source_weight": signal.get("source_weight", 0.7),
        "summary_length": len(normalized_summary),
        "content_length": len(_normalize_text(signal.get("content")) or summary),
        "score": None,
        "metadata": {
            "hn_points": points,
            "hn_comments": comments,
            "created_at": _normalize_text(metadata.get("created_at")) or published_at,
            "matched_keywords": matched_keywords,
            "search_term": search_term,
        },
    }


def normalize_producthunt_agent_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}

    title = _normalize_text(signal.get("title"))
    url = _normalize_text(signal.get("url"))
    summary = _normalize_text(signal.get("summary")) or "Emerging AI agent launch detected on Product Hunt."
    description = _normalize_text(signal.get("content")) or summary
    published_at = _normalize_text(signal.get("published_at")) or datetime.now(timezone.utc).isoformat()

    try:
        votes = int(metadata.get("product_hunt_votes") or 0)
    except Exception:
        votes = 0

    if not title or not url:
        return None

    matched_keywords = _normalize_tags(metadata.get("matched_keywords"))
    tags = _normalize_tags(metadata.get("tags"))
    topic_names = [
        _normalize_text(value)
        for value in (metadata.get("topic_names") or [])
        if _normalize_text(value)
    ]
    normalized_summary = f"{summary} Product Hunt traction: {votes} votes."

    return {
        "title": title,
        "summary": normalized_summary,
        "content": description,
        "url": url,
        "author": "Product Hunt",
        "source": "producthunt",
        "source_type": "producthunt_agent",
        "category": "AI Agents",
        "topic": "ai_agents",
        "published_at": published_at,
        "timestamp": _normalize_text(signal.get("timestamp")) or datetime.now(timezone.utc).isoformat(),
        "collected_at": _normalize_text(signal.get("collected_at")) or datetime.now(timezone.utc).isoformat(),
        "source_weight": signal.get("source_weight", 0.74),
        "summary_length": len(normalized_summary),
        "content_length": len(description),
        "score": None,
        "metadata": {
            "product_name": title,
            "product_url": url,
            "product_hunt_votes": votes,
            "launch_date": _normalize_text(metadata.get("launch_date")) or published_at,
            "tags": tags,
            "topic_names": topic_names,
            "matched_keywords": matched_keywords,
        },
    }


def normalize_github_agent_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for signal in signals:
        item = normalize_agent_signal(signal)
        if not item:
            continue

        dedupe_key = _normalize_text(item.get("url")).lower()
        if dedupe_key and dedupe_key in seen_urls:
            continue
        if dedupe_key:
            seen_urls.add(dedupe_key)

        normalized.append(item)

    return normalized


def collect_normalized_github_agent_signals() -> list[dict[str, Any]]:
    raw_signals = _load_collector_payload(RAW_GITHUB_AGENT_SIGNALS_FILE)
    return normalize_github_agent_signals(raw_signals)


def collect_normalized_hackernews_agent_signals() -> list[dict[str, Any]]:
    raw_signals = _load_collector_payload(RAW_HN_AGENT_SIGNALS_FILE)
    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for signal in raw_signals:
        item = normalize_hackernews_agent_signal(signal)
        if not item:
            continue

        dedupe_key = _normalize_text(item.get("url")).lower()
        if dedupe_key and dedupe_key in seen_urls:
            continue
        if dedupe_key:
            seen_urls.add(dedupe_key)

        normalized.append(item)

    return normalized


def collect_normalized_producthunt_agent_signals() -> list[dict[str, Any]]:
    raw_signals = _load_collector_payload(RAW_PRODUCTHUNT_AGENT_SIGNALS_FILE)
    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for signal in raw_signals:
        item = normalize_producthunt_agent_signal(signal)
        if not item:
            continue

        dedupe_key = _normalize_text(item.get("url")).lower()
        if dedupe_key and dedupe_key in seen_urls:
            continue
        if dedupe_key:
            seen_urls.add(dedupe_key)

        normalized.append(item)

    return normalized


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "agent_signal_processor",
        "count": len(signals),
        "signals": signals,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[agent_processor] saved {len(signals)} normalized signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    normalized = collect_normalized_github_agent_signals()
    save(normalized)
    print(f"[agent_processor] done, total normalized signals: {len(normalized)}")
