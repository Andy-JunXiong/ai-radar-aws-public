import json
from pathlib import Path


BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "notes"
    / "baselines"
    / "reflection-polish-human-review-checklist-v0.json"
)

REQUIRED_DIMENSION_IDS = {
    "meaning_preservation",
    "user_voice_preservation",
    "clarity_and_structure_gain",
    "context_grounding",
    "no_new_claims",
    "non_generic_specificity",
}


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_reflection_polish_checklist_identifies_human_review_scope():
    baseline = _load_baseline()

    assert baseline["baseline_id"] == "reflection-polish-human-review-checklist-v0"
    assert baseline["skill_name"] == "reflection-polish"
    assert baseline["baseline_type"] == "human_review_checklist"
    assert baseline["status"] == "checklist_only_no_golden_outputs"
    assert baseline["not_machine_evaluable"] is True
    assert "not a golden-output baseline" in baseline["source_note"]
    assert baseline["prompt_contract"]["human_in_loop"] is True


def test_reflection_polish_checklist_has_required_review_dimensions():
    baseline = _load_baseline()
    dimensions = baseline["review_dimensions"]

    assert {dimension["id"] for dimension in dimensions} == REQUIRED_DIMENSION_IDS
    for dimension in dimensions:
        assert isinstance(dimension["question"], str)
        assert dimension["question"].strip()
        assert isinstance(dimension["pass_condition"], str)
        assert dimension["pass_condition"].strip()
        assert isinstance(dimension["failure_modes"], list)
        assert dimension["failure_modes"]
        assert all(isinstance(item, str) and item.strip() for item in dimension["failure_modes"])


def test_reflection_polish_checklist_requires_before_after_review_context():
    baseline = _load_baseline()
    required_context = set(baseline["review_context_required"])

    assert {
        "original_draft",
        "polished_output",
        "provider_used",
        "fallback_used",
        "policy_metadata",
        "human_reviewer_id_or_note",
        "human_approval_outcome",
    }.issubset(required_context)
    assert set(baseline["required_review_outcomes"]) == {
        "approved",
        "needs_revision",
        "rejected",
    }


def test_reflection_polish_checklist_blocks_machine_evaluator_shortcut():
    baseline = _load_baseline()

    assert "cases" not in baseline
    assert "expected_analysis" not in baseline
    assert "expected_output" not in baseline
    assert any(
        "do not add reflection-polish to scripts/validate_skill_baselines.py yet" == item
        for item in baseline["do_not"]
    )
    assert baseline["minimum_future_golden_requirements"]["complete_human_reviewed_pairs"] == 3
