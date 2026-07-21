import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.execution_policy_service import PolicyInput, decide_execution_policy  # noqa: E402
from app.services.fallback_policy_service import execute_policy_text_json  # noqa: E402
from app.services.output_validation_service import (  # noqa: E402
    count_citations,
    mark_output_uncertain,
    validate_output,
)


class ExecutionPolicyServiceTests(unittest.TestCase):
    def test_low_risk_task_routes_to_fast_mode(self):
        result = decide_execution_policy(
            PolicyInput(
                task_type="reflection_polish",
                query="polish this",
                user_visible=False,
                importance_score=10,
                source_count=0,
            )
        )

        self.assertEqual(result.final_mode, "fast")
        self.assertEqual(result.selected_policy.output_mode, "draft")
        self.assertEqual(result.effective_task_type, "reflection_polish")

    def test_manual_session_routes_to_guarded_mode(self):
        result = decide_execution_policy(
            PolicyInput(
                task_type="manual_text_session",
                user_visible=True,
                importance_score=80,
                source_count=3,
            )
        )

        self.assertEqual(result.final_mode, "guarded")
        self.assertTrue(result.selected_policy.citation_required)
        self.assertEqual(result.selected_policy.output_mode, "grounded")

    def test_workspace_recommendation_routes_to_critical_mode(self):
        result = decide_execution_policy(
            PolicyInput(
                task_type="workspace_chat",
                query="What should I do next and what do you recommend?",
                user_visible=True,
                importance_score=85,
                source_count=2,
            )
        )

        self.assertEqual(result.final_mode, "critical")
        self.assertTrue(result.selected_policy.verification_required)
        self.assertIn(result.effective_task_type, {"reason", "workspace_chat"})


