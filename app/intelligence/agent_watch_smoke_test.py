from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.intelligence.processors.agent_signal_processor import (
    collect_normalized_hackernews_agent_signals,
    collect_normalized_producthunt_agent_signals,
    normalize_github_agent_signals,
    save as save_agent_watch_signals,
)
from app.intelligence.classifiers.agent_classifier import classify_agent_signals
from app.intelligence.scorers.agent_signal_scorer import attach_agent_scores_to_signals
from app.main_summary_v2 import build_agent_watch_summary
from signal_collectors.github_agent_collector import (
    collect_github_agent_signals,
    save as save_github_agent_signals,
)
from signal_collectors.hackernews_agent_collector import (
    collect_hackernews_agent_signals,
    save as save_hackernews_agent_signals,
)
from signal_collectors.producthunt_agent_collector import (
    collect_producthunt_agent_signals,
    save as save_producthunt_agent_signals,
)
from signal_collectors.merge_signals import main as run_merge_signals


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "data" / "output"
COLLECTED_SIGNALS_FILE = OUTPUT_DIR / "collected_signals.json"
DAILY_RADAR_FILE = OUTPUT_DIR / "agent_watch_smoke_test.json"


def _load_json_list(path: Path) -> list[dict[str, Any]]:
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


def run_agent_watch_smoke_test() -> dict[str, Any]:
    github_raw_signals = collect_github_agent_signals()
    save_github_agent_signals(github_raw_signals)
    hackernews_raw_signals = collect_hackernews_agent_signals()
    save_hackernews_agent_signals(hackernews_raw_signals)
    producthunt_raw_signals = collect_producthunt_agent_signals()
    save_producthunt_agent_signals(producthunt_raw_signals)

    normalized_signals = normalize_github_agent_signals(github_raw_signals)
    normalized_signals.extend(collect_normalized_hackernews_agent_signals())
    normalized_signals.extend(collect_normalized_producthunt_agent_signals())
    classified_signals = classify_agent_signals(normalized_signals)
    scored_signals = attach_agent_scores_to_signals(classified_signals)
    save_agent_watch_signals(scored_signals)

    run_merge_signals()
    merged_signals = _load_json_list(COLLECTED_SIGNALS_FILE)
    agent_watch_summary = build_agent_watch_summary(merged_signals)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_count": len(github_raw_signals) + len(hackernews_raw_signals) + len(producthunt_raw_signals),
        "raw_source_counts": {
            "github": len(github_raw_signals),
            "hackernews": len(hackernews_raw_signals),
            "producthunt": len(producthunt_raw_signals),
        },
        "normalized_count": len(normalized_signals),
        "classified_count": len(classified_signals),
        "scored_count": len(scored_signals),
        "merged_signal_count": len(merged_signals),
        "agent_watch": agent_watch_summary,
    }

    DAILY_RADAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    DAILY_RADAR_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Agent Watch Smoke Test ===")
    print(f"raw_count={payload['raw_count']}")
    print(f"normalized_count={payload['normalized_count']}")
    print(f"scored_count={payload['scored_count']}")
    print(f"merged_signal_count={payload['merged_signal_count']}")
    print(
        "agent_watch_summary="
        f"{agent_watch_summary.get('signal_count', 0)} signals / "
        f"{agent_watch_summary.get('top_signal_count', 0)} highlights"
    )
    print(f"output={DAILY_RADAR_FILE}")

    return payload


if __name__ == "__main__":
    run_agent_watch_smoke_test()
