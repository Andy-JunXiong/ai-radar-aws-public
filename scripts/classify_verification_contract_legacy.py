from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_verification_metadata_contract import (
    DEFAULT_MANUAL_SESSIONS_DIR,
    DEFAULT_PROJECT_IMPROVEMENTS_DIR,
    DEFAULT_SIGNAL_LIFECYCLE_DIR,
    DEFAULT_SIGNALS_FILE,
    build_verification_contract_report,
)


CLASSIFICATIONS = frozenset({"authoritative", "legacy", "fixture_demo", "manual_data"})


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def classify_contract_error_row(row: dict[str, Any]) -> dict[str, Any]:
    source = _safe_text(row.get("source"))
    path = _safe_text(row.get("path")).replace("\\", "/")
    record_id = _safe_text(row.get("record_id"))
    finding_codes = {
        _safe_text(finding.get("code"))
        for finding in row.get("findings") or []
        if isinstance(finding, dict)
    }

    if source == "insight_records" and "/manual_uploads/sessions/" in f"/{path}":
        classification = "manual_data"
        reason = "Historical user-selected manual session without the newer verification contract."
        disposition = "Preserve; regenerate or repair only after record-level human review."
    elif source == "insight_records" and path.endswith("backend/data/signals.json") and record_id.isdigit():
        classification = "fixture_demo"
        reason = "Numeric seed record in the local backend signals fixture file."
        disposition = "Keep outside authoritative migration metrics; do not backfill automatically."
    elif source == "project_takeaway" and "missing_verification_metadata" in finding_codes:
        classification = "legacy"
        reason = "Pre-contract Project Takeaway record with no verification metadata envelope."
        disposition = "Preserve legacy-read compatibility; require explicit migration review before repair."
    else:
        classification = "authoritative"
        reason = "Structured product record with verification metadata that is missing a narrower contract field."
        disposition = "Treat as authoritative local data; investigate a targeted repair separately."

    return {
        **row,
        "classification": classification,
        "classification_reason": reason,
        "recommended_disposition": disposition,
        "automatic_backfill_allowed": False,
    }


def build_legacy_classification_report(
    *,
    signals_file: Path = DEFAULT_SIGNALS_FILE,
    manual_sessions_dir: Path = DEFAULT_MANUAL_SESSIONS_DIR,
    project_improvements_dir: Path = DEFAULT_PROJECT_IMPROVEMENTS_DIR,
    signal_lifecycle_dir: Path = DEFAULT_SIGNAL_LIFECYCLE_DIR,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    contract_report = build_verification_contract_report(
        signals_file=signals_file,
        manual_sessions_dir=manual_sessions_dir,
        project_improvements_dir=project_improvements_dir,
        signal_lifecycle_dir=signal_lifecycle_dir,
        include_rows=True,
        root=root,
    )
    error_rows = [row for row in contract_report["rows"] if row.get("error_count", 0) > 0]
    rows = [classify_contract_error_row(row) for row in error_rows]
    counts = Counter(row["classification"] for row in rows)

    return {
        "report_boundary": {
            "mode": "read_only_legacy_classification",
            "writes_data": False,
            "automatic_backfill_allowed": False,
            "classification_set": sorted(CLASSIFICATIONS),
            "interpretation": (
                "Classification supports migration triage only. It does not reinterpret evidence, "
                "change verification status, or repair stored records."
            ),
        },
        "contract_audit_summary": contract_report["summary"],
        "summary": {
            "classified_error_count": len(rows),
            "classification_counts": {
                classification: counts.get(classification, 0)
                for classification in sorted(CLASSIFICATIONS)
            },
            "unclassified_count": sum(1 for row in rows if row["classification"] not in CLASSIFICATIONS),
            "automatic_backfill_allowed": False,
        },
        "rows": rows if include_rows else [],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only classification of verification contract errors.")
    parser.add_argument("--signals-file", default=str(DEFAULT_SIGNALS_FILE))
    parser.add_argument("--manual-sessions-dir", default=str(DEFAULT_MANUAL_SESSIONS_DIR))
    parser.add_argument("--project-improvements-dir", default=str(DEFAULT_PROJECT_IMPROVEMENTS_DIR))
    parser.add_argument("--signal-lifecycle-dir", default=str(DEFAULT_SIGNAL_LIFECYCLE_DIR))
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_legacy_classification_report(
        signals_file=Path(args.signals_file).resolve(),
        manual_sessions_dir=Path(args.manual_sessions_dir).resolve(),
        project_improvements_dir=Path(args.project_improvements_dir).resolve(),
        signal_lifecycle_dir=Path(args.signal_lifecycle_dir).resolve(),
        include_rows=not args.summary_only,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
