"""Cost-control regressions: real orchestration, mocked provider and storage."""

from io import BytesIO
from datetime import datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app.main_summary_v2 as pipeline
from app.intelligence.analysis_reuse import AnalysisReuse, analysis_fingerprint
from app.intelligence import analysis_reuse as reuse_module
from app.models import Signal


DAY_ONE = "2026-10-24T08:00:00+11:00"
DAY_TWO = "2026-10-25T08:00:00+11:00"


def signal(index=0, score=0.8, relevance=0.1):
    item = Signal(
        title=f"Observation {index}", summary="A specific external observation.",
        url=f"https://example.com/{index}", author="Author", source="test",
        category="AI", published_at="2026-10-20T00:00:00Z", collected_at=DAY_ONE,
    )
    item.score = score
    item.keyword_relevance = relevance
    item.recency_score = 0.8
    item.novelty_score = 0.5
    return item


def profile_input(kind, index=0):
    return {
        "title": f"Profile {index}", "summary": "An actionable observation.",
        "url": f"https://example.com/{kind}/{index}", "source": "github",
        "published_at": "2026-10-20T00:00:00Z", "topic": "ai_agents",
        "signal_type": "friction", "agent_watch_score": 1 - index / 100,
        "friction_score": 1 - index / 100,
        "metadata": {"repo_name": f"example/repo-{index}", "state": "open"},
    }


def result_payload(kind):
    if kind == "insight":
        return {k: "Specific useful interpretation with sufficient detail."
                for k in reuse_module.REQUIRED_TEXT[kind]}
    result = {k: "Specific useful interpretation." for k in reuse_module.REQUIRED_TEXT[kind]}
    result["confidence"] = "medium"
    if kind == "repo":
        result.update(suggested_use_cases=["Inspect this repo."], risks=["Partial evidence."])
    else:
        result["suggested_response"] = ["Inspect the underlying issue."]
    return result


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_RADAR_LOCAL_ONLY", "1")
    monkeypatch.setenv("PIPELINE_INSIGHT_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("AGENT_WATCH_REPO_PROFILE_LIMIT", "5")
    monkeypatch.setenv("FRICTION_SIGNAL_PROFILE_LIMIT", "5")
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "s3_client", Mock())
    monkeypatch.setattr(pipeline, "route_task", lambda task: SimpleNamespace(
        provider="openai", model="test-model", tier="tier_3_strategic"))
    monkeypatch.setattr(pipeline, "execute_routed_task", Mock(
        side_effect=AssertionError("Unexpected provider execution")))


def provider(monkeypatch, kind):
    parsed = result_payload(kind)
    call = Mock(return_value=SimpleNamespace(
        parsed_json=parsed, raw_text=json.dumps(parsed),
        route=SimpleNamespace(provider="openai", model="test-model"),
    ))
    monkeypatch.setattr(pipeline, "execute_routed_task", call)
    return call


def build(kind, items, date, reuse):
    fn = (pipeline.build_agent_watch_repo_profiles if kind == "repo"
          else pipeline.build_friction_signal_profiles)
    return fn(items, date, reuse=reuse)


@pytest.mark.parametrize("count", [0, 1, 2, 12, 15])
def test_only_qualified_signals_no_top_up_or_archive_fallback(count):
    qualified = [signal(i) for i in range(count)]
    candidates = [signal(100 + i, score=0.5) for i in range(10)]
    archived = [signal(200 + i, score=0.1) for i in range(10)]
    selected = pipeline.select_signals_for_insight(qualified + candidates + archived)
    assert len(selected) == min(count, 12)
    assert all(s.insight_status == "auto_generated" for s in selected)
    assert all(s.insight_status == "manual_candidate" for s in candidates)
    assert pipeline.select_signals_for_insight(archived) == []
    assert pipeline.select_signals_for_insight([]) == []


def test_relevance_qualification_is_preserved():
    item = signal(score=0.1, relevance=0.5)
    assert pipeline.select_signals_for_insight([item]) == [item]


