import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from signal_collectors import official_collector  # noqa: E402


def _lmarena_config():
    return next(config for config in official_collector.SOURCE_CONFIGS if config["source"] == "lmarena")


def test_lmarena_is_an_official_evaluation_source():
    config = _lmarena_config()

    assert config == {
        "source": "lmarena",
        "source_type": "official",
        "author": "LMArena",
        "category": "AI Evaluation",
        "list_url": "https://arena.ai/blog/",
        "base_url": "https://arena.ai",
        "allowed_prefixes": ["/blog/"],
        "excluded_prefixes": ["/blog/category/"],
    }


def test_lmarena_subscription_selects_the_official_collector(monkeypatch):
    monkeypatch.setattr(
        official_collector,
        "load_subscription_source_library",
        lambda: [
            {
                "name": "LMArena News",
                "url": "https://arena.ai/blog/",
                "type": "official_blog",
                "enabled": True,
            }
        ],
    )

    assert official_collector.get_effective_source_configs() == [_lmarena_config()]


def test_lmarena_list_page_only_admits_blog_article_links():
    html = """
    <a href="/blog/ranking-method">Ranking method</a>
    <a href="https://arena.ai/blog/leaderboard-changelog">Leaderboard changelog</a>
    <a href="/blog/category/news">News category</a>
    <a href="/leaderboard">Leaderboard</a>
    """

    links = official_collector.extract_links_from_list_page(
        html=html,
        base_url="https://arena.ai",
        allowed_prefixes=["/blog/"],
        excluded_prefixes=["/blog/category/"],
    )

    assert links == [
        "https://arena.ai/blog/ranking-method",
        "https://arena.ai/blog/leaderboard-changelog",
    ]


def test_public_snapshot_does_not_publish_private_source_library():
    source_file = REPO_ROOT / "backend" / "data" / "settings" / "subscriptions" / "admin_default.json"

    assert not source_file.exists()
