import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "github_agent_signals.json"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_SEARCH_WINDOW_DAYS = int(os.getenv("AI_AGENT_GITHUB_SEARCH_WINDOW_DAYS", "30"))
GITHUB_PER_QUERY_LIMIT = max(1, min(int(os.getenv("AI_AGENT_GITHUB_PER_QUERY_LIMIT", "10")), 25))
GITHUB_MIN_STARS = max(0, int(os.getenv("AI_AGENT_GITHUB_MIN_STARS", "20")))

GITHUB_AGENT_KEYWORDS = [
    "ai agent",
    "agent framework",
    "multi agent",
    "autonomous agent",
    "agentic",
    "multi-agent",
]

GITHUB_AGENT_SEARCH_QUERIES = [
    '"ai agent"',
    '"agent framework"',
    '"multi agent"',
    '"autonomous agent"',
    "agentic",
    '"multi-agent"',
]


def _github_token() -> str:
    return (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("Github_token")
        or os.getenv("github_token")
        or os.getenv("GITHUB_API_TOKEN")
        or ""
    ).strip()


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Radar-Agent-Watch/1.0",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_request(path: str) -> Any:
    req = request.Request(f"{GITHUB_API_BASE}{path}", headers=_github_headers(), method="GET")
    with request.urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _created_since_iso() -> str:
    created_since = datetime.now(timezone.utc) - timedelta(days=GITHUB_SEARCH_WINDOW_DAYS)
    return created_since.date().isoformat()


def _matched_keywords(*values: str) -> list[str]:
    haystack = " ".join(value.strip().lower() for value in values if value).strip()
    if not haystack:
        return []
    return [keyword for keyword in GITHUB_AGENT_KEYWORDS if keyword in haystack]


def _build_query(search_term: str) -> str:
    qualifiers = [
        search_term,
        "in:name,description,readme",
        "fork:false",
        "archived:false",
        f"created:>={_created_since_iso()}",
    ]
    if GITHUB_MIN_STARS > 0:
        qualifiers.append(f"stars:>={GITHUB_MIN_STARS}")
    return " ".join(qualifiers)


def _search_repositories(search_term: str) -> list[dict[str, Any]]:
    query = _build_query(search_term)
    encoded_query = parse.quote(query, safe="")
    path = (
        f"/search/repositories?q={encoded_query}"
        f"&sort=updated&order=desc&per_page={GITHUB_PER_QUERY_LIMIT}"
    )
    payload = _github_request(path)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _normalize_repo_signal(repo: dict[str, Any], matched_terms: list[str]) -> dict[str, Any] | None:
    full_name = str(repo.get("full_name") or "").strip()
    html_url = str(repo.get("html_url") or "").strip()
    description = str(repo.get("description") or "").strip()
    created_at = str(repo.get("created_at") or "").strip()
    updated_at = str(repo.get("updated_at") or "").strip()
    owner = repo.get("owner") or {}
    owner_login = str(owner.get("login") or "").strip() if isinstance(owner, dict) else ""
    stars = int(repo.get("stargazers_count") or 0)
    language = str(repo.get("language") or "").strip()
    license_payload = repo.get("license") if isinstance(repo.get("license"), dict) else {}
    license_spdx_id = str(license_payload.get("spdx_id") or "").strip()
    archived = bool(repo.get("archived", False))
    topics = repo.get("topics") if isinstance(repo.get("topics"), list) else []

    if not full_name or not html_url or not created_at:
        return None

    summary = description or "New GitHub repository detected in the AI agent ecosystem."
    now_iso = datetime.now(timezone.utc).isoformat()
    repo_topics = [str(topic).strip().lower() for topic in topics if str(topic).strip()]

    return {
        "title": full_name,
        "summary": summary,
        "content": summary,
        "url": html_url,
        "author": owner_login,
        "source": "github",
        "source_type": "github_agent",
        "category": "ai_agents",
        "topic": "ai_agents",
        "published_at": created_at,
        "timestamp": now_iso,
        "collected_at": now_iso,
        "source_weight": 0.95 if stars >= 1000 else 0.85 if stars >= 200 else 0.75,
        "summary_length": len(summary),
        "content_length": len(summary),
        "metadata": {
            "repo_name": full_name,
            "repo_url": html_url,
            "repo_stars": stars,
            "language": language,
            "license_spdx_id": license_spdx_id,
            "archived": archived,
            "created_at": created_at,
            "updated_at": updated_at,
            "canonical_scalars_resolved_at": now_iso,
            "tags": sorted(set(repo_topics + matched_terms)),
            "matched_keywords": matched_terms,
        },
    }


def collect_github_agent_signals() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    seen_repos: set[str] = set()

    for search_term in GITHUB_AGENT_SEARCH_QUERIES:
        print(f"[github_agent] searching GitHub for {search_term}")
        try:
            repositories = _search_repositories(search_term)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            print(f"[github_agent] search failed for {search_term}: {exc.code} {detail}")
            continue
        except Exception as exc:
            print(f"[github_agent] search failed for {search_term}: {exc}")
            continue

        print(f"[github_agent] {search_term} -> {len(repositories)} repositories")

        for repo in repositories:
            full_name = str(repo.get("full_name") or "").strip().lower()
            if not full_name or full_name in seen_repos:
                continue

            matched_terms = _matched_keywords(
                str(repo.get("name") or ""),
                str(repo.get("description") or ""),
                " ".join(str(topic) for topic in (repo.get("topics") or [])),
                search_term,
            )
            normalized = _normalize_repo_signal(repo, matched_terms)
            if not normalized:
                continue

            seen_repos.add(full_name)
            signals.append(normalized)

    return sorted(
        signals,
        key=lambda item: (
            -int(((item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}).get("repo_stars") or 0),
            str(item.get("published_at") or ""),
        ),
    )


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "github_agent_collector",
        "count": len(signals),
        "signals": signals,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"[github_agent] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    collected = collect_github_agent_signals()
    save(collected)
    print(f"[github_agent] done, total signals: {len(collected)}")
