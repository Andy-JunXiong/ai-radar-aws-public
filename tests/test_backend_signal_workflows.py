import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for {module_name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


signals_route = load_module(
    "backend_signals_route",
    BACKEND_ROOT / "app" / "routes" / "signals.py",
)
s3_reader = load_module(
    "backend_s3_reader",
    BACKEND_ROOT / "app" / "services" / "s3_reader.py",
)
workspace_route = load_module(
    "backend_workspace_route",
    BACKEND_ROOT / "app" / "routes" / "workspace.py",
)


class SignalRouteTests(unittest.TestCase):
    def test_save_reflection_request_accepts_verification_metadata(self):
        payload = workspace_route.SaveReflectionRequest(
            final_reflection="Done",
            verification_metadata={"verification_status": "weakly_supported"},
        )

        self.assertEqual(
            payload.verification_metadata,
            {"verification_status": "weakly_supported"},
        )

    def test_get_signal_detail_returns_normalized_auto_signal_payload(self):
        decision_trace = [{"event_type": "ingested", "actor": "system"}]
        source_excerpt = "Canonical source text from the original article."
        signal = {
            "signal_id": "sig-1",
            "title": "Test signal",
            "summary": "Summary",
            "source": "rss",
            "status": "saved",
            "saved_reason": "useful",
            "decision_trace": decision_trace,
            "topic": "Agents",
            "score": 0.88,
            "source_excerpt": source_excerpt,
            "source_excerpt_length": len(source_excerpt),
        }

        with patch.object(signals_route, "get_signal_by_id", return_value=signal), patch.object(
            signals_route, "find_manual_signal", return_value=None
        ):
            result = signals_route.get_signal_detail("sig-1")

        self.assertEqual(result["signal_id"], "sig-1")
        self.assertEqual(result["title"], "Test signal")
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["saved_reason"], "useful")
        self.assertEqual(result["decision_trace"], decision_trace)
        self.assertEqual(result["source_excerpt"], source_excerpt)
        self.assertEqual(result["source_excerpt_length"], len(source_excerpt))

    def test_get_signal_detail_returns_manual_payload_with_manual_fields(self):
        manual_signal = {
            "id": "manual-1",
            "signal_id": "manual-1",
            "title": "Manual Session",
            "summary": "Manual summary",
            "source": "manual",
            "status": "analyzed",
            "manual_session_id": "manual-1",
            "file_count": 2,
            "file_types": ["pdf", "image"],
            "analysis_status": "completed",
            "workspace_saved": True,
            "workspace_file_name": "workspace.json",
            "workspace_saved_at": "2026-04-05T00:00:00Z",
            "provider_used": "openai",
            "files": [],
        }

        with patch.object(signals_route, "get_signal_by_id", return_value=None), patch.object(
            signals_route, "find_manual_signal", return_value=manual_signal
        ):
            result = signals_route.get_signal_detail("manual-1")

        self.assertTrue(result["is_manual"])
        self.assertEqual(result["manual_session_id"], "manual-1")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["provider_used"], "openai")

    def test_update_manual_signal_status_records_lifecycle_softly(self):
        session_payloads = []
        session_data = {
            "session_id": "manual-1",
            "status": "pending",
            "analysis_status": "completed",
        }

        def capture_session_save(payload):
            session_payloads.append(dict(payload))

        with patch.object(
            signals_route,
            "find_manual_signal",
            return_value={"signal_id": "manual_manual-1", "status": "pending"},
        ), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "save_session_detail", side_effect=capture_session_save
        ), patch.object(
            signals_route, "build_session_summary", return_value={}
        ), patch.object(
            signals_route, "upsert_session_index_item", return_value=None
        ), patch.object(
            signals_route, "_soft_record_signal_status_lifecycle_events"
        ) as lifecycle_mock, patch.object(
            signals_route, "utc_now_iso", return_value="2026-05-23T00:00:00Z"
        ):
            result = signals_route.update_signal_status(
                signals_route.SignalStatusUpdate(
                    signal_id="manual_manual-1",
                    status="saved",
                    saved_reason="Review later",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["manual_session_id"], "manual-1")
        self.assertEqual(session_payloads[0]["status"], "saved")
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "manual_manual-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "manual_session")
        self.assertEqual(lifecycle_kwargs["source_record_id"], "manual-1")
        self.assertEqual(lifecycle_kwargs["status_before"], "pending")
        self.assertEqual(lifecycle_kwargs["status_after"], "saved")
        self.assertEqual(lifecycle_kwargs["saved_reason"], "Review later")

    def test_update_manual_signal_status_remains_best_effort_when_lifecycle_fails(self):
        session_payloads = []
        session_data = {
            "session_id": "manual-1",
            "status": "pending",
            "analysis_status": "completed",
        }

        def capture_session_save(payload):
            session_payloads.append(dict(payload))

        with patch.object(
            signals_route,
            "find_manual_signal",
            return_value={"signal_id": "manual_manual-1", "status": "pending"},
        ), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "save_session_detail", side_effect=capture_session_save
        ), patch.object(
            signals_route, "build_session_summary", return_value={}
        ), patch.object(
            signals_route, "upsert_session_index_item", return_value=None
        ), patch.object(
            signals_route,
            "append_signal_lifecycle_events",
            side_effect=RuntimeError("lifecycle write failed"),
        ), patch.object(
            signals_route, "utc_now_iso", return_value="2026-05-26T00:00:00Z"
        ):
            result = signals_route.update_signal_status(
                signals_route.SignalStatusUpdate(
                    signal_id="manual_manual-1",
                    status="saved",
                    saved_reason="Review later",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "saved")
        self.assertEqual(session_payloads[0]["status"], "saved")
        self.assertEqual(session_payloads[0]["saved_reason"], "Review later")

    def test_update_automatic_signal_status_records_lifecycle_softly(self):
        update_result = {
            "message": "Signal status updated successfully.",
            "signal_id": "sig-1",
            "status": "saved",
            "saved_reason": "Review later",
            "decision_trace_event": "operator_saved_for_later",
            "updated_keys": ["signals/latest/signals.json"],
        }

        with patch.object(signals_route, "find_manual_signal", return_value=None), patch.object(
            signals_route, "get_signal_by_id", return_value={"signal_id": "sig-1", "status": "pending"}
        ), patch.object(
            signals_route, "update_signal_status_by_signal_id", return_value=update_result
        ), patch.object(
            signals_route, "_soft_record_signal_status_lifecycle_events"
        ) as lifecycle_mock:
            result = signals_route.update_signal_status(
                signals_route.SignalStatusUpdate(
                    signal_id="sig-1",
                    status="saved",
                    saved_reason="Review later",
                )
            )

        self.assertEqual(result, update_result)
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "sig-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "signal")
        self.assertEqual(lifecycle_kwargs["source_record_id"], "sig-1")
        self.assertEqual(lifecycle_kwargs["status_before"], "pending")
        self.assertEqual(lifecycle_kwargs["status_after"], "saved")
        self.assertEqual(lifecycle_kwargs["decision_trace_event"], "operator_saved_for_later")
        self.assertEqual(lifecycle_kwargs["updated_keys"], ["signals/latest/signals.json"])

    def test_update_automatic_signal_status_remains_best_effort_when_lifecycle_fails(self):
        update_result = {
            "message": "Signal status updated successfully.",
            "signal_id": "sig-1",
            "status": "saved",
            "saved_reason": "Review later",
            "decision_trace_event": "operator_saved_for_later",
            "updated_keys": ["signals/latest/signals.json"],
        }

        with patch.object(signals_route, "find_manual_signal", return_value=None), patch.object(
            signals_route, "get_signal_by_id", return_value={"signal_id": "sig-1", "status": "pending"}
        ), patch.object(
            signals_route, "update_signal_status_by_signal_id", return_value=update_result
        ) as update_mock, patch.object(
            signals_route,
            "append_signal_lifecycle_events",
            side_effect=RuntimeError("lifecycle write failed"),
        ):
            result = signals_route.update_signal_status(
                signals_route.SignalStatusUpdate(
                    signal_id="sig-1",
                    status="saved",
                    saved_reason="Review later",
                )
            )

        self.assertEqual(result, update_result)
        update_mock.assert_called_once()

    def test_generate_insight_for_auto_signal_returns_evidence_pack_after_reread(self):
        signal = {
            "signal_id": "sig-1",
            "title": "Test signal",
            "summary": "Summary",
            "source": "rss",
            "status": "saved",
            "topic": "Agents",
            "source_excerpt": "Original source text with claim-level support.",
            "source_excerpt_length": 46,
        }
        generated = {
            "why_it_matters": "Fresh why",
            "relevance_to_projects": "Fresh projects",
            "relevance_to_career": "Fresh career",
            "synthesized_insight": "Fresh insight",
            "provider_used": "chatgpt",
            "actual_provider": "openai",
            "model_used": "gpt-test",
            "generation_mode": "llm",
            "requested_provider": "chatgpt",
            "content_fingerprint": "new-fingerprint",
            "policy_metadata": {"notes": ["Generated successfully."]},
            "verification": {
                "verification_status": "verified_with_limitations",
                "verified_insight_id": "vi_auto_1",
                "allowed_downstream_actions": ["normal_insight", "watch_only"],
                "blocked_downstream_actions": [],
            },
            "evidence_pack": {"source_signal_id": "sig-1", "evidence_version": "v1"},
        }
        persisted = {
            "signal_id": "sig-1",
            "provider_used": "chatgpt",
            "model_used": "gpt-test",
            "generation_mode": "llm",
            "requested_provider": "chatgpt",
            "evidence_pack": generated["evidence_pack"],
            "updated_keys": ["signals/latest/signals.json"],
        }
        refreshed = {
            **signal,
            "status": "analyzed",
            "why_it_matters": generated["why_it_matters"],
            "relevance_to_projects": generated["relevance_to_projects"],
            "relevance_to_career": generated["relevance_to_career"],
            "synthesized_insight": generated["synthesized_insight"],
            "provider_used": "chatgpt",
            "model_used": "gpt-test",
            "generation_mode": "llm",
            "requested_provider": "chatgpt",
            "evidence_pack": generated["evidence_pack"],
        }

        with patch.object(signals_route, "find_manual_signal", return_value=None), patch.object(
            signals_route, "get_signal_by_id", side_effect=[signal, refreshed]
        ), patch.object(
            signals_route, "resolve_request_user_id", return_value=None
        ), patch.object(
            signals_route, "load_subscription_settings", return_value={}
        ), patch.object(
            signals_route, "apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch.object(
            signals_route, "generate_signal_insight", return_value=generated
        ) as generate_mock, patch.object(
            signals_route, "update_signal_insight_by_signal_id", return_value=persisted
        ), patch.object(
            signals_route, "_soft_record_generate_insight_lifecycle_events"
        ) as lifecycle_mock, patch.object(
            signals_route, "write_signal_insight_debug_record", return_value="debug.json"
        ):
            result = signals_route.generate_insight_for_signal(
                signals_route.GenerateInsightRequest(signal_id="sig-1", selected_model="chatgpt"),
                request=object(),
            )

        self.assertEqual(result["why_it_matters"], "Fresh why")
        self.assertEqual(result["evidence_pack"], generated["evidence_pack"])
        self.assertEqual(result["actual_provider"], "openai")
        self.assertEqual(result["verification"]["verification_status"], "verified_with_limitations")
        self.assertEqual(result["verified_insight_id"], "vi_auto_1")
        self.assertEqual(result["updated_keys"], ["signals/latest/signals.json"])
        generated_signal_arg = generate_mock.call_args.args[0]
        self.assertEqual(
            generated_signal_arg["source_excerpt"],
            "Original source text with claim-level support.",
        )
        self.assertEqual(generated_signal_arg["source_excerpt_length"], 46)
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "sig-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "signal")
        self.assertEqual(lifecycle_kwargs["status_before"], "saved")
        self.assertEqual(lifecycle_kwargs["status_after"], "analyzed")
        self.assertEqual(lifecycle_kwargs["verification"], generated["verification"])
        self.assertEqual(lifecycle_kwargs["generated_fingerprint"], "new-fingerprint")

    def test_generate_insight_for_manual_session_persists_evidence_pack(self):
        manual_signal = {
            "id": "manual-1",
            "signal_id": "manual-1",
            "title": "Manual Session",
            "summary": "Manual summary",
            "source": "manual",
            "status": "analyzed",
            "manual_session_id": "manual-1",
            "analysis_status": "completed",
            "why_it_matters": "Old why",
        }
        session_data = {
            "session_id": "manual-1",
            "title": "Manual Session",
            "summary": "Manual summary",
            "status": "analyzed",
            "analysis_status": "completed",
            "upload_reason": "Product review",
            "intended_use": "Project takeaway review",
            "cognitive_layer": "L2",
            "files": [
                {
                    "original_filename": "manual-note.txt",
                    "stored_filename": "manual-note.txt",
                    "file_kind": "text",
                }
            ],
            "analysis": {
                "summary": "Manual summary",
                "topic": "Manual Upload",
            },
        }
        generated = {
            "why_it_matters": "Fresh why",
            "relevance_to_projects": "Fresh projects",
            "relevance_to_career": "Fresh career",
            "synthesized_insight": "Fresh insight",
            "provider_used": "claude",
            "actual_provider": "anthropic",
            "model_used": "claude-test",
            "generation_mode": "llm",
            "requested_provider": "claude",
            "content_fingerprint": "manual-fingerprint",
            "policy_metadata": {"notes": ["Generated successfully."]},
            "verification": {
                "verification_status": "weak_evidence",
                "verified_insight_id": "vi_manual_1",
                "verified_insight": {
                    "id": "vi_manual_1",
                    "status": "weak_evidence",
                    "evidence": {"level": "insufficient"},
                    "claims": {
                        "support_summary": {"inferred": 1, "unsupported": 0},
                    },
                    "action_policy": {
                        "allowed": ["weak_insight", "watch_only"],
                        "blocked": ["decision_card"],
                    },
                    "confidence": {"score": 0.34, "label": "low"},
                },
                "allowed_downstream_actions": ["weak_insight", "watch_only"],
                "blocked_downstream_actions": ["decision_card"],
            },
            "evidence_pack": {"source_signal_id": "manual-1", "evidence_version": "v1"},
        }
        saved_payloads = []

        def capture_save(payload):
            saved_payloads.append(dict(payload))

        with patch.object(signals_route, "find_manual_signal", return_value=manual_signal), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "resolve_request_user_id", return_value=None
        ), patch.object(
            signals_route, "load_subscription_settings", return_value={}
        ), patch.object(
            signals_route, "apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch.object(
            signals_route, "generate_signal_insight", return_value=generated
        ), patch.object(
            signals_route, "save_session_detail", side_effect=capture_save
        ), patch.object(
            signals_route, "build_session_summary", return_value={}
        ), patch.object(
            signals_route, "upsert_session_index_item", return_value=None
        ), patch.object(
            signals_route, "_soft_record_generate_insight_lifecycle_events"
        ) as lifecycle_mock, patch.object(
            signals_route, "write_signal_insight_debug_record", return_value="debug.json"
        ), patch.object(
            signals_route, "utc_now_iso", return_value="2026-04-27T00:00:00Z"
        ):
            result = signals_route.generate_insight_for_signal(
                signals_route.GenerateInsightRequest(signal_id="manual_manual-1", selected_model="claude"),
                request=object(),
            )

        self.assertEqual(result["why_it_matters"], "Fresh why")
        self.assertEqual(result["evidence_pack"], generated["evidence_pack"])
        self.assertEqual(result["actual_provider"], "anthropic")
        self.assertTrue(result["is_manual"])
        self.assertEqual(result["manual_session_id"], "manual-1")
        self.assertEqual(result["analysis_status"], "completed")
        self.assertEqual(result["upload_reason"], "Product review")
        self.assertEqual(result["intended_use"], "Project takeaway review")
        self.assertEqual(result["cognitive_layer"], "L2")
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["file_types"], ["text"])
        self.assertEqual(result["files"][0]["original_filename"], "manual-note.txt")
        self.assertEqual(result["verification"]["verification_status"], "weak_evidence")
        self.assertEqual(result["verified_insight_id"], "vi_manual_1")
        self.assertEqual(result["verification"]["verified_insight"]["id"], "vi_manual_1")
        self.assertTrue(saved_payloads)
        self.assertEqual(saved_payloads[0]["evidence_pack"], generated["evidence_pack"])
        self.assertEqual(saved_payloads[0]["verification"]["verified_insight"]["status"], "weak_evidence")
        self.assertEqual(saved_payloads[0]["analysis"]["why_it_matters"], "Fresh why")
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "manual_manual-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "manual_session")
        self.assertEqual(lifecycle_kwargs["source_record_id"], "manual-1")
        self.assertEqual(lifecycle_kwargs["status_before"], "analyzed")
        self.assertEqual(lifecycle_kwargs["status_after"], "analyzed")
        self.assertEqual(lifecycle_kwargs["verification"], generated["verification"])

    def test_generate_insight_lifecycle_soft_recording_is_best_effort(self):
        with patch.object(
            signals_route,
            "build_generate_insight_events",
            return_value=[{"event_type": "insight_generated"}],
        ) as build_events, patch.object(
            signals_route,
            "append_signal_lifecycle_events",
            side_effect=RuntimeError("write failed"),
        ) as append_events:
            signals_route._soft_record_generate_insight_lifecycle_events(
                signal_id="sig-1",
                source_record_family="signal",
                source_record_id="sig-1",
                status_before="pending",
                status_after="analyzed",
                verification={"verification_status": "weak_evidence"},
                produced_by_model={"provider": "openai"},
                preexisting_fingerprint="old",
                generated_fingerprint="new",
                stored_fingerprint="new",
                fingerprint_changed=True,
                event_time="2026-05-22T00:00:00Z",
            )

        build_events.assert_called_once()
        append_events.assert_called_once_with("sig-1", [{"event_type": "insight_generated"}])

    def test_generate_insight_for_manual_session_reports_missing_llm_key(self):
        manual_signal = {
            "id": "manual-1",
            "signal_id": "manual-1",
            "title": "Manual Link Source",
            "summary": "Manual link source",
            "source": "manual",
            "status": "pending",
            "manual_session_id": "manual-1",
            "analysis_status": "not_started",
        }
        session_data = {
            "session_id": "manual-1",
            "title": "Manual Link Source",
            "summary": "Manual link source",
            "status": "pending",
            "analysis_status": "not_started",
            "files": [
                {
                    "original_filename": "manual-link-source.md",
                    "stored_filename": "manual-link-source.md",
                    "file_kind": "text",
                }
            ],
            "analysis": None,
        }

        with patch.object(signals_route, "find_manual_signal", return_value=manual_signal), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "resolve_request_user_id", return_value=None
        ), patch.object(
            signals_route, "load_subscription_settings", return_value={}
        ), patch.object(
            signals_route, "apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch.object(
            signals_route,
            "generate_signal_insight",
            side_effect=ValueError("No supported LLM API key found for signal insight generation"),
        ):
            with self.assertRaises(signals_route.HTTPException) as raised:
                signals_route.generate_insight_for_signal(
                    signals_route.GenerateInsightRequest(signal_id="manual_manual-1", selected_model="claude"),
                    request=object(),
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("Insight generation is not configured", raised.exception.detail)

    def test_generate_insight_for_auto_signal_reports_missing_selected_provider_key(self):
        signal = {
            "signal_id": "sig-1",
            "title": "Test signal",
            "summary": "Summary",
            "source": "rss",
            "status": "saved",
            "topic": "Agents",
        }

        with patch.object(signals_route, "find_manual_signal", return_value=None), patch.object(
            signals_route, "get_signal_by_id", return_value=signal
        ), patch.object(
            signals_route, "resolve_request_user_id", return_value=None
        ), patch.object(
            signals_route, "load_subscription_settings", return_value={}
        ), patch.object(
            signals_route, "apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch.object(
            signals_route,
            "generate_signal_insight",
            side_effect=ValueError("ANTHROPIC_API_KEY not found"),
        ):
            with self.assertRaises(signals_route.HTTPException) as raised:
                signals_route.generate_insight_for_signal(
                    signals_route.GenerateInsightRequest(signal_id="sig-1", selected_model="claude"),
                    request=object(),
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("Claude insight generation is not configured", raised.exception.detail)

    def test_complete_manual_signal_returns_workspace_saved_metadata(self):
        saved_session_payloads = []
        saved_record = {
            "file_name": "manual-workspace.json",
            "record": {"saved_at": "2026-05-06T01:02:03Z"},
        }
        session_data = {
            "session_id": "manual-1",
            "title": "Manual Session",
            "analysis_status": "completed",
        }

        def capture_session_save(payload):
            saved_session_payloads.append(dict(payload))

        with patch.object(signals_route, "save_reflection_to_file", return_value=saved_record) as save_workspace, patch.object(
            signals_route, "add_signal_to_project_improvements", return_value=[]
        ) as add_project_improvements, patch.object(
            signals_route, "find_manual_signal", return_value={"signal_id": "manual_manual-1"}
        ), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "save_session_detail", side_effect=capture_session_save
        ), patch.object(
            signals_route, "build_session_summary", return_value={}
        ), patch.object(
            signals_route, "upsert_session_index_item", return_value=None
        ), patch.object(
            signals_route, "_soft_record_signal_completion_lifecycle_events"
        ) as lifecycle_mock, patch.object(
            signals_route, "utc_now_iso", return_value="2026-05-06T01:03:00Z"
        ):
            result = signals_route.complete_signal(
                signals_route.CompleteSignalRequest(
                    signal_id="manual_manual-1",
                    signal_title="Manual Session",
                    topic="Manual Upload",
                    final_reflection="Ready for workspace.",
                )
            )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["workspace_saved"])
        self.assertEqual(result["workspace_file_name"], "manual-workspace.json")
        self.assertEqual(result["workspace_saved_at"], "2026-05-06T01:02:03Z")
        self.assertTrue(saved_session_payloads)
        self.assertTrue(saved_session_payloads[0]["workspace_saved"])
        self.assertTrue(saved_session_payloads[0]["completion_saved"])
        self.assertEqual(saved_session_payloads[0]["workspace_file_name"], "manual-workspace.json")
        self.assertEqual(saved_session_payloads[0]["workspace_saved_at"], "2026-05-06T01:02:03Z")
        saved_payload = save_workspace.call_args.args[0]
        self.assertEqual(saved_payload.source_type, "manual_upload")
        self.assertEqual(saved_payload.content_type, "manual_session")
        self.assertEqual(saved_payload.signal_id, "manual_manual-1")
        self.assertEqual(add_project_improvements.call_args.kwargs["signal_id"], "manual_manual-1")
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "manual_manual-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "manual_session")
        self.assertEqual(lifecycle_kwargs["source_record_id"], "manual-1")
        self.assertEqual(lifecycle_kwargs["status_before"], "analyzed")
        self.assertEqual(lifecycle_kwargs["workspace_file_name"], "manual-workspace.json")

    def test_complete_manual_signal_normalizes_unprefixed_session_id_before_writing(self):
        saved_record = {
            "file_name": "manual-workspace.json",
            "record": {"saved_at": "2026-05-06T01:02:03Z"},
        }
        session_data = {
            "session_id": "manual-1",
            "title": "Manual Session",
            "analysis_status": "completed",
        }

        with patch.object(signals_route, "save_reflection_to_file", return_value=saved_record) as save_workspace, patch.object(
            signals_route, "add_signal_to_project_improvements", return_value=[]
        ) as add_project_improvements, patch.object(
            signals_route, "find_manual_signal", return_value={"signal_id": "manual-1", "manual_session_id": "manual-1"}
        ), patch.object(
            signals_route, "load_session_detail", return_value=session_data
        ), patch.object(
            signals_route, "save_session_detail", return_value=None
        ), patch.object(
            signals_route, "build_session_summary", return_value={}
        ), patch.object(
            signals_route, "upsert_session_index_item", return_value=None
        ), patch.object(
            signals_route, "_soft_record_signal_completion_lifecycle_events"
        ) as lifecycle_mock, patch.object(
            signals_route, "utc_now_iso", return_value="2026-05-06T01:03:00Z"
        ):
            result = signals_route.complete_signal(
                signals_route.CompleteSignalRequest(
                    signal_id="manual-1",
                    signal_title="Manual Session",
                    topic="Manual Upload",
                    final_reflection="Ready for workspace.",
                )
            )

        self.assertEqual(result["status"], "completed")
        saved_payload = save_workspace.call_args.args[0]
        self.assertEqual(saved_payload.source_type, "manual_upload")
        self.assertEqual(saved_payload.content_type, "manual_session")
        self.assertEqual(saved_payload.signal_id, "manual_manual-1")
        self.assertEqual(add_project_improvements.call_args.kwargs["signal_id"], "manual_manual-1")
        self.assertEqual(lifecycle_mock.call_args.kwargs["signal_id"], "manual_manual-1")

    def test_complete_automatic_signal_records_completion_lifecycle_softly(self):
        saved_record = {
            "file_name": "workspace.json",
            "record": {"saved_at": "2026-05-06T01:02:03Z"},
        }
        project_improvements = [
            {
                "project_id": "ai_radar",
                "signal_id": "sig-1",
                "status": "new",
            }
        ]

        with patch.object(signals_route, "save_reflection_to_file", return_value=saved_record), patch.object(
            signals_route, "add_signal_to_project_improvements", return_value=project_improvements
        ), patch.object(
            signals_route, "find_manual_signal", return_value=None
        ), patch.object(
            signals_route, "update_signal_status_by_signal_id", return_value={"updated_keys": ["signals/latest/signals.json"]}
        ), patch.object(
            signals_route, "_soft_record_signal_completion_lifecycle_events"
        ) as lifecycle_mock:
            result = signals_route.complete_signal(
                signals_route.CompleteSignalRequest(
                    signal_id="sig-1",
                    signal_title="Signal",
                    topic="Signal",
                    final_reflection="Ready for workspace.",
                    verification_metadata={"verification_status": "needs_human_review"},
                )
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["updated_keys"], ["signals/latest/signals.json"])
        lifecycle_mock.assert_called_once()
        lifecycle_kwargs = lifecycle_mock.call_args.kwargs
        self.assertEqual(lifecycle_kwargs["signal_id"], "sig-1")
        self.assertEqual(lifecycle_kwargs["source_record_family"], "signal")
        self.assertEqual(lifecycle_kwargs["source_record_id"], "sig-1")
        self.assertEqual(lifecycle_kwargs["status_before"], "")
        self.assertEqual(lifecycle_kwargs["verification"], {"verification_status": "needs_human_review"})
        self.assertEqual(lifecycle_kwargs["project_improvements"], project_improvements)

    def test_signal_completion_lifecycle_soft_recording_is_best_effort(self):
        with patch.object(
            signals_route,
            "build_signal_completion_events",
            return_value=[{"event_type": "workspace_completed"}],
        ) as build_events, patch.object(
            signals_route,
            "append_signal_lifecycle_events",
            side_effect=RuntimeError("write failed"),
        ) as append_events:
            signals_route._soft_record_signal_completion_lifecycle_events(
                signal_id="sig-1",
                source_record_family="signal",
                source_record_id="sig-1",
                status_before="analyzed",
                verification={"verification_status": "needs_human_review"},
                workspace_file_name="workspace.json",
                workspace_saved_at="2026-05-06T01:02:03Z",
                project_improvements=[],
                event_time="2026-05-23T00:00:00Z",
            )

        build_events.assert_called_once()
        append_events.assert_called_once_with("sig-1", [{"event_type": "workspace_completed"}])


