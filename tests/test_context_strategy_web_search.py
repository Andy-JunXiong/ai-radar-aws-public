import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services.context_strategy_service import apply_policy_to_prompts  # noqa: E402
from app.services.execution_policy_service import ExecutionPolicy  # noqa: E402


class ContextStrategyWebSearchTests(unittest.TestCase):
    def test_web_search_metadata_relaxes_provided_context_only_policy(self):
        policy = ExecutionPolicy(
            mode="guarded",
            rag_enabled=True,
            citation_required=True,
            verification_required=True,
            max_context_chunks=4,
            model_tier="standard",
            fallback_allowed=True,
            output_mode="grounded",
            reason="test",
            validation_rules=[],
        )

        system_prompt, user_prompt = apply_policy_to_prompts(
            system_prompt="System",
            user_prompt="User",
            policy=policy,
            metadata={
                "source_count": 1,
                "context_label": "workspace_context_plus_web_search",
                "web_search_enabled": True,
            },
        )

        self.assertIn("context strategy: workspace_context_plus_web_search", system_prompt)
        self.assertIn("use the available web search tool", system_prompt)
        self.assertIn("[Web search: source/title/url]", system_prompt)
        self.assertIn("Do not claim that external search is unavailable", system_prompt)
        self.assertNotIn("Use only the provided context as evidence.", system_prompt)
        self.assertIn("Web search is also available", user_prompt)


if __name__ == "__main__":
    unittest.main()
