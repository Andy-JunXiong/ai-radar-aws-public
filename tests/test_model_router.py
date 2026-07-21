import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence.model_router import (  # noqa: E402
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    TIER_1,
    TIER_2,
    TIER_3,
    route_task,
)


class ModelRouterTests(unittest.TestCase):
    def test_extract_routes_to_tier_1_openai(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "fallback-model",
                "MODEL_ROUTER_TIER1_MODEL": "fast-model",
                "MODEL_ROUTER_TIER1_PROVIDER": "openai",
            },
            clear=False,
        ):
            route = route_task("extract")

        self.assertEqual(route.tier, TIER_1)
        self.assertEqual(route.provider, PROVIDER_OPENAI)
        self.assertEqual(route.model, "fast-model")

    def test_structure_routes_to_tier_2_with_anthropic_default(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "baseline-model",
                "OPENAI_MODEL": "structured-model",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            route = route_task("structure")

        self.assertEqual(route.tier, TIER_2)
        self.assertEqual(route.provider, PROVIDER_ANTHROPIC)
        self.assertEqual(route.model, "claude-sonnet-4-6")

    def test_strategy_prefers_anthropic_when_key_exists(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "baseline-model",
                "ANTHROPIC_MODEL": "strategic-model",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            route = route_task("strategy")

        self.assertEqual(route.tier, TIER_3)
        self.assertEqual(route.provider, PROVIDER_ANTHROPIC)
        self.assertEqual(route.model, "strategic-model")

    def test_unknown_task_falls_back_to_structure_tier(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "baseline-model",
                "OPENAI_MODEL": "structured-model",
            },
            clear=False,
        ):
            route = route_task("unknown-task")

        self.assertEqual(route.tier, TIER_2)
        self.assertEqual(route.task_type, "unknown-task")

    def test_env_override_can_force_tier_3_to_openai(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "baseline-model",
                "MODEL_ROUTER_TIER3_PROVIDER": "openai",
                "MODEL_ROUTER_TIER3_MODEL": "o3-mini",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            route = route_task("strategy")

        self.assertEqual(route.provider, PROVIDER_OPENAI)
        self.assertEqual(route.model, "o3-mini")


if __name__ == "__main__":
    unittest.main()
