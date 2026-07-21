import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import final_takeaway_artifact_service as service  # noqa: E402


class FinalTakeawayArtifactServiceTests(unittest.TestCase):
    def test_external_synthesis_source_normalizes_html_without_storing_raw_content(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            source = service.create_external_synthesis_source(
                signal_id="sig-html",
                source_text="<h1>Claude Review</h1><script>alert('x')</script><p>Useful synthesis &amp; critique.</p>",
                source_file="claude-review.html",
                content_type="text/html",
                metadata={"tool": "claude"},
            )
            loaded = service.get_external_synthesis_source(source["external_synthesis_source_id"])

            self.assertEqual(loaded["record_type"], "external_synthesis_source")
            self.assertEqual(loaded["source_kind"], "external_html")
            self.assertIn("Claude Review", loaded["source_text"])
            self.assertIn("Useful synthesis & critique.", loaded["source_text"])
            self.assertNotIn("<script", loaded["source_text"])
            self.assertNotIn("alert", loaded["source_text"])
            self.assertEqual(loaded["evidence_boundary"], "review_context_not_verified_evidence")
            self.assertEqual(loaded["used_by"], "final_takeaway_review_bundle")
            self.assertEqual(loaded["metadata"]["normalization"], "html_text_only_no_script_execution")
            self.assertFalse(loaded["metadata"]["raw_content_stored"])
            self.assertTrue(loaded["original_content_hash"])
            self.assertTrue(loaded["normalized_content_hash"])

    def test_external_synthesis_source_lists_by_signal_and_rejects_empty_normalized_text(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            first = service.create_external_synthesis_source(
                signal_id="sig-1",
                source_text="# Codex Review\n\nA useful review.",
                source_file="codex-review.md",
            )
            service.create_external_synthesis_source(
                signal_id="sig-2",
                source_text="Other review.",
                source_file="other.txt",
            )

            by_signal = service.list_external_synthesis_sources(signal_id="sig-1")
            self.assertEqual([item["external_synthesis_source_id"] for item in by_signal], [first["external_synthesis_source_id"]])
            self.assertEqual(by_signal[0]["source_kind"], "external_markdown")

            with self.assertRaises(ValueError) as context:
                service.create_external_synthesis_source(
                    signal_id="sig-1",
                    source_text="<script>alert('only script')</script>",
                    source_file="empty.html",
                )
            self.assertIn("reviewable text", str(context.exception))

    def test_review_bundle_snapshot_is_immutable_and_hashes_content(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            first = service.create_review_bundle_snapshot(
                signal_id="sig-1",
                source_text="# Bundle\n\nClaude review v1",
                source_file="review.md",
                conversation_refs=[{"kind": "ai_discussion", "conversation_id": "chat-1"}],
                metadata={"reviewer": "Andy"},
            )
            second = service.create_review_bundle_snapshot(
                signal_id="sig-1",
                source_text="# Bundle\n\nClaude review v2",
                source_file="review.md",
                conversation_refs=[{"kind": "ai_discussion", "conversation_id": "chat-1"}],
                metadata={"reviewer": "Andy"},
            )

            loaded_first = service.get_review_bundle_snapshot(first["snapshot_id"])

            self.assertEqual(loaded_first["source_text"], "# Bundle\n\nClaude review v1")
            self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
            self.assertNotEqual(first["content_hash"], second["content_hash"])
            self.assertEqual(loaded_first["content_hash"], first["content_hash"])
            self.assertEqual(loaded_first["used_by"], "confirmed_final_takeaway")

    def test_external_synthesis_quality_metadata_is_non_blocking_review_context(self):
        quality = {
            "status": "warning",
            "summary": "This source looks like a chat export or captured app UI.",
            "flags": [
                {
                    "code": "chat_export_ui_dump",
                    "label": "Chat export / UI dump",
                    "detail": "Detected UI chrome.",
                }
            ],
            "checked_at": "2026-06-22T14:00:00+00:00",
            "checked_text_length": 1200,
            "source_file": "chat.html",
            "source_kind": "external_html",
            "topic_terms_checked": ["codex", "agent"],
            "topic_hit_count": 1,
        }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            source = service.create_external_synthesis_source(
                signal_id="sig-quality",
                source_text="<h1>Claude</h1><p>New chat Share Content useful synthesis.</p>",
                source_file="chat.html",
                metadata={"external_synthesis_quality": quality},
            )
            snapshot = service.create_review_bundle_snapshot(
                signal_id="sig-quality",
                source_text="# Bundle\n\nSynthesis",
                metadata={
                    "external_synthesis_source_id": source["external_synthesis_source_id"],
                    "external_synthesis_quality": quality,
                },
            )

            source_quality = source["metadata"]["external_synthesis_quality"]
            snapshot_quality = snapshot["metadata"]["external_synthesis_quality"]

            self.assertEqual(source_quality["status"], "warning")
            self.assertEqual(source_quality["flags"][0]["code"], "chat_export_ui_dump")
            self.assertEqual(source_quality["effect"], "non_blocking_review_context_warning")
            self.assertEqual(source_quality["evidence_boundary"], "review_context_not_verified_evidence")
            self.assertTrue(source_quality["review_context_only"])
            self.assertTrue(source_quality["not_verified_evidence"])
            self.assertEqual(snapshot_quality["status"], "warning")
            self.assertEqual(snapshot_quality["flags"][0]["label"], "Chat export / UI dump")
            self.assertEqual(snapshot_quality["topic_terms_checked"], ["codex", "agent"])

    def test_confirm_final_takeaway_requires_existing_snapshot_and_stores_snapshot_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            snapshot = service.create_review_bundle_snapshot(
                signal_id="sig-2",
                source_text="Andy synthesis plus Claude and Codex notes.",
                source_kind="external_md",
            )

            artifact = service.confirm_final_takeaway(
                signal_id="sig-2",
                confirmed_text="This is the Andy-confirmed final takeaway.",
                review_bundle_snapshot_id=snapshot["snapshot_id"],
                source_completion_note="Draft note",
                confirmed_by="Andy",
                provenance={"codex_review": "repo-grounded"},
            )
            loaded = service.get_final_takeaway(artifact["final_takeaway_id"])

            self.assertEqual(loaded["status"], "confirmed")
            self.assertEqual(loaded["review_bundle_snapshot_id"], snapshot["snapshot_id"])
            self.assertEqual(loaded["review_bundle_content_hash"], snapshot["content_hash"])
            self.assertEqual(loaded["confirmed_by"], "Andy")
            self.assertEqual(loaded["source_completion_note"], "Draft note")
            self.assertNotIn("candidate_source", loaded)
            self.assertNotIn("verification_metadata", loaded)

    def test_confirm_final_takeaway_rejects_missing_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            with self.assertRaises(ValueError) as context:
                service.confirm_final_takeaway(
                    signal_id="sig-3",
                    confirmed_text="Confirmed text",
                    review_bundle_snapshot_id="rbs_missing",
                )

            self.assertIn("snapshot not found", str(context.exception))

    def test_confirm_final_takeaway_rejects_snapshot_signal_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            snapshot = service.create_review_bundle_snapshot(
                signal_id="sig-source",
                source_text="Bundle content",
            )

            with self.assertRaises(ValueError) as context:
                service.confirm_final_takeaway(
                    signal_id="sig-other",
                    confirmed_text="Confirmed text",
                    review_bundle_snapshot_id=snapshot["snapshot_id"],
                )

            self.assertIn("signal_id does not match", str(context.exception))


if __name__ == "__main__":
    unittest.main()
