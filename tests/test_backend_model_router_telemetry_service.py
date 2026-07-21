import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import model_router_telemetry_service as telemetry_service  # noqa: E402


class BackendModelRouterTelemetryServiceTests(unittest.TestCase):
    def test_refresh_summary_builds_time_windows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            events_path = temp_root / "events.jsonl"
            summary_path = temp_root / "summary.json"
            now = datetime.now(timezone.utc).replace(microsecond=0)

            payloads = [
                {
                    "timestamp": now.isoformat(),
                    "task_type": "insight",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "tier": "tier_2_structured",
                    "mode": "text_json",
                    "outcome": "success",
                    "fallback_used": False,
                },
                {
                    "timestamp": (now - timedelta(days=2)).isoformat(),
                    "task_type": "manual_text",
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "tier": "tier_2_structured",
                    "mode": "text_json",
                    "outcome": "failure",
                    "fallback_used": True,
                },
                {
                    "timestamp": (now - timedelta(days=8)).isoformat(),
                    "task_type": "workspace_chat",
                    "provider": "perplexity",
                    "model": "sonar-pro",
                    "tier": "tier_2_structured",
                    "mode": "text",
                    "outcome": "success",
                    "fallback_used": False,
                },
            ]
            events_path.write_text(
                "\n".join(json.dumps(item) for item in payloads) + "\n",
                encoding="utf-8",
            )

            with patch.object(telemetry_service, "TELEMETRY_EVENTS_PATH", events_path), patch.object(
                telemetry_service, "TELEMETRY_SUMMARY_PATH", summary_path
            ):
                telemetry_service._refresh_summary()
                summary = telemetry_service.load_route_summary()

        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["time_windows"]["24h"]["total_events"], 1)
        self.assertEqual(summary["time_windows"]["24h"]["providers"]["anthropic"], 1)
        self.assertEqual(summary["time_windows"]["7d"]["total_events"], 2)
        self.assertEqual(summary["time_windows"]["7d"]["failure_count"], 1)
        self.assertEqual(summary["time_windows"]["7d"]["fallback_count"], 1)


if __name__ == "__main__":
    unittest.main()
