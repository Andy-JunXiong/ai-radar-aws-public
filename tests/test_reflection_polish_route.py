import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.routes import workspace as workspace_route  # noqa: E402
from app.services import reflection_polish_store_service as store_service  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402
from app.services.reflection_polish_pair_service import (  # noqa: E402
    DIMENSION_RESULT_FAIL,
    DIMENSION_RESULT_PASS,
    REVIEW_DIMENSIONS,
    REVIEW_OUTCOME_APPROVED,
    REVIEW_OUTCOME_NEEDS_REVISION,
)


class ReflectionPolishRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="reflection_polish_route_"))
        self.original_paths = (
            store_service.DATA_DIR,
            store_service.PAIRS_DIR,
            store_service.REVIEWS_DIR,
            store_service.INDEX_FILE,
        )
        store_service.DATA_DIR = self.temp_dir
        store_service.PAIRS_DIR = self.temp_dir / "pairs"
        store_service.REVIEWS_DIR = self.temp_dir / "reviews"
        store_service.INDEX_FILE = self.temp_dir / "index.json"
        app.dependency_overrides[require_admin_auth] = lambda: None

    def tearDown(self):
        (
            store_service.DATA_DIR,
            store_service.PAIRS_DIR,
            store_service.REVIEWS_DIR,
            store_service.INDEX_FILE,
        ) = self.original_paths
        app.dependency_overrides.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _policy_decision(self):
        selected_policy = SimpleNamespace(to_dict=lambda: {"task_type": "reflection_polish"})
        return SimpleNamespace(selected_policy=selected_policy)

    def _polish_payload(self, **overrides):
        payload = {
            "text": "This signal made me rethink how memory should preserve judgment.",
            "signal_id": "sig_reflect_1",
            "signal_title": "Reflection memory signal",
            "signal_summary": "A signal about preserving judgment.",
        }
        payload.update(overrides)
        return payload

    def _passing_dimensions(self):
        return {dimension: DIMENSION_RESULT_PASS for dimension in REVIEW_DIMENSIONS}

    def _post_polish_with_mocks(self, payload):
        with patch.object(workspace_route, "decide_execution_policy", return_value=self._policy_decision()), patch.object(
            workspace_route,
            "workspace_reflection_polish_prompts",
            return_value=("system", "user"),
        ), patch.object(
            workspace_route,
            "execute_workspace_text_with_policy",
            return_value=(
                "This signal made me rethink how memory should preserve judgment, and that shift is worth keeping.",
                "anthropic",
                False,
                {"execution": {"provider": "anthropic"}, "task_type": "reflection_polish"},
            ),
        ):
            return TestClient(app).post("/polish_reflection", json=payload)

    def test_polish_reflection_default_does_not_persist_pair(self):
        response = self._post_polish_with_mocks(self._polish_payload())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("polished_text", data)
        self.assertNotIn("reflection_polish_pair_id", data)
        self.assertFalse((self.temp_dir / "pairs").exists())

    def test_polish_reflection_uses_context_as_reference_not_evidence_source(self):
        selected_policy = SimpleNamespace(to_dict=lambda: {"task_type": "reflection_polish"})
        policy_decision = SimpleNamespace(selected_policy=selected_policy)
        with patch.object(workspace_route, "decide_execution_policy", return_value=policy_decision) as decide_mock, patch.object(
            workspace_route,
            "workspace_reflection_polish_prompts",
            return_value=("system", "user"),
        ), patch.object(
            workspace_route,
            "execute_workspace_text_with_policy",
            return_value=(
                "This signal makes me more careful about preserving judgment.",
                "anthropic",
                False,
                {"execution": {"provider": "anthropic"}, "task_type": "reflection_polish"},
            ),
        ) as execute_mock:
            response = TestClient(app).post("/polish_reflection", json=self._polish_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(decide_mock.call_args.args[0].source_count, 0)
        self.assertEqual(execute_mock.call_args.kwargs["source_count"], 0)

    def test_polish_reflection_persist_pair_writes_before_after_record(self):
        response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        pair_id = data["reflection_polish_pair_id"]
        self.assertTrue(pair_id.startswith("rpp_"))
        self.assertEqual(data["baseline_eligibility"], {"eligible": False, "reason": "human_review_required"})

        pair = store_service.load_reflection_polish_pair(pair_id)
        self.assertEqual(pair["draft"]["original_text"], self._polish_payload()["text"])
        self.assertEqual(pair["polish"]["provider_used"], "anthropic")
        self.assertEqual(pair["context"]["signal_id"], "sig_reflect_1")
        for forbidden in (
            "blocked_downstream_actions",
            "project_takeaway",
            "verification_ref",
            "verified_insight_id",
        ):
            self.assertNotIn(forbidden, pair)

    def test_empty_polish_request_does_not_create_pair_even_when_requested(self):
        response = self._post_polish_with_mocks(self._polish_payload(text=" ", persist_pair=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"polished_text": ""})
        self.assertFalse((self.temp_dir / "pairs").exists())

    def test_review_route_records_approved_human_review(self):
        polish_response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        pair_id = polish_response.json()["reflection_polish_pair_id"]

        response = TestClient(app).post(
            f"/reflection-polish/pairs/{pair_id}/review",
            json={
                "outcome": REVIEW_OUTCOME_APPROVED,
                "dimension_results": self._passing_dimensions(),
                "reviewer_id": "andy",
                "reviewer_note": "Preserves the user's voice and clarifies the point.",
                "final_reflection_text": "Final approved reflection.",
            },
        )

        self.assertEqual(response.status_code, 200)
        record = response.json()["record"]
        self.assertEqual(record["pair_id"], pair_id)
        self.assertEqual(record["outcome"], REVIEW_OUTCOME_APPROVED)
        self.assertTrue(record["review_id"].startswith("rpr_"))
        self.assertNotIn("project_takeaway", record)
        self.assertNotIn("blocked_downstream_actions", record)

        index = store_service.load_reflection_polish_index()
        self.assertEqual(index["pairs"][0]["review_outcome"], REVIEW_OUTCOME_APPROVED)
        self.assertEqual(index["pairs"][0]["review_id"], record["review_id"])

    def test_list_route_returns_pair_summaries_only(self):
        first = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        second = self._post_polish_with_mocks(
            self._polish_payload(
                text="A second reflection draft.",
                signal_id="sig_reflect_2",
                persist_pair=True,
            )
        )

        response = TestClient(app).get("/reflection-polish/pairs")

        self.assertEqual(response.status_code, 200)
        record = response.json()["record"]
        self.assertEqual(record["record_type"], "reflection_polish_pair_list")
        self.assertEqual(record["count"], 2)
        self.assertEqual(record["pairs"][0]["id"], second.json()["reflection_polish_pair_id"])
        self.assertEqual(record["pairs"][1]["id"], first.json()["reflection_polish_pair_id"])
        self.assertNotIn("draft", record["pairs"][0])
        self.assertNotIn("polish", record["pairs"][0])
        self.assertNotIn("project_takeaway", record["pairs"][0])

    def test_list_route_clamps_limit(self):
        self._post_polish_with_mocks(self._polish_payload(persist_pair=True))

        response = TestClient(app).get("/reflection-polish/pairs?limit=0")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["record"]["count"], 1)

    def test_detail_route_returns_pair_without_review_before_human_review(self):
        polish_response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        pair_id = polish_response.json()["reflection_polish_pair_id"]

        response = TestClient(app).get(f"/reflection-polish/pairs/{pair_id}")

        self.assertEqual(response.status_code, 200)
        detail = response.json()["record"]
        self.assertEqual(detail["record_type"], "reflection_polish_pair_detail")
        self.assertEqual(detail["pair"]["id"], pair_id)
        self.assertIsNone(detail["review"])
        self.assertEqual(detail["pair"]["baseline_eligibility"], {"eligible": False, "reason": "human_review_required"})
        for forbidden in (
            "blocked_downstream_actions",
            "project_takeaway",
            "verification_ref",
            "verified_insight_id",
        ):
            self.assertNotIn(forbidden, detail["pair"])

    def test_detail_route_returns_review_after_human_review(self):
        polish_response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        pair_id = polish_response.json()["reflection_polish_pair_id"]
        review_response = TestClient(app).post(
            f"/reflection-polish/pairs/{pair_id}/review",
            json={
                "outcome": REVIEW_OUTCOME_APPROVED,
                "dimension_results": self._passing_dimensions(),
                "reviewer_id": "andy",
                "reviewer_note": "Preserves the user's voice and clarifies the point.",
                "final_reflection_text": "Final approved reflection.",
            },
        )

        response = TestClient(app).get(f"/reflection-polish/pairs/{pair_id}")

        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        detail = response.json()["record"]
        self.assertEqual(detail["review"]["id"], review_response.json()["record"]["review_id"])
        self.assertEqual(detail["review"]["outcome"], REVIEW_OUTCOME_APPROVED)
        self.assertEqual(detail["index_entry"]["review_outcome"], REVIEW_OUTCOME_APPROVED)
        self.assertNotIn("project_takeaway", detail["review"])
        self.assertNotIn("blocked_downstream_actions", detail["review"])

    def test_detail_route_returns_404_for_unknown_pair(self):
        response = TestClient(app).get("/reflection-polish/pairs/rpp_missing")

        self.assertEqual(response.status_code, 404)

    def test_review_route_rejects_failed_dimension_for_approved_outcome(self):
        polish_response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        pair_id = polish_response.json()["reflection_polish_pair_id"]
        dimensions = self._passing_dimensions()
        dimensions["no_new_claims"] = DIMENSION_RESULT_FAIL

        response = TestClient(app).post(
            f"/reflection-polish/pairs/{pair_id}/review",
            json={
                "outcome": REVIEW_OUTCOME_APPROVED,
                "dimension_results": dimensions,
                "reviewer_id": "andy",
                "reviewer_note": "One dimension failed.",
                "final_reflection_text": "Final approved reflection.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be approved", response.json()["detail"])

    def test_review_route_requires_note_for_needs_revision(self):
        polish_response = self._post_polish_with_mocks(self._polish_payload(persist_pair=True))
        pair_id = polish_response.json()["reflection_polish_pair_id"]

        response = TestClient(app).post(
            f"/reflection-polish/pairs/{pair_id}/review",
            json={
                "outcome": REVIEW_OUTCOME_NEEDS_REVISION,
                "dimension_results": self._passing_dimensions(),
                "reviewer_id": "andy",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reviewer_note is required", response.json()["detail"])

    def test_review_route_returns_404_for_unknown_pair(self):
        response = TestClient(app).post(
            "/reflection-polish/pairs/rpp_missing/review",
            json={
                "outcome": REVIEW_OUTCOME_APPROVED,
                "dimension_results": self._passing_dimensions(),
                "reviewer_id": "andy",
                "reviewer_note": "Looks good.",
                "final_reflection_text": "Final approved reflection.",
            },
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
