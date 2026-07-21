import io
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402
from app.services import dev_inbox_draft_service as draft_service  # noqa: E402


class FakeS3Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_calls: list[dict[str, object]] = []

    def get_object(self, *, Bucket: str, Key: str):
        payload = self.objects[(Bucket, Key)]
        return {"Body": io.BytesIO(payload)}

    def put_object(self, **kwargs):
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        body = kwargs["Body"]
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.objects[(bucket, key)] = body
        self.put_calls.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class DevInboxAppRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = REPO_ROOT / ".tmp-tests" / "dev_inbox_app_route"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.previous_data_dir = draft_service.DATA_DIR
        self.previous_index_path = draft_service.INDEX_PATH
        draft_service.DATA_DIR = self.temp_dir
        draft_service.INDEX_PATH = self.temp_dir / "index.json"

    def tearDown(self):
        app.dependency_overrides.clear()
        draft_service.DATA_DIR = self.previous_data_dir
        draft_service.INDEX_PATH = self.previous_index_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _authorize(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

    def _payload(self, **overrides):
        payload = {
            "id": "legacy-1",
            "repo": "Andy-JunXiong/ai-radar-aws",
            "branch": "main",
            "requestType": "bug",
            "priority": "high",
            "surface": "/signals/detail",
            "task": "Fix a focused UI bug and validate the affected route.",
            "savedAt": "2026-06-19T00:00:00+00:00",
            "status": "open",
        }
        payload.update(overrides)
        return payload

    def test_routes_keep_admin_guard(self):
        with patch("app.routes.dev_inbox.draft_service.upsert_dev_inbox_draft") as mock_upsert:
            response = TestClient(app).post("/dev-inbox/drafts", json=self._payload())

        self.assertEqual(response.status_code, 401)
        mock_upsert.assert_not_called()

    def test_create_list_update_and_delete_draft(self):
        self._authorize()
        client = TestClient(app)

        created = client.post("/dev-inbox/drafts", json=self._payload())
        listed = client.get("/dev-inbox/drafts")
        updated = client.patch("/dev-inbox/drafts/legacy-1", json={"status": "done"})
        deleted = client.delete("/dev-inbox/drafts/legacy-1")
        listed_after_delete = client.get("/dev-inbox/drafts")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["draft"]["id"], "legacy-1")
        self.assertEqual(created.json()["storage"]["backend"], "local_file")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertEqual(listed.json()["storage"]["backend"], "local_file")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["draft"]["status"], "done")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(listed_after_delete.json()["count"], 0)

    def test_rejects_empty_task_and_invalid_status(self):
        self._authorize()
        client = TestClient(app)

        empty_task = client.post("/dev-inbox/drafts", json=self._payload(task=" "))
        created = client.post("/dev-inbox/drafts", json=self._payload())
        invalid_status = client.patch("/dev-inbox/drafts/legacy-1", json={"status": "archived"})

        self.assertEqual(empty_task.status_code, 400)
        self.assertIn("task is required", empty_task.json()["detail"])
        self.assertEqual(created.status_code, 200)
        self.assertEqual(invalid_status.status_code, 400)

    def test_upsert_preserves_single_record_for_legacy_migration_id(self):
        self._authorize()
        client = TestClient(app)

        first = client.post("/dev-inbox/drafts", json=self._payload(task="First draft body."))
        second = client.post("/dev-inbox/drafts", json=self._payload(task="Updated draft body."))
        listed = client.get("/dev-inbox/drafts")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertEqual(listed.json()["drafts"][0]["task"], "Updated draft body.")

    def test_s3_enabled_store_reads_and_writes_single_index_object(self):
        fake_s3 = FakeS3Client()
        env = {
            "AI_RADAR_DEV_INBOX_S3_ENABLED": "1",
            "S3_BUCKET": "ai-radar-test-bucket",
            "AI_RADAR_DEV_INBOX_S3_KEY": "dev-inbox/drafts/index.json",
        }

        with patch.dict(os.environ, env, clear=False), patch.object(draft_service, "_s3_client", return_value=fake_s3):
            created = draft_service.upsert_dev_inbox_draft(self._payload())
            listed = draft_service.list_dev_inbox_drafts()
            updated = draft_service.update_dev_inbox_draft_status("legacy-1", "done")
            deleted = draft_service.delete_dev_inbox_draft("legacy-1")
            listed_after_delete = draft_service.list_dev_inbox_drafts()
            storage = draft_service.get_dev_inbox_storage_status()

        self.assertEqual(created["id"], "legacy-1")
        self.assertEqual(listed[0]["id"], "legacy-1")
        self.assertEqual(updated["status"], "done")
        self.assertTrue(deleted)
        self.assertEqual(listed_after_delete, [])
        self.assertEqual(storage["backend"], "s3")
        self.assertEqual(storage["s3_key"], "dev-inbox/drafts/index.json")
        self.assertGreaterEqual(len(fake_s3.put_calls), 3)
        stored = json.loads(fake_s3.objects[("ai-radar-test-bucket", "dev-inbox/drafts/index.json")].decode("utf-8"))
        self.assertEqual(stored, {"drafts": []})


if __name__ == "__main__":
    unittest.main()
