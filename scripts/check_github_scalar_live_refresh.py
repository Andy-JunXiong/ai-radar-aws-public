from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

repo_root_text = str(REPO_ROOT)
if repo_root_text not in sys.path:
    sys.path.insert(0, repo_root_text)

backend_root_text = str(BACKEND_ROOT)
if backend_root_text in sys.path:
    sys.path.remove(backend_root_text)
sys.path.insert(0, backend_root_text)

existing_app = sys.modules.get("app")
existing_app_file = Path(str(getattr(existing_app, "__file__", ""))).resolve() if existing_app else None
if existing_app_file and not str(existing_app_file).startswith(str(BACKEND_ROOT.resolve())):
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]

from scripts.check_github_scalar_coverage import (  # noqa: E402
    DEFAULT_SIGNAL_FILES,
    _is_github_repo_record,
    _metadata,
    _read_json,
    _records_from_payload,
    _relative_path,
    _repo_name,
    _repo_url,
    _safe_text,
    _scalar_presence,
)


FetchRepo = Callable[[str], dict[str, Any]]
CORE_SCALARS = ("stars", "license", "archived", "created_at", "updated_at")
GITHUB_API_BASE = "https://api.github.com"


@dataclass(frozen=True)
class GithubScalarLiveRefreshRow:
    path: str
    index: int
    record_id: str
    repo_name: str
    repo_url: str
    fetch_status: str
    local_scalars: dict[str, Any]
    fetched_scalars: dict[str, Any]
    would_add_scalars: list[str]
    would_update_scalars: list[str]
    scalar_conflicts: list[str]
    error_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "index": self.index,
            "record_id": self.record_id,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "fetch_status": self.fetch_status,
            "local_scalars": self.local_scalars,
            "fetched_scalars": self.fetched_scalars,
            "would_add_scalars": self.would_add_scalars,
            "would_update_scalars": self.would_update_scalars,
            "scalar_conflicts": self.scalar_conflicts,
            "error_type": self.error_type,
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _record_id(record: dict[str, Any], fallback: str) -> str:
    return _safe_text(record.get("signal_id")) or _safe_text(record.get("id")) or fallback


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _normalize_scalar_value(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).lower()


