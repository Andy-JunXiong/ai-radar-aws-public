"""Official RSS discovers articles without replacing original source evidence."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_collectors import official_collector as collector


CONFIG = next(item for item in collector.SOURCE_CONFIGS if item["source"] == "openai")
FEED_URL = "https://openai.com/news/rss.xml"
BODY = "Original article body is long enough to supply an actual source excerpt from the publisher."


def feed(*links):
    return '<rss version="2.0"><channel><title>OpenAI News</title>' + ''.join(
        f'<item><title>Feed title</title><link>{escape(link)}</link>'
        '<description>Feed description is not article evidence.</description>'
        '<pubDate>Fri, 01 Jan 1999 00:00:00 GMT</pubDate></item>'
        for link in links
    ) + '</channel></rss>'


def article():
    published = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return (
        '<title>Original article</title><meta name="description" content="Article summary">'
        f'<meta property="article:published_time" content="{published}">'
        f'<article><p>{BODY}</p></article>'
    )


def test_rss_selects_only_bounded_unique_same_origin_article_links():
    xml = feed(
        'https://elsewhere.example/index/outside/', 'http://openai.com/index/insecure/',
        'https://openai.com/news/research/', 'https://openai.com/index/',
        'https://openai.com/index/nested/path/', 'https://openai.com/index/one/?track=1',
        'https://openai.com/index/one/#part', 'https://openai.com:444/index/one/',
        'https://user@openai.com/index/one/', '/index/relative/',
        'https://[invalid/index/bad/',
        'https://openai.com/index/../', 'https://openai.com/index/%2e%2e/',
        'https://openai.com/index/one', 'https://openai.com/index/one/',
        'https://openai.com/index/two/', 'https://openai.com/index/over-bound/',
    )
    assert collector._extract_openai_rss_article_links(xml, 2) == [
        'https://openai.com/index/one/', 'https://openai.com/index/two/',
    ]


def test_default_discovery_fetches_rss_then_original_articles():
    assert CONFIG['list_url'] == FEED_URL
    with patch.object(collector, 'fetch_html', side_effect=[
        feed('https://openai.com/index/one/'), article(),
    ]) as fetch:
        items = collector.collect_from_source(CONFIG)
    assert [call.args[0] for call in fetch.call_args_list] == [
        FEED_URL, 'https://openai.com/index/one/',
    ]
    assert len(items) == 1
    assert items[0]['title'] == 'Original article'
    assert items[0]['source_excerpt'] == BODY
    assert items[0]['content'] == items[0]['source_excerpt']
    assert items[0]['source'] == 'openai'
    assert items[0]['source_type'] == 'official'
    assert collector.is_within_time_window(items[0]['published_at'], 24)


@pytest.mark.parametrize('xml', [
    '', '<rss><channel>', '<html><main>Challenge page</main></html>',
    '<rss/>', '<rss><channel/></rss>',
    feed('https://elsewhere.example/index/outside/'),
    '<!DOCTYPE rss [<!ENTITY x "unexpected">]><rss><channel/></rss>',
])
def test_invalid_feed_keeps_source_coverage_failed(xml):
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(
        collector, 'fetch_html', return_value=xml
    ) as fetch:
        items = collector.collect_official_signals()
    assert items == []
    assert fetch.call_count == 1
    assert items.coverage['complete'] is False
    assert items.coverage['failed_units'] == [
        {'unit_id': 'official_source_001', 'reason_code': 'invalid_response'},
    ]


@pytest.mark.parametrize('fail_feed', [True, False])
def test_http_failure_is_not_hidden_by_feed_content(fail_feed):
    def fetch(url, **kwargs):
        if fail_feed or url != FEED_URL:
            kwargs['on_error'](requests.HTTPError('HTTP 403'))
            return None
        return feed('https://openai.com/index/one/')

    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(
        collector, 'fetch_html', side_effect=fetch
    ) as reads:
        items = collector.collect_official_signals()
    assert items == []
    assert reads.call_count == (1 if fail_feed else 2)
    assert items.coverage['complete'] is False
    assert items.coverage['failed_units'] == [
        {'unit_id': 'official_source_001', 'reason_code': 'http_error'},
    ]


def test_partial_article_success_keeps_failed_coverage():
    def fetch(url, **kwargs):
        if url == FEED_URL:
            return feed('https://openai.com/index/one/', 'https://openai.com/index/two/')
        if url.endswith('/one/'):
            return article()
        kwargs['on_error'](requests.HTTPError('HTTP 503'))
        return None

    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(
        collector, 'fetch_html', side_effect=fetch
    ):
        items = collector.collect_official_signals()
    assert len(items) == 1
    assert items.coverage['complete'] is False
    assert items.coverage['failed_units'][0]['reason_code'] == 'http_error'


@pytest.mark.parametrize('published', ['', 'invalid', '2099-01-01T00:00:00Z'])
def test_feed_does_not_repair_missing_or_invalid_article_date(published):
    html = ('<title>Incomplete article</title>'
            '<meta name="description" content="Original description">'
            f'<meta property="article:published_time" content="{published}">')
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(
        collector, 'fetch_html', side_effect=[feed('https://openai.com/index/one/'), html]
    ):
        items = collector.collect_official_signals()
    assert items == []
    assert items.coverage['complete'] is False
    assert items.coverage['failed_units'][0]['reason_code'] == 'invalid_response'


def test_old_original_article_remains_a_valid_zero_result():
    published = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    html = ('<title>Old article</title><meta name="description" content="Original description">'
            f'<meta property="article:published_time" content="{published}">')
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(
        collector, 'fetch_html', side_effect=[feed('https://openai.com/index/one/'), html]
    ):
        items = collector.collect_official_signals()
    assert items == []
    assert items.coverage['complete'] is True
    assert items.coverage['zero_result_unit_ids'] == ['official_source_001']


@pytest.mark.parametrize('url', ['https://openai.com/news/', FEED_URL])
def test_existing_subscription_url_still_selects_openai(url):
    with patch.object(collector, 'load_subscription_source_library', return_value=[
        {'name': 'Publisher', 'url': url, 'type': 'official_blog', 'enabled': True},
    ]):
        assert collector.get_effective_source_configs() == [CONFIG]


def test_openai_requests_identify_the_collector():
    with patch.object(collector.requests, 'get') as get:
        collector.fetch_html(FEED_URL)
    assert get.call_args.kwargs['headers']['User-Agent'].startswith('AI-Radar/')
