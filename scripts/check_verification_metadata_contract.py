from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.verification_metadata_reader import audit_verification_metadata_contract  # noqa: E402


DEFAULT_SIGNALS_FILE = BACKEND_ROOT / "data" / "signals.json"
DEFAULT_MANUAL_SESSIONS_DIR = BACKEND_ROOT / "data" / "manual_uploads" / "sessions"
DEFAULT_PROJECT_IMPROVEMENTS_DIR = BACKEND_ROOT / "data" / "project_improvements"
DEFAULT_SIGNAL_LIFECYCLE_DIR = BACKEND_ROOT / "data" / "signal_lifecycle"

SOURCE_CONTEXTS = {
    "insight_records": "insight_write",
    "project_takeaway": "project_takeaway_candidate",
    "signal_lifecycle": "lifecycle_support_snapshot",
}


@dataclass(frozen=True)
class VerificationContractAuditRow:
    source: str
    context: str
    path: str
    record_id: str
    signal_id: str
    project_id: str
    event_type: str
    verification_status: str
    evidence_level: str
    finding_count: int
    error_count: int
    warning_count: int
    contract_ok: bool
    findings: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "context": self.context,
            "path": self.path,
            "record_id": self.record_id,
            "signal_id": self.signal_id,
            "project_id": self.project_id,
            "event_type": self.event_type,
            "verification_status": self.verification_status,
            "evidence_level": self.evidence_level,
            "finding_count": self.finding_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "contract_ok": self.contract_ok,
            "findings": self.findings,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _verification_from_record(record: dict[str, Any]) -> dict[str, Any]:
    verification = _as_dict(record.get("verification"))
    if verification:
        return verification
    return _as_dict(_as_dict(record.get("policy_metadata")).get("verification"))


def _looks_like_insight_record(record: dict[str, Any]) -> bool:
    if _verification_from_record(record):
        return True
    if _safe_text(record.get("status")).lower() in {"analyzed", "completed"}:
        return True
    if _safe_text(record.get("analysis_status")).lower() == "completed":
        return True
    return any(
        _safe_text(record.get(key))
        for key in (
            "why_it_matters",
            "relevance_to_projects",
            "relevance_to_career",
            "synthesized_insight",
            "insight",
            "strategy",
        )
    )


def _record_signal_id(record: dict[str, Any], fallback: str) -> str:
    return (
        _safe_text(record.get("signal_id"))
        or _safe_text(record.get("id"))
        or _safe_text(record.get("session_id"))
        or _safe_text(record.get("manual_session_id"))
        or fallback
    )


def _row_from_audit(
    *,
    source: str,
    context: str,
    path: Path,
    root: Path,
    record_id: str,
    signal_id: str = "",
    project_id: str = "",
    event_type: str = "",
    verification: dict[str, Any] | None,
) -> VerificationContractAuditRow:
    report = audit_verification_metadata_contract(verification, context=context)
    normalized = report["normalized"]
    findings = [finding for finding in report["findings"] if isinstance(finding, dict)]
    severity_counts = Counter(_safe_text(finding.get("severity")) for finding in findings)
    return VerificationContractAuditRow(
        source=source,
        context=context,
        path=_relative_path(path, root),
        record_id=record_id,
        signal_id=signal_id,
        project_id=project_id,
        event_type=event_type,
        verification_status=_safe_text(normalized.get("verification_status")),
        evidence_level=_safe_text(normalized.get("evidence_level")),
        finding_count=len(findings),
        error_count=severity_counts.get("error", 0),
        warning_count=severity_counts.get("warning", 0),
        contract_ok=bool(report["contract_ok"]),
        findings=findings,
    )