class AgentWatchTrackingStateTests(unittest.TestCase):
    def test_tracking_index_prefers_canonical_tracking_state_status(self):
        snapshots = [
            {
                "entity_id": "https://github.com/example/agentkit",
                "captured_at": "2026-05-30T00:00:00+00:00",
                "agent_watch_score": 0.6,
            },
            {
                "entity_id": "https://github.com/example/agentkit",
                "captured_at": "2026-05-31T00:00:00+00:00",
                "agent_watch_score": 0.61,
            },
        ]
        tracking_state = {
            "items": [
                {
                    "entity_id": "https://github.com/example/agentkit",
                    "status": "heating",
                    "first_seen_at": "2026-05-30T00:00:00+00:00",
                    "last_seen_at": "2026-06-01T00:00:00+00:00",
                    "seen_days": 3,
                    "current_score": 0.72,
                    "previous_score": 0.61,
                    "score_delta_1d": 0.11,
                    "metric_delta_1d": 80,
                }
            ]
        }

        with patch.object(
            s3_reader,
            "_load_agent_watch_repo_snapshot_history",
            return_value=snapshots,
        ), patch.object(
            s3_reader,
            "_load_agent_watch_tracking_state",
            return_value=tracking_state,
        ):
            index = s3_reader._build_agent_watch_tracking_index(use_local=True)

        tracking = index["https://github.com/example/agentkit"]
        self.assertEqual(tracking["status"], "heating")
        self.assertEqual(tracking["first_seen"], "2026-05-30T00:00:00+00:00")
        self.assertEqual(tracking["last_seen"], "2026-06-01T00:00:00+00:00")
        self.assertEqual(tracking["days_observed"], 3)
        self.assertEqual(tracking["latest_score"], 0.72)
        self.assertEqual(tracking["score_change"], 0.11)
        self.assertEqual(tracking["metric_delta_1d"], 80)

    def test_friction_tracking_index_normalizes_canonical_state_fields(self):
        tracking_state = {
            "items": [
                {
                    "entity_id": "https://github.com/example/project/issues/1",
                    "status": "heating",
                    "first_seen_at": "2026-05-30T00:00:00+00:00",
                    "last_seen_at": "2026-06-01T00:00:00+00:00",
                    "seen_days": 3,
                    "current_score": 0.82,
                    "previous_score": 0.71,
                    "score_delta_1d": 0.11,
                    "metric_delta_1d": 8,
                    "pain_cluster_key": "reliability:example/project",
                }
            ]
        }

        with patch.object(
            s3_reader,
            "_load_friction_tracking_state",
            return_value=tracking_state,
        ):
            index = s3_reader._build_friction_tracking_index(use_local=True)

        tracking = index["https://github.com/example/project/issues/1"]
        self.assertEqual(tracking["status"], "heating")
        self.assertEqual(tracking["first_seen"], "2026-05-30T00:00:00+00:00")
        self.assertEqual(tracking["last_seen"], "2026-06-01T00:00:00+00:00")
        self.assertEqual(tracking["days_observed"], 3)
        self.assertEqual(tracking["latest_score"], 0.82)
        self.assertEqual(tracking["score_change"], 0.11)
        self.assertEqual(tracking["metric_delta_1d"], 8)
        self.assertEqual(tracking["pain_cluster_key"], "reliability:example/project")

    def test_friction_signals_loader_enriches_items_with_tracking_state(self):
        payload = {
            "generated_at": "2026-06-03T00:00:00+00:00",
            "signals": [
                {
                    "title": "Agent workflow fails on auth",
                    "url": "https://github.com/example/project/issues/1",
                    "source": "github",
                    "friction_score": 0.8,
                }
            ],
            "summary": {
                "signal_count": 1,
                "highlights": [
                    {
                        "title": "Agent workflow fails on auth",
                        "url": "https://github.com/example/project/issues/1",
                    }
                ],
            },
        }
        tracking_index = {
            "https://github.com/example/project/issues/1": {
                "status": "heating",
                "first_seen": "2026-05-30T00:00:00+00:00",
                "last_seen": "2026-06-01T00:00:00+00:00",
                "days_observed": 3,
                "latest_score": 0.82,
                "score_change": 0.11,
                "metric_delta_1d": 8,
            }
        }

        with patch.object(s3_reader, "read_json", return_value=payload), patch.object(
            s3_reader,
            "_load_friction_signals_fallback",
            return_value={},
        ), patch.object(
            s3_reader,
            "_load_friction_signal_profiles",
            return_value={},
        ), patch.object(
            s3_reader,
            "_build_friction_tracking_index",
            return_value=tracking_index,
        ):
            result = s3_reader.load_friction_signals(force_refresh=True, use_local=False)

        self.assertEqual(result["signals"][0]["tracking"]["status"], "heating")
        self.assertEqual(result["signals"][0]["tracking"]["days_observed"], 3)
        self.assertEqual(result["summary"]["highlights"][0]["tracking"]["metric_delta_1d"], 8)


