import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.registry import manual_text_analysis_prompt  # noqa: E402


class ManualTextPromptContractTests(unittest.TestCase):
    def test_single_text_prompt_requires_synthesis_not_plain_summary(self):
        prompt = manual_text_analysis_prompt(
            is_session=False,
            analysis_context="Evaluate this as an AI Radar cognitive asset seed.",
        )

        self.assertIn("This is a synthesis task, not a generic summary task.", prompt)
        self.assertIn("core thesis, argument structure, and underlying judgment", prompt)
        self.assertIn("reusable concepts, mental models, or decision rules", prompt)
        self.assertIn("what the material preserves, compresses, omits, or makes newly explicit", prompt)
        self.assertIn("Cite uploaded content inline as [Source: filename]", prompt)
        self.assertIn("Each value must be a string. Do not return nested objects or arrays.", prompt)
        self.assertIn("The synthesized_insight field should name the reusable insight or framework", prompt)
        self.assertIn('Do not prefix every field with "Uncertain:"', prompt)

    def test_verification_policy_marks_specific_facts_not_every_field(self):
        prompt = manual_text_analysis_prompt(
            is_session=False,
            analysis_context="Evaluate this as an AI Radar cognitive asset seed.",
            policy={"verification_required": True},
        )

        self.assertIn("concrete external factual claim", prompt)
        self.assertIn("mark that specific claim as Uncertain", prompt)
        self.assertIn("Do not use Uncertain as a blanket prefix for every response field", prompt)

    def test_session_prompt_requires_cross_document_synthesis(self):
        prompt = manual_text_analysis_prompt(
            is_session=True,
            analysis_context="Compare these files as one architecture-facing session.",
        )

        self.assertIn("This is a synthesis task, not a plain summary task.", prompt)
        self.assertIn("how the files modify or sharpen each other", prompt)
        self.assertIn("tensions, boundary decisions, missing distinctions, or unresolved questions", prompt)
        self.assertIn("deduplicate repeated points instead of restating each file", prompt)
        self.assertIn("Cite uploaded files inline as [Source: filename]", prompt)
        self.assertIn("Each value must be a string. Do not return nested objects or arrays.", prompt)
        self.assertIn("Use the user context as the prioritization lens", prompt)
        self.assertIn('Do not prefix every field with "Uncertain:"', prompt)


if __name__ == "__main__":
    unittest.main()
