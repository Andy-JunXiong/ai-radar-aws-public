import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

registry_stub = types.ModuleType("app.prompts.registry")
registry_stub.signal_insight_prompts = lambda **kwargs: ("system", "user")
registry_stub.manual_image_analysis_prompt = lambda **kwargs: ("system", "user")
registry_stub.manual_single_text_user_prompt = lambda **kwargs: "user"
registry_stub.manual_text_analysis_prompt = lambda **kwargs: ("system", "user")
registry_stub.manual_text_session_user_prompt = lambda **kwargs: "user"
registry_stub.source_assistant_prompts = lambda **kwargs: ("system", "user")
registry_stub.workspace_chat_system_prompt = lambda **kwargs: "system"
registry_stub.workspace_reflection_polish_prompts = lambda **kwargs: ("system", "user")
registry_stub.workspace_visual_prompt = lambda **kwargs: ("system", "user")
def _default_registry_attr(name):
    return lambda **kwargs: ("system", "user")
registry_stub.__getattr__ = _default_registry_attr
sys.modules["app.prompts.registry"] = registry_stub

context_bridge_stub = types.ModuleType("app.services.context_bridge")
context_bridge_stub.build_analysis_context = lambda user_id=None: {}
context_bridge_stub.get_context_scope = lambda *args, **kwargs: "default"
context_bridge_stub.load_personal_context_data = lambda *args, **kwargs: {}
context_bridge_stub.save_personal_context_data = lambda *args, **kwargs: {}
sys.modules["app.services.context_bridge"] = context_bridge_stub

llm_executor_stub = types.ModuleType("app.services.llm_executor_service")
llm_executor_stub.execute_text_json_task = lambda **kwargs: ({}, None)
llm_executor_stub.execute_vision_json_task = lambda **kwargs: ({}, None)
llm_executor_stub.execute_text_task = lambda **kwargs: ("", None)
sys.modules["app.services.llm_executor_service"] = llm_executor_stub

llm_json_stub = types.ModuleType("app.services.llm_json_service")
llm_json_stub.parse_model_json = lambda raw: __import__("json").loads(raw)
llm_json_stub.repair_output_to_json_with_openai = lambda *args, **kwargs: {}
sys.modules["app.services.llm_json_service"] = llm_json_stub

model_router_stub = types.ModuleType("app.services.model_router_service")
model_router_stub.PROVIDER_ANTHROPIC = "anthropic"
model_router_stub.PROVIDER_OPENAI = "openai"
model_router_stub.PROVIDER_PERPLEXITY = "perplexity"


@dataclass(frozen=True)
class StubModelRoute:
    task_type: str = "insight"
    tier: str = "tier_2_structured"
    provider: str = "openai"
    model: str = "gpt-test"
    source: str = "env_router"


model_router_stub.ModelRoute = StubModelRoute
model_router_stub.route_task = lambda *args, **kwargs: None
model_router_stub.router_startup_diagnostics = lambda: {"routes": {}, "route_details": {}, "warnings": []}
sys.modules["app.services.model_router_service"] = model_router_stub

from app.services.evidence_pack_service import build_signal_evidence_pack  # noqa: E402
from app.services import signal_insight_service  # noqa: E402


