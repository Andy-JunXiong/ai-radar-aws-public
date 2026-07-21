from pathlib import Path
import re

TOPIC_RELATIONS = {
    "AI_Agents": ["AI_Trends", "AI_Infrastructure", "AI_Models"],
    "AI_Trends": ["AI_Agents", "AI_Products", "AI_Research"],
    "AI_Models": ["AI_Agents", "AI_Research", "AI_Infrastructure"],
    "AI_Infrastructure": ["AI_Agents", "AI_Models", "AI_Products"],
}


def replace_or_append_section(content: str, section_title: str, section_body: str) -> str:
    new_block = f"## {section_title}\n\n{section_body}\n"
    pattern = rf"##\s*{re.escape(section_title)}\s*\n[\s\S]*?(?=\n## |\Z)"

    if re.search(pattern, content):
        return re.sub(pattern, new_block, content)

    return content.rstrip() + "\n\n" + new_block + "\n"


def export_topic_graph(vault_path: Path) -> None:
    research_path = vault_path / "03_Research"

    if not research_path.exists():
        print(f"Research path not found: {research_path}")
        return

    for topic, related_topics in TOPIC_RELATIONS.items():
        research_file = research_path / f"{topic}.md"
        if not research_file.exists():
            print(f"Research file not found, skip: {research_file.name}")
            continue

        try:
            content = research_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Failed to read research file {research_file.name}: {e}")
            continue

        lines = "\n".join(f"- [[{name}]]" for name in related_topics)
        content = replace_or_append_section(content, "Related Topics", lines)

        try:
            research_file.write_text(content, encoding="utf-8")
            print(f"Updated topic graph: {research_file.name}")
        except Exception as e:
            print(f"Failed to write research file {research_file.name}: {e}")

    print("Topic graph export complete.")