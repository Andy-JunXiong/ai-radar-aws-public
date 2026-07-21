import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from signal_collectors.official_collector import parse_article_page  # noqa: E402


class OfficialCollectorSourceExcerptTests(unittest.TestCase):
    def test_parse_article_page_preserves_bounded_source_excerpt_from_body(self):
        body = "This official article paragraph is long enough to be treated as source body text. " * 30
        html = f"""
        <html>
          <head>
            <meta property="og:title" content="Official model update" />
            <meta name="description" content="A short official summary." />
            <meta property="article:published_time" content="2026-05-28T01:00:00Z" />
          </head>
          <body>
            <article>
              <p>{body}</p>
            </article>
          </body>
        </html>
        """

        with patch("signal_collectors.official_collector.fetch_html", return_value=html):
            result = parse_article_page(
                url="https://example.com/news/model-update",
                fallback_source="openai",
                fallback_author="OpenAI",
                fallback_category="AI Model",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["title"], "Official model update")
        self.assertEqual(result["summary"], "A short official summary.")
        self.assertEqual(result["source_excerpt"], body[:1200])
        self.assertEqual(result["content"], body[:1200])
        self.assertEqual(result["source_excerpt_length"], 1200)
        self.assertEqual(result["content_length"], 1200)

    def test_parse_article_page_does_not_promote_description_to_source_excerpt(self):
        html = """
        <html>
          <head>
            <title>Description only update</title>
            <meta name="description" content="Only a metadata description is available." />
            <meta property="article:published_time" content="2026-05-28T01:00:00Z" />
          </head>
          <body>
            <p>short</p>
          </body>
        </html>
        """

        with patch("signal_collectors.official_collector.fetch_html", return_value=html):
            result = parse_article_page(
                url="https://example.com/news/description-only",
                fallback_source="openai",
                fallback_author="OpenAI",
                fallback_category="AI Model",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["summary"], "Only a metadata description is available.")
        self.assertEqual(result["content"], "Only a metadata description is available.")
        self.assertEqual(result["source_excerpt"], "")
        self.assertEqual(result["source_excerpt_length"], 0)


if __name__ == "__main__":
    unittest.main()