def test_insight_survives_fresh_state_and_day_without_selection(monkeypatch):
    call = provider(monkeypatch, "insight")
    original = signal()
    reuse = AnalysisReuse()
    first = pipeline.generate_insight(original, {"projects": ["radar"]}, reuse=reuse)
    # Serialize/deserialize as a new ECS task would, including an idle day.
    next_run = AnalysisReuse(json.loads(json.dumps(reuse.snapshot())))
    next_run = AnalysisReuse(next_run.snapshot())
    original.collected_at = DAY_TWO
    original.recency_score = 0.3
    original.novelty_score = 0.1
    original.score = 0.7
    second = pipeline.generate_insight(original, {"projects": ["radar"]}, reuse=next_run)
    assert call.call_count == 1
    assert second.synthesized_insight == first.synthesized_insight
    assert second.execution["analysis_reused"] is True
    assert second.execution["analysis_generated_at"] == first.execution["analysis_generated_at"]
    assert "radar" not in json.dumps(next_run.snapshot())  # Personal input isn't stored.


@pytest.mark.parametrize("change", ["content", "personal_context", "model", "prompt"])
def test_insight_meaningful_changes_invalidate(monkeypatch, change):
    call = provider(monkeypatch, "insight")
    reuse, item, context = AnalysisReuse(), signal(), {"projects": ["old"]}
    pipeline.generate_insight(item, context, reuse=reuse)
    if change == "content":
        item.summary = "New evidence changed the observation."
    elif change == "personal_context":
        context = {"projects": ["new"]}
    elif change == "model":
        monkeypatch.setattr(pipeline, "route_task", lambda task: SimpleNamespace(
            provider="openai", model="different-model", tier="tier_3_strategic"))
    else:
        old = pipeline.personalized_radar_insight_prompts
        monkeypatch.setattr(pipeline, "personalized_radar_insight_prompts",
                            lambda **kwargs: (old(**kwargs)[0] + " Changed instructions.", old(**kwargs)[1]))
    pipeline.generate_insight(item, context, reuse=reuse)
    assert call.call_count == 2


@pytest.mark.parametrize("kind", ["repo", "friction"])
def test_profiles_reuse_across_days_without_filling_new_call_slots(monkeypatch, kind):
    call = provider(monkeypatch, kind)
    items = [profile_input(kind, i) for i in range(6)]
    reuse = AnalysisReuse()
    first = build(kind, items, DAY_ONE, reuse)
    assert first["count"] == 5
    assert call.call_count == 5
    second = build(kind, items, DAY_TWO, AnalysisReuse(reuse.snapshot()))
    assert second["count"] == 5
    assert call.call_count == 5  # Sixth cache miss must not replace a cached top-five item.
    assert all(item["analysis_reused"] for item in second["items"])
    assert all(item["generated_at"] == DAY_ONE for item in second["items"])
    assert all(item["last_observed_at"] == DAY_TWO for item in second["items"])


@pytest.mark.parametrize("kind", ["repo", "friction"])
def test_profile_content_change_reanalyzes_only_changed_object(monkeypatch, kind):
    call = provider(monkeypatch, kind)
    items, reuse = [profile_input(kind, i) for i in range(5)], AnalysisReuse()
    build(kind, items, DAY_ONE, reuse)
    items[2]["summary"] = "Materially different evidence."
    second = build(kind, items, DAY_TWO, AnalysisReuse(reuse.snapshot()))
    assert call.call_count == 6
    assert sum(item["analysis_reused"] for item in second["items"]) == 4


def test_repo_future_date_boundary_invalidates(monkeypatch):
    call = provider(monkeypatch, "repo")
    item, reuse = profile_input("repo"), AnalysisReuse()
    item["published_at"] = "2026-10-25T00:00:00Z"
    build("repo", [item], DAY_ONE, reuse)
    build("repo", [item], DAY_TWO, reuse)
    assert call.call_count == 2


