import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_project_takeaway_a1_gaps import (  # noqa: E402
    analyze_project_takeaway_items,
    apply_classification_overrides,
    build_classification_decision_queue,
    build_classification_queue,
    build_repair_proposal,
    summarize_project_takeaway_gaps,
)


class ProjectTakeawayA1GapDetectorTests(unittest.TestCase):
    def test_verified_insight_candidate_with_allowed_gate_has_no_gap(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-verified",
                    "status": "candidate",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "verified",
                        "claim_support_summary": {"supported": 1, "unsupported": 0, "contradicted": 0},
                        "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
                        "blocked_downstream_actions": [],
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertEqual(gaps, [])

    def test_signal_completion_without_verification_context_is_flagged(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-legacy",
                    "status": "new",
                    "candidate_source": "signal_completion",
                    "verification_metadata": {},
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("missing_verification_context", {gap.code for gap in gaps})
        self.assertIn("signal_completion_not_normalized", {gap.code for gap in gaps})

    def test_unverified_manual_entry_must_not_allow_project_takeaway(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "manual-1",
                    "status": "candidate",
                    "candidate_source": "unverified_manual_entry",
                    "verification_metadata": {
                        "verification_status": "unverified_manual_entry",
                        "verification_required": True,
                    },
                    "action_eligibility": {
                        "project_takeaway_candidate": {"allowed": True, "reason": "bad legacy state"},
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("unverified_manual_allows_project_takeaway", {gap.code for gap in gaps})

    def test_unverified_manual_entry_must_not_carry_clean_claim_support(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "manual-claim-support",
                    "status": "candidate",
                    "candidate_source": "unverified_manual_entry",
                    "verification_metadata": {
                        "verification_status": "unverified_manual_entry",
                        "verification_required": True,
                        "claim_support_summary": {"directly_supported": 1},
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("unverified_manual_has_claim_support", {gap.code for gap in gaps})

    def test_unverified_manual_entry_must_not_embed_verified_insight_status(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "manual-verified-status",
                    "status": "candidate",
                    "candidate_source": "unverified_manual_entry",
                    "verification_metadata": {
                        "verification_status": "unverified_manual_entry",
                        "verification_required": True,
                        "verified_insight": {"status": "verified"},
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("unverified_manual_has_verified_insight_status", {gap.code for gap in gaps})

    def test_knowledge_convergence_must_block_low_risk_action(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "knowledge-1",
                    "status": "candidate",
                    "candidate_source": "knowledge_convergence",
                    "verification_metadata": {
                        "knowledge_convergence": True,
                        "verification_status": "knowledge_convergence_review_candidate",
                        "allowed_downstream_actions": ["project_takeaway_candidate"],
                        "blocked_downstream_actions": [],
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("knowledge_convergence_action_not_blocked", {gap.code for gap in gaps})
        self.assertEqual({gap.data_bucket for gap in gaps}, {"production_like"})

    def test_explicit_local_test_scope_is_separated_from_production_like_gaps(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-local-test-action",
                    "status": "action",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "partially_verified",
                        "blocked_downstream_actions": ["low_risk_action_candidate"],
                        "manual_override_scope": "local_test_data_only",
                    },
                }
            ],
            project_id="ai_radar",
        )

        gap = next(gap for gap in gaps if gap.code == "blocked_low_risk_action_stored_as_action")
        self.assertEqual(gap.data_scope, "local_test_data_only")
        self.assertEqual(gap.data_bucket, "test_or_legacy")
        self.assertEqual(gap.severity, "error")
        self.assertEqual(gap.report_severity, "info")

    def test_unclassified_legacy_review_record_requires_classification(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-legacy-confirmed",
                    "status": "confirmed",
                    "verification_metadata": {},
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("missing_candidate_source", {gap.code for gap in gaps})
        self.assertIn("missing_verification_context", {gap.code for gap in gaps})
        self.assertEqual({gap.data_bucket for gap in gaps}, {"needs_classification"})

    def test_summary_exposes_metadata_cleanup_readiness(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-legacy-confirmed",
                    "status": "confirmed",
                    "verification_metadata": {},
                },
                {
                    "signal_id": "sig-clean",
                    "status": "candidate",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "verified",
                        "claim_support_summary": {"supported": 1},
                        "allowed_downstream_actions": ["project_takeaway_candidate"],
                        "blocked_downstream_actions": [],
                    },
                },
            ],
            project_id="ai_radar",
        )

        summary = summarize_project_takeaway_gaps(gaps)

        self.assertEqual(summary["metadata_cleanup_counts"]["missing_candidate_source"], 1)
        self.assertEqual(summary["metadata_cleanup_counts"]["missing_verification_context"], 1)
        self.assertEqual(summary["needs_classification_record_count"], 1)
        self.assertFalse(summary["advisory_cleanup_ready"])

    def test_classification_queue_groups_needs_classification_records(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-confirmed",
                    "status": "confirmed",
                    "verification_metadata": {},
                },
                {
                    "signal_id": "sig-new",
                    "status": "new",
                    "verification_metadata": {},
                },
                {
                    "signal_id": "sig-production-like",
                    "status": "candidate",
                    "candidate_source": "knowledge_convergence",
                    "verification_metadata": {
                        "knowledge_convergence": True,
                        "verification_status": "knowledge_convergence_review_candidate",
                        "allowed_downstream_actions": ["project_takeaway_candidate"],
                        "blocked_downstream_actions": [],
                    },
                },
            ],
            project_id="ai_radar",
        )

        rows = build_classification_queue(gaps)

        self.assertEqual([row["signal_id"] for row in rows], ["sig-confirmed", "sig-new"])
        rows_by_signal = {row["signal_id"]: row for row in rows}
        self.assertEqual(rows_by_signal["sig-confirmed"]["queue_id"], "ai_radar:sig-confirmed")
        self.assertEqual(rows_by_signal["sig-confirmed"]["decision_group_id"], "sig-confirmed")
        self.assertEqual(rows_by_signal["sig-confirmed"]["priority"], "p1_reviewed_record")
        self.assertEqual(rows_by_signal["sig-confirmed"]["classification_hint"], "reviewed_record_missing_metadata")
        self.assertEqual(
            rows_by_signal["sig-confirmed"]["suggested_classification"],
            "legacy_reviewed_record_requires_human_label",
        )
        self.assertEqual(
            rows_by_signal["sig-confirmed"]["repair_policy"],
            "do_not_auto_repair_without_classification",
        )
        self.assertEqual(rows_by_signal["sig-confirmed"]["recommended_next_action"], "human_classify_before_repair")
        self.assertEqual(rows_by_signal["sig-new"]["priority"], "p2_new_record")
        self.assertEqual(rows_by_signal["sig-new"]["classification_hint"], "new_record_missing_metadata")
        self.assertEqual(
            rows_by_signal["sig-new"]["recommended_next_action"],
            "classify_as_legacy_or_backlog_before_repair",
        )

    def test_classification_decision_queue_groups_same_signal_across_projects(self):
        gaps = []
        for project_id, status in [("ai_radar", "confirmed"), ("glap", "new"), ("trajectory_memory", "new")]:
            gaps.extend(
                analyze_project_takeaway_items(
                    [
                        {
                            "signal_id": "sig-shared",
                            "signal_title": "Shared legacy signal",
                            "project_name": project_id,
                            "status": status,
                            "verification_metadata": {},
                        }
                    ],
                    project_id=project_id,
                )
            )

        rows = build_classification_decision_queue(gaps)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision_group_id"], "sig-shared")
        self.assertEqual(rows[0]["record_count"], 3)
        self.assertEqual(rows[0]["priority"], "p1_reviewed_record")
        self.assertEqual(rows[0]["project_ids"], ["ai_radar", "glap", "trajectory_memory"])
        self.assertEqual(
            rows[0]["suggested_classifications"],
            [
                "legacy_backlog_or_test_record_requires_human_label",
                "legacy_reviewed_record_requires_human_label",
            ],
        )

    def test_human_test_override_moves_classification_gaps_to_test_bucket(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-test-data",
                    "signal_title": "Fixture signal",
                    "status": "confirmed",
                    "verification_metadata": {},
                }
            ],
            project_id="ai_radar",
        )

        overridden = apply_classification_overrides(
            gaps,
            {
                "sig-test-data": {
                    "classification": "test_or_legacy",
                    "data_scope": "test_data",
                }
            },
        )
        summary = summarize_project_takeaway_gaps(overridden)

        self.assertEqual({gap.data_bucket for gap in overridden}, {"test_or_legacy"})
        self.assertEqual({gap.report_severity for gap in overridden}, {"info", "warning"})
        self.assertEqual(summary["bucket_counts"], {"test_or_legacy": 2})
        self.assertEqual(summary["needs_classification_record_count"], 0)
        self.assertTrue(summary["advisory_cleanup_ready"])

    def test_repair_proposal_is_dry_run_for_test_or_legacy_records(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-test-data",
                    "signal_title": "Fixture signal",
                    "project_name": "AI Radar",
                    "status": "confirmed",
                    "verification_metadata": {},
                }
            ],
            project_id="ai_radar",
        )
        overridden = apply_classification_overrides(
            gaps,
            {"sig-test-data": {"classification": "test_or_legacy", "data_scope": "test_data"}},
        )

        proposals = build_repair_proposal(overridden)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["write_action"], "dry_run_only")
        self.assertEqual(proposals[0]["proposed_metadata_patch"]["a1_classification"], "test_or_legacy")
        self.assertEqual(proposals[0]["proposed_metadata_patch"]["record_scope"], "legacy_fixture_or_demo_data")
        self.assertIn("Do not add verified_insight", proposals[0]["safety_note"])

    def test_manual_override_requires_note_and_expected_outcome(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-override-missing-audit",
                    "status": "confirmed",
                    "candidate_source": "manual_project_takeaway_override",
                    "verification_metadata": {
                        "manual_project_takeaway_override": True,
                        "verification_status": "weakly_supported",
                        "blocked_downstream_actions": ["project_takeaway_candidate"],
                    },
                }
            ],
            project_id="ai_radar",
        )

        codes = {gap.code for gap in gaps}
        self.assertIn("manual_override_missing_note", codes)
        self.assertIn("manual_override_missing_expected_outcome", codes)

    def test_manual_override_can_hold_blocked_action_status(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-override",
                    "status": "action",
                    "candidate_source": "manual_project_takeaway_override",
                    "verification_metadata": {
                        "manual_project_takeaway_override": True,
                        "manual_override_note": "Human accepted the risk.",
                        "manual_override_expected_outcome": "One scoped follow-up.",
                        "verification_status": "weakly_supported",
                        "blocked_downstream_actions": ["low_risk_action_candidate"],
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertEqual(gaps, [])

    def test_action_completed_must_not_be_review_outcome(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-action-completed",
                    "status": "action_completed",
                    "review_outcome": "action_completed",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "verified",
                        "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
                        "blocked_downstream_actions": [],
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertIn("action_completed_stored_as_review_outcome", {gap.code for gap in gaps})

    def test_action_completed_status_can_keep_action_review_outcome(self):
        gaps = analyze_project_takeaway_items(
            [
                {
                    "signal_id": "sig-action-completed-clean",
                    "status": "action_completed",
                    "review_outcome": "action",
                    "action_state": "completed",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "verified",
                        "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
                        "blocked_downstream_actions": [],
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertNotIn("action_completed_stored_as_review_outcome", {gap.code for gap in gaps})


if __name__ == "__main__":
    unittest.main()
