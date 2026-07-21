import os
import time
from typing import Any, Callable

import anthropic
from openai import OpenAI

from app.services.llm_json_service import parse_model_json
from app.services.metrics_event_service import record_llm_call
from app.services.model_router_service import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    PROVIDER_PERPLEXITY,
    ModelRoute,
    route_task,
)
from app.services.model_router_telemetry_service import record_route_event

ANTHROPIC_WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


def _should_log_route() -> bool:
    value = str(os.getenv("MODEL_ROUTER_LOGGING", "1")).strip().lower()
    return value not in {"0", "false", "off", "no"}


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


def _anthropic_model_supports_temperature(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return True

    temperature_unsupported_prefixes = (
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-haiku-4",
    )
    return not normalized.startswith(temperature_unsupported_prefixes)


def _anthropic_message_kwargs(
    *,
    model: str,
    temperature: float,
    web_search_enabled: bool = False,
    web_search_max_uses: int = 3,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "model": model,
        **kwargs,
    }
    if _anthropic_model_supports_temperature(model):
        payload["temperature"] = temperature
    if web_search_enabled:
        payload["tools"] = [
            {
                "type": ANTHROPIC_WEB_SEARCH_TOOL_TYPE,
                "name": "web_search",
                "max_uses": web_search_max_uses,
            }
        ]
    return payload


def _content_value(block: Any, key: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _plain_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if hasattr(value, "__dict__"):
        return {
            str(key): _plain_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def parse_anthropic_response_content(response: Any, *, web_search_enabled: bool = False) -> dict[str, Any]:
    text_parts: list[str] = []
    server_tool_uses: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    search_results: list[dict[str, Any]] = []

    for block in getattr(response, "content", []) or []:
        block_type = str(_content_value(block, "type", "") or "")
        block_text = _content_value(block, "text", "")
        if block_text:
            text_parts.append(str(block_text))

        if block_type == "server_tool_use":
            server_tool_uses.append(
                {
                    "source": "web_search" if _content_value(block, "name") == "web_search" else "server_tool",
                    "id": _content_value(block, "id"),
                    "name": _content_value(block, "name"),
                    "input": _plain_value(_content_value(block, "input", {})),
                }
            )

        for citation in _content_value(block, "citations", []) or []:
            normalized_citation = _plain_value(citation)
            if isinstance(normalized_citation, dict):
                normalized_citation = {"source": "web_search", **normalized_citation}
            citations.append(normalized_citation)

        if block_type == "web_search_tool_result":
            content = _content_value(block, "content", [])
            content_items = content if isinstance(content, list) else [content]
            for item in content_items:
                normalized_item = _plain_value(item)
                if isinstance(normalized_item, dict):
                    normalized_item = {"source": "web_search", **normalized_item}
                search_results.append(normalized_item)

    return {
        "text": "\n".join(part for part in text_parts if part).strip(),
        "server_tool_uses": server_tool_uses if web_search_enabled else [],
        "citations": citations if web_search_enabled else [],
        "search_results": search_results if web_search_enabled else [],
    }


def _record_llm_metric(
    *,
    route: ModelRoute,
    mode: str,
    started_at: float,
    success: bool,
    error_type: str | None = None,
    fallback_used: bool = False,
    response: Any = None,
    json_validation_passed: bool | None = None,
    json_repair_used: bool = False,
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
                "fallback_used": fallback_used,
                "retry_count": 0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": None,
                "json_validation_passed": json_validation_passed,
                "json_repair_used": json_repair_used,
            }
        )
    except Exception as exc:
        print(f"[metrics] failed to record LLM call: {exc}")


def _record_route_event(
    *,
    route: ModelRoute,
    mode: str,
    outcome: str,
    fallback_used: bool = False,
    error_type: str | None = None,
) -> None:
    if not _should_log_route():
        return
    print(
        "[router] "
        f"task={route.task_type} "
        f"tier={route.tier} "
        f"provider={route.provider} "
        f"model={route.model} "
        f"source={route.source} "
        f"mode={mode} "
        f"outcome={outcome} "
        f"fallback={str(fallback_used).lower()}"
    )
    record_route_event(
        route=route,
        mode=mode,
        outcome=outcome,
        fallback_used=fallback_used,
        error_type=error_type,
    )


def execute_text_json_task(
    *,
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1800,
    provider_override: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    fallback_used: bool = False,
    web_search_enabled: bool = False,
    web_search_max_uses: int | None = None,
    raw_output_callback: Callable[[str, ModelRoute], None] | None = None,
) -> tuple[dict[str, Any], ModelRoute]:
    route = route_task(
        task_type,
        provider_override=provider_override,
        web_search_enabled=web_search_enabled,
        web_search_max_uses=web_search_max_uses,
    )
    started_at = time.perf_counter()

    try:
        if route.provider == PROVIDER_OPENAI:
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found")
            client = OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                **_openai_chat_kwargs(
                    model=route.model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            )
            raw_output = (response.choices[0].message.content or "").strip()
            if raw_output_callback is not None:
                raw_output_callback(raw_output, route)
            parsed = parse_model_json(raw_output)
            _record_llm_metric(
                route=route,
                mode="text_json",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=True,
            )
            _record_route_event(
                route=route,
                mode="text_json",
                outcome="success",
                fallback_used=fallback_used,
            )
            return parsed, route

        if route.provider == PROVIDER_ANTHROPIC:
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                **_anthropic_message_kwargs(
                    model=route.model,
                    temperature=temperature,
                    web_search_enabled=route.web_search_enabled,
                    web_search_max_uses=route.web_search_max_uses,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        }
                    ],
                )
            )
            parsed_content = parse_anthropic_response_content(
                response,
                web_search_enabled=route.web_search_enabled,
            )
            raw_output = parsed_content["text"]
            if raw_output_callback is not None:
                raw_output_callback(raw_output, route)
            parsed = parse_model_json(raw_output)
            _record_llm_metric(
                route=route,
                mode="text_json",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=True,
            )
            _record_route_event(
                route=route,
                mode="text_json",
                outcome="success",
                fallback_used=fallback_used,
            )
            return parsed, route

        raise ValueError(f"Unsupported provider: {route.provider}")
    except Exception as exc:
        _record_llm_metric(
            route=route,
            mode="text_json",
            started_at=started_at,
            success=False,
            error_type=exc.__class__.__name__,
            fallback_used=fallback_used,
            json_validation_passed=False,
        )
        _record_route_event(
            route=route,
            mode="text_json",
            outcome="failure",
            fallback_used=fallback_used,
            error_type=exc.__class__.__name__,
        )
        raise


