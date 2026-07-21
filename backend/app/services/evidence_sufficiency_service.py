from __future__ import annotations

from typing import Any


SOURCE_RELIABILITY_BY_TYPE = {
    "manual": "high",
    "aws_ml": "high",
    "research": "high",
    "github": "medium",
    "hn": "medium",
    "hacker_news": "medium",
    "product_hunt": "medium",
    "rss": "medium",
    "unknown": "unknown",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _source_reliability(source_type: str) -> str:
    normalized = _clean_text(source_type).lower()
    return SOURCE_RELIABILITY_BY_TYPE.get(normalized, "unknown")


def assess_evidence_sufficiency(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(evidence_pack.get("source_title"))
    summary = _clean_text(evidence_pack.get("summary_excerpt"))
    source_url = _clean_text(evidence_pack.get("source_url"))
    source_type = _clean_text(evidence_pack.get("source_type") or "unknown")
    reliability = _source_reliability(source_type)
    summary_provenance = _clean_text(evidence_pack.get("summary_provenance") or "unknown").lower()

    score = 0.0
    notes: list[str] = []
    reason_codes: list[str] = []

    has_title = bool(title)
    has_summary = bool(summary)
    has_url = bool(source_url)
    summary_length = len(summary)
    summary_weight_applied = 0.0

    if has_title:
        score += 0.15
    else:
        notes.append("missing_title")
        reason_codes.append("missing_title")

    if summary_length >= 500:
        summary_weight_applied = 0.50
    elif summary_length >= 200:
        summary_weight_applied = 0.35
    elif summary_length >= 80:
        summary_weight_applied = 0.20
    elif summary_length > 0:
        summary_weight_applied = 0.10
        notes.append("summary_too_short_for_strong_inference")
        reason_codes.append("short_summary")
    else:
        notes.append("missing_summary")
        reason_codes.append("missing_summary")

    if summary_weight_applied:
        if summary_provenance == "llm_generated":
            summary_weight_applied = round(summary_weight_applied * 0.5, 2)
            notes.append("llm_generated_summary_downweighted")
            reason_codes.append("llm_generated_summary_downweighted")
        elif summary_provenance == "unknown":
            summary_weight_applied = round(summary_weight_applied * 0.65, 2)
            notes.append("unknown_summary_provenance_downweighted")
            reason_codes.append("unknown_summary_provenance_downweighted")
        elif summary_provenance == "collector_extracted":
            summary_weight_applied = round(summary_weight_applied * 0.85, 2)
            notes.append("collector_summary_slightly_downweighted")
            reason_codes.append("collector_summary_slightly_downweighted")
        elif summary_provenance == "source_excerpt":
            reason_codes.append("source_excerpt_summary")
        elif summary_provenance == "manual_user_written":
            reason_codes.append("manual_summary_context")

    score += summary_weight_applied

    if reliability == "high":
        score += 0.20
        reason_codes.append("high_source_reliability")
    elif reliability == "medium":
        score += 0.10
        reason_codes.append("medium_source_reliability")
    else:
        notes.append("unknown_source_reliability")
        reason_codes.append("unknown_source_reliability")

    if has_url:
        score += 0.10
        reason_codes.append("has_source_url")
    else:
        notes.append("missing_source_url")
        reason_codes.append("missing_source_url")

    score = max(0.0, min(round(score, 2), 1.0))

    if score < 0.35:
        level = "insufficient"
    elif score < 0.65:
        level = "thin"
    elif score < 0.85:
        level = "sufficient"
    else:
        level = "strong"

    if level in {"insufficient", "thin"}:
        notes.append("thin_signal_penalty_applied")
        reason_codes.append("thin_signal_penalty_applied")

    return {
        "level": level,
        "score": score,
        "has_title": has_title,
        "has_summary": has_summary,
        "has_url": has_url,
        "summary_length": summary_length,
        "summary_provenance": summary_provenance,
        "summary_weight_applied": summary_weight_applied,
        "source_reliability": reliability,
        "is_thin_signal": level in {"insufficient", "thin"},
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "notes": notes,
    }
