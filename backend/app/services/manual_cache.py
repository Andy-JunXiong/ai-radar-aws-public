import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


ANALYSIS_VERSION = "v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_file_hash(file_path: str) -> str:
    path = Path(file_path)
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def build_session_analysis_hash(session: Dict[str, Any]) -> str:
    """
    Build a stable hash for deciding whether session analysis can be reused.
    This should change if:
    - file contents change
    - file types change
    - analysis version changes
    """

    files = session.get("files", []) or []

    normalized_files: List[Dict[str, Any]] = []
    for file_item in files:
        file_path = file_item.get("stored_path") or file_item.get("path") or ""
        mime_type = file_item.get("mime_type", "")
        name = file_item.get("name", "")
        size = file_item.get("size", 0)

        content_hash = ""
        if file_path and Path(file_path).exists():
            content_hash = compute_file_hash(file_path)

        normalized_files.append(
            {
                "name": name,
                "mime_type": mime_type,
                "size": size,
                "content_hash": content_hash,
            }
        )

    normalized_files = sorted(
        normalized_files,
        key=lambda x: (x["name"], x["mime_type"], x["size"], x["content_hash"]),
    )

    payload = {
        "analysis_version": ANALYSIS_VERSION,
        "files": normalized_files,
    }

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256_text(canonical)


def should_use_cached_analysis(session: Dict[str, Any]) -> bool:
    existing_hash = session.get("analysis_hash")
    current_hash = build_session_analysis_hash(session)

    analysis = session.get("analysis")
    analysis_status = session.get("analysis_status")

    return (
        bool(existing_hash)
        and existing_hash == current_hash
        and analysis_status == "completed"
        and analysis is not None
    )