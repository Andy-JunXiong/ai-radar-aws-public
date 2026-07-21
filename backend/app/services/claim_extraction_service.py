from __future__ import annotations

import re
from typing import Any


INSIGHT_FIELDS = [
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
]

LOW_EVIDENCE_BOILERPLATE = [
    "Evidence is thin and supports only cautious interpretation.",
    "Avoid broad market or strategic claims from this single signal.",
    "Evidence is insufficient for strong conclusions.",
    "Treat this output as an observation, not a reliable strategic recommendation.",
]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _clean_claim_source(value: Any) -> str:
    text = _clean_text(value)
    text = re.sub(r"^Uncertain:\s*", "", text, flags=re.IGNORECASE)

    for boilerplate in LOW_EVIDENCE_BOILERPLATE:
        text = re.sub(
            rf"(^|\s){re.escape(boilerplate)}(?=\s|$)",
            " ",
            text,
            flags=re.IGNORECASE,
        )

    return _clean_text(text)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [_clean_text(part) for part in parts if len(_clean_text(part)) >= 24]


def _claim_type(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["will ", "likely", "future", "predict", "expected to"]):
        return "predictive"
    if any(word in lowered for word in ["because", "drives", "causes", "leads to", "enables"]):
        return "causal"
    if any(word in lowered for word in ["trend", "market", "ecosystem", "industry", "broader"]):
        return "trend"
    if any(word in lowered for word in ["more than", "less than", "compared", "versus", "vs."]):
        return "comparative"
    if any(word in lowered for word in ["should", "recommend", "takeaway", "adopt", "use ", "track "]):
        return "prescriptive"
    return "descriptive"


def extract_claims_from_insight(
    raw_insight: dict[str, Any],
    *,
    max_claims: int = 5,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    for field in INSIGHT_FIELDS:
        for sentence in _split_sentences(_clean_claim_source(raw_insight.get(field))):
            if len(claims) >= max_claims:
                break
            claims.append(
                {
                    "claim_id": f"claim_{len(claims) + 1}",
                    "claim_text": sentence,
                    "claim_type": _claim_type(sentence),
                    "source_field": field,
                }
            )
        if len(claims) >= max_claims:
            break

    return claims
