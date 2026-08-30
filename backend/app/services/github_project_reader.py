from __future__ import annotations

import base64
import json
import os
import re
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

DEVELOPMENT_REALITY_ANCHOR_KINDS = {"current_state", "development_plan", "roadmap"}
_DEVELOPMENT_SECTION_ALIASES = {
    "completed": {
        "completed",
        "completed recently",
        "completed last 7 days",
        "done",
        "recently completed",
        "shipped",
    },
    "in_progress": {
        "active",
        "active work",
        "current state",
        "current status",
        "current work",
        "in progress",
        "in progress partial",
        "current milestone",
        "current product reality",
        "product state",
    },
    "active_plan": {
        "active development plan",
        "active plan",
        "current p0",
        "current p0 track",
        "current plan",
    },
    "blocked": {
        "blocked",
        "active risks and stop conditions",
        "blockers",
        "blockers and risks",
        "blockers risks",
        "incomplete",
        "incomplete or blocked",
        "risks and blockers",
    },
    "next_up": {
        "next",
        "next steps",
        "next up",
        "priorities",
        "next slice",
        "remaining todos",
        "upcoming",
    },
}
_DEVELOPMENT_SECTION_PREFIXES = {
    "completed": ("recently completed",),
    "in_progress": ("active slice",),
}
_MARKDOWN_HEADING_PATTERN = re.compile(
    r"^(?P<marks>#{1,6})[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$",
    re.MULTILINE,
)
_SOURCE_LABELED_DATE_PATTERN = re.compile(
    r"^(?:Last updated|Last verified|Sydney as-of date)[ \t]*:[ \t]*(?P<value>.+)$",
    re.IGNORECASE,
)
_SOURCE_UPDATED_DATE_PATTERN = re.compile(
    r"^Updated[ \t]+(?P<value>\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _normalize_development_heading(value: str) -> str:
    normalized = value.casefold().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _development_section_key(title: str) -> str | None:
    normalized = _normalize_development_heading(title)
    for key, aliases in _DEVELOPMENT_SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    for key, prefixes in _DEVELOPMENT_SECTION_PREFIXES.items():
        if any(normalized.startswith(f"{prefix} ") for prefix in prefixes):
            return key
    return None


def extract_development_sections(
    content: str,
    *,
    max_chars: int,
    source_kind: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Extract bounded source-reported development sections from Markdown."""
    if not content or max_chars <= 0:
        return {}, []

    headings = list(_MARKDOWN_HEADING_PATTERN.finditer(content))
    candidates: dict[str, list[str]] = {}
    for index, heading in enumerate(headings):
        key = _development_section_key(heading.group("title"))
        if not key:
            continue

        level = len(heading.group("marks"))
        end = len(content)
        for following in headings[index + 1 :]:
            if len(following.group("marks")) <= level:
                end = following.start()
                break

        body = content[heading.end() : end].strip()
        if body:
            normalized_title = _normalize_development_heading(heading.group("title"))
            is_prefixed_heading = any(
                normalized_title.startswith(f"{prefix} ")
                for prefix in _DEVELOPMENT_SECTION_PREFIXES.get(key, ())
            )
            if key == "completed" and is_prefixed_heading:
                body = f"### {heading.group('title').strip()}\n\n{body[:240].rstrip()}"
            candidates.setdefault(key, []).append(body)

    if source_kind == "development_plan" and "active_plan" not in candidates:
        for index, heading in enumerate(headings):
            normalized_title = _normalize_development_heading(heading.group("title"))
            if not re.match(r"^p\d+(?: |$)", normalized_title):
                continue
            level = len(heading.group("marks"))
            end = len(content)
            for following in headings[index + 1 :]:
                if len(following.group("marks")) <= level:
                    end = following.start()
                    break
            body = content[heading.end() : end].strip()
            if body:
                candidates["active_plan"] = [f"### {heading.group('title').strip()}\n\n{body}"]
                break

    ordered_keys = [key for key in _DEVELOPMENT_SECTION_ALIASES if key in candidates]
    if not ordered_keys:
        return {}, []

    sections: dict[str, str] = {}
    truncated: list[str] = []
    remaining_chars = max_chars
    for index, key in enumerate(ordered_keys):
        remaining_sections = len(ordered_keys) - index
        section_limit = max(1, remaining_chars // remaining_sections)
        original = "\n\n".join(candidates[key])
        value = original[:section_limit].rstrip()
        if value:
            sections[key] = value
            remaining_chars -= len(value)
        if len(original) > len(value):
            truncated.append(key)

    return sections, truncated


def extract_source_last_updated(content: str) -> str:
    for raw_line in (content or "").splitlines():
        line = raw_line.strip().replace("**", "").replace("`", "").strip("*_ ")
        for pattern in (_SOURCE_LABELED_DATE_PATTERN, _SOURCE_UPDATED_DATE_PATTERN):
            match = pattern.match(line)
            if match:
                return match.group("value").strip().strip("*_`.").strip()[:80]
    return ""


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


def fetch_repo_head(repo: str, *, default_branch: str = "") -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    if not normalized:
        return {}

    branch = str(default_branch or "").strip()
    if not branch:
        metadata = fetch_repo_metadata(normalized)
        branch = str(metadata.get("default_branch") or "").strip()
    if not branch:
        return {}

    payload = _github_request(f"/repos/{normalized}/commits/{parse.quote(branch, safe='')}")
    if not isinstance(payload, dict):
        return {}
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
    sha = str(payload.get("sha") or "").strip()
    if not sha:
        return {}
    return {
        "sha": sha,
        "branch": branch,
        "committed_at": author.get("date"),
        "html_url": payload.get("html_url"),
    }


def fetch_repo_compare(
    repo: str,
    base_sha: str,
    head_sha: str,
    *,
    commit_limit: int = 20,
    file_limit: int = 50,
) -> dict[str, Any]:
    normalized = normalize_repo_name(repo)
    base = str(base_sha or "").strip()
    head = str(head_sha or "").strip()
    if not normalized or not base or not head:
        return {}

    comparison = f"{parse.quote(base, safe='')}...{parse.quote(head, safe='')}"
    payload = _github_request(f"/repos/{normalized}/compare/{comparison}")
    if not isinstance(payload, dict):
        return {}

    raw_commits = payload.get("commits") if isinstance(payload.get("commits"), list) else []
    raw_files = payload.get("files") if isinstance(payload.get("files"), list) else []
    commits: list[dict[str, Any]] = []
    for item in raw_commits[: max(1, min(commit_limit, 50))]:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
        commits.append(
            {
                "sha": str(item.get("sha") or ""),
                "message": str(commit.get("message") or "").splitlines()[0][:180],
                "committed_at": author.get("date"),
                "html_url": item.get("html_url"),
            }
        )

    files: list[dict[str, Any]] = []
    for item in raw_files[: max(1, min(file_limit, 100))]:
        if not isinstance(item, dict):
            continue
        files.append(
            {
                "path": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
                "changes": item.get("changes"),
                "previous_path": item.get("previous_filename"),
                "html_url": item.get("blob_url"),
            }
        )

    total_commits = int(payload.get("total_commits") or len(raw_commits))
    return {
        "compare_status": payload.get("status"),
        "ahead_by": payload.get("ahead_by"),
        "behind_by": payload.get("behind_by"),
        "total_commits": total_commits,
        "commits": commits,
        "files": files,
        "truncated": total_commits > len(commits) or len(raw_files) > len(files),
        "html_url": payload.get("html_url"),
    }


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
        "size": payload.get("size"),
        "html_url": payload.get("html_url"),
        "content": _decode_github_content(payload.get("content"), payload.get("encoding")),
    }


def fetch_repo_truth_map_anchors(repo: str, anchors: list[dict[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    blocking_error: str | None = None

    for anchor in anchors:
        kind = str(anchor.get("kind") or "")
        path = str(anchor.get("path") or "")
        required = bool(anchor.get("required", False))
        content_mode = str(anchor.get("content_mode") or "excerpt")
        observation: dict[str, Any] = {
            "kind": kind,
            "path": path,
            "required": required,
            "content_mode": content_mode,
            "found": False,
        }

        if blocking_error:
            observation["error"] = blocking_error
            observations.append(observation)
            continue

        try:
            entry = fetch_repo_content_entry(repo, path)
        except GitHubRequestError as exc:
            observation["error"] = exc.kind
            errors.append(f"{path}: {exc.kind}")
            if exc.kind in {"rate_limited", "unreachable", "unauthorized"}:
                blocking_error = exc.kind
            observations.append(observation)
            continue

        if not entry:
            observations.append(observation)
            continue

        content = str(entry.get("content") or "")
        observation.update(
            {
                "path": entry.get("path") or path,
                "found": True,
                "sha": entry.get("sha"),
                "size": entry.get("size") if entry.get("size") is not None else len(content.encode("utf-8")),
                "html_url": entry.get("html_url"),
            }
        )
        if content_mode == "excerpt":
            max_chars = int(anchor.get("max_chars") or 1600)
            observation["excerpt"] = content[:max_chars]
            if kind in DEVELOPMENT_REALITY_ANCHOR_KINDS:
                development_sections, truncated_sections = extract_development_sections(
                    content,
                    max_chars=max_chars,
                    source_kind=kind,
                )
                source_last_updated = extract_source_last_updated(content)
                if development_sections:
                    observation["development_sections"] = development_sections
                if truncated_sections:
                    observation["development_sections_truncated"] = truncated_sections
                if source_last_updated:
                    observation["source_last_updated"] = source_last_updated
        observations.append(observation)

    return {"anchors": observations, "errors": errors}


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
