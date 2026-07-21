import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.reflection_polish_pair_service import (  # noqa: E402
    DIMENSION_RESULT_FAIL,
    DIMENSION_RESULT_PASS,
    PAIR_RECORD_TYPE,
    REVIEW_DIMENSIONS,
    REVIEW_OUTCOME_APPROVED,
    REVIEW_OUTCOME_NEEDS_REVISION,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_RECORD_TYPE,
    build_reflection_polish_pair,
    build_reflection_polish_review,
    validate_reflection_polish_pair,
    validate_reflection_polish_review,
)


class ReflectionPolishPairServiceTests(unittest.TestCase):
    def _pair(self, **overrides):
        payload = {
            "original_text": "I think this signal matters because it changes my view.",
            "polished_text": "I think this signal matters because it changes my view, and the shift is worth recording.",
            "provider_used": "anthropic",
            "fallback_used": False,
            "policy_metadata": {"task_type": "reflection_polish"},
            "execution": {"provider": "anthropic"},
            "context": {
                "signal_id": "sig_1",
                "signal_title": "Memory boundary signal",
                "signal_summary": "A signal about memory boundaries.",
            },
            "pair_id": "rpp_test",
            "created_at": "2026-06-26T00:00:00+00:00",
        }
        payload.update(overrides)
        return build_reflection_polish_pair(**payload)

    def _passing_dimensions(self):
        return {dimension: DIMENSION_RESULT_PASS for dimension in REVIEW_DIMENSIONS}

    def test_pair_records_original_and_polished_text_with_fingerprints(self):
        pair = self._pair()

        self.assertEqual(pair["record_type"], PAIR_RECORD_TYPE)
        self.assertEqual(pair["id"], "rpp_test")
        self.assertEqual(pair["draft"]["original_text"], "I think this signal matters because it changes my view.")
        self.assertTrue(pair["draft"]["content_fingerprint"].startswith("sha256:"))
        self.assertTrue(pair["polish"]["content_fingerprint"].startswith("sha256:"))
        self.assertNotEqual(
            pair["draft"]["content_fingerprint"],
            pair["polish"]["content_fingerprint"],
        )
        self.assertEqual(pair["baseline_eligibility"], {"eligible": False, "reason": "human_review_required"})
        self.assertIsNone(pair["review_ref"])
        for forbidden in (
            "blocked_downstream_actions",
            "project_takeaway_eligibility",
            "evidence_pack",
            "verified_insight_id",
        ):
            self.assertNotIn(forbidden, pair)

    def test_pair_requires_non_empty_draft_and_polished_output(self):
        with self.assertRaisesRegex(ValueError, "original_text is required"):
            self._pair(original_text=" ")

        with self.assertRaisesRegex(ValueError, "polished_text is required"):
            self._pair(polished_text="")

    def test_pair_rejects_tampered_fingerprint_or_baseline_eligibility(self):
        pair = self._pair()
        tampered = copy.deepcopy(pair)
        tampered["draft"]["content_fingerprint"] = "sha256:bad"

        with self.assertRaisesRegex(ValueError, "draft.content_fingerprint"):
            validate_reflection_polish_pair(tampered)

        tampered = copy.deepcopy(pair)
        tampered["baseline_eligibility"]["eligible"] = True
        tampered["baseline_eligibility"]["reason"] = "approved"

        with self.assertRaisesRegex(ValueError, "baseline_eligibility.eligible"):
            validate_reflection_polish_pair(tampered)

    def test_pair_rejects_project_takeaway_or_evidence_path_top_level_fields(self):
        pair = self._pair()
        pair["blocked_downstream_actions"] = []

        with self.assertRaisesRegex(ValueError, "blocked_downstream_actions"):
            validate_reflection_polish_pair(pair)

    def test_approved_review_requires_all_dimensions_pass_and_final_text(self):
        pair = self._pair()
        review = build_reflection_polish_review(
            pair=pair,
            outcome=REVIEW_OUTCOME_APPROVED,
            dimension_results=self._passing_dimensions(),
            reviewer_id="andy",
            reviewer_note="Preserves the user's voice and improves clarity.",
            final_reflection_text="Final approved reflection.",
            review_id="rpr_test",
            reviewed_at="2026-06-26T00:00:00+00:00",
        )

        self.assertEqual(review["record_type"], REVIEW_RECORD_TYPE)
        self.assertEqual(review["pair_id"], pair["id"])
        self.assertEqual(review["outcome"], REVIEW_OUTCOME_APPROVED)
        self.assertEqual(review["reviewer"], {"type": "human", "id": "andy"})
        self.assertEqual(set(review["dimension_results"]), set(REVIEW_DIMENSIONS))

    def test_review_rejects_unknown_or_missing_dimensions(self):
        pair = self._pair()
        dimensions = self._passing_dimensions()
        dimensions["unexpected"] = DIMENSION_RESULT_PASS

        with self.assertRaisesRegex(ValueError, "exactly the reflection-polish checklist dimensions"):
            build_reflection_polish_review(
                pair=pair,
                outcome=REVIEW_OUTCOME_APPROVED,
                dimension_results=dimensions,
                reviewer_id="andy",
                final_reflection_text="Final approved reflection.",
            )

    def test_review_cannot_approve_failed_dimension(self):
        pair = self._pair()
        dimensions = self._passing_dimensions()
        dimensions["user_voice_preservation"] = DIMENSION_RESULT_FAIL

        with self.assertRaisesRegex(ValueError, "cannot be approved"):
            build_reflection_polish_review(
                pair=pair,
                outcome=REVIEW_OUTCOME_APPROVED,
                dimension_results=dimensions,
                reviewer_id="andy",
                final_reflection_text="Final approved reflection.",
            )

    def test_needs_revision_and_rejected_require_reviewer_note(self):
        pair = self._pair()

        for outcome in (REVIEW_OUTCOME_NEEDS_REVISION, REVIEW_OUTCOME_REJECTED):
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(ValueError, "reviewer_note is required"):
                    build_reflection_polish_review(
                        pair=pair,
                        outcome=outcome,
                        dimension_results=self._passing_dimensions(),
                        reviewer_id="andy",
                    )

    def test_approved_review_requires_final_reflection_text(self):
        pair = self._pair()

        with self.assertRaisesRegex(ValueError, "final_reflection_text is required"):
            build_reflection_polish_review(
                pair=pair,
                outcome=REVIEW_OUTCOME_APPROVED,
                dimension_results=self._passing_dimensions(),
                reviewer_id="andy",
                reviewer_note="Looks good.",
            )

    def test_review_must_reference_provided_pair(self):
        pair = self._pair()
        review = build_reflection_polish_review(
            pair=pair,
            outcome=REVIEW_OUTCOME_APPROVED,
            dimension_results=self._passing_dimensions(),
            reviewer_id="andy",
            reviewer_note="Looks good.",
            final_reflection_text="Final approved reflection.",
        )
        review["pair_id"] = "rpp_other"

        with self.assertRaisesRegex(ValueError, "must reference the provided pair"):
            validate_reflection_polish_review(review, pair=pair)


if __name__ == "__main__":
    unittest.main()
