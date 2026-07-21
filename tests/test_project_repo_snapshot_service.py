import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import project_repo_snapshot_service as service  # noqa: E402


class ProjectRepoSnapshotServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="repo_snapshot_test_"))
        self.original_dir = service.PROJECT_REPO_SNAPSHOT_DIR
        service.PROJECT_REPO_SNAPSHOT_DIR = self.temp_dir

    def tearDown(self):
        service.PROJECT_REPO_SNAPSHOT_DIR = self.original_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_repo_snapshot_is_not_connected_and_saved(self):
        snapshot = service.build_light_project_repo_snapshot(
            {
                "project_id": "ai_radar",
                "name": "AI Radar",
                "repo": "",
                "topics": ["AI intelligence"],
            }
        )

        self.assertEqual(snapshot["status"], "not_connected")
        self.assertFalse(snapshot["readme_found"])
        self.assertEqual(snapshot["repo"], "")
        self.assertTrue((self.temp_dir / "ai_radar.json").exists())

    def test_light_snapshot_uses_repo_context_tree_commits_and_manifests(self):
        with patch.object(
            service,
            "fetch_project_github_context",
            return_value={
                "status": "loaded",
                "message": "loaded",
                "repository": {
                    "full_name": "Andy-JunXiong/ai-radar-aws",
                    "description": "AI Radar project intelligence system.",
                },
                "readme": {"path": "README.md", "content": "AI Radar\n\nProject context."},
                "roadmap": {"path": "ROADMAP.md", "content": "Roadmap"},
            },
        ), patch.object(
            service,
            "fetch_repo_top_level_tree",
            return_value=[
                {"name": "frontend", "path": "frontend", "type": "dir"},
                {"name": "backend", "path": "backend", "type": "dir"},
                {"name": "docs", "path": "docs", "type": "dir"},
            ],
        ), patch.object(
            service,
            "fetch_repo_recent_commits",
            return_value=[{"sha": "abc123", "message": "add snapshot"}],
        ), patch.object(
            service,
            "fetch_repo_manifest_files",
            return_value=[{"path": "frontend/package.json"}, {"path": "backend/requirements.txt"}],
        ):
            snapshot = service.build_light_project_repo_snapshot(
                {
                    "project_id": "ai_radar",
                    "name": "AI Radar",
                    "repo": "https://github.com/Andy-JunXiong/ai-radar-aws",
                    "topics": ["AI intelligence"],
                }
            )

        self.assertEqual(snapshot["status"], "fresh")
        self.assertEqual(snapshot["repo"], "Andy-JunXiong/ai-radar-aws")
        self.assertTrue(snapshot["readme_found"])
        self.assertTrue(snapshot["roadmap_found"])
        self.assertIn("AI Radar", snapshot["readme_excerpt"])
        self.assertIn("Roadmap", snapshot["roadmap_excerpt"])
        self.assertIn("frontend/backend split", snapshot["architecture_hints"])
        self.assertIn("node/frontend manifest", snapshot["architecture_hints"])
        self.assertIn("python backend manifest", snapshot["architecture_hints"])
        self.assertEqual(snapshot["recent_commits"][0]["message"], "add snapshot")

    def test_light_snapshot_marks_partial_when_some_sections_load_after_github_context_failure(self):
        with patch.object(
            service,
            "fetch_project_github_context",
            return_value={
                "status": "unreachable",
                "message": "GitHub context unavailable.",
                "readme": {"path": "docs/README.md", "content": "AI Radar Docs"},
                "roadmap": {"path": "docs/roadmap.md", "content": "Roadmap"},
            },
        ), patch.object(
            service,
            "fetch_repo_top_level_tree",
            return_value=[{"name": "backend", "path": "backend", "type": "dir"}],
        ), patch.object(
            service,
            "fetch_repo_recent_commits",
            return_value=[{"sha": "abc123", "message": "recent work"}],
        ), patch.object(
            service,
            "fetch_repo_manifest_files",
            return_value=[{"path": "requirements.txt"}],
        ):
            snapshot = service.build_light_project_repo_snapshot(
                {
                    "project_id": "ai_radar",
                    "name": "AI Radar",
                    "repo": "Andy-JunXiong/ai-radar-aws",
                }
            )

        self.assertEqual(snapshot["status"], "partial")
        self.assertTrue(snapshot["readme_found"])
        self.assertTrue(snapshot["roadmap_found"])
        self.assertIn("partially loaded", snapshot["message"])

    def test_after_save_reuses_existing_snapshot_when_repo_is_unchanged(self):
        project = {
            "project_id": "ai_radar",
            "name": "AI Radar",
            "repo": "Andy-JunXiong/ai-radar-aws",
        }
        service.save_project_repo_snapshot(
            "ai_radar",
            {
                "status": "fresh",
                "repo": "Andy-JunXiong/ai-radar-aws",
                "scanned_at": "2026-05-26T00:00:00+00:00",
            },
        )

        with patch.object(service, "build_light_project_repo_snapshot") as build_snapshot:
            snapshot = service.maybe_refresh_project_repo_snapshot_after_save(
                project,
                previous_repo="Andy-JunXiong/ai-radar-aws",
            )

        build_snapshot.assert_not_called()
        self.assertEqual(snapshot["status"], "fresh")

    def test_load_normalizes_failed_snapshot_with_cached_context_to_partial(self):
        service.save_project_repo_snapshot(
            "ai_radar",
            {
                "status": "failed",
                "repo": "Andy-JunXiong/ai-radar-aws",
                "scanned_at": "2026-05-26T00:00:00+00:00",
                "summary": "# AI Radar Docs",
                "readme_found": True,
                "top_level_tree": [{"name": "backend", "path": "backend", "type": "dir"}],
                "message": "The repository is saved, but GitHub context could not be loaded right now.",
            },
        )

        snapshot = service.load_project_repo_snapshot("ai_radar")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["status"], "partial")


if __name__ == "__main__":
    unittest.main()
