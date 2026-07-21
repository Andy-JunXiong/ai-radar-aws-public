import hashlib
import json
import os
import re
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import boto3

from app.config import BASE_DIR
from app.services.llm_executor_service import execute_text_json_task
from app.services.execution_policy_service import PolicyInput
from app.services.fallback_policy_service import execute_policy_text_json
from app.services.signal_decision_trace_service import (
    append_decision_trace_event,
    build_decision_trace_event,
    status_event_type,
    verification_support_snapshot,
)

BUCKET_NAME = (
    os.getenv("AI_RADAR_S3_BUCKET")
    or os.getenv("S3_BUCKET")
    or "ai-radar-junxiong-data"
)

s3 = boto3.client("s3")

SIGNALS_CACHE: Dict[str, Any] = {
    "data": None,
    "by_id": {},
    "last_loaded": 0,
}
SIGNALS_LOAD_DIAGNOSTIC: Dict[str, Any] = {
    "source": "not_loaded",
    "local_snapshot_status": "not_checked",
    "local_snapshot_reason": "",
    "loaded_at": None,
}
LOCAL_SIGNALS_LOAD_STATUS: Dict[str, Any] = {
    "status": "not_checked",
    "reason": "",
}
INSIGHTS_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}
RADAR_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}
RADAR_INTELLIGENCE_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}
AGENT_WATCH_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}
FRICTION_SIGNALS_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}
MANUAL_SESSIONS_CACHE: Dict[str, Any] = {
    "data": None,
    "last_loaded": 0,
}

SIGNALS_CACHE_TTL = 60 * 60  # 1 hour
JSON_CACHE_TTL = 300
LOCAL_SIGNALS_SNAPSHOT_TTL = 6 * 60 * 60

PROJECT_ROOT_DIR = BASE_DIR.parent

LOCAL_SIGNALS_FILE = PROJECT_ROOT_DIR / "data" / "output" / "signals.json"
LOCAL_INSIGHTS_FILE = PROJECT_ROOT_DIR / "data" / "output" / "insights.json"
LOCAL_RADAR_FILE = PROJECT_ROOT_DIR / "data" / "output" / "daily_radar.json"
LOCAL_AGENT_WATCH_FILE = PROJECT_ROOT_DIR / "data" / "output" / "agent_watch_signals.json"
LOCAL_AGENT_WATCH_REPO_SNAPSHOTS_FILE = PROJECT_ROOT_DIR / "data" / "output" / "agent_watch_repo_snapshots.json"
LOCAL_AGENT_WATCH_REPO_PROFILES_FILE = PROJECT_ROOT_DIR / "data" / "output" / "agent_watch_repo_profiles.json"
LOCAL_AGENT_WATCH_TRACKING_STATE_FILE = PROJECT_ROOT_DIR / "data" / "output" / "agent_watch_tracking_state.json"
LOCAL_AGENT_WATCH_SMOKE_TEST_FILE = PROJECT_ROOT_DIR / "data" / "output" / "agent_watch_smoke_test.json"
LOCAL_FRICTION_SIGNALS_FILE = PROJECT_ROOT_DIR / "data" / "output" / "friction_signals.json"
LOCAL_FRICTION_SIGNAL_PROFILES_FILE = PROJECT_ROOT_DIR / "data" / "output" / "friction_signal_profiles.json"
LOCAL_FRICTION_TRACKING_STATE_FILE = PROJECT_ROOT_DIR / "data" / "output" / "friction_tracking_state.json"
LOCAL_INTELLIGENCE_DIR = PROJECT_ROOT_DIR / "data" / "output" / "intelligence"

INTELLIGENCE_FILE_MAP = {
    "topic_trends": "topic_trends.json",
    "topic_momentum": "topic_momentum.json",
    "rising_topics": "rising_topics.json",
    "strategic_priority": "strategic_priority.json",
    "weekly_momentum": "weekly_momentum.json",
}


def read_json(key: str):
    response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def invalidate_signals_cache() -> None:
    SIGNALS_CACHE["data"] = None
    SIGNALS_CACHE["by_id"] = {}
    SIGNALS_CACHE["last_loaded"] = 0


def _invalidate_simple_cache(cache: Dict[str, Any]) -> None:
    cache["data"] = None
    cache["last_loaded"] = 0


def _get_cached_payload(
    cache: Dict[str, Any],
    *,
    ttl_seconds: int,
) -> Any:
    if cache.get("data") is None:
        return None

    cache_age = time.time() - float(cache.get("last_loaded") or 0)
    if cache_age >= ttl_seconds:
        return None

    return cache.get("data")


def _set_cached_payload(cache: Dict[str, Any], data: Any) -> Any:
    cache["data"] = data
    cache["last_loaded"] = time.time()
    return data


