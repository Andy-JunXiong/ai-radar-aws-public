from __future__ import annotations

import json
from typing import Any


RELATION_ASSOCIATION = "association"
RELATION_EVIDENTIAL_SUPPORT = "evidential_support"
RELATION_LOGICAL_INFERENCE = "logical_inference"

RELATION_TYPES: frozenset[str] = frozenset(
    {
        RELATION_ASSOCIATION,
        RELATION_EVIDENTIAL_SUPPORT,
        RELATION_LOGICAL_INFERENCE,
    }
)
STRONG_RELATION_TYPES: frozenset[str] = frozenset(
    {
        RELATION_EVIDENTIAL_SUPPORT,
        RELATION_LOGICAL_INFERENCE,
    }
)

GROUNDING_SOURCE_EXCERPT = "source_excerpt"
GROUNDING_STRUCTURED_METADATA = "structured_metadata"
GROUNDING_VERIFIED_RECORD = "verified_record"
GROUNDING_HUMAN_NOTE = "human_note"
GROUNDING_NONE = "none"

GROUNDING_SOURCES: frozenset[str] = frozenset(
    {
        GROUNDING_SOURCE_EXCERPT,
        GROUNDING_STRUCTURED_METADATA,
        GROUNDING_VERIFIED_RECORD,
        GROUNDING_HUMAN_NOTE,
        GROUNDING_NONE,
    }
)

DERIVATION_DIRECT_OBSERVATION = "direct_observation"
DERIVATION_DETERMINISTIC_RULE = "deterministic_rule"
DERIVATION_HUMAN_ASSERTED = "human_asserted"
DERIVATION_MODEL_INFERRED = "model_inferred"

DERIVATION_MECHANISMS: frozenset[str] = frozenset(
    {
        DERIVATION_DIRECT_OBSERVATION,
        DERIVATION_DETERMINISTIC_RULE,
        DERIVATION_HUMAN_ASSERTED,
        DERIVATION_MODEL_INFERRED,
    }
)

SUPPORT_POSTURE_PROPOSED = "proposed"
SUPPORT_POSTURE_CONFIRMED = "confirmed"
SUPPORT_POSTURE_REJECTED = "rejected"
SUPPORT_POSTURE_NEEDS_REVIEW = "needs_review"

SUPPORT_POSTURES: frozenset[str] = frozenset(
    {
        SUPPORT_POSTURE_PROPOSED,
        SUPPORT_POSTURE_CONFIRMED,
        SUPPORT_POSTURE_REJECTED,
        SUPPORT_POSTURE_NEEDS_REVIEW,
    }
)
REVIEW_REQUIRED_POSTURES: frozenset[str] = frozenset(
    {
        SUPPORT_POSTURE_PROPOSED,
        SUPPORT_POSTURE_NEEDS_REVIEW,
    }
)

CLASSIFIED_BY_HUMAN = "human"
CLASSIFIED_BY_MODEL = "model"
CLASSIFIED_BY_SYSTEM_RULE = "system_rule"

CLASSIFIED_BY: frozenset[str] = frozenset(
    {
        CLASSIFIED_BY_HUMAN,
        CLASSIFIED_BY_MODEL,
        CLASSIFIED_BY_SYSTEM_RULE,
    }
)

REVIEW_REASON_METADATA_ONLY_SUPPORT = "metadata_only_support"
REVIEW_REASON_UNSOURCED_SUPPORT = "unsourced_support"
REVIEW_REASON_MODEL_INFERRED_LOGICAL = "model_inferred_logical"
REVIEW_REASON_MODEL_INFERRED_EVIDENTIAL = "model_inferred_evidential"
REVIEW_REASON_AMBIGUOUS_RELATIONSHIP = "ambiguous_relationship"
REVIEW_REASON_LOW_SUPPORT_DENSITY = "low_support_density"

REVIEW_REASON_CODES: frozenset[str] = frozenset(
    {
        REVIEW_REASON_METADATA_ONLY_SUPPORT,
        REVIEW_REASON_UNSOURCED_SUPPORT,
        REVIEW_REASON_MODEL_INFERRED_LOGICAL,
        REVIEW_REASON_MODEL_INFERRED_EVIDENTIAL,
        REVIEW_REASON_AMBIGUOUS_RELATIONSHIP,
        REVIEW_REASON_LOW_SUPPORT_DENSITY,
    }
)


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
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return {}


