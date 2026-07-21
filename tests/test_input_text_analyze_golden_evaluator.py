import copy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = (
    REPO_ROOT
    / "docs"
    / "notes"
    / "baselines"
    / "input-text-analyze-golden-candidates-v0.json"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_input_text_analyze_golden_baseline import (  # noqa: E402
    evaluate_baseline,
    evaluate_golden_case,
)


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _first_frozen_case() -> dict:
    baseline = _load_baseline()
    return next(case for case in baseline["cases"] if case["decision"] == "frozen_golden")


def test_input_text_analyze_golden_evaluator_passes_current_baseline():
    report = evaluate_baseline(BASELINE_PATH)

    assert report["baseline_id"] == "input-text-analyze-golden-candidates-v0"
    assert report["status"] == "passed"
    assert report["frozen_golden_count"] == 2
    assert report["finding_count"] == 0
    assert [case["passed"] for case in report["case_reports"]] == [True, True]


def test_input_text_analyze_golden_evaluator_detects_wording_drift():
    case = copy.deepcopy(_first_frozen_case())
    observed_analysis = copy.deepcopy(case["expected_analysis"])
    observed_analysis["summary"] = observed_analysis["summary"] + " Drift."

    report = evaluate_golden_case(
        case,
        observed_analysis=observed_analysis,
        observed_policy_metadata=case["expected_policy_metadata"],
    )

    assert report["passed"] is False
    assert "analysis_exact_wording_mismatch" in {
        finding["code"] for finding in report["findings"]
    }


def test_input_text_analyze_golden_evaluator_detects_missing_source_citation():
    case = copy.deepcopy(_first_frozen_case())
    observed_analysis = copy.deepcopy(case["expected_analysis"])
    observed_analysis["summary"] = observed_analysis["summary"].split("[Source:", 1)[0].strip()

    report = evaluate_golden_case(
        case,
        observed_analysis=observed_analysis,
        observed_policy_metadata=case["expected_policy_metadata"],
    )

    assert report["passed"] is False
    codes = {finding["code"] for finding in report["findings"]}
    assert "missing_source_citation" in codes


def test_input_text_analyze_golden_evaluator_detects_policy_metadata_drift():
    case = copy.deepcopy(_first_frozen_case())
    observed_metadata = copy.deepcopy(case["expected_policy_metadata"])
    observed_metadata["verification_status"] = "uncertain"

    report = evaluate_golden_case(
        case,
        observed_analysis=case["expected_analysis"],
        observed_policy_metadata=observed_metadata,
    )

    assert report["passed"] is False
    codes = {finding["code"] for finding in report["findings"]}
    assert "policy_metadata_verification_status_mismatch" in codes
    assert "policy_metadata_exact_verification_status_mismatch" in codes


def test_input_text_analyze_golden_evaluator_requires_frozen_status():
    baseline = _load_baseline()
    baseline["status"] = "provisional"

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "baseline.json"
        path.write_text(json.dumps(baseline), encoding="utf-8")

        report = evaluate_baseline(path)

    assert report["status"] == "failed"
    assert "baseline_not_exact_wording_frozen" in {
        finding["code"] for finding in report["findings"]
    }
