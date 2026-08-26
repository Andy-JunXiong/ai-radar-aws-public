import copy
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
TEST_TMP_ROOT = REPO_ROOT / ".tmp-tests"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services import project_intelligence_service  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402
from app.services.project_takeaway_merge_preview_service import (  # noqa: E402
    MergePreviewValidationError,
    build_project_takeaway_merge_preview,
)


def preview_items() -> list[dict]:
    return [
        {
            "project_id": "ai_radar",
            "signal_id": "sig-source",
            "signal_title": "Pending source",
            "signal_summary": "Source summary",
            "takeaway": "Source takeaway",
            "topics": ["agents", "evaluation"],
            "status": "candidate",
            "candidate_source": "signal_completion",
            "verification_metadata": {
                "verification_status": "weakly_supported",
                "claim_support_summary": {"inferred": 1},
                "allowed_downstream_actions": ["watch_only"],
                "blocked_downstream_actions": ["low_risk_action_candidate"],
            },
            "action_eligibility": {
                "low_risk_action_candidate": {"allowed": False, "reason": "Weak evidence."}
            },
        },
        {
            "project_id": "ai_radar",
            "signal_id": "sig-target",
            "signal_title": "Confirmed target",
            "signal_summary": "Target summary",
            "takeaway": "Target takeaway",
            "topics": ["agents"],
            "status": "confirmed",
            "candidate_source": "confirmed_final_takeaway",
            "confirmed_at": "2026-08-20T00:00:00+00:00",
            "verification_metadata": {
                "verification_status": "verified",
                "claim_support_summary": {"directly_supported": 2},
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            },
            "action_eligibility": {
                "project_takeaway_candidate": {"allowed": True, "reason": "Verified."}
            },
        },
    ]


class ProjectTakeawayMergePreviewServiceTests(unittest.TestCase):
    def test_preview_keeps_identity_and_verification_separate_and_defaults_to_target(self):
        items = preview_items()
        original = copy.deepcopy(items)

        result = build_project_takeaway_merge_preview(
            project_id="ai_radar",
            items=items,
            source_signal_id="sig-source",
            target_signal_id="sig-target",
            field_resolutions={"signal_summary": "source"},
        )

        self.assertEqual(result["preview_version"], "review_inbox_merge_preview_v1")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(result["source"]["identity"]["status"], "candidate")
        self.assertEqual(result["target"]["identity"]["status"], "confirmed")
        self.assertEqual(
            result["source"]["verification"]["verification_status"],
            "weakly_supported",
        )
        self.assertEqual(result["target"]["verification"]["verification_status"], "verified")
        self.assertEqual(result["result_preview"]["signal_summary"], "Source summary")
        self.assertEqual(result["result_preview"]["takeaway"], "Target takeaway")
        self.assertEqual(
            next(row for row in result["field_comparisons"] if row["field"] == "takeaway")[
                "selected_from"
            ],
            "target",
        )
        self.assertEqual(items, original)

        result["source"]["verification"]["verification_metadata"]["verification_status"] = "changed"
        self.assertEqual(
            items[0]["verification_metadata"]["verification_status"],
            "weakly_supported",
        )

    def test_preview_fails_closed_for_invalid_selections(self):
        cases = [
            (
                "same item",
                preview_items(),
                "sig-source",
                "sig-source",
                {},
                "same_item_selected",
            ),
            (
                "source status",
                [{**preview_items()[0], "status": "reopened"}, preview_items()[1]],
                "sig-source",
                "sig-target",
                {},
                "source_status_not_candidate",
            ),
            (
                "target status",
                [preview_items()[0], {**preview_items()[1], "status": "watch"}],
                "sig-source",
                "sig-target",
                {},
                "target_status_not_confirmed",
            ),
            (
                "cross project",
                [preview_items()[0], {**preview_items()[1], "project_id": "other"}],
                "sig-source",
                "sig-target",
                {},
                "cross_project_selection",
            ),
            (
                "ambiguous source",
                [preview_items()[0], copy.deepcopy(preview_items()[0]), preview_items()[1]],
                "sig-source",
                "sig-target",
                {},
                "source_ambiguous",
            ),
            (
                "unsupported field",
                preview_items(),
                "sig-source",
                "sig-target",
                {"verification_metadata": "source"},
                "invalid_field_resolution",
            ),
            (
                "invalid field choice",
                preview_items(),
                "sig-source",
                "sig-target",
                {"takeaway": "combine"},
                "invalid_field_selection",
            ),
        ]

        for name, items, source_id, target_id, resolutions, reason_code in cases:
            with self.subTest(name=name):
                with self.assertRaises(MergePreviewValidationError) as raised:
                    build_project_takeaway_merge_preview(
                        project_id="ai_radar",
                        items=items,
                        source_signal_id=source_id,
                        target_signal_id=target_id,
                        field_resolutions=resolutions,
                    )
                self.assertEqual(raised.exception.reason_code, reason_code)

    def test_preview_preserves_explicit_empty_gate_lists_without_nested_union(self):
        items = preview_items()
        items[1]["verification_metadata"] = {
            "allowed_downstream_actions": [],
            "blocked_downstream_actions": [],
            "verified_insight": {
                "action_policy": {
                    "allowed": ["project_takeaway_candidate"],
                    "blocked": ["low_risk_action_candidate"],
                }
            },
        }

        result = build_project_takeaway_merge_preview(
            project_id="ai_radar",
            items=items,
            source_signal_id="sig-source",
            target_signal_id="sig-target",
        )

        self.assertEqual(result["target"]["verification"]["allowed_downstream_actions"], [])
        self.assertEqual(result["target"]["verification"]["blocked_downstream_actions"], [])

    def test_readonly_loader_does_not_materialize_remote_payload(self):
        temp_path = TEST_TMP_ROOT / f"merge_preview_{uuid.uuid4().hex}"
        temp_path.mkdir(parents=True, exist_ok=False)
        try:
            remote_payload = {"project_id": "ai_radar", "items": preview_items()}
            with patch.object(
                project_intelligence_service,
                "PROJECT_IMPROVEMENTS_DIR",
                temp_path,
            ), patch.object(
                project_intelligence_service,
                "_local_output_enabled",
                return_value=False,
            ), patch.object(
                project_intelligence_service,
                "_read_s3_improvements",
                return_value=remote_payload,
            ):
                result = project_intelligence_service.load_project_improvements_readonly("ai_radar")

            self.assertEqual(len(result["items"]), 2)
            self.assertEqual(list(temp_path.iterdir()), [])
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)


class ProjectTakeawayMergePreviewRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_merge_preview_route_keeps_admin_guard(self):
        with patch("app.routes.projects.get_project") as get_project, patch(
            "app.routes.projects.load_project_improvements_readonly"
        ) as load_improvements:
            response = TestClient(app).post(
                "/projects/ai_radar/takeaway-candidates/merge-preview",
                json={
                    "source_signal_id": "sig-source",
                    "target_signal_id": "sig-target",
                },
            )

        self.assertEqual(response.status_code, 401)
        get_project.assert_not_called()
        load_improvements.assert_not_called()

    def test_merge_preview_route_returns_zero_write_preview_when_authorized(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

        with patch(
            "app.routes.projects.get_project",
            return_value={"project_id": "ai_radar", "name": "AI Radar"},
        ), patch(
            "app.routes.projects.load_project_improvements_readonly",
            return_value={"project_id": "ai_radar", "items": preview_items()},
        ), patch(
            "app.services.project_intelligence_service.save_project_improvements"
        ) as save_improvements, patch(
            "app.services.project_intelligence_service.append_project_review_record"
        ) as append_review_record, patch(
            "app.services.project_intelligence_service.append_project_calibration_event"
        ) as append_calibration_event:
            response = TestClient(app).post(
                "/projects/ai_radar/takeaway-candidates/merge-preview",
                json={
                    "source_signal_id": "sig-source",
                    "target_signal_id": "sig-target",
                    "field_resolutions": {"takeaway": "source"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["persisted"])
        self.assertFalse(body["mutation_performed"])
        self.assertEqual(body["result_preview"]["takeaway"], "Source takeaway")
        save_improvements.assert_not_called()
        append_review_record.assert_not_called()
        append_calibration_event.assert_not_called()

    def test_merge_preview_route_returns_stable_fail_closed_reason(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

        with patch(
            "app.routes.projects.get_project",
            return_value={"project_id": "ai_radar", "name": "AI Radar"},
        ), patch(
            "app.routes.projects.load_project_improvements_readonly",
            return_value={"project_id": "ai_radar", "items": preview_items()},
        ):
            response = TestClient(app).post(
                "/projects/ai_radar/takeaway-candidates/merge-preview",
                json={
                    "source_signal_id": "sig-source",
                    "target_signal_id": "sig-source",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["reason_code"], "same_item_selected")


if __name__ == "__main__":
    unittest.main()
