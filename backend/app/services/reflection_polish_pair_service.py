from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 1
PAIR_RECORD_TYPE = "reflection_polish_pair"
REVIEW_RECORD_TYPE = "reflection_polish_review"
PAIR_STATUS_GENERATED = "generated"

REVIEW_OUTCOME_APPROVED = "approved"
REVIEW_OUTCOME_NEEDS_REVISION = "needs_revision"
REVIEW_OUTCOME_REJECTED = "rejected"
REVIEW_OUTCOMES = frozenset(
    {
        REVIEW_OUTCOME_APPROVED,
        REVIEW_OUTCOME_NEEDS_REVISION,
        REVIEW_OUTCOME_REJECTED,
    }
)

DIMENSION_RESULT_PASS = "pass"
DIMENSION_RESULT_FAIL = "fail"
DIMENSION_RESULT_UNCERTAIN = "uncertain"
DIMENSION_RESULTS = frozenset(
    {
        DIMENSION_RESULT_PASS,
        DIMENSION_RESULT_FAIL,
        DIMENSION_RESULT_UNCERTAIN,
    }
)

REVIEW_DIMENSIONS = (
    "meaning_preservation",
    "user_voice_preservation",
    "clarity_and_structure_gain",
    "context_grounding",
    "no_new_claims",
    "non_generic_specificity",
)

CONTEXT_KEYS = (
    "signal_id",
    "signal_title",
    "signal_summary",
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
)

