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


class ProjectTakeawayCandidatesAppRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_project_takeaway_candidates_route_keeps_admin_guard(self):
        with patch("app.routes.projects.list_active_projects") as list_active_projects, patch(
            "app.routes.projects.load_project_improvements"
        ) as load_improvements:
            response = TestClient(app).get("/projects/takeaway-candidates")

        self.assertEqual(response.status_code, 401)
        list_active_projects.assert_not_called()
        load_improvements.assert_not_called()

    def test_project_takeaway_candidates_route_returns_items_when_authorized(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

        with patch(
            "app.routes.projects.list_active_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar"}],
        ), patch(
            "app.routes.projects.load_project_improvements",
            return_value={
                "updated_at": "2026-05-14T00:00:00+00:00",
                "items": [
                    {
                        "signal_id": "sig-1",
                        "signal_title": "Candidate one",
                        "status": "candidate",
                        "saved_at": "2026-05-14T00:00:00+00:00",
                    }
                ],
            },
        ):
            response = TestClient(app).get("/projects/takeaway-candidates")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "project takeaway candidates loaded successfully")
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["project_id"], "ai_radar")
        self.assertEqual(body["items"][0]["project_name"], "AI Radar")

    def test_project_workspace_view_only_returns_active_projects(self):
        with patch(
            "app.routes.projects.list_active_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar", "status": "active"}],
        ), patch(
            "app.routes.projects.load_project_improvements",
            return_value={"items": [{"signal_id": "sig-1", "status": "candidate"}]},
        ):
            response = TestClient(app).get("/projects/workspace-view")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["project"]["project_id"], "ai_radar")

    def test_reasoning_counter_check_route_persists_draft_when_authorized(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        draft = {
            "answer": "unclear",
            "summary": "The packet is underdetermined.",
            "boundary": "LLM advisory only.",
        }
        persisted_item = {
            "project_id": "ai_radar",
            "signal_id": "sig-counter-check",
            "reasoning_counter_check_draft": draft,
            "reasoning_counter_check_effect": "reviewer_advisory_only",
        }

        with patch("app.routes.projects.generate_reasoning_counter_check", return_value=draft) as generate, patch(
            "app.routes.projects.save_reasoning_counter_check_draft",
            return_value=persisted_item,
        ) as save:
            response = TestClient(app).post(
                "/projects/reasoning-counter-check",
                json={
                    "project_id": "ai_radar",
                    "signal_id": "sig-counter-check",
                    "takeaway": "Candidate takeaway",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["draft"], draft)
        self.assertEqual(body["item"], persisted_item)
        self.assertTrue(body["persisted"])
        generate.assert_called_once()
        save.assert_called_once_with("ai_radar", "sig-counter-check", draft)


if __name__ == "__main__":
    unittest.main()
