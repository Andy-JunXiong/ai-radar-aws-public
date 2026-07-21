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


class MetricsAppRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_metrics_daily_summary_route_is_mounted_on_fastapi_app(self):
        payload = {
            "date": "2026-05-04",
            "summary": {
                "date": "2026-05-04",
                "pipeline": {"success": True},
                "collectors": {"total_runs": 1},
                "llm": {"call_count": 2},
                "verification": {"verified_insight_count": 1},
            },
            "path": "data/output/metrics/daily_summary/2026-05-04.json",
            "exists": True,
        }

        app.dependency_overrides[require_admin_auth] = lambda: None
        with patch("app.routes.metrics.load_daily_metrics_summary", return_value=payload):
            response = TestClient(app).get("/metrics/daily-summary?date=2026-05-04")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-05-04")
        self.assertEqual(body["summary"]["llm"]["call_count"], 2)
        self.assertEqual(body["message"], "metrics daily summary loaded successfully")

    def test_metrics_daily_summary_route_keeps_admin_guard(self):
        with patch("app.routes.metrics.load_daily_metrics_summary") as mock_loader:
            response = TestClient(app).get("/metrics/daily-summary?date=2026-05-04")

        self.assertEqual(response.status_code, 401)
        mock_loader.assert_not_called()

    def test_metrics_status_route_is_mounted_on_fastapi_app(self):
        payload = {
            "metrics_dir": "data/output/metrics",
            "has_any_metrics": True,
            "available_dates": ["2026-05-04"],
            "latest_summary_date": "2026-05-04",
            "latest_summary_path": "data/output/metrics/daily_summary/2026-05-04.json",
            "categories": {"daily_summary": {"exists": True}},
        }

        app.dependency_overrides[require_admin_auth] = lambda: None
        with patch("app.routes.metrics.load_metrics_status", return_value=payload):
            response = TestClient(app).get("/metrics/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["has_any_metrics"], True)
        self.assertEqual(body["latest_summary_date"], "2026-05-04")
        self.assertEqual(body["message"], "metrics status loaded successfully")

    def test_metrics_status_route_keeps_admin_guard(self):
        with patch("app.routes.metrics.load_metrics_status") as mock_loader:
            response = TestClient(app).get("/metrics/status")

        self.assertEqual(response.status_code, 401)
        mock_loader.assert_not_called()

    def test_metrics_summaries_route_is_mounted_on_fastapi_app(self):
        payload = [{"date": "2026-05-13"}]

        app.dependency_overrides[require_admin_auth] = lambda: None
        with patch("app.routes.metrics.load_metrics_summaries", return_value=payload):
            response = TestClient(app).get(
                "/metrics/summaries?category=daily_summary&through_date=2026-05-13&limit=5",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summaries"], payload)
        self.assertEqual(body["message"], "metrics summaries loaded successfully")

    def test_metrics_summaries_route_keeps_admin_guard(self):
        with patch("app.routes.metrics.load_metrics_summaries") as mock_loader:
            response = TestClient(app).get("/metrics/summaries")

        self.assertEqual(response.status_code, 401)
        mock_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
