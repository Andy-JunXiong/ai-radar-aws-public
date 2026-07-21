import json
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


context_bridge = load_module(
    "backend_context_bridge",
    BACKEND_ROOT / "app" / "services" / "context_bridge.py",
)
request_identity_module = load_module(
    "backend_request_identity",
    BACKEND_ROOT / "app" / "services" / "request_identity.py",
)
resolve_request_user_id = request_identity_module.resolve_request_user_id


class RequestIdentityTests(unittest.TestCase):
    def test_resolves_user_id_from_primary_header(self):
        request = SimpleNamespace(headers={"x-ai-radar-user-id": "user-123"})

        self.assertEqual(resolve_request_user_id(request), "user-123")

    def test_resolves_user_id_from_fallback_header(self):
        request = SimpleNamespace(headers={"x-user-id": "user-456"})

        self.assertEqual(resolve_request_user_id(request), "user-456")

    def test_returns_none_without_supported_headers(self):
        request = SimpleNamespace(headers={"authorization": "Bearer token"})

        self.assertIsNone(resolve_request_user_id(request))


class ContextBridgeTests(unittest.TestCase):
    def test_prefers_user_specific_context_and_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            default_context_path = temp_root / "personal_context.json"
            user_context_dir = temp_root / "users" / "beta-user"
            user_context_dir.mkdir(parents=True)
            user_context_path = user_context_dir / "personal_context.json"

            default_context_path.write_text(
                json.dumps({"user_profile": {"role": "default-role"}}),
                encoding="utf-8",
            )
            user_context_path.write_text(
                json.dumps({"user_profile": {"role": "beta-role"}}),
                encoding="utf-8",
            )

            with patch.object(context_bridge, "PERSONAL_CONTEXT_PATH", default_context_path), patch.object(
                context_bridge, "USER_CONTEXTS_DIR", temp_root / "users"
            ):
                user_data = context_bridge.load_personal_context_data("beta-user")
                fallback_data = context_bridge.load_personal_context_data("missing-user")

        self.assertEqual(user_data["user_profile"]["role"], "beta-role")
        self.assertEqual(fallback_data["user_profile"]["role"], "default-role")

    def test_build_analysis_context_includes_user_id_when_provided(self):
        with patch.object(
            context_bridge,
            "load_personal_context_data",
            return_value={
                "user_profile": {"role": "builder"},
                "projects": [{"name": "AI Radar"}],
            },
        ):
            context_text = context_bridge.build_analysis_context("beta-user")

        self.assertIn("USER ID", context_text)
        self.assertIn("beta-user", context_text)
        self.assertIn("USER PROFILE", context_text)


if __name__ == "__main__":
    unittest.main()
