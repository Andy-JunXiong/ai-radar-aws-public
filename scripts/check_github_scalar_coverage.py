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

from app.services.canonical_scalar_resolver_service import (  # noqa: E402
    build_canonical_scalar_resolution,
)


DEFAULT_SIGNAL_FILES = (
    REPO_ROOT / "data" / "output" / "github_agent_signals.json",
    REPO_ROOT / "data" / "output" / "agent_watch_signals.json",
    REPO_ROOT / "data" / "output" / "collected_signals.json",
    REPO_ROOT / "data" / "output" / "signals.json",
)
CORE_SCALARS = ("stars", "license", "archived", "created_at", "updated_at")


@dataclass(frozen=True)
class GithubScalarCoverageRow:
    path: str
    index: int
    record_id: str
    title: str
    repo_name: str
    repo_url: str
    present_scalars: list[str]
    missing_scalars: list[str]
    scalar_resolution_total: int
    scalar_resolution_mismatch: int
    coverage_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "index": self.index,
            "record_id": self.record_id,
            "title": self.title,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "present_scalars": self.present_scalars,
            "missing_scalars": self.missing_scalars,
            "scalar_resolution_total": self.scalar_resolution_total,
            "scalar_resolution_mismatch": self.scalar_resolution_mismatch,
            "coverage_state": self.coverage_state,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("signals", "items", "records", "repos"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(record.get("metadata"))


def _repo_name(record: dict[str, Any], metadata: dict[str, Any]) -> str:
    return (
        _safe_text(metadata.get("repo_name"))
        or _safe_text(metadata.get("full_name"))
        or _safe_text(record.get("repo_name"))
        or _safe_text(record.get("title"))
    )


def _repo_url(record: dict[str, Any], metadata: dict[str, Any]) -> str:
    return (
        _safe_text(metadata.get("repo_url"))
        or _safe_text(record.get("url"))
        or _safe_text(record.get("link"))
        or _safe_text(record.get("source_url"))
    )


def _is_github_repo_record(record: dict[str, Any]) -> bool:
    metadata = _metadata(record)
    source = _safe_text(record.get("source")).lower()
    source_type = _safe_text(record.get("source_type")).lower()
    repo_name = _repo_name(record, metadata)
    repo_url = _repo_url(record, metadata).lower()
    return bool(
        "github" in source
        or "github" in source_type
        or "github.com/" in repo_url
        or _safe_text(metadata.get("repo_name"))
        or ("/" in repo_name and _has_value(metadata.get("repo_stars")))
    )


def _scalar_presence(record: dict[str, Any]) -> dict[str, bool]:
    metadata = _metadata(record)
    canonical_scalars = _as_dict(record.get("canonical_scalars") or metadata.get("canonical_scalars"))
    return {
        "stars": _has_value(
            canonical_scalars.get("stars")
            if "stars" in canonical_scalars
            else metadata.get("repo_stars")
        ),
        "license": _has_value(
            canonical_scalars.get("license")
            if "license" in canonical_scalars
            else metadata.get("license_spdx_id") or metadata.get("license")
        ),
        "archived": _has_value(
            canonical_scalars.get("archived")
            if "archived" in canonical_scalars
            else metadata.get("archived")
        ),
        "created_at": _has_value(
            canonical_scalars.get("created_at")
            if "created_at" in canonical_scalars
            else metadata.get("created_at") or record.get("published_at")
        ),
        "updated_at": _has_value(
            canonical_scalars.get("updated_at")
            if "updated_at" in canonical_scalars
            else metadata.get("updated_at")
        ),
    }


def _coverage_state(present_scalars: list[str], missing_scalars: list[str]) -> str:
    if not present_scalars:
        return "no_canonical_scalar_coverage"
    if not missing_scalars:
        return "complete_core_scalar_coverage"
    if {"stars", "created_at"}.issubset(set(present_scalars)):
        return "partial_historical_github_coverage"
    return "partial_scalar_coverage"


def _record_id(record: dict[str, Any], fallback: str) -> str:
    return _safe_text(record.get("signal_id")) or _safe_text(record.get("id")) or fallback


def _row_from_record(record: dict[str, Any], *, path: str, index: int) -> GithubScalarCoverageRow:
    metadata = _metadata(record)
    presence = _scalar_presence(record)
    present_scalars = [name for name in CORE_SCALARS if presence.get(name)]
    missing_scalars = [name for name in CORE_SCALARS if not presence.get(name)]
    resolution = build_canonical_scalar_resolution(record)
    resolution_summary = _as_dict(resolution.get("summary"))
    return GithubScalarCoverageRow(
        path=path,
        index=index,
        record_id=_record_id(record, f"{path}#{index}"),
        title=_safe_text(record.get("title")),
        repo_name=_repo_name(record, metadata),
        repo_url=_repo_url(record, metadata),
        present_scalars=present_scalars,
        missing_scalars=missing_scalars,
        scalar_resolution_total=int(resolution_summary.get("total") or 0),
        scalar_resolution_mismatch=int(resolution_summary.get("mismatch") or 0),
        coverage_state=_coverage_state(present_scalars, missing_scalars),
    )


def build_github_scalar_coverage_report(
    *,
    signal_files: list[Path],
    root: Path = REPO_ROOT,
    include_records: bool = True,
) -> dict[str, Any]:
    rows: list[GithubScalarCoverageRow] = []
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
        records = _records_from_payload(payload)
        github_records = [record for record in records if _is_github_repo_record(record)]
        file_record_counts[relative] = len(github_records)
        for index, record in enumerate(github_records):
            rows.append(_row_from_record(record, path=relative, index=index))

    coverage_counts = Counter(row.coverage_state for row in rows)
    missing_counts = Counter(
        scalar
        for row in rows
        for scalar in row.missing_scalars
    )
    present_counts = Counter(
        scalar
        for row in rows
        for scalar in row.present_scalars
    )
    rows_with_resolution = sum(1 for row in rows if row.scalar_resolution_total > 0)
    rows_with_mismatch = sum(1 for row in rows if row.scalar_resolution_mismatch > 0)

    report = {
        "report_boundary": {
            "mode": "read_only_advisory",
            "quality_boundary": (
                "Coverage gaps report missing canonical scalar metadata only; "
                "they are not source-truth or action-eligibility judgments."
            ),
        },
        "summary": {
            "files_scanned": files_scanned,
            "github_record_count": len(rows),
            "rows_with_scalar_resolution": rows_with_resolution,
            "rows_with_scalar_mismatch": rows_with_mismatch,
            "coverage_state_counts": dict(sorted(coverage_counts.items())),
            "present_scalar_counts": dict(sorted(present_counts.items())),
            "missing_scalar_counts": dict(sorted(missing_counts.items())),
            "file_record_counts": file_record_counts,
        },
    }
    if include_records:
        report["records"] = [row.to_dict() for row in rows]
    return report


def github_scalar_coverage_exit_code(report: dict[str, Any], *, fail_on_gaps: bool = False) -> int:
    if not fail_on_gaps:
        return 0
    counts = _as_dict(_as_dict(report.get("summary")).get("coverage_state_counts"))
    gap_count = sum(
        int(count or 0)
        for state, count in counts.items()
        if state != "complete_core_scalar_coverage"
    )
    return 1 if gap_count else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only GitHub canonical scalar coverage report for local signal outputs. "
            "It reports missing scalar metadata; it does not fetch GitHub or change verification gates."
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
        "--fail-on-gaps",
        action="store_true",
        help="Exit with code 1 when any GitHub record lacks complete core scalar coverage.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[github-scalar-coverage] scope: read-only local GitHub scalar coverage audit")
    print(f"[github-scalar-coverage] mode: {boundary['mode']}")
    print(f"[github-scalar-coverage] boundary: {boundary['quality_boundary']}")
    print(
        "[github-scalar-coverage] records: "
        f"files={summary['files_scanned']} github_records={summary['github_record_count']} "
        f"with_resolution={summary['rows_with_scalar_resolution']} "
        f"with_mismatch={summary['rows_with_scalar_mismatch']}"
    )
    print(
        "[github-scalar-coverage] coverage: "
        f"states={summary['coverage_state_counts']} "
        f"missing={summary['missing_scalar_counts']}"
    )
    for path, count in summary["file_record_counts"].items():
        print(f"[github-scalar-coverage] file: {path} github_records={count}")
    for record in report.get("records") or []:
        print(
            "- record: "
            f"path={record['path']} id={record['record_id']} repo={record['repo_name']} "
            f"state={record['coverage_state']} missing={record['missing_scalars']}"
        )


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    files = [Path(file) for file in args.files] if args.files else list(DEFAULT_SIGNAL_FILES)
    report = build_github_scalar_coverage_report(
        signal_files=files,
        root=root,
        include_records=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return github_scalar_coverage_exit_code(report, fail_on_gaps=args.fail_on_gaps)


if __name__ == "__main__":
    raise SystemExit(main())