class EvidencePackServiceTests(unittest.TestCase):
    def test_build_signal_evidence_pack_returns_observable_input_context(self):
        signal = {
            "signal_id": "sig-123",
            "title": "Agent repo launches enterprise mode",
            "summary": "Repo added enterprise deployment docs and issue chatter increased.",
            "source": "github",
            "published_at": "2026-04-21T00:00:00Z",
            "collected_at": "2026-04-21T01:00:00Z",
            "topic": "Agents",
            "score": 0.91,
            "url": "https://example.com/repo",
            "subscription_project_links": [
                {"project_id": "ai-radar", "project_name": "AI Radar", "relationship": "relevant"}
            ],
        }

        evidence_pack = build_signal_evidence_pack(signal)

        self.assertEqual(evidence_pack["source_signal_id"], "sig-123")
        self.assertEqual(evidence_pack["source_type"], "github")
        self.assertEqual(evidence_pack["summary_provenance"], "collector_extracted")
        self.assertEqual(evidence_pack["structured_context"]["topic"], "Agents")
        self.assertEqual(len(evidence_pack["structured_context"]["project_links"]), 1)
        self.assertTrue(evidence_pack["observed_facts"])
        self.assertTrue(evidence_pack["evidence_items"])
        self.assertIn("structured_metadata", {item["provenance"] for item in evidence_pack["evidence_items"]})
        self.assertIn("collector_extracted", {item["provenance"] for item in evidence_pack["evidence_items"]})

    def test_build_signal_evidence_pack_adds_bounded_source_excerpt_when_available(self):
        source_text = "Official article paragraph. " * 80
        signal = {
            "signal_id": "sig-source-excerpt",
            "title": "Official launch",
            "summary": "A short collector summary.",
            "source": "openai",
            "url": "https://example.com/launch",
            "content": source_text,
        }

        evidence_pack = build_signal_evidence_pack(signal)

        excerpt_items = [
            item
            for item in evidence_pack["evidence_items"]
            if item["provenance"] == "source_excerpt"
        ]
        self.assertEqual(len(excerpt_items), 1)
        self.assertEqual(excerpt_items[0]["source_field"], "content")
        self.assertEqual(excerpt_items[0]["kind"], "source_excerpt")
        self.assertEqual(len(excerpt_items[0]["content"]), 1200)
        self.assertTrue(excerpt_items[0]["traceable"])

    def test_build_signal_evidence_pack_does_not_duplicate_summary_as_source_excerpt(self):
        signal = {
            "signal_id": "sig-summary-only",
            "title": "Summary only",
            "summary": "The same text appears in content.",
            "source": "rss",
            "content": "The same text appears in content.",
        }

        evidence_pack = build_signal_evidence_pack(signal)

        self.assertNotIn(
            "source_excerpt",
            {item["provenance"] for item in evidence_pack["evidence_items"]},
        )

    def test_build_signal_evidence_pack_preserves_source_stated_limits_metadata(self):
        signal = {
            "signal_id": "sig-source-limits",
            "title": "AutoResearch framework report",
            "summary": "The project reports an in-framework simulated review.",
            "source": "research",
            "source_excerpt": "Limits: simulated review is not external peer review.",
            "source_stated_limits": [
                {
                    "text": "Simulated review is not external peer review.",
                    "source_field": "source_excerpt",
                }
            ],
            "source_stated_confidence": {
                "raw_text": "Known hallucinated citations exist.",
                "normalized_label": "limited",
            },
        }

        evidence_pack = build_signal_evidence_pack(signal)
        source_excerpt_item = next(
            item
            for item in evidence_pack["evidence_items"]
            if item["provenance"] == "source_excerpt"
        )

        metadata = source_excerpt_item["metadata"]
        self.assertEqual(metadata["source_stated_limits_status"], "limits_present")
        self.assertEqual(
            metadata["source_stated_limits"][0]["text"],
            "Simulated review is not external peer review.",
        )
        self.assertEqual(metadata["source_stated_limits"][0]["limit_type"], None)
        self.assertEqual(metadata["source_stated_confidence"]["raw_text"], "Known hallucinated citations exist.")

    def test_build_signal_evidence_pack_marks_source_limits_not_applicable_when_explicit(self):
        signal = {
            "signal_id": "sig-no-limits",
            "title": "Release note",
            "summary": "Patch release with no evaluative source limits.",
            "source": "rss",
            "source_stated_limits_not_applicable": True,
        }

        evidence_pack = build_signal_evidence_pack(signal)
        summary_item = next(
            item
            for item in evidence_pack["evidence_items"]
            if item["source_field"] == "summary"
        )

        self.assertEqual(
            summary_item["metadata"]["source_stated_limits_status"],
            "limits_not_applicable",
        )

    def test_build_signal_evidence_pack_adds_canonical_scalar_resolution_item(self):
        signal = {
            "signal_id": "sig-github-card",
            "title": "example/agentkit",
            "summary": "The GitHub card says example/agentkit has 12k stars and MIT license.",
            "source": "github",
            "url": "https://github.com/example/agentkit",
            "metadata": {
                "repo_name": "example/agentkit",
                "repo_stars": 842,
                "license_spdx_id": "AGPL-3.0",
                "claimed_scalars": {
                    "stars": "12000",
                    "license": "MIT",
                },
            },
        }

        evidence_pack = build_signal_evidence_pack(signal)
        scalar_item = next(
            item
            for item in evidence_pack["evidence_items"]
            if item["source_field"] == "canonical_scalars"
        )

        self.assertEqual(scalar_item["provenance"], "canonical_api_observed")
        self.assertTrue(scalar_item["traceable"])
        self.assertIn("stars=842", scalar_item["content"])
        self.assertEqual(
            scalar_item["metadata"]["canonical_scalar_resolution"]["summary"]["mismatch"],
            1,
        )
        self.assertEqual(
            scalar_item["metadata"]["canonical_scalar_resolution"]["summary"]["platform_delta"],
            1,
        )
        self.assertIn(
            "Canonical scalar observed:",
            " ".join(evidence_pack["observed_facts"]),
        )


