import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import rejected_learning_buffer_service  # noqa: E402


class RejectedLearningBufferServiceTests(unittest.TestCase):
    def test_builds_bounded_caution_context_from_rejected_and_dismissed_records(self):
        records = [
            {
                "id": "prv-rejected",
                "project_id": "ai_radar",
                "signal_id": "sig-1",
                "signal_title": "Unsupported agent benchmark claim",
                "outcome": "rejected",
                "reason": "The claim was not supported by the available evidence.",
                "candidate_source": "verified_insight",
                "verification_status": "partially_verified",
                "blocked_downstream_actions": ["low_risk_action_candidate"],
                "unsupported_claim_count": 1,
                "inferred_claim_count": 2,
                "confidence_label": "low",
                "reviewed_at": "2026-05-27T00:00:00+00:00",
            },
            {
                "id": "prv-confirmed",
                "project_id": "ai_radar",
                "signal_id": "sig-2",
                "outcome": "confirmed",
            },
            {
                "id": "prv-dismissed",
                "project_id": "ai_radar",
                "signal_id": "sig-3",
                "signal_title": "Low relevance project match",
                "outcome": "dismissed",
                "reason": "Not useful for this project.",
                "verification_status": "verified",
                "blocked_downstream_actions": [],
                "reviewed_at": "2026-05-26T00:00:00+00:00",
            },
        ]

        with patch.object(rejected_learning_buffer_service, "list_project_review_records", return_value=records):
            result = rejected_learning_buffer_service.build_rejected_learning_buffer(project_id="ai_radar", limit=10)

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["context_role"], "bounded_caution")
        self.assertEqual(result["evidence_boundary"], "not_factual_evidence")
        self.assertEqual(result["source"], "project_review_records")
        self.assertEqual(result["source_record_count"], 3)
        self.assertEqual(result["outcome_counts"], {"rejected": 1, "confirmed": 1, "dismissed": 1})
        self.assertEqual(result["buffer_outcomes"], ["dismissed", "rejected"])
        self.assertEqual(result["prompt_readiness"]["status"], "review_ready")
        self.assertFalse(result["prompt_readiness"]["safe_for_prompt_injection"])
        self.assertEqual(result["item_count"], 2)
        self.assertEqual([item["record_id"] for item in result["items"]], ["prv-rejected", "prv-dismissed"])
        self.assertIn("Reviewer reason", result["items"][0]["caution"])
        self.assertIn("low_risk_action_candidate", result["items"][0]["caution"])
        self.assertIn("not supported", result["items"][0]["review_reason"])

    def test_applies_upper_limit_to_keep_context_bounded(self):
        records = [
            {
                "id": f"prv-{index}",
                "project_id": "ai_radar",
                "signal_id": f"sig-{index}",
                "outcome": "rejected",
            }
            for index in range(30)
        ]

        with patch.object(rejected_learning_buffer_service, "list_project_review_records", return_value=records):
            result = rejected_learning_buffer_service.build_rejected_learning_buffer(project_id="ai_radar", limit=999)

        self.assertEqual(result["limit"], rejected_learning_buffer_service.MAX_LIMIT)
        self.assertEqual(result["item_count"], rejected_learning_buffer_service.MAX_LIMIT)

    def test_does_not_include_reflection_or_evidence_claims(self):
        records = [
            {
                "id": "prv-dismissed",
                "project_id": "ai_radar",
                "signal_id": "sig-1",
                "outcome": "dismissed",
                "reason": "This was a weak fit.",
                "final_reflection": "Internal cognitive context should not be copied here.",
                "claim_text": "This should not become evidence.",
            }
        ]

        with patch.object(rejected_learning_buffer_service, "list_project_review_records", return_value=records):
            result = rejected_learning_buffer_service.build_rejected_learning_buffer(project_id="ai_radar")

        item = result["items"][0]
        self.assertNotIn("final_reflection", item)
        self.assertNotIn("claim_text", item)
        self.assertEqual(result["evidence_boundary"], "not_factual_evidence")

    def test_prompt_readiness_blocks_prompt_injection_when_no_rejected_records_exist(self):
        records = [
            {
                "id": "prv-watch",
                "project_id": "ai_radar",
                "signal_id": "sig-1",
                "outcome": "watch",
            },
            {
                "id": "prv-action",
                "project_id": "ai_radar",
                "signal_id": "sig-2",
                "outcome": "action",
            },
        ]

        with patch.object(rejected_learning_buffer_service, "list_project_review_records", return_value=records):
            result = rejected_learning_buffer_service.build_rejected_learning_buffer(project_id="ai_radar")

        self.assertEqual(result["item_count"], 0)
        self.assertEqual(result["source_record_count"], 2)
        self.assertEqual(result["outcome_counts"], {"watch": 1, "action": 1})
        self.assertEqual(result["prompt_readiness"]["status"], "not_ready")
        self.assertFalse(result["prompt_readiness"]["safe_for_prompt_injection"])
        self.assertIn("No rejected or dismissed", result["prompt_readiness"]["reasons"][0])


if __name__ == "__main__":
    unittest.main()
