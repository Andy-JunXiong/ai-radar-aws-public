from __future__ import annotations

from typing import Any

from app.services.project_review_record_service import list_project_review_records
from app.services.project_takeaway_constants import (
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
)


REJECTED_LEARNING_BUFFER_SCHEMA_VERSION = 1
BUFFER_OUTCOMES = {REVIEW_OUTCOME_REJECTED, REVIEW_OUTCOME_DISMISSED}
DEFAULT_LIMIT = 5
MAX_LIMIT = 20


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value if _safe_text(item)]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bounded_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(_safe_int(limit) or DEFAULT_LIMIT, MAX_LIMIT))


def _pattern_key(record: dict[str, Any]) -> str:
    blocked_actions = ",".join(_safe_list(record.get("blocked_downstream_actions"))) or "none"
    return "|".join(
        [
            _safe_text(record.get("candidate_source")) or "unknown_source",
            _safe_text(record.get("verification_status")) or "unknown_verification",
            f"blocked:{blocked_actions}",
            _safe_text(record.get("outcome")) or "unknown_outcome",
        ]
    )


def _build_caution_item(record: dict[str, Any]) -> dict[str, Any]:
    outcome = _safe_text(record.get("outcome"))
    reason = _safe_text(record.get("reason"))
    signal_title = _safe_text(record.get("signal_title"))
    verification_status = _safe_text(record.get("verification_status"))
    blocked_actions = _safe_list(record.get("blocked_downstream_actions"))
    unsupported_claim_count = _safe_int(record.get("unsupported_claim_count"))
    inferred_claim_count = _safe_int(record.get("inferred_claim_count"))

    return {
        "record_id": _safe_text(record.get("id")),
        "project_id": _safe_text(record.get("project_id")),
        "signal_id": _safe_text(record.get("signal_id")),
        "signal_title": signal_title,
        "outcome": outcome,
        "review_reason": reason,
        "candidate_source": _safe_text(record.get("candidate_source")),
        "verification_status": verification_status,
        "blocked_downstream_actions": blocked_actions,
        "unsupported_claim_count": unsupported_claim_count,
        "inferred_claim_count": inferred_claim_count,
        "confidence_label": _safe_text(record.get("confidence_label")),
        "reviewed_at": _safe_text(record.get("reviewed_at") or record.get("updated_at")),
        "pattern_key": _pattern_key(record),
        "caution": _build_caution_text(
            outcome=outcome,
            signal_title=signal_title,
            reason=reason,
            verification_status=verification_status,
            blocked_actions=blocked_actions,
            unsupported_claim_count=unsupported_claim_count,
            inferred_claim_count=inferred_claim_count,
        ),
    }


def _build_caution_text(
    *,
    outcome: str,
    signal_title: str,
    reason: str,
    verification_status: str,
    blocked_actions: list[str],
    unsupported_claim_count: int,
    inferred_claim_count: int,
) -> str:
    subject = signal_title or "A prior Project Takeaway candidate"
    parts = [f"{subject} was {outcome or 'closed'} in review."]
    if reason:
        parts.append(f"Reviewer reason: {reason}.")
    if verification_status:
        parts.append(f"Verification status was {verification_status}.")
    if blocked_actions:
        parts.append(f"Blocked actions: {', '.join(blocked_actions)}.")
    if unsupported_claim_count > 0:
        parts.append(f"Unsupported or contradicted claims: {unsupported_claim_count}.")
    if inferred_claim_count > 0:
        parts.append(f"Inferred claims: {inferred_claim_count}.")
    return " ".join(parts)


def _build_prompt_readiness(
    *,
    source_record_count: int,
    caution_items: list[dict[str, Any]],
    outcome_counts: dict[str, int],
) -> dict[str, Any]:
    if not source_record_count:
        return {
            "status": "not_ready",
            "safe_for_prompt_injection": False,
            "reasons": ["No Project ReviewRecords matched the current query."],
            "next_action": "Create or inspect Project Takeaway review records before considering prompt wiring.",
        }

    if not caution_items:
        return {
            "status": "not_ready",
            "safe_for_prompt_injection": False,
            "reasons": [
                "No rejected or dismissed review records matched the current query.",
                f"Current outcomes: {', '.join(f'{key}={value}' for key, value in sorted(outcome_counts.items()))}.",
            ],
            "next_action": "Wait until real rejected or dismissed reviews exist; do not synthesize caution context from watch or action records.",
        }

    return {
        "status": "review_ready",
        "safe_for_prompt_injection": False,
        "reasons": [
            "Rejected or dismissed review records are available as bounded caution context.",
            "Human review of the caution text is still required before any generator prompt wiring.",
        ],
        "next_action": "Review the caution items in diagnostics before designing a separate prompt-injection slice.",
    }


def build_rejected_learning_buffer(
    *,
    project_id: str | None = None,
    signal_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    bounded_limit = _bounded_limit(limit)
    records = list_project_review_records(project_id=project_id, signal_id=signal_id)
    outcome_counts: dict[str, int] = {}
    for record in records:
        outcome = _safe_text(record.get("outcome")).lower() or "unknown"
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    caution_items = [
        _build_caution_item(record)
        for record in records
        if _safe_text(record.get("outcome")).lower() in BUFFER_OUTCOMES
    ][:bounded_limit]

    return {
        "schema_version": REJECTED_LEARNING_BUFFER_SCHEMA_VERSION,
        "context_role": "bounded_caution",
        "source": "project_review_records",
        "evidence_boundary": "not_factual_evidence",
        "project_id": _safe_text(project_id),
        "signal_id": _safe_text(signal_id),
        "limit": bounded_limit,
        "source_record_count": len(records),
        "outcome_counts": outcome_counts,
        "buffer_outcomes": sorted(BUFFER_OUTCOMES),
        "prompt_readiness": _build_prompt_readiness(
            source_record_count=len(records),
            caution_items=caution_items,
            outcome_counts=outcome_counts,
        ),
        "item_count": len(caution_items),
        "items": caution_items,
    }
