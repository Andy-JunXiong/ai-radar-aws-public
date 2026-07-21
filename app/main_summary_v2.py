import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.exporters.topic_intelligence_exporter import export_topic_intelligence
from app.exporters.topic_momentum_exporter import export_topic_momentum
from app.exporters.topic_graph_exporter import export_topic_graph
from app.exporters.research_map_exporter import export_research_map
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ROOT_ENV_PATH)

import boto3
from app.exporters.obsidian_exporter_v2 import export_to_obsidian
from app.prompts.registry import (
    agent_repo_profile_prompts,
    friction_signal_profile_prompts,
    personalized_radar_insight_prompts,
)
from app.project_linker import link_signal_to_projects
from app.intelligence.topic_momentum_engine import compute_topic_momentum
from app.intelligence.strategic_priority_engine import compute_strategic_priority_topics
from app.intelligence.executive_summary_engine import generate_daily_executive_summary
from app.intelligence.manual_signal_promotion import load_and_promote_manual_signals
from app.intelligence.weekly_topic_summary import compute_weekly_topic_summary
from app.intelligence.weekly_momentum_engine import compute_weekly_momentum
from app.intelligence.history_loader import (
    load_previous_topic_trends,
    save_dated_daily_radar,
)
from app.intelligence.topic_evolution_engine import compute_topic_evolution
from app.intelligence.rising_topics_engine import compute_rising_topics
from app.intelligence.topic_trend_engine import compute_topic_trends
from app.intelligence.importance_engine import attach_importance_to_signals
from app.intelligence.topic_classifier import attach_topics_to_signals
from app.intelligence.trend_engine import detect_trends
from app.intelligence.novelty_score import compute_novelty_score
from app.intelligence.relevance_score import compute_keyword_relevance
from app.intelligence.llm_executor import execute_routed_task
from app.intelligence.model_router import route_task
from app.config import BASE_DIR, settings
from app.models import Insight, Signal
from app.storage.s3_writer import S3Writer
from app.sources.source_quality import compute_source_quality
from app.sources.source_filter import filter_signals
from signal_collectors.rss_collector import collect_rss_signals, save_signals
from signal_collectors.official_collector import collect_official_signals, save as save_official_signals
from signal_collectors.github_agent_collector import (
    collect_github_agent_signals,
    save as save_github_agent_signals,
)
from signal_collectors.hackernews_agent_collector import (
    collect_hackernews_agent_signals,
    save as save_hackernews_agent_signals,
)
from signal_collectors.hackernews_friction_collector import (
    collect_hackernews_friction_signals,
    save as save_hackernews_friction_signals,
)
from signal_collectors.github_friction_collector import (
    collect_github_friction_signals,
    save as save_github_friction_signals,
)
from signal_collectors.producthunt_agent_collector import (
    collect_producthunt_agent_signals,
    save as save_producthunt_agent_signals,
)
from signal_collectors.merge_signals import main as run_merge_signals
from app.intelligence.processors.agent_signal_processor import (
    collect_normalized_hackernews_agent_signals,
    collect_normalized_producthunt_agent_signals,
    normalize_github_agent_signals,
    save as save_agent_watch_signals,
)
from app.intelligence.processors.friction_signal_processor import (
    collect_normalized_friction_signals,
    save as save_friction_signals,
)
from app.intelligence.classifiers.agent_classifier import classify_agent_signals
from app.intelligence.scorers.agent_signal_scorer import attach_agent_scores_to_signals
from app.intelligence.tracking.agent_friction_tracking import (
    build_agent_watch_tracking_state,
    build_friction_tracking_state,
)
from backend.app.services.metrics_event_service import (
    METRICS_DIR,
    record_collector_run,
    record_artifact_write,
    append_pipeline_run,
)
from backend.app.services.metrics_summary_service import write_daily_metrics_summary
from backend.app.services.metrics_summary_service import write_monthly_metrics_summary
from backend.app.services.metrics_summary_service import write_weekly_metrics_summary

OUTPUT_DIR = BASE_DIR / "data" / "output"
CONTEXT_FILE = BASE_DIR / "app" / "context" / "personal_context.json"
COLLECTOR_SIGNALS_FILE = OUTPUT_DIR / "collected_signals.json"
PIPELINE_SIGNALS_FILE = OUTPUT_DIR / "signals.json"
MANUAL_SESSIONS_FILE = OUTPUT_DIR / "manual_sessions.json"
INTELLIGENCE_OUTPUT_DIR = OUTPUT_DIR / "intelligence"
MAX_SOURCE_EXCERPT_CHARS = 1200
CURRENT_PIPELINE_RUN_ID: str | None = None
ARTIFACT_WRITTEN_COUNT = 0
TRUE_ENV_VALUES = {"1", "true", "yes", "on"}

S3_BUCKET_NAME = os.getenv("AI_RADAR_S3_BUCKET") or os.getenv(
    "S3_BUCKET", "ai-radar-junxiong-data"
)
s3_client = boto3.client("s3")
DEFAULT_SUBSCRIPTION_SCOPE = (
    os.getenv("AI_RADAR_SUBSCRIPTION_SCOPE")
    or "admin_default"
).strip() or "admin_default"
SUBSCRIPTION_SETTINGS_S3_PREFIX = (
    os.getenv("SUBSCRIPTION_SETTINGS_S3_PREFIX")
    or "settings/subscriptions"
).strip().strip("/")
LOCAL_SUBSCRIPTION_SETTINGS_FILE = (
    BASE_DIR
    / "backend"
    / "data"
    / "settings"
    / "subscriptions"
    / f"{DEFAULT_SUBSCRIPTION_SCOPE}.json"
)

def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTELLIGENCE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_ENV_VALUES


def s3_uploads_disabled() -> bool:
    return _env_flag_enabled("AI_RADAR_LOCAL_ONLY") or _env_flag_enabled(
        "AI_RADAR_SKIP_S3_UPLOADS"
    )


def _bounded_source_excerpt_value(value: object) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:MAX_SOURCE_EXCERPT_CHARS]


def _copy_source_excerpt_to_signal(signal: Signal, item: dict) -> None:
    source_excerpt = _bounded_source_excerpt_value(item.get("source_excerpt"))
    if source_excerpt:
        setattr(signal, "source_excerpt", source_excerpt)
        setattr(signal, "source_excerpt_length", len(source_excerpt))


def _duration_seconds(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 3)


def _safe_record_collector_run(event: dict) -> None:
    try:
        record_collector_run(event)
    except Exception as exc:
        print(f"[metrics] failed to record collector run: {exc}")


def _safe_record_pipeline_run(event: dict) -> None:
    try:
        append_pipeline_run(event)
    except Exception as exc:
        print(f"[metrics] failed to record pipeline run: {exc}")


def _safe_record_artifact_write(event: dict) -> None:
    try:
        record_artifact_write(event)
    except Exception as exc:
        print(f"[metrics] failed to record artifact write: {exc}")


def _safe_write_daily_metrics_summary(date: str) -> None:
    try:
        daily_path = write_daily_metrics_summary(date)
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        iso_week = parsed_date.isocalendar()
        weekly_path = write_weekly_metrics_summary(f"{iso_week.year}-W{iso_week.week:02d}")
        monthly_path = write_monthly_metrics_summary(date[:7])
        print(f"[metrics] daily summary written: {daily_path}")
        print(f"[metrics] weekly summary written: {weekly_path}")
        print(f"[metrics] monthly summary written: {monthly_path}")
    except Exception as exc:
        print(f"[metrics] failed to write metrics summaries: {exc}")


def _metrics_artifact_candidates(date: str) -> list[tuple[Path, str]]:
    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    iso_week = parsed_date.isocalendar()
    week_key = f"{iso_week.year}-W{iso_week.week:02d}"
    month_key = date[:7]

    return [
        (
            METRICS_DIR / "pipeline_runs" / f"{date}.json",
            f"metrics/pipeline_runs/{date}.json",
        ),
        (
            METRICS_DIR / "collector_runs" / f"{date}.jsonl",
            f"metrics/collector_runs/{date}.jsonl",
        ),
        (
            METRICS_DIR / "artifact_writes" / f"{date}.jsonl",
            f"metrics/artifact_writes/{date}.jsonl",
        ),
        (METRICS_DIR / "llm_calls" / f"{date}.jsonl", f"metrics/llm_calls/{date}.jsonl"),
        (
            METRICS_DIR / "verification_events" / f"{date}.jsonl",
            f"metrics/verification_events/{date}.jsonl",
        ),
        (
            METRICS_DIR / "daily_summary" / f"{date}.json",
            f"metrics/daily_summary/{date}.json",
        ),
        (
            METRICS_DIR / "weekly_summary" / f"{week_key}.json",
            f"metrics/weekly_summary/{week_key}.json",
        ),
        (
            METRICS_DIR / "monthly_summary" / f"{month_key}.json",
            f"metrics/monthly_summary/{month_key}.json",
        ),
    ]


def _upload_metrics_outputs_to_s3(s3: S3Writer, date: str) -> int:
    uploaded_count = 0
    latest_summary_keys = {
        "daily_summary": "metrics/latest/daily_summary.json",
        "weekly_summary": "metrics/latest/weekly_summary.json",
        "monthly_summary": "metrics/latest/monthly_summary.json",
    }

    for path, s3_key in _metrics_artifact_candidates(date):
        if not path.exists():
            continue

        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            s3.upload_json(payload, s3_key)
            category = path.parent.name
            latest_key = latest_summary_keys.get(category)
            if latest_key:
                s3.upload_json(payload, latest_key)
                uploaded_count += 1
        else:
            s3.upload_text(
                path.read_text(encoding="utf-8"),
                s3_key,
                content_type="application/x-ndjson",
            )

        uploaded_count += 1

    return uploaded_count


def _safe_upload_metrics_outputs_to_s3(date: str) -> None:
    if s3_uploads_disabled():
        print("[metrics] S3 uploads disabled by local-only setting. Skip metrics upload.")
        return

    try:
        uploaded_count = _upload_metrics_outputs_to_s3(S3Writer(), date)
        print(f"[metrics] uploaded metrics artifacts to S3: {uploaded_count}")
    except Exception as exc:
        print(f"[metrics] failed to upload metrics artifacts to S3: {exc}")


def _record_collector_result(
    *,
    collector_name: str,
    started_at: float,
    success: bool,
    items_fetched: int | None = None,
    items_normalized: int | None = None,
    items_written: int | None = None,
    error_count: int = 0,
    retry_count: int = 0,
    error_type: str | None = None,
) -> None:
    _safe_record_collector_run(
        {
            "run_id": CURRENT_PIPELINE_RUN_ID,
            "collector_name": collector_name,
            "started_at": datetime.now(settings.timezone).isoformat(),
            "duration_seconds": _duration_seconds(started_at),
            "success": success,
            "items_fetched": items_fetched,
            "items_normalized": items_normalized,
            "items_written": items_written,
            "error_count": error_count,
            "retry_count": retry_count,
            "error_type": error_type,
        }
    )


def _run_collector_step(
    collector_name: str,
    collect_fn,
    save_fn=None,
    normalize_fn=None,
):
    started_at = time.perf_counter()
    try:
        items = collect_fn()
        if save_fn:
            save_fn(items)
        normalized_items = normalize_fn(items) if normalize_fn else None
        items_fetched = len(items) if isinstance(items, list) else None
        items_normalized = (
            len(normalized_items) if isinstance(normalized_items, list) else None
        )
        _record_collector_result(
            collector_name=collector_name,
            started_at=started_at,
            success=True,
            items_fetched=items_fetched,
            items_normalized=items_normalized,
            items_written=items_fetched,
        )
        return items, normalized_items
    except Exception as exc:
        _record_collector_result(
            collector_name=collector_name,
            started_at=started_at,
            success=False,
            error_count=1,
            error_type=type(exc).__name__,
        )
        raise


