import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.model_router_service import (  # noqa: E402
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    TIER_2,
    route_task,
    router_startup_diagnostics,
)


class BackendModelRouterServiceTests(unittest.TestCase):
    def test_manual_text_defaults_to_anthropic_when_available(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_MODEL": "gpt-4.1-mini",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            route = route_task("manual_text")

        self.assertEqual(route.tier, TIER_2)
        self.assertEqual(route.provider, PROVIDER_ANTHROPIC)

    def test_manual_image_prefers_anthropic_when_available(self):
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
            clear=True,
        ):
            route = route_task("manual_image")

        self.assertEqual(route.provider, PROVIDER_ANTHROPIC)
        self.assertEqual(route.model, "claude-sonnet-4-6")

    def test_router_diagnostics_include_insight_and_manual_routes(self):
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
            clear=False,
        ):
            diagnostics = router_startup_diagnostics()

        routes = diagnostics.get("routes", {})
        self.assertIn("insight", routes)
        self.assertIn("manual_text_session", routes)
        self.assertIn("route_details", diagnostics)

    def test_router_diagnostics_explain_ignored_incompatible_model(self):
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "MODEL_ROUTER_TIER2_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ):
            diagnostics = router_startup_diagnostics()

        manual_text = diagnostics["route_details"]["manual_text_session"]
        self.assertEqual(manual_text["model"], "claude-sonnet-4-6")
        incompatible_candidate = next(
            candidate
            for candidate in manual_text["model_resolution"]["candidates"]
            if candidate["source"] == "MODEL_ROUTER_TIER2_MODEL"
        )
        self.assertFalse(incompatible_candidate["compatible"])
        self.assertFalse(incompatible_candidate["used"])
        self.assertTrue(
            any(
                "MODEL_ROUTER_TIER2_MODEL=gpt-4.1-mini is incompatible with provider 'anthropic'"
                in warning
                for warning in diagnostics["warnings"]
            )
        )

    def test_anthropic_route_ignores_incompatible_generic_tier_model(self):
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "MODEL_ROUTER_TIER2_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ):
            route = route_task("manual_text")

        self.assertEqual(route.provider, PROVIDER_ANTHROPIC)
        self.assertEqual(route.model, "claude-sonnet-4-6")

    def test_openai_route_ignores_incompatible_generic_tier_model(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_MODEL": "gpt-4.1-mini",
                "MODEL_ROUTER_TIER2_MODEL": "claude-sonnet-4-6",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ):
            route = route_task("manual_text")

        self.assertEqual(route.provider, PROVIDER_OPENAI)
        self.assertEqual(route.model, "gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
