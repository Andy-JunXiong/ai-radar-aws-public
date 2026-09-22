import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import boto3
from dotenv import load_dotenv

from signal_collectors.collection_coverage import (
    CollectionCoverageTracker,
    InvalidCollectionResponse,
    failure_reason_code,
    with_collection_coverage,
)


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "official_signals.json"
SUBSCRIPTION_DIR = BASE_DIR / "backend" / "data" / "settings" / "subscriptions"
DEFAULT_SUBSCRIPTION_SCOPE = (
    os.getenv("AI_RADAR_SUBSCRIPTION_SCOPE")
    or "admin_default"
).strip() or "admin_default"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
SUBSCRIPTION_S3_PREFIX = (
    os.getenv("SUBSCRIPTION_SETTINGS_S3_PREFIX")
    or "settings/subscriptions"
).strip().strip("/")

# This can be moved to config or .env later.
RADAR_TIME_WINDOW_HOURS = 24

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

SOURCE_CONFIGS = [
    {
        "source": "openai",
        "source_type": "official",
        "author": "OpenAI",
        "category": "AI Model",
        "list_url": "https://openai.com/news/",
        "base_url": "https://openai.com",
        "allowed_prefixes": ["/index/"],
    },
    {
        "source": "anthropic",
        "source_type": "official",
        "author": "Anthropic",
        "category": "AI Model",
        "list_url": "https://www.anthropic.com/news",
        "base_url": "https://www.anthropic.com",
        "allowed_prefixes": ["/news/"],
    },
    {
        "source": "google_deepmind",
        "source_type": "official",
        "author": "Google DeepMind",
        "category": "AI Research",
        "list_url": "https://deepmind.google/discover/blog/",
        "base_url": "https://deepmind.google",
        "allowed_prefixes": ["/discover/blog/"],
    },
    {
        "source": "aws_ai",
        "source_type": "official",
        "author": "AWS",
        "category": "AI Product",
        "list_url": "https://aws.amazon.com/blogs/machine-learning/",
        "base_url": "https://aws.amazon.com",
        "allowed_prefixes": [
            "/blogs/machine-learning/",
            "/blogs/aws/category/artificial-intelligence/",
        ],
    },
    {
        "source": "meta_ai",
        "source_type": "official",
        "author": "Meta AI",
        "category": "AI Research",
        "list_url": "https://ai.meta.com/blog/",
        "base_url": "https://ai.meta.com",
        "allowed_prefixes": ["/blog/"],
    },
    {
        "source": "lmarena",
        "source_type": "official",
        "author": "LMArena",
        "category": "AI Evaluation",
        "list_url": "https://arena.ai/blog/",
        "base_url": "https://arena.ai",
        "allowed_prefixes": ["/blog/"],
        "excluded_prefixes": ["/blog/category/"],
    },
]


def _subscription_file_path() -> Path:
    return SUBSCRIPTION_DIR / f"{DEFAULT_SUBSCRIPTION_SCOPE}.json"


def _subscription_s3_key() -> str:
    return f"{SUBSCRIPTION_S3_PREFIX}/{DEFAULT_SUBSCRIPTION_SCOPE}.json"


def _load_subscription_payload_from_s3() -> dict | None:
    if not S3_BUCKET:
        return None

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        response = s3.get_object(Bucket=S3_BUCKET, Key=_subscription_s3_key())
        raw = response["Body"].read().decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            try:
                SUBSCRIPTION_DIR.mkdir(parents=True, exist_ok=True)
                _subscription_file_path().write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return payload
    except Exception:
        return None

    return None


def load_subscription_source_library() -> list[dict]:
    payload = _load_subscription_payload_from_s3()
    if payload is None:
        path = _subscription_file_path()
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return [item for item in sources if isinstance(item, dict) and item.get("enabled")]


def _match_subscription_source(config: Dict, source_item: dict) -> bool:
    configured_url = str(source_item.get("url") or "").strip().lower()
    configured_name = str(source_item.get("name") or "").strip().lower()
    source_type = str(source_item.get("type") or "").strip().lower()

    if source_type not in {"official_blog", "research", "newsletter", "custom_url", "rss"}:
        return False

    candidates = [
        str(config.get("source") or "").strip().lower(),
        str(config.get("author") or "").strip().lower(),
        str(config.get("list_url") or "").strip().lower(),
        str(config.get("base_url") or "").strip().lower(),
    ]

    if configured_name and any(configured_name in candidate for candidate in candidates):
        return True

    if configured_url:
        for candidate in candidates[2:]:
            if configured_url in candidate or candidate in configured_url:
                return True
        try:
            configured_host = configured_url.split("/")[2]
            for candidate in candidates[2:]:
                candidate_host = candidate.split("/")[2]
                if configured_host and candidate_host and configured_host == candidate_host:
                    return True
        except Exception:
            pass

    return False


