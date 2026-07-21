import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402


def provenance(model_id="gpt-5.5"):
    return {
        "provider": "openai",
        "model_id": model_id,
        "task_type": "insight",
        "route_key": "insight.synthesize",
        "prompt_template_id": "signal_insight",
        "prompt_template_version": "v1",
        "deterministic_fingerprint": "d" * 64,
        "provenance_schema_version": 1,
    }


class ModelAttributionAnalyticsAppRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_model_attribution_summary_route_keeps_admin_guard(self):
        with patch("app.routes.projects.list_projects") as list_projects, patch(
            "app.routes.projects.list_project_review_records"
        ) as list_records, patch(
            "app.routes.projects.list_project_calibration_events"
        ) as list_events:
            response = TestClient(app).get("/projects/model-attribution/summary")

        self.assertEqual(response.status_code, 401)
        list_projects.assert_not_called()
        list_records.assert_not_called()
        list_events.assert_not_called()

    def test_model_attribution_summary_route_returns_admin_summary(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

        with patch(
            "app.routes.projects.list_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar"}],
        ), patch(
            "app.routes.projects.load_project_improvements",
            return_value={
                "items": [
                    {
                        "signal_id": "sig-1",
                        "status": "candidate",
                        "produced_by_model": provenance(),
                        "verification_metadata": {
                            "verification_status": "not_verifiable",
                            "review_priority": "do not act",
                            "blocked_downstream_actions": ["project_takeaway_candidate"],
                        },
                    },
                    {
                        "signal_id": "sig-2",
                        "status": "candidate",
                    },
                ]
            },
        ), patch(
            "app.routes.projects.list_project_review_records",
            return_value=[
                {
                    "signal_id": "sig-1",
                    "outcome": "watch",
                    "produced_by_model": provenance(),
                }
            ],
        ), patch(
            "app.routes.projects.list_project_calibration_events",
            return_value=[],
        ):
            response = TestClient(app).get("/projects/model-attribution/summary?project_id=ai_radar&days=7")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        summary = body["summary"]
        self.assertEqual(body["message"], "project model attribution summary loaded successfully")
        self.assertEqual(summary["scope"]["days"], 7)
        self.assertEqual(summary["scope"]["project_id"], "ai_radar")
        self.assertEqual(summary["coverage"]["total_records"], 3)
        self.assertEqual(summary["coverage"]["v1_records"], 2)
        self.assertEqual(summary["coverage"]["legacy_v0_records"], 1)
        self.assertEqual(summary["by_model"][0]["model_id"], "gpt-5.5")
        self.assertEqual(summary["review_outcomes"][0]["outcome"], "watch")
        self.assertEqual(summary["gate_outcomes"][0]["verification_status"], "not_verifiable")

    def test_model_attribution_summary_route_filters_candidates_by_signal_id(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

        with patch(
            "app.routes.projects.list_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar"}],
        ), patch(
            "app.routes.projects.load_project_improvements",
            return_value={
                "items": [
                    {"signal_id": "sig-1", "produced_by_model": provenance()},
                    {"signal_id": "sig-2"},
                ]
            },
        ), patch(
            "app.routes.projects.list_project_review_records",
            return_value=[],
        ) as list_records, patch(
            "app.routes.projects.list_project_calibration_events",
            return_value=[],
        ) as list_events:
            response = TestClient(app).get(
                "/projects/model-attribution/summary?project_id=ai_radar&signal_id=sig-2"
            )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["coverage"]["total_records"], 1)
        self.assertEqual(summary["coverage"]["legacy_v0_records"], 1)
        list_records.assert_called_once_with(project_id="ai_radar", signal_id="sig-2")
        list_events.assert_called_once_with(project_id="ai_radar", signal_id="sig-2")


if __name__ == "__main__":
    unittest.main()
