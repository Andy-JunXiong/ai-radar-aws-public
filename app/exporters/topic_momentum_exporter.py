from pathlib import Path
import json
import re
from typing import Union, List

from app.intelligence.topic_momentum_engine import compute_topic_momentum


def replace_or_append_section(content: str, title: str, body: str) -> str:
    new_block = f"## {title}\n\n{body}\n"
    pattern = rf"##\s*{re.escape(title)}\s*\n[\s\S]*?(?=\n## |\Z)"

    if re.search(pattern, content):
        return re.sub(pattern, new_block, content)

    return content.rstrip() + "\n\n" + new_block + "\n"


def _load_signals(signals_input: Union[Path, List[dict]]) -> List[dict]:
    """
    Support two input modes:
    1) signals_input = Path to signals.json
    2) signals_input = signals_data list (in-memory)
    """
    if isinstance(signals_input, list):
        return signals_input

    if isinstance(signals_input, Path):
        if not signals_input.exists():
            print(f"Topic momentum skipped: signals file not found: {signals_input}")
            return []

        try:
            with open(signals_input, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Topic momentum failed to read signals: {e}")
            return []

        if not isinstance(data, list):
            print("Topic momentum skipped: signals json is not a list.")
            return []

        return data

    print(f"Topic momentum skipped: unsupported signals_input type: {type(signals_input)}")
    return []


def export_topic_momentum(vault_path: Path, signals_input: Union[Path, List[dict]]) -> None:
    signals = _load_signals(signals_input)

    if not signals:
        print("Topic momentum skipped: no signals.")
        return

    momentum = compute_topic_momentum(signals)
    print("Topic momentum topics:", list(momentum.keys()))

    research_dir = vault_path / "03_Research"

    if not research_dir.exists():
        print("Topic momentum skipped: research dir missing:", research_dir)
        return

    for topic, stats in momentum.items():
        research_file = research_dir / f"{topic}.md"

        if not research_file.exists():
            print("Topic momentum skip missing file:", research_file.name)
            continue

        body = (
            f"Signals last 7 days: {stats['7d']}\n\n"
            f"Signals last 30 days: {stats['30d']}\n\n"
            f"Momentum: **{stats['momentum']}**"
        )

        try:
            content = research_file.read_text(encoding="utf-8")
            content = replace_or_append_section(content, "Topic Momentum", body)
            research_file.write_text(content, encoding="utf-8")
            print("Updated topic momentum:", research_file.name)
        except Exception as e:
            print("Failed writing topic momentum:", research_file.name, e)

    print("Topic momentum export complete.")