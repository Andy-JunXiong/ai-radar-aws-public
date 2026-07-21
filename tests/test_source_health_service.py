import sys
from pathlib import Path
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.source_health_service import check_subscription_source_health


def test_source_health_marks_valid_feed_ok():
    result = check_subscription_source_health(
        [
            {
                "id": "feed",
                "name": "Valid Feed",
                "url": "https://example.com/feed.xml",
                "type": "rss",
                "enabled": True,
            }
        ],
        fetcher=lambda _: (
            200,
            "application/rss+xml",
            b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title><item><title>A</title></item></channel></rss>""",
        ),
    )

    assert result["summary"]["ok"] == 1
    assert result["summary"]["checked_count"] == 1
    assert result["items"][0]["health_status"] == "ok"
    assert result["items"][0]["entry_count"] == 1


def test_source_health_warns_on_html_feed_url():
    result = check_subscription_source_health(
        [
            {
                "id": "html",
                "name": "HTML Page",
                "url": "https://example.com/feed",
                "type": "rss",
                "enabled": True,
            }
        ],
        fetcher=lambda _: (200, "text/html", b"<html><title>Not a feed</title></html>"),
    )

    assert result["summary"]["error"] == 1
    assert result["items"][0]["reason_code"] == "html_not_feed"
    assert result["items"][0]["entry_count"] == 0


def test_source_health_reports_http_errors():
    def failing_fetcher(url):
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    result = check_subscription_source_health(
        [
            {
                "id": "missing",
                "name": "Missing Feed",
                "url": "https://example.com/missing.xml",
                "type": "rss",
                "enabled": True,
            }
        ],
        fetcher=failing_fetcher,
    )

    assert result["summary"]["error"] == 1
    assert result["items"][0]["reason_code"] == "http_404"
    assert result["items"][0]["http_status"] == 404


def test_source_health_reports_non_success_fetch_results():
    result = check_subscription_source_health(
        [
            {
                "id": "missing",
                "name": "Missing Feed",
                "url": "https://example.com/missing.xml",
                "type": "rss",
                "enabled": True,
            }
        ],
        fetcher=lambda _: (404, "text/html", b"<html>Not found</html>"),
    )

    assert result["summary"]["error"] == 1
    assert result["items"][0]["reason_code"] == "http_404"
    assert result["items"][0]["entry_count"] == 0


def test_source_health_skips_non_feed_custom_urls_without_blocking():
    result = check_subscription_source_health(
        [
            {
                "id": "custom",
                "name": "Custom Page",
                "url": "https://example.com/",
                "type": "custom_url",
                "enabled": True,
            },
            {
                "id": "disabled",
                "name": "Disabled Feed",
                "url": "https://example.com/feed.xml",
                "type": "rss",
                "enabled": False,
            },
        ],
        fetcher=lambda _: (_ for _ in ()).throw(AssertionError("fetcher should not be called")),
    )

    assert result["summary"]["skipped"] == 2
    assert result["summary"]["checked_count"] == 0
    assert {item["reason_code"] for item in result["items"]} == {"not_feed_like", "disabled_source"}
