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


class AiDiscussionMemoryRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def _authorize(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

    def _payload(self, **overrides):
        payload = {
            "capture": {
                "source": {
                    "source_label": "ADR-0013 session",
                    "source_url": "",
                    "provider": "codex",
                    "captured_from": "",
                },
                "message_refs": [
                    {
                        "message_id": "msg_1",
                        "role": "assistant",
                        "sequence": 1,
                        "content_excerpt": "We judged the route should call the write-entry service.",
                        "content_fingerprint": "fp_msg_1",
                    }
                ],
                "discussion_excerpt": "Selected route-boundary discussion excerpt.",
                "discussion_fingerprint": "fp_route_1",
                "selection_reason": "ADR-0013 route boundary review",
            },
            "governed_claims": [
                {
                    "claim_text": "In this discussion, we judged the route must not call the store directly.",
                    "claim_posture": "discussion_judgment",
                    "asserted_subject": {
                        "subject_type": "ai_radar_design",
                        "label": "ADR-0013 route boundary",
                    },
                    "boundary_review": None,
                    "verification_ref": None,
                    "claim_snapshot": None,
                    "salience": None,
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_route_keeps_admin_guard(self):
        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection"
        ) as mock_create:
            response = TestClient(app).post("/ai-discussion-memory/selections", json=self._payload())

        self.assertEqual(response.status_code, 401)
        mock_create.assert_not_called()

    def test_authenticated_request_builds_caller_and_source_server_side(self):
        self._authorize()
        captured = {}

        def fake_create(request):
            captured["request"] = request
            return {
                "status": "committed",
                "write_batch_id": "aimb_route",
                "capture_id": "aid_route",
                "governed_claim_ids": ["agc_route"],
                "audit_event_ids": ["aida_route", "agca_route"],
                "capture_reused": False,
                "claims_created": True,
            }

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection",
            side_effect=fake_create,
        ):
            response = TestClient(app).post(
                "/ai-discussion-memory/selections",
                json=self._payload(),
                headers={"x-ai-radar-user-id": "andy"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "AI Discussion memory selection recorded successfully")
        self.assertEqual(response.json()["record"]["write_batch_id"], "aimb_route")
        service_request = captured["request"]
        self.assertEqual(service_request["caller"]["caller_type"], "explicit_human_or_agent_selection")
        self.assertEqual(service_request["caller"]["actor"], {"type": "human", "id": "andy"})
        self.assertEqual(service_request["capture"]["source"]["source_type"], "ai_discussion_session")
        self.assertNotIn("discussion_ref", service_request["governed_claims"][0])

    def test_route_rejects_client_supplied_caller(self):
        self._authorize()
        payload = self._payload(caller={"caller_type": "signal_import", "actor": {"type": "system", "id": "x"}})

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection"
        ) as mock_create:
            response = TestClient(app).post("/ai-discussion-memory/selections", json=payload)

        self.assertEqual(response.status_code, 422)
        mock_create.assert_not_called()

    def test_route_rejects_client_supplied_source_type(self):
        self._authorize()
        payload = self._payload()
        payload["capture"]["source"]["source_type"] = "reflection_import"

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection"
        ) as mock_create:
            response = TestClient(app).post("/ai-discussion-memory/selections", json=payload)

        self.assertEqual(response.status_code, 422)
        mock_create.assert_not_called()

    def test_route_never_accepts_client_supplied_discussion_ref(self):
        self._authorize()
        payload = self._payload()
        payload["governed_claims"][0]["discussion_ref"] = {
            "record_family": "ai_discussion_capture",
            "record_id": "aid_other",
        }

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection"
        ) as mock_create:
            response = TestClient(app).post("/ai-discussion-memory/selections", json=payload)

        self.assertEqual(response.status_code, 422)
        mock_create.assert_not_called()

    def test_service_value_error_maps_to_400(self):
        self._authorize()

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection",
            side_effect=ValueError("capture.discussion_fingerprint is required."),
        ):
            response = TestClient(app).post("/ai-discussion-memory/selections", json=self._payload())

        self.assertEqual(response.status_code, 400)
        self.assertIn("discussion_fingerprint", response.json()["detail"])

    def test_service_runtime_error_maps_to_503(self):
        self._authorize()

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection",
            side_effect=RuntimeError("AI Discussion memory store is unavailable."),
        ):
            response = TestClient(app).post("/ai-discussion-memory/selections", json=self._payload())

        self.assertEqual(response.status_code, 503)
        self.assertIn("unavailable", response.json()["detail"])

    def test_response_does_not_include_verification_or_action_eligibility(self):
        self._authorize()

        with patch(
            "app.routes.ai_discussion_memory.write_entry_service.create_ai_discussion_memory_from_selection",
            return_value={
                "status": "committed",
                "write_batch_id": "aimb_route",
                "capture_id": "aid_route",
                "governed_claim_ids": [],
                "audit_event_ids": [],
                "capture_reused": False,
                "claims_created": False,
            },
        ):
            response = TestClient(app).post("/ai-discussion-memory/selections", json=self._payload())

        record = response.json()["record"]
        self.assertNotIn("verification_status", record)
        self.assertNotIn("allowed_downstream_actions", record)
        self.assertNotIn("blocked_downstream_actions", record)
        self.assertNotIn("project_takeaway", record)


if __name__ == "__main__":
    unittest.main()
