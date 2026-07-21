from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_PATH = (
    REPO_ROOT
    / "docs"
    / "notes"
    / "baselines"
    / "input-text-analyze-golden-candidates-v0.json"
)
REQUIRED_ANALYSIS_KEYS = (
    "summary",
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
)
REQUIRED_POLICY_METADATA = {
    "citation_validation_passed": True,
    "verification_status": "basic_verified",
    "verification_passed": True,
    "validation_failures": [],
}


@dataclass(frozen=True)
class InputTextAnalyzeGoldenFinding:
    code: str
    severity: str
    case_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "case_id": self.case_id,
            "message": self.message,
        }


def _safe_case_id(case: dict[str, Any]) -> str:
    return str(case.get("id") or "<missing-case-id>")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _analysis_findings(
    *,
    case_id: str,
    expected_analysis: Any,
    observed_analysis: Any,
) -> list[InputTextAnalyzeGoldenFinding]:
    findings: list[InputTextAnalyzeGoldenFinding] = []

    if not isinstance(expected_analysis, dict):
        return [
            InputTextAnalyzeGoldenFinding(
                code="missing_expected_analysis",
                severity="error",
                case_id=case_id,
                message="Frozen golden cases must include expected_analysis.",
            )
        ]

    if not isinstance(observed_analysis, dict):
        return [
            InputTextAnalyzeGoldenFinding(
                code="invalid_observed_analysis",
                severity="error",
                case_id=case_id,
                message="Observed analysis must be a mapping of the five fixed fields.",
            )
        ]

    expected_keys = set(REQUIRED_ANALYSIS_KEYS)
    observed_keys = set(str(key) for key in observed_analysis)
    if observed_keys != expected_keys:
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="analysis_key_mismatch",
                severity="error",
                case_id=case_id,
                message=(
                    "Observed analysis keys must exactly match "
                    f"{', '.join(REQUIRED_ANALYSIS_KEYS)}."
                ),
            )
        )

    for key in REQUIRED_ANALYSIS_KEYS:
        value = observed_analysis.get(key)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                InputTextAnalyzeGoldenFinding(
                    code="analysis_value_not_string",
                    severity="error",
                    case_id=case_id,
                    message=f"analysis.{key} must be a non-empty string.",
                )
            )
            continue
        if "Uncertain:" in value:
            findings.append(
                InputTextAnalyzeGoldenFinding(
                    code="blanket_uncertain_prefix_present",
                    severity="error",
                    case_id=case_id,
                    message=f"analysis.{key} must not contain blanket Uncertain: text.",
                )
            )
        expected_value = expected_analysis.get(key)
        if isinstance(expected_value, str) and value != expected_value:
            findings.append(
                InputTextAnalyzeGoldenFinding(
                    code="analysis_exact_wording_mismatch",
                    severity="error",
                    case_id=case_id,
                    message=f"analysis.{key} does not match the frozen expected wording.",
                )
            )

    joined = json.dumps(observed_analysis, ensure_ascii=False)
    if "[Source:" not in joined:
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="missing_source_citation",
                severity="error",
                case_id=case_id,
                message="Observed analysis must include at least one [Source: ...] citation.",
            )
        )

    return findings


