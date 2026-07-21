import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.intelligence.llm_executor import execute_routed_task  # noqa: E402


class LLMExecutorTests(unittest.TestCase):
    def setUp(self):
        self.metrics_patcher = patch("app.intelligence.llm_executor.record_llm_call")
        self.mock_record_llm_call = self.metrics_patcher.start()
        self.route_event_patcher = patch("app.intelligence.llm_executor.record_route_event")
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
        ), patch("app.intelligence.llm_executor._openai_client", return_value=mock_client):
            result = execute_routed_task(
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
        ), patch("app.intelligence.llm_executor._openai_client", return_value=mock_client):
            result = execute_routed_task(
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
        ), patch("app.intelligence.llm_executor._openai_client", return_value=mock_client):
            result = execute_routed_task(
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
        ), patch("app.intelligence.llm_executor._anthropic_client", return_value=mock_client):
            result = execute_routed_task(
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
        ), patch("app.intelligence.llm_executor._anthropic_client", return_value=mock_client):
            result = execute_routed_task(
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


if __name__ == "__main__":
    unittest.main()
