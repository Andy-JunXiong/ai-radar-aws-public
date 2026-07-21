from __future__ import annotations

import hashlib
import re
from typing import Any


PRIMARY_EVIDENCE_PROVENANCE = {
    "source_excerpt",
    "structured_metadata",
    "collector_extracted",
    "manual_user_written",
    "canonical_api_observed",
}

NON_PRIMARY_EVIDENCE_PROVENANCE = {"llm_generated", "unknown"}
PARAPHRASE_SPAN_PROVENANCE = {"source_excerpt", "collector_extracted"}
PARAPHRASE_MIN_OVERLAP = 4
PARAPHRASE_MIN_CLAIM_COVERAGE = 0.45
PARAPHRASE_WINDOW_PADDING = 180
ASSERTION_INFLATION_TOKENS = {
    "prove",
    "proves",
    "proved",
    "solves",
    "solved",
    "guarantee",
    "guarantees",
    "eliminate",
    "eliminates",
    "eliminated",
}
PRESENTATION_LIMITS_PRESENT_AND_EXCEEDED = "limits_present_and_exceeded"
PRESENTATION_LIMITS_PRESENT_AND_PRESERVED = "limits_present_and_preserved"
PRESENTATION_LIMITS_ABSENT_UNKNOWN = "limits_absent_unknown"
PRESENTATION_LIMITS_NOT_APPLICABLE = "limits_not_applicable"
SCALAR_CANONICAL_MISMATCH = "canonical_scalar_mismatch"
SCALAR_CANONICAL_PLATFORM_DELTA = "canonical_scalar_platform_delta"
SCALAR_CANONICAL_VERIFIED = "canonical_scalar_verified"
SCALAR_NOT_APPLICABLE = "no_canonical_scalar_applicable"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_with_index_map(value: Any) -> tuple[str, list[int]]:
    text = str(value or "")
    normalized_chars: list[str] = []
    index_map: list[int] = []
    pending_space = False

    for index, char in enumerate(text):
        if char.isspace():
            pending_space = bool(normalized_chars)
            continue
        if pending_space:
            normalized_chars.append(" ")
            index_map.append(index)
            pending_space = False
        normalized_chars.append(char.lower())
        index_map.append(index)

    return "".join(normalized_chars).strip(), index_map


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _source_span_for_claim(claim_text: str, item: dict[str, Any]) -> dict[str, Any] | None:
    content = str(item.get("content") or "")
    normalized_claim, _ = _normalize_with_index_map(claim_text)
    normalized_content, index_map = _normalize_with_index_map(content)
    if not normalized_claim or not normalized_content:
        return None

    normalized_start = normalized_content.find(normalized_claim)
    if normalized_start < 0:
        return None

    normalized_end = normalized_start + len(normalized_claim)
    if normalized_end > len(index_map):
        return None

    char_start = index_map[normalized_start]
    char_end = index_map[normalized_end - 1] + 1
    return {
        "evidence_id": _clean_text(item.get("evidence_id")),
        "source_id": _clean_text(item.get("source_id")),
        "source_field": _clean_text(item.get("source_field")),
        "char_start": char_start,
        "char_end": char_end,
        "content_hash": _content_hash(content),
    }


def _token_spans(text: str) -> dict[str, list[tuple[int, int]]]:
    spans: dict[str, list[tuple[int, int]]] = {}
    for match in re.finditer(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text):
        token = match.group(0).lower()
        if token not in _tokens(token):
            continue
        spans.setdefault(token, []).append((match.start(), match.end()))
    return spans


def _has_unmatched_assertion_inflation(claim_tokens: set[str], content_tokens: set[str]) -> bool:
    return bool((claim_tokens - content_tokens).intersection(ASSERTION_INFLATION_TOKENS))


