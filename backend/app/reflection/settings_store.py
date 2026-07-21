from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3

from app.reflection import _BACKEND_DIR


BASE_DIR = _BACKEND_DIR / "data" / "settings" / "reflection"
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET") or "").strip()
REFLECTION_S3_PREFIX = (
    os.getenv("REFLECTION_SETTINGS_S3_PREFIX")
    or "settings/reflection"
).strip("/ ")
DEFAULT_REFLECTION_SCOPE = (
    os.getenv("REFLECTION_SETTINGS_SCOPE")
    or "admin_default"
).strip() or "admin_default"


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _safe_user_id(user_id: str | None) -> str:
    normalized = (user_id or DEFAULT_REFLECTION_SCOPE).strip() or DEFAULT_REFLECTION_SCOPE
    return normalized.replace("/", "_").replace("\\", "_")


def _local_path(user_id: str | None) -> Path:
    return BASE_DIR / f"{_safe_user_id(user_id)}.json"


def _s3_key(user_id: str | None) -> str:
    return f"{REFLECTION_S3_PREFIX}/{_safe_user_id(user_id)}.json"


def normalize_reflection_repo_input(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if "github.com" not in parsed.netloc.lower():
            return raw
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return raw

    cleaned = raw[:-4] if raw.endswith(".git") else raw
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return cleaned


def build_repo_url(repo: str) -> str:
    normalized = normalize_reflection_repo_input(repo)
    if not normalized or normalized.count("/") != 1:
        return ""
    return f"https://github.com/{normalized}"


def _default_payload(user_id: str | None) -> dict[str, Any]:
    repo = normalize_reflection_repo_input(os.getenv("GITHUB_REFLECTIONS_REPO", ""))
    branch = (os.getenv("GITHUB_REFLECTIONS_BRANCH", "main") or "main").strip() or "main"
    return {
        "user_id": user_id or DEFAULT_REFLECTION_SCOPE,
        "enabled": bool(repo),
        "repo": repo,
        "repo_url": build_repo_url(repo),
        "branch": branch,
    }


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


def _read_s3_payload(user_id: str | None) -> dict[str, Any] | None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=_s3_key(user_id))
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _write_s3_payload(user_id: str | None, payload: dict[str, Any]) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    client.put_object(
        Bucket=S3_BUCKET,
        Key=_s3_key(user_id),
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _normalize_payload(user_id: str | None, payload: Any) -> dict[str, Any]:
    default = _default_payload(user_id)
    if not isinstance(payload, dict):
        return default

    repo = normalize_reflection_repo_input(str(payload.get("repo") or default["repo"]))
    branch = str(payload.get("branch") or default["branch"]).strip() or "main"
    enabled = bool(payload.get("enabled", bool(repo)))

    return {
        "user_id": user_id or DEFAULT_REFLECTION_SCOPE,
        "enabled": enabled,
        "repo": repo,
        "repo_url": build_repo_url(repo),
        "branch": branch,
    }


def load_reflection_settings(user_id: str | None = None) -> dict[str, Any]:
    path = _local_path(user_id)
    s3_payload = _read_s3_payload(user_id)
    if s3_payload is not None:
        normalized = _normalize_payload(user_id, s3_payload)
        try:
            _write_local_payload(path, normalized)
        except Exception:
            pass
        return normalized

    local_payload = _read_local_payload(path)
    if local_payload is not None:
        return _normalize_payload(user_id, local_payload)

    return _default_payload(user_id)


def save_reflection_settings(user_id: str | None, payload: dict[str, Any]) -> Path:
    path = _local_path(user_id)
    normalized = _normalize_payload(user_id, payload)
    _write_local_payload(path, normalized)
    try:
        _write_s3_payload(user_id, normalized)
    except Exception:
        pass
    return path


def get_reflection_settings_status(user_id: str | None = None) -> dict[str, Any]:
    path = _local_path(user_id)
    settings = load_reflection_settings(user_id)
    return {
        "local_path": str(path),
        "s3_bucket": S3_BUCKET or "",
        "s3_key": _s3_key(user_id),
        "repo_url": settings.get("repo_url", ""),
        "has_pat": "yes" if os.getenv("GITHUB_REFLECTIONS_PAT") else "no",
    }
