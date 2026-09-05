"""Bounded same-publisher compatibility reads for two retired RSS endpoints.

Only public article metadata is collected; missing publication metadata or
failed reads keep source coverage incomplete. No feed or article timestamps
are synthesized from the collection time.
"""
from datetime import datetime, timezone
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from signal_collectors.collection_coverage import InvalidCollectionResponse, failure_reason_code

PUBLISHER_INDEXES = {
    "https://www.therundown.ai/rss": (
        "https://www.therundown.ai/articles", "main a[href]", r"/articles/[^/]+/?",
    ),
    "https://www.deeplearning.ai/the-batch/feed": (
        "https://www.deeplearning.ai/the-batch", "article a[href]", r"/the-batch/[^/]+/?",
    ),
}
PUBLISHER_ARTICLE_LIMIT = 10
PUBLISHER_HEADERS = {"User-Agent": "AI-Radar/1.0"}


def _read_page(url: str) -> BeautifulSoup:
    # Do not follow publisher-provided links or redirects onto another host.
    response = requests.get(url, headers=PUBLISHER_HEADERS, timeout=20, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise InvalidCollectionResponse("Publisher page did not return HTTP 200")
    return BeautifulSoup(response.content, "html.parser")


def _metadata(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return str(tag.get("content") or "").strip() if tag else ""


def collect_publisher_index(feed_url: str) -> tuple[list[dict], str | None]:
    index_url, selector, article_path = PUBLISHER_INDEXES[feed_url.rstrip("/")]
    index = _read_page(index_url)
    origin = urlparse(index_url)
    urls: list[str] = []
    for anchor in index.select(selector):
        parsed = urlparse(urljoin(index_url, anchor["href"]))
        if parsed.scheme != "https" or parsed.netloc != origin.netloc:
            continue
        if parsed.query or parsed.fragment or not re.fullmatch(article_path, parsed.path):
            continue
        url = parsed.geturl()
        if url not in urls:
            urls.append(url)
        if len(urls) == PUBLISHER_ARTICLE_LIMIT:
            break
    if not urls:
        raise InvalidCollectionResponse("Publisher index has no recognized article links")

    items: list[dict] = []
    failure: str | None = None
    for url in urls:
        try:
            page = _read_page(url)
            title = _metadata(page, "og:title")
            published = _metadata(page, "article:published_time")
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError as exc:
                raise InvalidCollectionResponse("Publisher article publication date is missing or invalid") from exc
            if not title or published_at.tzinfo is None or published_at > datetime.now(timezone.utc):
                raise InvalidCollectionResponse("Publisher article metadata is incomplete or future-dated")
            items.append({
                "title": title,
                "link": url,
                "published_at": published_at.isoformat(),
                "summary": _metadata(page, "description") or _metadata(page, "og:description"),
                "content_type": "publisher_html",
            })
        except Exception as exc:
            failure = failure or failure_reason_code(exc)
    return items, failure
