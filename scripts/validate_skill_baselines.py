from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_input_text_analyze_golden_baseline import (  # noqa: E402
    DEFAULT_BASELINE_PATH as INPUT_TEXT_ANALYZE_BASELINE_PATH,
    evaluate_baseline as evaluate_input_text_analyze_baseline,
)


UTIL_JSON_REPAIR_BASELINE_PATH = (
    REPO_ROOT / "docs" / "notes" / "baselines" / "util-json-repair-golden-cases.json"
)
UTIL_JSON_REPAIR_REQUIRED_EDGE_CASES = {
    "trailing_comma",
    "missing_closing_brace",
    "fenced_markdown",
    "commentary_before_after_json",
    "partially_truncated_json",
    "wrong_quote_style",
    "bom_encoding_noise",
    "extra_and_missing_keys",
}


@dataclass(frozen=True)
class SkillBaselineFinding:
    code: str
    severity: str
    skill_name: str
    case_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "skill_name": self.skill_name,
            "case_id": self.case_id,
            "message": self.message,
        }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_case_id(case: dict[str, Any]) -> str:
    return str(case.get("id") or "<missing-case-id>")


def _finding(
    *,
    code: str,
    skill_name: str,
    message: str,
    case_id: str = "<baseline>",
) -> SkillBaselineFinding:
    return SkillBaselineFinding(
        code=code,
        severity="error",
        skill_name=skill_name,
        case_id=case_id,
        message=message,
    )


def evaluate_util_json_repair_baseline(
    path: Path = UTIL_JSON_REPAIR_BASELINE_PATH,
) -> dict[str, Any]:
    skill_name = "util-json-repair"
    baseline = _load_json(path)
    findings: list[SkillBaselineFinding] = []

    expected_metadata = {
        "baseline_id": "util-json-repair-curated-goldens-v0",
        "skill_name": skill_name,
        "skill_version": "v1",
        "baseline_type": "hand_constructed",
    }
    for key, expected_value in expected_metadata.items():
        if baseline.get(key) != expected_value:
            findings.append(
                _finding(
                    code=f"metadata_{key}_mismatch",
                    skill_name=skill_name,
                    message=f"Baseline metadata {key} must be {expected_value!r}.",
                )
            )

    source_note = baseline.get("source_note")
    if not isinstance(source_note, str) or "not production artifacts" not in source_note:
        findings.append(
            _finding(
                code="missing_non_production_source_note",
                skill_name=skill_name,
                message=(
                    "Baseline source_note must state that curated cases are not "
                    "production artifacts."
                ),
            )
        )

    cases = baseline.get("cases")
    if not isinstance(cases, list):
        cases = []
        findings.append(
            _finding(
                code="cases_not_list",
                skill_name=skill_name,
                message="Baseline cases must be a list.",
            )
        )

    edge_cases = {
        case.get("edge_case")
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("edge_case"), str)
    }
    if edge_cases != UTIL_JSON_REPAIR_REQUIRED_EDGE_CASES:
        missing = sorted(UTIL_JSON_REPAIR_REQUIRED_EDGE_CASES - edge_cases)
        extra = sorted(edge_cases - UTIL_JSON_REPAIR_REQUIRED_EDGE_CASES)
        findings.append(
            _finding(
                code="edge_case_coverage_mismatch",
                skill_name=skill_name,
                message=f"Missing edge cases: {missing}; unexpected edge cases: {extra}.",
            )
        )

    seen_ids: set[str] = set()
    case_reports: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            findings.append(
                _finding(
                    code="case_not_object",
                    skill_name=skill_name,
                    message="Each baseline case must be an object.",
                )
            )
            continue

        case_id = _safe_case_id(case)
        case_findings: list[SkillBaselineFinding] = []
        if case_id in seen_ids:
            case_findings.append(
                _finding(
                    code="duplicate_case_id",
                    skill_name=skill_name,
                    case_id=case_id,
                    message="Case ids must be unique.",
                )
            )
        seen_ids.add(case_id)

        raw_text = case.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            case_findings.append(
                _finding(
                    code="invalid_raw_text",
                    skill_name=skill_name,
                    case_id=case_id,
                    message="raw_text must be a non-empty string.",
                )
            )

        requested_keys = case.get("requested_keys")
        expected_json = case.get("expected_json")
        if (
            not isinstance(requested_keys, list)
            or not requested_keys
            or any(not isinstance(key, str) or not key.strip() for key in requested_keys)
        ):
            case_findings.append(
                _finding(
                    code="invalid_requested_keys",
                    skill_name=skill_name,
                    case_id=case_id,
                    message="requested_keys must be a non-empty list of strings.",
                )
            )
        elif not isinstance(expected_json, dict):
            case_findings.append(
                _finding(
                    code="invalid_expected_json",
                    skill_name=skill_name,
                    case_id=case_id,
                    message="expected_json must be an object.",
                )
            )
        elif list(expected_json.keys()) != requested_keys:
            case_findings.append(
                _finding(
                    code="expected_json_key_order_mismatch",
                    skill_name=skill_name,
                    case_id=case_id,
                    message=(
                        "expected_json keys must exactly match requested_keys "
                        "and preserve their order."
                    ),
                )
            )

        for key in ("repair_expectation", "risk_note"):
            value = case.get(key)
            if not isinstance(value, str) or not value.strip():
                case_findings.append(
                    _finding(
                        code=f"missing_{key}",
                        skill_name=skill_name,
                        case_id=case_id,
                        message=f"{key} must be a non-empty string.",
                    )
                )

        findings.extend(case_findings)
        case_reports.append(
            {
                "case_id": case_id,
                "passed": not case_findings,
                "finding_count": len(case_findings),
                "findings": [finding.to_dict() for finding in case_findings],
            }
        )

    return {
        "skill_name": skill_name,
        "baseline_id": baseline.get("baseline_id"),
        "status": "passed" if not findings else "failed",
        "case_count": len(cases),
        "finding_count": len(findings),
        "case_reports": case_reports,
        "findings": [finding.to_dict() for finding in findings],
    }


