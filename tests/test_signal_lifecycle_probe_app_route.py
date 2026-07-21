import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

backend_root_text = str(BACKEND_ROOT)
if backend_root_text in sys.path:
    sys.path.remove(backend_root_text)
sys.path.insert(0, backend_root_text)

existing_app = sys.modules.get("app")
existing_app_file = Path(str(getattr(existing_app, "__file__", ""))).resolve() if existing_app else None
if existing_app_file and not str(existing_app_file).startswith(str(BACKEND_ROOT.resolve())):
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]


from app.main import app  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402


class SignalLifecycleProbeAppRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_signal_lifecycle_probe_route_is_admin_only(self):
        with patch("app.routes.signals.get_signal_by_id") as get_signal:
            response = TestClient(app).get("/signals/sig-1/lifecycle-probe")

        self.assertEqual(response.status_code, 401)
        get_signal.assert_not_called()

    def test_signal_lifecycle_summary_route_is_admin_only(self):
        with patch("app.routes.signals.summarize_signal_lifecycle_store") as summarize:
            response = TestClient(app).get("/signals/lifecycle-summary")

        self.assertEqual(response.status_code, 401)
        summarize.assert_not_called()

    def test_signal_near_duplicates_route_is_admin_only(self):
        with patch("app.routes.signals.build_signal_near_duplicate_report") as build_report:
            response = TestClient(app).get("/signals/near-duplicates")

        self.assertEqual(response.status_code, 401)
        build_report.assert_not_called()

    def test_signal_lifecycle_summary_route_returns_local_soft_event_summary(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        summary = {
            "schema_version": 1,
            "storage": "local_file",
            "authoritative": False,
            "event_count": 2,
            "event_types": {"insight_generated": 1, "verification_completed": 1},
            "recent_events": [],
        }

        with patch("app.routes.signals.summarize_signal_lifecycle_store", return_value=summary) as summarize:
            response = TestClient(app).get("/signals/lifecycle-summary?limit=3")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "signal lifecycle summary loaded successfully")
        self.assertEqual(body["storage"], "local_file")
        self.assertFalse(body["authoritative"])
        self.assertEqual(body["event_count"], 2)
        summarize.assert_called_once_with(recent_limit=3)

    def test_signal_near_duplicates_route_returns_read_only_diagnostics(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        report = {
            "schema_version": "signal_near_duplicate_report.v1",
            "report_boundary": {
                "mode": "read_only_local_signal_output_check",
                "writes_data": False,
                "runs_ingestion": False,
                "deduplicates_records": False,
                "hard_enforcement": False,
            },
            "summary": {
                "duplicate_group_count": 1,
                "cleanup_recommendation_counts": {
                    "prefer_canonical_for_display_and_insight_generation": 1,
                },
                "groups_requiring_human_review": 0,
            },
            "groups": [{"duplicate_type": "category_vs_article"}],
        }

        with patch("app.routes.signals.build_signal_near_duplicate_report", return_value=report) as build_report:
            response = TestClient(app).get("/signals/near-duplicates?summary_only=true")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "signal near-duplicate diagnostics loaded successfully")
        self.assertEqual(body["schema_version"], "signal_near_duplicate_report.v1")
        self.assertFalse(body["report_boundary"]["writes_data"])
        self.assertEqual(body["summary"]["duplicate_group_count"], 1)
        build_report.assert_called_once_with(include_records=False)

    def test_signal_lifecycle_probe_route_joins_project_records_by_signal_aliases(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        signal = {
            "signal_id": "sig-1",
            "title": "Signal",
            "source": "rss",
            "status": "analyzed",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }

        with patch("app.routes.signals.get_signal_by_id", return_value=signal), patch(
            "app.routes.signals.resolve_request_user_id", return_value=None
        ), patch("app.routes.signals.load_subscription_settings", return_value={}), patch(
            "app.routes.signals.apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch(
            "app.routes.signals.find_manual_signal", return_value=None
        ), patch(
            "app.routes.signals.list_project_review_records",
            return_value=[
                {
                    "id": "prv_1",
                    "project_id": "ai_radar",
                    "signal_id": "sig-1",
                    "outcome": "watch",
                    "reviewed_at": "2026-05-06T08:00:00+00:00",
                }
            ],
        ) as list_records, patch(
            "app.routes.signals.list_project_calibration_events", return_value=[]
        ), patch(
            "app.routes.signals.load_signal_lifecycle_events", return_value=[]
        ):
            response = TestClient(app).get("/signals/sig-1/lifecycle-probe")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["signal_id"], "sig-1")
        self.assertFalse(body["authoritative"])
        self.assertEqual(body["project_context"]["review_records_count"], 1)
        self.assertEqual(body["message"], "signal lifecycle probe loaded successfully")
        steps = {step["step_id"]: step for step in body["steps"]}
        self.assertEqual(steps["project_fanout"]["provenance"], "derived")
        self.assertEqual(steps["project_fanout"]["source"], "derived_lifecycle_event")
        self.assertIn("signal_lifecycle.project_review_attached", body["gap_report"]["direct_fields"])
        self.assertIn("sig-1", {call.kwargs["signal_id"] for call in list_records.call_args_list})

    def test_signal_lifecycle_probe_route_supports_manual_signal_alias(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        manual_signal = {
            "signal_id": "session-1",
            "id": "session-1",
            "manual_session_id": "session-1",
            "title": "Manual",
            "source": "manual",
            "status": "analyzed",
            "analysis_status": "completed",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }

        with patch("app.routes.signals.get_signal_by_id", return_value=None), patch(
            "app.routes.signals.find_manual_signal", return_value=manual_signal
        ), patch(
            "app.routes.signals.list_project_review_records", return_value=[]
        ) as list_records, patch(
            "app.routes.signals.list_project_calibration_events", return_value=[]
        ), patch(
            "app.routes.signals.load_signal_lifecycle_events", return_value=[]
        ):
            response = TestClient(app).get("/signals/session-1/lifecycle-probe")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["is_manual"])
        queried_aliases = {call.kwargs["signal_id"] for call in list_records.call_args_list}
        self.assertIn("session-1", queried_aliases)
        self.assertIn("manual_session-1", queried_aliases)

    def test_signal_lifecycle_probe_route_loads_direct_lifecycle_events_for_aliases(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        signal = {
            "signal_id": "sig-1",
            "title": "Signal",
            "source": "rss",
            "status": "saved",
            "saved_reason": "Review later",
            "why_it_matters": "Why",
            "verification": {"verification_status": "partially_verified"},
        }

        def lifecycle_events(signal_id):
            if signal_id == "sig-1":
                return [
                    {
                        "event_id": "sig_evt_1",
                        "event_type": "signal_status_changed",
                        "event_time": "2026-05-23T00:00:00+00:00",
                        "actor": {"type": "system", "id": "ai-radar-backend"},
                        "state": {"before": "pending", "after": "saved"},
                        "support": {"saved_reason": "Review later"},
                    }
                ]
            return []

        with patch("app.routes.signals.get_signal_by_id", return_value=signal), patch(
            "app.routes.signals.resolve_request_user_id", return_value=None
        ), patch("app.routes.signals.load_subscription_settings", return_value={}), patch(
            "app.routes.signals.apply_subscription_settings_to_signals", side_effect=lambda items, _: items
        ), patch(
            "app.routes.signals.find_manual_signal", return_value=None
        ), patch(
            "app.routes.signals.list_project_review_records", return_value=[]
        ), patch(
            "app.routes.signals.list_project_calibration_events", return_value=[]
        ), patch(
            "app.routes.signals.load_signal_lifecycle_events", side_effect=lifecycle_events
        ) as load_events:
            response = TestClient(app).get("/signals/sig-1/lifecycle-probe")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        steps = {step["step_id"]: step for step in body["steps"]}
        self.assertEqual(steps["signal_decision"]["source"], "signal_lifecycle_event")
        self.assertEqual(steps["signal_decision"]["provenance"], "direct")
        self.assertIn("sig-1", {call.args[0] for call in load_events.call_args_list})


if __name__ == "__main__":
    unittest.main()