def get_effective_source_configs() -> List[Dict]:
    active_sources = load_subscription_source_library()
    if not active_sources:
        return SOURCE_CONFIGS

    matched_configs = [
        config
        for config in SOURCE_CONFIGS
        if any(_match_subscription_source(config, source_item) for source_item in active_sources)
    ]

    if matched_configs:
        return matched_configs

    return SOURCE_CONFIGS


def fetch_html(
    url: str,
    timeout: int = 20,
    *,
    on_error=None,
) -> Optional[str]:
    try:
        headers = (
            {"User-Agent": "AI-Radar/1.0"}
            if urlparse(url).hostname == "ai.meta.com" else HEADERS
        )
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[fetch_html] failed for {url}: {e}")
        if on_error:
            on_error(e)
        return None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_datetime_safe(value: str) -> Optional[datetime]:
    if not value:
        return None

    value = clean_text(value)

    # Accept an ISO timestamp with a trailing Z.
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def is_within_time_window(published_at: str, window_hours: int) -> bool:
    dt = parse_datetime_safe(published_at)
    if not dt:
        return False

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=window_hours)
    return dt >= start_time


def extract_links_from_list_page(
    html: str,
    base_url: str,
    allowed_prefixes: List[str],
    limit: int = 10,
    excluded_prefixes: Optional[List[str]] = None,
) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    results: List[str] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(base_url, href)

        if not href:
            continue

        if href.startswith("http"):
            candidate_path_ok = any(prefix in href for prefix in allowed_prefixes)
        else:
            candidate_path_ok = any(href.startswith(prefix) for prefix in allowed_prefixes)

        if not candidate_path_ok:
            continue

        if excluded_prefixes and any(
            href.startswith(prefix) or prefix in full_url
            for prefix in excluded_prefixes
        ):
            continue

        if full_url in seen:
            continue

        seen.add(full_url)
        results.append(full_url)

        if len(results) >= limit:
            break

    return results


def extract_title(soup: BeautifulSoup) -> str:
    title = ""

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])

    if not title and soup.title:
        title = clean_text(soup.title.get_text())

    if not title:
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text())

    return title


def _extract_openai_article_links(html: str, limit: int) -> List[str]:
    # News categories live under /news/; article cards live under /index/.
    # Restrict discovery to the news content so global navigation is excluded.
    main = BeautifulSoup(html, "lxml").find("main")
    urls: List[str] = []
    if main is not None and limit > 0:
        for anchor in main.find_all("a", href=True):
            parsed = urlparse(urljoin("https://openai.com", anchor["href"].strip()))
            if (
                parsed.scheme != "https"
                or parsed.netloc != "openai.com"
                or parsed.query or parsed.fragment or parsed.params
                or not re.fullmatch(r"/index/[^/]+/?", parsed.path)
            ):
                continue
            url = parsed.geturl()
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
    if not urls:
        raise InvalidCollectionResponse("OpenAI news index has no recognized article links")
    return urls


def extract_description(soup: BeautifulSoup) -> str:
    description = ""

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = clean_text(meta_desc["content"])

    if not description:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            description = clean_text(og_desc["content"])

    return description


def extract_published_at(soup: BeautifulSoup) -> str:
    for attr_name in ["article:published_time", "og:published_time"]:
        tag = soup.find("meta", attrs={"property": attr_name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])

    time_tag = soup.find("time")
    if time_tag:
        return clean_text(time_tag.get("datetime") or time_tag.get_text())

    return ""