def execute_text_task(
    *,
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1000,
    provider_override: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    perplexity_api_key: str | None = None,
    fallback_used: bool = False,
    web_search_enabled: bool = False,
    web_search_max_uses: int | None = None,
) -> tuple[str, ModelRoute]:
    route = route_task(
        task_type,
        provider_override=provider_override,
        web_search_enabled=web_search_enabled,
        web_search_max_uses=web_search_max_uses,
    )
    started_at = time.perf_counter()

    try:
        if route.provider == PROVIDER_OPENAI:
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found")
            client = OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                **_openai_chat_kwargs(
                    model=route.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            )
            reply = (response.choices[0].message.content or "").strip()
            _record_llm_metric(
                route=route,
                mode="text",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=None,
            )
            _record_route_event(
                route=route,
                mode="text",
                outcome="success",
                fallback_used=fallback_used,
            )
            return reply, route

        if route.provider == PROVIDER_PERPLEXITY:
            if not perplexity_api_key:
                raise ValueError("PERPLEXITY_API_KEY not found")
            client = OpenAI(
                api_key=perplexity_api_key,
                base_url="https://api.perplexity.ai",
            )
            response = client.chat.completions.create(
                model=route.model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            reply = (response.choices[0].message.content or "").strip()
            _record_llm_metric(
                route=route,
                mode="text",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=None,
            )
            _record_route_event(
                route=route,
                mode="text",
                outcome="success",
                fallback_used=fallback_used,
            )
            return reply, route

        if route.provider == PROVIDER_ANTHROPIC:
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                **_anthropic_message_kwargs(
                    model=route.model,
                    temperature=temperature,
                    web_search_enabled=route.web_search_enabled,
                    web_search_max_uses=route.web_search_max_uses,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        }
                    ],
                )
            )
            parsed_content = parse_anthropic_response_content(
                response,
                web_search_enabled=route.web_search_enabled,
            )
            reply = parsed_content["text"]
            _record_llm_metric(
                route=route,
                mode="text",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=None,
            )
            _record_route_event(
                route=route,
                mode="text",
                outcome="success",
                fallback_used=fallback_used,
            )
            return reply, route

        raise ValueError(f"Unsupported provider: {route.provider}")
    except Exception as exc:
        _record_llm_metric(
            route=route,
            mode="text",
            started_at=started_at,
            success=False,
            error_type=exc.__class__.__name__,
            fallback_used=fallback_used,
            json_validation_passed=None,
        )
        _record_route_event(
            route=route,
            mode="text",
            outcome="failure",
            fallback_used=fallback_used,
            error_type=exc.__class__.__name__,
        )
        raise


