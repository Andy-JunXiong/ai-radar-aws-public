from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_event_service import append_pipeline_run  # noqa: E402
from app.services.metrics_event_service import record_collector_run  # noqa: E402
from app.services.metrics_event_service import record_llm_call  # noqa: E402
from app.services.metrics_event_service import record_verification_event  # noqa: E402
from app.services.metrics_summary_service import write_daily_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_monthly_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_weekly_metrics_summary  # noqa: E402


SAMPLE_DATE = "2026-05-04"
SAMPLE_RUN_ID = "sample-local-metrics-run"
SAMPLE_MONTH = "2026-05"
SAMPLE_WEEK = "2026-W19"


def main() -> int:
    append_pipeline_run(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "started_at": "2026-05-04T01:00:00Z",
            "finished_at": "2026-05-04T01:07:00Z",
            "duration_seconds": 420,
            "success": True,
            "error_count": 0,
            "artifact_written_count": 8,
        }
    )

    record_collector_run(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "collector_name": "rss_collector",
            "duration_seconds": 3.2,
            "success": True,
            "items_fetched": 120,
            "items_normalized": 110,
            "items_written": 42,
            "error_count": 0,
            "retry_count": 0,
        }
    )
    record_collector_run(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "collector_name": "official_collector",
            "duration_seconds": 1.7,
            "success": False,
            "items_fetched": 0,
            "items_normalized": 0,
            "items_written": 0,
            "error_count": 1,
            "retry_count": 1,
        }
    )

    record_llm_call(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "task_type": "signal_insight",
            "provider": "openai",
            "model": "gpt-test",
            "latency_ms": 8200,
            "success": True,
            "error_type": None,
            "fallback_used": False,
            "retry_count": 0,
            "input_tokens": 1200,
            "output_tokens": 420,
            "estimated_cost": 0.08,
            "json_validation_passed": True,
            "json_repair_used": False,
        }
    )
    record_llm_call(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "task_type": "verified_insight_generation",
            "provider": "anthropic",
            "model": "claude-test",
            "latency_ms": 10400,
            "success": True,
            "error_type": None,
            "fallback_used": True,
            "retry_count": 1,
            "input_tokens": 1600,
            "output_tokens": 520,
            "estimated_cost": 0.11,
            "json_validation_passed": True,
            "json_repair_used": True,
        }
    )

    record_verification_event(
        {
            "run_id": SAMPLE_RUN_ID,
            "date": SAMPLE_DATE,
            "signal_id": "sample-signal-1",
            "verified_insight_id": "sample-verified-insight-1",
            "evidence_level": "moderate",
            "verification_status": "partially_verified",
            "claim_count": 5,
            "unsupported_claim_count": 1,
            "inferred_claim_count": 1,
            "downgrade_applied": True,
            "allowed_downstream_actions": ["watch_only"],
            "blocked_downstream_actions": ["action"],
        }
    )

    daily_summary_path = write_daily_metrics_summary(SAMPLE_DATE)
    weekly_summary_path = write_weekly_metrics_summary(SAMPLE_WEEK)
    monthly_summary_path = write_monthly_metrics_summary(SAMPLE_MONTH)
    print(f"sample daily metrics written: {daily_summary_path}")
    print(f"sample weekly metrics written: {weekly_summary_path}")
    print(f"sample monthly metrics written: {monthly_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
