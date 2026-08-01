import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import reasoning_counter_check_service as service  # noqa: E402


def test_generated_counter_check_attaches_valid_reasoning_assessment():
    parsed = {
        "answer": "yes",
        "summary": "The packet supports a materially weaker conclusion.",
        "opposite_or_incompatible_conclusion": "The evidence supports Watch, not Action.",
        "evidence_used": ["Claim one", "Claim two"],
        "missing_evidence": [],
        "reviewer_next_step": "Inspect the warrant.",
        "boundary": service.COUNTER_CHECK_BOUNDARY,
    }
    route = SimpleNamespace(
        provider="openai",
        model="gpt-test",
        tier="reason.default",
        task_type="reason",
    )
    payload = {
        "signal_id": "sig-1",
        "takeaway": "The system is ready for Action.",
        "warrant": "The two verified claims jointly establish action readiness.",
        "source_model_provenance": {
            "provider": "anthropic",
            "model_id": "claude-test",
        },
        "verification_metadata": {
            "verified_insight_id": "vi-1",
            "claim_results": [
                {"claim_id": "claim-1"},
                {"claim_id": "claim-2"},
            ],
        },
    }

    with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
        service,
        "ANTHROPIC_API_KEY",
        "test-key",
    ), patch.object(
        service,
        "execute_text_json_task",
        return_value=(parsed, route),
    ):
        result = service.generate_reasoning_counter_check(payload)

    assessment = result["reasoning_assessment"]
    assert assessment["conclusion_ref"] == "vi-1"
    assert assessment["load_bearing_claim_ids"] == ["claim-1", "claim-2"]
    assert assessment["verdict"] == "underdetermined"
    assert assessment["effect"] == "reviewer_advisory_only"
    assert assessment["produced_by_model"]["model_id"] == "gpt-test"