def _default_subscription_settings() -> dict:
    return {
        "user_id": DEFAULT_SUBSCRIPTION_SCOPE,
        "sources": [],
        "topic_preferences": {
            "preferred_topics": [],
            "blocked_topics": [],
            "boosted_topics": [],
        },
        "signal_rules": {
            "min_score": 45,
            "auto_analyze_score": 70,
            "auto_backlog_score": 60,
            "max_signals_per_day": 25,
        },
        "project_links": [],
    }


def _subscription_settings_s3_key() -> str:
    return f"{SUBSCRIPTION_SETTINGS_S3_PREFIX}/{DEFAULT_SUBSCRIPTION_SCOPE}.json"


def _normalize_subscription_settings_payload(payload: object) -> dict:
    default = _default_subscription_settings()
    if not isinstance(payload, dict):
        return default

    merged = {
        **default,
        **payload,
        "topic_preferences": {
            **default["topic_preferences"],
            **(payload.get("topic_preferences") or {}),
        },
        "signal_rules": {
            **default["signal_rules"],
            **(payload.get("signal_rules") or {}),
        },
    }

    if not isinstance(merged.get("sources"), list):
        merged["sources"] = []
    if not isinstance(merged.get("project_links"), list):
        merged["project_links"] = []

    return merged


def load_ingestion_subscription_settings() -> dict:
    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=_subscription_settings_s3_key(),
        )
        payload = json.loads(response["Body"].read().decode("utf-8"))
        normalized = _normalize_subscription_settings_payload(payload)
        try:
            LOCAL_SUBSCRIPTION_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOCAL_SUBSCRIPTION_SETTINGS_FILE.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return normalized
    except Exception:
        pass

    if LOCAL_SUBSCRIPTION_SETTINGS_FILE.exists():
        try:
            payload = json.loads(LOCAL_SUBSCRIPTION_SETTINGS_FILE.read_text(encoding="utf-8"))
            return _normalize_subscription_settings_payload(payload)
        except Exception:
            pass

    return _default_subscription_settings()


def _score_as_percent(value: object) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric <= 1:
        numeric *= 100
    return numeric


def _pipeline_execution_policy(
    *,
    task_type: str,
    importance_score: float | None = None,
    requires_traceability: bool = False,
) -> dict:
    score = _score_as_percent(importance_score)
    normalized_task = str(task_type or "").strip().lower()

    if requires_traceability or normalized_task in {"strategic_intelligence", "strategy", "decision_support"}:
        return {
            "mode": "critical",
            "effective_task_type": "strategy" if normalized_task != "reason" else "reason",
            "citation_required": True,
            "verification_required": True,
            "model_tier": "strong",
            "policy_reason": "strategic_or_traceable_output",
        }

    if normalized_task in {"radar_summary", "manual_analysis", "workspace_answer", "trend_synthesis"} or (
        score is not None and score >= 70
    ):
        return {
            "mode": "guarded",
            "effective_task_type": "reason" if normalized_task == "radar_summary" else normalized_task,
            "citation_required": True,
            "verification_required": False,
            "model_tier": "standard",
            "policy_reason": "user_visible_factual_output",
        }

    return {
        "mode": "fast",
        "effective_task_type": normalized_task,
        "citation_required": False,
        "verification_required": False,
        "model_tier": "cheap",
        "policy_reason": "low_risk_output",
    }


def _apply_pipeline_policy_prompt(system_prompt: str, *, policy: dict) -> str:
    lines = [system_prompt.strip(), "", "EXECUTION POLICY"]
    lines.append(f"- mode: {policy['mode']}")
    if policy.get("citation_required"):
        lines.extend(
            [
                "- Base the answer only on the provided context.",
                "- Cite source IDs or evidence labels when available using [Evidence: ...].",
                "- If evidence is insufficient, say Uncertain instead of overstating.",
            ]
        )
    elif policy.get("verification_required"):
        lines.append("- Mark unsupported claims as Uncertain.")
    else:
        lines.append("- Keep the output concise and cheap.")
    return "\n".join(lines).strip()


def _is_manual_signal_item(item: dict) -> bool:
    source = str(item.get("source") or "").strip().lower()
    return bool(
        item.get("is_manual")
        or item.get("manual_session_id")
        or source.startswith("manual")
    )


def _match_subscription_source(item: dict, source: dict) -> bool:
    item_url = str(item.get("url") or item.get("link") or "").strip().lower()
    item_source = str(item.get("source") or "").strip().lower()
    configured_url = str(source.get("url") or "").strip().lower()
    configured_name = str(source.get("name") or "").strip().lower()

    if configured_url and item_url:
        if configured_url in item_url or item_url in configured_url:
            return True
        try:
            configured_host = configured_url.split("/")[2]
            item_host = item_url.split("/")[2]
            if configured_host and item_host and configured_host == item_host:
                return True
        except Exception:
            pass

    if configured_name and item_source and configured_name in item_source:
        return True

    return False


def apply_subscription_settings_to_pipeline_signals(
    signals_data: list[dict],
    subscription_settings: dict | None,
) -> list[dict]:
    if not subscription_settings:
        return signals_data

    topic_preferences = subscription_settings.get("topic_preferences") or {}
    signal_rules = subscription_settings.get("signal_rules") or {}
    sources = subscription_settings.get("sources") or []

    preferred_topics = {
        str(item).strip().lower()
        for item in topic_preferences.get("preferred_topics", [])
        if str(item).strip()
    }
    blocked_topics = {
        str(item).strip().lower()
        for item in topic_preferences.get("blocked_topics", [])
        if str(item).strip()
    }
    boosted_topics = {
        str(item).strip().lower()
        for item in topic_preferences.get("boosted_topics", [])
        if str(item).strip()
    }
    active_sources = [
        item
        for item in sources
        if isinstance(item, dict) and item.get("enabled")
    ]

    min_score = float(signal_rules.get("min_score", 0) or 0)
    max_signals_per_day = int(signal_rules.get("max_signals_per_day", 0) or 0)

    filtered: list[dict] = []
    for item in signals_data:
        topic = str(item.get("topic") or "").strip().lower()
        score_percent = _score_as_percent(item.get("score"))
        is_manual = _is_manual_signal_item(item)

        if topic and topic in blocked_topics:
            continue

        if active_sources and not is_manual:
            if not any(_match_subscription_source(item, source) for source in active_sources):
                continue

        if not is_manual and score_percent is not None and score_percent < min_score:
            continue

        topic_priority = "normal"
        if topic and topic in preferred_topics:
            topic_priority = "preferred"
        if topic and topic in boosted_topics:
            topic_priority = "boosted"

        filtered.append(
            {
                **item,
                "subscription_score_percent": score_percent,
                "subscription_topic_priority": topic_priority,
            }
        )

    filtered.sort(
        key=lambda item: (
            2 if item.get("subscription_topic_priority") == "boosted" else 1 if item.get("subscription_topic_priority") == "preferred" else 0,
            item.get("subscription_score_percent") or 0,
            item.get("recency_score") or 0,
        ),
        reverse=True,
    )

    if max_signals_per_day > 0:
        filtered = filtered[:max_signals_per_day]

    return filtered


def build_subscription_source_summary(
    signals_data: list[dict],
    subscription_settings: dict | None,
) -> dict:
    settings = subscription_settings or {}
    configured_sources = settings.get("sources") or []

    active_source_items = [
        item
        for item in configured_sources
        if isinstance(item, dict) and item.get("enabled")
    ]

    configured_names = [
        str(item.get("name") or item.get("url") or "").strip()
        for item in active_source_items
        if str(item.get("name") or item.get("url") or "").strip()
    ]

    matched_runtime_sources = sorted(
        {
            str(item.get("source") or "").strip()
            for item in signals_data
            if str(item.get("source") or "").strip()
        }
    )

    matched_subscription_sources: list[str] = []
    unmatched_active_sources: list[str] = []

    for source_item in active_source_items:
        display_name = str(source_item.get("name") or source_item.get("url") or "").strip()
        if not display_name:
            continue
        if any(_match_subscription_source(signal, source_item) for signal in signals_data):
            matched_subscription_sources.append(display_name)
        else:
            unmatched_active_sources.append(display_name)

    return {
        "configured_active_sources": configured_names,
        "configured_active_source_count": len(configured_names),
        "matched_subscription_sources": matched_subscription_sources,
        "matched_subscription_source_count": len(matched_subscription_sources),
        "unmatched_active_sources": unmatched_active_sources,
        "runtime_signal_sources": matched_runtime_sources,
    }


def build_agent_watch_summary(signals_data: list[dict]) -> dict:
    agent_signals = [
        item
        for item in signals_data
        if isinstance(item, dict) and str(item.get("topic") or "").strip().lower() == "ai_agents"
    ]

    def _sort_key(item: dict) -> tuple[float, float, str]:
        try:
            primary = float(item.get("agent_watch_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    top_signals = sorted(agent_signals, key=_sort_key, reverse=True)[:3]
    highlights: list[dict] = []
    runtime_sources = sorted(
        {
            str(item.get("source") or "").strip().lower()
            for item in agent_signals
            if str(item.get("source") or "").strip()
        }
    )

    for item in top_signals:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        highlights.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "agent_subtopic": item.get("agent_subtopic"),
                "agent_watch_score": item.get("agent_watch_score"),
                "repo_stars": metadata.get("repo_stars"),
                "language": metadata.get("language"),
                "matched_keywords": metadata.get("matched_keywords", []),
            }
        )

    return {
        "signal_count": len(agent_signals),
        "top_signal_count": len(highlights),
        "runtime_sources": runtime_sources,
        "highlights": highlights,
    }


