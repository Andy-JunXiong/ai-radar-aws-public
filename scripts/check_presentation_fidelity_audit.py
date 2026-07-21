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

from app.services.claim_extraction_service import extract_claims_from_insight  # noqa: E402
from app.services.claim_verification_service import verify_claims_against_evidence  # noqa: E402


DEFAULT_SIGNAL_FILES = (
    REPO_ROOT / "data" / "output" / "signals.json",
    BACKEND_ROOT / "data" / "signals.json",
)
DEFAULT_MANUAL_SESSIONS_DIR = BACKEND_ROOT / "data" / "manual_uploads" / "sessions"
INSIGHT_FIELDS = (
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
)
FIDELITY_STATES = (
    "limits_present_and_exceeded",
    "limits_present_and_preserved",
    "limits_absent_unknown",
    "limits_not_applicable",
)


@dataclass(frozen=True)
class PresentationFidelityRow:
    source: str
    path: str
    record_id: str
    signal_id: str
    signal_source: str
    generation_mode: str
    claim_count: int
    limits_state_counts: dict[str, int]
    exceeded_claim_count: int
    absent_unknown_claim_count: int
    not_applicable_claim_count: int
    preserved_claim_count: int
    exceeded_reason_counts: dict[str, int]
    coverage_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": self.path,
            "record_id": self.record_id,
            "signal_id": self.signal_id,
            "signal_source": self.signal_source,
            "generation_mode": self.generation_mode,
            "claim_count": self.claim_count,
            "limits_state_counts": self.limits_state_counts,
            "exceeded_claim_count": self.exceeded_claim_count,
            "absent_unknown_claim_count": self.absent_unknown_claim_count,
            "not_applicable_claim_count": self.not_applicable_claim_count,
            "preserved_claim_count": self.preserved_claim_count,
            "exceeded_reason_counts": self.exceeded_reason_counts,
            "coverage_state": self.coverage_state,
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


def _evidence_pack_from_record(record: dict[str, Any]) -> dict[str, Any]:
    evidence_pack = _as_dict(record.get("evidence_pack"))
    if evidence_pack:
        return evidence_pack
    return _as_dict(_as_dict(record.get("policy_metadata")).get("evidence_pack"))


def _record_signal_id(record: dict[str, Any], fallback: str) -> str:
    return (
        _safe_text(record.get("signal_id"))
        or _safe_text(record.get("id"))
        or _safe_text(record.get("session_id"))
        or _safe_text(record.get("manual_session_id"))
        or fallback
    )


def _claim_source_record(record: dict[str, Any]) -> dict[str, Any]:
    analysis = _as_dict(record.get("analysis"))
    if not analysis:
        return record

    claim_source = dict(record)
    for field in INSIGHT_FIELDS:
        if not _safe_text(claim_source.get(field)) and _safe_text(analysis.get(field)):
            claim_source[field] = analysis.get(field)
    if not _safe_text(claim_source.get("summary")) and _safe_text(analysis.get("summary")):
        claim_source["summary"] = analysis.get("summary")
    if not _safe_text(claim_source.get("topic")) and _safe_text(analysis.get("topic")):
        claim_source["topic"] = analysis.get("topic")
    return claim_source


def _has_insight_fields(record: dict[str, Any]) -> bool:
    claim_source = _claim_source_record(record)
    return any(_safe_text(claim_source.get(field)) for field in INSIGHT_FIELDS)


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(value or "missing" for value in values).items()))


def _limits_state(result: dict[str, Any]) -> str:
    fidelity = result.get("presentation_fidelity")
    if not isinstance(fidelity, dict):
        return "missing"
    state = _safe_text(fidelity.get("limits_state"))
    return state or "missing"


def _reason_codes(result: dict[str, Any]) -> list[str]:
    fidelity = result.get("presentation_fidelity")
    if not isinstance(fidelity, dict):
        return []
    raw_reasons = fidelity.get("reason_codes")
    if not isinstance(raw_reasons, list):
        return []
    return [_safe_text(reason) for reason in raw_reasons if _safe_text(reason)]


def _coverage_state(limits_state_counts: dict[str, int]) -> str:
    if limits_state_counts.get("limits_present_and_exceeded", 0) > 0:
        return "exceeded_limit_detected"
    if limits_state_counts.get("limits_absent_unknown", 0) > 0:
        return "coverage_gap_present"
    if limits_state_counts.get("limits_present_and_preserved", 0) > 0:
        return "source_limits_covered"
    if limits_state_counts.get("limits_not_applicable", 0) > 0:
        return "limits_not_applicable"
    return "no_auditable_claims"


