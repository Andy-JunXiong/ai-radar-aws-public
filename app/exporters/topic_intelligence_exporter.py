from pathlib import Path
import json
import re
from collections import defaultdict
from typing import Union, List


def normalize_topic_name(topic: str) -> str:
    return (topic or "").strip().replace(" ", "_")


def sanitize_note_title(title: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "", (title or "").strip())


def replace_or_append_section(content: str, section_title: str, section_body: str) -> str:
    new_block = f"## {section_title}\n\n{section_body}\n"
    pattern = rf"##\s*{re.escape(section_title)}\s*\n[\s\S]*?(?=\n## |\Z)"

    if re.search(pattern, content):
        return re.sub(pattern, new_block, content)

    return content.rstrip() + "\n\n" + new_block + "\n"


def _load_signals(signals_input: Union[Path, List[dict]]) -> List[dict]:
    if isinstance(signals_input, list):
        return signals_input

    if isinstance(signals_input, Path):
        if not signals_input.exists():
            print(f"Topic intelligence skipped: signals file not found: {signals_input}")
            return []

        try:
            with open(signals_input, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Topic intelligence failed to read signals file: {e}")
            return []

        if not isinstance(data, list):
            print("Topic intelligence skipped: signals json is not a list.")
            return []

        return data

    print(f"Topic intelligence skipped: unsupported signals_input type: {type(signals_input)}")
    return []


def export_topic_intelligence(vault_path: Path, signals_input: Union[Path, List[dict]]) -> None:
    signals_data = _load_signals(signals_input)
    if not signals_data:
        print("Topic intelligence skipped: no valid signals data.")
        return

    research_path = vault_path / "03_Research"
    if not research_path.exists():
        print(f"Research path not found: {research_path}")
        return

    topic_to_signals = defaultdict(list)

    for item in signals_data:
        topic_raw = (item.get("topic") or "").strip()
        title = (item.get("title") or "").strip()
        score = item.get("score", 0)

        if not topic_raw or not title:
            continue

        topic_name = normalize_topic_name(topic_raw)
        topic_to_signals[topic_name].append({
            "title": title,
            "score": score,
        })

    for topic_name, topic_signals in topic_to_signals.items():
        research_file = research_path / f"{topic_name}.md"
        if not research_file.exists():
            print(f"Research file not found, skip: {research_file.name}")
            continue

        sorted_signals = sorted(
            topic_signals,
            key=lambda x: float(x.get("score", 0) or 0),
            reverse=True,
        )

        signal_count = len(sorted_signals)
        top_signals = sorted_signals[:5]

        recent_signal_lines = "\n".join(
            f"- {sanitize_note_title(s['title'])} (score: {round(float(s.get('score', 0) or 0), 2)})"
            for s in top_signals
        )

        section_body = (
            f"Signal Count: {signal_count}\n\n"
            f"Top Signals\n"
            f"{recent_signal_lines if recent_signal_lines else '- None'}"
        )

        try:
            content = research_file.read_text(encoding="utf-8")
            content = replace_or_append_section(content, "Topic Intelligence", section_body)
            research_file.write_text(content, encoding="utf-8")
            print(f"Updated topic intelligence: {research_file.name}")
        except Exception as e:
            print(f"Failed to write research file {research_file.name}: {e}")

    print("Topic intelligence export complete.")