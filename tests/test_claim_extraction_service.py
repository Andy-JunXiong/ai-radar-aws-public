import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.claim_extraction_service import extract_claims_from_insight  # noqa: E402


class ClaimExtractionServiceTests(unittest.TestCase):
    def test_extracts_limited_typed_claims_from_insight_fields(self):
        claims = extract_claims_from_insight(
            {
                "why_it_matters": "This repo added enterprise deployment docs. This broader agent trend may influence infrastructure decisions.",
                "synthesized_insight": "Track this signal before making roadmap changes.",
            }
        )

        self.assertGreaterEqual(len(claims), 2)
        self.assertLessEqual(len(claims), 5)
        self.assertEqual(claims[0]["claim_id"], "claim_1")
        self.assertEqual(claims[0]["claim_type"], "descriptive")
        self.assertIn("trend", {claim["claim_type"] for claim in claims})
        self.assertIn("prescriptive", {claim["claim_type"] for claim in claims})

    def test_removes_uncertainty_and_low_evidence_boilerplate(self):
        claims = extract_claims_from_insight(
            {
                "why_it_matters": (
                    "Uncertain: The signal highlights emerging agent memory workflows. "
                    "Evidence is insufficient for strong conclusions. "
                    "Treat this output as an observation, not a reliable strategic recommendation."
                ),
                "relevance_to_projects": (
                    "Evidence is thin and supports only cautious interpretation. "
                    "Avoid broad market or strategic claims from this single signal."
                ),
            }
        )

        self.assertEqual(len(claims), 1)
        self.assertEqual(
            claims[0]["claim_text"],
            "The signal highlights emerging agent memory workflows.",
        )
        self.assertNotIn("Uncertain:", claims[0]["claim_text"])
        self.assertFalse(any("Evidence is" in claim["claim_text"] for claim in claims))


if __name__ == "__main__":
    unittest.main()
