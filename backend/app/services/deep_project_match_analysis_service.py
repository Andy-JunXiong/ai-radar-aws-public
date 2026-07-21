from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.services.context_bridge import build_analysis_context
from app.services.llm_executor_service import execute_text_json_task
from app.services.model_router_service import PROVIDER_ANTHROPIC, PROVIDER_OPENAI


REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = REPO_ROOT / ".env"

load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


DEEP_MATCH_TASK_TYPE = "reason"
SOURCE_DEPTH_TIERS = {"metadata", "source_excerpt", "full_source"}
SOURCE_ASSERTION_TYPES = {"fact", "aspiration", "result_with_data", "result_without_data", "unknown"}
SOURCE_CLAIM_RELIABILITY = {
    "fact_grounded",
    "mixed",
    "assertion_only",
    "aspiration_heavy",
    "result_without_data",
    "unknown",
}
SOURCE_CLAIM_LIMITING_RELIABILITY = {"assertion_only", "aspiration_heavy", "result_without_data", "unknown"}
SOURCE_CLAIM_LIMIT_NOTE = "Based on the source's claim, not verified implementation fact."

AI_RADAR_REFERENCE_FRAME = """
<ai_radar_reference_frame>
AI Radar transforms external AI ecosystem signals into reviewable project intelligence. Its verification spine is:
1. evidence_pack: captures source material and source provenance for a signal.
2. claim_verification: checks generated claims against available source evidence.
3. verified_insight: records the resulting claim-support and confidence metadata.
4. low_evidence_gate: blocks strong recommendations, low-risk Action, or unsupported Project Takeaway paths when evidence is thin.

AI Radar separates planes:
- Claim plane: what is being asserted.
- Verification plane: whether the assertion is supported by evidence.
- Insight plane: project interpretation and human judgment.
- Audit/provenance plane: where material came from, who/what produced it, and how it changed.

Core orientation: AI Radar is an epistemic notary. It asks whether a claim is supported, not merely who said it, signed it, repeated it, or made it look coherent. Provenance, signatures, popularity, effort spent, and source depth are audit signals; they are not verification_status.

Threat models to compare against external systems: metadata-coherent but unresolvable source, effort-coherent but unresolved work, source-asserted but unsubstantiated capability, scope inflation, causal substitution, and fabricated engineering detail.

Hard invariants: source_tier/source_depth_tier must not write verification_status; provenance is not verification; trust scores must not affect admission; project relevance is internal judgment until source evidence supports external claims; source excerpts prove the source said something, not that the source-side claim is true; blocked_downstream_actions remain hard gates for low-risk Action and strong recommendations.
</ai_radar_reference_frame>
""".strip()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return " ".join(text.strip().split())


def _resolve_provider_override(selected_model: str | None) -> str | None:
    normalized = str(selected_model or "").strip().lower()
    if normalized in {"claude", "anthropic"}:
        return PROVIDER_ANTHROPIC
    if normalized in {"chatgpt", "openai"}:
        return PROVIDER_OPENAI
    return None


def _missing_requested_provider_key(selected_model: str | None) -> str:
    provider_override = _resolve_provider_override(selected_model)
    if provider_override == PROVIDER_ANTHROPIC and not ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY not found"
    if provider_override == PROVIDER_OPENAI and not OPENAI_API_KEY:
        return "OPENAI_API_KEY not found"
    return ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _clean_source_assertion_type(value: Any) -> str:
    normalized = _clean_text(value).lower()
    return normalized if normalized in SOURCE_ASSERTION_TYPES else "unknown"


def _clean_source_claim_reliability(value: Any) -> str:
    normalized = _clean_text(value).lower()
    return normalized if normalized in SOURCE_CLAIM_RELIABILITY else ""


def _as_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return default