def execute_vision_json_task(
    *,
    task_type: str,
    prompt_text: str,
    attachments: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 1800,
    provider_override: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    fallback_used: bool = False,
    web_search_enabled: bool = False,
    web_search_max_uses: int | None = None,
) -> tuple[dict[str, Any], ModelRoute]:
    route = route_task(
        task_type,
        provider_override=provider_override,
        web_search_enabled=web_search_enabled,
        web_search_max_uses=web_search_max_uses,
    )
    started_at = time.perf_counter()

    try:
        if route.provider == PROVIDER_OPENAI:
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found")
            client = OpenAI(api_key=openai_api_key)
            content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
            for item in attachments:
                content_parts.append(
                    {
                        "type": "text",
                        "text": f"Image filename: {item['filename']}",
                    }
                )
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{item['media_type']};base64,{item['image_b64']}",
                        },
                    }
                )

            response = client.chat.completions.create(
                **_openai_chat_kwargs(
                    model=route.model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": content_parts}],
                )
            )
            raw_output = (response.choices[0].message.content or "").strip()
            parsed = parse_model_json(raw_output)
            _record_llm_metric(
                route=route,
                mode="vision_json",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=True,
            )
            _record_route_event(
                route=route,
                mode="vision_json",
                outcome="success",
                fallback_used=fallback_used,
            )
            return parsed, route

        if route.provider == PROVIDER_ANTHROPIC:
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            content_blocks: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
            for item in attachments:
                content_blocks.append(
                    {
                        "type": "text",
                        "text": f"Image filename: {item['filename']}",
                    }
                )
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": item["media_type"],
                            "data": item["image_b64"],
                        },
                    }
                )

            response = client.messages.create(
                **_anthropic_message_kwargs(
                    model=route.model,
                    temperature=temperature,
                    web_search_enabled=route.web_search_enabled,
                    web_search_max_uses=route.web_search_max_uses,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": content_blocks}],
                )
            )
            parsed_content = parse_anthropic_response_content(
                response,
                web_search_enabled=route.web_search_enabled,
            )
            raw_output = parsed_content["text"]
            parsed = parse_model_json(raw_output)
            _record_llm_metric(
                route=route,
                mode="vision_json",
                started_at=started_at,
                success=True,
                fallback_used=fallback_used,
                response=response,
                json_validation_passed=True,
            )
            _record_route_event(
                route=route,
                mode="vision_json",
                outcome="success",
                fallback_used=fallback_used,
            )
            return parsed, route

        raise ValueError(f"Unsupported provider: {route.provider}")
    except Exception as exc:
        _record_llm_metric(
            route=route,
            mode="vision_json",
            started_at=started_at,
            success=False,
            error_type=exc.__class__.__name__,
            fallback_used=fallback_used,
            json_validation_passed=False,
        )
        _record_route_event(
            route=route,
            mode="vision_json",
            outcome="failure",
            fallback_used=fallback_used,
            error_type=exc.__class__.__name__,
        )
        raise
