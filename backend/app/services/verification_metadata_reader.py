from __future__ import annotations

from typing import Any

from app.services.model_provenance_service import normalize_model_provenance


ACTION_PROJECT_TAKEAWAY_CANDIDATE = "project_takeaway_candidate"
ACTION_LOW_RISK_ACTION_CANDIDATE = "low_risk_action_candidate"
ACTION_WATCH_ONLY = "watch_only"
ACTION_STRONG_RECOMMENDATION = "strong_recommendation"

STATUS_UNSUPPORTED = "unsupported"
STATUS_CONTRADICTED = "contradicted"
STATUS_NOT_VERIFIABLE = "not_verifiable"
STATUS_WEAKLY_SUPPORTED = "weakly_supported"
STATUS_UNVERIFIED_MANUAL_ENTRY = "unverified_manual_entry"
STATUS_KNOWLEDGE_CONVERGENCE_REVIEW_CANDIDATE = "knowledge_convergence_review_candidate"

PROJECT_TAKEAWAY_BLOCKING_STATUSES = {
    STATUS_UNSUPPORTED,
    STATUS_CONTRADICTED,
    STATUS_NOT_VERIFIABLE,
    STATUS_UNVERIFIED_MANUAL_ENTRY,
}

LOW_RISK_ACTION_BLOCKING_STATUSES = PROJECT_TAKEAWAY_BLOCKING_STATUSES | {
    STATUS_WEAKLY_SUPPORTED,
    STATUS_KNOWLEDGE_CONVERGENCE_REVIEW_CANDIDATE,
}

WATCH_FRIENDLY_STATUSES = {
    "partially_verified",
    "verified",
    "verified_with_limitations",
    STATUS_WEAKLY_SUPPORTED,
}


