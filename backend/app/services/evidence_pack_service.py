from __future__ import annotations

from typing import Any

from app.services.canonical_scalar_resolver_service import (
    build_canonical_scalar_resolution,
    scalar_resolution_text,
)


MAX_SOURCE_EXCERPT_CHARS = 1200
SOURCE_EXCERPT_FIELDS = (
    "source_excerpt",
    "full_text",
    "article_body",
    "raw_content",
    "raw_text",
    "content",
)
SOURCE_LIMITS_PRESENT = "limits_present"
SOURCE_LIMITS_ABSENT_UNKNOWN = "limits_absent_unknown"
SOURCE_LIMITS_NOT_APPLICABLE = "limits_not_applicable"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _source_limits_not_applicable(signal: dict[str, Any]) -> bool:
    status = _clean_text(signal.get("source_stated_limits_status")).lower()
    if status == SOURCE_LIMITS_NOT_APPLICABLE:
        return True
    explicit = signal.get("source_stated_limits_not_applicable")
    if isinstance(explicit, bool):
        return explicit
    if isinstance(explicit, str):
        return explicit.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_source_stated_limits(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        items: list[Any] = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []

    limits: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            text = _clean_text(item)
            if text:
                limits.append(
                    {
                        "text": text,
                        "source_field": "source_stated_limits",
                        "source_span": None,
                        "limit_type": None,
                    }
                )
            continue
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text") or item.get("limit") or item.get("content"))
        if not text:
            continue
        limits.append(
            {
                "text": text,
                "source_field": _clean_text(item.get("source_field")) or "source_stated_limits",
                "source_span": item.get("source_span") if isinstance(item.get("source_span"), dict) else None,
                "limit_type": _clean_text(item.get("limit_type")) or None,
            }
        )
    return limits


def _normalize_source_stated_confidence(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        raw_text = _clean_text(value)
        return {"raw_text": raw_text, "normalized_label": None} if raw_text else {}
    if not isinstance(value, dict):
        return {}
    raw_text = _clean_text(value.get("raw_text") or value.get("text") or value.get("confidence"))
    normalized_label = _clean_text(value.get("normalized_label")) or None
    if not raw_text and not normalized_label:
        return {}
    return {
        "raw_text": raw_text,
        "normalized_label": normalized_label,
    }


def _source_stated_metadata(signal: dict[str, Any]) -> dict[str, Any]:
    limits = _normalize_source_stated_limits(signal.get("source_stated_limits"))
    confidence = _normalize_source_stated_confidence(signal.get("source_stated_confidence"))
    if _source_limits_not_applicable(signal):
        limits_status = SOURCE_LIMITS_NOT_APPLICABLE
    elif limits:
        limits_status = SOURCE_LIMITS_PRESENT
    else:
        limits_status = SOURCE_LIMITS_ABSENT_UNKNOWN

    metadata: dict[str, Any] = {
        "source_stated_limits_status": limits_status,
        "source_stated_limits": limits,
    }
    if confidence:
        metadata["source_stated_confidence"] = confidence
    return metadata


def _compact_project_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    compacted: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        compact = {
            "project_id": _clean_text(item.get("project_id") or item.get("id")),
            "project_name": _clean_text(item.get("project_name") or item.get("name")),
            "relationship": _clean_text(item.get("relationship")),
        }
        if any(compact.values()):
            compacted.append(compact)
    return compacted


def _infer_summary_provenance(signal: dict[str, Any], summary: str) -> str:
    explicit = _clean_text(signal.get("summary_provenance"))
    if explicit:
        return explicit.lower()

    if not summary:
        return "unknown"

    source = _clean_text(signal.get("source")).lower()
    if source == "manual":
        return "manual_user_written"

    # Current auto-signal records do not yet consistently preserve raw excerpt provenance.
    # Treat them as collector-level extracted summaries by default instead of pretending
    # they are verified source excerpts.
    if source:
        return "collector_extracted"

    return "unknown"


def _reliability_hint(source_type: str) -> str:
    normalized = _clean_text(source_type).lower()
    if normalized in {"manual", "aws_ml", "research"}:
        return "high"
    if normalized in {"github", "hn", "hacker_news", "product_hunt", "rss"}:
        return "medium"
    return "unknown"


def _bounded_source_excerpt(signal: dict[str, Any], summary: str) -> tuple[str, str]:
    normalized_summary = _clean_text(summary).lower()

    for field in SOURCE_EXCERPT_FIELDS:
        value = _clean_text(signal.get(field))
        if not value:
            continue

        if field == "content" and value.lower() == normalized_summary:
            continue

        return value[:MAX_SOURCE_EXCERPT_CHARS], field

    return "", ""


def _build_evidence_item(
    *,
    source_id: str,
    source_type: str,
    source_field: str,
    content: str,
    kind: str,
    provenance: str,
    source_url: str,
    timestamp: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_id = f"ev_{source_id or 'unknown'}_{source_field}".replace(" ", "_")
    traceable = provenance in {
        "source_excerpt",
        "structured_metadata",
        "collector_extracted",
        "manual_user_written",
        "canonical_api_observed",
    } and bool(content)

    return {
        "evidence_id": evidence_id,
        "kind": kind,
        "source_type": source_type or "unknown",
        "source_url": source_url,
        "source_id": source_id,
        "source_field": source_field,
        "content": content,
        "provenance": provenance,
        "traceable": traceable,
        "reliability_hint": _reliability_hint(source_type),
        "timestamp": timestamp,
        "metadata": metadata or {},
    }


def build_signal_evidence_pack(signal: dict[str, Any]) -> dict[str, Any]:
    signal_id = _clean_text(signal.get("signal_id") or signal.get("id"))
    title = _clean_text(signal.get("title"))
    summary = _clean_text(signal.get("summary"))
    source = _clean_text(signal.get("source"))
    source_url = _clean_text(
        signal.get("url") or signal.get("link") or signal.get("source_url")
    )
    published_at = _clean_text(signal.get("published_at"))
    collected_at = _clean_text(signal.get("collected_at"))
    topic = _clean_text(signal.get("topic") or "General AI")
    insight_status = _clean_text(signal.get("insight_status"))
    priority = _clean_text(signal.get("subscription_topic_priority"))
    summary_provenance = _infer_summary_provenance(signal, summary)
    source_excerpt, source_excerpt_field = _bounded_source_excerpt(signal, summary)
    source_metadata = _source_stated_metadata(signal)
    scalar_resolution = build_canonical_scalar_resolution(signal)
    scalar_resolution_summary = scalar_resolution_text(scalar_resolution)

    observed_facts: list[str] = []
    if title:
        observed_facts.append(f"Title observed: {title}")
    if summary:
        observed_facts.append(f"Summary observed: {summary[:280]}")
    if source_excerpt:
        observed_facts.append(
            f"Source excerpt observed from {source_excerpt_field}: {source_excerpt[:280]}"
        )
    if source:
        observed_facts.append(f"Source observed: {source}")
    if topic:
        observed_facts.append(f"Topic observed: {topic}")
    if published_at:
        observed_facts.append(f"Published at observed: {published_at}")
    if collected_at:
        observed_facts.append(f"Collected at observed: {collected_at}")
    if insight_status:
        observed_facts.append(f"Insight status observed: {insight_status}")

    score = signal.get("score")
    if score is not None and str(score).strip() != "":
        observed_facts.append(f"Score observed: {score}")
    if scalar_resolution_summary:
        observed_facts.append(f"Canonical scalar observed: {scalar_resolution_summary}")

    project_links = _compact_project_links(signal.get("subscription_project_links"))
    if project_links:
        observed_facts.append(
            f"Project links observed: {len(project_links)} candidate links."
        )

    evidence_items: list[dict[str, Any]] = []
    timestamp = published_at or collected_at

    if title:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source,
                source_field="title",
                content=title,
                kind="structured_metadata",
                provenance="structured_metadata",
                source_url=source_url,
                timestamp=timestamp,
                metadata=source_metadata,
            )
        )

    if summary:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source,
                source_field="summary",
                content=summary[:500],
                kind=(
                    "primary_excerpt"
                    if summary_provenance == "source_excerpt"
                    else (
                        "collector_excerpt"
                        if summary_provenance == "collector_extracted"
                        else (
                            "context_note"
                            if summary_provenance == "manual_user_written"
                            else "interpreted_summary"
                        )
                    )
                ),
                provenance=summary_provenance,
                source_url=source_url,
                timestamp=timestamp,
                metadata=source_metadata,
            )
        )

    if source_excerpt:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source,
                source_field=source_excerpt_field,
                content=source_excerpt,
                kind="source_excerpt",
                provenance="source_excerpt",
                source_url=source_url,
                timestamp=timestamp,
                metadata=source_metadata,
            )
        )

    if source:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source,
                source_field="source",
                content=source,
                kind="structured_metadata",
                provenance="structured_metadata",
                source_url=source_url,
                timestamp=timestamp,
            )
        )

    if source_url:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source,
                source_field="source_url",
                content=source_url,
                kind="structured_metadata",
                provenance="structured_metadata",
                source_url=source_url,
                timestamp=timestamp,
            )
        )

    if scalar_resolution_summary:
        evidence_items.append(
            _build_evidence_item(
                source_id=signal_id,
                source_type=source or "github",
                source_field="canonical_scalars",
                content=scalar_resolution_summary,
                kind="canonical_scalar_resolution",
                provenance="canonical_api_observed",
                source_url=source_url,
                timestamp=timestamp,
                metadata={
                    "provenance_tier": "canonical_api_observed",
                    "canonical_scalar_resolution": scalar_resolution,
                },
            )
        )

    return {
        "evidence_version": "v1",
        "source_signal_id": signal_id,
        "source_type": source or "unknown",
        "source_title": title,
        "source_url": source_url,
        "published_at": published_at,
        "collection_timestamp": collected_at,
        "summary_excerpt": summary[:500],
        "summary_provenance": summary_provenance,
        "observed_facts": observed_facts,
        "evidence_items": evidence_items,
        "structured_context": {
            "topic": topic,
            "score": score,
            "insight_status": insight_status,
            "subscription_topic_priority": priority,
            "project_links": project_links,
        },
    }
