from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "dev_inbox_drafts"
INDEX_PATH = DATA_DIR / "index.json"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_S3_KEY = "dev-inbox/drafts/index.json"

REQUEST_TYPES = frozenset({"bug", "feature", "review", "ops"})
PRIORITIES = frozenset({"normal", "high", "low"})
STATUSES = frozenset({"open", "done"})


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
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _s3_bucket() -> str:
    return (os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET") or "").strip()


def _s3_key() -> str:
    return (
        os.getenv("AI_RADAR_DEV_INBOX_S3_KEY")
        or os.getenv("DEV_INBOX_DRAFTS_S3_KEY")
        or DEFAULT_S3_KEY
    ).strip().lstrip("/")


def _s3_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_DEV_INBOX_S3_ENABLED", "")).strip().lower()
    if value:
        return value not in {"0", "false", "no", "off"}
    return bool(
        os.getenv("AWS_EXECUTION_ENV")
        or os.getenv("ECS_CONTAINER_METADATA_URI")
        or os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    )


def _s3_client():
    if not _s3_enabled() or not _s3_bucket():
        return None
    import boto3

    return boto3.client("s3", region_name=AWS_REGION)


def get_dev_inbox_storage_status() -> dict[str, str]:
    if _s3_enabled() and _s3_bucket():
        return {
            "backend": "s3",
            "s3_bucket": _s3_bucket(),
            "s3_key": _s3_key(),
            "local_path": str(INDEX_PATH),
        }
    return {
        "backend": "local_file",
        "s3_bucket": _s3_bucket(),
        "s3_key": _s3_key(),
        "local_path": str(INDEX_PATH),
    }


def _normalize_index_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("drafts"), list):
        payload = payload.get("drafts")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _read_s3_index() -> list[dict[str, Any]] | None:
    client = _s3_client()
    bucket = _s3_bucket()
    key = _s3_key()
    if client is None or not bucket or not key:
        return None

    try:
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read().decode("utf-8")
        return _normalize_index_payload(json.loads(raw))
    except KeyError:
        return None
    except Exception as exc:
        response = getattr(exc, "response", {}) if exc else {}
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        code = str(error.get("Code") or "").strip()
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise RuntimeError(f"Failed to read Dev Inbox S3 draft store: {type(exc).__name__}") from exc


def _write_s3_index(items: list[dict[str, Any]]) -> None:
    client = _s3_client()
    bucket = _s3_bucket()
    key = _s3_key()
    if client is None or not bucket or not key:
        raise RuntimeError("S3-backed Dev Inbox is enabled but no S3 client, bucket, or key is available.")

    payload = json.dumps({"drafts": items}, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/json; charset=utf-8",
    )


def _write_local_cache(items: list[dict[str, Any]]) -> None:
    try:
        _ensure_data_dir()
        INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _write_local_index(items: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_index() -> list[dict[str, Any]]:
    if _s3_enabled() and _s3_bucket():
        s3_items = _read_s3_index()
        if s3_items is not None:
            _write_local_cache(s3_items)
            return s3_items

    _ensure_data_dir()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return _normalize_index_payload(payload)


def _save_index(items: list[dict[str, Any]]) -> None:
    if _s3_enabled() and _s3_bucket():
        _write_s3_index(items)
        _write_local_cache(items)
        return

    _write_local_index(items)


def _normalize_choice(value: Any, allowed: frozenset[str], default: str) -> str:
    normalized = _safe_text(value).lower()
    return normalized if normalized in allowed else default


def _normalize_draft(raw: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _utc_now_iso()
    draft_id = _safe_text(raw.get("id")) or _safe_text(existing.get("id") if existing else "") or f"dev_{uuid.uuid4().hex[:12]}"
    task = _safe_text(raw.get("task"))
    if not task:
        raise ValueError("task is required.")

    created_at = _safe_text(existing.get("created_at") if existing else "") or _safe_text(raw.get("savedAt")) or now
    saved_at = _safe_text(raw.get("savedAt")) or _safe_text(existing.get("savedAt") if existing else "") or now

    return {
        "id": draft_id,
        "repo": _safe_text(raw.get("repo")) or _safe_text(existing.get("repo") if existing else "") or "Andy-JunXiong/ai-radar-aws",
        "branch": _safe_text(raw.get("branch")) or _safe_text(existing.get("branch") if existing else "") or "main",
        "requestType": _normalize_choice(raw.get("requestType"), REQUEST_TYPES, "bug"),
        "priority": _normalize_choice(raw.get("priority"), PRIORITIES, "normal"),
        "surface": _safe_text(raw.get("surface")),
        "task": task,
        "status": _normalize_choice(raw.get("status"), STATUSES, "open"),
        "savedAt": saved_at,
        "created_at": created_at,
        "updated_at": now,
    }


def list_dev_inbox_drafts() -> list[dict[str, Any]]:
    return sorted(_load_index(), key=lambda item: str(item.get("updated_at") or item.get("savedAt") or ""), reverse=True)


def upsert_dev_inbox_draft(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("draft must be a JSON object.")

    items = _load_index()
    draft_id = _safe_text(raw.get("id"))
    existing = next((item for item in items if draft_id and item.get("id") == draft_id), None)
    draft = _normalize_draft(raw, existing=existing)
    remaining = [item for item in items if item.get("id") != draft["id"]]
    remaining.append(draft)
    _save_index(sorted(remaining, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return draft


def update_dev_inbox_draft_status(draft_id: str, status: str) -> dict[str, Any]:
    normalized_id = _safe_text(draft_id)
    normalized_status = _normalize_choice(status, STATUSES, "")
    if not normalized_id:
        raise ValueError("draft id is required.")
    if not normalized_status:
        raise ValueError("status must be open or done.")

    items = _load_index()
    for item in items:
        if item.get("id") != normalized_id:
            continue
        item["status"] = normalized_status
        item["updated_at"] = _utc_now_iso()
        _save_index(sorted(items, key=lambda row: str(row.get("updated_at") or ""), reverse=True))
        return item

    raise ValueError("draft not found.")


def delete_dev_inbox_draft(draft_id: str) -> bool:
    normalized_id = _safe_text(draft_id)
    if not normalized_id:
        raise ValueError("draft id is required.")

    items = _load_index()
    remaining = [item for item in items if item.get("id") != normalized_id]
    if len(remaining) == len(items):
        return False
    _save_index(remaining)
    return True
