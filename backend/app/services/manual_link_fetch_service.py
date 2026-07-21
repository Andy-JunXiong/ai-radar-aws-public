from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import re


MAX_ARTICLE_BYTES = 1_000_000
MIN_ARTICLE_TEXT_CHARS = 400
DEFAULT_TIMEOUT_SECONDS = 8


@dataclass
class ArticleFetchResult:
    status: str
    source_url: str
    resolved_url: str = ""
    title: str = ""
    description: str = ""
    text: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_url": self.source_url,
            "resolved_url": self.resolved_url,
            "title": self.title,
            "description": self.description,
            "text": self.text,
            "error": self.error,
            "char_count": len(self.text),
            "word_count": len(self.text.split()) if self.text else 0,
        }


class ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.article_parts: list[str] = []
        self.meta_description = ""
        self.tag_stack: list[str] = []
        self.skip_depth = 0
        self.in_title = False
        self.in_article = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.tag_stack.append(tag)

        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "form", "button"}:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "article":
            self.in_article = True
        if tag == "meta":
            attr_map = {name.lower(): value or "" for name, value in attrs}
            if attr_map.get("name", "").lower() == "description" and attr_map.get("content"):
                self.meta_description = attr_map["content"].strip()

        if tag in {"p", "br", "li", "div", "section", "article", "h1", "h2", "h3"}:
            self._append_text("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"p", "li", "div", "section", "article", "h1", "h2", "h3"}:
            self._append_text("\n")
        if tag == "title":
            self.in_title = False
        if tag == "article":
            self.in_article = False
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "form", "button"}:
            self.skip_depth = max(0, self.skip_depth - 1)
        if self.tag_stack:
            self.tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
            return
        if self.skip_depth > 0:
            return
        self._append_text(text)

    def _append_text(self, text: str) -> None:
        self.body_parts.append(text)
        if self.in_article:
            self.article_parts.append(text)


def normalize_readable_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_readable_article(html: str) -> dict[str, str]:
    parser = ReadableTextParser()
    parser.feed(html)
    parser.close()

    article_text = normalize_readable_text(" ".join(parser.article_parts))
    body_text = normalize_readable_text(" ".join(parser.body_parts))
    text = article_text if len(article_text) >= MIN_ARTICLE_TEXT_CHARS else body_text

    return {
        "title": normalize_readable_text(" ".join(parser.title_parts)),
        "description": normalize_readable_text(parser.meta_description),
        "text": text,
    }


def _decode_response_body(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([\w.-]+)", content_type or "", flags=re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return raw.decode(charset, errors="ignore")
    except LookupError:
        return raw.decode("utf-8", errors="ignore")


def fetch_public_article(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    source_url = str(url or "").strip()
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ArticleFetchResult(
            status="failed",
            source_url=source_url,
            error="invalid_http_url",
        ).to_dict()

    request = Request(
        source_url,
        headers={
            "User-Agent": "AI-Radar-Manual-Link-Fetch/1.0 (+https://ai-radar.local)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            resolved_url = response.geturl()
            if "html" not in content_type.lower():
                return ArticleFetchResult(
                    status="failed",
                    source_url=source_url,
                    resolved_url=resolved_url,
                    error="non_html_content",
                ).to_dict()
            raw = response.read(MAX_ARTICLE_BYTES)
    except HTTPError as error:
        return ArticleFetchResult(
            status="failed",
            source_url=source_url,
            error=f"http_error_{error.code}",
        ).to_dict()
    except URLError as error:
        return ArticleFetchResult(
            status="failed",
            source_url=source_url,
            error=f"url_error: {error.reason}",
        ).to_dict()
    except Exception as error:
        return ArticleFetchResult(
            status="failed",
            source_url=source_url,
            error=f"fetch_error: {error}",
        ).to_dict()

    article = extract_readable_article(_decode_response_body(raw, content_type))
    text = article["text"]
    if len(text) < MIN_ARTICLE_TEXT_CHARS:
        return ArticleFetchResult(
            status="failed",
            source_url=source_url,
            resolved_url=resolved_url,
            title=article["title"],
            description=article["description"],
            text=text,
            error="no_readable_article_text",
        ).to_dict()

    return ArticleFetchResult(
        status="fetched",
        source_url=source_url,
        resolved_url=resolved_url,
        title=article["title"],
        description=article["description"],
        text=text,
    ).to_dict()
