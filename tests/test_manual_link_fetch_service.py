import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.manual_link_fetch_service import extract_readable_article


class ManualLinkFetchServiceTests(unittest.TestCase):
    def test_extract_readable_article_prefers_article_text_and_title(self):
        html = """
        <html>
          <head>
            <title>Interaction Models for AI Systems</title>
            <meta name="description" content="A useful summary">
            <style>.hidden { display: none; }</style>
          </head>
          <body>
            <nav>Home Pricing Login</nav>
            <article>
              <h1>Interaction Models</h1>
              <p>Human agency depends on interaction models that make system behavior legible.</p>
              <p>Teams need ways to inspect assumptions, compare alternatives, and preserve reviewer intent.</p>
              <p>This article explains why model-mediated work should expose uncertainty and source context.</p>
              <p>Those design constraints matter when building analytical workflows for AI-native tools.</p>
              <p>The strongest systems keep the user in control while still reducing repetitive synthesis work.</p>
            </article>
            <footer>Subscribe now</footer>
          </body>
        </html>
        """

        article = extract_readable_article(html)

        self.assertEqual(article["title"], "Interaction Models for AI Systems")
        self.assertEqual(article["description"], "A useful summary")
        self.assertIn("Human agency depends on interaction models", article["text"])
        self.assertNotIn("Home Pricing Login", article["text"])
        self.assertNotIn("Subscribe now", article["text"])

    def test_extract_readable_article_falls_back_to_body_text(self):
        html = """
        <html>
          <head><title>Short Article Tag</title></head>
          <body>
            <main>
              <p>This page does not use an article element, but it still contains enough readable body text for analysis.</p>
              <p>The parser should collect main body paragraphs and normalize whitespace without scripts or controls.</p>
              <p>Manual link uploads rely on this fallback because many public sites use div-based article layouts.</p>
              <p>Keeping this extractor small avoids a new dependency while still covering common article pages.</p>
              <p>The result should be good enough to feed the existing manual analysis path.</p>
            </main>
          </body>
        </html>
        """

        article = extract_readable_article(html)

        self.assertIn("does not use an article element", article["text"])
        self.assertIn("existing manual analysis path", article["text"])


if __name__ == "__main__":
    unittest.main()
