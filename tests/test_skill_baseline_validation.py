import copy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_TEXT_BASELINE_PATH = (
    REPO_ROOT
    / "docs"
    / "notes"
    / "baselines"
    / "input-text-analyze-golden-candidates-v0.json"
)
UTIL_JSON_REPAIR_BASELINE_PATH = (
    REPO_ROOT / "docs" / "notes" / "baselines" / "util-json-repair-golden-cases.json"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_skill_baselines import (  # noqa: E402
    evaluate_util_json_repair_baseline,
    validate_skill_baselines,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_skill_baselines_passes_current_baselines():
    report = validate_skill_baselines(
        input_text_analyze_path=INPUT_TEXT_BASELINE_PATH,
        util_json_repair_path=UTIL_JSON_REPAIR_BASELINE_PATH,
    )

    assert report["status"] == "passed"
    assert report["check_count"] == 2
    assert report["finding_count"] == 0
    assert [check["skill_name"] for check in report["checks"]] == [
        "input-text-analyze",
        "util-json-repair",
    ]


def test_validate_skill_baselines_reports_input_text_failure():
    input_text_baseline = _load_json(INPUT_TEXT_BASELINE_PATH)
    input_text_baseline["status"] = "provisional"

    with TemporaryDirectory() as tmp:
        input_text_path = Path(tmp) / "input-text-baseline.json"
        _write_json(input_text_path, input_text_baseline)

        report = validate_skill_baselines(
            input_text_analyze_path=input_text_path,
            util_json_repair_path=UTIL_JSON_REPAIR_BASELINE_PATH,
        )

    assert report["status"] == "failed"
    assert report["finding_count"] > 0
    input_text_report = report["checks"][0]
    assert input_text_report["skill_name"] == "input-text-analyze"
    assert "baseline_not_exact_wording_frozen" in {
        finding["code"] for finding in input_text_report["findings"]
    }


def test_util_json_repair_baseline_evaluator_detects_missing_edge_case():
    baseline = _load_json(UTIL_JSON_REPAIR_BASELINE_PATH)
    baseline["cases"] = [
        case for case in baseline["cases"] if case["edge_case"] != "trailing_comma"
    ]

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "util-baseline.json"
        _write_json(path, baseline)

        report = evaluate_util_json_repair_baseline(path)

    assert report["status"] == "failed"
    assert "edge_case_coverage_mismatch" in {
        finding["code"] for finding in report["findings"]
    }


def test_util_json_repair_baseline_evaluator_detects_key_order_drift():
    baseline = _load_json(UTIL_JSON_REPAIR_BASELINE_PATH)
    baseline = copy.deepcopy(baseline)
    first_case = baseline["cases"][0]
    first_case["expected_json"] = {
        "risk": "medium",
        "summary": "Agent workflows are converging",
    }

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "util-baseline.json"
        _write_json(path, baseline)

        report = evaluate_util_json_repair_baseline(path)

    assert report["status"] == "failed"
    first_case_report = report["case_reports"][0]
    assert "expected_json_key_order_mismatch" in {
        finding["code"] for finding in first_case_report["findings"]
    }
