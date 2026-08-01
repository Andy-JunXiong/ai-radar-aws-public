import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.calibrate_reasoning_assessments import (  # noqa: E402
    build_reasoning_assessment_calibration_report,
)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _assessment(assessment_id: str, verdict: str):
    counter_status = {
        "pass": "no_valid_counter",
        "underdetermined": "valid_counter",
        "needs_human_judgment": "not_attemptable",
    }[verdict]
    return {
        "assessment_id": assessment_id,
        "schema_version": 1,
        "conclusion_ref": f"vi:{assessment_id}",
        "conclusion_text": "Conclusion",
        "load_bearing_claim_ids": [f"claim:{assessment_id}"],
        "warrant": {"type": "comparison", "status": "explicit", "text": "Warrant"},
        "counter_conclusion": {"status": counter_status, "text": "Counter"},
        "verdict": verdict,
        "effect": "reviewer_advisory_only",
        "assessment_method": "model_assisted",
        "limitations": [],
        "reviewer_next_step": "Review",
        "produced_by_model": {"model_id": "test-model"},
    }


def test_calibration_report_measures_coverage_abstention_and_labeled_unsafe_pass():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        projects = root / "projects"
        labels = root / "labels.json"
        _write_json(
            projects / "ai_radar.json",
            {
                "project_id": "ai_radar",
                "items": [
                    {"signal_id": "s1", "reasoning_assessment": _assessment("ra-pass", "pass")},
                    {"signal_id": "s2", "reasoning_assessment": _assessment("ra-under", "underdetermined")},
                    {
                        "signal_id": "s3",
                        "reasoning_assessment": _assessment("ra-human", "needs_human_judgment"),
                    },
                ],
            },
        )
        _write_json(
            labels,
            {
                "labels": [
                    {
                        "assessment_id": "ra-pass",
                        "expected_verdict": "underdetermined",
                        "reviewer_note": "Packet supports a weaker conclusion.",
                    }
                ]
            },
        )

        report = build_reasoning_assessment_calibration_report(
            project_improvements_dir=projects,
            labels_file=labels,
            root=root,
        )

    summary = report["summary"]
    assert report["report_boundary"]["mode"] == "read_only_calibration"
    assert report["report_boundary"]["runtime_gate_change_allowed"] is False
    assert summary["attached_assessment_count"] == 3
    assert summary["coverage_complete"] is True
    assert summary["abstention_rate"] == 0.3333
    assert summary["unsafe_pass_count"] == 1
    assert summary["unsafe_pass_rate"] == 1.0


def test_calibration_report_exposes_empty_real_sample_baseline_without_fabricating_metrics():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = build_reasoning_assessment_calibration_report(
            project_improvements_dir=root / "projects",
            root=root,
        )

    summary = report["summary"]
    assert summary["attached_assessment_count"] == 0
    assert summary["coverage_complete"] is False
    assert summary["abstention_rate"] is None
    assert summary["false_positive_measurement_available"] is False
    assert summary["coverage_gaps"] == {
        "needs_human_judgment": 1,
        "pass": 1,
        "underdetermined": 1,
    }
