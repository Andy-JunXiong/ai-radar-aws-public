from typing import Annotated, List

from app.services.llm_json_service import (
    parse_model_json as shared_parse_model_json,
    repair_output_to_json_with_openai as shared_repair_output_to_json_with_openai,
)
from app.services.llm_executor_service import execute_text_json_task
from app.services.llm_executor_service import execute_vision_json_task
from app.services.model_router_service import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    route_task,
)
from app.services.manual_storage import mark_session_analysis_failed
from app.services.manual_link_fetch_service import fetch_public_article
from app.services.manual_source_link_service import apply_manual_source_url_metadata
from app.services.manual_source_link_service import extract_manual_source_urls
from app.services.request_identity import resolve_request_user_id
from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import json
import uuid
import base64
import boto3

from app.services.context_bridge import build_analysis_context, get_context_scope
from app.services.admin_guard import require_admin_auth
from app.services.execution_policy_service import PolicyInput
from app.services.execution_policy_service import decide_execution_policy
from app.services.fallback_policy_service import execute_policy_text_json, execute_policy_vision_json
from app.prompts.registry import (
    manual_image_analysis_prompt,
    manual_single_text_user_prompt,
    manual_text_analysis_prompt,
    manual_text_session_user_prompt,
)

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

# The repo root `.env` is the canonical local config source.
# Use override=True so stale shell vars or legacy backend/.env-loaded values
# do not silently win over the root file during local development.
load_dotenv(ROOT_ENV_PATH, override=True)

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "manual_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_DIR = UPLOAD_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_INDEX_PATH = SESSIONS_DIR / "index.json"
INPUT_TEXT_RAW_OUTPUT_SCHEMA_VERSION = "input_text_analysis_raw_output_v1"

AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET")
MANUAL_SESSIONS_S3_PREFIX = (
    os.getenv("MANUAL_SESSIONS_S3_PREFIX")
    or os.getenv("MANUAL_UPLOADS_S3_PREFIX")
    or "manual/sessions"
).strip("/ ")
MANUAL_FILES_S3_PREFIX = (
    os.getenv("MANUAL_FILES_S3_PREFIX")
    or "manual/uploads/files"
).strip("/ ")

