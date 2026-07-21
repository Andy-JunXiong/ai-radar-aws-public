import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "producthunt_agent_signals.json"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)

PRODUCT_HUNT_API_URL = "https://api.producthunt.com/v2/api/graphql"
PRODUCT_HUNT_SEARCH_WINDOW_DAYS = int(os.getenv("AI_AGENT_PRODUCTHUNT_SEARCH_WINDOW_DAYS", "30"))
PRODUCT_HUNT_PER_RUN_LIMIT = max(
    1,
    min(int(os.getenv("AI_AGENT_PRODUCTHUNT_PER_RUN_LIMIT", "20")), 50),
)
PRODUCT_HUNT_MIN_VOTES = max(0, int(os.getenv("AI_AGENT_PRODUCTHUNT_MIN_VOTES", "20")))

PRODUCT_HUNT_AGENT_KEYWORDS = [
    "ai agent",
    "agent",
    "agentic",
    "autonomous ai",
    "autonomous agent",
    "ai automation",
    "ai assistant",
    "agent platform",
]


def _product_hunt_token() -> str:
    return (
        os.getenv("PRODUCT_HUNT_API_TOKEN")
        or os.getenv("PRODUCTHUNT_API_TOKEN")
        or os.getenv("PRODUCT_HUNT_TOKEN")
        or ""
    ).strip()


def _created_since_iso() -> str:
    created_since = datetime.now(timezone.utc) - timedelta(days=PRODUCT_HUNT_SEARCH_WINDOW_DAYS)
    return created_since.isoformat()


def _matched_keywords(*values: str) -> list[str]:
    haystack = " ".join(value.strip().lower() for value in values if value).strip()
    if not haystack:
        return []
    return [keyword for keyword in PRODUCT_HUNT_AGENT_KEYWORDS if keyword in haystack]


def _graphql_query() -> str:
    return """
    query AgentWatchPosts($first: Int!, $postedAfter: DateTime) {
      posts(first: $first, postedAfter: $postedAfter, order: VOTES) {
        edges {
          node {
            id
            name
            tagline
            description
            votesCount
            createdAt
            url
            topics {
              edges {
                node {
                  name
                  slug
                }
              }
            }
          }
        }
      }
    }
    """


def _product_hunt_request() -> dict[str, Any]:
    token = _product_hunt_token()
    if not token:
        print("[producthunt_agent] PRODUCT_HUNT_API_TOKEN not configured; skipping Product Hunt collection")
        return {}

    payload = {
        "query": _graphql_query(),
        "variables": {
            "first": PRODUCT_HUNT_PER_RUN_LIMIT,
            "postedAfter": _created_since_iso(),
        },
    }
    req = request.Request(
        PRODUCT_HUNT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "AI-Radar-Agent-Watch/1.0",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def _topic_edges(post: dict[str, Any]) -> list[dict[str, Any]]:
    topics = post.get("topics")
    if not isinstance(topics, dict):
        return []
    edges = topics.get("edges")
    if not isinstance(edges, list):
        return []
    return [edge for edge in edges if isinstance(edge, dict)]


def _normalize_post(post: dict[str, Any]) -> dict[str, Any] | None:
    name = str(post.get("name") or "").strip()
    tagline = str(post.get("tagline") or "").strip()
    description = str(post.get("description") or "").strip()
    url = str(post.get("url") or "").strip()
    created_at = str(post.get("createdAt") or "").strip()

    try:
        votes = int(post.get("votesCount") or 0)
    except Exception:
        votes = 0

    if not name or not url or not created_at or votes < PRODUCT_HUNT_MIN_VOTES:
        return None

    topic_names: list[str] = []
    topic_slugs: list[str] = []
    for edge in _topic_edges(post):
        node = edge.get("node")
        if not isinstance(node, dict):
            continue
        topic_name = str(node.get("name") or "").strip()
        topic_slug = str(node.get("slug") or "").strip()
        if topic_name:
            topic_names.append(topic_name)
        if topic_slug:
            topic_slugs.append(topic_slug)

    matched_keywords = _matched_keywords(name, tagline, description, " ".join(topic_names + topic_slugs))
    if not matched_keywords:
        return None

    summary = tagline or description or "New Product Hunt launch detected in the AI agent ecosystem."
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "title": name,
        "summary": summary,
        "content": description or summary,
        "url": url,
        "author": "Product Hunt",
        "source": "producthunt",
        "source_type": "producthunt_agent",
        "category": "ai_agents",
        "topic": "ai_agents",
        "published_at": created_at,
        "timestamp": now_iso,
        "collected_at": now_iso,
        "source_weight": 0.92 if votes >= 500 else 0.84 if votes >= 150 else 0.74,
        "summary_length": len(summary),
        "content_length": len(description or summary),
        "metadata": {
            "product_name": name,
            "product_url": url,
            "product_hunt_votes": votes,
            "launch_date": created_at,
            "tags": sorted(set([slug.lower() for slug in topic_slugs if slug] + matched_keywords)),
            "topic_names": sorted(set(topic_names)),
            "matched_keywords": matched_keywords,
        },
    }


def collect_producthunt_agent_signals() -> list[dict[str, Any]]:
    try:
        payload = _product_hunt_request()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"[producthunt_agent] request failed: {exc.code} {detail}")
        return []
    except Exception as exc:
        print(f"[producthunt_agent] request failed: {exc}")
        return []

    data = payload.get("data") if isinstance(payload, dict) else {}
    posts = data.get("posts") if isinstance(data, dict) else {}
    edges = posts.get("edges") if isinstance(posts, dict) else []
    signals: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for edge in edges if isinstance(edges, list) else []:
        node = edge.get("node") if isinstance(edge, dict) else None
        if not isinstance(node, dict):
            continue

        normalized = _normalize_post(node)
        if not normalized:
            continue

        dedupe_key = str(normalized.get("url") or "").strip().lower()
        if not dedupe_key or dedupe_key in seen_urls:
            continue

        seen_urls.add(dedupe_key)
        signals.append(normalized)

    return sorted(
        signals,
        key=lambda item: (
            -int(((item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}).get("product_hunt_votes") or 0),
            str(item.get("published_at") or ""),
        ),
    )


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "producthunt_agent_collector",
        "count": len(signals),
        "signals": signals,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[producthunt_agent] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    collected = collect_producthunt_agent_signals()
    save(collected)
    print(f"[producthunt_agent] done, total signals: {len(collected)}")