@pytest.mark.parametrize("kind", ["insight", "repo", "friction"])
@pytest.mark.parametrize("failure", ["exception", "empty"])
def test_fallbacks_and_empty_outputs_are_never_cached(monkeypatch, kind, failure):
    call = Mock(side_effect=RuntimeError("provider failed")) if failure == "exception" else Mock(
        return_value=SimpleNamespace(parsed_json={}, raw_text="{}",
                                     route=SimpleNamespace(provider="openai", model="test-model")))
    monkeypatch.setattr(pipeline, "execute_routed_task", call)
    reuse = AnalysisReuse()
    for _ in range(2):
        if kind == "insight":
            output = pipeline.generate_insight(signal(), {}, reuse=reuse)
            assert output.execution["fallback_used"] is True
            assert output.execution["validation_passed"] is False
        else:
            build(kind, [profile_input(kind)], DAY_ONE, reuse)
    assert call.call_count == 2
    assert reuse.snapshot()["entries"] == {}


def test_persistence_prefers_s3_over_baked_local_file(monkeypatch, tmp_path):
    provider(monkeypatch, "insight")
    reuse = AnalysisReuse()
    pipeline.generate_insight(signal(), {}, reuse=reuse)
    (tmp_path / "daily_radar.json").write_text('{"analysis_reuse": {}}', encoding="utf-8")
    monkeypatch.setenv("AI_RADAR_LOCAL_ONLY", "0")
    monkeypatch.setenv("AI_RADAR_SKIP_S3_UPLOADS", "0")
    pipeline.s3_client.get_object.return_value = {
        "Body": BytesIO(json.dumps({"analysis_reuse": reuse.snapshot()}).encode())}
    loaded = pipeline._load_analysis_reuse()
    assert loaded.snapshot() == reuse.snapshot()
    pipeline.s3_client.get_object.assert_called_once_with(
        Bucket=pipeline.S3_BUCKET_NAME, Key="daily/latest/daily_radar.json")
    pipeline.s3_client.get_object.side_effect = RuntimeError("unavailable")
    assert pipeline._load_analysis_reuse().snapshot()["entries"] == {}


def test_local_state_load_and_corrupt_state_miss(monkeypatch, tmp_path):
    provider(monkeypatch, "insight")
    reuse = AnalysisReuse()
    pipeline.generate_insight(signal(), {}, reuse=reuse)
    path = tmp_path / "daily_radar.json"
    path.write_text(json.dumps({"analysis_reuse": reuse.snapshot()}), encoding="utf-8")
    assert pipeline._load_analysis_reuse().snapshot() == reuse.snapshot()
    pipeline.s3_client.get_object.assert_not_called()
    path.write_text("broken json", encoding="utf-8")
    assert pipeline._load_analysis_reuse().snapshot()["entries"] == {}
    damaged = reuse.snapshot()
    next(iter(damaged["entries"].values()))["result"]["why_it_matters"] = "tampered"
    assert AnalysisReuse(damaged).snapshot()["entries"] == {}
    for legacy in [None, [], {"version": 0}, {"version": 1, "entries": []}]:
        assert AnalysisReuse(legacy).snapshot()["entries"] == {}


def test_cache_limits_and_copy_isolation(monkeypatch):
    monkeypatch.setattr(reuse_module, "MAX_ENTRIES", 2)
    result = {**result_payload("repo"), "provider_used": "openai", "model_used": "test-model"}
    reuse, keys = AnalysisReuse(), []
    for i in range(3):
        key = analysis_fingerprint(kind="repo", provider="openai", model="test-model", messages=[str(i)])
        keys.append(key)
        reuse.remember(key, "repo", result, DAY_ONE)
    assert reuse.lookup(keys[0], "repo") is None
    hit = reuse.lookup(keys[1], "repo")
    hit["result"]["repo_summary"] = "changed externally"
    assert reuse.lookup(keys[1], "repo")["result"]["repo_summary"] == result["repo_summary"]
    monkeypatch.setattr(reuse_module, "MAX_STATE_BYTES", 1)
    assert AnalysisReuse(reuse.snapshot()).snapshot()["entries"] == {}


