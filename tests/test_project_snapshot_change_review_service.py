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
from app.services import project_snapshot_change_review_service as service  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402


def project(project_id: str, *, status: str = "active", repo: str | None = None, enabled: bool = True):
    return {
        "project_id": project_id,
        "name": project_id.title(),
        "status": status,
        "enabled": enabled,
        "repo": repo if repo is not None else f"owner/{project_id}",
    }


def snapshot(
    *,
    snapshot_status: str = "fresh",
    delta_status: str = "unchanged",
    refresh_status: str = "fresh",
):
    return {
        "status": snapshot_status,
        "scanned_at": "2026-08-31T06:05:20+00:00",
        "message": f"Snapshot is {snapshot_status}.",
        "delta": {
            "status": delta_status,
            "from_sha": "a" * 40,
            "to_sha": "b" * 40,
            "total_commits": 2,
            "commits": [{"sha": "b" * 40}],
            "files": [{"path": "README.md"}, {"path": "STATUS.md"}],
            "truncated": False,
            "message": f"Delta is {delta_status}.",
        },
        "refresh": {
            "last_attempt_status": refresh_status,
            "last_attempted_at": "2026-08-31T06:05:20+00:00",
            "last_succeeded_at": "2026-08-31T06:05:20+00:00",
            "last_failure": None,
        },
    }


class ProjectSnapshotChangeReviewServiceTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_review_filters_scope_classifies_two_dimensions_and_sorts_for_review(self):
        projects = [
            project("unchanged"),
            project("changed"),
            project("baseline"),
            project("stale"),
            project("missing"),
            project("partial"),
            project("on-hold", status="on_hold"),
            project("hidden", enabled=False),
            project("no-repo", repo=""),
        ]
        snapshots = {
            "unchanged": snapshot(delta_status="unchanged"),
            "changed": snapshot(delta_status="changed"),
            "baseline": snapshot(delta_status="initial"),
            "stale": snapshot(snapshot_status="stale", delta_status="unchanged"),
            "partial": snapshot(snapshot_status="partial", delta_status="changed"),
        }

        result = service.build_project_snapshot_change_review(
            projects,
            snapshot_loader=lambda project_id: snapshots.get(project_id),
        )

        self.assertEqual(result["summary"]["total"], 6)
        self.assertEqual(result["summary"]["needs_attention"], 3)
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertEqual(result["summary"]["baseline"], 1)
        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertEqual(result["summary"]["stale"], 1)
        self.assertEqual(result["summary"]["partial"], 1)
        self.assertEqual(result["summary"]["missing"], 1)
        self.assertEqual(
            [item["review_state"] for item in result["items"]],
            ["needs_attention", "needs_attention", "needs_attention", "changed", "baseline", "unchanged"],
        )
        by_id = {item["project_id"]: item for item in result["items"]}
        self.assertEqual(by_id["changed"]["commit_count"], 2)
        self.assertEqual(by_id["changed"]["file_count"], 2)
        self.assertEqual(by_id["partial"]["review_state"], "needs_attention")
        self.assertEqual(by_id["stale"]["review_state"], "needs_attention")
        self.assertEqual(by_id["missing"]["delta_status"], "unavailable")
        self.assertNotIn("on-hold", by_id)
        self.assertNotIn("hidden", by_id)
        self.assertNotIn("no-repo", by_id)

    def test_failed_refresh_takes_priority_over_retained_usable_snapshot(self):
        retained = snapshot(snapshot_status="fresh", delta_status="unchanged")
        retained["refresh"] = {
            "last_attempt_status": "failed",
            "last_attempted_at": "2026-08-31T08:00:00+00:00",
            "last_succeeded_at": "2026-08-31T06:00:00+00:00",
            "last_failure": {"message": "GitHub rate limited."},
        }

        result = service.build_project_snapshot_change_review(
            [project("retained")],
            snapshot_loader=lambda _project_id: retained,
        )

        item = result["items"][0]
        self.assertEqual(item["snapshot_status"], "fresh")
        self.assertEqual(item["delta_status"], "unchanged")
        self.assertEqual(item["review_state"], "needs_attention")
        self.assertIn("GitHub rate limited", item["review_reason"])
        self.assertEqual(result["summary"]["failed"], 1)

    def test_route_requires_admin_auth(self):
        with patch("app.routes.projects.list_active_projects") as list_projects:
            response = TestClient(app).get("/projects/repo-snapshot-changes")

        self.assertEqual(response.status_code, 401)
        list_projects.assert_not_called()

    def test_route_returns_read_only_projection(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        expected = {
            "generated_at": "2026-08-31T08:00:00+00:00",
            "summary": {"total": 0},
            "items": [],
            "message": "project snapshot change review loaded successfully",
        }
        with patch("app.routes.projects.list_active_projects", return_value=[]), patch(
            "app.routes.projects.build_project_snapshot_change_review",
            return_value=expected,
        ) as build:
            response = TestClient(app).get("/projects/repo-snapshot-changes")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        build.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