def _extract_openai_published_at(soup: BeautifulSoup) -> str:
    # Related-story cards also contain <time>; they are not this article's date.
    for property_name in ("article:published_time", "og:published_time"):
        tag = soup.find("meta", attrs={"property": property_name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    heading = soup.find("h1")
    header = heading.find_parent(attrs={"data-section-header": "true"}) if heading else None
    if header is None:
        return ""
    time_tag = header.find("time")
    if time_tag and time_tag.get("datetime"):
        return clean_text(time_tag["datetime"])
    for label in header.find_all("p"):
        try:
            return datetime.strptime(clean_text(label.get_text()), "%B %d, %Y").replace(
                tzinfo=timezone.utc
            ).isoformat()
        except ValueError:
            continue
    return ""


def extract_body_text(soup: BeautifulSoup, max_paragraphs: int = 5) -> str:
    paragraphs: List[str] = []

    for p in soup.find_all("p"):
        text = clean_text(p.get_text())
        if len(text) >= 60:
            paragraphs.append(text)
        if len(paragraphs) >= max_paragraphs:
            break

    return " ".join(paragraphs)


def parse_article_page(
    url: str,
    fallback_source: str,
    fallback_author: str,
    fallback_category: str,
    *,
    on_fetch_error=None,
) -> Optional[Dict]:
    html = fetch_html(url, on_error=on_fetch_error)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    title = extract_title(soup)
    description = extract_description(soup)
    published_at = (
        _extract_openai_published_at(soup)
        if urlparse(url).hostname == "openai.com" else extract_published_at(soup)
    )
    if not published_at and urlparse(url).hostname == "ai.meta.com":
        # Meta's public article header supplies a date instead of metadata.
        date_label = soup.select_one("span._amum")
        if date_label:
            try:
                published_at = datetime.strptime(
                    date_label.get_text(strip=True), "%B %d, %Y"
                ).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
    body_text = extract_body_text(soup, max_paragraphs=5)

    summary = description or body_text[:280]
    source_excerpt = body_text[:1200] if body_text else ""
    content = source_excerpt if source_excerpt else description

    published_dt = parse_datetime_safe(published_at)
    if urlparse(url).hostname in {"ai.meta.com", "openai.com"} and (
        not title or not summary or not published_dt
        or published_dt > datetime.now(timezone.utc)
    ):
        if on_fetch_error is not None:
            on_fetch_error(InvalidCollectionResponse("Official article metadata is incomplete or invalid"))
        return None

    if not title or not summary:
        return None

    if not published_dt:
        # Drop items without a parseable publish time so stale items do not mix in.
        print(f"[official] skip no/invalid published_at: {url}")
        return None

    now = datetime.now(timezone.utc).isoformat()

    return {
        "title": title,
        "summary": summary,
        "content": content,
        "source_excerpt": source_excerpt,
        "url": url,
        "author": fallback_author,
        "source": fallback_source,
        "source_type": "official",
        "category": fallback_category,
        "published_at": published_dt.isoformat(),
        "timestamp": now,
        "collected_at": now,
        "summary_length": len(summary),
        "content_length": len(content),
        "source_excerpt_length": len(source_excerpt),
    }


def collect_from_source(
    config: Dict,
    per_source_limit: int = 10,
    *,
    on_fetch_error=None,
) -> List[Dict]:
    list_html = fetch_html(config["list_url"], on_error=on_fetch_error)
    if not list_html:
        return []

    if config.get("source") == "openai" and config["list_url"] == "https://openai.com/news/":
        article_urls = _extract_openai_article_links(list_html, per_source_limit)
    else:
        article_urls = extract_links_from_list_page(
            html=list_html,
            base_url=config["base_url"],
            allowed_prefixes=config["allowed_prefixes"],
            limit=per_source_limit,
            excluded_prefixes=config.get("excluded_prefixes"),
        )
    if not article_urls and urlparse(config["list_url"]).hostname == "ai.meta.com":
        raise InvalidCollectionResponse("Meta index has no recognized article links")

    results: List[Dict] = []
    seen_titles = set()

    for url in article_urls:
        article = parse_article_page(
            url=url,
            fallback_source=config["source"],
            fallback_author=config["author"],
            fallback_category=config["category"],
            on_fetch_error=on_fetch_error,
        )
        if not article:
            continue

        if not is_within_time_window(
            article.get("published_at", ""),
            RADAR_TIME_WINDOW_HOURS,
        ):
            print(
                f"[official] skip old article: {article.get('title', '')} "
                f"({article.get('published_at', '')})"
            )
            continue

        title_key = clean_text(article["title"]).lower()
        if title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        article["source_type"] = config["source_type"]
        results.append(article)

    return results


def collect_official_signals() -> List[Dict]:
    all_signals: List[Dict] = []
    effective_configs = get_effective_source_configs()
    coverage = CollectionCoverageTracker(
        unit_type="source",
        expected_count=len(effective_configs),
        unit_prefix="official_source",
    )

    print(f"[official] effective source config count: {len(effective_configs)}")

    for source_index, config in enumerate(effective_configs):
        coverage.attempt(source_index)
        print(f"[official] collecting from {config['source']} ...")
        source_failure_reason: str | None = None

        def record_fetch_failure(exc: BaseException) -> None:
            nonlocal source_failure_reason
            source_failure_reason = failure_reason_code(exc)

        try:
            source_signals = collect_from_source(
                config,
                per_source_limit=10,
                on_fetch_error=record_fetch_failure,
            )
        except Exception as exc:
            print(f"[official] collection failed for {config['source']}: {exc}")
            coverage.fail(source_index, reason_code=failure_reason_code(exc))
            continue
        print(f"[official] {config['source']} -> {len(source_signals)} fresh signals")
        all_signals.extend(source_signals)
        if source_failure_reason:
            coverage.fail(source_index, reason_code=source_failure_reason)
        else:
            coverage.succeed(source_index, item_count=len(source_signals))

    deduped: List[Dict] = []
    seen_urls = set()

    for item in all_signals:
        url = item.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)

    return with_collection_coverage(deduped, coverage)


def save(signals: List[Dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "official_collector",
        "count": len(signals),
        "signals": signals,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[official] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    data = collect_official_signals()
    save(data)