def _normalize_input_text_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_name": "input-text-analyze",
        "baseline_id": report.get("baseline_id"),
        "status": report.get("status"),
        "case_count": report.get("case_count"),
        "finding_count": report.get("finding_count", 0),
        "case_reports": report.get("case_reports", []),
        "findings": report.get("findings", []),
    }


def validate_skill_baselines(
    *,
    input_text_analyze_path: Path = INPUT_TEXT_ANALYZE_BASELINE_PATH,
    util_json_repair_path: Path = UTIL_JSON_REPAIR_BASELINE_PATH,
) -> dict[str, Any]:
    reports = [
        _normalize_input_text_report(
            evaluate_input_text_analyze_baseline(input_text_analyze_path)
        ),
        evaluate_util_json_repair_baseline(util_json_repair_path),
    ]
    finding_count = sum(int(report.get("finding_count", 0)) for report in reports)

    return {
        "status": "passed" if finding_count == 0 else "failed",
        "check_count": len(reports),
        "finding_count": finding_count,
        "checks": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deterministic skill baseline files."
    )
    parser.add_argument(
        "--input-text-analyze-baseline",
        type=Path,
        default=INPUT_TEXT_ANALYZE_BASELINE_PATH,
        help="Path to the input-text-analyze baseline JSON.",
    )
    parser.add_argument(
        "--util-json-repair-baseline",
        type=Path,
        default=UTIL_JSON_REPAIR_BASELINE_PATH,
        help="Path to the util-json-repair baseline JSON.",
    )
    args = parser.parse_args()

    report = validate_skill_baselines(
        input_text_analyze_path=args.input_text_analyze_baseline,
        util_json_repair_path=args.util_json_repair_baseline,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
