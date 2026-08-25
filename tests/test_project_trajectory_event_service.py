import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import project_trajectory_event_service as service  # noqa: E402


class ProjectTrajectoryEventServiceTests(unittest.TestCase):
    def test_build_trajectory_events_response_derives_summary_and_filters(self):
        review_records = [
            {
                "id": "prv_manual",
                "project_id": "ai_radar",
                "project_name": "AI Radar",
                "signal_id": "manual_123",
                "topics": ["AI Agents", "Agent UX"],
                "outcome": "watch",
                "source_type": "manual_upload",
                "manual_session_id": "123",
                "is_manual_source": True,
                "upload_reason": "Compare against roadmap",
                "intended_use": "Watch for project fit",
                "cognitive_layer": "L2",
                "verification_status": "partially_verified",
                "unsupported_claim_count": 1,
                "deep_project_match_required": True,
                "deep_project_match_status": "needed",
                "deep_project_match_posture": "Watch",
                "deep_project_match_review_note": "Compare with AI Radar review loop before Confirm.",
                "deep_project_match_review_note_effect": "review_context_only",
                "deep_project_match_matched_projects": ["AI Radar"],
                "deep_project_match_relevant_modules": ["Project Takeaway Review Loop"],
                "deep_project_match_match_type": "analogous",
                "deep_project_match_evidence_boundary": "internal_judgment",
                "deep_project_match_downstream_posture": "Keep action blocked until human deep match review.",
                "reviewed_at": "2026-05-04T12:00:00+00:00",
            }
        ]
        calibration_events = [
            {
                "id": "pce_signal",
                "event_type": "takeaway_accepted",
                "project_id": "ai_radar",
                "signal_id": "sig_1",
                "topics": ["AI Policy"],
                "source_type": "signal",
                "verification_status": "verified",
                "created_at": "2026-05-04T13:00:00+00:00",
            }
        ]

        result = service.build_trajectory_events_response(review_records, calibration_events)

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["items"][0]["event_kind"], "calibration")
        self.assertEqual(result["items"][0]["risk_level"], "low")
        self.assertEqual(result["items"][0]["trajectory_signal_type"], "calibration_learning")
        self.assertEqual(result["items"][1]["event_kind"], "review")
        self.assertEqual(result["items"][1]["topics"], ["AI Agents", "Agent UX"])
        self.assertEqual(result["items"][1]["topic_display_labels"], ["AI Agents", "Agent UX"])
        self.assertEqual(result["items"][1]["risk_level"], "high")
        self.assertEqual(result["items"][1]["trajectory_signal_type"], "manual_judgment")
        self.assertTrue(result["items"][1]["deep_project_match_required"])
        self.assertEqual(result["items"][1]["deep_project_match_review_note"], "Compare with AI Radar review loop before Confirm.")
        self.assertEqual(result["items"][1]["deep_project_match_review_note_effect"], "review_context_only")
        self.assertEqual(result["items"][1]["deep_project_match_relevant_modules"], ["Project Takeaway Review Loop"])
        self.assertEqual(result["summary"]["risk_mix"], {"low": 1, "high": 1})
        self.assertEqual(result["summary"]["signal_type_mix"], {"calibration_learning": 1, "manual_judgment": 1})
        self.assertEqual(
            result["summary"]["topic_mix"],
            [
                {"value": "Agent UX", "count": 1},
                {"value": "AI Policy", "count": 1},
                {"value": "AI Agents", "count": 1},
            ],
        )
        self.assertEqual(result["summary"]["topic_event_count"], 2)
        self.assertEqual(result["summary"]["unclassified_topic_event_count"], 0)
        self.assertEqual(result["summary"]["project_mix"][0]["topic_mix"][0]["count"], 1)
        self.assertEqual(
            result["summary"]["manual_intent_summary"]["upload_reason_mix"],
            [{"value": "Compare against roadmap", "count": 1}],
        )
        self.assertEqual(
            result["summary"]["manual_intent_summary"]["intended_use_mix"],
            [{"value": "Watch for project fit", "count": 1}],
        )
        self.assertEqual(
            result["summary"]["manual_intent_summary"]["cognitive_layer_mix"],
            [{"value": "L2", "count": 1}],
        )
        self.assertEqual(result["summary"]["project_mix"][0]["event_count"], 2)
        self.assertEqual(result["summary"]["project_mix"][0]["watch_count"], 1)
        self.assertEqual(result["summary"]["project_mix"][0]["action_count"], 0)

        filtered = service.build_trajectory_events_response(
            review_records,
            calibration_events,
            risk_level="risk",
            source_type="manual_upload",
        )

        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["items"][0]["id"], "prv_manual")
        self.assertEqual(filtered["summary"]["risk_mix"], {"high": 1})

    def test_topic_summary_groups_format_variants_without_rewriting_raw_topics(self):
        result = service.build_trajectory_events_response(
            [
                {
                    "id": "prv_workflow",
                    "project_id": "ai_radar",
                    "signal_id": "sig_workflow",
                    "topics": ["workflow", "workflow"],
                    "outcome": "watch",
                    "reviewed_at": "2026-05-04T12:00:00+00:00",
                },
                {
                    "id": "prv_workflows",
                    "project_id": "ai_radar",
                    "signal_id": "sig_workflows",
                    "topics": ["Workflows"],
                    "outcome": "watch",
                    "reviewed_at": "2026-05-04T13:00:00+00:00",
                },
            ],
            [],
        )

        self.assertEqual(result["items"][0]["topics"], ["Workflows"])
        self.assertEqual(result["items"][1]["topics"], ["workflow", "workflow"])
        self.assertEqual(result["items"][0]["topic_display_labels"], ["Workflow"])
        self.assertEqual(result["items"][1]["topic_display_labels"], ["Workflow"])
        self.assertEqual(
            result["items"][1]["topic_label_projections"],
            [{"raw_label": "workflow", "canonical_label": "Workflow"}],
        )
        self.assertEqual(result["summary"]["topic_mix"], [{"value": "Workflow", "count": 2}])
        self.assertEqual(result["summary"]["project_mix"][0]["topic_mix"], [{"value": "Workflow", "count": 2}])
        self.assertEqual(result["summary"]["topic_variant_group_count"], 1)
        variance_group = result["summary"]["topic_variant_groups"][0]
        self.assertEqual(variance_group["canonical_label"], "Workflow")
        self.assertEqual(variance_group["event_count"], 2)
        self.assertEqual(variance_group["project_count"], 1)
        self.assertEqual(
            {item["value"]: item["count"] for item in variance_group["variants"]},
            {"workflow": 1, "Workflows": 1},
        )

    def test_topic_summary_keeps_legacy_events_unclassified_without_title_inference(self):
        result = service.build_trajectory_events_response(
            [
                {
                    "id": "prv_legacy",
                    "project_id": "ai_radar",
                    "signal_id": "sig_legacy",
                    "signal_title": "AI Agents should not become an inferred topic",
                    "outcome": "watch",
                    "reviewed_at": "2026-05-04T12:00:00+00:00",
                }
            ],
            [],
        )

        self.assertEqual(result["items"][0]["topics"], [])
        self.assertEqual(result["summary"]["topic_mix"], [])
        self.assertEqual(result["summary"]["topic_event_count"], 0)
        self.assertEqual(result["summary"]["unclassified_topic_event_count"], 1)
        self.assertEqual(result["summary"]["project_mix"][0]["topic_mix"], [])
        self.assertEqual(result["summary"]["project_mix"][0]["unclassified_topic_event_count"], 1)
        self.assertEqual(result["summary"]["topic_variant_group_count"], 0)
        self.assertEqual(result["summary"]["topic_variant_groups"], [])

    def test_calibration_followup_fields_are_exposed_to_trajectory(self):
        result = service.build_trajectory_events_response(
            [],
            [
                {
                    "id": "pce_watch_followup",
                    "event_type": "watch_item_reviewed",
                    "project_id": "ai_radar",
                    "signal_id": "sig_watch",
                    "signal_title": "Watch follow-up",
                    "outcome": "watch",
                    "followup_result": "evidence_improved",
                    "review_note": "A second source appeared.",
                    "evidence_update": "Independent source confirmed the direction.",
                    "next_review_date": "2026-05-31",
                    "verification_status": "partially_verified",
                    "created_at": "2026-05-04T13:00:00+00:00",
                }
            ],
        )

        self.assertEqual(result["count"], 1)
        event = result["items"][0]
        self.assertEqual(event["outcome"], "watch_item_reviewed")
        self.assertEqual(event["followup_result"], "evidence_improved")
        self.assertEqual(event["review_note"], "A second source appeared.")
        self.assertEqual(event["evidence_update"], "Independent source confirmed the direction.")
        self.assertEqual(event["next_review_date"], "2026-05-31")


if __name__ == "__main__":
    unittest.main()
