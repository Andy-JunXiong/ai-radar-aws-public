import shutil
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_event_service import append_pipeline_run  # noqa: E402
from app.services.metrics_event_service import record_llm_call  # noqa: E402
from scripts.refresh_metrics_summaries import discover_metric_dates  # noqa: E402
from scripts.refresh_metrics_summaries import refresh_metrics_summaries  # noqa: E402


def _test_metrics_dir() -> Path:
    root = REPO_ROOT / "tmp_metrics_refresh_tests"
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    return path


def test_refresh_metrics_summaries_discovers_raw_dates_and_writes_rollups():
    metrics_dir = _test_metrics_dir()
    try:
        append_pipeline_run(
            {
                "date": "2026-05-04",
                "run_id": "run-2026-05-04",
                "success": True,
                "duration_seconds": 12,
                "error_count": 0,
                "artifact_written_count": 2,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-05",
                "task_type": "signal_insight",
                "success": True,
                "fallback_used": False,
                "estimated_cost": 0.03,
            },
            metrics_dir=metrics_dir,
        )

        dates = discover_metric_dates(metrics_dir)
        written = refresh_metrics_summaries(metrics_dir, dates)
        written_names = {path.name for path in written}

        assert dates == ["2026-05-04", "2026-05-05"]
        assert "2026-05-04.json" in written_names
        assert "2026-05-05.json" in written_names
        assert "2026-W19.json" in written_names
        assert "2026-05.json" in written_names
        assert (metrics_dir / "daily_summary" / "2026-05-04.json").exists()
        assert (metrics_dir / "daily_summary" / "2026-05-05.json").exists()
        assert (metrics_dir / "weekly_summary" / "2026-W19.json").exists()
        assert (metrics_dir / "monthly_summary" / "2026-05.json").exists()
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)
