import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.reflection.frontmatter_parser import parse_reflection  # noqa: E402


class ReflectionFrontmatterParserTests(unittest.TestCase):
    def test_parse_reflection_supports_structured_reasoning_fields(self):
        content = """---
id: refl_2026-04-13_agent-memory
title: Agent memory notes
timestamp: 2026-04-13T10:00:00Z
source: manual
tags:
  - ai agents
  - memory
thesis: Memory is the product bottleneck.
key_claims:
  - context windows are not durable memory
counterpoints:
  - narrow workflows can avoid memory complexity
open_questions:
  - when does memory infra become necessary
final_takeaway: Durable memory is becoming product-critical.
confidence: 0.82
evidence_strength: medium
---

Reflection body.
"""

        result = parse_reflection(
            content=content,
            github_path="reflections/agent-memory.md",
            github_url="https://example.com/reflections/agent-memory",
            github_raw_url="https://example.com/raw/reflections/agent-memory",
            commit_sha="abc123",
            last_modified=datetime.now(timezone.utc),
        )

        self.assertEqual(result.thesis, "Memory is the product bottleneck.")
        self.assertEqual(result.key_claims, ["context windows are not durable memory"])
        self.assertEqual(
            result.counterpoints,
            ["narrow workflows can avoid memory complexity"],
        )
        self.assertEqual(
            result.open_questions,
            ["when does memory infra become necessary"],
        )
        self.assertEqual(result.final_takeaway, "Durable memory is becoming product-critical.")
        self.assertEqual(result.confidence, 0.82)
        self.assertEqual(result.evidence_strength, "medium")


if __name__ == "__main__":
    unittest.main()
