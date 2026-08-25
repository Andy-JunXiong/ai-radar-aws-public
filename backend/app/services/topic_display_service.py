from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


_CANONICAL_TOPIC_LABELS = {
    "agent ux": "Agent UX",
    "ai agent": "AI Agents",
    "ai agents": "AI Agents",
    "ai hardware": "AI Hardware",
    "ai infrastructure": "AI Infrastructure",
    "ai model": "AI Models",
    "ai models": "AI Models",
    "ai policy": "AI Policy",
    "cost control": "Cost Control",
    "developer tooling": "Developer Tooling",
    "evaluation": "Evaluation",
    "evaluations": "Evaluation",
    "infrastructure": "Infrastructure",
    "memory": "Memory",
    "monitoring": "Monitoring",
    "retrieval": "Retrieval",
    "security": "Security",
    "workflow": "Workflow",
    "workflows": "Workflow",
}

_TOKEN_LABELS = {
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "chatgpt": "ChatGPT",
    "github": "GitHub",
    "gpu": "GPU",
    "llm": "LLM",
    "mcp": "MCP",
    "openai": "OpenAI",
    "rag": "RAG",
    "ui": "UI",
    "ux": "UX",
}


def _clean_topic_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    return " ".join(normalized.split())


def _topic_key(value: Any) -> str:
    cleaned = _clean_topic_text(value)
    return re.sub(r"[\s_-]+", " ", cleaned).strip().casefold()


def _format_topic_token(token: str) -> str:
    token_key = token.casefold()
    if token_key in _TOKEN_LABELS:
        return _TOKEN_LABELS[token_key]
    if any(char.islower() for char in token) and any(char.isupper() for char in token):
        return token
    return token_key.capitalize()


def canonicalize_topic_label(value: Any) -> str:
    """Return a deterministic display label without changing stored topic data."""

    cleaned = _clean_topic_text(value)
    key = _topic_key(cleaned)
    if not key:
        return ""
    if key in _CANONICAL_TOPIC_LABELS:
        return _CANONICAL_TOPIC_LABELS[key]

    display_tokens = re.sub(r"[\s_-]+", " ", cleaned).strip().split()
    return " ".join(_format_topic_token(token) for token in display_tokens)


def canonicalize_topic_labels(values: Iterable[Any] | None) -> list[str]:
    """Canonicalize and deduplicate topic labels for read-only display/grouping."""

    labels: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        label = canonicalize_topic_label(value)
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels
