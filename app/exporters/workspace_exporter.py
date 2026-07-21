import json
from pathlib import Path
from typing import Any


WORKSPACE_DIR = Path(__file__).resolve().parents[2] / "backend" / "data" / "workspace"
OBSIDIAN_ROOT = Path(r"C:\ObsidianVault\AY System Vault")
PERSONAL_INSIGHTS_DIR = OBSIDIAN_ROOT / "04_Insights" / "Personal_Insights"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_workspace_records() -> list[dict[str, Any]]:
    ensure_dir(WORKSPACE_DIR)

    records: list[dict[str, Any]] = []

    for file_path in sorted(WORKSPACE_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["_workspace_file_name"] = file_path.name
                records.append(data)
        except Exception as e:
            print(f"Failed to read workspace record {file_path.name}: {e}")

    return records


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def slugify(value: str) -> str:
    text = safe_text(value)
    if not text:
        return "untitled"
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        text = text.replace(ch, "_")
    text = text.replace("\n", " ").replace("\r", " ")
    return "_".join(text.split())[:120]


def build_obsidian_note_content(record: dict[str, Any]) -> str:
    signal_title = safe_text(record.get("signal_title")) or "Untitled"
    topic = safe_text(record.get("topic")) or "General AI"
    saved_at = safe_text(record.get("saved_at"))
    source_type = safe_text(record.get("source_type")) or "unknown"
    content_type = safe_text(record.get("content_type")) or "unknown"
    selected_model = safe_text(record.get("selected_model"))

    final_reflection = safe_text(record.get("final_reflection"))
    signal_summary = safe_text(record.get("signal_summary"))
    why_it_matters = safe_text(record.get("why_it_matters"))
    relevance_to_projects = safe_text(record.get("relevance_to_projects"))
    relevance_to_career = safe_text(record.get("relevance_to_career"))
    synthesized_insight = safe_text(record.get("synthesized_insight"))

    lines: list[str] = [
        "---",
        f'title: "{signal_title.replace(chr(34), chr(39))}"',
        f'topic: "{topic.replace(chr(34), chr(39))}"',
        f'source_type: "{source_type}"',
        f'content_type: "{content_type}"',
        f'saved_at: "{saved_at}"',
        f'selected_model: "{selected_model}"',
        "---",
        "",
        f"# {signal_title}",
        "",
        f"**Topic:** {topic}",
        "",
        f"**Saved at:** {saved_at}",
        "",
        f"**Source type:** {source_type}",
        "",
        f"**Content type:** {content_type}",
        "",
    ]

    if signal_summary:
        lines.extend(
            [
                "## Signal Summary",
                "",
                signal_summary,
                "",
            ]
        )

    if why_it_matters:
        lines.extend(
            [
                "## Why It Matters",
                "",
                why_it_matters,
                "",
            ]
        )

    if relevance_to_projects:
        lines.extend(
            [
                "## Relevance to Projects",
                "",
                relevance_to_projects,
                "",
            ]
        )

    if relevance_to_career:
        lines.extend(
            [
                "## Relevance to Career",
                "",
                relevance_to_career,
                "",
            ]
        )

    if synthesized_insight:
        lines.extend(
            [
                "## Synthesized Insight",
                "",
                synthesized_insight,
                "",
            ]
        )

    if final_reflection:
        lines.extend(
            [
                "## Final Reflection",
                "",
                final_reflection,
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def export_workspace_record_to_obsidian(record: dict[str, Any]) -> Path:
    ensure_dir(PERSONAL_INSIGHTS_DIR)

    saved_at = safe_text(record.get("saved_at"))[:10].replace("-", "")
    topic = safe_text(record.get("topic")) or "General AI"
    signal_title = safe_text(record.get("signal_title")) or "Untitled"

    note_name = f"{saved_at}_{slugify(topic)}_{slugify(signal_title)}.md"
    note_path = PERSONAL_INSIGHTS_DIR / note_name

    content = build_obsidian_note_content(record)
    note_path.write_text(content, encoding="utf-8")
    return note_path


def export_all_workspace_to_obsidian() -> dict[str, Any]:
    records = load_workspace_records()

    exported: list[str] = []
    failed: list[dict[str, str]] = []

    for record in records:
        try:
            note_path = export_workspace_record_to_obsidian(record)
            exported.append(str(note_path))
        except Exception as e:
            failed.append(
                {
                    "workspace_file": record.get("_workspace_file_name", "unknown"),
                    "error": str(e),
                }
            )

    return {
        "workspace_count": len(records),
        "exported_count": len(exported),
        "failed_count": len(failed),
        "exported_files": exported,
        "failed_files": failed,
    }


if __name__ == "__main__":
    result = export_all_workspace_to_obsidian()
    print(json.dumps(result, ensure_ascii=False, indent=2))