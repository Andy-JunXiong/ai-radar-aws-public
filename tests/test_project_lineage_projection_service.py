import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import project_lineage_projection_service as service  # noqa: E402


class ProjectLineageProjectionServiceTests(unittest.TestCase):
    def test_projection_keeps_related_events_and_preserves_audit_shape(self):
        record = {
            "id": "prv_current",
            "project_id": "ai_radar",
            "signal_id": "sig_1",
        }
        events = [
            {
                "id": "pce_outcome",
                "event_type": "watch_item_created",
                "project_id": "ai_radar",
                "signal_id": "sig_1",
                "review_record_id": "",
                "created_at": "2026-08-13T02:00:00+00:00",
            },
            {
                "id": "pce_current",
                "event_type": "review_record_created",
                "project_id": "ai_radar",
                "signal_id": "sig_1",
                "review_record_id": "prv_current",
                "created_at": "2026-08-13T01:00:00+00:00",
            },
            {
                "id": "pce_other_signal",
                "event_type": "review_record_created",
                "project_id": "ai_radar",
                "signal_id": "sig_2",
                "review_record_id": "prv_current",
                "created_at": "2026-08-13T03:00:00+00:00",
            },
            {
                "id": "pce_other_project",
                "event_type": "review_record_created",
                "project_id": "other_project",
                "signal_id": "sig_1",
                "review_record_id": "prv_current",
                "created_at": "2026-08-13T04:00:00+00:00",
            },
        ]

        result = service.build_review_record_lineage_projection(record, events)

        self.assertEqual(
            [event["id"] for event in result["related_calibration_events"]],
            ["pce_current", "pce_outcome"],
        )
        self.assertTrue(result["related_calibration_events"][0]["is_current_review_record_event"])
        self.assertFalse(result["related_calibration_events"][1]["is_current_review_record_event"])
        self.assertEqual(
            result["audit_summary"],
            {
                "event_count": 2,
                "has_review_record_created": True,
                "has_outcome_event": True,
                "matching_review_record_event_count": 1,
            },
        )

    def test_projection_is_deterministic_and_applies_limit_after_sorting(self):
        record = {
            "id": "prv_current",
            "project_id": "ai_radar",
            "signal_id": "sig_1",
        }
        events = [
            {
                "id": f"pce_{index:02d}",
                "event_type": "watch_item_created",
                "project_id": "ai_radar",
                "signal_id": "sig_1",
                "review_record_id": "prv_current" if index == 0 else "",
                "created_at": "2026-08-13T01:00:00+00:00",
            }
            for index in range(25)
        ]

        forward = service.build_review_record_lineage_projection(record, events)
        reversed_input = service.build_review_record_lineage_projection(record, list(reversed(events)))

        self.assertEqual(forward, reversed_input)
        self.assertEqual(forward["audit_summary"]["event_count"], 20)
        self.assertEqual(forward["audit_summary"]["matching_review_record_event_count"], 1)
        self.assertEqual(forward["related_calibration_events"][0]["id"], "pce_00")
        self.assertNotIn("pce_01", [event["id"] for event in forward["related_calibration_events"]])

    def test_zero_limit_returns_an_empty_compatible_projection(self):
        result = service.build_review_record_lineage_projection(
            {"id": "prv_current", "project_id": "ai_radar", "signal_id": "sig_1"},
            [
                {
                    "id": "pce_current",
                    "event_type": "review_record_created",
                    "project_id": "ai_radar",
                    "signal_id": "sig_1",
                    "review_record_id": "prv_current",
                }
            ],
            related_event_limit=0,
        )

        self.assertEqual(result["related_calibration_events"], [])
        self.assertEqual(
            result["audit_summary"],
            {
                "event_count": 0,
                "has_review_record_created": False,
                "has_outcome_event": False,
                "matching_review_record_event_count": 0,
            },
        )

    def test_missing_review_record_id_does_not_match_empty_event_reference(self):
        result = service.build_review_record_lineage_projection(
            {"project_id": "ai_radar", "signal_id": "sig_1"},
            [
                {
                    "id": "pce_legacy",
                    "event_type": "watch_item_created",
                    "project_id": "ai_radar",
                    "signal_id": "sig_1",
                    "review_record_id": "",
                }
            ],
        )

        self.assertFalse(result["related_calibration_events"][0]["is_current_review_record_event"])
        self.assertEqual(result["audit_summary"]["matching_review_record_event_count"], 0)


if __name__ == "__main__":
    unittest.main()
