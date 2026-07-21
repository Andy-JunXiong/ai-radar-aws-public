import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import signal_review_feedback_service as service  # noqa: E402


TEST_TMP_ROOT = REPO_ROOT / ".tmp-tests"


@contextmanager
def feedback_temp_store():
    path = TEST_TMP_ROOT / f"signal_feedback_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        with patch.object(service, "DATA_DIR", path), patch.object(service, "INDEX_PATH", path / "index.json"):
            yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class SignalReviewFeedbackServiceTests(unittest.TestCase):
    def test_build_feedback_record_preserves_snapshots_and_boundaries(self):
        verification_snapshot = {
            "verification_status": "partially_verified",
            "claim_support_summary": {"inferred": 2, "unsupported": 1},
            "blocked_downstream_actions": ["low_risk_action_candidate"],
        }
        input_provenance_snapshot = {
            "signal": {"published_at": "2026-06-13T00:00:00+00:00"},
            "freshness": {"stale_flags": ["project_context_cache_stale"], "freshness_penalty": 0.15},
        }

        record = service.build_signal_review_feedback_record(
            signal_id="sig-123",
            insight_id="insight-1",
            content_fingerprint="abc123",
            claim_id="claim_1",
            claim_text_snapshot="This claim jumps too far.",
            claim_source_field="synthesized_insight",
            reason_slot="reasoning_gap",
            distortion_tags=["juxtaposition_fusion", "causal_overreach", "caveat_stripping"],
            note="The claim fuses two separate observations.",
            verification_snapshot=verification_snapshot,
            input_provenance_snapshot=input_provenance_snapshot,
            relationship_annotation={
                "relation_type": "evidential_support",
                "grounding_source": "source_excerpt",
                "derivation_mechanism": "direct_observation",
                "support_posture": "confirmed",
                "classified_by": "human",
                "source_refs": ["evidence:item:1"],
                "rationale": "The source excerpt directly states the claim.",
            },
            created_at="2026-06-13T00:00:00+00:00",
        )

        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["record_type"], "signal_claim_review_feedback")
        self.assertEqual(record["reason_slot"], "reasoning_gap")
        self.assertEqual(record["distortion_tags"], ["juxtaposition_fusion", "causal_overreach", "caveat_stripping"])
        self.assertEqual(record["verification_snapshot"], verification_snapshot)
        self.assertEqual(record["input_provenance_snapshot"], input_provenance_snapshot)
        self.assertEqual(
            record["relationship_annotation"],
            {
                "relation_type": "evidential_support",
                "grounding_source": "source_excerpt",
                "derivation_mechanism": "direct_observation",
                "support_posture": "confirmed",
                "review_reason_codes": [],
                "source_refs": ["evidence:item:1"],
                "rationale": "The source excerpt directly states the claim.",
                "classified_by": "human",
            },
        )
        self.assertEqual(record["downstream_effect"], "none")
        self.assertEqual(record["evidence_boundary"], "not_external_claim_evidence")
        self.assertEqual(record["background_update_candidate_id"], "")

        verification_snapshot["verification_status"] = "verified"
        input_provenance_snapshot["freshness"]["stale_flags"].append("mutated_after_build")
        self.assertEqual(record["verification_snapshot"]["verification_status"], "partially_verified")
        self.assertEqual(record["input_provenance_snapshot"]["freshness"]["stale_flags"], ["project_context_cache_stale"])

    def test_relationship_annotation_rejects_metadata_laundered_support(self):
        with self.assertRaises(ValueError) as context:
            service.build_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="reasoning_gap",
                note="Stars are not evidence for the claim.",
                relationship_annotation={
                    "relation_type": "evidential_support",
                    "grounding_source": "structured_metadata",
                    "derivation_mechanism": "deterministic_rule",
                    "support_posture": "confirmed",
                    "classified_by": "system_rule",
                },
            )

        self.assertIn("cannot be confirmed", str(context.exception))

    def test_invalid_reason_slot_and_distortion_tag_are_rejected(self):
        with self.assertRaises(ValueError) as reason_context:
            service.build_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="score_bad",
                note="Wrong shape.",
            )
        self.assertIn("reason_slot", str(reason_context.exception))

        with self.assertRaises(ValueError) as tag_context:
            service.build_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="not_me",
                distortion_tags=["unknown_tag"],
                note="This is not how I would judge it.",
            )
        self.assertIn("Unknown distortion_tags", str(tag_context.exception))

    def test_feedback_record_requires_core_fields(self):
        for kwargs in (
            {"signal_id": "", "claim_id": "claim_1", "reason_slot": "stale_input", "note": "Source is stale."},
            {"signal_id": "sig-123", "claim_id": "", "reason_slot": "stale_input", "note": "Source is stale."},
            {"signal_id": "sig-123", "claim_id": "claim_1", "reason_slot": "stale_input", "note": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    service.build_signal_review_feedback_record(**kwargs)

    def test_append_and_list_feedback_records_use_isolated_store(self):
        with feedback_temp_store() as store:
            first = service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="not_me",
                distortion_tags=["personal_context_mismatch"],
                note="This does not match my project priority.",
                verification_snapshot={"verification_status": "partially_verified"},
                input_provenance_snapshot={"user_context": {"context_scope": "user_specific"}},
            )
            second = service.append_signal_review_feedback_record(
                signal_id="sig-456",
                claim_id="claim_1",
                reason_slot="blind_spot",
                note="This exposed a useful blind spot.",
            )

            self.assertTrue((store / "index.json").exists())
            self.assertTrue((store / f"{first['id']}.json").exists())
            self.assertTrue((store / f"{second['id']}.json").exists())

            with (store / "index.json").open(encoding="utf-8") as handle:
                index = json.load(handle)
            self.assertEqual(len(index), 2)
            self.assertEqual(index[0]["record_type"], "signal_claim_review_feedback")

            self.assertEqual(service.get_signal_review_feedback_record(first["id"]), first)
            self.assertEqual(
                [record["id"] for record in service.list_signal_review_feedback_records(signal_id="sig-123")],
                [first["id"]],
            )
            self.assertEqual(
                [record["id"] for record in service.list_signal_review_feedback_records(reason_slot="blind_spot")],
                [second["id"]],
            )

    def test_creating_feedback_does_not_mutate_verification_or_input_snapshots(self):
        verification_snapshot = {
            "verification_status": "unsupported",
            "blocked_downstream_actions": ["project_takeaway_candidate", "low_risk_action_candidate"],
        }
        input_provenance_snapshot = {"freshness": {"freshness_penalty": 0.25}}

        with feedback_temp_store():
            service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="stale_input",
                note="The project snapshot is stale.",
                verification_snapshot=verification_snapshot,
                input_provenance_snapshot=input_provenance_snapshot,
            )

        self.assertEqual(
            verification_snapshot,
            {
                "verification_status": "unsupported",
                "blocked_downstream_actions": ["project_takeaway_candidate", "low_risk_action_candidate"],
            },
        )
        self.assertEqual(input_provenance_snapshot, {"freshness": {"freshness_penalty": 0.25}})

    def test_background_update_candidates_include_only_user_context_reason_slots(self):
        with feedback_temp_store():
            not_me = service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="not_me",
                distortion_tags=["personal_context_mismatch"],
                note="This does not match my current project priority.",
                verification_snapshot={
                    "verification_status": "partially_verified",
                    "confidence_label": "medium",
                    "blocked_downstream_actions": ["low_risk_action_candidate"],
                },
                input_provenance_snapshot={
                    "freshness": {
                        "summary": "Project context cache may be stale.",
                        "stale_flags": ["project_context_cache_stale"],
                        "freshness_penalty": 0.2,
                    }
                },
            )
            blind_spot = service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_2",
                reason_slot="blind_spot",
                note="This exposed a useful attention gap.",
            )
            service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_3",
                reason_slot="reasoning_gap",
                note="This is a reasoning issue, not a background update.",
            )

            candidates = service.list_background_update_candidates(signal_id="sig-123")

        by_source_id = {candidate["source_feedback_id"]: candidate for candidate in candidates}
        self.assertEqual(set(by_source_id.keys()), {not_me["id"], blind_spot["id"]})
        blind_spot_candidate = by_source_id[blind_spot["id"]]
        not_me_candidate = by_source_id[not_me["id"]]

        self.assertEqual(blind_spot_candidate["record_type"], "background_update_candidate")
        self.assertEqual(blind_spot_candidate["candidate_status"], "inactive_review_only")
        self.assertEqual(blind_spot_candidate["downstream_effect"], "candidate_only")
        self.assertEqual(blind_spot_candidate["evidence_boundary"], "not_external_claim_evidence")
        self.assertFalse(blind_spot_candidate["review_boundary"]["mutates_context"])
        self.assertFalse(blind_spot_candidate["review_boundary"]["mutates_verification_status"])
        self.assertFalse(blind_spot_candidate["review_boundary"]["mutates_project_takeaway_gate"])
        self.assertFalse(blind_spot_candidate["review_boundary"]["mutates_action_gate"])
        self.assertFalse(blind_spot_candidate["review_boundary"]["external_claim_evidence"])
        self.assertEqual(not_me_candidate["candidate_type"], "user_context_alignment")
        self.assertEqual(
            not_me_candidate["verification_snapshot_summary"]["blocked_downstream_actions"],
            ["low_risk_action_candidate"],
        )
        self.assertEqual(not_me_candidate["input_freshness_summary"]["stale_flags"], ["project_context_cache_stale"])

    def test_background_update_candidate_reason_slot_filter_and_limit(self):
        with feedback_temp_store():
            service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="not_me",
                note="This does not match my current project priority.",
            )
            service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_2",
                reason_slot="blind_spot",
                note="This exposed a useful attention gap.",
            )

            not_me_candidates = service.list_background_update_candidates(reason_slot="not_me")
            limited_candidates = service.list_background_update_candidates(limit=1)

        self.assertEqual(len(not_me_candidates), 1)
        self.assertEqual(not_me_candidates[0]["reason_slot"], "not_me")
        self.assertEqual(len(limited_candidates), 1)

    def test_background_update_candidate_decision_is_ledger_only(self):
        with feedback_temp_store():
            feedback = service.append_signal_review_feedback_record(
                signal_id="sig-123",
                claim_id="claim_1",
                reason_slot="not_me",
                note="This does not match my current project priority.",
            )
            candidate = service.list_background_update_candidates(signal_id="sig-123")[0]

            decision = service.append_background_update_candidate_decision(
                candidate_id=str(candidate["id"]),
                source_feedback_id=str(candidate["source_feedback_id"]),
                decision="confirmed",
                note="Confirmed as useful context, but do not apply automatically.",
                candidate_snapshot=candidate,
            )
            enriched_candidate = service.find_background_update_candidate(str(candidate["id"]))

        self.assertEqual(decision["record_type"], "background_update_candidate_decision")
        self.assertEqual(decision["candidate_id"], candidate["id"])
        self.assertEqual(decision["source_feedback_id"], feedback["id"])
        self.assertEqual(decision["decision"], "confirmed")
        self.assertEqual(decision["downstream_effect"], "decision_record_only")
        self.assertEqual(decision["evidence_boundary"], "not_external_claim_evidence")
        self.assertFalse(decision["review_boundary"]["mutates_context"])
        self.assertFalse(decision["review_boundary"]["mutates_verification_status"])
        self.assertFalse(decision["review_boundary"]["mutates_project_takeaway_gate"])
        self.assertFalse(decision["review_boundary"]["mutates_action_gate"])
        self.assertFalse(decision["review_boundary"]["external_claim_evidence"])
        self.assertIsNotNone(enriched_candidate)
        self.assertEqual(enriched_candidate["latest_decision"]["decision"], "confirmed")
        self.assertEqual(enriched_candidate["latest_decision"]["downstream_effect"], "decision_record_only")

    def test_background_update_candidate_decision_rejects_invalid_decision(self):
        with feedback_temp_store():
            with self.assertRaises(ValueError) as context:
                service.append_background_update_candidate_decision(
                    candidate_id="buc_123",
                    source_feedback_id="srf_123",
                    decision="apply_now",
                )

        self.assertIn("decision must be one of", str(context.exception))


if __name__ == "__main__":
    unittest.main()