def _metadata_findings(
    *,
    case_id: str,
    expected_metadata: Any,
    observed_metadata: Any,
) -> list[InputTextAnalyzeGoldenFinding]:
    findings: list[InputTextAnalyzeGoldenFinding] = []

    if not isinstance(expected_metadata, dict):
        return [
            InputTextAnalyzeGoldenFinding(
                code="missing_expected_policy_metadata",
                severity="error",
                case_id=case_id,
                message="Frozen golden cases must include expected_policy_metadata.",
            )
        ]

    if not isinstance(observed_metadata, dict):
        return [
            InputTextAnalyzeGoldenFinding(
                code="invalid_observed_policy_metadata",
                severity="error",
                case_id=case_id,
                message="Observed policy metadata must be a mapping.",
            )
        ]

    citation_count = observed_metadata.get("citation_count")
    if not isinstance(citation_count, int) or citation_count < 1:
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="invalid_citation_count",
                severity="error",
                case_id=case_id,
                message="policy metadata must record citation_count >= 1.",
            )
        )

    for key, required_value in REQUIRED_POLICY_METADATA.items():
        if observed_metadata.get(key) != required_value:
            findings.append(
                InputTextAnalyzeGoldenFinding(
                    code=f"policy_metadata_{key}_mismatch",
                    severity="error",
                    case_id=case_id,
                    message=f"policy metadata {key} must be {required_value!r}.",
                )
            )

    for key, expected_value in expected_metadata.items():
        if observed_metadata.get(key) != expected_value:
            findings.append(
                InputTextAnalyzeGoldenFinding(
                    code=f"policy_metadata_exact_{key}_mismatch",
                    severity="error",
                    case_id=case_id,
                    message=f"policy metadata {key} does not match the frozen expected value.",
                )
            )

    return findings


def evaluate_golden_case(
    case: dict[str, Any],
    *,
    observed_analysis: dict[str, Any] | None = None,
    observed_policy_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_id = _safe_case_id(case)
    expected_analysis = case.get("expected_analysis")
    expected_metadata = case.get("expected_policy_metadata")
    analysis = observed_analysis if observed_analysis is not None else expected_analysis
    metadata = (
        observed_policy_metadata
        if observed_policy_metadata is not None
        else expected_metadata
    )

    findings: list[InputTextAnalyzeGoldenFinding] = []
    if case.get("decision") != "frozen_golden":
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="case_not_frozen_golden",
                severity="error",
                case_id=case_id,
                message="Evaluator only accepts cases marked decision=frozen_golden.",
            )
        )
    findings.extend(
        _analysis_findings(
            case_id=case_id,
            expected_analysis=expected_analysis,
            observed_analysis=analysis,
        )
    )
    findings.extend(
        _metadata_findings(
            case_id=case_id,
            expected_metadata=expected_metadata,
            observed_metadata=metadata,
        )
    )

    return {
        "case_id": case_id,
        "passed": not findings,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def evaluate_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    baseline = _load_json(path)
    findings: list[InputTextAnalyzeGoldenFinding] = []

    if baseline.get("status") != "exact_wording_frozen":
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="baseline_not_exact_wording_frozen",
                severity="error",
                case_id="<baseline>",
                message="Baseline status must be exact_wording_frozen before deterministic evaluation.",
            )
        )

    cases = baseline.get("cases")
    if not isinstance(cases, list):
        cases = []
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="baseline_cases_not_list",
                severity="error",
                case_id="<baseline>",
                message="Baseline cases must be a list.",
            )
        )

    frozen_cases = [
        case for case in cases
        if isinstance(case, dict) and case.get("decision") == "frozen_golden"
    ]
    case_reports = [evaluate_golden_case(case) for case in frozen_cases]
    for report in case_reports:
        findings.extend(
            InputTextAnalyzeGoldenFinding(
                code=finding["code"],
                severity=finding["severity"],
                case_id=finding["case_id"],
                message=finding["message"],
            )
            for finding in report["findings"]
        )

    if len(frozen_cases) < 2:
        findings.append(
            InputTextAnalyzeGoldenFinding(
                code="too_few_frozen_goldens",
                severity="error",
                case_id="<baseline>",
                message="Baseline must contain at least two frozen golden cases.",
            )
        )

    return {
        "baseline_id": baseline.get("baseline_id"),
        "status": "passed" if not findings else "failed",
        "case_count": len(cases),
        "frozen_golden_count": len(frozen_cases),
        "finding_count": len(findings),
        "case_reports": case_reports,
        "findings": [finding.to_dict() for finding in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen input-text-analyze golden baseline."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to input-text-analyze golden baseline JSON.",
    )
    args = parser.parse_args()

    report = evaluate_baseline(args.baseline)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
