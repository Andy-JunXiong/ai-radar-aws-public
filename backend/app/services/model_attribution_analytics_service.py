from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA_VERSION = 1
V1_PROVENANCE_SCHEMA_VERSION = 1
LEGACY_PROVENANCE_SCHEMA_VERSION = 0
UNVERIFIED_MANUAL_ENTRY_SOURCE = "unverified_manual_entry"


def summarize_model_attribution(
    *,
    candidates: Iterable[dict[str, Any]] | None = None,
    review_records: Iterable[dict[str, Any]] | None = None,
    calibration_events: Iterable[dict[str, Any]] | None = None,
    signals: Iterable[dict[str, Any]] | None = None,
    generated_at: str | None = None,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build read-only descriptive analytics for ADR-0009 model provenance."""

    families = {
        "candidate": list(candidates or []),
        "review_record": list(review_records or []),
        "calibration_event": list(calibration_events or []),
        "signal": list(signals or []),
    }
    coverage = _empty_coverage()
    family_coverage: dict[str, dict[str, Any]] = {}
    by_model: dict[tuple[str, str], dict[str, Any]] = {}
    by_route: dict[tuple[str, str], dict[str, Any]] = {}
    review_outcomes: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    gate_outcomes: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    excluded = {
        "legacy_v0": 0,
        "malformed": 0,
        "manual_unverified": 0,
    }

    for family, records in families.items():
        family_coverage[family] = {"record_family": family, **_empty_coverage()}
        for record in records:
            classification = classify_model_provenance(record)
            manual_unverified = _is_unverified_manual_entry(record)

            _increment_coverage(coverage, classification, manual_unverified=manual_unverified)
            _increment_coverage(family_coverage[family], classification, manual_unverified=manual_unverified)

            if classification["state"] == "legacy_v0":
                excluded["legacy_v0"] += 1
            elif classification["state"] == "malformed":
                excluded["malformed"] += 1
            if manual_unverified:
                excluded["manual_unverified"] += 1

            if classification["state"] != "v1":
                continue

            provenance = classification["produced_by_model"]
            if not isinstance(provenance, dict):
                continue

            _increment_model_summary(by_model, provenance)
            _increment_route_summary(by_route, provenance)
            if family == "review_record":
                _increment_review_outcome_summary(review_outcomes, record, provenance)
            if family in {"candidate", "signal"}:
                _increment_gate_outcome_summary(gate_outcomes, record, provenance)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "scope": scope or {"record_families": list(families.keys())},
        "coverage": coverage,
        "by_record_family": _sort_summaries(family_coverage.values(), "record_family"),
        "by_model": _sort_summaries(by_model.values(), "provider", "model_id"),
        "by_route": _sort_summaries(by_route.values(), "route_key", "task_type"),
        "review_outcomes": _sort_summaries(
            review_outcomes.values(),
            "outcome",
            "provider",
            "model_id",
            "route_key",
        ),
        "gate_outcomes": _sort_summaries(
            gate_outcomes.values(),
            "verification_status",
            "review_priority",
            "blocked_downstream_actions_key",
        ),
        "excluded": excluded,
    }


def classify_model_provenance(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"state": "legacy_v0", "produced_by_model": None}

    candidates = _model_provenance_candidates(record)
    v1_candidate = next((_clean_provenance(value) for value in candidates if _is_valid_v1_provenance(value)), None)
    if v1_candidate:
        return {"state": "v1", "produced_by_model": v1_candidate}

    if any(_is_malformed_provenance(value) for value in candidates):
        return {"state": "malformed", "produced_by_model": None}

    return {"state": "legacy_v0", "produced_by_model": None}


def _empty_coverage() -> dict[str, int]:
    return {
        "total_records": 0,
        "v1_records": 0,
        "legacy_v0_records": 0,
        "malformed_records": 0,
        "manual_unverified_records": 0,
        "attribution_eligible_records": 0,
    }


def _increment_coverage(
    coverage: dict[str, Any],
    classification: dict[str, Any],
    *,
    manual_unverified: bool,
) -> None:
    coverage["total_records"] += 1
    state = classification.get("state")
    if state == "v1":
        coverage["v1_records"] += 1
        coverage["attribution_eligible_records"] += 1
    elif state == "malformed":
        coverage["malformed_records"] += 1
    else:
        coverage["legacy_v0_records"] += 1
    if manual_unverified:
        coverage["manual_unverified_records"] += 1


def _model_provenance_candidates(record: dict[str, Any]) -> list[Any]:
    verification = record.get("verification_metadata") if isinstance(record.get("verification_metadata"), dict) else {}
    direct_verification = record.get("verification") if isinstance(record.get("verification"), dict) else {}
    policy_metadata = record.get("policy_metadata") if isinstance(record.get("policy_metadata"), dict) else {}
    policy_verification = (
        policy_metadata.get("verification")
        if isinstance(policy_metadata.get("verification"), dict)
        else {}
    )
    verified_insight = (
        verification.get("verified_insight")
        if isinstance(verification.get("verified_insight"), dict)
        else {}
    )
    direct_verified_insight = (
        direct_verification.get("verified_insight")
        if isinstance(direct_verification.get("verified_insight"), dict)
        else {}
    )
    policy_verified_insight = (
        policy_verification.get("verified_insight")
        if isinstance(policy_verification.get("verified_insight"), dict)
        else {}
    )
    return [
        record.get("produced_by_model"),
        verification.get("produced_by_model"),
        verified_insight.get("produced_by_model"),
        direct_verification.get("produced_by_model"),
        direct_verified_insight.get("produced_by_model"),
        policy_verification.get("produced_by_model"),
        policy_verified_insight.get("produced_by_model"),
    ]


def _is_valid_v1_provenance(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("provenance_schema_version") != V1_PROVENANCE_SCHEMA_VERSION:
        return False
    return bool(
        _safe_text(value.get("provider"))
        and value.get("model_id") is not None
        and (_safe_text(value.get("route_key")) or _safe_text(value.get("task_type")))
        and _safe_text(value.get("deterministic_fingerprint"))
    )


def _is_malformed_provenance(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, dict):
        return True
    version = value.get("provenance_schema_version")
    if version == LEGACY_PROVENANCE_SCHEMA_VERSION:
        return False
    if version != V1_PROVENANCE_SCHEMA_VERSION:
        return True
    return not _is_valid_v1_provenance(value)


def _clean_provenance(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_unverified_manual_entry(record: dict[str, Any]) -> bool:
    verification = record.get("verification_metadata") if isinstance(record.get("verification_metadata"), dict) else {}
    return (
        _safe_text(record.get("candidate_source")) == UNVERIFIED_MANUAL_ENTRY_SOURCE
        or _safe_text(verification.get("candidate_source")) == UNVERIFIED_MANUAL_ENTRY_SOURCE
        or _safe_text(verification.get("verification_status")) == UNVERIFIED_MANUAL_ENTRY_SOURCE
    )


def _increment_model_summary(target: dict[tuple[str, str], dict[str, Any]], provenance: dict[str, Any]) -> None:
    provider = _safe_text(provenance.get("provider")) or "unknown"
    model_id = _safe_text(provenance.get("model_id"))
    key = (provider, model_id)
    item = target.setdefault(
        key,
        {
            "provider": provider,
            "model_id": model_id,
            "count": 0,
        },
    )
    item["count"] += 1


def _increment_route_summary(target: dict[tuple[str, str], dict[str, Any]], provenance: dict[str, Any]) -> None:
    route_key = _safe_text(provenance.get("route_key")) or "unknown"
    task_type = _safe_text(provenance.get("task_type")) or "unknown"
    prompt_template_id = _safe_text(provenance.get("prompt_template_id")) or "unknown"
    prompt_template_version = _safe_text(provenance.get("prompt_template_version")) or "unknown"
    key = (route_key, task_type)
    item = target.setdefault(
        key,
        {
            "route_key": route_key,
            "task_type": task_type,
            "prompt_template_id": prompt_template_id,
            "prompt_template_version": prompt_template_version,
            "count": 0,
        },
    )
    item["count"] += 1


def _increment_review_outcome_summary(
    target: dict[tuple[str, str, str, str, str], dict[str, Any]],
    record: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    outcome = _safe_text(record.get("outcome")) or "unknown"
    provider = _safe_text(provenance.get("provider")) or "unknown"
    model_id = _safe_text(provenance.get("model_id"))
    route_key = _safe_text(provenance.get("route_key")) or "unknown"
    fingerprint_prefix = _safe_text(provenance.get("deterministic_fingerprint"))[:8]
    key = (outcome, provider, model_id, route_key, fingerprint_prefix)
    item = target.setdefault(
        key,
        {
            "outcome": outcome,
            "provider": provider,
            "model_id": model_id,
            "route_key": route_key,
            "fingerprint_prefix": fingerprint_prefix,
            "count": 0,
        },
    )
    item["count"] += 1


def _increment_gate_outcome_summary(
    target: dict[tuple[str, str, str, str, str], dict[str, Any]],
    record: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    verification = record.get("verification_metadata") if isinstance(record.get("verification_metadata"), dict) else {}
    verification_status = _safe_text(
        record.get("verification_status") or verification.get("verification_status")
    )
    review_priority = _safe_text(record.get("review_priority") or verification.get("review_priority"))
    blocked_actions = _string_list(record.get("blocked_downstream_actions") or verification.get("blocked_downstream_actions"))
    allowed_actions = _string_list(record.get("allowed_downstream_actions") or verification.get("allowed_downstream_actions"))
    if not (verification_status or review_priority or blocked_actions or allowed_actions):
        return

    provider = _safe_text(provenance.get("provider")) or "unknown"
    model_id = _safe_text(provenance.get("model_id"))
    blocked_key = ",".join(blocked_actions)
    allowed_key = ",".join(allowed_actions)
    key = (verification_status, review_priority, blocked_key, provider, model_id)
    item = target.setdefault(
        key,
        {
            "verification_status": verification_status or "unknown",
            "review_priority": review_priority or "unknown",
            "blocked_downstream_actions": blocked_actions,
            "blocked_downstream_actions_key": blocked_key,
            "allowed_downstream_actions": allowed_actions,
            "allowed_downstream_actions_key": allowed_key,
            "provider": provider,
            "model_id": model_id,
            "count": 0,
        },
    )
    item["count"] += 1


def _sort_summaries(items: Iterable[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -int(item.get("count", item.get("total_records", 0)) or 0),
            *(_safe_text(item.get(key)) for key in keys),
        ),
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(_safe_text(item) for item in value if _safe_text(item))


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
