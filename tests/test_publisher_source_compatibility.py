"""Regression coverage for the September 2026 publisher-source failures."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
from pathlib import Path
import sys

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from signal_collectors import publisher_index, rss_collector, official_collector, producthunt_agent_collector
from signal_collectors.collection_coverage import InvalidCollectionResponse


def article_html(date=None):
    date = date if date is not None else (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return f'<meta property="og:title" content="Publisher update"><meta property="article:published_time" content="{date}"><meta name="description" content="Publisher-provided summary">'


def response(html, status=200):
    def check():
        if status >= 400:
            raise requests.HTTPError(f"HTTP {status}")
    return SimpleNamespace(content=html.encode(), text=html, status_code=status, raise_for_status=check)


@pytest.mark.parametrize(("feed", "index", "card"), [
    ("https://www.therundown.ai/rss", "https://www.therundown.ai/articles", '<main><a href="/articles/update">Article</a><a href="/articles/update">Duplicate</a><a href="https://other.example/articles/update">Outside</a></main>'),
    ("https://www.deeplearning.ai/the-batch/feed", "https://www.deeplearning.ai/the-batch", '<article><a href="/the-batch/tag/news">Tag</a><a href="/the-batch/update">Article</a></article>'),
])
def test_publisher_reads_are_bounded_same_host_and_preserve_metadata(feed, index, card):
    with patch.object(publisher_index.requests, "get", side_effect=[response(card), response(article_html())]) as get:
        items, failure = publisher_index.collect_publisher_index(feed)
    assert failure is None
    assert len(items) == 1
    assert items[0]["summary"] == "Publisher-provided summary"
    assert items[0]["content_type"] == "publisher_html"
    assert get.call_count == 2
    assert get.call_args_list[0].args[0] == index
    assert all(call.kwargs["allow_redirects"] is False for call in get.call_args_list)


@pytest.mark.parametrize("date", ["", "invalid", "2026-09-01", "2099-01-01T00:00:00Z"])
def test_missing_ambiguous_or_future_publication_date_fails_coverage(date):
    with patch.object(publisher_index.requests, "get", side_effect=[
        response('<main><a href="/articles/update">Article</a></main>'), response(article_html(date)),
    ]):
        items, failure = publisher_index.collect_publisher_index("https://www.therundown.ai/rss")
    assert items == []
    assert failure == "invalid_response"


def test_unrecognized_index_is_not_a_successful_empty_collection():
    with patch.object(publisher_index.requests, "get", return_value=response('<main>Unexpected layout</main>')):
        with pytest.raises(InvalidCollectionResponse):
            publisher_index.collect_publisher_index("https://www.therundown.ai/rss")


def test_article_failure_keeps_good_items_and_failed_source_status():
    with patch.object(publisher_index.requests, "get", side_effect=[
        response('<main><a href="/articles/one">One</a><a href="/articles/two">Two</a></main>'),
        response(article_html()), response('', 503),
    ]):
        items, failure = publisher_index.collect_publisher_index("https://www.therundown.ai/rss")
    assert len(items) == 1
    assert failure == "http_error"


def test_publisher_read_limit_and_no_redirect_following():
    links=''.join(f'<a href="/articles/item-{i}">Article</a>' for i in range(30))
    with patch.object(publisher_index.requests, "get", side_effect=[response(f'<main>{links}</main>')] + [response(article_html())] * 10) as get:
        items, failure = publisher_index.collect_publisher_index("https://www.therundown.ai/rss")
    assert len(items) == 10 and failure is None and get.call_count == 11
    with patch.object(publisher_index.requests, "get", return_value=response('',302)):
        with pytest.raises(InvalidCollectionResponse):
            publisher_index.collect_publisher_index("https://www.therundown.ai/rss")


def test_retired_feed_fallback_preserves_original_source_unit():
    item={"title":"Update", "link":"https://www.therundown.ai/articles/update", "published_at":datetime.now(timezone.utc).isoformat(), "summary":"Summary", "content_type":"publisher_html"}
    with patch.object(rss_collector, "get_effective_rss_sources", return_value={"the_rundown":"https://www.therundown.ai/rss"}), patch.object(rss_collector.feedparser,"parse",return_value=SimpleNamespace(entries=[],status=404)), patch.object(rss_collector,"collect_publisher_index",return_value=([item],None)):
        items=rss_collector.collect_rss_signals()
    assert len(items)==1 and items[0]["source"]=="the_rundown"
    assert items.coverage["expected_unit_ids"]==["rss_source_001"]
    assert items.coverage["complete"] is True


def test_fallback_does_not_hide_partial_failure_or_intercept_unrelated_feeds():
    with patch.object(rss_collector,"get_effective_rss_sources",return_value={"the_rundown":"https://www.therundown.ai/rss","custom":"https://example.org/rss"}), patch.object(rss_collector.feedparser,"parse",return_value=SimpleNamespace(entries=[],status=404)), patch.object(rss_collector,"collect_publisher_index",return_value=([],"http_error")) as fallback:
        items=rss_collector.collect_rss_signals()
    assert items.coverage["complete"] is False
    assert len(items.coverage["failed_units"])==2
    assert fallback.call_count==1


def test_meta_uses_honest_headers_without_changing_other_sources():
    with patch.object(official_collector.requests,"get",return_value=response('ok')) as get:
        official_collector.fetch_html("https://ai.meta.com/blog/update/")
        assert get.call_args.kwargs["headers"]["User-Agent"].startswith("AI-Radar/")
        official_collector.fetch_html("https://www.anthropic.com/news")
        assert get.call_args.kwargs["headers"]==official_collector.HEADERS


def test_meta_uses_published_header_date_without_collection_time_substitution():
    html='<title>Meta update</title><meta name="description" content="Publisher description"><h1>Meta update</h1><span class="_amum">July 9, 2026</span>'
    with patch.object(official_collector,"fetch_html",return_value=html):
        item=official_collector.parse_article_page("https://ai.meta.com/blog/update/","meta_ai","Meta AI","AI Research")
    assert item["published_at"]=="2026-07-09T00:00:00+00:00"


def test_missing_producthunt_token_is_explicit_and_still_failed():
    with patch.object(producthunt_agent_collector,"_product_hunt_token",return_value=""), patch.object(producthunt_agent_collector.request,"urlopen") as request:
        items=producthunt_agent_collector.collect_producthunt_agent_signals()
    assert items.coverage["failed_units"]==[{"unit_id":"producthunt_request_001","reason_code":"not_configured"}]
    assert items.coverage["complete"] is False
    request.assert_not_called()


@pytest.mark.parametrize("date", ["", "invalid", "January 1, 2099"])
def test_meta_invalid_date_records_failure_instead_of_successful_zero(date):
    html = f'<title>Meta update</title><meta name="description" content="Description"><span class="_amum">{date}</span>'
    failures = []
    with patch.object(official_collector, "fetch_html", return_value=html):
        item = official_collector.parse_article_page(
            "https://ai.meta.com/blog/update/", "meta_ai", "Meta AI", "AI Research",
            on_fetch_error=failures.append,
        )
    assert item is None
    assert len(failures) == 1 and isinstance(failures[0], InvalidCollectionResponse)


def test_meta_unrecognized_index_is_not_a_successful_empty_collection():
    config = next(c for c in official_collector.SOURCE_CONFIGS if c["source"] == "meta_ai")
    with patch.object(official_collector, "fetch_html", return_value='<main>Unexpected layout</main>'):
        with pytest.raises(InvalidCollectionResponse):
            official_collector.collect_from_source(config)


def test_producthunt_http_error_does_not_log_response_body(capsys):
    with patch.object(producthunt_agent_collector,"_product_hunt_request",side_effect=HTTPError("https://api.producthunt.com",401,"unauthorized",{},BytesIO(b'private upstream payload'))):
        items=producthunt_agent_collector.collect_producthunt_agent_signals()
    assert items.coverage["failed_units"][0]["reason_code"]=="http_error"
    assert 'private upstream payload' not in capsys.readouterr().out
