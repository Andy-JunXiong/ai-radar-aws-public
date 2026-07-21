from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ExecutionMode = Literal["fast", "guarded", "critical"]
ModelTier = Literal["cheap", "standard", "strong"]
OutputMode = Literal["draft", "grounded", "verified"]


@dataclass(frozen=True)
class PolicyInput:
    task_type: str
    query: str | None = None
    user_visible: bool = False
    importance_score: float | None = None
    requires_traceability: bool = False
    source_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: ExecutionMode
    rag_enabled: bool
    citation_required: bool
    verification_required: bool
    max_context_chunks: int
    model_tier: ModelTier
    fallback_allowed: bool
    output_mode: OutputMode
    reason: str
    validation_rules: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyResult:
    selected_policy: ExecutionPolicy
    final_mode: ExecutionMode
    effective_task_type: str
    context_strategy: str
    escalation_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["selected_policy"] = self.selected_policy.to_dict()
        return payload


FAST_TASK_TYPES = {
    "json_repair",
    "reflection_polish",
    "translate",
    "extract",
    "classify",
    "low_score_signal_summary",
}

GUARDED_TASK_TYPES = {
    "structure",
    "normalize",
    "radar_summary",
    "workspace_answer",
    "manual_analysis",
    "high_score_signal_insight",
    "manual_text",
    "manual_text_session",
    "manual_image",
    "manual_image_session",
    "workspace_chat",
    "insight",
    "summary",
}

CRITICAL_TASK_TYPES = {
    "strategy",
    "reason",
    "strategic_intelligence",
    "decision_support",
    "workspace_recommendation",
}


def _as_score(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric <= 1:
        numeric *= 100
    return numeric


def _contains_recommendation_request(query: str | None) -> bool:
    text = str(query or "").lower()
    markers = [
        "should i",
        "what should",
        "recommend",
        "what to do",
        "next step",
        "decision",
        "apply this",
        "worth doing",
    ]
    return any(marker in text for marker in markers)


def _resolve_mode(policy_input: PolicyInput) -> tuple[ExecutionMode, str]:
    task_type = str(policy_input.task_type or "").strip().lower()
    importance_score = _as_score(policy_input.importance_score)
    metadata = policy_input.metadata or {}

    if (
        policy_input.requires_traceability
        or metadata.get("strategic_output")
        or metadata.get("high_risk")
        or metadata.get("decision_support")
        or task_type in CRITICAL_TASK_TYPES
        or (task_type == "trend_synthesis" and importance_score is not None and importance_score >= 70)
        or (task_type == "workspace_chat" and _contains_recommendation_request(policy_input.query))
    ):
        return "critical", "traceability_or_recommendation_required"

    if (
        task_type in GUARDED_TASK_TYPES
        or task_type == "trend_synthesis"
        or policy_input.user_visible
        or (importance_score is not None and importance_score >= 70)
    ):
        return "guarded", "user_visible_or_medium_risk_output"

    return "fast", "low_risk_or_internal_output"


def _validation_rules_for_mode(mode: ExecutionMode) -> list[str]:
    rules = ["required_fields"]
    if mode in {"guarded", "critical"}:
        rules.append("citation_presence")
    if mode == "critical":
        rules.append("claim_verification")
    return rules


def _effective_task_type(task_type: str, mode: ExecutionMode) -> str:
    normalized = str(task_type or "").strip().lower() or "structure"
    if mode == "fast":
        return {
            "insight": "structure",
            "summary": "structure",
            "reason": "summary",
            "strategy": "summary",
            "workspace_chat": "summary",
        }.get(normalized, normalized)
    if mode == "critical":
        return {
            "insight": "reason",
            "summary": "reason",
            "workspace_chat": "reason",
        }.get(normalized, normalized)
    return normalized


def decide_execution_policy(policy_input: PolicyInput) -> PolicyResult:
    mode, reason = _resolve_mode(policy_input)

    if mode == "fast":
        policy = ExecutionPolicy(
            mode="fast",
            rag_enabled=False,
            citation_required=False,
            verification_required=False,
            max_context_chunks=2,
            model_tier="cheap",
            fallback_allowed=False,
            output_mode="draft",
            reason=reason,
            validation_rules=_validation_rules_for_mode("fast"),
        )
        return PolicyResult(
            selected_policy=policy,
            final_mode="fast",
            effective_task_type=_effective_task_type(policy_input.task_type, "fast"),
            context_strategy="minimal_context",
        )

    source_count = policy_input.source_count or 0
    if mode == "guarded":
        policy = ExecutionPolicy(
            mode="guarded",
            rag_enabled=source_count > 0,
            citation_required=source_count > 0,
            verification_required=False,
            max_context_chunks=6,
            model_tier="standard",
            fallback_allowed=True,
            output_mode="grounded",
            reason=reason,
            validation_rules=_validation_rules_for_mode("guarded"),
        )
        return PolicyResult(
            selected_policy=policy,
            final_mode="guarded",
            effective_task_type=_effective_task_type(policy_input.task_type, "guarded"),
            context_strategy="grounded_context" if source_count > 0 else "minimal_context",
        )

    policy = ExecutionPolicy(
        mode="critical",
        rag_enabled=True,
        citation_required=True,
        verification_required=True,
        max_context_chunks=10,
        model_tier="strong",
        fallback_allowed=True,
        output_mode="verified",
        reason=reason,
        validation_rules=_validation_rules_for_mode("critical"),
    )
    return PolicyResult(
        selected_policy=policy,
        final_mode="critical",
        effective_task_type=_effective_task_type(policy_input.task_type, "critical"),
        context_strategy="max_grounded_context",
    )
