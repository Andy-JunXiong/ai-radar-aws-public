import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import project_snapshot_refresh_service as service  # noqa: E402


class ProjectSnapshotRefreshServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

    def test_due_policy_uses_last_usable_scan_time(self):
        self.assertTrue(service.project_snapshot_is_due(None, now=self.now))
        self.assertTrue(
            service.project_snapshot_is_due(
                {"scanned_at": "2026-08-30T12:00:00+00:00"},
                now=self.now,
            )
        )
        self.assertFalse(
            service.project_snapshot_is_due(
                {"scanned_at": "2026-08-31T00:00:01+00:00"},
                now=self.now,
            )
        )
        self.assertTrue(service.project_snapshot_is_due({"scanned_at": "invalid"}, now=self.now))

    def test_batch_filters_scope_skips_fresh_and_isolates_failures(self):
        projects = [
            {"project_id": "due", "enabled": True, "status": "active", "repo": "owner/due"},
            {"project_id": "fresh", "enabled": True, "status": "active", "repo": "owner/fresh"},
            {"project_id": "failed", "enabled": True, "status": "active", "repo": "owner/failed"},
            {"project_id": "on-hold", "enabled": True, "status": "on_hold", "repo": "owner/hold"},
            {"project_id": "no-repo", "enabled": True, "status": "active", "repo": ""},
        ]

        def load_snapshot(project_id):
            if project_id == "fresh":
                return {"status": "fresh", "scanned_at": "2026-08-31T11:00:00+00:00"}
            return {"status": "fresh", "scanned_at": "2026-08-29T11:00:00+00:00"}

        def refresh(project, *, force_refresh):
            self.assertTrue(force_refresh)
            if project["project_id"] == "failed":
                return {
                    "status": "fresh",
                    "scanned_at": "2026-08-29T11:00:00+00:00",
                    "refresh": {
                        "last_attempt_status": "failed",
                        "last_attempted_at": "2026-08-31T12:00:00+00:00",
                        "last_failure": {"message": "GitHub unavailable."},
                    },
                }
            return {
                "status": "fresh",
                "scanned_at": "2026-08-31T12:00:00+00:00",
                "refresh": {
                    "last_attempt_status": "fresh",
                    "last_attempted_at": "2026-08-31T12:00:00+00:00",
                },
            }

        with patch.object(service, "load_project_repo_snapshot", side_effect=load_snapshot), patch.object(
            service, "get_or_refresh_project_repo_snapshot", side_effect=refresh
        ):
            result = service.refresh_due_project_snapshots(projects=projects, now=self.now)

        self.assertEqual(result["eligible_project_count"], 3)
        self.assertEqual(result["counts"]["refreshed"], 1)
        self.assertEqual(result["counts"]["skipped_fresh"], 1)
        self.assertEqual(result["counts"]["failed"], 1)
        self.assertEqual(result["status"], "partial")
        by_id = {item["project_id"]: item for item in result["items"]}
        self.assertEqual(by_id["fresh"]["result"], "skipped_fresh")
        self.assertEqual(by_id["failed"]["message"], "GitHub unavailable.")
        self.assertNotIn("on-hold", by_id)
        self.assertNotIn("no-repo", by_id)

    def test_dry_run_reports_due_without_refreshing(self):
        projects = [{"project_id": "due", "enabled": True, "status": "active", "repo": "owner/due"}]
        with patch.object(service, "load_project_repo_snapshot", return_value=None), patch.object(
            service, "get_or_refresh_project_repo_snapshot"
        ) as refresh:
            result = service.refresh_due_project_snapshots(projects=projects, now=self.now, dry_run=True)

        refresh.assert_not_called()
        self.assertEqual(result["counts"]["due"], 1)
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
