import json
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SIGNALS_FILE = BASE_DIR / "output" / "signals.json"


def load_signals() -> List[Dict]:
    if not SIGNALS_FILE.exists():
        print(f"[source_quality] signals file not found: {SIGNALS_FILE}")
        return []

    with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data if isinstance(data, list) else []


def safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def compute_source_quality(signals: List[Dict]) -> Dict[str, Dict]:
    stats: Dict[str, Dict] = {}

    for item in signals:
        source = safe_text(item.get("source")) or "unknown"

        if source not in stats:
            stats[source] = {
                "raw_count": 0,
                "has_summary": 0,
                "has_url": 0,
                "has_author": 0,
                "has_category": 0,
                "avg_summary_length_total": 0,
            }

        stats[source]["raw_count"] += 1

        summary = safe_text(item.get("summary"))
        url = safe_text(item.get("url"))
        author = safe_text(item.get("author"))
        category = safe_text(item.get("category"))

        if summary:
            stats[source]["has_summary"] += 1
            stats[source]["avg_summary_length_total"] += len(summary)
        if url:
            stats[source]["has_url"] += 1
        if author:
            stats[source]["has_author"] += 1
        if category:
            stats[source]["has_category"] += 1

    for source, item in stats.items():
        raw_count = item["raw_count"]

        item["summary_rate"] = round(item["has_summary"] / raw_count, 2) if raw_count else 0
        item["url_rate"] = round(item["has_url"] / raw_count, 2) if raw_count else 0
        item["author_rate"] = round(item["has_author"] / raw_count, 2) if raw_count else 0
        item["category_rate"] = round(item["has_category"] / raw_count, 2) if raw_count else 0
        item["avg_summary_length"] = round(
            item["avg_summary_length_total"] / item["has_summary"], 1
        ) if item["has_summary"] else 0

        quality_score = (
            item["summary_rate"] * 0.4
            + item["url_rate"] * 0.2
            + item["author_rate"] * 0.2
            + item["category_rate"] * 0.2
        )
        item["quality_score"] = round(quality_score, 2)

        del item["avg_summary_length_total"]

    return stats


def debug_print(stats: Dict[str, Dict]) -> None:
    print("\n=== SOURCE QUALITY REPORT ===")
    for source, item in sorted(
        stats.items(),
        key=lambda x: x[1]["quality_score"],
        reverse=True
    ):
        print(f"\n[{source}]")
        print(f" raw_count: {item['raw_count']}")
        print(f" summary_rate: {item['summary_rate']}")
        print(f" url_rate: {item['url_rate']}")
        print(f" author_rate: {item['author_rate']}")
        print(f" category_rate: {item['category_rate']}")
        print(f" avg_summary_length: {item['avg_summary_length']}")
        print(f" quality_score: {item['quality_score']}")
    print("\n=============================\n")


if __name__ == "__main__":
    signals = load_signals()
    stats = compute_source_quality(signals)
    debug_print(stats)