def _github_token() -> str:
    return (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("Github_token")
        or os.getenv("github_token")
        or os.getenv("GITHUB_API_TOKEN")
        or ""
    ).strip()


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Radar-GitHub-Scalar-Live-Refresh/0.1",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_github_repo(repo_name: str) -> dict[str, Any]:
    req = request.Request(
        f"{GITHUB_API_BASE}/repos/{repo_name}",
        headers=_github_headers(),
        method="GET",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _scalars_from_github_payload(payload: dict[str, Any]) -> dict[str, Any]:
    license_payload = payload.get("license") if isinstance(payload.get("license"), dict) else {}
    scalars: dict[str, Any] = {
        "stars": payload.get("stargazers_count"),
        "license": license_payload.get("spdx_id"),
        "archived": payload.get("archived"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }
    return {key: value for key, value in scalars.items() if _has_value(value)}


def _local_scalars(record: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(record)
    canonical_scalars = _as_dict(record.get("canonical_scalars") or metadata.get("canonical_scalars"))
    scalars: dict[str, Any] = {}
    sources = {
        "stars": canonical_scalars.get("stars") if "stars" in canonical_scalars else metadata.get("repo_stars"),
        "license": (
            canonical_scalars.get("license")
            if "license" in canonical_scalars
            else metadata.get("license_spdx_id") or metadata.get("license")
        ),
        "archived": (
            canonical_scalars.get("archived")
            if "archived" in canonical_scalars
            else metadata.get("archived")
        ),
        "created_at": (
            canonical_scalars.get("created_at")
            if "created_at" in canonical_scalars
            else metadata.get("created_at") or record.get("published_at")
        ),
        "updated_at": (
            canonical_scalars.get("updated_at")
            if "updated_at" in canonical_scalars
            else metadata.get("updated_at")
        ),
    }
    for key, value in sources.items():
        if _has_value(value):
            scalars[key] = value
    return scalars


def _record_needs_live_refresh(record: dict[str, Any]) -> bool:
    presence = _scalar_presence(record)
    return any(not presence.get(scalar) for scalar in CORE_SCALARS)


def _compare_scalars(local: dict[str, Any], fetched: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    would_add: list[str] = []
    would_update: list[str] = []
    conflicts: list[str] = []
    for scalar in CORE_SCALARS:
        fetched_value = fetched.get(scalar)
        local_value = local.get(scalar)
        if not _has_value(fetched_value):
            continue
        if not _has_value(local_value):
            would_add.append(scalar)
            continue
        if _normalize_scalar_value(local_value) != _normalize_scalar_value(fetched_value):
            would_update.append(scalar)
            conflicts.append(scalar)
    return would_add, would_update, conflicts


def _row_from_record(
    record: dict[str, Any],
    *,
    path: str,
    index: int,
    fetcher: FetchRepo,
) -> GithubScalarLiveRefreshRow:
    metadata = _metadata(record)
    repo_name = _repo_name(record, metadata)
    repo_url = _repo_url(record, metadata)
    local = _local_scalars(record)

    if not repo_name:
        return GithubScalarLiveRefreshRow(
            path=path,
            index=index,
            record_id=_record_id(record, f"{path}#{index}"),
            repo_name=repo_name,
            repo_url=repo_url,
            fetch_status="skipped_missing_repo_name",
            local_scalars=local,
            fetched_scalars={},
            would_add_scalars=[],
            would_update_scalars=[],
            scalar_conflicts=[],
            error_type="",
        )

    try:
        fetched = _scalars_from_github_payload(fetcher(repo_name))
    except error.HTTPError as exc:
        return GithubScalarLiveRefreshRow(
            path=path,
            index=index,
            record_id=_record_id(record, f"{path}#{index}"),
            repo_name=repo_name,
            repo_url=repo_url,
            fetch_status="fetch_failed",
            local_scalars=local,
            fetched_scalars={},
            would_add_scalars=[],
            would_update_scalars=[],
            scalar_conflicts=[],
            error_type=f"http_{exc.code}",
        )
    except Exception as exc:
        return GithubScalarLiveRefreshRow(
            path=path,
            index=index,
            record_id=_record_id(record, f"{path}#{index}"),
            repo_name=repo_name,
            repo_url=repo_url,
            fetch_status="fetch_failed",
            local_scalars=local,
            fetched_scalars={},
            would_add_scalars=[],
            would_update_scalars=[],
            scalar_conflicts=[],
            error_type=type(exc).__name__,
        )

    would_add, would_update, conflicts = _compare_scalars(local, fetched)
    fetch_status = "fetched_no_change"
    if would_add or would_update:
        fetch_status = "fetched_would_change"

    return GithubScalarLiveRefreshRow(
        path=path,
        index=index,
        record_id=_record_id(record, f"{path}#{index}"),
        repo_name=repo_name,
        repo_url=repo_url,
        fetch_status=fetch_status,
        local_scalars=local,
        fetched_scalars=fetched,
        would_add_scalars=would_add,
        would_update_scalars=would_update,
        scalar_conflicts=conflicts,
        error_type="",
    )


def _candidate_records(signal_files: list[Path], root: Path) -> list[tuple[str, int, dict[str, Any]]]:
    candidates: list[tuple[str, int, dict[str, Any]]] = []
    for raw_path in signal_files:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        relative = _relative_path(path, root)
        payload = _read_json(path)
        if payload is None:
            continue
        for index, record in enumerate(_records_from_payload(payload)):
            if not _is_github_repo_record(record):
                continue
            if not _record_needs_live_refresh(record):
                continue
            candidates.append((relative, index, record))
    return candidates


def build_github_scalar_live_refresh_report(
    *,
    signal_files: list[Path],
    root: Path = REPO_ROOT,
    max_records: int = 5,
    fetcher: FetchRepo = fetch_github_repo,
    include_records: bool = True,
) -> dict[str, Any]:
    limit = max(0, int(max_records))
    candidates = _candidate_records(signal_files, root)
    selected = candidates[:limit] if limit else []
    rows = [
        _row_from_record(record, path=path, index=index, fetcher=fetcher)
        for path, index, record in selected
    ]

    status_counts = Counter(row.fetch_status for row in rows)
    would_add_counts = Counter(scalar for row in rows for scalar in row.would_add_scalars)
    would_update_counts = Counter(scalar for row in rows for scalar in row.would_update_scalars)
    conflict_counts = Counter(scalar for row in rows for scalar in row.scalar_conflicts)
    error_counts = Counter(row.error_type for row in rows if row.error_type)

    report = {
        "report_boundary": {
            "mode": "read_only_live_fetch_dry_run",
            "write_boundary": "This script performs HTTP GET only; it does not rewrite records or backfill data.",
            "quality_boundary": (
                "Fetched scalar differences are refresh candidates, not source scoring, "
                "Project Takeaway gate logic, or action eligibility."
            ),
        },
        "summary": {
            "candidate_count": len(candidates),
            "fetched_record_count": len(rows),
            "max_records": limit,
            "fetch_status_counts": dict(sorted(status_counts.items())),
            "would_add_scalar_counts": dict(sorted(would_add_counts.items())),
            "would_update_scalar_counts": dict(sorted(would_update_counts.items())),
            "scalar_conflict_counts": dict(sorted(conflict_counts.items())),
            "error_counts": dict(sorted(error_counts.items())),
        },
    }
    if include_records:
        report["records"] = [row.to_dict() for row in rows]
    return report


def github_scalar_live_refresh_exit_code(report: dict[str, Any], *, fail_on_fetch_error: bool = False) -> int:
    if not fail_on_fetch_error:
        return 0
    error_counts = _as_dict(_as_dict(report.get("summary")).get("error_counts"))
    return 1 if any(int(count or 0) for count in error_counts.values()) else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only live GitHub scalar refresh prototype. "
            "It fetches a bounded number of GitHub repos and reports what would be added or updated."
        )
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root. Defaults to current checkout.")
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        help="Signal JSON file to scan. Can be passed multiple times. Defaults to local GitHub signal outputs.",
    )
    parser.add_argument("--max-records", type=int, default=5, help="Maximum GitHub repos to fetch. Defaults to 5.")
    parser.add_argument("--summary-only", action="store_true", help="Omit record rows from JSON output.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Report format.")
    parser.add_argument(
        "--fail-on-fetch-error",
        action="store_true",
        help="Exit with code 1 if any selected live fetch fails.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[github-scalar-live-refresh] scope: read-only live GitHub scalar refresh dry-run")
    print(f"[github-scalar-live-refresh] mode: {boundary['mode']}")
    print(f"[github-scalar-live-refresh] write-boundary: {boundary['write_boundary']}")
    print(f"[github-scalar-live-refresh] quality-boundary: {boundary['quality_boundary']}")
    print(
        "[github-scalar-live-refresh] records: "
        f"candidates={summary['candidate_count']} fetched={summary['fetched_record_count']} "
        f"max={summary['max_records']}"
    )
    print(f"[github-scalar-live-refresh] statuses: {summary['fetch_status_counts']}")
    print(f"[github-scalar-live-refresh] would-add: {summary['would_add_scalar_counts']}")
    print(f"[github-scalar-live-refresh] would-update: {summary['would_update_scalar_counts']}")
    print(f"[github-scalar-live-refresh] conflicts: {summary['scalar_conflict_counts']}")
    print(f"[github-scalar-live-refresh] errors: {summary['error_counts']}")
    for record in report.get("records") or []:
        print(
            "- record: "
            f"path={record['path']} id={record['record_id']} repo={record['repo_name']} "
            f"status={record['fetch_status']} add={record['would_add_scalars']} "
            f"update={record['would_update_scalars']} conflicts={record['scalar_conflicts']}"
        )


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    files = [Path(file) for file in args.files] if args.files else list(DEFAULT_SIGNAL_FILES)
    report = build_github_scalar_live_refresh_report(
        signal_files=files,
        root=root,
        max_records=args.max_records,
        include_records=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return github_scalar_live_refresh_exit_code(report, fail_on_fetch_error=args.fail_on_fetch_error)


if __name__ == "__main__":
    raise SystemExit(main())
