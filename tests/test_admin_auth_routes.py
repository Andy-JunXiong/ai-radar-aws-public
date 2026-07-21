import sys
import shutil
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi import HTTPException


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes.auth import AdminLoginRequest, AdminPasswordChangeRequest, auth_change_password, auth_login  # noqa: E402
from app.services import admin_auth as auth_service  # noqa: E402


class AdminAuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = REPO_ROOT / "tmp_admin_auth_route_tests"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True)
        self.previous_auth_dir = auth_service.AUTH_DIR
        self.previous_auth_file = auth_service.AUTH_FILE
        self.previous_legacy_auth_file = auth_service.LEGACY_AUTH_FILE
        self.previous_read_s3_payload = auth_service._read_s3_payload
        self.previous_write_s3_payload = auth_service._write_s3_payload

        auth_service.AUTH_DIR = self.temp_dir
        auth_service.AUTH_FILE = self.temp_dir / "admin_auth.json"
        auth_service.LEGACY_AUTH_FILE = self.temp_dir / "legacy_admin_auth.json"
        auth_service._read_s3_payload = lambda: None
        auth_service._write_s3_payload = lambda payload: None
        auth_service.ACTIVE_TOKENS.clear()

    def tearDown(self):
        auth_service.AUTH_DIR = self.previous_auth_dir
        auth_service.AUTH_FILE = self.previous_auth_file
        auth_service.LEGACY_AUTH_FILE = self.previous_legacy_auth_file
        auth_service._read_s3_payload = self.previous_read_s3_payload
        auth_service._write_s3_payload = self.previous_write_s3_payload
        auth_service.ACTIVE_TOKENS.clear()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_change_password_invalidates_existing_tokens_and_requires_new_login(self):
        auth_service.create_admin_account("admin", "old-password")
        login_result = auth_login(AdminLoginRequest(username="admin", password="old-password"))
        old_token = login_result["token"]

        self.assertTrue(auth_service.is_valid_admin_token(old_token))

        result = auth_change_password(
            AdminPasswordChangeRequest(current_password="old-password", new_password="new-password"),
            x_ai_radar_admin_token=old_token,
        )

        self.assertIn("sign in again", result["message"])
        self.assertFalse(auth_service.is_valid_admin_token(old_token))

        with self.assertRaises(HTTPException):
            auth_login(AdminLoginRequest(username="admin", password="old-password"))

        new_login_result = auth_login(AdminLoginRequest(username="admin", password="new-password"))
        self.assertTrue(auth_service.is_valid_admin_token(new_login_result["token"]))

    def test_load_prefers_s3_payload_and_refreshes_local_cache(self):
        auth_service.AUTH_FILE.write_text(
            '{"username":"local","password_hash":"local-hash","salt":"local-salt","tokens":[]}',
            encoding="utf-8",
        )
        auth_service._read_s3_payload = lambda: {
            "username": "s3-admin",
            "password_hash": "s3-hash",
            "salt": "s3-salt",
            "tokens": ["s3-token"],
        }

        payload = auth_service.load_admin_auth_payload()

        self.assertEqual(payload["username"], "s3-admin")
        self.assertTrue(auth_service.is_valid_admin_token("s3-token"))
        self.assertIn("s3-admin", auth_service.AUTH_FILE.read_text(encoding="utf-8"))

    def test_save_writes_local_payload_and_s3_payload(self):
        written_payloads = []
        auth_service._write_s3_payload = lambda payload: written_payloads.append(dict(payload))

        auth_service.create_admin_account("admin", "new-password")

        self.assertTrue(auth_service.AUTH_FILE.exists())
        self.assertEqual(written_payloads[-1]["username"], "admin")
        self.assertEqual(written_payloads[-1]["tokens"], [])

    def test_s3_bucket_defaults_to_shared_ai_radar_bucket_without_env(self):
        with patch.dict(auth_service.os.environ, {}, clear=True):
            self.assertEqual(auth_service._s3_bucket(), "ai-radar-junxiong-data")

    def test_s3_auth_is_disabled_locally_unless_explicitly_enabled(self):
        with patch.dict(auth_service.os.environ, {}, clear=True):
            self.assertFalse(auth_service._s3_auth_enabled())

        with patch.dict(auth_service.os.environ, {"AI_RADAR_AUTH_S3_ENABLED": "true"}, clear=True):
            self.assertTrue(auth_service._s3_auth_enabled())

        with patch.dict(auth_service.os.environ, {"AWS_EXECUTION_ENV": "AWS_ECS_FARGATE"}, clear=True):
            self.assertTrue(auth_service._s3_auth_enabled())


if __name__ == "__main__":
    unittest.main()
