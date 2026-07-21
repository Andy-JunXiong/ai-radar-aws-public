from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from dotenv import load_dotenv

GITHUB_API_BASE = "https://api.github.com"
ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH)

ROADMAP_CANDIDATE_PATHS = [
    "ROADMAP.md",
    "roadmap.md",
    "docs/ROADMAP.md",
    "docs/roadmap.md",
    "planning/ROADMAP.md",
    "planning/roadmap.md",
]

MANIFEST_CANDIDATE_PATHS = [
    "package.json",
    "frontend/package.json",
    "pyproject.toml",
    "requirements.txt",
    "backend/requirements.txt",
    "Dockerfile",
]


class GitHubRequestError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def _github_token() -> str:
    return (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("Github_token")
        or os.getenv("github_token")
        or os.getenv("GITHUB_API_TOKEN")
        or ""
    ).strip()


def normalize_repo_name(repo: str) -> str:
    value = (repo or "").strip()
    if not value:
        return ""

    if value.startswith("https://github.com/"):
        value = value.replace("https://github.com/", "", 1)
    elif value.startswith("http://github.com/"):
        value = value.replace("http://github.com/", "", 1)

    return value.strip("/").replace(".git", "")


def _github_request(path: str, *, method: str = "GET", data: Any | None = None) -> Any:
    url = f"{GITHUB_API_BASE}{path}"
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
    req = request.Request(url, data=payload, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "ai-radar")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    token = _github_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with request.urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except error.HTTPError as exc:
        raw_payload = ""
        try:
            raw_payload = exc.read().decode("utf-8")
        except Exception:
            raw_payload = ""

        message = raw_payload
        try:
            parsed = json.loads(raw_payload) if raw_payload else {}
            if isinstance(parsed, dict) and parsed.get("message"):
                message = str(parsed["message"])
        except Exception:
            pass

        lowered = (message or "").lower()
        if exc.code == 403 and "rate limit" in lowered:
            raise GitHubRequestError(
                "rate_limited",
                "GitHub API rate limit exceeded. Add GITHUB_TOKEN to increase the limit.",
            ) from exc
        if exc.code == 404:
            raise GitHubRequestError("not_found", "GitHub resource not found.") from exc
        raise GitHubRequestError("http_error", message or f"GitHub request failed ({exc.code}).") from exc
    except Exception as exc:
        raise GitHubRequestError("unreachable", "GitHub could not be reached from the backend.") from exc


def _decode_github_content(content: str | None, encoding: str | None) -> str:
    if not content:
        return ""
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8")
        except Exception:
            return ""
    return content


def fetch_repo_metadata(repo: str) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return {}
    return _github_request(f"/repos/{normalized}")


def fetch_repo_readme(repo: str) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return {}

    try:
        payload = _github_request(f"/repos/{normalized}/readme")
        return {
            "path": payload.get("path") or "README.md",
            "sha": payload.get("sha"),
            "html_url": payload.get("html_url"),
            "content": _decode_github_content(payload.get("content"), payload.get("encoding")),
        }
    except GitHubRequestError as exc:
        if exc.kind == "not_found":
            return {}
        raise


def fetch_repo_roadmap(repo: str) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return {}

    for candidate in ROADMAP_CANDIDATE_PATHS:
        encoded_path = parse.quote(candidate)
        try:
            payload = _github_request(f"/repos/{normalized}/contents/{encoded_path}")
            content = _decode_github_content(payload.get("content"), payload.get("encoding"))
            if content.strip():
                return {
                    "path": payload.get("path") or candidate,
                    "html_url": payload.get("html_url"),
                    "content": content,
                }
        except GitHubRequestError as exc:
            if exc.kind == "not_found":
                continue
            raise

    return {}


def fetch_repo_open_issues(repo: str, limit: int = 8) -> list[dict[str, Any]]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return []

    try:
        payload = _github_request(f"/repos/{normalized}/issues?state=open&per_page={max(1, min(limit, 20))}")
    except GitHubRequestError as exc:
        if exc.kind == "not_found":
            return []
        raise

    if not isinstance(payload, list):
        return []

    issues: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("pull_request"):
            continue
        issues.append(
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "html_url": item.get("html_url"),
                "state": item.get("state"),
                "labels": [
                    label.get("name")
                    for label in (item.get("labels") or [])
                    if isinstance(label, dict) and label.get("name")
                ],
            }
        )

    return issues


def fetch_repo_top_level_tree(repo: str, limit: int = 40) -> list[dict[str, Any]]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return []

    try:
        payload = _github_request(f"/repos/{normalized}/contents")
    except GitHubRequestError as exc:
        if exc.kind == "not_found":
            return []
        raise

    if not isinstance(payload, list):
        return []

    entries: list[dict[str, Any]] = []
    for item in payload[: max(1, min(limit, 100))]:
        if not isinstance(item, dict):
            continue
        entries.append(
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "type": item.get("type"),
                "html_url": item.get("html_url"),
            }
        )
    return entries


def fetch_repo_recent_commits(repo: str, limit: int = 6) -> list[dict[str, Any]]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return []

    try:
        payload = _github_request(f"/repos/{normalized}/commits?per_page={max(1, min(limit, 20))}")
    except GitHubRequestError as exc:
        if exc.kind == "not_found":
            return []
        raise

    if not isinstance(payload, list):
        return []

    commits: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
        commits.append(
            {
                "sha": str(item.get("sha") or "")[:12],
                "message": str(commit.get("message") or "").splitlines()[0][:180],
                "committed_at": author.get("date"),
                "html_url": item.get("html_url"),
            }
        )
    return commits


