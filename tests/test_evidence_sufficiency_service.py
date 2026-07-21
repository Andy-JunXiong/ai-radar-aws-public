import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.evidence_sufficiency_service import assess_evidence_sufficiency  # noqa: E402
from app.services.low_evidence_gate_service import build_low_evidence_gate  # noqa: E402


class EvidenceSufficiencyServiceTests(unittest.TestCase):
    def test_title_only_signal_is_insufficient(self):
        evidence_pack = {
            "source_title": "Only title",
            "summary_excerpt": "",
            "source_type": "unknown",
            "source_url": "",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertEqual(result["level"], "insufficient")
        self.assertTrue(result["is_thin_signal"])

    def test_title_and_short_summary_is_thin(self):
        evidence_pack = {
            "source_title": "Title",
            "summary_excerpt": "Short summary with not much detail.",
            "source_type": "github",
            "source_url": "https://example.com",
            "summary_provenance": "collector_extracted",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertEqual(result["level"], "thin")
        self.assertLess(result["score"], 0.65)

    def test_title_and_long_summary_can_be_sufficient(self):
        evidence_pack = {
            "source_title": "Title",
            "summary_excerpt": "A" * 260,
            "source_type": "github",
            "source_url": "https://example.com",
            "summary_provenance": "source_excerpt",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertEqual(result["level"], "sufficient")
        self.assertGreaterEqual(result["score"], 0.65)

    def test_manual_rich_signal_can_be_strong(self):
        evidence_pack = {
            "source_title": "Manual upload evidence",
            "summary_excerpt": "A" * 520,
            "source_type": "manual",
            "source_url": "https://example.com/source",
            "summary_provenance": "manual_user_written",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertEqual(result["level"], "strong")
        self.assertGreaterEqual(result["score"], 0.85)

    def test_unknown_summary_provenance_is_downweighted(self):
        evidence_pack = {
            "source_title": "Title",
            "summary_excerpt": "A" * 260,
            "source_type": "github",
            "source_url": "https://example.com",
            "summary_provenance": "unknown",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertEqual(result["summary_provenance"], "unknown")
        self.assertLess(result["summary_weight_applied"], 0.35)
        self.assertIn("unknown_summary_provenance_downweighted", result["reason_codes"])

    def test_llm_generated_summary_is_more_heavily_downweighted(self):
        evidence_pack = {
            "source_title": "Title",
            "summary_excerpt": "A" * 260,
            "source_type": "github",
            "source_url": "https://example.com",
            "summary_provenance": "llm_generated",
        }

        result = assess_evidence_sufficiency(evidence_pack)

        self.assertLess(result["summary_weight_applied"], 0.2)
        self.assertIn("llm_generated_summary_downweighted", result["reason_codes"])


class LowEvidenceGateServiceTests(unittest.TestCase):
    def test_insufficient_evidence_caps_confidence_and_blocks_decision_card(self):
        gate = build_low_evidence_gate({"level": "insufficient"})

        self.assertEqual(gate["max_confidence"], 0.35)
        self.assertFalse(gate["decision_card_allowed"])
        self.assertEqual(gate["output_mode"], "observation_only")

    def test_thin_evidence_caps_confidence_and_is_watch_only(self):
        gate = build_low_evidence_gate({"level": "thin"})

        self.assertEqual(gate["max_confidence"], 0.55)
        self.assertEqual(gate["decision_card_allowed"], "watch_only")
        self.assertEqual(gate["output_mode"], "weak_insight_with_uncertainty")


if __name__ == "__main__":
    unittest.main()
