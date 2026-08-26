from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.project_takeaway_constants import (
    PROJECT_IMPROVEMENT_STATUS_CANDIDATE,
    REVIEW_OUTCOME_CONFIRMED,
    normalize_project_takeaway_status,
)


PREVIEW_VERSION = "review_inbox_merge_preview_v1"

NARRATIVE_FIELDS: tuple[str, ...] = (
    "signal_title",
    "signal_summary",
    "takeaway",
    "why_it_matters",
    "fit_reason",
    "benefits",
    "final_reflection",
    "topics",
)

PROVENANCE_FIELDS: tuple[str, ...] = (
    "source_type",
    "candidate_source",
    "manual_session_id",
    "is_manual_source",
    "upload_reason",
    "intended_use",
    "cognitive_layer",
    "produced_by_model",
    "final_takeaway_id",
    "review_bundle_snapshot_id",
)

TIMESTAMP_FIELDS: tuple[str, ...] = (
    "saved_at",
    "created_at",
    "updated_at",
    "reviewed_at",
    "confirmed_at",
)


class MergePreviewValidationError(ValueError):
    def __init__(self, reason_code: str, message: str, *, http_status: int = 400):
        super().__init__(message)
        self.reason_code = reason_code
        self.http_status = http_status


def _text(value: object) -> str:
    return str(value or "").strip()


def _resolve_unique_item(
    items: list[dict[str, Any]],
    signal_id: str,
    *,
    role: str,
) -> dict[str, Any]:
    matches = [item for item in items if _text(item.get("signal_id")) == signal_id]
    if not matches:
        raise MergePreviewValidationError(
            f"{role}_not_found",
            f"{role.capitalize()} Project Takeaway was not found in the selected project.",
            http_status=404,
        )
    if len(matches) > 1:
        raise MergePreviewValidationError(
            f"{role}_ambiguous",
            f"{role.capitalize()} signal_id resolves to multiple Project Takeaways.",
            http_status=409,
        )
    return matches[0]


def _verification_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("verification_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    verified_insight = metadata.get("verified_insight")
    if not isinstance(verified_insight, dict):
        verified_insight = {}
    action_policy = verified_insight.get("action_policy")
    if not isinstance(action_policy, dict):
        action_policy = {}
    claims = verified_insight.get("claims")
    if not isinstance(claims, dict):
        claims = {}

    verification_status = (
        metadata["verification_status"]
        if "verification_status" in metadata
        else verified_insight.get("status")
    )
    claim_support_summary = (
        metadata["claim_support_summary"]
        if "claim_support_summary" in metadata
        else claims.get("support_summary")
    )
    allowed_downstream_actions = (
        metadata["allowed_downstream_actions"]
        if "allowed_downstream_actions" in metadata
        else action_policy.get("allowed", [])
    )
    blocked_downstream_actions = (
        metadata["blocked_downstream_actions"]
        if "blocked_downstream_actions" in metadata
        else action_policy.get("blocked", [])
    )

    return {
        "verification_status": deepcopy(verification_status),
        "claim_support_summary": deepcopy(claim_support_summary),
        "allowed_downstream_actions": deepcopy(allowed_downstream_actions),
        "blocked_downstream_actions": deepcopy(blocked_downstream_actions),
        "action_eligibility": deepcopy(item.get("action_eligibility") or {}),
        "verification_metadata": deepcopy(metadata),
    }


def _item_view(project_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity": {
            "project_id": project_id,
            "signal_id": _text(item.get("signal_id")),
            "status": normalize_project_takeaway_status(item.get("status")),
        },
        "narrative": {field: deepcopy(item.get(field)) for field in NARRATIVE_FIELDS},
        "provenance": {field: deepcopy(item.get(field)) for field in PROVENANCE_FIELDS},
        "verification": _verification_snapshot(item),
        "timestamps": {field: deepcopy(item.get(field)) for field in TIMESTAMP_FIELDS},
    }


