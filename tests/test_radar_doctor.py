import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.radar_doctor import (  # noqa: E402
    build_radar_doctor_report,
    radar_doctor_exit_code,
)


class RadarDoctorTests(unittest.TestCase):
    def test_doctor_aggregates_read_only_operational_and_scalar_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            signal_path = root / "signals.json"
            signal_path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "id": "partial",
                                "title": "example/partial",
                                "url": "https://github.com/example/partial",
                                "source": "github",
                                "published_at": "2026-06-01T00:00:00Z",
                                "metadata": {
                                    "repo_name": "example/partial",
                                    "repo_stars": 50,
                                    "created_at": "2026-06-01T00:00:00Z",
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_dir = root / "settings"
            settings_dir.mkdir()
            (settings_dir / "admin_default.json").write_text(
                json.dumps(
                    {
                        "user_id": "admin_default",
                        "sources": [
                            {
                                "id": "rss",
                                "name": "RSS",
                                "type": "rss",
                                "url": "https://example.com/feed.xml",
                                "enabled": True,
                            },
                            {
                                "id": "disabled",
                                "name": "Disabled",
                                "type": "custom_url",
                                "url": "https://example.com/",
                                "enabled": False,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "scripts.radar_doctor.router_startup_diagnostics",
                return_value={
                    "routes": {"insight": {"provider": "openai", "model": "gpt-5.5"}},
                    "warnings": ["example model warning"],
                },
            ), patch(
                "scripts.radar_doctor.load_route_summary",
                return_value={
                    "total_events": 3,
                    "last_event_at": "2026-06-24T00:00:00+00:00",
                    "success_rate": 0.667,
                    "failure_rate": 0.333,
                    "fallback_count": 1,
                    "time_windows": {},
                },
            ):
                report = build_radar_doctor_report(
                    root=root,
                    signal_files=[signal_path],
                    subscription_settings_dir=settings_dir,
                    user_id="admin_default",
                    source_health_fetcher=lambda _: (_ for _ in ()).throw(AssertionError("source probe should be skipped")),
                    github_fetcher=lambda _: (_ for _ in ()).throw(AssertionError("github probe should be skipped")),
                )

        self.assertEqual(report["report_boundary"]["mode"], "read_only_local_doctor")
        self.assertIn("does not write", report["report_boundary"]["write_boundary"])
        self.assertIn("skipped by default", report["report_boundary"]["network_boundary"])
        self.assertIn("not source scoring", report["report_boundary"]["quality_boundary"])
        self.assertEqual(report["summary"]["overall_status"], "warning")
        self.assertEqual(report["model_router"]["route_count"], 1)
        self.assertEqual(report["model_router"]["telemetry"]["total_events"], 3)
        self.assertEqual(report["sources"]["subscription_settings"]["source_count"], 2)
        self.assertEqual(report["sources"]["subscription_settings"]["enabled_source_count"], 1)
        self.assertEqual(report["sources"]["signal_outputs"]["summary"]["readable_json_files"], 1)
        self.assertEqual(report["github_scalars"]["coverage"]["summary"]["github_record_count"], 1)
        self.assertEqual(report["sources"]["live_source_probe"]["status"], "skipped")
        self.assertEqual(report["sources"]["live_source_probe"]["github_api"]["status"], "skipped")
        self.assertEqual(
            report["github_scalars"]["coverage"]["summary"]["rows_with_scalar_mismatch"],
            0,
        )
        self.assertNotIn("records", report["github_scalars"]["coverage"])
        self.assertEqual(radar_doctor_exit_code(report), 0)
        self.assertEqual(radar_doctor_exit_code(report, fail_on_warning=True), 1)

    def test_doctor_reports_credential_presence_without_secret_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            signal_path = root / "signals.json"
            signal_path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            settings_dir = root / "settings"
            settings_dir.mkdir()
            (settings_dir / "admin_default.json").write_text(
                json.dumps({"sources": []}),
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "sk-secret-value",
                    "GITHUB_TOKEN": "ghp-secret-value",
                },
                clear=False,
            ), patch(
                "scripts.radar_doctor.router_startup_diagnostics",
                return_value={"routes": {}, "warnings": []},
            ), patch(
                "scripts.radar_doctor.load_route_summary",
                return_value={"total_events": 0, "fallback_count": 0, "time_windows": {}},
            ):
                report = build_radar_doctor_report(
                    root=root,
                    signal_files=[signal_path],
                    subscription_settings_dir=settings_dir,
                    user_id="admin_default",
                )

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertTrue(report["model_router"]["credential_env_presence"]["OPENAI_API_KEY"])
        self.assertTrue(report["github_scalars"]["credential_env_presence"]["GITHUB_TOKEN"])
        self.assertNotIn("sk-secret-value", serialized)
        self.assertNotIn("ghp-secret-value", serialized)

    def test_live_source_probe_is_explicit_and_uses_injected_fetchers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            signal_path = root / "signals.json"
            signal_path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            settings_dir = root / "settings"
            settings_dir.mkdir()
            (settings_dir / "admin_default.json").write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "feed",
                                "name": "Feed",
                                "type": "rss",
                                "url": "https://example.com/feed.xml",
                                "enabled": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "scripts.radar_doctor.router_startup_diagnostics",
                return_value={"routes": {}, "warnings": []},
            ), patch(
                "scripts.radar_doctor.load_route_summary",
                return_value={"total_events": 0, "fallback_count": 0, "time_windows": {}},
            ):
                report = build_radar_doctor_report(
                    root=root,
                    signal_files=[signal_path],
                    subscription_settings_dir=settings_dir,
                    user_id="admin_default",
                    live_source_probe=True,
                    source_health_fetcher=lambda _: (
                        200,
                        "application/rss+xml",
                        b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title><item><title>A</title></item></channel></rss>""",
                    ),
                    github_fetcher=lambda _: (200, "application/json", b"{}"),
                )

        live_probe = report["sources"]["live_source_probe"]
        self.assertEqual(live_probe["status"], "ok")
        self.assertEqual(live_probe["mode"], "explicit_live_probe")
        self.assertEqual(live_probe["summary"]["source_probe_count"], 1)
        self.assertTrue(live_probe["summary"]["github_api_checked"])
        self.assertEqual(live_probe["subscription_source_health"]["summary"]["ok"], 1)
        self.assertEqual(live_probe["github_api"]["status"], "ok")
        self.assertEqual(report["summary"]["section_statuses"]["live_source_probe"], "ok")

    def test_live_source_probe_surfaces_advisory_warnings_without_secret_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            signal_path = root / "signals.json"
            signal_path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            settings_dir = root / "settings"
            settings_dir.mkdir()
            (settings_dir / "admin_default.json").write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "feed",
                                "name": "Feed",
                                "type": "rss",
                                "url": "https://example.com/feed.xml",
                                "enabled": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp-secret-value"}, clear=False), patch(
                "scripts.radar_doctor.router_startup_diagnostics",
                return_value={"routes": {}, "warnings": []},
            ), patch(
                "scripts.radar_doctor.load_route_summary",
                return_value={"total_events": 0, "fallback_count": 0, "time_windows": {}},
            ):
                report = build_radar_doctor_report(
                    root=root,
                    signal_files=[signal_path],
                    subscription_settings_dir=settings_dir,
                    user_id="admin_default",
                    live_source_probe=True,
                    source_health_fetcher=lambda _: (500, "text/html", b"<html>down</html>"),
                    github_fetcher=lambda _: (403, "application/json", b"{}"),
                )

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["sources"]["live_source_probe"]["status"], "warning")
        self.assertEqual(report["sources"]["live_source_probe"]["github_api"]["reason_code"], "http_403")
        self.assertGreater(report["summary"]["warning_count"], 0)
        self.assertNotIn("ghp-secret-value", serialized)


if __name__ == "__main__":
    unittest.main()
