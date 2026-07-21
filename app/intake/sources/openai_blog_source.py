import feedparser
from bs4 import BeautifulSoup

from intake.schemas import Signal

OPENAI_BLOG_RSS = "https://openai.com/news/rss.xml"


def html_to_text(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def collect_openai_blog_signals(limit: int = 5) -> list[Signal]:
    feed = feedparser.parse(OPENAI_BLOG_RSS)

    signals: list[Signal] = []

    for idx, entry in enumerate(feed.entries[:limit], start=1):
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        published_at = getattr(entry, "published", "").strip()

        raw_summary = getattr(entry, "summary", "")
        summary_text = html_to_text(raw_summary)

        signal = Signal(
            id=f"openai_blog_{idx}",
            title=title,
            url=url,
            source="OpenAI Blog",
            source_type="blog",
            published_at=published_at,
            raw_text=summary_text,
            summary=summary_text,
        )
        signals.append(signal)

    return signals