def _normalize_source_claims(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    claims: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        source_claim = _clean_text(item.get("source_claim") or item.get("claim"))
        assertion_type = _clean_source_assertion_type(
            item.get("source_assertion_type") or item.get("assertion_type") or item.get("claim_type")
        )
        can_support_default = assertion_type in {"fact", "result_with_data"}
        normalized = {
            "source_claim": source_claim,
            "source_assertion_type": assertion_type,
            "evidence_locator": _clean_text(item.get("evidence_locator")),
            "honesty_signals": _string_list(item.get("honesty_signals")),
            "inflation_signals": _string_list(item.get("inflation_signals")),
            "can_support_differentiated_insight": _as_bool(
                item.get("can_support_differentiated_insight"),
                default=can_support_default,
            ),
            "limitation": _clean_text(item.get("limitation")),
        }
        if any(
            [
                normalized["source_claim"],
                normalized["evidence_locator"],
                normalized["honesty_signals"],
                normalized["inflation_signals"],
                normalized["limitation"],
                assertion_type != "unknown",
            ]
        ):
            claims.append(normalized)
    return claims


def _derive_source_claim_reliability(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "unknown"

    assertion_types = {claim["source_assertion_type"] for claim in claims}
    supportable_count = sum(1 for claim in claims if claim["can_support_differentiated_insight"])

    if assertion_types.issubset({"fact", "result_with_data"}) and supportable_count == len(claims):
        return "fact_grounded"
    if assertion_types.issubset({"aspiration"}):
        return "aspiration_heavy"
    if assertion_types.issubset({"result_without_data"}):
        return "result_without_data"
    if supportable_count and supportable_count < len(claims):
        return "mixed"
    if assertion_types.intersection({"aspiration"}):
        return "aspiration_heavy"
    if assertion_types.intersection({"result_without_data"}):
        return "result_without_data"
    return "assertion_only"


def _normalize_source_claim_reading(value: Any, *, source_depth_tier: str) -> dict[str, Any]:
    reading = value if isinstance(value, dict) else {}
    claims = _normalize_source_claims(reading.get("claims"))
    reliability = _clean_source_claim_reliability(reading.get("source_claim_reliability"))
    if not reliability:
        reliability = _derive_source_claim_reliability(claims)

    source_read_depth = _normalize_source_depth_tier(reading.get("source_read_depth") or source_depth_tier)
    return {
        "source_read_depth": source_read_depth,
        "source_claim_reliability": reliability,
        "claims": claims,
        "summary": _clean_text(reading.get("summary")),
    }


def _source_claim_limited(source_claim_reading: dict[str, Any]) -> bool:
    reliability = _clean_text(source_claim_reading.get("source_claim_reliability")).lower()
    if reliability in SOURCE_CLAIM_LIMITING_RELIABILITY:
        return True

    claims = source_claim_reading.get("claims")
    if not isinstance(claims, list) or not claims:
        return reliability == "unknown"

    return not any(
        bool(claim.get("can_support_differentiated_insight"))
        for claim in claims
        if isinstance(claim, dict)
    )


def _append_source_claim_limit_note(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return SOURCE_CLAIM_LIMIT_NOTE
    if SOURCE_CLAIM_LIMIT_NOTE.lower() in text.lower():
        return text
    return f"{text} {SOURCE_CLAIM_LIMIT_NOTE}"


def _normalize_source_read_targets(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    targets: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            target_type = _clean_text(item.get("target_type")) or "source_section"
            url = _clean_text(item.get("url"))
            path = _clean_text(item.get("path"))
            section_hint = _clean_text(item.get("section_hint") or item.get("section"))
            question = _clean_text(item.get("question"))
        else:
            target_type = "source_section"
            url = ""
            path = ""
            section_hint = _clean_text(item)
            question = ""
        if not any([url, path, section_hint, question]):
            continue
        targets.append(
            {
                "target_type": target_type,
                "url": url,
                "path": path,
                "section_hint": section_hint,
                "question": question,
            }
        )
    return targets


def _default_source_read_target() -> dict[str, str]:
    return {
        "target_type": "source_section",
        "url": "",
        "path": "original source or repository README",
        "section_hint": "mechanism, trust model, verification/admission claims, limitations",
        "question": "Which source-grounded mechanism confirms or falsifies the metadata-tier hypothesis?",
    }


def _normalize_source_depth_tier(value: Any) -> str:
    normalized = _clean_text(value).lower()
    return normalized if normalized in SOURCE_DEPTH_TIERS else "metadata"


def _analysis_mode_for_source_depth(source_depth_tier: str) -> str:
    return "source_grounded_comparison" if source_depth_tier == "full_source" else "hypothesis_only"


def _analysis_system_prompt(source_depth_tier: str) -> str:
    analysis_mode = _analysis_mode_for_source_depth(source_depth_tier)
    return (
        "You are AI Radar's Deep Project Match analyst. "
        "Your job is to compare one external signal with AI Radar's actual project architecture and judgment boundaries. "
        "Return JSON only. "
        f"Current source_depth_tier is {source_depth_tier}; current analysis_mode is {analysis_mode}. "
        "Use the AI Radar reference frame as a comparison ruler, not as evidence about the external signal. "
        "Analyze the external signal as the object under review. "
        "Do not update, rewrite, or infer new AI Radar architecture facts from the external signal. "
        "Differentiated insight must identify where the external signal aligns with, contrasts with, or pressures one AI Radar boundary, plane, threat model, or invariant. "
        "Do not treat project relevance as external factual verification. "
        "Separate provenance, source evidence, project-fit interpretation, and downstream action readiness. "
        "Never say that a signal is verified unless the provided verification metadata says so. "
        "source_depth_tier must never modify verification_status or admission. "
        "Reading more source material increases source depth only; it does not prove the claim true. "
        "A source sentence is a claim before it is a fact; first classify source-side assertions as fact, aspiration, result_with_data, or result_without_data. "
        "Use source_claim_reading to separate source_read_depth from source_claim_reliability. "
        "Use only these source_claim_reliability values: fact_grounded, mixed, assertion_only, aspiration_heavy, result_without_data, unknown. "
        "Aspiration or result_without_data claims must not support differentiated subtraction against AI Radar as if they were implemented facts. "
        "result_with_data requires traceable support such as a code path, dataset, benchmark definition, table, or figure locator. "
        "For mixed source_claim_reliability, decide by the specific claims that support the differentiated insight; do not downgrade an entire full-source read only because some unrelated source claims are limited. "
        "If source_depth_tier is metadata or source_excerpt, do not produce a definitive differentiated insight. "
        "In metadata/source_excerpt tiers, write suspected_differentiated_insight as a hypothesis and name the source section needed to confirm it. "
        "Only full_source tier with fact or result_with_data source claims may produce source-grounded differentiated insight. "
        f"If full_source analysis depends on aspiration or result_without_data claims, label it source_claim_limited and include this note in suspected_differentiated_insight: {SOURCE_CLAIM_LIMIT_NOTE} "
        "It is valid to leave suspected_differentiated_insight empty when metadata is insufficient. "
        "If metadata/source_excerpt tier provides suspected_differentiated_insight, it must also provide source_read_targets that can confirm or falsify it. "
        "Prefer a clear one-paragraph human judgment plus structured fields that a reviewer can use."
    )


def _analysis_user_prompt(
    *,
    signal: dict[str, Any],
    deep_match_review: dict[str, Any],
    analysis_context: str,
    source_depth_tier: str,
    source_text: str,
) -> str:
    analysis_mode = _analysis_mode_for_source_depth(source_depth_tier)
    payload = {
        "source_depth_tier": source_depth_tier,
        "analysis_mode": analysis_mode,
        "ai_radar_reference_frame": AI_RADAR_REFERENCE_FRAME,
        "external_signal": {
            "signal": signal,
            "source_text": source_text,
            "current_deep_match_review": deep_match_review,
        },
        "additional_ai_radar_context": analysis_context,
        "required_output_schema": {
            "narrative_summary": "One paragraph. In metadata/source_excerpt tier, phrase it as a hypothesis, not a conclusion.",
            "signal_side_fact": "What the external signal actually appears to be about.",
            "ai_radar_side_fact": "The specific AI Radar mechanism, module, or architecture issue it maps to.",
            "suspected_differentiated_insight": "Metadata/source_excerpt tier: optional. Leave empty if metadata cannot support a meaningful hypothesis. If present, bind it to source_read_targets. Full-source tier: the source-grounded differentiated insight.",
            "concrete_relevance": "Why this may be relevant to AI Radar, not just a shared keyword.",
            "architecture_comparison": "Metadata/source_excerpt tier: suspected comparison. Full-source tier: source-grounded comparison.",
            "borrow": "What AI Radar might borrow, if source-grounded. Metadata/source_excerpt tier must label this as tentative.",
            "beware": "What AI Radar should avoid or treat carefully.",
            "evidence_boundary": "What is source-supported vs internal project-fit judgment.",
            "decision_posture": "Knowledge, Watch, Review, or Reject, with reason.",
            "review_note": "A concise note suitable for Project Review metadata.",
            "needs_source_read": "true if source_depth_tier is not full_source or key mechanism claims require source confirmation.",
            "source_claim_reading": {
                "source_read_depth": (
                    "metadata|source_excerpt|full_source. Read depth only; this must not change "
                    "verification_status or source_claim_reliability by itself."
                ),
                "source_claim_reliability": (
                    "fact_grounded|mixed|assertion_only|aspiration_heavy|result_without_data|unknown. "
                    "fact_grounded means source-side claims are mainly falsifiable implementation facts. "
                    "mixed means supportable and limited source claims are both present; judge by the claims used for this differentiated insight. "
                    "assertion_only means the source says it but offers no implementation/data basis. "
                    "aspiration_heavy means goals or design intent are phrased as achieved capability. "
                    "result_without_data means result/effect claims lack traceable data, benchmark, table, figure, or code locator. "
                    "unknown means the current read depth cannot classify the source-side assertion."
                ),
                "claims": [
                    {
                        "source_claim": "Short source-side assertion being used for comparison.",
                        "source_assertion_type": (
                            "fact|aspiration|result_with_data|result_without_data. "
                            "fact is a falsifiable implementation detail. "
                            "aspiration is a goal/design intent or future capability. "
                            "result_with_data is a result claim with traceable support. "
                            "result_without_data is a result claim without traceable support."
                        ),
                        "evidence_locator": (
                            "README section, code path, paper table/figure, benchmark link, or blank. "
                            "Required for result_with_data."
                        ),
                        "honesty_signals": ["Source admits limitation, early stage, advisory status, or not-yet status."],
                        "inflation_signals": ["Present-tense capability claim without implementation or data."],
                        "can_support_differentiated_insight": "true only for fact or result_with_data claims.",
                        "limitation": "Why this claim can or cannot support comparison against AI Radar.",
                    }
                ],
                "summary": "One sentence explaining whether the source supports fact-grounded comparison or only source-assertion review.",
            },
            "source_read_targets": [
                {
                    "target_type": "url|repo_file|source_section",
                    "url": "Optional URL if known.",
                    "path": "Optional file path such as README.md.",
                    "section_hint": "The specific section/mechanism to inspect.",
                    "question": "What question this source read should confirm or falsify.",
                }
            ],
            "evidence_basis": "State exactly what input tier supports this analysis.",
            "structured_checklist": [
                {
                    "label": "Checklist label",
                    "value": "Human-readable finding",
                    "status": "ok|watch|risk",
                }
            ],
            "limitations": ["Any important limits or missing evidence."],
        },
        "hard_rules": [
            "This output is internal project-fit analysis, not verified external evidence.",
            "The AI Radar reference frame is the comparison ruler; it is not part of the external signal evidence pack.",
            "Keep ai_radar_reference_frame and external_signal physically and semantically separate.",
            "Do not let the external signal contaminate or rewrite the AI Radar reference frame.",
            "Do not recommend low-risk Action readiness from this analysis alone.",
            "Do not write or imply verification_status changes.",
            "If project fit is analogous rather than direct, say so clearly.",
            "If the signal is mainly a reference case, recommend Knowledge or Watch.",
            "Metadata/source_excerpt tier must output hypothesis + source read plan, not a firm conclusion.",
            "Metadata/source_excerpt tier may output no suspected_differentiated_insight if there is not enough metadata.",
            "Full-source source_claim_reading must still distinguish source assertion from implementation fact.",
            "Do not use aspiration or result_without_data claims as the basis for differentiated insight subtraction.",
            "For mixed source_claim_reliability, do not collapse the whole analysis; judge whether the specific differentiated insight depends on supportable source claims.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_structured_checklist(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _clean_text(item.get("label"))
        finding = _clean_text(item.get("value"))
        status = _clean_text(item.get("status")).lower()
        if status not in {"ok", "watch", "risk"}:
            status = "watch"
        if label or finding:
            normalized.append(
                {
                    "label": label or "Finding",
                    "value": finding or "Not recorded",
                    "status": status,
                }
            )
    return normalized


def _normalize_deep_match_analysis(payload: dict[str, Any], *, source_depth_tier: str) -> dict[str, Any]:
    analysis_mode = _analysis_mode_for_source_depth(source_depth_tier)
    needs_source_read = source_depth_tier != "full_source" or bool(payload.get("needs_source_read"))
    raw_source_read_targets = _normalize_source_read_targets(payload.get("source_read_targets"))
    source_read_targets = list(raw_source_read_targets)
    if needs_source_read and not source_read_targets:
        source_read_targets = [_default_source_read_target()]
    suspected_differentiated_insight = _clean_text(payload.get("suspected_differentiated_insight"))
    limitations = _string_list(payload.get("limitations"))
    source_claim_reading = _normalize_source_claim_reading(
        payload.get("source_claim_reading"),
        source_depth_tier=source_depth_tier,
    )
    if source_depth_tier in {"metadata", "source_excerpt"}:
        if suspected_differentiated_insight and raw_source_read_targets:
            hypothesis_status = "hypothesis_with_source_target"
        elif suspected_differentiated_insight and not raw_source_read_targets:
            suspected_differentiated_insight = ""
            hypothesis_status = "not_enough_metadata"
            limitations.append(
                "Model proposed a differentiated hypothesis without source_read_targets; treated as not_enough_metadata."
            )
        else:
            hypothesis_status = "not_enough_metadata"
    elif suspected_differentiated_insight and _source_claim_limited(source_claim_reading):
        suspected_differentiated_insight = _append_source_claim_limit_note(suspected_differentiated_insight)
        hypothesis_status = "source_claim_limited"
        limitations.append(
            "Full-source read depth found source assertions that are not sufficient implementation facts for differentiated subtraction."
        )
    elif suspected_differentiated_insight:
        hypothesis_status = "source_grounded"
    else:
        hypothesis_status = "not_enough_metadata"
    return {
        "analysis_type": "internal_project_fit_analysis",
        "reference_frame_version": "deep_match_reference_frame_v1",
        "reference_frame_source_hint": "AGENTS.md Intelligence Quality Boundaries plus implemented verification services.",
        "source_depth_tier": source_depth_tier,
        "analysis_mode": analysis_mode,
        "hypothesis_status": hypothesis_status,
        "differentiated_insight_status": "source_grounded" if hypothesis_status == "source_grounded" else hypothesis_status,
        "narrative_summary": _clean_text(payload.get("narrative_summary")),
        "signal_side_fact": _clean_text(payload.get("signal_side_fact")),
        "ai_radar_side_fact": _clean_text(payload.get("ai_radar_side_fact")),
        "suspected_differentiated_insight": suspected_differentiated_insight,
        "concrete_relevance": _clean_text(payload.get("concrete_relevance")),
        "architecture_comparison": _clean_text(payload.get("architecture_comparison")),
        "borrow": _clean_text(payload.get("borrow")),
        "beware": _clean_text(payload.get("beware")),
        "evidence_boundary": _clean_text(payload.get("evidence_boundary")),
        "decision_posture": _clean_text(payload.get("decision_posture")),
        "review_note": _clean_text(payload.get("review_note")),
        "review_note_effect": "review_context_only",
        "needs_source_read": needs_source_read,
        "source_claim_reading": source_claim_reading,
        "source_read_targets": source_read_targets,
        "evidence_basis": _clean_text(payload.get("evidence_basis"))
        or (
            "Metadata-tier analysis based on signal title, summary, project relevance text, and AI Radar context. "
            "Original source has not been deeply read in this analysis layer."
            if source_depth_tier == "metadata"
            else f"{source_depth_tier} analysis layer."
        ),
        "structured_checklist": _normalize_structured_checklist(payload.get("structured_checklist")),
        "limitations": limitations,
        "verification_effect": "none",
        "allowed_downstream_effect": "review_context_only",
    }


def generate_deep_project_match_analysis(
    *,
    signal: dict[str, Any],
    deep_match_review: dict[str, Any] | None = None,
    selected_model: str | None = None,
    user_id: str | None = None,
    source_depth_tier: str | None = None,
    source_text: str | None = None,
) -> dict[str, Any]:
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        raise ValueError("No supported LLM API key found for deep project match analysis")

    missing_provider_key = _missing_requested_provider_key(selected_model)
    if missing_provider_key:
        raise ValueError(missing_provider_key)

    analysis_context = build_analysis_context(user_id)
    provider_override = _resolve_provider_override(selected_model)
    normalized_source_depth_tier = _normalize_source_depth_tier(source_depth_tier)
    parsed_payload, route = execute_text_json_task(
        task_type=DEEP_MATCH_TASK_TYPE,
        provider_override=provider_override,
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
        max_tokens=2200,
        temperature=0.2,
        system_prompt=_analysis_system_prompt(normalized_source_depth_tier),
        user_prompt=_analysis_user_prompt(
            signal=signal,
            deep_match_review=deep_match_review or {},
            analysis_context=analysis_context,
            source_depth_tier=normalized_source_depth_tier,
            source_text=_clean_text(source_text),
        ),
    )

    normalized = _normalize_deep_match_analysis(parsed_payload, source_depth_tier=normalized_source_depth_tier)
    return {
        **normalized,
        "provider_used": getattr(route, "provider", "") or "",
        "model_used": getattr(route, "model", "") or "",
        "route_task_type": getattr(route, "task_type", DEEP_MATCH_TASK_TYPE),
    }