class SignalInsightEvidencePackIntegrationTests(unittest.TestCase):
    def test_generate_signal_insight_attaches_evidence_pack_on_llm_success(self):
        source_excerpt = "Source-supported launch claim. " * 20
        signal = {
            "signal_id": "sig-1",
            "title": "Title",
            "summary": "Summary",
            "source": "github",
            "topic": "Agents",
            "source_excerpt": source_excerpt,
            "source_excerpt_length": len(source_excerpt),
        }

        parsed_payload = {
            "why_it_matters": "This matters because the signal reveals a concrete repo shift.",
            "relevance_to_projects": "Relevant to project direction and evidence quality discipline.",
            "relevance_to_career": "Useful for understanding modern AI product execution patterns.",
            "synthesized_insight": "Track the repo as a concrete indicator of implementation momentum.",
        }

        with patch.object(signal_insight_service, "OPENAI_API_KEY", "test-key"), patch.object(
            signal_insight_service,
            "execute_text_json_task",
            return_value=(parsed_payload, type("Route", (), {"provider": "openai", "model": "gpt-test"})()),
        ), patch.object(signal_insight_service, "parse_model_json", side_effect=lambda raw: __import__("json").loads(raw)):
            result = signal_insight_service.generate_signal_insight(signal, selected_model="chatgpt")

        self.assertIn("evidence_pack", result)
        self.assertEqual(result["evidence_pack"]["source_signal_id"], "sig-1")
        self.assertIn(
            "source_excerpt",
            {item["provenance"] for item in result["evidence_pack"]["evidence_items"]},
        )
        self.assertIn("evidence_pack", result["policy_metadata"])
        self.assertIn("verification", result)
        self.assertIn("evidence_quality", result["verification"])
        self.assertIn("low_evidence_gate", result["verification"])
        self.assertIn("verified_insight_id", result["verification"])
        self.assertIn("allowed_downstream_actions", result["verification"])
        self.assertIn("claim_results", result["verification"])
        self.assertEqual(result["produced_by_model"]["provenance_schema_version"], 1)
        self.assertEqual(result["verification"]["produced_by_model"]["model_id"], "gpt-test")
        self.assertEqual(result["policy_metadata"]["verification"]["produced_by_model"]["model_id"], "gpt-test")

    def test_generate_signal_insight_recovers_source_excerpt_from_collected_output(self):
        temp_dir = REPO_ROOT / "tmp_metrics_tests" / "source_excerpt_recovery"
        temp_dir.mkdir(parents=True, exist_ok=True)
        collected_file = temp_dir / "collected_signals.json"
        source_excerpt = "Recovered source excerpt with claim-level support. " * 20
        collected_file.write_text(
            __import__("json").dumps(
                [
                    {
                        "title": "Recovered signal",
                        "summary": "Collector summary.",
                        "source": "aws_ai",
                        "url": "https://example.com/recovered",
                        "source_excerpt": source_excerpt,
                        "source_excerpt_length": len(source_excerpt),
                    }
                ]
            ),
            encoding="utf-8",
        )
        signal = {
            "signal_id": "sig-recovered",
            "title": "Recovered signal",
            "summary": "Collector summary.",
            "source": "aws_ai",
            "url": "https://example.com/other-url",
        }
        parsed_payload = {
            "why_it_matters": "This matters because source evidence is recovered before insight generation.",
            "relevance_to_projects": "Relevant to claim-origin validation and evidence quality.",
            "relevance_to_career": "Useful for evaluating evidence-aware product engineering.",
            "synthesized_insight": "Recover source excerpts before building the evidence pack.",
        }

        try:
            with patch.object(signal_insight_service, "COLLECTED_SIGNALS_FILE", collected_file), patch.object(
                signal_insight_service, "OPENAI_API_KEY", "test-key"
            ), patch.object(
                signal_insight_service,
                "execute_text_json_task",
                return_value=(parsed_payload, type("Route", (), {"provider": "openai", "model": "gpt-test"})()),
            ), patch.object(
                signal_insight_service,
                "parse_model_json",
                side_effect=lambda raw: __import__("json").loads(raw),
            ):
                result = signal_insight_service.generate_signal_insight(signal, selected_model="chatgpt")

            self.assertIn(
                "source_excerpt",
                {item["provenance"] for item in result["evidence_pack"]["evidence_items"]},
            )
        finally:
            try:
                collected_file.unlink()
                temp_dir.rmdir()
            except OSError:
                pass

    def test_generate_signal_insight_normalizes_structured_model_fields(self):
        signal = {
            "signal_id": "sig-structured",
            "title": "Title",
            "summary": "Summary",
            "source": "github",
            "topic": "Agents",
        }

        parsed_payload = {
            "why_it_matters": {
                "summary": "This matters because the signal exposes a concrete workflow shift.",
                "impact": "It affects how AI Radar should evaluate automation maturity.",
            },
            "relevance_to_projects": "Relevant to project direction and evidence quality discipline.",
            "relevance_to_career": "Useful for understanding modern AI product execution patterns.",
            "synthesized_insight": "Track the repo as a concrete indicator of implementation momentum.",
        }

        with patch.object(signal_insight_service, "OPENAI_API_KEY", "test-key"), patch.object(
            signal_insight_service,
            "execute_text_json_task",
            return_value=(parsed_payload, type("Route", (), {"provider": "openai", "model": "gpt-test"})()),
        ), patch.object(signal_insight_service, "parse_model_json", side_effect=lambda raw: __import__("json").loads(raw)):
            result = signal_insight_service.generate_signal_insight(signal, selected_model="chatgpt")

        self.assertEqual(result["generation_mode"], "llm")
        self.assertIn("workflow shift", result["why_it_matters"])
        self.assertNotEqual(result["provider_used"], "fallback")

    def test_generate_signal_insight_attaches_evidence_pack_on_fallback(self):
        signal = {
            "signal_id": "sig-2",
            "title": "Fallback title",
            "summary": "Fallback summary",
            "source": "hn",
        }

        with patch.object(signal_insight_service, "OPENAI_API_KEY", "test-key"), patch.object(
            signal_insight_service,
            "execute_text_json_task",
            side_effect=RuntimeError("boom"),
        ):
            result = signal_insight_service.generate_signal_insight(signal, selected_model="chatgpt")

        self.assertEqual(result["generation_mode"], "fallback")
        self.assertEqual(result["evidence_pack"]["source_signal_id"], "sig-2")
        self.assertIn("Evidence Pack MVP attached", " ".join(result["policy_metadata"]["notes"]))
        self.assertIn("verification", result)
        self.assertIn("uncertainty_boundaries", result["verification"])
        self.assertEqual(result["verification"]["verification_status"], "needs_human_review")
        self.assertIn("claim_results", result["verification"])
        self.assertEqual(result["produced_by_model"]["provider"], "fallback")
        self.assertEqual(result["verification"]["produced_by_model"]["model_id"], "")

    def test_generate_signal_insight_requires_requested_anthropic_key(self):
        signal = {
            "signal_id": "sig-3",
            "title": "Claude requested",
            "summary": "Summary",
            "source": "manual",
        }

        with patch.object(signal_insight_service, "OPENAI_API_KEY", "test-key"), patch.object(
            signal_insight_service, "ANTHROPIC_API_KEY", None
        ), patch.object(signal_insight_service, "execute_text_json_task") as execute_mock:
            with self.assertRaises(ValueError) as raised:
                signal_insight_service.generate_signal_insight(signal, selected_model="claude")

        self.assertIn("ANTHROPIC_API_KEY not found", str(raised.exception))
        execute_mock.assert_not_called()

    def test_generate_signal_insight_requires_requested_openai_key(self):
        signal = {
            "signal_id": "sig-4",
            "title": "ChatGPT requested",
            "summary": "Summary",
            "source": "manual",
        }

        with patch.object(signal_insight_service, "OPENAI_API_KEY", None), patch.object(
            signal_insight_service, "ANTHROPIC_API_KEY", "test-key"
        ), patch.object(signal_insight_service, "execute_text_json_task") as execute_mock:
            with self.assertRaises(ValueError) as raised:
                signal_insight_service.generate_signal_insight(signal, selected_model="chatgpt")

        self.assertIn("OPENAI_API_KEY not found", str(raised.exception))
        execute_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
