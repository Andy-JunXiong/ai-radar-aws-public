import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import admin_auth  # noqa: E402


class AdminAuthSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.auth_dir = Path(self.temp_dir.name)
        self.original_auth_dir = admin_auth.AUTH_DIR
        self.original_auth_file = admin_auth.AUTH_FILE
        admin_auth.AUTH_DIR = self.auth_dir
        admin_auth.AUTH_FILE = self.auth_dir / "admin_auth.json"
        admin_auth.ACTIVE_TOKENS.clear()

    def tearDown(self):
        admin_auth.AUTH_DIR = self.original_auth_dir
        admin_auth.AUTH_FILE = self.original_auth_file
        admin_auth.ACTIVE_TOKENS.clear()
        self.temp_dir.cleanup()

    def _read_payload(self):
        return json.loads(admin_auth.AUTH_FILE.read_text(encoding="utf-8"))

    def test_valid_token_refreshes_last_seen_timestamp(self):
        with patch("app.services.admin_auth.time.time", return_value=1000.0):
            admin_auth.create_admin_account("admin", "password123")
            admin_auth.add_admin_token("session-token")

        with patch("app.services.admin_auth.time.time", return_value=1100.0):
            self.assertTrue(admin_auth.is_valid_admin_token("session-token"))

        payload = self._read_payload()
        self.assertEqual(payload["tokens"][0]["token"], "session-token")
        self.assertEqual(payload["tokens"][0]["last_seen_at"], 1100.0)

    def test_idle_token_expires_after_sixty_minutes(self):
        with patch("app.services.admin_auth.time.time", return_value=1000.0):
            admin_auth.create_admin_account("admin", "password123")
            admin_auth.add_admin_token("session-token")

        with patch("app.services.admin_auth.time.time", return_value=1000.0 + 59 * 60):
            self.assertTrue(admin_auth.is_valid_admin_token("session-token"))

        with patch("app.services.admin_auth.time.time", return_value=1000.0 + 120 * 60 + 1):
            self.assertFalse(admin_auth.is_valid_admin_token("session-token"))

        self.assertEqual(self._read_payload()["tokens"], [])

    def test_legacy_string_tokens_are_not_valid_sessions(self):
        admin_auth.save_admin_auth_payload(
            {
                "username": "admin",
                "password_hash": "hash",
                "salt": "salt",
                "tokens": ["legacy-token"],
            }
        )

        self.assertFalse(admin_auth.is_valid_admin_token("legacy-token"))
        self.assertEqual(self._read_payload()["tokens"], [])

    def test_invalid_token_without_admin_account_does_not_create_empty_auth_file(self):
        self.assertFalse(admin_auth.AUTH_FILE.exists())

        self.assertFalse(admin_auth.is_valid_admin_token("missing-token"))

        self.assertFalse(admin_auth.AUTH_FILE.exists())

    def test_logout_without_admin_account_does_not_create_empty_auth_file(self):
        self.assertFalse(admin_auth.AUTH_FILE.exists())

        admin_auth.remove_admin_token("missing-token")

        self.assertFalse(admin_auth.AUTH_FILE.exists())

    def test_add_token_without_admin_account_does_not_create_empty_auth_file(self):
        self.assertFalse(admin_auth.AUTH_FILE.exists())

        admin_auth.add_admin_token("session-token")

        self.assertFalse(admin_auth.AUTH_FILE.exists())

    def test_auth_file_with_utf8_bom_is_loaded(self):
        payload = {
            "username": "admin",
            "password_hash": "hash",
            "salt": "salt",
            "tokens": [],
        }
        admin_auth.AUTH_FILE.write_text(
            "\ufeff" + json.dumps(payload),
            encoding="utf-8",
        )

        self.assertTrue(admin_auth.has_admin_account())

    def test_auth_file_with_trailing_garbage_is_loaded(self):
        payload = {
            "username": "admin",
            "password_hash": "hash",
            "salt": "salt",
            "tokens": [],
        }
        admin_auth.AUTH_FILE.write_text(
            json.dumps(payload) + "}\n",
            encoding="utf-8",
        )

        self.assertTrue(admin_auth.has_admin_account())


if __name__ == "__main__":
    unittest.main()
