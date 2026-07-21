import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import relationship_annotation_service as service  # noqa: E402


class RelationshipAnnotationServiceTests(unittest.TestCase):
    def test_model_can_infer_from_structured_metadata_without_axis_collapse(self):
        annotation = service.normalize_relationship_annotation(
            {
                "relation_type": "association",
                "grounding_source": "structured_metadata",
                "derivation_mechanism": "model_inferred",
                "classified_by": "model",
                "source_refs": ["repo:owner/project"],
                "rationale": "The repositories share an owner and release window.",
            }
        )

        self.assertEqual(annotation["grounding_source"], "structured_metadata")
        self.assertEqual(annotation["derivation_mechanism"], "model_inferred")
        self.assertEqual(annotation["support_posture"], "proposed")
        self.assertEqual(annotation["review_reason_codes"], ["low_support_density"])
        self.assertTrue(service.relationship_review_required(annotation))

    def test_metadata_only_strong_relationship_cannot_be_confirmed(self):
        with self.assertRaises(ValueError) as context:
            service.normalize_relationship_annotation(
                {
                    "relation_type": "evidential_support",
                    "grounding_source": "structured_metadata",
                    "derivation_mechanism": "deterministic_rule",
                    "support_posture": "confirmed",
                    "classified_by": "system_rule",
                }
            )

        self.assertIn("cannot be confirmed", str(context.exception))

    def test_unsourced_evidential_support_is_invalid(self):
        with self.assertRaises(ValueError) as context:
            service.normalize_relationship_annotation(
                {
                    "relation_type": "evidential_support",
                    "grounding_source": "none",
                    "derivation_mechanism": "model_inferred",
                    "support_posture": "needs_review",
                    "classified_by": "model",
                }
            )

        self.assertIn("require a grounding_source", str(context.exception))

    def test_unsourced_logical_inference_is_review_only(self):
        annotation = service.normalize_relationship_annotation(
            {
                "relation_type": "logical_inference",
                "grounding_source": "none",
                "derivation_mechanism": "model_inferred",
                "support_posture": "needs_review",
                "classified_by": "model",
            }
        )

        self.assertEqual(annotation["support_posture"], "needs_review")
        self.assertIn("unsourced_support", annotation["review_reason_codes"])
        self.assertIn("model_inferred_logical", annotation["review_reason_codes"])
        self.assertIn("ambiguous_relationship", annotation["review_reason_codes"])
        self.assertTrue(service.relationship_review_required(annotation))

    def test_model_classified_annotation_cannot_be_confirmed(self):
        with self.assertRaises(ValueError) as context:
            service.normalize_relationship_annotation(
                {
                    "relation_type": "association",
                    "grounding_source": "source_excerpt",
                    "derivation_mechanism": "direct_observation",
                    "support_posture": "confirmed",
                    "classified_by": "model",
                }
            )

        self.assertIn("model-classified", str(context.exception))

    def test_review_reason_codes_are_rule_generated_only(self):
        with self.assertRaises(ValueError) as context:
            service.normalize_relationship_annotation(
                {
                    "relation_type": "association",
                    "grounding_source": "source_excerpt",
                    "derivation_mechanism": "direct_observation",
                    "support_posture": "needs_review",
                    "classified_by": "human",
                    "review_reason_codes": ["free_text_reason"],
                }
            )

        self.assertIn("rule-generated", str(context.exception))


if __name__ == "__main__":
    unittest.main()
