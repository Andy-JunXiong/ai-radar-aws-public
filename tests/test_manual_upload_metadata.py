import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes import manual as manual_route
from app.routes import signals as signals_route
from app.services.evidence_pack_service import build_signal_evidence_pack
from app.services.manual_source_link_service import apply_manual_source_url_metadata
from app.services.manual_source_link_service import extract_manual_source_urls


class ManualUploadMetadataTests(unittest.TestCase):
    def test_create_manual_session_persists_upload_intent_metadata(self):
        files = [
            {
                "stored_filename": "note.md",
                "original_filename": "note.md",
                "file_kind": "text",
                "preview_text": "hello",
            }
        ]

        with patch.object(manual_route, "resolve_analysis_context", return_value=({}, "default")), patch.object(
            manual_route, "save_session_detail"
        ) as save_detail, patch.object(manual_route, "upsert_session_index_item") as upsert_index:
            session = manual_route.create_manual_session(
                files,
                upload_reason="Track a product signal",
                intended_use="Review for project takeaways",
                cognitive_layer="L3",
            )

        self.assertEqual(session["upload_reason"], "Track a product signal")
        self.assertEqual(session["intended_use"], "Review for project takeaways")
        self.assertEqual(session["cognitive_layer"], "L3")
        save_detail.assert_called_once()
        upsert_index.assert_called_once()
        summary = upsert_index.call_args.args[0]
        self.assertEqual(summary["upload_reason"], "Track a product signal")
        self.assertEqual(summary["intended_use"], "Review for project takeaways")
        self.assertEqual(summary["cognitive_layer"], "L3")

    def test_create_manual_session_persists_source_stated_limits_metadata(self):
        files = [
            {
                "stored_filename": "note.md",
                "original_filename": "note.md",
                "file_kind": "text",
                "preview_text": "Framework report with caveats.",
            }
        ]

        with patch.object(manual_route, "resolve_analysis_context", return_value=({}, "default")), patch.object(
            manual_route, "save_session_detail"
        ) as save_detail, patch.object(manual_route, "upsert_session_index_item") as upsert_index:
            session = manual_route.create_manual_session(
                files,
                source_stated_limits="In-framework simulated review; not external peer review.",
                source_stated_confidence="Known hallucinated citations exist.",
            )

        self.assertEqual(
            session["source_stated_limits"],
            "In-framework simulated review; not external peer review.",
        )
        self.assertEqual(
            session["source_stated_confidence"]["raw_text"],
            "Known hallucinated citations exist.",
        )
        saved_payload = save_detail.call_args.args[0]
        summary = upsert_index.call_args.args[0]
        self.assertEqual(saved_payload["source_stated_limits"], session["source_stated_limits"])
        self.assertEqual(summary["source_stated_limits"], session["source_stated_limits"])

    def test_create_manual_session_promotes_link_source_url_metadata(self):
        files = [
            {
                "stored_filename": "manual-link-source.md",
                "original_filename": "manual-link-source.md",
                "file_kind": "text",
                "preview_text": "# Manual Link Source\n\nSource URL: https://example.com/source\n",
            }
        ]

        with patch.object(manual_route, "resolve_analysis_context", return_value=({}, "default")), patch.object(
            manual_route, "save_session_detail"
        ) as save_detail, patch.object(manual_route, "upsert_session_index_item") as upsert_index:
            session = manual_route.create_manual_session(files)

        self.assertEqual(session["source_url"], "https://example.com/source")
        self.assertEqual(session["url"], "https://example.com/source")
        self.assertEqual(session["link"], "https://example.com/source")
        self.assertEqual(session["source_urls"], ["https://example.com/source"])
        saved_payload = save_detail.call_args.args[0]
        self.assertEqual(saved_payload["source_url"], "https://example.com/source")
        summary = upsert_index.call_args.args[0]
        self.assertEqual(summary["source_url"], "https://example.com/source")

    def test_enrich_manual_link_file_with_article_rewrites_link_source_for_analysis(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            manual_route,
            "fetch_public_article",
            return_value={
                "status": "fetched",
                "source_url": "https://example.com/source",
                "resolved_url": "https://example.com/source",
                "title": "Fetched Article",
                "text": "Fetched article body. " * 40,
                "error": "",
            },
        ):
            file_path = Path(temp_dir) / "manual-link-source.md"
            original_text = "# Manual Link Source\n\nSource URL: https://example.com/source\n"
            file_path.write_text(original_text, encoding="utf-8")

            metadata = manual_route.enrich_manual_link_file_with_article(
                file_path=file_path,
                preview_text=original_text,
                original_filename="manual-link-source.md",
            )
            rewritten_text = file_path.read_text(encoding="utf-8")

        self.assertEqual(metadata["article_fetch_status"], "fetched")
        self.assertEqual(metadata["article_title"], "Fetched Article")
        self.assertIn("linked article fetched", metadata["message"])
        self.assertIn("## Fetched Article Text", metadata["preview_text"])
        self.assertIn("Fetched article body.", metadata["preview_text"])
        self.assertIn("Fetched article body.", rewritten_text)

    def test_pdf_preview_uses_extracted_text_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            manual_route,
            "extract_text_from_file",
            return_value="PDF paper body about knowledge distillation. " * 20,
        ):
            file_path = Path(temp_dir) / "paper.pdf"
            file_path.write_bytes(b"%PDF-test")

            preview = manual_route.build_manual_file_preview_text(file_path, "pdf")

        self.assertIn("PDF paper body about knowledge distillation", preview)
        self.assertNotIn("Text preview will be generated during analysis", preview)

    def test_existing_pdf_placeholder_is_enriched_for_session_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            manual_route,
            "UPLOAD_DIR",
            Path(temp_dir),
        ), patch.object(
            manual_route,
            "extract_text_from_file",
            return_value="Extracted PDF content for the detail preview.",
        ):
            stored_filename = "paper.pdf"
            (Path(temp_dir) / stored_filename).write_bytes(b"%PDF-test")

            enriched = manual_route.enrich_manual_pdf_previews(
                {
                    "session_id": "session-1",
                    "files": [
                        {
                            "stored_filename": stored_filename,
                            "original_filename": "paper.pdf",
                            "file_kind": "pdf",
                            "preview_text": manual_route.PDF_PREVIEW_PENDING_MESSAGE,
                        }
                    ],
                }
            )

        self.assertEqual(
            enriched["files"][0]["preview_text"],
            "Extracted PDF content for the detail preview.",
        )

    def test_session_summary_enriches_existing_pdf_placeholder(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            manual_route,
            "UPLOAD_DIR",
            Path(temp_dir),
        ), patch.object(
            manual_route,
            "extract_text_from_file",
            return_value="Extracted PDF content for the session list.",
        ):
            stored_filename = "paper.pdf"
            (Path(temp_dir) / stored_filename).write_bytes(b"%PDF-test")
            with patch.object(
                manual_route,
                "load_session_detail",
                return_value={
                    "session_id": "session-1",
                    "title": "paper.pdf",
                    "files": [
                        {
                            "stored_filename": stored_filename,
                            "original_filename": "paper.pdf",
                            "file_kind": "pdf",
                            "preview_text": manual_route.PDF_PREVIEW_PENDING_MESSAGE,
                        }
                    ],
                },
            ):
                summaries = manual_route.enrich_session_summaries(
                    [{"session_id": "session-1", "title": "paper.pdf"}]
                )

        self.assertEqual(
            summaries[0]["files"][0]["preview_text"],
            "Extracted PDF content for the session list.",
        )

    def test_manual_upload_metadata_defaults_to_unclassified_for_unknown_layer(self):
        metadata = manual_route.normalize_manual_upload_metadata(
            upload_reason="  ",
            intended_use="Decision prep",
            cognitive_layer="private_notes",
        )

        self.assertEqual(
            metadata,
            {
                "upload_reason": "",
                "intended_use": "Decision prep",
                "cognitive_layer": "unclassified",
            },
        )

    def test_manual_signal_normalization_preserves_upload_intent_metadata(self):
        normalized = signals_route.normalize_manual_session(
            {
                "session_id": "session-1",
                "title": "Manual Session",
                "created_at": "2026-05-05T00:00:00Z",
                "analysis_status": "completed",
                "upload_reason": "Compare against roadmap",
                "intended_use": "Action review",
                "cognitive_layer": "L2",
                "source_stated_limits": "Simulated review only.",
                "source_stated_confidence": {
                    "raw_text": "Known citation caveats.",
                    "normalized_label": None,
                },
                "files": [],
                "analysis": {"summary": "Manual summary"},
            },
            0,
        )

        self.assertEqual(normalized["upload_reason"], "Compare against roadmap")
        self.assertEqual(normalized["intended_use"], "Action review")
        self.assertEqual(normalized["cognitive_layer"], "L2")
        self.assertEqual(normalized["source_stated_limits"], "Simulated review only.")
        self.assertEqual(normalized["source_stated_confidence"]["raw_text"], "Known citation caveats.")

    def test_manual_source_limits_reach_evidence_pack_metadata(self):
        normalized = signals_route.normalize_manual_session(
            {
                "session_id": "session-1",
                "title": "Manual Session",
                "created_at": "2026-05-05T00:00:00Z",
                "analysis_status": "completed",
                "source_stated_limits": "In-framework simulated review; not external peer review.",
                "source_stated_confidence": "Known hallucinated citations exist.",
                "files": [
                    {
                        "stored_filename": "note.md",
                        "original_filename": "note.md",
                        "file_kind": "text",
                        "preview_text": "Deli AutoResearch reports an in-framework simulated review score of 8.5/10.",
                    }
                ],
                "analysis": {"summary": "Manual summary"},
            },
            0,
        )

        evidence_pack = build_signal_evidence_pack(normalized)
        metadata = next(
            item["metadata"]
            for item in evidence_pack["evidence_items"]
            if item["source_field"] == "summary"
        )

        self.assertEqual(metadata["source_stated_limits_status"], "limits_present")
        self.assertEqual(
            metadata["source_stated_limits"][0]["text"],
            "In-framework simulated review; not external peer review.",
        )
        self.assertEqual(
            metadata["source_stated_confidence"]["raw_text"],
            "Known hallucinated citations exist.",
        )

    def test_manual_signal_detail_payload_exposes_upload_intent_metadata(self):
        normalized = signals_route.normalize_manual_session(
            {
                "session_id": "session-1",
                "title": "Manual Session",
                "created_at": "2026-05-05T00:00:00Z",
                "analysis_status": "completed",
                "upload_reason": "Compare against roadmap",
                "intended_use": "Action review",
                "cognitive_layer": "L2",
                "files": [],
                "analysis": {"summary": "Manual summary"},
            },
            0,
        )

        payload = signals_route._manual_signal_response_payload(normalized)

        self.assertEqual(payload["upload_reason"], "Compare against roadmap")
        self.assertEqual(payload["intended_use"], "Action review")
        self.assertEqual(payload["cognitive_layer"], "L2")

    def test_manual_signal_normalization_promotes_link_source_url(self):
        normalized = signals_route.normalize_manual_session(
            {
                "session_id": "session-1",
                "title": "manual-link-source.md",
                "created_at": "2026-05-05T00:00:00Z",
                "analysis_status": "not_started",
                "files": [
                    {
                        "original_filename": "manual-link-source.md",
                        "stored_filename": "manual-link-source.md",
                        "file_kind": "text",
                        "preview_text": "Source URL: https://example.com/source\n",
                    }
                ],
                "analysis": None,
            },
            0,
        )

        self.assertEqual(normalized["source_url"], "https://example.com/source")
        self.assertEqual(normalized["url"], "https://example.com/source")
        self.assertEqual(normalized["link"], "https://example.com/source")

    def test_extract_manual_source_urls_dedupes_and_ignores_non_http_urls(self):
        urls = extract_manual_source_urls(
            [
                {
                    "source_url": "https://example.com/source",
                    "preview_text": "\nSource URL: https://example.com/source\n",
                },
                {"url": "ftp://example.com/ignored"},
                {"link": "http://example.com/second"},
                {"preview_text": "Source URL: not-a-url\n"},
            ]
        )

        self.assertEqual(
            urls,
            [
                "https://example.com/source",
                "http://example.com/second",
            ],
        )

    def test_apply_manual_source_url_metadata_uses_extracted_url_when_existing_alias_is_invalid(self):
        session = apply_manual_source_url_metadata(
            {
                "source_url": "",
                "url": "manual-link-source.md",
                "link": "manual-link-source.md",
                "files": [
                    {
                        "preview_text": "Source URL: https://example.com/source\n",
                    }
                ],
            }
        )

        self.assertEqual(session["source_url"], "https://example.com/source")
        self.assertEqual(session["url"], "https://example.com/source")
        self.assertEqual(session["link"], "https://example.com/source")

    def test_input_text_session_raw_output_capture_preserves_pre_parse_model_output(self):
        raw_output = '{"summary":"Raw model summary","why_it_matters":"Because","relevance_to_projects":"AI Radar","relevance_to_career":"Career","synthesized_insight":"Insight"}'
        route = SimpleNamespace(provider="openai", model="gpt-test")

        def fake_policy_text_json(*, executor, **kwargs):
            self.assertEqual(
                kwargs["metadata"]["source_labels"],
                ["first.txt", "second.pdf"],
            )
            self.assertEqual(
                kwargs["policy_input"].metadata["source_labels"],
                ["first.txt", "second.pdf"],
            )
            payload, selected_route = executor("manual_text_session", "system", "user")
            return payload, selected_route, {"policy": "guarded"}

        def fake_execute_text_json_task(*, raw_output_callback=None, **kwargs):
            self.assertIsNotNone(raw_output_callback)
            raw_output_callback(raw_output, route)
            return {"summary": "parsed"}, route

        with patch.object(
            manual_route,
            "execute_policy_text_json",
            side_effect=fake_policy_text_json,
        ), patch.object(
            manual_route,
            "execute_text_json_task",
            side_effect=fake_execute_text_json_task,
        ):
            analysis, selected_route, policy_metadata = manual_route._analyze_with_routed_text_json(
                "system",
                "user",
                task_type="manual_text_session",
                source_count=2,
                source_labels=["first.txt", "second.pdf"],
                capture_raw_output=True,
            )

        record = policy_metadata["input_text_analysis_raw_output"]
        self.assertEqual(analysis, {"summary": "parsed"})
        self.assertEqual(selected_route.provider, "openai")
        self.assertEqual(record["schema_version"], manual_route.INPUT_TEXT_RAW_OUTPUT_SCHEMA_VERSION)
        self.assertEqual(record["skill_name"], "input-text-analyze")
        self.assertEqual(record["capture_stage"], "before_parse")
        self.assertEqual(record["provider"], "openai")
        self.assertEqual(record["model"], "gpt-test")
        self.assertEqual(record["source_count"], 2)
        self.assertFalse(record["contains_system_prompt"])
        self.assertFalse(record["contains_user_prompt"])
        self.assertEqual(record["raw_output"], raw_output)
        self.assertEqual(record["raw_output_char_count"], len(raw_output))
        self.assertEqual(record["raw_output_sha256"], hashlib.sha256(raw_output.encode("utf-8")).hexdigest())

    def test_analyze_manual_text_session_stores_raw_output_record_in_detail_only(self):
        raw_output_record = {
            "schema_version": manual_route.INPUT_TEXT_RAW_OUTPUT_SCHEMA_VERSION,
            "skill_name": "input-text-analyze",
            "skill_version": "v1",
            "task_type": "manual_text_session",
            "capture_stage": "before_parse",
            "storage_scope": "manual_session_detail_only",
            "contains_system_prompt": False,
            "contains_user_prompt": False,
            "captured_at": "2026-06-22T00:00:00+00:00",
            "provider": "anthropic",
            "model": "claude-test",
            "fallback_used": False,
            "source_count": 1,
            "raw_output_char_count": 18,
            "raw_output_sha256": "abc123",
            "raw_output": '{"summary":"raw"}',
        }
        analysis = {
            "summary": "Parsed summary",
            "why_it_matters": "Parsed importance",
            "relevance_to_projects": "Parsed projects",
            "relevance_to_career": "Parsed career",
            "synthesized_insight": "Parsed insight",
        }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            manual_route,
            "UPLOAD_DIR",
            Path(temp_dir) / "manual_uploads",
        ), patch.object(
            manual_route,
            "SESSIONS_DIR",
            Path(temp_dir) / "manual_uploads" / "sessions",
        ), patch.object(
            manual_route,
            "SESSIONS_INDEX_PATH",
            Path(temp_dir) / "manual_uploads" / "sessions" / "index.json",
        ), patch.object(
            manual_route,
            "resolve_analysis_context",
            return_value=({}, "test"),
        ), patch.object(
            manual_route,
            "resolve_request_user_id",
            return_value=None,
        ), patch.object(
            manual_route,
            "analyze_text_session_with_routed_llm",
            return_value=(
                analysis,
                SimpleNamespace(provider="anthropic", model="claude-test"),
                {
                    "provider_used": "anthropic",
                    "model_used": "claude-test",
                    "input_text_analysis_raw_output": raw_output_record,
                },
            ),
        ):
            manual_route.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            manual_route.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            (manual_route.UPLOAD_DIR / "note.md").write_text(
                "Manual text material for baseline capture.",
                encoding="utf-8",
            )
            session = manual_route.create_manual_session(
                [
                    {
                        "stored_filename": "note.md",
                        "original_filename": "note.md",
                        "file_kind": "text",
                        "preview_text": "Manual text material for baseline capture.",
                    }
                ]
            )

            response = manual_route.analyze_manual_session(
                manual_route.ManualAnalyzeSessionRequest(
                    session_id=session["session_id"],
                    files=[
                        manual_route.SessionFileItem(
                            stored_filename="note.md",
                            original_filename="note.md",
                            file_kind="text",
                        )
                    ],
                ),
                SimpleNamespace(),
            )

            completed_session = manual_route.load_session_detail(session["session_id"])
            index_items = manual_route.load_sessions_index()

        self.assertEqual(response["analysis"], analysis)
        self.assertNotIn("input_text_analysis_raw_output", response["policy_metadata"])
        self.assertEqual(completed_session["input_text_analysis_raw_output"], raw_output_record)
        self.assertNotIn("input_text_analysis_raw_output", index_items[0])
        self.assertNotIn("input_text_analysis_raw_output", index_items[0]["policy_metadata"])


if __name__ == "__main__":
    unittest.main()
