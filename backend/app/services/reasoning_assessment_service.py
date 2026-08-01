from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA_VERSION = 1
ASSESSMENT_EFFECT = "reviewer_advisory_only"
ASSESSMENT_METHOD_MODEL_ASSISTED = "model_assisted"

VERDICTS = frozenset({"pass", "underdetermined", "needs_human_judgment"})
COUNTER_CONCLUSION_STATUSES = frozenset({"valid_counter", "no_valid_counter", "not_attemptable"})
WARRANT_TYPES = frozenset(
    {
        "aggregation",
        "trend_extrapolation",
        "comparison",
        "causal",
        "analogy",
        "other",
    }
)
WARRANT_STATUSES = frozenset({"explicit", "provisional", "missing"})


class ReasoningAssessmentContractError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _safe_text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return " ".join(str(text).split())[:limit]


def _string_list(value: Any, *, limit: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_safe_text(item, 240) for item in value]
    return list(dict.fromkeys(item for item in items if item))[:limit]


def _verification_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("verification_metadata")
    return value if isinstance(value, dict) else {}


def _load_bearing_claim_ids(payload: dict[str, Any]) -> list[str]:
    explicit = _string_list(payload.get("load_bearing_claim_ids"))
    if explicit:
        return explicit

    verification = _verification_metadata(payload)
    claim_results = verification.get("claim_results")
    if not isinstance(claim_results, list):
        verified_insight = verification.get("verified_insight")
        claims = verified_insight.get("claims") if isinstance(verified_insight, dict) else {}
        claim_results = claims.get("items") if isinstance(claims, dict) else []

    return _string_list(
        [
            claim.get("claim_id")
            for claim in claim_results or []
            if isinstance(claim, dict) and claim.get("claim_id")
        ]
    )


def _conclusion_ref(payload: dict[str, Any]) -> str:
    explicit = _safe_text(payload.get("conclusion_ref"), 240)
    if explicit:
        return explicit
    verification = _verification_metadata(payload)
    verified_insight = verification.get("verified_insight")
    verified_insight_id = _safe_text(
        verification.get("verified_insight_id")
        or (verified_insight.get("id") if isinstance(verified_insight, dict) else ""),
        240,
    )
    if verified_insight_id:
        return verified_insight_id
    signal_id = _safe_text(payload.get("signal_id"), 160)
    return f"signal:{signal_id}:project_takeaway" if signal_id else ""


def _warrant_status(payload: dict[str, Any], warrant_text: str) -> str:
    explicit = _safe_text(payload.get("warrant_status"), 40).lower()
    if explicit in WARRANT_STATUSES:
        return explicit
    if not warrant_text or warrant_text.lower().startswith("no explicit warrant recorded"):
        return "missing"
    return "explicit"


def _counter_status(answer: str) -> str:
    if answer == "yes":
        return "valid_counter"
    if answer == "no":
        return "no_valid_counter"
    return "not_attemptable"


def _verdict(*, answer: str, warrant_status: str, load_bearing_claim_ids: list[str]) -> str:
    if warrant_status == "missing" or not load_bearing_claim_ids:
        return "needs_human_judgment"
    if answer == "yes":
        return "underdetermined"
    if answer == "no":
        return "pass"
    return "needs_human_judgment"


