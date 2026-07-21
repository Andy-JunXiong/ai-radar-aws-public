import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from app.prompts.registry import signal_insight_prompts
from app.services.context_bridge import build_analysis_context
from app.services.claim_extraction_service import extract_claims_from_insight
from app.services.claim_verification_service import verify_claims_against_evidence
from app.services.evidence_pack_service import build_signal_evidence_pack
from app.services.evidence_sufficiency_service import assess_evidence_sufficiency
from app.services.llm_executor_service import execute_text_json_task
from app.services.llm_json_service import parse_model_json
from app.services.low_evidence_gate_service import build_low_evidence_gate
from app.services.model_provenance_service import build_model_provenance
from app.services.model_router_service import PROVIDER_ANTHROPIC, PROVIDER_OPENAI
from app.services.verified_insight_service import build_verified_insight_metadata

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = REPO_ROOT / ".env"
COLLECTED_SIGNALS_FILE = REPO_ROOT / "data" / "output" / "collected_signals.json"

load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SIGNAL_INSIGHT_DEBUG_DIR = Path(__file__).resolve().parents[2] / "data" / "output" / "signal_insight_debug"
SIGNAL_INSIGHT_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
SIGNAL_INSIGHT_PROMPT_TEMPLATE_ID = "signal_insight"
SIGNAL_INSIGHT_PROMPT_TEMPLATE_VERSION = "v1"
SIGNAL_INSIGHT_ROUTE_KEY = "insight.synthesize"
SIGNAL_INSIGHT_INFERENCE_PARAMS = {
    "temperature": 0.3,
    "max_tokens": 1800,
    "top_p": None,
    "stop_sequences": [],
}


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


def _signal_match_key(signal: Dict[str, Any]) -> tuple[str, str, str]:
    url = _clean_text(signal.get("url") or signal.get("link") or signal.get("source_url")).lower()
    title = _clean_text(signal.get("title") or signal.get("signal_title")).lower()
    source = _clean_text(signal.get("source")).lower()
    return url, title, source