class OutputValidationServiceTests(unittest.TestCase):
    def test_count_citations_detects_inline_evidence(self):
        payload = {
            "why_it_matters": "This matters. [Evidence: OpenAI blog, Apr 2026]",
            "summary": "Another line.",
        }
        self.assertEqual(count_citations(payload), 1)

    def test_guarded_validation_fails_without_citations_when_context_exists(self):
        policy = decide_execution_policy(
            PolicyInput(
                task_type="insight",
                user_visible=True,
                importance_score=80,
                source_count=1,
            )
        ).selected_policy

        validation = validate_output(
            policy=policy,
            output={"why_it_matters": "A factual claim without evidence."},
            context_available=True,
        )

        self.assertFalse(validation.passed)
        self.assertIn("missing_citations", validation.failures)
        self.assertFalse(validation.citation_validation_passed)

    def test_mark_output_uncertain_prefixes_strings(self):
        updated = mark_output_uncertain({"field": "Concrete claim"})
        self.assertEqual(updated["field"], "Uncertain: Concrete claim")

    def test_critical_validation_marks_unsupported_claims(self):
        policy = decide_execution_policy(
            PolicyInput(
                task_type="strategic_intelligence",
                user_visible=True,
                importance_score=90,
                requires_traceability=True,
                source_count=1,
            )
        ).selected_policy

        validation = validate_output(
            policy=policy,
            output={"summary": "OpenAI definitely dominates the market."},
            context_available=True,
        )

        self.assertFalse(validation.verification_passed)
        self.assertTrue(validation.unsupported_claims)

    def test_manual_text_policy_keeps_uncertainty_in_metadata_not_body(self):
        def executor(effective_task_type, system_prompt, user_prompt):
            return (
                {
                    "summary": "The uploaded material defines a reusable judgment frame.",
                    "synthesized_insight": "Use this as a cognitive asset seed.",
                },
                SimpleNamespace(provider="openai", model="gpt-test"),
            )

        payload, route, metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="manual_text_session",
                user_visible=True,
                importance_score=80,
                requires_traceability=True,
                source_count=1,
            ),
            system_prompt="system",
            user_prompt="user",
            metadata={"source_count": 1},
            executor=executor,
        )

        self.assertEqual(route.provider, "openai")
        self.assertFalse(payload["summary"].startswith("Uncertain:"))
        self.assertEqual(metadata["verification_status"], "uncertain")
        self.assertIn("verification_incomplete", metadata["validation_failures"])

    def test_manual_text_policy_injects_uploaded_source_citation_before_validation(self):
        def executor(effective_task_type, system_prompt, user_prompt):
            return (
                {
                    "summary": "The uploaded material defines a reusable judgment frame.",
                    "synthesized_insight": "Use this as a cognitive asset seed.",
                },
                SimpleNamespace(provider="openai", model="gpt-test"),
            )

        payload, route, metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="manual_text_session",
                user_visible=True,
                importance_score=80,
                requires_traceability=True,
                source_count=1,
            ),
            system_prompt="system",
            user_prompt="user",
            metadata={"source_count": 1, "source_labels": ["seed-note.txt"]},
            executor=executor,
        )

        self.assertEqual(route.provider, "openai")
        self.assertIn("[Source: seed-note.txt]", payload["summary"])
        self.assertEqual(metadata["citation_count"], 1)
        self.assertEqual(metadata["verification_status"], "basic_verified")
        self.assertTrue(metadata["source_citation_injected"])
        self.assertEqual(metadata["validation_failures"], [])

    def test_manual_text_policy_does_not_duplicate_existing_citation(self):
        def executor(effective_task_type, system_prompt, user_prompt):
            return (
                {
                    "summary": "Already grounded. [Source: existing.txt]",
                    "synthesized_insight": "Use this as a cognitive asset seed.",
                },
                SimpleNamespace(provider="openai", model="gpt-test"),
            )

        payload, route, metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="manual_text_session",
                user_visible=True,
                importance_score=80,
                requires_traceability=True,
                source_count=1,
            ),
            system_prompt="system",
            user_prompt="user",
            metadata={"source_count": 1, "source_labels": ["seed-note.txt"]},
            executor=executor,
        )

        self.assertEqual(route.provider, "openai")
        self.assertEqual(payload["summary"].count("[Source:"), 1)
        self.assertNotIn("source_citation_injected", metadata)
        self.assertEqual(metadata["verification_status"], "basic_verified")

    def test_manual_text_policy_sanitizes_injected_source_labels(self):
        def executor(effective_task_type, system_prompt, user_prompt):
            return (
                {"summary": "Grounded analysis.", "synthesized_insight": "Use this."},
                SimpleNamespace(provider="openai", model="gpt-test"),
            )

        payload, route, metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="manual_text_session",
                user_visible=True,
                importance_score=80,
                requires_traceability=True,
                source_count=1,
            ),
            system_prompt="system",
            user_prompt="user",
            metadata={"source_count": 1, "source_labels": [" messy\nsource\tname.txt "]},
            executor=executor,
        )

        self.assertEqual(route.provider, "openai")
        self.assertIn("[Source: messy source name.txt]", payload["summary"])
        self.assertTrue(metadata["source_citation_injected"])

    def test_non_manual_critical_policy_still_marks_body_uncertain(self):
        def executor(effective_task_type, system_prompt, user_prompt):
            return (
                {"summary": "This unsupported strategic claim is decisive."},
                SimpleNamespace(provider="openai", model="gpt-test"),
            )

        payload, route, metadata = execute_policy_text_json(
            policy_input=PolicyInput(
                task_type="strategy",
                user_visible=True,
                importance_score=90,
                requires_traceability=True,
                source_count=1,
            ),
            system_prompt="system",
            user_prompt="user",
            metadata={"source_count": 1},
            executor=executor,
        )

        self.assertEqual(route.provider, "openai")
        self.assertTrue(payload["summary"].startswith("Uncertain:"))
        self.assertEqual(metadata["verification_status"], "uncertain")


if __name__ == "__main__":
    unittest.main()
