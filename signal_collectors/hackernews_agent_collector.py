import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "hackernews_agent_signals.json"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)

HN_API_BASE = "https://hn.algolia.com/api/v1/search_by_date"
HN_SEARCH_WINDOW_DAYS = int(os.getenv("AI_AGENT_HN_SEARCH_WINDOW_DAYS", "14"))
HN_PER_QUERY_LIMIT = max(1, min(int(os.getenv("AI_AGENT_HN_PER_QUERY_LIMIT", "10")), 20))
HN_MIN_POINTS = max(0, int(os.getenv("AI_AGENT_HN_MIN_POINTS", "15")))

HN_AGENT_KEYWORDS = [
    "ai agent",
    "agent framework",
    "autonomous ai",
    "autonomous agent",
    "multi-agent",
    "multi agent",
    "agentic",
]


def _hn_request(url: str) -> Any:
    req = request.Request(
        url,
        headers={"User-Agent": "AI-Radar-Agent-Watch/1.0"},
        method="GET",
    )
    with request.urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _created_since_epoch() -> int:
    dt = datetime.now(timezone.utc) - timedelta(days=HN_SEARCH_WINDOW_DAYS)
    return int(dt.timestamp())


def _matched_keywords(*values: str) -> list[str]:
    haystack = " ".join(value.strip().lower() for value in values if value).strip()
    if not haystack:
        return []
    return [keyword for keyword in HN_AGENT_KEYWORDS if keyword in haystack]


def _search_hn(keyword: str) -> list[dict[str, Any]]:
    params = {
        "query": keyword,
        "tags": "story",
        "numericFilters": f"created_at_i>{_created_since_epoch()},points>={HN_MIN_POINTS}",
        "hitsPerPage": HN_PER_QUERY_LIMIT,
    }
    url = f"{HN_API_BASE}?{parse.urlencode(params)}"
    payload = _hn_request(url)
    hits = payload.get("hits", []) if isinstance(payload, dict) else []
    return [item for item in hits if isinstance(item, dict)]


def _normalize_hit(hit: dict[str, Any], search_term: str) -> dict[str, Any] | None:
    title = str(hit.get("title") or hit.get("story_title") or "").strip()
    story_url = str(hit.get("url") or hit.get("story_url") or "").strip()
    author = str(hit.get("author") or "").strip()
    created_at = str(hit.get("created_at") or "").strip()
    points = int(hit.get("points") or 0)
    comments = int(hit.get("num_comments") or 0)

    if not title or not story_url or not created_at:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    matched_keywords = _matched_keywords(title, search_term)
    summary = (
        f"Hacker News discussion detected for an AI agent-related project. "
        f"Current traction: {points} points and {comments} comments."
    )

    return {
        "title": title,
        "summary": summary,
        "content": summary,
        "url": story_url,
        "author": author,
        "source": "hackernews",
        "source_type": "hackernews_agent",
        "category": "ai_agents",
        "topic": "ai_agents",
        "published_at": created_at,
        "timestamp": now_iso,
        "collected_at": now_iso,
        "source_weight": 0.9 if points >= 100 else 0.8 if points >= 40 else 0.7,
        "summary_length": len(summary),
        "content_length": len(summary),
        "metadata": {
            "hn_points": points,
            "hn_comments": comments,
            "created_at": created_at,
            "matched_keywords": matched_keywords,
            "search_term": search_term,
        },
    }


def collect_hackernews_agent_signals() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for keyword in HN_AGENT_KEYWORDS:
        print(f"[hn_agent] searching Hacker News for {keyword}")
        try:
            hits = _search_hn(keyword)
        except Exception as exc:
            print(f"[hn_agent] search failed for {keyword}: {exc}")
            continue

        print(f"[hn_agent] {keyword} -> {len(hits)} hits")

        for hit in hits:
            normalized = _normalize_hit(hit, keyword)
            if not normalized:
                continue

            url = str(normalized.get("url") or "").strip().lower()
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            signals.append(normalized)

    return sorted(
        signals,
        key=lambda item: (
            -int(((item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}).get("hn_points") or 0),
            str(item.get("published_at") or ""),
        ),
    )


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "hackernews_agent_collector",
        "count": len(signals),
        "signals": signals,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[hn_agent] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    collected = collect_hackernews_agent_signals()
    save(collected)
    print(f"[hn_agent] done, total signals: {len(collected)}")
