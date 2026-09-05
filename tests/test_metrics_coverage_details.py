"""Regression: successful collector steps must not hide failed source units."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services import metrics_summary_service as metrics  # noqa: E402

DATE = "2026-09-05"


def seed(root):
    pipeline = {
        "run_id": "selected-run", "success": True,
        "collector_plan": {
            "plan_version": "pipeline-collector-plan-v1", "complete": True,
            "expected_step_ids": ["rss"], "attempted_step_ids": ["rss"],
        },
    }
    event = {
        "run_id": "selected-run", "collector_name": "rss", "success": True,
        "coverage": {
            "plan_version": "collector-coverage-v1", "complete": False,
            "expected_unit_ids": ["rss_001", "rss_002", "rss_003"],
            "attempted_unit_ids": ["rss_001", "rss_002"],
            "succeeded_unit_ids": ["rss_001"], "zero_result_unit_ids": ["rss_001"],
            "failed_units": [{"unit_id": "rss_002", "reason_code": "http_error", "raw_payload": "excluded"}],
            "skipped_units": [{"unit_id": "rss_003", "reason_code": "not_configured"}],
        },
    }
    for folder in ("pipeline_runs", "collector_runs", "daily_summary"):
        (root / folder).mkdir()
    (root / "pipeline_runs" / f"{DATE}.json").write_text(json.dumps([pipeline]), encoding="utf-8")
    (root / "collector_runs" / f"{DATE}.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    summary = metrics.build_daily_metrics_summary(DATE, metrics_dir=root)
    return summary, event


def save_legacy(root, summary):
    for key in ("failed_units", "skipped_units", "unit_details_available"):
        summary["collectors"]["coverage"].pop(key)
    path = root / "daily_summary" / f"{DATE}.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    return path


def test_successful_step_preserves_failed_and_skipped_unit_diagnostics(tmp_path):
    summary, _ = seed(tmp_path)
    assert summary["collectors"]["success_rate"] == 1
    coverage = summary["collectors"]["coverage"]
    assert coverage["completeness"] == "partial"
    assert coverage["failed_units"] == [{"collector_name": "rss", "unit_id": "rss_002", "reason_code": "http_error"}]
    assert coverage["skipped_units"] == [{"collector_name": "rss", "unit_id": "rss_003", "reason_code": "not_configured"}]
    assert "excluded" not in json.dumps(coverage)


@pytest.mark.parametrize("requested_date", [DATE, None])
def test_legacy_local_summary_gets_exact_run_details_without_write(tmp_path, requested_date):
    summary, event = seed(tmp_path)
    path = save_legacy(tmp_path, summary)
    original = path.read_bytes()
    # A different run must not supply the failure detail, even when more recent.
    with (tmp_path / "collector_runs" / f"{DATE}.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**event, "run_id": "other-run"}) + "\n")
    loaded = metrics.load_daily_metrics_summary(requested_date, metrics_dir=tmp_path)
    coverage = loaded["summary"]["collectors"]["coverage"]
    assert coverage["failed_units"][0]["unit_id"] == "rss_002"
    assert {key: coverage[key] for key in summary["collectors"]["coverage"]} == summary["collectors"]["coverage"]
    assert path.read_bytes() == original


@pytest.mark.parametrize("mismatch", ["run_id", "succeeded_unit_count"])
def test_mismatched_local_events_do_not_enrich_summary(tmp_path, mismatch):
    summary, _ = seed(tmp_path)
    save_legacy(tmp_path, summary)
    summary["collectors"]["coverage"][mismatch] = "absent-run" if mismatch == "run_id" else 0
    (tmp_path / "daily_summary" / f"{DATE}.json").write_text(json.dumps(summary), encoding="utf-8")
    loaded = metrics.load_daily_metrics_summary(DATE, metrics_dir=tmp_path)
    assert "unit_details_available" not in loaded["summary"]["collectors"]["coverage"]


def test_s3_summary_never_uses_local_failure_details(tmp_path, monkeypatch):
    summary, _ = seed(tmp_path)
    save_legacy(tmp_path, summary)
    monkeypatch.setattr(metrics, "METRICS_DIR", tmp_path)
    monkeypatch.setattr(metrics, "_s3_metrics_enabled", lambda _: True)
    monkeypatch.setattr(metrics, "_read_s3_metrics_json", lambda _: summary)
    monkeypatch.setattr(metrics, "_read_jsonl", lambda _: pytest.fail("S3 summary must not consult local events"))
    loaded = metrics.load_daily_metrics_summary(DATE)
    assert loaded["data_source"] == "s3"
    assert loaded["summary"] == summary


def test_missing_events_keep_details_unknown(tmp_path):
    summary, _ = seed(tmp_path)
    save_legacy(tmp_path, summary)
    (tmp_path / "collector_runs" / f"{DATE}.jsonl").write_text("", encoding="utf-8")
    loaded = metrics.load_daily_metrics_summary(DATE, metrics_dir=tmp_path)
    assert "unit_details_available" not in loaded["summary"]["collectors"]["coverage"]
