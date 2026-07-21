import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.s3_reader import build_signal_identity, dedupe_signals  # noqa: E402


class SignalDedupeTests(unittest.TestCase):
    def test_fragment_only_atom_urls_share_identity(self):
        base = {
            "title": "Datasette Apps: Host custom HTML applications inside Datasette",
            "source": "simon_willisons_weblog",
            "published_at": "2026-06-18T23:58:38+00:00",
        }

        everything = {
            **base,
            "url": "https://simonwillison.net/2026/Jun/18/datasette-apps/#atom-everything",
        }
        entries = {
            **base,
            "source": "simon_willisons_weblog_2",
            "url": "https://simonwillison.net/2026/Jun/18/datasette-apps/#atom-entries",
        }

        self.assertEqual(build_signal_identity(everything), build_signal_identity(entries))
        deduped = dedupe_signals([everything, entries])
        self.assertEqual(len(deduped), 1)

    def test_category_article_same_content_prefers_article_record(self):
        summary = (
            "Web Search on Amazon Bedrock AgentCore is now generally available. "
            "In this post, we walk through what makes Web Search on Amazon Bedrock "
            "AgentCore different, why it matters, and how to wire it in with a few lines of code."
        )
        article = {
            "title": "Introducing Web Search on Amazon Bedrock AgentCore",
            "source": "aws_ml",
            "url": "https://aws.amazon.com/blogs/machine-learning/introducing-web-search-on-amazon-bedrock-agentcore/",
            "published_at": "2026-06-19T14:15:24+00:00",
            "summary": summary,
        }
        category = {
            "title": "Amazon Bedrock AgentCore | Artificial Intelligence",
            "source": "aws_ai",
            "url": "https://aws.amazon.com/blogs/machine-learning/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/amazon-bedrock-agentcore/",
            "published_at": "2026-06-19T14:15:24+00:00",
            "summary": f"{summary} Today, Amazon Bedrock AgentCore harness is generally available.",
        }
        listing = {
            "title": "Advanced (300) | Artificial Intelligence",
            "source": "aws_ai",
            "url": "https://aws.amazon.com/blogs/machine-learning/category/learning-levels/advanced-300/",
            "published_at": "2026-06-19T14:15:24+00:00",
            "summary": f"{summary} Today, Amazon Bedrock AgentCore harness is generally available.",
        }

        deduped = dedupe_signals([category, article, listing])

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["title"], "Introducing Web Search on Amazon Bedrock AgentCore")
        self.assertEqual(deduped[0]["url"], article["url"])


if __name__ == "__main__":
    unittest.main()
