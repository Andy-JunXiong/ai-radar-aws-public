import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import decision_card_service, decision_review_service  # noqa: E402


class DecisionServicesTests(unittest.TestCase):
    def test_save_and_list_decision_card(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "decision_cards"
            index_path = data_dir / "index.json"
            with patch.object(decision_card_service, "DATA_DIR", data_dir), patch.object(
                decision_card_service, "INDEX_PATH", index_path
            ):
                card = decision_card_service.build_decision_card(
                    title="Test decision",
                    signal_refs=["sig_1"],
                    project_refs=["proj_1"],
                    thesis="A concrete thesis",
                    importance_score=80,
                    confidence_score=70,
                    counter_argument="Could be noise.",
                    recommended_action="Watch one week.",
                    action_type="watch",
                    invalidation_condition="No follow-through.",
                    expiry_at=None,
                    review_at="2026-05-01T00:00:00+00:00",
                )
                decision_card_service.save_decision_card(card)
                items = decision_card_service.list_decision_cards()
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], card["id"])

    def test_complete_review_marks_decision_reviewed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            card_dir = Path(tmpdir) / "decision_cards"
            card_index = card_dir / "index.json"
            review_dir = Path(tmpdir) / "reviews"
            review_index = review_dir / "index.json"

            with patch.object(decision_card_service, "DATA_DIR", card_dir), patch.object(
                decision_card_service, "INDEX_PATH", card_index
            ), patch.object(decision_review_service, "DATA_DIR", review_dir), patch.object(
                decision_review_service, "INDEX_PATH", review_index
            ):
                card = decision_card_service.build_decision_card(
                    title="Review me",
                    signal_refs=["sig_2"],
                    project_refs=[],
                    thesis="Thesis",
                    importance_score=90,
                    confidence_score=80,
                    counter_argument="Maybe not.",
                    recommended_action="Act.",
                    action_type="apply",
                    invalidation_condition="Contrary evidence.",
                    expiry_at=None,
                    review_at="2026-05-01T00:00:00+00:00",
                )
                decision_card_service.save_decision_card(card)
                review = decision_review_service.build_review_record(
                    decision_card_id=card["id"],
                )
                decision_review_service.save_review_record(review)
                completed = decision_review_service.complete_review(
                    review_id=review["id"],
                    outcome="correct",
                    what_happened="It played out.",
                    confidence_adjustment=5,
                    notes="Good call.",
                )
                decision_card_service.attach_review_to_decision(
                    card["id"], completed["id"], review_date=completed["updated_at"]
                )
                updated_card = decision_card_service.get_decision_card(card["id"])
                self.assertEqual(updated_card["status"], "reviewed")
                self.assertEqual(updated_card["latest_review_id"], completed["id"])

    def test_due_reviews_auto_create_draft_for_overdue_card(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            card_dir = Path(tmpdir) / "decision_cards"
            card_index = card_dir / "index.json"
            review_dir = Path(tmpdir) / "reviews"
            review_index = review_dir / "index.json"

            with patch.object(decision_card_service, "DATA_DIR", card_dir), patch.object(
                decision_card_service, "INDEX_PATH", card_index
            ), patch.object(decision_review_service, "DATA_DIR", review_dir), patch.object(
                decision_review_service, "INDEX_PATH", review_index
            ):
                card = decision_card_service.build_decision_card(
                    title="Overdue review",
                    signal_refs=[],
                    project_refs=[],
                    thesis="A thesis",
                    importance_score=70,
                    confidence_score=65,
                    counter_argument="Maybe not.",
                    recommended_action="Wait and review.",
                    action_type="watch",
                    invalidation_condition="Contrary evidence.",
                    expiry_at=None,
                    review_at="2026-01-01T00:00:00+00:00",
                )
                decision_card_service.save_decision_card(card)

                created = decision_review_service.ensure_due_review_drafts(
                    due_before="2026-02-01T00:00:00+00:00"
                )
                due_reviews = decision_review_service.list_due_reviews(
                    due_before="2026-02-01T00:00:00+00:00"
                )

                self.assertEqual(len(created), 1)
                self.assertEqual(len(due_reviews), 1)
                self.assertEqual(due_reviews[0]["decision_card_id"], card["id"])
                self.assertEqual(due_reviews[0]["status"], "draft")


if __name__ == "__main__":
    unittest.main()