def _row_from_record(
    *,
    source: str,
    path: Path,
    root: Path,
    record: dict[str, Any],
    fallback_id: str,
) -> PresentationFidelityRow | None:
    if not _has_insight_fields(record):
        return None

    evidence_pack = _evidence_pack_from_record(record)
    if not isinstance(evidence_pack.get("evidence_items"), list):
        return None

    claim_source = _claim_source_record(record)
    claims = extract_claims_from_insight(claim_source)
    if not claims:
        return None

    claim_results = verify_claims_against_evidence(claims, evidence_pack)
    limits_state_counts = Counter(_limits_state(result) for result in claim_results)
    exceeded_reason_counts: Counter[str] = Counter()
    for result in claim_results:
        if _limits_state(result) == "limits_present_and_exceeded":
            exceeded_reason_counts.update(_reason_codes(result))

    signal_id = _record_signal_id(record, fallback_id)
    counts = dict(sorted(limits_state_counts.items()))

    return PresentationFidelityRow(
        source=source,
        path=_relative_path(path, root),
        record_id=signal_id,
        signal_id=signal_id,
        signal_source=_safe_text(record.get("source")) or _safe_text(evidence_pack.get("source_type")),
        generation_mode=_safe_text(record.get("generation_mode")),
        claim_count=len(claim_results),
        limits_state_counts=counts,
        exceeded_claim_count=counts.get("limits_present_and_exceeded", 0),
        absent_unknown_claim_count=counts.get("limits_absent_unknown", 0),
        not_applicable_claim_count=counts.get("limits_not_applicable", 0),
        preserved_claim_count=counts.get("limits_present_and_preserved", 0),
        exceeded_reason_counts=dict(sorted(exceeded_reason_counts.items())),
        coverage_state=_coverage_state(counts),
    )


def scan_signal_file(path: Path, *, root: Path, source: str = "signal_file") -> list[PresentationFidelityRow]:
    payload = _read_json(path) if path.exists() else None
    if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
        records = payload["signals"]
    else:
        records = payload if isinstance(payload, list) else []

    rows: list[PresentationFidelityRow] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        row = _row_from_record(
            source=source,
            path=path,
            root=root,
            record=record,
            fallback_id=str(index + 1),
        )
        if row is not None:
            rows.append(row)
    return rows


def scan_manual_sessions_dir(path: Path, *, root: Path) -> list[PresentationFidelityRow]:
    if not path.exists():
        return []

    rows: list[PresentationFidelityRow] = []
    for file_path in sorted(path.glob("*.json")):
        if file_path.name == "index.json":
            continue
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        row = _row_from_record(
            source="manual_session",
            path=file_path,
            root=root,
            record=payload,
            fallback_id=file_path.stem,
        )
        if row is not None:
            rows.append(row)
    return rows


def summarize_rows(rows: list[PresentationFidelityRow]) -> dict[str, Any]:
    source_counts = Counter(row.source for row in rows)
    signal_source_counts = Counter(row.signal_source or "missing" for row in rows)
    generation_mode_counts = Counter(row.generation_mode or "missing" for row in rows)
    limits_state_counts: Counter[str] = Counter()
    exceeded_reason_counts: Counter[str] = Counter()
    coverage_state_counts: Counter[str] = Counter()

    for row in rows:
        limits_state_counts.update(row.limits_state_counts)
        exceeded_reason_counts.update(row.exceeded_reason_counts)
        coverage_state_counts[row.coverage_state] += 1

    state_counts = {state: limits_state_counts.get(state, 0) for state in FIDELITY_STATES}
    extra_state_counts = {
        key: value
        for key, value in sorted(limits_state_counts.items())
        if key not in FIDELITY_STATES
    }
    state_counts.update(extra_state_counts)

    return {
        "record_count": len(rows),
        "claim_count": sum(row.claim_count for row in rows),
        "limits_state_counts": state_counts,
        "exceeded_claim_count": state_counts.get("limits_present_and_exceeded", 0),
        "absent_unknown_claim_count": state_counts.get("limits_absent_unknown", 0),
        "not_applicable_claim_count": state_counts.get("limits_not_applicable", 0),
        "preserved_claim_count": state_counts.get("limits_present_and_preserved", 0),
        "coverage_gap_record_count": sum(1 for row in rows if row.absent_unknown_claim_count > 0),
        "exceeded_record_count": sum(1 for row in rows if row.exceeded_claim_count > 0),
        "source_counts": dict(sorted(source_counts.items())),
        "signal_source_counts": dict(sorted(signal_source_counts.items())),
        "generation_mode_counts": dict(sorted(generation_mode_counts.items())),
        "coverage_state_counts": dict(sorted(coverage_state_counts.items())),
        "exceeded_reason_counts": dict(sorted(exceeded_reason_counts.items())),
    }


