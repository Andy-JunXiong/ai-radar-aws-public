from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


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
    CORE_SCALARS,
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


LIVE_API_ONLY_SCALARS = ("license", "archived", "updated_at")


@dataclass(frozen=True)
class GithubScalarBackfillReadinessRow:
    path: str
    index: int
    record_id: str
    repo_name: str
    repo_url: str
    local_available_scalars: list[str]
    local_missing_scalars: list[str]
    local_standardization_scalars: list[str]
    live_api_required_scalars: list[str]
    refresh_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "index": self.index,
            "record_id": self.record_id,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "local_available_scalars": self.local_available_scalars,
            "local_missing_scalars": self.local_missing_scalars,
            "local_standardization_scalars": self.local_standardization_scalars,
            "live_api_required_scalars": self.live_api_required_scalars,
            "refresh_state": self.refresh_state,
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _record_id(record: dict[str, Any], fallback: str) -> str:
    return _safe_text(record.get("signal_id")) or _safe_text(record.get("id")) or fallback


def _has_canonical_scalars_map(record: dict[str, Any]) -> bool:
    metadata = _metadata(record)
    return isinstance(record.get("canonical_scalars"), dict) or isinstance(metadata.get("canonical_scalars"), dict)


def _refresh_state(
    *,
    repo_name: str,
    repo_url: str,
    local_available_scalars: list[str],
    local_missing_scalars: list[str],
    local_standardization_scalars: list[str],
    live_api_required_scalars: list[str],
) -> str:
    if not repo_name and "github.com/" not in repo_url.lower():
        return "not_refreshable_missing_repo_id"
    if not local_missing_scalars:
        return "already_complete"
    if live_api_required_scalars:
        return "needs_live_github_api"
    if local_standardization_scalars:
        return "local_standardization_only"
    if local_available_scalars:
        return "partial_local_only"
    return "no_local_scalar_data"


def _row_from_record(record: dict[str, Any], *, path: str, index: int) -> GithubScalarBackfillReadinessRow:
    metadata = _metadata(record)
    repo_name = _repo_name(record, metadata)
    repo_url = _repo_url(record, metadata)
    presence = _scalar_presence(record)
    local_available_scalars = [name for name in CORE_SCALARS if presence.get(name)]
    local_missing_scalars = [name for name in CORE_SCALARS if not presence.get(name)]
    has_canonical_map = _has_canonical_scalars_map(record)
    local_standardization_scalars = [] if has_canonical_map else list(local_available_scalars)
    live_api_required_scalars = [
        name
        for name in local_missing_scalars
        if name in LIVE_API_ONLY_SCALARS or name in {"stars", "created_at"}
    ]

    return GithubScalarBackfillReadinessRow(
        path=path,
        index=index,
        record_id=_record_id(record, f"{path}#{index}"),
        repo_name=repo_name,
        repo_url=repo_url,
        local_available_scalars=local_available_scalars,
        local_missing_scalars=local_missing_scalars,
        local_standardization_scalars=local_standardization_scalars,
        live_api_required_scalars=live_api_required_scalars,
        refresh_state=_refresh_state(
            repo_name=repo_name,
            repo_url=repo_url,
            local_available_scalars=local_available_scalars,
            local_missing_scalars=local_missing_scalars,
            local_standardization_scalars=local_standardization_scalars,
            live_api_required_scalars=live_api_required_scalars,
        ),
    )


