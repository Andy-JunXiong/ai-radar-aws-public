import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services.topic_display_service import (  # noqa: E402
    canonicalize_topic_label,
    canonicalize_topic_labels,
)


class TopicDisplayServiceTests(unittest.TestCase):
    def test_canonicalizes_format_variants_without_mutating_raw_values(self):
        raw_topics = [" ai-agents ", "AI_agents", "AI Agent", "agent ux", "Agent-UX"]

        labels = canonicalize_topic_labels(raw_topics)

        self.assertEqual(labels, ["AI Agents", "Agent UX"])
        self.assertEqual(raw_topics, [" ai-agents ", "AI_agents", "AI Agent", "agent ux", "Agent-UX"])

    def test_unknown_topics_receive_display_formatting_without_semantic_aliasing(self):
        self.assertEqual(canonicalize_topic_label("agentic ai"), "Agentic AI")
        self.assertEqual(canonicalize_topic_label("OpenAI safety"), "OpenAI Safety")
        self.assertEqual(canonicalize_topic_label(""), "")


if __name__ == "__main__":
    unittest.main()
