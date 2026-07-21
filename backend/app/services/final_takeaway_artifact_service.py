from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "final_takeaways"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_string_list(value: Any, *, max_items: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:max_items]:
        text = _safe_text(item)
        if text:
            items.append(text)
    return items


def _safe_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_external_synthesis_quality(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    status = _safe_text(value.get("status")).lower()
    if status not in {"clean", "warning", "not_checked", "not_attached"}:
        status = "not_checked"

    flags: list[dict[str, str]] = []
    raw_flags = value.get("flags")
    if isinstance(raw_flags, list):
        for item in raw_flags[:12]:
            if not isinstance(item, dict):
                continue
            code = _safe_text(item.get("code"))
            label = _safe_text(item.get("label"))
            detail = _safe_text(item.get("detail"))
            if code:
                flags.append({
                    "code": code,
                    "label": label or code,
                    "detail": detail,
                })

    return {
        "schema_version": 1,
        "status": status,
        "summary": _safe_text(value.get("summary")),
        "flags": flags,
        "effect": "non_blocking_review_context_warning",
        "evidence_boundary": "review_context_not_verified_evidence",
        "review_context_only": True,
        "not_verified_evidence": True,
        "checked_at": _safe_text(value.get("checked_at")),
        "checked_text_length": _safe_nonnegative_int(value.get("checked_text_length")),
        "source_file": _safe_text(value.get("source_file")),
        "source_kind": _safe_text(value.get("source_kind")),
        "topic_terms_checked": _safe_string_list(value.get("topic_terms_checked")),
        "topic_hit_count": _safe_nonnegative_int(value.get("topic_hit_count")),
    }


def _safe_metadata(value: Any) -> dict[str, Any]:
    metadata = _safe_dict(value)
    quality = _safe_external_synthesis_quality(metadata.get("external_synthesis_quality"))
    if quality:
        metadata["external_synthesis_quality"] = quality
    return metadata


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snapshot_dir() -> Path:
    return BASE_DIR / "review_bundle_snapshots"


def _artifact_dir() -> Path:
    return BASE_DIR / "artifacts"


def _external_synthesis_dir() -> Path:
    return BASE_DIR / "external_synthesis_sources"


def _snapshot_index_path() -> Path:
    return _snapshot_dir() / "index.json"


def _artifact_index_path() -> Path:
    return _artifact_dir() / "index.json"


def _external_synthesis_index_path() -> Path:
    return _external_synthesis_dir() / "index.json"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ensure_index(path: Path) -> None:
    _ensure_dir(path.parent)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")


def _load_index(path: Path) -> list[dict[str, Any]]:
    _ensure_index(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _save_index(path: Path, items: list[dict[str, Any]]) -> None:
    _ensure_index(path)
    path.write_text(_json_dumps(items), encoding="utf-8")


def _safe_id(value: str) -> str:
    return _safe_text(value).replace("/", "_").replace("\\", "_")


def _snapshot_path(snapshot_id: str) -> Path:
    return _snapshot_dir() / f"{_safe_id(snapshot_id)}.json"


def _artifact_path(final_takeaway_id: str) -> Path:
    return _artifact_dir() / f"{_safe_id(final_takeaway_id)}.json"


def _external_synthesis_path(source_id: str) -> Path:
    return _external_synthesis_dir() / f"{_safe_id(source_id)}.json"


def _write_record(path: Path, record: dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    path.write_text(_json_dumps(record), encoding="utf-8")


def _read_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _upsert_index_item(path: Path, item: dict[str, Any], id_field: str) -> None:
    items = _load_index(path)
    item_id = _safe_text(item.get(id_field))
    next_items = [existing for existing in items if _safe_text(existing.get(id_field)) != item_id]
    next_items.insert(0, item)
    _save_index(path, next_items)


def _normalize_html_as_text(value: str) -> str:
    without_scripts = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", value)
    without_comments = re.sub(r"(?s)<!--.*?-->", " ", without_scripts)
    with_breaks = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h[1-6])\s*/?\s*>", "\n", without_comments)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", with_breaks)
    decoded = html.unescape(without_tags)
    lines = [" ".join(line.split()) for line in decoded.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _normalize_external_synthesis_text(
    *,
    source_text: str,
    source_kind: str,
    source_file: str,
    content_type: str,
) -> tuple[str, str]:
    normalized_kind = (_safe_text(source_kind) or "paste").lower()
    normalized_file = _safe_text(source_file).lower()
    normalized_content_type = _safe_text(content_type).lower()
    is_html = (
        "html" in normalized_kind
        or normalized_file.endswith(".html")
        or normalized_file.endswith(".htm")
        or "html" in normalized_content_type
    )
    if is_html:
        return _normalize_html_as_text(source_text), "external_html"
    if normalized_file.endswith(".md") or "markdown" in normalized_kind or "markdown" in normalized_content_type:
        return _safe_text(source_text), "external_markdown"
    if normalized_file.endswith(".txt") or "plain" in normalized_content_type:
        return _safe_text(source_text), "external_plaintext"
    return _safe_text(source_text), normalized_kind or "external_synthesis"


def create_external_synthesis_source(
    *,
    signal_id: str,
    source_text: str,
    source_file: str = "",
    source_kind: str = "paste",
    content_type: str = "",
    created_by: str = "Andy",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_signal_id = _safe_text(signal_id)
    original_text = _safe_text(source_text)
    if not normalized_signal_id:
        raise ValueError("signal_id is required.")
    if not original_text:
        raise ValueError("source_text is required.")

    normalized_text, normalized_kind = _normalize_external_synthesis_text(
        source_text=original_text,
        source_kind=source_kind,
        source_file=source_file,
        content_type=content_type,
    )
    if not normalized_text:
        raise ValueError("source_text did not contain reviewable text after normalization.")

    now = _utc_now_iso()
    source_id = f"ess_{uuid.uuid4().hex[:12]}"
    record = {
        "external_synthesis_source_id": source_id,
        "record_type": "external_synthesis_source",
        "schema_version": 1,
        "signal_id": normalized_signal_id,
        "source_kind": normalized_kind,
        "source_file": _safe_text(source_file),
        "content_type": _safe_text(content_type),
        "source_text": normalized_text,
        "source_text_length": len(normalized_text),
        "original_content_hash": _text_hash(original_text),
        "normalized_content_hash": _text_hash(normalized_text),
        "evidence_boundary": "review_context_not_verified_evidence",
        "used_by": "final_takeaway_review_bundle",
        "created_by": _safe_text(created_by) or "Andy",
        "created_at": now,
        "metadata": {
            **_safe_metadata(metadata),
            "normalization": "html_text_only_no_script_execution" if normalized_kind == "external_html" else "text_preserved",
            "raw_content_stored": False,
        },
    }
    _write_record(_external_synthesis_path(source_id), record)
    _upsert_index_item(
        _external_synthesis_index_path(),
        {
            "external_synthesis_source_id": source_id,
            "signal_id": record["signal_id"],
            "source_kind": record["source_kind"],
            "source_file": record["source_file"],
            "source_text_length": record["source_text_length"],
            "normalized_content_hash": record["normalized_content_hash"],
            "evidence_boundary": record["evidence_boundary"],
            "used_by": record["used_by"],
            "created_at": now,
        },
        "external_synthesis_source_id",
    )
    return record


def get_external_synthesis_source(source_id: str) -> dict[str, Any] | None:
    normalized = _safe_text(source_id)
    if not normalized:
        return None
    return _read_record(_external_synthesis_path(normalized))


def list_external_synthesis_sources(*, signal_id: str = "") -> list[dict[str, Any]]:
    normalized_signal_id = _safe_text(signal_id)
    items = _load_index(_external_synthesis_index_path())
    if normalized_signal_id:
        items = [item for item in items if _safe_text(item.get("signal_id")) == normalized_signal_id]
    return items


def create_review_bundle_snapshot(
    *,
    signal_id: str,
    source_text: str,
    source_file: str = "",
    source_kind: str = "external_md",
    snapshot_reason: str = "final_takeaway_review_bundle",
    used_by: str = "confirmed_final_takeaway",
    created_by: str = "Andy",
    conversation_refs: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_signal_id = _safe_text(signal_id)
    normalized_source_text = _safe_text(source_text)
    if not normalized_signal_id:
        raise ValueError("signal_id is required.")
    if not normalized_source_text:
        raise ValueError("source_text is required.")

    payload_for_hash = {
        "signal_id": normalized_signal_id,
        "source_text": normalized_source_text,
        "source_file": _safe_text(source_file),
        "source_kind": _safe_text(source_kind) or "external_md",
        "snapshot_reason": _safe_text(snapshot_reason) or "final_takeaway_review_bundle",
        "used_by": _safe_text(used_by) or "confirmed_final_takeaway",
        "conversation_refs": _safe_list(conversation_refs),
        "metadata": _safe_metadata(metadata),
    }
    now = _utc_now_iso()
    snapshot_id = f"rbs_{uuid.uuid4().hex[:12]}"
    record = {
        "snapshot_id": snapshot_id,
        "record_type": "review_bundle_snapshot",
        "schema_version": 1,
        "created_at": now,
        "created_by": _safe_text(created_by) or "Andy",
        "content_hash": _content_hash(payload_for_hash),
        **payload_for_hash,
    }
    _write_record(_snapshot_path(snapshot_id), record)
    _upsert_index_item(
        _snapshot_index_path(),
        {
            "snapshot_id": snapshot_id,
            "signal_id": record["signal_id"],
            "source_kind": record["source_kind"],
            "snapshot_reason": record["snapshot_reason"],
            "used_by": record["used_by"],
            "content_hash": record["content_hash"],
            "created_at": now,
        },
        "snapshot_id",
    )
    return record


def get_review_bundle_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    normalized = _safe_text(snapshot_id)
    if not normalized:
        return None
    return _read_record(_snapshot_path(normalized))


def list_review_bundle_snapshots(*, signal_id: str = "") -> list[dict[str, Any]]:
    normalized_signal_id = _safe_text(signal_id)
    items = _load_index(_snapshot_index_path())
    if normalized_signal_id:
        items = [item for item in items if _safe_text(item.get("signal_id")) == normalized_signal_id]
    return items


def confirm_final_takeaway(
    *,
    signal_id: str,
    confirmed_text: str,
    review_bundle_snapshot_id: str,
    source_completion_note: str = "",
    confirmed_by: str = "Andy",
    provenance: dict[str, Any] | None = None,
    source_signal_id: str = "",
) -> dict[str, Any]:
    normalized_signal_id = _safe_text(signal_id)
    normalized_confirmed_text = _safe_text(confirmed_text)
    normalized_snapshot_id = _safe_text(review_bundle_snapshot_id)
    normalized_confirmed_by = _safe_text(confirmed_by) or "Andy"
    if not normalized_signal_id:
        raise ValueError("signal_id is required.")
    if not normalized_confirmed_text:
        raise ValueError("confirmed_text is required.")
    if not normalized_snapshot_id:
        raise ValueError("review_bundle_snapshot_id is required.")

    snapshot = get_review_bundle_snapshot(normalized_snapshot_id)
    if not snapshot:
        raise ValueError("review bundle snapshot not found.")
    snapshot_signal_id = _safe_text(snapshot.get("signal_id"))
    if snapshot_signal_id and snapshot_signal_id != normalized_signal_id:
        raise ValueError("review bundle snapshot signal_id does not match.")

    now = _utc_now_iso()
    final_takeaway_id = f"fta_{uuid.uuid4().hex[:12]}"
    record = {
        "final_takeaway_id": final_takeaway_id,
        "record_type": "final_takeaway_artifact",
        "schema_version": 1,
        "status": "confirmed",
        "signal_id": normalized_signal_id,
        "source_signal_id": _safe_text(source_signal_id) or normalized_signal_id,
        "confirmed_text": normalized_confirmed_text,
        "source_completion_note": _safe_text(source_completion_note),
        "review_bundle_snapshot_id": normalized_snapshot_id,
        "review_bundle_content_hash": _safe_text(snapshot.get("content_hash")),
        "confirmed_by": normalized_confirmed_by,
        "confirmed_at": now,
        "created_at": now,
        "provenance": _safe_dict(provenance),
    }
    _write_record(_artifact_path(final_takeaway_id), record)
    _upsert_index_item(
        _artifact_index_path(),
        {
            "final_takeaway_id": final_takeaway_id,
            "signal_id": record["signal_id"],
            "source_signal_id": record["source_signal_id"],
            "review_bundle_snapshot_id": normalized_snapshot_id,
            "review_bundle_content_hash": record["review_bundle_content_hash"],
            "confirmed_by": record["confirmed_by"],
            "confirmed_at": now,
            "status": record["status"],
        },
        "final_takeaway_id",
    )
    return record


def get_final_takeaway(final_takeaway_id: str) -> dict[str, Any] | None:
    normalized = _safe_text(final_takeaway_id)
    if not normalized:
        return None
    return _read_record(_artifact_path(normalized))


def list_final_takeaways(*, signal_id: str = "") -> list[dict[str, Any]]:
    normalized_signal_id = _safe_text(signal_id)
    items = _load_index(_artifact_index_path())
    if normalized_signal_id:
        items = [item for item in items if _safe_text(item.get("signal_id")) == normalized_signal_id]
    return items
