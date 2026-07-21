from __future__ import annotations

import json
import os
import importlib.util
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from dotenv import load_dotenv

from app.services.llm_executor_service import execute_text_json_task
from app.prompts.registry import source_assistant_prompts
from app.project_registry import list_active_projects


BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "settings" / "subscriptions"
ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_RSS_COLLECTOR_PATH = REPO_ROOT / "signal_collectors" / "rss_collector.py"
load_dotenv(ROOT_ENV_PATH)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
SUBSCRIPTION_S3_PREFIX = (
    os.getenv("SUBSCRIPTION_SETTINGS_S3_PREFIX")
    or "settings/subscriptions"
).strip().strip("/")


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _default_payload(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
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


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _file_path(user_id: str) -> Path:
    normalized = (user_id or "demo_default").strip() or "demo_default"
    safe_name = normalized.replace("/", "_").replace("\\", "_")
    return BASE_DIR / f"{safe_name}.json"


def _s3_key(user_id: str) -> str:
    normalized = (user_id or "demo_default").strip() or "demo_default"
    safe_name = normalized.replace("/", "_").replace("\\", "_")
    return f"{SUBSCRIPTION_S3_PREFIX}/{safe_name}.json"


def get_subscription_settings_status(user_id: str) -> dict[str, Any]:
    path = _file_path(user_id)
    settings = load_subscription_settings(user_id)
    source_count = len(settings.get("sources", [])) if isinstance(settings, dict) else 0
    last_updated = None
    if path.exists():
        try:
            last_updated = path.stat().st_mtime
        except Exception:
            last_updated = None

    return {
        "local_path": str(path),
        "s3_bucket": S3_BUCKET or "",
        "s3_key": _s3_key(user_id),
        "saved_source_count": source_count,
        "last_updated_epoch": last_updated,
    }


def _merge_payload_with_default(user_id: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _default_payload(user_id)

    default = _default_payload(user_id)
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


def _read_local_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_local_payload(path: Path, payload: dict[str, Any]) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_s3_payload(user_id: str) -> dict[str, Any] | None:
    local_mode = str(os.getenv("AI_RADAR_USE_LOCAL_OUTPUT", "")).strip().lower()
    if local_mode in {"1", "true", "yes", "on"}:
        return None

    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None

    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=_s3_key(user_id))
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _write_s3_payload(user_id: str, payload: dict[str, Any]) -> str:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return "skipped"

    client.put_object(
        Bucket=S3_BUCKET,
        Key=_s3_key(user_id),
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return "succeeded"


def load_subscription_settings(user_id: str) -> dict[str, Any]:
    path = _file_path(user_id)
    local_payload = _read_local_payload(path)
    if local_payload is not None:
        return _merge_payload_with_default(user_id, local_payload)

    s3_payload = _read_s3_payload(user_id)
    if s3_payload is not None:
        merged = _merge_payload_with_default(user_id, s3_payload)
        try:
            _write_local_payload(path, merged)
        except Exception:
            pass
        return merged

    return _default_payload(user_id)


def save_subscription_settings_with_status(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _file_path(user_id)
    normalized = load_subscription_settings(user_id)

    normalized["sources"] = payload.get("sources", [])
    normalized["topic_preferences"] = payload.get("topic_preferences", normalized["topic_preferences"])
    normalized["signal_rules"] = payload.get("signal_rules", normalized["signal_rules"])
    normalized["project_links"] = payload.get("project_links", [])

    _write_local_payload(path, normalized)
    print(
        "===== SUBSCRIPTIONS SAVE: "
        f"user_id={user_id!r} "
        f"local_path={str(path)!r} "
        f"s3_bucket={S3_BUCKET or 'unset'!r} "
        f"s3_key={_s3_key(user_id)!r} ====="
    )
    s3_sync = "skipped"
    s3_error_type = ""
    try:
        s3_sync = _write_s3_payload(user_id, normalized)
        if s3_sync == "succeeded":
            print("===== SUBSCRIPTIONS SAVE: S3 write succeeded =====")
        else:
            print("===== SUBSCRIPTIONS SAVE: S3 write skipped, local fallback retained =====")
    except Exception as exc:
        s3_sync = "failed"
        s3_error_type = type(exc).__name__
        print("===== SUBSCRIPTIONS SAVE: S3 write failed, local fallback retained =====")

    return {
        "path": path,
        "local_saved": True,
        "source_count": len(normalized.get("sources", [])) if isinstance(normalized.get("sources"), list) else 0,
        "s3_sync": s3_sync,
        "s3_bucket": S3_BUCKET or "",
        "s3_key": _s3_key(user_id),
        "s3_error_type": s3_error_type,
    }


def save_subscription_settings(user_id: str, payload: dict[str, Any]) -> Path:
    result = save_subscription_settings_with_status(user_id, payload)
    path = result.get("path")
    if isinstance(path, Path):
        return path
    return _file_path(user_id)


def _load_legacy_rss_sources() -> dict[str, str]:
    if not LEGACY_RSS_COLLECTOR_PATH.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location("legacy_rss_collector", LEGACY_RSS_COLLECTOR_PATH)
        if not spec or not spec.loader:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sources = getattr(module, "RSS_SOURCES", {})
        if not isinstance(sources, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in sources.items()
            if str(key).strip() and str(value).strip()
        }
    except Exception:
        return {}


def import_legacy_rss_sources(user_id: str) -> dict[str, Any]:
    settings = load_subscription_settings(user_id)
    current_sources = settings.get("sources", [])
    existing_urls = {
        str(item.get("url", "")).strip().lower()
        for item in current_sources
        if isinstance(item, dict)
    }
    imported_items: list[dict[str, Any]] = []
    legacy_sources = _load_legacy_rss_sources()

    for source_key, source_url in legacy_sources.items():
        normalized_url = source_url.strip().lower()
        if not normalized_url or normalized_url in existing_urls:
            continue

        imported_items.append(
            {
                "id": f"legacy_{source_key}",
                "name": source_key.replace("_", " ").title(),
                "url": source_url,
                "type": "rss",
                "enabled": True,
                "priority": "normal",
                "tags": ["rss", "legacy-imported"],
            }
        )
        existing_urls.add(normalized_url)

    if imported_items:
        settings["sources"] = [*current_sources, *imported_items]
        save_subscription_settings(user_id, settings)

    return {
        "imported_count": len(imported_items),
        "total_legacy_sources": len(legacy_sources),
        "imported_sources": imported_items,
    }


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _detect_source_type_from_url(url: str) -> str:
    lowered = url.lower()
    if lowered.endswith(".xml") or "rss" in lowered or "feed" in lowered:
        return "rss"
    if any(token in lowered for token in ("arxiv.org", "paperswithcode", "research", "paper", "journal")):
        return "research"
    if any(token in lowered for token in ("substack.com", "newsletter", "beehiiv", "mailchi.mp")):
        return "newsletter"
    if any(token in lowered for token in ("blog", "news", "updates", "announcements")):
        return "official_blog"
    return "custom_url"


def _guess_source_name(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if not host:
        return "New Source"
    root = host.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return root.title() or "New Source"


def _guess_tags(url: str) -> list[str]:
    lowered = url.lower()
    tags: list[str] = []
    if "openai" in lowered:
        tags.extend(["openai", "official"])
    if "anthropic" in lowered:
        tags.extend(["anthropic", "official"])
    if "google" in lowered or "deepmind" in lowered or "gemini" in lowered:
        tags.extend(["google", "ai_models"])
    if "research" in lowered or "arxiv" in lowered:
        tags.append("research")
    if "policy" in lowered or "government" in lowered:
        tags.append("policy")
    if "newsletter" in lowered or "substack" in lowered:
        tags.append("newsletter")
    if "rss" in lowered or "feed" in lowered:
        tags.append("rss")
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped


def suggest_source_from_url(
    url: str,
    user_context: str | None = None,
    extra_context: str | None = None,
) -> dict[str, Any]:
    normalized_url = _safe_text(url)
    if not normalized_url:
        return {
            "url": "",
            "source_name": "",
            "recommended_type": "custom_url",
            "recommended_priority": "normal",
            "suggested_tags": [],
            "rss_available": False,
            "possible_subscribe_url": "",
            "notes": "Provide a URL first.",
            "subscription_candidates": [],
        }

    lowered_url = normalized_url.lower()
    youtube_hint = "youtube.com" in lowered_url or "youtu.be" in lowered_url
    fallback = {
        "url": normalized_url,
        "source_name": _guess_source_name(normalized_url),
        "recommended_type": "custom_url" if youtube_hint else _detect_source_type_from_url(normalized_url),
        "recommended_priority": "normal",
        "suggested_tags": _guess_tags(normalized_url) + (["youtube", "creator"] if youtube_hint else []),
        "rss_available": any(token in lowered_url for token in ("rss", "feed", ".xml")),
        "possible_subscribe_url": normalized_url if any(token in lowered_url for token in ("rss", "feed", ".xml")) else "",
        "notes": (
            "This suggestion was inferred from the URL structure. You can adjust the result before adding it to Source Library."
            if not youtube_hint
            else "This looks like a YouTube channel or video source. Use the channel URL as a tracked source first. If you later find a direct uploads feed or newsletter/site link, add that as a second source."
        ),
        "subscription_candidates": [
            {
                "label": "Primary source",
                "url": normalized_url,
                "type": "custom_url" if youtube_hint else _detect_source_type_from_url(normalized_url),
                "reason": "Track the original page or channel directly.",
            }
        ],
    }

    if youtube_hint:
        fallback["subscription_candidates"].append(
            {
                "label": "Related website or newsletter",
                "url": "",
                "type": "newsletter",
                "reason": "If the creator links a newsletter, Skool community, blog, or website, add that as a second subscribable source.",
            }
        )

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        return fallback

    system_prompt, user_prompt = source_assistant_prompts(
        user_context=_safe_text(user_context),
        normalized_url=normalized_url,
        extra_context=_safe_text(extra_context),
    )

    try:
        parsed, route = execute_text_json_task(
            task_type="structure",
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            max_tokens=1600,
            temperature=0.2,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        source_type = _safe_text(parsed.get("recommended_type")).lower() or fallback["recommended_type"]
        if source_type not in {"rss", "official_blog", "research", "newsletter", "custom_url"}:
            source_type = fallback["recommended_type"]
        priority = _safe_text(parsed.get("recommended_priority")).lower() or fallback["recommended_priority"]
        if priority not in {"high", "normal", "low"}:
            priority = fallback["recommended_priority"]
        tags = [
            _safe_text(item).lower()
            for item in (parsed.get("suggested_tags") or [])
            if _safe_text(item)
        ]
        if not tags:
            tags = fallback["suggested_tags"]
        return {
            "url": normalized_url,
            "source_name": _safe_text(parsed.get("source_name")) or fallback["source_name"],
            "recommended_type": source_type,
            "recommended_priority": priority,
            "suggested_tags": tags,
            "rss_available": bool(parsed.get("rss_available", fallback["rss_available"])),
            "possible_subscribe_url": _safe_text(parsed.get("possible_subscribe_url")) or fallback["possible_subscribe_url"],
            "notes": _safe_text(parsed.get("notes")) or fallback["notes"],
            "subscription_candidates": [
                {
                    "label": _safe_text(item.get("label")) or "Candidate source",
                    "url": _safe_text(item.get("url")),
                    "type": _safe_text(item.get("type")) or "custom_url",
                    "reason": _safe_text(item.get("reason")) or "Suggested by AI Source Assistant.",
                }
                for item in (parsed.get("subscription_candidates") or [])
                if isinstance(item, dict)
            ] or fallback["subscription_candidates"],
        }
    except Exception as exc:
        print(f"[WARN] Source suggestion routed generation failed: {exc}")
        return fallback


def _score_as_percent(value: Any) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric <= 1:
        numeric *= 100
    return numeric


def _match_source(item: dict[str, Any], source: dict[str, Any]) -> bool:
    url = str(item.get("url") or item.get("source_url") or item.get("link") or "").strip().lower()
    source_name = str(item.get("source") or "").strip().lower()
    configured_url = str(source.get("url") or "").strip().lower()
    configured_name = str(source.get("name") or "").strip().lower()

    if configured_url and url:
        try:
            configured_host = urlparse(configured_url).netloc.lower()
            item_host = urlparse(url).netloc.lower()
            if configured_host and item_host and configured_host == item_host:
                return True
        except Exception:
            pass
        if configured_url in url:
            return True

    if configured_name and source_name and configured_name in source_name:
        return True

    return False


def match_subscription_project_links(
    text: str,
    settings: dict[str, Any] | None,
    active_project_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not settings:
        return []

    text_blob = str(text or "").strip().lower()
    if not text_blob:
        return []

    if active_project_ids is None:
        active_project_ids = {
            str(project.get("project_id") or "").strip()
            for project in list_active_projects()
            if str(project.get("project_id") or "").strip()
        }

    matches: list[dict[str, Any]] = []
    for project in settings.get("project_links") or []:
        if not isinstance(project, dict) or not project.get("enabled"):
            continue

        project_id = str(project.get("project_id") or "").strip()
        if not project_id or project_id not in active_project_ids:
            continue

        keywords = _clean_list(project.get("topic_keywords"))
        matched_keywords = [
            keyword
            for keyword in keywords
            if keyword.lower() in text_blob
        ]

        if matched_keywords:
            matches.append(
                {
                    "project_id": project_id,
                    "topic_keywords": keywords,
                    "matched_keywords": matched_keywords,
                    "match_score": len(matched_keywords),
                }
            )

    matches.sort(
        key=lambda item: (
            int(item.get("match_score") or 0),
            len(item.get("matched_keywords") or []),
        ),
        reverse=True,
    )
    return matches


def build_subscription_settings_context(user_id: str | None) -> str:
    settings = load_subscription_settings(user_id or "demo_default")
    sources = settings.get("sources") or []
    topic_preferences = settings.get("topic_preferences") or {}
    signal_rules = settings.get("signal_rules") or {}
    project_links = settings.get("project_links") or []
    active_project_ids = {
        str(project.get("project_id") or "").strip()
        for project in list_active_projects()
        if str(project.get("project_id") or "").strip()
    }

    active_sources = [
        {
            "name": str(item.get("name") or "").strip(),
            "type": str(item.get("type") or "").strip(),
            "priority": str(item.get("priority") or "").strip(),
            "tags": _clean_list(item.get("tags")),
        }
        for item in sources
        if isinstance(item, dict) and item.get("enabled")
    ]

    enabled_projects = [
        {
            "project_id": str(item.get("project_id") or "").strip(),
            "topic_keywords": _clean_list(item.get("topic_keywords")),
        }
        for item in project_links
        if isinstance(item, dict)
        and item.get("enabled")
        and str(item.get("project_id") or "").strip() in active_project_ids
    ]

    payload = {
        "active_sources": active_sources,
        "preferred_topics": _clean_list(topic_preferences.get("preferred_topics")),
        "blocked_topics": _clean_list(topic_preferences.get("blocked_topics")),
        "boosted_topics": _clean_list(topic_preferences.get("boosted_topics")),
        "signal_rules": {
            "min_score": signal_rules.get("min_score"),
            "auto_analyze_score": signal_rules.get("auto_analyze_score"),
            "auto_backlog_score": signal_rules.get("auto_backlog_score"),
            "max_signals_per_day": signal_rules.get("max_signals_per_day"),
        },
        "project_linked_intake": enabled_projects,
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


def apply_subscription_settings_to_signals(
    items: list[dict[str, Any]],
    settings: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not settings:
        return items

    topic_preferences = settings.get("topic_preferences") or {}
    signal_rules = settings.get("signal_rules") or {}
    sources = settings.get("sources") or []
    project_links = settings.get("project_links") or []

    preferred_topics = {str(item).strip().lower() for item in topic_preferences.get("preferred_topics", []) if str(item).strip()}
    blocked_topics = {str(item).strip().lower() for item in topic_preferences.get("blocked_topics", []) if str(item).strip()}
    boosted_topics = {str(item).strip().lower() for item in topic_preferences.get("boosted_topics", []) if str(item).strip()}
    active_sources = [item for item in sources if isinstance(item, dict) and item.get("enabled")]
    active_project_ids = {
        str(project.get("project_id") or "").strip()
        for project in list_active_projects()
        if str(project.get("project_id") or "").strip()
    }

    min_score = float(signal_rules.get("min_score", 0) or 0)
    auto_analyze_score = float(signal_rules.get("auto_analyze_score", 0) or 0)
    auto_backlog_score = float(signal_rules.get("auto_backlog_score", 0) or 0)

    filtered: list[dict[str, Any]] = []
    for item in items:
        topic = str(item.get("topic") or "").strip().lower()
        score_percent = _score_as_percent(item.get("score"))
        is_manual = bool(item.get("is_manual"))

        if topic and topic in blocked_topics:
            continue

        if active_sources and not is_manual:
            if not any(_match_source(item, source) for source in active_sources):
                continue

        if not is_manual and score_percent is not None and score_percent < min_score:
            continue

        text_blob = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("topic") or ""),
                str(item.get("why_it_matters") or ""),
                str(item.get("relevance_to_projects") or ""),
                str(item.get("synthesized_insight") or ""),
            ]
        ).lower()
        matched_projects = match_subscription_project_links(
            text_blob,
            {"project_links": project_links},
            active_project_ids=active_project_ids,
        )

        topic_priority = "normal"
        if topic and topic in preferred_topics:
            topic_priority = "preferred"
        if topic and topic in boosted_topics:
            topic_priority = "boosted"

        auto_action_hint = ""
        if not is_manual and score_percent is not None:
            if auto_analyze_score and score_percent >= auto_analyze_score:
                auto_action_hint = "auto_analyze_candidate"
            elif auto_backlog_score and score_percent >= auto_backlog_score:
                auto_action_hint = "auto_backlog_candidate"

        filtered.append(
            {
                **item,
                "subscription_score_percent": score_percent,
                "subscription_topic_priority": topic_priority,
                "subscription_project_links": matched_projects,
                "auto_action_hint": auto_action_hint,
            }
        )

    filtered.sort(
        key=lambda item: (
            2 if item.get("subscription_topic_priority") == "boosted" else 1 if item.get("subscription_topic_priority") == "preferred" else 0,
            item.get("subscription_score_percent") or 0,
            item.get("collected_at") or item.get("published_at") or item.get("_sort_updated_at") or "",
        ),
        reverse=True,
    )
    return filtered
