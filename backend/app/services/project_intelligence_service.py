from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from dotenv import load_dotenv

from app.project_registry import list_active_projects, list_projects
from app.prompts.registry import (
    project_fit_analysis_prompts,
    project_update_review_prompts,
    updated_project_documents_prompts,
)
from app.services.execution_policy_service import PolicyInput
from app.services.fallback_policy_service import execute_policy_text_json
from app.services.github_project_reader import (
    GitHubRequestError,
    create_pull_request,
    create_repo_branch,
    fetch_project_github_context,
    normalize_repo_name,
    upsert_repo_file,
)
from app.services.llm_executor_service import execute_text_json_task
from app.services.project_calibration_event_service import append_project_calibration_event
from app.services.project_review_record_service import append_project_review_record
from app.services.project_takeaway_constants import (
    ACTION_STATE_COMPLETED,
    EVENT_TYPE_BY_ACTION_STATE,
    EVENT_TYPE_BY_REVIEW_OUTCOME,
    PROJECT_FOLLOWUP_EVENT_WATCH_REVIEWED,
    PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
    PROJECT_IMPROVEMENT_STATUS_REOPENED,
    REVIEW_OUTCOME_ACTION,
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_OUTCOME_WATCH,
    REVIEW_OUTCOMES,
)
from app.services.subscription_settings_service import load_subscription_settings
from app.services.verification_metadata_reader import (
    build_action_eligibility_summary,
    get_model_provenance,
    has_project_takeaway_verification_context,
)


BASE_DIR = Path(__file__).resolve().parents[2] / "data"
PROJECT_CONTEXT_CACHE_DIR = BASE_DIR / "project_context_cache"
PROJECT_IMPROVEMENTS_DIR = BASE_DIR / "project_improvements"

PROJECT_CONTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
PROJECT_IMPROVEMENTS_S3_PREFIX = (
    os.getenv("PROJECT_IMPROVEMENTS_S3_PREFIX")
    or "project_intelligence/improvements"
).strip().strip("/")

UNVERIFIED_MANUAL_ENTRY_SOURCE = "unverified_manual_entry"
UNVERIFIED_MANUAL_ENTRY_STATUS = "unverified_manual_entry"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_project_takeaway_write_metadata(
    *,
    verification_metadata: dict[str, Any] | None,
    candidate_source: str,
    status: str,
) -> tuple[dict[str, Any], str]:
    metadata = dict(verification_metadata) if isinstance(verification_metadata, dict) else {}
    normalized_status = _safe_text(status).lower()
    normalized_source = _safe_text(candidate_source)

    if has_project_takeaway_verification_context(metadata):
        return metadata, normalized_source

    if normalized_status == "candidate" and not metadata.get("manual_project_takeaway_override"):
        raise ValueError("Project Takeaway candidate creation requires verification metadata.")

    if normalized_source == "signal_completion":
        metadata = {
            **metadata,
            "verification_required": True,
            "verification_status": metadata.get("verification_status") or UNVERIFIED_MANUAL_ENTRY_STATUS,
            "candidate_source": UNVERIFIED_MANUAL_ENTRY_SOURCE,
        }
        return metadata, UNVERIFIED_MANUAL_ENTRY_SOURCE

    return metadata, normalized_source


def _execute_project_policy_json(
    *,
    task_type: str,
    query: str,
    system_prompt: str,
    user_prompt: str,
    importance_score: float,
    requires_traceability: bool,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    return execute_policy_text_json(
        policy_input=PolicyInput(
            task_type=task_type,
            query=query,
            user_visible=True,
            importance_score=importance_score,
            requires_traceability=requires_traceability,
            source_count=1,
            metadata={"source_count": 1, "context_label": "project_intelligence"},
        ),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata={"source_count": 1, "context_label": "project_intelligence"},
        executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_json_task(
            task_type=effective_task_type,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            max_tokens=1800 if task_type != "strategy" else 2600,
            temperature=0.2,
            system_prompt=patched_system_prompt,
            user_prompt=patched_user_prompt,
        ),
    )


def _truncate(value: str, limit: int = 900) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _cache_file_path(project_id: str) -> Path:
    return PROJECT_CONTEXT_CACHE_DIR / f"{project_id}.json"


def _improvement_file_path(project_id: str) -> Path:
    return PROJECT_IMPROVEMENTS_DIR / f"{project_id}.json"


def _improvement_s3_key(project_id: str) -> str:
    safe_project_id = _safe_text(project_id).replace("/", "_").replace("\\", "_")
    return f"{PROJECT_IMPROVEMENTS_S3_PREFIX}/{safe_project_id}.json"


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            config=Config(
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 1},
            ),
        )
    except Exception:
        return None


def _local_output_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_USE_LOCAL_OUTPUT", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_improvement_payload(project_id: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"project_id": project_id, "items": []}

    items = payload.get("items")
    if not isinstance(items, list):
        items = []

    return {
        "project_id": project_id,
        "updated_at": payload.get("updated_at") or _utc_now_iso(),
        "items": items,
    }