FORBIDDEN_TOP_LEVEL_FIELDS = frozenset(
    {
        "action_eligibility",
        "blocked_downstream_actions",
        "evidence_pack",
        "project_takeaway",
        "project_takeaway_eligibility",
        "verification_ref",
        "verified_insight_id",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _json_object_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return copy.deepcopy(json.loads(json.dumps(value, ensure_ascii=False)))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _content_fingerprint(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _validate_no_forbidden_top_level_fields(record: dict[str, Any], *, field: str) -> None:
    forbidden = sorted(FORBIDDEN_TOP_LEVEL_FIELDS.intersection(record))
    _require(not forbidden, f"{field} must not include {', '.join(forbidden)}.")


def _validate_context(value: Any) -> dict[str, Any]:
    context = {key: None for key in CONTEXT_KEYS}
    snapshot = _json_object_snapshot(value)
    for key in CONTEXT_KEYS:
        if key in snapshot:
            context[key] = snapshot[key]
    return context


def _validate_enum(value: Any, allowed: frozenset[str], field: str) -> str:
    normalized = _safe_text(value)
    _require(normalized in allowed, f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return normalized


def build_reflection_polish_pair(
    *,
    original_text: str,
    polished_text: str,
    provider_used: str,
    fallback_used: bool = False,
    policy_metadata: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    created_at: str | None = None,
    pair_id: str | None = None,
) -> dict[str, Any]:
    draft_text = _safe_text(original_text)
    output_text = _safe_text(polished_text)
    _require(bool(draft_text), "original_text is required.")
    _require(bool(output_text), "polished_text is required.")

    source_payload = {
        "route": "POST /polish_reflection",
        "task_type": "reflection_polish",
        "source_type": "signal",
        "content_type": "signal",
    }
    source_payload.update(_json_object_snapshot(source))

    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": PAIR_RECORD_TYPE,
        "id": _safe_text(pair_id) or f"rpp_{uuid.uuid4().hex[:12]}",
        "created_at": _safe_text(created_at) or _utc_now_iso(),
        "status": PAIR_STATUS_GENERATED,
        "source": source_payload,
        "context": _validate_context(context or {}),
        "draft": {
            "original_text": draft_text,
            "content_fingerprint": _content_fingerprint(draft_text),
        },
        "polish": {
            "polished_text": output_text,
            "content_fingerprint": _content_fingerprint(output_text),
            "provider_used": _safe_text(provider_used),
            "fallback_used": bool(fallback_used),
            "policy_metadata": _json_object_snapshot(policy_metadata or {}),
            "execution": _json_object_snapshot(execution or {}),
        },
        "baseline_eligibility": {
            "eligible": False,
            "reason": "human_review_required",
        },
        "review_ref": None,
    }
    return validate_reflection_polish_pair(record)


def validate_reflection_polish_pair(record: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object_snapshot(record)
    _require(bool(payload), "pair must be a JSON object.")
    _validate_no_forbidden_top_level_fields(payload, field="pair")

    _require(payload.get("schema_version") == SCHEMA_VERSION, "pair schema_version must be 1.")
    _require(payload.get("record_type") == PAIR_RECORD_TYPE, f"pair record_type must be {PAIR_RECORD_TYPE}.")
    _require(bool(_safe_text(payload.get("id"))), "pair id is required.")
    _require(bool(_safe_text(payload.get("created_at"))), "pair created_at is required.")
    _require(_safe_text(payload.get("status")) == PAIR_STATUS_GENERATED, "pair status must be generated.")

    source = _json_object_snapshot(payload.get("source"))
    _require(_safe_text(source.get("route")) == "POST /polish_reflection", "pair source.route must be POST /polish_reflection.")
    _require(_safe_text(source.get("task_type")) == "reflection_polish", "pair source.task_type must be reflection_polish.")
    _require(bool(_safe_text(source.get("source_type"))), "pair source.source_type is required.")
    _require(bool(_safe_text(source.get("content_type"))), "pair source.content_type is required.")
    payload["source"] = source
    payload["context"] = _validate_context(payload.get("context"))

    draft = _json_object_snapshot(payload.get("draft"))
    draft_text = _safe_text(draft.get("original_text"))
    _require(bool(draft_text), "pair draft.original_text is required.")
    _require(
        _safe_text(draft.get("content_fingerprint")) == _content_fingerprint(draft_text),
        "pair draft.content_fingerprint does not match original_text.",
    )
    draft["original_text"] = draft_text
    payload["draft"] = draft

    polish = _json_object_snapshot(payload.get("polish"))
    polished_text = _safe_text(polish.get("polished_text"))
    _require(bool(polished_text), "pair polish.polished_text is required.")
    _require(
        _safe_text(polish.get("content_fingerprint")) == _content_fingerprint(polished_text),
        "pair polish.content_fingerprint does not match polished_text.",
    )
    _require(bool(_safe_text(polish.get("provider_used"))), "pair polish.provider_used is required.")
    _require(isinstance(polish.get("fallback_used"), bool), "pair polish.fallback_used must be a boolean.")
    _require(isinstance(polish.get("policy_metadata"), dict), "pair polish.policy_metadata must be an object.")
    _require(isinstance(polish.get("execution"), dict), "pair polish.execution must be an object.")
    polish["polished_text"] = polished_text
    polish["provider_used"] = _safe_text(polish.get("provider_used"))
    polish["policy_metadata"] = _json_object_snapshot(polish.get("policy_metadata"))
    polish["execution"] = _json_object_snapshot(polish.get("execution"))
    payload["polish"] = polish

    baseline = _json_object_snapshot(payload.get("baseline_eligibility"))
    _require(baseline.get("eligible") is False, "pair baseline_eligibility.eligible must remain false before human review.")
    _require(
        _safe_text(baseline.get("reason")) == "human_review_required",
        "pair baseline_eligibility.reason must be human_review_required.",
    )
    payload["baseline_eligibility"] = baseline
    _require(payload.get("review_ref") is None, "pair review_ref must be null in v0 generated pair records.")
    return payload


def build_reflection_polish_review(
    *,
    pair: dict[str, Any],
    outcome: str,
    dimension_results: dict[str, str],
    reviewer_id: str,
    reviewer_note: str = "",
    final_reflection_text: str = "",
    reviewed_at: str | None = None,
    review_id: str | None = None,
    save_reflection_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validated_pair = validate_reflection_polish_pair(pair)
    review = {
        "schema_version": SCHEMA_VERSION,
        "record_type": REVIEW_RECORD_TYPE,
        "id": _safe_text(review_id) or f"rpr_{uuid.uuid4().hex[:12]}",
        "pair_id": _safe_text(validated_pair.get("id")),
        "reviewed_at": _safe_text(reviewed_at) or _utc_now_iso(),
        "reviewer": {
            "type": "human",
            "id": _safe_text(reviewer_id),
        },
        "outcome": _safe_text(outcome),
        "reviewer_note": _safe_text(reviewer_note),
        "dimension_results": _json_object_snapshot(dimension_results),
        "final_reflection_text": _safe_text(final_reflection_text),
        "save_reflection_ref": _json_object_snapshot(save_reflection_ref) if save_reflection_ref else None,
    }
    return validate_reflection_polish_review(review, pair=validated_pair)


def validate_reflection_polish_review(
    record: dict[str, Any],
    *,
    pair: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _json_object_snapshot(record)
    _require(bool(payload), "review must be a JSON object.")
    _validate_no_forbidden_top_level_fields(payload, field="review")

    _require(payload.get("schema_version") == SCHEMA_VERSION, "review schema_version must be 1.")
    _require(payload.get("record_type") == REVIEW_RECORD_TYPE, f"review record_type must be {REVIEW_RECORD_TYPE}.")
    _require(bool(_safe_text(payload.get("id"))), "review id is required.")
    pair_id = _safe_text(payload.get("pair_id"))
    _require(bool(pair_id), "review pair_id is required.")
    if pair is not None:
        validated_pair = validate_reflection_polish_pair(pair)
        _require(pair_id == _safe_text(validated_pair.get("id")), "review pair_id must reference the provided pair.")
    _require(bool(_safe_text(payload.get("reviewed_at"))), "review reviewed_at is required.")

    reviewer = _json_object_snapshot(payload.get("reviewer"))
    _require(_safe_text(reviewer.get("type")) == "human", "review reviewer.type must be human.")
    _require(bool(_safe_text(reviewer.get("id"))), "review reviewer.id is required.")
    reviewer["type"] = "human"
    reviewer["id"] = _safe_text(reviewer.get("id"))
    payload["reviewer"] = reviewer

    outcome = _validate_enum(payload.get("outcome"), REVIEW_OUTCOMES, "review outcome")
    payload["outcome"] = outcome
    reviewer_note = _safe_text(payload.get("reviewer_note"))
    payload["reviewer_note"] = reviewer_note

    dimensions = _json_object_snapshot(payload.get("dimension_results"))
    _require(
        set(dimensions) == set(REVIEW_DIMENSIONS),
        "review dimension_results must include exactly the reflection-polish checklist dimensions.",
    )
    normalized_dimensions: dict[str, str] = {}
    for dimension in REVIEW_DIMENSIONS:
        normalized_dimensions[dimension] = _validate_enum(
            dimensions.get(dimension),
            DIMENSION_RESULTS,
            f"review dimension_results.{dimension}",
        )
    payload["dimension_results"] = normalized_dimensions

    has_failed_dimension = any(value == DIMENSION_RESULT_FAIL for value in normalized_dimensions.values())
    _require(
        not (outcome == REVIEW_OUTCOME_APPROVED and has_failed_dimension),
        "review outcome cannot be approved when any dimension failed.",
    )
    _require(
        not (outcome in {REVIEW_OUTCOME_NEEDS_REVISION, REVIEW_OUTCOME_REJECTED} and not reviewer_note),
        "reviewer_note is required for needs_revision and rejected outcomes.",
    )
    final_text = _safe_text(payload.get("final_reflection_text"))
    _require(
        not (outcome == REVIEW_OUTCOME_APPROVED and not final_text),
        "final_reflection_text is required for approved outcomes.",
    )
    payload["final_reflection_text"] = final_text

    save_ref = payload.get("save_reflection_ref")
    if save_ref is not None:
        _require(isinstance(save_ref, dict), "review save_reflection_ref must be an object when present.")
        payload["save_reflection_ref"] = _json_object_snapshot(save_ref)
    return payload
