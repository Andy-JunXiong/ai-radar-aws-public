from app.exporters.obsidian_exporter import export_insight_to_obsidian

vault_path = r"C:\ObsidianVault\AY System Vault"

test_insight = {
    "title": "AI Agent Memory Bottleneck",
    "core_idea": "Memory is becoming the main bottleneck for multi-agent systems.",
    "explanation": "Agents need persistent memory to maintain context, continuity, and learning across tasks.",
    "why_it_matters": "Without structured memory, agents remain reactive tools rather than durable systems.",
    "connected_projects": "- [[Trajectory_Memory]]\n- [[AI_Cognitive_OS]]",
    "related_research": "- [[AI_Agents]]",
    "source": "AI Radar test export",
    "tags": "#ai_system #agent #memory",
}

export_insight_to_obsidian(vault_path, test_insight)