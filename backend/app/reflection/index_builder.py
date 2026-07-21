from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

from app.reflection import _BACKEND_DIR
from app.reflection.frontmatter_parser import (
    FrontmatterParseError,
    parse_reflection,
    parse_reflection_json_bundle,
)
from app.reflection.github_client import GitHubReflectionClient
from app.reflection.schemas import ReflectionIndex, SyncState


REFLECTIONS_S3_INDEX_KEY = "reflections/index.json"
REFLECTIONS_S3_SYNC_STATE_KEY = "reflections/sync_state.json"

LOCAL_REFLECTIONS_DIR = _BACKEND_DIR / "data" / "reflections"
LOCAL_REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_INDEX_PATH = LOCAL_REFLECTIONS_DIR / "index.json"
LOCAL_SYNC_STATE_PATH = LOCAL_REFLECTIONS_DIR / "sync_state.json"

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _read_local_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_local_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_s3_json(key: str) -> Any | None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _write_s3_json(key: str, payload: Any) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def load_reflection_index() -> ReflectionIndex:
    payload = _read_local_json(LOCAL_INDEX_PATH) or _read_s3_json(REFLECTIONS_S3_INDEX_KEY)
    if not payload:
        return ReflectionIndex(last_updated=_utc_now(), total_count=0, reflections=[])
    return ReflectionIndex(**payload)


def load_sync_state() -> SyncState:
    payload = _read_local_json(LOCAL_SYNC_STATE_PATH) or _read_s3_json(REFLECTIONS_S3_SYNC_STATE_KEY)
    if not payload:
        return SyncState(last_sync_at=_utc_now(), last_commit_sha=None, total_reflections=0)
    return SyncState(**payload)


def sync_reflections(force_full: bool = False) -> SyncState:
    client = GitHubReflectionClient()
    state = load_sync_state()
    errors: list[str] = []

    current_sha = client.get_latest_commit_sha()
    if not force_full and state.last_commit_sha == current_sha:
        state.last_sync_at = _utc_now()
        state.last_success = True
        _write_local_json(LOCAL_SYNC_STATE_PATH, state.model_dump(mode="json"))
        _write_s3_json(REFLECTIONS_S3_SYNC_STATE_KEY, state.model_dump(mode="json"))
        return state

    # Minimal Phase 1: full rebuild when repo changed. Safer than partial diff for now.
    files = client.list_reflection_source_files()

    reflections = []
    markdown_files = [file_info for file_info in files if file_info.name.endswith(".md")]
    json_files = [file_info for file_info in files if file_info.name.endswith(".json")]
    html_files = [file_info for file_info in files if file_info.name.endswith(".html")]
    html_by_prefix = {
        file_info.name.split("_", 1)[0]: file_info
        for file_info in html_files
        if file_info.name.split("_", 1)[0].isdigit()
    }

    for file_info in markdown_files:
        try:
            content = client.get_file_content(file_info.path)
            metadata = client.get_file_metadata(file_info.path)
            last_modified_raw = metadata.get("last_modified") or _utc_now().isoformat()
            last_modified = datetime.fromisoformat(last_modified_raw.replace("Z", "+00:00"))
            commit_sha = metadata.get("commit_sha") or file_info.sha or current_sha

            reflection = parse_reflection(
                content=content,
                github_path=file_info.path,
                github_url=file_info.html_url,
                github_raw_url=client.build_raw_url(file_info.path),
                commit_sha=commit_sha,
                last_modified=last_modified,
            )
            reflections.append(reflection)
        except FrontmatterParseError as exc:
            errors.append(f"{file_info.path}: {exc}")
        except Exception as exc:
            errors.append(f"{file_info.path}: unexpected error: {exc}")

    for file_info in json_files:
        try:
            schema_content = client.get_file_content(file_info.path)
            metadata = client.get_file_metadata(file_info.path)
            last_modified_raw = metadata.get("last_modified") or _utc_now().isoformat()
            last_modified = datetime.fromisoformat(last_modified_raw.replace("Z", "+00:00"))
            commit_sha = metadata.get("commit_sha") or file_info.sha or current_sha
            prefix = file_info.name.split("_", 1)[0]
            html_file = html_by_prefix.get(prefix) if prefix.isdigit() else None

            reflection, _rendered_content = parse_reflection_json_bundle(
                schema_content=schema_content,
                schema_path=file_info.path,
                schema_url=file_info.html_url,
                schema_raw_url=client.build_raw_url(file_info.path),
                html_path=html_file.path if html_file else None,
                html_url=html_file.html_url if html_file else None,
                html_raw_url=client.build_raw_url(html_file.path) if html_file else None,
                commit_sha=commit_sha,
                last_modified=last_modified,
            )
            reflections.append(reflection)
        except FrontmatterParseError as exc:
            errors.append(f"{file_info.path}: {exc}")
        except Exception as exc:
            errors.append(f"{file_info.path}: unexpected error: {exc}")

    reflections.sort(key=lambda item: item.timestamp, reverse=True)

    index = ReflectionIndex(
        schema_version="2.0",
        last_updated=_utc_now(),
        total_count=len(reflections),
        reflections=reflections,
    )
    _write_local_json(LOCAL_INDEX_PATH, index.model_dump(mode="json"))
    _write_s3_json(REFLECTIONS_S3_INDEX_KEY, index.model_dump(mode="json"))

    state.last_sync_at = _utc_now()
    state.last_commit_sha = current_sha
    state.last_success = len(errors) == 0
    state.last_error = "; ".join(errors[:5]) if errors else None
    state.total_reflections = index.total_count
    _write_local_json(LOCAL_SYNC_STATE_PATH, state.model_dump(mode="json"))
    _write_s3_json(REFLECTIONS_S3_SYNC_STATE_KEY, state.model_dump(mode="json"))
    return state
