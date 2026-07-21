import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for {module_name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


settings_route = load_module(
    "backend_settings_route",
    BACKEND_ROOT / "app" / "routes" / "settings.py",
)
context_bridge = load_module(
    "backend_context_bridge_for_settings",
    BACKEND_ROOT / "app" / "services" / "context_bridge.py",
)


class SettingsContextRouteTests(unittest.TestCase):
    def test_get_personal_context_returns_demo_default_without_user_header(self):
        request = SimpleNamespace(headers={})

        with patch.object(
            settings_route,
            "load_personal_context_data",
            return_value={"user_profile": {"role": "demo"}},
        ), patch.object(
            settings_route,
            "get_context_scope",
            return_value="demo_default",
        ):
            result = settings_route.get_personal_context(request)

        self.assertIsNone(result["user_id"])
        self.assertEqual(result["scope"], "demo_default")
        self.assertEqual(result["context"]["user_profile"]["role"], "demo")

    def test_save_personal_context_requires_user_id(self):
        request = SimpleNamespace(headers={})
        payload = settings_route.PersonalContextUpdateRequest(context={"user_profile": {"role": "beta"}})

        with self.assertRaises(settings_route.HTTPException) as exc:
            settings_route.save_personal_context(payload, request)

        self.assertEqual(exc.exception.status_code, 400)

    def test_save_personal_context_writes_user_specific_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            user_context_root = temp_root / "users"
            request = SimpleNamespace(headers={"x-ai-radar-user-id": "beta-user"})
            payload = settings_route.PersonalContextUpdateRequest(
                context={"user_profile": {"role": "beta"}}
            )

            with patch.object(context_bridge, "USER_CONTEXTS_DIR", user_context_root), patch.object(
                settings_route,
                "save_personal_context_data",
                side_effect=context_bridge.save_personal_context_data,
            ):
                result = settings_route.save_personal_context(payload, request)

            saved_path = user_context_root / "beta-user" / "personal_context.json"
            saved_exists = saved_path.exists()

        self.assertEqual(result["user_id"], "beta-user")
        self.assertEqual(result["scope"], "user_specific")
        self.assertEqual(result["path"], str(saved_path))
        self.assertTrue(saved_exists)

    def test_save_subscription_settings_returns_cloud_sync_status(self):
        request = SimpleNamespace(headers={"x-ai-radar-user-id": "admin_default"})
        payload = settings_route.SubscriptionSettingsUpdateRequest(
            settings={
                "sources": [
                    {
                        "name": "Example Feed",
                        "url": "https://example.com/feed.xml",
                        "type": "rss",
                        "enabled": True,
                    }
                ]
            }
        )

        with patch.object(
            settings_route,
            "save_subscription_settings_with_status",
            return_value={
                "path": Path("backend/data/settings/subscriptions/admin_default.json"),
                "local_saved": True,
                "source_count": 1,
                "s3_sync": "succeeded",
                "s3_bucket": "example-bucket",
                "s3_key": "settings/subscriptions/admin_default.json",
                "s3_error_type": "",
            },
        ):
            result = settings_route.save_subscriptions(payload, request)

        self.assertEqual(result["user_id"], "admin_default")
        self.assertTrue(result["local_saved"])
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["s3_sync"], "succeeded")
        self.assertEqual(result["s3_key"], "settings/subscriptions/admin_default.json")

    def test_source_health_route_returns_advisory_report(self):
        payload = settings_route.SourceHealthRequest(
            sources=[
                {
                    "id": "feed",
                    "name": "Example Feed",
                    "url": "https://example.com/feed.xml",
                    "type": "rss",
                    "enabled": True,
                }
            ]
        )

        with patch.object(
            settings_route,
            "check_subscription_source_health",
            return_value={"items": [], "summary": {"total": 1, "ok": 1}},
        ) as checker:
            result = settings_route.source_health(payload)

        checker.assert_called_once_with(payload.sources)
        self.assertEqual(result["summary"]["ok"], 1)

    def test_get_model_routing_status_includes_telemetry(self):
        with patch.object(
            settings_route,
            "router_startup_diagnostics",
            return_value={
                "routes": {"insight": {"provider": "anthropic"}},
                "route_details": {
                    "insight": {
                        "provider_resolution": {"selected_from": "MODEL_ROUTER_ANALYSIS_PROVIDER"}
                    }
                },
            },
        ), patch.object(
            settings_route,
            "load_route_summary",
            return_value={"total_events": 3, "fallback_count": 1},
        ):
            result = settings_route.get_model_routing_status()

        self.assertEqual(result["routes"]["insight"]["provider"], "anthropic")
        self.assertEqual(
            result["route_details"]["insight"]["provider_resolution"]["selected_from"],
            "MODEL_ROUTER_ANALYSIS_PROVIDER",
        )
        self.assertEqual(result["telemetry"]["total_events"], 3)
        self.assertEqual(result["telemetry"]["fallback_count"], 1)


if __name__ == "__main__":
    unittest.main()