def build_presentation_fidelity_audit_report(
    *,
    signal_files: list[Path] | None = None,
    manual_sessions_dir: Path = DEFAULT_MANUAL_SESSIONS_DIR,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    rows: list[PresentationFidelityRow] = []
    selected_signal_files = list(DEFAULT_SIGNAL_FILES) if signal_files is None else list(signal_files)
    for index, signal_file in enumerate(selected_signal_files):
        rows.extend(scan_signal_file(signal_file, root=root, source=f"signal_file_{index + 1}"))
    rows.extend(scan_manual_sessions_dir(manual_sessions_dir, root=root))

    return {
        "report_boundary": {
            "mode": "read_only",
            "writes_data": False,
            "regenerates_llm_output": False,
            "changes_project_takeaway_gate": False,
            "changes_source_scoring": False,
            "detects_hop_level_deletion": False,
            "interpretation": (
                "This report rebuilds claim extraction and claim verification from stored "
                "insight text plus stored evidence packs. It surfaces presentation-fidelity "
                "coverage and exceeded-limit downgrades only; limits_absent_unknown is a "
                "coverage gap, not a fidelity failure."
            ),
        },
        "paths": {
            "signal_files": [str(path) for path in selected_signal_files],
            "manual_sessions_dir": str(manual_sessions_dir),
        },
        "summary": summarize_rows(rows),
        "rows": [row.to_dict() for row in rows] if include_rows else [],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only presentation-fidelity audit. Rebuilds claim verification "
            "from local stored insight text and evidence packs."
        )
    )
    parser.add_argument(
        "--signal-file",
        action="append",
        default=[],
        help="Signal JSON file to scan. Repeat to include multiple files.",
    )
    parser.add_argument("--manual-sessions-dir", default=str(DEFAULT_MANUAL_SESSIONS_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def _signal_files_from_args(values: list[str]) -> list[Path] | None:
    files = [Path(value).resolve() for value in values if _safe_text(value)]
    return files or None


def _print_text_report(report: dict[str, Any], *, summary_only: bool = False) -> None:
    summary = report["summary"]
    state_counts = summary["limits_state_counts"]
    print("[presentation-fidelity] scope: read-only local audit", flush=True)
    print(
        "[presentation-fidelity] records: "
        f"{summary['record_count']} claims={summary['claim_count']} "
        f"exceeded={summary['exceeded_claim_count']} "
        f"absent_unknown={summary['absent_unknown_claim_count']} "
        f"not_applicable={summary['not_applicable_claim_count']} "
        f"preserved={summary['preserved_claim_count']}",
        flush=True,
    )
    print(
        "[presentation-fidelity] states: "
        + ", ".join(f"{key}={value}" for key, value in state_counts.items()),
        flush=True,
    )
    print(
        "[presentation-fidelity] record coverage: "
        f"coverage_gap_records={summary['coverage_gap_record_count']} "
        f"exceeded_records={summary['exceeded_record_count']} "
        f"coverage_states={summary['coverage_state_counts']}",
        flush=True,
    )
    if summary["exceeded_reason_counts"]:
        print(
            "[presentation-fidelity] exceeded reasons: "
            + ", ".join(f"{key}={value}" for key, value in summary["exceeded_reason_counts"].items()),
            flush=True,
        )
    if summary_only:
        return

    for row in report["rows"]:
        if row["exceeded_claim_count"] == 0 and row["absent_unknown_claim_count"] == 0:
            continue
        print(
            f"- {row['record_id']} coverage={row['coverage_state']} "
            f"claims={row['claim_count']} exceeded={row['exceeded_claim_count']} "
            f"absent_unknown={row['absent_unknown_claim_count']} "
            f"not_applicable={row['not_applicable_claim_count']} "
            f"preserved={row['preserved_claim_count']} path={row['path']}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    report = build_presentation_fidelity_audit_report(
        signal_files=_signal_files_from_args(args.signal_file),
        manual_sessions_dir=Path(args.manual_sessions_dir).resolve(),
        include_rows=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report, summary_only=args.summary_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
