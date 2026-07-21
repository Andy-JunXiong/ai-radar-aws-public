import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "github_friction_signals.json"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_SEARCH_WINDOW_DAYS = int(os.getenv("AI_FRICTION_GITHUB_SEARCH_WINDOW_DAYS", "30"))
GITHUB_PER_QUERY_LIMIT = max(1, min(int(os.getenv("AI_FRICTION_GITHUB_PER_QUERY_LIMIT", "10")), 25))

GITHUB_FRICTION_SEARCH_QUERIES = [
    '"ai agent" bug',
    '"ai coding agent" issue',
    '"copilot" bug',
    '"cursor" issue',
    '"llm" "not working"',
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
        "User-Agent": "AI-Radar-Friction/1.0",
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


def _build_query(search_term: str) -> str:
    qualifiers = [
        search_term,
        "is:issue",
        f"created:>={_created_since_iso()}",
        "comments:>=2",
    ]
    return " ".join(qualifiers)


def _search_issues(search_term: str) -> list[dict[str, Any]]:
    query = _build_query(search_term)
    encoded_query = parse.quote(query, safe="")
    path = (
        f"/search/issues?q={encoded_query}"
        f"&sort=comments&order=desc&per_page={GITHUB_PER_QUERY_LIMIT}"
    )
    payload = _github_request(path)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _normalize_issue(issue: dict[str, Any], search_term: str) -> dict[str, Any] | None:
    title = str(issue.get("title") or "").strip()
    html_url = str(issue.get("html_url") or "").strip()
    body = str(issue.get("body") or "").strip()
    created_at = str(issue.get("created_at") or "").strip()
    updated_at = str(issue.get("updated_at") or "").strip()
    comments = int(issue.get("comments") or 0)
    state = str(issue.get("state") or "").strip()
    repository_url = str(issue.get("repository_url") or "").strip()
    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    author = str(user.get("login") or "").strip()

    if not title or not html_url or not created_at:
        return None

    repo_name = repository_url.split("/repos/")[-1] if "/repos/" in repository_url else ""
    summary = (
        f"GitHub issue discussion detected around AI tooling friction. "
        f"State: {state or 'unknown'}, comments: {comments}."
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "title": title,
        "summary": summary,
        "content": body[:1200] if body else summary,
        "url": html_url,
        "author": author,
        "source": "github",
        "source_type": "github_friction",
        "category": "AI Friction",
        "topic": "ai_friction",
        "signal_type": "friction",
        "published_at": created_at,
        "timestamp": now_iso,
        "collected_at": now_iso,
        "source_weight": 0.82 if comments >= 20 else 0.74 if comments >= 8 else 0.66,
        "summary_length": len(summary),
        "content_length": len(body[:1200] if body else summary),
        "metadata": {
            "repo_name": repo_name,
            "comments": comments,
            "state": state,
            "updated_at": updated_at,
            "search_term": search_term,
        },
    }


def collect_github_friction_signals() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for search_term in GITHUB_FRICTION_SEARCH_QUERIES:
        print(f"[github_friction] searching GitHub issues for {search_term}")
        try:
            issues = _search_issues(search_term)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            print(f"[github_friction] search failed for {search_term}: {exc.code} {detail}")
            continue
        except Exception as exc:
            print(f"[github_friction] search failed for {search_term}: {exc}")
            continue

        for issue in issues:
            normalized = _normalize_issue(issue, search_term)
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
            -int(((item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}).get("comments") or 0),
            str(item.get("published_at") or ""),
        ),
    )


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "github_friction_collector",
        "count": len(signals),
        "signals": signals,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[github_friction] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    collected = collect_github_friction_signals()
    save(collected)
    print(f"[github_friction] done, total signals: {len(collected)}")
