from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from app.project_registry import is_active_project
from app.services.github_project_reader import normalize_repo_name
from app.services.project_repo_snapshot_service import load_project_repo_snapshot


REVIEW_STATE_NEEDS_ATTENTION = "needs_attention"
REVIEW_STATE_CHANGED = "changed"
REVIEW_STATE_BASELINE = "baseline"
REVIEW_STATE_UNCHANGED = "unchanged"

_REVIEW_STATE_ORDER = {
    REVIEW_STATE_NEEDS_ATTENTION: 0,
    REVIEW_STATE_CHANGED: 1,
    REVIEW_STATE_BASELINE: 2,
    REVIEW_STATE_UNCHANGED: 3,
}
_UNHEALTHY_SNAPSHOT_STATUSES = {"partial", "stale", "failed", "missing", "not_connected"}


def _text(value: object) -> str:
    return str(value or "").strip()


def _number(value: object, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return max(0, int(value))
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return fallback


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _eligible_projects(projects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        project
        for project in projects
        if isinstance(project, dict)
        and is_active_project(project)
        and bool(normalize_repo_name(_text(project.get("repo"))))
    ]


def _review_classification(snapshot: dict[str, Any] | None) -> tuple[str, str]:
    if not snapshot:
        return REVIEW_STATE_NEEDS_ATTENTION, "No cached Light Snapshot is available."

    snapshot_status = _text(snapshot.get("status")).lower() or "missing"
    refresh = snapshot.get("refresh") if isinstance(snapshot.get("refresh"), dict) else {}
    if _text(refresh.get("last_attempt_status")).lower() == "failed":
        failure = refresh.get("last_failure") if isinstance(refresh.get("last_failure"), dict) else {}
        detail = _text(failure.get("message"))
        return (
            REVIEW_STATE_NEEDS_ATTENTION,
            f"Latest Light Snapshot refresh failed. {detail}".strip(),
        )

    if snapshot_status in _UNHEALTHY_SNAPSHOT_STATUSES:
        return REVIEW_STATE_NEEDS_ATTENTION, (
            _text(snapshot.get("message")) or f"Snapshot status is {snapshot_status}."
        )

    delta = snapshot.get("delta") if isinstance(snapshot.get("delta"), dict) else {}
    delta_status = _text(delta.get("status")).lower() or "unavailable"
    if delta_status == "changed":
        return REVIEW_STATE_CHANGED, _text(delta.get("message")) or "Repository changes were observed since baseline."
    if delta_status == "unchanged":
        return REVIEW_STATE_UNCHANGED, _text(delta.get("message")) or "Repository head is unchanged."
    if delta_status == "initial":
        return REVIEW_STATE_BASELINE, _text(delta.get("message")) or "Initial Snapshot v2 baseline is recorded."
    return REVIEW_STATE_NEEDS_ATTENTION, (
        _text(delta.get("message")) or "Repository delta is unavailable and cannot be treated as unchanged."
    )


def _review_item(project: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    payload = snapshot if isinstance(snapshot, dict) else {}
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    refresh = payload.get("refresh") if isinstance(payload.get("refresh"), dict) else {}
    last_failure = refresh.get("last_failure") if isinstance(refresh.get("last_failure"), dict) else {}
    commits = delta.get("commits") if isinstance(delta.get("commits"), list) else []
    files = delta.get("files") if isinstance(delta.get("files"), list) else []
    review_state, review_reason = _review_classification(snapshot)

    return {
        "project_id": _text(project.get("project_id")),
        "project_name": _text(project.get("name")) or _text(project.get("project_id")),
        "repo": normalize_repo_name(_text(project.get("repo"))),
        "snapshot_status": _text(payload.get("status")).lower() or "missing",
        "scanned_at": _text(payload.get("scanned_at")),
        "snapshot_message": _text(payload.get("message")),
        "delta_status": _text(delta.get("status")).lower() or "unavailable",
        "from_sha": _text(delta.get("from_sha")),
        "to_sha": _text(delta.get("to_sha")),
        "commit_count": _number(delta.get("total_commits"), len(commits)),
        "file_count": len(files),
        "delta_truncated": bool(delta.get("truncated")),
        "review_state": review_state,
        "review_reason": review_reason,
        "last_attempted_at": _text(refresh.get("last_attempted_at")),
        "last_attempt_status": _text(refresh.get("last_attempt_status")).lower(),
        "last_succeeded_at": _text(refresh.get("last_succeeded_at")),
        "last_failure_message": _text(last_failure.get("message")),
    }


def build_project_snapshot_change_review(
    projects: Iterable[dict[str, Any]],
    *,
    snapshot_loader: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    loader = snapshot_loader or load_project_repo_snapshot
    items = [
        _review_item(project, loader(_text(project.get("project_id"))))
        for project in _eligible_projects(projects)
    ]
    items.sort(
        key=lambda item: (
            _REVIEW_STATE_ORDER.get(_text(item.get("review_state")), 99),
            _text(item.get("project_name")).lower(),
            _text(item.get("project_id")),
        )
    )

    summary = {
        "total": len(items),
        "needs_attention": sum(item["review_state"] == REVIEW_STATE_NEEDS_ATTENTION for item in items),
        "changed": sum(item["review_state"] == REVIEW_STATE_CHANGED for item in items),
        "baseline": sum(item["review_state"] == REVIEW_STATE_BASELINE for item in items),
        "unchanged": sum(item["review_state"] == REVIEW_STATE_UNCHANGED for item in items),
        "failed": sum(
            item["snapshot_status"] == "failed" or item["last_attempt_status"] == "failed"
            for item in items
        ),
        "stale": sum(item["snapshot_status"] == "stale" for item in items),
        "partial": sum(item["snapshot_status"] == "partial" for item in items),
        "missing": sum(item["snapshot_status"] == "missing" for item in items),
    }
    return {
        "generated_at": _utc_now_iso(),
        "summary": summary,
        "items": items,
        "message": "project snapshot change review loaded successfully",
    }