def _metadata_from_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _canonical_scalar_resolutions(evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolutions: list[dict[str, Any]] = []
    for item in evidence_items:
        resolution = _metadata_from_item(item).get("canonical_scalar_resolution")
        if isinstance(resolution, dict):
            resolutions.append(resolution)
    return resolutions


def _scalar_value_markers(value: Any) -> set[str]:
    text = _clean_text(value).lower()
    if not text:
        return set()
    markers = {text, text.replace(",", "")}
    try:
        numeric = float(text.replace(",", ""))
    except Exception:
        numeric = None
    if numeric is not None and numeric >= 1000:
        markers.add(f"{int(numeric):,}".lower())
        markers.add(str(int(numeric)))
        if numeric % 1000 == 0:
            markers.add(f"{int(numeric / 1000)}k")
        compact = f"{numeric / 1000:.1f}".rstrip("0").rstrip(".")
        if compact:
            markers.add(f"{compact}k")
    return {marker for marker in markers if marker}


def _claim_mentions_scalar_value(claim_text: str, scalar_name: str, value: Any) -> bool:
    claim = _clean_text(claim_text).lower()
    if not claim:
        return False
    scalar_markers = {
        "stars": ("star", "stars", "stargazer", "stargazers"),
        "license": ("license", "licensed", "mit", "apache", "agpl", "gpl", "bsd"),
        "archived": ("archived", "archive"),
        "created_at": ("created", "created_at", "launched"),
        "updated_at": ("updated", "updated_at"),
    }.get(scalar_name, (scalar_name,))
    if not any(marker in claim for marker in scalar_markers):
        return False
    return any(marker in claim for marker in _scalar_value_markers(value))


def _scalar_fidelity_for_claim(
    claim_text: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    resolutions = _canonical_scalar_resolutions(evidence_items)
    if not resolutions:
        return {
            "scalar_state": SCALAR_NOT_APPLICABLE,
            "reason_codes": [],
            "matched_scalars": [],
        }

    matched_scalars: list[dict[str, Any]] = []
    reason_codes: list[str] = []
    platform_delta_reason_codes: list[str] = []
    for resolution in resolutions:
        entity_id = _clean_text(resolution.get("entity_id"))
        canonical_source = _clean_text(resolution.get("canonical_source")) or "github_api"
        for scalar in resolution.get("scalars") or []:
            if not isinstance(scalar, dict):
                continue
            name = _clean_text(scalar.get("name")).lower()
            status = _clean_text(scalar.get("status")).lower()
            canonical_value = scalar.get("canonical_value")
            claimed_value = scalar.get("claimed_value")
            mentions_claimed = _claim_mentions_scalar_value(claim_text, name, claimed_value)
            mentions_canonical = _claim_mentions_scalar_value(claim_text, name, canonical_value)
            if status == "mismatch" and mentions_claimed:
                state = "mismatch" if scalar.get("can_contradict_claim", True) else "platform_delta"
                matched_scalars.append(
                    {
                        "name": name,
                        "state": state,
                        "canonical_value": canonical_value,
                        "claimed_value": claimed_value,
                        "canonical_source": canonical_source,
                        "entity_id": entity_id,
                        "resolution_confidence": scalar.get("resolution_confidence"),
                        "resolution_notes": scalar.get("resolution_notes") or [],
                    }
                )
                if state == "mismatch":
                    reason_codes.append(f"{name}_canonical_mismatch")
                else:
                    platform_delta_reason_codes.append(f"{name}_platform_delta_requires_review")
            elif status in {"platform_delta", "uncertain"} and mentions_claimed:
                matched_scalars.append(
                    {
                        "name": name,
                        "state": status,
                        "canonical_value": canonical_value,
                        "claimed_value": claimed_value,
                        "canonical_source": canonical_source,
                        "entity_id": entity_id,
                        "resolution_confidence": scalar.get("resolution_confidence"),
                        "resolution_notes": scalar.get("resolution_notes") or [],
                    }
                )
                platform_delta_reason_codes.append(f"{name}_{status}_requires_review")
            elif mentions_canonical:
                matched_scalars.append(
                    {
                        "name": name,
                        "state": "verified",
                        "canonical_value": canonical_value,
                        "claimed_value": claimed_value,
                        "canonical_source": canonical_source,
                        "entity_id": entity_id,
                        "resolution_confidence": scalar.get("resolution_confidence"),
                        "resolution_notes": scalar.get("resolution_notes") or [],
                    }
                )

    if any(item.get("state") == "mismatch" for item in matched_scalars):
        return {
            "scalar_state": SCALAR_CANONICAL_MISMATCH,
            "reason_codes": list(dict.fromkeys(reason_codes)),
            "matched_scalars": matched_scalars,
        }
    if any(item.get("state") in {"platform_delta", "uncertain"} for item in matched_scalars):
        return {
            "scalar_state": SCALAR_CANONICAL_PLATFORM_DELTA,
            "reason_codes": list(dict.fromkeys(platform_delta_reason_codes)),
            "matched_scalars": matched_scalars,
        }
    if matched_scalars:
        return {
            "scalar_state": SCALAR_CANONICAL_VERIFIED,
            "reason_codes": [],
            "matched_scalars": matched_scalars,
        }
    return {
        "scalar_state": "canonical_scalar_recorded_not_claimed",
        "reason_codes": [],
        "matched_scalars": [],
    }


def _provenance_tier_for_claim(
    matched: list[dict[str, Any]],
    scalar_fidelity: dict[str, Any],
) -> str:
    scalar_state = _clean_text(scalar_fidelity.get("scalar_state"))
    if scalar_state == SCALAR_CANONICAL_MISMATCH:
        return "canonical_conflicted"
    if scalar_state == SCALAR_CANONICAL_PLATFORM_DELTA:
        return "canonical_platform_delta"
    if scalar_state == SCALAR_CANONICAL_VERIFIED:
        return "canonical_api_observed"

    explicit_tiers = [
        _clean_text(_metadata_from_item(item).get("provenance_tier"))
        for item in matched
        if _clean_text(_metadata_from_item(item).get("provenance_tier"))
    ]
    if explicit_tiers:
        return explicit_tiers[0]

    provenances = {_clean_text(item.get("provenance")).lower() for item in matched}
    if "source_excerpt" in provenances:
        return "source_self_reported"
    if provenances.intersection({"structured_metadata", "collector_extracted", "manual_user_written"}):
        return "third_party_summary"
    if not matched:
        return "model_inferred"
    return "unknown"


def _canonical_scalar_rewrite(claim_text: str, scalar_fidelity: dict[str, Any]) -> str:
    mismatches = [
        item
        for item in scalar_fidelity.get("matched_scalars") or []
        if isinstance(item, dict) and item.get("state") == "mismatch"
    ]
    if not mismatches:
        return f"Treat as unverified: {claim_text}"
    facts = []
    for item in mismatches:
        name = _clean_text(item.get("name"))
        canonical_value = _clean_text(item.get("canonical_value"))
        source = _clean_text(item.get("canonical_source")) or "canonical source"
        if name and canonical_value:
            facts.append(f"{name}={canonical_value} per {source}")
    if not facts:
        return f"Treat as unverified: {claim_text}"
    return f"Revise scalar claim: {', '.join(facts)}."


def _source_stated_limits_from_evidence(evidence_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    limits: list[dict[str, Any]] = []
    not_applicable = False

    for item in evidence_items:
        metadata = _metadata_from_item(item)
        status = _clean_text(metadata.get("source_stated_limits_status")).lower()
        if status == PRESENTATION_LIMITS_NOT_APPLICABLE:
            not_applicable = True

        raw_limits = metadata.get("source_stated_limits")
        if not isinstance(raw_limits, list):
            continue
        for raw_limit in raw_limits:
            if not isinstance(raw_limit, dict):
                continue
            text = _clean_text(raw_limit.get("text"))
            if not text:
                continue
            limits.append(
                {
                    "text": text,
                    "source_field": _clean_text(raw_limit.get("source_field")),
                    "limit_type": _clean_text(raw_limit.get("limit_type")),
                }
            )

    return limits, not_applicable and not limits


def _source_stated_confidence_present(evidence_items: list[dict[str, Any]]) -> bool:
    for item in evidence_items:
        confidence = _metadata_from_item(item).get("source_stated_confidence")
        if isinstance(confidence, dict) and any(confidence.values()):
            return True
    return False


def _limit_exceeded_reasons(claim_text: str, limits: list[dict[str, Any]]) -> list[str]:
    claim = _clean_text(claim_text).lower()
    limit_text = " ".join(_clean_text(limit.get("text")).lower() for limit in limits)
    reasons: list[str] = []
    if not claim or not limit_text:
        return reasons

    peer_review_claim = bool(re.search(r"\bpeer[-\s]?review(?:ed)?\b", claim))
    simulated_or_internal_limit = any(
        marker in limit_text
        for marker in (
            "simulated review",
            "simulation",
            "in-framework",
            "internal review",
            "not external",
            "not a peer review",
            "not peer review",
        )
    )
    if peer_review_claim and simulated_or_internal_limit:
        reasons.append("peer_review_claim_exceeds_simulated_review_limit")

    numeric_quality_claim = bool(re.search(r"\b\d+(?:\.\d+)?\s*/\s*10\b", claim))
    quality_limit = any(
        marker in limit_text
        for marker in (
            "not external quality",
            "not a quality claim",
            "not an external quality claim",
            "simulated review",
            "in-framework",
        )
    )
    if numeric_quality_claim and quality_limit and peer_review_claim:
        reasons.append("quality_score_claim_exceeds_source_limit")

    strong_validation_claim = bool(
        re.search(r"\b(validated|verified|proved|proven|confirmed|certified)\b", claim)
    )
    hallucination_limit = "hallucinat" in limit_text or "fabricated citation" in limit_text
    if strong_validation_claim and hallucination_limit:
        reasons.append("validation_claim_omits_hallucination_limit")

    return list(dict.fromkeys(reasons))


def _presentation_fidelity_for_claim(
    claim_text: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    limits, limits_not_applicable = _source_stated_limits_from_evidence(evidence_items)
    confidence_present = _source_stated_confidence_present(evidence_items)

    if limits_not_applicable:
        return {
            "limits_state": PRESENTATION_LIMITS_NOT_APPLICABLE,
            "reason_codes": ["source_stated_limits_not_applicable"],
            "source_stated_limits_count": 0,
            "source_stated_confidence_present": confidence_present,
        }

    if not limits:
        return {
            "limits_state": PRESENTATION_LIMITS_ABSENT_UNKNOWN,
            "reason_codes": ["source_stated_limits_absent_unknown"],
            "source_stated_limits_count": 0,
            "source_stated_confidence_present": confidence_present,
        }

    exceeded_reasons = _limit_exceeded_reasons(claim_text, limits)
    if exceeded_reasons:
        return {
            "limits_state": PRESENTATION_LIMITS_PRESENT_AND_EXCEEDED,
            "reason_codes": exceeded_reasons,
            "source_stated_limits_count": len(limits),
            "source_stated_confidence_present": confidence_present,
        }

    return {
        "limits_state": PRESENTATION_LIMITS_PRESENT_AND_PRESERVED,
        "reason_codes": [],
        "source_stated_limits_count": len(limits),
        "source_stated_confidence_present": confidence_present,
    }


def _compatible_token(claim_token: str, content_token: str) -> bool:
    if claim_token == content_token:
        return True
    if min(len(claim_token), len(content_token)) < 5:
        return False
    return claim_token in content_token or content_token in claim_token


def _sentence_window(content: str, start: int, end: int) -> tuple[int, int]:
    window_start = max(0, start - PARAPHRASE_WINDOW_PADDING)
    window_end = min(len(content), end + PARAPHRASE_WINDOW_PADDING)

    sentence_start = content.rfind(".", 0, start)
    sentence_start = max(sentence_start, content.rfind("\n", 0, start))
    if sentence_start >= 0 and start - sentence_start <= PARAPHRASE_WINDOW_PADDING:
        window_start = sentence_start + 1

    sentence_end_candidates = [
        position
        for position in (
            content.find(".", end),
            content.find("\n", end),
        )
        if position >= 0
    ]
    if sentence_end_candidates:
        sentence_end = min(sentence_end_candidates)
        if sentence_end - end <= PARAPHRASE_WINDOW_PADDING:
            window_end = sentence_end + 1

    while window_start < window_end and content[window_start].isspace():
        window_start += 1
    while window_end > window_start and content[window_end - 1].isspace():
        window_end -= 1
    return window_start, window_end


def _supporting_source_span_for_claim(claim_text: str, item: dict[str, Any]) -> dict[str, Any] | None:
    content = str(item.get("content") or "")
    claim_tokens = _tokens(claim_text)
    content_token_spans = _token_spans(content)
    content_tokens = set(content_token_spans)
    if not claim_tokens or not content_tokens:
        return None

    matched_token_spans: dict[str, list[tuple[int, int]]] = {}
    for claim_token in claim_tokens:
        spans: list[tuple[int, int]] = []
        for content_token, content_spans in content_token_spans.items():
            if _compatible_token(claim_token, content_token):
                spans.extend(content_spans)
        if spans:
            matched_token_spans[claim_token] = spans

    overlap = set(matched_token_spans)
    coverage = len(overlap) / max(1, len(claim_tokens))
    provenance = _clean_text(item.get("provenance")).lower()
    if provenance not in PARAPHRASE_SPAN_PROVENANCE:
        return None
    if len(overlap) < PARAPHRASE_MIN_OVERLAP or coverage < PARAPHRASE_MIN_CLAIM_COVERAGE:
        return None
    if _has_unmatched_assertion_inflation(claim_tokens, content_tokens):
        return None

    matched_spans = [span for token in overlap for span in matched_token_spans.get(token, [])]
    if not matched_spans:
        return None

    char_start = min(start for start, _ in matched_spans)
    char_end = max(end for _, end in matched_spans)
    window_start, window_end = _sentence_window(content, char_start, char_end)
    return {
        "evidence_id": _clean_text(item.get("evidence_id")),
        "source_id": _clean_text(item.get("source_id")),
        "source_field": _clean_text(item.get("source_field")),
        "char_start": window_start,
        "char_end": window_end,
        "content_hash": _content_hash(content),
        "match_type": "paraphrase_window",
        "matched_token_count": len(overlap),
        "claim_token_coverage": round(coverage, 3),
    }


def _first_source_span(claim_text: str, evidence_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in evidence_items:
        span = _source_span_for_claim(claim_text, item)
        if span is not None:
            return span
    return None


def _first_supporting_source_span(claim_text: str, evidence_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for item in evidence_items:
        span = _supporting_source_span_for_claim(claim_text, item)
        if span is not None:
            candidates.append(span)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda span: (
            float(span.get("claim_token_coverage") or 0),
            int(span.get("matched_token_count") or 0),
        ),
    )


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text.lower())
        if token
        not in {
            "this",
            "that",
            "with",
            "from",
            "because",
            "into",
            "about",
            "signal",
            "insight",
            "project",
            "career",
        }
    }


def _match_evidence(claim_text: str, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_tokens = _tokens(claim_text)
    if not claim_tokens:
        return []

    matched: list[dict[str, Any]] = []
    for item in evidence_items:
        content = _clean_text(item.get("content"))
        if not content:
            continue
        overlap = claim_tokens.intersection(_tokens(content))
        if len(overlap) >= 2 or len(overlap) >= max(1, min(3, len(claim_tokens) // 3)):
            matched.append(item)
    return matched


def _cap_support_by_claim_type(
    *,
    claim_type: str,
    source_field: str,
    base_support: str,
    matched_count: int,
) -> tuple[str, str | None]:
    if source_field in {"relevance_to_projects", "relevance_to_career"}:
        if base_support in {"directly_supported", "partially_supported"}:
            return "partially_supported", f"{source_field}_requires_contextual_review"
        return base_support, f"{source_field}_requires_contextual_review"

    if claim_type == "predictive":
        return "inferred", "predictive_claim_capped"
    if claim_type == "causal":
        return "inferred", "causal_claim_requires_explicit_causal_evidence"
    if claim_type == "trend" and matched_count < 2:
        if base_support == "directly_supported":
            return "partially_supported", "single_source_trend_claim_downgraded"
        return base_support, "single_source_trend_claim_downgraded"
    if claim_type == "comparative" and matched_count < 2:
        return "inferred", "comparative_claim_missing_baseline"
    if claim_type == "prescriptive":
        return "inferred", "prescriptive_claim_requires_human_review"
    return base_support, None


def verify_claims_against_evidence(
    claims: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_items = [
        item
        for item in evidence_pack.get("evidence_items") or []
        if isinstance(item, dict)
    ]

    results: list[dict[str, Any]] = []
    for claim in claims:
        claim_text = _clean_text(claim.get("claim_text"))
        claim_type = _clean_text(claim.get("claim_type") or "descriptive")
        source_field = _clean_text(claim.get("source_field"))
        matched = _match_evidence(claim_text, evidence_items)
        matched_ids = [_clean_text(item.get("evidence_id")) for item in matched if item.get("evidence_id")]
        provenances = {_clean_text(item.get("provenance")).lower() for item in matched}
        traceable_primary = [
            item
            for item in matched
            if item.get("traceable") and _clean_text(item.get("provenance")).lower() in PRIMARY_EVIDENCE_PROVENANCE
        ]
        source_span = _first_source_span(claim_text, traceable_primary)
        source_span_match_type = "exact_quote" if source_span else ""
        if source_span is None:
            source_span = _first_supporting_source_span(claim_text, traceable_primary)
            source_span_match_type = "paraphrase_window" if source_span else ""

        limitations: list[str] = []
        recommended_rewrite = None

        if not matched:
            support_level = "unsupported"
            inference_distance = "far"
            risk_level = "medium"
            limitations.append("no_matched_evidence")
            recommended_rewrite = f"Treat as unverified: {claim_text}"
        elif provenances and provenances.issubset(NON_PRIMARY_EVIDENCE_PROVENANCE):
            support_level = "inferred"
            inference_distance = "medium"
            risk_level = "medium"
            limitations.append("only_non_primary_evidence_matched")
        elif traceable_primary and source_span:
            if source_span_match_type == "exact_quote" and claim_type == "descriptive":
                support_level = "directly_supported"
                inference_distance = "direct"
                risk_level = "low"
            else:
                support_level = "partially_supported"
                inference_distance = "near"
                risk_level = "medium"
                if source_span_match_type == "paraphrase_window":
                    limitations.append("paraphrase_grounded_to_source_span")
        elif traceable_primary:
            support_level = "inferred"
            inference_distance = "medium"
            risk_level = "medium"
            limitations.append("matched_evidence_without_source_span")
        else:
            support_level = "inferred"
            inference_distance = "medium"
            risk_level = "medium"
            limitations.append("matched_evidence_not_traceable_primary")

        capped_support, cap_reason = _cap_support_by_claim_type(
            claim_type=claim_type,
            source_field=source_field,
            base_support=support_level,
            matched_count=len(traceable_primary),
        )
        if cap_reason:
            limitations.append(cap_reason)
        support_level = capped_support
        presentation_fidelity = _presentation_fidelity_for_claim(claim_text, evidence_items)
        if presentation_fidelity["limits_state"] == PRESENTATION_LIMITS_PRESENT_AND_EXCEEDED:
            limitations.append("presentation_fidelity_limit_exceeded")
            if support_level == "directly_supported":
                support_level = "partially_supported"
            if risk_level == "low":
                risk_level = "medium"
        scalar_fidelity = _scalar_fidelity_for_claim(claim_text, evidence_items)
        if scalar_fidelity["scalar_state"] == SCALAR_CANONICAL_MISMATCH:
            limitations.append("canonical_scalar_mismatch")
            limitations.extend(scalar_fidelity.get("reason_codes") or [])
            support_level = "contradicted"
            inference_distance = "direct"
            risk_level = "high"
            recommended_rewrite = _canonical_scalar_rewrite(claim_text, scalar_fidelity)
        elif scalar_fidelity["scalar_state"] == SCALAR_CANONICAL_PLATFORM_DELTA:
            limitations.append("canonical_scalar_platform_delta")
            limitations.extend(scalar_fidelity.get("reason_codes") or [])
            if support_level == "directly_supported":
                support_level = "partially_supported"
            if risk_level == "low":
                risk_level = "medium"
        provenance_tier = _provenance_tier_for_claim(matched, scalar_fidelity)

        results.append(
            {
                **claim,
                "support_level": support_level,
                "evidence_refs": matched_ids,
                "origin": (
                    "quoted"
                    if source_span_match_type == "exact_quote"
                    else ("grounded_excerpt" if source_span_match_type == "paraphrase_window" else "inferred")
                ),
                "source_span": source_span,
                "inference_distance": inference_distance,
                "risk_level": risk_level,
                "unsupported_parts": (
                    [claim_text] if support_level in {"unsupported", "contradicted"} else []
                ),
                "recommended_rewrite": recommended_rewrite,
                "provenance_tier": provenance_tier,
                "scalar_fidelity": scalar_fidelity,
                "presentation_fidelity": presentation_fidelity,
                "verification_notes": list(dict.fromkeys(limitations)),
            }
        )

    return results