@pytest.mark.parametrize("qualified_count", [0, 2])
def test_full_pipeline_persists_reuse_and_next_day_makes_zero_calls(
    monkeypatch, tmp_path, qualified_count,
):
    class Clock(datetime):
        current = datetime.fromisoformat(DAY_ONE)

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(pipeline, "datetime", Clock)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
    monkeypatch.setattr(pipeline.settings, "validate", lambda: None)
    monkeypatch.setattr(pipeline, "INTELLIGENCE_OUTPUT_DIR", tmp_path / "intelligence")
    monkeypatch.setattr(pipeline, "PIPELINE_SIGNALS_FILE", tmp_path / "signals.json")
    items = [signal(i, score=0.8 if i < qualified_count else 0.5) for i in range(3)]
    for item in items:
        item.topic = "ai_agents"
        item.signal_type = "friction"
        item.metadata = {"repo_name": item.title}
    monkeypatch.setattr(pipeline, "load_personal_context", lambda: {"projects": ["radar"]})
    monkeypatch.setattr(pipeline, "load_ingestion_subscription_settings", lambda: {
        "signal_rules": {"auto_analyze_score": 70, "auto_backlog_score": 40}})
    monkeypatch.setattr(pipeline, "collect_signals", lambda: items)
    monkeypatch.setattr(pipeline, "enrich_and_filter_signals", lambda *a, **k: (items, {}))
    monkeypatch.setattr(pipeline, "attach_projects_to_signals", lambda items: items)
    for name in ("detect_trends", "compute_topic_trends", "compute_rising_topics",
                 "load_previous_topic_trends", "compute_topic_evolution",
                 "compute_weekly_topic_summary", "compute_weekly_momentum",
                 "compute_topic_momentum_safe", "compute_strategic_priority_topics",
                 "generate_daily_executive_summary", "build_intelligence_outputs"):
        monkeypatch.setattr(pipeline, name, lambda *a, **k: {})
    monkeypatch.setattr(pipeline, "_safe_record_artifact_write", lambda *a: None)
    monkeypatch.setattr(pipeline, "save_feed_activity", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_dated_daily_radar", lambda *a: tmp_path / "history.json")
    forbidden_upload = Mock(side_effect=AssertionError("No external writes in tests"))
    monkeypatch.setattr(pipeline, "upload_outputs_to_s3", forbidden_upload)

    def complete(**kwargs):
        user = kwargs["messages"][-1]["content"]
        kind = ("repo" if "Repo candidate:" in user else
                "friction" if "Friction signal:" in user else "insight")
        parsed = result_payload(kind)
        return SimpleNamespace(parsed_json=parsed, raw_text=json.dumps(parsed),
                               route=SimpleNamespace(provider="openai", model="test-model"))

    call = Mock(side_effect=complete)
    monkeypatch.setattr(pipeline, "execute_routed_task", call)
    pipeline._run_main_pipeline()
    assert call.call_count == 6 + qualified_count
    initial = json.loads((tmp_path / "daily_radar.json").read_text(encoding="utf-8"))
    assert initial["insight_count"] == qualified_count
    assert len(initial["analysis_reuse"]["entries"]) == 6 + qualified_count

    Clock.current = datetime.fromisoformat(DAY_TWO)
    for item in items:
        item.collected_at = DAY_TWO
    call.reset_mock()
    pipeline._run_main_pipeline()  # Loads the serialized file, not a retained cache object.
    call.assert_not_called()
    second = json.loads((tmp_path / "daily_radar.json").read_text(encoding="utf-8"))
    assert second["insight_count"] == qualified_count
    for name in ("agent_watch_repo_profiles", "friction_signal_profiles"):
        profiles = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
        assert profiles["count"] == 3
        assert all(item["analysis_reused"] for item in profiles["items"])
        assert all(item["generated_at"] == DAY_ONE for item in profiles["items"])
    forbidden_upload.assert_not_called()
    pipeline.s3_client.get_object.assert_not_called()
