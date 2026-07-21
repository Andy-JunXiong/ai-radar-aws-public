import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.model_router_service import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    PROVIDER_PERPLEXITY,
)
from app.services.llm_executor_service import execute_text_json_task, execute_text_task
from app.services.s3_reader import (
    analyze_agent_watch_repo,
    load_agent_watch,
    load_agent_watch_detail,
    load_friction_signal_detail,
    load_friction_signals,
    load_radar,
    load_radar_intelligence,
)
from app.project_registry import list_projects
from app.services.admin_guard import require_admin_auth
from app.services.project_calibration_event_service import summarize_project_calibration_events
from app.services.project_review_record_service import summarize_project_review_records
from app.services.strategic_synthesis_service import build_strategic_synthesis_response

router = APIRouter()

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


class TranslationRequest(BaseModel):
    text: str


def _translation_provider_fallback_enabled() -> bool:
    value = str(os.getenv("ENABLE_TRANSLATION_PROVIDER_FALLBACK", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _is_retryable_translation_error(error: Exception) -> bool:
    text = str(error)
    lowered = text.lower()
    return (
        "overloaded_error" in text
        or "overloaded" in lowered
        or "529" in text
        or "rate limit" in lowered
        or "timeout" in lowered
    )


def _is_invalid_openai_key_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "invalid_api_key" in text
        or "incorrect api key provided" in text
        or ("401" in text and "api key" in text)
    )


def _is_invalid_anthropic_key_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "authentication_error" in text
        or "invalid x-api-key" in text
        or ("401" in text and "api key" in text)
        or ("401" in text and "anthropic" in text)
    )


def _format_translation_error(error: Exception) -> str:
    text = str(error).lower()

    if _is_invalid_openai_key_error(error):
        return (
            "OpenAI translation is unavailable because OPENAI_API_KEY is invalid. "
            "Update the root .env file or use Claude translation fallback."
        )

    if _is_invalid_anthropic_key_error(error):
        return (
            "Claude translation is unavailable because ANTHROPIC_API_KEY is invalid. "
            "Update the root .env file and restart the backend."
        )

    if "not_found_error" in text or "model not found" in text or "model:" in text:
        return (
            "The configured translation model is not available for the current account. "
            "Check the provider model settings in the root .env file."
        )

    return f"Translation failed: {error}"


def _translate_text_to_cn(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        return {"translated_text": "", "provider_used": None, "model_used": None}

    system_prompt = """
You translate AI intelligence content into natural, clear Simplified Chinese.

Rules:
- Preserve meaning faithfully
- Keep repo names, company names, product names, URLs, and technical identifiers in original form when helpful
- Keep bullet structure when present
- Do not add commentary
- Return translated text only
""".strip()

    attempts: list[str] = []

    def _attempt(provider: str, *, fallback_used: bool) -> tuple[str, object]:
        attempts.append(provider)
        return execute_text_task(
            task_type="translate",
            system_prompt=system_prompt,
            user_prompt=text,
            temperature=0.1,
            provider_override=provider,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            perplexity_api_key=PERPLEXITY_API_KEY,
            fallback_used=fallback_used,
        )

    try:
        if ANTHROPIC_API_KEY:
            try:
                translated_text, route = _attempt(PROVIDER_ANTHROPIC, fallback_used=False)
            except Exception as anthropic_error:
                if _translation_provider_fallback_enabled() and _is_retryable_translation_error(anthropic_error) and OPENAI_API_KEY:
                    try:
                        translated_text, route = _attempt(PROVIDER_OPENAI, fallback_used=True)
                    except Exception as openai_error:
                        if _translation_provider_fallback_enabled() and _is_retryable_translation_error(openai_error) and PERPLEXITY_API_KEY:
                            translated_text, route = _attempt(PROVIDER_PERPLEXITY, fallback_used=True)
                        else:
                            raise HTTPException(
                                status_code=502,
                                detail=_format_translation_error(openai_error),
                            ) from openai_error
                elif _translation_provider_fallback_enabled() and _is_retryable_translation_error(anthropic_error) and PERPLEXITY_API_KEY:
                    translated_text, route = _attempt(PROVIDER_PERPLEXITY, fallback_used=True)
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=_format_translation_error(anthropic_error),
                    ) from anthropic_error
        elif OPENAI_API_KEY:
            try:
                translated_text, route = _attempt(PROVIDER_OPENAI, fallback_used=False)
            except Exception as openai_error:
                if _translation_provider_fallback_enabled() and _is_retryable_translation_error(openai_error) and PERPLEXITY_API_KEY:
                    translated_text, route = _attempt(PROVIDER_PERPLEXITY, fallback_used=True)
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=_format_translation_error(openai_error),
                    ) from openai_error
        elif PERPLEXITY_API_KEY:
            translated_text, route = _attempt(PROVIDER_PERPLEXITY, fallback_used=False)
        else:
            raise HTTPException(
                status_code=500,
                detail="No translation provider is configured. Add ANTHROPIC_API_KEY, OPENAI_API_KEY, or PERPLEXITY_API_KEY to the root .env file.",
            )
    except HTTPException:
        raise
    except Exception as final_error:
        raise HTTPException(
            status_code=502,
            detail=_format_translation_error(final_error),
        ) from final_error

    return {
        "translated_text": translated_text,
        "provider_used": route.provider,
        "model_used": route.model,
    }


