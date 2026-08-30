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
from app.services.project_truth_map_service import (  # noqa: E402
    TruthMapValidationError,
    merge_project_metadata,
    resolve_project_truth_map,
    validate_and_normalize_truth_map,
)


def truth_map(anchor_overrides=None):
    anchor = {
        "kind": "product_spec",
        "path": "docs/product.md",
        "required": True,
        "content_mode": "excerpt",
        "max_chars": 2400,
    }
    anchor.update(anchor_overrides or {})
    return {"schema_version": 1, "anchors": [anchor]}


class ProjectTruthMapServiceTests(unittest.TestCase):
    def test_valid_truth_map_is_normalized_with_explicit_defaults(self):
        normalized = validate_and_normalize_truth_map(
            {
                "schema_version": 1,
                "anchors": [
                    {"kind": "roadmap", "path": " docs\\ROADMAP.md "},
                    {
                        "kind": "dependency_manifest",
                        "path": "backend/requirements.txt",
                        "content_mode": "metadata_only",
                    },
                ],
            }
        )

        self.assertEqual(normalized["schema_version"], 1)
        self.assertEqual(normalized["anchors"][0]["path"], "docs/ROADMAP.md")
        self.assertFalse(normalized["anchors"][0]["required"])
        self.assertEqual(normalized["anchors"][0]["max_chars"], 1600)
        self.assertNotIn("max_chars", normalized["anchors"][1])

    def test_invalid_truth_map_cases_return_specific_paths_and_codes(self):
        cases = [
            ({"schema_version": True, "anchors": [truth_map()["anchors"][0]]}, "unsupported_schema_version"),
            ({"schema_version": 1, "anchors": []}, "anchor_count"),
            (
                {
                    "schema_version": 1,
                    "anchors": [{"kind": "doc", "path": f"docs/{index}.md"} for index in range(21)],
                },
                "anchor_count",
            ),
            (truth_map({"kind": "Product Spec"}), "invalid_kind"),
            (truth_map({"path": "/etc/passwd"}), "absolute_path"),
            (truth_map({"path": "docs/../README.md"}), "unsafe_segment"),
            (truth_map({"path": "docs/*.md"}), "wildcard_path"),
            (truth_map({"path": ".env.production"}), "secret_like_path"),
            (truth_map({"content_mode": []}), "invalid_content_mode"),
            (truth_map({"content_mode": "excerpt", "max_chars": 399}), "invalid_excerpt_limit"),
            (truth_map({"content_mode": "metadata_only", "max_chars": 1600}), "field_not_allowed"),
        ]

        for payload, expected_code in cases:
            with self.subTest(expected_code=expected_code), self.assertRaises(TruthMapValidationError) as raised:
                validate_and_normalize_truth_map(payload)
            self.assertIn(expected_code, {item["code"] for item in raised.exception.errors})
            self.assertTrue(all(item["path"].startswith("metadata.repo_context.truth_map") for item in raised.exception.errors))

    def test_duplicate_paths_are_case_insensitive_after_normalization(self):
        payload = {
            "schema_version": 1,
            "anchors": [
                {"kind": "readme", "path": "README.md"},
                {"kind": "overview", "path": "readme.md"},
            ],
        }

        with self.assertRaises(TruthMapValidationError) as raised:
            validate_and_normalize_truth_map(payload)

        self.assertEqual(raised.exception.errors[-1]["code"], "duplicate_path")
        self.assertEqual(raised.exception.errors[-1]["path"], "metadata.repo_context.truth_map.anchors[1].path")

    def test_merge_preserves_unrelated_metadata_and_repo_context(self):
        existing = {
            "owner": "operator",
            "repo_context": {"visibility": "private", "legacy_hint": "keep"},
        }

        merged = merge_project_metadata(
            existing,
            {"repo_context": {"truth_map": truth_map({"path": " README.md "})}},
        )

        self.assertEqual(merged["owner"], "operator")
        self.assertEqual(merged["repo_context"]["visibility"], "private")
        self.assertEqual(merged["repo_context"]["legacy_hint"], "keep")
        self.assertEqual(merged["repo_context"]["truth_map"]["anchors"][0]["path"], "README.md")
        self.assertNotIn("truth_map", existing["repo_context"])

    def test_null_truth_map_clears_only_truth_map(self):
        existing = {
            "owner": "operator",
            "repo_context": {"visibility": "private", "truth_map": truth_map()},
        }

        merged = merge_project_metadata(existing, {"repo_context": {"truth_map": None}})

        self.assertEqual(merged["owner"], "operator")
        self.assertEqual(merged["repo_context"], {"visibility": "private"})

    def test_resolve_truth_map_distinguishes_absent_valid_and_invalid(self):
        absent = resolve_project_truth_map({"metadata": {"repo_context": {}}})
        valid = resolve_project_truth_map(
            {"metadata": {"repo_context": {"truth_map": truth_map({"path": " README.md "})}}}
        )
        invalid = resolve_project_truth_map(
            {"metadata": {"repo_context": {"truth_map": truth_map({"path": "../README.md"})}}}
        )

        self.assertEqual(absent["config_status"], "absent")
        self.assertEqual(absent["mode"], "heuristic")
        self.assertEqual(valid["config_status"], "valid")
        self.assertEqual(valid["truth_map"]["anchors"][0]["path"], "README.md")
        self.assertEqual(invalid["config_status"], "invalid")
        self.assertEqual(invalid["config_errors"][0]["code"], "unsafe_segment")


class ProjectTruthMapAppRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

    def tearDown(self):
        app.dependency_overrides.clear()

    @staticmethod
    def _project_payload(metadata_marker=True):
        payload = {
            "project_id": "ai_radar",
            "name": "AI Radar",
            "enabled": True,
            "status": "active",
            "description": "Project intelligence",
            "repo": "https://github.com/Andy-JunXiong/ai-radar-aws",
            "current_state": "Active",
            "roadmap": "Phase 7",
            "topics": ["AI intelligence"],
        }
        if metadata_marker is not True:
            payload["metadata"] = metadata_marker
        return payload

    def test_project_save_merges_and_persists_normalized_truth_map(self):
        previous = {
            "project_id": "ai_radar",
            "repo": "https://github.com/Andy-JunXiong/ai-radar-aws",
            "metadata": {"owner": "operator", "repo_context": {"visibility": "private"}},
        }

        def save_item(project_id, updates):
            return {"project_id": project_id, **updates}

        with patch("app.routes.projects.get_project", return_value=previous), patch(
            "app.routes.projects.upsert_project", side_effect=save_item
        ) as upsert, patch(
            "app.routes.projects.maybe_refresh_project_repo_snapshot_after_save",
            return_value={"status": "fresh"},
        ):
            response = TestClient(app).post(
                "/projects",
                json=self._project_payload({"repo_context": {"truth_map": truth_map({"path": " README.md "})}}),
            )

        self.assertEqual(response.status_code, 200)
        updates = upsert.call_args.args[1]
        self.assertEqual(updates["metadata"]["owner"], "operator")
        self.assertEqual(updates["metadata"]["repo_context"]["visibility"], "private")
        self.assertEqual(
            updates["metadata"]["repo_context"]["truth_map"]["anchors"][0]["path"],
            "README.md",
        )
        self.assertEqual(response.json()["item"]["metadata"], updates["metadata"])

    def test_project_save_returns_structured_422_for_invalid_truth_map(self):
        previous = {"project_id": "ai_radar", "repo": "", "metadata": {}}
        with patch("app.routes.projects.get_project", return_value=previous), patch(
            "app.routes.projects.upsert_project"
        ) as upsert:
            response = TestClient(app).post(
                "/projects",
                json=self._project_payload({"repo_context": {"truth_map": truth_map({"path": ".env"})}}),
            )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "invalid_project_truth_map")
        self.assertEqual(detail["errors"][0]["code"], "secret_like_path")
        upsert.assert_not_called()

    def test_project_save_without_metadata_keeps_legacy_route_behavior(self):
        previous = {
            "project_id": "ai_radar",
            "repo": "https://github.com/Andy-JunXiong/ai-radar-aws",
            "metadata": {"owner": "operator"},
        }

        def save_item(project_id, updates):
            return {"project_id": project_id, **updates, "metadata": previous["metadata"]}

        with patch("app.routes.projects.get_project", return_value=previous), patch(
            "app.routes.projects.upsert_project", side_effect=save_item
        ) as upsert, patch(
            "app.routes.projects.maybe_refresh_project_repo_snapshot_after_save",
            return_value={"status": "fresh"},
        ):
            response = TestClient(app).post("/projects", json=self._project_payload())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("metadata", upsert.call_args.args[1])
        self.assertEqual(response.json()["item"]["metadata"], {"owner": "operator"})


if __name__ == "__main__":
    unittest.main()