def validate_reasoning_assessment(assessment: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(assessment, dict):
        raise ReasoningAssessmentContractError(
            "invalid_reasoning_assessment",
            "reasoning_assessment must be an object.",
        )
    if assessment.get("schema_version") != SCHEMA_VERSION:
        raise ReasoningAssessmentContractError(
            "invalid_reasoning_assessment_schema_version",
            "reasoning_assessment.schema_version must be 1.",
        )
    if not _safe_text(assessment.get("assessment_id"), 240):
        raise ReasoningAssessmentContractError(
            "missing_reasoning_assessment_id",
            "reasoning_assessment.assessment_id is required.",
        )
    if not _safe_text(assessment.get("conclusion_ref"), 240):
        raise ReasoningAssessmentContractError(
            "missing_reasoning_conclusion_ref",
            "reasoning_assessment.conclusion_ref is required.",
        )
    if assessment.get("effect") != ASSESSMENT_EFFECT:
        raise ReasoningAssessmentContractError(
            "invalid_reasoning_assessment_effect",
            f"reasoning_assessment.effect must be {ASSESSMENT_EFFECT}.",
        )
    if assessment.get("assessment_method") != ASSESSMENT_METHOD_MODEL_ASSISTED:
        raise ReasoningAssessmentContractError(
            "invalid_reasoning_assessment_method",
            f"reasoning_assessment.assessment_method must be {ASSESSMENT_METHOD_MODEL_ASSISTED}.",
        )
    if assessment.get("verdict") not in VERDICTS:
        raise ReasoningAssessmentContractError(
            "invalid_reasoning_assessment_verdict",
            f"reasoning_assessment.verdict must be one of: {', '.join(sorted(VERDICTS))}.",
        )

    claim_ids = assessment.get("load_bearing_claim_ids")
    if not isinstance(claim_ids, list) or any(not _safe_text(item, 240) for item in claim_ids):
        raise ReasoningAssessmentContractError(
            "invalid_load_bearing_claim_ids",
            "reasoning_assessment.load_bearing_claim_ids must be a list of non-empty IDs.",
        )

    warrant = assessment.get("warrant")
    if not isinstance(warrant, dict):
        raise ReasoningAssessmentContractError("missing_warrant", "reasoning_assessment.warrant is required.")
    if warrant.get("type") not in WARRANT_TYPES:
        raise ReasoningAssessmentContractError(
            "invalid_warrant_type",
            f"warrant.type must be one of: {', '.join(sorted(WARRANT_TYPES))}.",
        )
    if warrant.get("status") not in WARRANT_STATUSES:
        raise ReasoningAssessmentContractError(
            "invalid_warrant_status",
            f"warrant.status must be one of: {', '.join(sorted(WARRANT_STATUSES))}.",
        )

    counter = assessment.get("counter_conclusion")
    if not isinstance(counter, dict) or counter.get("status") not in COUNTER_CONCLUSION_STATUSES:
        raise ReasoningAssessmentContractError(
            "invalid_counter_conclusion",
            "reasoning_assessment.counter_conclusion has an invalid status.",
        )

    if warrant.get("status") == "missing" and assessment.get("verdict") != "needs_human_judgment":
        raise ReasoningAssessmentContractError(
            "missing_warrant_requires_human_judgment",
            "a missing warrant must produce needs_human_judgment.",
        )
    if not claim_ids and assessment.get("verdict") != "needs_human_judgment":
        raise ReasoningAssessmentContractError(
            "missing_claim_anchors_require_human_judgment",
            "missing load-bearing claim IDs must produce needs_human_judgment.",
        )

    produced_by_model = assessment.get("produced_by_model")
    if not isinstance(produced_by_model, dict) or not _safe_text(produced_by_model.get("model_id"), 240):
        raise ReasoningAssessmentContractError(
            "missing_reasoning_model_provenance",
            "model-assisted reasoning assessments require produced_by_model.model_id.",
        )
    return assessment


def build_reasoning_assessment(
    *,
    payload: dict[str, Any],
    counter_check: dict[str, Any],
) -> dict[str, Any]:
    answer = _safe_text(counter_check.get("answer"), 40).lower()
    if answer not in {"yes", "no", "unclear"}:
        answer = "unclear"

    claim_ids = _load_bearing_claim_ids(payload)
    warrant_text = _safe_text(payload.get("warrant"), 1600)
    warrant_status = _warrant_status(payload, warrant_text)
    warrant_type = _safe_text(payload.get("warrant_type"), 80).lower() or "other"
    if warrant_type not in WARRANT_TYPES:
        warrant_type = "other"
    conclusion_ref = _conclusion_ref(payload)
    conclusion_text = _safe_text(payload.get("takeaway"), 1600)
    counter_text = _safe_text(counter_check.get("opposite_or_incompatible_conclusion"), 1200)
    produced_by_model = counter_check.get("produced_by_model")
    if not isinstance(produced_by_model, dict):
        produced_by_model = {}

    seed = json.dumps(
        {
            "conclusion_ref": conclusion_ref,
            "claim_ids": claim_ids,
            "warrant": warrant_text,
            "counter": counter_text,
            "model_id": produced_by_model.get("model_id"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    assessment_id = f"ra_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

    limitations: list[str] = []
    if warrant_status == "missing":
        limitations.append("missing_warrant")
    if not claim_ids:
        limitations.append("missing_load_bearing_claim_ids")
    limitations.extend(_string_list(counter_check.get("missing_evidence"), limit=10))

    assessment = {
        "assessment_id": assessment_id,
        "schema_version": SCHEMA_VERSION,
        "conclusion_ref": conclusion_ref,
        "conclusion_text": conclusion_text,
        "load_bearing_claim_ids": claim_ids,
        "warrant": {
            "type": warrant_type,
            "status": warrant_status,
            "text": warrant_text,
        },
        "counter_conclusion": {
            "status": _counter_status(answer),
            "text": counter_text,
        },
        "verdict": _verdict(
            answer=answer,
            warrant_status=warrant_status,
            load_bearing_claim_ids=claim_ids,
        ),
        "effect": ASSESSMENT_EFFECT,
        "assessment_method": ASSESSMENT_METHOD_MODEL_ASSISTED,
        "limitations": list(dict.fromkeys(limitations)),
        "reviewer_next_step": _safe_text(counter_check.get("reviewer_next_step"), 800),
        "produced_by_model": produced_by_model,
    }
    return validate_reasoning_assessment(assessment)
