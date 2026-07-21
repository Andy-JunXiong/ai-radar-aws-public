import sys
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.routes import projects as projects_route  # noqa: E402
from app.services import (  # noqa: E402
    project_calibration_event_service,
    project_intelligence_service,
    project_learning_profile_service,
    project_review_record_service,
    project_takeaway_constants,
    verification_metadata_reader,
)


TEST_TMP_ROOT = REPO_ROOT / ".tmp-tests"


@contextmanager
def workspace_temp_dir():
    path = TEST_TMP_ROOT / f"project_review_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ProjectTakeawayReviewFlowTests(unittest.TestCase):
    def test_project_takeaway_constants_keep_review_outcome_and_action_state_separate(self):
        self.assertEqual(
            project_takeaway_constants.REVIEW_OUTCOMES,
            frozenset({"confirmed", "rejected", "dismissed", "watch", "action"}),
        )
        self.assertNotIn(
            project_takeaway_constants.PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
            project_takeaway_constants.REVIEW_OUTCOMES,
        )
        self.assertEqual(project_takeaway_constants.ACTION_STATE_COMPLETED, "completed")
        self.assertEqual(
            project_takeaway_constants.EVENT_TYPE_BY_ACTION_STATE[project_takeaway_constants.ACTION_STATE_COMPLETED],
            "action_item_completed",
        )

    def test_action_eligibility_reason_names_unsupported_claim_blocker(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"unsupported": 1, "contradicted": 1}},
                    "action_policy": {"allowed": ["watch_only"], "blocked": []},
                }
            }
        )

        self.assertFalse(result["project_takeaway_candidate"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertIn("2 unsupported or contradicted claim", result["project_takeaway_candidate"]["reason"])
        self.assertIn("2 unsupported or contradicted claim", result["low_risk_action_candidate"]["reason"])
        self.assertTrue(result["watch_only"]["allowed"])
        self.assertEqual(result["project_takeaway_candidate"]["gate"]["severity"], "critical")
        self.assertEqual(result["project_takeaway_candidate"]["gate"]["enforcement_mode"], "hard_block")
        self.assertIn(
            "unsupported_or_contradicted_claims",
            result["project_takeaway_candidate"]["gate"]["reason_codes"],
        )

    def test_action_eligibility_reason_names_not_verifiable_source_blocker(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "verified_insight": {
                    "status": "not_verifiable",
                    "claims": {"support_summary": {}},
                    "action_policy": {"allowed": [], "blocked": []},
                }
            }
        )

        self.assertFalse(result["project_takeaway_candidate"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertIn("not traceable enough", result["project_takeaway_candidate"]["reason"])
        self.assertIn("not traceable enough", result["low_risk_action_candidate"]["reason"])

    def test_action_eligibility_reason_names_weak_evidence_watch_path(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "verified_insight": {
                    "status": "weakly_supported",
                    "claims": {"support_summary": {"inferred": 1}},
                    "action_policy": {"allowed": ["watch_only"], "blocked": []},
                }
            }
        )

        self.assertTrue(result["watch_only"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertIn("weak", result["watch_only"]["reason"].lower())
        self.assertIn("weak evidence", result["low_risk_action_candidate"]["reason"].lower())
        self.assertTrue(result["project_takeaway_candidate"]["allowed"])
        self.assertEqual(result["project_takeaway_candidate"]["gate"]["severity"], "warning")
        self.assertEqual(result["project_takeaway_candidate"]["gate"]["enforcement_mode"], "warn_proceed")
        self.assertIn(
            "weak_evidence_review_only",
            result["project_takeaway_candidate"]["gate"]["reason_codes"],
        )
        self.assertEqual(result["low_risk_action_candidate"]["gate"]["severity"], "critical")
        self.assertEqual(result["low_risk_action_candidate"]["gate"]["enforcement_mode"], "hard_block")

    def test_action_eligibility_reason_names_explicit_low_risk_action_block(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "verified_insight": {
                    "status": "verified",
                    "claims": {"support_summary": {"directly_supported": 2}},
                    "action_policy": {
                        "allowed": ["project_takeaway_candidate", "watch_only"],
                        "blocked": ["low_risk_action_candidate"],
                    },
                }
            }
        )

        self.assertTrue(result["project_takeaway_candidate"]["allowed"])
        self.assertTrue(result["watch_only"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertIn("explicitly blocks low-risk Action", result["low_risk_action_candidate"]["reason"])
        self.assertEqual(result["project_takeaway_candidate"]["gate"]["enforcement_mode"], "pass")
        self.assertEqual(result["low_risk_action_candidate"]["gate"]["severity"], "critical")
        self.assertEqual(result["low_risk_action_candidate"]["gate"]["enforcement_mode"], "hard_block")
        self.assertIn(
            "explicit_downstream_block",
            result["low_risk_action_candidate"]["gate"]["reason_codes"],
        )

    def test_action_eligibility_blocks_knowledge_convergence_action_by_default(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "knowledge_convergence": True,
                "verification_status": "knowledge_convergence_review_candidate",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            }
        )

        self.assertTrue(result["project_takeaway_candidate"]["allowed"])
        self.assertTrue(result["watch_only"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertIn("Knowledge convergence", result["low_risk_action_candidate"]["reason"])

    def test_action_eligibility_reports_allowed_blocked_conflicts_without_changing_gate(self):
        result = verification_metadata_reader.build_action_eligibility_summary(
            {
                "verification_status": "partially_verified",
                "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
                "blocked_downstream_actions": ["watch_only", "low_risk_action_candidate"],
                "claim_support_summary": {"inferred": 1},
            }
        )

        self.assertTrue(result["project_takeaway_candidate"]["allowed"])
        self.assertTrue(result["watch_only"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])
        self.assertEqual(result["signals"]["conflicting_downstream_actions"], ["watch_only"])
        self.assertEqual(result["watch_only"]["gate"]["severity"], "warning")
        self.assertEqual(result["watch_only"]["gate"]["enforcement_mode"], "warn_proceed")
        self.assertIn(
            "conflicting_allowed_and_blocked_actions",
            result["watch_only"]["gate"]["reason_codes"],
        )

    def test_model_provenance_alone_does_not_satisfy_project_takeaway_gate(self):
        verification = {
            "produced_by_model": {
                "provenance_schema_version": 1,
                "provider": "openai",
                "model_id": "gpt-test",
            }
        }

        self.assertFalse(verification_metadata_reader.has_project_takeaway_verification_context(verification))
        self.assertEqual(
            verification_metadata_reader.get_model_provenance(verification)["provenance_schema_version"],
            1,
        )
        result = verification_metadata_reader.build_action_eligibility_summary(verification)
        self.assertFalse(result["project_takeaway_candidate"]["allowed"])
        self.assertFalse(result["low_risk_action_candidate"]["allowed"])

    def test_create_project_takeaway_candidate_reads_nested_verified_insight_gate(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-nested-block",
            signal_title="Nested block",
            verification_metadata={
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"partially_supported": 1}},
                    "action_policy": {
                        "allowed": ["reflection_draft", "watch_only"],
                        "blocked": ["project_takeaway_candidate"],
                    },
                }
            },
        )

        with self.assertRaises(HTTPException) as context:
            projects_route.create_project_takeaway_candidate(payload)

        self.assertIn(
            "Verification blocks project takeaway candidate creation",
            str(getattr(context.exception, "detail", context.exception)),
        )

    def test_create_project_takeaway_candidate_rejects_missing_verification_metadata(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-missing-verification",
            signal_title="Missing verification",
            relevance_to_projects={"AI Radar": "This should not enter review without verification."},
            verification_metadata={},
        )

        with self.assertRaises(HTTPException) as context:
            projects_route.create_project_takeaway_candidate(payload)

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("requires verification metadata", context.exception.detail)

    def test_project_takeaway_candidate_write_carries_model_provenance(self):
        produced_by_model = {
            "provider": "openai",
            "model_id": "gpt-test",
            "model_version": "",
            "task_type": "insight",
            "route_key": "insight.synthesize",
            "router_source": "env",
            "prompt_template_id": "signal_insight",
            "prompt_template_version": "v1",
            "inference_params": {
                "temperature": 0.3,
                "max_tokens": 1800,
                "top_p": None,
                "stop_sequences": [],
            },
            "deterministic_fingerprint": "b" * 64,
            "generated_at": "2026-05-22T00:00:00+00:00",
            "provenance_schema_version": 1,
        }

        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "list_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar", "enabled": True}],
        ):
            written = project_intelligence_service.add_signal_to_project_improvements(
                signal_id="sig-provenance",
                signal_title="Provenance candidate",
                signal_summary="Summary",
                why_it_matters="Why",
                relevance_to_projects={"AI Radar": "Useful project fit."},
                synthesized_insight="Insight",
                final_reflection="Reflection",
                verification_metadata={
                    "verification_status": "verified",
                    "allowed_downstream_actions": ["project_takeaway_candidate"],
                    "blocked_downstream_actions": [],
                    "produced_by_model": produced_by_model,
                },
                candidate_source="verified_insight",
                status="candidate",
            )

        self.assertEqual(written[0]["produced_by_model"], produced_by_model)
        self.assertEqual(written[0]["verification_metadata"]["produced_by_model"], produced_by_model)

    def test_create_project_takeaway_candidate_fills_model_provenance_from_signal(self):
        produced_by_model = {
            "provider": "anthropic",
            "model_id": "claude-test",
            "model_version": "",
            "task_type": "insight",
            "route_key": "insight.synthesize",
            "router_source": "env",
            "prompt_template_id": "signal_insight",
            "prompt_template_version": "v1",
            "inference_params": {
                "temperature": 0.3,
                "max_tokens": 1800,
                "top_p": None,
                "stop_sequences": [],
            },
            "deterministic_fingerprint": "c" * 64,
            "generated_at": "2026-05-22T00:00:00+00:00",
            "provenance_schema_version": 1,
        }
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-route-provenance",
            signal_title="Route fills provenance",
            relevance_to_projects={"AI Radar": "Useful project fit."},
            verification_metadata={
                "verification_status": "verified",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            },
        )

        with patch.object(
            projects_route,
            "get_signal_by_id",
            return_value={"produced_by_model": produced_by_model},
        ), patch.object(
            projects_route,
            "add_signal_to_project_improvements",
            return_value=[],
        ) as add_signal:
            projects_route.create_project_takeaway_candidate(payload)

        passed_metadata = add_signal.call_args.kwargs["verification_metadata"]
        self.assertEqual(passed_metadata["produced_by_model"], produced_by_model)

    def test_create_project_takeaway_candidate_preserves_verified_claim_items(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-claim-items",
            signal_title="Claim item preservation",
            relevance_to_projects={"AI Radar": "Useful project fit."},
            verification_metadata={
                "verification_status": "partially_verified",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": ["low_risk_action_candidate"],
                "claim_support_summary": {"partially_supported": 1},
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {
                        "count": 1,
                        "support_summary": {"partially_supported": 1},
                        "items": [
                            {
                                "claim_id": "claim_1",
                                "claim_text": "Project-relevant but bounded claim.",
                                "support_level": "partially_supported",
                            }
                        ],
                    },
                    "action_policy": {
                        "allowed": ["project_takeaway_candidate"],
                        "blocked": ["low_risk_action_candidate"],
                    },
                },
            },
        )

        with patch.object(
            projects_route,
            "add_signal_to_project_improvements",
            return_value=[{"signal_id": "sig-claim-items"}],
        ) as add_signal:
            result = projects_route.create_project_takeaway_candidate(payload)

        self.assertEqual(result["created_count"], 1)
        passed_metadata = add_signal.call_args.kwargs["verification_metadata"]
        claim_items = passed_metadata["verified_insight"]["claims"]["items"]
        self.assertEqual(claim_items[0]["claim_id"], "claim_1")
        self.assertEqual(
            passed_metadata["verified_insight"]["claims"]["support_summary"],
            {"partially_supported": 1},
        )

    def test_create_project_takeaway_candidate_requires_manual_override_note(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-manual-override-no-note",
            signal_title="Manual override without note",
            relevance_to_projects={"AI Radar": "Human reviewer wants to inspect this."},
            verification_metadata={
                "manual_project_takeaway_override": True,
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"unsupported": 1}},
                    "action_policy": {
                        "allowed": ["reflection_draft"],
                        "blocked": ["project_takeaway_candidate"],
                    },
                },
            },
        )

        with self.assertRaises(HTTPException) as context:
            projects_route.create_project_takeaway_candidate(payload)

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("override note", context.exception.detail)

    def test_signal_completion_without_verification_is_marked_unverified(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "list_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar", "enabled": True}],
        ):
            written = project_intelligence_service.add_signal_to_project_improvements(
                signal_id="sig-unverified-completion",
                signal_title="Unverified completion",
                signal_summary="A signal completed from the workspace path.",
                why_it_matters="It may matter.",
                relevance_to_projects={"AI Radar": "Review this manually."},
                synthesized_insight="Possible project relevance.",
                final_reflection="Completed without verification metadata.",
                verification_metadata={},
                candidate_source="signal_completion",
                status="new",
            )

        self.assertEqual(len(written), 1)
        item = written[0]
        self.assertEqual(item["candidate_source"], "unverified_manual_entry")
        self.assertTrue(item["verification_metadata"]["verification_required"])
        self.assertEqual(item["verification_metadata"]["verification_status"], "unverified_manual_entry")
        self.assertFalse(item["action_eligibility"]["project_takeaway_candidate"]["allowed"])

    def test_create_project_takeaway_candidate_reads_nested_claim_support_summary(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-nested-claims",
            signal_title="Nested claims",
            verification_metadata={
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"unsupported": 1}},
                    "action_policy": {
                        "allowed": ["reflection_draft"],
                        "blocked": [],
                    },
                }
            },
        )

        with self.assertRaises(HTTPException) as context:
            projects_route.create_project_takeaway_candidate(payload)

        self.assertIn(
            "Unsupported or contradicted claims block project takeaway candidate creation",
            str(getattr(context.exception, "detail", context.exception)),
        )

    def test_create_project_takeaway_candidate_allows_manual_override_with_blocked_gate(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="sig-manual-override",
            signal_title="Manual override",
            relevance_to_projects={"AI Radar": "Human reviewer wants to inspect this."},
            verification_metadata={
                "manual_project_takeaway_override": True,
                "manual_override_note": "verification blocks Project Takeaway candidate creation",
                "verified_insight": {
                    "status": "partially_verified",
                    "claims": {"support_summary": {"unsupported": 1}},
                    "action_policy": {
                        "allowed": ["reflection_draft"],
                        "blocked": ["project_takeaway_candidate"],
                    },
                },
            },
        )

        with patch.object(projects_route, "add_signal_to_project_improvements", return_value=[{"signal_id": "sig-manual-override"}]) as add_signal:
            result = projects_route.create_project_takeaway_candidate(payload)

        self.assertEqual(result["created_count"], 1)
        add_signal.assert_called_once()
        kwargs = add_signal.call_args.kwargs
        self.assertEqual(kwargs["candidate_source"], "manual_project_takeaway_override")
        self.assertTrue(kwargs["verification_metadata"]["manual_project_takeaway_override"])

    def test_create_project_takeaway_candidate_marks_knowledge_convergence_source(self):
        payload = projects_route.ProjectTakeawayCandidateRequest(
            signal_id="knowledge-convergence-abc",
            signal_title="Knowledge convergence",
            relevance_to_projects={"AI Radar": "Review supply-demand convergence."},
            verification_metadata={
                "knowledge_convergence": True,
                "verification_status": "knowledge_convergence_review_candidate",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            },
        )

        with patch.object(projects_route, "add_signal_to_project_improvements", return_value=[{"signal_id": "knowledge-convergence-abc"}]) as add_signal:
            result = projects_route.create_project_takeaway_candidate(payload)

        self.assertEqual(result["created_count"], 1)
        add_signal.assert_called_once()
        kwargs = add_signal.call_args.kwargs
        self.assertEqual(kwargs["candidate_source"], "knowledge_convergence")
        self.assertTrue(kwargs["verification_metadata"]["knowledge_convergence"])
        self.assertIn("low_risk_action_candidate", kwargs["verification_metadata"]["blocked_downstream_actions"])
        self.assertIn("strong_recommendation", kwargs["verification_metadata"]["blocked_downstream_actions"])

    def test_create_project_takeaway_candidate_from_confirmed_final_takeaway(self):
        payload = projects_route.ConfirmedFinalTakeawayCandidateRequest(
            signal_id="sig-final-takeaway",
            signal_title="Final Takeaway source",
            relevance_to_projects={"AI Radar": "Review the confirmed takeaway."},
            final_takeaway_id="fta_confirmed",
            verification_metadata={
                "verification_status": "partially_verified",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            },
        )
        artifact = {
            "final_takeaway_id": "fta_confirmed",
            "status": "confirmed",
            "signal_id": "sig-final-takeaway",
            "confirmed_text": "Andy-confirmed project takeaway wording.",
            "source_completion_note": "Draft completion note.",
            "confirmed_at": "2026-06-21T09:44:00+00:00",
            "review_bundle_snapshot_id": "rbs_confirmed",
            "review_bundle_content_hash": "a" * 64,
        }

        with patch.object(
            projects_route.final_takeaway_artifacts,
            "get_final_takeaway",
            return_value=artifact,
        ), patch.object(
            projects_route,
            "add_signal_to_project_improvements",
            return_value=[{"signal_id": "sig-final-takeaway"}],
        ) as add_signal:
            result = projects_route.create_project_takeaway_candidate_from_final_takeaway(payload)

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["candidate_source"], "confirmed_final_takeaway")
        self.assertEqual(result["final_takeaway_id"], "fta_confirmed")
        kwargs = add_signal.call_args.kwargs
        self.assertEqual(kwargs["candidate_source"], "confirmed_final_takeaway")
        self.assertEqual(kwargs["synthesized_insight"], "Andy-confirmed project takeaway wording.")
        metadata = kwargs["verification_metadata"]
        self.assertTrue(metadata["confirmed_final_takeaway"])
        self.assertEqual(metadata["candidate_requested_from"], "confirmed_final_takeaway")
        self.assertEqual(metadata["final_takeaway_id"], "fta_confirmed")
        self.assertEqual(metadata["review_bundle_snapshot_id"], "rbs_confirmed")
        self.assertIn("low_risk_action_candidate", metadata["blocked_downstream_actions"])
        self.assertIn("strong_recommendation", metadata["blocked_downstream_actions"])

    def test_create_project_takeaway_candidate_from_final_takeaway_requires_artifact(self):
        payload = projects_route.ConfirmedFinalTakeawayCandidateRequest(
            signal_id="sig-missing-final-takeaway",
            signal_title="Missing Final Takeaway",
            relevance_to_projects={"AI Radar": "Review this."},
            final_takeaway_id="fta_missing",
            verification_metadata={
                "verification_status": "partially_verified",
                "allowed_downstream_actions": ["project_takeaway_candidate"],
                "blocked_downstream_actions": [],
            },
        )

        with patch.object(
            projects_route.final_takeaway_artifacts,
            "get_final_takeaway",
            return_value=None,
        ), self.assertRaises(HTTPException) as context:
            projects_route.create_project_takeaway_candidate_from_final_takeaway(payload)

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("final takeaway artifact not found", context.exception.detail)

    def test_close_project_takeaway_candidate_rejects_with_reason(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {
                    "items": [
                        {
                            "project_id": "ai_radar",
                            "signal_id": "sig-1",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                        }
                    ]
                },
            )

            result = project_intelligence_service.close_project_takeaway_candidate(
                "ai_radar",
                "sig-1",
                status="rejected",
                reason="Not relevant enough for this project.",
            )

            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["review_outcome"], "rejected")
            self.assertEqual(result["rejection_reason"], "Not relevant enough for this project.")
            self.assertIn("reviewed_at", result)
            self.assertIn("rejected_at", result)

            saved = project_intelligence_service.load_project_improvements("ai_radar")
            self.assertEqual(saved["items"][0]["status"], "rejected")
            records = project_review_record_service.list_project_review_records(
                project_id="ai_radar",
                signal_id="sig-1",
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["outcome"], "rejected")
            self.assertEqual(records[0]["reason"], "Not relevant enough for this project.")
            events = project_calibration_event_service.list_project_calibration_events(project_id="ai_radar")
            self.assertEqual({event["event_type"] for event in events}, {"review_record_created", "takeaway_rejected"})

    def test_reasoning_counter_check_draft_persists_as_reviewer_advisory_only(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {
                    "items": [
                        {
                            "project_id": "ai_radar",
                            "signal_id": "sig-counter-check",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                            "verification_metadata": {
                                "verification_status": "partially_verified",
                                "blocked_downstream_actions": ["low_risk_action_candidate"],
                            },
                            "action_eligibility": {
                                "low_risk_action_candidate": {"allowed": False},
                            },
                        }
                    ]
                },
            )

            draft = {
                "answer": "unclear",
                "summary": "The packet is underdetermined.",
                "boundary": "LLM advisory only.",
            }

            result = project_intelligence_service.save_reasoning_counter_check_draft(
                "ai_radar",
                "sig-counter-check",
                draft,
            )

            self.assertEqual(result["reasoning_counter_check_draft"], draft)
            self.assertEqual(result["reasoning_counter_check_effect"], "reviewer_advisory_only")
            self.assertIn("reasoning_counter_check_saved_at", result)
            self.assertEqual(
                result["verification_metadata"],
                {
                    "verification_status": "partially_verified",
                    "blocked_downstream_actions": ["low_risk_action_candidate"],
                },
            )
            self.assertEqual(result["action_eligibility"], {"low_risk_action_candidate": {"allowed": False}})

            saved = project_intelligence_service.load_project_improvements("ai_radar")
            self.assertEqual(saved["items"][0]["reasoning_counter_check_draft"], draft)
            self.assertNotIn("reasoning_counter_check_draft", saved["items"][0]["verification_metadata"])

    def test_project_review_record_detail_route_returns_record_by_id(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            saved = project_review_record_service.save_project_review_record(
                project_review_record_service.build_project_review_record(
                    project_id="ai_radar",
                    signal_id="sig-record-detail",
                    outcome="watch",
                    reason="Keep under observation.",
                    source_status="candidate",
                    item={
                        "project_name": "AI Radar",
                        "signal_title": "Record detail signal",
                        "verification_metadata": {
                            "verification_status": "partially_verified",
                            "claims": {"support_summary": {"inferred": 1}},
                            "action_policy": {"blocked": ["low_risk_action_candidate"]},
                        },
                    },
                )
            )
            project_calibration_event_service.append_project_calibration_event(
                event_type="review_record_created",
                project_id="ai_radar",
                signal_id="sig-record-detail",
                outcome="watch",
                source_status="candidate",
                review_record_id=saved["id"],
            )
            project_calibration_event_service.append_project_calibration_event(
                event_type="watch_item_created",
                project_id="ai_radar",
                signal_id="sig-record-detail",
                outcome="watch",
                source_status="candidate",
            )

            result = projects_route.get_project_review_record_detail(saved["id"])

            self.assertEqual(result["item"]["id"], saved["id"])
            self.assertEqual(result["item"]["outcome"], "watch")
            self.assertEqual(result["item"]["reason"], "Keep under observation.")
            self.assertEqual(result["item"]["verification_status"], "partially_verified")
            self.assertEqual(result["audit_summary"]["event_count"], 2)
            self.assertTrue(result["audit_summary"]["has_review_record_created"])
            self.assertTrue(result["audit_summary"]["has_outcome_event"])
            self.assertEqual(result["audit_summary"]["matching_review_record_event_count"], 1)
            self.assertEqual(
                {event["event_type"] for event in result["related_calibration_events"]},
                {"review_record_created", "watch_item_created"},
            )
            self.assertEqual(result["related_calibration_events"][0]["event_type"], "review_record_created")
            self.assertTrue(result["related_calibration_events"][0]["is_current_review_record_event"])
            self.assertFalse(result["related_calibration_events"][1]["is_current_review_record_event"])
            self.assertEqual(result["message"], "project review record loaded successfully")

    def test_project_review_record_detail_route_raises_404_for_missing_record(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            with self.assertRaises(HTTPException) as error:
                projects_route.get_project_review_record_detail("prv_missing")

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "project review record not found")

    def test_close_project_takeaway_candidate_blocks_action_when_verification_blocks_low_risk_action(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {
                    "items": [
                        {
                            "project_id": "ai_radar",
                            "signal_id": "sig-action-blocked",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                            "verification_metadata": {
                                "verified_insight": {
                                    "status": "partially_verified",
                                    "claims": {"support_summary": {"unsupported": 1}},
                                    "action_policy": {
                                        "allowed": ["watch_only"],
                                        "blocked": ["low_risk_action_candidate"],
                                    },
                                }
                            },
                        }
                    ]
                },
            )

            with self.assertRaises(ValueError) as context:
                project_intelligence_service.close_project_takeaway_candidate(
                    "ai_radar",
                    "sig-action-blocked",
                    status="action",
                    expected_outcome="Ship a change",
                    due_date="2026-05-15",
                    review_date="2026-05-20",
                )

            self.assertIn("not action", str(context.exception))

    def test_close_project_takeaway_candidate_blocks_manual_override_action_without_override_endpoint(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {
                    "items": [
                        {
                            "project_id": "ai_radar",
                            "signal_id": "sig-action-override",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                            "verification_metadata": {
                                "manual_project_takeaway_override": True,
                                "verified_insight": {
                                    "status": "partially_verified",
                                    "claims": {"support_summary": {"unsupported": 1}},
                                    "action_policy": {
                                        "allowed": ["watch_only"],
                                        "blocked": ["low_risk_action_candidate"],
                                    },
                                },
                            },
                        }
                    ]
                },
            )

            with self.assertRaises(ValueError) as context:
                project_intelligence_service.close_project_takeaway_candidate(
                    "ai_radar",
                    "sig-action-override",
                    status="action",
                    expected_outcome="Human-reviewed low-risk action",
                    due_date="2026-05-15",
                    review_date="2026-05-20",
                )

            self.assertIn("explicitly blocks low-risk Action", str(context.exception))

    def test_override_action_project_takeaway_candidate_records_auditable_override(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {
                    "items": [
                        {
                            "project_id": "ai_radar",
                            "signal_id": "sig-action-override",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                            "verification_metadata": {
                                "verified_insight": {
                                    "status": "partially_verified",
                                    "claims": {"support_summary": {"unsupported": 1}},
                                    "action_policy": {
                                        "allowed": ["watch_only"],
                                        "blocked": ["low_risk_action_candidate"],
                                    },
                                },
                            },
                        }
                    ]
                },
            )

            result = project_intelligence_service.override_action_project_takeaway_candidate(
                "ai_radar",
                "sig-action-override",
                reason="Human reviewer accepts the risk for a bounded action.",
                expected_outcome="The action produces a measurable project learning.",
                due_date="2026-05-15",
                review_date="2026-05-20",
            )

            records = project_review_record_service.list_project_review_records(
                project_id="ai_radar",
                signal_id="sig-action-override",
            )

        self.assertEqual(result["status"], "action")
        self.assertEqual(result["candidate_source"], "manual_project_takeaway_override")
        self.assertTrue(result["verification_metadata"]["manual_project_takeaway_override"])
        self.assertEqual(result["verification_metadata"]["manual_override_type"], "action")
        self.assertFalse(result["action_eligibility"]["low_risk_action_candidate"]["allowed"])
        self.assertEqual(records[0]["outcome"], "action")
        self.assertTrue(records[0]["manual_project_takeaway_override"])
        self.assertEqual(records[0]["manual_override_note"], "Human reviewer accepts the risk for a bounded action.")

    def test_close_project_takeaway_candidate_dismisses_with_reason(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "glap",
                {
                    "items": [
                        {
                            "project_id": "glap",
                            "signal_id": "sig-2",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                        }
                    ]
                },
            )

            result = project_intelligence_service.close_project_takeaway_candidate(
                "glap",
                "sig-2",
                status="dismissed",
                reason="Later, but not for this review queue.",
            )

            self.assertEqual(result["status"], "dismissed")
            self.assertEqual(result["review_outcome"], "dismissed")
            self.assertEqual(result["dismissal_reason"], "Later, but not for this review queue.")
            self.assertIn("reviewed_at", result)
            self.assertIn("dismissed_at", result)

    def test_close_project_takeaway_candidate_adds_watch_with_reason(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "trajectory_memory",
                {
                    "items": [
                        {
                            "project_id": "trajectory_memory",
                            "signal_id": "sig-3",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                        }
                    ]
                },
            )

            result = project_intelligence_service.close_project_takeaway_candidate(
                "trajectory_memory",
                "sig-3",
                status="watch",
                reason="Interesting, but needs more evidence over time.",
                review_date="2026-05-15",
                success_criteria="Watch for two independent repo adoption signals.",
                watch_status="watching",
            )

            self.assertEqual(result["status"], "watch")
            self.assertEqual(result["review_outcome"], "watch")
            self.assertEqual(result["watch_reason"], "Interesting, but needs more evidence over time.")
            self.assertEqual(result["watch_review_date"], "2026-05-15")
            self.assertEqual(result["watch_success_criteria"], "Watch for two independent repo adoption signals.")
            self.assertEqual(result["watch_status"], "watching")
            self.assertIn("reviewed_at", result)
            self.assertIn("watched_at", result)
            summary = project_calibration_event_service.summarize_project_calibration_events(
                project_id="trajectory_memory"
            )
            self.assertEqual(summary["event_counts"]["watch_item_created"], 1)
            self.assertEqual(summary["event_counts"]["review_record_created"], 1)

    def test_confirm_project_improvement_blocks_missing_verification(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {"items": [{"project_id": "ai_radar", "signal_id": "sig-unverified", "status": "candidate"}]},
            )

            with self.assertRaises(ValueError) as context:
                project_intelligence_service.confirm_project_improvement("ai_radar", "sig-unverified")

        self.assertIn("verification metadata is missing", str(context.exception))

    def test_override_confirm_project_improvement_requires_note_and_expected_outcome(self):
        with self.assertRaises(ValueError) as context:
            project_intelligence_service.override_confirm_project_improvement(
                "ai_radar",
                "sig-any",
                reason="",
                expected_outcome="",
            )

        self.assertIn("manual override note", str(context.exception))

    def test_override_confirm_project_improvement_records_auditable_override(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_radar",
                {"items": [{"project_id": "ai_radar", "signal_id": "sig-override-confirm", "status": "candidate"}]},
            )

            result = project_intelligence_service.override_confirm_project_improvement(
                "ai_radar",
                "sig-override-confirm",
                reason="Human reviewer accepts the risk for a narrow experiment.",
                expected_outcome="The candidate produces a useful reviewed project note.",
            )

            records = project_review_record_service.list_project_review_records(project_id="ai_radar")

        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["candidate_source"], "manual_project_takeaway_override")
        self.assertTrue(result["verification_metadata"]["manual_project_takeaway_override"])
        self.assertEqual(result["verification_metadata"]["manual_override_type"], "confirm")
        self.assertEqual(result["manual_override_expected_outcome"], "The candidate produces a useful reviewed project note.")
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["manual_project_takeaway_override"])
        self.assertEqual(records[0]["manual_override_note"], "Human reviewer accepts the risk for a narrow experiment.")

    def test_close_project_takeaway_candidate_adds_action_with_reason(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_cognitive",
                {
                    "items": [
                        {
                            "project_id": "ai_cognitive",
                            "signal_id": "sig-4",
                            "status": "candidate",
                            "takeaway": "Candidate takeaway",
                            "verification_metadata": {
                                "verified_insight": {
                                    "status": "verified",
                                    "claims": {"support_summary": {"directly_supported": 1}},
                                    "action_policy": {
                                        "allowed": ["project_takeaway_candidate", "low_risk_action_candidate"],
                                        "blocked": [],
                                    },
                                }
                            },
                        }
                    ]
                },
            )

            result = project_intelligence_service.close_project_takeaway_candidate(
                "ai_cognitive",
                "sig-4",
                status="action",
                reason="Turn this into a small implementation task.",
                expected_outcome="A small implementation task is created and validated.",
                due_date="2026-05-10",
                review_date="2026-05-17",
            )

            self.assertEqual(result["status"], "action")
            self.assertEqual(result["review_outcome"], "action")
            self.assertEqual(result["action_reason"], "Turn this into a small implementation task.")
            self.assertEqual(result["action_expected_outcome"], "A small implementation task is created and validated.")
            self.assertEqual(result["action_due_date"], "2026-05-10")
            self.assertEqual(result["action_review_date"], "2026-05-17")
            self.assertIn("reviewed_at", result)
            self.assertIn("action_created_at", result)

    def test_watch_route_requires_watch_detail_fields(self):
        with patch.object(projects_route, "get_project", return_value={"id": "ai_radar"}), patch.object(
            projects_route,
            "close_project_takeaway_candidate",
        ) as close_candidate:
            with self.assertRaises(projects_route.HTTPException) as context:
                projects_route.watch_project_takeaway_candidate(
                    "ai_radar",
                    "sig-watch-required",
                    projects_route.ProjectTakeawayReviewActionRequest(
                        reason="Watch this later.",
                        review_date="2026-05-15",
                        success_criteria="",
                        watch_status="watching",
                    ),
                )

            self.assertEqual(context.exception.status_code, 400)
            self.assertIn("watch success criteria", context.exception.detail)
            close_candidate.assert_not_called()

    def test_action_route_requires_action_detail_fields(self):
        with patch.object(projects_route, "get_project", return_value={"id": "ai_radar"}), patch.object(
            projects_route,
            "close_project_takeaway_candidate",
        ) as close_candidate:
            with self.assertRaises(projects_route.HTTPException) as context:
                projects_route.action_project_takeaway_candidate(
                    "ai_radar",
                    "sig-action-required",
                    projects_route.ProjectTakeawayReviewActionRequest(
                        reason="Turn this into action.",
                        expected_outcome="Ship the follow-up change.",
                        due_date="",
                        review_date="2026-05-17",
                    ),
                )

            self.assertEqual(context.exception.status_code, 400)
            self.assertIn("action due date", context.exception.detail)
            close_candidate.assert_not_called()

    def test_review_watch_route_requires_followup_result(self):
        with patch.object(projects_route, "get_project", return_value={"id": "ai_radar"}), patch.object(
            projects_route,
            "review_project_watch_item",
            side_effect=ValueError("Watch review requires a follow-up result."),
        ) as review_watch:
            with self.assertRaises(projects_route.HTTPException) as context:
                projects_route.review_project_takeaway_watch(
                    "ai_radar",
                    "sig-watch-route",
                    projects_route.ProjectTakeawayReviewActionRequest(
                        reason="No result yet.",
                        followup_result="",
                    ),
                )

            self.assertEqual(context.exception.status_code, 400)
            self.assertIn("follow-up result", context.exception.detail)
            review_watch.assert_called_once()

    def test_complete_project_action_item_marks_action_completed(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_cognitive",
                {
                    "items": [
                        {
                            "project_id": "ai_cognitive",
                            "signal_id": "sig-5",
                            "status": "action",
                            "takeaway": "Action takeaway",
                            "action_expected_outcome": "Ship the follow-up change.",
                            "action_due_date": "2026-05-10",
                            "action_review_date": "2026-05-17",
                        }
                    ]
                },
            )

            result = project_intelligence_service.complete_project_action_item(
                "ai_cognitive",
                "sig-5",
                note="Implemented the first follow-up task.",
                followup_result="expected_outcome_met",
                evidence_update="The implementation shipped and local tests passed.",
                next_review_date="2026-05-24",
            )

            self.assertEqual(result["status"], "action_completed")
            self.assertEqual(result["review_outcome"], "action")
            self.assertEqual(result["action_state"], "completed")
            self.assertEqual(result["action_completion_note"], "Implemented the first follow-up task.")
            self.assertEqual(result["action_completion_result"], "expected_outcome_met")
            self.assertEqual(result["action_completion_evidence_update"], "The implementation shipped and local tests passed.")
            self.assertEqual(result["action_next_review_date"], "2026-05-24")
            self.assertEqual(result["action_expected_outcome"], "Ship the follow-up change.")
            self.assertEqual(result["action_due_date"], "2026-05-10")
            self.assertEqual(result["action_review_date"], "2026-05-17")
            self.assertIn("action_completed_at", result)
            records = project_review_record_service.list_project_review_records(
                project_id="ai_cognitive",
                signal_id="sig-5",
            )
            self.assertEqual(records, [])
            events = project_calibration_event_service.list_project_calibration_events(project_id="ai_cognitive")
            self.assertEqual(
                {event["event_type"] for event in events},
                {"action_item_completed"},
            )
            completed_event = next(event for event in events if event["event_type"] == "action_item_completed")
            self.assertEqual(completed_event["followup_result"], "expected_outcome_met")
            self.assertEqual(completed_event["review_note"], "Implemented the first follow-up task.")
            self.assertEqual(completed_event["evidence_update"], "The implementation shipped and local tests passed.")
            self.assertEqual(completed_event["next_review_date"], "2026-05-24")
            self.assertEqual(completed_event["expected_outcome"], "Ship the follow-up change.")

    def test_review_project_watch_item_records_followup_calibration_event(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_intelligence_service,
            "PROJECT_IMPROVEMENTS_DIR",
            temp_dir,
        ), patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_intelligence_service,
            "_read_s3_improvements",
            return_value=None,
        ), patch.object(
            project_intelligence_service,
            "_write_s3_improvements",
            return_value=None,
        ):
            project_intelligence_service.save_project_improvements(
                "ai_cognitive",
                {
                    "items": [
                        {
                            "project_id": "ai_cognitive",
                            "signal_id": "sig-watch-followup",
                            "status": "watch",
                            "takeaway": "Watch takeaway",
                            "watch_review_date": "2026-05-17",
                            "watch_success_criteria": "Look for a second credible source.",
                            "watch_status": "watching",
                            "verification_metadata": {
                                "verified_insight": {
                                    "status": "partially_verified",
                                    "claims": {"support_summary": {"inferred": 1}},
                                    "action_policy": {
                                        "allowed": ["project_takeaway_candidate", "watch_only"],
                                        "blocked": ["low_risk_action_candidate"],
                                    },
                                }
                            },
                        }
                    ]
                },
            )

            result = project_intelligence_service.review_project_watch_item(
                "ai_cognitive",
                "sig-watch-followup",
                followup_result="evidence_improved",
                note="A second source appeared; keep watching for adoption.",
                evidence_update="Source B now independently reports the same direction.",
                next_review_date="2026-05-31",
            )

            self.assertEqual(result["status"], "watch")
            self.assertEqual(result["watch_followup_result"], "evidence_improved")
            self.assertEqual(result["watch_review_note"], "A second source appeared; keep watching for adoption.")
            self.assertEqual(result["watch_evidence_update"], "Source B now independently reports the same direction.")
            self.assertEqual(result["watch_next_review_date"], "2026-05-31")
            self.assertEqual(result["watch_followup_count"], 1)
            self.assertEqual(result["watch_review_date"], "2026-05-31")
            events = project_calibration_event_service.list_project_calibration_events(project_id="ai_cognitive")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "watch_item_reviewed")
            self.assertEqual(events[0]["outcome"], "watch")
            self.assertEqual(events[0]["followup_result"], "evidence_improved")
            self.assertEqual(events[0]["review_note"], "A second source appeared; keep watching for adoption.")
            summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_cognitive")
            self.assertEqual(summary["watch_reviewed_event_count"], 1)

    def test_review_inbox_list_excludes_closed_candidates(self):
        with patch.object(
            projects_route,
            "list_projects",
            return_value=[{"project_id": "ai_radar", "name": "AI Radar"}],
        ), patch.object(
            projects_route,
            "load_project_improvements",
            return_value={
                "items": [
                    {"project_id": "ai_radar", "signal_id": "pending-1", "status": "candidate"},
                    {"project_id": "ai_radar", "signal_id": "done-1", "status": "confirmed"},
                    {"project_id": "ai_radar", "signal_id": "reject-1", "status": "rejected"},
                    {"project_id": "ai_radar", "signal_id": "dismiss-1", "status": "dismissed"},
                    {"project_id": "ai_radar", "signal_id": "watch-1", "status": "watch"},
                    {"project_id": "ai_radar", "signal_id": "action-1", "status": "action"},
                    {"project_id": "ai_radar", "signal_id": "action-done-1", "status": "action_completed"},
                ],
                "updated_at": "2026-04-30T00:00:00Z",
            },
        ):
            pending = projects_route.list_project_takeaway_candidates()
            self.assertEqual([item["signal_id"] for item in pending["items"]], ["pending-1"])

            with_confirmed = projects_route.list_project_takeaway_candidates(include_confirmed=True)
            self.assertEqual(
                {item["signal_id"] for item in with_confirmed["items"]},
                {"pending-1", "done-1"},
            )

            with_closed = projects_route.list_project_takeaway_candidates(
                include_confirmed=True,
                include_closed=True,
            )
            self.assertEqual(
                {item["signal_id"] for item in with_closed["items"]},
                {"pending-1", "done-1", "reject-1", "dismiss-1", "watch-1", "action-1", "action-done-1"},
            )

    def test_project_review_record_summary_counts_outcomes(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            for outcome in ["confirmed", "action", "action_completed", "watch", "rejected", "dismissed"]:
                project_review_record_service.append_project_review_record(
                    project_id="ai_radar",
                    signal_id=f"sig-{outcome}",
                    outcome=outcome,
                    reason=f"{outcome} reason",
                    source_status="candidate",
                    item={
                        "project_name": "AI Radar",
                        "signal_title": f"Signal {outcome}",
                        "verification_metadata": {
                            "verified_insight": {
                                "status": "partially_verified" if outcome in {"watch", "action"} else "verified",
                                "claims": {
                                    "support_summary": {
                                        "unsupported": 1 if outcome == "watch" else 0,
                                        "inferred": 2 if outcome == "watch" else 0,
                                    }
                                },
                                "confidence": {
                                    "score": 0.4 if outcome == "watch" else 0.8,
                                    "label": "low" if outcome == "watch" else "high",
                                },
                                "action_policy": {
                                    "allowed": ["watch_only"],
                                    "blocked": ["low_risk_action_candidate"] if outcome == "watch" else [],
                                },
                            }
                        },
                    },
                )

            summary = project_review_record_service.summarize_project_review_records(project_id="ai_radar")

            self.assertEqual(summary["total_records"], 6)
            self.assertEqual(summary["outcome_counts"]["confirmed"], 1)
            self.assertEqual(summary["actionable_count"], 3)
            self.assertEqual(summary["watch_count"], 1)
            self.assertEqual(summary["rejected_or_dismissed_count"], 2)
            self.assertEqual(summary["verification_status_counts"]["partially_verified"], 2)
            self.assertEqual(summary["unsupported_claim_count"], 1)
            self.assertEqual(summary["inferred_claim_count"], 2)
            self.assertEqual(summary["low_confidence_count"], 1)
            self.assertEqual(summary["records_with_blocked_actions"], 1)
            self.assertEqual(summary["blocked_action_counts"]["low_risk_action_candidate"], 1)
            self.assertEqual(summary["records_with_action_blocked"], 1)
            self.assertEqual(summary["action_outcomes_with_blocked_gate"], 0)
            self.assertEqual(summary["watch_outcomes_with_action_blocked"], 1)
            self.assertEqual(summary["manual_overrides_with_blocked_action"], 0)
            self.assertEqual(summary["gate_conflict_record_count"], 0)
            self.assertEqual(summary["blocked_action_rate"], round(1 / 6, 4))
            self.assertEqual(summary["manual_record_count"], 0)
            self.assertEqual(summary["manual_record_rate"], 0)

    def test_project_review_record_preserves_deep_project_match_review_summary(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            record = project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig_deep_match",
                outcome="watch",
                reason="Project relevance needs deeper review before action.",
                source_status="candidate",
                item={
                    "project_name": "AI Radar",
                    "signal_title": "Agent memory learning loop",
                    "verification_metadata": {
                        "verification_status": "partially_verified",
                        "blocked_downstream_actions": ["low_risk_action_candidate"],
                        "deep_project_match_review": {
                            "required": True,
                            "status": "needed",
                            "posture": "Watch",
                            "review_note": "Compare with AI Radar review loop before Confirm.",
                            "review_note_effect": "review_context_only",
                            "matched_projects": ["AI Radar"],
                            "relevant_modules": ["Project Takeaway Review Loop", "Trajectory / Learning History"],
                            "match_type": "analogous",
                            "evidence_boundary": "internal_judgment",
                            "downstream_posture": "Keep action blocked until human deep match review.",
                        },
                    },
                },
            )

            self.assertTrue(record["deep_project_match_required"])
            self.assertEqual(record["deep_project_match_status"], "needed")
            self.assertEqual(record["deep_project_match_posture"], "Watch")
            self.assertEqual(record["deep_project_match_review_note"], "Compare with AI Radar review loop before Confirm.")
            self.assertEqual(record["deep_project_match_review_note_effect"], "review_context_only")
            self.assertEqual(record["deep_project_match_matched_projects"], ["AI Radar"])
            self.assertEqual(
                record["deep_project_match_relevant_modules"],
                ["Project Takeaway Review Loop", "Trajectory / Learning History"],
            )
            self.assertEqual(record["deep_project_match_match_type"], "analogous")
            self.assertEqual(record["deep_project_match_evidence_boundary"], "internal_judgment")

            events = project_calibration_event_service.list_project_calibration_events(
                project_id="ai_radar",
                signal_id="sig_deep_match",
            )
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0]["deep_project_match_required"])
            self.assertEqual(events[0]["deep_project_match_review_note"], "Compare with AI Radar review loop before Confirm.")
            self.assertEqual(events[0]["deep_project_match_review_note_effect"], "review_context_only")
            self.assertEqual(events[0]["deep_project_match_relevant_modules"], ["Project Takeaway Review Loop", "Trajectory / Learning History"])

    def test_project_review_record_summary_counts_action_gate_conflicts(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig-watch-blocked-action",
                outcome="watch",
                source_status="candidate",
                item={
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"unsupported": 1}},
                            "action_policy": {"allowed": ["watch_only"], "blocked": ["low_risk_action_candidate"]},
                        }
                    }
                },
            )
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig-action-override",
                outcome="action",
                source_status="candidate",
                item={
                    "verification_metadata": {
                        "manual_project_takeaway_override": True,
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"unsupported": 1}},
                            "action_policy": {"allowed": ["watch_only"], "blocked": ["low_risk_action_candidate"]},
                        },
                    }
                },
            )

            summary = project_review_record_service.summarize_project_review_records(project_id="ai_radar")

            self.assertEqual(summary["total_records"], 2)
            self.assertEqual(summary["records_with_blocked_actions"], 2)
            self.assertEqual(summary["records_with_action_blocked"], 2)
            self.assertEqual(summary["watch_outcomes_with_action_blocked"], 1)
            self.assertEqual(summary["action_outcomes_with_blocked_gate"], 1)
            self.assertEqual(summary["manual_overrides_with_blocked_action"], 1)
            self.assertEqual(summary["gate_conflict_record_count"], 1)

    def test_project_review_record_summary_counts_manual_source_records(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="manual_session-123",
                outcome="watch",
                source_status="candidate",
                item={
                    "source_type": "manual_upload",
                    "manual_session_id": "session-123",
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"inferred": 1}},
                            "action_policy": {"allowed": ["watch_only"], "blocked": []},
                        }
                    },
                },
            )
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig-auto",
                outcome="confirmed",
                source_status="candidate",
                item={"verification_metadata": {"verification_status": "verified"}},
            )

            summary = project_review_record_service.summarize_project_review_records(project_id="ai_radar")

            self.assertEqual(summary["total_records"], 2)
            self.assertEqual(summary["source_type_counts"]["manual_upload"], 1)
            self.assertEqual(summary["source_type_counts"]["signal"], 1)
            self.assertEqual(summary["manual_record_count"], 1)
            self.assertEqual(summary["manual_record_rate"], 0.5)
            self.assertEqual(summary["manual_outcome_counts"]["watch"], 1)
            self.assertEqual(summary["manual_actionable_count"], 0)
            self.assertEqual(summary["manual_watch_count"], 1)

    def test_project_review_record_reads_nested_verified_insight_metadata(self):
        record = project_review_record_service.build_project_review_record(
            project_id="ai_radar",
            signal_id="sig-nested-review",
            outcome="watch",
            source_status="candidate",
            item={
                "project_name": "AI Radar",
                "signal_title": "Nested review signal",
                "verification_metadata": {
                    "verified_insight": {
                        "status": "partially_verified",
                        "claims": {
                            "support_summary": {
                                "partially_supported": 1,
                                "unsupported": 1,
                                "inferred": 2,
                            }
                        },
                        "confidence": {"score": 0.55, "label": "medium"},
                        "action_policy": {
                            "allowed": ["reflection_draft", "watch_only"],
                            "blocked": ["project_takeaway_candidate"],
                        },
                    }
                },
            },
        )

        self.assertEqual(record["verification_status"], "partially_verified")
        self.assertEqual(record["unsupported_claim_count"], 1)
        self.assertEqual(record["inferred_claim_count"], 2)
        self.assertEqual(record["confidence_score"], 0.55)
        self.assertEqual(record["confidence_label"], "medium")
        self.assertIn("watch_only", record["allowed_downstream_actions"])
        self.assertIn("project_takeaway_candidate", record["blocked_downstream_actions"])
        self.assertFalse(record["action_eligibility"]["project_takeaway_candidate"]["allowed"])
        self.assertTrue(record["action_eligibility"]["watch_only"]["allowed"])

    def test_project_review_record_preserves_manual_source_metadata(self):
        record = project_review_record_service.build_project_review_record(
            project_id="ai_radar",
            signal_id="manual_session-123",
            outcome="watch",
            source_status="candidate",
            item={
                "source_type": "manual_upload",
                "manual_session_id": "session-123",
                "signal_title": "Manual source",
                "verification_metadata": {
                    "upload_reason": "Compare against roadmap",
                    "intended_use": "Watch for project fit",
                    "cognitive_layer": "L2",
                    "verified_insight": {
                        "status": "partially_verified",
                        "claims": {"support_summary": {"inferred": 1}},
                        "action_policy": {"allowed": ["watch_only"], "blocked": []},
                    }
                },
            },
        )

        self.assertEqual(record["source_type"], "manual_upload")
        self.assertTrue(record["is_manual_source"])
        self.assertEqual(record["manual_session_id"], "session-123")
        self.assertEqual(record["upload_reason"], "Compare against roadmap")
        self.assertEqual(record["intended_use"], "Watch for project fit")
        self.assertEqual(record["cognitive_layer"], "L2")
        self.assertEqual(record["verification_status"], "partially_verified")

    def test_project_review_record_preserves_manual_override_metadata(self):
        record = project_review_record_service.build_project_review_record(
            project_id="ai_radar",
            signal_id="sig-manual-override",
            outcome="watch",
            item={
                "candidate_source": "manual_project_takeaway_override",
                "verification_metadata": {
                    "manual_project_takeaway_override": True,
                    "manual_override_note": "verification gate was bypassed by reviewer",
                    "verification_status": "weakly_supported",
                },
            },
        )

        self.assertTrue(record["manual_project_takeaway_override"])
        self.assertEqual(record["manual_override_note"], "verification gate was bypassed by reviewer")

    def test_project_calibration_event_summary_counts_review_quality_events(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            for event_type, outcome in [
                ("takeaway_accepted", "confirmed"),
                ("takeaway_rejected", "rejected"),
                ("watch_item_created", "watch"),
                ("action_item_created", "action"),
                ("action_item_completed", "action_completed"),
            ]:
                project_calibration_event_service.append_project_calibration_event(
                    event_type=event_type,
                    project_id="ai_radar",
                    signal_id=f"sig-{outcome}",
                    outcome=outcome,
                    source_status="candidate",
                    item={
                        "project_name": "AI Radar",
                        "signal_title": f"Signal {outcome}",
                        "verification_metadata": {
                            "verified_insight": {
                                "status": "weakly_supported" if outcome == "watch" else "verified",
                                "claims": {
                                    "support_summary": {
                                        "unsupported": 1 if outcome == "watch" else 0,
                                        "inferred": 2 if outcome == "watch" else 0,
                                    }
                                },
                                "confidence": {
                                    "score": 0.4 if outcome == "watch" else 0.85,
                                    "label": "low" if outcome == "watch" else "high",
                                },
                                "action_policy": {
                                    "blocked": ["project_takeaway_candidate"] if outcome == "watch" else [],
                                },
                            }
                        },
                    },
                )

            summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_radar")

            self.assertEqual(summary["total_events"], 5)
            self.assertEqual(summary["event_counts"]["takeaway_accepted"], 1)
            self.assertEqual(summary["outcome_counts"]["action_completed"], 1)
            self.assertEqual(summary["actionable_event_count"], 3)
            self.assertEqual(summary["watch_event_count"], 1)
            self.assertEqual(summary["rejected_or_dismissed_event_count"], 1)
            self.assertEqual(summary["candidate_review_event_count"], 4)
            self.assertEqual(summary["candidate_to_actionable_rate"], 0.5)
            self.assertEqual(summary["takeaway_rejection_rate"], 0.25)
            self.assertEqual(summary["verification_status_counts"]["weakly_supported"], 1)
            self.assertEqual(summary["unsupported_claim_count"], 1)
            self.assertEqual(summary["inferred_claim_count"], 2)
            self.assertEqual(summary["low_confidence_event_count"], 1)
            self.assertEqual(summary["events_with_blocked_actions"], 1)
            self.assertEqual(summary["blocked_action_counts"]["project_takeaway_candidate"], 1)
            self.assertEqual(summary["events_with_action_blocked"], 1)
            self.assertEqual(summary["action_events_with_blocked_gate"], 0)
            self.assertEqual(summary["watch_events_with_action_blocked"], 1)
            self.assertEqual(summary["manual_overrides_with_blocked_action"], 0)
            self.assertEqual(summary["gate_conflict_event_count"], 0)
            self.assertEqual(summary["blocked_action_rate"], 0.2)
            self.assertEqual(summary["manual_event_count"], 0)
            self.assertEqual(summary["manual_event_rate"], 0)

    def test_project_calibration_event_summary_counts_action_gate_conflicts(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            project_calibration_event_service.append_project_calibration_event(
                event_type="watch_item_created",
                project_id="ai_radar",
                signal_id="sig-watch-blocked-action",
                outcome="watch",
                item={
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"unsupported": 1}},
                            "action_policy": {"allowed": ["watch_only"], "blocked": ["low_risk_action_candidate"]},
                        }
                    }
                },
            )
            project_calibration_event_service.append_project_calibration_event(
                event_type="action_item_created",
                project_id="ai_radar",
                signal_id="sig-action-override",
                outcome="action",
                item={
                    "verification_metadata": {
                        "manual_project_takeaway_override": True,
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"unsupported": 1}},
                            "action_policy": {"allowed": ["watch_only"], "blocked": ["low_risk_action_candidate"]},
                        },
                    }
                },
            )
            project_calibration_event_service.append_project_calibration_event(
                event_type="review_record_created",
                project_id="ai_radar",
                signal_id="sig-review-record-override",
                outcome="action",
                review_record_id="prv-override",
                item={
                    "verification_metadata": {
                        "manual_project_takeaway_override": True,
                        "verified_insight": {
                            "status": "weakly_supported",
                            "claims": {"support_summary": {"inferred": 1}},
                            "action_policy": {"blocked": ["low_risk_action_candidate"]},
                        },
                    }
                },
            )

            summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_radar")

            self.assertEqual(summary["total_events"], 3)
            self.assertEqual(summary["events_with_blocked_actions"], 3)
            self.assertEqual(summary["events_with_action_blocked"], 3)
            self.assertEqual(summary["watch_events_with_action_blocked"], 1)
            self.assertEqual(summary["action_events_with_blocked_gate"], 1)
            self.assertEqual(summary["manual_overrides_with_blocked_action"], 2)
            self.assertEqual(summary["gate_conflict_event_count"], 2)

    def test_project_calibration_event_reads_nested_verified_insight_metadata(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            event = project_calibration_event_service.append_project_calibration_event(
                event_type="watch_item_created",
                project_id="ai_radar",
                signal_id="sig-nested-event",
                outcome="watch",
                item={
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "weakly_supported",
                            "claims": {"support_summary": {"inferred": 2}},
                            "confidence": {"score": 0.5, "label": "medium"},
                            "action_policy": {"blocked": ["low_risk_action_candidate"]},
                        }
                    }
                },
            )

            self.assertEqual(event["verification_status"], "weakly_supported")
            self.assertEqual(event["inferred_claim_count"], 2)
            self.assertEqual(event["confidence_score"], 0.5)
            self.assertEqual(event["confidence_label"], "medium")
            self.assertIn("low_risk_action_candidate", event["blocked_downstream_actions"])

    def test_project_calibration_event_preserves_manual_source_metadata(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            event = project_calibration_event_service.append_project_calibration_event(
                event_type="watch_item_created",
                project_id="ai_radar",
                signal_id="manual_session-123",
                outcome="watch",
                item={
                    "source_type": "manual_upload",
                    "manual_session_id": "session-123",
                    "verification_metadata": {
                        "upload_reason": "User-selected case study",
                        "intended_use": "Action review",
                        "cognitive_layer": "L3",
                        "verified_insight": {
                            "status": "weakly_supported",
                            "claims": {"support_summary": {"inferred": 1}},
                            "confidence": {"score": 0.4, "label": "low"},
                            "action_policy": {"blocked": ["low_risk_action_candidate"]},
                        }
                    },
                },
            )

            self.assertEqual(event["source_type"], "manual_upload")
            self.assertTrue(event["is_manual_source"])
            self.assertEqual(event["manual_session_id"], "session-123")
            self.assertEqual(event["upload_reason"], "User-selected case study")
            self.assertEqual(event["intended_use"], "Action review")
            self.assertEqual(event["cognitive_layer"], "L3")
            self.assertEqual(event["verification_status"], "weakly_supported")

    def test_project_calibration_event_summary_counts_manual_source_events(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ):
            project_calibration_event_service.append_project_calibration_event(
                event_type="watch_item_created",
                project_id="ai_radar",
                signal_id="manual_session-123",
                outcome="watch",
                item={
                    "source_type": "manual_upload",
                    "manual_session_id": "session-123",
                    "verification_metadata": {"verification_status": "weakly_supported"},
                },
            )
            project_calibration_event_service.append_project_calibration_event(
                event_type="takeaway_accepted",
                project_id="ai_radar",
                signal_id="sig-auto",
                outcome="confirmed",
                item={"verification_metadata": {"verification_status": "verified"}},
            )

            summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_radar")

            self.assertEqual(summary["total_events"], 2)
            self.assertEqual(summary["source_type_counts"]["manual_upload"], 1)
            self.assertEqual(summary["source_type_counts"]["signal"], 1)
            self.assertEqual(summary["manual_event_count"], 1)
            self.assertEqual(summary["manual_event_rate"], 0.5)
            self.assertEqual(summary["manual_event_counts"]["watch_item_created"], 1)
            self.assertEqual(summary["manual_outcome_counts"]["watch"], 1)
            self.assertEqual(summary["manual_actionable_event_count"], 0)
            self.assertEqual(summary["manual_watch_event_count"], 1)

    def test_project_calibration_events_summary_route(self):
        with patch.object(
            projects_route,
            "summarize_project_calibration_events",
            return_value={"total_events": 2},
        ) as summarize:
            result = projects_route.get_project_calibration_events_summary(project_id="ai_radar", signal_id=None)

            self.assertEqual(result["summary"], {"total_events": 2})
            summarize.assert_called_once_with(project_id="ai_radar", signal_id=None)

    def test_project_learning_profile_combines_review_and_calibration_history(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig-watch",
                outcome="watch",
                reason="Needs follow-up before action.",
                source_status="candidate",
                item={
                    "source_type": "manual_upload",
                    "manual_session_id": "manual-1",
                    "signal_title": "Manual source",
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "partially_verified",
                            "claims": {"support_summary": {"unsupported": 1, "inferred": 2}},
                            "confidence": {"score": 0.4, "label": "low"},
                            "action_policy": {
                                "allowed": ["watch_only"],
                                "blocked": ["low_risk_action_candidate"],
                            },
                        }
                    },
                },
            )
            project_review_record_service.append_project_review_record(
                project_id="ai_radar",
                signal_id="sig-confirmed",
                outcome="confirmed",
                reason="Useful project memory.",
                source_status="candidate",
                item={
                    "signal_title": "Confirmed source",
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "verified",
                            "claims": {"support_summary": {"directly_supported": 1}},
                            "confidence": {"score": 0.9, "label": "high"},
                            "action_policy": {"allowed": ["project_takeaway_candidate"], "blocked": []},
                        }
                    },
                },
            )

            profile = project_learning_profile_service.build_project_learning_profile(
                project_id="ai_radar",
                recent_limit=1,
            )

            self.assertEqual(profile["profile_type"], "project_learning_profile")
            self.assertEqual(profile["context_role"], "read_only_project_learning_context")
            self.assertEqual(profile["evidence_boundary"], "review_and_calibration_history_not_external_claim_evidence")
            self.assertEqual(profile["review_summary"]["total_records"], 2)
            self.assertEqual(profile["calibration_summary"]["total_events"], 2)
            self.assertTrue(profile["learning_signals"]["has_actionable_memory"])
            self.assertTrue(profile["learning_signals"]["has_watch_memory"])
            self.assertTrue(profile["learning_signals"]["has_gate_risk"])
            self.assertTrue(profile["learning_signals"]["has_manual_source_learning"])
            self.assertEqual(profile["risk_profile"]["top_blocked_actions"][0]["key"], "low_risk_action_candidate")
            self.assertEqual(profile["source_profile"]["manual_record_count"], 1)
            self.assertEqual(len(profile["recent_review_records"]), 1)
            self.assertEqual(len(profile["recent_calibration_events"]), 1)
            self.assertIn("Review blocked-action", profile["next_focus"][0])

    def test_project_learning_profile_route_returns_read_only_profile(self):
        with patch.object(
            projects_route,
            "build_project_learning_profile",
            return_value={
                "schema_version": 1,
                "profile_type": "project_learning_profile",
                "context_role": "read_only_project_learning_context",
                "scope": {"project_id": "ai_radar", "recent_limit": 3},
            },
        ) as build_profile:
            result = projects_route.get_project_learning_profile(project_id="ai_radar", recent_limit=3)

            self.assertEqual(result["message"], "project learning profile loaded successfully")
            self.assertEqual(result["profile_type"], "project_learning_profile")
            self.assertEqual(result["context_role"], "read_only_project_learning_context")
            build_profile.assert_called_once_with(project_id="ai_radar", recent_limit=3)

    def test_rejected_learning_buffer_route_returns_bounded_caution_context(self):
        with patch.object(
            projects_route,
            "build_rejected_learning_buffer",
            return_value={
                "schema_version": 1,
                "context_role": "bounded_caution",
                "source": "project_review_records",
                "evidence_boundary": "not_factual_evidence",
                "project_id": "ai_radar",
                "signal_id": "sig-1",
                "limit": 3,
                "item_count": 1,
                "items": [{"record_id": "prv-1", "outcome": "rejected"}],
            },
        ) as build_buffer:
            result = projects_route.get_project_rejected_learning_buffer(
                project_id="ai_radar",
                signal_id="sig-1",
                limit=3,
            )

            self.assertEqual(result["message"], "project rejected learning buffer loaded successfully")
            self.assertEqual(result["context_role"], "bounded_caution")
            self.assertEqual(result["evidence_boundary"], "not_factual_evidence")
            self.assertEqual(result["items"], [{"record_id": "prv-1", "outcome": "rejected"}])
            build_buffer.assert_called_once_with(project_id="ai_radar", signal_id="sig-1", limit=3)

    def test_project_trajectory_events_route_combines_review_and_calibration_events(self):
        with patch.object(
            projects_route,
            "list_project_review_records",
            return_value=[
                {
                    "id": "prv_manual",
                    "project_id": "ai_radar",
                    "project_name": "AI Radar",
                    "signal_id": "manual_123",
                    "signal_title": "Manual signal",
                    "outcome": "watch",
                    "reason": "Track this user-selected material.",
                    "source_type": "manual_upload",
                    "manual_session_id": "123",
                    "is_manual_source": True,
                    "upload_reason": "Compare a user-selected case study",
                    "intended_use": "Watch against project direction",
                    "cognitive_layer": "L3",
                    "verification_status": "partially_verified",
                    "confidence_label": "medium",
                    "confidence_score": 0.61,
                    "unsupported_claim_count": 1,
                    "inferred_claim_count": 2,
                    "blocked_downstream_actions": ["project_takeaway_candidate"],
                    "reviewed_at": "2026-05-04T12:00:00+00:00",
                }
            ],
        ) as list_records, patch.object(
            projects_route,
            "list_project_calibration_events",
            return_value=[
                {
                    "id": "pce_signal",
                    "event_type": "takeaway_accepted",
                    "project_id": "ai_radar",
                    "signal_id": "sig_1",
                    "source_type": "signal",
                    "verification_status": "verified",
                    "created_at": "2026-05-04T13:00:00+00:00",
                }
            ],
        ) as list_events:
            result = projects_route.get_project_trajectory_events(project_id="ai_radar", signal_id=None)

            self.assertEqual(result["count"], 2)
            self.assertEqual(result["items"][0]["event_kind"], "calibration")
            self.assertEqual(result["items"][0]["outcome"], "takeaway_accepted")
            self.assertEqual(result["items"][0]["risk_level"], "low")
            self.assertEqual(result["items"][0]["trajectory_signal_type"], "calibration_learning")
            self.assertEqual(result["items"][1]["event_kind"], "review")
            self.assertEqual(result["items"][1]["is_manual_source"], True)
            self.assertEqual(result["items"][1]["manual_session_id"], "123")
            self.assertEqual(result["items"][1]["upload_reason"], "Compare a user-selected case study")
            self.assertEqual(result["items"][1]["intended_use"], "Watch against project direction")
            self.assertEqual(result["items"][1]["cognitive_layer"], "L3")
            self.assertEqual(result["items"][1]["unsupported_claim_count"], 1)
            self.assertEqual(result["items"][1]["blocked_downstream_actions"], ["project_takeaway_candidate"])
            self.assertEqual(result["items"][1]["risk_level"], "high")
            self.assertEqual(result["items"][1]["trajectory_signal_type"], "manual_judgment")
            self.assertEqual(result["summary"]["total_events"], 2)
            self.assertEqual(result["summary"]["manual_count"], 1)
            self.assertEqual(result["summary"]["risk_count"], 1)
            self.assertEqual(result["summary"]["risk_mix"], {"low": 1, "high": 1})
            self.assertEqual(result["summary"]["signal_type_mix"], {"calibration_learning": 1, "manual_judgment": 1})
            self.assertEqual(result["summary"]["event_kind_mix"], {"calibration": 1, "review": 1})
            self.assertEqual(result["summary"]["source_type_mix"], {"signal": 1, "manual_upload": 1})
            self.assertEqual(
                result["summary"]["manual_intent_summary"]["upload_reason_mix"],
                [{"value": "Compare a user-selected case study", "count": 1}],
            )
            self.assertEqual(
                result["summary"]["manual_intent_summary"]["intended_use_mix"],
                [{"value": "Watch against project direction", "count": 1}],
            )
            self.assertEqual(
                result["summary"]["manual_intent_summary"]["cognitive_layer_mix"],
                [{"value": "L3", "count": 1}],
            )
            self.assertEqual(result["summary"]["project_mix"][0]["project_id"], "ai_radar")
            self.assertEqual(result["summary"]["project_mix"][0]["event_count"], 2)
            self.assertEqual(result["summary"]["project_mix"][0]["manual_count"], 1)
            self.assertEqual(result["summary"]["project_mix"][0]["risk_count"], 1)
            self.assertEqual(result["summary"]["project_mix"][0]["watch_count"], 1)
            self.assertEqual(result["summary"]["project_mix"][0]["action_count"], 0)
            list_records.assert_called_once_with(project_id="ai_radar", signal_id=None)
            list_events.assert_called_once_with(project_id="ai_radar", signal_id=None)

    def test_project_trajectory_events_route_filters_by_derived_fields(self):
        with patch.object(
            projects_route,
            "list_project_review_records",
            return_value=[
                {
                    "id": "prv_manual",
                    "project_id": "ai_radar",
                    "signal_id": "manual_123",
                    "outcome": "watch",
                    "source_type": "manual_upload",
                    "is_manual_source": True,
                    "verification_status": "partially_verified",
                    "unsupported_claim_count": 1,
                    "reviewed_at": "2026-05-04T12:00:00+00:00",
                }
            ],
        ), patch.object(
            projects_route,
            "list_project_calibration_events",
            return_value=[
                {
                    "id": "pce_signal",
                    "event_type": "takeaway_accepted",
                    "project_id": "ai_radar",
                    "signal_id": "sig_1",
                    "source_type": "signal",
                    "verification_status": "verified",
                    "created_at": "2026-05-04T13:00:00+00:00",
                }
            ],
        ):
            result = projects_route.get_project_trajectory_events(
                project_id="ai_radar",
                signal_id=None,
                event_kind="review",
                risk_level="high",
                trajectory_signal_type="manual_judgment",
                source_type="manual_upload",
            )

            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"][0]["id"], "prv_manual")
            self.assertEqual(result["summary"]["risk_mix"], {"high": 1})
            self.assertEqual(result["summary"]["signal_type_mix"], {"manual_judgment": 1})

            risk_result = projects_route.get_project_trajectory_events(
                project_id="ai_radar",
                signal_id=None,
                event_kind=None,
                risk_level="risk",
                trajectory_signal_type=None,
                source_type=None,
            )
            self.assertEqual(risk_result["count"], 1)
            self.assertEqual(risk_result["items"][0]["id"], "prv_manual")

    def test_project_calibration_backfill_is_idempotent(self):
        with workspace_temp_dir() as temp_dir, patch.object(
            project_calibration_event_service,
            "DATA_DIR",
            temp_dir / "project_calibration_events",
        ), patch.object(
            project_calibration_event_service,
            "INDEX_PATH",
            temp_dir / "project_calibration_events" / "index.json",
        ), patch.object(
            project_review_record_service,
            "DATA_DIR",
            temp_dir / "project_review_records",
        ), patch.object(
            project_review_record_service,
            "INDEX_PATH",
            temp_dir / "project_review_records" / "index.json",
        ):
            review_record = project_review_record_service.save_project_review_record(
                {
                    "id": "prv_backfill_1",
                    "record_type": "project_takeaway_review",
                    "project_id": "ai_radar",
                    "project_name": "AI Radar",
                    "signal_id": "sig-backfill",
                    "signal_title": "Backfill signal",
                    "outcome": "confirmed",
                    "reason": "Confirmed during earlier review.",
                    "source_status": "candidate",
                    "verification_status": "partially_verified",
                    "reviewed_at": "2026-05-02T23:02:08+00:00",
                    "created_at": "2026-05-02T23:02:08+00:00",
                    "updated_at": "2026-05-02T23:02:08+00:00",
                }
            )

            first = project_calibration_event_service.backfill_project_calibration_events_from_review_records(
                [review_record]
            )
            second = project_calibration_event_service.backfill_project_calibration_events_from_review_records(
                [review_record]
            )

            self.assertEqual(first["created_count"], 2)
            self.assertEqual(second["created_count"], 0)
            summary = project_calibration_event_service.summarize_project_calibration_events(project_id="ai_radar")
            self.assertEqual(summary["total_events"], 2)
            self.assertEqual(summary["event_counts"]["review_record_created"], 1)
            self.assertEqual(summary["event_counts"]["takeaway_accepted"], 1)
            self.assertEqual(summary["outcome_counts"]["confirmed"], 1)

    def test_project_calibration_backfill_route_uses_review_records(self):
        with patch.object(
            projects_route,
            "list_project_review_records",
            return_value=[{"id": "prv_1", "project_id": "ai_radar", "signal_id": "sig-1", "outcome": "watch"}],
        ) as list_records, patch.object(
            projects_route,
            "backfill_project_calibration_events_from_review_records",
            return_value={"created_count": 2, "record_count": 1},
        ) as backfill:
            result = projects_route.backfill_project_calibration_events(project_id="ai_radar", signal_id=None)

            self.assertEqual(result["created_count"], 2)
            list_records.assert_called_once_with(project_id="ai_radar", signal_id=None)
            backfill.assert_called_once_with(
                [{"id": "prv_1", "project_id": "ai_radar", "signal_id": "sig-1", "outcome": "watch"}]
            )


if __name__ == "__main__":
    unittest.main()
