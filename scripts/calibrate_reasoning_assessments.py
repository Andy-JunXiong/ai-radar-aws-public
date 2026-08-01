from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.reasoning_assessment_service import (  # noqa: E402
    ASSESSMENT_EFFECT,
    ReasoningAssessmentContractError,
    VERDICTS,
    validate_reasoning_assessment,
)


DEFAULT_PROJECT_IMPROVEMENTS_DIR = BACKEND_ROOT / "data" / "project_improvements"
CALIBRATION_LABEL_VERDICTS = frozenset(VERDICTS)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def load_calibration_labels(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = _read_json(path)
    rows = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}

    labels: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        assessment_id = _safe_text(row.get("assessment_id"))
        expected_verdict = _safe_text(row.get("expected_verdict"))
        if not assessment_id or expected_verdict not in CALIBRATION_LABEL_VERDICTS:
            continue
        labels[assessment_id] = {
            "expected_verdict": expected_verdict,
            "reviewer_note_present": bool(_safe_text(row.get("reviewer_note"))),
        }
    return labels


def scan_reasoning_assessments(
    project_improvements_dir: Path,
    *,
    labels: dict[str, dict[str, Any]] | None = None,
    root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    labels = labels or {}
    if not project_improvements_dir.exists():
        return rows

    for file_path in sorted(project_improvements_dir.glob("*.json")):
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
            assessment = item.get("reasoning_assessment")
            if not isinstance(assessment, dict):
                continue

            assessment_id = _safe_text(assessment.get("assessment_id"))
            contract_error = ""
            try:
                validate_reasoning_assessment(assessment)
            except ReasoningAssessmentContractError as exc:
                contract_error = exc.code

            label = labels.get(assessment_id, {})
            rows.append(
                {
                    "path": _relative_path(file_path, root),
                    "project_id": project_id,
                    "record_id": _safe_text(item.get("id")) or f"{project_id}:{index}",
                    "signal_id": _safe_text(item.get("signal_id")),
                    "assessment_id": assessment_id,
                    "verdict": _safe_text(assessment.get("verdict")),
                    "effect": _safe_text(assessment.get("effect")),
                    "model_id": _safe_text(
                        (assessment.get("produced_by_model") or {}).get("model_id")
                        if isinstance(assessment.get("produced_by_model"), dict)
                        else ""
                    ),
                    "limitation_count": len(assessment.get("limitations") or [])
                    if isinstance(assessment.get("limitations"), list)
                    else 0,
                    "contract_ok": not contract_error,
                    "contract_error": contract_error,
                    "expected_verdict": _safe_text(label.get("expected_verdict")),
                    "reviewer_note_present": bool(label.get("reviewer_note_present")),
                }
            )
    return rows


def summarize_reasoning_assessments(
    rows: list[dict[str, Any]],
    *,
    minimum_per_verdict: int = 1,
) -> dict[str, Any]:
    verdict_counts = Counter(_safe_text(row.get("verdict")) or "missing" for row in rows)
    valid_rows = [row for row in rows if row.get("contract_ok")]
    labeled_rows = [row for row in valid_rows if _safe_text(row.get("expected_verdict"))]
    pass_rows = [row for row in labeled_rows if row.get("verdict") == "pass"]
    unsafe_pass_rows = [row for row in pass_rows if row.get("expected_verdict") != "pass"]
    mismatch_rows = [row for row in labeled_rows if row.get("verdict") != row.get("expected_verdict")]
    abstention_count = verdict_counts.get("needs_human_judgment", 0)
    coverage_gaps = {
        verdict: max(0, minimum_per_verdict - verdict_counts.get(verdict, 0))
        for verdict in sorted(VERDICTS)
    }

    return {
        "attached_assessment_count": len(rows),
        "contract_valid_count": len(valid_rows),
        "contract_error_count": len(rows) - len(valid_rows),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "minimum_per_verdict": minimum_per_verdict,
        "coverage_gaps": coverage_gaps,
        "coverage_complete": not any(coverage_gaps.values()),
        "abstention_count": abstention_count,
        "abstention_rate": round(abstention_count / len(valid_rows), 4) if valid_rows else None,
        "human_labeled_count": len(labeled_rows),
        "verdict_mismatch_count": len(mismatch_rows),
        "verdict_mismatch_rate": round(len(mismatch_rows) / len(labeled_rows), 4) if labeled_rows else None,
        "labeled_pass_count": len(pass_rows),
        "unsafe_pass_count": len(unsafe_pass_rows),
        "unsafe_pass_rate": round(len(unsafe_pass_rows) / len(pass_rows), 4) if pass_rows else None,
        "false_positive_measurement_available": bool(pass_rows),
        "runtime_gate_change_allowed": False,
    }


def build_reasoning_assessment_calibration_report(
    *,
    project_improvements_dir: Path = DEFAULT_PROJECT_IMPROVEMENTS_DIR,
    labels_file: Path | None = None,
    minimum_per_verdict: int = 1,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    labels = load_calibration_labels(labels_file)
    rows = scan_reasoning_assessments(
        project_improvements_dir,
        labels=labels,
        root=root,
    )
    summary = summarize_reasoning_assessments(rows, minimum_per_verdict=minimum_per_verdict)
    return {
        "report_boundary": {
            "mode": "read_only_calibration",
            "writes_data": False,
            "effect_required": ASSESSMENT_EFFECT,
            "runtime_gate_change_allowed": False,
            "interpretation": (
                "This report measures attached reviewer-advisory assessments only. "
                "It does not generate samples, change verification status, or alter downstream eligibility."
            ),
        },
        "paths": {
            "project_improvements_dir": str(project_improvements_dir),
            "labels_file": str(labels_file) if labels_file else "",
        },
        "summary": summary,
        "rows": rows if include_rows else [],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only calibration report for attached reasoning assessments.")
    parser.add_argument("--project-improvements-dir", default=str(DEFAULT_PROJECT_IMPROVEMENTS_DIR))
    parser.add_argument("--labels-file")
    parser.add_argument("--minimum-per-verdict", type=int, default=1)
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_reasoning_assessment_calibration_report(
        project_improvements_dir=Path(args.project_improvements_dir).resolve(),
        labels_file=Path(args.labels_file).resolve() if args.labels_file else None,
        minimum_per_verdict=max(1, args.minimum_per_verdict),
        include_rows=not args.summary_only,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
