from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.project_registry import is_active_project, list_active_projects
from app.services.github_project_reader import normalize_repo_name
from app.services.project_repo_snapshot_service import (
    get_or_refresh_project_repo_snapshot,
    load_project_repo_snapshot,
)


DEFAULT_REFRESH_INTERVAL_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: object) -> str:
    return str(value or "").strip()


def _parse_timestamp(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def project_snapshot_is_due(
    snapshot: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
) -> bool:
    if not snapshot:
        return True
    scanned_at = _parse_timestamp(snapshot.get("scanned_at"))
    if scanned_at is None:
        return True
    effective_now = (now or _utc_now()).astimezone(timezone.utc)
    return scanned_at <= effective_now - timedelta(hours=max(1, interval_hours))


def _eligible_projects(projects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            project
            for project in projects
            if isinstance(project, dict)
            and is_active_project(project)
            and bool(normalize_repo_name(_text(project.get("repo"))))
        ],
        key=lambda project: _text(project.get("project_id")),
    )


def refresh_due_project_snapshots(
    *,
    projects: Iterable[dict[str, Any]] | None = None,
    now: datetime | None = None,
    interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
    dry_run: bool = False,
) -> dict[str, Any]:
    started = (now or _utc_now()).astimezone(timezone.utc)
    candidates = _eligible_projects(projects if projects is not None else list_active_projects())
    items: list[dict[str, Any]] = []

    for project in candidates:
        project_id = _text(project.get("project_id"))
        repo = normalize_repo_name(_text(project.get("repo")))
        snapshot = load_project_repo_snapshot(project_id)
        due = project_snapshot_is_due(snapshot, now=started, interval_hours=interval_hours)
        if not due:
            items.append(
                {
                    "project_id": project_id,
                    "repo": repo,
                    "result": "skipped_fresh",
                    "scanned_at": _text((snapshot or {}).get("scanned_at")),
                }
            )
            continue

        if dry_run:
            items.append({"project_id": project_id, "repo": repo, "result": "due"})
            continue

        try:
            refreshed = get_or_refresh_project_repo_snapshot(project, force_refresh=True)
            refresh_state = refreshed.get("refresh") if isinstance(refreshed.get("refresh"), dict) else {}
            attempt_status = _text(refresh_state.get("last_attempt_status")) or _text(refreshed.get("status"))
            result = "failed" if attempt_status == "failed" else "refreshed"
            item = {
                "project_id": project_id,
                "repo": repo,
                "result": result,
                "snapshot_status": _text(refreshed.get("status")),
                "scanned_at": _text(refreshed.get("scanned_at")),
                "last_attempted_at": _text(refresh_state.get("last_attempted_at")),
            }
            if result == "failed":
                last_failure = refresh_state.get("last_failure") if isinstance(refresh_state.get("last_failure"), dict) else {}
                item["message"] = _text(last_failure.get("message")) or _text(refreshed.get("message"))
            items.append(item)
        except Exception as exc:
            items.append(
                {
                    "project_id": project_id,
                    "repo": repo,
                    "result": "failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

    counts = {
        result: sum(1 for item in items if item.get("result") == result)
        for result in ("refreshed", "skipped_fresh", "due", "failed")
    }
    return {
        "job": "project_snapshot_freshness_v1",
        "started_at": _utc_iso(started),
        "finished_at": _utc_iso(_utc_now()),
        "interval_hours": max(1, interval_hours),
        "dry_run": dry_run,
        "eligible_project_count": len(candidates),
        "counts": counts,
        "status": "failed" if counts["failed"] and counts["refreshed"] == 0 else "partial" if counts["failed"] else "ok",
        "items": items,
    }
