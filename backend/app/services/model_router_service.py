import os
from dataclasses import dataclass


PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_PERPLEXITY = "perplexity"

DEFAULT_ANTHROPIC_WEB_SEARCH_MODEL = "claude-opus-4-8"
DEFAULT_ANTHROPIC_WEB_SEARCH_MAX_USES = 3

TIER_1 = "tier_1_fast"
TIER_2 = "tier_2_structured"
TIER_3 = "tier_3_strategic"

DEFAULT_TASK_TYPE = "structure"

TASK_TIER_MAP = {
    "extract": TIER_1,
    "translate": TIER_1,
    "classify": TIER_1,
    "normalize": TIER_2,
    "structure": TIER_2,
    "insight": TIER_2,
    "manual_text": TIER_2,
    "manual_text_session": TIER_2,
    "vision": TIER_2,
    "manual_image": TIER_2,
    "manual_image_session": TIER_2,
    "reason": TIER_3,
    "summary": TIER_3,
    "strategy": TIER_3,
}

VISION_TASKS = {"vision", "manual_image", "manual_image_session"}
MANUAL_TEXT_TASKS = {"manual_text", "manual_text_session"}
ANALYSIS_TASKS = {"insight", "reason", "summary", "strategy"}


@dataclass(frozen=True)
class ModelRoute:
    task_type: str
    tier: str
    provider: str
    model: str
    source: str
    web_search_enabled: bool = False
    web_search_max_uses: int = DEFAULT_ANTHROPIC_WEB_SEARCH_MAX_USES


def _is_model_compatible(provider: str, model: str | None) -> bool:
    normalized_provider = str(provider or "").strip().lower()
    normalized_model = str(model or "").strip().lower()

    if not normalized_model:
        return False

    if normalized_provider == PROVIDER_ANTHROPIC:
        return normalized_model.startswith("claude")

    if normalized_provider == PROVIDER_PERPLEXITY:
        return normalized_model.startswith("sonar") or "sonar" in normalized_model

    if normalized_provider == PROVIDER_OPENAI:
        incompatible_prefixes = ("claude", "sonar")
        return not normalized_model.startswith(incompatible_prefixes)

    return True


def _first_compatible_model(provider: str, candidates: list[str | None], fallback: str) -> str:
    for candidate in candidates:
        if _is_model_compatible(provider, candidate):
            return str(candidate).strip()
    return fallback


def _env_int(key: str, default: int) -> int:
    try:
        parsed = int(str(os.getenv(key, "")).strip())
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _anthropic_model_supports_web_search(model: str | None) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith(("claude-opus-4", "claude-sonnet-4"))


def _anthropic_web_search_model(model: str) -> str:
    configured = str(os.getenv("ANTHROPIC_WEB_SEARCH_MODEL", "")).strip()
    if configured:
        if _anthropic_model_supports_web_search(configured):
            return configured
        raise ValueError(
            "ANTHROPIC_WEB_SEARCH_MODEL must be a Claude 4 Opus or Sonnet model."
        )
    if _anthropic_model_supports_web_search(model):
        return model
    return DEFAULT_ANTHROPIC_WEB_SEARCH_MODEL


def _web_search_max_uses(max_uses: int | None = None) -> int:
    if max_uses is not None:
        return max_uses if max_uses > 0 else DEFAULT_ANTHROPIC_WEB_SEARCH_MAX_USES
    return _env_int("ANTHROPIC_WEB_SEARCH_MAX_USES", DEFAULT_ANTHROPIC_WEB_SEARCH_MAX_USES)


def _normalized_task_type(task_type: str | None) -> str:
    normalized = str(task_type or "").strip().lower()
    return normalized or DEFAULT_TASK_TYPE


def _tier_provider_env_key(tier: str) -> str:
    return {
        TIER_1: "MODEL_ROUTER_TIER1_PROVIDER",
        TIER_2: "MODEL_ROUTER_TIER2_PROVIDER",
        TIER_3: "MODEL_ROUTER_TIER3_PROVIDER",
    }[tier]


def _tier_model_env_key(tier: str) -> str:
    return {
        TIER_1: "MODEL_ROUTER_TIER1_MODEL",
        TIER_2: "MODEL_ROUTER_TIER2_MODEL",
        TIER_3: "MODEL_ROUTER_TIER3_MODEL",
    }[tier]


