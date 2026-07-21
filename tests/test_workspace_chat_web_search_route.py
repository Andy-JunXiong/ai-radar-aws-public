import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.routes import workspace as workspace_route  # noqa: E402


class WorkspaceChatWebSearchRouteTests(unittest.TestCase):
    def _policy_result(self):
        return SimpleNamespace(
            selected_policy=SimpleNamespace(to_dict=lambda: {"mode": "standard"})
        )

    def test_claude_discussion_enables_anthropic_web_search(self):
        captured_kwargs = {}

        def fake_execute_workspace_text_with_policy(**kwargs):
            captured_kwargs.update(kwargs)
            return (
                "reply",
                "anthropic",
                False,
                {
                    "model_used": "claude-opus-4-8",
                    "web_search_enabled": True,
                    "web_search_max_uses": 3,
                    "execution": {"mode": "standard"},
                },
            )

        with patch.object(workspace_route, "resolve_request_user_id", return_value="admin_default"), patch.object(
            workspace_route,
            "build_analysis_context",
            return_value="personal context",
        ), patch.object(
            workspace_route,
            "build_project_repo_snapshot_context",
            return_value="project context",
        ), patch.object(
            workspace_route,
            "decide_execution_policy",
            return_value=self._policy_result(),
        ), patch.object(
            workspace_route,
            "execute_workspace_text_with_policy",
            side_effect=fake_execute_workspace_text_with_policy,
        ):
            result = workspace_route.workspace_chat(
                workspace_route.ChatRequest(
                    model="claude",
                    message="What changed this week?",
                    conversation_intent="discussion",
                    signal_title="Signal",
                ),
                request=SimpleNamespace(),
            )

        self.assertTrue(captured_kwargs["web_search_enabled"])
        self.assertEqual(captured_kwargs["provider_override"], workspace_route.PROVIDER_ANTHROPIC)
        self.assertTrue(result["web_search_enabled"])
        self.assertEqual(result["web_search_max_uses"], 3)

    def test_claude_artifact_path_keeps_web_search_off(self):
        captured_kwargs = {}

        def fake_execute_workspace_text_with_policy(**kwargs):
            captured_kwargs.update(kwargs)
            return (
                "reply",
                "anthropic",
                False,
                {
                    "model_used": "claude-opus-4-8",
                    "web_search_enabled": False,
                    "web_search_max_uses": 3,
                    "execution": {"mode": "standard"},
                },
            )

        with patch.object(workspace_route, "resolve_request_user_id", return_value="admin_default"), patch.object(
            workspace_route,
            "build_analysis_context",
            return_value="personal context",
        ), patch.object(
            workspace_route,
            "build_project_repo_snapshot_context",
            return_value="project context",
        ), patch.object(
            workspace_route,
            "decide_execution_policy",
            return_value=self._policy_result(),
        ), patch.object(
            workspace_route,
            "execute_workspace_text_with_policy",
            side_effect=fake_execute_workspace_text_with_policy,
        ):
            result = workspace_route.workspace_chat(
                workspace_route.ChatRequest(
                    model="claude",
                    message="Draft this as an artifact.",
                    conversation_intent="artifact",
                    signal_title="Signal",
                ),
                request=SimpleNamespace(),
            )

        self.assertFalse(captured_kwargs["web_search_enabled"])
        self.assertFalse(result["web_search_enabled"])

    def test_claude_discussion_includes_bounded_recent_context_as_non_evidence(self):
        captured_kwargs = {}

        def fake_execute_workspace_text_with_policy(**kwargs):
            captured_kwargs.update(kwargs)
            return (
                "reply",
                "anthropic",
                False,
                {
                    "model_used": "claude-opus-4-8",
                    "web_search_enabled": True,
                    "web_search_max_uses": 3,
                    "execution": {"mode": "standard"},
                },
            )

        recent_messages = [
            {"role": "user", "content": "oldest question"},
            {"role": "assistant", "content": "older answer"},
            {"role": "user", "content": "recent question one"},
            {"role": "assistant", "content": "recent answer one"},
            {"role": "user", "content": "recent question two"},
            {"role": "assistant", "content": "recent answer two"},
            {"role": "tool", "content": "ignored tool output"},
        ]

        with patch.object(workspace_route, "resolve_request_user_id", return_value="admin_default"), patch.object(
            workspace_route,
            "build_analysis_context",
            return_value="personal context",
        ), patch.object(
            workspace_route,
            "build_project_repo_snapshot_context",
            return_value="project context",
        ), patch.object(
            workspace_route,
            "decide_execution_policy",
            return_value=self._policy_result(),
        ), patch.object(
            workspace_route,
            "execute_workspace_text_with_policy",
            side_effect=fake_execute_workspace_text_with_policy,
        ):
            result = workspace_route.workspace_chat(
                workspace_route.ChatRequest(
                    model="claude",
                    message="Continue from that comparison.",
                    conversation_intent="discussion",
                    signal_title="Signal",
                    recent_messages=recent_messages,
                ),
                request=SimpleNamespace(),
            )

        user_prompt = captured_kwargs["user_prompt"]
        self.assertEqual(captured_kwargs["max_tokens"], 3000)
        self.assertTrue(result["web_search_enabled"])
        self.assertIn("Recent discussion context:", user_prompt)
        self.assertIn("conversation memory only", user_prompt)
        self.assertIn("not AI Radar verified evidence", user_prompt)
        self.assertNotIn("oldest question", user_prompt)
        self.assertNotIn("older answer", user_prompt)
        self.assertIn("recent question one", user_prompt)
        self.assertIn("recent answer one", user_prompt)
        self.assertIn("recent question two", user_prompt)
        self.assertIn("recent answer two", user_prompt)
        self.assertNotIn("ignored tool output", user_prompt)


if __name__ == "__main__":
    unittest.main()