def _load_agent_watch_tracking_candidates(signals_data: list[dict]) -> list[dict]:
    agent_signals = [
        item
        for item in signals_data
        if isinstance(item, dict) and str(item.get("topic") or "").strip().lower() == "ai_agents"
    ]
    if agent_signals:
        return agent_signals

    agent_watch_file = OUTPUT_DIR / "agent_watch_signals.json"
    if agent_watch_file.exists():
        try:
            payload = json.loads(agent_watch_file.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
                return [item for item in payload["signals"] if isinstance(item, dict)]
        except Exception as e:
            print(f"[WARN] Failed to load agent watch fallback signals for tracking: {e}")

    return []


def build_agent_watch_repo_snapshots(signals_data: list[dict], generated_at: str) -> dict:
    agent_signals = _load_agent_watch_tracking_candidates(signals_data)

    snapshots: list[dict] = []
    seen_entities: set[str] = set()

    def _sort_key(item: dict) -> tuple[float, float, str]:
        try:
            primary = float(item.get("agent_watch_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    for item in sorted(agent_signals, key=_sort_key, reverse=True):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        canonical_url = str(metadata.get("repo_url") or item.get("url") or "").strip()
        if not canonical_url:
            continue

        entity_id = canonical_url.lower()
        if entity_id in seen_entities:
            continue
        seen_entities.add(entity_id)

        snapshots.append(
            {
                "entity_id": entity_id,
                "title": item.get("title", ""),
                "canonical_url": canonical_url,
                "source": item.get("source", ""),
                "source_type": item.get("source_type", ""),
                "agent_subtopic": item.get("agent_subtopic"),
                "published_at": item.get("published_at", ""),
                "captured_at": generated_at,
                "agent_watch_score": item.get("agent_watch_score"),
                "signal_score": item.get("score"),
                "repo_name": metadata.get("repo_name"),
                "repo_stars": metadata.get("repo_stars"),
                "language": metadata.get("language"),
                "hn_points": metadata.get("hn_points"),
                "hn_comments": metadata.get("hn_comments"),
                "product_hunt_votes": metadata.get("product_hunt_votes"),
                "matched_keywords": metadata.get("matched_keywords", []),
                "tags": metadata.get("tags", []),
            }
        )

    return {
        "generated_at": generated_at,
        "count": len(snapshots),
        "items": snapshots,
    }


def build_agent_watch_repo_profiles(signals_data: list[dict], generated_at: str) -> dict:
    agent_signals = _load_agent_watch_tracking_candidates(signals_data)

    try:
        profile_limit = max(1, int(os.getenv("AGENT_WATCH_REPO_PROFILE_LIMIT", "5")))
    except Exception:
        profile_limit = 5

    profiled_items: list[dict] = []
    seen_entities: set[str] = set()

    def _sort_key(item: dict) -> tuple[float, float, str]:
        try:
            primary = float(item.get("agent_watch_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    def _fallback_profile(item: dict, metadata: dict) -> dict:
        title = _clean_text(str(item.get("title") or ""))
        summary = _clean_text(str(item.get("summary") or ""))
        subtopic = _clean_text(str(item.get("agent_subtopic") or "agent_repo"))
        repo_name = _clean_text(str(metadata.get("repo_name") or ""))
        subject = repo_name or title or "This repo"

        return {
            "repo_summary": summary or f"{subject} is currently tracked in Agent Watch.",
            "what_it_does": summary or f"{subject} appears to be an {subtopic} project in the AI agent ecosystem.",
            "why_it_matters": f"{subject} is showing enough signal strength to enter the current watchlist.",
            "project_fit": f"Review {subject} for ideas, implementation patterns, and relevance to your current AI Radar work.",
            "suggested_use_cases": [
                "Study the repo positioning and implementation approach.",
                "Compare it with your current AI Radar intelligence features.",
            ],
            "risks": [
                "This fallback profile is based on limited repo surface data only.",
            ],
            "confidence": "low",
        }

    for item in sorted(agent_signals, key=_sort_key, reverse=True):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        canonical_url = str(metadata.get("repo_url") or item.get("url") or "").strip()
        if not canonical_url:
            continue

        entity_id = canonical_url.lower()
        if entity_id in seen_entities:
            continue
        seen_entities.add(entity_id)

        profile_input = {
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "source_type": item.get("source_type", ""),
            "published_at": item.get("published_at", ""),
            "agent_subtopic": item.get("agent_subtopic"),
            "agent_watch_score": item.get("agent_watch_score"),
            "repo_name": metadata.get("repo_name"),
            "repo_stars": metadata.get("repo_stars"),
            "language": metadata.get("language"),
            "matched_keywords": metadata.get("matched_keywords", []),
            "tags": metadata.get("tags", []),
            "hn_points": metadata.get("hn_points"),
            "hn_comments": metadata.get("hn_comments"),
            "product_hunt_votes": metadata.get("product_hunt_votes"),
        }

        normalized_profile = None
        provider_used = None
        model_used = None
        policy_metadata = None

        try:
            system_prompt, user_prompt = agent_repo_profile_prompts(
                repo_candidate_payload=profile_input,
                current_date=generated_at[:10],
            )
            policy = _pipeline_execution_policy(
                task_type="strategic_intelligence",
                importance_score=item.get("agent_watch_score"),
                requires_traceability=True,
            )
            result = execute_routed_task(
                task_type=policy["effective_task_type"],
                temperature=0.2,
                json_mode=True,
                max_tokens=1200,
                messages=[
                    {"role": "system", "content": _apply_pipeline_policy_prompt(system_prompt, policy=policy)},
                    {"role": "user", "content": user_prompt},
                ],
            )
            parsed = result.parsed_json or {}
            normalized_profile = {
                "repo_summary": _clean_text(str(parsed.get("repo_summary") or "")),
                "what_it_does": _clean_text(str(parsed.get("what_it_does") or "")),
                "why_it_matters": _clean_text(str(parsed.get("why_it_matters") or "")),
                "project_fit": _clean_text(str(parsed.get("project_fit") or "")),
                "suggested_use_cases": [
                    _clean_text(str(value))
                    for value in (parsed.get("suggested_use_cases") or [])
                    if _clean_text(str(value))
                ],
                "risks": [
                    _clean_text(str(value))
                    for value in (parsed.get("risks") or [])
                    if _clean_text(str(value))
                ],
                "confidence": _clean_text(str(parsed.get("confidence") or "")) or "medium",
            }
            provider_used = result.route.provider
            model_used = result.route.model
            policy_metadata = policy
        except Exception as e:
            print(f"[WARN] Agent watch repo profile failed for '{item.get('title', '')[:80]}': {e}")

        if not normalized_profile:
            normalized_profile = _fallback_profile(item, metadata)

        profiled_items.append(
            {
                "entity_id": entity_id,
                "generated_at": generated_at,
                "title": item.get("title", ""),
                "canonical_url": canonical_url,
                "source": item.get("source", ""),
                "agent_subtopic": item.get("agent_subtopic"),
                "provider_used": provider_used,
                "model_used": model_used,
                "execution_policy": policy_metadata,
                **normalized_profile,
            }
        )

        if len(profiled_items) >= profile_limit:
            break

    return {
        "generated_at": generated_at,
        "count": len(profiled_items),
        "items": profiled_items,
    }


def build_friction_signals_summary(signals_data: list[dict]) -> dict:
    friction_signals = [
        item
        for item in signals_data
        if isinstance(item, dict) and str(item.get("signal_type") or "").strip().lower() == "friction"
    ]

    def _sort_key(item: dict) -> tuple[float, float, str]:
        try:
            primary = float(item.get("friction_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("pain_severity_score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    top_signals = sorted(friction_signals, key=_sort_key, reverse=True)[:3]
    highlights: list[dict] = []
    runtime_sources = sorted(
        {
            str(item.get("source") or "").strip().lower()
            for item in friction_signals
            if str(item.get("source") or "").strip()
        }
    )

    for item in top_signals:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        highlights.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "friction_subtopic": item.get("friction_subtopic"),
                "friction_score": item.get("friction_score"),
                "pain_severity_score": item.get("pain_severity_score"),
                "ecosystem_relevance_score": item.get("ecosystem_relevance_score"),
                "repo_name": metadata.get("repo_name"),
                "matched_keywords": metadata.get("matched_keywords", []),
            }
        )

    return {
        "signal_count": len(friction_signals),
        "top_signal_count": len(highlights),
        "runtime_sources": runtime_sources,
        "highlights": highlights,
    }


def _load_friction_profile_candidates(signals_data: list[dict]) -> list[dict]:
    friction_signals = [
        item
        for item in signals_data
        if isinstance(item, dict) and str(item.get("signal_type") or "").strip().lower() == "friction"
    ]
    if friction_signals:
        return friction_signals

    friction_file = OUTPUT_DIR / "friction_signals.json"
    if friction_file.exists():
        try:
            payload = json.loads(friction_file.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
                return [item for item in payload["signals"] if isinstance(item, dict)]
        except Exception as e:
            print(f"[WARN] Failed to load friction fallback signals for profiling: {e}")

    return []


def build_friction_signal_profiles(signals_data: list[dict], generated_at: str) -> dict:
    friction_signals = _load_friction_profile_candidates(signals_data)

    try:
        profile_limit = max(1, int(os.getenv("FRICTION_SIGNAL_PROFILE_LIMIT", "5")))
    except Exception:
        profile_limit = 5

    profiled_items: list[dict] = []
    seen_entities: set[str] = set()

    def _sort_key(item: dict) -> tuple[float, float, str]:
        try:
            primary = float(item.get("friction_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("pain_severity_score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    def _fallback_profile(item: dict, metadata: dict) -> dict:
        title = _clean_text(str(item.get("title") or "This signal"))
        summary = _clean_text(str(item.get("summary") or ""))
        subtopic = _clean_text(str(item.get("friction_subtopic") or "general friction"))
        repo_name = _clean_text(str(item.get("repo_name") or metadata.get("repo_name") or ""))
        subject = repo_name or title

        return {
            "problem_summary": summary or f"{subject} surfaces a friction signal in the AI ecosystem.",
            "why_this_matters": f"{subject} indicates repeated pain around {subtopic}, which may affect adoption or trust.",
            "who_is_affected": "Builders and users encountering this workflow or implementation problem.",
            "product_opportunity": "Review whether this pain suggests a tooling, workflow, or UX opportunity.",
            "suggested_response": [
                "Inspect the concrete complaint pattern behind this signal.",
                "Compare it with similar issues already visible in AI Radar.",
            ],
            "confidence": "low",
        }

    for item in sorted(friction_signals, key=_sort_key, reverse=True):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        entity_key = _clean_text(str(item.get("url") or item.get("title") or "")).lower()
        if not entity_key or entity_key in seen_entities:
            continue
        seen_entities.add(entity_key)

        profile_input = {
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "published_at": item.get("published_at", ""),
            "friction_subtopic": item.get("friction_subtopic"),
            "friction_score": item.get("friction_score"),
            "pain_severity_score": item.get("pain_severity_score"),
            "ecosystem_relevance_score": item.get("ecosystem_relevance_score"),
            "repo_name": item.get("repo_name") or metadata.get("repo_name"),
            "matched_keywords": item.get("matched_keywords") or metadata.get("matched_keywords") or [],
            "metadata": metadata,
        }

        normalized_profile = None
        provider_used = None
        model_used = None
        policy_metadata = None

        try:
            system_prompt, user_prompt = friction_signal_profile_prompts(
                friction_signal_payload=profile_input
            )
            policy = _pipeline_execution_policy(
                task_type="strategic_intelligence",
                importance_score=item.get("friction_score"),
                requires_traceability=True,
            )
            result = execute_routed_task(
                task_type=policy["effective_task_type"],
                temperature=0.2,
                json_mode=True,
                max_tokens=1100,
                messages=[
                    {"role": "system", "content": _apply_pipeline_policy_prompt(system_prompt, policy=policy)},
                    {"role": "user", "content": user_prompt},
                ],
            )
            parsed = result.parsed_json or {}
            normalized_profile = {
                "problem_summary": _clean_text(str(parsed.get("problem_summary") or "")),
                "why_this_matters": _clean_text(str(parsed.get("why_this_matters") or "")),
                "who_is_affected": _clean_text(str(parsed.get("who_is_affected") or "")),
                "product_opportunity": _clean_text(str(parsed.get("product_opportunity") or "")),
                "suggested_response": [
                    _clean_text(str(value))
                    for value in (parsed.get("suggested_response") or [])
                    if _clean_text(str(value))
                ],
                "confidence": _clean_text(str(parsed.get("confidence") or "")) or "medium",
            }
            provider_used = result.route.provider
            model_used = result.route.model
            policy_metadata = policy
        except Exception as e:
            print(f"[WARN] Friction signal profile failed for '{item.get('title', '')[:80]}': {e}")

        if not normalized_profile:
            normalized_profile = _fallback_profile(item, metadata)

        profiled_items.append(
            {
                "entity_id": entity_key,
                "generated_at": generated_at,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "friction_subtopic": item.get("friction_subtopic"),
                "provider_used": provider_used,
                "model_used": model_used,
                "execution_policy": policy_metadata,
                **normalized_profile,
            }
        )

        if len(profiled_items) >= profile_limit:
            break

    return {
        "generated_at": generated_at,
        "count": len(profiled_items),
        "items": profiled_items,
    }


def load_personal_context() -> dict:
    if not CONTEXT_FILE.exists():
        return {
            "background": "",
            "projects": [],
            "technical_focus": [],
            "interests": [],
            "thinking_style": "",
            "writing_style": "",
            "career_direction": "",
        }

    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_sample_signals() -> list[Signal]:
    now = datetime.now(settings.timezone).isoformat()

    signals = [
        Signal(
            title="AI agents are shifting from demo workflows to production operations",
            summary=(
                "More teams are moving agent systems from experimental prototypes "
                "into operational pipelines with stronger observability, guardrails, "
                "and workflow orchestration."
            ),
            url="https://example.com/ai-agents-production",
            author="Sample Source",
            source="sample",
            category="AI Agent",
            published_at=now,
            collected_at=now,
        ),
        Signal(
            title="Context engineering is becoming as important as prompt engineering",
            summary=(
                "Stable context pipelines, structured memory, and reliable retrieval "
                "are increasingly seen as critical for production AI systems."
            ),
            url="https://example.com/context-engineering",
            author="Sample Source",
            source="sample",
            category="AI Architect",
            published_at=now,
            collected_at=now,
        ),
    ]

    return signals[: settings.max_signals_per_run]


def compute_recency_score(published_at: str) -> float:
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours = (now - pub).total_seconds() / 3600

        if hours < 6:
            return 1.0
        elif hours < 24:
            return 0.8
        elif hours < 48:
            return 0.6
        else:
            return 0.3
    except Exception:
        return 0.5


def load_signals_from_file() -> list[Signal]:
    """
    Load raw signals from output/collected_signals.json generated by collectors.
    Supports two formats:
    1. list[dict]
    2. {"generated_at": ..., "signals": [...]}
    """
    if not COLLECTOR_SIGNALS_FILE.exists():
        print(f"Collector signals file not found: {COLLECTOR_SIGNALS_FILE}")
        return []

    try:
        with open(COLLECTOR_SIGNALS_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Failed to read signals file: {e}")
        return []

    if isinstance(raw_data, dict) and "signals" in raw_data:
        raw_signals = raw_data.get("signals", [])
    elif isinstance(raw_data, list):
        raw_signals = raw_data
    else:
        print("Signals file format not recognized.")
        return []

    signals: list[Signal] = []

    for idx, item in enumerate(raw_signals, start=1):
        try:
            raw_summary = (item.get("summary") or "").strip()
            raw_content = (item.get("content") or "").strip()
            summary = raw_summary if raw_summary else raw_content

            author = item.get("author", "Unknown")
            source = item.get("source", "external")
            url = item.get("url") or item.get("link", "")

            published_at = (
                item.get("published_at")
                or item.get("timestamp")
                or datetime.now(settings.timezone).isoformat()
            )
            collected_at = (
                item.get("collected_at")
                or datetime.now(settings.timezone).isoformat()
            )

            title = item.get("title")
            if not title:
                fallback_text = summary or raw_content
                if fallback_text:
                    title = fallback_text[:120].replace("\n", " ").strip()
                else:
                    title = f"Signal {idx}"

            category = item.get("category", source)

            signal = Signal(
                title=title,
                summary=summary,
                url=url,
                author=author,
                source=source,
                category=category,
                published_at=published_at,
                collected_at=collected_at,
            )

            setattr(signal, "source_weight", item.get("source_weight", 0.5))

            if "quality_level" in item:
                setattr(signal, "quality_level", item.get("quality_level", "unknown"))

            if "topic" in item:
                setattr(signal, "topic", item.get("topic", "General AI"))

            if isinstance(item.get("metadata"), dict):
                setattr(signal, "metadata", item.get("metadata"))

            _copy_source_excerpt_to_signal(signal, item)

            for field in (
                "signal_type",
                "agent_subtopic",
                "friction_subtopic",
                "pain_severity_score",
                "ecosystem_relevance_score",
                "friction_score",
                "agent_relevance_score",
                "buildability_score",
                "strategic_relevance_score",
                "agent_watch_score",
            ):
                if field in item:
                    setattr(signal, field, item.get(field))

            signals.append(signal)

        except Exception as e:
            print(f"Failed to parse signal #{idx}: {e}")

    return signals


def run_collectors() -> None:
    """
    Orchestrate upstream data generation before the main pipeline reads inputs.

    Active layers:
    1. rss_collector.py
    2. official_collector.py
    3. github_agent_collector.py
    4. hackernews_agent_collector.py
    5. producthunt_agent_collector.py
    6. friction collectors
    7. manual signals
    8. merge_signals.py
    """
    print("=== STEP 1: Collect RSS signals ===")
    rss_signals, _ = _run_collector_step(
        "rss_collector",
        collect_rss_signals,
        save_fn=save_signals,
    )
    print(f"RSS signals generated: {len(rss_signals)}")

    print("=== STEP 2: Collect official signals ===")
    official_signals, _ = _run_collector_step(
        "official_collector",
        collect_official_signals,
        save_fn=save_official_signals,
    )
    print(f"Official signals generated: {len(official_signals)}")

    print("=== STEP 3: Collect agent watch signals ===")
    github_agent_signals, normalized_agent_signals = _run_collector_step(
        "github_agent_collector",
        collect_github_agent_signals,
        save_fn=save_github_agent_signals,
        normalize_fn=normalize_github_agent_signals,
    )
    hackernews_agent_signals, _ = _run_collector_step(
        "hackernews_agent_collector",
        collect_hackernews_agent_signals,
        save_fn=save_hackernews_agent_signals,
    )
    normalized_agent_signals.extend(collect_normalized_hackernews_agent_signals())
    producthunt_agent_signals, _ = _run_collector_step(
        "producthunt_agent_collector",
        collect_producthunt_agent_signals,
        save_fn=save_producthunt_agent_signals,
    )
    normalized_agent_signals.extend(collect_normalized_producthunt_agent_signals())
    classified_agent_signals = classify_agent_signals(normalized_agent_signals)
    scored_agent_signals = attach_agent_scores_to_signals(classified_agent_signals)
    save_agent_watch_signals(scored_agent_signals)
    print(
        f"Agent watch signals generated: "
        f"{len(github_agent_signals)} github raw + "
        f"{len(hackernews_agent_signals)} hn raw + "
        f"{len(producthunt_agent_signals)} producthunt raw / "
        f"{len(scored_agent_signals)} normalized"
    )

    print("=== STEP 4: Collect friction signals ===")
    github_friction_signals, _ = _run_collector_step(
        "github_friction_collector",
        collect_github_friction_signals,
        save_fn=save_github_friction_signals,
    )
    hackernews_friction_signals, _ = _run_collector_step(
        "hackernews_friction_collector",
        collect_hackernews_friction_signals,
        save_fn=save_hackernews_friction_signals,
    )
    normalized_friction_signals = collect_normalized_friction_signals()
    save_friction_signals(normalized_friction_signals)
    print(
        f"Friction signals generated: "
        f"{len(github_friction_signals)} github raw + "
        f"{len(hackernews_friction_signals)} hn raw / "
        f"{len(normalized_friction_signals)} normalized"
    )

    print("=== STEP 5: Merge signals ===")
    merge_started_at = time.perf_counter()
    try:
        run_merge_signals()
        _record_collector_result(
            collector_name="merge_signals",
            started_at=merge_started_at,
            success=True,
        )
    except Exception as exc:
        _record_collector_result(
            collector_name="merge_signals",
            started_at=merge_started_at,
            success=False,
            error_count=1,
            error_type=type(exc).__name__,
        )
        raise
    print("Merged signals file refreshed.")


def collect_signals() -> list[Signal]:
    run_collectors()

    file_signals = load_signals_from_file()

    today = datetime.now(settings.timezone).strftime("%Y-%m-%d")
    manual_signals = load_and_promote_manual_signals(MANUAL_SESSIONS_FILE, today)

    combined_signals = []

    if file_signals:
        combined_signals.extend(file_signals)

    for item in manual_signals:
        try:
            signal = Signal(
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                url=item.get("url", ""),
                author=item.get("author", "Manual Workspace"),
                source=item.get("source", "manual_workspace"),
                category=item.get("category", "Manual Research"),
                published_at=item.get("published_at", datetime.now(settings.timezone).isoformat()),
                collected_at=item.get("collected_at", datetime.now(settings.timezone).isoformat()),
            )
            setattr(signal, "source_weight", item.get("source_weight", 0.95))
            setattr(signal, "quality_level", item.get("quality_level", "high"))
            combined_signals.append(signal)
        except Exception as e:
            print(f"Failed to convert manual signal: {e}")

    if combined_signals:
        print(
            f"Loaded {len(file_signals)} collector signals + "
            f"{len(manual_signals)} manual promoted signals."
        )
        return combined_signals

    print("No collected signals found after collector run. Falling back to sample signals.")
    return collect_sample_signals()


def compute_final_signal_score(item: dict, source_stats: dict) -> float:
    source_quality = source_stats.get(item.get("source", "unknown"), {}).get(
        "quality_score", 0
    )
    source_weight = item.get("source_weight", 0.5)
    recency_score = item.get("recency_score", 0.5)
    keyword_relevance = item.get("keyword_relevance", 0.0)
    novelty_score = item.get("novelty_score", 0.0)

    score = (
        source_quality * 0.3
        + source_weight * 0.2
        + recency_score * 0.2
        + keyword_relevance * 0.15
        + novelty_score * 0.15
    )

    return round(score, 4)


def enrich_and_filter_signals(
    signals: list[Signal],
    subscription_settings: dict | None = None,
) -> tuple[list[Signal], dict]:
    """
    1. Convert Signal objects to dict
    2. Compute source quality
    3. Add quality_level to each signal
    4. Score and sort signals
    5. Attach topic to each signal
    6. Convert back to Signal objects
    """
    signals_data = []
    signal_rules = (subscription_settings or {}).get("signal_rules") or {}
    for s in signals:
        item = s.to_dict()
        item["source_weight"] = getattr(s, "source_weight", 0.5)
        source_excerpt = getattr(s, "source_excerpt", "")
        if source_excerpt:
            item["source_excerpt"] = _bounded_source_excerpt_value(source_excerpt)
            item["source_excerpt_length"] = len(item["source_excerpt"])

        # recency score
        item["recency_score"] = compute_recency_score(item.get("published_at", ""))

        # keyword relevance
        item["keyword_relevance"] = compute_keyword_relevance(item)
        item["novelty_score"] = compute_novelty_score(item)
        signals_data.append(item)

    source_stats = compute_source_quality(signals_data)
    signals_data = filter_signals(signals_data, source_stats)

    for item in signals_data:
        item["score"] = compute_final_signal_score(item, source_stats)

    signals_data = sorted(
        signals_data,
        key=lambda s: s.get("score", 0),
        reverse=True,
    )

    # NEW: attach topic after filtering/scoring, before converting back to Signal
    signals_data = attach_topics_to_signals(signals_data)
    # NEW: attach importance layer
    signals_data = attach_importance_to_signals(signals_data)
    signals_data = apply_subscription_settings_to_pipeline_signals(
        signals_data,
        subscription_settings,
    )

    print("=== Source Stats ===")
    for source, stats in source_stats.items():
        print(
            f"{source}: "
            f"quality_score={stats.get('quality_score')}, "
            f"raw_count={stats.get('raw_count')}, "
            f"url_rate={stats.get('url_rate')}, "
            f"summary_rate={stats.get('summary_rate')}"
        )

    print("=== Sample Signals After Filtering ===")
    for s in signals_data[:5]:
        source_name = s.get("source", "unknown")
        quality_score = source_stats.get(source_name, {}).get("quality_score", 0)

        print(
            f"title={s.get('title', '')[:80]} | "
            f"source={source_name} | "
            f"topic={s.get('topic', 'General AI')} | "
            f"quality={quality_score} | "
            f"quality_level={s.get('quality_level', 'unknown')} | "
            f"weight={s.get('source_weight', 0.5)} | "
            f"recency={s.get('recency_score', 0.5)} | "
            f"relevance={s.get('keyword_relevance', 0.0)} | "
            f"novelty={s.get('novelty_score', 0.0)} | "
            f"score={s.get('score', 0.0)}"
        )

    enriched_signals: list[Signal] = []
    for item in signals_data:
        signal = Signal(
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            url=item.get("url", "") or item.get("link", ""),
            author=item.get("author", "Unknown"),
            source=item.get("source", "external"),
            category=item.get("category", item.get("source", "external")),
            published_at=(
                item.get("published_at")
                or item.get("timestamp")
                or datetime.now(settings.timezone).isoformat()
            ),
            collected_at=(
                item.get("collected_at")
                or datetime.now(settings.timezone).isoformat()
            ),
        )
        setattr(signal, "quality_level", item.get("quality_level", "unknown"))
        setattr(signal, "source_weight", item.get("source_weight", 0.5))
        setattr(signal, "recency_score", item.get("recency_score", 0.5))
        setattr(signal, "keyword_relevance", item.get("keyword_relevance", 0.0))
        setattr(signal, "novelty_score", item.get("novelty_score", 0.0))
        setattr(signal, "score", item.get("score", 0.0))
        setattr(signal, "topic", item.get("topic", "General AI"))
        setattr(signal, "importance_level", item.get("importance_level", "low"))
        setattr(signal, "importance_reason", item.get("importance_reason", []))
        setattr(signal, "subscription_score_percent", item.get("subscription_score_percent"))
        setattr(signal, "subscription_topic_priority", item.get("subscription_topic_priority", "normal"))
        _copy_source_excerpt_to_signal(signal, item)
        tier = classify_signal_processing_tier(signal, signal_rules=signal_rules)
        setattr(signal, "insight_status", tier)
        setattr(signal, "insight_status_label", get_insight_status_label(tier))
        enriched_signals.append(signal)


    return enriched_signals, source_stats

def classify_signal_processing_tier(
    signal: Signal,
    signal_rules: dict | None = None,
) -> str:
    score = float(getattr(signal, "score", 0.0) or 0.0)
    relevance = float(getattr(signal, "keyword_relevance", 0.0) or 0.0)
    rules = signal_rules or {}

    auto_analyze_score = float(rules.get("auto_analyze_score", 62) or 62) / 100
    auto_backlog_score = float(rules.get("auto_backlog_score", 48) or 48) / 100

    if score >= auto_analyze_score or relevance >= 0.45:
        return "auto_generated"

    if score >= auto_backlog_score or relevance >= 0.25:
        return "manual_candidate"

    return "archived_only"

def get_insight_status_label(status: str) -> str:
    if status == "auto_generated":
        return "Insight auto-generated"
    if status == "manual_candidate":
        return "Insight available on demand"
    if status == "archived_only":
        return "Archived signal only"
    return "Status unknown"

def select_signals_for_insight(
    signals: list[Signal],
    subscription_settings: dict | None = None,
) -> list[Signal]:
    def get_score(s: Signal) -> float:
        return float(getattr(s, "score", 0.0) or 0.0)

    def get_relevance(s: Signal) -> float:
        return float(getattr(s, "keyword_relevance", 0.0) or 0.0)

    def get_recency(s: Signal) -> float:
        return float(getattr(s, "recency_score", 0.0) or 0.0)

    def get_topic_priority(s: Signal) -> int:
        priority = str(getattr(s, "subscription_topic_priority", "normal") or "normal")
        if priority == "boosted":
            return 2
        if priority == "preferred":
            return 1
        return 0

    signal_rules = (subscription_settings or {}).get("signal_rules") or {}

    sorted_signals = sorted(
        signals,
        key=lambda s: (get_topic_priority(s), get_score(s), get_relevance(s), get_recency(s)),
        reverse=True,
    )

    auto_insight_signals: list[Signal] = []
    manual_candidate_signals: list[Signal] = []
    archive_signals: list[Signal] = []

    for s in sorted_signals:
        tier = classify_signal_processing_tier(s, signal_rules=signal_rules)
        setattr(s, "insight_status", tier)
        setattr(s, "insight_status_label", get_insight_status_label(tier))

        if tier == "auto_generated":
            auto_insight_signals.append(s)
        elif tier == "manual_candidate":
            manual_candidate_signals.append(s)
        else:
            archive_signals.append(s)

    MAX_AUTO_INSIGHTS = 12
    selected = auto_insight_signals[:MAX_AUTO_INSIGHTS]

    MIN_AUTO_INSIGHTS = 6
    if len(selected) < MIN_AUTO_INSIGHTS:
        needed = MIN_AUTO_INSIGHTS - len(selected)
        for s in manual_candidate_signals[:needed]:
            if not getattr(s, "insight_status", None):
                setattr(s, "insight_status", "manual_candidate")
                setattr(s, "insight_status_label", "Insight available on demand")
            selected.append(s)

    if not selected:
        selected = sorted_signals[:5]
        for s in selected:
            if not getattr(s, "insight_status", None):
                setattr(s, "insight_status", "auto_generated")
                setattr(s, "insight_status_label", "Insight auto-generated")

    print("=== Insight Input Distribution ===")
    print(f"total signals: {len(signals)}")
    print(f"auto insight tier: {len(auto_insight_signals)}")
    print(f"manual candidate tier: {len(manual_candidate_signals)}")
    print(f"archive tier: {len(archive_signals)}")
    print(f"using auto insights: {len(selected)}")

    return selected


def _clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _has_meaningful_insight(parsed: dict) -> bool:
    fields = [
        _clean_text(parsed.get("why_it_matters", "")),
        _clean_text(parsed.get("relevance_to_projects", "")),
        _clean_text(parsed.get("relevance_to_career", "")),
        _clean_text(parsed.get("synthesized_insight", "")),
    ]
    return any(len(x) >= 20 for x in fields)


def _build_fallback_insight(signal: Signal) -> dict:
    topic = getattr(signal, "topic", "General AI")
    source = signal.source or "unknown source"

    return {
        "why_it_matters": (
            f"This signal matters because it highlights a potentially relevant development "
            f"in {topic}, and may influence how AI systems are being built or applied."
        ),
        "relevance_to_projects": (
            f"This could be relevant to AI Radar, GLAP, or AI Cognitive if the topic connects "
            f"to signal processing, intelligence workflows, or AI system design."
        ),
        "relevance_to_career": (
            f"This is useful for your career because it helps strengthen your understanding of "
            f"AI product architecture, system thinking, and industry trend interpretation."
        ),
        "synthesized_insight": (
            f"A practical takeaway is to track how signals from {source} map into your project "
            f"architecture, product positioning, and long-term AI systems narrative."
        ),
    }


def generate_insight(signal: Signal, personal_context: dict) -> Insight:
    signal_dict = signal.to_dict()
    signal_dict["quality_level"] = getattr(signal, "quality_level", "unknown")
    signal_dict["source_weight"] = getattr(signal, "source_weight", 0.5)
    signal_dict["recency_score"] = getattr(signal, "recency_score", 0.5)
    signal_dict["keyword_relevance"] = getattr(signal, "keyword_relevance", 0.0)
    signal_dict["novelty_score"] = getattr(signal, "novelty_score", 0.0)
    signal_dict["score"] = getattr(signal, "score", 0.0)
    signal_dict["topic"] = getattr(signal, "topic", "General AI")

    insight_policy = _pipeline_execution_policy(
        task_type="radar_summary",
        importance_score=getattr(signal, "score", 0.0),
        requires_traceability=False,
    )

    system_prompt, user_prompt = personalized_radar_insight_prompts(
        personal_context=personal_context,
        signal_payload=signal_dict,
        policy=insight_policy,
    )

    parsed = None
    last_error = None
    provider_used = None
    model_used = None

    insight_route = route_task(insight_policy["effective_task_type"])

    insight_attempts_raw = str(os.getenv("PIPELINE_INSIGHT_MAX_ATTEMPTS", "1")).strip()
    try:
        insight_attempts = max(1, min(int(insight_attempts_raw), 2))
    except Exception:
        insight_attempts = 1

    for attempt in range(insight_attempts):
        try:
            result = execute_routed_task(
                task_type=insight_policy["effective_task_type"],
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": _apply_pipeline_policy_prompt(system_prompt, policy=insight_policy),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                json_mode=True,
            )

            content = result.raw_text or "{}"
            if attempt == 0:
                print(
                    f"[router] signal insight -> {insight_route.tier} / "
                    f"{insight_route.provider} / "
                    f"{insight_route.model}"
                )
            print(f"[DEBUG] raw insight response for '{signal.title[:80]}': {content}")

            parsed = result.parsed_json or json.loads(content)
            provider_used = result.route.provider
            model_used = result.route.model

            parsed = {
                "why_it_matters": _clean_text(parsed.get("why_it_matters", "")),
                "relevance_to_projects": _clean_text(parsed.get("relevance_to_projects", "")),
                "relevance_to_career": _clean_text(parsed.get("relevance_to_career", "")),
                "synthesized_insight": _clean_text(parsed.get("synthesized_insight", "")),
            }

            if _has_meaningful_insight(parsed):
                break

            print(f"[WARN] Empty/weak insight returned on attempt {attempt + 1} for: {signal.title}")

        except Exception as e:
            last_error = e
            print(f"[WARN] Insight generation failed on attempt {attempt + 1} for '{signal.title}': {e}")

    if not parsed or not _has_meaningful_insight(parsed):
        print(f"[WARN] Using fallback insight for: {signal.title}")
        parsed = _build_fallback_insight(signal)

    return Insight(
        signal_title=signal.title,
        signal_summary=signal.summary,
        why_it_matters=parsed.get("why_it_matters", ""),
        relevance_to_projects=parsed.get("relevance_to_projects", ""),
        relevance_to_career=parsed.get("relevance_to_career", ""),
        synthesized_insight=parsed.get("synthesized_insight", ""),
        provider_used=provider_used,
        model_used=model_used,
        execution_policy=insight_policy,
        execution={
            "mode": insight_policy.get("mode"),
            "final_mode": insight_policy.get("mode"),
            "validation_passed": _has_meaningful_insight(parsed),
        },
    )


def signal_to_output_dict(signal: Signal) -> dict:
    data = signal.to_dict()
    data["quality_level"] = getattr(signal, "quality_level", "unknown")
    data["source_weight"] = getattr(signal, "source_weight", 0.5)
    data["recency_score"] = getattr(signal, "recency_score", 0.5)
    data["keyword_relevance"] = getattr(signal, "keyword_relevance", 0.0)
    data["novelty_score"] = getattr(signal, "novelty_score", 0.0)
    data["score"] = getattr(signal, "score", 0.0)
    data["topic"] = getattr(signal, "topic", "General AI")
    data["importance_level"] = getattr(signal, "importance_level", "low")
    data["importance_reason"] = getattr(signal, "importance_reason", [])
    data["insight_status"] = getattr(signal, "insight_status", "unknown")
    data["insight_status_label"] = getattr(
        signal,
        "insight_status_label",
        "Status unknown",
    )
    data["subscription_score_percent"] = getattr(signal, "subscription_score_percent", None)
    data["subscription_topic_priority"] = getattr(signal, "subscription_topic_priority", "normal")
    data["processing_bucket"] = getattr(signal, "insight_status", "unknown")
    source_excerpt = getattr(signal, "source_excerpt", "")
    if source_excerpt:
        data["source_excerpt"] = _bounded_source_excerpt_value(source_excerpt)
        data["source_excerpt_length"] = len(data["source_excerpt"])

    for field in (
        "signal_type",
        "agent_subtopic",
        "friction_subtopic",
        "pain_severity_score",
        "ecosystem_relevance_score",
        "friction_score",
        "agent_relevance_score",
        "buildability_score",
        "strategic_relevance_score",
        "agent_watch_score",
    ):
        value = getattr(signal, field, None)
        if value is not None:
            data[field] = value

    metadata = getattr(signal, "metadata", None)
    if isinstance(metadata, dict):
        data["metadata"] = metadata

    return data

def normalize_insight_key(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def build_insight_lookup_keys(title: str, summary: str) -> list[str]:
    normalized_title = normalize_insight_key(title)
    normalized_summary = normalize_insight_key(summary)

    keys = []

    if normalized_title and normalized_summary:
        keys.append(f"title_summary::{normalized_title}||{normalized_summary}")

    if normalized_title:
        keys.append(f"title::{normalized_title}")

    if normalized_summary:
        keys.append(f"summary::{normalized_summary}")

    return keys


def merge_insights_into_signals(
    signals_data: list[dict],
    insights_data: list[dict],
) -> list[dict]:
    """
    Merge generated insight fields back into signal records.

    Match order:
    1. title + summary
    2. title only
    3. summary only
    """
    insight_map = {}

    for item in insights_data:
        signal_title = item.get("signal_title", "")
        signal_summary = item.get("signal_summary", "")

        for key in build_insight_lookup_keys(signal_title, signal_summary):
            insight_map[key] = item

    merged: list[dict] = []
    matched_count = 0
    meaningful_count = 0

    for signal in signals_data:
        signal_copy = dict(signal)

        title = signal_copy.get("title", "")
        summary = signal_copy.get("summary", "")

        matched = None
        for key in build_insight_lookup_keys(title, summary):
            if key in insight_map:
                matched = insight_map[key]
                break

        if matched:
            matched_count += 1
            signal_copy["why_it_matters"] = matched.get("why_it_matters", "")
            signal_copy["relevance_to_projects"] = matched.get("relevance_to_projects", "")
            signal_copy["relevance_to_career"] = matched.get("relevance_to_career", "")
            signal_copy["synthesized_insight"] = matched.get("synthesized_insight", "")

            # backward-compatible aliases
            signal_copy["insight"] = matched.get("why_it_matters", "")
            signal_copy["strategy"] = matched.get("synthesized_insight", "")
            if any([
                (signal_copy.get("why_it_matters") or "").strip(),
                (signal_copy.get("relevance_to_projects") or "").strip(),
                (signal_copy.get("relevance_to_career") or "").strip(),
                (signal_copy.get("synthesized_insight") or "").strip(),
            ]):
                meaningful_count += 1

        merged.append(signal_copy)

    print("=== Insight Merge Summary ===")
    print(f"signals with merged insights: {matched_count}/{len(signals_data)}")
    print(f"signals with non-empty insights: {meaningful_count}/{len(signals_data)}")
    return merged

def build_signal_project_text(signal_item: dict) -> str:
    parts = [
        signal_item.get("title", ""),
        signal_item.get("summary", ""),
        signal_item.get("why_it_matters", ""),
        signal_item.get("relevance_to_projects", ""),
        signal_item.get("relevance_to_career", ""),
        signal_item.get("synthesized_insight", ""),
        signal_item.get("topic", ""),
    ]
    return "\n".join([str(p).strip() for p in parts if str(p).strip()])


def attach_projects_to_signals(signals_data: list[dict]) -> list[dict]:
    enriched: list[dict] = []

    for signal in signals_data:
        signal_copy = dict(signal)

        signal_id = build_signal_identity(signal_copy)
        signal_id_str = "||".join(signal_id)

        text = build_signal_project_text(signal_copy)
        linked_projects = link_signal_to_projects(
            signal_id=signal_id_str,
            text=text,
            min_score=2,
        )

        signal_copy["projects"] = [
            item.get("project_id")
            for item in linked_projects
            if item.get("project_id")
        ]
        signal_copy["project_links"] = linked_projects

        enriched.append(signal_copy)

    print("=== Project Linking Summary ===")
    linked_count = sum(1 for s in enriched if s.get("projects"))
    print(f"signals with linked projects: {linked_count}/{len(enriched)}")

    return enriched

def normalize_identity_text(value: str) -> str:
    return (value or "").strip().lower()


def build_signal_identity(item: dict) -> tuple[str, str, str, str]:
    """
    Stable identity for matching a signal across runs.
    Prefer title + source + url + published_at.
    """
    return (
        normalize_identity_text(item.get("title", "")),
        normalize_identity_text(item.get("source", "")),
        normalize_identity_text(item.get("url", "") or item.get("link", "")),
        normalize_identity_text(item.get("published_at", "") or item.get("timestamp", "")),
    )


def load_existing_latest_signals(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("signals", []) or data.get("items", [])

        return []
    except Exception as e:
        print(f"Failed to load existing latest signals: {e}")
        return []


def _first_non_empty_value(*values):
    for value in values:
        if value is not None and str(value).strip():
            return value
    return None


def _raw_dict(item: dict) -> dict:
    raw = item.get("raw")
    return raw if isinstance(raw, dict) else {}


def _first_seen_collected_at(existing: dict, incoming: dict, fallback: str) -> str:
    existing_raw = _raw_dict(existing)
    incoming_raw = _raw_dict(incoming)
    return str(
        _first_non_empty_value(
            existing.get("collected_at"),
            existing_raw.get("collected_at"),
            incoming.get("collected_at"),
            incoming_raw.get("collected_at"),
            fallback,
        )
    )


def _apply_collected_at(item: dict, collected_at: str) -> dict:
    updated = dict(item)
    updated["collected_at"] = collected_at

    if isinstance(updated.get("raw"), dict):
        raw = dict(updated["raw"])
        raw["collected_at"] = collected_at
        updated["raw"] = raw

    return updated


def preserve_signal_history_fields(
    new_signals: list[dict],
    existing_signals: list[dict],
) -> list[dict]:
    """
    Preserve first-seen metadata and review / insight fields across reruns.

    Fields preserved when identity matches:
    - topic
    - insight_status
    - insight_status_label
    - collected_at (top-level and raw payload)
    - status
    - saved_reason
    - insight
    - strategy
    - why_it_matters
    - relevance_to_projects
    - relevance_to_career
    - synthesized_insight
    """
    existing_by_identity = {
        build_signal_identity(item): item
        for item in existing_signals
    }

    now_iso = datetime.now(settings.timezone).isoformat()
    merged: list[dict] = []

    for item in new_signals:
        identity = build_signal_identity(item)
        existing = existing_by_identity.get(identity)

        merged_item = dict(item)

        if existing:
            merged_item = _apply_collected_at(
                merged_item,
                _first_seen_collected_at(existing, item, now_iso),
            )
            merged_item["status"] = existing.get("status", item.get("status", "pending"))
            merged_item["saved_reason"] = existing.get("saved_reason", item.get("saved_reason"))
            merged_item["topic"] = existing.get("topic", item.get("topic", "General AI"))
            merged_item["insight_status"] = existing.get("insight_status", item.get("insight_status", "unknown"))
            merged_item["insight_status_label"] = existing.get(
                "insight_status_label",
                item.get("insight_status_label", "Status unknown")
            )
            merged_item["insight"] = existing.get("insight", item.get("insight", ""))
            merged_item["strategy"] = existing.get("strategy", item.get("strategy", ""))

            merged_item["why_it_matters"] = (
                existing.get("why_it_matters") or item.get("why_it_matters", "")
            )
            merged_item["relevance_to_projects"] = (
                existing.get("relevance_to_projects") or item.get("relevance_to_projects", "")
            )
            merged_item["relevance_to_career"] = (
                existing.get("relevance_to_career") or item.get("relevance_to_career", "")
            )
            merged_item["synthesized_insight"] = (
                existing.get("synthesized_insight") or item.get("synthesized_insight", "")
            )
        else:
            merged_item = _apply_collected_at(
                merged_item,
                _first_seen_collected_at({}, item, now_iso),
            )
            merged_item["status"] = item.get("status", "pending")
            merged_item["saved_reason"] = item.get("saved_reason")

            merged_item["topic"] = item.get("topic", "General AI")
            merged_item["insight_status"] = item.get("insight_status", "unknown")
            merged_item["insight_status_label"] = item.get("insight_status_label", "Status unknown")
            merged_item["insight"] = item.get("insight", "")
            merged_item["strategy"] = item.get("strategy", "")

            merged_item["why_it_matters"] = item.get("why_it_matters", "")
            merged_item["relevance_to_projects"] = item.get("relevance_to_projects", "")
            merged_item["relevance_to_career"] = item.get("relevance_to_career", "")
            merged_item["synthesized_insight"] = item.get("synthesized_insight", "")

        merged.append(merged_item)

    return merged

def save_json(data: dict | list, file_path: Path) -> None:
    global ARTIFACT_WRITTEN_COUNT
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    ARTIFACT_WRITTEN_COUNT += 1
    artifact_name = file_path.stem
    _safe_record_artifact_write(
        {
            "run_id": CURRENT_PIPELINE_RUN_ID,
            "date": datetime.now(settings.timezone).strftime("%Y-%m-%d"),
            "artifact_name": artifact_name,
            "path": file_path,
            "size_bytes": file_path.stat().st_size if file_path.exists() else None,
            "success": True,
        }
    )


def load_latest_pipeline_state(file_name: str, s3_key: str) -> dict:
    local_path = OUTPUT_DIR / file_name
    if local_path.exists():
        try:
            payload = json.loads(local_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception as e:
            print(f"[WARN] Failed to load local pipeline state {file_name}: {e}")

    if s3_uploads_disabled():
        return {}

    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
        )
        payload = json.loads(response["Body"].read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception as e:
        print(f"[INFO] No prior S3 pipeline state at {s3_key}: {e}")

    return {}


def save_feed_activity(today: str, rss_fetched: int, new_signals: int) -> None:
    """
    Save daily feed activity statistics.
    """
    activity_file = OUTPUT_DIR / "feed_activity.json"

    activity_data = []

    if activity_file.exists():
        try:
            with open(activity_file, "r", encoding="utf-8") as f:
                activity_data = json.load(f)
        except Exception:
            activity_data = []

    activity_data.append(
        {
            "date": today,
            "rss_fetched": rss_fetched,
            "new_signals": new_signals,
        }
    )

    with open(activity_file, "w", encoding="utf-8") as f:
        json.dump(activity_data, f, ensure_ascii=False, indent=2)

    print(f"Feed activity updated: {today} | RSS={rss_fetched} | NewSignals={new_signals}")

def _write_json_to_s3(key: str, data: dict | list) -> None:
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def upload_outputs_to_s3(
    s3: S3Writer,
    today: str,
    signals_data: list[dict],
    insights_data: list[dict],
    daily_radar: dict,
    write_signals_history: bool,
) -> None:
    """
    S3 upload rules

    signals:
      - latest: always overwrite
      - dated history: only write when there are new first-seen signals

    insights:
      - latest: always overwrite
      - dated snapshot: always write once per successful run/day

    daily radar:
      - latest: always overwrite
      - dated snapshot: always write once per successful run/day
    """

    # ----------------------------
    # signals
    # ----------------------------
    signals_latest_key = "signals/latest/signals.json"
    _write_json_to_s3(signals_latest_key, signals_data)
    print(f"Uploaded signals latest to S3: {signals_latest_key}")

    if write_signals_history:
        signals_history_key = f"signals/{today}/signals.json"
        _write_json_to_s3(signals_history_key, signals_data)
        print(f"Uploaded signals history to S3: {signals_history_key}")
    else:
        print("No new first-seen signals. Skip writing signals history to S3.")

    # ----------------------------
    # insights
    # ----------------------------
    insights_latest_key = "insights/latest/insights.json"
    insights_history_key = f"insights/{today}/insights.json"

    # always overwrite latest
    _write_json_to_s3(insights_latest_key, insights_data)
    print(f"Uploaded insights latest to S3: {insights_latest_key}")

    # always write dated snapshot for the day
    _write_json_to_s3(insights_history_key, insights_data)
    print(f"Uploaded insights history to S3: {insights_history_key}")

    # ----------------------------
    # daily radar
    # ----------------------------
    daily_latest_key = "daily/latest/daily_radar.json"
    daily_history_key = f"daily/{today}/daily_radar.json"

    # always overwrite latest
    _write_json_to_s3(daily_latest_key, daily_radar)
    print(f"Uploaded daily radar latest to S3: {daily_latest_key}")

    # always write dated snapshot for the day
    _write_json_to_s3(daily_history_key, daily_radar)
    print(f"Uploaded daily radar history to S3: {daily_history_key}")

    # ----------------------------
    # agent watch signals
    # ----------------------------
    agent_watch_file = OUTPUT_DIR / "agent_watch_signals.json"
    if agent_watch_file.exists():
        try:
            with open(agent_watch_file, "r", encoding="utf-8") as f:
                agent_watch_payload = json.load(f)
            agent_watch_latest_key = "signals/latest/agent_watch_signals.json"
            agent_watch_history_key = f"signals/{today}/agent_watch_signals.json"
            _write_json_to_s3(agent_watch_latest_key, agent_watch_payload)
            _write_json_to_s3(agent_watch_history_key, agent_watch_payload)
            print(f"Uploaded agent watch latest to S3: {agent_watch_latest_key}")
            print(f"Uploaded agent watch history to S3: {agent_watch_history_key}")
        except Exception as e:
            print(f"Failed to upload agent watch signals to S3: {e}")
    else:
        print("Agent watch signals file not found. Skip agent watch S3 upload.")

    agent_watch_repo_snapshots_file = OUTPUT_DIR / "agent_watch_repo_snapshots.json"
    if agent_watch_repo_snapshots_file.exists():
        try:
            with open(agent_watch_repo_snapshots_file, "r", encoding="utf-8") as f:
                agent_watch_repo_snapshots_payload = json.load(f)
            agent_watch_repo_snapshots_latest_key = "signals/latest/agent_watch_repo_snapshots.json"
            agent_watch_repo_snapshots_history_key = f"signals/{today}/agent_watch_repo_snapshots.json"
            _write_json_to_s3(agent_watch_repo_snapshots_latest_key, agent_watch_repo_snapshots_payload)
            _write_json_to_s3(agent_watch_repo_snapshots_history_key, agent_watch_repo_snapshots_payload)
            print(f"Uploaded agent watch repo snapshots latest to S3: {agent_watch_repo_snapshots_latest_key}")
            print(f"Uploaded agent watch repo snapshots history to S3: {agent_watch_repo_snapshots_history_key}")
        except Exception as e:
            print(f"Failed to upload agent watch repo snapshots to S3: {e}")
    else:
        print("Agent watch repo snapshots file not found. Skip repo snapshot S3 upload.")

    agent_watch_tracking_state_file = OUTPUT_DIR / "agent_watch_tracking_state.json"
    if agent_watch_tracking_state_file.exists():
        try:
            with open(agent_watch_tracking_state_file, "r", encoding="utf-8") as f:
                agent_watch_tracking_state_payload = json.load(f)
            agent_watch_tracking_state_latest_key = "signals/latest/agent_watch_tracking_state.json"
            agent_watch_tracking_state_history_key = f"signals/{today}/agent_watch_tracking_state.json"
            _write_json_to_s3(agent_watch_tracking_state_latest_key, agent_watch_tracking_state_payload)
            _write_json_to_s3(agent_watch_tracking_state_history_key, agent_watch_tracking_state_payload)
            print(f"Uploaded agent watch tracking state latest to S3: {agent_watch_tracking_state_latest_key}")
            print(f"Uploaded agent watch tracking state history to S3: {agent_watch_tracking_state_history_key}")
        except Exception as e:
            print(f"Failed to upload agent watch tracking state to S3: {e}")
    else:
        print("Agent watch tracking state file not found. Skip tracking state S3 upload.")

    agent_watch_repo_profiles_file = OUTPUT_DIR / "agent_watch_repo_profiles.json"
    if agent_watch_repo_profiles_file.exists():
        try:
            with open(agent_watch_repo_profiles_file, "r", encoding="utf-8") as f:
                agent_watch_repo_profiles_payload = json.load(f)
            agent_watch_repo_profiles_latest_key = "signals/latest/agent_watch_repo_profiles.json"
            agent_watch_repo_profiles_history_key = f"signals/{today}/agent_watch_repo_profiles.json"
            _write_json_to_s3(agent_watch_repo_profiles_latest_key, agent_watch_repo_profiles_payload)
            _write_json_to_s3(agent_watch_repo_profiles_history_key, agent_watch_repo_profiles_payload)
            print(f"Uploaded agent watch repo profiles latest to S3: {agent_watch_repo_profiles_latest_key}")
            print(f"Uploaded agent watch repo profiles history to S3: {agent_watch_repo_profiles_history_key}")
        except Exception as e:
            print(f"Failed to upload agent watch repo profiles to S3: {e}")
    else:
        print("Agent watch repo profiles file not found. Skip repo profile S3 upload.")

    friction_file = OUTPUT_DIR / "friction_signals.json"
    if friction_file.exists():
        try:
            with open(friction_file, "r", encoding="utf-8") as f:
                friction_payload = json.load(f)
            friction_latest_key = "signals/latest/friction_signals.json"
            friction_history_key = f"signals/{today}/friction_signals.json"
            _write_json_to_s3(friction_latest_key, friction_payload)
            _write_json_to_s3(friction_history_key, friction_payload)
            print(f"Uploaded friction latest to S3: {friction_latest_key}")
            print(f"Uploaded friction history to S3: {friction_history_key}")
        except Exception as e:
            print(f"Failed to upload friction signals to S3: {e}")
    else:
        print("Friction signals file not found. Skip friction S3 upload.")

    friction_tracking_state_file = OUTPUT_DIR / "friction_tracking_state.json"
    if friction_tracking_state_file.exists():
        try:
            with open(friction_tracking_state_file, "r", encoding="utf-8") as f:
                friction_tracking_state_payload = json.load(f)
            friction_tracking_state_latest_key = "signals/latest/friction_tracking_state.json"
            friction_tracking_state_history_key = f"signals/{today}/friction_tracking_state.json"
            _write_json_to_s3(friction_tracking_state_latest_key, friction_tracking_state_payload)
            _write_json_to_s3(friction_tracking_state_history_key, friction_tracking_state_payload)
            print(f"Uploaded friction tracking state latest to S3: {friction_tracking_state_latest_key}")
            print(f"Uploaded friction tracking state history to S3: {friction_tracking_state_history_key}")
        except Exception as e:
            print(f"Failed to upload friction tracking state to S3: {e}")
    else:
        print("Friction tracking state file not found. Skip friction tracking state S3 upload.")

    friction_profiles_file = OUTPUT_DIR / "friction_signal_profiles.json"
    if friction_profiles_file.exists():
        try:
            with open(friction_profiles_file, "r", encoding="utf-8") as f:
                friction_profiles_payload = json.load(f)
            friction_profiles_latest_key = "signals/latest/friction_signal_profiles.json"
            friction_profiles_history_key = f"signals/{today}/friction_signal_profiles.json"
            _write_json_to_s3(friction_profiles_latest_key, friction_profiles_payload)
            _write_json_to_s3(friction_profiles_history_key, friction_profiles_payload)
            print(f"Uploaded friction profiles latest to S3: {friction_profiles_latest_key}")
            print(f"Uploaded friction profiles history to S3: {friction_profiles_history_key}")
        except Exception as e:
            print(f"Failed to upload friction profiles to S3: {e}")
    else:
        print("Friction signal profiles file not found. Skip friction profile S3 upload.")


def _coerce_topic_key(value: object) -> str:
    if value is None:
        return "Unknown"
    text = str(value).strip()
    return text or "Unknown"


def _extract_topic_metric_value(item: object, keys: list[str]) -> float:
    if not isinstance(item, dict):
        return 0.0

    for key in keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            if value is not None and str(value).strip() != "":
                return float(value)
        except Exception:
            continue

    return 0.0


def _fallback_topic_momentum_from_existing_outputs(
    topic_trends: list[dict],
    weekly_momentum: list[dict] | dict,
) -> list[dict]:
    trend_map: dict[str, dict] = {}

    if isinstance(topic_trends, list):
        for item in topic_trends:
            if not isinstance(item, dict):
                continue
            topic = _coerce_topic_key(item.get("topic") or item.get("name") or item.get("label"))
            trend_map[topic] = item

    weekly_map: dict[str, dict] = {}
    if isinstance(weekly_momentum, list):
        for item in weekly_momentum:
            if not isinstance(item, dict):
                continue
            topic = _coerce_topic_key(item.get("topic") or item.get("name") or item.get("label"))
            weekly_map[topic] = item
    elif isinstance(weekly_momentum, dict):
        for key, value in weekly_momentum.items():
            topic = _coerce_topic_key(key)
            if isinstance(value, dict):
                weekly_map[topic] = value
            else:
                weekly_map[topic] = {"weekly_momentum": value}

    topics = sorted(set(trend_map.keys()) | set(weekly_map.keys()))
    combined: list[dict] = []

    for topic in topics:
        trend_item = trend_map.get(topic, {})
        weekly_item = weekly_map.get(topic, {})

        trend_score = _extract_topic_metric_value(
            trend_item,
            ["score", "trend_score", "trend_strength", "count", "signal_count"],
        )
        weekly_score = _extract_topic_metric_value(
            weekly_item,
            ["momentum", "weekly_momentum", "score", "change", "delta"],
        )
        momentum_score = round(trend_score + weekly_score, 4)

        combined.append(
            {
                "topic": topic,
                "trend_score": trend_score,
                "weekly_momentum": weekly_score,
                "momentum_score": momentum_score,
            }
        )

    combined.sort(key=lambda x: x.get("momentum_score", 0.0), reverse=True)
    return combined


def compute_topic_momentum_safe(
    signals_data: list[dict],
    topic_trends: list[dict],
    weekly_momentum: list[dict] | dict,
) -> list[dict] | dict:
    call_patterns = [
        lambda: compute_topic_momentum(signals_data),
        lambda: compute_topic_momentum(topic_trends),
        lambda: compute_topic_momentum(signals_data=signals_data),
        lambda: compute_topic_momentum(topic_trends=topic_trends),
        lambda: compute_topic_momentum(
            signals_data=signals_data,
            topic_trends=topic_trends,
            weekly_momentum=weekly_momentum,
        ),
        lambda: compute_topic_momentum(
            signals_data,
            topic_trends,
            weekly_momentum,
        ),
    ]

    for idx, call in enumerate(call_patterns, start=1):
        try:
            result = call()
            if result is not None:
                print(f"Topic momentum computed using call pattern #{idx}.")
                return result
        except TypeError:
            continue
        except Exception as e:
            print(f"[WARN] compute_topic_momentum failed on pattern #{idx}: {e}")

    print("[WARN] Falling back to derived topic momentum payload.")
    return _fallback_topic_momentum_from_existing_outputs(topic_trends, weekly_momentum)


def build_intelligence_outputs(
    *,
    today: str,
    generated_at: str,
    topic_trends: list[dict],
    topic_momentum: list[dict] | dict,
    rising_topics: list[dict] | dict,
    strategic_priority: list[dict] | dict,
    weekly_momentum: list[dict] | dict,
) -> dict[str, dict]:
    return {
        "topic_trends.json": {
            "date": today,
            "generated_at": generated_at,
            "items": topic_trends,
        },
        "topic_momentum.json": {
            "date": today,
            "generated_at": generated_at,
            "items": topic_momentum,
        },
        "rising_topics.json": {
            "date": today,
            "generated_at": generated_at,
            "items": rising_topics,
        },
        "strategic_priority.json": {
            "date": today,
            "generated_at": generated_at,
            "items": strategic_priority,
        },
        "weekly_momentum.json": {
            "date": today,
            "generated_at": generated_at,
            "items": weekly_momentum,
        },
    }


def save_intelligence_outputs_locally(intelligence_outputs: dict[str, dict]) -> None:
    for filename, payload in intelligence_outputs.items():
        save_json(payload, INTELLIGENCE_OUTPUT_DIR / filename)
        save_json(payload, OUTPUT_DIR / filename)
        print(f"Saved local intelligence output: {filename}")


def upload_intelligence_outputs_to_s3(s3: S3Writer, today: str, intelligence_outputs: dict[str, dict]) -> None:
    for filename, payload in intelligence_outputs.items():
        latest_key = f"intelligence/latest/{filename}"
        history_key = f"intelligence/{today}/{filename}"
        s3.upload_json(payload, latest_key)
        s3.upload_json(payload, history_key)
        print(f"Uploaded intelligence latest to S3: {latest_key}")
        print(f"Uploaded intelligence history to S3: {history_key}")


def _run_main_pipeline() -> None:
    settings.validate()
    ensure_output_dir()

    now = datetime.now(settings.timezone)
    today = now.strftime("%Y-%m-%d")

    print("Starting AI Radar run...")
    print(f"Timezone: {settings.radar_timezone}")
    print(f"Generated at: {now.isoformat()}")
    print(f"Run date: {today}")

    personal_context = load_personal_context()
    print("Personal context loaded.")
    subscription_settings = load_ingestion_subscription_settings()
    print(
        "Ingestion subscription settings loaded. "
        f"scope={DEFAULT_SUBSCRIPTION_SCOPE} "
        f"sources={len(subscription_settings.get('sources', []))} "
        f"projects={len(subscription_settings.get('project_links', []))}"
    )

    raw_signals = collect_signals()
    rss_fetched = len(raw_signals)

    print(f"Collected {rss_fetched} raw signals.")

    signals, source_stats = enrich_and_filter_signals(
        raw_signals,
        subscription_settings=subscription_settings,
    )
    print(f"Prepared {len(signals)} signals after quality enrichment/filtering.")

    signals_for_insight = select_signals_for_insight(
        signals,
        subscription_settings=subscription_settings,
    )

    insights: list[Insight] = []
    for idx, signal in enumerate(signals_for_insight, start=1):
        print(
            f"Generating insight {idx}/{len(signals_for_insight)} "
            f"for signal: {signal.title}"
        )
        insight = generate_insight(signal, personal_context)
        insights.append(insight)

    signals_data = [signal_to_output_dict(s) for s in signals]

    existing_latest_signals = load_existing_latest_signals(PIPELINE_SIGNALS_FILE)
    signals_data = preserve_signal_history_fields(
        new_signals=signals_data,
        existing_signals=existing_latest_signals,
    )
    insights_data = [i.to_dict() for i in insights]

    signals_data = merge_insights_into_signals(
        signals_data=signals_data,
        insights_data=insights_data,
    )

    signals_data = attach_projects_to_signals(signals_data)

    current_signal_count = len(signals_data)
    trend_summary = detect_trends(signals_data)
    
    preserved_count = 0
    new_count = 0

    existing_identity_set = {
        build_signal_identity(item)
        for item in existing_latest_signals
    }

    for item in signals_data:
        if build_signal_identity(item) in existing_identity_set:
            preserved_count += 1
        else:
            new_count += 1

    print("=== Timeline Preservation Summary ===")
    print(f"matched existing signals: {preserved_count}")
    print(f"new first-seen signals: {new_count}")
    topic_trends = compute_topic_trends(signals_data)
    rising_topics = compute_rising_topics(signals_data)

    previous_topic_trends = load_previous_topic_trends(OUTPUT_DIR, today)
    topic_evolution = compute_topic_evolution(topic_trends, previous_topic_trends)

    weekly_topic_summary = compute_weekly_topic_summary(OUTPUT_DIR, today, days=7)
    weekly_momentum = compute_weekly_momentum(weekly_topic_summary)
    topic_momentum = compute_topic_momentum_safe(
        signals_data=signals_data,
        topic_trends=topic_trends,
        weekly_momentum=weekly_momentum,
    )
    strategic_priority = compute_strategic_priority_topics(
        topic_trends=topic_trends,
        rising_topics=rising_topics,
        weekly_momentum=weekly_momentum,
    )

    executive_summary = generate_daily_executive_summary(
        signals_data=signals_data,
        topic_trends=topic_trends,
        rising_topics=rising_topics,
        weekly_momentum=weekly_momentum,
        strategic_priority=strategic_priority,
    )
    subscription_source_summary = build_subscription_source_summary(
        signals_data,
        subscription_settings,
    )
    agent_watch_summary = build_agent_watch_summary(signals_data)
    agent_watch_repo_snapshots = build_agent_watch_repo_snapshots(signals_data, now.isoformat())
    agent_watch_repo_profiles = build_agent_watch_repo_profiles(signals_data, now.isoformat())
    friction_signals_summary = build_friction_signals_summary(signals_data)
    friction_signal_profiles = build_friction_signal_profiles(signals_data, now.isoformat())
    previous_agent_tracking_state = load_latest_pipeline_state(
        "agent_watch_tracking_state.json",
        "signals/latest/agent_watch_tracking_state.json",
    )
    previous_friction_tracking_state = load_latest_pipeline_state(
        "friction_tracking_state.json",
        "signals/latest/friction_tracking_state.json",
    )
    agent_watch_tracking_state = build_agent_watch_tracking_state(
        agent_watch_repo_snapshots,
        previous_agent_tracking_state or None,
        generated_at=now.isoformat(),
    )
    friction_tracking_state = build_friction_tracking_state(
        {"signals": _load_friction_profile_candidates(signals_data)},
        previous_friction_tracking_state or None,
        generated_at=now.isoformat(),
    )
    print("=== Subscription Runtime Summary ===")
    print(
        f"configured active sources: "
        f"{subscription_source_summary.get('configured_active_source_count', 0)}"
    )
    print(
        f"matched subscription sources: "
        f"{subscription_source_summary.get('matched_subscription_source_count', 0)}"
    )
    print(
        "runtime signal sources: "
        f"{subscription_source_summary.get('runtime_signal_sources', [])}"
    )
    print("=== Agent Watch Summary ===")
    print(
        f"agent watch signals: {agent_watch_summary.get('signal_count', 0)} | "
        f"highlights: {agent_watch_summary.get('top_signal_count', 0)}"
    )
    print("=== Friction Signals Summary ===")
    print(
        f"friction signals: {friction_signals_summary.get('signal_count', 0)} | "
        f"highlights: {friction_signals_summary.get('top_signal_count', 0)}"
    )
    print("=== Agent/Friction Tracking Summary ===")
    print(
        f"agent tracking: {agent_watch_tracking_state.get('counts_by_status', {})} | "
        f"friction tracking: {friction_tracking_state.get('counts_by_status', {})}"
    )
    print("=== Trend Summary ===")
    print(trend_summary)

    daily_radar = {
        "date": today,
        "timezone": settings.radar_timezone,
        "generated_at": now.isoformat(),
        "subscription_scope": DEFAULT_SUBSCRIPTION_SCOPE,
        "subscription_summary": {
            "source_count": len(subscription_settings.get("sources", [])),
            "project_link_count": len(subscription_settings.get("project_links", [])),
            "preferred_topics": (
                subscription_settings.get("topic_preferences", {}).get("preferred_topics", [])
            ),
            "blocked_topics": (
                subscription_settings.get("topic_preferences", {}).get("blocked_topics", [])
            ),
            "boosted_topics": (
                subscription_settings.get("topic_preferences", {}).get("boosted_topics", [])
            ),
            "signal_rules": subscription_settings.get("signal_rules", {}),
            "source_runtime_summary": subscription_source_summary,
        },
        "agent_watch": agent_watch_summary,
        "friction_signals": friction_signals_summary,
        "signal_count": current_signal_count,
        "new_first_seen_signal_count": new_count,
        "matched_existing_signal_count": preserved_count,
        "insight_count": len(insights_data),
        "source_stats": source_stats,
        "trend_summary": trend_summary,
        "topic_trends": topic_trends,
        "topic_momentum": topic_momentum,
        "rising_topics": rising_topics,
        "topic_evolution": topic_evolution,
        "weekly_topic_summary": weekly_topic_summary,
        "weekly_momentum": weekly_momentum,
        "strategic_priority": strategic_priority,
        "executive_summary": executive_summary,
        "signals": signals_data,
        "insights": insights_data,
    }

    intelligence_outputs = build_intelligence_outputs(
        today=today,
        generated_at=now.isoformat(),
        topic_trends=topic_trends,
        topic_momentum=topic_momentum,
        rising_topics=rising_topics,
        strategic_priority=strategic_priority,
        weekly_momentum=weekly_momentum,
    )

    save_json(signals_data, PIPELINE_SIGNALS_FILE)
    save_json(insights_data, OUTPUT_DIR / "insights.json")
    save_json(daily_radar, OUTPUT_DIR / "daily_radar.json")
    save_json(agent_watch_repo_snapshots, OUTPUT_DIR / "agent_watch_repo_snapshots.json")
    save_json(agent_watch_repo_profiles, OUTPUT_DIR / "agent_watch_repo_profiles.json")
    save_json(agent_watch_tracking_state, OUTPUT_DIR / "agent_watch_tracking_state.json")
    save_json(friction_tracking_state, OUTPUT_DIR / "friction_tracking_state.json")
    save_json(friction_signal_profiles, OUTPUT_DIR / "friction_signal_profiles.json")
    save_intelligence_outputs_locally(intelligence_outputs)

    import traceback
    obsidian_vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()

    if obsidian_vault:
        try:
            export_to_obsidian(
                vault_root=obsidian_vault,
                signals_data=signals_data,
                daily_radar=daily_radar,
                project_registry_path=BASE_DIR / "data" / "project_registry.json",
            )
            print("STEP OK: export_to_obsidian")

            export_research_map(Path(obsidian_vault))
            print("STEP OK: export_research_map")
            export_topic_graph(Path(obsidian_vault))
            print("STEP OK: export_topic_graph")
            export_topic_intelligence(Path(obsidian_vault), signals_data)
            print("STEP OK: export_topic_intelligence")

            
            export_topic_momentum(Path(obsidian_vault), signals_data)
            print("STEP OK: export_topic_momentum")
            print("Obsidian export completed.")
        except Exception as e:
            print(f"Obsidian export failed: {e}")
            traceback.print_exc()
    else:
        print("OBSIDIAN_VAULT_PATH not set. Skip Obsidian export.")
    save_feed_activity(today, rss_fetched, new_count)

    history_file = save_dated_daily_radar(OUTPUT_DIR, today, daily_radar)

    print("Saved all outputs locally.")
    print(f"Saved dated daily radar history: {history_file}")

    if s3_uploads_disabled():
        print("S3 uploads disabled by local-only setting. Skip output uploads.")
        print("AI Radar run completed successfully.")
        return

    s3 = S3Writer()
    upload_outputs_to_s3(
        s3=s3,
        today=today,
        signals_data=signals_data,
        insights_data=insights_data,
        daily_radar=daily_radar,
        write_signals_history=(new_count > 0),
    )
    upload_intelligence_outputs_to_s3(
        s3=s3,
        today=today,
        intelligence_outputs=intelligence_outputs,
    )

    print("AI Radar run completed successfully.")


def main() -> None:
    global ARTIFACT_WRITTEN_COUNT, CURRENT_PIPELINE_RUN_ID

    run_id = uuid.uuid4().hex
    CURRENT_PIPELINE_RUN_ID = run_id
    ARTIFACT_WRITTEN_COUNT = 0
    started_perf = time.perf_counter()
    started_at = datetime.now(settings.timezone)
    today = started_at.strftime("%Y-%m-%d")

    try:
        _run_main_pipeline()
    except Exception as exc:
        finished_at = datetime.now(settings.timezone)
        _safe_record_pipeline_run(
            {
                "run_id": run_id,
                "date": today,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": _duration_seconds(started_perf),
                "success": False,
                "error_count": 1,
                "error_type": type(exc).__name__,
                "artifact_written_count": ARTIFACT_WRITTEN_COUNT,
            }
        )
        _safe_write_daily_metrics_summary(today)
        _safe_upload_metrics_outputs_to_s3(today)
        raise

    finished_at = datetime.now(settings.timezone)
    _safe_record_pipeline_run(
        {
            "run_id": run_id,
            "date": today,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": _duration_seconds(started_perf),
            "success": True,
            "error_count": 0,
            "artifact_written_count": ARTIFACT_WRITTEN_COUNT,
        }
    )
    _safe_write_daily_metrics_summary(today)
    _safe_upload_metrics_outputs_to_s3(today)


if __name__ == "__main__":
    main()
