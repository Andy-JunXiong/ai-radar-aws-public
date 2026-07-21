from pathlib import Path
import re
from collections import defaultdict


def extract_bullet_section(content: str, section_name: str) -> list[str]:
    pattern = rf"##\s*{re.escape(section_name)}\s*\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, content)

    if not match:
        return []

    block = match.group(1)
    lines = block.split("\n")
    items = []

    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("• "):
            items.append(line[2:].strip())

    return items


def extract_tags(content: str) -> list[str]:
    pattern = r"##\s*Tags\s*\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, content)

    if not match:
        return []

    block = match.group(1)
    tags = re.findall(r"#([a-zA-Z0-9_\-]+)", block)
    return tags


def replace_or_append_section(content: str, section_title: str, section_body: str) -> str:
    new_block = f"## {section_title}\n\n{section_body}\n"

    pattern = rf"##\s*{re.escape(section_title)}\s*\n[\s\S]*?(?=\n## |\Z)"
    if re.search(pattern, content):
        return re.sub(pattern, new_block, content)

    content = content.rstrip()
    return content + "\n\n" + new_block + "\n"


def export_research_map(vault_path: Path) -> None:
    insights_path = vault_path / "04_Insights" / "System_Insights"
    research_path = vault_path / "03_Research"

    topic_to_insights = defaultdict(list)
    topic_to_projects = defaultdict(set)
    topic_to_tags = defaultdict(set)

    if not insights_path.exists():
        print(f"System insights path not found: {insights_path}")
        return

    if not research_path.exists():
        print(f"Research path not found: {research_path}")
        return

    for insight_file in insights_path.glob("*.md"):
        insight_name = insight_file.stem

        try:
            content = insight_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Failed to read insight file {insight_file.name}: {e}")
            continue

        related_research = extract_bullet_section(content, "Related Research")
        connected_projects = extract_bullet_section(content, "Connected Projects")
        tags = extract_tags(content)

        for topic in related_research:
            clean_topic = topic.replace("[[", "").replace("]]", "").strip()
            if not clean_topic:
                continue

            topic_to_insights[clean_topic].append(insight_name)

            for project in connected_projects:
                clean_project = project.replace("[[", "").replace("]]", "").strip()
                if clean_project:
                    topic_to_projects[clean_topic].add(clean_project)

            for tag in tags:
                if tag.strip():
                    topic_to_tags[clean_topic].add(tag.strip())

    for topic, insights in topic_to_insights.items():
        research_file = research_path / f"{topic}.md"
        if not research_file.exists():
            print(f"Research file not found, skip: {research_file.name}")
            continue

        try:
            content = research_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Failed to read research file {research_file.name}: {e}")
            continue

        insight_lines = "\n".join(f"- [[{name}]]" for name in sorted(set(insights)))
        project_lines = "\n".join(f"- [[{name}]]" for name in sorted(topic_to_projects[topic]))
        tag_lines = "\n".join(f"- {tag}" for tag in sorted(topic_to_tags[topic]))

        content = replace_or_append_section(content, "Insights", insight_lines or "- None")
        content = replace_or_append_section(content, "Related Projects", project_lines or "- None")
        content = replace_or_append_section(content, "Tags", tag_lines or "- None")

        try:
            research_file.write_text(content, encoding="utf-8")
            print(f"Updated research map: {research_file.name}")
        except Exception as e:
            print(f"Failed to write research file {research_file.name}: {e}")

    print("Research map export complete.")