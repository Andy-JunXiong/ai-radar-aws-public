from __future__ import annotations

from collections import Counter
from typing import Any, Callable
from urllib.error import HTTPError, URLError

import feedparser
import requests
from requests import RequestException


FetchResult = tuple[int | None, str, bytes]
Fetcher = Callable[[str], FetchResult]

FEED_SOURCE_TYPES = {"rss"}
FEED_URL_HINTS = ("rss", "feed", ".xml", "atom")
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36 AI-Radar-Source-Health/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _looks_like_feed_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in FEED_URL_HINTS)


def _default_fetcher(url: str) -> FetchResult:
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=12,
        allow_redirects=True,
    )
    return response.status_code, response.headers.get("content-type", ""), response.content[:2_000_000]


def _result(
    source: dict[str, Any],
    *,
    status: str,
    severity: str,
    reason_code: str,
    message: str,
    checked_as: str,
    http_status: int | None = None,
    content_type: str = "",
    entry_count: int | None = None,
) -> dict[str, Any]:
    return {
        "source_id": _safe_text(source.get("id")),
        "name": _safe_text(source.get("name")) or "Untitled source",
        "url": _safe_text(source.get("url")),
        "source_type": _safe_text(source.get("type")) or "custom_url",
        "enabled": bool(source.get("enabled", True)),
        "health_status": status,
        "severity": severity,
        "reason_code": reason_code,
        "message": message,
        "checked_as": checked_as,
        "http_status": http_status,
        "content_type": content_type,
        "entry_count": entry_count,
    }


def check_subscription_source_health(
    sources: list[dict[str, Any]] | None,
    *,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    checker = fetcher or _default_fetcher
    items: list[dict[str, Any]] = []

    for raw_source in sources or []:
        if not isinstance(raw_source, dict):
            continue

        url = _safe_text(raw_source.get("url"))
        source_type = _safe_text(raw_source.get("type")).lower()
        enabled = bool(raw_source.get("enabled", True))

        if not enabled:
            items.append(
                _result(
                    raw_source,
                    status="skipped",
                    severity="info",
                    reason_code="disabled_source",
                    message="Source is disabled, so it will not be checked or collected.",
                    checked_as="disabled",
                )
            )
            continue

        if not url:
            items.append(
                _result(
                    raw_source,
                    status="warning",
                    severity="warning",
                    reason_code="missing_url",
                    message="Source has no URL.",
                    checked_as="missing_url",
                )
            )
            continue

        should_check_feed = source_type in FEED_SOURCE_TYPES or _looks_like_feed_url(url)
        if not should_check_feed:
            items.append(
                _result(
                    raw_source,
                    status="skipped",
                    severity="info",
                    reason_code="not_feed_like",
                    message="Custom or newsletter URL kept as an advisory source; RSS health check was skipped.",
                    checked_as="non_feed",
                )
            )
            continue

        try:
            http_status, content_type, body = checker(url)
        except HTTPError as exc:
            items.append(
                _result(
                    raw_source,
                    status="error",
                    severity="error",
                    reason_code=f"http_{exc.code}",
                    message=f"Feed request returned HTTP {exc.code}.",
                    checked_as="feed",
                    http_status=exc.code,
                    content_type=exc.headers.get("content-type", "") if exc.headers else "",
                    entry_count=0,
                )
            )
            continue
        except (TimeoutError, URLError, RequestException, OSError) as exc:
            items.append(
                _result(
                    raw_source,
                    status="error",
                    severity="error",
                    reason_code=type(exc).__name__,
                    message="Feed request failed before it could be parsed.",
                    checked_as="feed",
                    entry_count=0,
                )
            )
            continue

        if http_status is not None and http_status >= 400:
            items.append(
                _result(
                    raw_source,
                    status="error",
                    severity="error",
                    reason_code=f"http_{http_status}",
                    message=f"Feed request returned HTTP {http_status}.",
                    checked_as="feed",
                    http_status=http_status,
                    content_type=content_type,
                    entry_count=0,
                )
            )
            continue

        parsed = feedparser.parse(body)
        entry_count = len(parsed.entries or [])
        is_html = "html" in content_type.lower()

        if entry_count > 0:
            items.append(
                _result(
                    raw_source,
                    status="ok",
                    severity="ok",
                    reason_code="feed_entries_found",
                    message=f"Feed parsed successfully with {entry_count} entries.",
                    checked_as="feed",
                    http_status=http_status,
                    content_type=content_type,
                    entry_count=entry_count,
                )
            )
            continue

        reason_code = "html_not_feed" if is_html else "no_feed_entries"
        message = (
            "URL returned HTML and did not parse as a feed."
            if is_html
            else "Feed parsed but did not expose entries."
        )
        items.append(
            _result(
                raw_source,
                status="error" if is_html else "warning",
                severity="error" if is_html else "warning",
                reason_code=reason_code,
                message=message,
                checked_as="feed",
                http_status=http_status,
                content_type=content_type,
                entry_count=entry_count,
            )
        )

    status_counts = Counter(item["health_status"] for item in items)
    severity_counts = Counter(item["severity"] for item in items)
    checked_count = sum(1 for item in items if item.get("checked_as") == "feed")

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "checked_count": checked_count,
            "ok": status_counts.get("ok", 0),
            "warning": status_counts.get("warning", 0),
            "error": status_counts.get("error", 0),
            "skipped": status_counts.get("skipped", 0),
            "severity_counts": dict(severity_counts),
        },
    }
