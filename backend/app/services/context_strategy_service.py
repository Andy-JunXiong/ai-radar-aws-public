from __future__ import annotations

from typing import Any

from app.services.execution_policy_service import ExecutionPolicy


def apply_policy_to_prompts(
    *,
    system_prompt: str,
    user_prompt: str,
    policy: ExecutionPolicy,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, str]:
    meta = metadata or {}
    source_count = int(meta.get("source_count") or 0)
    context_label = str(meta.get("context_label") or "provided_context")
    web_search_enabled = bool(meta.get("web_search_enabled"))

    policy_lines = [
        "EXECUTION POLICY",
        f"- mode: {policy.mode}",
        f"- output mode: {policy.output_mode}",
        f"- context strategy: {context_label}",
    ]

    if policy.citation_required and source_count > 0 and web_search_enabled:
        policy_lines.extend(
            [
                "- Use provided context as AI Radar evidence.",
                "- For current external facts, comparable products, or source checks, use the available web search tool.",
                "- Label AI Radar evidence with [Evidence: ...] and web-derived facts with [Web search: source/title/url].",
                "- Do not claim that external search is unavailable in this mode.",
            ]
        )
    elif policy.citation_required and source_count > 0:
        policy_lines.extend(
            [
                "- Use only the provided context as evidence.",
                "- Add short inline citations in this format: [Evidence: ...].",
                "- Every factual or source-dependent claim should be supported by evidence when possible.",
            ]
        )

    if policy.verification_required and web_search_enabled:
        policy_lines.extend(
            [
                "- Before finalizing, check whether strong AI Radar claims are supported by provided context and current external claims are supported by web search sources.",
                "- If a claim is not clearly supported by either provided context or web search sources, mark it as 'Uncertain:' instead of stating it as fact.",
                "- Do not invent evidence, citations, or search results.",
            ]
        )
    elif policy.verification_required:
        policy_lines.extend(
            [
                "- Before finalizing, check whether each strong claim is supported by provided context.",
                "- If a claim is not clearly supported, mark it as 'Uncertain:' instead of stating it as fact.",
                "- Do not invent evidence or citations.",
            ]
        )

    if policy.mode == "fast":
        policy_lines.extend(
            [
                "- Keep the answer lean.",
                "- Do not add unnecessary verification or evidence formatting.",
            ]
        )

    patched_system_prompt = f"{system_prompt.strip()}\n\n" + "\n".join(policy_lines)

    if policy.rag_enabled and source_count > 0:
        search_note = (
            " Web search is also available for current external facts; keep web search sources separate from AI Radar evidence."
            if web_search_enabled
            else ""
        )
        patched_user_prompt = (
            f"{user_prompt.strip()}\n\n"
            f"Context availability: {source_count} source block(s) were supplied. "
            f"Preserve source grounding when making factual statements.{search_note}"
        )
    else:
        patched_user_prompt = user_prompt.strip()

    return patched_system_prompt, patched_user_prompt
