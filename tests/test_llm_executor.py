import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence import llm_executor  # noqa: E402


class LLMExecutorTests(unittest.TestCase):
    def setUp(self):
        self.metrics_patcher = patch.object(llm_executor, "record_llm_call")
        self.mock_record_llm_call = self.metrics_patcher.start()
        self.route_event_patcher = patch.object(llm_executor, "record_route_event")
        self.mock_record_route_event = self.route_event_patcher.start()

    def tearDown(self):
        self.route_event_patcher.stop()
        self.metrics_patcher.stop()

    def test_openai_json_mode_returns_parsed_payload(self):
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content='{"summary":"ok"}')
                            )
                        ]
                    )
                )
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "openai",
                "MODEL_ROUTER_TIER2_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ), patch.object(llm_executor, "_openai_client", return_value=mock_client):
            result = llm_executor.execute_routed_task(
                task_type="structure",
                messages=[{"role": "user", "content": "hello"}],
                json_mode=True,
            )

        self.assertEqual(result.route.provider, "openai")
        self.assertEqual(result.parsed_json, {"summary": "ok"})
        self.mock_record_llm_call.assert_called_once()
        metric = self.mock_record_llm_call.call_args.args[0]
        self.assertEqual(metric["task_type"], "structure")
        self.assertEqual(metric["provider"], "openai")
        self.assertEqual(metric["mode"], "json")
        self.assertTrue(metric["success"])
        self.assertTrue(metric["json_validation_passed"])

    def test_openai_gpt5_omits_temperature(self):
        captured_kwargs = {}

        def create_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"summary":"ok"}')
                    )
                ]
            )

        mock_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion)
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "openai",
                "MODEL_ROUTER_TIER2_MODEL": "gpt-5.5",
            },
            clear=False,
        ), patch.object(llm_executor, "_openai_client", return_value=mock_client):
            result = llm_executor.execute_routed_task(
                task_type="structure",
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.2,
                json_mode=True,
            )

        self.assertEqual(result.route.provider, "openai")
        self.assertEqual(result.route.model, "gpt-5.5")
        self.assertEqual(result.parsed_json, {"summary": "ok"})
        self.assertNotIn("temperature", captured_kwargs)

    def test_openai_standard_model_keeps_temperature(self):
        captured_kwargs = {}

        def create_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"summary":"ok"}')
                    )
                ]
            )

        mock_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion)
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "openai",
                "MODEL_ROUTER_TIER2_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ), patch.object(llm_executor, "_openai_client", return_value=mock_client):
            result = llm_executor.execute_routed_task(
                task_type="structure",
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.2,
                json_mode=True,
            )

        self.assertEqual(result.route.provider, "openai")
        self.assertEqual(result.route.model, "gpt-4.1-mini")
        self.assertEqual(result.parsed_json, {"summary": "ok"})
        self.assertEqual(captured_kwargs["temperature"], 0.2)

    def test_anthropic_text_mode_returns_joined_text(self):
        mock_response = SimpleNamespace(
            content=[
                SimpleNamespace(text="first line"),
                SimpleNamespace(text="second line"),
            ]
        )
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kwargs: mock_response)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER3_PROVIDER": "anthropic",
                "MODEL_ROUTER_TIER3_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ), patch.object(llm_executor, "_anthropic_client", return_value=mock_client):
            result = llm_executor.execute_routed_task(
                task_type="strategy",
                messages=[
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "hello"},
                ],
                json_mode=False,
            )

        self.assertEqual(result.route.provider, "anthropic")
        self.assertEqual(result.raw_text, "first line\nsecond line")
        self.mock_record_llm_call.assert_called_once()
        metric = self.mock_record_llm_call.call_args.args[0]
        self.assertEqual(metric["task_type"], "strategy")
        self.assertEqual(metric["provider"], "anthropic")
        self.assertEqual(metric["mode"], "text")
        self.assertTrue(metric["success"])
        self.assertIsNone(metric["json_validation_passed"])

    def test_anthropic_opus_47_omits_temperature(self):
        captured_kwargs = []
        mock_response = SimpleNamespace(content=[SimpleNamespace(text='{"ok": true}')])
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(
                create=lambda **kwargs: captured_kwargs.append(kwargs) or mock_response
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_ANALYSIS_PROVIDER": "anthropic",
                "MODEL_ROUTER_TIER2_MODEL": "claude-opus-4-7",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ), patch.object(llm_executor, "_anthropic_client", return_value=mock_client):
            result = llm_executor.execute_routed_task(
                task_type="structure",
                messages=[
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "hello"},
                ],
                json_mode=True,
            )

        self.assertEqual(result.route.provider, "anthropic")
        self.assertEqual(result.route.model, "claude-opus-4-7")
        self.assertEqual(result.parsed_json, {"ok": True})
        self.assertNotIn("temperature", captured_kwargs[0])


class IngestionLLMReportingDateTests(unittest.TestCase):
    def test_daily_summary_counts_success_and_failure_on_the_pipeline_local_date(self):
        from backend.app.services import metrics_event_service, metrics_summary_service

        test_root = REPO_ROOT / ".tmp-tests"
        test_root.mkdir(exist_ok=True)
        cases = [
            ("2026-09-21T22:00:00+00:00", "Australia/Sydney", "2026-09-22"),
            ("2026-10-04T21:00:00+00:00", "Australia/Sydney", "2026-10-05"),
            ("2026-09-21T22:00:00+00:00", "UTC", "2026-09-21"),
            ("2026-09-21T02:00:00+00:00", "America/New_York", "2026-09-20"),
        ]
        route = llm_executor.ModelRoute("insight", "tier_2_structured", "openai", "mock-model", "test")
        for timestamp, timezone_name, reporting_date in cases:
            instant = datetime.fromisoformat(timestamp)

            class FrozenDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return instant.astimezone(tz)

            for success in (True, False):
                with self.subTest(timezone=timezone_name, timestamp=timestamp, success=success), tempfile.TemporaryDirectory(dir=test_root) as folder:
                    metrics_dir = Path(folder)
                    audit_time = instant.isoformat().replace("+00:00", "Z")

                    def record(event):
                        return metrics_event_service.record_llm_call(event, metrics_dir=metrics_dir)

                    with patch.object(llm_executor, "datetime", FrozenDateTime, create=True), patch.object(
                        llm_executor, "settings", SimpleNamespace(timezone=ZoneInfo(timezone_name)), create=True
                    ), patch.object(llm_executor, "record_llm_call", side_effect=record), patch.object(
                        metrics_event_service, "utc_now_iso", return_value=audit_time
                    ):
                        llm_executor._record_llm_metric(
                            route=route, mode="json", started_at=llm_executor.time.perf_counter(),
                            success=success, error_type=None if success else "RuntimeError",
                        )

                    summary = metrics_summary_service.build_daily_metrics_summary(reporting_date, metrics_dir=metrics_dir)
                    self.assertEqual(summary["llm"]["call_count"], 1)
                    self.assertEqual(summary["llm"]["success_rate"], 1.0 if success else 0.0)
                    self.assertEqual(summary["llm"]["error_count"], 0 if success else 1)
                    files = list((metrics_dir / "llm_calls").glob("*.jsonl"))
                    self.assertEqual([path.name for path in files], [f"{reporting_date}.jsonl"])
                    event = json.loads(files[0].read_text(encoding="utf-8"))
                    self.assertEqual(event["date"], reporting_date)
                    self.assertEqual(event["created_at"], audit_time)


if __name__ == "__main__":
    unittest.main()
