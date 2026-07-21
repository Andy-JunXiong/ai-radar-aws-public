import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "output" / "official_signals.json"


def build_signal(
    title: str,
    summary: str,
    url: str,
    author: str,
    source: str,
    category: str,
    now: str,
) -> Dict:
    return {
        "title": title,
        "summary": summary,
        "content": summary,  # Retained temporarily for main.py compatibility.
        "url": url,
        "author": author,
        "source": source,
        "category": category,
        "published_at": now,
        "timestamp": now,
        "collected_at": now,
        "summary_length": len(summary),
    }


def collect_official_signals() -> List[Dict]:
    """
    Use a high-quality mock for now.
    This can later be replaced with RSS or API ingestion.
    """

    now = datetime.now(timezone.utc).isoformat()

    signals = []

    # ===== Signal 1 =====
    signals.append(
        build_signal(
            title="OpenAI improves reasoning capabilities in new model updates",
            summary=(
                "OpenAI has introduced improvements in reasoning capabilities across its latest models, "
                "focusing on more reliable multi-step problem solving and better consistency in outputs. "
                "These updates reflect a broader shift from raw capability scaling toward production stability "
                "and structured reasoning performance in real-world use cases."
            ),
            url="https://openai.com",
            author="OpenAI",
            source="openai",
            category="AI Model",
            now=now,
        )
    )

    # ===== Signal 2 =====
    signals.append(
        build_signal(
            title="Anthropic advances research on AI alignment and safety",
            summary=(
                "Anthropic has released new research focused on improving AI alignment and safety mechanisms, "
                "including better control over model behavior and risk mitigation strategies. "
                "This highlights the increasing importance of governance, reliability, and safety frameworks "
                "as AI systems move into production environments."
            ),
            url="https://anthropic.com",
            author="Anthropic",
            source="anthropic",
            category="AI Safety",
            now=now,
        )
    )

    return signals


def save(signals: List[Dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "official_collector",
        "count": len(signals),
        "signals": signals,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[official] saved {len(signals)} signals to {OUTPUT_FILE}")


if __name__ == "__main__":
    data = collect_official_signals()
    save(data)
