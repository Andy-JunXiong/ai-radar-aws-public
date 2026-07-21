from __future__ import annotations

from datetime import datetime
from typing import Any
import json
import re

import yaml

from app.reflection.schemas import (
    ReflectionDepth,
    ReflectionMetadata,
    ReflectionSource,
)


class FrontmatterParseError(Exception):
    pass


PAIR_CODE_RE = re.compile(r"^(?P<code>\d{3,})")


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        raise FrontmatterParseError("Missing YAML frontmatter block.")

    lines = content.splitlines()
    end_index: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break

    if end_index is None:
        raise FrontmatterParseError("Frontmatter block is not closed.")

    raw_yaml = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])

    try:
        payload = yaml.safe_load(raw_yaml) or {}
    except Exception as exc:
        raise FrontmatterParseError(f"YAML parse failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise FrontmatterParseError("Frontmatter must parse to an object.")

    return payload, body


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("timestamp is empty")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _parse_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _extract_pair_code(path: str) -> str:
    file_name = path.rsplit("/", 1)[-1]
    match = PAIR_CODE_RE.match(file_name)
    return match.group("code") if match else ""


def _clean_title_from_path(path: str) -> str:
    file_name = path.rsplit("/", 1)[-1]
    stem = file_name.rsplit(".", 1)[0]
    stem = re.sub(r"^\d{3,}[_-]?", "", stem)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem or file_name


def _iter_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_objects(child)


def _find_first(payload: Any, keys: list[str]) -> Any | None:
    normalized_keys = {key.lower() for key in keys}
    for obj in _iter_objects(payload):
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            if str(key).lower() in normalized_keys and value not in (None, "", [], {}):
                return value
    return None


def _parse_source(value: Any) -> ReflectionSource:
    text = str(value or "").strip().lower()
    if text in {item.value for item in ReflectionSource}:
        return ReflectionSource(text)
    if "claude" in text:
        return ReflectionSource.CLAUDE_CHAT
    if "obsidian" in text:
        return ReflectionSource.OBSIDIAN
    if "manual" in text:
        return ReflectionSource.MANUAL
    if "book" in text:
        return ReflectionSource.BOOK
    if "podcast" in text:
        return ReflectionSource.PODCAST
    return ReflectionSource.OTHER


def _parse_depth(value: Any) -> ReflectionDepth | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {item.value for item in ReflectionDepth}:
        return ReflectionDepth(text)
    if "deep" in text:
        return ReflectionDepth.DEEP
    if "medium" in text:
        return ReflectionDepth.MEDIUM
    if "shallow" in text:
        return ReflectionDepth.SHALLOW
    return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _render_json_reflection_content(payload: Any) -> str:
    sections: list[str] = []

    title = _find_first(payload, ["title", "reflection_title", "session_title", "name", "topic"])
    if title:
        sections.append(f"# {title}")

    for label, keys in [
        ("Summary", ["summary", "compressed_core", "compressedCore", "overview"]),
        ("Thesis", ["thesis"]),
        ("Key Claims", ["key_claims", "keyClaims", "claims"]),
        ("Counterpoints", ["counterpoints"]),
        ("Open Questions", ["open_questions", "openQuestions", "questions"]),
        ("Final Takeaway", ["final_takeaway", "finalTakeaway", "takeaway"]),
        ("Corrections", ["corrections", "self_corrections", "selfCorrections"]),
        ("Retained Judgements", ["retained_judgements", "retainedJudgements"]),
    ]:
        value = _find_first(payload, keys)
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


def parse_reflection(
    *,
    content: str,
    github_path: str,
    github_url: str,
    github_raw_url: str,
    commit_sha: str,
    last_modified: datetime,
) -> ReflectionMetadata:
    meta, _body = _extract_frontmatter(content)

    required = ["id", "title", "timestamp", "source", "tags"]
    missing = [key for key in required if key not in meta]
    if missing:
        raise FrontmatterParseError(f"Missing required fields: {missing}")

    try:
        tags = meta["tags"] if isinstance(meta["tags"], list) else []
        return ReflectionMetadata(
            id=str(meta["id"]),
            title=str(meta["title"]),
            timestamp=_parse_datetime(meta["timestamp"]),
            source=ReflectionSource(str(meta["source"])),
            tags=[str(item) for item in tags if str(item).strip()],
            github_path=github_path,
            github_url=github_url,
            github_raw_url=github_raw_url,
            commit_sha=commit_sha,
            last_modified=last_modified,
            depth=ReflectionDepth(str(meta["depth"])) if meta.get("depth") else None,
            duration_minutes=int(meta["duration_minutes"]) if meta.get("duration_minutes") is not None else None,
            self_correction_count=int(meta["self_correction_count"]) if meta.get("self_correction_count") is not None else None,
            thesis=str(meta["thesis"]) if meta.get("thesis") else None,
            key_claims=_parse_string_list(meta.get("key_claims")),
            counterpoints=_parse_string_list(meta.get("counterpoints")),
            open_questions=_parse_string_list(meta.get("open_questions")),
            final_takeaway=str(meta["final_takeaway"]) if meta.get("final_takeaway") else None,
            confidence=float(meta["confidence"]) if meta.get("confidence") is not None else None,
            evidence_strength=str(meta["evidence_strength"]) if meta.get("evidence_strength") else None,
            related=[str(item) for item in meta.get("related", []) if str(item).strip()],
            raw_archive=str(meta["raw_archive"]) if meta.get("raw_archive") else None,
        )
    except Exception as exc:
        raise FrontmatterParseError(f"Schema validation failed: {exc}") from exc


def parse_reflection_json_bundle(
    *,
    schema_content: str,
    schema_path: str,
    schema_url: str,
    schema_raw_url: str,
    html_path: str | None,
    html_url: str | None,
    html_raw_url: str | None,
    commit_sha: str,
    last_modified: datetime,
) -> tuple[ReflectionMetadata, str]:
    try:
        payload = json.loads(schema_content)
    except Exception as exc:
        raise FrontmatterParseError(f"JSON parse failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise FrontmatterParseError("Reflection JSON must parse to an object.")

    pair_code = _extract_pair_code(schema_path)
    title = str(
        _find_first(payload, ["title", "reflection_title", "session_title", "name", "topic"])
        or _clean_title_from_path(schema_path)
    ).strip()
    timestamp = _find_first(payload, ["timestamp", "created_at", "createdAt", "datetime", "date", "exported_at"])
    reflection_id = str(
        _find_first(payload, ["id", "reflection_id", "reflectionId", "conversation_id", "conversationId"])
        or f"refl_{pair_code or schema_path.rsplit('/', 1)[-1].rsplit('.', 1)[0]}"
    ).strip()
    tags = _parse_string_list(_find_first(payload, ["tags", "keywords", "topics", "labels"]))
    source = _parse_source(_find_first(payload, ["source", "platform", "assistant", "provider", "model_family"]))

    try:
        metadata = ReflectionMetadata(
            id=reflection_id,
            title=title,
            timestamp=_parse_datetime(timestamp or last_modified.isoformat()),
            source=source,
            tags=tags,
            github_path=html_path or schema_path,
            github_url=html_url or schema_url,
            github_raw_url=html_raw_url or schema_raw_url,
            commit_sha=commit_sha,
            last_modified=last_modified,
            content_format="json_html",
            schema_path=schema_path,
            schema_url=schema_url,
            schema_raw_url=schema_raw_url,
            raw_html_path=html_path,
            raw_html_url=html_url,
            depth=_parse_depth(_find_first(payload, ["depth"])),
            duration_minutes=_parse_int(_find_first(payload, ["duration_minutes", "durationMinutes", "duration"])),
            self_correction_count=_parse_int(
                _find_first(payload, ["self_correction_count", "selfCorrectionCount", "correction_count", "corrections"])
            ),
            thesis=str(_find_first(payload, ["thesis"]) or "") or None,
            key_claims=_parse_string_list(_find_first(payload, ["key_claims", "keyClaims", "claims"])),
            counterpoints=_parse_string_list(_find_first(payload, ["counterpoints"])),
            open_questions=_parse_string_list(_find_first(payload, ["open_questions", "openQuestions", "questions"])),
            final_takeaway=str(_find_first(payload, ["final_takeaway", "finalTakeaway", "takeaway"]) or "") or None,
            confidence=_parse_float(_find_first(payload, ["confidence"])),
            evidence_strength=str(_find_first(payload, ["evidence_strength", "evidenceStrength"]) or "") or None,
            related=_parse_string_list(_find_first(payload, ["related", "related_reflections", "relatedReflections"])),
            raw_archive=html_path or str(_find_first(payload, ["raw_archive", "rawArchive"]) or "") or None,
        )
    except Exception as exc:
        raise FrontmatterParseError(f"Schema validation failed: {exc}") from exc

    return metadata, _render_json_reflection_content(payload)
