import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.registry import workspace_chat_system_prompt  # noqa: E402
from app.routes.workspace import build_project_repo_snapshot_context  # noqa: E402


class WorkspaceChatPromptTests(unittest.TestCase):
    def test_default_workspace_chat_prompt_has_no_challenge_protocol(self):
        prompt = workspace_chat_system_prompt("chatgpt")

        self.assertNotIn("CONVERSATION CHALLENGE PROTOCOL", prompt)
        self.assertNotIn("ANDY CONVERSATION PREFERENCES", prompt)
        self.assertNotIn("可 = continue", prompt)

    def test_challenge_mode_adds_reasoning_only_protocol(self):
        prompt = workspace_chat_system_prompt("chatgpt", challenge_mode=True)

        self.assertIn("CONVERSATION CHALLENGE PROTOCOL", prompt)
        self.assertIn("reasoning challenge only", prompt)
        self.assertIn("可 = continue", prompt)
        self.assertIn("Do not frame this as factual verification", prompt)

    def test_claude_discussion_can_mount_andy_conversation_preferences(self):
        prompt = workspace_chat_system_prompt(
            "claude",
            challenge_mode=True,
            conversation_preferences=True,
        )

        self.assertIn("ANDY CONVERSATION PREFERENCES", prompt)
        self.assertIn("Evidence grading is always on", prompt)
        self.assertIn("tension axis", prompt)
        self.assertIn("valence could flip", prompt)
        self.assertIn("framework density inflation", prompt)
        self.assertIn("CONVERSATION CHALLENGE PROTOCOL", prompt)

    def test_claude_prompt_does_not_mount_preferences_by_default(self):
        prompt = workspace_chat_system_prompt("claude", challenge_mode=True)

        self.assertNotIn("ANDY CONVERSATION PREFERENCES", prompt)
        self.assertIn("CONVERSATION CHALLENGE PROTOCOL", prompt)

    def test_claude_discussion_web_search_prompt_allows_external_search(self):
        prompt = workspace_chat_system_prompt(
            "claude",
            policy={"mode": "standard", "citation_required": True},
            challenge_mode=True,
            conversation_preferences=True,
            web_search_enabled=True,
        )

        self.assertIn("WEB SEARCH TOOL AVAILABILITY", prompt)
        self.assertIn("Anthropic web search is available", prompt)
        self.assertIn("Do not say you lack external search capability", prompt)
        self.assertIn("[Web search: source/title/url]", prompt)
        self.assertIn("Keep the answer scoped to the user's focal entity and question", prompt)
        self.assertIn("answer that product-specific relevance instead of writing a general product profile", prompt)
        self.assertIn("Do not include pricing, funding, company background", prompt)
        self.assertIn("true but irrelevant to the user's question, omit them", prompt)
        self.assertNotIn("Base the answer on the provided context only.", prompt)

    def test_workspace_chat_context_includes_cached_repo_snapshot(self):
        with patch(
            "app.routes.workspace.list_projects",
            return_value=[
                {
                    "project_id": "ai_radar",
                    "name": "AI Radar",
                    "repo": "https://github.com/Andy-JunXiong/ai-radar-aws",
                    "enabled": True,
                }
            ],
        ), patch(
            "app.routes.workspace.load_project_repo_snapshot",
            return_value={
                "status": "fresh",
                "repo": "Andy-JunXiong/ai-radar-aws",
                "summary": "AI Radar is an AI-native intelligence system.",
                "readme_path": "README.md",
                "readme_excerpt": "Signal -> Insight -> Trend -> Strategic Intelligence",
                "roadmap_path": "ROADMAP.md",
                "roadmap_excerpt": "Strategic Intelligence -> Decision -> Review -> Learning",
                "architecture_hints": ["frontend/backend split"],
                "keywords": ["Project Takeaways"],
                "manifests": [{"path": "frontend/package.json"}],
                "recent_commits": [{"message": "add project repo context"}],
            },
        ):
            context = build_project_repo_snapshot_context()

        self.assertIn("Repo snapshots are project context only", context)
        self.assertIn("README.md", context)
        self.assertIn("Signal -> Insight -> Trend -> Strategic Intelligence", context)
        self.assertIn("Strategic Intelligence -> Decision -> Review -> Learning", context)
        self.assertIn("frontend/backend split", context)


if __name__ == "__main__":
    unittest.main()
