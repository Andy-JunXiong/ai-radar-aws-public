"""OpenAI news discovery must fetch articles, not category/navigation pages."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_collectors import official_collector as collector


CONFIG = next(item for item in collector.SOURCE_CONFIGS if item['source'] == 'openai')


def article(date=None):
    date = date if date is not None else (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return f'<title>Update</title><meta name="description" content="Official description"><meta property="article:published_time" content="{date}">'


def test_news_discovery_ignores_categories_navigation_and_external_links():
    html = '''<nav><a href="/index/navigation/">Navigation</a></nav><main>
      <a href="/news/company-announcements/">Category</a>
      <a href="https://elsewhere.example/index/outside/">Outside</a>
      <a href="http://openai.com/index/insecure/">Insecure</a>
      <a href="/index/">Index root</a>
      <a href="/index/nested/path/">Not an article slug</a>
      <a href="/index/one/?tracking=1">Query</a>
      <a href="/index/one/#section">Fragment</a>
      <a href="/index/one/">One</a>
      <a href="https://openai.com/index/one/">Duplicate</a>
      <a href="/index/two/">Two</a><a href="/index/three/">Over bound</a>
    </main><footer><a href="/index/footer/">Footer</a></footer>'''
    with patch.object(collector, 'fetch_html', side_effect=[html, article(), article()]) as fetch:
        items = collector.collect_from_source(CONFIG, per_source_limit=2)
    assert [call.args[0] if call.args else call.kwargs['url'] for call in fetch.call_args_list] == [
        CONFIG['list_url'], 'https://openai.com/index/one/', 'https://openai.com/index/two/',
    ]
    assert items and items[0]['source'] == 'openai'


@pytest.mark.parametrize('html', [
    '<nav><a href="/index/navigation/">Only navigation</a></nav>',
    '<main><a href="/news/research/">Only category</a></main>',
])
def test_unrecognized_index_is_failed_coverage(html):
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(collector, 'fetch_html', return_value=html):
        items = collector.collect_official_signals()
    assert items == []
    assert items.coverage['failed_units'] == [{'unit_id': 'official_source_001', 'reason_code': 'invalid_response'}]
    assert items.coverage['complete'] is False


@pytest.mark.parametrize('date', ['', 'invalid', '2099-01-01T00:00:00Z'])
def test_invalid_article_date_is_not_successful_empty_coverage(date):
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(collector, 'fetch_html', side_effect=[
        '<main><a href="/index/update/">Update</a></main>', article(date),
    ]):
        items = collector.collect_official_signals()
    assert items == []
    assert items.coverage['failed_units'][0]['reason_code'] == 'invalid_response'


def test_old_article_is_valid_zero_result():
    date = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(collector, 'fetch_html', side_effect=[
        '<main><a href="/index/update/">Update</a></main>', article(date),
    ]):
        items = collector.collect_official_signals()
    assert items == []
    assert items.coverage['complete'] is True
    assert items.coverage['zero_result_unit_ids'] == ['official_source_001']


def test_http_failure_keeps_unit_failed():
    def read(url, **kwargs):
        if url == CONFIG['list_url']:
            return '<main><a href="/index/update/">Update</a></main>'
        kwargs['on_error'](requests.HTTPError('HTTP 503'))
        return None
    with patch.object(collector, 'get_effective_source_configs', return_value=[CONFIG]), patch.object(collector, 'fetch_html', side_effect=read):
        items = collector.collect_official_signals()
    assert items.coverage['failed_units'] == [{'unit_id': 'official_source_001', 'reason_code': 'http_error'}]


def test_article_header_date_wins_over_related_story_time():
    html = '''<title>Update</title><meta name="description" content="Description">
      <div data-section-header="true"><p>September 16, 2026</p><h1>Update</h1></div>
      <aside><time datetime="2026-09-21T12:00:00Z">Related story</time></aside>'''
    with patch.object(collector, 'fetch_html', return_value=html):
        item = collector.parse_article_page('https://openai.com/index/update/', 'openai', 'OpenAI', 'AI Model')
    assert item['published_at'] == '2026-09-16T00:00:00+00:00'


def test_related_story_cannot_supply_missing_article_date():
    html = '''<title>Update</title><meta name="description" content="Description">
      <div data-section-header="true"><h1>Update</h1></div>
      <aside><time datetime="2026-09-21T12:00:00Z">Related story</time></aside>'''
    failures = []
    with patch.object(collector, 'fetch_html', return_value=html):
        item = collector.parse_article_page('https://openai.com/index/update/', 'openai', 'OpenAI', 'AI Model', on_fetch_error=failures.append)
    assert item is None
    assert failures and isinstance(failures[0], collector.InvalidCollectionResponse)
