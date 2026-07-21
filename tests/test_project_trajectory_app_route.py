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


class ProjectTrajectoryAppRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_project_trajectory_events_route_is_mounted_on_fastapi_app(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        with patch(
            "app.routes.projects.list_project_review_records",
            return_value=[
                {
                    "id": "prv_manual",
                    "project_id": "ai_radar",
                    "signal_id": "manual_123",
                    "outcome": "watch",
                    "source_type": "manual_upload",
                    "is_manual_source": True,
                    "verification_status": "partially_verified",
                    "unsupported_claim_count": 1,
                    "reviewed_at": "2026-05-04T12:00:00+00:00",
                }
            ],
        ), patch("app.routes.projects.list_project_calibration_events", return_value=[]):
            response = TestClient(app).get(
                "/projects/trajectory-events?project_id=ai_radar&risk_level=risk&source_type=manual_upload"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["event_kind"], "review")
        self.assertEqual(body["items"][0]["risk_level"], "high")
        self.assertEqual(body["items"][0]["trajectory_signal_type"], "manual_judgment")
        self.assertEqual(body["summary"]["risk_mix"], {"high": 1})
        self.assertEqual(body["message"], "project trajectory events loaded successfully")

    def test_project_trajectory_events_route_keeps_admin_guard(self):
        with patch("app.routes.projects.list_project_review_records") as list_records, patch(
            "app.routes.projects.list_project_calibration_events"
        ) as list_events:
            response = TestClient(app).get("/projects/trajectory-events")

        self.assertEqual(response.status_code, 401)
        list_records.assert_not_called()
        list_events.assert_not_called()


if __name__ == "__main__":
    unittest.main()