def _translate_json_to_cn(payload: dict) -> dict:
    system_prompt = """
You translate structured AI intelligence content into natural, clear Simplified Chinese.

Rules:
- Preserve JSON shape exactly
- Translate user-facing prose into Simplified Chinese
- Keep repo names, company names, product names, URLs, technical identifiers, and scores unchanged when helpful
- Keep arrays as arrays
- Do not add commentary
""".strip()

    def _attempt(provider: str, *, fallback_used: bool) -> tuple[dict, object]:
        return execute_text_json_task(
            task_type="translate",
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            temperature=0.1,
            provider_override=provider,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            fallback_used=fallback_used,
        )

    try:
        if ANTHROPIC_API_KEY:
            try:
                translated_payload, route = _attempt(PROVIDER_ANTHROPIC, fallback_used=False)
            except Exception as anthropic_error:
                if _translation_provider_fallback_enabled() and _is_retryable_translation_error(anthropic_error) and OPENAI_API_KEY:
                    try:
                        translated_payload, route = _attempt(PROVIDER_OPENAI, fallback_used=True)
                    except Exception as openai_error:
                        raise HTTPException(
                            status_code=502,
                            detail=_format_translation_error(openai_error),
                        ) from openai_error
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=_format_translation_error(anthropic_error),
                    ) from anthropic_error
        elif OPENAI_API_KEY:
            try:
                translated_payload, route = _attempt(PROVIDER_OPENAI, fallback_used=False)
            except Exception as openai_error:
                raise HTTPException(
                    status_code=502,
                    detail=_format_translation_error(openai_error),
                ) from openai_error
        else:
            raise HTTPException(
                status_code=500,
                detail="No supported translation provider is configured. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to the root .env file.",
            )
    except HTTPException:
        raise
    except Exception as final_error:
        raise HTTPException(
            status_code=502,
            detail=_format_translation_error(final_error),
        ) from final_error

    return {
        "translated": translated_payload,
        "provider_used": route.provider,
        "model_used": route.model,
    }

@router.get("/radar")
def get_radar():
    return load_radar()

@router.get("/radar/intelligence")
def get_radar_intelligence():
    return load_radar_intelligence()


@router.get("/radar/strategic-synthesis", dependencies=[Depends(require_admin_auth)])
def get_radar_strategic_synthesis():
    return build_strategic_synthesis_response(
        radar_intelligence=load_radar_intelligence(),
        review_summary=summarize_project_review_records(),
        calibration_summary=summarize_project_calibration_events(),
        projects=list_projects(),
    )


@router.get("/radar/agent-watch")
def get_radar_agent_watch():
    return load_agent_watch()