def scan_insight_records(
    *,
    signals_file: Path,
    manual_sessions_dir: Path,
    root: Path,
) -> list[VerificationContractAuditRow]:
    rows: list[VerificationContractAuditRow] = []

    signals_payload = _read_json(signals_file) if signals_file.exists() else None
    signal_records = signals_payload if isinstance(signals_payload, list) else []
    for index, record in enumerate(signal_records):
        if not isinstance(record, dict) or not _looks_like_insight_record(record):
            continue
        signal_id = _record_signal_id(record, str(index + 1))
        rows.append(
            _row_from_audit(
                source="insight_records",
                context=SOURCE_CONTEXTS["insight_records"],
                path=signals_file,
                root=root,
                record_id=signal_id,
                signal_id=signal_id,
                verification=_verification_from_record(record),
            )
        )

    if not manual_sessions_dir.exists():
        return rows

    for file_path in sorted(manual_sessions_dir.glob("*.json")):
        if file_path.name == "index.json":
            continue
        payload = _read_json(file_path)
        if not isinstance(payload, dict) or not _looks_like_insight_record(payload):
            continue
        signal_id = _record_signal_id(payload, file_path.stem)
        rows.append(
            _row_from_audit(
                source="insight_records",
                context=SOURCE_CONTEXTS["insight_records"],
                path=file_path,
                root=root,
                record_id=signal_id,
                signal_id=signal_id,
                verification=_verification_from_record(payload),
            )
        )
    return rows


def scan_project_improvements_dir(path: Path, *, root: Path) -> list[VerificationContractAuditRow]:
    rows: list[VerificationContractAuditRow] = []
    if not path.exists():
        return rows

    for file_path in sorted(path.glob("*.json")):
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        project_id = _safe_text(payload.get("project_id")) or file_path.stem
        items = payload.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            signal_id = _safe_text(item.get("signal_id"))
            record_id = _safe_text(item.get("id")) or f"{project_id}:{signal_id or index}"
            rows.append(
                _row_from_audit(
                    source="project_takeaway",
                    context=SOURCE_CONTEXTS["project_takeaway"],
                    path=file_path,
                    root=root,
                    record_id=record_id,
                    signal_id=signal_id,
                    project_id=project_id,
                    verification=_as_dict(item.get("verification_metadata")),
                )
            )
    return rows


def scan_signal_lifecycle_dir(path: Path, *, root: Path) -> list[VerificationContractAuditRow]:
    rows: list[VerificationContractAuditRow] = []
    if not path.exists():
        return rows

    for file_path in sorted(path.glob("*.json")):
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        signal_id = _safe_text(payload.get("signal_id")) or file_path.stem
        events = payload.get("events")
        if not isinstance(events, list):
            continue
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            support = _as_dict(event.get("support"))
            if not _looks_like_verification_support(support):
                continue
            event_type = _safe_text(event.get("event_type"))
            record_id = _safe_text(event.get("event_id")) or f"{signal_id}:{event_type or index}:{index}"
            rows.append(
                _row_from_audit(
                    source="signal_lifecycle",
                    context=SOURCE_CONTEXTS["signal_lifecycle"],
                    path=file_path,
                    root=root,
                    record_id=record_id,
                    signal_id=signal_id,
                    event_type=event_type,
                    verification=support,
                )
            )
    return rows


def _looks_like_verification_support(support: dict[str, Any]) -> bool:
    if not support:
        return False
    return any(
        key in support
        for key in (
            "verification_status",
            "allowed_downstream_actions",
            "blocked_downstream_actions",
            "claim_support_summary",
        )
    )


