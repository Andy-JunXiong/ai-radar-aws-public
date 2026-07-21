from __future__ import annotations

import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from collections import Counter

from app.reflection.github_client import GitHubReflectionClient
from app.reflection.frontmatter_parser import _extract_frontmatter
from app.reflection.index_builder import load_reflection_index, load_sync_state, sync_reflections
from app.services.reflection_relationship_index_service import (
    build_reflection_relationship_index,
    get_reflection_relationships,
)
from app.services.s3_reader import load_signals
import yaml


TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
MANUAL_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "manual_uploads" / "sessions"
BACKFILL_DRAFTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reflections" / "backfill_drafts"
GENERIC_TOPIC_STOPWORDS = {
    "about",
    "after",
    "agent",
    "agents",
    "ai",
    "and",
    "been",
    "better",
    "build",
    "from",
    "general",
    "have",
    "into",
    "more",
    "news",
    "that",
    "than",
    "their",
    "this",
    "what",
    "with",
}
TOPIC_ALIASES = {
    "ai agents": {"agent", "agents", "agentic", "multiagent", "multi", "orchestration"},
    "ai agent": {"agent", "agents", "agentic"},
    "llm": {"llm", "llms", "model", "models", "language"},
    "memory": {"memory", "context", "retrieval"},
    "friction": {"friction", "pain", "problem", "issue", "bug"},
}


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _tokenize(value: str) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    return {token for token in TOKEN_SPLIT_RE.split(normalized) if len(token) >= 2}


def _expand_topic_tokens(topic: str) -> set[str]:
    tokens = _tokenize(topic)
    alias_tokens = set()
    normalized_topic = _normalize_text(topic)
    for key, values in TOPIC_ALIASES.items():
        if key in normalized_topic or normalized_topic in key:
            alias_tokens.update(values)
    return tokens | alias_tokens


def _extract_signal_topics(signal: dict[str, Any]) -> list[str]:
    title = _normalize_text(signal.get("title") or signal.get("signal_title"))
    summary = _normalize_text(signal.get("summary") or signal.get("signal_summary"))
    topic = _normalize_text(signal.get("topic"))
    signal_type = _normalize_text(signal.get("signal_type"))

    combined_text = " ".join(part for part in [title, summary, topic, signal_type] if part)
    combined_tokens = _tokenize(combined_text)

    topics: list[str] = []

    if topic and topic not in {"general ai", "general"}:
        topics.append(topic)

    if signal_type == "friction" or signal.get("friction_score") is not None:
        topics.append("friction")

    if signal.get("agent_watch_score") is not None:
        topics.append("ai agents")

    for label, aliases in TOPIC_ALIASES.items():
        if combined_tokens & aliases:
            topics.append(label)

    keyword_tokens = [
        token
        for token in _tokenize(f"{title} {summary}")
        if len(token) >= 4 and token not in GENERIC_TOPIC_STOPWORDS
    ]
    topics.extend(keyword_tokens[:6])

    deduped: list[str] = []
    seen: set[str] = set()
    for item in topics:
        normalized = _normalize_text(item)
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)

    return deduped[:10]


def _extract_candidate_sentences(content: str) -> list[str]:
    text = content.replace("\r", "\n")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("---"):
            continue
        lines.append(line)

    joined = " ".join(lines)
    raw_sentences = re.split(r"(?<=[.!?])\s+", joined)
    sentences = [sentence.strip(" -\t") for sentence in raw_sentences if len(sentence.strip()) >= 20]
    return sentences