TEXT_EXTENSIONS = {".txt", ".md", ".json"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MANUAL_SESSION_SCHEMA_VERSION = 2
MAX_MANUAL_PREVIEW_CHARS = 12000
PDF_PREVIEW_PENDING_MESSAGE = (
    "[PDF uploaded successfully. Text preview will be generated during analysis.]"
)
PDF_PREVIEW_EMPTY_MESSAGE = (
    "[PDF uploaded successfully, but no extractable text preview was found. "
    "The file may be scanned or image-only.]"
)
COGNITIVE_LAYER_VALUES = {"L1", "L2", "L3", "unclassified"}
SOURCE_LIMITS_NOT_APPLICABLE = "limits_not_applicable"
IMAGE_MEDIA_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _manual_provider_fallback_enabled() -> bool:
    value = str(os.getenv("ENABLE_MANUAL_PROVIDER_FALLBACK", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _manual_sessions_prefer_s3_reads() -> bool:
    value = str(os.getenv("MANUAL_SESSIONS_PREFER_S3_READS", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def get_file_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()

    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def get_image_media_type(file_path: Path) -> str:
    return IMAGE_MEDIA_TYPE_MAP.get(file_path.suffix.lower(), "image/jpeg")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_input_text_raw_output_record(
    raw_output: str,
    *,
    task_type: str,
    route,
    fallback_used: bool,
    source_count: int,
) -> dict:
    raw_text = raw_output or ""
    return {
        "schema_version": INPUT_TEXT_RAW_OUTPUT_SCHEMA_VERSION,
        "skill_name": "input-text-analyze",
        "skill_version": "v1",
        "task_type": task_type,
        "capture_stage": "before_parse",
        "storage_scope": "manual_session_detail_only",
        "contains_system_prompt": False,
        "contains_user_prompt": False,
        "captured_at": utc_now_iso(),
        "provider": getattr(route, "provider", ""),
        "model": getattr(route, "model", ""),
        "fallback_used": fallback_used,
        "source_count": source_count,
        "raw_output_char_count": len(raw_text),
        "raw_output_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "raw_output": raw_text,
    }


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _sessions_index_s3_key() -> str:
    return f"{MANUAL_SESSIONS_S3_PREFIX}/index.json"


def _session_s3_key(session_id: str) -> str:
    safe_session_id = str(session_id).replace("/", "_").replace("\\", "_")
    return f"{MANUAL_SESSIONS_S3_PREFIX}/{safe_session_id}.json"


def _manual_file_s3_key(stored_filename: str) -> str:
    safe_name = str(stored_filename).replace("/", "_").replace("\\", "_")
    return f"{MANUAL_FILES_S3_PREFIX}/{safe_name}"


def _read_s3_json(key: str):
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _write_s3_json(key: str, payload) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def _guess_upload_content_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".json":
        return "application/json"
    if ext == ".md":
        return "text/markdown; charset=utf-8"
    if ext == ".txt":
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def _write_s3_file(key: str, content: bytes, content_type: str) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=content_type,
    )


def _read_s3_file(key: str) -> tuple[bytes | None, str | None]:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None, None
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
        body = response["Body"].read()
        return body, response.get("ContentType")
    except Exception:
        return None, None


def ensure_uploaded_file_local(stored_filename: str) -> Path:
    file_path = UPLOAD_DIR / stored_filename
    if file_path.exists():
        return file_path

    content, _ = _read_s3_file(_manual_file_s3_key(stored_filename))
    if content is not None:
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)
        except Exception:
            pass

    return file_path


def resolve_analysis_context(
    *,
    user_id: str | None = None,
    analysis_context_override: str | None = None,
    analysis_context_source_override: str | None = None,
) -> tuple[str, str]:
    if analysis_context_override is not None:
        return (
            analysis_context_override,
            analysis_context_source_override or "user_provided",
        )

    analysis_context = build_analysis_context(user_id)
    if get_context_scope(user_id) == "user_specific":
        return analysis_context, "auto_generated"

    return analysis_context, "personal_context_default"


def build_image_analysis_prompt(*, is_session: bool, user_id: str | None = None) -> str:
    analysis_context, _ = resolve_analysis_context(user_id=user_id)
    prompt_policy = decide_execution_policy(
        PolicyInput(
            task_type="manual_analysis",
            user_visible=True,
            importance_score=80 if is_session else 75,
            requires_traceability=is_session,
            source_count=2 if is_session else 1,
        )
    ).selected_policy.to_dict()
    return manual_image_analysis_prompt(
        is_session=is_session,
        analysis_context=analysis_context,
        policy=prompt_policy,
    )


def build_text_analysis_prompt(*, is_session: bool, user_id: str | None = None) -> str:
    analysis_context = build_analysis_context(user_id)
    prompt_policy = decide_execution_policy(
        PolicyInput(
            task_type="manual_analysis",
            user_visible=True,
            importance_score=80 if is_session else 75,
            requires_traceability=is_session,
            source_count=2 if is_session else 1,
        )
    ).selected_policy.to_dict()
    return manual_text_analysis_prompt(
        is_session=is_session,
        analysis_context=analysis_context,
        policy=prompt_policy,
    )


def ensure_sessions_index() -> None:
    if not SESSIONS_INDEX_PATH.exists():
        SESSIONS_INDEX_PATH.write_text("[]", encoding="utf-8")


def load_sessions_index() -> List[dict]:
    ensure_sessions_index()
    prefer_s3 = _manual_sessions_prefer_s3_reads()

    if not prefer_s3:
        try:
            data = json.loads(SESSIONS_INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    s3_payload = _read_s3_json(_sessions_index_s3_key())
    if isinstance(s3_payload, list):
        SESSIONS_INDEX_PATH.write_text(
            json.dumps(s3_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return s3_payload

    if prefer_s3:
        try:
            data = json.loads(SESSIONS_INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    return []


def save_sessions_index(items: List[dict]) -> None:
    SESSIONS_INDEX_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        _write_s3_json(_sessions_index_s3_key(), items)
    except Exception:
        pass


def get_session_file_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def save_session_detail(session_data: dict) -> None:
    session_id = session_data["session_id"]
    session_file = get_session_file_path(session_id)
    session_file.write_text(
        json.dumps(session_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        _write_s3_json(_session_s3_key(session_id), session_data)
    except Exception:
        pass


def load_session_detail(session_id: str) -> dict | None:
    session_file = get_session_file_path(session_id)
    prefer_s3 = _manual_sessions_prefer_s3_reads()

    if not prefer_s3 and session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    s3_payload = _read_s3_json(_session_s3_key(session_id))
    if isinstance(s3_payload, dict):
        session_file.write_text(
            json.dumps(s3_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return s3_payload

    if not session_file.exists():
        return None

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None

    return None


def enrich_session_summaries(index_items: List[dict]) -> List[dict]:
    enriched: List[dict] = []

    for item in index_items:
        session_id = item.get("session_id")
        if not session_id:
            enriched.append(item)
            continue

        session_data = load_session_detail(str(session_id))
        if not session_data:
            enriched.append(item)
            continue

        session_data = enrich_manual_pdf_previews(session_data)
        merged = dict(item)
        rebuilt = build_session_summary(session_data)

        for key, value in rebuilt.items():
            if value not in (None, "", [], {}):
                merged[key] = value

        enriched.append(merged)

    return enriched


def upsert_session_index_item(session_summary: dict) -> None:
    index_items = load_sessions_index()

    existing_index = None
    for i, item in enumerate(index_items):
        if item.get("session_id") == session_summary.get("session_id"):
            existing_index = i
            break

    if existing_index is not None:
        index_items[existing_index] = session_summary
    else:
        index_items.insert(0, session_summary)

    index_items.sort(
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )
    save_sessions_index(index_items)


def build_session_summary(session_data: dict) -> dict:
    files = session_data.get("files", [])
    file_types = sorted(list({f.get("file_kind", "unknown") for f in files}))
    analysis = session_data.get("analysis") or {}

    summary = ""
    why_it_matters = ""
    relevance_to_projects = ""
    relevance_to_career = ""
    synthesized_insight = ""
    topic = None

    if isinstance(analysis, dict):
        summary = analysis.get("summary") or ""
        why_it_matters = analysis.get("why_it_matters") or ""
        relevance_to_projects = analysis.get("relevance_to_projects") or ""
        relevance_to_career = analysis.get("relevance_to_career") or ""
        synthesized_insight = analysis.get("synthesized_insight") or ""
        topic = analysis.get("topic")

    return {
        "session_id": session_data.get("session_id"),
        "title": session_data.get("title"),
        "created_at": session_data.get("created_at"),
        "updated_at": session_data.get("updated_at"),
        "status": session_data.get("status", "pending"),
        "saved_reason": session_data.get("saved_reason"),
        "file_count": len(files),
        "file_types": file_types,
        "analysis_status": session_data.get("analysis_status", "not_started"),
        "upload_reason": session_data.get("upload_reason", ""),
        "intended_use": session_data.get("intended_use", ""),
        "cognitive_layer": session_data.get("cognitive_layer", "unclassified"),
        "source_stated_limits": session_data.get("source_stated_limits", ""),
        "source_stated_confidence": session_data.get("source_stated_confidence"),
        "source_stated_limits_not_applicable": bool(
            session_data.get("source_stated_limits_not_applicable")
        ),
        "source_stated_limits_status": session_data.get("source_stated_limits_status", ""),
        "workspace_saved": session_data.get("workspace_saved", False),
        "completion_saved": session_data.get("completion_saved", False),
        "source_url": session_data.get("source_url", ""),
        "source_urls": session_data.get("source_urls", []),
        "url": session_data.get("url", ""),
        "link": session_data.get("link", ""),
        "topic": topic,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "relevance_to_projects": relevance_to_projects,
        "relevance_to_career": relevance_to_career,
        "synthesized_insight": synthesized_insight,
        "provider_used": session_data.get("provider_used"),
        "model_used": session_data.get("model_used"),
        "generation_mode": session_data.get("generation_mode"),
        "requested_provider": session_data.get("requested_provider"),
        "verification": session_data.get("verification"),
        "policy_metadata": session_data.get("policy_metadata"),
        "evidence_pack": session_data.get("evidence_pack"),
        "workspace_file_name": session_data.get("workspace_file_name"),
        "workspace_saved_at": session_data.get("workspace_saved_at"),
        "files": files,
    }


def normalize_manual_upload_metadata(
    *,
    upload_reason: str | None = None,
    intended_use: str | None = None,
    cognitive_layer: str | None = None,
    source_stated_limits: str | None = None,
    source_stated_confidence: str | None = None,
    source_stated_limits_not_applicable: bool | str | None = None,
) -> dict:
    normalized_layer = (cognitive_layer or "unclassified").strip()
    if normalized_layer not in COGNITIVE_LAYER_VALUES:
        normalized_layer = "unclassified"
    limits_text = (source_stated_limits or "").strip()
    confidence_text = (source_stated_confidence or "").strip()
    limits_not_applicable = False
    if isinstance(source_stated_limits_not_applicable, bool):
        limits_not_applicable = source_stated_limits_not_applicable
    elif isinstance(source_stated_limits_not_applicable, str):
        limits_not_applicable = source_stated_limits_not_applicable.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    metadata = {
        "upload_reason": (upload_reason or "").strip(),
        "intended_use": (intended_use or "").strip(),
        "cognitive_layer": normalized_layer,
    }
    if limits_text:
        metadata["source_stated_limits"] = limits_text
    if confidence_text:
        metadata["source_stated_confidence"] = {
            "raw_text": confidence_text,
            "normalized_label": None,
        }
    if limits_not_applicable:
        metadata["source_stated_limits_not_applicable"] = True
        metadata["source_stated_limits_status"] = SOURCE_LIMITS_NOT_APPLICABLE
    return metadata


def create_manual_session(
    files: List[dict],
    user_id: str | None = None,
    upload_reason: str | None = None,
    intended_use: str | None = None,
    cognitive_layer: str | None = None,
    source_stated_limits: str | None = None,
    source_stated_confidence: str | None = None,
    source_stated_limits_not_applicable: bool | str | None = None,
) -> dict:
    session_id = uuid.uuid4().hex
    now = utc_now_iso()
    analysis_context, analysis_context_source = resolve_analysis_context(user_id=user_id)
    upload_metadata = normalize_manual_upload_metadata(
        upload_reason=upload_reason,
        intended_use=intended_use,
        cognitive_layer=cognitive_layer,
        source_stated_limits=source_stated_limits,
        source_stated_confidence=source_stated_confidence,
        source_stated_limits_not_applicable=source_stated_limits_not_applicable,
    )

    if len(files) == 1:
        title = files[0].get("original_filename", "Manual Session")
    else:
        title = f"Manual Session ({len(files)} files)"

    session_data = {
        "session_id": session_id,
        "session_schema_version": MANUAL_SESSION_SCHEMA_VERSION,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "status": "pending",
        "saved_reason": None,
        "analysis_status": "not_started",
        "analysis_context": analysis_context,
        "analysis_context_source": analysis_context_source,
        **upload_metadata,
        "workspace_saved": False,
        "analysis": None,
        "files": files,
    }
    apply_manual_source_url_metadata(session_data)

    save_session_detail(session_data)
    upsert_session_index_item(build_session_summary(session_data))
    return session_data


def update_session_analysis(session_id: str, analysis: dict) -> None:
    session_data = load_session_detail(session_id)
    if not session_data:
        return

    session_data["analysis"] = analysis
    session_data["analysis_status"] = "completed"
    if session_data.get("status") != "completed":
        session_data["status"] = "analyzed"
        session_data["saved_reason"] = None
    session_data["updated_at"] = utc_now_iso()

    save_session_detail(session_data)
    upsert_session_index_item(build_session_summary(session_data))

def save_manual_analysis_to_workspace(
    session_data: dict,
    analysis: dict,
    provider_used: str | None = None,
) -> dict:
    workspace_dir = Path(__file__).resolve().parents[2] / "data" / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    session_id = session_data.get("session_id", "manual")
    safe_session_id = str(session_id).replace("/", "_").replace("\\", "_")

    file_name = f"{timestamp}_manual_{safe_session_id}.json"
    file_path = workspace_dir / file_name

    record = {
        "saved_at": datetime.utcnow().isoformat(),
        "source_type": "manual",
        "content_type": "manual_session",
        "topic": analysis.get("topic"),
        "signal_id": f"manual_{safe_session_id}",
        "signal_title": session_data.get("title"),
        "selected_model": provider_used,
        "user_input": None,
        "ai_response": None,
        "final_reflection": "",
        "signal_summary": analysis.get("summary", ""),
        "why_it_matters": analysis.get("why_it_matters"),
        "relevance_to_projects": analysis.get("relevance_to_projects"),
        "relevance_to_career": analysis.get("relevance_to_career"),
        "synthesized_insight": analysis.get("synthesized_insight"),
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "record": record,
    }

def extract_text_from_file(file_path: Path) -> str:
    ext = file_path.suffix.lower()

    if ext in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if ext == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = []

        for page in reader.pages:
            text = page.extract_text() or ""
            text = text.encode("utf-8", errors="ignore").decode(
                "utf-8", errors="ignore"
            )
            pages.append(text)

        return "\n\n".join(pages)

    return ""


def build_manual_file_preview_text(file_path: Path, file_kind: str) -> str:
    normalized_kind = str(file_kind or "").lower()
    if normalized_kind not in {"text", "pdf"}:
        return ""

    text = extract_text_from_file(file_path).strip()
    if text:
        return text[:MAX_MANUAL_PREVIEW_CHARS]

    if normalized_kind == "pdf":
        return PDF_PREVIEW_EMPTY_MESSAGE

    return ""


def _pdf_preview_needs_extraction(preview_text: str) -> bool:
    preview = str(preview_text or "").strip()
    return not preview or preview == PDF_PREVIEW_PENDING_MESSAGE


def enrich_manual_pdf_previews(session_data: dict) -> dict:
    files = session_data.get("files")
    if not isinstance(files, list):
        return session_data

    enriched_files = []
    changed = False
    for file_info in files:
        if not isinstance(file_info, dict):
            enriched_files.append(file_info)
            continue

        item = dict(file_info)
        if str(item.get("file_kind") or "").lower() == "pdf" and _pdf_preview_needs_extraction(
            str(item.get("preview_text") or "")
        ):
            stored_filename = str(item.get("stored_filename") or "").strip()
            if stored_filename:
                try:
                    file_path = ensure_uploaded_file_local(stored_filename)
                    if file_path.exists():
                        item["preview_text"] = build_manual_file_preview_text(
                            file_path,
                            "pdf",
                        )
                        changed = True
                except Exception as exc:
                    item["preview_text"] = f"[PDF preview extraction failed: {exc}]"
                    changed = True

        enriched_files.append(item)

    if not changed:
        return session_data

    enriched = dict(session_data)
    enriched["files"] = enriched_files
    return enriched


def build_manual_link_article_content(
    *,
    original_text: str,
    source_url: str,
    article_result: dict,
) -> str:
    status = article_result.get("status") or "failed"
    title = article_result.get("title") or ""
    resolved_url = article_result.get("resolved_url") or source_url
    error = article_result.get("error") or ""
    article_text = article_result.get("text") or ""

    metadata_lines = [
        "# Manual Link Source",
        "",
        f"Source URL: {source_url}",
        f"Fetch status: {status}",
    ]
    if resolved_url and resolved_url != source_url:
        metadata_lines.append(f"Fetched URL: {resolved_url}")
    if title:
        metadata_lines.append(f"Fetched title: {title}")
    if error:
        metadata_lines.append(f"Fetch note: {error}")

    if status == "fetched":
        metadata_lines.extend(
            [
                "",
                "AI Radar fetched the public article text below for manual analysis.",
                "",
                "## Reviewer Context",
                "",
                original_text.strip(),
                "",
                "## Fetched Article Text",
                "",
                article_text.strip(),
            ]
        )
    else:
        metadata_lines.extend(
            [
                "",
                "AI Radar saved the source URL, but could not fetch enough public article text for analysis.",
                "Analyze Session will use the reviewer-provided context below unless another text/PDF file is included.",
                "",
                "## Reviewer Context",
                "",
                original_text.strip(),
            ]
        )

    return "\n".join(line for line in metadata_lines if line is not None).strip() + "\n"


def enrich_manual_link_file_with_article(
    *,
    file_path: Path,
    preview_text: str,
    original_filename: str,
) -> dict:
    if original_filename != "manual-link-source.md":
        return {"preview_text": preview_text}

    urls = extract_manual_source_urls([{"preview_text": preview_text}])
    if not urls:
        return {"preview_text": preview_text}

    source_url = urls[0]
    article_result = fetch_public_article(source_url)
    article_content = build_manual_link_article_content(
        original_text=preview_text,
        source_url=source_url,
        article_result=article_result,
    )
    file_path.write_text(article_content, encoding="utf-8")

    status = article_result.get("status") or "failed"
    title = article_result.get("title") or ""
    error = article_result.get("error") or ""
    article_text = article_result.get("text") or ""

    message = "file uploaded successfully"
    if status == "fetched":
        message = "file uploaded successfully; linked article fetched for analysis"
    elif original_filename == "manual-link-source.md":
        message = "file uploaded successfully; linked article could not be fetched"

    return {
        "message": message,
        "preview_text": article_content[:12000],
        "source_url": source_url,
        "fetched_url": article_result.get("resolved_url") or "",
        "article_fetch_status": status,
        "article_title": title,
        "article_excerpt": article_text[:500],
        "article_text_char_count": len(article_text),
        "article_fetch_error": error,
    }

def is_provider_overloaded_error(error: Exception) -> bool:
    text = str(error)
    return (
        "overloaded_error" in text
        or "Overloaded" in text
        or "529" in text
        or "rate limit" in text.lower()
        or "timeout" in text.lower()
    )


def is_provider_model_not_found_error(error: Exception) -> bool:
    text = str(error)
    lowered = text.lower()
    return (
        "not_found_error" in lowered
        or "model:" in lowered
        or "model not found" in lowered
    )


def is_provider_authentication_error(error: Exception) -> bool:
    text = str(error)
    lowered = text.lower()
    return (
        "authentication_error" in lowered
        or "invalid x-api-key" in lowered
        or "invalid_api_key" in lowered
        or "incorrect api key provided" in lowered
        or ("401" in lowered and "api key" in lowered)
        or ("401" in lowered and "anthropic" in lowered)
        or ("401" in lowered and "openai" in lowered)
    )


def parse_model_json(raw_output: str):
    return shared_parse_model_json(
        raw_output,
        repair_with_openai=True,
        schema_keys=[
            "summary",
            "why_it_matters",
            "relevance_to_projects",
            "relevance_to_career",
            "synthesized_insight",
        ],
    )


def repair_output_to_json_with_openai(raw_text: str):
    return shared_repair_output_to_json_with_openai(
        raw_text,
        schema_keys=[
            "summary",
            "why_it_matters",
            "relevance_to_projects",
            "relevance_to_career",
            "synthesized_insight",
        ],
    )


def _analyze_with_routed_text_json(
    system_prompt: str,
    user_prompt: str,
    *,
    task_type: str,
    source_count: int = 0,
    source_labels: list[str] | None = None,
    provider_override: str | None = None,
    fallback_used: bool = False,
    capture_raw_output: bool = False,
):
    raw_output_records: list[dict] = []
    policy_metadata_input = {
        "source_count": source_count,
        "source_labels": source_labels or [],
        "context_label": "manual_upload_session" if task_type.endswith("_session") else "manual_upload",
    }

    def capture_raw_output_record(raw_output: str, route) -> None:
        raw_output_records.append(
            build_input_text_raw_output_record(
                raw_output,
                task_type=task_type,
                route=route,
                fallback_used=fallback_used,
                source_count=source_count,
            )
        )

    analysis, route, policy_metadata = execute_policy_text_json(
        policy_input=PolicyInput(
            task_type=task_type,
            user_visible=True,
            importance_score=75,
            requires_traceability=task_type.endswith("_session"),
            source_count=source_count,
            metadata=policy_metadata_input,
        ),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata=policy_metadata_input,
        executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_json_task(
            task_type=effective_task_type,
            system_prompt=patched_system_prompt,
            user_prompt=patched_user_prompt,
            temperature=0.3,
            provider_override=provider_override,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            fallback_used=fallback_used,
            raw_output_callback=capture_raw_output_record if capture_raw_output else None,
        ),
    )
    if capture_raw_output and raw_output_records:
        policy_metadata = {
            **(policy_metadata or {}),
            "input_text_analysis_raw_output": raw_output_records[-1],
        }
    return analysis, route, policy_metadata


def build_text_session_prompt_for_claude(files: List[dict], user_id: str | None = None) -> str:
    combined_sections = []
    for file_info in files:
        file_path = ensure_uploaded_file_local(file_info["stored_filename"])
        text = extract_text_from_file(file_path).strip()
        if text:
            combined_sections.append(
                f"Filename: {file_info['original_filename']}\n\n{text[:6000]}"
            )

    if not combined_sections:
        raise ValueError("No extractable text found in the uploaded session.")

    combined_text = "\n\n---\n\n".join(combined_sections)
    return f"""
        {build_text_analysis_prompt(is_session=True, user_id=user_id)}

Uploaded session content:
{combined_text[:18000]}

Return valid JSON only.
""".strip()


def _build_text_session_messages(
    files: List[dict],
    user_id: str | None = None,
) -> tuple[str, str]:
    combined_sections = []
    for file_info in files:
        file_path = ensure_uploaded_file_local(file_info["stored_filename"])
        text = extract_text_from_file(file_path).strip()
        if text:
            combined_sections.append(
                f"Filename: {file_info['original_filename']}\n\n{text[:6000]}"
            )

    if not combined_sections:
        raise ValueError("No extractable text found in the uploaded session.")

    combined_text = "\n\n---\n\n".join(combined_sections)
    system_prompt = build_text_analysis_prompt(is_session=True, user_id=user_id)
    user_prompt = manual_text_session_user_prompt(combined_text)
    return system_prompt, user_prompt


def _build_image_attachments(files: List[dict]) -> list[dict[str, str]]:
    attachments = []
    for file_info in files:
        file_path = ensure_uploaded_file_local(file_info["stored_filename"])
        attachments.append(
            {
                "filename": file_info["original_filename"],
                "media_type": get_image_media_type(file_path),
                "image_b64": base64.b64encode(file_path.read_bytes()).decode("utf-8"),
            }
        )
    return attachments


def analyze_text_with_openai(filename: str, text: str, user_id: str | None = None):
    system_prompt = build_text_analysis_prompt(is_session=False, user_id=user_id)
    user_prompt = manual_single_text_user_prompt(filename, text)

    analysis, _, _ = _analyze_with_routed_text_json(
        system_prompt,
        user_prompt,
        task_type="manual_text",
        source_count=1,
        source_labels=[filename],
        provider_override=PROVIDER_OPENAI,
    )
    return analysis


def analyze_text_with_routed_llm(filename: str, text: str, user_id: str | None = None):
    system_prompt = build_text_analysis_prompt(is_session=False, user_id=user_id)
    user_prompt = manual_single_text_user_prompt(filename, text)

    return _analyze_with_routed_text_json(
        system_prompt,
        user_prompt,
        task_type="manual_text",
        source_count=1,
        source_labels=[filename],
    )


def analyze_image_with_claude(filename: str, file_path: Path, user_id: str | None = None):
    media_type = get_image_media_type(file_path)
    image_bytes = file_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    analysis, _ = execute_vision_json_task(
        task_type="manual_image",
        prompt_text=f"Filename: {filename}\n\n{build_image_analysis_prompt(is_session=False, user_id=user_id)}",
        attachments=[
            {
                "filename": filename,
                "media_type": media_type,
                "image_b64": image_b64,
            }
        ],
        max_tokens=1200,
        provider_override=PROVIDER_ANTHROPIC,
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
    )
    return analysis


def analyze_image_with_routed_llm(filename: str, file_path: Path, user_id: str | None = None):
    media_type = get_image_media_type(file_path)
    image_bytes = file_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return execute_policy_vision_json(
        policy_input=PolicyInput(
            task_type="manual_image",
            user_visible=True,
            importance_score=75,
            requires_traceability=False,
            source_count=1,
            metadata={"source_count": 1, "context_label": "manual_image"},
        ),
        prompt_text=f"Filename: {filename}\n\n{build_image_analysis_prompt(is_session=False, user_id=user_id)}",
        metadata={"source_count": 1, "context_label": "manual_image"},
        executor=lambda effective_task_type, patched_prompt: execute_vision_json_task(
            task_type=effective_task_type,
            prompt_text=patched_prompt,
            attachments=[
                {
                    "filename": filename,
                    "media_type": media_type,
                    "image_b64": image_b64,
                }
            ],
            max_tokens=1200,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
        ),
    )


def analyze_image_session_with_claude(files: List[dict], user_id: str | None = None):
    analysis, _ = execute_vision_json_task(
        task_type="manual_image_session",
        prompt_text=build_image_analysis_prompt(is_session=True, user_id=user_id),
        attachments=_build_image_attachments(files),
        max_tokens=1800,
        provider_override=PROVIDER_ANTHROPIC,
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
    )
    return analysis


def analyze_image_session_with_openai(files: List[dict], user_id: str | None = None):
    analysis, _ = execute_vision_json_task(
        task_type="manual_image_session",
        prompt_text=build_image_analysis_prompt(is_session=True, user_id=user_id),
        attachments=_build_image_attachments(files),
        max_tokens=1800,
        provider_override=PROVIDER_OPENAI,
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
    )
    return analysis


def analyze_image_session_with_routed_llm(files: List[dict], user_id: str | None = None):
    attachments = _build_image_attachments(files)
    return execute_policy_vision_json(
        policy_input=PolicyInput(
            task_type="manual_image_session",
            user_visible=True,
            importance_score=80,
            requires_traceability=True,
            source_count=len(files),
            metadata={"source_count": len(files), "context_label": "manual_image_session"},
        ),
        prompt_text=build_image_analysis_prompt(is_session=True, user_id=user_id),
        metadata={"source_count": len(files), "context_label": "manual_image_session"},
        executor=lambda effective_task_type, patched_prompt: execute_vision_json_task(
            task_type=effective_task_type,
            prompt_text=patched_prompt,
            attachments=attachments,
            max_tokens=1800,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
        ),
    )


def analyze_text_session_with_openai(files: List[dict], user_id: str | None = None):
    system_prompt, user_prompt = _build_text_session_messages(files, user_id=user_id)
    analysis, _, _ = _analyze_with_routed_text_json(
        system_prompt,
        user_prompt,
        task_type="manual_text_session",
        source_count=len(files),
        source_labels=[item.get("original_filename", "") for item in files],
        provider_override=PROVIDER_OPENAI,
        capture_raw_output=True,
    )
    return analysis


@router.post("/manual/upload", dependencies=[Depends(require_admin_auth)])
async def upload_manual_file(
    request: Request,
    files: Annotated[List[UploadFile], File(description="Upload one or more files")],
    upload_reason: Annotated[str, Form()] = "",
    intended_use: Annotated[str, Form()] = "",
    cognitive_layer: Annotated[str, Form()] = "unclassified",
    source_stated_limits: Annotated[str, Form()] = "",
    source_stated_confidence: Annotated[str, Form()] = "",
    source_stated_limits_not_applicable: Annotated[bool, Form()] = False,
):
    try:
        user_id = resolve_request_user_id(request)
        results = []

        for file in files:
            original_filename = file.filename or "uploaded_file"
            file_kind = get_file_kind(original_filename)

            if file_kind == "unknown":
                results.append(
                    {
                        "message": "Unsupported file type. Please upload txt, md, json, pdf, png, jpg, jpeg, or webp.",
                        "stored_filename": "",
                        "original_filename": original_filename,
                        "file_kind": "unknown",
                        "preview_text": "",
                    }
                )
                continue

            ext = Path(original_filename).suffix.lower()
            stored_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = UPLOAD_DIR / stored_filename

            content = await file.read()
            file_path.write_bytes(content)
            try:
                _write_s3_file(
                    _manual_file_s3_key(stored_filename),
                    content,
                    _guess_upload_content_type(original_filename),
                )
            except Exception:
                pass

            preview_text = ""
            file_metadata: dict = {
                "message": "file uploaded successfully",
            }

            if file_kind == "text":
                try:
                    preview_text = build_manual_file_preview_text(file_path, file_kind)
                    article_metadata = enrich_manual_link_file_with_article(
                        file_path=file_path,
                        preview_text=preview_text,
                        original_filename=original_filename,
                    )
                    file_metadata.update(article_metadata)
                    preview_text = file_metadata.get("preview_text", preview_text)
                    try:
                        refreshed_content = file_path.read_bytes()
                        _write_s3_file(
                            _manual_file_s3_key(stored_filename),
                            refreshed_content,
                            _guess_upload_content_type(original_filename),
                        )
                    except Exception:
                        pass
                except Exception as e:
                    preview_text = f"[Preview extraction failed: {e}]"

            elif file_kind == "pdf":
                try:
                    preview_text = build_manual_file_preview_text(file_path, file_kind)
                except Exception as e:
                    preview_text = f"[PDF preview extraction failed: {e}]"

            elif file_kind == "image":
                preview_text = ""

            results.append(
                {
                    **file_metadata,
                    "stored_filename": stored_filename,
                    "original_filename": original_filename,
                    "file_kind": file_kind,
                    "preview_text": preview_text,
                }
            )

        valid_results = [item for item in results if item.get("stored_filename")]

        session_data = None
        if valid_results:
            session_data = create_manual_session(
                valid_results,
                user_id=user_id,
                upload_reason=upload_reason,
                intended_use=intended_use,
                cognitive_layer=cognitive_layer,
                source_stated_limits=source_stated_limits,
                source_stated_confidence=source_stated_confidence,
                source_stated_limits_not_applicable=source_stated_limits_not_applicable,
            )

        return {
            "message": "files uploaded successfully",
            "session_id": session_data["session_id"] if session_data else None,
            "files": results,
        }

    except Exception as e:
        return {
            "message": f"failed to upload files: {e}",
            "session_id": None,
            "files": [],
        }


def analyze_text_session_with_claude(files: List[dict], user_id: str | None = None):
    prompt = build_text_session_prompt_for_claude(files, user_id=user_id)
    analysis, _, _ = _analyze_with_routed_text_json(
        "",
        prompt,
        task_type="manual_text_session",
        source_count=len(files),
        source_labels=[item.get("original_filename", "") for item in files],
        provider_override=PROVIDER_ANTHROPIC,
        capture_raw_output=True,
    )
    return analysis


def analyze_text_session_with_routed_llm(files: List[dict], user_id: str | None = None):
    system_prompt, user_prompt = _build_text_session_messages(files, user_id=user_id)
    return _analyze_with_routed_text_json(
        system_prompt,
        user_prompt,
        task_type="manual_text_session",
        source_count=len(files),
        source_labels=[item.get("original_filename", "") for item in files],
        capture_raw_output=True,
    )


@router.get("/manual/file/{stored_filename}", dependencies=[Depends(require_admin_auth)])
def get_manual_file(stored_filename: str):
    file_path = ensure_uploaded_file_local(stored_filename)
    if not file_path.exists():
        return {"message": "file not found"}
    return FileResponse(file_path)


@router.get("/manual/file-preview/{stored_filename}", dependencies=[Depends(require_admin_auth)])
def get_manual_file_preview(stored_filename: str):
    file_path = ensure_uploaded_file_local(stored_filename)
    if not file_path.exists():
        return {
            "message": "file not found",
            "stored_filename": stored_filename,
            "preview_text": "",
            "preview_available": False,
        }

    file_kind = get_file_kind(stored_filename)
    if file_kind not in {"text", "pdf"}:
        return {
            "message": "preview unsupported for this file type",
            "stored_filename": stored_filename,
            "file_kind": file_kind,
            "preview_text": "",
            "preview_available": False,
        }

    try:
        preview_text = build_manual_file_preview_text(file_path, file_kind)
    except Exception as exc:
        preview_text = f"[Preview extraction failed: {exc}]"

    return {
        "message": "file preview loaded successfully",
        "stored_filename": stored_filename,
        "file_kind": file_kind,
        "preview_text": preview_text,
        "preview_available": bool(preview_text),
    }


@router.get("/manual/sessions", dependencies=[Depends(require_admin_auth)])
def list_manual_sessions():
    try:
        items = enrich_session_summaries(load_sessions_index())
        return {
            "message": "manual sessions loaded successfully",
            "sessions": items,
        }
    except Exception as e:
        return {
            "message": f"failed to load manual sessions: {e}",
            "sessions": [],
        }


@router.get("/manual/session/{session_id}", dependencies=[Depends(require_admin_auth)])
def get_manual_session(session_id: str):
    try:
        session_data = load_session_detail(session_id)
        if not session_data:
            return {
                "message": "manual session not found",
                "session": None,
            }

        return {
            "message": "manual session loaded successfully",
            "session": enrich_manual_pdf_previews(session_data),
        }
    except Exception as e:
        return {
            "message": f"failed to load manual session: {e}",
            "session": None,
        }


class ManualAnalyzeRequest(BaseModel):
    stored_filename: str
    original_filename: str


class SessionFileItem(BaseModel):
    stored_filename: str
    original_filename: str
    file_kind: str


class ManualAnalyzeSessionRequest(BaseModel):
    files: List[SessionFileItem]
    session_id: str | None = None


@router.post("/manual/analyze", dependencies=[Depends(require_admin_auth)])
def analyze_manual_file(payload: ManualAnalyzeRequest, request: Request):
    try:
        user_id = resolve_request_user_id(request)
        file_path = ensure_uploaded_file_local(payload.stored_filename)

        if not file_path.exists():
            return {
                "message": "uploaded file not found",
                "analysis": None,
            }

        file_kind = get_file_kind(payload.original_filename)

        if file_kind in {"text", "pdf"}:
            text = extract_text_from_file(file_path)
            if not text.strip():
                return {
                    "message": "no extractable text found",
                    "analysis": None,
                }

            analysis, route, policy_metadata = analyze_text_with_routed_llm(
                payload.original_filename,
                text,
                user_id=user_id,
            )

        elif file_kind == "image":
            analysis, route, policy_metadata = analyze_image_with_routed_llm(
                payload.original_filename,
                file_path,
                user_id=user_id,
            )

        else:
            return {
                "message": "unsupported file type for analysis",
                "analysis": None,
            }

        return {
            "message": "analysis generated successfully",
            "analysis": analysis,
            "provider_used": route.provider,
            "policy_metadata": policy_metadata,
            "execution": (policy_metadata or {}).get("execution"),
        }

    except Exception as e:
        return {
            "message": f"failed to analyze file: {e}",
            "analysis": None,
        }


@router.post("/manual/analyze-session", dependencies=[Depends(require_admin_auth)])
def analyze_manual_session(payload: ManualAnalyzeSessionRequest, request: Request):
    try:
        user_id = resolve_request_user_id(request)
        if not payload.files:
            return {
                "message": "no uploaded files provided",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        files = [item.model_dump() for item in payload.files]
        valid_files = []

        for item in files:
            file_path = ensure_uploaded_file_local(item["stored_filename"])
            if file_path.exists():
                valid_files.append(item)

        if not valid_files:
            return {
                "message": "no valid uploaded files found",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        file_kinds = {item["file_kind"] for item in valid_files}

        analysis = None
        provider_used = None
        fallback_used = False
        policy_metadata = None
        input_text_raw_output_record = None

        if file_kinds == {"image"}:
            try:
                analysis, route, policy_metadata = analyze_image_session_with_routed_llm(
                    valid_files,
                    user_id=user_id,
                )
                provider_used = route.provider
            except Exception as first_error:
                if (
                    not _manual_provider_fallback_enabled()
                    or not is_provider_overloaded_error(first_error)
                ):
                    raise

                routed_provider = route_task("manual_image_session").provider
                fallback_provider = (
                    PROVIDER_ANTHROPIC
                    if routed_provider == PROVIDER_OPENAI
                    else PROVIDER_OPENAI
                )
                analysis, route = execute_vision_json_task(
                    task_type="manual_image_session",
                    prompt_text=build_image_analysis_prompt(is_session=True, user_id=user_id),
                    attachments=_build_image_attachments(valid_files),
                    max_tokens=1800,
                    provider_override=fallback_provider,
                    openai_api_key=OPENAI_API_KEY,
                    anthropic_api_key=ANTHROPIC_API_KEY,
                    fallback_used=True,
                )
                provider_used = route.provider
                fallback_used = True

        elif file_kinds.issubset({"text", "pdf"}):
            try:
                analysis, route, policy_metadata = analyze_text_session_with_routed_llm(
                    valid_files,
                    user_id=user_id,
                )
                provider_used = route.provider
            except Exception as first_error:
                routed_provider = route_task("manual_text_session").provider
                if (
                    not _manual_provider_fallback_enabled()
                    or not is_provider_overloaded_error(first_error)
                ):
                    raise

                fallback_provider = (
                    PROVIDER_ANTHROPIC
                    if routed_provider == PROVIDER_OPENAI
                    else PROVIDER_OPENAI
                )
                system_prompt, user_prompt = _build_text_session_messages(
                    valid_files,
                    user_id=user_id,
                )
                analysis, route, policy_metadata = _analyze_with_routed_text_json(
                    system_prompt,
                    user_prompt,
                    task_type="manual_text_session",
                    source_count=len(valid_files),
                    provider_override=fallback_provider,
                    fallback_used=True,
                    capture_raw_output=True,
                )
                provider_used = route.provider
                fallback_used = True

        else:
            return {
                "message": "mixed file session analysis is not supported yet. Please upload either all images or all text/PDF files in one session.",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        if file_kinds.issubset({"text", "pdf"}):
            input_text_raw_output_record = (policy_metadata or {}).pop(
                "input_text_analysis_raw_output",
                None,
            )

        if payload.session_id:
            session_data = load_session_detail(payload.session_id)

            if session_data:
                session_data["analysis"] = analysis
                session_data["analysis_status"] = "completed"
                session_data["updated_at"] = utc_now_iso()
                session_data["provider_used"] = provider_used
                session_data["fallback_used"] = fallback_used
                session_data["policy_metadata"] = policy_metadata
                if input_text_raw_output_record:
                    session_data["input_text_analysis_raw_output"] = input_text_raw_output_record
                session_data["workspace_saved"] = False
                session_data["completion_saved"] = False
                session_data["workspace_file_name"] = None
                session_data["workspace_saved_at"] = None

                save_session_detail(session_data)
                upsert_session_index_item(build_session_summary(session_data))
            else:
                update_session_analysis(payload.session_id, analysis)

        message = "session analysis generated successfully"
        if fallback_used:
            message = f"session analysis generated successfully via fallback provider ({provider_used})"

        return {
            "message": message,
            "analysis": analysis,
            "provider_used": provider_used,
            "fallback_used": fallback_used,
            "policy_metadata": policy_metadata,
            "execution": (policy_metadata or {}).get("execution"),
            "workspace_saved": False,
            "workspace_file_name": None,
        }

    except Exception as e:
        error_text = str(e)

        if (
            "overloaded_error" in error_text
            or "Overloaded" in error_text
            or "529" in error_text
        ):
            return {
                "message": "Analysis provider is temporarily overloaded. Please try again in a moment.",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        if is_provider_model_not_found_error(e):
            return {
                "message": "Primary analysis model is unavailable for this account. Please configure a supported Anthropic model or retry with fallback provider.",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        if is_provider_authentication_error(e):
            return {
                "message": "Primary analysis provider authentication failed and no working fallback provider completed the request. Check Anthropic/OpenAI API key configuration for the backend service.",
                "analysis": None,
                "provider_used": None,
                "fallback_used": False,
            }

        return {
            "message": f"failed to analyze session: {e}",
            "analysis": None,
            "provider_used": None,
            "fallback_used": False,
        }