def fetch_repo_manifest_files(repo: str) -> list[dict[str, Any]]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return []

    manifests: list[dict[str, Any]] = []
    for path in MANIFEST_CANDIDATE_PATHS:
        entry = fetch_repo_content_entry(normalized, path)
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        manifests.append(
            {
                "path": entry.get("path") or path,
                "html_url": entry.get("html_url"),
                "excerpt": content[:1200],
            }
        )
    return manifests


def fetch_repo_content_entry(repo: str, path: str, *, ref: str | None = None) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized or not path:
        return {}

    encoded_path = parse.quote(path)
    query = f"?ref={parse.quote(ref)}" if ref else ""
    try:
        payload = _github_request(f"/repos/{normalized}/contents/{encoded_path}{query}")
    except GitHubRequestError as exc:
        if exc.kind == "not_found":
            return {}
        raise

    if not isinstance(payload, dict):
        return {}

    return {
        "path": payload.get("path") or path,
        "sha": payload.get("sha"),
        "html_url": payload.get("html_url"),
        "content": _decode_github_content(payload.get("content"), payload.get("encoding")),
    }


def create_repo_branch(repo: str, *, base_branch: str, new_branch: str) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        raise GitHubRequestError("not_found", "Repository is not configured.")
    if not _github_token():
        raise GitHubRequestError("unauthorized", "GITHUB_TOKEN is required for GitHub write operations.")

    ref_payload = _github_request(f"/repos/{normalized}/git/ref/heads/{parse.quote(base_branch)}")
    base_sha = (((ref_payload or {}).get("object")) or {}).get("sha")
    if not base_sha:
        raise GitHubRequestError("not_found", f"Base branch not found: {base_branch}")

    try:
        return _github_request(
            f"/repos/{normalized}/git/refs",
            method="POST",
            data={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
        )
    except GitHubRequestError as exc:
        if exc.kind == "http_error" and "Reference already exists" in exc.message:
            return {"ref": f"refs/heads/{new_branch}", "object": {"sha": base_sha}}
        raise


def upsert_repo_file(
    repo: str,
    *,
    branch: str,
    path: str,
    content: str,
    message: str,
) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        raise GitHubRequestError("not_found", "Repository is not configured.")
    if not _github_token():
        raise GitHubRequestError("unauthorized", "GITHUB_TOKEN is required for GitHub write operations.")

    existing = fetch_repo_content_entry(normalized, path, ref=branch)
    request_payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if existing.get("sha"):
        request_payload["sha"] = existing["sha"]

    result = _github_request(
        f"/repos/{normalized}/contents/{parse.quote(path)}",
        method="PUT",
        data=request_payload,
    )
    if not isinstance(result, dict):
        return {}
    return result


def create_pull_request(
    repo: str,
    *,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        raise GitHubRequestError("not_found", "Repository is not configured.")
    if not _github_token():
        raise GitHubRequestError("unauthorized", "GITHUB_TOKEN is required for GitHub write operations.")

    try:
        result = _github_request(
            f"/repos/{normalized}/pulls",
            method="POST",
            data={
                "title": title,
                "head": head_branch,
                "base": base_branch,
                "body": body,
            },
        )
    except GitHubRequestError as exc:
        if exc.kind == "http_error" and "A pull request already exists" in exc.message:
            return {"html_url": "", "message": exc.message}
        raise

    return result if isinstance(result, dict) else {}


def fetch_project_github_context(repo: str) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return {
            "status": "no_repo",
            "repo": "",
            "repository": None,
            "readme": None,
            "roadmap": None,
            "issues": [],
            "message": "No GitHub repository is connected yet.",
        }

    metadata: dict[str, Any] = {}
    readme: dict[str, Any] = {}
    roadmap: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    status = "loaded"
    message = "GitHub project context loaded successfully."

    try:
        metadata = fetch_repo_metadata(normalized)
        readme = fetch_repo_readme(normalized)
        roadmap = fetch_repo_roadmap(normalized)
        issues = fetch_repo_open_issues(normalized)
    except GitHubRequestError as exc:
        if exc.kind == "rate_limited":
            status = "rate_limited"
            message = exc.message
        else:
            status = "unreachable"
            message = (
                "The repository is saved, but GitHub context could not be loaded right now. "
                "This can happen if the repo is private or temporarily unavailable."
            )
    else:
        if not metadata and not readme and not roadmap and not issues:
            status = "unreachable"
            message = (
                "The repository is saved, but GitHub context could not be loaded right now. "
                "This can happen if the repo is private or temporarily unavailable."
            )
        elif metadata or readme or issues:
            if not roadmap:
                status = "missing_roadmap"
                message = (
                    "GitHub is reachable and repository content is loading, but no roadmap file was found yet. "
                    "Add ROADMAP.md or docs/roadmap.md if you want roadmap content to appear here."
                )

    return {
        "status": status,
        "repo": normalized,
        "repository": {
            "full_name": metadata.get("full_name"),
            "description": metadata.get("description"),
            "default_branch": metadata.get("default_branch"),
            "html_url": metadata.get("html_url"),
            "open_issues_count": metadata.get("open_issues_count"),
            "updated_at": metadata.get("updated_at"),
        }
        if metadata
        else None,
        "readme": readme or None,
        "roadmap": roadmap or None,
        "issues": issues,
        "message": message,
    }
