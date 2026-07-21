from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import boto3
import os
from datetime import datetime
import json
import base64
from pathlib import Path
from openai import OpenAI
from app.services.context_bridge import build_analysis_context
from app.services.execution_policy_service import PolicyInput
from app.services.execution_policy_service import decide_execution_policy
from app.services.fallback_policy_service import execute_policy_text
from app.services.llm_executor_service import execute_text_task
from app.services.model_router_service import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    PROVIDER_PERPLEXITY,
)
from app.prompts.registry import (
    workspace_chat_system_prompt,
    workspace_reflection_polish_prompts,
    workspace_visual_prompt,
)
from app.project_registry import list_projects
from app.services.request_identity import resolve_request_user_id
from app.services.admin_guard import require_admin_auth
from app.services.project_repo_snapshot_service import load_project_repo_snapshot
from app.services.reflection_polish_pair_service import build_reflection_polish_pair
from app.services.reflection_polish_store_service import get_reflection_polish_pair_detail
from app.services.reflection_polish_store_service import list_reflection_polish_pairs
from app.services.reflection_polish_store_service import save_reflection_polish_pair
from app.services.reflection_polish_store_service import save_reflection_polish_review

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

load_dotenv(ROOT_ENV_PATH)

router = APIRouter()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

GPT_VISUAL_MODEL = os.getenv("GPT_VISUAL_MODEL", "gpt-5.5")
WORKSPACE_VISUALS_DIR = Path(__file__).resolve().parents[2] / "data" / "workspace_visuals"
WORKSPACE_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR = Path(__file__).resolve().parents[2] / "data" / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
WORKSPACE_S3_PREFIX = (
    os.getenv("WORKSPACE_S3_PREFIX")
    or "workspace/records"
).strip().strip("/")
WORKSPACE_VISUALS_S3_PREFIX = (
    os.getenv("WORKSPACE_VISUALS_S3_PREFIX")
    or "workspace/visuals"
).strip().strip("/")


