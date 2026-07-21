import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import snscrape.modules.twitter as sntwitter


BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_FILE = BASE_DIR / "app" / "context" / "source_accounts.json"

# Important: do not write to the primary pipeline's signals.json.
OUTPUT_FILE = BASE_DIR / "output" / "twitter_signals.json"

RADAR_TIME_WINDOW_HOURS = 24


def ensure_output_dir() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_accounts() -> List[str]:
    if not CONTEXT_FILE.exists():
        raise FileNotFoundError(f"Account config not found: {CONTEXT_FILE}")

    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("twitter_accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("twitter_accounts must be a list in source_accounts.json")

    return accounts


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    return text


def build_title_from_content(content: str, max_len: int = 100) -> str:
    content = clean_text(content)
    if not content:
        return "Untitled signal"

    if len(content) <= max_len:
        return content

    return content[:max_len].rstrip() + "..."


def build_summary_from_tweet(content: str) -> str:
    return clean_text(content)


def infer_category(content: str) -> str:
    text = clean_text(content).lower()

    if any(k in text for k in ["agent", "agents", "workflow", "orchestration"]):
        return "AI Agent"
    if any(k in text for k in ["context", "memory", "retrieval", "rag"]):
        return "Context Engineering"
    if any(k in text for k in ["reasoning", "inference", "thinking"]):
        return "Reasoning"
    if any(k in text for k in ["safety", "alignment", "governance"]):
        return "AI Safety"
    if any(k in text for k in ["model", "llm", "openai", "anthropic", "claude"]):
        return "AI Model"

    return "twitter"


def is_within_time_window(dt: datetime, window_hours: int) -> bool:
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=window_hours)
    return dt.astimezone(timezone.utc) >= start_time


def normalize_tweet(tweet: Any, account: str) -> Dict[str, Any]:
    raw_content = getattr(tweet, "content", None)
    if raw_content is None:
        raw_content = getattr(tweet, "rawContent", "")

    content = clean_text(raw_content)
    summary = build_summary_from_tweet(content)
    title = build_title_from_content(content)
    category = infer_category(content)

    published_at = tweet.date.astimezone(timezone.utc).isoformat()
    collected_at = datetime.now(timezone.utc).isoformat()

    return {
        "title": title,
        "summary": summary,
        "content": content,
        "url": tweet.url,
        "author": account,
        "source": "twitter",
        "source_type": "curated",
        "category": category,
        "published_at": published_at,
        "timestamp": published_at,
        "collected_at": collected_at,
        "id": str(tweet.id),
        "summary_length": len(summary),
        "content_length": len(content),
    }


def collect_tweets(account: str, limit: int = 5) -> List[Dict[str, Any]]:
    query = f"from:{account}"
    tweets: List[Dict[str, Any]] = []

    print(f"[twitter] Fetching @{account}")

    scraper = sntwitter.TwitterSearchScraper(query)

    for tweet in scraper.get_items():
        if len(tweets) >= limit:
            break

        tweet_dt = tweet.date.astimezone(timezone.utc)
        if not is_within_time_window(tweet_dt, RADAR_TIME_WINDOW_HOURS):
            continue

        raw_content = getattr(tweet, "content", None)
        if raw_content is None:
            raw_content = getattr(tweet, "rawContent", "")

        content = clean_text(raw_content)
        if not content:
            continue

        tweets.append(normalize_tweet(tweet, account))

    print(f"[twitter] Collected {len(tweets)} fresh tweets from @{account}")
    return tweets


def deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_ids = set()
    deduped: List[Dict[str, Any]] = []

    for record in records:
        record_id = record.get("id")
        if not record_id:
            deduped.append(record)
            continue

        if record_id in seen_ids:
            continue

        seen_ids.add(record_id)
        deduped.append(record)

    return deduped


def run_collector(per_account_limit: int = 5) -> List[Dict[str, Any]]:
    print("[twitter] START twitter collector")

    accounts = load_accounts()
    print(f"[twitter] Loaded accounts: {accounts}")

    all_records: List[Dict[str, Any]] = []

    for account in accounts:
        try:
            records = collect_tweets(account, per_account_limit)
            all_records.extend(records)
        except Exception as e:
            print(f"[twitter][ERROR] Failed for @{account}: {e}")

    all_records = deduplicate_records(all_records)

    print(f"[twitter] TOTAL records: {len(all_records)}")
    return all_records


def save_signals(records: List[Dict[str, Any]]) -> None:
    ensure_output_dir()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "twitter_collector",
        "count": len(records),
        "signals": records,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[twitter] Saved signals to: {OUTPUT_FILE}")


def main() -> None:
    try:
        records = run_collector(per_account_limit=5)
        save_signals(records)
        print("[twitter] END twitter collector")
    except Exception as e:
        print(f"[twitter][FATAL] {e}")
        raise


if __name__ == "__main__":
    main()
