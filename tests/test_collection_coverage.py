import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_event_service import (  # noqa: E402
    append_pipeline_run,
    record_collector_run,
)
from app.services.metrics_summary_service import build_daily_metrics_summary  # noqa: E402
from signal_collectors import (  # noqa: E402
    github_agent_collector,
    github_friction_collector,
    hackernews_agent_collector,
    hackernews_friction_collector,
    official_collector,
    producthunt_agent_collector,
    rss_collector,
)
from signal_collectors.collection_coverage import (  # noqa: E402
    CollectionCoverageTracker,
    with_collection_coverage,
)


def _coverage(*, complete: bool, prefix: str = "unit") -> dict:
    tracker = CollectionCoverageTracker(
        unit_type="query",
        expected_count=1,
        unit_prefix=prefix,
    )
    tracker.attempt(0)
    if complete:
        tracker.succeed(0, item_count=0)
    else:
        tracker.fail(0, reason_code="timeout")
    return tracker.to_dict()


def _pipeline_plan(expected: list[str], attempted: list[str]) -> dict:
    missing = [step_id for step_id in expected if step_id not in attempted]
    return {
        "plan_version": "pipeline-collector-plan-v1",
        "expected_step_ids": expected,
        "attempted_step_ids": attempted,
        "missing_step_ids": missing,
        "complete": not missing,
    }


def test_zero_result_is_a_complete_success_without_private_locator_leakage():
    tracker = CollectionCoverageTracker(
        unit_type="source",
        expected_count=1,
        unit_prefix="rss_source",
    )
    tracker.attempt(0)
    tracker.succeed(0, item_count=0)

    coverage = tracker.to_dict()

    assert coverage["complete"] is True
    assert coverage["zero_result_unit_ids"] == ["rss_source_001"]
    assert "https://private.example/feed" not in json.dumps(coverage)


@pytest.mark.parametrize(
    ("module", "plan_attribute", "search_attribute", "collect_attribute"),
    [
        (
            github_agent_collector,
            "GITHUB_AGENT_SEARCH_QUERIES",
            "_search_repositories",
            "collect_github_agent_signals",
        ),
        (
            hackernews_agent_collector,
            "HN_AGENT_KEYWORDS",
            "_search_hn",
            "collect_hackernews_agent_signals",
        ),
        (
            github_friction_collector,
            "GITHUB_FRICTION_SEARCH_QUERIES",
            "_search_issues",
            "collect_github_friction_signals",
        ),
        (
            hackernews_friction_collector,
            "HN_FRICTION_KEYWORDS",
            "_search_hn",
            "collect_hackernews_friction_signals",
        ),
    ],
)
def test_query_collectors_report_successful_zero_result_units(
    module,
    plan_attribute,
    search_attribute,
    collect_attribute,
):
    with (
        patch.object(module, plan_attribute, ["private query"]),
        patch.object(module, search_attribute, return_value=[]),
    ):
        result = getattr(module, collect_attribute)()

    assert result == []
    assert result.coverage["complete"] is True
    assert result.coverage["zero_result_unit_ids"]
    assert "private query" not in json.dumps(result.coverage)


def test_swallowed_query_failure_makes_collector_coverage_partial():
    with (
        patch.object(
            github_agent_collector,
            "GITHUB_AGENT_SEARCH_QUERIES",
            ["private query one", "private query two"],
        ),
        patch.object(
            github_agent_collector,
            "_search_repositories",
            side_effect=[[], TimeoutError("private detail")],
        ),
    ):
        result = github_agent_collector.collect_github_agent_signals()

    assert result.coverage["complete"] is False
    assert result.coverage["zero_result_unit_ids"] == ["github_agent_query_001"]
    assert result.coverage["failed_units"] == [
        {"unit_id": "github_agent_query_002", "reason_code": "timeout"}
    ]
    serialized = json.dumps(result.coverage)
    assert "private query" not in serialized
    assert "private detail" not in serialized


def test_malformed_api_payload_is_not_reported_as_successful_zero():
    with (
        patch.object(
            github_agent_collector,
            "GITHUB_AGENT_SEARCH_QUERIES",
            ["private query"],
        ),
        patch.object(github_agent_collector, "_github_request", return_value={}),
    ):
        result = github_agent_collector.collect_github_agent_signals()

    assert result.coverage["complete"] is False
    assert result.coverage["failed_units"] == [
        {"unit_id": "github_agent_query_001", "reason_code": "invalid_response"}
    ]


def test_rss_and_official_source_failures_are_visible_without_source_names():
    rss_sources = {
        "private-source-a": "https://private.example/a.xml",
        "private-source-b": "https://private.example/b.xml",
    }
    with (
        patch.object(rss_collector, "get_effective_rss_sources", return_value=rss_sources),
        patch.object(
            rss_collector.feedparser,
            "parse",
            side_effect=[
                SimpleNamespace(entries=[], bozo=False, status=200),
                SimpleNamespace(entries=[], bozo=False, status=503),
            ],
        ),
    ):
        rss_result = rss_collector.collect_rss_signals()

    private_config = {"source": "private-official-source"}

    def fail_fetch(_config, per_source_limit, *, on_fetch_error):
        on_fetch_error(ConnectionError("private connection detail"))
        return []

    with (
        patch.object(
            official_collector,
            "get_effective_source_configs",
            return_value=[private_config],
        ),
        patch.object(official_collector, "collect_from_source", side_effect=fail_fetch),
    ):
        official_result = official_collector.collect_official_signals()

    assert rss_result.coverage["complete"] is False
    assert official_result.coverage["complete"] is False
    serialized = json.dumps([rss_result.coverage, official_result.coverage])
    assert "private.example" not in serialized
    assert "private-official-source" not in serialized
    assert "private connection detail" not in serialized


