from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.services.llm_executor_service import execute_text_json_task
from app.services.model_router_service import PROVIDER_ANTHROPIC, PROVIDER_OPENAI


REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = REPO_ROOT / ".env"

load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
COUNTER_CHECK_TASK_TYPE = "reason"
COUNTER_CHECK_BOUNDARY = (
    "LLM advisory only: does not change verification_status, Project Takeaway gate, "
    "blocked_downstream_actions, or Action eligibility."
)


def _clean_text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(str(text).split())
    return text[:limit]


def _string_list(value: Any, limit: int = 5) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []
    cleaned = [_clean_text(item, limit=360) for item in items]
    return [item for item in cleaned if item][:limit]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_source_provider(provenance: dict[str, Any]) -> str:
    provider = _clean_text(provenance.get("provider"), 80).lower()
    model = _clean_text(
        provenance.get("model_id") or provenance.get("model") or provenance.get("model_used"),
        160,
    ).lower()

    if provider in {PROVIDER_ANTHROPIC, "claude"} or model.startswith("claude"):
        return PROVIDER_ANTHROPIC
    if provider in {PROVIDER_OPENAI, "gpt", "chatgpt"} or model.startswith(("gpt", "o1", "o3", "o4")):
        return PROVIDER_OPENAI
    return ""


def _provider_has_key(provider: str) -> bool:
    if provider == PROVIDER_OPENAI:
        return bool(OPENAI_API_KEY)
    if provider == PROVIDER_ANTHROPIC:
        return bool(ANTHROPIC_API_KEY)
    return False


def _provider_selection(payload: dict[str, Any]) -> dict[str, str | None]:
    source_provenance = _dict_value(payload.get("source_model_provenance"))
    source_provider = _normalize_source_provider(source_provenance)
    preferred_provider = ""
    if source_provider == PROVIDER_ANTHROPIC:
        preferred_provider = PROVIDER_OPENAI
    elif source_provider == PROVIDER_OPENAI:
        preferred_provider = PROVIDER_ANTHROPIC

    if preferred_provider and _provider_has_key(preferred_provider):
        return {
            "provider_override": preferred_provider,
            "comparison_mode": "cross_provider",
            "source_provider": source_provider,
            "source_model_id": _clean_text(source_provenance.get("model_id"), 160),
            "preferred_counter_provider": preferred_provider,
            "provider_selection_note": "Counter-check used the opposite provider from the source model.",
        }

    if source_provider and _provider_has_key(source_provider):
        return {
            "provider_override": source_provider,
            "comparison_mode": "same_provider_fallback",
            "source_provider": source_provider,
            "source_model_id": _clean_text(source_provenance.get("model_id"), 160),
            "preferred_counter_provider": preferred_provider,
            "provider_selection_note": "Opposite provider API key was unavailable; counter-check used same-provider fallback.",
        }

    fallback_override = None
    if OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        fallback_override = PROVIDER_OPENAI
    elif ANTHROPIC_API_KEY and not OPENAI_API_KEY:
        fallback_override = PROVIDER_ANTHROPIC

    return {
        "provider_override": fallback_override,
        "comparison_mode": "default_route",
        "source_provider": source_provider,
        "source_model_id": _clean_text(source_provenance.get("model_id"), 160),
        "preferred_counter_provider": preferred_provider,
        "provider_selection_note": "Source provider was unknown or unavailable; counter-check used the default model route.",
    }


def _packet_json(payload: dict[str, Any]) -> str:
    source_provenance = _dict_value(payload.get("source_model_provenance"))
    safe_payload = {
        "project": {
            "project_id": _clean_text(payload.get("project_id"), 160),
            "project_name": _clean_text(payload.get("project_name"), 240),
        },
        "signal": {
            "signal_id": _clean_text(payload.get("signal_id"), 160),
            "signal_title": _clean_text(payload.get("signal_title"), 320),
            "signal_summary": _clean_text(payload.get("signal_summary"), 1400),
        },
        "candidate_takeaway": {
            "takeaway": _clean_text(payload.get("takeaway"), 1200),
            "why_it_matters": _clean_text(payload.get("why_it_matters"), 1200),
            "fit_reason": _clean_text(payload.get("fit_reason"), 1200),
            "benefits": _clean_text(payload.get("benefits"), 1200),
            "final_reflection": _clean_text(payload.get("final_reflection"), 1200),
        },
        "reviewer_advisory": {
            "claim_support": _clean_text(payload.get("claim_support"), 800),
            "warrant": _clean_text(payload.get("warrant"), 1600),
            "counter_check_prompt": _clean_text(payload.get("counter_check_prompt"), 1200),
            "boundary": _clean_text(payload.get("boundary"), 800),
        },
        "source_model_provenance": {
            "provider": _clean_text(source_provenance.get("provider"), 80),
            "model_id": _clean_text(source_provenance.get("model_id"), 160),
            "task_type": _clean_text(source_provenance.get("task_type"), 80),
            "provenance_schema_version": source_provenance.get("provenance_schema_version"),
        },
        "verification_metadata": payload.get("verification_metadata") or {},
        "action_eligibility": payload.get("action_eligibility") or {},
    }
    return json.dumps(safe_payload, ensure_ascii=False, indent=2)[:12000]


