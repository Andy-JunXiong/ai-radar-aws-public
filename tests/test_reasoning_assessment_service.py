import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.reasoning_assessment_service import (  # noqa: E402
    ReasoningAssessmentContractError,
    build_reasoning_assessment,
    validate_reasoning_assessment,
)


def _payload(*, warrant="The comparison establishes the preferred conclusion.", claim_ids=None):
    return {
        "signal_id": "sig-1",
        "takeaway": "The system is ready for broader adoption.",
        "warrant": warrant,
        "verification_metadata": {
            "verified_insight_id": "vi_1",
            "claim_results": [
                {"claim_id": claim_id}
                for claim_id in (claim_ids if claim_ids is not None else ["claim-1", "claim-2"])
            ],
        },
    }


def _counter_check(answer):
    return {
        "answer": answer,
        "opposite_or_incompatible_conclusion": "The same evidence supports only a Watch posture.",
        "missing_evidence": [],
        "reviewer_next_step": "Review the warrant.",
        "produced_by_model": {
            "provider": "openai",
            "model_id": "gpt-test",
            "task_type": "reason",
        },
    }


@pytest.mark.parametrize(
    ("answer", "verdict", "counter_status"),
    [
        ("yes", "underdetermined", "valid_counter"),
        ("no", "pass", "no_valid_counter"),
        ("unclear", "needs_human_judgment", "not_attemptable"),
    ],
)
def test_counter_check_answer_maps_to_reasoning_verdict(answer, verdict, counter_status):
    assessment = build_reasoning_assessment(
        payload=_payload(),
        counter_check=_counter_check(answer),
    )

    assert assessment["verdict"] == verdict
    assert assessment["counter_conclusion"]["status"] == counter_status
    assert assessment["effect"] == "reviewer_advisory_only"
    assert assessment["load_bearing_claim_ids"] == ["claim-1", "claim-2"]


def test_missing_warrant_forces_human_judgment_even_when_model_answers_yes():
    assessment = build_reasoning_assessment(
        payload=_payload(warrant="No explicit warrant recorded; reviewer must provide one."),
        counter_check=_counter_check("yes"),
    )

    assert assessment["warrant"]["status"] == "missing"
    assert assessment["verdict"] == "needs_human_judgment"
    assert "missing_warrant" in assessment["limitations"]


def test_missing_claim_anchors_force_human_judgment():
    assessment = build_reasoning_assessment(
        payload=_payload(claim_ids=[]),
        counter_check=_counter_check("no"),
    )

    assert assessment["load_bearing_claim_ids"] == []
    assert assessment["verdict"] == "needs_human_judgment"
    assert "missing_load_bearing_claim_ids" in assessment["limitations"]


def test_model_assisted_assessment_requires_model_provenance():
    assessment = build_reasoning_assessment(
        payload=_payload(),
        counter_check=_counter_check("no"),
    )
    assessment["produced_by_model"] = {}

    with pytest.raises(ReasoningAssessmentContractError) as raised:
        validate_reasoning_assessment(assessment)

    assert raised.value.code == "missing_reasoning_model_provenance"


def test_non_advisory_effect_is_rejected():
    assessment = build_reasoning_assessment(
        payload=_payload(),
        counter_check=_counter_check("no"),
    )
    assessment["effect"] = "blocks_action"

    with pytest.raises(ReasoningAssessmentContractError) as raised:
        validate_reasoning_assessment(assessment)

    assert raised.value.code == "invalid_reasoning_assessment_effect"
