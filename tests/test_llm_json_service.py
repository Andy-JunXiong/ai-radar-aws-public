import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm_json_service import parse_model_json  # noqa: E402


class ParseModelJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        raw_output = '{"summary":"x","why_it_matters":"y","relevance_to_projects":"z","relevance_to_career":"c","synthesized_insight":"s"}'

        parsed = parse_model_json(raw_output)

        self.assertEqual(parsed["summary"], "x")
        self.assertEqual(parsed["synthesized_insight"], "s")

    def test_parses_json_inside_code_fence(self):
        raw_output = """```json
{"summary":"x","why_it_matters":"y","relevance_to_projects":"z","relevance_to_career":"c","synthesized_insight":"s"}
```"""

        parsed = parse_model_json(raw_output)

        self.assertEqual(parsed["why_it_matters"], "y")

    def test_parses_embedded_json_object(self):
        raw_output = """
Here is the result:
{"summary":"x","why_it_matters":"y","relevance_to_projects":"z","relevance_to_career":"c","synthesized_insight":"s"}
Thanks.
"""

        parsed = parse_model_json(raw_output)

        self.assertEqual(parsed["relevance_to_projects"], "z")

    def test_uses_openai_repair_when_enabled(self):
        with patch(
            "app.services.llm_json_service.repair_output_to_json_with_openai",
            return_value={
                "summary": "fixed",
                "why_it_matters": "fixed",
                "relevance_to_projects": "fixed",
                "relevance_to_career": "fixed",
                "synthesized_insight": "fixed",
            },
        ) as repair_mock:
            parsed = parse_model_json(
                "not-json-at-all",
                repair_with_openai=True,
                schema_keys=[
                    "summary",
                    "why_it_matters",
                    "relevance_to_projects",
                    "relevance_to_career",
                    "synthesized_insight",
                ],
            )

        self.assertEqual(parsed["summary"], "fixed")
        repair_mock.assert_called_once()

    def test_raises_when_invalid_and_repair_disabled(self):
        with self.assertRaises(ValueError):
            parse_model_json("not-json-at-all", repair_with_openai=False)


if __name__ == "__main__":
    unittest.main()