def _build_reflection_backfill_suggestion(metadata: dict[str, Any], content: str) -> dict[str, Any]:
    sentences = _extract_candidate_sentences(content)
    title = str(metadata.get("title") or metadata.get("id") or "Untitled reflection")
    existing_key_claims = metadata.get("key_claims") or []
    missing_fields = []

    if not metadata.get("thesis"):
        missing_fields.append("thesis")
    if not existing_key_claims:
        missing_fields.append("key_claims")
    if not metadata.get("final_takeaway"):
        missing_fields.append("final_takeaway")

    thesis = metadata.get("thesis") or (sentences[0] if sentences else "")
    remaining = [sentence for sentence in sentences if sentence != thesis]

    suggested_claims = list(existing_key_claims)
    if not suggested_claims:
        suggested_claims = remaining[:3]

    counterpoints = metadata.get("counterpoints") or [
        sentence
        for sentence in remaining
        if any(marker in sentence.lower() for marker in ["however", "but", "although", "on the other hand"])
    ][:2]

    open_questions = metadata.get("open_questions") or [
        sentence for sentence in sentences if sentence.endswith("?")
    ][:3]

    final_takeaway = metadata.get("final_takeaway") or (sentences[-1] if len(sentences) >= 2 else thesis)

    suggestion = {
        "id": metadata.get("id"),
        "title": title,
        "missing_fields": missing_fields,
        "suggested_thesis": thesis,
        "suggested_key_claims": suggested_claims,
        "suggested_counterpoints": counterpoints,
        "suggested_open_questions": open_questions,
        "suggested_final_takeaway": final_takeaway,
    }
    suggestion["suggested_frontmatter_patch"] = _build_frontmatter_patch(suggestion)
    return suggestion


def _yaml_list_block(items: list[str], indent: str = "") -> str:
    if not items:
        return "[]"
    return "\n".join(f"{indent}- {item}" for item in items)


def _build_frontmatter_patch(suggestion: dict[str, Any]) -> str:
    lines: list[str] = []

    if "thesis" in suggestion.get("missing_fields", []) and suggestion.get("suggested_thesis"):
        lines.append(f"thesis: {suggestion['suggested_thesis']}")
    if "key_claims" in suggestion.get("missing_fields", []) and suggestion.get("suggested_key_claims"):
        lines.append("key_claims:")
        lines.append(_yaml_list_block(list(suggestion["suggested_key_claims"]), indent="  "))
    if suggestion.get("suggested_counterpoints"):
        lines.append("counterpoints:")
        lines.append(_yaml_list_block(list(suggestion["suggested_counterpoints"]), indent="  "))
    if suggestion.get("suggested_open_questions"):
        lines.append("open_questions:")
        lines.append(_yaml_list_block(list(suggestion["suggested_open_questions"]), indent="  "))
    if "final_takeaway" in suggestion.get("missing_fields", []) and suggestion.get("suggested_final_takeaway"):
        lines.append(f"final_takeaway: {suggestion['suggested_final_takeaway']}")

    return "\n".join(lines).strip()


