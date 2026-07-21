import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.claim_verification_service import verify_claims_against_evidence  # noqa: E402


def evidence_item(
    content,
    *,
    evidence_id="ev_1",
    provenance="source_excerpt",
    traceable=True,
    source_id="sig_1",
    source_field="summary",
    metadata=None,
):
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_field": source_field,
        "content": content,
        "provenance": provenance,
        "traceable": traceable,
        "metadata": metadata or {},
    }


class ClaimVerificationServiceTests(unittest.TestCase):
    def test_direct_descriptive_claim_can_be_supported_by_primary_evidence(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The repo added enterprise deployment docs.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("The repo added enterprise deployment docs. Setup guidance followed.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "directly_supported")
        self.assertEqual(result[0]["evidence_refs"], ["ev_1"])
        self.assertEqual(result[0]["origin"], "quoted")
        self.assertEqual(result[0]["source_span"]["evidence_id"], "ev_1")
        self.assertEqual(result[0]["source_span"]["source_id"], "sig_1")
        self.assertEqual(
            result[0]["source_span"]["char_end"] - result[0]["source_span"]["char_start"],
            len("The repo added enterprise deployment docs."),
        )

    def test_trend_claim_with_single_source_is_downgraded(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "This signal shows a broader agent infrastructure trend.",
                    "claim_type": "trend",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("This signal shows a broader agent infrastructure trend.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "partially_supported")
        self.assertIn("single_source_trend_claim_downgraded", result[0]["verification_notes"])
        self.assertEqual(result[0]["origin"], "quoted")

    def test_token_overlap_without_source_span_is_not_direct_support(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The product launch proves durable memory is now solved.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("Product launch notes discuss durable memory integrations.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "inferred")
        self.assertEqual(result[0]["origin"], "inferred")
        self.assertIsNone(result[0]["source_span"])
        self.assertIn("matched_evidence_without_source_span", result[0]["verification_notes"])

    def test_strong_source_excerpt_paraphrase_gets_supporting_span_without_direct_support(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": (
                        "SkillOS separates skill execution from skill curation by pairing "
                        "a frozen executor with a trainable curator."
                    ),
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "SkillOS pairs a frozen agent executor that retrieves and applies skills "
                        "with a trainable skill curator that performs insert, update, and delete "
                        "operations on a markdown skill repository.",
                        source_field="source_excerpt",
                    )
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "partially_supported")
        self.assertEqual(result[0]["origin"], "grounded_excerpt")
        self.assertEqual(result[0]["source_span"]["match_type"], "paraphrase_window")
        self.assertGreaterEqual(result[0]["source_span"]["matched_token_count"], 4)
        self.assertIn("paraphrase_grounded_to_source_span", result[0]["verification_notes"])
        self.assertNotIn("matched_evidence_without_source_span", result[0]["verification_notes"])

    def test_predictive_claim_is_not_directly_supported(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "This model will reshape enterprise agent workflows.",
                    "claim_type": "predictive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("The model supports enterprise agent workflows.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "inferred")
        self.assertIn("predictive_claim_capped", result[0]["verification_notes"])

    def test_llm_generated_summary_cannot_directly_support_claim(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The integration improves persistent memory.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "The integration improves persistent memory.",
                        provenance="llm_generated",
                    )
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "inferred")
        self.assertIn("only_non_primary_evidence_matched", result[0]["verification_notes"])

    def test_project_relevance_claim_is_contextual_not_directly_supported(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "This approach is relevant to the AI Radar project.",
                    "claim_type": "descriptive",
                    "source_field": "relevance_to_projects",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("This approach is relevant to the AI Radar project.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "partially_supported")
        self.assertIn(
            "relevance_to_projects_requires_contextual_review",
            result[0]["verification_notes"],
        )

    def test_career_relevance_claim_is_contextual_not_directly_supported(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "This strengthens the user's AI systems career positioning.",
                    "claim_type": "descriptive",
                    "source_field": "relevance_to_career",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("This strengthens the user's AI systems career positioning.")
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "partially_supported")
        self.assertIn(
            "relevance_to_career_requires_contextual_review",
            result[0]["verification_notes"],
        )

    def test_presentation_fidelity_flags_peer_review_claim_over_source_limits(self):
        source_limits_metadata = {
            "source_stated_limits_status": "limits_present",
            "source_stated_limits": [
                {
                    "text": (
                        "The review is an in-framework simulated review, not external peer review "
                        "or an external quality claim; hallucinated citations are known to exist."
                    ),
                    "source_field": "source_excerpt",
                    "source_span": None,
                    "limit_type": None,
                }
            ],
            "source_stated_confidence": {
                "raw_text": "Hallucinated citations are known to exist.",
                "normalized_label": "limited",
            },
        }

        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_deli_fixture",
                    "claim_text": "Deli AutoResearch received peer review 8.5/10.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "Deli AutoResearch reports an in-framework simulated review score of 8.5/10.",
                        metadata=source_limits_metadata,
                    )
                ]
            },
        )

        self.assertEqual(
            result[0]["presentation_fidelity"]["limits_state"],
            "limits_present_and_exceeded",
        )
        self.assertIn("presentation_fidelity_limit_exceeded", result[0]["verification_notes"])
        self.assertIn(
            "peer_review_claim_exceeds_simulated_review_limit",
            result[0]["presentation_fidelity"]["reason_codes"],
        )
        self.assertTrue(result[0]["presentation_fidelity"]["source_stated_confidence_present"])

    def test_presentation_fidelity_preserves_claim_that_carries_source_limits(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The source reports an in-framework simulated review.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "The source reports an in-framework simulated review.",
                        metadata={
                            "source_stated_limits_status": "limits_present",
                            "source_stated_limits": [
                                {
                                    "text": "This is an in-framework simulated review, not external peer review.",
                                    "source_field": "source_excerpt",
                                    "source_span": None,
                                    "limit_type": None,
                                }
                            ],
                        },
                    )
                ]
            },
        )

        self.assertEqual(
            result[0]["presentation_fidelity"]["limits_state"],
            "limits_present_and_preserved",
        )
        self.assertNotIn("presentation_fidelity_limit_exceeded", result[0]["verification_notes"])

    def test_presentation_fidelity_absent_limits_is_coverage_gap_not_failure(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The project received peer review 8.5/10.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("The project received peer review 8.5/10.")
                ]
            },
        )

        self.assertEqual(
            result[0]["presentation_fidelity"]["limits_state"],
            "limits_absent_unknown",
        )
        self.assertNotIn("presentation_fidelity_limit_exceeded", result[0]["verification_notes"])

    def test_presentation_fidelity_not_applicable_is_explicitly_quiet(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The repo added enterprise deployment docs.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "The repo added enterprise deployment docs.",
                        metadata={"source_stated_limits_status": "limits_not_applicable"},
                    )
                ]
            },
        )

        self.assertEqual(
            result[0]["presentation_fidelity"]["limits_state"],
            "limits_not_applicable",
        )
        self.assertNotIn("presentation_fidelity_limit_exceeded", result[0]["verification_notes"])

    def test_canonical_scalar_mismatch_contradicts_claim(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The GitHub card says example/agentkit has 12k stars and MIT license.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "The GitHub card says example/agentkit has 12k stars and MIT license.",
                        provenance="collector_extracted",
                        metadata={"provenance_tier": "third_party_summary"},
                    ),
                    evidence_item(
                        "github_api observed example/agentkit: stars=842, license=AGPL-3.0.",
                        evidence_id="ev_scalars",
                        provenance="canonical_api_observed",
                        source_field="canonical_scalars",
                        metadata={
                            "provenance_tier": "canonical_api_observed",
                            "canonical_scalar_resolution": {
                                "schema_version": 1,
                                "entity_type": "github_repo",
                                "entity_id": "example/agentkit",
                                "canonical_source": "github_api",
                                "provenance_tier": "canonical_api_observed",
                                "scalars": [
                                    {
                                        "name": "stars",
                                        "canonical_value": 842,
                                        "claimed_value": 12000,
                                        "status": "mismatch",
                                    },
                                    {
                                        "name": "license",
                                        "canonical_value": "AGPL-3.0",
                                        "claimed_value": "MIT",
                                        "status": "platform_delta",
                                        "resolution_confidence": "medium",
                                        "can_contradict_claim": False,
                                    },
                                ],
                            },
                        },
                    ),
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "contradicted")
        self.assertEqual(result[0]["provenance_tier"], "canonical_conflicted")
        self.assertEqual(
            result[0]["scalar_fidelity"]["scalar_state"],
            "canonical_scalar_mismatch",
        )
        self.assertIn("canonical_scalar_mismatch", result[0]["verification_notes"])
        self.assertIn("stars_canonical_mismatch", result[0]["verification_notes"])
        self.assertNotIn("license_canonical_mismatch", result[0]["verification_notes"])
        self.assertIn("stars=842", result[0]["recommended_rewrite"])

    def test_license_platform_delta_requires_review_without_contradicting_claim(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The GitHub card says example/agentkit uses the MIT license.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item(
                        "The GitHub card says example/agentkit uses the MIT license.",
                        provenance="collector_extracted",
                        metadata={"provenance_tier": "third_party_summary"},
                    ),
                    evidence_item(
                        "github_api observed example/agentkit: license=AGPL-3.0.",
                        evidence_id="ev_scalars",
                        provenance="canonical_api_observed",
                        source_field="canonical_scalars",
                        metadata={
                            "provenance_tier": "canonical_api_observed",
                            "canonical_scalar_resolution": {
                                "schema_version": 1,
                                "entity_type": "github_repo",
                                "entity_id": "example/agentkit",
                                "canonical_source": "github_api",
                                "scalars": [
                                    {
                                        "name": "license",
                                        "canonical_value": "AGPL-3.0",
                                        "claimed_value": "MIT",
                                        "status": "platform_delta",
                                        "resolution_confidence": "medium",
                                        "can_contradict_claim": False,
                                        "resolution_notes": ["license_detection_not_definitive"],
                                    },
                                ],
                            },
                        },
                    ),
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "partially_supported")
        self.assertEqual(result[0]["risk_level"], "medium")
        self.assertEqual(result[0]["provenance_tier"], "canonical_platform_delta")
        self.assertIsNone(result[0]["recommended_rewrite"])
        self.assertEqual(
            result[0]["scalar_fidelity"]["scalar_state"],
            "canonical_scalar_platform_delta",
        )
        self.assertIn("canonical_scalar_platform_delta", result[0]["verification_notes"])
        self.assertIn("license_platform_delta_requires_review", result[0]["verification_notes"])
        self.assertNotIn("canonical_scalar_mismatch", result[0]["verification_notes"])

    def test_canonical_scalar_metadata_does_not_penalize_unrelated_claim(self):
        result = verify_claims_against_evidence(
            [
                {
                    "claim_id": "claim_1",
                    "claim_text": "The repo added enterprise deployment docs.",
                    "claim_type": "descriptive",
                }
            ],
            {
                "evidence_items": [
                    evidence_item("The repo added enterprise deployment docs."),
                    evidence_item(
                        "github_api observed example/agentkit: stars=842, license=AGPL-3.0.",
                        evidence_id="ev_scalars",
                        provenance="canonical_api_observed",
                        source_field="canonical_scalars",
                        metadata={
                            "provenance_tier": "canonical_api_observed",
                            "canonical_scalar_resolution": {
                                "schema_version": 1,
                                "entity_type": "github_repo",
                                "entity_id": "example/agentkit",
                                "canonical_source": "github_api",
                                "scalars": [
                                    {
                                        "name": "stars",
                                        "canonical_value": 842,
                                        "claimed_value": 12000,
                                        "status": "mismatch",
                                    }
                                ],
                            },
                        },
                    ),
                ]
            },
        )

        self.assertEqual(result[0]["support_level"], "directly_supported")
        self.assertNotIn("canonical_scalar_mismatch", result[0]["verification_notes"])
        self.assertEqual(
            result[0]["scalar_fidelity"]["scalar_state"],
            "canonical_scalar_recorded_not_claimed",
        )


if __name__ == "__main__":
    unittest.main()
