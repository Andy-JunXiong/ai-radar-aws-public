import os
from dataclasses import dataclass


PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

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
    "reason": TIER_3,
    "summary": TIER_3,
    "strategy": TIER_3,
}

MANUAL_TEXT_TASKS = {"manual_text", "manual_text_session"}
CLAUDE_ANALYSIS_TASKS = {"structure", "insight"}


@dataclass(frozen=True)
class ModelRoute:
    task_type: str
    tier: str
    provider: str
    model: str
    source: str


def _normalized_task_type(task_type: str | None) -> str:
    normalized = str(task_type or "").strip().lower()
    return normalized or DEFAULT_TASK_TYPE


def _default_provider_by_tier() -> dict[str, str]:
    return {
        TIER_1: os.getenv("MODEL_ROUTER_TIER1_PROVIDER", PROVIDER_OPENAI).strip().lower(),
        TIER_2: os.getenv("MODEL_ROUTER_TIER2_PROVIDER", PROVIDER_OPENAI).strip().lower(),
        TIER_3: os.getenv("MODEL_ROUTER_TIER3_PROVIDER", PROVIDER_OPENAI).strip().lower(),
    }


def _default_model_for_provider(provider: str, *, tier: str) -> str:
    openai_fallback = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    anthropic_fallback = os.getenv(
        "ANTHROPIC_MODEL",
        os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
    )

    if provider == PROVIDER_ANTHROPIC:
        return os.getenv(
            {
                TIER_1: "MODEL_ROUTER_TIER1_MODEL",
                TIER_2: "MODEL_ROUTER_TIER2_MODEL",
                TIER_3: "MODEL_ROUTER_TIER3_MODEL",
            }[tier],
            anthropic_fallback,
        )

    return os.getenv(
        {
            TIER_1: "MODEL_ROUTER_TIER1_MODEL",
            TIER_2: "MODEL_ROUTER_TIER2_MODEL",
            TIER_3: "MODEL_ROUTER_TIER3_MODEL",
        }[tier],
        openai_fallback,
    )


def _default_provider_for_task(task_type: str, tier: str) -> str:
    if task_type in MANUAL_TEXT_TASKS:
        return (
            os.getenv("MODEL_ROUTER_MANUAL_TEXT_PROVIDER", "").strip().lower()
            or PROVIDER_OPENAI
        )
    if task_type in CLAUDE_ANALYSIS_TASKS:
        return (
            os.getenv("MODEL_ROUTER_ANALYSIS_PROVIDER", "").strip().lower()
            or PROVIDER_OPENAI
        )
    return _default_provider_by_tier()[tier]


def route_task(task_type: str | None) -> ModelRoute:
    normalized_task = _normalized_task_type(task_type)
    tier = TASK_TIER_MAP.get(normalized_task, TASK_TIER_MAP[DEFAULT_TASK_TYPE])
    provider = _default_provider_for_task(normalized_task, tier)
    model = _default_model_for_provider(provider, tier=tier)
    env_override_present = any(
        os.getenv(key)
        for key in [
            "MODEL_ROUTER_TIER1_PROVIDER",
            "MODEL_ROUTER_TIER2_PROVIDER",
            "MODEL_ROUTER_TIER3_PROVIDER",
            "MODEL_ROUTER_TIER1_MODEL",
            "MODEL_ROUTER_TIER2_MODEL",
            "MODEL_ROUTER_TIER3_MODEL",
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
    )


def resolve_model(task_type: str | None, default_model: str | None = None) -> str:
    route = route_task(task_type)
    if route.model:
        return route.model
    return str(default_model or "").strip()


def router_startup_diagnostics() -> dict[str, object]:
    sample_tasks = [
        "extract",
        "structure",
        "insight",
        "manual_text_session",
        "strategy",
    ]
    routes = {
        task: {
            "tier": route_task(task).tier,
            "provider": route_task(task).provider,
            "model": route_task(task).model,
        }
        for task in sample_tasks
    }
    return {"routes": routes}