def test_producthunt_request_failure_is_not_reported_as_successful_zero():
    with patch.object(
        producthunt_agent_collector,
        "_product_hunt_request",
        side_effect=TimeoutError("private request detail"),
    ):
        result = producthunt_agent_collector.collect_producthunt_agent_signals()

    assert result == []
    assert result.coverage["complete"] is False
    assert result.coverage["failed_units"][0]["reason_code"] == "timeout"
    assert "private request detail" not in json.dumps(result.coverage)


def test_daily_summary_uses_latest_run_and_reports_complete(tmp_path):
    date = "2026-08-25"
    steps = ["rss_collector", "merge_signals"]
    append_pipeline_run(
        {
            "run_id": "older-partial-run",
            "date": date,
            "success": False,
            "collector_plan": _pipeline_plan(steps, ["rss_collector"]),
        },
        metrics_dir=tmp_path,
    )
    append_pipeline_run(
        {
            "run_id": "latest-complete-run",
            "date": date,
            "success": True,
            "collector_plan": _pipeline_plan(steps, steps),
        },
        metrics_dir=tmp_path,
    )
    for step_id in steps:
        record_collector_run(
            {
                "run_id": "latest-complete-run",
                "date": date,
                "collector_name": step_id,
                "success": True,
                "coverage": _coverage(complete=True, prefix=step_id),
            },
            metrics_dir=tmp_path,
        )

    coverage = build_daily_metrics_summary(date, metrics_dir=tmp_path)["collectors"][
        "coverage"
    ]

    assert coverage["completeness"] == "complete"
    assert coverage["run_id"] == "latest-complete-run"
    assert coverage["expected_step_count"] == 2
    assert coverage["zero_result_unit_count"] == 2


def test_daily_summary_reports_inner_failure_as_partial(tmp_path):
    date = "2026-08-25"
    steps = ["rss_collector"]
    append_pipeline_run(
        {
            "run_id": "inner-failure-run",
            "date": date,
            "success": True,
            "collector_plan": _pipeline_plan(steps, steps),
        },
        metrics_dir=tmp_path,
    )
    record_collector_run(
        {
            "run_id": "inner-failure-run",
            "date": date,
            "collector_name": "rss_collector",
            "success": True,
            "coverage": _coverage(complete=False, prefix="rss_source"),
        },
        metrics_dir=tmp_path,
    )

    coverage = build_daily_metrics_summary(date, metrics_dir=tmp_path)["collectors"][
        "coverage"
    ]

    assert coverage["completeness"] == "partial"
    assert coverage["failed_unit_count"] == 1
    assert "unit_coverage_incomplete" in coverage["reason_codes"]


def test_daily_summary_reports_early_abort_missing_steps_as_partial(tmp_path):
    date = "2026-08-25"
    steps = ["rss_collector", "official_collector", "merge_signals"]
    append_pipeline_run(
        {
            "run_id": "early-abort-run",
            "date": date,
            "success": False,
            "collector_plan": _pipeline_plan(
                steps,
                ["rss_collector", "official_collector"],
            ),
        },
        metrics_dir=tmp_path,
    )
    record_collector_run(
        {
            "run_id": "early-abort-run",
            "date": date,
            "collector_name": "rss_collector",
            "success": True,
            "coverage": _coverage(complete=True, prefix="rss_source"),
        },
        metrics_dir=tmp_path,
    )
    record_collector_run(
        {
            "run_id": "early-abort-run",
            "date": date,
            "collector_name": "official_collector",
            "success": False,
        },
        metrics_dir=tmp_path,
    )

    coverage = build_daily_metrics_summary(date, metrics_dir=tmp_path)["collectors"][
        "coverage"
    ]

    assert coverage["completeness"] == "partial"
    assert coverage["missing_step_ids"] == ["merge_signals"]
    assert coverage["failed_step_ids"] == ["official_collector"]


def test_daily_summary_keeps_historical_events_unknown(tmp_path):
    date = "2026-08-25"
    append_pipeline_run(
        {"run_id": "legacy-run", "date": date, "success": True},
        metrics_dir=tmp_path,
    )
    record_collector_run(
        {
            "run_id": "legacy-run",
            "date": date,
            "collector_name": "rss_collector",
            "success": True,
        },
        metrics_dir=tmp_path,
    )

    coverage = build_daily_metrics_summary(date, metrics_dir=tmp_path)["collectors"][
        "coverage"
    ]

    assert coverage["completeness"] == "unknown"
    assert coverage["reason_codes"] == ["coverage_not_recorded"]