def _clean_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = _safe_text(item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _normalize_enum(value: Any, *, allowed: frozenset[str], field: str, default: str = "") -> str:
    normalized = _safe_text(value).lower()
    if not normalized and default:
        normalized = default
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return normalized


def relationship_review_required(annotation: dict[str, Any] | None) -> bool:
    if not isinstance(annotation, dict):
        return False
    return _safe_text(annotation.get("support_posture")).lower() in REVIEW_REQUIRED_POSTURES


def _rule_reason_codes(
    *,
    relation_type: str,
    grounding_source: str,
    derivation_mechanism: str,
    support_posture: str,
) -> list[str]:
    reasons: list[str] = []

    if relation_type in STRONG_RELATION_TYPES and grounding_source == GROUNDING_STRUCTURED_METADATA:
        reasons.append(REVIEW_REASON_METADATA_ONLY_SUPPORT)

    if relation_type in STRONG_RELATION_TYPES and grounding_source == GROUNDING_NONE:
        reasons.append(REVIEW_REASON_UNSOURCED_SUPPORT)

    if relation_type == RELATION_LOGICAL_INFERENCE and derivation_mechanism == DERIVATION_MODEL_INFERRED:
        reasons.append(REVIEW_REASON_MODEL_INFERRED_LOGICAL)

    if relation_type == RELATION_EVIDENTIAL_SUPPORT and derivation_mechanism == DERIVATION_MODEL_INFERRED:
        reasons.append(REVIEW_REASON_MODEL_INFERRED_EVIDENTIAL)

    if support_posture == SUPPORT_POSTURE_NEEDS_REVIEW:
        reasons.append(REVIEW_REASON_AMBIGUOUS_RELATIONSHIP)

    if support_posture == SUPPORT_POSTURE_PROPOSED:
        reasons.append(REVIEW_REASON_LOW_SUPPORT_DENSITY)

    return reasons


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def normalize_relationship_annotation(value: Any) -> dict[str, Any]:
    annotation = _json_object_snapshot(value)
    if not annotation:
        return {}

    relation_type = _normalize_enum(
        annotation.get("relation_type"),
        allowed=RELATION_TYPES,
        field="relationship_annotation.relation_type",
    )
    grounding_source = _normalize_enum(
        annotation.get("grounding_source"),
        allowed=GROUNDING_SOURCES,
        field="relationship_annotation.grounding_source",
    )
    derivation_mechanism = _normalize_enum(
        annotation.get("derivation_mechanism"),
        allowed=DERIVATION_MECHANISMS,
        field="relationship_annotation.derivation_mechanism",
    )
    classified_by = _normalize_enum(
        annotation.get("classified_by"),
        allowed=CLASSIFIED_BY,
        field="relationship_annotation.classified_by",
        default=CLASSIFIED_BY_MODEL,
    )
    support_posture = _normalize_enum(
        annotation.get("support_posture"),
        allowed=SUPPORT_POSTURES,
        field="relationship_annotation.support_posture",
        default=SUPPORT_POSTURE_PROPOSED if classified_by == CLASSIFIED_BY_MODEL else SUPPORT_POSTURE_NEEDS_REVIEW,
    )

    _require(
        not (
            classified_by == CLASSIFIED_BY_MODEL
            and support_posture == SUPPORT_POSTURE_CONFIRMED
        ),
        "model-classified relationship annotations cannot be confirmed without human or system-rule review.",
    )
    _require(
        not (
            relation_type in STRONG_RELATION_TYPES
            and grounding_source in {GROUNDING_STRUCTURED_METADATA, GROUNDING_NONE}
            and support_posture == SUPPORT_POSTURE_CONFIRMED
        ),
        "metadata-only or unsourced strong relationships cannot be confirmed.",
    )
    _require(
        not (
            relation_type == RELATION_EVIDENTIAL_SUPPORT
            and grounding_source == GROUNDING_NONE
        ),
        "evidential_support relationships require a grounding_source.",
    )

    provided_reason_codes = _clean_text_list(annotation.get("review_reason_codes"))
    _require(
        not provided_reason_codes,
        "relationship_annotation.review_reason_codes is rule-generated and must not be supplied by callers.",
    )

    generated_reason_codes = _rule_reason_codes(
        relation_type=relation_type,
        grounding_source=grounding_source,
        derivation_mechanism=derivation_mechanism,
        support_posture=support_posture,
    )
    reason_codes = []
    for code in generated_reason_codes:
        if code not in reason_codes:
            reason_codes.append(code)

    if relationship_review_required({"support_posture": support_posture}):
        _require(
            bool(reason_codes),
            "relationship_annotation.review_reason_codes must include a rule reason when support_posture requires review.",
        )

    return {
        "relation_type": relation_type,
        "grounding_source": grounding_source,
        "derivation_mechanism": derivation_mechanism,
        "support_posture": support_posture,
        "review_reason_codes": reason_codes,
        "source_refs": _clean_text_list(annotation.get("source_refs")),
        "rationale": _safe_text(annotation.get("rationale")),
        "classified_by": classified_by,
    }
