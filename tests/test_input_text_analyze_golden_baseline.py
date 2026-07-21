import json
from pathlib import Path


BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "notes"
    / "baselines"
    / "input-text-analyze-golden-candidates-v0.json"
)

REQUIRED_ANALYSIS_KEYS = [
    "summary",
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
]


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_input_text_analyze_frozen_baseline_has_two_goldens():
    baseline = _load_baseline()

    assert baseline["baseline_id"] == "input-text-analyze-golden-candidates-v0"
    assert baseline["status"] == "exact_wording_frozen"

    frozen_goldens = [
        case for case in baseline["cases"] if case.get("decision") == "frozen_golden"
    ]
    assert [case["id"] for case in frozen_goldens] == [
        "ita-pdf-verification-asset-architecture",
        "ita-multi-adr0013-memory-boundary",
    ]


def test_input_text_analyze_frozen_goldens_have_string_expected_outputs():
    baseline = _load_baseline()

    for case in baseline["cases"]:
        if case.get("decision") != "frozen_golden":
            continue

        expected_analysis = case.get("expected_analysis")
        assert sorted(expected_analysis) == sorted(REQUIRED_ANALYSIS_KEYS)
        for value in expected_analysis.values():
            assert isinstance(value, str)
            assert value.strip()
            assert "Uncertain:" not in value


def test_input_text_analyze_frozen_goldens_are_citation_complete():
    baseline = _load_baseline()

    for case in baseline["cases"]:
        if case.get("decision") != "frozen_golden":
            continue

        expected_analysis = case["expected_analysis"]
        joined = json.dumps(expected_analysis, ensure_ascii=False)
        metadata = case["expected_policy_metadata"]

        assert "[Source:" in joined
        assert metadata["citation_count"] >= 1
        assert metadata["citation_validation_passed"] is True
        assert metadata["verification_status"] == "basic_verified"
        assert metadata["verification_passed"] is True
        assert metadata["validation_failures"] == []