def build_project_takeaway_merge_preview(
    *,
    project_id: str,
    items: list[dict[str, Any]],
    source_signal_id: str,
    target_signal_id: str,
    field_resolutions: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized_project_id = _text(project_id)
    normalized_source_id = _text(source_signal_id)
    normalized_target_id = _text(target_signal_id)
    if not normalized_project_id:
        raise MergePreviewValidationError("project_id_required", "project_id is required.")
    if not normalized_source_id:
        raise MergePreviewValidationError("source_signal_id_required", "source_signal_id is required.")
    if not normalized_target_id:
        raise MergePreviewValidationError("target_signal_id_required", "target_signal_id is required.")
    if normalized_source_id == normalized_target_id:
        raise MergePreviewValidationError(
            "same_item_selected",
            "Source and target must be different Project Takeaways.",
        )

    normalized_items = [item for item in items if isinstance(item, dict)]
    source = _resolve_unique_item(normalized_items, normalized_source_id, role="source")
    target = _resolve_unique_item(normalized_items, normalized_target_id, role="target")

    for role, item in (("source", source), ("target", target)):
        item_project_id = _text(item.get("project_id"))
        if item_project_id and item_project_id != normalized_project_id:
            raise MergePreviewValidationError(
                "cross_project_selection",
                f"{role.capitalize()} Project Takeaway belongs to a different project.",
            )

    source_status = normalize_project_takeaway_status(source.get("status"))
    if source_status != PROJECT_IMPROVEMENT_STATUS_CANDIDATE:
        raise MergePreviewValidationError(
            "source_status_not_candidate",
            "Source Project Takeaway must have candidate status for preview v1.",
        )
    target_status = normalize_project_takeaway_status(target.get("status"))
    if target_status != REVIEW_OUTCOME_CONFIRMED:
        raise MergePreviewValidationError(
            "target_status_not_confirmed",
            "Target Project Takeaway must have confirmed status for preview v1.",
        )

    resolutions = field_resolutions or {}
    invalid_fields = sorted(set(resolutions) - set(NARRATIVE_FIELDS))
    if invalid_fields:
        raise MergePreviewValidationError(
            "invalid_field_resolution",
            f"Unsupported narrative field resolution: {invalid_fields[0]}.",
        )
    invalid_selections = sorted(
        field for field, selection in resolutions.items() if selection not in {"source", "target"}
    )
    if invalid_selections:
        raise MergePreviewValidationError(
            "invalid_field_selection",
            f"Field resolution must select source or target: {invalid_selections[0]}.",
        )

    field_comparisons: list[dict[str, Any]] = []
    result_preview: dict[str, Any] = {}
    for field in NARRATIVE_FIELDS:
        source_value = deepcopy(source.get(field))
        target_value = deepcopy(target.get(field))
        selected_from = resolutions.get(field, "target")
        preview_value = deepcopy(source_value if selected_from == "source" else target_value)
        result_preview[field] = preview_value
        field_comparisons.append(
            {
                "field": field,
                "source_value": source_value,
                "target_value": target_value,
                "selected_from": selected_from,
                "preview_value": preview_value,
                "different": source_value != target_value,
            }
        )

    return {
        "preview_version": PREVIEW_VERSION,
        "project_id": normalized_project_id,
        "source_ref": {
            "project_id": normalized_project_id,
            "signal_id": normalized_source_id,
        },
        "target_ref": {
            "project_id": normalized_project_id,
            "signal_id": normalized_target_id,
        },
        "source": _item_view(normalized_project_id, source),
        "target": _item_view(normalized_project_id, target),
        "field_comparisons": field_comparisons,
        "result_preview": result_preview,
        "warnings": [
            {
                "code": "preview_only_no_write",
                "message": "This preview does not mutate either Project Takeaway.",
            },
            {
                "code": "verification_not_combined",
                "message": "Source and target verification and provenance remain separate.",
            },
            {
                "code": "action_gate_not_changed",
                "message": "This preview does not change blocked actions or Action eligibility.",
            },
        ],
        "persisted": False,
        "mutation_performed": False,
    }
