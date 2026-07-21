from pathlib import Path
import re


def _safe_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    text = text.replace(" ", "_")
    return text


def export_insight_to_obsidian(vault_path, insight):
    """
    Export Radar insight to Obsidian markdown note.
    """

    insights_dir = Path(vault_path) / "04_Insights" / "System_Insights"
    insights_dir.mkdir(parents=True, exist_ok=True)

    title = insight.get("title", "Untitled Insight").strip()
    filename = _safe_filename(title) + ".md"
    filepath = insights_dir / filename

    core_idea = insight.get("core_idea", "")
    explanation = insight.get("explanation", "")
    why_it_matters = insight.get("why_it_matters", "")
    connected_projects = insight.get("connected_projects", "")
    related_research = insight.get("related_research", "")
    source = insight.get("source", "Generated from AI Radar")
    tags = insight.get("tags", "#ai_system #insight")

    content = f"""# {title}

## Related System
[[AI_Radar]]

---

## Core Idea
{core_idea}

---

## Explanation
{explanation}

---

## Why It Matters
{why_it_matters}

---

## Connected Projects
{connected_projects}

---

## Related Research
{related_research}

---

## Source
{source}

---

## Tags
{tags}
"""

    filepath.write_text(content, encoding="utf-8")

    print(f"Insight exported → {filepath}")
    return filepath