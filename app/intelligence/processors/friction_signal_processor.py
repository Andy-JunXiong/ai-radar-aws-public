import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[3]
RAW_GITHUB_FRICTION_SIGNALS_FILE = BASE_DIR / "data" / "output" / "github_friction_signals.json"
RAW_HN_FRICTION_SIGNALS_FILE = BASE_DIR / "data" / "output" / "hackernews_friction_signals.json"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "friction_signals.json"

PAIN_KEYWORDS = [
    "bug",
    "issue",
    "problem",
    "broken",
    "friction",
    "struggle",
    "fail",
    "failure",
    "not working",
    "wrapper",
    "hallucination",
    "latency",
    "context",
]

SUBTOPIC_RULES = {
    "reliability": ["bug", "broken", "fail", "failure", "not working"],
    "observability": ["debug", "trace", "observability", "visibility"],
    "context": ["context", "memory", "long context", "retrieval"],
    "cost": ["cost", "pricing", "token", "latency"],
    "ecosystem_noise": ["wrapper", "hype", "spam", "launch"],
}


def _load_collector_payload(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
        return [item for item in payload["signals"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_source(signal: dict[str, Any], fallback_type: str) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    summary = _normalize_text(signal.get("summary")) or "Emerging AI friction signal detected."
    content = _normalize_text(signal.get("content")) or summary
    title = _normalize_text(signal.get("title"))
    url = _normalize_text(signal.get("url"))
    if not title or not url:
        return {}
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
    return {
        "title": title,
        "summary": summary,
        "content": content,
        "url": url,
        "author": _normalize_text(signal.get("author")),
        "source": _normalize_text(signal.get("source")) or fallback_type.split("_")[0],
        "source_type": _normalize_text(signal.get("source_type")) or fallback_type,
        "category": "AI Friction",
        "topic": "ai_friction",
        "signal_type": "friction",
        "published_at": _normalize_text(signal.get("published_at")) or now_iso,
        "timestamp": _normalize_text(signal.get("timestamp")) or now_iso,
        "collected_at": _normalize_text(signal.get("collected_at")) or now_iso,
        "source_weight": signal.get("source_weight", 0.7),
        "summary_length": len(summary),
        "content_length": len(content),
        "metadata": metadata,
    }


def _match_subtopic(*values: str) -> str:
    haystack = " ".join(value.lower() for value in values if value).strip()
    if not haystack:
        return "general_friction"
    best_match = "general_friction"
    best_score = 0
    for subtopic, keywords in SUBTOPIC_RULES.items():
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_match = subtopic
            best_score = score
    return best_match


def _pain_score(*values: str) -> float:
    haystack = " ".join(value.lower() for value in values if value).strip()
    if not haystack:
        return 0.35
    hits = sum(1 for keyword in PAIN_KEYWORDS if keyword in haystack)
    return min(1.0, 0.35 + hits * 0.08)


def _score_signal(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    source = _normalize_text(item.get("source")).lower()
    comments = 0
    if source == "github":
        comments = int(metadata.get("comments") or 0)
    elif source == "hackernews":
        comments = int(metadata.get("hn_comments") or 0)
    traction_score = min(1.0, 0.25 + comments / 40.0)
    pain_score = _pain_score(
        _normalize_text(item.get("title")),
        _normalize_text(item.get("summary")),
        _normalize_text(item.get("content")),
    )
    ecosystem_relevance = min(1.0, float(item.get("source_weight") or 0.6) * 0.7 + traction_score * 0.3)
    friction_score = round(pain_score * 0.6 + ecosystem_relevance * 0.4, 3)
    item["friction_subtopic"] = _match_subtopic(
        _normalize_text(item.get("title")),
        _normalize_text(item.get("summary")),
        _normalize_text(item.get("content")),
    )
    item["pain_severity_score"] = round(pain_score, 3)
    item["ecosystem_relevance_score"] = round(ecosystem_relevance, 3)
    item["friction_score"] = friction_score
    item["score"] = friction_score
    return item


def collect_normalized_friction_signals() -> list[dict[str, Any]]:
    raw_signals = []
    raw_signals.extend(_load_collector_payload(RAW_GITHUB_FRICTION_SIGNALS_FILE))
    raw_signals.extend(_load_collector_payload(RAW_HN_FRICTION_SIGNALS_FILE))

    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for signal in raw_signals:
        fallback_type = _normalize_text(signal.get("source_type")) or "friction"
        item = _normalize_source(signal, fallback_type)
        if not item:
            continue
        dedupe_key = _normalize_text(item.get("url")).lower()
        if dedupe_key and dedupe_key in seen_urls:
            continue
        if dedupe_key:
            seen_urls.add(dedupe_key)
        normalized.append(_score_signal(item))

    return sorted(
        normalized,
        key=lambda item: (
            -float(item.get("friction_score") or 0.0),
            str(item.get("published_at") or ""),
        ),
    )


def save(signals: list[dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "friction_signal_processor",
        "count": len(signals),
        "signals": signals,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[friction_processor] saved {len(signals)} normalized signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    normalized = collect_normalized_friction_signals()
    save(normalized)
    print(f"[friction_processor] done, total normalized signals: {len(normalized)}")
