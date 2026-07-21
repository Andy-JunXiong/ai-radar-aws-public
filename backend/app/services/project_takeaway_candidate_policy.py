from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.verification_metadata_reader import (
    build_action_eligibility_summary,
    get_verification_status,
    has_project_takeaway_verification_context,
)


CandidateSource = Literal[
    "verified_insight",
    "knowledge_convergence",
    "confirmed_final_takeaway",
    "unverified_manual_entry",
    "manual_project_takeaway_override",
]

INVARIANT_SCOPE = (
    "Verification Boundary #1",
    "Verification Boundary #3",
    "Project Takeaway Gates #1",
    "Project Takeaway Gates #3",
    "Project Takeaway Gates #4",
    "Project Takeaway Gates #6",
    "Project Takeaway Gates #7",
    "Reflection Boundary #4",
)


@dataclass(frozen=True)
class ProjectTakeawayCandidatePolicy:
    allowed: bool
    reason: str
    source_category: CandidateSource
    action_eligibility: dict[str, Any]


@dataclass(frozen=True)
class ProjectTakeawayCandidateEnvelope:
    candidate_source: CandidateSource
    verification_metadata: dict[str, Any]
    policy: ProjectTakeawayCandidatePolicy
    invariant_scope: tuple[str, ...] = INVARIANT_SCOPE


def build_project_takeaway_candidate_input(
    verification: dict[str, Any] | None,
) -> ProjectTakeawayCandidateEnvelope:
    normalized = normalize_project_takeaway_candidate_verification(verification)
    source_category = classify_project_takeaway_candidate_source(normalized)
    policy = evaluate_project_takeaway_candidate_policy(
        normalized,
        source_category=source_category,
    )
    if not policy.allowed:
        raise ValueError(policy.reason)
    return ProjectTakeawayCandidateEnvelope(
        candidate_source=source_category,
        verification_metadata=normalized,
        policy=policy,
    )


def normalize_project_takeaway_candidate_verification(
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = dict(verification) if isinstance(verification, dict) else {}
    if not _is_review_context_only_candidate(normalized):
        return normalized

    blocked_actions = normalized.get("blocked_downstream_actions")
    blocked = [str(action) for action in blocked_actions] if isinstance(blocked_actions, list) else []
    for action in ("low_risk_action_candidate", "strong_recommendation"):
        if action not in blocked:
            blocked.append(action)
    normalized["blocked_downstream_actions"] = blocked
    return normalized


def classify_project_takeaway_candidate_source(
    verification: dict[str, Any] | None,
) -> CandidateSource:
    metadata = verification if isinstance(verification, dict) else {}
    if metadata.get("manual_project_takeaway_override"):
        return "manual_project_takeaway_override"
    if (
        metadata.get("confirmed_final_takeaway")
        or metadata.get("candidate_requested_from") == "confirmed_final_takeaway"
        or get_verification_status(metadata) == "confirmed_final_takeaway_review_candidate"
    ):
        return "confirmed_final_takeaway"
    if (
        metadata.get("knowledge_convergence")
        or get_verification_status(metadata) == "knowledge_convergence_review_candidate"
    ):
        return "knowledge_convergence"
    if get_verification_status(metadata) == "unverified_manual_entry":
        return "unverified_manual_entry"
    return "verified_insight"


def evaluate_project_takeaway_candidate_policy(
    verification: dict[str, Any] | None,
    *,
    source_category: CandidateSource | None = None,
) -> ProjectTakeawayCandidatePolicy:
    metadata = verification if isinstance(verification, dict) else {}
    resolved_source = source_category or classify_project_takeaway_candidate_source(metadata)
    action_eligibility = build_action_eligibility_summary(metadata)
    project_takeaway = action_eligibility["project_takeaway_candidate"]

    if resolved_source == "manual_project_takeaway_override":
        if not _safe_text(metadata.get("manual_override_note")):
            return _blocked(
                reason="Manual Project Takeaway override requires an override note.",
                source_category=resolved_source,
                action_eligibility=action_eligibility,
            )
        return ProjectTakeawayCandidatePolicy(
            allowed=True,
            reason="Manual Project Takeaway override is explicit and auditable.",
            source_category=resolved_source,
            action_eligibility=action_eligibility,
        )

    if not has_project_takeaway_verification_context(metadata):
        return _blocked(
            reason=(
                "Project Takeaway candidate creation requires verification metadata "
                "or an explicit manual override note."
            ),
            source_category=resolved_source,
            action_eligibility=action_eligibility,
        )

    if _safe_text(metadata.get("review_priority")).lower() == "do not act":
        return _blocked(
            reason="Review priority is Do Not Act; project takeaway candidate creation is blocked.",
            source_category=resolved_source,
            action_eligibility=action_eligibility,
        )

    if resolved_source == "unverified_manual_entry":
        return _blocked(
            reason=(
                "Unverified manual entries must pass verification or explicit override "
                "before Project Takeaway creation."
            ),
            source_category=resolved_source,
            action_eligibility=action_eligibility,
        )

    if not bool(project_takeaway.get("allowed")):
        return _blocked(
            reason=_project_takeaway_block_reason(str(project_takeaway.get("reason") or "")),
            source_category=resolved_source,
            action_eligibility=action_eligibility,
        )

    return ProjectTakeawayCandidatePolicy(
        allowed=True,
        reason=str(project_takeaway.get("reason") or "Project Takeaway review is allowed."),
        source_category=resolved_source,
        action_eligibility=action_eligibility,
    )


def _blocked(
    *,
    reason: str,
    source_category: CandidateSource,
    action_eligibility: dict[str, Any],
) -> ProjectTakeawayCandidatePolicy:
    return ProjectTakeawayCandidatePolicy(
        allowed=False,
        reason=reason,
        source_category=source_category,
        action_eligibility=action_eligibility,
    )


def _project_takeaway_block_reason(reason: str) -> str:
    if "explicitly blocks Project Takeaway" in reason:
        return "Verification blocks project takeaway candidate creation."
    if "unsupported or contradicted claim" in reason:
        return "Unsupported or contradicted claims block project takeaway candidate creation."
    if reason:
        return reason
    return "Verification blocks project takeaway candidate creation."


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _is_review_context_only_candidate(metadata: dict[str, Any]) -> bool:
    status = get_verification_status(metadata)
    return bool(
        metadata.get("knowledge_convergence")
        or status == "knowledge_convergence_review_candidate"
        or metadata.get("confirmed_final_takeaway")
        or metadata.get("candidate_requested_from") == "confirmed_final_takeaway"
        or status == "confirmed_final_takeaway_review_candidate"
    )
