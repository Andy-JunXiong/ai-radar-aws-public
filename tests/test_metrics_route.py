import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes.metrics import get_metrics_daily_summary  # noqa: E402
from app.routes.metrics import get_metrics_summaries  # noqa: E402
from app.routes.metrics import get_metrics_status  # noqa: E402


class MetricsRouteTests(unittest.TestCase):
    def test_get_metrics_daily_summary_returns_loaded_payload(self):
        payload = {
            "date": "2026-05-04",
            "summary": {"date": "2026-05-04", "pipeline": {"success": True}},
            "path": "data/output/metrics/daily_summary/2026-05-04.json",
            "exists": True,
        }

        with patch("app.routes.metrics.load_daily_metrics_summary", return_value=payload):
            result = get_metrics_daily_summary(date="2026-05-04")

        self.assertEqual(result["summary"]["pipeline"]["success"], True)
        self.assertEqual(result["message"], "metrics daily summary loaded successfully")

    def test_get_metrics_daily_summary_rejects_bad_date_format(self):
        with self.assertRaises(HTTPException) as ctx:
            get_metrics_daily_summary(date="05-04-2026")

        self.assertEqual(ctx.exception.status_code, 400)

    def test_get_metrics_daily_summary_raises_404_when_missing(self):
        with patch("app.routes.metrics.load_daily_metrics_summary", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                get_metrics_daily_summary(date="2026-05-04")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_metrics_status_returns_loaded_payload(self):
        payload = {
            "metrics_dir": "data/output/metrics",
            "has_any_metrics": True,
            "available_dates": ["2026-05-04"],
            "latest_summary_date": "2026-05-04",
            "latest_summary_path": "data/output/metrics/daily_summary/2026-05-04.json",
            "categories": {"daily_summary": {"exists": True}},
        }

        with patch("app.routes.metrics.load_metrics_status", return_value=payload):
            result = get_metrics_status()

        self.assertEqual(result["has_any_metrics"], True)
        self.assertEqual(result["latest_summary_date"], "2026-05-04")
        self.assertEqual(result["message"], "metrics status loaded successfully")

    def test_get_metrics_summaries_returns_loaded_payloads(self):
        payload = [{"date": "2026-05-13"}]

        with patch("app.routes.metrics.load_metrics_summaries", return_value=payload):
            result = get_metrics_summaries(
                category="daily_summary",
                through_date="2026-05-13",
                limit=5,
            )

        self.assertEqual(result["summaries"], payload)
        self.assertEqual(result["message"], "metrics summaries loaded successfully")

    def test_get_metrics_summaries_rejects_bad_category(self):
        with self.assertRaises(HTTPException) as ctx:
            get_metrics_summaries(category="bad", through_date=None, limit=5)

        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
