import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services.project_takeaway_candidate_policy import (  # noqa: E402
    INVARIANT_SCOPE,
    build_project_takeaway_candidate_input,
    evaluate_project_takeaway_candidate_policy,
)


class ProjectTakeawayCandidatePolicyTests(unittest.TestCase):
    def test_weakly_supported_can_enter_takeaway_review_while_low_risk_action_is_blocked(
        self,
    ):
        envelope = build_project_takeaway_candidate_input(
            {
                "verification_status": "weakly_supported",
                "claim_support_summary": {"inferred": 1},
                "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
                "blocked_downstream_actions": ["low_risk_action_candidate"],
            }
        )

        self.assertEqual(envelope.candidate_source, "verified_insight")
        self.assertTrue(envelope.policy.allowed)
        self.assertTrue(envelope.policy.action_eligibility["project_takeaway_candidate"]["allowed"])
        self.assertFalse(envelope.policy.action_eligibility["low_risk_action_candidate"]["allowed"])

    def test_knowledge_convergence_is_review_context_and_blocks_low_risk_action(self):
        envelope = build_project_takeaway_candidate_input(
            {
                "knowledge_convergence": True,
                "verification_status": "knowledge_convergence_review_candidate",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            }
        )

        self.assertEqual(envelope.candidate_source, "knowledge_convergence")
        self.assertIn(
            "low_risk_action_candidate",
            envelope.verification_metadata["blocked_downstream_actions"],
        )
        self.assertIn(
            "strong_recommendation",
            envelope.verification_metadata["blocked_downstream_actions"],
        )
        self.assertTrue(envelope.policy.action_eligibility["project_takeaway_candidate"]["allowed"])
        self.assertFalse(envelope.policy.action_eligibility["low_risk_action_candidate"]["allowed"])

    def test_confirmed_final_takeaway_is_review_context_and_blocks_low_risk_action(self):
        envelope = build_project_takeaway_candidate_input(
            {
                "confirmed_final_takeaway": True,
                "verification_status": "confirmed_final_takeaway_review_candidate",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
                "final_takeaway_id": "fta_abc123",
                "review_bundle_snapshot_id": "rbs_abc123",
            }
        )

        self.assertEqual(envelope.candidate_source, "confirmed_final_takeaway")
        self.assertIn(
            "low_risk_action_candidate",
            envelope.verification_metadata["blocked_downstream_actions"],
        )
        self.assertIn(
            "strong_recommendation",
            envelope.verification_metadata["blocked_downstream_actions"],
        )
        self.assertTrue(envelope.policy.action_eligibility["project_takeaway_candidate"]["allowed"])
        self.assertFalse(envelope.policy.action_eligibility["low_risk_action_candidate"]["allowed"])

    def test_unverified_manual_entry_cannot_enter_ordinary_takeaway_creation(self):
        policy = evaluate_project_takeaway_candidate_policy(
            {
                "verification_status": "unverified_manual_entry",
                "claim_support_summary": {},
                "allowed_downstream_actions": [],
                "blocked_downstream_actions": [],
            }
        )

        self.assertEqual(policy.source_category, "unverified_manual_entry")
        self.assertFalse(policy.allowed)
        self.assertIn("Unverified manual entries", policy.reason)

    def test_manual_override_is_explicit_exception_with_note(self):
        envelope = build_project_takeaway_candidate_input(
            {
                "manual_project_takeaway_override": True,
                "manual_override_note": "Human reviewed this blocked candidate.",
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"unsupported": 1}},
                    "action_policy": {
                        "allowed": [],
                        "blocked": ["project_takeaway_candidate", "low_risk_action_candidate"],
                    },
                },
            }
        )

        self.assertEqual(envelope.candidate_source, "manual_project_takeaway_override")
        self.assertTrue(envelope.policy.allowed)

    def test_envelope_records_handwritten_invariant_scope_selector(self):
        envelope = build_project_takeaway_candidate_input(
            {
                "verification_status": "verified",
                "claim_support_summary": {},
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            }
        )

        self.assertEqual(envelope.invariant_scope, INVARIANT_SCOPE)
        self.assertIn("Project Takeaway Gates #1", envelope.invariant_scope)
        self.assertIn("Project Takeaway Gates #7", envelope.invariant_scope)


if __name__ == "__main__":
    unittest.main()
