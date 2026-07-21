import json
import os
from pathlib import Path
import feedparser
from datetime import datetime, timezone, timedelta

import boto3
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "rss_signals.json"
SUBSCRIPTION_DIR = BASE_DIR / "backend" / "data" / "settings" / "subscriptions"
DEFAULT_SUBSCRIPTION_SCOPE = "admin_default"
ROOT_ENV_PATH = BASE_DIR / ".env"
load_dotenv(ROOT_ENV_PATH)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
S3_BUCKET = (
    os.getenv("S3_BUCKET")
    or os.getenv("AI_RADAR_S3_BUCKET")
    or ""
).strip()
SUBSCRIPTION_S3_PREFIX = (
    os.getenv("SUBSCRIPTION_SETTINGS_S3_PREFIX")
    or "settings/subscriptions"
).strip().strip("/")

# ==========================================
# AI Radar Curated Sources
# ==========================================

RSS_SOURCES = {

    # --------------------------------------
    # Official AI Labs
    # --------------------------------------
    "openai": "https://openai.com/blog/rss.xml",
    "aws_ml": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",

    # --------------------------------------
    # AI Experts / Curated
    # --------------------------------------
    "latent_space": "https://www.latent.space/feed",
    "import_ai": "https://importai.substack.com/feed",

    # --------------------------------------
    # AI Newsletters
    # --------------------------------------
    "ben_bites": "https://www.bensbites.co/rss",
    "the_rundown": "https://www.therundown.ai/rss",
    "deeplearning_ai": "https://www.deeplearning.ai/the-batch/feed",
}

# ==========================================
# Time Window
# ==========================================

TIME_WINDOW_HOURS = 24 * 7

# ==========================================
# Source Weights
# ==========================================

SOURCE_WEIGHTS = {

    # official
    "openai": 1.0,
    "deepmind": 1.0,
    "aws_ml": 0.95,
    "huggingface": 0.95,

    # experts
    "latent_space": 0.9,
    "import_ai": 0.9,

    # curated
    "ben_bites": 0.85,
    "the_rundown": 0.85,
    "deeplearning_ai": 0.85,
}


def _subscription_file_path() -> Path:

    return SUBSCRIPTION_DIR / f"{DEFAULT_SUBSCRIPTION_SCOPE}.json"


def _subscription_s3_key() -> str:

    return f"{SUBSCRIPTION_S3_PREFIX}/{DEFAULT_SUBSCRIPTION_SCOPE}.json"


def _load_subscription_payload_from_s3() -> dict | None:

    if not S3_BUCKET:
        return None

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        response = s3.get_object(Bucket=S3_BUCKET, Key=_subscription_s3_key())
        raw = response["Body"].read().decode("utf-8")
        payload = json.loads(raw)

        if isinstance(payload, dict):
            try:
                SUBSCRIPTION_DIR.mkdir(parents=True, exist_ok=True)
                _subscription_file_path().write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return payload
    except Exception:
        return None

    return None


def _looks_like_feed(url: str) -> bool:

    lowered = (url or "").strip().lower()
    return any(token in lowered for token in ("rss", "feed", ".xml", "atom"))


def _normalize_source_key(name: str, fallback_index: int) -> str:

    raw = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    cleaned = "".join(char for char in raw if char.isalnum() or char == "_").strip("_")
    return cleaned or f"subscription_source_{fallback_index}"


def load_subscription_rss_sources() -> dict[str, str]:

    payload = _load_subscription_payload_from_s3()
    if payload is None:
        path = _subscription_file_path()
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    if not isinstance(sources, list):
        return {}

    subscription_sources: dict[str, str] = {}
    for index, item in enumerate(sources, start=1):
        if not isinstance(item, dict):
            continue

        enabled = bool(item.get("enabled", True))
        url = str(item.get("url", "")).strip()
        source_type = str(item.get("type", "")).strip().lower()
        name = str(item.get("name", "")).strip()

        if not enabled or not url:
            continue

        if source_type not in {"rss", "official_blog", "newsletter", "research", "custom_url"}:
            continue

        if source_type == "custom_url" and not _looks_like_feed(url):
            continue

        if source_type != "rss" and not _looks_like_feed(url):
            continue

        source_key = _normalize_source_key(name, index)
        dedupe_counter = 2
        while source_key in subscription_sources:
            source_key = f"{_normalize_source_key(name, index)}_{dedupe_counter}"
            dedupe_counter += 1

        subscription_sources[source_key] = url

    return subscription_sources


def get_effective_rss_sources() -> dict[str, str]:

    subscription_sources = load_subscription_rss_sources()
    if not subscription_sources:
        return RSS_SOURCES

    merged_sources = dict(RSS_SOURCES)
    existing_urls = {url.strip().lower() for url in merged_sources.values()}

    for source_key, source_url in subscription_sources.items():
        normalized_url = source_url.strip().lower()
        if normalized_url in existing_urls:
            continue
        merged_sources[source_key] = source_url
        existing_urls.add(normalized_url)

    return merged_sources


def parse_feed_entry(source_name: str, entry) -> dict:

    published_at = None

    if hasattr(entry, "published_parsed") and entry.published_parsed:
        published_at = datetime(
            *entry.published_parsed[:6],
            tzinfo=timezone.utc
        ).isoformat()

    summary = ""

    if hasattr(entry, "summary"):
        summary = entry.summary

    elif hasattr(entry, "description"):
        summary = entry.description

    return {
        "source": source_name,
        "title": getattr(entry, "title", "").strip(),
        "link": getattr(entry, "link", "").strip(),
        "published_at": published_at,
        "summary": summary.strip(),
        "content_type": "rss",
        "source_weight": SOURCE_WEIGHTS.get(source_name, 0.5),
    }


def is_recent(published_at: str | None) -> bool:

    if not published_at:
        return False

    try:
        published_dt = datetime.fromisoformat(published_at)
        now = datetime.now(timezone.utc)

        return (now - published_dt) <= timedelta(hours=TIME_WINDOW_HOURS)

    except Exception:

        return False


def collect_rss_signals() -> list[dict]:

    all_signals = []
    effective_sources = get_effective_rss_sources()

    print(f"[rss] effective source count: {len(effective_sources)}")

    for source_name, feed_url in effective_sources.items():

        print(f"[rss] collecting from {source_name} -> {feed_url}")

        try:

            feed = feedparser.parse(feed_url)

            entries = getattr(feed, "entries", [])

            print(f"[rss] {source_name} -> {len(entries)} entries")

            fresh_count = 0

            for entry in entries:

                signal = parse_feed_entry(source_name, entry)

                if not signal["title"] or not signal["link"]:
                    continue

                if not is_recent(signal["published_at"]):
                    continue

                all_signals.append(signal)

                fresh_count += 1

            print(f"[rss] {source_name} -> {fresh_count} fresh signals")

        except Exception as e:

            print(f"[rss] failed for {source_name}: {e}")

    return all_signals


def save_signals(signals: list[dict]):

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "rss_collector",
        "count": len(signals),
        "signals": signals
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[rss] saved {len(signals)} signals -> {OUTPUT_FILE}")


if __name__ == "__main__":

    signals = collect_rss_signals()

    save_signals(signals)

    print(f"[rss] done, total fresh signals: {len(signals)}")