def get_verified_insight_object(verification: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(verification, dict):
        return {}
    verified_insight = verification.get("verified_insight")
    return verified_insight if isinstance(verified_insight, dict) else {}


def get_verification_status(verification: dict[str, Any] | None) -> str:
    if not isinstance(verification, dict):
        return ""
    verified_insight = get_verified_insight_object(verification)
    return str(
        verification.get("verification_status")
        or verified_insight.get("status")
        or ""
    ).strip().lower()


def get_claim_support_summary(verification: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(verification, dict):
        return {}

    claim_support_summary = verification.get("claim_support_summary")
    if isinstance(claim_support_summary, dict):
        return {
            str(key): _safe_int(value)
            for key, value in claim_support_summary.items()
        }

    verified_insight = get_verified_insight_object(verification)
    claims = verified_insight.get("claims")
    if isinstance(claims, dict) and isinstance(claims.get("support_summary"), dict):
        return {
            str(key): _safe_int(value)
            for key, value in claims["support_summary"].items()
        }

    return {}


def get_blocked_downstream_actions(verification: dict[str, Any] | None) -> list[str]:
    if not isinstance(verification, dict):
        return []

    blocked_actions = verification.get("blocked_downstream_actions")
    if isinstance(blocked_actions, list):
        return [str(action) for action in blocked_actions]

    verified_insight = get_verified_insight_object(verification)
    action_policy = verified_insight.get("action_policy")
    if isinstance(action_policy, dict) and isinstance(action_policy.get("blocked"), list):
        return [str(action) for action in action_policy["blocked"]]

    return []


def get_allowed_downstream_actions(verification: dict[str, Any] | None) -> list[str]:
    if not isinstance(verification, dict):
        return []

    allowed_actions = verification.get("allowed_downstream_actions")
    if isinstance(allowed_actions, list):
        return [str(action) for action in allowed_actions]

    verified_insight = get_verified_insight_object(verification)
    action_policy = verified_insight.get("action_policy")
    if isinstance(action_policy, dict) and isinstance(action_policy.get("allowed"), list):
        return [str(action) for action in action_policy["allowed"]]

    return []


def get_conflicting_downstream_actions(verification: dict[str, Any] | None) -> list[str]:
    allowed = {str(action).strip() for action in get_allowed_downstream_actions(verification)}
    blocked = {str(action).strip() for action in get_blocked_downstream_actions(verification)}
    allowed.discard("")
    blocked.discard("")
    return sorted(allowed.intersection(blocked))


def get_evidence_level(verification: dict[str, Any] | None) -> str:
    if not isinstance(verification, dict):
        return ""

    evidence_level = verification.get("evidence_level")
    if evidence_level:
        return str(evidence_level or "").strip().lower()

    evidence_quality = verification.get("evidence_quality")
    if isinstance(evidence_quality, dict) and evidence_quality.get("level"):
        return str(evidence_quality.get("level") or "").strip().lower()

    verified_insight = get_verified_insight_object(verification)
    evidence = verified_insight.get("evidence")
    if isinstance(evidence, dict) and evidence.get("level"):
        return str(evidence.get("level") or "").strip().lower()

    return ""


def has_project_takeaway_verification_context(verification: dict[str, Any] | None) -> bool:
    if not isinstance(verification, dict) or not verification:
        return False

    if isinstance(verification.get("verified_insight"), dict):
        return True
    if str(verification.get("verification_status") or "").strip():
        return True
    if isinstance(verification.get("claim_support_summary"), dict):
        return True
    if isinstance(verification.get("allowed_downstream_actions"), list):
        return True
    if isinstance(verification.get("blocked_downstream_actions"), list):
        return True
    if bool(verification.get("knowledge_convergence")):
        return True

    return False


def get_confidence_score(verification: dict[str, Any] | None) -> float | None:
    if not isinstance(verification, dict):
        return None

    if verification.get("confidence_score") is not None:
        return _safe_float_or_none(verification.get("confidence_score"))

    verified_insight = get_verified_insight_object(verification)
    confidence = verified_insight.get("confidence")
    if isinstance(confidence, dict):
        return _safe_float_or_none(confidence.get("score"))

    return None


def get_confidence_label(verification: dict[str, Any] | None) -> str:
    if not isinstance(verification, dict):
        return ""

    if verification.get("confidence_label"):
        return str(verification.get("confidence_label") or "").strip()

    verified_insight = get_verified_insight_object(verification)
    confidence = verified_insight.get("confidence")
    if isinstance(confidence, dict):
        return str(confidence.get("label") or "").strip()

    return ""


VERIFICATION_CONTRACT_VERSION = 1

VERIFICATION_CONTRACT_REQUIRED_FIELDS_BY_CONTEXT = {
    "general": (
        "verification_status",
        "blocked_downstream_actions",
    ),
    "insight_write": (
        "verification_status",
        "evidence_level",
        "blocked_downstream_actions",
    ),
    "project_takeaway_candidate": (
        "verification_status",
        "blocked_downstream_actions",
        "claim_support_summary",
    ),
    "lifecycle_support_snapshot": (
        "verification_status",
        "blocked_downstream_actions",
    ),
}

BLOCKED_STATUSES_REQUIRING_ACTION_GATES = {
    STATUS_UNSUPPORTED,
    STATUS_CONTRADICTED,
    STATUS_NOT_VERIFIABLE,
    STATUS_UNVERIFIED_MANUAL_ENTRY,
}


def build_verification_contract_snapshot(verification: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "verification_status": get_verification_status(verification),
        "evidence_level": get_evidence_level(verification),
        "allowed_downstream_actions": get_allowed_downstream_actions(verification),
        "blocked_downstream_actions": get_blocked_downstream_actions(verification),
        "conflicting_downstream_actions": get_conflicting_downstream_actions(verification),
        "claim_support_summary": get_claim_support_summary(verification),
        "confidence_label": get_confidence_label(verification),
        "confidence_score": get_confidence_score(verification),
        "has_verification_context": has_project_takeaway_verification_context(verification),
    }


def audit_verification_metadata_contract(
    verification: dict[str, Any] | None,
    *,
    context: str = "general",
) -> dict[str, Any]:
    normalized_context = str(context or "general").strip().lower()
    required_fields = VERIFICATION_CONTRACT_REQUIRED_FIELDS_BY_CONTEXT.get(
        normalized_context,
        VERIFICATION_CONTRACT_REQUIRED_FIELDS_BY_CONTEXT["general"],
    )
    snapshot = build_verification_contract_snapshot(verification)
    findings: list[dict[str, str]] = []

    if not isinstance(verification, dict) or not verification:
        findings.append(
            _contract_finding(
                code="missing_verification_metadata",
                severity="error",
                field="verification",
                message="Verification metadata is missing for this contract context.",
            )
        )

    for field in required_fields:
        if not _verification_contract_field_present(verification, field):
            findings.append(
                _contract_finding(
                    code=f"missing_{field}",
                    severity="error",
                    field=field,
                    message=f"{field} is required for {normalized_context} verification contract audit.",
                )
            )

    verification_status = snapshot["verification_status"]
    evidence_level = snapshot["evidence_level"]
    blocked_actions = snapshot["blocked_downstream_actions"]
    conflicting_actions = snapshot["conflicting_downstream_actions"]

    if conflicting_actions:
        findings.append(
            _contract_finding(
                code="conflicting_downstream_actions",
                severity="warning",
                field="allowed_downstream_actions,blocked_downstream_actions",
                message=(
                    "The same downstream action appears in both allowed and blocked metadata: "
                    f"{', '.join(conflicting_actions)}."
                ),
            )
        )

    if verification_status in {"verified", "verified_with_limitations"} and evidence_level in {"insufficient", "thin"}:
        findings.append(
            _contract_finding(
                code="verified_status_with_low_evidence",
                severity="warning",
                field="evidence_level",
                message="Verified-style status is paired with low evidence; reviewer attention is recommended.",
            )
        )

    if verification_status in BLOCKED_STATUSES_REQUIRING_ACTION_GATES:
        expected_blocks = {ACTION_PROJECT_TAKEAWAY_CANDIDATE, ACTION_LOW_RISK_ACTION_CANDIDATE}
        missing_blocks = sorted(expected_blocks.difference(set(blocked_actions)))
        if missing_blocks:
            findings.append(
                _contract_finding(
                    code="blocked_status_missing_downstream_blocks",
                    severity="warning",
                    field="blocked_downstream_actions",
                    message=(
                        f"{verification_status} should normally block downstream action gates; "
                        f"missing: {', '.join(missing_blocks)}."
                    ),
                )
            )

    if (
        verification_status == STATUS_KNOWLEDGE_CONVERGENCE_REVIEW_CANDIDATE
        and ACTION_LOW_RISK_ACTION_CANDIDATE not in blocked_actions
    ):
        findings.append(
            _contract_finding(
                code="knowledge_convergence_missing_action_block",
                severity="warning",
                field="blocked_downstream_actions",
                message="Knowledge convergence is review context and should block low-risk Action by default.",
            )
        )

    return {
        "contract_version": VERIFICATION_CONTRACT_VERSION,
        "audit_mode": "soft_report_only",
        "context": normalized_context,
        "required_fields": list(required_fields),
        "normalized": snapshot,
        "finding_count": len(findings),
        "findings": findings,
        "contract_ok": not any(finding["severity"] == "error" for finding in findings),
    }


def get_model_provenance(verification: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(verification, dict):
        return normalize_model_provenance(None)

    produced_by_model = verification.get("produced_by_model")
    if isinstance(produced_by_model, dict):
        return normalize_model_provenance(produced_by_model)

    verified_insight = get_verified_insight_object(verification)
    return normalize_model_provenance(verified_insight.get("produced_by_model"))


def build_action_eligibility_summary(verification: dict[str, Any] | None) -> dict[str, Any]:
    verification_status = get_verification_status(verification)
    claim_support_summary = get_claim_support_summary(verification)
    allowed_actions = get_allowed_downstream_actions(verification)
    blocked_actions = get_blocked_downstream_actions(verification)
    conflicting_actions = get_conflicting_downstream_actions(verification)
    has_verification_context = has_project_takeaway_verification_context(verification)

    unsupported_count = _safe_int(claim_support_summary.get("unsupported")) + _safe_int(
        claim_support_summary.get("contradicted")
    )
    inferred_count = _safe_int(claim_support_summary.get("inferred"))

    project_takeaway_blocked = (
        not has_verification_context
        or ACTION_PROJECT_TAKEAWAY_CANDIDATE in blocked_actions
        or verification_status in PROJECT_TAKEAWAY_BLOCKING_STATUSES
        or unsupported_count > 0
    )
    action_blocked = (
        not has_verification_context
        or ACTION_LOW_RISK_ACTION_CANDIDATE in blocked_actions
        or verification_status in LOW_RISK_ACTION_BLOCKING_STATUSES
        or unsupported_count > 0
    )
    watch_allowed = (
        ACTION_WATCH_ONLY in allowed_actions
        or ACTION_PROJECT_TAKEAWAY_CANDIDATE in allowed_actions
        or verification_status in WATCH_FRIENDLY_STATUSES
    )

    project_takeaway_reason = _build_project_takeaway_reason(
        blocked=project_takeaway_blocked,
        verification_status=verification_status,
        unsupported_count=unsupported_count,
        blocked_actions=blocked_actions,
    )
    watch_reason = _build_watch_reason(
        allowed=watch_allowed,
        verification_status=verification_status,
        inferred_count=inferred_count,
        blocked_actions=blocked_actions,
    )
    action_reason = _build_low_risk_action_reason(
        blocked=action_blocked,
        verification_status=verification_status,
        unsupported_count=unsupported_count,
        inferred_count=inferred_count,
        blocked_actions=blocked_actions,
    )

    return {
        "project_takeaway_candidate": {
            "allowed": not project_takeaway_blocked,
            "reason": project_takeaway_reason,
            "gate": _build_gate_metadata(
                gate_id=ACTION_PROJECT_TAKEAWAY_CANDIDATE,
                allowed=not project_takeaway_blocked,
                verification_status=verification_status,
                has_verification_context=has_verification_context,
                unsupported_count=unsupported_count,
                inferred_count=inferred_count,
                blocked_actions=blocked_actions,
                conflicting_actions=conflicting_actions,
            ),
        },
        "watch_only": {
            "allowed": watch_allowed,
            "reason": watch_reason,
            "gate": _build_gate_metadata(
                gate_id=ACTION_WATCH_ONLY,
                allowed=watch_allowed,
                verification_status=verification_status,
                has_verification_context=has_verification_context,
                unsupported_count=unsupported_count,
                inferred_count=inferred_count,
                blocked_actions=blocked_actions,
                conflicting_actions=conflicting_actions,
            ),
        },
        "low_risk_action_candidate": {
            "allowed": not action_blocked,
            "reason": action_reason,
            "gate": _build_gate_metadata(
                gate_id=ACTION_LOW_RISK_ACTION_CANDIDATE,
                allowed=not action_blocked,
                verification_status=verification_status,
                has_verification_context=has_verification_context,
                unsupported_count=unsupported_count,
                inferred_count=inferred_count,
                blocked_actions=blocked_actions,
                conflicting_actions=conflicting_actions,
            ),
        },
        "signals": {
            "verification_status": verification_status,
            "has_verification_context": has_verification_context,
            "unsupported_or_contradicted_claim_count": unsupported_count,
            "inferred_claim_count": inferred_count,
            "allowed_downstream_actions": allowed_actions,
            "blocked_downstream_actions": blocked_actions,
            "conflicting_downstream_actions": conflicting_actions,
        },
    }


def _build_gate_metadata(
    *,
    gate_id: str,
    allowed: bool,
    verification_status: str,
    has_verification_context: bool,
    unsupported_count: int,
    inferred_count: int,
    blocked_actions: list[str],
    conflicting_actions: list[str],
) -> dict[str, Any]:
    reason_codes = _gate_reason_codes(
        gate_id=gate_id,
        allowed=allowed,
        verification_status=verification_status,
        has_verification_context=has_verification_context,
        unsupported_count=unsupported_count,
        inferred_count=inferred_count,
        blocked_actions=blocked_actions,
        conflicting_actions=conflicting_actions,
    )
    if not allowed:
        severity = "critical"
        enforcement_mode = "hard_block"
    elif reason_codes:
        severity = "warning"
        enforcement_mode = "warn_proceed"
    else:
        severity = "info"
        enforcement_mode = "pass"

    return {
        "gate_id": gate_id,
        "evaluation": "deterministic_verification_metadata",
        "severity": severity,
        "enforcement_mode": enforcement_mode,
        "triggered": enforcement_mode != "pass",
        "reason_codes": reason_codes,
    }


def _gate_reason_codes(
    *,
    gate_id: str,
    allowed: bool,
    verification_status: str,
    has_verification_context: bool,
    unsupported_count: int,
    inferred_count: int,
    blocked_actions: list[str],
    conflicting_actions: list[str],
) -> list[str]:
    codes: list[str] = []
    if not has_verification_context:
        codes.append("missing_verification_context")
    if gate_id in blocked_actions:
        codes.append("explicit_downstream_block")
    if unsupported_count > 0:
        codes.append("unsupported_or_contradicted_claims")

    if gate_id == ACTION_PROJECT_TAKEAWAY_CANDIDATE:
        if verification_status in PROJECT_TAKEAWAY_BLOCKING_STATUSES:
            codes.append("blocking_verification_status")
        if allowed and verification_status == STATUS_WEAKLY_SUPPORTED:
            codes.append("weak_evidence_review_only")
        if allowed and inferred_count > 0:
            codes.append("inferred_claim_context")
    elif gate_id == ACTION_LOW_RISK_ACTION_CANDIDATE:
        if verification_status in LOW_RISK_ACTION_BLOCKING_STATUSES:
            codes.append("blocking_verification_status")
        if ACTION_STRONG_RECOMMENDATION in blocked_actions:
            codes.append("strong_recommendation_blocked")
        if allowed and (inferred_count > 0 or verification_status == "partially_verified"):
            codes.append("reviewer_confirmation_needed")
    elif gate_id == ACTION_WATCH_ONLY:
        if gate_id in conflicting_actions:
            codes.append("conflicting_allowed_and_blocked_actions")
        if allowed and verification_status == STATUS_WEAKLY_SUPPORTED:
            codes.append("weak_evidence_watch_path")
        if allowed and inferred_count > 0:
            codes.append("inferred_claim_watch_path")

    return _dedupe_strings(codes)


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def _build_project_takeaway_reason(
    *,
    blocked: bool,
    verification_status: str,
    unsupported_count: int,
    blocked_actions: list[str],
) -> str:
    if ACTION_PROJECT_TAKEAWAY_CANDIDATE in blocked_actions:
        return "Verification explicitly blocks Project Takeaway creation for this insight."
    if not verification_status and not blocked_actions and unsupported_count == 0:
        return "Project Takeaway creation is blocked because verification metadata is missing."
    if unsupported_count > 0:
        return f"{unsupported_count} unsupported or contradicted claim(s) block Project Takeaway creation."
    if verification_status in {STATUS_UNSUPPORTED, STATUS_CONTRADICTED}:
        return "Verification status blocks Project Takeaway creation because the core claim is unsupported or contradicted."
    if verification_status == STATUS_NOT_VERIFIABLE:
        return "Project Takeaway creation is blocked because the source evidence is not traceable enough."
    if verification_status == STATUS_UNVERIFIED_MANUAL_ENTRY:
        return "Project Takeaway creation is blocked because this entry still requires verification."
    if blocked:
        return "Project Takeaway creation is blocked by verification quality."
    return "Project Takeaway review is allowed."


def _build_watch_reason(
    *,
    allowed: bool,
    verification_status: str,
    inferred_count: int,
    blocked_actions: list[str],
) -> str:
    if allowed and ACTION_WATCH_ONLY in blocked_actions:
        return "Watch is allowed, but the metadata also contains a watch block that needs reviewer attention."
    if allowed and verification_status == STATUS_WEAKLY_SUPPORTED:
        return "Watch is the safer downstream path because evidence is weak but still worth monitoring."
    if allowed and inferred_count > 0:
        return f"Watch is suggested while {inferred_count} inferred claim(s) wait for stronger evidence."
    if allowed:
        return "Watch is the safer downstream path for limited or partial evidence."
    return "Watch is not explicitly supported by the current verification metadata."


def _build_low_risk_action_reason(
    *,
    blocked: bool,
    verification_status: str,
    unsupported_count: int,
    inferred_count: int,
    blocked_actions: list[str],
) -> str:
    if ACTION_LOW_RISK_ACTION_CANDIDATE in blocked_actions:
        return "Verification explicitly blocks low-risk Action; this insight is not action-ready."
    if not verification_status and not blocked_actions and unsupported_count == 0:
        return "Low-risk Action is blocked because verification metadata is missing."
    if ACTION_STRONG_RECOMMENDATION in blocked_actions:
        return "Verification blocks strong recommendations, so low-risk Action needs reviewer caution."
    if unsupported_count > 0:
        return f"{unsupported_count} unsupported or contradicted claim(s) block low-risk Action."
    if verification_status in {STATUS_UNSUPPORTED, STATUS_CONTRADICTED}:
        return "Low-risk Action is blocked because the core claim is unsupported or contradicted."
    if verification_status == STATUS_NOT_VERIFIABLE:
        return "Low-risk Action is blocked because the source evidence is not traceable enough."
    if verification_status == STATUS_UNVERIFIED_MANUAL_ENTRY:
        return "Low-risk Action is blocked because this entry still requires verification."
    if verification_status == STATUS_KNOWLEDGE_CONVERGENCE_REVIEW_CANDIDATE:
        return "Low-risk Action is blocked because Knowledge convergence is review context, not verified action evidence."
    if verification_status == STATUS_WEAKLY_SUPPORTED:
        return "Low-risk Action is blocked until weak evidence is upgraded or independently confirmed."
    if blocked:
        return "Verification quality supports review or watch, but not action."
    if inferred_count > 0 or verification_status == "partially_verified":
        return "Action is available only after reviewer confirms the inferred or partial claim context."
    return "Verification does not block low-risk action."


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _verification_contract_field_present(verification: dict[str, Any] | None, field: str) -> bool:
    if field == "verification_status":
        return bool(get_verification_status(verification))
    if field == "evidence_level":
        return bool(get_evidence_level(verification))
    if field == "allowed_downstream_actions":
        return _actions_field_present(verification, "allowed_downstream_actions", "allowed")
    if field == "blocked_downstream_actions":
        return _actions_field_present(verification, "blocked_downstream_actions", "blocked")
    if field == "claim_support_summary":
        if not isinstance(verification, dict):
            return False
        if isinstance(verification.get("claim_support_summary"), dict):
            return True
        verified_insight = get_verified_insight_object(verification)
        claims = verified_insight.get("claims")
        return isinstance(claims, dict) and isinstance(claims.get("support_summary"), dict)
    return False


def _actions_field_present(
    verification: dict[str, Any] | None,
    top_level_field: str,
    nested_field: str,
) -> bool:
    if not isinstance(verification, dict):
        return False
    if isinstance(verification.get(top_level_field), list):
        return True
    verified_insight = get_verified_insight_object(verification)
    action_policy = verified_insight.get("action_policy")
    return isinstance(action_policy, dict) and isinstance(action_policy.get(nested_field), list)


def _contract_finding(*, code: str, severity: str, field: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
    }
