import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm_executor_service import (  # noqa: E402
    ANTHROPIC_WEB_SEARCH_TOOL_TYPE,
    execute_text_task,
    execute_text_json_task,
    execute_vision_json_task,
    parse_anthropic_response_content,
)


class BackendLLMExecutorServiceTests(unittest.TestCase):
    def setUp(self):
        self.metrics_patcher = patch("app.services.llm_executor_service.record_llm_call")
        self.mock_record_llm_call = self.metrics_patcher.start()
        self.route_event_patcher = patch("app.services.llm_executor_service.record_route_event")
        self.mock_record_route_event = self.route_event_patcher.start()

    def tearDown(self):
        self.route_event_patcher.stop()
        self.metrics_patcher.stop()

    def test_openai_text_json_execution(self):
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
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                openai_api_key="test-key",
            )

        self.assertEqual(route.provider, "openai")
        self.assertEqual(parsed, {"summary": "ok"})

    def test_openai_text_json_omits_temperature_for_gpt5_models(self):
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
                "MODEL_ROUTER_TIER2_MODEL": "gpt-5.1",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                temperature=0.7,
                openai_api_key="test-key",
            )

        self.assertEqual(route.model, "gpt-5.1")
        self.assertEqual(parsed, {"summary": "ok"})
        self.assertNotIn("temperature", captured_kwargs)

    def test_openai_text_json_keeps_temperature_for_standard_models(self):
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
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                temperature=0.7,
                openai_api_key="test-key",
            )

        self.assertEqual(route.model, "gpt-4.1-mini")
        self.assertEqual(parsed, {"summary": "ok"})
        self.assertEqual(captured_kwargs["temperature"], 0.7)

    def test_anthropic_text_json_execution(self):
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(text='{"summary":"ok"}')]
        )
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kwargs: mock_response)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "anthropic",
                "MODEL_ROUTER_TIER2_MODEL": "claude-sonnet-4-6",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "anthropic",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.anthropic.Anthropic", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                anthropic_api_key="test-key",
            )

        self.assertEqual(route.provider, "anthropic")
        self.assertEqual(parsed, {"summary": "ok"})

    def test_anthropic_text_json_omits_tools_when_web_search_flag_off(self):
        captured_kwargs = {}
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"summary":"ok"}')]
        )

        def create_message(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=create_message)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "anthropic",
                "MODEL_ROUTER_TIER2_MODEL": "claude-opus-4-8",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "anthropic",
            },
            clear=True,
        ), patch("app.services.llm_executor_service.anthropic.Anthropic", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                anthropic_api_key="test-key",
            )

        self.assertEqual(route.provider, "anthropic")
        self.assertFalse(route.web_search_enabled)
        self.assertEqual(parsed, {"summary": "ok"})
        self.assertNotIn("tools", captured_kwargs)

    def test_anthropic_text_json_adds_web_search_tool_when_enabled(self):
        captured_kwargs = {}
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"summary":"ok"}')]
        )

        def create_message(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=create_message)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "anthropic",
                "ANTHROPIC_WEB_SEARCH_MODEL": "claude-opus-4-8",
                "ANTHROPIC_WEB_SEARCH_MAX_USES": "5",
            },
            clear=True,
        ), patch("app.services.llm_executor_service.anthropic.Anthropic", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                anthropic_api_key="test-key",
                web_search_enabled=True,
            )

        self.assertTrue(route.web_search_enabled)
        self.assertEqual(route.model, "claude-opus-4-8")
        self.assertEqual(route.web_search_max_uses, 5)
        self.assertEqual(parsed, {"summary": "ok"})
        self.assertEqual(
            captured_kwargs["tools"],
            [
                {
                    "type": ANTHROPIC_WEB_SEARCH_TOOL_TYPE,
                    "name": "web_search",
                    "max_uses": 5,
                }
            ],
        )

    def test_anthropic_web_search_upgrades_unsupported_fallback_model(self):
        captured_kwargs = {}
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"summary":"ok"}')]
        )

        def create_message(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=create_message)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "anthropic",
                "CLAUDE_MODEL": "claude-3-5-sonnet-20241022",
            },
            clear=True,
        ), patch("app.services.llm_executor_service.anthropic.Anthropic", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                anthropic_api_key="test-key",
                web_search_enabled=True,
            )

        self.assertEqual(parsed, {"summary": "ok"})
        self.assertEqual(route.model, "claude-opus-4-8")
        self.assertEqual(captured_kwargs["model"], "claude-opus-4-8")
        self.assertEqual(captured_kwargs["tools"][0]["type"], ANTHROPIC_WEB_SEARCH_TOOL_TYPE)

    def test_anthropic_web_search_response_parser_preserves_provenance(self):
        mock_response = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="I'll search first."),
                SimpleNamespace(
                    type="server_tool_use",
                    id="srvtoolu_123",
                    name="web_search",
                    input={"query": "Claude Shannon birth date"},
                ),
                SimpleNamespace(
                    type="web_search_tool_result",
                    tool_use_id="srvtoolu_123",
                    content=[
                        {
                            "type": "web_search_result",
                            "url": "https://example.com/shannon",
                            "title": "Claude Shannon",
                            "page_age": "April 30, 2025",
                        }
                    ],
                ),
                SimpleNamespace(
                    type="text",
                    text="Claude Shannon was born in 1916.",
                    citations=[
                        {
                            "type": "web_search_result_location",
                            "url": "https://example.com/shannon",
                            "title": "Claude Shannon",
                            "cited_text": "Claude Elwood Shannon was born...",
                        }
                    ],
                ),
            ]
        )

        parsed = parse_anthropic_response_content(mock_response, web_search_enabled=True)

        self.assertEqual(
            parsed["text"],
            "I'll search first.\nClaude Shannon was born in 1916.",
        )
        self.assertEqual(
            parsed["server_tool_uses"],
            [
                {
                    "source": "web_search",
                    "id": "srvtoolu_123",
                    "name": "web_search",
                    "input": {"query": "Claude Shannon birth date"},
                }
            ],
        )
        self.assertEqual(parsed["search_results"][0]["source"], "web_search")
        self.assertEqual(parsed["search_results"][0]["url"], "https://example.com/shannon")
        self.assertEqual(parsed["citations"][0]["source"], "web_search")
        self.assertEqual(parsed["citations"][0]["title"], "Claude Shannon")

    def test_anthropic_text_json_omits_temperature_for_claude_4_models(self):
        captured_kwargs = {}
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(text='{"summary":"ok"}')]
        )

        def create_message(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=create_message)
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "anthropic",
                "MODEL_ROUTER_TIER2_MODEL": "claude-opus-4-7",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "anthropic",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.anthropic.Anthropic", return_value=mock_client):
            parsed, route = execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                temperature=0.7,
                anthropic_api_key="test-key",
            )

        self.assertEqual(route.model, "claude-opus-4-7")
        self.assertEqual(parsed, {"summary": "ok"})
        self.assertNotIn("temperature", captured_kwargs)

    def test_openai_vision_json_execution(self):
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content='{"summary":"vision"}')
                            )
                        ]
                    )
                )
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_VISION_PROVIDER": "openai",
                "MODEL_ROUTER_VISION_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client):
            parsed, route = execute_vision_json_task(
                task_type="manual_image",
                prompt_text="describe image",
                attachments=[
                    {
                        "filename": "a.png",
                        "media_type": "image/png",
                        "image_b64": "abc",
                    }
                ],
                openai_api_key="test-key",
            )

        self.assertEqual(route.provider, "openai")
        self.assertEqual(parsed, {"summary": "vision"})

    def test_perplexity_text_execution(self):
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="perplexity reply")
                            )
                        ]
                    )
                )
            )
        )

        with patch.dict(
            "os.environ",
            {
                "PERPLEXITY_MODEL": "sonar-pro",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client):
            reply, route = execute_text_task(
                task_type="workspace_chat",
                system_prompt="system",
                user_prompt="user",
                provider_override="perplexity",
                perplexity_api_key="test-key",
            )

        self.assertEqual(route.provider, "perplexity")
        self.assertEqual(reply, "perplexity reply")

    def test_executor_logs_success_outcome(self):
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
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=mock_client), patch(
            "app.services.llm_executor_service.record_route_event"
        ) as mock_record:
            execute_text_json_task(
                task_type="manual_text",
                system_prompt="system",
                user_prompt="user",
                openai_api_key="test-key",
                fallback_used=True,
            )

        mock_record.assert_called_once()
        self.assertEqual(mock_record.call_args.kwargs["outcome"], "success")
        self.assertTrue(mock_record.call_args.kwargs["fallback_used"])
        self.mock_record_llm_call.assert_called_once()
        metric = self.mock_record_llm_call.call_args.args[0]
        self.assertEqual(metric["task_type"], "manual_text")
        self.assertEqual(metric["provider"], "openai")
        self.assertEqual(metric["mode"], "text_json")
        self.assertTrue(metric["success"])
        self.assertTrue(metric["fallback_used"])
        self.assertTrue(metric["json_validation_passed"])

    def test_executor_logs_failure_outcome(self):
        failing_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
                )
            )
        )

        with patch.dict(
            "os.environ",
            {
                "MODEL_ROUTER_TIER2_PROVIDER": "openai",
                "MODEL_ROUTER_MANUAL_TEXT_PROVIDER": "openai",
            },
            clear=False,
        ), patch("app.services.llm_executor_service.OpenAI", return_value=failing_client), patch(
            "app.services.llm_executor_service.record_route_event"
        ) as mock_record:
            with self.assertRaises(RuntimeError):
                execute_text_json_task(
                    task_type="manual_text",
                    system_prompt="system",
                    user_prompt="user",
                    openai_api_key="test-key",
                )

        mock_record.assert_called_once()
        self.assertEqual(mock_record.call_args.kwargs["outcome"], "failure")
        self.assertEqual(mock_record.call_args.kwargs["error_type"], "RuntimeError")
        self.mock_record_llm_call.assert_called_once()
        metric = self.mock_record_llm_call.call_args.args[0]
        self.assertFalse(metric["success"])
        self.assertEqual(metric["error_type"], "RuntimeError")
        self.assertFalse(metric["json_validation_passed"])


if __name__ == "__main__":
    unittest.main()
