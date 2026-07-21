from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.metrics_event_service import record_verification_event


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _normalized_status(
    *,
    evidence_level: str,
    generation_mode: str,
    claim_results: list[dict[str, Any]] | None = None,
) -> str:
    if generation_mode == "fallback":
        return "needs_human_review"

    if claim_results is not None:
        support_levels = {
            str(claim.get("support_level") or "").lower()
            for claim in claim_results
            if isinstance(claim, dict)
        }
        if evidence_level == "insufficient":
            return "not_verifiable"
        if "contradicted" in support_levels:
            return "contradicted"
        if support_levels and support_levels.issubset({"unsupported"}):
            return "unsupported"
        if support_levels and support_levels.issubset({"inferred"}):
            return "weakly_supported"
        if support_levels.intersection({"unsupported", "inferred", "partially_supported"}):
            return "partially_verified"
        if support_levels and support_levels.issubset({"directly_supported"}):
            return "verified" if evidence_level in {"sufficient", "strong"} else "weakly_supported"

    if evidence_level == "strong":
        return "verified"
    if evidence_level == "sufficient":
        return "verified_with_limitations"
    return "weak_evidence"


def _build_action_policy(
    *,
    evidence_level: str,
    generation_mode: str,
    decision_card_allowed: Any,
    verification_status: str | None = None,
) -> tuple[list[str], list[str]]:
    allowed = ["reflection_draft"]
    blocked = ["strong_recommendation"]

    if verification_status in {"not_verifiable", "unsupported", "contradicted"}:
        allowed.append("observation_only")
        blocked.extend(["decision_card", "project_takeaway_candidate", "low_risk_action_candidate"])
        return list(dict.fromkeys(allowed)), list(dict.fromkeys(blocked))

    if verification_status == "weakly_supported":
        allowed.extend(["weak_insight", "watch_only"])
        blocked.extend(["decision_card", "project_takeaway_candidate", "low_risk_action_candidate"])
        return list(dict.fromkeys(allowed)), list(dict.fromkeys(blocked))

    if verification_status == "partially_verified":
        allowed.extend(["normal_insight", "watch_only", "project_takeaway_candidate"])
        blocked.extend(["decision_card", "low_risk_action_candidate"])
        return list(dict.fromkeys(allowed)), list(dict.fromkeys(blocked))

    if generation_mode == "fallback":
        allowed.extend(["observation_only", "needs_human_review"])
        blocked.extend(["decision_card", "project_takeaway_candidate"])
        return allowed, blocked

    if evidence_level == "insufficient":
        allowed.append("observation_only")
        blocked.extend(["decision_card", "project_takeaway_candidate"])
        return allowed, blocked

    if evidence_level == "thin":
        allowed.extend(["weak_insight", "watch_only"])
        blocked.extend(["decision_card", "project_takeaway_candidate"])
        return allowed, blocked

    if evidence_level == "sufficient":
        allowed.extend(["normal_insight", "watch_only", "project_takeaway_candidate"])
    else:
        allowed.extend(
            [
                "normal_insight",
                "watch_only",
                "project_takeaway_candidate",
                "decision_card",
            ]
        )

    if decision_card_allowed == "watch_only":
        blocked.append("decision_card")
    elif not _as_bool(decision_card_allowed):
        blocked.extend(["decision_card", "project_takeaway_candidate"])

    dedup_allowed = [item for item in dict.fromkeys(allowed) if item not in blocked]
    dedup_blocked = list(dict.fromkeys(blocked))
    return dedup_allowed, dedup_blocked


def _claim_support_confidence_cap(
    *,
    verification_status: str,
    claim_results: list[dict[str, Any]] | None,
) -> float | None:
    if claim_results is None:
        return None

    if verification_status in {"contradicted", "unsupported", "not_verifiable"}:
        return 0.35
    if verification_status == "weakly_supported":
        return 0.55
    if verification_status == "partially_verified":
        return 0.75
    if verification_status == "verified":
        return None
    return 0.65


