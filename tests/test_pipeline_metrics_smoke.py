import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

import app.main_summary_v2 as pipeline  # noqa: E402
from backend.app.services import metrics_event_service, metrics_summary_service  # noqa: E402
from app.models import Insight, Signal  # noqa: E402


def _test_root() -> Path:
    root = REPO_ROOT / "tmp_pipeline_metrics_tests"
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    return path


def _signal() -> Signal:
    return Signal(
        title="Smoke signal",
        summary="Smoke summary",
        url="https://example.com/smoke",
        author="AI Radar",
        source="smoke",
        category="Test",
        published_at="2026-05-04T00:00:00Z",
        collected_at="2026-05-04T00:00:00Z",
    )


def _insight() -> Insight:
    return Insight(
        signal_title="Smoke signal",
        signal_summary="Smoke summary",
        why_it_matters="Because smoke tests should prove the wiring.",
        relevance_to_projects="Relevant to metrics.",
        relevance_to_career="Relevant to reliability.",
        synthesized_insight="Metrics wiring works.",
        provider_used="mock",
        model_used="mock-model",
    )


class _FakeS3MetricsWriter:
    def __init__(self) -> None:
        self.json_uploads: dict[str, object] = {}
        self.text_uploads: dict[str, str] = {}

    def upload_json(self, data, s3_key: str) -> None:
        self.json_uploads[s3_key] = data

    def upload_text(
        self,
        text: str,
        s3_key: str,
        *,
        content_type: str = "text/plain",
    ) -> None:
        self.text_uploads[s3_key] = text


def test_pipeline_uploads_metrics_artifacts_to_s3_prefix():
    temp_root = _test_root()
    metrics_dir = temp_root / "metrics"
    try:
        date = "2026-05-13"
        (metrics_dir / "pipeline_runs").mkdir(parents=True)
        (metrics_dir / "collector_runs").mkdir(parents=True)
        (metrics_dir / "daily_summary").mkdir(parents=True)
        (metrics_dir / "weekly_summary").mkdir(parents=True)
        (metrics_dir / "monthly_summary").mkdir(parents=True)
        (metrics_dir / "pipeline_runs" / f"{date}.json").write_text(
            json.dumps([{"date": date, "success": True}]),
            encoding="utf-8",
        )
        (metrics_dir / "collector_runs" / f"{date}.jsonl").write_text(
            json.dumps({"date": date, "success": True}) + "\n",
            encoding="utf-8",
        )
        (metrics_dir / "daily_summary" / f"{date}.json").write_text(
            json.dumps({"date": date, "pipeline": {"run_count": 1}}),
            encoding="utf-8",
        )
        (metrics_dir / "weekly_summary" / "2026-W20.json").write_text(
            json.dumps({"period_id": "2026-W20"}),
            encoding="utf-8",
        )
        (metrics_dir / "monthly_summary" / "2026-05.json").write_text(
            json.dumps({"period_id": "2026-05"}),
            encoding="utf-8",
        )

        fake_s3 = _FakeS3MetricsWriter()
        with patch.object(pipeline, "METRICS_DIR", metrics_dir):
            uploaded_count = pipeline._upload_metrics_outputs_to_s3(fake_s3, date)

        assert uploaded_count == 8
        assert (
            fake_s3.json_uploads["metrics/pipeline_runs/2026-05-13.json"][0]["success"]
            is True
        )
        assert (
            fake_s3.json_uploads["metrics/latest/daily_summary.json"]["pipeline"][
                "run_count"
            ]
            == 1
        )
        assert (
            fake_s3.json_uploads["metrics/latest/weekly_summary.json"]["period_id"]
            == "2026-W20"
        )
        assert fake_s3.text_uploads["metrics/collector_runs/2026-05-13.jsonl"].strip()
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_local_only_setting_skips_s3_upload_helpers(monkeypatch):
    monkeypatch.delenv("AI_RADAR_LOCAL_ONLY", raising=False)
    monkeypatch.delenv("AI_RADAR_SKIP_S3_UPLOADS", raising=False)
    assert pipeline.s3_uploads_disabled() is False

    monkeypatch.setenv("AI_RADAR_LOCAL_ONLY", "1")
    assert pipeline.s3_uploads_disabled() is True

    with patch.object(pipeline, "S3Writer", side_effect=AssertionError("no S3")):
        pipeline._safe_upload_metrics_outputs_to_s3("2026-05-28")

    monkeypatch.delenv("AI_RADAR_LOCAL_ONLY", raising=False)
    monkeypatch.setenv("AI_RADAR_SKIP_S3_UPLOADS", "true")
    assert pipeline.s3_uploads_disabled() is True


