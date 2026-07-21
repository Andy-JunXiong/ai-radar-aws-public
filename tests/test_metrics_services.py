import json
import shutil
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_event_service import (  # noqa: E402
    append_pipeline_run,
    record_artifact_write,
    record_collector_run,
    record_llm_call,
    record_signal_timeline_load,
    record_verification_event,
)
from app.services.metrics_summary_service import build_daily_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import build_monthly_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import build_weekly_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import load_daily_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import load_metrics_summaries  # noqa: E402
from app.services.metrics_summary_service import load_metrics_status  # noqa: E402
from app.services.metrics_summary_service import write_daily_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_monthly_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_weekly_metrics_summary  # noqa: E402
import app.services.metrics_summary_service as metrics_summary_module  # noqa: E402


def _test_metrics_dir() -> Path:
    root = REPO_ROOT / "tmp_metrics_tests"
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    return path


def test_metrics_events_are_file_backed_and_append_only():
    metrics_dir = _test_metrics_dir()
    try:
        append_pipeline_run(
            {
                "run_id": "run-1",
                "date": "2026-05-04",
                "started_at": "2026-05-04T01:00:00Z",
                "finished_at": "2026-05-04T01:02:00Z",
                "duration_seconds": 120,
                "success": True,
                "error_count": 0,
                "artifact_written_count": 3,
            },
            metrics_dir=metrics_dir,
        )
        append_pipeline_run(
            {
                "run_id": "run-2",
                "date": "2026-05-04",
                "duration_seconds": 60,
                "success": False,
                "error_count": 1,
                "artifact_written_count": 1,
            },
            metrics_dir=metrics_dir,
        )
        record_artifact_write(
            {
                "date": "2026-05-04",
                "run_id": "run-1",
                "artifact_name": "signals",
                "path": "data/output/signals.json",
                "size_bytes": 100,
                "success": True,
            },
            metrics_dir=metrics_dir,
        )
        record_collector_run(
            {
                "run_id": "run-2",
                "collector_name": "rss_collector",
                "date": "2026-05-04",
                "duration_seconds": 2.5,
                "success": True,
                "items_fetched": 10,
                "items_normalized": None,
                "items_written": 10,
                "error_count": 0,
                "retry_count": 0,
            },
            metrics_dir=metrics_dir,
        )
        record_signal_timeline_load(
            {
                "date": "2026-05-04",
                "route": "/signals",
                "success": True,
                "duration_ms": 320,
                "returned_count": 10,
                "total_count": 12,
                "load_source": "s3",
            },
            metrics_dir=metrics_dir,
        )

        pipeline_payload = json.loads(
            (metrics_dir / "pipeline_runs" / "2026-05-04.json").read_text(
                encoding="utf-8"
            )
        )
        collector_lines = (
            metrics_dir / "collector_runs" / "2026-05-04.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        timeline_lines = (
            metrics_dir / "signal_timeline_loads" / "2026-05-04.jsonl"
        ).read_text(encoding="utf-8").splitlines()

        assert [item["run_id"] for item in pipeline_payload] == ["run-1", "run-2"]
        assert len(collector_lines) == 1
        assert json.loads(collector_lines[0])["collector_name"] == "rss_collector"
        assert json.loads(timeline_lines[0])["load_source"] == "s3"
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_daily_metrics_summary_aggregates_available_event_families():
    metrics_dir = _test_metrics_dir()
    try:
        (metrics_dir.parent / "signals.json").write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "signal_id": "sig-a",
                            "source": "rss",
                            "collected_at": "2026-05-04T09:00:00+10:00",
                            "published_at": "2026-05-04T01:00:00Z",
                        },
                        {
                            "signal_id": "sig-b",
                            "source": "official",
                            "collected_at": "2026-05-04T10:00:00+10:00",
                            "published_at": "2026-05-03T01:00:00Z",
                        },
                        {
                            "signal_id": "sig-c",
                            "source": "rss",
                            "collected_at": "2026-05-05T09:00:00+10:00",
                            "published_at": "2026-05-04T02:00:00Z",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        append_pipeline_run(
            {
                "run_id": "run-1",
                "date": "2026-05-04",
                "duration_seconds": 420,
                "success": True,
                "error_count": 0,
                "artifact_written_count": 8,
            },
            metrics_dir=metrics_dir,
        )
        record_artifact_write(
            {
                "date": "2026-05-04",
                "run_id": "run-1",
                "artifact_name": "signals",
                "path": "data/output/signals.json",
                "size_bytes": 100,
                "success": True,
            },
            metrics_dir=metrics_dir,
        )
        record_collector_run(
            {
                "date": "2026-05-04",
                "collector_name": "rss_collector",
                "success": True,
                "items_fetched": 12,
                "items_normalized": 12,
                "items_written": 12,
                "error_count": 0,
                "retry_count": 0,
            },
            metrics_dir=metrics_dir,
        )
        record_collector_run(
            {
                "date": "2026-05-04",
                "collector_name": "official_collector",
                "success": False,
                "items_fetched": 0,
                "items_normalized": 0,
                "items_written": 0,
                "error_count": 1,
                "retry_count": 0,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-04",
                "task_type": "signal_insight",
                "provider": "openai",
                "model": "gpt-test",
                "latency_ms": 1000,
                "success": True,
                "fallback_used": False,
                "retry_count": 2,
                "estimated_cost": 0.01,
                "json_validation_passed": True,
                "json_repair_used": False,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-04",
                "task_type": "signal_insight",
                "provider": "openai",
                "model": "gpt-test",
                "latency_ms": 3000,
                "success": False,
                "fallback_used": True,
                "retry_count": 1,
                "estimated_cost": 0.03,
                "json_validation_passed": False,
                "json_repair_used": True,
            },
            metrics_dir=metrics_dir,
        )
        record_signal_timeline_load(
            {
                "date": "2026-05-04",
                "route": "/signals",
                "success": True,
                "duration_ms": 630,
                "returned_count": 42,
                "total_count": 42,
                "latest_published_date": "2026-05-04",
                "latest_collected_date": "2026-05-04",
                "load_source": "s3",
                "local_snapshot_status": "stale",
                "local_snapshot_reason": "content_timestamp_too_old",
            },
            metrics_dir=metrics_dir,
        )
        record_signal_timeline_load(
            {
                "date": "2026-05-04",
                "route": "/signals",
                "success": True,
                "duration_ms": 20500,
                "returned_count": 42,
                "total_count": 42,
                "load_source": "runtime_cache",
                "local_snapshot_status": "loaded",
            },
            metrics_dir=metrics_dir,
        )
        record_verification_event(
            {
                "date": "2026-05-04",
                "signal_id": "sig-1",
                "verified_insight_id": "vi-1",
                "evidence_level": "thin",
                "verification_status": "partially_verified",
                "claim_count": 4,
                "unsupported_claim_count": 1,
                "inferred_claim_count": 1,
                "downgrade_applied": True,
                "allowed_downstream_actions": ["watch_only"],
                "blocked_downstream_actions": ["action"],
            },
            metrics_dir=metrics_dir,
        )

        summary = build_daily_metrics_summary("2026-05-04", metrics_dir=metrics_dir)

        assert summary["pipeline"]["success"] is True
        assert summary["pipeline"]["duration_seconds"] == 420
        assert summary["artifacts"]["write_count"] == 1
        assert summary["artifacts"]["signals_file_written"] is True
        assert summary["artifacts"]["daily_radar_file_written"] is False
        assert summary["artifacts"]["total_bytes"] == 100
        assert summary["collectors"]["total_runs"] == 2
        assert summary["collectors"]["success_rate"] == 0.5
        assert summary["collectors"]["failed_collectors"] == ["official_collector"]
        assert summary["signals"]["collected_count"] == 2
        assert summary["signals"]["published_count"] == 2
        assert summary["signals"]["latest_collected_at"] == "2026-05-04T10:00:00+10:00"
        assert summary["signals"]["source_count"] == 2
        assert summary["llm"]["call_count"] == 2
        assert summary["llm"]["fallback_rate"] == 0.5
        assert summary["llm"]["error_count"] == 1
        assert summary["llm"]["retry_count"] == 3
        assert summary["llm"]["avg_latency_ms"] == 2000
        assert summary["llm"]["estimated_cost"] == 0.04
        assert summary["llm"]["estimated_cost_per_verified_insight"] == 0.04
        assert summary["llm"]["json_validation_pass_rate"] == 0.5
        assert summary["llm"]["json_repair_count"] == 1
        assert summary["timeline_loads"]["load_count"] == 2
        assert summary["timeline_loads"]["success_rate"] == 1
        assert summary["timeline_loads"]["avg_duration_ms"] == 10565
        assert summary["timeline_loads"]["slow_load_count"] == 1
        assert summary["timeline_loads"]["stale_local_snapshot_count"] == 1
        assert summary["timeline_loads"]["source_mix"] == {"s3": 1, "runtime_cache": 1}
        assert summary["verification"]["downgrade_rate"] == 1.0
        assert summary["verification"]["unsupported_claim_rate"] == 0.25
        assert summary["verification"]["watch_only_count"] == 1
        assert summary["verification"]["action_blocked_count"] == 1
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_daily_metrics_summary_falls_back_to_raw_events_read_only():
    metrics_dir = _test_metrics_dir()
    try:
        record_collector_run(
            {
                "date": "2026-05-04",
                "collector_name": "rss_collector",
                "success": True,
                "items_fetched": 4,
                "items_normalized": 4,
                "items_written": 4,
                "error_count": 0,
                "retry_count": 0,
            },
            metrics_dir=metrics_dir,
        )

        payload = load_daily_metrics_summary("2026-05-04", metrics_dir=metrics_dir)

        assert payload is not None
        assert payload["date"] == "2026-05-04"
        assert payload["exists"] is False
        assert payload["summary"]["collectors"]["total_runs"] == 1
        assert not (metrics_dir / "daily_summary" / "2026-05-04.json").exists()
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_daily_metrics_summary_prefers_s3_when_available(monkeypatch):
    payload = {
        "date": "2026-05-13",
        "pipeline": {"run_count": 1, "success": True},
    }

    monkeypatch.setattr(
        metrics_summary_module,
        "_read_s3_metrics_json",
        lambda key: payload if key == "metrics/daily_summary/2026-05-13.json" else None,
    )

    loaded = load_daily_metrics_summary("2026-05-13")

    assert loaded is not None
    assert loaded["data_source"] == "s3"
    assert loaded["path"] == "metrics/daily_summary/2026-05-13.json"
    assert loaded["summary"]["pipeline"]["run_count"] == 1


def test_weekly_and_monthly_metrics_summary_roll_up_daily_summaries():
    metrics_dir = _test_metrics_dir()
    try:
        (metrics_dir.parent / "signals.json").write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "signal_id": "sig-1",
                            "source": "rss",
                            "collected_at": "2026-05-04T09:00:00+10:00",
                            "published_at": "2026-05-04T01:00:00Z",
                        },
                        {
                            "signal_id": "sig-2",
                            "source": "official",
                            "collected_at": "2026-05-05T09:00:00+10:00",
                            "published_at": "2026-05-05T01:00:00Z",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        for date, success, cost in [
            ("2026-05-04", True, 0.04),
            ("2026-05-05", False, 0.06),
        ]:
            append_pipeline_run(
                {
                    "date": date,
                    "run_id": f"run-{date}",
                    "success": success,
                    "duration_seconds": 100,
                    "error_count": 0 if success else 1,
                    "artifact_written_count": 2,
                },
                metrics_dir=metrics_dir,
            )
            record_artifact_write(
                {
                    "date": date,
                    "run_id": f"run-{date}",
                    "artifact_name": "signals" if success else "daily_radar",
                    "path": f"data/output/{date}.json",
                    "size_bytes": 50,
                    "success": True,
                },
                metrics_dir=metrics_dir,
            )
            record_collector_run(
                {
                    "date": date,
                    "collector_name": "rss_collector",
                    "success": success,
                    "items_fetched": 10,
                    "items_normalized": 8,
                    "items_written": 4,
                    "error_count": 0 if success else 1,
                    "retry_count": 0 if success else 1,
                },
                metrics_dir=metrics_dir,
            )
            record_llm_call(
                {
                    "date": date,
                    "task_type": "signal_insight",
                    "success": True,
                    "fallback_used": not success,
                    "retry_count": 0 if success else 1,
                    "latency_ms": 1000 if success else 3000,
                    "estimated_cost": cost,
                    "json_validation_passed": success,
                    "json_repair_used": not success,
                },
                metrics_dir=metrics_dir,
            )
            record_verification_event(
                {
                    "date": date,
                    "signal_id": f"sig-{date}",
                    "verified_insight_id": f"vi-{date}",
                    "claim_count": 5,
                    "unsupported_claim_count": 1,
                    "downgrade_applied": not success,
                    "allowed_downstream_actions": ["watch_only"],
                    "blocked_downstream_actions": ["action"] if not success else [],
                },
                metrics_dir=metrics_dir,
            )
            write_daily_metrics_summary(date, metrics_dir=metrics_dir)

        weekly_summary = build_weekly_metrics_summary("2026-W19", metrics_dir=metrics_dir)
        monthly_summary = build_monthly_metrics_summary("2026-05", metrics_dir=metrics_dir)
        weekly_path = write_weekly_metrics_summary("2026-W19", metrics_dir=metrics_dir)
        monthly_path = write_monthly_metrics_summary("2026-05", metrics_dir=metrics_dir)

        assert weekly_summary["period_type"] == "week"
        assert weekly_summary["date_count"] == 2
        assert weekly_summary["dates"] == ["2026-05-04", "2026-05-05"]
        assert weekly_summary["pipeline"]["success_rate"] == 0.5
        assert weekly_summary["artifacts"]["write_count"] == 2
        assert weekly_summary["artifacts"]["signals_file_written"] is True
        assert weekly_summary["artifacts"]["daily_radar_file_written"] is True
        assert weekly_summary["artifacts"]["total_bytes"] == 100
        assert weekly_summary["collectors"]["total_runs"] == 2
        assert weekly_summary["collectors"]["success_rate"] == 0.5
        assert weekly_summary["signals"]["collected_count"] == 2
        assert weekly_summary["signals"]["published_count"] == 2
        assert weekly_summary["signals"]["latest_collected_at"] == "2026-05-05T09:00:00+10:00"
        assert weekly_summary["llm"]["call_count"] == 2
        assert weekly_summary["llm"]["fallback_rate"] == 0.5
        assert weekly_summary["llm"]["estimated_cost"] == 0.1
        assert weekly_summary["llm"]["estimated_cost_per_verified_insight"] == 0.05
        assert weekly_summary["verification"]["verified_insight_count"] == 2
        assert weekly_summary["verification"]["downgrade_rate"] == 0.5
        assert monthly_summary["period_type"] == "month"
        assert monthly_summary["date_count"] == 2
        assert weekly_path.exists()
        assert monthly_path.exists()
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_metrics_status_reports_available_metrics_files():
    metrics_dir = _test_metrics_dir()
    try:
        (metrics_dir.parent / "signals.json").write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "signal_id": "sig-1",
                            "source": "rss",
                            "collected_at": "2026-05-05T09:00:00+10:00",
                            "published_at": "2026-05-04T09:00:00+10:00",
                        },
                        {
                            "signal_id": "sig-old",
                            "source": "rss",
                            "collected_at": "2026-04-01T09:00:00+10:00",
                            "published_at": "2026-04-01T09:00:00+10:00",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        append_pipeline_run(
            {
                "date": "2026-05-04",
                "run_id": "run-1",
                "success": True,
            },
            metrics_dir=metrics_dir,
        )
        record_artifact_write(
            {
                "date": "2026-05-04",
                "run_id": "run-1",
                "artifact_name": "signals",
                "success": True,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-05",
                "task_type": "signal_insight",
                "success": True,
            },
            metrics_dir=metrics_dir,
        )
        record_signal_timeline_load(
            {
                "date": "2026-05-05",
                "route": "/signals",
                "success": True,
                "duration_ms": 700,
                "load_source": "s3",
            },
            metrics_dir=metrics_dir,
        )

        status = load_metrics_status(metrics_dir=metrics_dir)

        assert status["has_any_metrics"] is True
        assert status["available_dates"] == ["2026-05-04", "2026-05-05"]
        assert status["latest_raw_event_date"] == "2026-05-05"
        assert status["latest_signal_activity_date"] == "2026-05-05"
        assert status["is_summary_stale"] is True
        assert status["missing_summary_dates"] == ["2026-05-04", "2026-05-05"]
        assert status["signal_dates_missing_pipeline_runs"] == ["2026-05-05"]
        assert status["signal_dates_missing_collector_runs"] == ["2026-05-05"]
        assert status["categories"]["pipeline_runs"]["exists"] is True
        assert status["categories"]["artifact_writes"]["exists"] is True
        assert status["categories"]["artifact_writes"]["latest_date"] == "2026-05-04"
        assert status["categories"]["pipeline_runs"]["file_count"] == 1
        assert status["categories"]["pipeline_runs"]["latest_date"] == "2026-05-04"
        assert status["categories"]["llm_calls"]["latest_date"] == "2026-05-05"
        assert status["categories"]["signal_timeline_loads"]["latest_date"] == "2026-05-05"
        assert status["categories"]["daily_summary"]["exists"] is False
        assert status["categories"]["weekly_summary"]["exists"] is False
        assert status["categories"]["monthly_summary"]["exists"] is False
        assert status["latest_summary_date"] is None
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_metrics_status_flags_raw_events_newer_than_daily_summary():
    metrics_dir = _test_metrics_dir()
    try:
        append_pipeline_run(
            {
                "date": "2026-05-04",
                "success": True,
                "duration_seconds": 420,
            },
            metrics_dir=metrics_dir,
        )
        write_daily_metrics_summary("2026-05-04", metrics_dir=metrics_dir)
        record_llm_call(
            {
                "date": "2026-05-05",
                "task_type": "signal_insight",
                "success": True,
            },
            metrics_dir=metrics_dir,
        )

        status = load_metrics_status(metrics_dir=metrics_dir)

        assert status["latest_raw_event_date"] == "2026-05-05"
        assert status["latest_summary_date"] == "2026-05-04"
        assert status["is_summary_stale"] is True
        assert status["missing_summary_dates"] == ["2026-05-05"]
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_metrics_status_uses_s3_metric_inventory(monkeypatch):
    monkeypatch.setattr(
        metrics_summary_module,
        "_list_s3_metrics_keys",
        lambda: [
            "metrics/pipeline_runs/2026-05-13.json",
            "metrics/collector_runs/2026-05-13.jsonl",
            "metrics/llm_calls/2026-05-13.jsonl",
            "metrics/daily_summary/2026-05-13.json",
            "metrics/weekly_summary/2026-W20.json",
            "metrics/monthly_summary/2026-05.json",
            "metrics/latest/daily_summary.json",
        ],
    )

    status = load_metrics_status()

    assert status["data_source"] == "s3"
    assert status["latest_raw_event_date"] == "2026-05-13"
    assert status["latest_summary_date"] == "2026-05-13"
    assert status["is_summary_stale"] is False
    assert status["categories"]["pipeline_runs"]["file_count"] == 1
    assert status["categories"]["collector_runs"]["latest_date"] == "2026-05-13"


def test_load_metrics_summaries_reads_recent_s3_daily_payloads(monkeypatch):
    payloads = {
        "metrics/daily_summary/2026-05-12.json": {"date": "2026-05-12"},
        "metrics/daily_summary/2026-05-13.json": {"date": "2026-05-13"},
        "metrics/daily_summary/2026-05-14.json": {"date": "2026-05-14"},
    }
    monkeypatch.setattr(metrics_summary_module, "_list_s3_metrics_keys", lambda: list(payloads))
    monkeypatch.setattr(metrics_summary_module, "_read_s3_metrics_json", lambda key: payloads.get(key))

    summaries = load_metrics_summaries(
        "daily_summary",
        through_date="2026-05-13",
        limit=2,
    )

    assert [summary["date"] for summary in summaries] == ["2026-05-12", "2026-05-13"]


def test_load_metrics_summaries_rebuilds_weekly_from_daily_summaries():
    metrics_dir = _test_metrics_dir()
    try:
        daily_dir = metrics_dir / "daily_summary"
        weekly_dir = metrics_dir / "weekly_summary"
        daily_dir.mkdir(parents=True)
        weekly_dir.mkdir(parents=True)

        for date, items_written in [
            ("2026-05-15", 201),
            ("2026-05-16", 199),
            ("2026-05-17", 212),
            ("2026-05-18", 195),
        ]:
            (daily_dir / f"{date}.json").write_text(
                json.dumps(
                    {
                        "date": date,
                        "pipeline": {
                            "success": True,
                            "duration_seconds": 100,
                            "run_count": 1,
                            "error_count": 0,
                            "artifact_written_count": 16,
                        },
                        "artifacts": {
                            "write_count": 16,
                            "signals_file_written": True,
                            "daily_radar_file_written": True,
                            "total_bytes": 100,
                            "failed_write_count": 0,
                        },
                        "collectors": {
                            "total_runs": 8,
                            "success_rate": 1.0,
                            "total_items_fetched": items_written,
                            "total_items_normalized": items_written,
                            "total_items_written": items_written,
                            "error_count": 0,
                            "retry_count": 0,
                            "failed_collectors": [],
                        },
                        "signals": {
                            "collected_count": 25,
                            "published_count": 0,
                            "latest_collected_at": f"{date}T10:00:00+10:00",
                            "source_count": 5,
                        },
                        "llm": {
                            "call_count": 0,
                            "success_rate": None,
                            "fallback_rate": None,
                            "error_count": 0,
                            "retry_count": 0,
                            "avg_latency_ms": None,
                            "estimated_cost": 0,
                            "json_validation_pass_rate": None,
                            "json_repair_count": 0,
                        },
                        "verification": {
                            "verified_insight_count": 0,
                            "downgrade_rate": None,
                            "unsupported_claim_rate": None,
                            "watch_only_count": 0,
                            "action_blocked_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )

        (weekly_dir / "2026-W21.json").write_text(
            json.dumps(
                {
                    "period_type": "week",
                    "period_id": "2026-W21",
                    "date_count": 1,
                    "pipeline": {"run_count": 1},
                    "collectors": {"total_items_written": 195},
                }
            ),
            encoding="utf-8",
        )

        summaries = load_metrics_summaries(
            "weekly_summary",
            limit=2,
            metrics_dir=metrics_dir,
        )

        by_period = {summary["period_id"]: summary for summary in summaries}

        assert by_period["2026-W20"]["pipeline"]["run_count"] == 3
        assert by_period["2026-W20"]["collectors"]["total_items_written"] == 612
        assert by_period["2026-W21"]["pipeline"]["run_count"] == 1
        assert by_period["2026-W21"]["collectors"]["total_items_written"] == 195
        assert by_period["2026-W21"]["date_count"] == 1
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_metrics_summaries_rebuilds_periods_with_raw_daily_fallbacks():
    metrics_dir = _test_metrics_dir()
    try:
        (metrics_dir.parent / "signals.json").write_text(
            json.dumps({"signals": []}),
            encoding="utf-8",
        )
        append_pipeline_run(
            {
                "date": "2026-05-15",
                "run_id": "run-2026-05-15",
                "success": True,
                "duration_seconds": 100,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-15",
                "task_type": "signal_insight",
                "success": True,
                "fallback_used": False,
                "estimated_cost": 0.01,
            },
            metrics_dir=metrics_dir,
        )
        record_llm_call(
            {
                "date": "2026-05-16",
                "task_type": "signal_insight",
                "success": True,
                "fallback_used": False,
                "estimated_cost": 0.02,
            },
            metrics_dir=metrics_dir,
        )
        write_daily_metrics_summary("2026-05-15", metrics_dir=metrics_dir)

        weekly_summaries = load_metrics_summaries(
            "weekly_summary",
            limit=1,
            metrics_dir=metrics_dir,
        )
        monthly_summaries = load_metrics_summaries(
            "monthly_summary",
            limit=1,
            metrics_dir=metrics_dir,
        )

        assert weekly_summaries[0]["period_id"] == "2026-W20"
        assert weekly_summaries[0]["dates"] == ["2026-05-15", "2026-05-16"]
        assert weekly_summaries[0]["date_count"] == 2
        assert weekly_summaries[0]["llm"]["call_count"] == 2
        assert weekly_summaries[0]["llm"]["estimated_cost"] == 0.03
        assert monthly_summaries[0]["period_id"] == "2026-05"
        assert monthly_summaries[0]["dates"] == ["2026-05-15", "2026-05-16"]
        assert monthly_summaries[0]["llm"]["call_count"] == 2
    finally:
        shutil.rmtree(metrics_dir, ignore_errors=True)


def test_load_metrics_summaries_rebuilds_s3_monthly_from_s3_daily_payloads(monkeypatch):
    payloads = {
        "metrics/daily_summary/2026-05-17.json": {
            "date": "2026-05-17",
            "pipeline": {"success": True, "duration_seconds": 100, "run_count": 1},
            "artifacts": {"write_count": 16, "total_bytes": 100},
            "collectors": {
                "total_runs": 8,
                "success_rate": 1.0,
                "total_items_written": 212,
            },
            "signals": {"collected_count": 25, "published_count": 0},
            "llm": {"call_count": 0, "estimated_cost": 0},
            "verification": {"verified_insight_count": 0},
        },
        "metrics/daily_summary/2026-05-18.json": {
            "date": "2026-05-18",
            "pipeline": {"success": True, "duration_seconds": 100, "run_count": 1},
            "artifacts": {"write_count": 16, "total_bytes": 100},
            "collectors": {
                "total_runs": 8,
                "success_rate": 1.0,
                "total_items_written": 195,
            },
            "signals": {"collected_count": 25, "published_count": 0},
            "llm": {"call_count": 0, "estimated_cost": 0},
            "verification": {"verified_insight_count": 0},
        },
        "metrics/monthly_summary/2026-05.json": {
            "period_type": "month",
            "period_id": "2026-05",
            "date_count": 1,
            "pipeline": {"run_count": 1},
            "collectors": {"total_items_written": 195},
        },
    }
    monkeypatch.setattr(metrics_summary_module, "_list_s3_metrics_keys", lambda: list(payloads))
    monkeypatch.setattr(metrics_summary_module, "_read_s3_metrics_json", lambda key: payloads.get(key))

    summaries = load_metrics_summaries("monthly_summary", limit=1)

    assert len(summaries) == 1
    assert summaries[0]["period_id"] == "2026-05"
    assert summaries[0]["pipeline"]["run_count"] == 2
    assert summaries[0]["collectors"]["total_items_written"] == 407
    assert summaries[0]["date_count"] == 2