class S3ReaderCacheInvalidationTests(unittest.TestCase):
    def setUp(self):
        s3_reader.INSIGHTS_CACHE["data"] = {"stale": True}
        s3_reader.INSIGHTS_CACHE["last_loaded"] = 123
        s3_reader.RADAR_CACHE["data"] = {"stale": True}
        s3_reader.RADAR_CACHE["last_loaded"] = 123
        s3_reader.RADAR_INTELLIGENCE_CACHE["data"] = {"stale": True}
        s3_reader.RADAR_INTELLIGENCE_CACHE["last_loaded"] = 123

    def test_update_signal_status_invalidates_radar_caches(self):
        updated_item = {"signal_id": "sig-1", "status": "pending"}

        def update_documents(*, signal_id, update_fn, fallback_scan_all=True):
            self.assertEqual(signal_id, "sig-1")
            update_fn(updated_item)
            return ["signals/latest/signals.json"]

        with patch.object(
            s3_reader,
            "_update_signal_documents",
            side_effect=update_documents,
        ), patch.object(
            s3_reader,
            "_refresh_signals_after_targeted_update",
        ) as refresh_mock:
            result = s3_reader.update_signal_status_by_signal_id("sig-1", "saved", "reason")

        self.assertEqual(result["signal_id"], "sig-1")
        self.assertEqual(updated_item["status"], "saved")
        self.assertEqual(updated_item["decision_trace"][0]["event_type"], "operator_saved_for_later")
        self.assertEqual(updated_item["decision_trace"][0]["status_before"], "pending")
        self.assertEqual(updated_item["decision_trace"][0]["status_after"], "saved")
        self.assertEqual(updated_item["decision_trace"][0]["support"]["saved_reason"], "reason")
        self.assertIsNone(s3_reader.RADAR_CACHE["data"])
        self.assertIsNone(s3_reader.RADAR_INTELLIGENCE_CACHE["data"])
        refresh_mock.assert_called_once()
        self.assertEqual(refresh_mock.call_args.args[0], "sig-1")

    def test_update_signal_insight_appends_generation_trace(self):
        updated_item = {"signal_id": "sig-2", "status": "pending"}
        produced_by_model = {
            "provider": "openai",
            "model_id": "gpt-test",
            "provenance_schema_version": 1,
        }

        def update_documents(*, signal_id, update_fn, fallback_scan_all=True):
            self.assertEqual(signal_id, "sig-2")
            update_fn(updated_item)
            return ["signals/latest/signals.json"]

        with patch.object(
            s3_reader,
            "_update_signal_documents",
            side_effect=update_documents,
        ), patch.object(s3_reader, "load_signals", return_value=[]):
            s3_reader.update_signal_insight_by_signal_id(
                "sig-2",
                {
                    "why_it_matters": "why",
                    "relevance_to_projects": "projects",
                    "relevance_to_career": "career",
                    "synthesized_insight": "insight",
                    "verification": {
                        "verification_status": "partially_verified",
                        "blocked_downstream_actions": ["low_risk_action_candidate"],
                    },
                    "produced_by_model": produced_by_model,
                },
            )

        self.assertEqual(updated_item["produced_by_model"], produced_by_model)
        trace_event = updated_item["decision_trace"][0]
        self.assertEqual(trace_event["event_type"], "insight_generated")
        self.assertEqual(trace_event["status_before"], "pending")
        self.assertEqual(trace_event["status_after"], "analyzed")
        self.assertEqual(trace_event["support"]["verification_status"], "partially_verified")
        self.assertEqual(trace_event["support"]["blocked_downstream_actions"], ["low_risk_action_candidate"])

    def test_update_signal_insight_invalidates_related_caches(self):
        with patch.object(
            s3_reader,
            "_update_signal_documents",
            return_value=["signals/latest/signals.json"],
        ), patch.object(
            s3_reader,
            "_refresh_signals_after_targeted_update",
        ) as refresh_mock:
            result = s3_reader.update_signal_insight_by_signal_id(
                "sig-2",
                {
                    "why_it_matters": "why",
                    "relevance_to_projects": "projects",
                    "relevance_to_career": "career",
                    "synthesized_insight": "insight",
                },
            )

        self.assertEqual(result["signal_id"], "sig-2")
        self.assertIsNone(s3_reader.INSIGHTS_CACHE["data"])
        self.assertIsNone(s3_reader.RADAR_CACHE["data"])
        self.assertIsNone(s3_reader.RADAR_INTELLIGENCE_CACHE["data"])
        refresh_mock.assert_called_once()
        self.assertEqual(refresh_mock.call_args.args[0], "sig-2")

    def test_update_signal_insight_returns_evidence_pack_when_present(self):
        evidence_pack = {"source_signal_id": "sig-2", "evidence_version": "v1"}
        with patch.object(
            s3_reader,
            "_update_signal_documents",
            return_value=["signals/latest/signals.json"],
        ), patch.object(s3_reader, "load_signals", return_value=[]):
            result = s3_reader.update_signal_insight_by_signal_id(
                "sig-2",
                {
                    "why_it_matters": "why",
                    "relevance_to_projects": "projects",
                    "relevance_to_career": "career",
                    "synthesized_insight": "insight",
                    "evidence_pack": evidence_pack,
                },
            )

        self.assertEqual(result["evidence_pack"], evidence_pack)


if __name__ == "__main__":
    unittest.main()
