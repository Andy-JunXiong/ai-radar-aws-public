from __future__ import annotations

from typing import Any


def _text_parts(signal: dict[str, Any]) -> tuple[str, str, list[str], list[str]]:
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
    title = str(signal.get("title") or "").lower()
    summary = str(signal.get("summary") or "").lower()
    tags = [str(item).strip().lower() for item in (metadata.get("tags") or []) if str(item).strip()]
    keywords = [
        str(item).strip().lower()
        for item in (metadata.get("matched_keywords") or [])
        if str(item).strip()
    ]
    return title, summary, tags, keywords


def classify_agent_signal(signal: dict[str, Any]) -> dict[str, Any]:
    title, summary, tags, keywords = _text_parts(signal)
    haystack = " ".join([title, summary, *tags, *keywords]).strip()

    subtopic = "agent_app"

    infra_terms = [
        "runtime",
        "orchestration",
        "infrastructure",
        "observability",
        "debug",
        "evaluation",
        "monitoring",
        "deployment",
        "workflow",
        "platform",
    ]
    framework_terms = [
        "framework",
        "sdk",
        "toolkit",
        "library",
        "multi agent",
        "multi-agent",
        "agent framework",
    ]

    if any(term in haystack for term in infra_terms):
        subtopic = "agent_infra"
    elif any(term in haystack for term in framework_terms):
        subtopic = "agent_framework"

    enriched = dict(signal)
    enriched["agent_subtopic"] = subtopic

    metadata = dict(signal.get("metadata") or {}) if isinstance(signal.get("metadata"), dict) else {}
    metadata["agent_subtopic"] = subtopic
    enriched["metadata"] = metadata
    return enriched


def classify_agent_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not signals:
        return []
    return [classify_agent_signal(signal) for signal in signals]