def _provider_specific_tier_model_env_key(provider: str, tier: str) -> str | None:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == PROVIDER_OPENAI:
        prefix = "MODEL_ROUTER_OPENAI"
    elif normalized_provider == PROVIDER_ANTHROPIC:
        prefix = "MODEL_ROUTER_ANTHROPIC"
    elif normalized_provider == PROVIDER_PERPLEXITY:
        prefix = "MODEL_ROUTER_PERPLEXITY"
    else:
        return None
    return {
        TIER_1: f"{prefix}_TIER1_MODEL",
        TIER_2: f"{prefix}_TIER2_MODEL",
        TIER_3: f"{prefix}_TIER3_MODEL",
    }[tier]


def _provider_candidates(task_type: str, tier: str) -> list[tuple[str, str | None]]:
    if task_type in VISION_TASKS:
        return [
            ("MODEL_ROUTER_VISION_PROVIDER", os.getenv("MODEL_ROUTER_VISION_PROVIDER")),
            (
                "availability_fallback",
                PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI,
            ),
        ]
    if task_type in MANUAL_TEXT_TASKS:
        return [
            (
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER",
                os.getenv("MODEL_ROUTER_MANUAL_TEXT_PROVIDER"),
            ),
            (
                "availability_fallback",
                PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI,
            ),
        ]
    if task_type in ANALYSIS_TASKS:
        return [
            ("MODEL_ROUTER_ANALYSIS_PROVIDER", os.getenv("MODEL_ROUTER_ANALYSIS_PROVIDER")),
            (
                "availability_fallback",
                PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI,
            ),
        ]
    if tier == TIER_3:
        return [
            ("MODEL_ROUTER_TIER3_PROVIDER", os.getenv("MODEL_ROUTER_TIER3_PROVIDER")),
            (
                "availability_fallback",
                PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI,
            ),
        ]
    return [
        (_tier_provider_env_key(tier), os.getenv(_tier_provider_env_key(tier))),
        (
            "tier_default",
            PROVIDER_OPENAI if tier == TIER_1 else os.getenv(_tier_provider_env_key(tier), PROVIDER_OPENAI),
        ),
    ]


def _model_candidates(provider: str, task_type: str, tier: str) -> list[tuple[str, str | None]]:
    if task_type in VISION_TASKS:
        if provider == PROVIDER_ANTHROPIC:
            return [
                ("MODEL_ROUTER_ANTHROPIC_VISION_MODEL", os.getenv("MODEL_ROUTER_ANTHROPIC_VISION_MODEL")),
                ("MODEL_ROUTER_VISION_MODEL", os.getenv("MODEL_ROUTER_VISION_MODEL")),
                ("ANTHROPIC_MODEL", os.getenv("ANTHROPIC_MODEL")),
                ("CLAUDE_MODEL", os.getenv("CLAUDE_MODEL")),
            ]
        return [
            ("MODEL_ROUTER_OPENAI_VISION_MODEL", os.getenv("MODEL_ROUTER_OPENAI_VISION_MODEL")),
            ("MODEL_ROUTER_VISION_MODEL", os.getenv("MODEL_ROUTER_VISION_MODEL")),
            ("OPENAI_MODEL", os.getenv("OPENAI_MODEL")),
            ("LLM_MODEL", os.getenv("LLM_MODEL")),
        ]

    provider_tier_key = _provider_specific_tier_model_env_key(provider, tier)
    candidates: list[tuple[str, str | None]] = []
    if provider_tier_key:
        candidates.append((provider_tier_key, os.getenv(provider_tier_key)))
    candidates.append((_tier_model_env_key(tier), os.getenv(_tier_model_env_key(tier))))

    if provider == PROVIDER_ANTHROPIC:
        candidates.extend(
            [
                ("ANTHROPIC_MODEL", os.getenv("ANTHROPIC_MODEL")),
                ("CLAUDE_MODEL", os.getenv("CLAUDE_MODEL")),
            ]
        )
    elif provider == PROVIDER_PERPLEXITY:
        candidates.extend(
            [
                ("PERPLEXITY_MODEL", os.getenv("PERPLEXITY_MODEL")),
                ("LLM_MODEL", os.getenv("LLM_MODEL")),
            ]
        )
    else:
        candidates.extend(
            [
                ("OPENAI_MODEL", os.getenv("OPENAI_MODEL")),
                ("LLM_MODEL", os.getenv("LLM_MODEL")),
            ]
        )
    return candidates


def _default_provider_for_task(task_type: str, tier: str) -> str:
    if task_type in VISION_TASKS:
        return (
            os.getenv("MODEL_ROUTER_VISION_PROVIDER", "").strip().lower()
            or (PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI)
        )
    if task_type in MANUAL_TEXT_TASKS:
        return (
            os.getenv("MODEL_ROUTER_MANUAL_TEXT_PROVIDER", "").strip().lower()
            or (PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI)
        )
    if task_type in ANALYSIS_TASKS:
        return (
            os.getenv("MODEL_ROUTER_ANALYSIS_PROVIDER", "").strip().lower()
            or (PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI)
        )
    if tier == TIER_3:
        return (
            os.getenv("MODEL_ROUTER_TIER3_PROVIDER", "").strip().lower()
            or (PROVIDER_ANTHROPIC if os.getenv("ANTHROPIC_API_KEY") else PROVIDER_OPENAI)
        )
    if tier == TIER_1:
        return os.getenv("MODEL_ROUTER_TIER1_PROVIDER", PROVIDER_OPENAI).strip().lower()
    return os.getenv("MODEL_ROUTER_TIER2_PROVIDER", PROVIDER_OPENAI).strip().lower()


def _default_model_for_provider(provider: str, *, task_type: str, tier: str) -> str:
    openai_fallback = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    anthropic_fallback = os.getenv(
        "ANTHROPIC_MODEL",
        os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
    )
    perplexity_fallback = os.getenv(
        "PERPLEXITY_MODEL",
        os.getenv("LLM_MODEL", "llama-3.1-sonar-small-128k-online"),
    )

    if task_type in VISION_TASKS:
        if provider == PROVIDER_ANTHROPIC:
            return _first_compatible_model(
                provider,
                [
                    os.getenv("MODEL_ROUTER_ANTHROPIC_VISION_MODEL"),
                    os.getenv("MODEL_ROUTER_VISION_MODEL"),
                    os.getenv("ANTHROPIC_MODEL"),
                    os.getenv("CLAUDE_MODEL"),
                ],
                anthropic_fallback,
            )
        return _first_compatible_model(
            provider,
            [
                os.getenv("MODEL_ROUTER_OPENAI_VISION_MODEL"),
                os.getenv("MODEL_ROUTER_VISION_MODEL"),
                os.getenv("OPENAI_MODEL"),
                os.getenv("LLM_MODEL"),
            ],
            openai_fallback,
        )

    if provider == PROVIDER_ANTHROPIC:
        tier_key = {
            TIER_1: "MODEL_ROUTER_TIER1_MODEL",
            TIER_2: "MODEL_ROUTER_TIER2_MODEL",
            TIER_3: "MODEL_ROUTER_TIER3_MODEL",
        }[tier]
        provider_tier_key = {
            TIER_1: "MODEL_ROUTER_ANTHROPIC_TIER1_MODEL",
            TIER_2: "MODEL_ROUTER_ANTHROPIC_TIER2_MODEL",
            TIER_3: "MODEL_ROUTER_ANTHROPIC_TIER3_MODEL",
        }[tier]
        return _first_compatible_model(
            provider,
            [
                os.getenv(provider_tier_key),
                os.getenv(tier_key),
                os.getenv("ANTHROPIC_MODEL"),
                os.getenv("CLAUDE_MODEL"),
            ],
            anthropic_fallback,
        )

    if provider == PROVIDER_PERPLEXITY:
        tier_key = {
            TIER_1: "MODEL_ROUTER_TIER1_MODEL",
            TIER_2: "MODEL_ROUTER_TIER2_MODEL",
            TIER_3: "MODEL_ROUTER_TIER3_MODEL",
        }[tier]
        provider_tier_key = {
            TIER_1: "MODEL_ROUTER_PERPLEXITY_TIER1_MODEL",
            TIER_2: "MODEL_ROUTER_PERPLEXITY_TIER2_MODEL",
            TIER_3: "MODEL_ROUTER_PERPLEXITY_TIER3_MODEL",
        }[tier]
        return _first_compatible_model(
            provider,
            [
                os.getenv(provider_tier_key),
                os.getenv(tier_key),
                os.getenv("PERPLEXITY_MODEL"),
                os.getenv("LLM_MODEL"),
            ],
            perplexity_fallback,
        )

    return _first_compatible_model(
        provider,
        [
            os.getenv(
                {
                    TIER_1: "MODEL_ROUTER_OPENAI_TIER1_MODEL",
                    TIER_2: "MODEL_ROUTER_OPENAI_TIER2_MODEL",
                    TIER_3: "MODEL_ROUTER_OPENAI_TIER3_MODEL",
                }[tier]
            ),
            os.getenv(
                {
                    TIER_1: "MODEL_ROUTER_TIER1_MODEL",
                    TIER_2: "MODEL_ROUTER_TIER2_MODEL",
                    TIER_3: "MODEL_ROUTER_TIER3_MODEL",
                }[tier]
            ),
            os.getenv("OPENAI_MODEL"),
            os.getenv("LLM_MODEL"),
        ],
        openai_fallback,
    )