@router.get("/radar/agent-watch/detail")
def get_radar_agent_watch_detail(entity_id: str = Query(...)):
    return load_agent_watch_detail(entity_id)


@router.post("/radar/agent-watch/analyze")
def post_radar_agent_watch_analyze(entity_id: str = Query(...)):
    return analyze_agent_watch_repo(entity_id)


@router.get("/radar/agent-watch/analyze")
def get_radar_agent_watch_analyze(entity_id: str = Query(...)):
    return analyze_agent_watch_repo(entity_id)


@router.get("/radar/friction-signals")
def get_radar_friction_signals():
    return load_friction_signals()


@router.get("/radar/friction-signals/detail")
def get_radar_friction_signal_detail(entity_id: str = Query(...)):
    return load_friction_signal_detail(entity_id)


@router.post("/radar/translate-cn")
def post_radar_translate_cn(payload: TranslationRequest):
    return _translate_text_to_cn(payload.text)


@router.get("/radar/friction-signals/translate")
def get_radar_friction_signal_translate(entity_id: str = Query(...)):
    detail = load_friction_signal_detail(entity_id)
    if not detail.get("found"):
        raise HTTPException(status_code=404, detail="Friction signal not found.")

    current = detail.get("signal") if isinstance(detail.get("signal"), dict) else {}
    profile = detail.get("profile") if isinstance(detail.get("profile"), dict) else {}

    text = "\n\n".join(
        [
            value
            for value in [
                str(current.get("title") or "").strip(),
                str(current.get("summary") or "").strip(),
                str(profile.get("problem_summary") or "").strip(),
                str(profile.get("why_this_matters") or "").strip(),
                str(profile.get("product_opportunity") or "").strip(),
            ]
            if value
        ]
    )

    if not text:
        raise HTTPException(status_code=400, detail="This friction item does not have enough text to translate.")

    translated_text_payload = _translate_text_to_cn(text)
    translated_fields_payload = _translate_json_to_cn(
        {
            "title": str(current.get("title") or "").strip(),
            "summary": str(current.get("summary") or "").strip(),
            "friction_subtopic": str(current.get("friction_subtopic") or "").strip(),
            "profile": {
                "why_this_matters": str(profile.get("why_this_matters") or "").strip(),
                "product_opportunity": str(profile.get("product_opportunity") or "").strip(),
            },
        }
    )

    return {
        "translated_text": translated_text_payload.get("translated_text", ""),
        "translated_fields": translated_fields_payload.get("translated", {}),
        "provider_used": translated_fields_payload.get("provider_used") or translated_text_payload.get("provider_used"),
        "model_used": translated_fields_payload.get("model_used") or translated_text_payload.get("model_used"),
    }


@router.get("/radar/friction-signals/detail/translate")
def get_radar_friction_signal_detail_translate(entity_id: str = Query(...)):
    detail = load_friction_signal_detail(entity_id)
    if not detail.get("found"):
        raise HTTPException(status_code=404, detail="Friction signal not found.")

    profile = detail.get("profile") if isinstance(detail.get("profile"), dict) else {}
    related_signals = detail.get("related_signals") if isinstance(detail.get("related_signals"), list) else []

    payload = {
        "title": str(detail.get("title") or "").strip(),
        "summary": str(detail.get("summary") or "").strip(),
        "friction_subtopic": str(detail.get("friction_subtopic") or "").strip(),
        "profile": {
            "problem_summary": str(profile.get("problem_summary") or "").strip(),
            "why_this_matters": str(profile.get("why_this_matters") or "").strip(),
            "who_is_affected": str(profile.get("who_is_affected") or "").strip(),
            "product_opportunity": str(profile.get("product_opportunity") or "").strip(),
            "suggested_response": profile.get("suggested_response") or [],
        },
        "matched_keywords": detail.get("matched_keywords") or [],
        "related_signals": [
            {
                "title": str(item.get("title") or "").strip(),
                "source": str(item.get("source") or "").strip(),
            }
            for item in related_signals
            if isinstance(item, dict)
        ],
    }

    return _translate_json_to_cn(payload)