def build_verification_contract_report(
    *,
    signals_file: Path = DEFAULT_SIGNALS_FILE,
    manual_sessions_dir: Path = DEFAULT_MANUAL_SESSIONS_DIR,
    project_improvements_dir: Path = DEFAULT_PROJECT_IMPROVEMENTS_DIR,
    signal_lifecycle_dir: Path = DEFAULT_SIGNAL_LIFECYCLE_DIR,
    sources: set[str] | None = None,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    selected_sources = sources or set(SOURCE_CONTEXTS)
    rows: list[VerificationContractAuditRow] = []

    if "insight_records" in selected_sources:
        rows.extend(
            scan_insight_records(
                signals_file=signals_file,
                manual_sessions_dir=manual_sessions_dir,
                root=root,
            )
        )
    if "project_takeaway" in selected_sources:
        rows.extend(scan_project_improvements_dir(project_improvements_dir, root=root))
    if "signal_lifecycle" in selected_sources:
        rows.extend(scan_signal_lifecycle_dir(signal_lifecycle_dir, root=root))

    return {
        "report_boundary": {
            "mode": "read_only",
            "audit_mode": "soft_report_only",
            "writes_data": False,
            "hard_enforcement": False,
            "interpretation": (
                "Use this report to inspect verification metadata contract shape only. "
                "It does not judge factual quality or change runtime gates."
            ),
        },
        "sources": sorted(selected_sources),
        "paths": {
            "signals_file": str(signals_file),
            "manual_sessions_dir": str(manual_sessions_dir),
            "project_improvements_dir": str(project_improvements_dir),
            "signal_lifecycle_dir": str(signal_lifecycle_dir),
        },
        "summary": summarize_rows(rows),
        "rows": [row.to_dict() for row in rows] if include_rows else [],
    }


def summarize_rows(rows: list[VerificationContractAuditRow]) -> dict[str, Any]:
    source_counts = Counter(row.source for row in rows)
    context_counts = Counter(row.context for row in rows)
    status_counts = Counter(row.verification_status or "missing" for row in rows)
    finding_code_counts: Counter[str] = Counter()
    for row in rows:
        for finding in row.findings:
            finding_code_counts.update([_safe_text(finding.get("code")) or "unknown"])

    return {
        "record_count": len(rows),
        "contract_ok_count": sum(1 for row in rows if row.contract_ok),
        "contract_error_count": sum(1 for row in rows if row.error_count > 0),
        "contract_warning_count": sum(1 for row in rows if row.warning_count > 0),
        "finding_count": sum(row.finding_count for row in rows),
        "error_count": sum(row.error_count for row in rows),
        "warning_count": sum(row.warning_count for row in rows),
        "source_counts": dict(sorted(source_counts.items())),
        "context_counts": dict(sorted(context_counts.items())),
        "verification_status_counts": dict(sorted(status_counts.items())),
        "finding_code_counts": dict(sorted(finding_code_counts.items())),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only verification metadata contract audit. It applies the "
            "runtime contract helper to local insight, Project Takeaway, and lifecycle records."
        )
    )
    parser.add_argument("--signals-file", default=str(DEFAULT_SIGNALS_FILE))
    parser.add_argument("--manual-sessions-dir", default=str(DEFAULT_MANUAL_SESSIONS_DIR))
    parser.add_argument("--project-improvements-dir", default=str(DEFAULT_PROJECT_IMPROVEMENTS_DIR))
    parser.add_argument("--signal-lifecycle-dir", default=str(DEFAULT_SIGNAL_LIFECYCLE_DIR))
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(SOURCE_CONTEXTS),
        default=[],
        help="Limit to one source. Repeat to include multiple sources.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only the aggregate summary and omit per-record findings.",
    )
    return parser.parse_args()


def _selected_sources(values: list[str]) -> set[str] | None:
    selected = {_safe_text(value) for value in values if _safe_text(value)}
    return selected or None


def _print_text_report(report: dict[str, Any], *, summary_only: bool = False) -> None:
    summary = report["summary"]
    print("[verification-contract] scope: read-only local contract audit", flush=True)
    print(f"[verification-contract] sources: {', '.join(report['sources'])}", flush=True)
    print(
        "[verification-contract] records: "
        f"{summary['record_count']} ok={summary['contract_ok_count']} "
        f"errors={summary['contract_error_count']} warnings={summary['contract_warning_count']}",
        flush=True,
    )
    print(
        "[verification-contract] findings: "
        f"total={summary['finding_count']} error={summary['error_count']} warning={summary['warning_count']}",
        flush=True,
    )
    if summary_only:
        return
    for row in report["rows"]:
        if row["finding_count"] == 0:
            continue
        print(
            f"- {row['source']} {row['record_id']} "
            f"status={row['verification_status'] or 'missing'} "
            f"errors={row['error_count']} warnings={row['warning_count']} path={row['path']}",
            flush=True,
        )
        for finding in row["findings"]:
            print(
                f"  - {finding.get('severity', 'unknown').upper()} "
                f"{finding.get('code', 'unknown')}: {finding.get('message', '')}",
                flush=True,
            )


def main() -> int:
    args = _parse_args()
    report = build_verification_contract_report(
        signals_file=Path(args.signals_file).resolve(),
        manual_sessions_dir=Path(args.manual_sessions_dir).resolve(),
        project_improvements_dir=Path(args.project_improvements_dir).resolve(),
        signal_lifecycle_dir=Path(args.signal_lifecycle_dir).resolve(),
        sources=_selected_sources(args.source),
        include_rows=not args.summary_only,
    )

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report, summary_only=args.summary_only)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
