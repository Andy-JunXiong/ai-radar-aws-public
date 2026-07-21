from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.github_project_reader import (
    GitHubRequestError,
    fetch_project_github_context,
    fetch_repo_manifest_files,
    fetch_repo_recent_commits,
    fetch_repo_top_level_tree,
    normalize_repo_name,
)


BASE_DIR = Path(__file__).resolve().parents[2] / "data"
PROJECT_REPO_SNAPSHOT_DIR = BASE_DIR / "project_repo_snapshots"
PROJECT_REPO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _snapshot_path(project_id: str) -> Path:
    safe_project_id = _safe_text(project_id).replace("/", "_").replace("\\", "_")
    return PROJECT_REPO_SNAPSHOT_DIR / f"{safe_project_id}.json"


def _truncate(value: Any, limit: int = 900) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _first_paragraph(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    paragraphs = [item.strip() for item in text.split("\n\n") if item.strip()]
    return _truncate(paragraphs[0] if paragraphs else text, 420)


def _architecture_hints(tree: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> list[str]:
    names = {_safe_text(item.get("path") or item.get("name")).lower() for item in tree}
    manifest_paths = {_safe_text(item.get("path")).lower() for item in manifests}
    hints: list[str] = []

    if {"frontend", "backend"} <= names:
        hints.append("frontend/backend split")
    if "app" in names:
        hints.append("app entrypoint")
    if "docs" in names:
        hints.append("docs directory")
    if "agent-skills" in names:
        hints.append("agent skill registry")
    if "package.json" in manifest_paths or "frontend/package.json" in manifest_paths:
        hints.append("node/frontend manifest")
    if "pyproject.toml" in manifest_paths or "requirements.txt" in manifest_paths or "backend/requirements.txt" in manifest_paths:
        hints.append("python backend manifest")
    if "dockerfile" in manifest_paths:
        hints.append("dockerized runtime")

    return hints


def _keywords(project: dict[str, Any], github: dict[str, Any], tree: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    values.extend(_safe_text(topic) for topic in project.get("topics", []) if _safe_text(topic))
    repository = github.get("repository") if isinstance(github.get("repository"), dict) else {}
    values.extend(
        [
            _safe_text(project.get("name")),
            _safe_text(repository.get("full_name")),
            _safe_text(repository.get("description")),
        ]
    )
    values.extend(_safe_text(item.get("name")) for item in tree if item.get("type") == "dir")
    values.extend(_safe_text(item.get("path")) for item in manifests)

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = value.strip()
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result[:18]


def _status_from_github(github: dict[str, Any], repo: str, *, has_partial_context: bool = False) -> tuple[str, str]:
    if not repo:
        return "not_connected", "No GitHub repository is connected."
    github_status = _safe_text(github.get("status"))
    if github_status in {"loaded", "missing_roadmap"}:
        return "fresh", _safe_text(github.get("message")) or "Light repo snapshot generated."
    if has_partial_context:
        detail = _safe_text(github.get("message"))
        message = "Light repo snapshot partially loaded; some GitHub context sections were unavailable."
        return "partial", f"{message} {detail}".strip()
    return "failed", _safe_text(github.get("message")) or "GitHub repository context could not be loaded."


def _has_snapshot_context(snapshot: dict[str, Any]) -> bool:
    github = snapshot.get("github") if isinstance(snapshot.get("github"), dict) else {}
    repository = github.get("repository") if isinstance(github.get("repository"), dict) else {}
    return bool(
        repository
        or snapshot.get("summary")
        or snapshot.get("readme_found")
        or snapshot.get("roadmap_found")
        or snapshot.get("architecture_hints")
        or snapshot.get("top_level_tree")
        or snapshot.get("recent_commits")
        or snapshot.get("manifests")
    )


def _normalize_snapshot_status(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("status") == "failed" and _has_snapshot_context(snapshot):
        message = _safe_text(snapshot.get("message"))
        if not message or "partially loaded" not in message.lower():
            message = "Light repo snapshot partially loaded; some GitHub context sections were unavailable."
        return {**snapshot, "status": "partial", "message": message}
    return snapshot


def _apply_freshness(snapshot: dict[str, Any], *, ttl_hours: int = 168) -> dict[str, Any]:
    if snapshot.get("status") not in {"fresh", "partial"}:
        return snapshot

    scanned_at_raw = _safe_text(snapshot.get("scanned_at"))
    try:
        scanned_at = datetime.fromisoformat(scanned_at_raw.replace("Z", "+00:00"))
    except Exception:
        return {**snapshot, "status": "stale"}

    if scanned_at < datetime.now(timezone.utc) - timedelta(hours=ttl_hours):
        return {**snapshot, "status": "stale"}
    return snapshot


def load_project_repo_snapshot(project_id: str, *, include_freshness: bool = True) -> dict[str, Any] | None:
    path = _snapshot_path(project_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    normalized = _normalize_snapshot_status(payload)
    return _apply_freshness(normalized) if include_freshness else normalized


def save_project_repo_snapshot(project_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        **snapshot,
        "project_id": project_id,
    }
    _snapshot_path(project_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def build_light_project_repo_snapshot(project: dict[str, Any]) -> dict[str, Any]:
    project_id = _safe_text(project.get("project_id"))
    repo = normalize_repo_name(_safe_text(project.get("repo")))
    scanned_at = _utc_now_iso()

    if not repo:
        return save_project_repo_snapshot(
            project_id,
            {
                "status": "not_connected",
                "repo": "",
                "scanned_at": scanned_at,
                "message": "No GitHub repository is connected.",
                "summary": "",
                "readme_found": False,
                "roadmap_found": False,
                "architecture_hints": [],
                "keywords": [],
                "top_level_tree": [],
                "recent_commits": [],
                "manifests": [],
                "github": {"status": "no_repo"},
            },
        )

    github = fetch_project_github_context(repo)
    tree: list[dict[str, Any]] = []
    commits: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    extra_errors: list[str] = []

    for label, fetcher in (
        ("top_level_tree", lambda: fetch_repo_top_level_tree(repo)),
        ("recent_commits", lambda: fetch_repo_recent_commits(repo)),
        ("manifests", lambda: fetch_repo_manifest_files(repo)),
    ):
        try:
            value = fetcher()
        except GitHubRequestError as exc:
            extra_errors.append(f"{label}: {exc.kind}")
            value = []
        if label == "top_level_tree":
            tree = value
        elif label == "recent_commits":
            commits = value
        else:
            manifests = value

    repository = github.get("repository") if isinstance(github.get("repository"), dict) else {}
    readme = github.get("readme") if isinstance(github.get("readme"), dict) else {}
    roadmap = github.get("roadmap") if isinstance(github.get("roadmap"), dict) else {}
    has_partial_context = bool(repository or readme or roadmap or tree or commits or manifests)
    status, message = _status_from_github(github, repo, has_partial_context=has_partial_context)
    if extra_errors and status in {"fresh", "partial"}:
        message = f"{message} Some optional snapshot sections were unavailable: {', '.join(extra_errors)}."

    summary_source = repository.get("description") or _first_paragraph(readme.get("content")) or _safe_text(project.get("description"))

    snapshot = {
        "status": status,
        "repo": repo,
        "scanned_at": scanned_at,
        "message": message,
        "summary": _truncate(summary_source, 500),
        "readme_found": bool(readme),
        "readme_path": readme.get("path") if readme else "",
        "readme_excerpt": _truncate(readme.get("content"), 1600) if readme else "",
        "roadmap_found": bool(roadmap),
        "roadmap_path": roadmap.get("path") if roadmap else "",
        "roadmap_excerpt": _truncate(roadmap.get("content"), 1600) if roadmap else "",
        "architecture_hints": _architecture_hints(tree, manifests),
        "keywords": _keywords(project, github, tree, manifests),
        "top_level_tree": tree,
        "recent_commits": commits,
        "manifests": manifests,
        "github": {
            "status": github.get("status"),
            "message": github.get("message"),
            "repository": repository or None,
        },
        "optional_section_errors": extra_errors,
    }
    return save_project_repo_snapshot(project_id, snapshot)


def get_or_refresh_project_repo_snapshot(
    project: dict[str, Any],
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    project_id = _safe_text(project.get("project_id"))
    repo = normalize_repo_name(_safe_text(project.get("repo")))
    existing = load_project_repo_snapshot(project_id)

    if not force_refresh and existing and normalize_repo_name(_safe_text(existing.get("repo"))) == repo:
        return existing

    return build_light_project_repo_snapshot(project)


def maybe_refresh_project_repo_snapshot_after_save(
    project: dict[str, Any],
    *,
    previous_repo: str = "",
) -> dict[str, Any] | None:
    repo = normalize_repo_name(_safe_text(project.get("repo")))
    previous = normalize_repo_name(previous_repo)
    if not repo:
        return build_light_project_repo_snapshot(project)

    existing = load_project_repo_snapshot(_safe_text(project.get("project_id")))
    force_refresh = repo != previous or not existing
    return get_or_refresh_project_repo_snapshot(project, force_refresh=force_refresh)
