import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence.processors import friction_signal_processor as processor  # noqa: E402


class FrictionSignalProcessorTests(unittest.TestCase):
    def test_collect_normalized_friction_signals_scores_and_tags_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            github_path = temp_root / "github_friction_signals.json"
            hn_path = temp_root / "hackernews_friction_signals.json"

            github_path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "title": "Cursor bug breaks long-context workflow",
                                "summary": "GitHub issue discussion detected.",
                                "content": "The agent fails and context memory is broken in larger repos.",
                                "url": "https://example.com/github-issue",
                                "source": "github",
                                "source_type": "github_friction",
                                "topic": "ai_friction",
                                "signal_type": "friction",
                                "source_weight": 0.8,
                                "metadata": {"comments": 12, "repo_name": "cursor/issues"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hn_path.write_text(json.dumps({"signals": []}), encoding="utf-8")

            with patch.object(processor, "RAW_GITHUB_FRICTION_SIGNALS_FILE", github_path), patch.object(
                processor, "RAW_HN_FRICTION_SIGNALS_FILE", hn_path
            ):
                signals = processor.collect_normalized_friction_signals()

        self.assertEqual(len(signals), 1)
        item = signals[0]
        self.assertEqual(item["signal_type"], "friction")
        self.assertEqual(item["topic"], "ai_friction")
        self.assertEqual(item["friction_subtopic"], "reliability")
        self.assertGreater(item["pain_severity_score"], 0.3)
        self.assertGreater(item["friction_score"], 0.3)


if __name__ == "__main__":
    unittest.main()