def _workspace_provider_fallback_enabled() -> bool:
    value = str(os.getenv("ENABLE_WORKSPACE_PROVIDER_FALLBACK", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_provider_retryable_error(error: Exception) -> bool:
    text = str(error)
    lowered = text.lower()
    return (
        "overloaded_error" in text
        or "Overloaded" in text
        or "529" in text
        or "rate limit" in lowered
        or "timeout" in lowered
    )

RECENT_DISCUSSION_CONTEXT_LIMIT = 4
RECENT_DISCUSSION_MESSAGE_CHAR_LIMIT = 1200


def format_workspace_model_error(model_label: str, error: Exception) -> str:
    text = str(error)
    lowered = text.lower()

    if (
        "invalid_api_key" in lowered
        or "incorrect api key provided" in lowered
        or ("401" in lowered and "api key" in lowered)
    ):
        if model_label.lower() == "chatgpt":
            return (
                "ChatGPT is not available right now because the OpenAI API key is invalid. "
                "Update OPENAI_API_KEY in the root .env file and restart the backend."
            )
        if model_label.lower() == "claude":
            return (
                "Claude is not available right now because the Anthropic API key is invalid. "
                "Update ANTHROPIC_API_KEY in the root .env file and restart the backend."
            )
        if model_label.lower() == "perplexity":
            return (
                "Perplexity is not available right now because the Perplexity API key is invalid. "
                "Update PERPLEXITY_API_KEY in the root .env file and restart the backend."
            )

    if "not_found_error" in lowered or "model not found" in lowered or "model:" in lowered:
        return (
            f"{model_label} is configured, but the selected model is not available for the current account. "
            f"Check the {model_label} model setting in the root .env file."
        )

    return f"{model_label} error: {error}"


def _compact_text(value: object, limit: int = 900) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def build_project_repo_snapshot_context(*, max_projects: int = 5, max_chars: int = 6000) -> str:
    """Return cached project repo context for LLM chat prompts.

    Repo snapshots are project context only. They are not verification evidence.
    """
    sections: list[str] = []
    for project in list_projects():
        if project.get("enabled", True) is False:
            continue
        project_id = str(project.get("project_id") or "").strip()
        if not project_id:
            continue
        snapshot = load_project_repo_snapshot(project_id)
        if not snapshot:
            continue
        status = str(snapshot.get("status") or "").strip()
        if status in {"missing", "not_connected", "failed"}:
            continue

        manifests = [
            str(item.get("path") or "").strip()
            for item in snapshot.get("manifests", [])
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        ][:5]
        commits = [
            str(item.get("message") or "").strip()
            for item in snapshot.get("recent_commits", [])
            if isinstance(item, dict) and str(item.get("message") or "").strip()
        ][:3]
        hints = [str(item).strip() for item in snapshot.get("architecture_hints", []) if str(item).strip()][:8]
        keywords = [str(item).strip() for item in snapshot.get("keywords", []) if str(item).strip()][:12]

        section = f"""
Project: {project.get("name") or project_id} ({project_id})
Snapshot status: {status}
Repo: {snapshot.get("repo") or project.get("repo") or ""}
Summary: {_compact_text(snapshot.get("summary"), 500)}
README: {snapshot.get("readme_path") or "not found"}
README excerpt:
{_compact_text(snapshot.get("readme_excerpt"), 1000)}
Roadmap: {snapshot.get("roadmap_path") or "not found"}
Roadmap excerpt:
{_compact_text(snapshot.get("roadmap_excerpt"), 1000)}
Architecture hints: {", ".join(hints) if hints else "none"}
Keywords: {", ".join(keywords) if keywords else "none"}
Manifests: {", ".join(manifests) if manifests else "none"}
Recent commits: {" | ".join(commits) if commits else "none"}
""".strip()
        sections.append(section)
        if len(sections) >= max_projects:
            break

    if not sections:
        return "No cached project repo snapshots are available."
    context = (
        "Repo snapshots are project context only; they are not verification evidence.\n\n"
        + "\n\n---\n\n".join(sections)
    )
    return _compact_text(context, max_chars)


def build_recent_discussion_context(messages: list["ChatContextMessage"] | None) -> str:
    if not messages:
        return ""

    valid_messages = [
        message
        for message in messages
        if (message.role or "").strip().lower() in {"user", "assistant"} and str(message.content or "").strip()
    ]

    normalized: list[str] = []
    for message in valid_messages[-RECENT_DISCUSSION_CONTEXT_LIMIT:]:
        role = (message.role or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = _compact_text(message.content, RECENT_DISCUSSION_MESSAGE_CHAR_LIMIT)
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        normalized.append(f"{label}: {content}")

    if not normalized:
        return ""

    return "\n".join(
        [
            "Recent discussion context:",
            "Boundary: this is conversation memory only, not AI Radar verified evidence or source support.",
            *normalized,
        ]
    )


def execute_workspace_text_with_fallback(
    *,
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int = 1000,
) -> tuple[str, str, bool]:
    try:
        reply, route = execute_text_task(
            task_type=task_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_override=PROVIDER_ANTHROPIC,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            perplexity_api_key=PERPLEXITY_API_KEY,
        )
        return reply, route.provider, False
    except Exception as first_error:
        if (
            not _workspace_provider_fallback_enabled()
            or not is_provider_retryable_error(first_error)
        ):
            raise

        reply, route = execute_text_task(
            task_type=task_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_override=PROVIDER_OPENAI,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            perplexity_api_key=PERPLEXITY_API_KEY,
            fallback_used=True,
        )
        return reply, route.provider, True


def execute_workspace_text_with_policy(
    *,
    task_type: str,
    query: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int = 1000,
    provider_override: str | None = None,
    user_visible: bool = True,
    importance_score: float | None = None,
    requires_traceability: bool = False,
    source_count: int = 0,
    web_search_enabled: bool = False,
    web_search_max_uses: int | None = None,
) -> tuple[str, str, bool, dict]:
    context_label = "workspace_context_plus_web_search" if web_search_enabled else "workspace_context"
    policy_metadata_input = {
        "source_count": source_count,
        "context_label": context_label,
        "web_search_enabled": web_search_enabled,
    }
    reply, route, policy_metadata = execute_policy_text(
        policy_input=PolicyInput(
            task_type=task_type,
            query=query,
            user_visible=user_visible,
            importance_score=importance_score,
            requires_traceability=requires_traceability,
            source_count=source_count,
            metadata=policy_metadata_input,
        ),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata=policy_metadata_input,
        executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_task(
            task_type=effective_task_type,
            system_prompt=patched_system_prompt,
            user_prompt=patched_user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_override=provider_override,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            perplexity_api_key=PERPLEXITY_API_KEY,
            web_search_enabled=web_search_enabled,
            web_search_max_uses=web_search_max_uses,
        ),
    )
    policy_metadata["web_search_enabled"] = bool(getattr(route, "web_search_enabled", False))
    policy_metadata["web_search_max_uses"] = getattr(route, "web_search_max_uses", None)
    return reply, route.provider, False, policy_metadata


class ReflectionRequest(BaseModel):
    text: str
    persist_pair: bool | None = False
    signal_id: str | None = None
    signal_title: str | None = None
    signal_summary: str | None = None
    why_it_matters: str | None = None
    relevance_to_projects: str | None = None
    relevance_to_career: str | None = None
    synthesized_insight: str | None = None


class ReflectionPolishReviewRequest(BaseModel):
    outcome: str
    dimension_results: dict[str, str]
    reviewer_id: str | None = None
    reviewer_note: str | None = ""
    final_reflection_text: str | None = ""


class SaveReflectionRequest(BaseModel):
    source_type: str | None = "signal"
    content_type: str | None = "signal"
    topic: str | None = None

    signal_id: str | None = None
    signal_title: str | None = None

    selected_model: str | None = None

    user_input: str | None = None
    ai_response: str | None = None

    final_reflection: str

    signal_summary: str | None = None
    why_it_matters: str | None = None
    relevance_to_projects: str | None = None
    relevance_to_career: str | None = None
    synthesized_insight: str | None = None
    verification_metadata: dict | None = None


class GenerateVisualRequest(BaseModel):
    signal_id: str | None = None
    signal_title: str | None = None
    signal_summary: str | None = None
    why_it_matters: str | None = None
    relevance_to_projects: str | None = None
    relevance_to_career: str | None = None
    synthesized_insight: str | None = None
    verification_metadata: dict | None = None
    reflection: str | None = None
    visual_style: str | None = "architecture"
    visual_direction: str | None = None


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    provider_used: str | None = None
    model_used: str | None = None
    fallback_used: bool | None = None


class SaveChatHistoryRequest(BaseModel):
    model: str
    signal_id: str | None = None
    signal_title: str | None = None
    signal_summary: str | None = None
    why_it_matters: str | None = None
    relevance_to_projects: str | None = None
    relevance_to_career: str | None = None
    synthesized_insight: str | None = None
    reflection: str | None = None
    messages: list[ChatHistoryMessage] = []


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _workspace_local_path(file_name: str) -> Path:
    safe_name = (file_name or "").replace("/", "_").replace("\\", "_")
    return WORKSPACE_DIR / safe_name


def _workspace_s3_key(file_name: str) -> str:
    safe_name = (file_name or "").replace("\\", "_").strip("/")
    return f"{WORKSPACE_S3_PREFIX}/{safe_name}"


def _workspace_visual_local_path(file_name: str) -> Path:
    safe_name = (file_name or "").replace("/", "_").replace("\\", "_")
    return WORKSPACE_VISUALS_DIR / safe_name


def _workspace_visual_s3_key(file_name: str) -> str:
    safe_name = (file_name or "").replace("\\", "_").strip("/")
    return f"{WORKSPACE_VISUALS_S3_PREFIX}/{safe_name}"


def _write_workspace_record_local(file_name: str, record: dict) -> Path:
    file_path = _workspace_local_path(file_name)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


def _write_workspace_record_s3(file_name: str, record: dict) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return

    client.put_object(
        Bucket=S3_BUCKET,
        Key=_workspace_s3_key(file_name),
        Body=json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _read_workspace_record_s3(file_name: str) -> dict | None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None

    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=_workspace_s3_key(file_name))
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _delete_workspace_record_s3(file_name: str) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    try:
        client.delete_object(Bucket=S3_BUCKET, Key=_workspace_s3_key(file_name))
    except Exception:
        pass


def _write_workspace_visual_s3(file_name: str, content: bytes, content_type: str) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return

    client.put_object(
        Bucket=S3_BUCKET,
        Key=_workspace_visual_s3_key(file_name),
        Body=content,
        ContentType=content_type,
    )


def _read_workspace_visual_s3(file_name: str) -> tuple[bytes | None, str | None]:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None, None

    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=_workspace_visual_s3_key(file_name))
        return response["Body"].read(), response.get("ContentType")
    except Exception:
        return None, None


def _delete_workspace_visual_s3(file_name: str) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    try:
        client.delete_object(Bucket=S3_BUCKET, Key=_workspace_visual_s3_key(file_name))
    except Exception:
        pass


def _guess_workspace_visual_content_type(file_name: str) -> str:
    lowered = str(file_name or "").lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "image/jpeg"
    if lowered.endswith(".webp"):
        return "image/webp"
    if lowered.endswith(".json"):
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def _ensure_workspace_visual_local(file_name: str) -> Path:
    file_path = _workspace_visual_local_path(file_name)
    if file_path.exists():
        return file_path

    content, _ = _read_workspace_visual_s3(file_name)
    if content is not None:
        try:
            WORKSPACE_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)
        except Exception:
            pass

    return file_path


def _load_workspace_record(file_name: str) -> tuple[dict | None, Path]:
    file_path = _workspace_local_path(file_name)

    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8")), file_path
        except Exception:
            pass

    s3_record = _read_workspace_record_s3(file_name)
    if isinstance(s3_record, dict):
        try:
            _write_workspace_record_local(file_name, s3_record)
        except Exception:
            pass
        return s3_record, file_path

    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8")), file_path
        except Exception:
            return None, file_path

    return None, file_path


def _list_workspace_record_names() -> list[str]:
    names: set[str] = set()

    client = _s3_client()
    if client is not None and S3_BUCKET:
        continuation_token: str | None = None
        while True:
            kwargs = {
                "Bucket": S3_BUCKET,
                "Prefix": f"{WORKSPACE_S3_PREFIX}/",
                "MaxKeys": 1000,
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            try:
                response = client.list_objects_v2(**kwargs)
            except Exception:
                break

            for item in response.get("Contents") or []:
                key = str(item.get("Key") or "")
                if not key or key.endswith("/"):
                    continue
                names.add(key.split("/")[-1])

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

    for file_path in WORKSPACE_DIR.glob("*.json"):
        names.add(file_path.name)

    return sorted(names, reverse=True)


def build_workspace_record_path(signal_id: str | None = None) -> tuple[Path, str]:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_signal_id = (signal_id or "manual").replace("/", "_").replace("\\", "_")
    file_name = f"{timestamp}_{safe_signal_id}.json"
    file_path = _workspace_local_path(file_name)
    return file_path, file_name


def build_chat_history_file_path(signal_id: str | None, model: str) -> tuple[Path, str]:
    safe_signal_id = (signal_id or "manual").replace("/", "_").replace("\\", "_")
    safe_model = (model or "unknown").replace("/", "_").replace("\\", "_").lower()
    file_name = f"chat_{safe_signal_id}_{safe_model}.json"
    return _workspace_local_path(file_name), file_name


def build_visual_prompt(payload: GenerateVisualRequest) -> str:
    return workspace_visual_prompt(payload)


def save_generated_visual(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    payload: GenerateVisualRequest,
) -> dict:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_signal_id = (payload.signal_id or "manual").replace("/", "_").replace("\\", "_")
    extension = ".png" if "png" in mime_type else ".jpg"

    image_name = f"{timestamp}_{safe_signal_id}_gpt_visual{extension}"
    metadata_name = f"{timestamp}_{safe_signal_id}_gpt_visual.json"

    image_path = _workspace_visual_local_path(image_name)
    metadata_path = _workspace_visual_local_path(metadata_name)

    image_path.write_bytes(image_bytes)
    metadata_payload = {
        "saved_at": datetime.utcnow().isoformat(),
        "signal_id": payload.signal_id,
        "signal_title": payload.signal_title,
        "visual_style": payload.visual_style,
        "visual_direction": payload.visual_direction,
        "model": GPT_VISUAL_MODEL,
        "mime_type": mime_type,
        "image_file_name": image_name,
        "prompt": prompt,
    }
    metadata_path.write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        _write_workspace_visual_s3(image_name, image_bytes, mime_type)
        _write_workspace_visual_s3(
            metadata_name,
            json.dumps(metadata_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
        )
    except Exception:
        pass

    return {
        "image_file_name": image_name,
        "metadata_file_name": metadata_name,
        "image_url": f"/workspace_visuals/{image_name}",
        "metadata_url": f"/workspace_visuals/{metadata_name}",
    }


def save_workspace_record(
    record: dict,
    signal_id: str | None = None,
    file_name_override: str | None = None,
) -> dict:
    if file_name_override:
        file_name = file_name_override
        file_path = _workspace_local_path(file_name)
    else:
        file_path, file_name = build_workspace_record_path(signal_id)

    _write_workspace_record_local(file_name, record)
    try:
        _write_workspace_record_s3(file_name, record)
    except Exception:
        pass

    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "record": record,
    }


def save_reflection_to_file(payload: SaveReflectionRequest):
    record = {
        "saved_at": datetime.utcnow().isoformat(),

        "source_type": payload.source_type,
        "content_type": payload.content_type,
        "topic": payload.topic,

        "signal_id": payload.signal_id,
        "signal_title": payload.signal_title,

        "selected_model": payload.selected_model,

        "user_input": payload.user_input,
        "ai_response": payload.ai_response,

        "final_reflection": payload.final_reflection,

        "signal_summary": payload.signal_summary,
        "why_it_matters": payload.why_it_matters,
        "relevance_to_projects": payload.relevance_to_projects,
        "relevance_to_career": payload.relevance_to_career,
        "synthesized_insight": payload.synthesized_insight,
        "verification_metadata": payload.verification_metadata,
    }

    return save_workspace_record(record, payload.signal_id)


def save_visual_record_to_workspace(
    payload: GenerateVisualRequest,
    prompt: str,
    saved_visual: dict,
) -> dict:
    record = {
        "saved_at": datetime.utcnow().isoformat(),
        "source_type": "signal",
        "content_type": "visual",
        "topic": None,
        "signal_id": payload.signal_id,
        "signal_title": payload.signal_title,
        "selected_model": GPT_VISUAL_MODEL,
        "user_input": payload.visual_direction,
        "ai_response": prompt,
        "final_reflection": payload.reflection,
        "signal_summary": payload.signal_summary,
        "why_it_matters": payload.why_it_matters,
        "relevance_to_projects": payload.relevance_to_projects,
        "relevance_to_career": payload.relevance_to_career,
        "synthesized_insight": payload.synthesized_insight,
        "image_url": saved_visual["image_url"],
        "image_file_name": saved_visual["image_file_name"],
        "image_metadata_url": saved_visual["metadata_url"],
        "image_metadata_file_name": saved_visual["metadata_file_name"],
        "visual_style": payload.visual_style,
        "visual_direction": payload.visual_direction,
    }
    return save_workspace_record(record, payload.signal_id)


def save_chat_history_to_workspace(payload: SaveChatHistoryRequest) -> dict:
    file_path, file_name = build_chat_history_file_path(payload.signal_id, payload.model)

    messages = [
        {
            "role": item.role,
            "content": item.content,
            "provider_used": item.provider_used,
            "model_used": item.model_used,
            "fallback_used": item.fallback_used,
        }
        for item in payload.messages
        if item.content.strip()
    ]

    last_user = next((item["content"] for item in reversed(messages) if item["role"] == "user"), "")
    last_assistant = next(
        (item["content"] for item in reversed(messages) if item["role"] == "assistant"),
        "",
    )

    record = {
        "saved_at": datetime.utcnow().isoformat(),
        "source_type": "signal",
        "content_type": "chat_conversation",
        "topic": None,
        "signal_id": payload.signal_id,
        "signal_title": payload.signal_title,
        "selected_model": payload.model,
        "user_input": last_user,
        "ai_response": last_assistant,
        "final_reflection": "",
        "signal_summary": payload.signal_summary,
        "why_it_matters": "",
        "relevance_to_projects": "",
        "relevance_to_career": "",
        "synthesized_insight": "",
        "reflection_context": payload.reflection,
        "chat_messages": messages,
        "chat_message_count": len(messages),
    }

    return save_workspace_record(
        record,
        payload.signal_id,
        file_name_override=file_name,
    )


def load_workspace_history():
    records = []

    for file_name in _list_workspace_record_names():
        try:
            data, file_path = _load_workspace_record(file_name)
            if not isinstance(data, dict):
                continue

            records.append({
                "file_name": file_name,
                "saved_at": data.get("saved_at"),
                "source_type": data.get("source_type"),
                "content_type": data.get("content_type"),
                "topic": data.get("topic"),
                "signal_id": data.get("signal_id"),
                "signal_title": data.get("signal_title"),
                "selected_model": data.get("selected_model"),
                "user_input": data.get("user_input"),
                "ai_response": data.get("ai_response"),
                "final_reflection": data.get("final_reflection"),
                "signal_summary": data.get("signal_summary"),
                "why_it_matters": data.get("why_it_matters"),
                "relevance_to_projects": data.get("relevance_to_projects"),
                "relevance_to_career": data.get("relevance_to_career"),
                "synthesized_insight": data.get("synthesized_insight"),
                "chat_messages": data.get("chat_messages"),
                "chat_message_count": data.get("chat_message_count"),
                "reflection_context": data.get("reflection_context"),
                "image_url": data.get("image_url"),
                "image_file_name": data.get("image_file_name"),
                "image_metadata_url": data.get("image_metadata_url"),
                "image_metadata_file_name": data.get("image_metadata_file_name"),
                "visual_style": data.get("visual_style"),
                "visual_direction": data.get("visual_direction"),
            })
        except Exception as e:
            print(f"Failed to read {file_name}: {e}")

    return records


def load_workspace_history_summary():
    records = []

    for file_name in _list_workspace_record_names():
        try:
            data, file_path = _load_workspace_record(file_name)
            if not isinstance(data, dict):
                continue

            records.append(
                {
                    "file_name": file_name,
                    "saved_at": data.get("saved_at"),
                    "source_type": data.get("source_type"),
                    "content_type": data.get("content_type"),
                    "topic": data.get("topic"),
                    "signal_id": data.get("signal_id"),
                    "signal_title": data.get("signal_title"),
                    "signal_summary": data.get("signal_summary"),
                    "final_reflection": data.get("final_reflection"),
                    "relevance_to_career": data.get("relevance_to_career"),
                    "career_takeaway": data.get("career_takeaway"),
                    "career_relevance": data.get("career_relevance"),
                    "reflection": data.get("reflection"),
                    "user_reflection": data.get("user_reflection"),
                    "saved_reflection": data.get("saved_reflection"),
                    "synthesized_insight": data.get("synthesized_insight"),
                    "strategic_insight": data.get("strategic_insight"),
                    "insight": data.get("insight"),
                }
            )
        except Exception as e:
            print(f"Failed to read summary for {file_name}: {e}")

    return records


def load_workspace_item(file_name: str):
    data, file_path = _load_workspace_record(file_name)
    if not isinstance(data, dict):
        return None

    return {
        "file_name": file_path.name,
        "saved_at": data.get("saved_at"),
        "source_type": data.get("source_type"),
        "content_type": data.get("content_type"),
        "topic": data.get("topic"),
        "signal_id": data.get("signal_id"),
        "signal_title": data.get("signal_title"),
        "selected_model": data.get("selected_model"),
        "user_input": data.get("user_input"),
        "ai_response": data.get("ai_response"),
        "final_reflection": data.get("final_reflection"),
        "signal_summary": data.get("signal_summary"),
        "why_it_matters": data.get("why_it_matters"),
        "relevance_to_projects": data.get("relevance_to_projects"),
        "relevance_to_career": data.get("relevance_to_career"),
        "synthesized_insight": data.get("synthesized_insight"),
        "chat_messages": data.get("chat_messages"),
        "chat_message_count": data.get("chat_message_count"),
        "reflection_context": data.get("reflection_context"),
        "image_url": data.get("image_url"),
        "image_file_name": data.get("image_file_name"),
        "image_metadata_url": data.get("image_metadata_url"),
        "image_metadata_file_name": data.get("image_metadata_file_name"),
        "visual_style": data.get("visual_style"),
        "visual_direction": data.get("visual_direction"),
    }

@router.post("/polish_reflection", dependencies=[Depends(require_admin_auth)])
def polish_reflection(payload: ReflectionRequest):
    raw_text = payload.text.strip()

    if not raw_text:
        return {"polished_text": ""}

    try:
        reflection_prompt_policy = decide_execution_policy(
            PolicyInput(
                task_type="reflection_polish",
                query=raw_text,
                user_visible=True,
                importance_score=20,
                requires_traceability=False,
                source_count=0,
            )
        ).selected_policy.to_dict()
        system_prompt, user_prompt = workspace_reflection_polish_prompts(payload, policy=reflection_prompt_policy)

        polished_text, provider_used, fallback_used, policy_metadata = execute_workspace_text_with_policy(
            task_type="reflection_polish",
            query=raw_text,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=800,
            provider_override=PROVIDER_ANTHROPIC,
            user_visible=True,
            importance_score=20,
            requires_traceability=False,
            source_count=0,
        )

        response = {
            "polished_text": polished_text,
            "provider_used": provider_used,
            "fallback_used": bool(fallback_used),
            "policy_metadata": policy_metadata,
            "execution": policy_metadata.get("execution"),
        }
        if payload.persist_pair:
            pair = build_reflection_polish_pair(
                original_text=raw_text,
                polished_text=polished_text,
                provider_used=provider_used,
                fallback_used=bool(fallback_used),
                policy_metadata=policy_metadata,
                execution=policy_metadata.get("execution") or {},
                context={
                    "signal_id": payload.signal_id,
                    "signal_title": payload.signal_title,
                    "signal_summary": payload.signal_summary,
                    "why_it_matters": payload.why_it_matters,
                    "relevance_to_projects": payload.relevance_to_projects,
                    "relevance_to_career": payload.relevance_to_career,
                    "synthesized_insight": payload.synthesized_insight,
                },
            )
            saved_pair = save_reflection_polish_pair(pair)
            response["reflection_polish_pair_id"] = saved_pair["id"]
            response["baseline_eligibility"] = saved_pair["baseline_eligibility"]
        return response

    except Exception as e:
        return {"polished_text": format_workspace_model_error("Claude", e)}


@router.post("/reflection-polish/pairs/{pair_id}/review", dependencies=[Depends(require_admin_auth)])
def review_reflection_polish_pair(pair_id: str, payload: ReflectionPolishReviewRequest, request: Request):
    reviewer_id = (payload.reviewer_id or resolve_request_user_id(request) or "admin_default").strip()
    try:
        review = save_reflection_polish_review(
            pair_id=pair_id,
            outcome=payload.outcome,
            dimension_results=payload.dimension_results,
            reviewer_id=reviewer_id,
            reviewer_note=payload.reviewer_note or "",
            final_reflection_text=payload.final_reflection_text or "",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "message": "Reflection polish review recorded successfully",
        "record": {
            "review_id": review["id"],
            "pair_id": review["pair_id"],
            "outcome": review["outcome"],
            "dimension_results": review["dimension_results"],
        },
    }


@router.get("/reflection-polish/pairs", dependencies=[Depends(require_admin_auth)])
def list_reflection_polish_pair_records(limit: int = 50):
    return {
        "message": "Reflection polish pairs loaded successfully",
        "record": list_reflection_polish_pairs(limit=limit),
    }


@router.get("/reflection-polish/pairs/{pair_id}", dependencies=[Depends(require_admin_auth)])
def get_reflection_polish_pair_record(pair_id: str):
    try:
        detail = get_reflection_polish_pair_detail(pair_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "message": "Reflection polish pair loaded successfully",
        "record": detail,
    }

class ChatContextMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    message: str
    conversation_intent: str | None = "artifact"
    recent_messages: list[ChatContextMessage] | None = None
    signal_title: str | None = None
    signal_summary: str | None = None
    why_it_matters: str | None = None
    relevance_to_projects: str | None = None
    relevance_to_career: str | None = None
    synthesized_insight: str | None = None
    reflection: str | None = None


@router.post("/workspace_chat", dependencies=[Depends(require_admin_auth)])
def workspace_chat(payload: ChatRequest, request: Request):

    user_message = payload.message.strip()
    personal_context = build_analysis_context(resolve_request_user_id(request))
    requested_model = (payload.model or "").strip().lower()
    challenge_mode = (payload.conversation_intent or "").strip().lower() == "discussion"

    if not user_message:
        return {"reply": ""}

    project_repo_context = build_project_repo_snapshot_context()
    recent_discussion_context = build_recent_discussion_context(payload.recent_messages) if challenge_mode else ""

    signal_context = f"""
Personal context:
{personal_context}

Cached project repo context:
{project_repo_context}

Signal context:
Title: {payload.signal_title or ""}
Summary: {payload.signal_summary or ""}
Why it matters: {payload.why_it_matters or ""}
Relevance to projects: {payload.relevance_to_projects or ""}
Relevance to career: {payload.relevance_to_career or ""}
Strategic takeaway: {payload.synthesized_insight or ""}

Current reflection draft:
{payload.reflection or ""}

{recent_discussion_context}

User message:
{user_message}
""".strip()

    if requested_model == "claude":
        try:
            prompt_policy = decide_execution_policy(
                PolicyInput(
                    task_type="workspace_answer",
                    query=user_message,
                    user_visible=True,
                    importance_score=70,
                    requires_traceability=False,
                    source_count=1,
                )
            ).selected_policy.to_dict()
            system_prompt = workspace_chat_system_prompt(
                "claude",
                policy=prompt_policy,
                challenge_mode=challenge_mode,
                conversation_preferences=challenge_mode,
                web_search_enabled=challenge_mode,
            )
            reply, provider_used, fallback_used, policy_metadata = execute_workspace_text_with_policy(
                task_type="workspace_chat",
                query=user_message,
                system_prompt=system_prompt,
                user_prompt=signal_context,
                temperature=0.4,
                max_tokens=3000 if challenge_mode else 1000,
                provider_override=PROVIDER_ANTHROPIC,
                user_visible=True,
                importance_score=70,
                requires_traceability=False,
                source_count=1,
                web_search_enabled=challenge_mode,
            )
            return {
                "reply": reply,
                "provider_used": provider_used,
                "model_used": policy_metadata.get("model_used"),
                "fallback_used": fallback_used,
                "web_search_enabled": policy_metadata.get("web_search_enabled"),
                "web_search_max_uses": policy_metadata.get("web_search_max_uses"),
                "policy_metadata": policy_metadata,
                "execution": policy_metadata.get("execution"),
            }

        except Exception as e:
            return {"reply": format_workspace_model_error("Claude", e)}

    elif requested_model == "chatgpt":
        try:
            prompt_policy = decide_execution_policy(
                PolicyInput(
                    task_type="workspace_answer",
                    query=user_message,
                    user_visible=True,
                    importance_score=70,
                    requires_traceability=False,
                    source_count=1,
                )
            ).selected_policy.to_dict()
            system_prompt = workspace_chat_system_prompt("chatgpt", policy=prompt_policy, challenge_mode=challenge_mode)

            reply, route, policy_metadata = execute_policy_text(
                policy_input=PolicyInput(
                    task_type="workspace_chat",
                    query=user_message,
                    user_visible=True,
                    importance_score=70,
                    requires_traceability=False,
                    source_count=1,
                    metadata={"source_count": 1, "context_label": "workspace_context"},
                ),
                system_prompt=system_prompt,
                user_prompt=signal_context,
                metadata={"source_count": 1, "context_label": "workspace_context"},
                executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_task(
                    task_type=effective_task_type,
                    system_prompt=patched_system_prompt,
                    user_prompt=patched_user_prompt,
                    temperature=0.4,
                    provider_override=PROVIDER_OPENAI,
                    openai_api_key=OPENAI_API_KEY,
                    anthropic_api_key=ANTHROPIC_API_KEY,
                    perplexity_api_key=PERPLEXITY_API_KEY,
                ),
            )
            return {
                "reply": reply,
                "provider_used": route.provider,
                "model_used": route.model,
                "fallback_used": False,
                "policy_metadata": policy_metadata,
                "execution": policy_metadata.get("execution"),
            }

        except Exception as e:
            return {"reply": format_workspace_model_error("ChatGPT", e)}

    elif requested_model == "perplexity":
        try:
            prompt_policy = decide_execution_policy(
                PolicyInput(
                    task_type="workspace_answer",
                    query=user_message,
                    user_visible=True,
                    importance_score=70,
                    requires_traceability=True,
                    source_count=1,
                )
            ).selected_policy.to_dict()
            system_prompt = workspace_chat_system_prompt("perplexity", policy=prompt_policy, challenge_mode=challenge_mode)

            reply, route, policy_metadata = execute_policy_text(
                policy_input=PolicyInput(
                    task_type="workspace_chat",
                    query=user_message,
                    user_visible=True,
                    importance_score=70,
                    requires_traceability=True,
                    source_count=1,
                    metadata={"source_count": 1, "context_label": "workspace_context"},
                ),
                system_prompt=system_prompt,
                user_prompt=signal_context,
                metadata={"source_count": 1, "context_label": "workspace_context"},
                executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_task(
                    task_type=effective_task_type,
                    system_prompt=patched_system_prompt,
                    user_prompt=patched_user_prompt,
                    temperature=0.2,
                    provider_override=PROVIDER_PERPLEXITY,
                    openai_api_key=OPENAI_API_KEY,
                    anthropic_api_key=ANTHROPIC_API_KEY,
                    perplexity_api_key=PERPLEXITY_API_KEY,
                ),
            )
            return {
                "reply": reply,
                "provider_used": route.provider,
                "model_used": route.model,
                "fallback_used": False,
                "policy_metadata": policy_metadata,
                "execution": policy_metadata.get("execution"),
            }

        except Exception as e:
            return {"reply": format_workspace_model_error("Perplexity", e)}

    else:
        return {"reply": f"{payload.model} is not connected yet."}

@router.post("/save_reflection", dependencies=[Depends(require_admin_auth)])
def save_reflection(payload: SaveReflectionRequest):
    final_text = payload.final_reflection.strip()
    is_manual_session = payload.content_type == "manual_session"

    if not final_text and not is_manual_session:
        return {"message": "final_reflection is empty."}

    try:
        saved = save_reflection_to_file(payload)
        return {
            "message": "reflection saved successfully",
            "data": saved
        }
    except Exception as e:
        return {
            "message": f"failed to save reflection: {e}"
        }


@router.post("/workspace_generate_visual", dependencies=[Depends(require_admin_auth)])
def workspace_generate_visual(payload: GenerateVisualRequest):
    if not OPENAI_API_KEY:
        return {"message": "GPT-5.5 visual error: OPENAI_API_KEY not found.", "image_url": None}

    prompt = build_visual_prompt(payload)

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.images.generate(
            model=GPT_VISUAL_MODEL,
            prompt=prompt,
            size="1536x1024",
        )
    except Exception as e:
        return {
            "message": f"GPT-5.5 visual generation failed: {e}",
            "image_url": None,
        }

    for image in getattr(response, "data", []) or []:
        data_b64 = (
            getattr(image, "b64_json", None)
            or getattr(image, "image_base64", None)
            or (image.get("b64_json") if isinstance(image, dict) else None)
            or (image.get("image_base64") if isinstance(image, dict) else None)
        )
        if not data_b64:
            continue

        try:
            image_bytes = base64.b64decode(data_b64)
        except Exception:
            continue

        saved = save_generated_visual(image_bytes, "image/png", prompt, payload)
        workspace_record = save_visual_record_to_workspace(payload, prompt, saved)
        return {
            "message": "GPT-5.5 visual generated successfully.",
            "image_url": saved["image_url"],
            "image_file_name": saved["image_file_name"],
            "metadata_file_name": saved["metadata_file_name"],
            "model": GPT_VISUAL_MODEL,
            "workspace_file_name": workspace_record["file_name"],
        }

    return {
        "message": "GPT-5.5 did not return an image for this request.",
        "image_url": None,
    }


@router.post("/workspace_chat_history", dependencies=[Depends(require_admin_auth)])
def save_workspace_chat_history(payload: SaveChatHistoryRequest):
    try:
        saved = save_chat_history_to_workspace(payload)
        return {
            "message": "workspace chat history saved successfully",
            "file_name": saved["file_name"],
            "message_count": saved["record"].get("chat_message_count", 0),
        }
    except Exception as e:
        return {
            "message": f"failed to save workspace chat history: {e}",
            "file_name": None,
        }


@router.get("/workspace_chat_history/{signal_id}", dependencies=[Depends(require_admin_auth)])
def get_workspace_chat_history(signal_id: str):
    safe_signal_id = (signal_id or "manual").replace("/", "_").replace("\\", "_")

    result: dict[str, dict] = {}

    for model in ("claude", "chatgpt", "perplexity"):
        file_name = f"chat_{safe_signal_id}_{model}.json"
        data, file_path = _load_workspace_record(file_name)
        if not isinstance(data, dict):
            continue

        try:
            result[model] = {
                "file_name": file_path.name,
                "messages": data.get("chat_messages") or [],
                "saved_at": data.get("saved_at"),
                "message_count": data.get("chat_message_count", 0),
            }
        except Exception:
            continue

    return {"signal_id": signal_id, "models": result}


@router.delete("/workspace_chat_history/{signal_id}", dependencies=[Depends(require_admin_auth)])
def delete_workspace_chat_history(signal_id: str, model: str):
    file_path, file_name = build_chat_history_file_path(signal_id, model)
    data, _ = _load_workspace_record(file_name)
    if not file_path.exists() and not isinstance(data, dict):
        return {"message": "workspace chat history not found", "file_name": file_name}

    if file_path.exists():
        file_path.unlink()
    _delete_workspace_record_s3(file_name)
    return {"message": "workspace chat history deleted successfully", "file_name": file_name}


@router.get("/workspace_visuals/{file_name}")
def get_workspace_visual(file_name: str):
    file_path = _ensure_workspace_visual_local(file_name)
    if not file_path.exists():
        return {"message": "workspace visual not found"}
    return FileResponse(file_path, media_type=_guess_workspace_visual_content_type(file_name))


@router.get("/workspace_history", dependencies=[Depends(require_admin_auth)])
def get_workspace_history():
    try:
        items = load_workspace_history()
        return {"items": items}
    except Exception as e:
        return {"items": [], "message": f"failed to load workspace history: {e}"}


@router.get("/workspace_history/summary", dependencies=[Depends(require_admin_auth)])
def get_workspace_history_summary():
    try:
        items = load_workspace_history_summary()
        return {"items": items}
    except Exception as e:
        return {"items": [], "message": f"failed to load workspace history summary: {e}"}

@router.get("/workspace_history/{file_name}", dependencies=[Depends(require_admin_auth)])
def get_workspace_item(file_name: str):
    try:
        item = load_workspace_item(file_name)
        if not item:
            return {"message": "workspace item not found", "item": None}
        return {"item": item}
    except Exception as e:
        return {"message": f"failed to load workspace item: {e}", "item": None}
    
@router.delete("/workspace_history/{file_name}", dependencies=[Depends(require_admin_auth)])
def delete_workspace_item(file_name: str):
    try:
        data, file_path = _load_workspace_record(file_name)
        if not file_path.exists() and not isinstance(data, dict):
            return {"message": "workspace item not found"}

        if not isinstance(data, dict):
            data = {}

        for related_name in [
            data.get("image_file_name"),
            data.get("image_metadata_file_name"),
        ]:
            if not related_name:
                continue
            related_path = _workspace_visual_local_path(str(related_name))
            if related_path.exists():
                related_path.unlink()
            _delete_workspace_visual_s3(str(related_name))

        if file_path.exists():
            file_path.unlink()
        _delete_workspace_record_s3(file_name)

        return {"message": "workspace item deleted successfully"}
    except Exception as e:
        return {"message": f"failed to delete workspace item: {e}"}
