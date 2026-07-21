from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from app.services.context_strategy_service import apply_policy_to_prompts
from app.services.execution_policy_service import (
    ExecutionPolicy,
    PolicyInput,
    PolicyResult,
    decide_execution_policy,
)
from app.services.output_validation_service import (
    ValidationResult,
    count_citations,
    mark_output_uncertain,
    validate_output,
)
from app.services.policy_metrics_service import record_policy_event


def _cost_guard_active() -> bool:
    value = str(os.getenv("EXECUTION_POLICY_DISABLE_ESCALATION", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _critical_variant(policy_result: PolicyResult) -> PolicyResult:
    critical_policy = ExecutionPolicy(
        mode="critical",
        rag_enabled=True,
        citation_required=True,
        verification_required=True,
        max_context_chunks=max(policy_result.selected_policy.max_context_chunks, 8),
        model_tier="strong",
        fallback_allowed=False,
        output_mode="verified",
        reason=f"{policy_result.selected_policy.reason}_escalated",
        validation_rules=["required_fields", "citation_presence", "claim_verification"],
    )
    effective = policy_result.effective_task_type
    if effective in {"structure", "insight", "summary", "workspace_chat"}:
        effective = "reason"
    return PolicyResult(
        selected_policy=critical_policy,
        final_mode="critical",
        effective_task_type=effective,
        context_strategy="max_grounded_context",
        escalation_used=True,
    )


def _metadata_payload(
    *,
    policy_result: PolicyResult,
    validation: ValidationResult,
    provider: str,
    model: str,
    fallback_used: bool,
    escalation_used: bool,
) -> dict[str, Any]:
    validation_passed = not validation.failures
    return {
        "selected_policy": policy_result.selected_policy.to_dict(),
        "execution_policy": {
            "mode": policy_result.selected_policy.mode,
            "citation_required": policy_result.selected_policy.citation_required,
            "verification_required": policy_result.selected_policy.verification_required,
            "model_tier": policy_result.selected_policy.model_tier,
            "fallback_count": int(bool(fallback_used)) + int(bool(escalation_used)),
            "policy_reason": policy_result.selected_policy.reason,
        },
        "execution": {
            "mode": policy_result.selected_policy.mode,
            "final_mode": policy_result.final_mode,
            "validation_passed": validation_passed,
        },
        "final_mode": policy_result.final_mode,
        "effective_task_type": policy_result.effective_task_type,
        "context_strategy": policy_result.context_strategy,
        "fallback_count": int(bool(fallback_used)) + int(bool(escalation_used)),
        "citation_count": validation.citation_count,
        "citation_validation_passed": validation.citation_validation_passed,
        "verification_status": validation.verification_status,
        "verification_passed": validation.verification_passed,
        "unsupported_claims": validation.unsupported_claims,
        "notes": validation.notes,
        "validation_failures": validation.failures,
        "fallback_used": fallback_used,
        "escalation_used": escalation_used,
        "provider_used": provider,
        "model_used": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _should_mark_output_uncertain(
    *,
    policy_input: PolicyInput,
    policy_result: PolicyResult,
    validation: ValidationResult,
) -> bool:
    if not policy_result.selected_policy.verification_required:
        return False
    if validation.verification_status == "basic_verified":
        return False

    # Manual uploaded text/PDF analysis is cognitive analysis over user-supplied
    # material, not an evidence-path claim write. Keep uncertainty in policy
    # metadata instead of rewriting every JSON field with an Uncertain prefix.
    if str(policy_input.task_type or "").strip().lower() in {
        "manual_text",
        "manual_text_session",
    }:
        return False

    return True


def _manual_source_labels(metadata: dict[str, Any] | None) -> list[str]:
    raw_labels = (metadata or {}).get("source_labels")
    if not isinstance(raw_labels, list):
        return []

    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_labels:
        label = " ".join(str(item or "").split()).strip()[:160]
        if not label or label in seen:
            continue
        labels.append(label)
        seen.add(label)
        if len(labels) >= 3:
            break
    return labels


def _ensure_manual_text_source_citation(
    payload: dict[str, Any],
    *,
    metadata: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    labels = _manual_source_labels(metadata)
    if not labels or count_citations(payload) > 0:
        return payload, False

    citations = " ".join(f"[Source: {label}]" for label in labels)
    target_keys = [
        "summary",
        "synthesized_insight",
        "why_it_matters",
        "relevance_to_projects",
        "relevance_to_career",
    ]
    updated = dict(payload)
    for key in target_keys:
        value = updated.get(key)
        if isinstance(value, str) and value.strip():
            updated[key] = f"{value.rstrip()} {citations}"
            return updated, True
    return payload, False


def execute_policy_text_json(
    *,
    policy_input: PolicyInput,
    system_prompt: str,
    user_prompt: str,
    metadata: dict[str, Any] | None,
    executor: Callable[[str, str, str], tuple[dict[str, Any], Any]],
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    policy_result = decide_execution_policy(policy_input)
    context_available = bool((metadata or {}).get("source_count") or 0)

    patched_system_prompt, patched_user_prompt = apply_policy_to_prompts(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        policy=policy_result.selected_policy,
        metadata=metadata,
    )
    payload, route = executor(
        policy_result.effective_task_type,
        patched_system_prompt,
        patched_user_prompt,
    )
    source_citation_injected = False
    if str(policy_input.task_type or "").strip().lower() in {"manual_text", "manual_text_session"}:
        payload, source_citation_injected = _ensure_manual_text_source_citation(
            payload,
            metadata=metadata,
        )
    validation = validate_output(
        policy=policy_result.selected_policy,
        output=payload,
        context_available=context_available,
    )
    escalation_used = False

    if (
        not validation.passed
        and policy_result.final_mode == "guarded"
        and policy_result.selected_policy.fallback_allowed
        and not _cost_guard_active()
    ):
        escalated = _critical_variant(policy_result)
        patched_system_prompt, patched_user_prompt = apply_policy_to_prompts(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            policy=escalated.selected_policy,
            metadata=metadata,
        )
        payload, route = executor(
            escalated.effective_task_type,
            patched_system_prompt,
            patched_user_prompt,
        )
        if str(policy_input.task_type or "").strip().lower() in {"manual_text", "manual_text_session"}:
            payload, source_citation_injected = _ensure_manual_text_source_citation(
                payload,
                metadata=metadata,
            )
        validation = validate_output(
            policy=escalated.selected_policy,
            output=payload,
            context_available=context_available,
        )
        policy_result = escalated
        escalation_used = True

    if _should_mark_output_uncertain(
        policy_input=policy_input,
        policy_result=policy_result,
        validation=validation,
    ):
        payload = mark_output_uncertain(payload)

    policy_metadata = _metadata_payload(
        policy_result=policy_result,
        validation=validation,
        provider=getattr(route, "provider", ""),
        model=getattr(route, "model", ""),
        fallback_used=False,
        escalation_used=escalation_used,
    )
    if source_citation_injected:
        policy_metadata["source_citation_injected"] = True
    record_policy_event(
        {
            "task_type": policy_input.task_type,
            "mode": policy_result.final_mode,
            "provider": getattr(route, "provider", ""),
            "model": getattr(route, "model", ""),
            "citation_count": validation.citation_count,
            "citation_validation_passed": validation.citation_validation_passed,
            "verification_status": validation.verification_status,
            "verification_passed": validation.verification_passed,
            "validation_failed": not validation.passed,
            "escalation_used": escalation_used,
        }
    )
    return payload, route, policy_metadata


def execute_policy_vision_json(
    *,
    policy_input: PolicyInput,
    prompt_text: str,
    metadata: dict[str, Any] | None,
    executor: Callable[[str, str], tuple[dict[str, Any], Any]],
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    policy_result = decide_execution_policy(policy_input)
    context_available = bool((metadata or {}).get("source_count") or 0)

    patched_prompt, _ = apply_policy_to_prompts(
        system_prompt=prompt_text,
        user_prompt="",
        policy=policy_result.selected_policy,
        metadata=metadata,
    )
    payload, route = executor(policy_result.effective_task_type, patched_prompt)
    validation = validate_output(
        policy=policy_result.selected_policy,
        output=payload,
        context_available=context_available,
    )
    escalation_used = False

    if (
        not validation.passed
        and policy_result.final_mode == "guarded"
        and policy_result.selected_policy.fallback_allowed
        and not _cost_guard_active()
    ):
        escalated = _critical_variant(policy_result)
        patched_prompt, _ = apply_policy_to_prompts(
            system_prompt=prompt_text,
            user_prompt="",
            policy=escalated.selected_policy,
            metadata=metadata,
        )
        payload, route = executor(escalated.effective_task_type, patched_prompt)
        validation = validate_output(
            policy=escalated.selected_policy,
            output=payload,
            context_available=context_available,
        )
        policy_result = escalated
        escalation_used = True

    if _should_mark_output_uncertain(
        policy_input=policy_input,
        policy_result=policy_result,
        validation=validation,
    ):
        payload = mark_output_uncertain(payload)

    policy_metadata = _metadata_payload(
        policy_result=policy_result,
        validation=validation,
        provider=getattr(route, "provider", ""),
        model=getattr(route, "model", ""),
        fallback_used=False,
        escalation_used=escalation_used,
    )
    record_policy_event(
        {
            "task_type": policy_input.task_type,
            "mode": policy_result.final_mode,
            "provider": getattr(route, "provider", ""),
            "model": getattr(route, "model", ""),
            "citation_count": validation.citation_count,
            "citation_validation_passed": validation.citation_validation_passed,
            "verification_status": validation.verification_status,
            "verification_passed": validation.verification_passed,
            "validation_failed": not validation.passed,
            "escalation_used": escalation_used,
        }
    )
    return payload, route, policy_metadata


def execute_policy_text(
    *,
    policy_input: PolicyInput,
    system_prompt: str,
    user_prompt: str,
    metadata: dict[str, Any] | None,
    executor: Callable[[str, str, str], tuple[str, Any]],
) -> tuple[str, Any, dict[str, Any]]:
    policy_result = decide_execution_policy(policy_input)
    context_available = bool((metadata or {}).get("source_count") or 0)

    patched_system_prompt, patched_user_prompt = apply_policy_to_prompts(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        policy=policy_result.selected_policy,
        metadata=metadata,
    )
    text, route = executor(
        policy_result.effective_task_type,
        patched_system_prompt,
        patched_user_prompt,
    )
    validation = validate_output(
        policy=policy_result.selected_policy,
        output=text,
        context_available=context_available,
    )
    escalation_used = False

    if (
        not validation.passed
        and policy_result.final_mode == "guarded"
        and policy_result.selected_policy.fallback_allowed
        and not _cost_guard_active()
    ):
        escalated = _critical_variant(policy_result)
        patched_system_prompt, patched_user_prompt = apply_policy_to_prompts(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            policy=escalated.selected_policy,
            metadata=metadata,
        )
        text, route = executor(
            escalated.effective_task_type,
            patched_system_prompt,
            patched_user_prompt,
        )
        validation = validate_output(
            policy=escalated.selected_policy,
            output=text,
            context_available=context_available,
        )
        policy_result = escalated
        escalation_used = True

    if policy_result.selected_policy.verification_required and validation.verification_status != "basic_verified":
        text = str(mark_output_uncertain(text))

    policy_metadata = _metadata_payload(
        policy_result=policy_result,
        validation=validation,
        provider=getattr(route, "provider", ""),
        model=getattr(route, "model", ""),
        fallback_used=False,
        escalation_used=escalation_used,
    )
    record_policy_event(
        {
            "task_type": policy_input.task_type,
            "mode": policy_result.final_mode,
            "provider": getattr(route, "provider", ""),
            "model": getattr(route, "model", ""),
            "citation_count": validation.citation_count,
            "citation_validation_passed": validation.citation_validation_passed,
            "verification_status": validation.verification_status,
            "verification_passed": validation.verification_passed,
            "validation_failed": not validation.passed,
            "escalation_used": escalation_used,
        }
    )
    return text, route, policy_metadata
