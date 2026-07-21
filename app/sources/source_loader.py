import json
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "sources" / "expert_sources.json"


def load_source_config() -> Dict:
    if not SOURCE_FILE.exists():
        print(f"[source_loader] file not found: {SOURCE_FILE}")
        return {}

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_active_blogs(config: Dict) -> List[Dict]:
    return [
        item
        for item in config.get("blogs", [])
        if item.get("status") in ["active", "candidate"]
    ]


def get_experimental_x_accounts(config: Dict) -> List[Dict]:
    return [
        item
        for item in config.get("x_accounts", [])
        if item.get("status") == "experimental"
    ]


def get_active_manual_sources(config: Dict) -> List[Dict]:
    return [
        item
        for item in config.get("manual_candidates", [])
        if item.get("status") == "active"
    ]


def debug_print():
    config = load_source_config()

    blogs = get_active_blogs(config)
    x_accounts = get_experimental_x_accounts(config)
    manual = get_active_manual_sources(config)

    print("\n=== SOURCE CONFIG DEBUG ===")
    print(f"Blogs: {len(blogs)}")
    for b in blogs:
        print(f" - {b['name']} ({b['url']})")

    print(f"\nX accounts (experimental): {len(x_accounts)}")
    for x in x_accounts:
        print(f" - @{x['handle']}")

    print(f"\nManual sources: {len(manual)}")
    for m in manual:
        print(f" - {m['name']}")

    print("==========================\n")


if __name__ == "__main__":
    debug_print()