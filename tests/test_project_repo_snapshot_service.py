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
from app.services import github_project_reader as reader  # noqa: E402


class ProjectRepoSnapshotServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="repo_snapshot_test_"))
        self.original_dir = service.PROJECT_REPO_SNAPSHOT_DIR
        service.PROJECT_REPO_SNAPSHOT_DIR = self.temp_dir
        self.head_patcher = patch.object(
            service,
            "fetch_repo_head",
            return_value={
                "sha": "a" * 40,
                "branch": "main",
                "committed_at": "2026-08-30T10:00:00Z",
                "html_url": "https://example.test/commit/head",
            },
        )
        self.fetch_head = self.head_patcher.start()

    def tearDown(self):
        self.head_patcher.stop()
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
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertFalse(snapshot["readme_found"])
        self.assertEqual(snapshot["repo"], "")
        self.assertEqual(snapshot["delta"]["status"], "unavailable")
        self.assertTrue((self.temp_dir / "ai_radar.json").exists())

    def test_deterministic_summary_skips_markdown_heading_quote_and_badge(self):
        summary = service._deterministic_summary(
            """# Project title

> **A bold marketing tagline that should not become the project summary.**

[![CI](https://example.test/badge.svg)](https://example.test/actions)

A governed [data platform](https://example.test/platform) that turns source records into auditable analytics and bounded forecasts.
"""
        )

        self.assertEqual(
            summary,
            "A governed data platform that turns source records into auditable analytics and bounded forecasts.",
        )

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
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(snapshot["delta"]["status"], "initial")
        self.assertEqual(snapshot["observation"]["head"]["sha"], "a" * 40)
        self.assertEqual(snapshot["observation"]["baseline"]["sha"], "a" * 40)
        self.assertEqual(snapshot["interpretation"]["method"], "deterministic_v1")
        self.assertEqual(snapshot["discovery"]["mode"], "heuristic")
        self.assertEqual(snapshot["discovery"]["config_status"], "absent")
        self.assertEqual(snapshot["repo"], "Andy-JunXiong/ai-radar-aws")
        self.assertTrue(snapshot["readme_found"])
        self.assertTrue(snapshot["roadmap_found"])
        self.assertIn("AI Radar", snapshot["readme_excerpt"])
        self.assertIn("Roadmap", snapshot["roadmap_excerpt"])
        self.assertIn("frontend/backend split", snapshot["architecture_hints"])
        self.assertIn("node/frontend manifest", snapshot["architecture_hints"])
        self.assertIn("python backend manifest", snapshot["architecture_hints"])
        self.assertEqual(snapshot["recent_commits"][0]["message"], "add snapshot")

    def test_configured_snapshot_uses_truth_map_without_heuristic_document_discovery(self):
        anchors = [
            {
                "kind": "readme",
                "path": "docs/overview.md",
                "required": True,
                "content_mode": "excerpt",
                "found": True,
                "sha": "readme-sha",
                "size": 120,
                "excerpt": "Configured overview",
            },
            {
                "kind": "dependency_manifest",
                "path": "pyproject.toml",
                "required": False,
                "content_mode": "metadata_only",
                "found": True,
                "sha": "manifest-sha",
                "size": 80,
            },
        ]
        project = {
            "project_id": "configured",
            "name": "Configured Project",
            "repo": "owner/configured",
            "metadata": {
                "repo_context": {
                    "truth_map": {
                        "schema_version": 1,
                        "anchors": [
                            {"kind": "readme", "path": "docs/overview.md", "required": True},
                            {
                                "kind": "dependency_manifest",
                                "path": "pyproject.toml",
                                "content_mode": "metadata_only",
                            },
                        ],
                    }
                }
            },
        }

        with patch.object(
            service,
            "fetch_repo_metadata",
            return_value={"full_name": "owner/configured", "description": "Configured repo"},
        ), patch.object(service, "fetch_repo_top_level_tree", return_value=[]), patch.object(
            service, "fetch_repo_recent_commits", return_value=[]
        ), patch.object(
            service, "fetch_repo_truth_map_anchors", return_value={"anchors": anchors, "errors": []}
        ), patch.object(service, "fetch_project_github_context") as heuristic_context, patch.object(
            service, "fetch_repo_manifest_files"
        ) as heuristic_manifests:
            snapshot = service.build_light_project_repo_snapshot(project)

        self.assertEqual(snapshot["status"], "fresh")
        self.assertEqual(snapshot["delta"]["status"], "initial")
        self.assertEqual(snapshot["discovery"], {"mode": "configured", "config_status": "valid", "config_errors": []})
        self.assertEqual(snapshot["anchors"], anchors)
        self.assertTrue(snapshot["readme_found"])
        self.assertEqual(snapshot["readme_path"], "docs/overview.md")
        self.assertEqual(snapshot["manifests"][0]["path"], "pyproject.toml")
        heuristic_context.assert_not_called()
        heuristic_manifests.assert_not_called()

    def test_configured_snapshot_is_partial_when_required_anchor_is_missing(self):
        project = {
            "project_id": "configured_missing",
            "name": "Configured Project",
            "repo": "owner/configured",
            "metadata": {
                "repo_context": {
                    "truth_map": {
                        "schema_version": 1,
                        "anchors": [{"kind": "roadmap", "path": "docs/roadmap.md", "required": True}],
                    }
                }
            },
        }
        with patch.object(
            service, "fetch_repo_metadata", return_value={"full_name": "owner/configured"}
        ), patch.object(service, "fetch_repo_top_level_tree", return_value=[]), patch.object(
            service, "fetch_repo_recent_commits", return_value=[]
        ), patch.object(
            service,
            "fetch_repo_truth_map_anchors",
            return_value={
                "anchors": [
                    {
                        "kind": "roadmap",
                        "path": "docs/roadmap.md",
                        "required": True,
                        "content_mode": "excerpt",
                        "found": False,
                    }
                ],
                "errors": [],
            },
        ):
            snapshot = service.build_light_project_repo_snapshot(project)

        self.assertEqual(snapshot["status"], "partial")
        self.assertIn("Required anchors missing", snapshot["message"])

    def test_invalid_truth_map_does_not_use_heuristic_discovery(self):
        project = {
            "project_id": "configured_invalid",
            "name": "Configured Project",
            "repo": "owner/configured",
            "metadata": {
                "repo_context": {
                    "truth_map": {
                        "schema_version": 1,
                        "anchors": [{"kind": "roadmap", "path": "../roadmap.md"}],
                    }
                }
            },
        }
        with patch.object(
            service, "fetch_repo_metadata", return_value={"full_name": "owner/configured"}
        ), patch.object(service, "fetch_repo_top_level_tree", return_value=[]), patch.object(
            service, "fetch_repo_recent_commits", return_value=[]
        ), patch.object(service, "fetch_project_github_context") as heuristic_context, patch.object(
            service, "fetch_repo_manifest_files"
        ) as heuristic_manifests, patch.object(service, "fetch_repo_truth_map_anchors") as configured_anchors:
            snapshot = service.build_light_project_repo_snapshot(project)

        self.assertEqual(snapshot["status"], "partial")
        self.assertEqual(snapshot["discovery"]["config_status"], "invalid")
        self.assertTrue(snapshot["discovery"]["config_errors"])
        self.assertIn("heuristic document discovery was not used", snapshot["message"])
        heuristic_context.assert_not_called()
        heuristic_manifests.assert_not_called()
        configured_anchors.assert_not_called()

    def test_truth_map_anchor_reader_bounds_excerpt_and_omits_metadata_only_content(self):
        with patch.object(
            reader,
            "fetch_repo_content_entry",
            side_effect=[
                {
                    "path": "README.md",
                    "sha": "abc",
                    "size": 900,
                    "html_url": "https://example.test/readme",
                    "content": "x" * 900,
                },
                {
                    "path": "pyproject.toml",
                    "sha": "def",
                    "size": 120,
                    "html_url": "https://example.test/manifest",
                    "content": "secret-not-returned",
                },
            ],
        ):
            result = reader.fetch_repo_truth_map_anchors(
                "owner/repo",
                [
                    {
                        "kind": "readme",
                        "path": "README.md",
                        "required": True,
                        "content_mode": "excerpt",
                        "max_chars": 400,
                    },
                    {
                        "kind": "dependency_manifest",
                        "path": "pyproject.toml",
                        "required": False,
                        "content_mode": "metadata_only",
                    },
                ],
            )

        self.assertEqual(len(result["anchors"][0]["excerpt"]), 400)
        self.assertNotIn("excerpt", result["anchors"][1])
        self.assertNotIn("development_sections", result["anchors"][1])
        self.assertEqual(result["errors"], [])

    def test_status_anchor_extracts_bounded_source_reported_development_sections(self):
        content = """# Project status

Last updated: 2026-08-31

## Completed Last 7 Days

- Shipped the repository snapshot.

## In Progress / Partial

### Preview

- Development Reality is under active implementation.

## Blockers & Risks

- Waiting for operator validation.

## Next Up

- Configure the remaining project sources.

## Today Log

- This section is not part of Development Reality.
"""
        with patch.object(
            reader,
            "fetch_repo_content_entry",
            return_value={
                "path": "CURRENT_DEVELOPMENT_STATUS.md",
                "sha": "status-sha",
                "size": len(content.encode("utf-8")),
                "html_url": "https://example.test/status",
                "content": content,
            },
        ):
            result = reader.fetch_repo_truth_map_anchors(
                "owner/repo",
                [
                    {
                        "kind": "current_state",
                        "path": "CURRENT_DEVELOPMENT_STATUS.md",
                        "required": False,
                        "content_mode": "excerpt",
                        "max_chars": 400,
                    }
                ],
            )

        observation = result["anchors"][0]
        sections = observation["development_sections"]
        self.assertEqual(set(sections), {"completed", "in_progress", "blocked", "next_up"})
        self.assertIn("repository snapshot", sections["completed"])
        self.assertIn("### Preview", sections["in_progress"])
        self.assertIn("operator validation", sections["blocked"])
        self.assertIn("remaining project sources", sections["next_up"])
        self.assertLessEqual(sum(len(value) for value in sections.values()), 400)
        self.assertNotIn("Today Log", "\n".join(sections.values()))
        self.assertEqual(observation["source_last_updated"], "2026-08-31")

    def test_development_plan_extracts_active_plan_without_model_inference(self):
        content = """# Development plan

Last updated: 2026-08-30

## Current P0 Track

### Unified reasoning layer

- Complete the bounded verification flow.

### Project review loop

- Validate the operator-facing review surface.

## Supporting Infrastructure

- This is outside the active plan section.
"""
        with patch.object(
            reader,
            "fetch_repo_content_entry",
            return_value={"path": "DEVELOPMENT_PLAN.md", "sha": "plan-sha", "content": content},
        ):
            result = reader.fetch_repo_truth_map_anchors(
                "owner/repo",
                [
                    {
                        "kind": "development_plan",
                        "path": "DEVELOPMENT_PLAN.md",
                        "content_mode": "excerpt",
                        "max_chars": 400,
                    }
                ],
            )

        observation = result["anchors"][0]
        self.assertIn("Unified reasoning layer", observation["development_sections"]["active_plan"])
        self.assertIn("Project review loop", observation["development_sections"]["active_plan"])
        self.assertNotIn("Supporting Infrastructure", observation["development_sections"]["active_plan"])
        self.assertEqual(observation["source_last_updated"], "2026-08-30")

    def test_real_project_status_heading_and_date_variants_are_deterministic(self):
        glap = """# GLAP Current Development Status

**Sydney as-of date:** `2026-08-31`

## Active slice — Learning proposal fix

- Implement the bounded repair.

## Recently completed — Decision review

- Added the review surface.

## Recently completed — Runtime gate

- Added the runtime gate.

## Incomplete or blocked

- Waiting for a real production sample.

## Next Up

- Validate the active slice.
"""
        sections, _ = reader.extract_development_sections(glap, max_chars=1200)

        self.assertEqual(reader.extract_source_last_updated(glap), "2026-08-31")
        self.assertEqual(set(sections), {"completed", "in_progress", "blocked", "next_up"})
        self.assertIn("Decision review", sections["completed"])
        self.assertIn("Runtime gate", sections["completed"])

        agent_status = """# Status

Last verified: 2026-08-28

## Current state

- The release surface is implemented.

## Current milestone

- Validate consumer adoption.

## Remaining TODOs

- Collect a real consumer replay.
"""
        agent_sections, _ = reader.extract_development_sections(agent_status, max_chars=800)

        self.assertEqual(reader.extract_source_last_updated(agent_status), "2026-08-28")
        self.assertIn("in_progress", agent_sections)
        self.assertIn("next_up", agent_sections)

        nyc_status = """# NYC status

Updated 2026-08-24. Canonical current implementation state.

## Product state

- The bounded pilot is implemented and awaiting operational validation.

## Recently completed

- Completed the bounded candidate evaluation.

## Active risks and stop conditions

- Promotion remains human-authorized.

## Next slice

- Validate the operational pilot.
"""
        nyc_sections, _ = reader.extract_development_sections(nyc_status, max_chars=800)

        self.assertEqual(reader.extract_source_last_updated(nyc_status), "2026-08-24")
        self.assertIn("in_progress", nyc_sections)
        self.assertEqual(set(nyc_sections), {"completed", "in_progress", "blocked", "next_up"})

    def test_unstructured_plan_anchor_does_not_invent_development_sections(self):
        with patch.object(
            reader,
            "fetch_repo_content_entry",
            return_value={
                "path": "PLAN.md",
                "sha": "plan-sha",
                "content": "# Plan\n\nA narrative without recognized development-state headings.",
            },
        ):
            result = reader.fetch_repo_truth_map_anchors(
                "owner/repo",
                [
                    {
                        "kind": "development_plan",
                        "path": "PLAN.md",
                        "content_mode": "excerpt",
                        "max_chars": 400,
                    }
                ],
            )

        self.assertNotIn("development_sections", result["anchors"][0])

    def test_development_plan_uses_first_numbered_priority_as_bounded_plan_focus(self):
        content = """# Development plan

## Product direction

Durable product direction.

## P1 — Pilot and adoption

### Cross-domain pilot

- Validate one real consumer.

## P2 — Report evolution

- Deferred until the pilot is useful.
"""
        with patch.object(
            reader,
            "fetch_repo_content_entry",
            return_value={"path": "DEVELOPMENT_PLAN.md", "sha": "plan-sha", "content": content},
        ):
            result = reader.fetch_repo_truth_map_anchors(
                "owner/repo",
                [
                    {
                        "kind": "development_plan",
                        "path": "DEVELOPMENT_PLAN.md",
                        "content_mode": "excerpt",
                        "max_chars": 400,
                    }
                ],
            )

        active_plan = result["anchors"][0]["development_sections"]["active_plan"]
        self.assertIn("P1 — Pilot and adoption", active_plan)
        self.assertIn("Cross-domain pilot", active_plan)
        self.assertNotIn("P2", active_plan)

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
                "scanned_at": service._utc_now_iso(),
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
                "scanned_at": service._utc_now_iso(),
                "summary": "# AI Radar Docs",
                "readme_found": True,
                "top_level_tree": [{"name": "backend", "path": "backend", "type": "dir"}],
                "message": "The repository is saved, but GitHub context could not be loaded right now.",
            },
        )

        snapshot = service.load_project_repo_snapshot("ai_radar")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["status"], "partial")

    def test_unchanged_head_skips_compare_and_advances_from_previous_success(self):
        project = {
            "project_id": "unchanged",
            "name": "Unchanged",
            "repo": "owner/unchanged",
        }
        with patch.object(
            service,
            "fetch_project_github_context",
            return_value={
                "status": "loaded",
                "message": "loaded",
                "repository": {"full_name": "owner/unchanged", "description": "Stable repo"},
                "readme": {"path": "README.md", "content": "Stable repository context."},
                "roadmap": None,
            },
        ), patch.object(service, "fetch_repo_top_level_tree", return_value=[]), patch.object(
            service, "fetch_repo_recent_commits", return_value=[]
        ), patch.object(service, "fetch_repo_manifest_files", return_value=[]), patch.object(
            service, "fetch_repo_compare"
        ) as compare:
            first = service.build_light_project_repo_snapshot(project)
            second = service.build_light_project_repo_snapshot(project)

        self.assertEqual(first["delta"]["status"], "initial")
        self.assertEqual(second["delta"]["status"], "unchanged")
        self.assertEqual(second["delta"]["from_sha"], "a" * 40)
        compare.assert_not_called()

    def test_changed_head_returns_bounded_compare_delta(self):
        project = {
            "project_id": "changed",
            "name": "Changed",
            "repo": "owner/changed",
        }
        heads = [
            {"sha": "1" * 40, "branch": "main", "committed_at": "2026-08-30T09:00:00Z"},
            {"sha": "2" * 40, "branch": "main", "committed_at": "2026-08-30T10:00:00Z"},
        ]
        github_context = {
            "status": "loaded",
            "message": "loaded",
            "repository": {"full_name": "owner/changed", "description": "Changing repo"},
            "readme": {"path": "README.md", "content": "Changing repository context."},
            "roadmap": None,
        }
        comparison = {
            "compare_status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "total_commits": 1,
            "commits": [{"sha": "2" * 40, "message": "update snapshot"}],
            "files": [{"path": "README.md", "status": "modified", "changes": 4}],
            "truncated": False,
            "html_url": "https://example.test/compare",
        }
        self.fetch_head.side_effect = heads
        with patch.object(
            service, "fetch_project_github_context", return_value=github_context
        ), patch.object(service, "fetch_repo_top_level_tree", return_value=[]), patch.object(
            service, "fetch_repo_recent_commits", return_value=[]
        ), patch.object(service, "fetch_repo_manifest_files", return_value=[]), patch.object(
            service, "fetch_repo_compare", return_value=comparison
        ) as compare:
            first = service.build_light_project_repo_snapshot(project)
            second = service.build_light_project_repo_snapshot(project)

        self.assertEqual(first["delta"]["status"], "initial")
        self.assertEqual(second["delta"]["status"], "changed")
        self.assertEqual(second["observation"]["baseline"]["sha"], "1" * 40)
        self.assertEqual(second["observation"]["head"]["sha"], "2" * 40)
        self.assertEqual(second["delta"]["files"][0]["path"], "README.md")
        compare.assert_called_once_with("owner/changed", "1" * 40, "2" * 40)

    def test_compare_unavailable_keeps_prior_baseline_for_next_refresh(self):
        prior = {
            "schema_version": 2,
            "status": "fresh",
            "repo": "owner/repo",
            "scanned_at": "2026-08-30T09:00:00+00:00",
            "observation": {
                "head": {"sha": "1" * 40, "branch": "main"},
                "baseline": {"sha": "1" * 40, "branch": "main"},
            },
            "delta": {"status": "initial"},
        }
        with patch.object(
            service,
            "fetch_repo_compare",
            side_effect=service.GitHubRequestError("unreachable", "offline"),
        ):
            baseline, delta, errors = service._build_snapshot_delta(
                "owner/repo",
                scanned_at="2026-08-30T10:00:00+00:00",
                previous_snapshot=prior,
                head={"sha": "2" * 40, "branch": "main"},
            )

        unavailable_snapshot = {
            **prior,
            "observation": {
                "head": {"sha": "2" * 40, "branch": "main"},
                "baseline": baseline,
            },
            "delta": delta,
        }
        self.assertEqual(delta["status"], "unavailable")
        self.assertEqual(errors, ["delta: unreachable"])
        self.assertEqual(service._previous_successful_head(unavailable_snapshot, "owner/repo")["sha"], "1" * 40)

    def test_failed_refresh_preserves_baseline_and_repo_change_starts_new_baseline(self):
        prior = {
            "schema_version": 2,
            "status": "fresh",
            "repo": "owner/old",
            "scanned_at": "2026-08-30T09:00:00+00:00",
            "observation": {
                "head": {"sha": "1" * 40, "branch": "main"},
                "baseline": {"sha": "1" * 40, "branch": "main"},
            },
            "delta": {"status": "unchanged"},
        }

        baseline, failed_delta, errors = service._build_snapshot_delta(
            "owner/old",
            scanned_at="2026-08-30T10:00:00+00:00",
            previous_snapshot=prior,
            head={},
        )
        self.assertEqual(baseline["sha"], "1" * 40)
        self.assertEqual(failed_delta["status"], "unavailable")
        self.assertEqual(errors, [])

        with patch.object(service, "fetch_repo_compare") as compare:
            new_baseline, new_delta, _ = service._build_snapshot_delta(
                "owner/new",
                scanned_at="2026-08-30T11:00:00+00:00",
                previous_snapshot=prior,
                head={"sha": "9" * 40, "branch": "main"},
            )

        self.assertEqual(new_delta["status"], "initial")
        self.assertEqual(new_baseline["sha"], "9" * 40)
        compare.assert_not_called()

    def test_github_reader_returns_full_head_and_bounded_compare_facts(self):
        commits = [
            {
                "sha": str(index) * 40,
                "commit": {
                    "message": f"commit {index}\nbody",
                    "author": {"date": f"2026-08-{index + 1:02d}T00:00:00Z"},
                },
                "html_url": f"https://example.test/commit/{index}",
            }
            for index in range(3)
        ]
        files = [
            {
                "filename": f"file-{index}.txt",
                "status": "modified",
                "additions": index,
                "deletions": 0,
                "changes": index,
                "blob_url": f"https://example.test/file/{index}",
            }
            for index in range(3)
        ]
        with patch.object(
            reader,
            "_github_request",
            side_effect=[
                {
                    "sha": "f" * 40,
                    "commit": {"author": {"date": "2026-08-30T10:00:00Z"}},
                    "html_url": "https://example.test/head",
                },
                {
                    "status": "ahead",
                    "ahead_by": 3,
                    "behind_by": 0,
                    "total_commits": 3,
                    "commits": commits,
                    "files": files,
                    "html_url": "https://example.test/compare",
                },
            ],
        ) as github_request:
            head = reader.fetch_repo_head("owner/repo", default_branch="main")
            comparison = reader.fetch_repo_compare("owner/repo", "a" * 40, "f" * 40, commit_limit=2, file_limit=2)

        self.assertEqual(head["sha"], "f" * 40)
        self.assertEqual(head["branch"], "main")
        self.assertEqual(len(comparison["commits"]), 2)
        self.assertEqual(len(comparison["files"]), 2)
        self.assertTrue(comparison["truncated"])
        self.assertEqual(github_request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