def _system_prompt() -> str:
    return (
        "You are AI Radar's ADR-0015 reviewer advisory assistant. "
        "You inspect whether a Project Review candidate's recorded evidence and warrant "
        "can also support an opposite, incompatible, weaker, Watch-only, or no-takeaway conclusion. "
        "Use only the supplied packet. Do not browse. Do not add outside facts. "
        "Do not decide verification status, Project Takeaway gates, blocked downstream actions, or Action eligibility. "
        "Return strict JSON only with keys: answer, summary, opposite_or_incompatible_conclusion, "
        "evidence_used, missing_evidence, reviewer_next_step, boundary. "
        "answer must be exactly yes, no, or unclear. "
        "Use yes when the same packet materially supports an opposite or incompatible conclusion; "
        "no when the packet only supports the proposed takeaway under the stated warrant; "
        "unclear when the packet is underdetermined or missing decisive evidence."
    )


def _user_prompt(payload: dict[str, Any]) -> str:
    return (
        "Generate a reviewer-only counter-check draft for this Review Inbox candidate.\n\n"
        "Required output shape:\n"
        "{\n"
        '  "answer": "yes|no|unclear",\n'
        '  "summary": "one or two sentences explaining the advisory judgment",\n'
        '  "opposite_or_incompatible_conclusion": "the strongest alternative conclusion, or why none is supported",\n'
        '  "evidence_used": ["specific packet facts used"],\n'
        '  "missing_evidence": ["missing facts or checks that would reduce uncertainty"],\n'
        '  "reviewer_next_step": "what the human reviewer should do next",\n'
        f'  "boundary": "{COUNTER_CHECK_BOUNDARY}"\n'
        "}\n\n"
        "Candidate packet:\n"
        f"{_packet_json(payload)}"
    )


def generate_reasoning_counter_check(payload: dict[str, Any]) -> dict[str, Any]:
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        raise ValueError("No supported LLM API key found for counter-check generation")

    provider_selection = _provider_selection(payload)
    parsed, route = execute_text_json_task(
        task_type=COUNTER_CHECK_TASK_TYPE,
        provider_override=provider_selection["provider_override"],
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
        max_tokens=1200,
        temperature=0.1,
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(payload),
    )

    answer = _clean_text(parsed.get("answer"), limit=40).lower()
    if answer not in {"yes", "no", "unclear"}:
        answer = "unclear"

    return {
        "answer": answer,
        "summary": _clean_text(parsed.get("summary"), limit=900),
        "opposite_or_incompatible_conclusion": _clean_text(
            parsed.get("opposite_or_incompatible_conclusion"),
            limit=900,
        ),
        "evidence_used": _string_list(parsed.get("evidence_used")),
        "missing_evidence": _string_list(parsed.get("missing_evidence")),
        "reviewer_next_step": _clean_text(parsed.get("reviewer_next_step"), limit=600),
        "boundary": COUNTER_CHECK_BOUNDARY,
        "comparison_mode": provider_selection["comparison_mode"],
        "source_provider": provider_selection["source_provider"] or "",
        "source_model_id": provider_selection["source_model_id"] or "",
        "preferred_counter_provider": provider_selection["preferred_counter_provider"] or "",
        "countercheck_provider": getattr(route, "provider", "") or "",
        "provider_selection_note": provider_selection["provider_selection_note"] or "",
        "produced_by_model": {
            "provider": getattr(route, "provider", "") or "",
            "model_id": getattr(route, "model", "") or "",
            "route_key": getattr(route, "tier", "") or "",
            "task_type": getattr(route, "task_type", COUNTER_CHECK_TASK_TYPE),
            "provenance_schema_version": 1,
            "provenance_completeness": "route_only",
        },
    }
