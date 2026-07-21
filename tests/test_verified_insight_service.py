import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.verified_insight_service import build_verified_insight_metadata  # noqa: E402


class VerifiedInsightServiceTests(unittest.TestCase):
    def setUp(self):
        self.metrics_patcher = patch("app.services.verified_insight_service.record_verification_event")
        self.mock_record_verification_event = self.metrics_patcher.start()

    def tearDown(self):
        self.metrics_patcher.stop()

    def test_strong_evidence_builds_verified_status_and_decision_card_permission(self):
        result = build_verified_insight_metadata(
            signal_id="sig-1",
            content_fingerprint="abc123",
            evidence_quality={"level": "strong"},
            low_evidence_gate={"decision_card_allowed": True},
            generation_mode="llm",
        )

        self.assertTrue(result["verified_insight_id"].startswith("vi_"))
        self.assertEqual(result["verification_status"], "verified")
        self.assertIn("decision_card", result["allowed_downstream_actions"])
        self.assertNotIn("decision_card", result["blocked_downstream_actions"])
        self.assertEqual(result["verified_insight"]["id"], result["verified_insight_id"])
        self.assertEqual(result["verified_insight"]["schema_version"], 1)
        self.assertEqual(result["verified_insight"]["version"], "v1")
        self.assertEqual(result["verified_insight"]["status"], "verified")
        self.assertEqual(result["verified_insight"]["evidence"]["level"], "strong")
        self.assertIn("decision_card", result["verified_insight"]["action_policy"]["allowed"])

    def test_thin_evidence_is_watch_only(self):
        result = build_verified_insight_metadata(
            signal_id="sig-2",
            content_fingerprint="def456",
            evidence_quality={"level": "thin"},
            low_evidence_gate={"decision_card_allowed": "watch_only"},
            generation_mode="llm",
        )

        self.assertEqual(result["verification_status"], "weak_evidence")
        self.assertIn("watch_only", result["allowed_downstream_actions"])
        self.assertIn("decision_card", result["blocked_downstream_actions"])

    def test_fallback_requires_human_review(self):
        result = build_verified_insight_metadata(
            signal_id="sig-3",
            content_fingerprint="ghi789",
            evidence_quality={"level": "sufficient"},
            low_evidence_gate={"decision_card_allowed": True},
            generation_mode="fallback",
        )

        self.assertEqual(result["verification_status"], "needs_human_review")
        self.assertIn("needs_human_review", result["allowed_downstream_actions"])
        self.assertIn("decision_card", result["blocked_downstream_actions"])

    def test_claim_results_can_downgrade_strong_evidence(self):
        result = build_verified_insight_metadata(
            signal_id="sig-4",
            content_fingerprint="jkl012",
            evidence_quality={"level": "strong"},
            low_evidence_gate={"decision_card_allowed": True, "max_confidence": 0.95},
            generation_mode="llm",
            claim_results=[
                {
                    "claim_id": "claim_1",
                    "claim_text": "This proves a broad market trend.",
                    "claim_type": "trend",
                    "support_level": "partially_supported",
                    "verification_notes": ["single_source_trend_claim_downgraded"],
                }
            ],
            evidence_pack_id="sig-4",
        )

        self.assertEqual(result["verification_status"], "partially_verified")
        self.assertIn("project_takeaway_candidate", result["allowed_downstream_actions"])
        self.assertIn("decision_card", result["blocked_downstream_actions"])
        self.assertEqual(result["downgrade_reason"], "claim_support_limitations")
        self.assertEqual(result["claim_support_summary"]["partially_supported"], 1)
        self.assertEqual(result["confidence_score"], 0.75)
        self.assertEqual(result["confidence_label"], "high")
        self.assertEqual(result["verified_insight"]["claims"]["count"], 1)
        self.assertEqual(
            result["verified_insight"]["claims"]["support_summary"]["partially_supported"],
            1,
        )
        self.assertEqual(result["verified_insight"]["confidence"]["score"], 0.75)
        self.assertEqual(result["verified_insight"]["downgrade"]["reason"], "claim_support_limitations")
        self.mock_record_verification_event.assert_called_once()
        metric = self.mock_record_verification_event.call_args.args[0]
        self.assertEqual(metric["signal_id"], "sig-4")
        self.assertEqual(metric["verified_insight_id"], result["verified_insight_id"])
        self.assertEqual(metric["evidence_level"], "strong")
        self.assertEqual(metric["verification_status"], "partially_verified")
        self.assertEqual(metric["claim_count"], 1)
        self.assertEqual(metric["unsupported_claim_count"], 0)
        self.assertTrue(metric["downgrade_applied"])
        self.assertIn("project_takeaway_candidate", metric["allowed_downstream_actions"])

    def test_unsupported_claim_blocks_project_takeaway_candidate(self):
        result = build_verified_insight_metadata(
            signal_id="sig-5",
            content_fingerprint="mno345",
            evidence_quality={"level": "strong"},
            low_evidence_gate={"decision_card_allowed": True, "max_confidence": 0.95},
            generation_mode="llm",
            claim_results=[
                {
                    "claim_id": "claim_1",
                    "claim_text": "Unsupported roadmap-changing claim.",
                    "claim_type": "prescriptive",
                    "support_level": "unsupported",
                    "verification_notes": ["no_matched_evidence"],
                }
            ],
            evidence_pack_id="sig-5",
        )

        self.assertEqual(result["verification_status"], "unsupported")
        self.assertIn("observation_only", result["allowed_downstream_actions"])
        self.assertIn("project_takeaway_candidate", result["blocked_downstream_actions"])
        self.assertEqual(result["claim_support_summary"]["unsupported"], 1)
        self.assertEqual(result["confidence_score"], 0.35)
        self.assertEqual(result["confidence_label"], "low")
        self.assertEqual(result["verified_insight"]["claims"]["unsupported_or_contradicted_count"], 1)
        self.assertIn("project_takeaway_candidate", result["verified_insight"]["action_policy"]["blocked"])
        metric = self.mock_record_verification_event.call_args.args[0]
        self.assertEqual(metric["verification_status"], "unsupported")
        self.assertEqual(metric["unsupported_claim_count"], 1)
        self.assertIn("project_takeaway_candidate", metric["blocked_downstream_actions"])

    def test_inferred_borrowed_shell_claim_blocks_downstream_action_gates(self):
        result = build_verified_insight_metadata(
            signal_id="sig-borrowed-shell",
            content_fingerprint="borrowed123",
            evidence_quality={"level": "strong"},
            low_evidence_gate={"decision_card_allowed": True, "max_confidence": 0.95},
            generation_mode="llm",
            claim_results=[
                {
                    "claim_id": "claim_1",
                    "claim_text": "The product launch proves durable memory is now solved.",
                    "claim_type": "descriptive",
                    "support_level": "inferred",
                    "origin": "inferred",
                    "source_span": None,
                    "verification_notes": ["matched_evidence_without_source_span"],
                }
            ],
            evidence_pack_id="sig-borrowed-shell",
        )

        self.assertEqual(result["verification_status"], "weakly_supported")
        self.assertIn("project_takeaway_candidate", result["blocked_downstream_actions"])
        self.assertIn("low_risk_action_candidate", result["blocked_downstream_actions"])
        self.assertEqual(result["claim_support_summary"]["inferred"], 1)
        self.assertEqual(result["verified_insight"]["claims"]["inferred_count"], 1)

    def test_model_provenance_is_attached_to_flat_and_nested_verified_insight(self):
        produced_by_model = {
            "provider": "openai",
            "model_id": "gpt-test",
            "model_version": "",
            "task_type": "insight",
            "route_key": "insight.synthesize",
            "router_source": "env",
            "prompt_template_id": "signal_insight",
            "prompt_template_version": "v1",
            "inference_params": {
                "temperature": 0.3,
                "max_tokens": 1800,
                "top_p": None,
                "stop_sequences": [],
            },
            "deterministic_fingerprint": "a" * 64,
            "generated_at": "2026-05-22T00:00:00+00:00",
            "provenance_schema_version": 1,
        }

        result = build_verified_insight_metadata(
            signal_id="sig-6",
            content_fingerprint="pqr678",
            evidence_quality={"level": "strong"},
            low_evidence_gate={"decision_card_allowed": True},
            generation_mode="llm",
            produced_by_model=produced_by_model,
        )

        self.assertEqual(result["produced_by_model"], produced_by_model)
        self.assertEqual(result["verified_insight"]["produced_by_model"], produced_by_model)


if __name__ == "__main__":
    unittest.main()