def _local_output_enabled(use_local: bool = False) -> bool:
    if use_local:
        return True
    value = str(os.getenv("AI_RADAR_USE_LOCAL_OUTPUT", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def read_local_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_local_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_keys(prefix: str, *, suffix: str | None = None) -> List[str]:
    paginator = s3.get_paginator("list_objects_v2")
    keys: List[str] = []

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if suffix is None or key.endswith(suffix):
                keys.append(key)

    return keys


def list_json_keys(prefix: str) -> List[str]:
    return list_keys(prefix, suffix=".json")


def list_json_keys_for_prefixes(prefixes: List[str]) -> List[str]:
    keys: List[str] = []
    seen = set()

    for prefix in prefixes:
        for key in list_json_keys(prefix):
            if key not in seen:
                seen.add(key)
                keys.append(key)

    return keys


def normalize_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", []) or data.get("signals", [])
    return []


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_signal_timestamp(value: Any) -> float | None:
    text = _safe_str(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _signal_snapshot_latest_timestamp(items: List[Dict[str, Any]]) -> float | None:
    timestamps: List[float] = []
    for item in items:
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        for value in [
            item.get("collected_at"),
            raw.get("collected_at"),
            item.get("published_at"),
            raw.get("published_at"),
        ]:
            timestamp = _parse_signal_timestamp(value)
            if timestamp is not None:
                timestamps.append(timestamp)
    return max(timestamps) if timestamps else None


def _signal_snapshot_latest_iso(items: List[Dict[str, Any]]) -> str | None:
    latest = _signal_snapshot_latest_timestamp(items)
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _set_local_signals_load_status(status: str, reason: str = "") -> None:
    LOCAL_SIGNALS_LOAD_STATUS["status"] = status
    LOCAL_SIGNALS_LOAD_STATUS["reason"] = reason


def _set_signal_load_diagnostic(
    *,
    source: str,
    items: List[Dict[str, Any]] | None,
    started_at: float,
) -> None:
    loaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    SIGNALS_LOAD_DIAGNOSTIC.update(
        {
            "source": source,
            "count": len(items or []),
            "latest_content_at": _signal_snapshot_latest_iso(items or []),
            "duration_ms": round((time.time() - started_at) * 1000, 2),
            "loaded_at": loaded_at,
            "local_snapshot_status": LOCAL_SIGNALS_LOAD_STATUS.get("status") or "not_checked",
            "local_snapshot_reason": LOCAL_SIGNALS_LOAD_STATUS.get("reason") or "",
        }
    )


def get_last_signal_load_diagnostic() -> Dict[str, Any]:
    return dict(SIGNALS_LOAD_DIAGNOSTIC)


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}
CONTENT_DEDUPE_TOKEN_LIMIT = 24
CONTENT_DEDUPE_MIN_TOKENS = 18


def _canonical_signal_url(url: str) -> str:
    text = _safe_str(url)
    if not text:
        return ""

    parsed = urlparse(text)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path or "").rstrip("/")

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered_key = key.lower()
        if lowered_key in TRACKING_QUERY_PARAMS:
            continue
        if any(lowered_key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_pairs.append((key, value))

    query = urlencode(sorted(query_pairs))
    return urlunparse((scheme, netloc, path, "", query, ""))


def build_signal_identity(item: Dict[str, Any]) -> str:
    raw = item.get("raw", item)

    url = _canonical_signal_url(_safe_str(raw.get("url")))
    title = _safe_str(raw.get("title") or raw.get("signal_title"))
    source = _safe_str(raw.get("source"))
    published_at = _safe_str(
        raw.get("published_at")
        or raw.get("publish_time")
        or raw.get("published_time")
    )

    base = url or f"{title}||{source}||{published_at}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _signal_url(item: Dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else item
    return _canonical_signal_url(_safe_str(raw.get("url") or item.get("url") or raw.get("link") or item.get("link")))


def _is_category_signal_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(token in path for token in ("/category/", "/tag/", "/tags/", "/topics/", "/learning-levels/"))


def _is_article_signal_url(url: str) -> bool:
    path = urlparse(url).path.lower().strip("/")
    return bool(path) and not _is_category_signal_url(url)


def _signal_content_text(item: Dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    candidates = [
        item.get("source_excerpt"),
        raw.get("source_excerpt"),
        item.get("content"),
        raw.get("content"),
        item.get("summary"),
        raw.get("summary"),
        item.get("description"),
        raw.get("description"),
    ]
    values = [_safe_str(value) for value in candidates if _safe_str(value)]
    return max(values, key=len) if values else ""


def _signal_content_tokens(item: Dict[str, Any]) -> List[str]:
    return re.findall(r"[a-z0-9]+", _signal_content_text(item).lower())


def _signal_published_at(item: Dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    return _safe_str(
        item.get("published_at")
        or raw.get("published_at")
        or item.get("published")
        or raw.get("published")
        or item.get("publish_time")
        or raw.get("publish_time")
    )


def _content_duplicate_key(item: Dict[str, Any]) -> str:
    tokens = _signal_content_tokens(item)
    if len(tokens) < CONTENT_DEDUPE_MIN_TOKENS:
        return ""
    published_at = _signal_published_at(item)
    return f"{published_at}||{' '.join(tokens[:CONTENT_DEDUPE_TOKEN_LIMIT])}"


def _signal_title_quality(item: Dict[str, Any]) -> int:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    title = _safe_str(item.get("title") or raw.get("title") or item.get("signal_title") or raw.get("signal_title"))
    score = len(re.findall(r"[a-z0-9]+", title.lower()))
    url = _signal_url(item)
    if _is_article_signal_url(url):
        score += 10
    if _is_category_signal_url(url):
        score -= 10
    lowered = title.lower()
    if lowered in {"artificial intelligence | artificial intelligence", "artificial intelligence"}:
        score -= 8
    return score


def _prefer_signal_record(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if _signal_title_quality(incoming) > _signal_title_quality(existing):
        return merge_signal_records(incoming, existing)
    return merge_signal_records(existing, incoming)


def _dedupe_category_article_content(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = _content_duplicate_key(item)
        if key:
            groups.setdefault(key, []).append(item)

    replacement_by_signal_id: Dict[str, str] = {}
    merged_by_signal_id = {str(item.get("signal_id") or ""): item for item in items}

    for records in groups.values():
        if len(records) < 2:
            continue

        urls = [_signal_url(record) for record in records]
        has_category = any(_is_category_signal_url(url) for url in urls)
        has_article = any(_is_article_signal_url(url) for url in urls)
        if not has_category or not has_article:
            continue

        preferred = sorted(records, key=_signal_title_quality, reverse=True)[0]
        preferred_id = str(preferred.get("signal_id") or "")
        if not preferred_id:
            continue

        merged = preferred
        for record in records:
            record_id = str(record.get("signal_id") or "")
            if not record_id or record_id == preferred_id:
                continue
            merged = _prefer_signal_record(merged, record)
            replacement_by_signal_id[record_id] = preferred_id

        merged_by_signal_id[preferred_id] = merged

    if not replacement_by_signal_id:
        return items

    deduped: List[Dict[str, Any]] = []
    emitted: set[str] = set()
    for item in items:
        signal_id = str(item.get("signal_id") or "")
        if signal_id in replacement_by_signal_id:
            continue
        next_item = merged_by_signal_id.get(signal_id, item)
        next_id = str(next_item.get("signal_id") or signal_id)
        if next_id in emitted:
            continue
        emitted.add(next_id)
        deduped.append(next_item)

    return deduped


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def _normalized_signal_status(value: Any) -> str:
    status = _safe_str(value).lower()
    if status in {"pending", "saved", "analyzed", "completed", "rejected"}:
        return status
    return "pending"


def _signal_status_rank(value: Any) -> int:
    status = _normalized_signal_status(value)
    ranking = {
        "pending": 0,
        "saved": 1,
        "analyzed": 2,
        "rejected": 3,
        "completed": 4,
    }
    return ranking.get(status, 0)


def merge_signal_records(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并重复 signal，尽量保留更完整字段。
    """
    merged = dict(existing)

    for key, value in incoming.items():
        if key == "raw":
            continue
        if key not in merged or _is_empty(merged.get(key)):
            if not _is_empty(value):
                merged[key] = value

    merged_raw = dict(existing.get("raw", existing))
    incoming_raw = incoming.get("raw", incoming)
    if isinstance(incoming_raw, dict):
        for key, value in incoming_raw.items():
            if key not in merged_raw or _is_empty(merged_raw.get(key)):
                if not _is_empty(value):
                    merged_raw[key] = value
    merged["raw"] = merged_raw

    if not _is_empty(incoming.get("status")):
        existing_status = merged.get("status")
        incoming_status = incoming.get("status")
        if _signal_status_rank(incoming_status) >= _signal_status_rank(existing_status):
            merged["status"] = incoming_status
    if "saved_reason" in incoming:
        merged["saved_reason"] = incoming.get("saved_reason")
    if "starred" in incoming:
        merged["starred"] = bool(incoming.get("starred"))
    if "starred_at" in incoming:
        merged["starred_at"] = incoming.get("starred_at")
    if isinstance(incoming.get("decision_trace"), list):
        merged["decision_trace"] = incoming.get("decision_trace")

    for key in [
        "why_it_matters",
        "relevance_to_projects",
        "relevance_to_career",
        "synthesized_insight",
        "insight",
        "strategy",
    ]:
        incoming_value = incoming.get(key)
        if not _is_empty(incoming_value):
            merged[key] = incoming_value

    return merged


def dedupe_signals(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged_by_identity: Dict[str, Dict[str, Any]] = {}

    for item in items:
        identity = build_signal_identity(item)
        item = dict(item)
        item["signal_id"] = identity

        if identity not in merged_by_identity:
            merged_by_identity[identity] = item
        else:
            merged_by_identity[identity] = merge_signal_records(
                merged_by_identity[identity],
                item,
            )

    return _dedupe_category_article_content(list(merged_by_identity.values()))


def sort_by_collected_at_desc(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda x: (
            x.get("raw", x).get("collected_at")
            or x.get("collected_at")
            or x.get("raw", x).get("published_at")
            or x.get("published_at")
            or ""
        ),
        reverse=True,
    )


def assign_stable_ids(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []

    for item in items:
        signal_id = item.get("signal_id") or build_signal_identity(item)
        next_item = dict(item)
        next_item["signal_id"] = signal_id
        next_item["id"] = signal_id
        normalized.append(next_item)

    return normalized


MAIN_SIGNAL_HISTORY_KEY_RE = re.compile(r"^signals/\d{4}-\d{2}-\d{2}/signals\.json$")


def _is_main_signal_history_key(key: str) -> bool:
    return bool(MAIN_SIGNAL_HISTORY_KEY_RE.match(str(key or "")))


def _is_main_signal_document_key(key: str) -> bool:
    return key == "signals/latest/signals.json" or _is_main_signal_history_key(key)


def _build_signal_id_index(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for item in items:
        signal_id = str(item.get("signal_id") or item.get("id") or "").strip()
        if signal_id:
            indexed[signal_id] = item
    return indexed


def _item_matches_signal_id(item: Dict[str, Any], signal_id: str) -> bool:
    candidate_ids = {
        str(item.get("signal_id") or "").strip(),
        str(item.get("id") or "").strip(),
    }
    try:
        candidate_ids.add(build_signal_identity(item))
    except Exception:
        pass
    return str(signal_id).strip() in candidate_ids


def _load_signals_from_local(*, max_age_seconds: int | None = None):
    print("===== TRY LOAD SIGNALS FROM LOCAL FILE =====")
    print(f"[DEBUG] local signals path = {LOCAL_SIGNALS_FILE}")
    _set_local_signals_load_status("checking")

    if not LOCAL_SIGNALS_FILE.exists():
        print("[DEBUG] local signals file does not exist")
        _set_local_signals_load_status("unavailable", "missing_file")
        return None

    if max_age_seconds is not None:
        file_age = time.time() - LOCAL_SIGNALS_FILE.stat().st_mtime
        if file_age > max_age_seconds:
            print(f"[DEBUG] local signals snapshot is stale (age={file_age:.1f}s)")
            _set_local_signals_load_status("stale", "file_mtime_too_old")
            return None

    try:
        data = read_local_json(LOCAL_SIGNALS_FILE)
        items = normalize_items(data)
        print(f"[DEBUG] local count before dedupe = {len(items)}")

        if max_age_seconds is not None:
            latest_item_timestamp = _signal_snapshot_latest_timestamp(items)
            if latest_item_timestamp is not None:
                content_age = time.time() - latest_item_timestamp
                if content_age > max_age_seconds:
                    print(f"[DEBUG] local signals snapshot content is stale (age={content_age:.1f}s)")
                    _set_local_signals_load_status("stale", "content_timestamp_too_old")
                    return None

        items = dedupe_signals(items)
        items = sort_by_collected_at_desc(items)
        items = assign_stable_ids(items)

        print(f"===== LOADED {len(items)} SIGNALS FROM LOCAL FILE =====")
        _set_local_signals_load_status("loaded")
        return items
    except Exception as e:
        print(f"[DEBUG] failed reading local signals: {e}")
        _set_local_signals_load_status("error", type(e).__name__)
        return None


def _load_signals_from_s3():
    print("===== LOAD SIGNALS FROM S3 =====")

    all_items: List[Dict[str, Any]] = []
    loaded_any_s3_payload = False

    try:
        latest_data = read_json("signals/latest/signals.json")
        latest_items = normalize_items(latest_data)
        print(f"[DEBUG] latest count = {len(latest_items)}")
        all_items.extend(latest_items)
        loaded_any_s3_payload = True
    except Exception as e:
        print(f"[DEBUG] latest load failed: {e}")

    try:
        all_signal_keys = list_json_keys("signals/")
        history_keys = [
            key
            for key in all_signal_keys
            if _is_main_signal_history_key(key)
        ]
        history_keys = sorted(history_keys, reverse=True)
        print(f"[DEBUG] history keys used = {history_keys}")

        for key in history_keys:
            try:
                history_data = read_json(key)
                history_items = normalize_items(history_data)
                print(f"[DEBUG] loaded {len(history_items)} from {key}")
                all_items.extend(history_items)
                loaded_any_s3_payload = True
            except Exception as inner_e:
                print(f"[DEBUG] failed reading {key}: {inner_e}")
    except Exception as e:
        print(f"[DEBUG] history listing failed: {e}")

    if not loaded_any_s3_payload:
        print("[DEBUG] no S3 signal payload loaded; local snapshot fallback may be used")
        return None

    print(f"[DEBUG] before dedupe total = {len(all_items)}")
    all_items = dedupe_signals(all_items)
    print(f"[DEBUG] after dedupe total = {len(all_items)}")

    all_items = sort_by_collected_at_desc(all_items)
    all_items = assign_stable_ids(all_items)

    print(f"===== LOADED {len(all_items)} SIGNALS FROM S3 =====")
    try:
        write_local_json(LOCAL_SIGNALS_FILE, {"signals": all_items})
        print(f"[DEBUG] wrote local signals snapshot to {LOCAL_SIGNALS_FILE}")
    except Exception as e:
        print(f"[DEBUG] failed writing local signals snapshot: {e}")
    return all_items


def _update_cached_signal_snapshot(signal_id: str, update_fn) -> bool:
    if isinstance(SIGNALS_CACHE.get("data"), list):
        items = [dict(item) for item in SIGNALS_CACHE["data"]]
    else:
        try:
            data = read_local_json(LOCAL_SIGNALS_FILE)
            items = normalize_items(data)
        except Exception as e:
            print(f"[DEBUG] failed loading local snapshot for cache patch: {e}")
            return False

    updated = False
    for item in items:
        if _item_matches_signal_id(item, signal_id):
            update_fn(item)
            updated = True

    if not updated:
        print(f"[DEBUG] signal not found in runtime snapshot for cache patch: {signal_id}")
        return False

    items = dedupe_signals(items)
    items = sort_by_collected_at_desc(items)
    items = assign_stable_ids(items)

    SIGNALS_CACHE["data"] = items
    SIGNALS_CACHE["by_id"] = _build_signal_id_index(items)
    SIGNALS_CACHE["last_loaded"] = time.time()

    try:
        write_local_json(LOCAL_SIGNALS_FILE, {"signals": items})
        print(f"[DEBUG] patched local signals snapshot for {signal_id}")
    except Exception as e:
        print(f"[DEBUG] failed writing patched local signals snapshot: {e}")

    return True


def _refresh_signals_after_targeted_update(signal_id: str, update_fn) -> None:
    if _update_cached_signal_snapshot(signal_id, update_fn):
        return
    load_signals(force_refresh=True)


def _extract_signal_date_key(item: Dict[str, Any]) -> Optional[str]:
    raw = item.get("raw", item)
    raw_value = (
        raw.get("collected_at")
        or item.get("collected_at")
        or raw.get("published_at")
        or item.get("published_at")
        or ""
    )
    if not raw_value:
        return None

    text = str(raw_value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.date().isoformat()
    except Exception:
        return text[:10] if len(text) >= 10 else None


def _candidate_signal_keys_for_update(signal_id: str) -> List[str]:
    candidate_keys = ["signals/latest/signals.json"]

    try:
        latest_data = read_json("signals/latest/signals.json")
        latest_items = normalize_items(latest_data)
    except Exception as e:
        print(f"[DEBUG] failed loading latest signals for targeted update: {e}")
        return candidate_keys

    matched_item = None
    for item in latest_items:
        current_signal_id = build_signal_identity(item)
        if current_signal_id == signal_id:
            matched_item = item
            break

    if matched_item:
        date_key = _extract_signal_date_key(matched_item)
        if date_key:
            candidate_keys.append(f"signals/{date_key}/signals.json")

    deduped: List[str] = []
    seen = set()
    for key in candidate_keys:
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def _all_signal_history_keys() -> List[str]:
    all_signal_keys = list_json_keys("signals/")
    return [key for key in all_signal_keys if _is_main_signal_document_key(key)]


def _update_signal_documents(
    signal_id: str,
    update_fn,
    fallback_scan_all: bool = True,
) -> List[str]:
    candidate_keys = _candidate_signal_keys_for_update(signal_id)
    attempted_keys: List[str] = []
    updated_keys: List[str] = []

    def process_keys(keys: List[str]) -> None:
        nonlocal attempted_keys, updated_keys
        for key in keys:
            if key in attempted_keys:
                continue
            attempted_keys.append(key)
            try:
                data = read_json(key)
                items, wrapped_mode = _extract_items_and_mode(data)

                file_updated = False
                for item in items:
                    current_signal_id = build_signal_identity(item)
                    if current_signal_id == signal_id:
                        update_fn(item)
                        file_updated = True

                if file_updated:
                    output = _wrap_output(data, items, wrapped_mode)
                    write_json(key, output)
                    updated_keys.append(key)
            except Exception as e:
                print(f"Failed updating {key}: {e}")

    process_keys(candidate_keys)

    if not updated_keys and fallback_scan_all:
        process_keys(_all_signal_history_keys())

    return updated_keys


def load_signals(force_refresh: bool = False, use_local: bool = False):
    global SIGNALS_CACHE
    started_at = time.time()
    use_local = _local_output_enabled(use_local)

    print("===== LOAD_SIGNALS FUNCTION CALLED =====")

    now = time.time()
    cache_age = now - SIGNALS_CACHE["last_loaded"]

    if (
        not force_refresh
        and not use_local
        and SIGNALS_CACHE["data"] is not None
        and cache_age < SIGNALS_CACHE_TTL
    ):
        print(f"===== RETURN SIGNALS FROM CACHE (age={cache_age:.1f}s) =====")
        _set_signal_load_diagnostic(
            source="runtime_cache",
            items=SIGNALS_CACHE["data"],
            started_at=started_at,
        )
        return SIGNALS_CACHE["data"]

    print("===== CACHE MISS / EXPIRED, RELOADING SIGNALS =====")

    source = "empty"
    if use_local:
        data = _load_signals_from_local()
        source = "local_snapshot"
        if data is None:
            print("[DEBUG] local mode requested but local file unavailable, fallback to S3")
            data = _load_signals_from_s3()
            source = "s3_fallback" if data is not None else "empty"
        _set_signal_load_diagnostic(source=source, items=data or [], started_at=started_at)
        return data

    if force_refresh:
        data = _load_signals_from_s3()
        source = "s3_force_refresh" if data is not None else "empty"
    else:
        data = _load_signals_from_local(max_age_seconds=LOCAL_SIGNALS_SNAPSHOT_TTL)
        if data is None:
            data = _load_signals_from_s3()
            source = "s3" if data is not None else "empty"
        else:
            source = "local_snapshot"
        if data is None:
            data = []
    SIGNALS_CACHE["data"] = data
    SIGNALS_CACHE["by_id"] = _build_signal_id_index(data)
    SIGNALS_CACHE["last_loaded"] = now
    _set_signal_load_diagnostic(source=source, items=data, started_at=started_at)
    return data


def get_signal_by_id(
    signal_id: str,
    force_refresh: bool = False,
    use_local: bool = False,
) -> Optional[Dict[str, Any]]:
    items = load_signals(force_refresh=force_refresh, use_local=use_local)
    if not force_refresh and not use_local:
        cached = SIGNALS_CACHE.get("by_id", {})
        if signal_id in cached:
            return cached[signal_id]
    for item in items:
        if str(item.get("signal_id") or item.get("id")) == str(signal_id):
            return item
    return None


def load_manual_sessions(force_refresh: bool = False):
    """
    Load manual upload sessions from S3 by scanning the whole bucket
    for likely manual/session JSON files.
    """
    if not force_refresh:
        cached = _get_cached_payload(
            MANUAL_SESSIONS_CACHE,
            ttl_seconds=JSON_CACHE_TTL,
        )
        if cached is not None:
            print("===== RETURN MANUAL SESSIONS FROM CACHE =====")
            return cached

    candidate_keys: List[str] = []

    try:
        targeted_prefixes = [
            "manual_uploads/",
            "manual_sessions/",
            "workspace/",
        ]
        candidate_keys = list_json_keys_for_prefixes(targeted_prefixes)
        candidate_keys = [
            key for key in candidate_keys
            if key.endswith(".json")
        ]

        if not candidate_keys:
            all_json_keys = list_json_keys("")
            candidate_keys = [
                key
                for key in all_json_keys
                if (
                    key.endswith(".json")
                    and (
                        "manual" in key.lower()
                        or "session" in key.lower()
                        or "upload" in key.lower()
                        or "workspace" in key.lower()
                    )
                )
            ]
        candidate_keys = sorted(candidate_keys, reverse=True)
        print(f"[DEBUG] manual candidate keys = {candidate_keys}")
    except Exception as e:
        print(f"[DEBUG] failed listing manual keys: {e}")
        return []

    all_sessions: List[Dict[str, Any]] = []

    for key in candidate_keys:
        try:
            data = read_json(key)

            if isinstance(data, list):
                dict_items = [x for x in data if isinstance(x, dict)]
                if dict_items:
                    matched = [
                        x for x in dict_items
                        if x.get("session_id") or x.get("id") or x.get("files")
                    ]
                    if matched:
                        print(f"[DEBUG] matched {len(matched)} manual sessions from list file: {key}")
                        all_sessions.extend(matched)
                continue

            if isinstance(data, dict):
                if isinstance(data.get("sessions"), list):
                    matched = [x for x in data["sessions"] if isinstance(x, dict)]
                    print(f"[DEBUG] matched {len(matched)} manual sessions from sessions file: {key}")
                    all_sessions.extend(matched)
                    continue

                if isinstance(data.get("items"), list):
                    matched = [
                        x for x in data["items"]
                        if isinstance(x, dict) and (x.get("session_id") or x.get("id") or x.get("files"))
                    ]
                    if matched:
                        print(f"[DEBUG] matched {len(matched)} manual sessions from items file: {key}")
                        all_sessions.extend(matched)
                    continue

                if data.get("session_id") or data.get("id") or data.get("files"):
                    print(f"[DEBUG] matched single manual session file: {key}")
                    all_sessions.append(data)
                    continue

        except Exception as e:
            print(f"[DEBUG] failed loading manual session file {key}: {e}")

    print(f"[DEBUG] loaded manual sessions count = {len(all_sessions)}")
    return _set_cached_payload(MANUAL_SESSIONS_CACHE, all_sessions)


def load_insights(force_refresh: bool = False, use_local: bool = False):
    if use_local and LOCAL_INSIGHTS_FILE.exists():
        print(f"===== LOADED INSIGHTS FROM LOCAL FILE: {LOCAL_INSIGHTS_FILE} =====")
        return read_local_json(LOCAL_INSIGHTS_FILE)

    if not force_refresh:
        cached = _get_cached_payload(INSIGHTS_CACHE, ttl_seconds=JSON_CACHE_TTL)
        if cached is not None:
            print("===== RETURN INSIGHTS FROM CACHE =====")
            return cached

    data = read_json("insights/latest/insights.json")
    return _set_cached_payload(INSIGHTS_CACHE, data)


def load_radar(force_refresh: bool = False, use_local: bool = False):
    if use_local and LOCAL_RADAR_FILE.exists():
        print(f"===== LOADED RADAR FROM LOCAL FILE: {LOCAL_RADAR_FILE} =====")
        return read_local_json(LOCAL_RADAR_FILE)

    if not force_refresh:
        cached = _get_cached_payload(RADAR_CACHE, ttl_seconds=JSON_CACHE_TTL)
        if cached is not None:
            print("===== RETURN RADAR FROM CACHE =====")
            return cached

    data = read_json("daily/latest/daily_radar.json")
    return _set_cached_payload(RADAR_CACHE, data)


def load_trends():
    return read_json("trends/latest/trends.json")


def _load_intelligence_file_from_local(name: str):
    filename = INTELLIGENCE_FILE_MAP[name]
    local_path = LOCAL_INTELLIGENCE_DIR / filename

    if local_path.exists():
        print(f"===== LOADED INTELLIGENCE FROM LOCAL FILE: {local_path} =====")
        return read_local_json(local_path)

    # fallback: some outputs may still exist only inside daily_radar.json
    radar = load_radar(use_local=True)
    if isinstance(radar, dict):
        return radar.get(name, [])

    return []


def _load_intelligence_file_from_s3(name: str):
    filename = INTELLIGENCE_FILE_MAP[name]

    primary_keys = [
        f"intelligence/latest/{filename}",
        f"daily/latest/{filename}",
    ]

    for key in primary_keys:
        try:
            return read_json(key)
        except Exception:
            pass

    # fallback: derive from daily radar payload if standalone file not found
    try:
        radar = read_json("daily/latest/daily_radar.json")
        if isinstance(radar, dict):
            return radar.get(name, [])
    except Exception:
        pass

    return []


def _load_agent_watch_fallback(use_local: bool = False):
    if use_local and LOCAL_AGENT_WATCH_SMOKE_TEST_FILE.exists():
        try:
            payload = read_local_json(LOCAL_AGENT_WATCH_SMOKE_TEST_FILE)
            if isinstance(payload, dict):
                return payload.get("agent_watch", {}) or {}
        except Exception:
            pass

    try:
        payload = read_json("daily/latest/agent_watch_smoke_test.json")
        if isinstance(payload, dict):
            return payload.get("agent_watch", {}) or {}
    except Exception:
        pass

    return {}


def _derive_friction_summary(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _sort_key(item: Dict[str, Any]) -> tuple[float, float, str]:
        try:
            primary = float(item.get("friction_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("pain_severity_score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    runtime_sources = sorted(
        {
            str(item.get("source") or "").strip().lower()
            for item in signals
            if str(item.get("source") or "").strip()
        }
    )

    top_signals = sorted(signals, key=_sort_key, reverse=True)[:3]
    highlights: List[Dict[str, Any]] = []

    for item in top_signals:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        highlights.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "friction_subtopic": item.get("friction_subtopic"),
                "friction_score": item.get("friction_score"),
                "pain_severity_score": item.get("pain_severity_score"),
                "ecosystem_relevance_score": item.get("ecosystem_relevance_score"),
                "repo_name": metadata.get("repo_name"),
                "matched_keywords": metadata.get("matched_keywords", []),
            }
        )

    return {
        "signal_count": len(signals),
        "top_signal_count": len(highlights),
        "runtime_sources": runtime_sources,
        "highlights": highlights,
    }


def _load_friction_signals_fallback(use_local: bool = False) -> Dict[str, Any]:
    payload: Any = None

    if use_local and LOCAL_FRICTION_SIGNALS_FILE.exists():
        try:
            payload = read_local_json(LOCAL_FRICTION_SIGNALS_FILE)
        except Exception:
            payload = None
    elif not use_local:
        for key in (
            "signals/latest/friction_signals.json",
            "daily/latest/friction_signals.json",
        ):
            try:
                payload = read_json(key)
                break
            except Exception:
                continue

    if isinstance(payload, dict):
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        return _derive_friction_summary([item for item in signals if isinstance(item, dict)])

    return {}


def _needs_agent_watch_fallback(summary: Any) -> bool:
    if not isinstance(summary, dict):
        return True

    signal_count = summary.get("signal_count")
    top_signal_count = summary.get("top_signal_count")
    runtime_sources = summary.get("runtime_sources")
    highlights = summary.get("highlights")

    return (
        int(signal_count or 0) == 0
        and int(top_signal_count or 0) == 0
        and not runtime_sources
        and not highlights
    )


def _needs_friction_fallback(summary: Any) -> bool:
    if not isinstance(summary, dict):
        return True

    signal_count = summary.get("signal_count")
    top_signal_count = summary.get("top_signal_count")
    runtime_sources = summary.get("runtime_sources")
    highlights = summary.get("highlights")

    return (
        int(signal_count or 0) == 0
        and int(top_signal_count or 0) == 0
        and not runtime_sources
        and not highlights
    )


def _derive_agent_watch_summary(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _sort_key(item: Dict[str, Any]) -> tuple[float, float, str]:
        try:
            primary = float(item.get("agent_watch_score") or 0.0)
        except Exception:
            primary = 0.0
        try:
            secondary = float(item.get("score") or 0.0)
        except Exception:
            secondary = 0.0
        published_at = str(item.get("published_at") or "")
        return (primary, secondary, published_at)

    runtime_sources = sorted(
        {
            str(item.get("source") or "").strip().lower()
            for item in signals
            if str(item.get("source") or "").strip()
        }
    )

    top_signals = sorted(signals, key=_sort_key, reverse=True)[:3]
    highlights: List[Dict[str, Any]] = []

    for item in top_signals:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        highlights.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "agent_subtopic": item.get("agent_subtopic"),
                "agent_watch_score": item.get("agent_watch_score"),
                "repo_stars": metadata.get("repo_stars"),
                "language": metadata.get("language"),
                "matched_keywords": metadata.get("matched_keywords", []),
            }
        )

    return {
        "signal_count": len(signals),
        "top_signal_count": len(highlights),
        "runtime_sources": runtime_sources,
        "highlights": highlights,
    }


def _merge_agent_watch_summary(
    signals: List[Dict[str, Any]],
    payload_summary: Optional[Dict[str, Any]],
    fallback_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    derived_summary = _derive_agent_watch_summary(signals)
    summary: Dict[str, Any] = {}

    if isinstance(fallback_summary, dict):
        summary.update(fallback_summary)
    if isinstance(payload_summary, dict):
        summary.update(payload_summary)

    for key, value in derived_summary.items():
        if _is_empty(summary.get(key)):
            summary[key] = value

    return summary


def _load_agent_watch_repo_snapshot_history(
    use_local: bool = False,
    *,
    include_history: bool = True,
) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []

    if use_local:
        if LOCAL_AGENT_WATCH_REPO_SNAPSHOTS_FILE.exists():
            try:
                payload = read_local_json(LOCAL_AGENT_WATCH_REPO_SNAPSHOTS_FILE)
                if isinstance(payload, dict) and isinstance(payload.get("items"), list):
                    snapshots.extend([item for item in payload["items"] if isinstance(item, dict)])
            except Exception:
                return []
        return snapshots

    try:
        latest_payload = read_json("signals/latest/agent_watch_repo_snapshots.json")
        if isinstance(latest_payload, dict) and isinstance(latest_payload.get("items"), list):
            snapshots.extend([item for item in latest_payload["items"] if isinstance(item, dict)])
    except Exception:
        pass

    if not include_history:
        return snapshots

    try:
        history_keys = [
            key
            for key in list_json_keys("signals/")
            if key.endswith("agent_watch_repo_snapshots.json") and "/latest/" not in key
        ]
        for key in sorted(history_keys, reverse=True):
            try:
                payload = read_json(key)
                if isinstance(payload, dict) and isinstance(payload.get("items"), list):
                    snapshots.extend([item for item in payload["items"] if isinstance(item, dict)])
            except Exception:
                continue
    except Exception:
        pass

    return snapshots


def _load_agent_watch_tracking_state(use_local: bool = False) -> Dict[str, Any]:
    if use_local:
        if LOCAL_AGENT_WATCH_TRACKING_STATE_FILE.exists():
            try:
                payload = read_local_json(LOCAL_AGENT_WATCH_TRACKING_STATE_FILE)
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}
        return {}

    for key in (
        "signals/latest/agent_watch_tracking_state.json",
        "daily/latest/agent_watch_tracking_state.json",
    ):
        try:
            payload = read_json(key)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            continue

    return {}


def _build_agent_watch_tracking_state_index(use_local: bool = False) -> Dict[str, Dict[str, Any]]:
    payload = _load_agent_watch_tracking_state(use_local=use_local)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    tracking_index: Dict[str, Dict[str, Any]] = {}

    def _preferred(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        entity_id = _safe_str(item.get("entity_id") or item.get("canonical_url")).lower()
        if not entity_id:
            continue

        tracking_index[entity_id] = {
            **item,
            "first_seen": _preferred(item.get("first_seen_at"), item.get("first_seen")),
            "last_seen": _preferred(item.get("last_seen_at"), item.get("last_seen")),
            "days_observed": _preferred(item.get("seen_days"), item.get("days_observed")),
            "latest_score": _preferred(item.get("current_score"), item.get("latest_score")),
            "previous_score": item.get("previous_score"),
            "score_change": _preferred(item.get("score_delta_1d"), item.get("score_change")),
        }

    return tracking_index


def _build_agent_watch_tracking_index(use_local: bool = False) -> Dict[str, Dict[str, Any]]:
    state_index = _build_agent_watch_tracking_state_index(use_local=use_local)
    if state_index:
        return state_index

    snapshots = _load_agent_watch_repo_snapshot_history(use_local=use_local)
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for item in snapshots:
        entity_id = _safe_str(item.get("entity_id") or item.get("canonical_url")).lower()
        if not entity_id:
            continue
        grouped.setdefault(entity_id, []).append(item)

    tracking_index: Dict[str, Dict[str, Any]] = {}

    for entity_id, items in grouped.items():
        sorted_items = sorted(
            items,
            key=lambda item: _safe_str(item.get("captured_at") or item.get("published_at")),
        )
        if not sorted_items:
            continue

        first_item = sorted_items[0]
        latest_item = sorted_items[-1]
        previous_item = sorted_items[-2] if len(sorted_items) > 1 else None

        first_seen = _safe_str(first_item.get("captured_at") or first_item.get("published_at"))
        last_seen = _safe_str(latest_item.get("captured_at") or latest_item.get("published_at"))

        latest_score = latest_item.get("agent_watch_score")
        previous_score = previous_item.get("agent_watch_score") if previous_item else None

        try:
            latest_score_value = float(latest_score) if latest_score not in (None, "") else None
        except Exception:
            latest_score_value = None
        try:
            previous_score_value = float(previous_score) if previous_score not in (None, "") else None
        except Exception:
            previous_score_value = None

        score_change: Optional[float] = None
        if latest_score_value is not None and previous_score_value is not None:
            score_change = round(latest_score_value - previous_score_value, 3)

        observed_days = len(
            {
                _safe_str(item.get("captured_at"))[:10]
                for item in sorted_items
                if _safe_str(item.get("captured_at"))
            }
        )

        tracking_index[entity_id] = {
            "first_seen": first_seen or None,
            "last_seen": last_seen or None,
            "days_observed": observed_days or len(sorted_items),
            "observations": len(sorted_items),
            "latest_score": latest_score_value,
            "previous_score": previous_score_value,
            "score_change": score_change,
        }

    for entity_id, state_tracking in _build_agent_watch_tracking_state_index(use_local=use_local).items():
        tracking_index[entity_id] = {
            **tracking_index.get(entity_id, {}),
            **state_tracking,
        }

    return tracking_index


def _load_friction_tracking_state(use_local: bool = False) -> Dict[str, Any]:
    if use_local:
        if LOCAL_FRICTION_TRACKING_STATE_FILE.exists():
            try:
                payload = read_local_json(LOCAL_FRICTION_TRACKING_STATE_FILE)
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}
        return {}

    for key in (
        "signals/latest/friction_tracking_state.json",
        "daily/latest/friction_tracking_state.json",
    ):
        try:
            payload = read_json(key)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            continue

    return {}


def _build_friction_tracking_index(use_local: bool = False) -> Dict[str, Dict[str, Any]]:
    payload = _load_friction_tracking_state(use_local=use_local)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    tracking_index: Dict[str, Dict[str, Any]] = {}

    def _preferred(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        entity_id = _safe_str(item.get("entity_id") or item.get("canonical_url")).lower()
        if not entity_id:
            continue

        tracking_index[entity_id] = {
            **item,
            "first_seen": _preferred(item.get("first_seen_at"), item.get("first_seen")),
            "last_seen": _preferred(item.get("last_seen_at"), item.get("last_seen")),
            "days_observed": _preferred(item.get("seen_days"), item.get("days_observed")),
            "latest_score": _preferred(item.get("current_score"), item.get("latest_score")),
            "previous_score": item.get("previous_score"),
            "score_change": _preferred(item.get("score_delta_1d"), item.get("score_change")),
        }

    return tracking_index


def _load_agent_watch_repo_profiles(use_local: bool = False) -> Dict[str, Dict[str, Any]]:
    payload: Any = None

    if use_local:
        if LOCAL_AGENT_WATCH_REPO_PROFILES_FILE.exists():
            try:
                payload = read_local_json(LOCAL_AGENT_WATCH_REPO_PROFILES_FILE)
            except Exception:
                payload = None
    else:
        for key in (
            "signals/latest/agent_watch_repo_profiles.json",
            "daily/latest/agent_watch_repo_profiles.json",
        ):
            try:
                payload = read_json(key)
                break
            except Exception:
                continue

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return {}

    profile_index: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        entity_id = _safe_str(item.get("entity_id") or item.get("canonical_url")).lower()
        if not entity_id:
            continue
        profile_index[entity_id] = item

    return profile_index


def _fallback_agent_watch_repo_profile(item: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    title = _safe_str(item.get("title"))
    summary = _safe_str(item.get("summary"))
    subtopic = _safe_str(item.get("agent_subtopic")) or "agent_repo"
    repo_name = _safe_str(metadata.get("repo_name"))
    subject = repo_name or title or "This repo"

    return {
        "repo_summary": summary or f"{subject} is currently tracked in Agent Watch.",
        "what_it_does": summary or f"{subject} appears to be an {subtopic} project in the AI agent ecosystem.",
        "why_it_matters": f"{subject} is showing enough signal strength to enter the current watchlist.",
        "project_fit": f"Review {subject} for ideas, implementation patterns, and relevance to your current AI Radar work.",
        "suggested_use_cases": [
            "Study the repo positioning and implementation approach.",
            "Compare it with your current AI Radar intelligence features.",
        ],
        "risks": [
            "This fallback profile is based on limited repo surface data only.",
        ],
        "confidence": "low",
    }


def _build_agent_watch_profile_input(item: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "url": item.get("url", ""),
        "source": item.get("source", ""),
        "source_type": item.get("source_type", ""),
        "published_at": item.get("published_at", ""),
        "agent_subtopic": item.get("agent_subtopic"),
        "agent_watch_score": item.get("agent_watch_score"),
        "repo_name": metadata.get("repo_name"),
        "repo_stars": metadata.get("repo_stars"),
        "language": metadata.get("language"),
        "matched_keywords": metadata.get("matched_keywords", []),
        "tags": metadata.get("tags", []),
        "hn_points": metadata.get("hn_points"),
        "hn_comments": metadata.get("hn_comments"),
        "product_hunt_votes": metadata.get("product_hunt_votes"),
    }


def _generate_agent_watch_repo_profile(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    canonical_url = _safe_str(metadata.get("repo_url") or item.get("url"))
    entity_id = canonical_url.lower()
    generated_at = datetime.utcnow().isoformat()
    normalized_profile: Optional[Dict[str, Any]] = None
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    policy_metadata: Optional[Dict[str, Any]] = None

    profile_input = _build_agent_watch_profile_input(item, metadata)

    try:
        parsed, route, policy_metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="strategy",
                query=str(item.get("title") or ""),
                user_visible=True,
                importance_score=85,
                requires_traceability=True,
                source_count=1,
                metadata={"source_count": 1, "context_label": "agent_watch_repo_candidate"},
            ),
            system_prompt=(
                "You are an AI Radar repo intelligence analyst. "
                "Read the repo surface data carefully and return practical, "
                "specific judgments. Prefer concrete product and implementation "
                "interpretation over hype. Be honest about uncertainty."
            ),
            user_prompt=(
                "Analyze this tracked agent repo candidate and return JSON with exactly these keys:\n"
                "repo_summary\n"
                "what_it_does\n"
                "why_it_matters\n"
                "project_fit\n"
                "suggested_use_cases\n"
                "risks\n"
                "confidence\n\n"
                "Rules:\n"
                "- repo_summary, what_it_does, why_it_matters, project_fit must be short but specific strings.\n"
                "- suggested_use_cases and risks must be arrays of short strings.\n"
                "- confidence must be one of: low, medium, high.\n"
                "- project_fit should explicitly consider personal project usefulness for AI Radar.\n"
                "- If the repo surface is ambiguous, say so clearly.\n\n"
                f"Repo candidate:\n{json.dumps(profile_input, ensure_ascii=False, indent=2)}"
            ),
            metadata={"source_count": 1, "context_label": "agent_watch_repo_candidate"},
            executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_json_task(
                task_type=effective_task_type,
                temperature=0.2,
                max_tokens=1200,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                system_prompt=patched_system_prompt,
                user_prompt=patched_user_prompt,
            ),
        )
        normalized_profile = {
            "repo_summary": _safe_str(parsed.get("repo_summary")),
            "what_it_does": _safe_str(parsed.get("what_it_does")),
            "why_it_matters": _safe_str(parsed.get("why_it_matters")),
            "project_fit": _safe_str(parsed.get("project_fit")),
            "suggested_use_cases": [
                _safe_str(value)
                for value in (parsed.get("suggested_use_cases") or [])
                if _safe_str(value)
            ],
            "risks": [
                _safe_str(value)
                for value in (parsed.get("risks") or [])
                if _safe_str(value)
            ],
            "confidence": _safe_str(parsed.get("confidence")) or "medium",
        }
        provider_used = route.provider
        model_used = route.model
    except Exception as e:
        print(f"[WARN] Manual agent watch repo profile failed for '{item.get('title', '')[:80]}': {e}")

    if not normalized_profile:
        normalized_profile = _fallback_agent_watch_repo_profile(item, metadata)

    return {
        "entity_id": entity_id,
        "generated_at": generated_at,
        "title": item.get("title", ""),
        "canonical_url": canonical_url,
        "source": item.get("source", ""),
        "agent_subtopic": item.get("agent_subtopic"),
        "provider_used": provider_used,
        "model_used": model_used,
        "policy_metadata": policy_metadata,
        **normalized_profile,
    }


def _persist_agent_watch_repo_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any]
    if LOCAL_AGENT_WATCH_REPO_PROFILES_FILE.exists():
        try:
            payload = read_local_json(LOCAL_AGENT_WATCH_REPO_PROFILES_FILE)
        except Exception:
            payload = {}
    else:
        payload = {}

    existing_items = payload.get("items") if isinstance(payload, dict) and isinstance(payload.get("items"), list) else []
    normalized_entity_id = _safe_str(profile.get("entity_id")).lower()
    next_items: List[Dict[str, Any]] = []
    replaced = False

    for item in existing_items:
        if not isinstance(item, dict):
            continue
        item_entity_id = _safe_str(item.get("entity_id") or item.get("canonical_url")).lower()
        if item_entity_id == normalized_entity_id:
            next_items.append(profile)
            replaced = True
        else:
            next_items.append(item)

    if not replaced:
        next_items.append(profile)

    next_payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(next_items),
        "items": next_items,
    }

    write_local_json(LOCAL_AGENT_WATCH_REPO_PROFILES_FILE, next_payload)

    try:
        write_json("signals/latest/agent_watch_repo_profiles.json", next_payload)
    except Exception as e:
        print(f"[WARN] Failed writing latest agent watch repo profiles to S3: {e}")

    try:
        today = datetime.utcnow().date().isoformat()
        write_json(f"signals/{today}/agent_watch_repo_profiles.json", next_payload)
    except Exception as e:
        print(f"[WARN] Failed writing dated agent watch repo profiles to S3: {e}")

    _invalidate_simple_cache(AGENT_WATCH_CACHE)
    _invalidate_simple_cache(RADAR_INTELLIGENCE_CACHE)
    _invalidate_simple_cache(RADAR_CACHE)

    return next_payload


def _load_friction_signal_profiles(use_local: bool = False) -> Dict[str, Dict[str, Any]]:
    payload: Any = None

    if use_local:
        if LOCAL_FRICTION_SIGNAL_PROFILES_FILE.exists():
            try:
                payload = read_local_json(LOCAL_FRICTION_SIGNAL_PROFILES_FILE)
            except Exception:
                payload = None
    else:
        for key in (
            "signals/latest/friction_signal_profiles.json",
            "daily/latest/friction_signal_profiles.json",
        ):
            try:
                payload = read_json(key)
                break
            except Exception:
                continue

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return {}

    profile_index: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        entity_id = _safe_str(item.get("entity_id") or item.get("url") or item.get("title")).lower()
        if not entity_id:
            continue
        profile_index[entity_id] = item

    return profile_index


def load_agent_watch(force_refresh: bool = False, use_local: bool = False):
    use_local = _local_output_enabled(use_local)

    if not use_local and not force_refresh:
        cached = _get_cached_payload(
            AGENT_WATCH_CACHE,
            ttl_seconds=JSON_CACHE_TTL,
        )
        if cached is not None:
            print("===== RETURN AGENT WATCH FROM CACHE =====")
            return cached

    payload: Any = None

    if use_local and LOCAL_AGENT_WATCH_FILE.exists():
        try:
            payload = read_local_json(LOCAL_AGENT_WATCH_FILE)
        except Exception:
            payload = None
    elif not use_local:
        for key in (
            "signals/latest/agent_watch_signals.json",
            "daily/latest/agent_watch_signals.json",
        ):
            try:
                payload = read_json(key)
                break
            except Exception:
                continue

    fallback_summary = _load_agent_watch_fallback(use_local=use_local)

    if payload is None:
        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "source": "agent_watch_fallback",
            "count": 0,
            "signals": [],
            "summary": fallback_summary,
        }
    elif isinstance(payload, dict):
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        tracking_index = _build_agent_watch_tracking_index(use_local=use_local)
        profile_index = _load_agent_watch_repo_profiles(use_local=use_local)
        enriched_signals: List[Dict[str, Any]] = []

        for item in signals:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            entity_id = _safe_str(metadata.get("repo_url") or item.get("url")).lower()
            tracking = tracking_index.get(entity_id)
            profile = profile_index.get(entity_id)
            enriched_item = dict(item)
            if tracking:
                enriched_item["tracking"] = tracking
            if profile:
                enriched_item["profile"] = profile
            enriched_signals.append(enriched_item)

        payload = {
            **payload,
            "signals": enriched_signals,
            "count": payload.get("count") if not _is_empty(payload.get("count")) else len(enriched_signals),
            "summary": _merge_agent_watch_summary(
                enriched_signals,
                None
                if _needs_agent_watch_fallback(payload.get("summary"))
                else payload.get("summary")
                if isinstance(payload.get("summary"), dict)
                else None,
                fallback_summary,
            ),
        }

    if use_local:
        return payload

    return _set_cached_payload(AGENT_WATCH_CACHE, payload)


def load_agent_watch_detail(
    entity_id: str,
    *,
    force_refresh: bool = False,
    use_local: bool = False,
) -> Dict[str, Any]:
    use_local = _local_output_enabled(use_local)
    normalized_entity_id = _safe_str(entity_id).lower()
    if not normalized_entity_id:
        return {"entity_id": None, "found": False, "message": "Missing entity_id."}

    payload = load_agent_watch(force_refresh=force_refresh, use_local=use_local)
    signals = payload.get("signals") if isinstance(payload, dict) else []
    current_signal: Optional[Dict[str, Any]] = None
    related_signals: List[Dict[str, Any]] = []

    if isinstance(signals, list):
        for item in signals:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            current_entity_id = _safe_str(metadata.get("repo_url") or item.get("url")).lower()
            if current_entity_id != normalized_entity_id:
                continue
            related_signals.append(item)
            if current_signal is None:
                current_signal = item

    profile = (
        current_signal.get("profile")
        if isinstance(current_signal, dict) and isinstance(current_signal.get("profile"), dict)
        else None
    )
    tracking = (
        current_signal.get("tracking")
        if isinstance(current_signal, dict) and isinstance(current_signal.get("tracking"), dict)
        else None
    )

    profile_index: Dict[str, Dict[str, Any]] = {}
    if profile is None:
        profile_index = _load_agent_watch_repo_profiles(use_local=use_local)
        profile = profile_index.get(normalized_entity_id)

    if tracking is None:
        tracking_index = _build_agent_watch_tracking_state_index(use_local=use_local)
        tracking = tracking_index.get(normalized_entity_id)

    snapshot_history = [
        item
        for item in _load_agent_watch_repo_snapshot_history(use_local=use_local, include_history=False)
        if _safe_str(item.get("entity_id") or item.get("canonical_url")).lower() == normalized_entity_id
    ]
    snapshot_history = sorted(
        snapshot_history,
        key=lambda item: _safe_str(item.get("captured_at") or item.get("published_at")),
    )

    if current_signal is None and not profile and not tracking and not snapshot_history:
        return {
            "entity_id": normalized_entity_id,
            "found": False,
            "message": "No tracked agent watch repo found for this entity.",
        }

    metadata = current_signal.get("metadata") if isinstance(current_signal, dict) and isinstance(current_signal.get("metadata"), dict) else {}

    return {
        "entity_id": normalized_entity_id,
        "found": True,
        "title": (current_signal or {}).get("title") or (profile or {}).get("title"),
        "canonical_url": _safe_str(metadata.get("repo_url") or (current_signal or {}).get("url") or (profile or {}).get("canonical_url")),
        "source": (current_signal or {}).get("source") or (profile or {}).get("source"),
        "agent_subtopic": (current_signal or {}).get("agent_subtopic") or (profile or {}).get("agent_subtopic"),
        "summary": (current_signal or {}).get("summary"),
        "published_at": (current_signal or {}).get("published_at"),
        "agent_watch_score": (current_signal or {}).get("agent_watch_score"),
        "metadata": metadata,
        "tracking": tracking,
        "profile": profile,
        "history": snapshot_history,
        "related_signals": related_signals,
    }


def analyze_agent_watch_repo(
    entity_id: str,
    *,
    use_local: bool = False,
) -> Dict[str, Any]:
    use_local = _local_output_enabled(use_local)
    normalized_entity_id = _safe_str(entity_id).lower()
    if not normalized_entity_id:
        return {"entity_id": None, "ok": False, "message": "Missing entity_id."}

    payload = load_agent_watch(force_refresh=True, use_local=use_local)
    signals = payload.get("signals") if isinstance(payload, dict) and isinstance(payload.get("signals"), list) else []

    target_signal: Optional[Dict[str, Any]] = None
    for item in signals:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        current_entity_id = _safe_str(metadata.get("repo_url") or item.get("url")).lower()
        if current_entity_id == normalized_entity_id:
            target_signal = item
            break

    if target_signal is None:
        return {
            "entity_id": normalized_entity_id,
            "ok": False,
            "message": "No tracked agent watch repo found for this entity.",
        }

    profile = _generate_agent_watch_repo_profile(target_signal)
    _persist_agent_watch_repo_profile(profile)
    detail = load_agent_watch_detail(
        normalized_entity_id,
        force_refresh=True,
        use_local=use_local,
    )

    return {
        "ok": True,
        "entity_id": normalized_entity_id,
        "message": "Agent watch repo analysis generated successfully.",
        "profile": profile,
        "detail": detail,
    }


def load_friction_signals(force_refresh: bool = False, use_local: bool = False):
    use_local = _local_output_enabled(use_local)

    if not use_local and not force_refresh:
        cached = _get_cached_payload(
            FRICTION_SIGNALS_CACHE,
            ttl_seconds=JSON_CACHE_TTL,
        )
        if cached is not None:
            print("===== RETURN FRICTION SIGNALS FROM CACHE =====")
            return cached

    payload: Any = None

    if use_local and LOCAL_FRICTION_SIGNALS_FILE.exists():
        try:
            payload = read_local_json(LOCAL_FRICTION_SIGNALS_FILE)
        except Exception:
            payload = None
    elif not use_local:
        for key in (
            "signals/latest/friction_signals.json",
            "daily/latest/friction_signals.json",
        ):
            try:
                payload = read_json(key)
                break
            except Exception:
                continue

    fallback_summary = _load_friction_signals_fallback(use_local=use_local)
    profile_index = _load_friction_signal_profiles(use_local=use_local)
    tracking_index = _build_friction_tracking_index(use_local=use_local)

    if payload is None:
        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "source": "friction_signals_fallback",
            "count": 0,
            "signals": [],
            "summary": fallback_summary,
        }
    elif isinstance(payload, dict):
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        enriched_signals: List[Dict[str, Any]] = []
        for item in signals:
            if not isinstance(item, dict):
                continue
            entity_id = _safe_str(item.get("url") or item.get("title")).lower()
            profile = profile_index.get(entity_id)
            tracking = tracking_index.get(entity_id)
            enriched_item = dict(item)
            if profile:
                enriched_item["profile"] = profile
            if tracking:
                enriched_item["tracking"] = tracking
            enriched_signals.append(enriched_item)

        summary_payload = fallback_summary if _needs_friction_fallback(payload.get("summary")) else payload.get("summary")
        if not isinstance(summary_payload, dict):
            summary_payload = fallback_summary if isinstance(fallback_summary, dict) else {}

        highlights = summary_payload.get("highlights") if isinstance(summary_payload.get("highlights"), list) else []
        enriched_highlights: List[Dict[str, Any]] = []
        for item in highlights:
            if not isinstance(item, dict):
                continue
            entity_id = _safe_str(item.get("url") or item.get("title")).lower()
            profile = profile_index.get(entity_id)
            tracking = tracking_index.get(entity_id)
            enriched_item = dict(item)
            if profile:
                enriched_item["profile"] = profile
            if tracking:
                enriched_item["tracking"] = tracking
            enriched_highlights.append(enriched_item)

        payload = {
            **payload,
            "signals": enriched_signals,
            "count": payload.get("count") if not _is_empty(payload.get("count")) else len(enriched_signals),
            "summary": {
                **summary_payload,
                "highlights": enriched_highlights,
            },
        }

    if use_local:
        return payload

    return _set_cached_payload(FRICTION_SIGNALS_CACHE, payload)


def load_friction_signal_detail(
    entity_id: str,
    *,
    force_refresh: bool = False,
    use_local: bool = False,
) -> Dict[str, Any]:
    use_local = _local_output_enabled(use_local)
    normalized_entity_id = _safe_str(entity_id).lower()
    if not normalized_entity_id:
        return {"entity_id": None, "found": False, "message": "Missing entity_id."}

    payload = load_friction_signals(force_refresh=force_refresh, use_local=use_local)
    signals = payload.get("signals") if isinstance(payload, dict) and isinstance(payload.get("signals"), list) else []
    summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}
    fallback_items = summary.get("highlights") if isinstance(summary.get("highlights"), list) else []
    candidates = signals if signals else fallback_items

    current_signal: Optional[Dict[str, Any]] = None
    related_signals: List[Dict[str, Any]] = []

    for item in candidates:
        if not isinstance(item, dict):
            continue
        current_entity_key = _safe_str(item.get("url") or item.get("title")).lower()
        if current_entity_key != normalized_entity_id:
            continue
        related_signals.append(item)
        if current_signal is None:
            current_signal = item

    if current_signal is None:
        return {
            "entity_id": normalized_entity_id,
            "found": False,
            "message": "No friction signal found for this entity.",
        }

    metadata = current_signal.get("metadata") if isinstance(current_signal.get("metadata"), dict) else {}
    profile_index = _load_friction_signal_profiles(use_local=use_local)
    tracking_index = _build_friction_tracking_index(use_local=use_local)
    matched_keywords = current_signal.get("matched_keywords")
    if not isinstance(matched_keywords, list):
        matched_keywords = metadata.get("matched_keywords") if isinstance(metadata.get("matched_keywords"), list) else []
    profile = profile_index.get(normalized_entity_id)
    tracking = tracking_index.get(normalized_entity_id)

    return {
        "entity_id": normalized_entity_id,
        "found": True,
        "title": current_signal.get("title"),
        "url": current_signal.get("url"),
        "source": current_signal.get("source"),
        "published_at": current_signal.get("published_at"),
        "summary": current_signal.get("summary"),
        "friction_subtopic": current_signal.get("friction_subtopic"),
        "friction_score": current_signal.get("friction_score"),
        "pain_severity_score": current_signal.get("pain_severity_score"),
        "ecosystem_relevance_score": current_signal.get("ecosystem_relevance_score"),
        "repo_name": current_signal.get("repo_name") or metadata.get("repo_name"),
        "matched_keywords": matched_keywords,
        "metadata": metadata,
        "tracking": tracking,
        "profile": profile,
        "related_signals": related_signals,
    }


def load_radar_intelligence(force_refresh: bool = False, use_local: bool = False):
    use_local = _local_output_enabled(use_local)

    if not use_local and not force_refresh:
        cached = _get_cached_payload(
            RADAR_INTELLIGENCE_CACHE,
            ttl_seconds=JSON_CACHE_TTL,
        )
        if cached is not None:
            print("===== RETURN RADAR INTELLIGENCE FROM CACHE =====")
            return cached

    payload = {}

    for name in INTELLIGENCE_FILE_MAP:
        if use_local:
            payload[name] = _load_intelligence_file_from_local(name)
        else:
            payload[name] = _load_intelligence_file_from_s3(name)

    payload["agent_watch"] = load_agent_watch(
        force_refresh=force_refresh,
        use_local=use_local,
    )
    payload["friction_signals"] = load_friction_signals(
        force_refresh=force_refresh,
        use_local=use_local,
    )

    if use_local:
        return payload

    return _set_cached_payload(RADAR_INTELLIGENCE_CACHE, payload)


def debug_list_keys(prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    print(f"===== DEBUG LISTING PREFIX: {prefix} =====")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for item in page.get("Contents", []):
            print(item["Key"])


def write_json(key: str, data):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _extract_items_and_mode(data):
    if isinstance(data, dict):
        if "items" in data:
            return data.get("items", []), "items"
        if "signals" in data:
            return data.get("signals", []), "signals"
        return [], "items"
    return data, "list"


def _wrap_output(original_data, items, wrapped_mode):
    if wrapped_mode == "items":
        output = dict(original_data) if isinstance(original_data, dict) else {}
        output["items"] = items
        return output
    if wrapped_mode == "signals":
        output = dict(original_data) if isinstance(original_data, dict) else {}
        output["signals"] = items
        return output
    return items


def update_signal_status_by_signal_id(
    signal_id: str,
    new_status: str,
    saved_reason: Optional[str] = None,
):
    def apply_status_update(item: Dict[str, Any]) -> None:
        previous_status = _normalized_signal_status(item.get("status"))
        item.update(
            {
                "status": new_status,
                "saved_reason": saved_reason if new_status == "saved" else None,
            }
        )
        append_decision_trace_event(
            item,
            build_decision_trace_event(
                event_type=status_event_type(new_status),
                actor="admin",
                route="/signals/update-status",
                status_before=previous_status,
                status_after=new_status,
                support={"saved_reason": saved_reason} if new_status == "saved" and saved_reason else None,
            ),
        )

    updated_keys = _update_signal_documents(
        signal_id=signal_id,
        update_fn=apply_status_update,
    )

    if not updated_keys:
        raise ValueError("Signal not found in any signals.json file")

    _refresh_signals_after_targeted_update(signal_id, apply_status_update)
    _invalidate_simple_cache(RADAR_CACHE)
    _invalidate_simple_cache(RADAR_INTELLIGENCE_CACHE)

    return {
        "message": "Signal status updated successfully.",
        "signal_id": signal_id,
        "status": new_status,
        "saved_reason": saved_reason if new_status == "saved" else None,
        "decision_trace_event": status_event_type(new_status),
        "updated_keys": updated_keys,
    }


def update_signal_star_by_signal_id(
    signal_id: str,
    starred: bool,
    starred_at: Optional[str] = None,
):
    next_starred_at = starred_at if starred else None

    def apply_star_update(item: Dict[str, Any]) -> None:
        item["starred"] = starred
        item["starred_at"] = next_starred_at

    updated_keys = _update_signal_documents(
        signal_id=signal_id,
        update_fn=apply_star_update,
    )

    if not updated_keys:
        raise ValueError("Signal not found in any signals.json file")

    _refresh_signals_after_targeted_update(signal_id, apply_star_update)
    _invalidate_simple_cache(RADAR_CACHE)
    _invalidate_simple_cache(RADAR_INTELLIGENCE_CACHE)

    return {
        "message": "Signal star updated successfully.",
        "signal_id": signal_id,
        "starred": starred,
        "starred_at": next_starred_at,
        "updated_keys": updated_keys,
    }


def update_signal_insight_by_signal_id(
    signal_id: str,
    insight_fields: Dict[str, Any],
    new_status: str = "analyzed",
):
    why_it_matters = (insight_fields.get("why_it_matters") or "").strip()
    relevance_to_projects = (insight_fields.get("relevance_to_projects") or "").strip()
    relevance_to_career = (insight_fields.get("relevance_to_career") or "").strip()
    synthesized_insight = (insight_fields.get("synthesized_insight") or "").strip()
    provider_used = (insight_fields.get("provider_used") or "").strip()
    model_used = (insight_fields.get("model_used") or "").strip()
    generation_mode = (insight_fields.get("generation_mode") or "").strip()
    requested_provider = (insight_fields.get("requested_provider") or "").strip()
    verification = insight_fields.get("verification")
    policy_metadata = insight_fields.get("policy_metadata")
    evidence_pack = insight_fields.get("evidence_pack")
    produced_by_model = insight_fields.get("produced_by_model")

    def apply_insight_update(item: Dict[str, Any]) -> None:
        previous_status = _normalized_signal_status(item.get("status"))
        item["why_it_matters"] = why_it_matters
        item["relevance_to_projects"] = relevance_to_projects
        item["relevance_to_career"] = relevance_to_career
        item["synthesized_insight"] = synthesized_insight
        item["insight"] = why_it_matters
        item["strategy"] = synthesized_insight
        if provider_used:
            item["provider_used"] = provider_used
        if model_used:
            item["model_used"] = model_used
        if generation_mode:
            item["generation_mode"] = generation_mode
        if requested_provider:
            item["requested_provider"] = requested_provider
        if verification is not None:
            item["verification"] = verification
        if policy_metadata is not None:
            item["policy_metadata"] = policy_metadata
        if evidence_pack is not None:
            item["evidence_pack"] = evidence_pack
        if produced_by_model is not None:
            item["produced_by_model"] = produced_by_model
        item["status"] = new_status
        item["saved_reason"] = item.get("saved_reason")
        append_decision_trace_event(
            item,
            build_decision_trace_event(
                event_type="insight_generated",
                actor="system",
                route="/signals/generate-insight",
                status_before=previous_status,
                status_after=new_status,
                support=verification_support_snapshot(verification if isinstance(verification, dict) else None),
            ),
        )

    updated_keys = _update_signal_documents(
        signal_id=signal_id,
        update_fn=apply_insight_update,
    )

    if not updated_keys:
        raise ValueError("Signal not found in any signals.json file")

    _refresh_signals_after_targeted_update(signal_id, apply_insight_update)
    _invalidate_simple_cache(INSIGHTS_CACHE)
    _invalidate_simple_cache(RADAR_CACHE)
    _invalidate_simple_cache(RADAR_INTELLIGENCE_CACHE)

    return {
        "message": "Signal insight updated successfully.",
        "signal_id": signal_id,
        "status": new_status,
        "why_it_matters": why_it_matters,
        "relevance_to_projects": relevance_to_projects,
        "relevance_to_career": relevance_to_career,
        "synthesized_insight": synthesized_insight,
        "provider_used": provider_used,
        "model_used": model_used,
        "generation_mode": generation_mode,
        "requested_provider": requested_provider,
        "verification": verification,
        "policy_metadata": policy_metadata,
        "evidence_pack": evidence_pack,
        "produced_by_model": produced_by_model,
        "updated_keys": updated_keys,
    }


def update_signal_status_by_identity(
    target_title: str,
    target_source: str,
    target_published_at: str,
    target_collected_at: str,
    new_status: str,
    saved_reason: Optional[str] = None,
):
    pseudo_item = {
        "title": target_title,
        "source": target_source,
        "published_at": target_published_at,
        "collected_at": target_collected_at,
    }
    signal_id = build_signal_identity(pseudo_item)
    return update_signal_status_by_signal_id(
        signal_id=signal_id,
        new_status=new_status,
        saved_reason=saved_reason,
    )


def update_signal_star_by_identity(
    target_title: str,
    target_source: str,
    target_published_at: str,
    target_collected_at: str,
    starred: bool,
    starred_at: Optional[str] = None,
):
    pseudo_item = {
        "title": target_title,
        "source": target_source,
        "published_at": target_published_at,
        "collected_at": target_collected_at,
    }
    signal_id = build_signal_identity(pseudo_item)
    return update_signal_star_by_signal_id(
        signal_id=signal_id,
        starred=starred,
        starred_at=starred_at,
    )