def _confidence_label(score: Any) -> str:
    numeric = float(score or 0)
    if numeric < 0.45:
        return "low"
    if numeric < 0.75:
        return "medium"
    return "high"


def _build_verified_insight_object(
    *,
    verified_insight_id: str,
    signal_id: str,
    content_fingerprint: str,
    evidence_level: str,
    evidence_quality: dict[str, Any],
    evidence_pack_id: str | None,
    generation_mode: str,
    verification_status: str,
    allowed_actions: list[str],
    blocked_actions: list[str],
    claim_results: list[dict[str, Any]] | None,
    claim_support_summary: dict[str, int],
    confidence_score: float | None,
    confidence_label: str | None,
    confidence_reason: list[str],
    downgrade_reason: str | None,
    limitations: list[str],
    produced_by_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claims = claim_results or []
    unsupported_count = sum(
        1
        for claim in claims
        if str(claim.get("support_level") or "").lower() in {"unsupported", "contradicted"}
    )
    inferred_count = sum(
        1
        for claim in claims
        if str(claim.get("support_level") or "").lower() == "inferred"
    )

    result = {
        "id": verified_insight_id,
        "signal_id": signal_id,
        "schema_version": 1,
        "version": "v1",
        "content_fingerprint": content_fingerprint,
        "generation_mode": generation_mode,
        "status": verification_status,
        "evidence": {
            "level": evidence_level,
            "score": evidence_quality.get("score"),
            "pack_id": evidence_pack_id,
            "summary_provenance": evidence_quality.get("summary_provenance"),
            "reason_codes": evidence_quality.get("reason_codes", []),
        },
        "claims": {
            "count": len(claims),
            "support_summary": claim_support_summary,
            "unsupported_or_contradicted_count": unsupported_count,
            "inferred_count": inferred_count,
            "items": claims,
        },
        "confidence": {
            "score": confidence_score,
            "label": confidence_label,
            "reason": confidence_reason,
        },
        "action_policy": {
            "allowed": allowed_actions,
            "blocked": blocked_actions,
        },
        "downgrade": {
            "applied": bool(downgrade_reason),
            "reason": downgrade_reason,
        },
        "limitations": limitations,
    }
    if produced_by_model:
        result["produced_by_model"] = produced_by_model
    return result


def _record_verified_insight_metric(
    *,
    signal_id: str,
    evidence_level: str,
    result: dict[str, Any],
    claim_results: list[dict[str, Any]] | None,
) -> None:
    unsupported_count = 0
    inferred_count = 0
    for claim in claim_results or []:
        support_level = str(claim.get("support_level") or "").lower()
        if support_level in {"unsupported", "contradicted"}:
            unsupported_count += 1
        if support_level == "inferred":
            inferred_count += 1

    try:
        record_verification_event(
            {
                "signal_id": signal_id,
                "verified_insight_id": result.get("verified_insight_id"),
                "evidence_level": evidence_level,
                "verification_status": result.get("verification_status"),
                "claim_count": len(claim_results or []),
                "unsupported_claim_count": unsupported_count,
                "inferred_claim_count": inferred_count,
                "downgrade_applied": bool(result.get("downgrade_reason")),
                "allowed_downstream_actions": result.get("allowed_downstream_actions", []),
                "blocked_downstream_actions": result.get("blocked_downstream_actions", []),
            }
        )
    except Exception as exc:
        print(f"[metrics] failed to record verification event: {exc}")


def build_verified_insight_metadata(
    *,
    signal_id: str,
    content_fingerprint: str,
    evidence_quality: dict[str, Any],
    low_evidence_gate: dict[str, Any],
    generation_mode: str,
    claim_results: list[dict[str, Any]] | None = None,
    evidence_pack_id: str | None = None,
    produced_by_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_level = str(evidence_quality.get("level") or "thin").lower()
    verification_status = _normalized_status(
        evidence_level=evidence_level,
        generation_mode=str(generation_mode or "").lower(),
        claim_results=claim_results,
    )
    allowed_actions, blocked_actions = _build_action_policy(
        evidence_level=evidence_level,
        generation_mode=str(generation_mode or "").lower(),
        decision_card_allowed=low_evidence_gate.get("decision_card_allowed"),
        verification_status=verification_status if claim_results is not None else None,
    )

    seed = json.dumps(
        {
            "signal_id": signal_id,
            "content_fingerprint": content_fingerprint,
            "verification_status": verification_status,
            "evidence_level": evidence_level,
            "generation_mode": generation_mode,
            "claim_results": claim_results or [],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    verified_insight_id = f"vi_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

    limitations: list[str] = []
    for claim in claim_results or []:
        for note in claim.get("verification_notes") or []:
            if note:
                limitations.append(str(note))

    unsupported_count = len(
        [
            claim
            for claim in claim_results or []
            if str(claim.get("support_level") or "").lower()
            in {"unsupported", "contradicted"}
        ]
    )
    claim_support_summary: dict[str, int] = {}
    for claim in claim_results or []:
        support_level = str(claim.get("support_level") or "unknown").lower()
        claim_support_summary[support_level] = claim_support_summary.get(support_level, 0) + 1

    downgrade_reason = None
    if unsupported_count:
        downgrade_reason = "unsupported_or_contradicted_claims"
    elif verification_status in {"weakly_supported", "partially_verified"}:
        downgrade_reason = "claim_support_limitations"
    elif evidence_level in {"insufficient", "thin"}:
        downgrade_reason = "low_evidence"

    result = {
        "verified_insight_id": verified_insight_id,
        "verification_status": verification_status,
        "allowed_downstream_actions": allowed_actions,
        "blocked_downstream_actions": blocked_actions,
    }
    if produced_by_model:
        result["produced_by_model"] = produced_by_model
    confidence_score: float | None = None
    confidence_label: str | None = None
    confidence_reason: list[str] = []

    if claim_results is not None:
        evidence_confidence = float(low_evidence_gate.get("max_confidence") or 0)
        claim_confidence_cap = _claim_support_confidence_cap(
            verification_status=verification_status,
            claim_results=claim_results,
        )
        confidence_score = min(
            evidence_confidence,
            claim_confidence_cap if claim_confidence_cap is not None else evidence_confidence,
        )
        confidence_label = _confidence_label(confidence_score)
        confidence_reason = [
            f"evidence_cap:{evidence_confidence}",
            (
                f"claim_support_cap:{claim_confidence_cap}"
                if claim_confidence_cap is not None
                else "claim_support_cap:not_applied"
            ),
        ]
        result.update(
            {
                "evidence_pack_id": evidence_pack_id,
                "evidence_level": evidence_level,
                "claim_results": claim_results,
                "claim_support_summary": claim_support_summary,
                "limitations": list(dict.fromkeys(limitations)),
                "downgrade_reason": downgrade_reason,
                "max_confidence": confidence_score,
                "confidence_score": confidence_score,
                "confidence_label": confidence_label,
                "confidence_reason": confidence_reason,
            }
        )

    result["verified_insight"] = _build_verified_insight_object(
        verified_insight_id=verified_insight_id,
        signal_id=signal_id,
        content_fingerprint=content_fingerprint,
        evidence_level=evidence_level,
        evidence_quality=evidence_quality,
        evidence_pack_id=evidence_pack_id,
        generation_mode=generation_mode,
        verification_status=verification_status,
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        claim_results=claim_results,
        claim_support_summary=claim_support_summary,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        confidence_reason=confidence_reason,
        downgrade_reason=downgrade_reason,
        limitations=list(dict.fromkeys(limitations)),
        produced_by_model=produced_by_model,
    )

    _record_verified_insight_metric(
        signal_id=signal_id,
        evidence_level=evidence_level,
        result=result,
        claim_results=claim_results,
    )

    return result
