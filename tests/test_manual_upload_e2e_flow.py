import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.routes import manual as manual_route  # noqa: E402
from app.routes import signals as signals_route  # noqa: E402
from app.services import (  # noqa: E402
    project_calibration_event_service,
    project_intelligence_service,
    project_review_record_service,
    project_trajectory_event_service,
    reflection_service,
    strategic_synthesis_service,
)


TEST_TMP_ROOT = REPO_ROOT / ".tmp-tests"


@contextmanager
def manual_e2e_temp_dir():
    path = TEST_TMP_ROOT / f"manual_e2e_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ManualUploadE2EFlowTests(unittest.TestCase):
    def test_manual_upload_review_record_trajectory_knowledge_and_reflection_loop(self):
        with manual_e2e_temp_dir() as temp_dir, patch.object(
            manual_route,
            "UPLOAD_DIR",
            temp_dir / "manual_uploads",
        ), patch.object(
            manual_route,
            "SESSIONS_DIR",
            temp_dir / "manual_uploads" / "sessions",
        ), patch.object(
            manual_route,
            "SESSIONS_INDEX_PATH",
            temp_dir / "manual_uploads" / "sessions" / "index.json",
        ), patch.object(
            manual_route,
            "resolve_analysis_context",
            return_value=({}, "test"),
        ), patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir / "project_improvements",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "list_projects",
            return_value=[
                {
                    "project_id": "ai_radar",
                    "name": "AI Radar",
                    "status": "active",
                    "topics": ["manual upload", "project review", "trajectory"],
                }
            ],
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            reflection_service,
            "MANUAL_SESSIONS_DIR",
            temp_dir / "manual_uploads" / "sessions",
        ):
            manual_route.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            manual_route.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            project_intelligence_service.PROJECT_IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
            (manual_route.UPLOAD_DIR / "manual-e2e-note.md").write_text(
                "Manual upload material about project review and trajectory memory.\n"
                "This sentence should be preserved as source evidence for Generate Insight.",
                encoding="utf-8",
            )

            session = manual_route.create_manual_session(
                [
                    {
                        "original_filename": "manual-e2e-note.md",
                        "stored_filename": "manual-e2e-note.md",
                        "file_kind": "text",
                        "preview_text": "Manual upload material about project review and trajectory memory.",
                    }
                ],
                upload_reason="Validate manual E2E handoff",
                intended_use="Project review and trajectory validation",
                cognitive_layer="L2",
            )

            analysis = {
                "summary": "Manual upload shows how review records should preserve source context.",
                "why_it_matters": "It validates the human-selected material path.",
                "relevance_to_projects": {"AI Radar": "Use this to verify Project Review and Trajectory handoff."},
                "relevance_to_career": "Demonstrates operating discipline.",
                "synthesized_insight": "Manual material can become review memory without becoming factual evidence.",
                "topic": "project review trajectory",
            }
            manual_route.update_session_analysis(session["session_id"], analysis)
            completed_session = manual_route.load_session_detail(session["session_id"])

            manual_signal = signals_route.normalize_manual_session(completed_session, 0)
            review_signal_id = f"manual_{manual_signal['manual_session_id']}"
            self.assertEqual(manual_signal["signal_id"], session["session_id"])
            self.assertEqual(manual_signal["manual_session_id"], session["session_id"])
            self.assertEqual(manual_signal["upload_reason"], "Validate manual E2E handoff")
            self.assertEqual(manual_signal["intended_use"], "Project review and trajectory validation")
            self.assertEqual(manual_signal["cognitive_layer"], "L2")
            self.assertIn(
                "This sentence should be preserved as source evidence",
                manual_signal["source_excerpt"],
            )
            self.assertGreater(manual_signal["source_excerpt_length"], 0)

            verification_metadata = {
                "verification_status": "partially_verified",
                "confidence_label": "medium",
                "confidence_score": 0.62,
                "upload_reason": completed_session["upload_reason"],
                "intended_use": completed_session["intended_use"],
                "cognitive_layer": completed_session["cognitive_layer"],
                "claim_support_summary": {"inferred": 1},
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": ["low_risk_action_candidate", "strong_recommendation"],
            }

            written = project_intelligence_service.add_signal_to_project_improvements(
                signal_id=review_signal_id,
                signal_title=manual_signal["title"],
                signal_summary=analysis["summary"],
                why_it_matters=analysis["why_it_matters"],
                relevance_to_projects=analysis["relevance_to_projects"],
                synthesized_insight=analysis["synthesized_insight"],
                final_reflection="Review manually selected material without bypassing verification gates.",
                subscription_project_links=[{"project_id": "ai_radar", "enabled": True, "source": "manual_upload"}],
                verification_metadata=verification_metadata,
                candidate_source="manual_upload",
                status="candidate",
            )

            self.assertEqual(len(written), 1)
            self.assertEqual(written[0]["project_id"], "ai_radar")
            self.assertEqual(written[0]["source_type"], "manual_upload")
            self.assertEqual(written[0]["manual_session_id"], session["session_id"])

            reviewed = project_intelligence_service.close_project_takeaway_candidate(
                "ai_radar",
                review_signal_id,
                status="watch",
                reason="Watch this manual-source material before action.",
                review_date="2026-06-01",
                success_criteria="Independent evidence appears.",
            )

            self.assertEqual(reviewed["review_outcome"], "watch")
            records = project_review_record_service.list_project_review_records(project_id="ai_radar", signal_id=review_signal_id)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertTrue(record["is_manual_source"])
            self.assertEqual(record["upload_reason"], "Validate manual E2E handoff")
            self.assertEqual(record["intended_use"], "Project review and trajectory validation")
            self.assertEqual(record["cognitive_layer"], "L2")
            self.assertEqual(record["outcome"], "watch")
            self.assertIn("low_risk_action_candidate", record["blocked_downstream_actions"])

            calibration_events = project_calibration_event_service.list_project_calibration_events(
                project_id="ai_radar",
                signal_id=review_signal_id,
            )
            event_types = {event["event_type"] for event in calibration_events}
            self.assertIn("review_record_created", event_types)
            self.assertIn("watch_item_created", event_types)

            trajectory = project_trajectory_event_service.build_trajectory_events_response(records, calibration_events)
            self.assertEqual(trajectory["summary"]["manual_count"], len(trajectory["items"]))
            self.assertEqual(
                trajectory["summary"]["manual_intent_summary"]["upload_reason_mix"],
                [{"value": "Validate manual E2E handoff", "count": len(trajectory["items"])}],
            )
            self.assertEqual(trajectory["summary"]["signal_type_mix"]["manual_judgment"], len(trajectory["items"]))

            review_summary = project_review_record_service.summarize_project_review_records(project_id="ai_radar")
            calibration_summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_radar")
            knowledge = strategic_synthesis_service.build_strategic_synthesis_response(
                radar_intelligence={},
                review_summary=review_summary,
                calibration_summary=calibration_summary,
                projects=[{"project_id": "ai_radar", "name": "AI Radar", "topics": ["project review", "trajectory"]}],
            )
            self.assertEqual(
                knowledge["summary"]["manual_source_event_count"],
                review_summary["manual_record_count"] + calibration_summary["manual_event_count"],
            )
            self.assertTrue(
                any("manual-source review/calibration events" in item for item in knowledge["review_quality"]["ops_summary"]["achieved"])
            )

            fake_reflection_index = SimpleNamespace(
                reflections=[
                    SimpleNamespace(
                        id="refl_manual_e2e",
                        title="Project review trajectory note",
                        tags=["project review", "trajectory"],
                    )
                ]
            )
            with patch.object(reflection_service, "load_reflection_index", return_value=fake_reflection_index):
                related_manual_sessions = reflection_service.get_related_manual_sessions("refl_manual_e2e", limit=5)

            self.assertEqual(len(related_manual_sessions), 1)
            self.assertEqual(related_manual_sessions[0]["session_id"], session["session_id"])
            self.assertEqual(related_manual_sessions[0]["upload_reason"], "Validate manual E2E handoff")
            self.assertEqual(related_manual_sessions[0]["intended_use"], "Project review and trajectory validation")
            self.assertEqual(related_manual_sessions[0]["cognitive_layer"], "L2")


if __name__ == "__main__":
    unittest.main()
