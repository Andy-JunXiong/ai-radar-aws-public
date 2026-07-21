import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_summary_service import load_metrics_status  # noqa: E402
from app.services.metrics_summary_service import load_metrics_summaries  # noqa: E402


class MetricsDailyFallbackTests(unittest.TestCase):
    def test_daily_summary_history_falls_back_to_signal_activity_without_written_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            metrics_dir = output_dir / "metrics"
            metrics_dir.mkdir(parents=True)
            (output_dir / "signals.json").write_text(
                json.dumps(
                    [
                        {
                            "signal_id": "sig-1",
                            "source": "aws",
                            "status": "pending",
                            "collected_at": "2026-05-15T07:32:21+10:00",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            summaries = load_metrics_summaries(
                "daily_summary",
                through_date="2026-05-15",
                limit=5,
                metrics_dir=metrics_dir,
            )
            status = load_metrics_status(metrics_dir=metrics_dir)

        self.assertEqual([summary["date"] for summary in summaries], ["2026-05-15"])
        self.assertEqual(summaries[0]["signals"]["collected_count"], 1)
        self.assertEqual(status["latest_signal_activity_date"], "2026-05-15")
        self.assertIn("2026-05-15", status["available_dates"])
        self.assertIn("2026-05-15", status["missing_summary_dates"])
        self.assertTrue(status["has_any_metrics"])

    def test_weekly_and_monthly_history_fall_back_to_signal_activity_without_written_summaries(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            metrics_dir = output_dir / "metrics"
            metrics_dir.mkdir(parents=True)
            (output_dir / "signals.json").write_text(
                json.dumps(
                    [
                        {
                            "signal_id": "sig-1",
                            "source": "aws",
                            "status": "pending",
                            "collected_at": "2026-05-14T07:32:21+10:00",
                        },
                        {
                            "signal_id": "sig-2",
                            "source": "nvidia_blog",
                            "status": "pending",
                            "collected_at": "2026-05-15T07:32:21+10:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            weekly = load_metrics_summaries(
                "weekly_summary",
                through_date="2026-05-15",
                limit=5,
                metrics_dir=metrics_dir,
            )
            monthly = load_metrics_summaries(
                "monthly_summary",
                through_date="2026-05-15",
                limit=5,
                metrics_dir=metrics_dir,
            )

        self.assertEqual([summary["period_id"] for summary in weekly], ["2026-W20"])
        self.assertEqual(weekly[0]["date_count"], 2)
        self.assertEqual(weekly[0]["signals"]["collected_count"], 2)
        self.assertEqual([summary["period_id"] for summary in monthly], ["2026-05"])
        self.assertEqual(monthly[0]["date_count"], 2)
        self.assertEqual(monthly[0]["signals"]["collected_count"], 2)

    def test_period_history_fallback_honors_through_date(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            metrics_dir = output_dir / "metrics"
            metrics_dir.mkdir(parents=True)
            (output_dir / "signals.json").write_text(
                json.dumps(
                    [
                        {
                            "signal_id": "sig-1",
                            "source": "aws",
                            "status": "pending",
                            "collected_at": "2026-05-14T07:32:21+10:00",
                        },
                        {
                            "signal_id": "sig-2",
                            "source": "nvidia_blog",
                            "status": "pending",
                            "collected_at": "2026-05-15T07:32:21+10:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            weekly = load_metrics_summaries(
                "weekly_summary",
                through_date="2026-05-14",
                limit=5,
                metrics_dir=metrics_dir,
            )
            monthly = load_metrics_summaries(
                "monthly_summary",
                through_date="2026-05-14",
                limit=5,
                metrics_dir=metrics_dir,
            )

        self.assertEqual(weekly[0]["dates"], ["2026-05-14"])
        self.assertEqual(monthly[0]["dates"], ["2026-05-14"])


if __name__ == "__main__":
    unittest.main()