def build_github_scalar_backfill_readiness_report(
    *,
    signal_files: list[Path],
    root: Path = REPO_ROOT,
    include_records: bool = True,
) -> dict[str, Any]:
    rows: list[GithubScalarBackfillReadinessRow] = []
    file_record_counts: dict[str, int] = {}
    files_scanned = 0

    for raw_path in signal_files:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        relative = _relative_path(path, root)
        payload = _read_json(path)
        if payload is None:
            file_record_counts[relative] = 0
            continue
        files_scanned += 1
        github_records = [
            record
            for record in _records_from_payload(payload)
            if _is_github_repo_record(record)
        ]
        file_record_counts[relative] = len(github_records)
        for index, record in enumerate(github_records):
            rows.append(_row_from_record(record, path=relative, index=index))

    refresh_state_counts = Counter(row.refresh_state for row in rows)
    local_standardization_counts = Counter(
        scalar
        for row in rows
        for scalar in row.local_standardization_scalars
    )
    live_api_required_counts = Counter(
        scalar
        for row in rows
        for scalar in row.live_api_required_scalars
    )
    local_available_counts = Counter(
        scalar
        for row in rows
        for scalar in row.local_available_scalars
    )

    report = {
        "report_boundary": {
            "mode": "read_only_dry_run",
            "write_boundary": "This script does not fetch GitHub, rewrite records, or backfill data.",
            "quality_boundary": (
                "Backfill readiness is metadata coverage only; it is not source-truth, "
                "source-quality, or action-eligibility judgment."
            ),
        },
        "summary": {
            "files_scanned": files_scanned,
            "github_record_count": len(rows),
            "refresh_state_counts": dict(sorted(refresh_state_counts.items())),
            "local_available_scalar_counts": dict(sorted(local_available_counts.items())),
            "local_standardization_scalar_counts": dict(sorted(local_standardization_counts.items())),
            "live_api_required_scalar_counts": dict(sorted(live_api_required_counts.items())),
            "file_record_counts": file_record_counts,
        },
    }
    if include_records:
        report["records"] = [row.to_dict() for row in rows]
    return report


def github_scalar_backfill_readiness_exit_code(report: dict[str, Any], *, fail_on_live_required: bool = False) -> int:
    if not fail_on_live_required:
        return 0
    live_counts = _as_dict(_as_dict(report.get("summary")).get("live_api_required_scalar_counts"))
    return 1 if any(int(count or 0) for count in live_counts.values()) else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only dry-run for GitHub scalar backfill readiness. "
            "It classifies local standardization opportunities versus fields that require live GitHub API refresh."
        )
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root. Defaults to current checkout.")
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        help="Signal JSON file to scan. Can be passed multiple times. Defaults to local GitHub signal outputs.",
    )
    parser.add_argument("--summary-only", action="store_true", help="Omit record rows from JSON output.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Report format.")
    parser.add_argument(
        "--fail-on-live-required",
        action="store_true",
        help="Exit with code 1 when any scalar would require live GitHub API refresh.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[github-scalar-backfill] scope: read-only GitHub scalar backfill readiness dry-run")
    print(f"[github-scalar-backfill] mode: {boundary['mode']}")
    print(f"[github-scalar-backfill] write-boundary: {boundary['write_boundary']}")
    print(f"[github-scalar-backfill] quality-boundary: {boundary['quality_boundary']}")
    print(
        "[github-scalar-backfill] records: "
        f"files={summary['files_scanned']} github_records={summary['github_record_count']}"
    )
    print(
        "[github-scalar-backfill] states: "
        f"{summary['refresh_state_counts']}"
    )
    print(
        "[github-scalar-backfill] local-standardization: "
        f"{summary['local_standardization_scalar_counts']}"
    )
    print(
        "[github-scalar-backfill] live-api-required: "
        f"{summary['live_api_required_scalar_counts']}"
    )
    for path, count in summary["file_record_counts"].items():
        print(f"[github-scalar-backfill] file: {path} github_records={count}")
    for record in report.get("records") or []:
        print(
            "- record: "
            f"path={record['path']} id={record['record_id']} repo={record['repo_name']} "
            f"state={record['refresh_state']} "
            f"local={record['local_standardization_scalars']} "
            f"live={record['live_api_required_scalars']}"
        )


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    files = [Path(file) for file in args.files] if args.files else list(DEFAULT_SIGNAL_FILES)
    report = build_github_scalar_backfill_readiness_report(
        signal_files=files,
        root=root,
        include_records=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return github_scalar_backfill_readiness_exit_code(
        report,
        fail_on_live_required=args.fail_on_live_required,
    )


if __name__ == "__main__":
    raise SystemExit(main())
