import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_project_takeaway_claim_dependencies import (  # noqa: E402
    ClaimDependencyAuditFilters,
    analyze_project_takeaway_claim_dependencies,
    build_phase2_readiness_summary,
    build_phase2_schema_inputs,
    summarize_rows,
)


class ProjectTakeawayClaimDependencyAuditTests(unittest.TestCase):
    def test_embedded_claim_items_with_ids_are_linked(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-1",
                    "status": "candidate",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verified_insight": {
                            "status": "verified",
                            "claims": {
                                "items": [
                                    {
                                        "claim_id": "claim_1",
                                        "support_level": "directly_supported",
                                    },
                                    {
                                        "claim_id": "claim_2",
                                        "support_level": "inferred",
                                    },
                                ],
                            },
                        },
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].claim_link_status, "linked_claims_present")
        self.assertEqual(rows[0].claim_ids, ["sig-1:claim_1", "sig-1:claim_2"])
        self.assertEqual(rows[0].linked_claim_id_count, 2)
        self.assertEqual(rows[0].weak_or_negative_claim_count, 1)
        self.assertEqual(rows[0].support_summary["directly_supported"], 1)
        self.assertEqual(rows[0].support_summary["inferred"], 1)

    def test_aggregate_claim_summary_without_ids_is_summary_only(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-summary",
                    "status": "confirmed",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verification_status": "partially_verified",
                        "claim_support_summary": {
                            "partially_supported": 2,
                            "unsupported": 1,
                        },
                    },
                }
            ],
            project_id="ai_radar",
        )

        self.assertEqual(rows[0].claim_link_status, "claim_summary_only")
        self.assertEqual(rows[0].claim_count, 3)
        self.assertEqual(rows[0].linked_claim_id_count, 0)
        self.assertEqual(rows[0].weak_or_negative_claim_count, 1)

    def test_missing_claim_context_is_reported_without_gap_semantics(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "legacy-1",
                    "status": "new",
                    "candidate_source": "signal_completion",
                    "verification_metadata": {},
                }
            ],
            project_id="ai_radar",
        )

        self.assertEqual(rows[0].claim_link_status, "no_claim_dependency_data")
        self.assertEqual(rows[0].claim_count, 0)
        self.assertEqual(rows[0].weak_or_negative_claim_count, 0)

    def test_summary_counts_linkability_and_support_levels(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-1",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "contradicted"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-2",
                    "verification_metadata": {
                        "claim_support_summary": {"directly_supported": 1},
                    },
                },
                {
                    "signal_id": "sig-3",
                    "verification_metadata": {},
                },
            ],
            project_id="ai_radar",
        )

        summary = summarize_rows(rows)

        self.assertEqual(summary["record_count"], 3)
        self.assertEqual(summary["link_status_counts"]["linked_claims_present"], 1)
        self.assertEqual(summary["link_status_counts"]["claim_summary_only"], 1)
        self.assertEqual(summary["link_status_counts"]["no_claim_dependency_data"], 1)
        self.assertEqual(summary["linked_claim_id_count"], 1)
        self.assertEqual(summary["weak_or_negative_claim_count"], 1)
        self.assertEqual(
            summary["breakdowns"]["by_candidate_source"]["(missing)"]["linked_record_coverage"],
            0.3333,
        )
        self.assertEqual(
            summary["breakdowns"]["by_status"]["(missing)"]["no_dependency_record_count"],
            1,
        )
        self.assertEqual(
            summary["breakdowns"]["by_project_id"]["ai_radar"]["record_count"],
            3,
        )

    def test_summary_breakdowns_preserve_source_and_status_shape(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-linked",
                    "status": "candidate",
                    "candidate_source": "manual_project_takeaway_override",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "inferred"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-summary",
                    "status": "candidate",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "claim_support_summary": {"unsupported": 2},
                    },
                },
                {
                    "signal_id": "sig-empty",
                    "status": "watch",
                    "candidate_source": "knowledge_convergence",
                    "verification_metadata": {},
                },
            ],
            project_id="ai_radar",
        )

        breakdowns = summarize_rows(rows)["breakdowns"]

        self.assertEqual(
            breakdowns["by_candidate_source"]["manual_project_takeaway_override"]["linked_record_count"],
            1,
        )
        self.assertEqual(
            breakdowns["by_candidate_source"]["verified_insight"]["summary_only_record_count"],
            1,
        )
        self.assertEqual(
            breakdowns["by_candidate_source"]["knowledge_convergence"]["no_dependency_record_count"],
            1,
        )
        self.assertEqual(breakdowns["by_status"]["candidate"]["record_count"], 2)
        self.assertEqual(breakdowns["by_status"]["candidate"]["linked_record_coverage"], 0.5)
        self.assertEqual(breakdowns["by_status"]["watch"]["no_dependency_record_count"], 1)
        self.assertEqual(breakdowns["by_project_id"]["ai_radar"]["weak_or_negative_claim_count"], 3)

    def test_filters_limit_project_source_status_and_reviewable_records(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-candidate",
                    "status": "candidate",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "directly_supported"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-new",
                    "status": "new",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "claim_support_summary": {"directly_supported": 1},
                    },
                },
                {
                    "signal_id": "sig-knowledge",
                    "status": "candidate",
                    "candidate_source": "knowledge_convergence",
                    "verification_metadata": {},
                },
            ],
            project_id="ai_radar",
            filters=ClaimDependencyAuditFilters(
                project_ids={"ai_radar"},
                candidate_sources={"verified_insight"},
                statuses={"candidate", "new"},
                only_reviewable=True,
            ),
        )

        self.assertEqual([row.signal_id for row in rows], ["sig-candidate"])

    def test_phase2_readiness_requires_trusted_sample_before_schema_work(self):
        readiness = build_phase2_readiness_summary([])

        self.assertEqual(readiness["readiness"], "needs_trusted_sample")
        self.assertEqual(readiness["decision_boundary"], "architecture_readiness_only")
        self.assertIn("factual_quality_judgment", readiness["not_for"])

    def test_phase2_readiness_flags_partial_link_coverage(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-linked",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "directly_supported"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-summary",
                    "verification_metadata": {
                        "claim_support_summary": {"directly_supported": 1},
                    },
                },
            ],
            project_id="ai_radar",
        )

        readiness = build_phase2_readiness_summary(rows)

        self.assertEqual(readiness["readiness"], "needs_backfill_or_source_boundary_design")
        self.assertEqual(readiness["selected_record_count"], 2)
        self.assertEqual(readiness["linked_record_count"], 1)
        self.assertEqual(readiness["summary_only_record_count"], 1)
        self.assertEqual(readiness["linked_record_coverage"], 0.5)

    def test_phase2_schema_inputs_classify_candidate_sources(self):
        rows = analyze_project_takeaway_claim_dependencies(
            [
                {
                    "signal_id": "sig-linked",
                    "candidate_source": "confirmed_final_takeaway",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "directly_supported"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-summary",
                    "candidate_source": "verified_insight",
                    "verification_metadata": {
                        "claim_support_summary": {"directly_supported": 1},
                    },
                },
                {
                    "signal_id": "sig-empty",
                    "candidate_source": "knowledge_convergence",
                    "verification_metadata": {},
                },
                {
                    "signal_id": "sig-mixed-linked",
                    "candidate_source": "signal_completion",
                    "verification_metadata": {
                        "verified_insight": {
                            "claims": {
                                "items": [
                                    {"claim_id": "claim_1", "support_level": "inferred"},
                                ],
                            },
                        },
                    },
                },
                {
                    "signal_id": "sig-mixed-empty",
                    "candidate_source": "signal_completion",
                    "verification_metadata": {},
                },
            ],
            project_id="ai_radar",
        )

        schema_inputs = build_phase2_schema_inputs(rows)

        self.assertEqual(schema_inputs["decision_boundary"], "schema_design_input_only")
        self.assertIn("schema_migration_approval", schema_inputs["not_for"])
        self.assertEqual(schema_inputs["eligible_candidate_sources"], ["confirmed_final_takeaway"])
        self.assertEqual(schema_inputs["backfill_or_summary_only_candidate_sources"], ["verified_insight"])
        self.assertEqual(schema_inputs["dependency_unknown_candidate_sources"], ["knowledge_convergence"])
        self.assertEqual(schema_inputs["mixed_shape_candidate_sources"], ["signal_completion"])
        self.assertEqual(
            schema_inputs["candidate_source_policies"]["signal_completion"]["policy"],
            "requires_source_specific_split_policy",
        )


if __name__ == "__main__":
    unittest.main()
