from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from app.services.github_project_reader import (
    GitHubRequestError,
    fetch_project_github_context,
    fetch_repo_compare,
    fetch_repo_head,
    fetch_repo_manifest_files,
    fetch_repo_metadata,
    fetch_repo_recent_commits,
    fetch_repo_top_level_tree,
    fetch_repo_truth_map_anchors,
    normalize_repo_name,
)
from app.services.project_truth_map_service import resolve_project_truth_map


BASE_DIR = Path(__file__).resolve().parents[2] / "data"
PROJECT_REPO_SNAPSHOT_DIR = BASE_DIR / "project_repo_snapshots"
PROJECT_REPO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROJECT_REPO_SNAPSHOT_S3_PREFIX = "project_repo_snapshots"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _snapshot_path(project_id: str) -> Path:
    safe_project_id = _safe_text(project_id).replace("/", "_").replace("\\", "_")
    return PROJECT_REPO_SNAPSHOT_DIR / f"{safe_project_id}.json"


def _local_output_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_USE_LOCAL_OUTPUT", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _shared_storage_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_PROJECT_SNAPSHOT_S3_ENABLED", "")).strip().lower()
    return bool(_snapshot_bucket()) and value in {"1", "true", "yes", "on"} and not _local_output_enabled()


def _snapshot_bucket() -> str:
    return str(os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET") or "").strip()


def _snapshot_s3_prefix() -> str:
    return (
        str(os.getenv("PROJECT_REPO_SNAPSHOT_S3_PREFIX") or DEFAULT_PROJECT_REPO_SNAPSHOT_S3_PREFIX)
        .strip()
        .strip("/")
    )


def _snapshot_s3_key(project_id: str) -> str:
    safe_project_id = _safe_text(project_id).replace("/", "_").replace("\\", "_")
    return f"{_snapshot_s3_prefix()}/{safe_project_id}.json"


def _s3_client():
    if not _snapshot_bucket():
        return None
    return boto3.client(
        "s3",
        region_name=str(os.getenv("AWS_REGION") or "ap-southeast-2").strip(),
        config=Config(connect_timeout=2, read_timeout=4, retries={"max_attempts": 2}),
    )


def _read_local_snapshot(project_id: str) -> dict[str, Any] | None:
    path = _snapshot_path(project_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _write_local_snapshot(project_id: str, payload: dict[str, Any]) -> None:
    path = _snapshot_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _read_shared_snapshot(project_id: str) -> dict[str, Any] | None:
    client = _s3_client()
    bucket = _snapshot_bucket()
    if client is None or not bucket:
        return None
    try:
        response = client.get_object(Bucket=bucket, Key=_snapshot_s3_key(project_id))
        payload = json.loads(response["Body"].read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _write_shared_snapshot(project_id: str, payload: dict[str, Any]) -> None:
    client = _s3_client()
    bucket = _snapshot_bucket()
    if client is None or not bucket:
        raise RuntimeError("Project Snapshot shared storage is enabled but unavailable.")
    client.put_object(
        Bucket=bucket,
        Key=_snapshot_s3_key(project_id),
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


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


def _deterministic_summary(primary: Any, fallback: Any = "") -> str:
    text = _safe_text(primary)
    if not text:
        return _truncate(fallback, 500)

    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line.startswith(("```", "#", ">", "![", "[![")):
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = line.replace("**", "").replace("__", "").replace("`", "").strip()
        if line:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    useful = next((paragraph for paragraph in paragraphs if len(paragraph) >= 40), None)
    return _truncate(useful or (paragraphs[0] if paragraphs else fallback), 500)


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
        or snapshot.get("anchors")
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
    payload: dict[str, Any] | None = None
    if _shared_storage_enabled():
        payload = _read_shared_snapshot(project_id)
        if payload is not None:
            try:
                _write_local_snapshot(project_id, payload)
            except Exception:
                pass
    if payload is None:
        payload = _read_local_snapshot(project_id)
    if payload is None:
        return None
    normalized = _normalize_snapshot_status(payload)
    return _apply_freshness(normalized) if include_freshness else normalized


def _refresh_state_for_saved_snapshot(
    snapshot: dict[str, Any],
    *,
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    attempted_at = _safe_text(snapshot.get("scanned_at")) or _utc_now_iso()
    status = _safe_text(snapshot.get("status")).lower() or "failed"
    existing_refresh = existing.get("refresh") if isinstance((existing or {}).get("refresh"), dict) else {}

    if status == "failed" and existing and _has_snapshot_context(existing):
        return {
            **existing,
            "refresh": {
                **existing_refresh,
                "last_attempted_at": attempted_at,
                "last_attempt_status": "failed",
                "last_succeeded_at": _safe_text(existing_refresh.get("last_succeeded_at"))
                or _safe_text(existing.get("scanned_at")),
                "last_failure": {
                    "at": attempted_at,
                    "message": _safe_text(snapshot.get("message")) or "Project Snapshot refresh failed.",
                },
            },
        }

    refresh = {
        **existing_refresh,
        "last_attempted_at": attempted_at,
        "last_attempt_status": status,
        "last_failure": None,
    }
    if status in {"fresh", "partial"}:
        refresh["last_succeeded_at"] = attempted_at
    return {**snapshot, "refresh": refresh}


def save_project_repo_snapshot(project_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    existing = load_project_repo_snapshot(project_id, include_freshness=False)
    prepared = _refresh_state_for_saved_snapshot(snapshot, existing=existing)
    payload = {
        **prepared,
        "schema_version": 2,
        "project_id": project_id,
    }
    if _shared_storage_enabled():
        try:
            _write_shared_snapshot(project_id, payload)
        except Exception as exc:
            raise RuntimeError(f"Failed to persist Project Snapshot in shared storage: {type(exc).__name__}") from exc
        try:
            _write_local_snapshot(project_id, payload)
        except Exception:
            pass
    else:
        _write_local_snapshot(project_id, payload)
    return payload


def _fetch_head(repo: str, default_branch: str = "") -> tuple[dict[str, Any], list[str]]:
    try:
        head = fetch_repo_head(repo, default_branch=default_branch)
    except GitHubRequestError as exc:
        return {}, [f"head: {exc.kind}"]
    if not head:
        return {}, ["head: unavailable"]
    return head, []


def _previous_successful_head(previous_snapshot: Any, repo: str) -> dict[str, Any] | None:
    if not isinstance(previous_snapshot, dict):
        return None
    if normalize_repo_name(_safe_text(previous_snapshot.get("repo"))) != normalize_repo_name(repo):
        return None
    observation = previous_snapshot.get("observation")
    if not isinstance(observation, dict):
        return None
    delta = previous_snapshot.get("delta") if isinstance(previous_snapshot.get("delta"), dict) else {}
    delta_status = _safe_text(delta.get("status"))
    candidate_order = ("head", "baseline") if delta_status in {"initial", "unchanged", "changed"} else ("baseline", "head")
    for key in candidate_order:
        candidate = observation.get(key)
        if isinstance(candidate, dict) and _safe_text(candidate.get("sha")):
            return {
                "sha": _safe_text(candidate.get("sha")),
                "branch": _safe_text(candidate.get("branch")),
                "committed_at": candidate.get("committed_at"),
                "scanned_at": candidate.get("scanned_at") or previous_snapshot.get("scanned_at"),
            }
    return None


def _build_snapshot_delta(
    repo: str,
    *,
    scanned_at: str,
    previous_snapshot: Any,
    head: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    current_sha = _safe_text(head.get("sha"))
    previous_head = _previous_successful_head(previous_snapshot, repo)
    if not current_sha:
        return (
            previous_head,
            {
                "status": "unavailable",
                "from_sha": _safe_text((previous_head or {}).get("sha")),
                "to_sha": "",
                "commits": [],
                "files": [],
                "truncated": False,
                "message": "Current repository head is unavailable.",
            },
            [],
        )

    if not previous_head:
        baseline = {**head, "scanned_at": scanned_at}
        return (
            baseline,
            {
                "status": "initial",
                "from_sha": current_sha,
                "to_sha": current_sha,
                "commits": [],
                "files": [],
                "truncated": False,
                "message": "Initial Snapshot v2 baseline recorded.",
            },
            [],
        )

    previous_sha = _safe_text(previous_head.get("sha"))
    if previous_sha == current_sha:
        return (
            previous_head,
            {
                "status": "unchanged",
                "from_sha": previous_sha,
                "to_sha": current_sha,
                "commits": [],
                "files": [],
                "truncated": False,
                "message": "Repository head is unchanged since the previous successful refresh.",
            },
            [],
        )

    try:
        comparison = fetch_repo_compare(repo, previous_sha, current_sha)
    except GitHubRequestError as exc:
        comparison = {}
        compare_error = exc.kind
    else:
        compare_error = "unavailable" if not comparison else ""

    if not comparison:
        return (
            previous_head,
            {
                "status": "unavailable",
                "from_sha": previous_sha,
                "to_sha": current_sha,
                "commits": [],
                "files": [],
                "truncated": False,
                "message": "Repository changed, but the bounded GitHub comparison is unavailable.",
            },
            [f"delta: {compare_error}"],
        )

    return (
        previous_head,
        {
            "status": "changed",
            "from_sha": previous_sha,
            "to_sha": current_sha,
            "compare_status": comparison.get("compare_status"),
            "ahead_by": comparison.get("ahead_by"),
            "behind_by": comparison.get("behind_by"),
            "total_commits": comparison.get("total_commits"),
            "commits": comparison.get("commits") or [],
            "files": comparison.get("files") or [],
            "truncated": bool(comparison.get("truncated")),
            "html_url": comparison.get("html_url"),
            "message": "Repository changes observed since the previous successful refresh.",
        },
        [],
    )


def _snapshot_v2_sections(
    *,
    repo: str,
    scanned_at: str,
    previous_snapshot: Any,
    head: dict[str, Any],
    anchors: list[dict[str, Any]],
    repository: dict[str, Any],
    tree: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    summary: str,
    architecture_hints: list[str],
    keywords: list[str],
) -> tuple[dict[str, Any], list[str]]:
    current_head = {**head, "scanned_at": scanned_at} if head else {}
    baseline, delta, delta_errors = _build_snapshot_delta(
        repo,
        scanned_at=scanned_at,
        previous_snapshot=previous_snapshot,
        head=current_head,
    )
    return (
        {
            "observation": {
                "head": current_head or None,
                "baseline": baseline,
                "anchors": anchors,
                "repository": repository or None,
                "top_level_tree": tree,
                "recent_commits": commits,
                "manifests": manifests,
            },
            "interpretation": {
                "method": "deterministic_v1",
                "summary": summary,
                "architecture_hints": architecture_hints,
                "keywords": keywords,
            },
            "delta": delta,
        },
        delta_errors,
    )


def _repository_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    if not metadata:
        return {}
    return {
        "full_name": metadata.get("full_name"),
        "description": metadata.get("description"),
        "default_branch": metadata.get("default_branch"),
        "html_url": metadata.get("html_url"),
        "open_issues_count": metadata.get("open_issues_count"),
        "updated_at": metadata.get("updated_at"),
    }


def _fetch_basic_repo_sections(
    repo: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    metadata: dict[str, Any] = {}
    tree: list[dict[str, Any]] = []
    commits: list[dict[str, Any]] = []
    errors: list[str] = []
    for label, fetcher in (
        ("repository", lambda: fetch_repo_metadata(repo)),
        ("top_level_tree", lambda: fetch_repo_top_level_tree(repo)),
        ("recent_commits", lambda: fetch_repo_recent_commits(repo)),
    ):
        try:
            value = fetcher()
        except GitHubRequestError as exc:
            errors.append(f"{label}: {exc.kind}")
            value = {} if label == "repository" else []
        if label == "repository":
            metadata = value
        elif label == "top_level_tree":
            tree = value
        else:
            commits = value
    head, head_errors = _fetch_head(repo, _safe_text(metadata.get("default_branch")))
    return metadata, tree, commits, head, [*errors, *head_errors]


def _build_configured_project_repo_snapshot(
    project: dict[str, Any],
    *,
    repo: str,
    scanned_at: str,
    discovery: dict[str, Any],
    previous_snapshot: Any,
) -> dict[str, Any]:
    metadata, tree, commits, head, section_errors = _fetch_basic_repo_sections(repo)
    truth_map = discovery.get("truth_map") if isinstance(discovery.get("truth_map"), dict) else {}
    anchor_result = fetch_repo_truth_map_anchors(repo, truth_map.get("anchors") or [])
    anchors = anchor_result.get("anchors") if isinstance(anchor_result.get("anchors"), list) else []
    anchor_errors = anchor_result.get("errors") if isinstance(anchor_result.get("errors"), list) else []
    found_anchors = [anchor for anchor in anchors if anchor.get("found")]
    has_context = bool(metadata or tree or commits or found_anchors or head)

    readme = next((anchor for anchor in anchors if anchor.get("kind") == "readme" and anchor.get("found")), None)
    roadmap = next((anchor for anchor in anchors if anchor.get("kind") == "roadmap" and anchor.get("found")), None)
    manifests = [
        {
            "path": anchor.get("path"),
            "html_url": anchor.get("html_url"),
            "excerpt": anchor.get("excerpt", ""),
        }
        for anchor in anchors
        if anchor.get("found") and "manifest" in str(anchor.get("kind") or "")
    ]
    repository = _repository_summary(metadata)
    summary = _deterministic_summary(
        repository.get("description") or (readme or {}).get("excerpt"),
        project.get("description") if has_context else "",
    )
    architecture_hints = _architecture_hints(tree, manifests)
    keywords = _keywords(project, {"repository": repository}, tree, manifests)
    v2_sections, delta_errors = _snapshot_v2_sections(
        repo=repo,
        scanned_at=scanned_at,
        previous_snapshot=previous_snapshot,
        head=head,
        anchors=anchors,
        repository=repository,
        tree=tree,
        commits=commits,
        manifests=manifests,
        summary=summary,
        architecture_hints=architecture_hints,
        keywords=keywords,
    )
    all_errors = [*section_errors, *anchor_errors, *delta_errors]
    required_missing = [anchor.get("path") for anchor in anchors if anchor.get("required") and not anchor.get("found")]
    if not has_context:
        status = "failed"
        message = "Configured Truth Map snapshot could not load usable repository context."
    elif required_missing or all_errors:
        status = "partial"
        reasons: list[str] = []
        if required_missing:
            reasons.append(f"Required anchors missing: {', '.join(str(path) for path in required_missing)}.")
        if all_errors:
            reasons.append(f"Unavailable sections: {', '.join(str(item) for item in all_errors)}.")
        message = f"Configured Truth Map snapshot partially loaded. {' '.join(reasons)}".strip()
    else:
        status = "fresh"
        message = "Configured Truth Map snapshot generated successfully."
    github_status = "loaded" if status == "fresh" else ("partial" if has_context else "unreachable")

    return save_project_repo_snapshot(
        _safe_text(project.get("project_id")),
        {
            "status": status,
            "repo": repo,
            "scanned_at": scanned_at,
            "message": message,
            "summary": summary,
            "readme_found": bool(readme),
            "readme_path": (readme or {}).get("path", ""),
            "readme_excerpt": (readme or {}).get("excerpt", ""),
            "roadmap_found": bool(roadmap),
            "roadmap_path": (roadmap or {}).get("path", ""),
            "roadmap_excerpt": (roadmap or {}).get("excerpt", ""),
            "architecture_hints": architecture_hints,
            "keywords": keywords,
            "top_level_tree": tree,
            "recent_commits": commits,
            "manifests": manifests,
            "anchors": anchors,
            "discovery": {
                "mode": "configured",
                "config_status": "valid",
                "config_errors": [],
            },
            "github": {
                "status": github_status,
                "message": message,
                "repository": repository or None,
            },
            "optional_section_errors": all_errors,
            **v2_sections,
        },
    )


def _build_invalid_config_project_repo_snapshot(
    project: dict[str, Any],
    *,
    repo: str,
    scanned_at: str,
    discovery: dict[str, Any],
    previous_snapshot: Any,
) -> dict[str, Any]:
    metadata, tree, commits, head, section_errors = _fetch_basic_repo_sections(repo)
    repository = _repository_summary(metadata)
    has_context = bool(repository or tree or commits or head)
    status = "partial" if has_context else "failed"
    message = "Truth Map configuration is invalid; heuristic document discovery was not used."

    summary = _deterministic_summary(
        repository.get("description"),
        project.get("description") if has_context else "",
    )
    architecture_hints = _architecture_hints(tree, [])
    keywords = _keywords(project, {"repository": repository}, tree, [])
    v2_sections, delta_errors = _snapshot_v2_sections(
        repo=repo,
        scanned_at=scanned_at,
        previous_snapshot=previous_snapshot,
        head=head,
        anchors=[],
        repository=repository,
        tree=tree,
        commits=commits,
        manifests=[],
        summary=summary,
        architecture_hints=architecture_hints,
        keywords=keywords,
    )
    all_errors = [*section_errors, *delta_errors]
    if all_errors:
        message = f"{message} Unavailable sections: {', '.join(all_errors)}."

    return save_project_repo_snapshot(
        _safe_text(project.get("project_id")),
        {
            "status": status,
            "repo": repo,
            "scanned_at": scanned_at,
            "message": message,
            "summary": summary,
            "readme_found": False,
            "readme_path": "",
            "readme_excerpt": "",
            "roadmap_found": False,
            "roadmap_path": "",
            "roadmap_excerpt": "",
            "architecture_hints": architecture_hints,
            "keywords": keywords,
            "top_level_tree": tree,
            "recent_commits": commits,
            "manifests": [],
            "anchors": [],
            "discovery": {
                "mode": "configured",
                "config_status": "invalid",
                "config_errors": discovery.get("config_errors") or [],
            },
            "github": {
                "status": "partial" if has_context else "unreachable",
                "message": message,
                "repository": repository or None,
            },
            "optional_section_errors": all_errors,
            **v2_sections,
        },
    )


def build_light_project_repo_snapshot(project: dict[str, Any]) -> dict[str, Any]:
    project_id = _safe_text(project.get("project_id"))
    repo = normalize_repo_name(_safe_text(project.get("repo")))
    scanned_at = _utc_now_iso()
    discovery = resolve_project_truth_map(project)
    previous_snapshot = load_project_repo_snapshot(project_id, include_freshness=False)

    if not repo:
        v2_sections, _ = _snapshot_v2_sections(
            repo="",
            scanned_at=scanned_at,
            previous_snapshot=previous_snapshot,
            head={},
            anchors=[],
            repository={},
            tree=[],
            commits=[],
            manifests=[],
            summary="",
            architecture_hints=[],
            keywords=[],
        )
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
                "anchors": [],
                "discovery": {
                    "mode": discovery.get("mode"),
                    "config_status": discovery.get("config_status"),
                    "config_errors": discovery.get("config_errors") or [],
                },
                "github": {"status": "no_repo"},
                **v2_sections,
            },
        )

    if discovery.get("config_status") == "invalid":
        return _build_invalid_config_project_repo_snapshot(
            project,
            repo=repo,
            scanned_at=scanned_at,
            discovery=discovery,
            previous_snapshot=previous_snapshot,
        )
    if discovery.get("config_status") == "valid":
        return _build_configured_project_repo_snapshot(
            project,
            repo=repo,
            scanned_at=scanned_at,
            discovery=discovery,
            previous_snapshot=previous_snapshot,
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
    head, head_errors = _fetch_head(repo, _safe_text(repository.get("default_branch")))
    extra_errors.extend(head_errors)
    has_partial_context = bool(has_partial_context or head)
    summary = _deterministic_summary(
        repository.get("description") or readme.get("content"),
        project.get("description") if has_partial_context else "",
    )
    architecture_hints = _architecture_hints(tree, manifests)
    keywords = _keywords(project, github, tree, manifests)
    v2_sections, delta_errors = _snapshot_v2_sections(
        repo=repo,
        scanned_at=scanned_at,
        previous_snapshot=previous_snapshot,
        head=head,
        anchors=[],
        repository=repository,
        tree=tree,
        commits=commits,
        manifests=manifests,
        summary=summary,
        architecture_hints=architecture_hints,
        keywords=keywords,
    )
    extra_errors.extend(delta_errors)
    status, message = _status_from_github(github, repo, has_partial_context=has_partial_context)
    if extra_errors and status in {"fresh", "partial"}:
        status = "partial"
        message = f"{message} Some optional snapshot sections were unavailable: {', '.join(extra_errors)}."

    snapshot = {
        "status": status,
        "repo": repo,
        "scanned_at": scanned_at,
        "message": message,
        "summary": summary,
        "readme_found": bool(readme),
        "readme_path": readme.get("path") if readme else "",
        "readme_excerpt": _truncate(readme.get("content"), 1600) if readme else "",
        "roadmap_found": bool(roadmap),
        "roadmap_path": roadmap.get("path") if roadmap else "",
        "roadmap_excerpt": _truncate(roadmap.get("content"), 1600) if roadmap else "",
        "architecture_hints": architecture_hints,
        "keywords": keywords,
        "top_level_tree": tree,
        "recent_commits": commits,
        "manifests": manifests,
        "anchors": [],
        "discovery": {
            "mode": "heuristic",
            "config_status": "absent",
            "config_errors": [],
        },
        "github": {
            "status": github.get("status"),
            "message": github.get("message"),
            "repository": repository or None,
        },
        "optional_section_errors": extra_errors,
        **v2_sections,
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