def _load_manual_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    if not MANUAL_SESSIONS_DIR.exists():
        return sessions

    for file_path in sorted(MANUAL_SESSIONS_DIR.glob("*.json"), reverse=True):
        if file_path.name == "index.json":
            continue
        try:
            data = load_json(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            sessions.append(data)
    return sessions


def load_json(raw: str) -> Any:
    import json

    return json.loads(raw)


def list_reflections(
    *,
    q: str = "",
    tags: list[str] | None = None,
    source: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    index = load_reflection_index()
    items = index.reflections

    query = q.strip().lower()
    wanted_tags = [tag.strip().lower() for tag in (tags or []) if tag.strip()]
    wanted_source = source.strip().lower()

    filtered = []
    for item in items:
        item_tags = [tag.lower() for tag in item.tags]
        haystack = " ".join([item.title.lower(), " ".join(item_tags), item.id.lower()])

        if query and query not in haystack:
            continue
        if wanted_source and item.source.value.lower() != wanted_source:
            continue
        if wanted_tags and not all(tag in item_tags for tag in wanted_tags):
            continue
        filtered.append(item)

    filtered = filtered[: max(1, min(limit, 500))]
    return {
        "schema_version": index.schema_version,
        "last_updated": index.last_updated.isoformat(),
        "total_count": len(filtered),
        "reflections": [item.model_dump(mode="json") for item in filtered],
    }


def find_related_reflections(
    *,
    q: str = "",
    topics: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    index = load_reflection_index()
    query = q.strip().lower()
    normalized_topics = [topic.strip().lower() for topic in (topics or []) if topic.strip()]
    query_tokens = _tokenize(query)
    topic_token_map = {topic: _expand_topic_tokens(topic) for topic in normalized_topics}

    results = []
    for item in index.reflections:
        item_tags = [tag.lower() for tag in item.tags]
        haystack = " ".join([item.title.lower(), item.id.lower(), " ".join(item_tags)])
        reflection_tokens = _tokenize(item.title) | _tokenize(item.id)
        for tag in item_tags:
            reflection_tokens.update(_expand_topic_tokens(tag))

        matched_topics = []
        matched_terms: set[str] = set()
        for topic, expanded_tokens in topic_token_map.items():
            token_overlap = expanded_tokens & reflection_tokens
            if topic in haystack or token_overlap:
                matched_topics.append(topic)
                matched_terms.update(token_overlap)

        score = 0.0

        if query:
            query_overlap = query_tokens & reflection_tokens
            if query in haystack:
                score += 0.45
                matched_terms.update(query_tokens)
            elif query_overlap:
                score += min(0.35, 0.12 * len(query_overlap))
                matched_terms.update(query_overlap)
            else:
                continue

        if normalized_topics:
            score += min(0.4, 0.18 * len(matched_topics))
            if not matched_topics and not query:
                continue

            token_overlap_total = sum(
                len(expanded_tokens & reflection_tokens)
                for expanded_tokens in topic_token_map.values()
            )
            if token_overlap_total:
                score += min(0.2, 0.04 * token_overlap_total)

        if score <= 0:
            continue

        results.append(
            {
                **item.model_dump(mode="json"),
                "match_score": round(min(1.0, score), 2),
                "matched_topics": matched_topics,
                "matched_terms": sorted(matched_terms),
            }
        )

    results.sort(
        key=lambda item: (float(item.get("match_score") or 0.0), str(item.get("timestamp") or "")),
        reverse=True,
    )

    capped = results[: max(1, min(limit, 20))]
    return {
        "total_count": len(capped),
        "reflections": capped,
    }


def find_related_reflections_for_signal(
    signal: dict[str, Any],
    *,
    limit: int = 5,
) -> dict[str, Any]:
    signal_topics = _extract_signal_topics(signal)
    result = find_related_reflections(topics=signal_topics, limit=limit)
    return {
        **result,
        "signal_topics": signal_topics,
    }


def get_reflection_full(reflection_id: str) -> dict[str, Any] | None:
    index = load_reflection_index()
    target = next((item for item in index.reflections if item.id == reflection_id), None)
    if target is None:
        return None

    client = GitHubReflectionClient()
    content = client.get_file_content(target.github_path)
    schema_json: Any | None = None
    raw_html_content: str | None = None

    if getattr(target, "content_format", "markdown") == "json_html":
        if target.schema_path:
            try:
                schema_raw = client.get_file_content(target.schema_path)
                schema_json = json.loads(schema_raw)
                content = _render_json_content(schema_json)
            except Exception:
                content = content
        if target.raw_html_path:
            try:
                raw_html_content = client.get_file_content(target.raw_html_path)
            except Exception:
                raw_html_content = None

    return {
        "metadata": target.model_dump(mode="json"),
        "content": content,
        "schema_json": schema_json,
        "raw_html_content": raw_html_content,
    }


def _render_json_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, indent=2)

    sections: list[str] = []
    title = payload.get("title") or payload.get("reflection_title") or payload.get("session_title")
    if title:
        sections.append(f"# {title}")

    field_groups = [
        ("Summary", ["summary", "compressed_core", "compressedCore", "overview"]),
        ("Thesis", ["thesis"]),
        ("Key Claims", ["key_claims", "keyClaims", "claims"]),
        ("Counterpoints", ["counterpoints"]),
        ("Open Questions", ["open_questions", "openQuestions", "questions"]),
        ("Final Takeaway", ["final_takeaway", "finalTakeaway", "takeaway"]),
    ]

    for label, keys in field_groups:
        value = None
        for key in keys:
            if payload.get(key) not in (None, "", [], {}):
                value = payload.get(key)
                break
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            body = "\n".join(f"- {item}" for item in value if str(item).strip())
        elif isinstance(value, dict):
            body = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            body = str(value)
        sections.append(f"## {label}\n{body}")

    if not sections:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return "\n\n".join(sections)


def get_related_signals(reflection_id: str, days: int = 30) -> list[dict[str, Any]]:
    index = load_reflection_index()
    target = next((item for item in index.reflections if item.id == reflection_id), None)
    if target is None:
        return []

    tags = [tag.lower() for tag in target.tags]
    if not tags:
        return []

    signals = load_signals()
    items = signals if isinstance(signals, list) else signals.get("items", [])
    cutoff: datetime | None = None
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    matches: list[dict[str, Any]] = []

    for raw in items:
        signal = raw.get("raw", raw)
        text = " ".join(
            [
                str(signal.get("title") or ""),
                str(signal.get("summary") or ""),
                str(signal.get("topic") or ""),
                str(signal.get("source") or ""),
            ]
        ).lower()
        matched_tags = [tag for tag in tags if tag in text]
        if not matched_tags:
            continue
        published_at = signal.get("published_at") or signal.get("publish_time")
        if cutoff and published_at:
            try:
                published_dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                if published_dt < cutoff:
                    continue
            except Exception:
                pass
        matches.append(
            {
                "signal_id": raw.get("id") or signal.get("id"),
                "title": signal.get("title") or signal.get("signal_title"),
                "url": signal.get("url"),
                "source": signal.get("source"),
                "published_at": published_at,
                "matched_tags": matched_tags,
                "score": round(min(1.0, 0.4 + 0.2 * len(matched_tags)), 2),
            }
        )

    matches.sort(
        key=lambda item: (float(item["score"]), str(item.get("published_at") or "")),
        reverse=True,
    )
    return matches[:20]


def get_related_manual_sessions(reflection_id: str, limit: int = 10) -> list[dict[str, Any]]:
    index = load_reflection_index()
    target = next((item for item in index.reflections if item.id == reflection_id), None)
    if target is None:
        return []

    tags = [tag.lower() for tag in target.tags]
    if not tags:
        return []

    tag_token_map = {tag: _expand_topic_tokens(tag) for tag in tags}
    matches: list[dict[str, Any]] = []

    for session in _load_manual_sessions():
        session_id = str(session.get("session_id") or session.get("id") or "").strip()
        if not session_id:
            continue

        analysis = session.get("analysis") if isinstance(session.get("analysis"), dict) else {}
        text = " ".join(
            [
                str(session.get("title") or ""),
                str(session.get("summary") or ""),
                str(session.get("topic") or ""),
                str(analysis.get("summary") or ""),
                str(analysis.get("why_it_matters") or ""),
                str(analysis.get("relevance_to_projects") or ""),
                str(analysis.get("relevance_to_career") or ""),
                str(analysis.get("synthesized_insight") or ""),
            ]
        ).lower()

        session_tokens = _tokenize(text)
        matched_tags: list[str] = []
        matched_terms: set[str] = set()
        score = 0.0

        for tag, expanded_tokens in tag_token_map.items():
            token_overlap = expanded_tokens & session_tokens
            if tag in text or token_overlap:
                matched_tags.append(tag)
                matched_terms.update(token_overlap)
                score += 0.35 if tag in text else min(0.25, 0.08 * len(token_overlap))

        if not matched_tags:
            continue

        matches.append(
            {
                "session_id": session_id,
                "title": session.get("title") or "Untitled Manual Session",
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at"),
                "analysis_status": session.get("analysis_status"),
                "upload_reason": session.get("upload_reason") or "",
                "intended_use": session.get("intended_use") or "",
                "cognitive_layer": session.get("cognitive_layer") or "unclassified",
                "matched_tags": matched_tags,
                "matched_terms": sorted(matched_terms),
                "score": round(min(1.0, score), 2),
            }
        )

    matches.sort(
        key=lambda item: (float(item.get("score") or 0.0), str(item.get("updated_at") or item.get("created_at") or "")),
        reverse=True,
    )
    return matches[: max(1, min(limit, 20))]


def get_relationship_analytics(*, days: int = 30, limit: int = 5) -> dict[str, Any]:
    index = load_reflection_index()
    tag_counter: Counter[str] = Counter()
    reflection_summaries: list[dict[str, Any]] = []
    reflections_with_signal_matches = 0
    reflections_with_manual_matches = 0
    total_signal_matches = 0
    total_manual_matches = 0

    for item in index.reflections:
        signal_matches = get_related_signals(item.id, days=days)
        manual_matches = get_related_manual_sessions(item.id, limit=limit)

        if signal_matches:
            reflections_with_signal_matches += 1
        if manual_matches:
            reflections_with_manual_matches += 1

        total_signal_matches += len(signal_matches)
        total_manual_matches += len(manual_matches)

        for match in signal_matches:
            tag_counter.update(match.get("matched_tags") or [])
        for match in manual_matches:
            tag_counter.update(match.get("matched_tags") or [])

        total_matches = len(signal_matches) + len(manual_matches)
        if total_matches <= 0:
            continue

        reflection_summaries.append(
            {
                "id": item.id,
                "title": item.title,
                "timestamp": item.timestamp.isoformat() if hasattr(item.timestamp, "isoformat") else str(item.timestamp),
                "total_matches": total_matches,
                "signal_matches": len(signal_matches),
                "manual_matches": len(manual_matches),
                "tags": list(item.tags),
            }
        )

    reflection_summaries.sort(
        key=lambda entry: (int(entry.get("total_matches") or 0), str(entry.get("timestamp") or "")),
        reverse=True,
    )

    return {
        "window_days": days,
        "total_reflections": len(index.reflections),
        "reflections_with_signal_matches": reflections_with_signal_matches,
        "reflections_with_manual_matches": reflections_with_manual_matches,
        "total_signal_matches": total_signal_matches,
        "total_manual_matches": total_manual_matches,
        "top_reflections": reflection_summaries[: max(1, min(limit, 20))],
        "top_relationship_tags": [
            {"tag": tag, "count": count}
            for tag, count in tag_counter.most_common(max(1, min(limit, 20)))
        ],
    }


def get_explicit_relationship_index() -> dict[str, Any]:
    index = load_reflection_index()
    return build_reflection_relationship_index(index.reflections)


def get_explicit_relationships_for_reflection(reflection_id: str) -> dict[str, Any] | None:
    relationship_index = get_explicit_relationship_index()
    result = get_reflection_relationships(relationship_index, reflection_id)
    if result["node"] is None:
        return None
    return result


def get_vnext_backfill_preview(*, limit: int = 10) -> dict[str, Any]:
    index = load_reflection_index()
    candidates: list[dict[str, Any]] = []

    for item in index.reflections:
        metadata = item.model_dump(mode="json")
        has_structured_fields = bool(
            metadata.get("thesis")
            or metadata.get("key_claims")
            or metadata.get("final_takeaway")
        )
        if has_structured_fields:
            continue

        full = get_reflection_full(item.id)
        if not full or not full.get("content"):
            continue

        suggestion = _build_reflection_backfill_suggestion(metadata, str(full["content"]))
        if suggestion["missing_fields"]:
            candidates.append(suggestion)

        if len(candidates) >= max(1, min(limit, 20)):
            break

    return {
        "total_candidates": len(candidates),
        "suggestions": candidates,
    }


def get_vnext_backfill_suggestion(reflection_id: str) -> dict[str, Any] | None:
    full = get_reflection_full(reflection_id)
    if not full:
        return None

    metadata = full.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None

    has_structured_fields = bool(
        metadata.get("thesis")
        or metadata.get("key_claims")
        or metadata.get("final_takeaway")
    )
    if has_structured_fields:
        return {
            "id": metadata.get("id"),
            "title": metadata.get("title"),
            "missing_fields": [],
            "suggested_frontmatter_patch": "",
        }

    content = str(full.get("content") or "")
    if not content.strip():
        return None

    return _build_reflection_backfill_suggestion(metadata, content)


def create_vnext_backfill_draft(reflection_id: str) -> dict[str, Any] | None:
    full = get_reflection_full(reflection_id)
    suggestion = get_vnext_backfill_suggestion(reflection_id)
    if not full or not suggestion:
        return None

    metadata = full.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None

    BACKFILL_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", reflection_id)
    file_path = BACKFILL_DRAFTS_DIR / f"{safe_id}.md"

    body = "\n".join(
        [
            f"# Reflection Backfill Draft: {metadata.get('title') or reflection_id}",
            "",
            f"- Reflection ID: {reflection_id}",
            f"- GitHub Path: {metadata.get('github_path') or 'unknown'}",
            f"- GitHub URL: {metadata.get('github_url') or 'unknown'}",
            f"- Missing Fields: {', '.join(suggestion.get('missing_fields') or []) or 'none'}",
            "",
            "## Copy-ready Frontmatter Patch",
            "",
            "```yaml",
            suggestion.get("suggested_frontmatter_patch") or "# No patch required",
            "```",
            "",
            "## Suggested Thesis",
            "",
            suggestion.get("suggested_thesis") or "N/A",
            "",
            "## Suggested Final Takeaway",
            "",
            suggestion.get("suggested_final_takeaway") or "N/A",
            "",
        ]
    )

    file_path.write_text(body, encoding="utf-8")
    return {
        "reflection_id": reflection_id,
        "file_path": str(file_path),
        "missing_fields": suggestion.get("missing_fields") or [],
        "suggested_frontmatter_patch": suggestion.get("suggested_frontmatter_patch") or "",
    }


def create_vnext_backfill_drafts_batch(*, limit: int = 10) -> dict[str, Any]:
    preview = get_vnext_backfill_preview(limit=limit)
    created: list[dict[str, Any]] = []

    for item in preview.get("suggestions") or []:
        reflection_id = str(item.get("id") or "").strip()
        if not reflection_id:
            continue
        draft = create_vnext_backfill_draft(reflection_id)
        if draft:
            created.append(draft)

    return {
        "requested_limit": limit,
        "created_count": len(created),
        "drafts": created,
    }


def apply_vnext_backfill_to_source(reflection_id: str) -> dict[str, Any] | None:
    full = get_reflection_full(reflection_id)
    suggestion = get_vnext_backfill_suggestion(reflection_id)
    if not full or not suggestion:
        return None

    metadata = full.get("metadata") or {}
    content = str(full.get("content") or "")
    if not isinstance(metadata, dict) or not content.strip():
        return None

    github_path = str(metadata.get("github_path") or "").strip()
    if not github_path:
        return None

    frontmatter, body = _extract_frontmatter(content)
    if not isinstance(frontmatter, dict):
        return None

    changed_fields: list[str] = []

    if not frontmatter.get("thesis") and suggestion.get("suggested_thesis"):
        frontmatter["thesis"] = suggestion["suggested_thesis"]
        changed_fields.append("thesis")
    if not frontmatter.get("key_claims") and suggestion.get("suggested_key_claims"):
        frontmatter["key_claims"] = suggestion["suggested_key_claims"]
        changed_fields.append("key_claims")
    if not frontmatter.get("counterpoints") and suggestion.get("suggested_counterpoints"):
        frontmatter["counterpoints"] = suggestion["suggested_counterpoints"]
        changed_fields.append("counterpoints")
    if not frontmatter.get("open_questions") and suggestion.get("suggested_open_questions"):
        frontmatter["open_questions"] = suggestion["suggested_open_questions"]
        changed_fields.append("open_questions")
    if not frontmatter.get("final_takeaway") and suggestion.get("suggested_final_takeaway"):
        frontmatter["final_takeaway"] = suggestion["suggested_final_takeaway"]
        changed_fields.append("final_takeaway")

    serialized_frontmatter = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    updated_content = f"---\n{serialized_frontmatter}\n---\n\n{body.lstrip()}"

    client = GitHubReflectionClient()
    commit_message = f"AI Radar: backfill reflection vNext fields for {reflection_id}"
    result = client.update_file_content(
        path=github_path,
        content=updated_content,
        message=commit_message,
    )

    return {
        "reflection_id": reflection_id,
        "github_path": github_path,
        "changed_fields": changed_fields,
        "commit_message": commit_message,
        "commit_sha": (((result or {}).get("commit")) or {}).get("sha"),
        "content_url": (((result or {}).get("content")) or {}).get("html_url"),
    }


def trigger_sync(*, force_full: bool = False):
    return sync_reflections(force_full=force_full)


def get_sync_state() -> dict[str, Any]:
    return load_sync_state().model_dump(mode="json")