def _load_collected_signal_records() -> list[Dict[str, Any]]:
    try:
        payload = json.loads(COLLECTED_SIGNALS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        records = payload.get("signals") or payload.get("items") or []
        return [item for item in records if isinstance(item, dict)]
    return []


def _source_excerpt_from_collected_signal(signal: Dict[str, Any]) -> tuple[str, int]:
    existing_source_excerpt = _clean_text(signal.get("source_excerpt"))
    if existing_source_excerpt:
        return (
            existing_source_excerpt,
            int(signal.get("source_excerpt_length") or len(existing_source_excerpt)),
        )

    signal_url, signal_title, signal_source = _signal_match_key(signal)
    if not signal_url and not signal_title:
        return "", 0

    for candidate in _load_collected_signal_records():
        candidate_url, candidate_title, candidate_source = _signal_match_key(candidate)
        url_matches = bool(signal_url and candidate_url and signal_url == candidate_url)
        title_source_matches = bool(
            signal_title
            and candidate_title
            and signal_title == candidate_title
            and (not signal_source or not candidate_source or signal_source == candidate_source)
        )
        if not url_matches and not title_source_matches:
            continue

        source_excerpt = _clean_text(candidate.get("source_excerpt"))
        if source_excerpt:
            return (
                source_excerpt,
                int(candidate.get("source_excerpt_length") or len(source_excerpt)),
            )

    return "", 0


def _with_collected_source_excerpt(signal: Dict[str, Any]) -> Dict[str, Any]:
    source_excerpt, source_excerpt_length = _source_excerpt_from_collected_signal(signal)
    if not source_excerpt:
        return signal
    return {
        **signal,
        "source_excerpt": source_excerpt,
        "source_excerpt_length": source_excerpt_length,
    }


def _normalize_insight_payload(parsed: Dict[str, Any]) -> Dict[str, str]:
    return {
        "why_it_matters": _clean_text(parsed.get("why_it_matters", "")),
        "relevance_to_projects": _clean_text(parsed.get("relevance_to_projects", "")),
        "relevance_to_career": _clean_text(parsed.get("relevance_to_career", "")),
        "synthesized_insight": _clean_text(parsed.get("synthesized_insight", "")),
    }


def _has_meaningful_insight(parsed: Dict[str, Any]) -> bool:
    fields = [
        _clean_text(parsed.get("why_it_matters", "")),
        _clean_text(parsed.get("relevance_to_projects", "")),
        _clean_text(parsed.get("relevance_to_career", "")),
        _clean_text(parsed.get("synthesized_insight", "")),
    ]
    return any(len(value) >= 20 for value in fields)


def _build_fallback_insight(signal: Dict[str, Any]) -> Dict[str, str]:
    topic = signal.get("topic") or "General AI"
    source = signal.get("source") or "unknown source"

    return {
        "why_it_matters": (
            f"This signal matters because it highlights a potentially relevant development "
            f"in {topic}, and may influence how AI systems are being built or applied."
        ),
        "relevance_to_projects": (
            "This could be relevant to AI Radar, GLAP, or AI Cognitive if the topic connects "
            "to signal processing, intelligence workflows, or AI system design."
        ),
        "relevance_to_career": (
            "This is useful for your career because it helps strengthen your understanding of "
            "AI product architecture, system thinking, and industry trend interpretation."
        ),
        "synthesized_insight": (
            f"A practical takeaway is to track how signals from {source} map into your project "
            "architecture, product positioning, and long-term AI systems narrative."
        ),
    }


def _build_signal_payload(signal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signal_id": signal.get("signal_id") or signal.get("id") or "",
        "title": signal.get("title", ""),
        "summary": signal.get("summary", ""),
        "source": signal.get("source", ""),
        "published_at": signal.get("published_at", ""),
        "collected_at": signal.get("collected_at", ""),
        "topic": signal.get("topic", "General AI"),
        "score": signal.get("score"),
        "url": signal.get("url") or signal.get("link") or signal.get("source_url") or "",
        "source_excerpt": signal.get("source_excerpt", ""),
        "source_excerpt_length": signal.get("source_excerpt_length"),
        "insight_status": signal.get("insight_status", "unknown"),
        "insight_status_label": signal.get("insight_status_label", "Status unknown"),
        "subscription_topic_priority": signal.get("subscription_topic_priority", "normal"),
        "subscription_score_percent": signal.get("subscription_score_percent"),
        "subscription_project_links": signal.get("subscription_project_links", []),
        "auto_action_hint": signal.get("auto_action_hint", ""),
    }


def build_insight_fingerprint(payload: Dict[str, Any]) -> str:
    normalized = {
        "why_it_matters": _clean_text(str(payload.get("why_it_matters", ""))),
        "relevance_to_projects": _clean_text(str(payload.get("relevance_to_projects", ""))),
        "relevance_to_career": _clean_text(str(payload.get("relevance_to_career", ""))),
        "synthesized_insight": _clean_text(str(payload.get("synthesized_insight", ""))),
    }
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def write_signal_insight_debug_record(record: Dict[str, Any]) -> str:
    timestamp = str(record.get("generated_at") or "").replace(":", "").replace("-", "")
    signal_id = str(record.get("signal_id") or "unknown").replace("/", "_").replace("\\", "_")
    provider = str(record.get("actual_provider") or record.get("provider_used") or "unknown")
    file_name = f"{timestamp}_{signal_id}_{provider}.json"
    file_path = SIGNAL_INSIGHT_DEBUG_DIR / file_name
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_name


def _build_policy_metadata(
    *,
    signal_id: str,
    route_provider: str,
    route_model: str,
    evidence_pack: Dict[str, Any],
    evidence_quality: Dict[str, Any],
    low_evidence_gate: Dict[str, Any],
    generation_mode: str,
    content_fingerprint: str,
    notes: list[str],
    claim_results: list[dict[str, Any]] | None = None,
    produced_by_model: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    verified_insight = build_verified_insight_metadata(
        signal_id=signal_id,
        content_fingerprint=content_fingerprint,
        evidence_quality=evidence_quality,
        low_evidence_gate=low_evidence_gate,
        generation_mode=generation_mode,
        claim_results=claim_results,
        evidence_pack_id=evidence_pack.get("source_signal_id"),
        produced_by_model=produced_by_model,
    )
    return {
        "notes": notes,
        "evidence_pack_summary": {
            "source_signal_id": evidence_pack.get("source_signal_id", ""),
            "evidence_version": evidence_pack.get("evidence_version", "v1"),
            "observed_fact_count": len(evidence_pack.get("observed_facts") or []),
            "has_summary_excerpt": bool(evidence_pack.get("summary_excerpt")),
            "route_provider": route_provider,
            "route_model": route_model,
        },
        "verification": {
            **verified_insight,
            "evidence_quality": evidence_quality,
            "low_evidence_gate": low_evidence_gate,
            "confidence_score": low_evidence_gate.get("max_confidence"),
            "confidence_label": (
                "low"
                if float(low_evidence_gate.get("max_confidence") or 0) < 0.45
                else ("medium" if float(low_evidence_gate.get("max_confidence") or 0) < 0.75 else "high")
            ),
            "uncertainty_boundaries": low_evidence_gate.get("required_uncertainty_notes", []),
        },
        "evidence_pack": evidence_pack,
    }


def _apply_uncertainty_boundaries(
    payload: Dict[str, str],
    uncertainty_notes: list[str],
) -> Dict[str, str]:
    note = " ".join(str(item or "").strip() for item in uncertainty_notes if str(item or "").strip())
    if not note:
        return payload

    updated = dict(payload)
    for key, value in updated.items():
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        if cleaned.lower().startswith("uncertain:"):
            continue
        updated[key] = f"Uncertain: {cleaned} {note}".strip()
    return updated


def _build_claim_level_verification(
    *,
    signal_id: str,
    payload: Dict[str, Any],
    evidence_pack: Dict[str, Any],
    evidence_quality: Dict[str, Any],
    low_evidence_gate: Dict[str, Any],
    generation_mode: str,
    content_fingerprint: str,
    produced_by_model: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    claims = extract_claims_from_insight(payload)
    claim_results = verify_claims_against_evidence(claims, evidence_pack)
    verified_insight = build_verified_insight_metadata(
        signal_id=signal_id,
        content_fingerprint=content_fingerprint,
        evidence_quality=evidence_quality,
        low_evidence_gate=low_evidence_gate,
        generation_mode=generation_mode,
        claim_results=claim_results,
        evidence_pack_id=evidence_pack.get("source_signal_id"),
        produced_by_model=produced_by_model,
    )
    return {
        **verified_insight,
        "evidence_quality": evidence_quality,
        "low_evidence_gate": low_evidence_gate,
        "confidence_score": verified_insight.get("confidence_score", low_evidence_gate.get("max_confidence")),
        "confidence_label": (
            verified_insight.get("confidence_label")
            or (
                "low"
                if float(low_evidence_gate.get("max_confidence") or 0) < 0.45
                else ("medium" if float(low_evidence_gate.get("max_confidence") or 0) < 0.75 else "high")
            )
        ),
        "confidence_reason": verified_insight.get("confidence_reason", []),
        "uncertainty_boundaries": low_evidence_gate.get("required_uncertainty_notes", []),
    }


def _resolve_provider_override(selected_model: Optional[str]) -> Optional[str]:
    normalized = str(selected_model or "").strip().lower()
    if normalized in {"claude", "anthropic"}:
        return PROVIDER_ANTHROPIC
    if normalized in {"chatgpt", "openai"}:
        return PROVIDER_OPENAI
    return None


def _build_signal_insight_model_provenance(route: Any) -> dict[str, Any]:
    return build_model_provenance(
        provider=getattr(route, "provider", "") or "",
        model_id=getattr(route, "model", "") or "",
        task_type=getattr(route, "task_type", "insight") or "insight",
        route_key=SIGNAL_INSIGHT_ROUTE_KEY,
        router_source=getattr(route, "source", "") or "",
        prompt_template_id=SIGNAL_INSIGHT_PROMPT_TEMPLATE_ID,
        prompt_template_version=SIGNAL_INSIGHT_PROMPT_TEMPLATE_VERSION,
        inference_params=SIGNAL_INSIGHT_INFERENCE_PARAMS,
    )


def _build_signal_insight_fallback_model_provenance() -> dict[str, Any]:
    return build_model_provenance(
        provider="fallback",
        model_id="",
        task_type="insight",
        route_key=SIGNAL_INSIGHT_ROUTE_KEY,
        router_source="fallback",
        prompt_template_id="signal_insight_fallback",
        prompt_template_version=SIGNAL_INSIGHT_PROMPT_TEMPLATE_VERSION,
        inference_params={
            "temperature": None,
            "max_tokens": None,
            "top_p": None,
            "stop_sequences": [],
        },
    )


def _resolve_provider_label(selected_model: Optional[str], route_provider: str | None) -> str:
    normalized = str(selected_model or "").strip().lower()
    if normalized in {"claude", "anthropic"}:
        return "claude"
    if normalized in {"chatgpt", "openai"}:
        return "chatgpt"
    if str(route_provider or "").strip().lower() == PROVIDER_ANTHROPIC:
        return "claude"
    return "chatgpt"


def _missing_requested_provider_key(selected_model: Optional[str]) -> str:
    provider_override = _resolve_provider_override(selected_model)
    if provider_override == PROVIDER_ANTHROPIC and not ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY not found"
    if provider_override == PROVIDER_OPENAI and not OPENAI_API_KEY:
        return "OPENAI_API_KEY not found"
    return ""


def generate_signal_insight(
    signal: Dict[str, Any],
    *,
    selected_model: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, str]:
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        raise ValueError("No supported LLM API key found for signal insight generation")
    missing_provider_key = _missing_requested_provider_key(selected_model)
    if missing_provider_key:
        raise ValueError(missing_provider_key)

    enriched_signal = _with_collected_source_excerpt(signal)
    analysis_context = build_analysis_context(user_id)
    signal_payload = _build_signal_payload(enriched_signal)
    evidence_pack = build_signal_evidence_pack(enriched_signal)
    evidence_quality = assess_evidence_sufficiency(evidence_pack)
    low_evidence_gate = build_low_evidence_gate(evidence_quality)

    system_prompt, user_prompt = signal_insight_prompts(
        analysis_context=analysis_context,
        signal_payload=signal_payload,
    )

    provider_override = _resolve_provider_override(selected_model)
    last_error_message = ""

    for attempt in range(2):
        try:
            parsed_payload, route = execute_text_json_task(
                task_type="insight",
                provider_override=provider_override,
                openai_api_key=OPENAI_API_KEY,
                anthropic_api_key=ANTHROPIC_API_KEY,
                max_tokens=1800,
                temperature=0.3,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            parsed = _normalize_insight_payload(
                parse_model_json(json.dumps(parsed_payload, ensure_ascii=False))
            )
            parsed = _apply_uncertainty_boundaries(
                parsed,
                low_evidence_gate.get("required_uncertainty_notes", []),
            )

            if _has_meaningful_insight(parsed):
                fingerprint = build_insight_fingerprint(parsed)
                produced_by_model = _build_signal_insight_model_provenance(route)
                verification = _build_claim_level_verification(
                    signal_id=str(signal.get("signal_id") or signal.get("id") or ""),
                    payload=parsed,
                    evidence_pack=evidence_pack,
                    evidence_quality=evidence_quality,
                    low_evidence_gate=low_evidence_gate,
                    generation_mode="llm",
                    content_fingerprint=fingerprint,
                    produced_by_model=produced_by_model,
                )
                return {
                    **parsed,
                    "evidence_pack": evidence_pack,
                    "verification": verification,
                    "produced_by_model": produced_by_model,
                    "provider_used": _resolve_provider_label(selected_model, getattr(route, "provider", "")),
                    "actual_provider": getattr(route, "provider", "") or "",
                    "model_used": getattr(route, "model", "") or "",
                    "generation_mode": "llm",
                    "requested_provider": _resolve_provider_label(selected_model, getattr(route, "provider", "")),
                    "content_fingerprint": fingerprint,
                    "policy_metadata": _build_policy_metadata(
                        signal_id=str(signal.get("signal_id") or signal.get("id") or ""),
                        route_provider=getattr(route, "provider", "unknown"),
                        route_model=getattr(route, "model", "unknown"),
                        evidence_pack=evidence_pack,
                        evidence_quality=evidence_quality,
                        low_evidence_gate=low_evidence_gate,
                        generation_mode="llm",
                        content_fingerprint=fingerprint,
                        claim_results=verification.get("claim_results", []),
                        produced_by_model=produced_by_model,
                        notes=[
                            f"Generated successfully via {getattr(route, 'provider', 'unknown')}:{getattr(route, 'model', 'unknown')}.",
                            f"Evidence quality assessed as {evidence_quality.get('level')} ({evidence_quality.get('score')}).",
                            f"Verified insight status set to {verification.get('verification_status')}.",
                            "Evidence Pack MVP attached to insight output.",
                        ],
                    ),
                }

            last_error_message = (
                f"Weak result via {getattr(route, 'provider', 'unknown')}:{getattr(route, 'model', 'unknown')} "
                "did not pass the minimum content check."
            )
            print(
                f"[WARN] Weak insight returned on attempt {attempt + 1} "
                f"for signal {signal.get('signal_id') or signal.get('id')} "
                f"via {route.provider}:{route.model}"
            )
        except Exception as e:
            last_error_message = str(e).strip() or e.__class__.__name__
            print(f"[WARN] Insight generation failed on attempt {attempt + 1}: {e}")

    fallback_payload = _apply_uncertainty_boundaries(
        _build_fallback_insight(signal),
        low_evidence_gate.get("required_uncertainty_notes", []),
    )
    fallback_fingerprint = build_insight_fingerprint(fallback_payload)
    produced_by_model = _build_signal_insight_fallback_model_provenance()
    verification = _build_claim_level_verification(
        signal_id=str(signal.get("signal_id") or signal.get("id") or ""),
        payload=fallback_payload,
        evidence_pack=evidence_pack,
        evidence_quality=evidence_quality,
        low_evidence_gate=low_evidence_gate,
        generation_mode="fallback",
        content_fingerprint=fallback_fingerprint,
        produced_by_model=produced_by_model,
    )
    return {
        **fallback_payload,
        "evidence_pack": evidence_pack,
        "verification": verification,
        "produced_by_model": produced_by_model,
        "provider_used": "fallback",
        "actual_provider": "fallback",
        "model_used": "",
        "generation_mode": "fallback",
        "requested_provider": _resolve_provider_label(selected_model, None),
        "content_fingerprint": fallback_fingerprint,
        "policy_metadata": _build_policy_metadata(
            signal_id=str(signal.get("signal_id") or signal.get("id") or ""),
            route_provider="fallback",
            route_model="",
            evidence_pack=evidence_pack,
            evidence_quality=evidence_quality,
            low_evidence_gate=low_evidence_gate,
            generation_mode="fallback",
            content_fingerprint=fallback_fingerprint,
            claim_results=verification.get("claim_results", []),
            produced_by_model=produced_by_model,
            notes=[
                "Fallback template output was used.",
                f"Evidence quality assessed as {evidence_quality.get('level')} ({evidence_quality.get('score')}).",
                f"Verified insight status set to {verification.get('verification_status')}.",
                "Evidence Pack MVP attached to fallback insight output.",
                last_error_message or "Claude/OpenAI generation did not return a usable result.",
            ],
        ),
    }
