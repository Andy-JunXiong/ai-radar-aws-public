import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
MAX_SOURCE_EXCERPT_CHARS = 1200
SOURCE_EXCERPT_FIELDS = (
    "source_excerpt",
    "raw_content",
    "raw_text",
    "article_body",
    "content",
)

# manual signals
MANUAL_FILE = BASE_DIR / "app" / "context" / "manual_signals.json"

# collector outputs
RSS_FILE = BASE_DIR / "data" / "output" / "rss_signals.json"
OFFICIAL_FILE = BASE_DIR / "data" / "output" / "official_signals.json"
AGENT_WATCH_FILE = BASE_DIR / "data" / "output" / "agent_watch_signals.json"
FRICTION_FILE = BASE_DIR / "data" / "output" / "friction_signals.json"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "collected_signals.json"


def load_json(path: Path):
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_rss(data):
    """
    collector 输出格式支持两种：
    1. list[dict]
    2. {
         "generated_at": "...",
         "source": "...",
         "count": N,
         "signals": [...]
       }
    """
    if isinstance(data, dict) and "signals" in data:
        return data["signals"]
    if isinstance(data, list):
        return data
    return []


def normalize_manual(data):
    """
    manual_signals.json 预期是：
    1. list[dict]
    2. {"signals": [...]}
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "signals" in data:
        return data["signals"]
    return []


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def bounded_source_excerpt(item: dict, summary: str) -> str:
    normalized_summary = clean_text(summary).lower()

    for field in SOURCE_EXCERPT_FIELDS:
        value = clean_text(item.get(field))
        if not value:
            continue

        if field == "content" and value.lower() == normalized_summary:
            continue

        return value[:MAX_SOURCE_EXCERPT_CHARS]

    return ""


def normalize_signal(item: dict, source_type_fallback: str = "") -> dict:
    title = clean_text(item.get("title"))
    summary = clean_text(item.get("summary"))
    content = clean_text(item.get("content"))

    if not summary and content:
        summary = content[:280]

    if not title:
        fallback_text = summary or content
        title = fallback_text[:120] if fallback_text else "Untitled Signal"

    source_excerpt = bounded_source_excerpt(item, summary)

    normalized = {
        "title": title,
        "summary": summary,
        "content": content,
        "url": clean_text(item.get("url") or item.get("link")),
        "author": clean_text(item.get("author")),
        "source": clean_text(item.get("source")),
        "source_type": clean_text(item.get("source_type")) or source_type_fallback,
        "category": clean_text(item.get("category")),
        "published_at": clean_text(item.get("published_at")),
        "timestamp": clean_text(item.get("timestamp")),
        "collected_at": clean_text(item.get("collected_at")),
        "source_weight": item.get("source_weight", 0.5),
        "summary_length": item.get("summary_length")
        if isinstance(item.get("summary_length"), int)
        else len(summary),
        "content_length": item.get("content_length")
        if isinstance(item.get("content_length"), int)
        else len(content),
    }

    if source_excerpt:
        normalized["source_excerpt"] = source_excerpt
        normalized["source_excerpt_length"] = len(source_excerpt)

    topic = clean_text(item.get("topic"))
    if topic:
        normalized["topic"] = topic

    score = item.get("score")
    if isinstance(score, (int, float)):
        normalized["score"] = score

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        normalized["metadata"] = metadata

    for field in (
        "pain_severity_score",
        "ecosystem_relevance_score",
        "friction_score",
        "agent_relevance_score",
        "buildability_score",
        "strategic_relevance_score",
        "agent_watch_score",
    ):
        value = item.get(field)
        if isinstance(value, (int, float)):
            normalized[field] = value

    agent_subtopic = clean_text(item.get("agent_subtopic"))
    if agent_subtopic:
        normalized["agent_subtopic"] = agent_subtopic

    friction_subtopic = clean_text(item.get("friction_subtopic"))
    if friction_subtopic:
        normalized["friction_subtopic"] = friction_subtopic

    signal_type = clean_text(item.get("signal_type"))
    if signal_type:
        normalized["signal_type"] = signal_type

    return normalized


def build_dedup_key(item: dict) -> str:
    url = clean_text(item.get("url")).lower()
    if url:
        return f"url::{url}"

    title = clean_text(item.get("title")).lower()
    if title:
        return f"title::{title}"

    return "unknown"


def main():
    manual_raw = load_json(MANUAL_FILE)
    rss_raw = load_json(RSS_FILE)
    official_raw = load_json(OFFICIAL_FILE)
    agent_watch_raw = load_json(AGENT_WATCH_FILE)
    friction_raw = load_json(FRICTION_FILE)

    manual = normalize_manual(manual_raw)
    rss = normalize_rss(rss_raw)
    official = normalize_rss(official_raw)
    agent_watch = normalize_rss(agent_watch_raw)
    friction = normalize_rss(friction_raw)

    normalized_manual = [
        normalize_signal(item, source_type_fallback="manual")
        for item in manual
        if isinstance(item, dict)
    ]

    normalized_rss = [
        normalize_signal(item, source_type_fallback="rss")
        for item in rss
        if isinstance(item, dict)
    ]

    normalized_official = [
        normalize_signal(item, source_type_fallback="official")
        for item in official
        if isinstance(item, dict)
    ]

    normalized_agent_watch = [
        normalize_signal(item, source_type_fallback="github_agent")
        for item in agent_watch
        if isinstance(item, dict)
    ]

    normalized_friction = [
        normalize_signal(item, source_type_fallback="friction")
        for item in friction
        if isinstance(item, dict)
    ]

    merged = normalized_manual + normalized_rss + normalized_official + normalized_agent_watch + normalized_friction

    seen = set()
    deduped = []

    for item in merged:
        key = build_dedup_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print(f"[merge] manual: {len(normalized_manual)}")
    print(f"[merge] rss: {len(normalized_rss)}")
    print(f"[merge] official: {len(normalized_official)}")
    print(f"[merge] github_agent: {len(normalized_agent_watch)}")
    print(f"[merge] friction: {len(normalized_friction)}")
    print(f"[merge] total merged: {len(merged)}")
    print(f"[merge] total deduped: {len(deduped)}")
    print(f"[merge] output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
