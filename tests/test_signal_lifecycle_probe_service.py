import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services.signal_lifecycle_probe_service import build_signal_lifecycle_probe  # noqa: E402


class SignalLifecycleProbeServiceTests(unittest.TestCase):
    def test_probe_marks_workspace_and_project_records_as_non_authoritative_trajectory(self):
        signal = {
            "signal_id": "manual_123",
            "title": "Manual source",
            "source": "manual",
            "status": "completed",
            "analysis_status": "completed",
            "workspace_saved": True,
            "workspace_file_name": "workspace.json",
            "workspace_saved_at": "2026-05-06T07:18:37+00:00",
            "why_it_matters": "Why",
            "verification": {
                "verification_status": "partially_verified",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": ["low_risk_action_candidate"],
                "claim_support_summary": {"supported": 1, "inferred": 1},
            },
        }
        review_records = [
            {
                "id": "prv_1",
                "project_id": "ai_radar",
                "signal_id": "manual_123",
                "outcome": "watch",
                "reviewed_at": "2026-05-06T08:00:00+00:00",
            }
        ]

        result = build_signal_lifecycle_probe(signal, review_records=review_records, calibration_events=[])

        self.assertFalse(result["authoritative"])
        self.assertEqual(result["adapter"], "signal_lifecycle_probe_legacy_adapter_v0")
        self.assertEqual(result["contract_version"], "trajectory_view_contract_v0")
        self.assertEqual(result["project_context"]["review_records_count"], 1)

        steps = {step["step_id"]: step for step in result["steps"]}
        self.assertEqual(steps["workspace_completion"]["provenance"], "direct")
        self.assertEqual(steps["workspace_completion"]["state"], "completed")
        self.assertEqual(steps["project_fanout"]["provenance"], "derived")
        self.assertEqual(steps["project_outcomes"]["support"]["outcomes"], ["watch"])
        self.assertIn("signal.workspace_saved", result["gap_report"]["direct_fields"])
        self.assertIn(
            "Signal-owned lifecycle history cannot yet show project outcomes without joining project-side records.",
            result["gap_report"]["architecture_gaps"],
        )

    def test_probe_exposes_saved_signal_as_inferred_when_decision_trace_is_missing(self):
        signal = {
            "signal_id": "sig_saved",
            "title": "Saved signal",
            "source": "aws_ml",
            "status": "saved",
            "saved_reason": "Worth a later look",
            "published_at": "2026-05-13T17:33:16+00:00",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }

        result = build_signal_lifecycle_probe(signal)

        steps = {step["step_id"]: step for step in result["steps"]}
        self.assertEqual(steps["signal_decision"]["state"], "saved")
        self.assertEqual(steps["signal_decision"]["provenance"], "inferred")
        self.assertIn("Status exists, but the transition event, actor, and timestamp are missing.", steps["signal_decision"]["gaps"])
        self.assertIn(
            "Signal status is stored, but status transition history is not authoritative for legacy/current records.",
            result["gap_report"]["architecture_gaps"],
        )

    def test_probe_prefers_direct_lifecycle_events_over_legacy_inference(self):
        signal = {
            "signal_id": "sig_direct",
            "title": "Direct signal",
            "source": "rss",
            "status": "saved",
            "saved_reason": "Worth a later look",
            "published_at": "2026-05-19T15:23:22+00:00",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }
        lifecycle_events = [
            {
                "event_id": "sig_evt_1",
                "event_type": "signal_status_changed",
                "event_time": "2026-05-23T00:00:00+00:00",
                "actor": {"type": "system", "id": "ai-radar-backend"},
                "source_ref": {"record_family": "signal", "record_id": "sig_direct"},
                "state": {"before": "pending", "after": "saved"},
                "support": {
                    "saved_reason": "Worth a later look",
                    "decision_trace_event": "operator_saved_for_later",
                },
            }
        ]

        result = build_signal_lifecycle_probe(signal, lifecycle_events=lifecycle_events)

        steps = {step["step_id"]: step for step in result["steps"]}
        self.assertEqual(steps["signal_decision"]["provenance"], "direct")
        self.assertEqual(steps["signal_decision"]["source"], "signal_lifecycle_event")
        self.assertEqual(steps["signal_decision"]["timestamp"], "2026-05-23T00:00:00+00:00")
        self.assertEqual(steps["signal_decision"]["actor"], "system:ai-radar-backend")
        self.assertEqual(steps["signal_decision"]["support"]["saved_reason"], "Worth a later look")
        self.assertNotIn("Status exists, but the transition event, actor, and timestamp are missing.", steps["signal_decision"]["gaps"])
        self.assertIn("signal_lifecycle.events", result["gap_report"]["direct_fields"])

    def test_probe_uses_derived_project_review_attachment_events_for_outcomes(self):
        signal = {
            "signal_id": "manual_123",
            "title": "Manual source",
            "source": "manual",
            "status": "completed",
            "analysis_status": "completed",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }
        lifecycle_events = [
            {
                "event_id": "sig_evt_project_1",
                "event_type": "project_review_attached",
                "event_time": "2026-05-24T00:00:00+00:00",
                "recorded_at": "2026-05-24T00:01:00+00:00",
                "actor": {"type": "system", "id": "signal_lifecycle_probe"},
                "provenance_class": "derived",
                "source_ref": {"record_family": "project_review_record", "record_id": "prv_1"},
                "state": {"before": "new", "after": "watch"},
                "project_ref": {
                    "project_id": "ai_radar",
                    "record_family": "project_review_record",
                    "record_id": "prv_1",
                    "outcome": "watch",
                },
                "support": {"blocked_downstream_actions": ["low_risk_action_candidate"]},
            }
        ]

        result = build_signal_lifecycle_probe(signal, lifecycle_events=lifecycle_events)

        steps = {step["step_id"]: step for step in result["steps"]}
        self.assertEqual(steps["project_fanout"]["source"], "derived_lifecycle_event")
        self.assertEqual(steps["project_fanout"]["provenance"], "derived")
        self.assertEqual(steps["project_outcomes"]["source"], "derived_lifecycle_event")
        self.assertEqual(steps["project_outcomes"]["support"]["outcomes"], ["watch"])
        self.assertIn("signal_lifecycle.project_review_attached", result["gap_report"]["direct_fields"])
        self.assertNotIn(
            "Signal-owned lifecycle history cannot yet show project outcomes without joining project-side records.",
            result["gap_report"]["architecture_gaps"],
        )

    def test_probe_keeps_missing_verification_visible(self):
        signal = {
            "signal_id": "sig_pending",
            "title": "Pending signal",
            "source": "rss",
            "status": "pending",
            "published_at": "2026-05-19T15:23:22+00:00",
        }

        result = build_signal_lifecycle_probe(signal)

        steps = {step["step_id"]: step for step in result["steps"]}
        self.assertEqual(steps["verification_gate"]["provenance"], "missing")
        self.assertEqual(steps["verification_gate"]["state"], "unknown")
        self.assertEqual(steps["signal_decision"]["state"], "waiting")
        self.assertIn(
            "Missing verification metadata cannot distinguish unverified legacy paths from not-yet-reviewed signals.",
            result["gap_report"]["architecture_gaps"],
        )


if __name__ == "__main__":
    unittest.main()
