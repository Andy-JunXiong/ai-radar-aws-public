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
from app.services import signal_review_feedback_service as feedback_service  # noqa: E402


class SignalReviewFeedbackAppRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = REPO_ROOT / ".tmp-tests" / "signal_review_feedback_app_route"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.previous_data_dir = feedback_service.DATA_DIR
        self.previous_index_path = feedback_service.INDEX_PATH
        feedback_service.DATA_DIR = self.temp_dir
        feedback_service.INDEX_PATH = self.temp_dir / "index.json"

    def tearDown(self):
        app.dependency_overrides.clear()
        feedback_service.DATA_DIR = self.previous_data_dir
        feedback_service.INDEX_PATH = self.previous_index_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _authorize(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

    def _payload(self, **overrides):
        payload = {
            "signal_id": "signal-123",
            "insight_id": "insight-456",
            "content_fingerprint": "fp-789",
            "claim_id": "claim-1",
            "claim_text_snapshot": "The source says adoption doubled.",
            "claim_source_field": "source_excerpt",
            "reason_slot": "reasoning_gap",
            "distortion_tags": ["pseudo_precision"],
            "note": "The number is too exact for the cited excerpt.",
            "verification_snapshot": {
                "verification_status": "partial",
                "unsupported_claim_count": 1,
                "blocked_downstream_actions": ["project_takeaway"],
            },
            "input_provenance_snapshot": {
                "schema_version": 1,
                "freshness": {"stale_flags": ["signal_timestamp_stale"], "freshness_penalty": 0.1},
            },
            "relationship_annotation": {
                "relation_type": "logical_inference",
                "grounding_source": "structured_metadata",
                "derivation_mechanism": "model_inferred",
                "support_posture": "needs_review",
                "classified_by": "model",
                "source_refs": ["signal:signal-123"],
                "rationale": "Metadata suggests a relationship, but does not prove the claim.",
            },
        }
        payload.update(overrides)
        return payload

    def test_create_route_keeps_admin_guard(self):
        with patch("app.routes.signal_review_feedback.feedback_service.append_signal_review_feedback_record") as mock_append:
            response = TestClient(app).post("/signal-review-feedback", json=self._payload())

        self.assertEqual(response.status_code, 401)
        mock_append.assert_not_called()

    def test_create_route_records_feedback_without_changing_gate_semantics(self):
        self._authorize()
        payload = self._payload()

        response = TestClient(app).post("/signal-review-feedback", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        record = body["record"]
        self.assertEqual(body["message"], "signal review feedback recorded successfully")
        self.assertEqual(record["record_type"], feedback_service.RECORD_TYPE)
        self.assertEqual(record["signal_id"], "signal-123")
        self.assertEqual(record["claim_id"], "claim-1")
        self.assertEqual(record["reason_slot"], "reasoning_gap")
        self.assertEqual(record["distortion_tags"], ["pseudo_precision"])
        self.assertEqual(record["created_by"], "human")
        self.assertEqual(record["downstream_effect"], "none")
        self.assertEqual(record["evidence_boundary"], "not_external_claim_evidence")
        self.assertEqual(record["background_update_candidate_id"], "")
        self.assertEqual(
            record["verification_snapshot"]["blocked_downstream_actions"],
            ["project_takeaway"],
        )
        self.assertEqual(
            record["input_provenance_snapshot"]["freshness"]["stale_flags"],
            ["signal_timestamp_stale"],
        )
        self.assertEqual(record["relationship_annotation"]["grounding_source"], "structured_metadata")
        self.assertEqual(record["relationship_annotation"]["derivation_mechanism"], "model_inferred")
        self.assertEqual(record["relationship_annotation"]["support_posture"], "needs_review")
        self.assertIn("metadata_only_support", record["relationship_annotation"]["review_reason_codes"])
        self.assertIn("model_inferred_logical", record["relationship_annotation"]["review_reason_codes"])

    def test_create_route_rejects_invalid_reason_slot_and_distortion_tag(self):
        self._authorize()
        client = TestClient(app)

        invalid_reason = client.post(
            "/signal-review-feedback",
            json=self._payload(reason_slot="score_instead"),
        )
        invalid_tag = client.post(
            "/signal-review-feedback",
            json=self._payload(distortion_tags=["made_up_tag"]),
        )

        self.assertEqual(invalid_reason.status_code, 400)
        self.assertIn("reason_slot must be one of", invalid_reason.json()["detail"])
        self.assertEqual(invalid_tag.status_code, 400)
        self.assertIn("Unknown distortion_tags", invalid_tag.json()["detail"])
        self.assertEqual(feedback_service.list_signal_review_feedback_records(), [])

    def test_create_route_rejects_confirmed_metadata_only_support_annotation(self):
        self._authorize()

        response = TestClient(app).post(
            "/signal-review-feedback",
            json=self._payload(
                relationship_annotation={
                    "relation_type": "evidential_support",
                    "grounding_source": "structured_metadata",
                    "derivation_mechanism": "deterministic_rule",
                    "support_posture": "confirmed",
                    "classified_by": "system_rule",
                },
            ),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be confirmed", response.json()["detail"])

    def test_list_route_filters_records_and_validates_reason_slot(self):
        self._authorize()
        client = TestClient(app)
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-1", reason_slot="reasoning_gap"))
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-2", reason_slot="stale_input"))
        client.post("/signal-review-feedback", json=self._payload(signal_id="signal-999", claim_id="claim-3", reason_slot="blind_spot"))

        by_signal = client.get("/signal-review-feedback?signal_id=signal-123")
        by_claim = client.get("/signal-review-feedback?claim_id=claim-2")
        by_reason = client.get("/signal-review-feedback?reason_slot=blind_spot")
        invalid_reason = client.get("/signal-review-feedback?reason_slot=score_instead")

        self.assertEqual(by_signal.status_code, 200)
        self.assertEqual(by_signal.json()["count"], 2)
        self.assertEqual(by_claim.status_code, 200)
        self.assertEqual(by_claim.json()["records"][0]["claim_id"], "claim-2")
        self.assertEqual(by_reason.status_code, 200)
        self.assertEqual(by_reason.json()["records"][0]["signal_id"], "signal-999")
        self.assertEqual(invalid_reason.status_code, 400)

    def test_background_update_candidate_route_keeps_admin_guard(self):
        with patch("app.routes.signal_review_feedback.feedback_service.list_background_update_candidates") as mock_list:
            response = TestClient(app).get("/signal-review-feedback/background-update-candidates")

        self.assertEqual(response.status_code, 401)
        mock_list.assert_not_called()

    def test_background_update_candidate_route_returns_inactive_candidates_only(self):
        self._authorize()
        client = TestClient(app)
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-1", reason_slot="not_me"))
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-2", reason_slot="blind_spot"))
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-3", reason_slot="reasoning_gap"))

        response = client.get("/signal-review-feedback/background-update-candidates?signal_id=signal-123")
        filtered = client.get("/signal-review-feedback/background-update-candidates?reason_slot=not_me")
        invalid = client.get("/signal-review-feedback/background-update-candidates?reason_slot=stale_input")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["queue_type"], "background_update_candidate_queue")
        self.assertEqual(body["candidate_status"], "inactive_review_only")
        self.assertEqual(body["evidence_boundary"], "not_external_claim_evidence")
        self.assertEqual(body["count"], 2)
        self.assertEqual({record["reason_slot"] for record in body["records"]}, {"not_me", "blind_spot"})
        self.assertTrue(all(record["review_boundary"]["requires_explicit_confirmation"] for record in body["records"]))
        self.assertTrue(all(not record["review_boundary"]["mutates_context"] for record in body["records"]))
        self.assertTrue(all(not record["review_boundary"]["mutates_action_gate"] for record in body["records"]))
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["count"], 1)
        self.assertEqual(filtered.json()["records"][0]["reason_slot"], "not_me")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("background update candidates can only be filtered", invalid.json()["detail"])

    def test_background_update_candidate_decision_route_keeps_admin_guard(self):
        with patch("app.routes.signal_review_feedback.feedback_service.append_background_update_candidate_decision") as mock_append:
            response = TestClient(app).post(
                "/signal-review-feedback/background-update-candidates/buc_123/decision",
                json={"decision": "confirmed"},
            )

        self.assertEqual(response.status_code, 401)
        mock_append.assert_not_called()

    def test_background_update_candidate_decision_route_records_ledger_only_decision(self):
        self._authorize()
        client = TestClient(app)
        client.post("/signal-review-feedback", json=self._payload(claim_id="claim-1", reason_slot="not_me"))
        candidate = client.get("/signal-review-feedback/background-update-candidates").json()["records"][0]

        response = client.post(
            f"/signal-review-feedback/background-update-candidates/{candidate['id']}/decision",
            json={"decision": "confirmed", "note": "Useful context, but do not apply automatically."},
        )
        refreshed = client.get("/signal-review-feedback/background-update-candidates")
        invalid = client.post(
            f"/signal-review-feedback/background-update-candidates/{candidate['id']}/decision",
            json={"decision": "apply_now"},
        )
        missing = client.post(
            "/signal-review-feedback/background-update-candidates/buc_missing/decision",
            json={"decision": "dismissed"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        record = body["record"]
        self.assertEqual(body["message"], "background update candidate decision recorded successfully")
        self.assertEqual(record["record_type"], "background_update_candidate_decision")
        self.assertEqual(record["candidate_id"], candidate["id"])
        self.assertEqual(record["decision"], "confirmed")
        self.assertEqual(record["downstream_effect"], "decision_record_only")
        self.assertEqual(record["evidence_boundary"], "not_external_claim_evidence")
        self.assertFalse(record["review_boundary"]["mutates_context"])
        self.assertFalse(record["review_boundary"]["mutates_verification_status"])
        self.assertFalse(record["review_boundary"]["mutates_project_takeaway_gate"])
        self.assertFalse(record["review_boundary"]["mutates_action_gate"])
        self.assertFalse(record["review_boundary"]["external_claim_evidence"])
        self.assertEqual(refreshed.json()["records"][0]["latest_decision"]["decision"], "confirmed")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("decision must be one of", invalid.json()["detail"])
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
