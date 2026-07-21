import json
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.intelligence.model_router import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    ModelRoute,
    route_task,
)
from app.intelligence.model_router_telemetry import record_route_event
from backend.app.services.metrics_event_service import record_llm_call


@dataclass(frozen=True)
class LLMExecutionResult:
    route: ModelRoute
    raw_text: str
    parsed_json: dict[str, Any] | None = None


def _should_log_route() -> bool:
    value = str(os.getenv("MODEL_ROUTER_LOGGING", "1")).strip().lower()
    return value not in {"0", "false", "off", "no"}


def _log_route(*, route: ModelRoute, mode: str) -> None:
    if not _should_log_route():
        return
    print(
        "[router] "
        f"task={route.task_type} "
        f"tier={route.tier} "
        f"provider={route.provider} "
        f"model={route.model} "
        f"source={route.source} "
        f"mode={mode}"
    )
    record_route_event(route=route, mode=mode)


def _usage_tokens(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None

    input_tokens = (
        getattr(usage, "prompt_tokens", None)
        or getattr(usage, "input_tokens", None)
    )
    output_tokens = (
        getattr(usage, "completion_tokens", None)
        or getattr(usage, "output_tokens", None)
    )
    return input_tokens, output_tokens


def _record_llm_metric(
    *,
    route: ModelRoute,
    mode: str,
    started_at: float,
    success: bool,
    error_type: str | None = None,
    response: Any = None,
    json_validation_passed: bool | None = None,
) -> None:
    input_tokens, output_tokens = _usage_tokens(response)
    try:
        record_llm_call(
            {
                "task_type": route.task_type,
                "provider": route.provider,
                "model": route.model,
                "mode": mode,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "success": success,
                "error_type": error_type,
                "fallback_used": False,
                "retry_count": 0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": None,
                "json_validation_passed": json_validation_passed,
                "json_repair_used": False,
            }
        )
    except Exception as exc:
        print(f"[metrics] failed to record LLM call: {exc}")


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = (raw_text or "").strip()
    if not stripped:
        raise ValueError("Empty JSON response.")

    try:
        return json.loads(stripped)
    except Exception:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start : end + 1])

    raise ValueError("No JSON object found in model output.")


def _openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")
    return OpenAI(api_key=api_key)


def _openai_model_supports_temperature(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return True

    temperature_unsupported_prefixes = (
        "gpt-5",
        "o1",
        "o3",
        "o4",
    )
    return not normalized.startswith(temperature_unsupported_prefixes)


def _openai_chat_kwargs(*, model: str, temperature: float, **kwargs: Any) -> dict[str, Any]:
    payload = {
        "model": model,
        **kwargs,
    }
    if _openai_model_supports_temperature(model):
        payload["temperature"] = temperature
    return payload


def _anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")

    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def _anthropic_message_kwargs(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    system: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if system is not None:
        kwargs["system"] = system
    return kwargs


def _split_system_messages(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    remaining: list[dict[str, Any]] = []

    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = message.get("content")
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
            continue
        remaining.append(message)

    system_prompt = "\n\n".join(system_parts).strip() or None
    return system_prompt, remaining


def _normalize_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    for message in messages:
        role = str(message.get("role") or "user").strip().lower()
        content = message.get("content")
        if isinstance(content, list):
            text_parts = [
                str(item.get("text") or "").strip()
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            content = "\n".join(part for part in text_parts if part)
        if not isinstance(content, str):
            content = str(content or "")
        normalized.append({"role": role or "user", "content": content})

    return normalized


def execute_routed_task(
    *,
    task_type: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    json_mode: bool = False,
    max_tokens: int = 1400,
) -> LLMExecutionResult:
    route = route_task(task_type)
    mode = "json" if json_mode else "text"
    started_at = time.perf_counter()
    _log_route(route=route, mode=mode)

    try:
        if route.provider == PROVIDER_OPENAI:
            client = _openai_client()
            request_kwargs: dict[str, Any] = _openai_chat_kwargs(
                model=route.model,
                temperature=temperature,
                messages=messages,
            )
            if json_mode:
                request_kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**request_kwargs)
            raw_text = response.choices[0].message.content or ""
        elif route.provider == PROVIDER_ANTHROPIC:
            client = _anthropic_client()
            system_prompt, prompt_messages = _split_system_messages(messages)
            response = client.messages.create(
                **_anthropic_message_kwargs(
                    model=route.model,
                    system=system_prompt,
                    messages=_normalize_anthropic_messages(prompt_messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            parts = []
            for block in response.content:
                text = getattr(block, "text", "")
                if text:
                    parts.append(text)
            raw_text = "\n".join(parts).strip()
        else:
            raise ValueError(f"Unsupported LLM provider: {route.provider}")

        parsed_json = _extract_json_object(raw_text) if json_mode else None
        _record_llm_metric(
            route=route,
            mode=mode,
            started_at=started_at,
            success=True,
            response=response,
            json_validation_passed=True if json_mode else None,
        )
        return LLMExecutionResult(route=route, raw_text=raw_text, parsed_json=parsed_json)
    except Exception as exc:
        _record_llm_metric(
            route=route,
            mode=mode,
            started_at=started_at,
            success=False,
            error_type=exc.__class__.__name__,
            json_validation_passed=False if json_mode else None,
        )
        raise
