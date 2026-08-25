import tempfile
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.exporters.obsidian_exporter import export_insight_to_obsidian


def test_export_insight_to_obsidian_writes_only_to_supplied_vault():
    insight = {
        "title": "AI Agent Memory Bottleneck",
        "core_idea": "Memory is becoming the main bottleneck for multi-agent systems.",
        "explanation": "Agents need persistent memory to maintain context, continuity, and learning across tasks.",
        "why_it_matters": "Without structured memory, agents remain reactive tools rather than durable systems.",
        "connected_projects": "- [[Trajectory_Memory]]\n- [[AI_Cognitive_OS]]",
        "related_research": "- [[AI_Agents]]",
        "source": "AI Radar test export",
        "tags": "#ai_system #agent #memory",
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        vault_path = Path(temp_dir) / "vault"
        exported_path = export_insight_to_obsidian(vault_path, insight)
        content = exported_path.read_text(encoding="utf-8")

        assert exported_path == (
            vault_path
            / "04_Insights"
            / "System_Insights"
            / "AI_Agent_Memory_Bottleneck.md"
        )
        assert exported_path.exists()
        assert "# AI Agent Memory Bottleneck" in content
        assert "[[Trajectory_Memory]]" in content