def route_task(
    task_type: str | None,
    provider_override: str | None = None,
    *,
    web_search_enabled: bool = False,
    web_search_max_uses: int | None = None,
) -> ModelRoute:
    normalized_task = _normalized_task_type(task_type)
    tier = TASK_TIER_MAP.get(normalized_task, TASK_TIER_MAP[DEFAULT_TASK_TYPE])
    provider = (provider_override or _default_provider_for_task(normalized_task, tier)).strip().lower()
    model = _default_model_for_provider(provider, task_type=normalized_task, tier=tier)
    if web_search_enabled and provider == PROVIDER_ANTHROPIC:
        model = _anthropic_web_search_model(model)
    env_override_present = any(
        os.getenv(key)
        for key in [
            "MODEL_ROUTER_TIER1_PROVIDER",
            "MODEL_ROUTER_TIER2_PROVIDER",
            "MODEL_ROUTER_TIER3_PROVIDER",
            "MODEL_ROUTER_TIER1_MODEL",
            "MODEL_ROUTER_TIER2_MODEL",
            "MODEL_ROUTER_TIER3_MODEL",
            "MODEL_ROUTER_VISION_PROVIDER",
            "MODEL_ROUTER_VISION_MODEL",
            "MODEL_ROUTER_MANUAL_TEXT_PROVIDER",
            "MODEL_ROUTER_ANALYSIS_PROVIDER",
        ]
    )
    return ModelRoute(
        task_type=normalized_task,
        tier=tier,
        provider=provider,
        model=model,
        source="env_router" if env_override_present else "default_router",
        web_search_enabled=bool(web_search_enabled and provider == PROVIDER_ANTHROPIC),
        web_search_max_uses=_web_search_max_uses(web_search_max_uses),
    )


def router_startup_diagnostics() -> dict[str, object]:
    sample_tasks = [
        "extract",
        "structure",
        "manual_text_session",
        "manual_image_session",
        "insight",
        "strategy",
    ]
    routes = {}
    route_details = {}
    for task in sample_tasks:
        route = route_task(task)
        provider_candidates = _provider_candidates(route.task_type, route.tier)
        model_candidates = _model_candidates(route.provider, route.task_type, route.tier)
        selected_provider_source = next(
            (
                source
                for source, value in provider_candidates
                if str(value or "").strip().lower() == route.provider
            ),
            "fallback",
        )
        selected_model_source = next(
            (
                source
                for source, value in model_candidates
                if str(value or "").strip() == route.model
                and _is_model_compatible(route.provider, value)
            ),
            "fallback",
        )

        routes[task] = {
            "tier": route.tier,
            "provider": route.provider,
            "model": route.model,
        }
        route_details[task] = {
            "tier": route.tier,
            "provider": route.provider,
            "model": route.model,
            "source": route.source,
            "provider_resolution": {
                "selected": route.provider,
                "selected_from": selected_provider_source,
                "candidates": [
                    {
                        "source": source,
                        "value": value,
                        "used": str(value or "").strip().lower() == route.provider,
                    }
                    for source, value in provider_candidates
                ],
            },
            "model_resolution": {
                "selected": route.model,
                "selected_from": selected_model_source,
                "candidates": [
                    {
                        "source": source,
                        "value": value,
                        "compatible": _is_model_compatible(route.provider, value),
                        "used": (
                            str(value or "").strip() == route.model
                            and _is_model_compatible(route.provider, value)
                        ),
                    }
                    for source, value in model_candidates
                ],
            },
        }

    warnings: list[str] = []
    if os.getenv("ANTHROPIC_API_KEY") and not (
        os.getenv("ANTHROPIC_MODEL") or os.getenv("CLAUDE_MODEL")
    ):
        warnings.append(
            "ANTHROPIC_API_KEY is set but ANTHROPIC_MODEL/CLAUDE_MODEL is not configured; "
            "Claude-first tasks will fall back to a generic default model name that may not be available on this account."
        )

    warned_pairs: set[tuple[str, str]] = set()
    for task, detail in route_details.items():
        provider = str(detail.get("provider") or "")
        resolution = detail.get("model_resolution") or {}
        for candidate in resolution.get("candidates") or []:
            source = str(candidate.get("source") or "")
            value = str(candidate.get("value") or "").strip()
            compatible = bool(candidate.get("compatible"))
            if not source or not value or compatible:
                continue
            warning_key = (source, value)
            if warning_key in warned_pairs:
                continue
            warned_pairs.add(warning_key)
            warnings.append(
                f"{source}={value} is incompatible with provider '{provider}' and is being ignored. "
                f"Example affected task: {task}."
            )

    return {
        "routes": routes,
        "route_details": route_details,
        "warnings": warnings,
    }