def test_main_pipeline_writes_metrics_artifacts_without_external_services():
    temp_root = _test_root()
    metrics_dir = temp_root / "metrics"
    output_dir = temp_root / "output"
    intelligence_dir = output_dir / "intelligence"
    output_dir.mkdir()
    intelligence_dir.mkdir()
    today = datetime.now(pipeline.settings.timezone).strftime("%Y-%m-%d")
    iso_week = datetime.strptime(today, "%Y-%m-%d").date().isocalendar()
    expected_week = f"{iso_week.year}-W{iso_week.week:02d}"
    expected_month = today[:7]

    smoke_signal = _signal()

    patches = [
        patch.object(metrics_event_service, "METRICS_DIR", metrics_dir),
        patch.object(metrics_summary_service, "METRICS_DIR", metrics_dir),
        patch.object(pipeline, "OUTPUT_DIR", output_dir),
        patch.object(pipeline, "INTELLIGENCE_OUTPUT_DIR", intelligence_dir),
        patch.object(pipeline, "COLLECTOR_SIGNALS_FILE", output_dir / "collected_signals.json"),
        patch.object(pipeline, "PIPELINE_SIGNALS_FILE", output_dir / "signals.json"),
        patch.object(pipeline, "MANUAL_SESSIONS_FILE", output_dir / "manual_sessions.json"),
        patch.object(pipeline.settings, "validate", return_value=None),
        patch.object(pipeline, "load_personal_context", return_value={}),
        patch.object(pipeline, "load_ingestion_subscription_settings", return_value={"sources": [], "project_links": []}),
        patch.object(pipeline, "collect_rss_signals", return_value=[smoke_signal.to_dict()]),
        patch.object(pipeline, "save_signals", return_value=None),
        patch.object(pipeline, "collect_official_signals", return_value=[]),
        patch.object(pipeline, "save_official_signals", return_value=None),
        patch.object(pipeline, "collect_github_agent_signals", return_value=[]),
        patch.object(pipeline, "save_github_agent_signals", return_value=None),
        patch.object(pipeline, "normalize_github_agent_signals", return_value=[]),
        patch.object(pipeline, "collect_hackernews_agent_signals", return_value=[]),
        patch.object(pipeline, "save_hackernews_agent_signals", return_value=None),
        patch.object(pipeline, "collect_normalized_hackernews_agent_signals", return_value=[]),
        patch.object(pipeline, "collect_producthunt_agent_signals", return_value=[]),
        patch.object(pipeline, "save_producthunt_agent_signals", return_value=None),
        patch.object(pipeline, "collect_normalized_producthunt_agent_signals", return_value=[]),
        patch.object(pipeline, "classify_agent_signals", side_effect=lambda items: items),
        patch.object(pipeline, "attach_agent_scores_to_signals", side_effect=lambda items: items),
        patch.object(pipeline, "save_agent_watch_signals", return_value=None),
        patch.object(pipeline, "collect_github_friction_signals", return_value=[]),
        patch.object(pipeline, "save_github_friction_signals", return_value=None),
        patch.object(pipeline, "collect_hackernews_friction_signals", return_value=[]),
        patch.object(pipeline, "save_hackernews_friction_signals", return_value=None),
        patch.object(pipeline, "collect_normalized_friction_signals", return_value=[]),
        patch.object(pipeline, "save_friction_signals", return_value=None),
        patch.object(pipeline, "run_merge_signals", return_value=None),
        patch.object(pipeline, "load_signals_from_file", return_value=[smoke_signal]),
        patch.object(pipeline, "load_and_promote_manual_signals", return_value=[]),
        patch.object(pipeline, "enrich_and_filter_signals", return_value=([smoke_signal], {})),
        patch.object(pipeline, "select_signals_for_insight", return_value=[smoke_signal]),
        patch.object(pipeline, "generate_insight", return_value=_insight()),
        patch.object(pipeline, "load_existing_latest_signals", return_value=[]),
        patch.object(pipeline, "preserve_signal_history_fields", side_effect=lambda new_signals, existing_signals: new_signals),
        patch.object(pipeline, "merge_insights_into_signals", side_effect=lambda signals_data, insights_data: signals_data),
        patch.object(pipeline, "attach_projects_to_signals", side_effect=lambda signals_data: signals_data),
        patch.object(pipeline, "detect_trends", return_value={}),
        patch.object(pipeline, "compute_topic_trends", return_value=[]),
        patch.object(pipeline, "compute_rising_topics", return_value=[]),
        patch.object(pipeline, "load_previous_topic_trends", return_value=[]),
        patch.object(pipeline, "compute_topic_evolution", return_value=[]),
        patch.object(pipeline, "compute_weekly_topic_summary", return_value={}),
        patch.object(pipeline, "compute_weekly_momentum", return_value=[]),
        patch.object(pipeline, "compute_topic_momentum_safe", return_value=[]),
        patch.object(pipeline, "compute_strategic_priority_topics", return_value=[]),
        patch.object(pipeline, "generate_daily_executive_summary", return_value={}),
        patch.object(pipeline, "build_subscription_source_summary", return_value={}),
        patch.object(pipeline, "build_agent_watch_summary", return_value={}),
        patch.object(pipeline, "build_agent_watch_repo_snapshots", return_value={}),
        patch.object(pipeline, "build_agent_watch_repo_profiles", return_value={}),
        patch.object(pipeline, "build_friction_signals_summary", return_value={}),
        patch.object(pipeline, "build_friction_signal_profiles", return_value={}),
        patch.object(pipeline, "build_intelligence_outputs", return_value={}),
        patch.object(pipeline, "save_feed_activity", return_value=None),
        patch.object(pipeline, "save_dated_daily_radar", return_value=output_dir / "history" / today / "daily_radar.json"),
        patch.object(pipeline, "S3Writer", side_effect=AssertionError("no S3")),
        patch.object(pipeline, "upload_outputs_to_s3", side_effect=AssertionError("no S3")),
        patch.object(
            pipeline,
            "upload_intelligence_outputs_to_s3",
            side_effect=AssertionError("no S3"),
        ),
        patch.dict(
            "os.environ",
            {"OBSIDIAN_VAULT_PATH": "", "AI_RADAR_LOCAL_ONLY": "1"},
            clear=False,
        ),
    ]

    try:
        with patches[0]:
            for patcher in patches[1:]:
                patcher.start()
            try:
                pipeline.main()
            finally:
                for patcher in reversed(patches[1:]):
                    patcher.stop()

        pipeline_runs = json.loads(
            (metrics_dir / "pipeline_runs" / f"{today}.json").read_text(encoding="utf-8")
        )
        collector_lines = (
            metrics_dir / "collector_runs" / f"{today}.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        summary = json.loads(
            (metrics_dir / "daily_summary" / f"{today}.json").read_text(encoding="utf-8")
        )
        weekly_summary = json.loads(
            (metrics_dir / "weekly_summary" / f"{expected_week}.json").read_text(
                encoding="utf-8"
            )
        )
        monthly_summary = json.loads(
            (metrics_dir / "monthly_summary" / f"{expected_month}.json").read_text(
                encoding="utf-8"
            )
        )

        assert pipeline_runs[-1]["success"] is True
        assert pipeline_runs[-1]["artifact_written_count"] >= 3
        assert len(collector_lines) >= 8
        assert summary["pipeline"]["success"] is True
        assert summary["collectors"]["total_runs"] >= 8
        assert weekly_summary["period_id"] == expected_week
        assert weekly_summary["date_count"] == 1
        assert monthly_summary["period_id"] == expected_month
        assert monthly_summary["date_count"] == 1
        assert "rss_collector" in {
            json.loads(line)["collector_name"] for line in collector_lines
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