def _read_s3_improvements(project_id: str) -> dict[str, Any] | None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None

    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=_improvement_s3_key(project_id))
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _write_s3_improvements(project_id: str, payload: dict[str, Any]) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return

    client.put_object(
        Bucket=S3_BUCKET,
        Key=_improvement_s3_key(project_id),
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def load_cached_project_context(project_id: str) -> dict[str, Any] | None:
    path = _cache_file_path(project_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def save_cached_project_context(project_id: str, repo: str, github_context: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "project_id": project_id,
        "repo": repo,
        "fetched_at": _utc_now_iso(),
        "github": github_context,
    }
    _cache_file_path(project_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def get_project_github_context_with_cache(
    project: dict[str, Any],
    *,
    force_refresh: bool = False,
    ttl_hours: int = 12,
) -> dict[str, Any]:
    project_id = str(project.get("project_id") or "").strip()
    repo = str(project.get("repo") or "").strip()

    if not project_id:
        return {
            "project_id": "",
            "repo": repo,
            "fetched_at": None,
            "github": fetch_project_github_context(repo),
        }

    cached = load_cached_project_context(project_id)
    if not force_refresh and cached and cached.get("repo") == repo:
        fetched_at_raw = str(cached.get("fetched_at") or "").strip()
        try:
            fetched_at = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00"))
        except Exception:
            fetched_at = None

        if fetched_at and fetched_at >= datetime.now(timezone.utc) - timedelta(hours=ttl_hours):
            return cached

    github = fetch_project_github_context(repo)
    return save_cached_project_context(project_id, repo, github)


def build_project_analysis_context(limit: int = 6, user_id: str | None = None) -> str:
    projects = list_active_projects()
    if not projects:
        return "No registered projects available."

    preferred_project_ids: list[str] = []
    if user_id:
        subscription_settings = load_subscription_settings(user_id)
        preferred_project_ids = [
            str(item.get("project_id") or "").strip()
            for item in subscription_settings.get("project_links") or []
            if isinstance(item, dict) and item.get("enabled")
        ]

    if preferred_project_ids:
        order_map = {project_id: index for index, project_id in enumerate(preferred_project_ids)}
        projects.sort(
            key=lambda project: (
                0 if str(project.get("project_id") or "") in order_map else 1,
                order_map.get(str(project.get("project_id") or ""), 999),
                str(project.get("name") or "").lower(),
            )
        )

    sections: list[str] = []
    for project in projects[:limit]:
        project_id = str(project.get("project_id") or "").strip()
        cache_payload = load_cached_project_context(project_id) if project_id else None
        github = cache_payload.get("github", {}) if isinstance(cache_payload, dict) else {}

        block = {
            "project_id": project_id,
            "name": project.get("name", ""),
            "status": project.get("status", ""),
            "description": _truncate(project.get("description", ""), 360),
            "current_state": _truncate(project.get("current_state", ""), 500),
            "manual_roadmap": _truncate(project.get("roadmap", ""), 500),
            "topics": project.get("topics", []),
            "subscription_priority": "linked" if project_id in preferred_project_ids else "normal",
            "github_repo": project.get("repo", ""),
            "github_status": github.get("status") if isinstance(github, dict) else "",
            "github_readme_excerpt": _truncate(((github.get("readme") or {}) if isinstance(github, dict) else {}).get("content", ""), 500),
            "github_roadmap_excerpt": _truncate(((github.get("roadmap") or {}) if isinstance(github, dict) else {}).get("content", ""), 500),
        }
        sections.append(json.dumps(block, ensure_ascii=False, indent=2))

    return "REGISTERED PROJECTS\n" + "\n\n".join(sections)


def _parse_project_takeaway_map(value: Any) -> dict[str, str]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return {
            str(key).strip(): _safe_text(raw)
            for key, raw in value.items()
            if str(key).strip() and _safe_text(raw)
        }

    text = _safe_text(value)
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {
                str(key).strip(): _safe_text(raw)
                for key, raw in parsed.items()
                if str(key).strip() and _safe_text(raw)
            }
    except Exception:
        pass

    project_map: dict[str, str] = {}
    normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in normalized_lines:
        for project in list_active_projects():
            name = _safe_text(project.get("name"))
            if not name:
                continue
            if name.lower() in line.lower():
                project_map[name] = line

    if project_map:
        return project_map

    return {"General": text}


def _resolve_projects_for_takeaway_map(
    project_takeaway_map: dict[str, str],
    subscription_project_links: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    registry_projects = list_active_projects()
    matched: list[dict[str, Any]] = []

    for project_name, takeaway in project_takeaway_map.items():
        lowered_name = project_name.lower()
        resolved = None
        for project in registry_projects:
            name = _safe_text(project.get("name"))
            if name and (name.lower() == lowered_name or name.lower() in lowered_name or lowered_name in name.lower()):
                resolved = project
                break
        if resolved:
            subscription_match = next(
                (
                    link
                    for link in (subscription_project_links or [])
                    if isinstance(link, dict)
                    and _safe_text(link.get("project_id")) == _safe_text(resolved.get("project_id"))
                ),
                None,
            )
            matched.append(
                {
                    "project": resolved,
                    "takeaway": takeaway,
                    "subscription_match": subscription_match,
                }
            )

    combined_text = " ".join(project_takeaway_map.values()).lower()
    if not matched:
        for project in registry_projects:
            name = _safe_text(project.get("name"))
            topics = [_safe_text(item).lower() for item in project.get("topics", [])]
            if name and name.lower() in combined_text:
                matched.append({"project": project, "takeaway": " ".join(project_takeaway_map.values())})
                continue
            if any(topic and topic in combined_text for topic in topics):
                subscription_match = next(
                    (
                        link
                        for link in (subscription_project_links or [])
                        if isinstance(link, dict)
                        and _safe_text(link.get("project_id")) == _safe_text(project.get("project_id"))
                    ),
                    None,
                )
                matched.append(
                    {
                        "project": project,
                        "takeaway": " ".join(project_takeaway_map.values()),
                        "subscription_match": subscription_match,
                    }
                )

    subscription_ids = {
        _safe_text(item.get("project_id"))
        for item in (subscription_project_links or [])
        if isinstance(item, dict) and _safe_text(item.get("project_id"))
    }
    if subscription_ids:
        fallback_takeaway = " ".join(project_takeaway_map.values()).strip()
        for project in registry_projects:
            project_id = _safe_text(project.get("project_id"))
            if not project_id or project_id not in subscription_ids:
                continue
            matched.append(
                {
                    "project": project,
                    "takeaway": fallback_takeaway,
                    "subscription_match": next(
                        (
                            link
                            for link in (subscription_project_links or [])
                            if isinstance(link, dict)
                            and _safe_text(link.get("project_id")) == project_id
                        ),
                        None,
                    ),
                }
            )

    unique: dict[str, dict[str, Any]] = {}
    for item in matched:
        project = item["project"]
        project_id = _safe_text(project.get("project_id"))
        if project_id and project_id not in unique:
            unique[project_id] = item

    resolved_items = list(unique.values())
    resolved_items.sort(
        key=lambda item: (
            int(((item.get("subscription_match") or {}) if isinstance(item.get("subscription_match"), dict) else {}).get("match_score") or 0),
            1 if item.get("subscription_match") else 0,
        ),
        reverse=True,
    )
    return resolved_items


def _build_project_fit_analysis(
    *,
    project: dict[str, Any],
    signal_title: str,
    signal_summary: str,
    why_it_matters: str,
    takeaway: str,
    synthesized_insight: str,
    final_reflection: str,
    subscription_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_name = _safe_text(project.get("name")).lower()
    project_topics = " ".join(_safe_text(topic).lower() for topic in project.get("topics", []))
    combined_signal_text = " ".join(
        [
            signal_title,
            signal_summary,
            why_it_matters,
            takeaway,
            synthesized_insight,
            final_reflection,
        ]
    ).lower()

    heuristic_score = 48
    if project_name and project_name in combined_signal_text:
        heuristic_score += 18
    if project_topics and any(topic and topic in combined_signal_text for topic in project_topics.split()):
        heuristic_score += 14
    if _safe_text(project.get("current_state")):
        heuristic_score += 6
    if _safe_text(project.get("roadmap")):
        heuristic_score += 6
    subscription_match_score = int(((subscription_match or {}) if isinstance(subscription_match, dict) else {}).get("match_score") or 0)
    matched_keywords = [
        _safe_text(keyword)
        for keyword in ((subscription_match or {}) if isinstance(subscription_match, dict) else {}).get("matched_keywords", [])
        if _safe_text(keyword)
    ]
    if subscription_match_score:
        heuristic_score += min(18, 5 * subscription_match_score)
    heuristic_score = max(20, min(heuristic_score, 95))

    fallback = {
        "project_takeaway": takeaway,
        "score": heuristic_score,
        "should_apply": heuristic_score >= 60,
        "fit_reason": (
            f"{takeaway or signal_summary}"
            + (
                f" Subscription-linked intake matched: {', '.join(matched_keywords)}."
                if matched_keywords
                else ""
            )
        ).strip(),
        "benefits": synthesized_insight or why_it_matters or takeaway,
        "suggested_stage": "review",
        "readme_update_suggestion": "Update the README only if this improvement changes project scope, current priorities, product direction, or planned capabilities.",
        "roadmap_update_suggestion": takeaway,
        "subscription_linked": bool(subscription_match_score),
        "subscription_match_score": subscription_match_score,
        "subscription_matched_keywords": matched_keywords,
        "fit_analysis_status": "ready",
    }

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        return fallback

    cache_payload = get_project_github_context_with_cache(project, force_refresh=False)
    github = cache_payload.get("github", {}) if isinstance(cache_payload, dict) else {}
    readme_excerpt = _truncate(((github.get("readme") or {}) if isinstance(github, dict) else {}).get("content", ""), 800)
    roadmap_excerpt = _truncate(((github.get("roadmap") or {}) if isinstance(github, dict) else {}).get("content", ""), 800)

    system_prompt, user_prompt = project_fit_analysis_prompts(
        project_payload={
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "status": project.get("status"),
            "description": project.get("description"),
            "current_state": project.get("current_state"),
            "manual_roadmap": project.get("roadmap"),
            "topics": project.get("topics", []),
            "github_readme_excerpt": readme_excerpt,
            "github_roadmap_excerpt": roadmap_excerpt,
        },
        signal_payload={
            "signal_title": signal_title,
            "signal_summary": signal_summary,
            "why_it_matters": why_it_matters,
            "project_takeaway": takeaway,
            "strategic_takeaway": synthesized_insight,
            "final_reflection": final_reflection,
        },
    )

    try:
        parsed, route, policy_metadata = _execute_project_policy_json(
            task_type="reason",
            query=signal_title,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            importance_score=80,
            requires_traceability=True,
        )
        return {
            "project_takeaway": _safe_text(parsed.get("project_takeaway")) or fallback["project_takeaway"],
            "score": max(0, min(100, int(parsed.get("score", heuristic_score)))),
            "should_apply": bool(parsed.get("should_apply", True)),
            "fit_reason": _safe_text(parsed.get("fit_reason")) or fallback["fit_reason"],
            "benefits": _safe_text(parsed.get("benefits")) or fallback["benefits"],
            "suggested_stage": _safe_text(parsed.get("suggested_stage")) or fallback["suggested_stage"],
            "readme_update_suggestion": _safe_text(parsed.get("readme_update_suggestion")) or fallback["readme_update_suggestion"],
            "roadmap_update_suggestion": _safe_text(parsed.get("roadmap_update_suggestion")) or fallback["roadmap_update_suggestion"],
            "subscription_linked": fallback["subscription_linked"],
            "subscription_match_score": fallback["subscription_match_score"],
            "subscription_matched_keywords": fallback["subscription_matched_keywords"],
            "fit_analysis_status": "ready",
            "policy_metadata": policy_metadata,
        }
    except Exception as exc:
        print(f"[WARN] Project fit analysis routed generation failed: {exc}")
        return fallback


def _build_project_fit_stub(
    *,
    project: dict[str, Any],
    signal_title: str,
    signal_summary: str,
    why_it_matters: str,
    takeaway: str,
    synthesized_insight: str,
    final_reflection: str,
    subscription_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_name = _safe_text(project.get("name")).lower()
    project_topics = " ".join(_safe_text(topic).lower() for topic in project.get("topics", []))
    combined_signal_text = " ".join(
        [
            signal_title,
            signal_summary,
            why_it_matters,
            takeaway,
            synthesized_insight,
            final_reflection,
        ]
    ).lower()

    heuristic_score = 48
    if project_name and project_name in combined_signal_text:
        heuristic_score += 18
    if project_topics and any(topic and topic in combined_signal_text for topic in project_topics.split()):
        heuristic_score += 14
    if _safe_text(project.get("current_state")):
        heuristic_score += 6
    if _safe_text(project.get("roadmap")):
        heuristic_score += 6

    subscription_match_score = int(((subscription_match or {}) if isinstance(subscription_match, dict) else {}).get("match_score") or 0)
    matched_keywords = [
        _safe_text(keyword)
        for keyword in ((subscription_match or {}) if isinstance(subscription_match, dict) else {}).get("matched_keywords", [])
        if _safe_text(keyword)
    ]
    if subscription_match_score:
        heuristic_score += min(18, 5 * subscription_match_score)
    heuristic_score = max(20, min(heuristic_score, 95))

    return {
        "project_takeaway": takeaway,
        "score": heuristic_score,
        "should_apply": heuristic_score >= 60,
        "fit_reason": (
            f"{takeaway or signal_summary}"
            + (
                f" Subscription-linked intake matched: {', '.join(matched_keywords)}."
                if matched_keywords
                else ""
            )
        ).strip(),
        "benefits": synthesized_insight or why_it_matters or takeaway,
        "suggested_stage": "review",
        "readme_update_suggestion": "Fit analysis has not been generated yet. Open this improvement and run Refresh Fit Analysis when you are ready to evaluate README changes.",
        "roadmap_update_suggestion": takeaway,
        "subscription_linked": bool(subscription_match_score),
        "subscription_match_score": subscription_match_score,
        "subscription_matched_keywords": matched_keywords,
        "fit_analysis_status": "pending",
    }


def _build_project_update_reviews(
    *,
    project: dict[str, Any],
    improvement: dict[str, Any],
) -> dict[str, str]:
    fallback = {
        "readme_review": _safe_text(improvement.get("readme_update_suggestion"))
        or "Add a short section to the README explaining why this improvement matters, what capability it adds, and how it changes current project direction.",
        "roadmap_review": _safe_text(improvement.get("roadmap_update_suggestion"))
        or "Add this item to the roadmap under the suggested stage and describe the benefit, scope, and next execution step.",
    }

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        return fallback

    cache_payload = get_project_github_context_with_cache(project, force_refresh=False)
    github = cache_payload.get("github", {}) if isinstance(cache_payload, dict) else {}
    readme_excerpt = _truncate(((github.get("readme") or {}) if isinstance(github, dict) else {}).get("content", ""), 1200)
    roadmap_excerpt = _truncate(((github.get("roadmap") or {}) if isinstance(github, dict) else {}).get("content", ""), 1200)

    system_prompt, user_prompt = project_update_review_prompts(
        project_payload={
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "description": project.get("description"),
            "current_state": project.get("current_state"),
            "manual_roadmap": project.get("roadmap"),
            "github_readme_excerpt": readme_excerpt,
            "github_roadmap_excerpt": roadmap_excerpt,
        },
        improvement_payload={
            "signal_title": improvement.get("signal_title"),
            "signal_summary": improvement.get("signal_summary"),
            "project_takeaway": improvement.get("takeaway"),
            "fit_reason": improvement.get("fit_reason"),
            "benefits": improvement.get("benefits"),
            "score": improvement.get("score"),
            "suggested_stage": improvement.get("suggested_stage"),
            "readme_update_suggestion": improvement.get("readme_update_suggestion"),
            "roadmap_update_suggestion": improvement.get("roadmap_update_suggestion"),
        },
    )

    try:
        parsed, route, policy_metadata = _execute_project_policy_json(
            task_type="summary",
            query=str(improvement.get("signal_title") or project.get("name") or ""),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            importance_score=72,
            requires_traceability=True,
        )
        return {
            "readme_review": _safe_text(parsed.get("readme_review")) or fallback["readme_review"],
            "roadmap_review": _safe_text(parsed.get("roadmap_review")) or fallback["roadmap_review"],
            "policy_metadata": policy_metadata,
        }
    except Exception as exc:
        print(f"[WARN] Project update review routed generation failed: {exc}")
        return fallback


def _build_updated_project_documents(
    *,
    project: dict[str, Any],
    improvement: dict[str, Any],
) -> dict[str, str]:
    cache_payload = get_project_github_context_with_cache(project, force_refresh=False)
    github = cache_payload.get("github", {}) if isinstance(cache_payload, dict) else {}
    current_readme = _safe_text(((github.get("readme") or {}) if isinstance(github, dict) else {}).get("content"))
    current_roadmap = _safe_text(((github.get("roadmap") or {}) if isinstance(github, dict) else {}).get("content"))
    current_readme_sha = _safe_text(((github.get("readme") or {}) if isinstance(github, dict) else {}).get("sha"))
    current_roadmap_sha = _safe_text(((github.get("roadmap") or {}) if isinstance(github, dict) else {}).get("sha"))
    manual_roadmap = _safe_text(project.get("roadmap"))

    fallback_readme = current_readme or (
        f"# {project.get('name') or project.get('project_id')}\n\n"
        f"{_safe_text(project.get('description'))}\n\n"
        f"## Potential improvement under review\n\n{_safe_text(improvement.get('readme_review')) or _safe_text(improvement.get('readme_update_suggestion'))}"
    )
    fallback_roadmap = current_roadmap or manual_roadmap or (
        f"# Roadmap\n\n## Backlog candidate\n\n{_safe_text(improvement.get('roadmap_review')) or _safe_text(improvement.get('roadmap_update_suggestion'))}"
    )

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        return {
            "updated_readme": fallback_readme,
            "updated_roadmap": fallback_roadmap,
            "baseline_readme_sha": current_readme_sha,
            "baseline_roadmap_sha": current_roadmap_sha,
        }

    system_prompt, user_prompt = updated_project_documents_prompts(
        project_payload={
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "description": project.get("description"),
            "status": project.get("status"),
            "current_state": project.get("current_state"),
            "manual_roadmap": manual_roadmap,
        },
        improvement_payload={
            "signal_title": improvement.get("signal_title"),
            "signal_summary": improvement.get("signal_summary"),
            "project_takeaway": improvement.get("takeaway"),
            "fit_reason": improvement.get("fit_reason"),
            "benefits": improvement.get("benefits"),
            "score": improvement.get("score"),
            "suggested_stage": improvement.get("suggested_stage"),
            "readme_update_suggestion": improvement.get("readme_update_suggestion"),
            "roadmap_update_suggestion": improvement.get("roadmap_update_suggestion"),
            "readme_review": improvement.get("readme_review"),
            "roadmap_review": improvement.get("roadmap_review"),
        },
        current_readme=current_readme,
        current_roadmap=current_roadmap or manual_roadmap,
    )

    try:
        parsed, route, policy_metadata = _execute_project_policy_json(
            task_type="strategy",
            query=str(improvement.get("signal_title") or project.get("name") or ""),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            importance_score=90,
            requires_traceability=True,
        )
        return {
            "updated_readme": _safe_text(parsed.get("updated_readme")) or fallback_readme,
            "updated_roadmap": _safe_text(parsed.get("updated_roadmap")) or fallback_roadmap,
            "baseline_readme_sha": current_readme_sha,
            "baseline_roadmap_sha": current_roadmap_sha,
            "policy_metadata": policy_metadata,
        }
    except Exception as exc:
        print(f"[WARN] Project document generation routed generation failed: {exc}")
        return {
            "updated_readme": fallback_readme,
            "updated_roadmap": fallback_roadmap,
            "baseline_readme_sha": current_readme_sha,
            "baseline_roadmap_sha": current_roadmap_sha,
        }


def load_project_improvements(project_id: str) -> dict[str, Any]:
    path = _improvement_file_path(project_id)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return _normalize_improvement_payload(project_id, payload)
        except Exception:
            pass

    if _local_output_enabled():
        return {"project_id": project_id, "items": []}

    s3_payload = _read_s3_improvements(project_id)
    if s3_payload is not None:
        normalized = _normalize_improvement_payload(project_id, s3_payload)
        try:
            _improvement_file_path(project_id).write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return normalized

    return {"project_id": project_id, "items": []}


def save_project_improvements(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_improvement_payload(
        project_id,
        {
            "project_id": project_id,
            "updated_at": _utc_now_iso(),
            "items": payload.get("items", []),
        },
    )
    _improvement_file_path(project_id).write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if _local_output_enabled():
        return normalized
    try:
        _write_s3_improvements(project_id, normalized)
    except Exception:
        pass
    return normalized


def save_reasoning_counter_check_draft(
    project_id: str,
    signal_id: str,
    draft: dict[str, Any],
) -> dict[str, Any]:
    normalized_project_id = _safe_text(project_id)
    normalized_signal_id = _safe_text(signal_id)
    if not normalized_project_id or not normalized_signal_id:
        raise ValueError("project_id and signal_id are required to persist a counter-check draft.")
    if not isinstance(draft, dict) or not draft:
        raise ValueError("counter-check draft is required.")

    payload = load_project_improvements(normalized_project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == normalized_signal_id:
            saved_at = _utc_now_iso()
            updated = {
                **existing,
                "reasoning_counter_check_draft": draft,
                "reasoning_counter_check_saved_at": saved_at,
                "reasoning_counter_check_effect": "reviewer_advisory_only",
            }
            items[index] = updated
            save_project_improvements(normalized_project_id, {"items": items})
            return updated

    raise ValueError(f"Improvement not found for signal: {normalized_signal_id}")


def confirm_project_improvement(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            verification_metadata = existing.get("verification_metadata") if isinstance(existing.get("verification_metadata"), dict) else {}
            action_eligibility = build_action_eligibility_summary(verification_metadata)
            project_takeaway = action_eligibility.get("project_takeaway_candidate")
            if (
                isinstance(project_takeaway, dict)
                and not bool(project_takeaway.get("allowed"))
            ):
                raise ValueError(_safe_text(project_takeaway.get("reason")) or "Verification blocks Project Takeaway confirmation.")
            updated = {
                **existing,
                "status": REVIEW_OUTCOME_CONFIRMED,
                "confirmed_at": _utc_now_iso(),
                "action_eligibility": action_eligibility,
            }
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            append_project_calibration_event(
                event_type=EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_CONFIRMED],
                project_id=project_id,
                signal_id=signal_id,
                outcome=REVIEW_OUTCOME_CONFIRMED,
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            append_project_review_record(
                project_id=project_id,
                signal_id=signal_id,
                outcome=REVIEW_OUTCOME_CONFIRMED,
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def override_confirm_project_improvement(
    project_id: str,
    signal_id: str,
    *,
    reason: str,
    expected_outcome: str,
) -> dict[str, Any]:
    override_note = _safe_text(reason)
    override_expected_outcome = _safe_text(expected_outcome)
    if not override_note:
        raise ValueError("Override confirmation requires a manual override note.")
    if not override_expected_outcome:
        raise ValueError("Override confirmation requires an expected outcome.")

    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            verification_metadata = existing.get("verification_metadata") if isinstance(existing.get("verification_metadata"), dict) else {}
            verification_metadata = {
                **verification_metadata,
                "manual_project_takeaway_override": True,
                "manual_override_note": override_note,
                "manual_override_expected_outcome": override_expected_outcome,
                "manual_override_type": "confirm",
            }
            action_eligibility = build_action_eligibility_summary(verification_metadata)
            now = _utc_now_iso()
            updated = {
                **existing,
                "status": REVIEW_OUTCOME_CONFIRMED,
                "confirmed_at": now,
                "review_outcome": REVIEW_OUTCOME_CONFIRMED,
                "manual_override_confirmed_at": now,
                "manual_override_note": override_note,
                "manual_override_expected_outcome": override_expected_outcome,
                "candidate_source": "manual_project_takeaway_override",
                "verification_metadata": verification_metadata,
                "action_eligibility": action_eligibility,
            }
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            append_project_calibration_event(
                event_type=EVENT_TYPE_BY_REVIEW_OUTCOME[REVIEW_OUTCOME_CONFIRMED],
                project_id=project_id,
                signal_id=signal_id,
                outcome=REVIEW_OUTCOME_CONFIRMED,
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            append_project_review_record(
                project_id=project_id,
                signal_id=signal_id,
                outcome=REVIEW_OUTCOME_CONFIRMED,
                reason=override_note,
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def close_project_takeaway_candidate(
    project_id: str,
    signal_id: str,
    *,
    status: str,
    reason: str = "",
    review_date: str = "",
    success_criteria: str = "",
    watch_status: str = "",
    expected_outcome: str = "",
    due_date: str = "",
    allow_manual_override: bool = False,
) -> dict[str, Any]:
    normalized_status = _safe_text(status).lower()
    closeable_outcomes = REVIEW_OUTCOMES - {REVIEW_OUTCOME_CONFIRMED}
    if normalized_status not in closeable_outcomes:
        raise ValueError("Candidate status must be rejected, dismissed, watch, or action.")

    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            verification_metadata = existing.get("verification_metadata") if isinstance(existing.get("verification_metadata"), dict) else {}
            action_eligibility = build_action_eligibility_summary(verification_metadata)
            low_risk_action = action_eligibility.get("low_risk_action_candidate")
            if (
                normalized_status == REVIEW_OUTCOME_ACTION
                and isinstance(low_risk_action, dict)
                and not bool(low_risk_action.get("allowed"))
                and not allow_manual_override
            ):
                raise ValueError(_safe_text(low_risk_action.get("reason")) or "Verification blocks action creation.")
            now = _utc_now_iso()
            if normalized_status == REVIEW_OUTCOME_ACTION and allow_manual_override:
                verification_metadata = {
                    **verification_metadata,
                    "manual_project_takeaway_override": True,
                    "manual_override_note": _safe_text(reason),
                    "manual_override_expected_outcome": _safe_text(expected_outcome),
                    "manual_override_type": "action",
                }
                action_eligibility = build_action_eligibility_summary(verification_metadata)
            updated = {
                **existing,
                "status": normalized_status,
                "review_outcome": normalized_status,
                "reviewed_at": now,
                "action_eligibility": action_eligibility,
                "verification_metadata": verification_metadata,
            }
            if normalized_status == REVIEW_OUTCOME_REJECTED:
                updated["rejected_at"] = now
                updated["rejection_reason"] = _safe_text(reason)
            elif normalized_status == REVIEW_OUTCOME_DISMISSED:
                updated["dismissed_at"] = now
                updated["dismissal_reason"] = _safe_text(reason)
            elif normalized_status == REVIEW_OUTCOME_WATCH:
                updated["watched_at"] = now
                updated["watch_reason"] = _safe_text(reason)
                updated["watch_review_date"] = _safe_text(review_date)
                updated["watch_success_criteria"] = _safe_text(success_criteria)
                updated["watch_status"] = _safe_text(watch_status) or "watching"
            else:
                updated["action_created_at"] = now
                updated["action_reason"] = _safe_text(reason)
                updated["action_expected_outcome"] = _safe_text(expected_outcome)
                updated["action_due_date"] = _safe_text(due_date)
                updated["action_review_date"] = _safe_text(review_date)
                if allow_manual_override:
                    updated["candidate_source"] = "manual_project_takeaway_override"
                    updated["manual_override_action_created_at"] = now
                    updated["manual_override_note"] = _safe_text(reason)
                    updated["manual_override_expected_outcome"] = _safe_text(expected_outcome)
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            append_project_calibration_event(
                event_type=EVENT_TYPE_BY_REVIEW_OUTCOME[normalized_status],
                project_id=project_id,
                signal_id=signal_id,
                outcome=normalized_status,
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            append_project_review_record(
                project_id=project_id,
                signal_id=signal_id,
                outcome=normalized_status,
                reason=_safe_text(reason),
                source_status=_safe_text(existing.get("status")),
                item=updated,
            )
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def override_action_project_takeaway_candidate(
    project_id: str,
    signal_id: str,
    *,
    reason: str,
    review_date: str,
    expected_outcome: str,
    due_date: str,
) -> dict[str, Any]:
    if not _safe_text(reason):
        raise ValueError("Override action requires a manual override note.")
    if not _safe_text(expected_outcome):
        raise ValueError("Override action requires an expected outcome.")
    if not _safe_text(due_date):
        raise ValueError("Override action requires an action due date.")
    if not _safe_text(review_date):
        raise ValueError("Override action requires an action review date.")

    return close_project_takeaway_candidate(
        project_id,
        signal_id,
        status=REVIEW_OUTCOME_ACTION,
        reason=reason,
        expected_outcome=expected_outcome,
        due_date=due_date,
        review_date=review_date,
        allow_manual_override=True,
    )


def complete_project_action_item(
    project_id: str,
    signal_id: str,
    *,
    note: str = "",
    followup_result: str = "",
    evidence_update: str = "",
    next_review_date: str = "",
) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            if _safe_text(existing.get("status")).lower() != REVIEW_OUTCOME_ACTION:
                raise ValueError("Only action items can be marked completed.")
            now = _utc_now_iso()
            updated = {
                **existing,
                "status": PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
                "review_outcome": _safe_text(existing.get("review_outcome")) or REVIEW_OUTCOME_ACTION,
                "action_state": ACTION_STATE_COMPLETED,
                "action_completed_at": now,
                "action_completion_note": _safe_text(note),
                "action_completion_result": _safe_text(followup_result) or "completed",
                "action_completion_evidence_update": _safe_text(evidence_update),
                "action_next_review_date": _safe_text(next_review_date),
            }
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            append_project_calibration_event(
                event_type=EVENT_TYPE_BY_ACTION_STATE[ACTION_STATE_COMPLETED],
                project_id=project_id,
                signal_id=signal_id,
                outcome=PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
                source_status=_safe_text(existing.get("status")),
                item=updated,
                followup_result=updated["action_completion_result"],
                review_note=updated["action_completion_note"],
                evidence_update=updated["action_completion_evidence_update"],
                next_review_date=updated["action_next_review_date"],
                expected_outcome=_safe_text(updated.get("action_expected_outcome")),
            )
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def review_project_watch_item(
    project_id: str,
    signal_id: str,
    *,
    followup_result: str,
    note: str = "",
    evidence_update: str = "",
    next_review_date: str = "",
) -> dict[str, Any]:
    normalized_result = _safe_text(followup_result)
    if not normalized_result:
        raise ValueError("Watch review requires a follow-up result.")

    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            if _safe_text(existing.get("status")).lower() != REVIEW_OUTCOME_WATCH:
                raise ValueError("Only watch items can be reviewed as watch follow-up.")
            now = _utc_now_iso()
            followup_count = _safe_int(existing.get("watch_followup_count")) + 1
            updated = {
                **existing,
                "watch_last_reviewed_at": now,
                "watch_followup_result": normalized_result,
                "watch_review_note": _safe_text(note),
                "watch_evidence_update": _safe_text(evidence_update),
                "watch_next_review_date": _safe_text(next_review_date),
                "watch_followup_count": followup_count,
            }
            if _safe_text(next_review_date):
                updated["watch_review_date"] = _safe_text(next_review_date)
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            append_project_calibration_event(
                event_type=PROJECT_FOLLOWUP_EVENT_WATCH_REVIEWED,
                project_id=project_id,
                signal_id=signal_id,
                outcome=REVIEW_OUTCOME_WATCH,
                source_status=_safe_text(existing.get("status")),
                item=updated,
                followup_result=normalized_result,
                review_note=_safe_text(note),
                evidence_update=_safe_text(evidence_update),
                next_review_date=_safe_text(next_review_date),
            )
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def reopen_project_improvement(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for index, existing in enumerate(items):
        if isinstance(existing, dict) and _safe_text(existing.get("signal_id")) == signal_id:
            updated = {
                **existing,
                "status": PROJECT_IMPROVEMENT_STATUS_REOPENED,
            }
            updated.pop("confirmed_at", None)
            items[index] = updated
            save_project_improvements(project_id, {"items": items})
            return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def refresh_project_improvement_analysis(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    project = next(
        (project for project in list_projects() if _safe_text(project.get("project_id")) == project_id),
        None,
    )
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    for index, existing in enumerate(items):
        if not isinstance(existing, dict):
            continue
        if _safe_text(existing.get("signal_id")) != signal_id:
            continue

        source_takeaway = (
            _safe_text(existing.get("source_takeaway"))
            or _safe_text(existing.get("takeaway"))
            or _safe_text(existing.get("fit_reason"))
            or _safe_text(existing.get("signal_summary"))
        )

        refreshed = {
            **existing,
            "source_takeaway": source_takeaway,
            **_build_project_fit_analysis(
                project=project,
                signal_title=_safe_text(existing.get("signal_title")),
                signal_summary=_safe_text(existing.get("signal_summary")),
                why_it_matters=_safe_text(existing.get("why_it_matters")),
                takeaway=source_takeaway,
                synthesized_insight=_safe_text(existing.get("benefits")) or _safe_text(existing.get("roadmap_update_suggestion")),
                final_reflection=_safe_text(existing.get("final_reflection")),
            ),
        }
        refreshed["takeaway"] = _safe_text(refreshed.get("project_takeaway")) or source_takeaway
        items[index] = refreshed
        save_project_improvements(project_id, {"items": items})
        return refreshed

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def generate_project_improvement_reviews(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    project = next(
        (project for project in list_projects() if _safe_text(project.get("project_id")) == project_id),
        None,
    )
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    for index, existing in enumerate(items):
        if not isinstance(existing, dict):
            continue
        if _safe_text(existing.get("signal_id")) != signal_id:
            continue

        reviews = _build_project_update_reviews(project=project, improvement=existing)
        updated = {
            **existing,
            **reviews,
        }
        items[index] = updated
        save_project_improvements(project_id, {"items": items})
        return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def generate_project_improvement_updated_documents(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    project = next(
        (project for project in list_projects() if _safe_text(project.get("project_id")) == project_id),
        None,
    )
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    for index, existing in enumerate(items):
        if not isinstance(existing, dict):
            continue
        if _safe_text(existing.get("signal_id")) != signal_id:
            continue

        updated_docs = _build_updated_project_documents(project=project, improvement=existing)
        updated = {
            **existing,
            **updated_docs,
            "documents_generated_at": _utc_now_iso(),
        }
        items[index] = updated
        save_project_improvements(project_id, {"items": items})
        return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def submit_project_improvement_to_github(project_id: str, signal_id: str) -> dict[str, Any]:
    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    project = next(
        (project for project in list_projects() if _safe_text(project.get("project_id")) == project_id),
        None,
    )
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    repo = normalize_repo_name(_safe_text(project.get("repo")))
    if not repo:
        raise ValueError("Project GitHub repo is not configured.")

    cache_payload = get_project_github_context_with_cache(project, force_refresh=False)
    github = cache_payload.get("github", {}) if isinstance(cache_payload, dict) else {}

    for index, existing in enumerate(items):
        if not isinstance(existing, dict):
            continue
        if _safe_text(existing.get("signal_id")) != signal_id:
            continue
        if _safe_text(existing.get("status")) != REVIEW_OUTCOME_CONFIRMED:
            raise ValueError("Confirm the improvement before submitting to GitHub.")

        updated_readme = _safe_text(existing.get("updated_readme"))
        updated_roadmap = _safe_text(existing.get("updated_roadmap"))
        baseline_readme_sha = _safe_text(existing.get("baseline_readme_sha"))
        baseline_roadmap_sha = _safe_text(existing.get("baseline_roadmap_sha"))
        if not updated_readme and not updated_roadmap:
            raise ValueError("Generate updated README or roadmap documents before submitting to GitHub.")

        latest_cache = get_project_github_context_with_cache(project, force_refresh=True)
        latest_github = latest_cache.get("github", {}) if isinstance(latest_cache, dict) else {}
        default_branch = _safe_text((((latest_github.get("repository") or {}) if isinstance(latest_github, dict) else {}).get("default_branch"))) or "main"
        readme_path = _safe_text((((latest_github.get("readme") or {}) if isinstance(latest_github, dict) else {}).get("path"))) or "README.md"
        roadmap_path = _safe_text((((latest_github.get("roadmap") or {}) if isinstance(latest_github, dict) else {}).get("path"))) or "ROADMAP.md"
        latest_readme = ((latest_github.get("readme") or {}) if isinstance(latest_github, dict) else {})
        latest_roadmap = ((latest_github.get("roadmap") or {}) if isinstance(latest_github, dict) else {})
        latest_readme_sha = _safe_text(latest_readme.get("sha"))
        latest_roadmap_sha = _safe_text(latest_roadmap.get("sha"))

        if updated_readme and baseline_readme_sha and latest_readme_sha and baseline_readme_sha != latest_readme_sha:
            raise ValueError("README changed on GitHub after this draft was generated. Refresh GitHub context and regenerate the updated README before submitting.")
        if updated_roadmap and baseline_roadmap_sha and latest_roadmap_sha and baseline_roadmap_sha != latest_roadmap_sha:
            raise ValueError("Roadmap changed on GitHub after this draft was generated. Refresh GitHub context and regenerate the updated roadmap before submitting.")

        branch_name = f"ai-radar/{project_id.lower()}-{signal_id.lower()[:24]}".replace("_", "-")

        try:
            create_repo_branch(repo, base_branch=default_branch, new_branch=branch_name)
            if updated_readme:
                upsert_repo_file(
                    repo,
                    branch=branch_name,
                    path=readme_path,
                    content=updated_readme,
                    message=f"Update README for {project.get('name') or project_id} from AI Radar improvement",
                )
            if updated_roadmap:
                upsert_repo_file(
                    repo,
                    branch=branch_name,
                    path=roadmap_path,
                    content=updated_roadmap,
                    message=f"Update roadmap for {project.get('name') or project_id} from AI Radar improvement",
                )
        except GitHubRequestError as exc:
            raise ValueError(exc.message) from exc

        compare_url = f"https://github.com/{repo}/compare/{default_branch}...{branch_name}?expand=1"
        pr_url = ""
        pr_title = f"AI Radar: apply improvement to {project.get('name') or project_id}"
        pr_body = "\n".join(
            [
                "This PR was generated from an AI Radar project improvement workflow.",
                "",
                f"- Project: {_safe_text(project.get('name')) or project_id}",
                f"- Signal: {_safe_text(existing.get('signal_title')) or signal_id}",
                f"- Score: {_safe_text(existing.get('score'))}",
                f"- Suggested stage: {_safe_text(existing.get('suggested_stage'))}",
                "",
                "Please review the README and roadmap updates before merging.",
            ]
        )
        try:
            pr_payload = create_pull_request(
                repo,
                head_branch=branch_name,
                base_branch=default_branch,
                title=pr_title,
                body=pr_body,
            )
            pr_url = _safe_text(pr_payload.get("html_url"))
        except GitHubRequestError:
            pr_url = ""

        updated = {
            **existing,
            "github_submission": {
                "repo": repo,
                "branch": branch_name,
                "default_branch": default_branch,
                "readme_path": readme_path if updated_readme else None,
                "roadmap_path": roadmap_path if updated_roadmap else None,
                "compare_url": compare_url,
                "pull_request_url": pr_url,
                "submitted_at": _utc_now_iso(),
            },
        }
        items[index] = updated
        save_project_improvements(project_id, {"items": items})
        return updated

    raise ValueError(f"Improvement not found for signal: {signal_id}")


def add_signal_to_project_improvements(
    *,
    signal_id: str,
    signal_title: str,
    signal_summary: str,
    why_it_matters: str,
    relevance_to_projects: Any,
    synthesized_insight: str,
    final_reflection: str,
    subscription_project_links: list[dict[str, Any]] | None = None,
    verification_metadata: dict[str, Any] | None = None,
    candidate_source: str = "signal_completion",
    status: str = "new",
) -> list[dict[str, Any]]:
    project_takeaway_map = _parse_project_takeaway_map(relevance_to_projects)
    effective_verification_metadata, effective_candidate_source = _normalize_project_takeaway_write_metadata(
        verification_metadata=verification_metadata,
        candidate_source=candidate_source,
        status=status,
    )
    matched_projects = _resolve_projects_for_takeaway_map(
        project_takeaway_map,
        subscription_project_links=subscription_project_links,
    )
    written: list[dict[str, Any]] = []
    normalized_signal_id = _safe_text(signal_id)
    is_manual_source = normalized_signal_id.startswith("manual_") or normalized_signal_id.startswith("manual-")
    manual_session_id = ""
    if is_manual_source:
        manual_session_id = (
            normalized_signal_id[len("manual_") :]
            if normalized_signal_id.startswith("manual_")
            else normalized_signal_id
        )

    for item in matched_projects:
        project = item["project"]
        takeaway = _safe_text(item["takeaway"])
        subscription_match = item.get("subscription_match") if isinstance(item, dict) else None
        project_id = _safe_text(project.get("project_id"))
        project_name = _safe_text(project.get("name"))
        if not project_id:
            continue

        payload = load_project_improvements(project_id)
        items = payload.get("items", [])
        if not isinstance(items, list):
            items = []

        improvement_item = {
            "signal_id": signal_id,
            "signal_title": signal_title,
            "signal_summary": signal_summary,
            "source_type": "manual_upload" if is_manual_source else "signal",
            "manual_session_id": manual_session_id,
            "project_id": project_id,
            "project_name": project_name,
            "source_takeaway": takeaway,
            "why_it_matters": why_it_matters,
            **_build_project_fit_stub(
                project=project,
                signal_title=signal_title,
                signal_summary=signal_summary,
                why_it_matters=why_it_matters,
                takeaway=takeaway,
                synthesized_insight=synthesized_insight,
                final_reflection=final_reflection,
                subscription_match=subscription_match if isinstance(subscription_match, dict) else None,
            ),
            "final_reflection": final_reflection,
            "status": status,
            "candidate_source": effective_candidate_source,
            "verification_metadata": effective_verification_metadata,
            "produced_by_model": get_model_provenance(effective_verification_metadata),
            "action_eligibility": build_action_eligibility_summary(effective_verification_metadata),
            "saved_at": _utc_now_iso(),
        }
        improvement_item["takeaway"] = _safe_text(improvement_item.get("project_takeaway")) or takeaway

        replaced = False
        for index, existing in enumerate(items):
            if (
                isinstance(existing, dict)
                and _safe_text(existing.get("signal_id")) == signal_id
                and _safe_text(existing.get("project_id")) == project_id
            ):
                items[index] = {**existing, **improvement_item}
                replaced = True
                break

        if not replaced:
            items.insert(0, improvement_item)

        save_project_improvements(project_id, {"items": items})
        written.append(improvement_item)

    return written
