from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = BASE_DIR / "data" / "project_registry.json"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
PROJECT_REGISTRY_S3_KEY = (
    os.getenv("PROJECT_REGISTRY_S3_KEY")
    or "settings/project_registry.json"
).strip().lstrip("/")


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _default_registry() -> Dict[str, Any]:
    return {"projects": []}


def _s3_client():
    if not S3_BUCKET:
        return None
    try:
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception:
        return None


def _normalize_registry_payload(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return _default_registry()

    if "projects" not in data or not isinstance(data["projects"], list):
        data["projects"] = []

    return data


def _read_local_registry() -> Dict[str, Any] | None:
    ensure_registry_exists()
    try:
        with REGISTRY_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_local_registry(data: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_s3_registry() -> Dict[str, Any] | None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return None

    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=PROJECT_REGISTRY_S3_KEY)
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _write_s3_registry(data: Dict[str, Any]) -> None:
    client = _s3_client()
    if client is None or not S3_BUCKET:
        return

    client.put_object(
        Bucket=S3_BUCKET,
        Key=PROJECT_REGISTRY_S3_KEY,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def ensure_registry_exists() -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        with REGISTRY_PATH.open("w", encoding="utf-8") as f:
            json.dump(_default_registry(), f, indent=2, ensure_ascii=False)


def load_registry() -> Dict[str, Any]:
    s3_data = _read_s3_registry()
    if s3_data is not None:
        normalized = _normalize_registry_payload(s3_data)
        try:
            _write_local_registry(normalized)
        except Exception:
            pass
        return normalized

    local_data = _read_local_registry()
    if local_data is not None:
        return _normalize_registry_payload(local_data)

    return _default_registry()


def save_registry(data: Dict[str, Any]) -> None:
    normalized = _normalize_registry_payload(data)
    _write_local_registry(normalized)
    try:
        _write_s3_registry(normalized)
    except Exception:
        pass


def list_projects() -> List[Dict[str, Any]]:
    data = load_registry()
    return data.get("projects", [])


def is_active_project(project: Dict[str, Any]) -> bool:
    return bool(project.get("enabled", True)) and str(project.get("status", "")).strip().lower() == "active"


def list_active_projects() -> List[Dict[str, Any]]:
    return [project for project in list_projects() if is_active_project(project)]


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    projects = list_projects()
    for project in projects:
        if project.get("project_id") == project_id:
            return project
    return None


def add_project(project: Dict[str, Any]) -> Dict[str, Any]:
    data = load_registry()
    projects = data["projects"]

    project_id = project.get("project_id")
    if not project_id:
        raise ValueError("project_id is required")

    existing = get_project(project_id)
    if existing:
        raise ValueError(f"Project already exists: {project_id}")

    now = _utc_now_iso()

    new_project = {
        "project_id": project_id,
        "name": project.get("name", project_id),
        "enabled": bool(project.get("enabled", True)),
        "status": project.get("status", "research"),
        "description": project.get("description", ""),
        "repo": project.get("repo", ""),
        "current_state": project.get("current_state", ""),
        "roadmap": project.get("roadmap", ""),
        "topics": project.get("topics", []),
        "source": project.get("source", "manual"),
        "created_at": project.get("created_at") or now,
        "updated_at": project.get("updated_at") or now,
        "related_signals": project.get("related_signals", []),
        "related_notes": project.get("related_notes", []),
        "metadata": project.get("metadata", {}),
    }

    projects.append(new_project)
    save_registry(data)
    return new_project


def upsert_project(project_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    data = load_registry()
    now = _utc_now_iso()

    for project in data["projects"]:
        if project.get("project_id") == project_id:
            project["name"] = updates.get("name", project.get("name", project_id))
            project["enabled"] = bool(updates.get("enabled", project.get("enabled", True)))
            project["status"] = updates.get("status", project.get("status", "research"))
            project["description"] = updates.get("description", project.get("description", ""))
            project["repo"] = updates.get("repo", project.get("repo", ""))
            project["current_state"] = updates.get("current_state", project.get("current_state", ""))
            project["roadmap"] = updates.get("roadmap", project.get("roadmap", ""))
            project["topics"] = updates.get("topics", project.get("topics", []))
            project["source"] = updates.get("source", project.get("source", "manual"))
            project["metadata"] = updates.get("metadata", project.get("metadata", {}))
            project["updated_at"] = now
            save_registry(data)
            return project

    return add_project(
        {
            "project_id": project_id,
            "name": updates.get("name", project_id),
            "enabled": updates.get("enabled", True),
            "status": updates.get("status", "research"),
            "description": updates.get("description", ""),
            "repo": updates.get("repo", ""),
            "current_state": updates.get("current_state", ""),
            "roadmap": updates.get("roadmap", ""),
            "topics": updates.get("topics", []),
            "source": updates.get("source", "manual"),
            "created_at": now,
            "updated_at": now,
            "related_signals": updates.get("related_signals", []),
            "related_notes": updates.get("related_notes", []),
            "metadata": updates.get("metadata", {}),
        }
    )


def update_project_status(project_id: str, status: str) -> Dict[str, Any]:
    data = load_registry()

    for project in data["projects"]:
        if project.get("project_id") == project_id:
            project["status"] = status
            project["updated_at"] = _utc_now_iso()
            save_registry(data)
            return project

    raise ValueError(f"Project not found: {project_id}")


def update_project_repo(project_id: str, repo: str) -> Dict[str, Any]:
    data = load_registry()

    for project in data["projects"]:
        if project.get("project_id") == project_id:
            project["repo"] = repo
            project["updated_at"] = _utc_now_iso()
            save_registry(data)
            return project

    raise ValueError(f"Project not found: {project_id}")


def map_signal_to_project(project_id: str, signal_id: str) -> Dict[str, Any]:
    data = load_registry()

    for project in data["projects"]:
        if project.get("project_id") == project_id:
            related_signals = project.setdefault("related_signals", [])
            if signal_id not in related_signals:
                related_signals.append(signal_id)
                project["updated_at"] = _utc_now_iso()
                save_registry(data)
            return project

    raise ValueError(f"Project not found: {project_id}")


def add_note_to_project(project_id: str, note_id: str) -> Dict[str, Any]:
    data = load_registry()

    for project in data["projects"]:
        if project.get("project_id") == project_id:
            related_notes = project.setdefault("related_notes", [])
            if note_id not in related_notes:
                related_notes.append(note_id)
                project["updated_at"] = _utc_now_iso()
                save_registry(data)
            return project

    raise ValueError(f"Project not found: {project_id}")


def find_projects_by_topic(topic_keyword: str) -> List[Dict[str, Any]]:
    keyword = topic_keyword.strip().lower()
    if not keyword:
        return []

    matched: List[Dict[str, Any]] = []
    for project in list_projects():
        topics = project.get("topics", [])
        if any(keyword in str(topic).lower() for topic in topics):
            matched.append(project)

    return matched
