import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import deep_project_match_analysis_service as service  # noqa: E402


class DeepProjectMatchAnalysisServiceTests(unittest.TestCase):
    def test_generate_deep_project_match_analysis_is_review_context_only(self):
        parsed = {
            "narrative_summary": "Komi-learn is relevant as a provenance-vs-verification reference case.",
            "signal_side_fact": "It stores signed community learnings for coding agents.",
            "ai_radar_side_fact": "AI Radar separates provenance from evidence verification.",
            "suspected_differentiated_insight": "It may confuse signed provenance with verification.",
            "concrete_relevance": "It helps review whether signed provenance should remain advisory.",
            "architecture_comparison": "Komi-learn ranks signed lessons; AI Radar gates claims through evidence.",
            "borrow": "Content addressing could help audit artifacts.",
            "beware": "Do not treat account signatures as truth.",
            "evidence_boundary": "Project fit is internal judgment.",
            "decision_posture": "Watch as architecture reference.",
            "review_note": "Use as provenance plane vs verification plane comparison.",
            "needs_source_read": True,
            "source_read_targets": [
                {
                    "target_type": "repo_file",
                    "path": "README.md",
                    "section_hint": "trust model section",
                    "question": "Does it treat provenance as advisory or verification?",
                }
            ],
            "evidence_basis": "Metadata only.",
            "structured_checklist": [
                {"label": "Boundary", "value": "Verification unchanged", "status": "ok"},
                {"label": "Risk", "value": "Could confuse trust with truth", "status": "watch"},
            ],
            "limitations": ["README-level analysis only."],
        }
        route = SimpleNamespace(provider="openai", model="gpt-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ) as execute:
            result = service.generate_deep_project_match_analysis(
                signal={"title": "komi-learn", "summary": "continuous memory"},
                deep_match_review={"matched_projects": ["AI Radar"]},
                selected_model="chatgpt",
                user_id="demo",
                source_depth_tier="metadata",
            )

        self.assertEqual(result["analysis_type"], "internal_project_fit_analysis")
        self.assertEqual(result["source_depth_tier"], "metadata")
        self.assertEqual(result["analysis_mode"], "hypothesis_only")
        self.assertEqual(result["hypothesis_status"], "hypothesis_with_source_target")
        self.assertEqual(result["differentiated_insight_status"], "hypothesis_with_source_target")
        self.assertTrue(result["needs_source_read"])
        self.assertEqual(result["source_read_targets"][0]["path"], "README.md")
        self.assertEqual(result["source_read_targets"][0]["section_hint"], "trust model section")
        self.assertEqual(result["review_note_effect"], "review_context_only")
        self.assertEqual(result["verification_effect"], "none")
        self.assertEqual(result["allowed_downstream_effect"], "review_context_only")
        self.assertEqual(result["provider_used"], "openai")
        self.assertEqual(result["model_used"], "gpt-test")
        self.assertEqual(result["structured_checklist"][0]["status"], "ok")
        execute.assert_called_once()
        self.assertEqual(execute.call_args.kwargs["task_type"], "reason")
        system_prompt = execute.call_args.kwargs["system_prompt"]
        user_prompt = execute.call_args.kwargs["user_prompt"]
        self.assertIn("AI Radar reference frame as a comparison ruler", system_prompt)
        self.assertIn("source_depth_tier must never modify verification_status", system_prompt)
        self.assertIn("provenance is not verification", user_prompt)
        self.assertIn("<ai_radar_reference_frame>", user_prompt)
        self.assertIn("</ai_radar_reference_frame>", user_prompt)
        self.assertIn('"external_signal"', user_prompt)
        self.assertIn("metadata-coherent but unresolvable source", user_prompt)
        self.assertIn("effort-coherent but unresolved work", user_prompt)
        self.assertIn("source-asserted but unsubstantiated", user_prompt)
        self.assertIn("source_claim_reading", user_prompt)
        self.assertIn("source_assertion_type", user_prompt)
        self.assertIn("fact_grounded|mixed|assertion_only|aspiration_heavy|result_without_data|unknown", user_prompt)
        self.assertIn("result_with_data requires traceable support", system_prompt)
        self.assertIn("For mixed source_claim_reliability", system_prompt)

    def test_metadata_tier_drops_unbound_suspected_insight(self):
        parsed = {
            "narrative_summary": "Potentially relevant, but source details are absent.",
            "suspected_differentiated_insight": "This sounds sharp but lacks a source target.",
            "concrete_relevance": "It may relate to AI Radar.",
            "needs_source_read": True,
        }
        route = SimpleNamespace(provider="openai", model="gpt-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ):
            result = service.generate_deep_project_match_analysis(
                signal={"title": "metadata-only signal"},
                selected_model="chatgpt",
                source_depth_tier="metadata",
            )

        self.assertEqual(result["hypothesis_status"], "not_enough_metadata")
        self.assertEqual(result["differentiated_insight_status"], "not_enough_metadata")
        self.assertEqual(result["suspected_differentiated_insight"], "")
        self.assertTrue(result["needs_source_read"])
        self.assertEqual(result["source_read_targets"][0]["target_type"], "source_section")
        self.assertIn("without source_read_targets", result["limitations"][0])

    def test_full_source_aspiration_claim_downgrades_differentiated_insight(self):
        parsed = {
            "narrative_summary": "The README presents a memory-loop direction for coding agents.",
            "signal_side_fact": "The README says the project plans to learn from every coding session.",
            "ai_radar_side_fact": "AI Radar separates source depth from verification status.",
            "suspected_differentiated_insight": "It pressures AI Radar to compare memory-loop designs.",
            "concrete_relevance": "It is a useful reference case for source-asserted capability.",
            "architecture_comparison": "The source describes intended memory behavior.",
            "borrow": "Review the memory interface vocabulary.",
            "beware": "Do not treat the README capability claim as implemented behavior.",
            "evidence_boundary": "The source supports that the README makes the claim, not that the capability is implemented.",
            "decision_posture": "Watch as source-claim-limited reference.",
            "review_note": "Use as a claim-reading case, not verified implementation evidence.",
            "needs_source_read": False,
            "source_claim_reading": {
                "source_read_depth": "full_source",
                "source_claim_reliability": "aspiration_heavy",
                "claims": [
                    {
                        "source_claim": "The system learns from every coding session.",
                        "source_assertion_type": "aspiration",
                        "evidence_locator": "README.md#vision",
                        "honesty_signals": ["early"],
                        "inflation_signals": ["present-tense capability claim"],
                        "can_support_differentiated_insight": False,
                        "limitation": "The README expresses an intended capability, not verified implementation fact.",
                    }
                ],
                "summary": "Full-source read found source assertion, not verified implementation fact.",
            },
            "evidence_basis": "Full README source text.",
            "limitations": [],
        }
        route = SimpleNamespace(provider="anthropic", model="claude-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", ""), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "test-key",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ):
            result = service.generate_deep_project_match_analysis(
                signal={"title": "memory-loop repo", "summary": "README says it learns from sessions"},
                selected_model="claude",
                source_depth_tier="full_source",
                source_text="README says the system is early and learns from every coding session.",
            )

        self.assertEqual(result["source_depth_tier"], "full_source")
        self.assertEqual(result["analysis_mode"], "source_grounded_comparison")
        self.assertEqual(result["hypothesis_status"], "source_claim_limited")
        self.assertEqual(result["differentiated_insight_status"], "source_claim_limited")
        self.assertFalse(result["needs_source_read"])
        self.assertIn(
            "Based on the source's claim, not verified implementation fact.",
            result["suspected_differentiated_insight"],
        )
        self.assertEqual(result["source_claim_reading"]["source_claim_reliability"], "aspiration_heavy")
        self.assertEqual(
            result["source_claim_reading"]["claims"][0]["source_assertion_type"],
            "aspiration",
        )
        self.assertFalse(result["source_claim_reading"]["claims"][0]["can_support_differentiated_insight"])
        self.assertEqual(result["verification_effect"], "none")
        self.assertEqual(result["allowed_downstream_effect"], "review_context_only")

    def test_full_source_fact_claim_can_remain_source_grounded(self):
        parsed = {
            "narrative_summary": "The source exposes a concrete signing mechanism.",
            "signal_side_fact": "The README states the repo verifies records with Ed25519 signatures.",
            "ai_radar_side_fact": "AI Radar separates provenance from verification.",
            "suspected_differentiated_insight": "The source can be compared as an implementation reference for signed provenance.",
            "concrete_relevance": "It gives AI Radar a concrete provenance mechanism to examine.",
            "architecture_comparison": "The source signs records; AI Radar treats provenance as audit context.",
            "borrow": "Review signature metadata shape.",
            "beware": "Do not turn signatures into truth verification.",
            "evidence_boundary": "Source-grounded implementation comparison, not external truth verification.",
            "decision_posture": "Knowledge as implementation reference.",
            "review_note": "Fact-grounded source read can support implementation comparison.",
            "needs_source_read": False,
            "source_claim_reading": {
                "source_read_depth": "full_source",
                "source_claim_reliability": "fact_grounded",
                "claims": [
                    {
                        "source_claim": "Records are verified with Ed25519 signatures.",
                        "source_assertion_type": "fact",
                        "evidence_locator": "README.md#trust-model",
                        "honesty_signals": [],
                        "inflation_signals": [],
                        "can_support_differentiated_insight": True,
                        "limitation": "Signature provenance does not verify content truth.",
                    }
                ],
                "summary": "The source provides a falsifiable implementation detail.",
            },
            "evidence_basis": "Full README source text.",
            "limitations": [],
        }
        route = SimpleNamespace(provider="openai", model="gpt-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ):
            result = service.generate_deep_project_match_analysis(
                signal={"title": "signed-memory repo", "summary": "README documents Ed25519 signatures"},
                selected_model="chatgpt",
                source_depth_tier="full_source",
                source_text="README trust model describes Ed25519 signatures.",
            )

        self.assertEqual(result["hypothesis_status"], "source_grounded")
        self.assertEqual(result["differentiated_insight_status"], "source_grounded")
        self.assertNotIn(service.SOURCE_CLAIM_LIMIT_NOTE, result["suspected_differentiated_insight"])
        self.assertEqual(result["source_claim_reading"]["source_claim_reliability"], "fact_grounded")
        self.assertEqual(result["source_claim_reading"]["claims"][0]["source_assertion_type"], "fact")
        self.assertTrue(result["source_claim_reading"]["claims"][0]["can_support_differentiated_insight"])

    def test_full_source_mixed_claims_do_not_collapse_supportable_insight(self):
        parsed = {
            "narrative_summary": "The source mixes advisory boundary facts with aspirational memory claims.",
            "signal_side_fact": "The README says the learning signal is advisory and the project aims to learn from sessions.",
            "ai_radar_side_fact": "AI Radar keeps learning context separate from verification gates.",
            "suspected_differentiated_insight": (
                "The source-grounded comparison is the advisory learning boundary, not the unverified memory capability."
            ),
            "concrete_relevance": "It pressures AI Radar to keep learned context advisory.",
            "architecture_comparison": "Both systems separate memory from hard verification decisions.",
            "borrow": "Borrow advisory learning language only.",
            "beware": "Do not borrow aspirational memory capability as implemented fact.",
            "evidence_boundary": "Only the advisory boundary claim supports the comparison.",
            "decision_posture": "Knowledge as bounded reference.",
            "review_note": "Mixed source claims can support only the fact-grounded part of the comparison.",
            "needs_source_read": False,
            "source_claim_reading": {
                "source_read_depth": "full_source",
                "source_claim_reliability": "mixed",
                "claims": [
                    {
                        "source_claim": "The learning signal is advisory, not a hard gate.",
                        "source_assertion_type": "fact",
                        "evidence_locator": "README.md#learning-signal",
                        "honesty_signals": ["Source limits the authority of the learning signal."],
                        "inflation_signals": [],
                        "can_support_differentiated_insight": True,
                        "limitation": "This supports a design-boundary comparison only.",
                    },
                    {
                        "source_claim": "The project aims to help coding agents learn from every session.",
                        "source_assertion_type": "aspiration",
                        "evidence_locator": "README.md#vision",
                        "honesty_signals": ["aims to marks design intent"],
                        "inflation_signals": [],
                        "can_support_differentiated_insight": False,
                        "limitation": "This cannot support an implemented memory-capability comparison.",
                    },
                ],
                "summary": "The source has one supportable boundary fact and one non-supporting aspiration.",
            },
            "evidence_basis": "Full README source text.",
            "limitations": [],
        }
        route = SimpleNamespace(provider="openai", model="gpt-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ):
            result = service.generate_deep_project_match_analysis(
                signal={"title": "advisory memory repo", "summary": "README mixes advisory and memory claims"},
                selected_model="chatgpt",
                source_depth_tier="full_source",
                source_text="README says the learning signal is advisory and the project aims to learn from sessions.",
            )

        self.assertEqual(result["hypothesis_status"], "source_grounded")
        self.assertEqual(result["differentiated_insight_status"], "source_grounded")
        self.assertNotIn(service.SOURCE_CLAIM_LIMIT_NOTE, result["suspected_differentiated_insight"])
        self.assertEqual(result["source_claim_reading"]["source_claim_reliability"], "mixed")
        self.assertEqual(result["source_claim_reading"]["claims"][0]["source_assertion_type"], "fact")
        self.assertTrue(result["source_claim_reading"]["claims"][0]["can_support_differentiated_insight"])
        self.assertEqual(result["source_claim_reading"]["claims"][1]["source_assertion_type"], "aspiration")
        self.assertFalse(result["source_claim_reading"]["claims"][1]["can_support_differentiated_insight"])
        self.assertEqual(result["verification_effect"], "none")
        self.assertEqual(result["allowed_downstream_effect"], "review_context_only")

    def test_full_source_result_with_data_claim_can_remain_source_grounded(self):
        parsed = {
            "narrative_summary": "The source reports a benchmark result with a locator.",
            "signal_side_fact": "The paper reports benchmark results in Table 2.",
            "ai_radar_side_fact": "AI Radar requires traceable evidence for result claims.",
            "suspected_differentiated_insight": "The source can be compared as a result-with-data reference case.",
            "concrete_relevance": "It shows how result claims should carry locators.",
            "architecture_comparison": "The source ties result claims to a table; AI Radar ties generated claims to evidence spans.",
            "borrow": "Use explicit result locators in review notes.",
            "beware": "Do not generalize beyond the benchmark.",
            "evidence_boundary": "Result claim is source-grounded to a table locator, not independently reproduced.",
            "decision_posture": "Knowledge as evidence-format reference.",
            "review_note": "Result-with-data source read can support limited comparison.",
            "needs_source_read": False,
            "source_claim_reading": {
                "source_read_depth": "full_source",
                "source_claim_reliability": "fact_grounded",
                "claims": [
                    {
                        "source_claim": "The method improved task success by 18 points.",
                        "source_assertion_type": "result_with_data",
                        "evidence_locator": "paper Table 2",
                        "honesty_signals": ["benchmark named"],
                        "inflation_signals": [],
                        "can_support_differentiated_insight": True,
                        "limitation": "The result is benchmark-scoped and not independently reproduced.",
                    }
                ],
                "summary": "The source provides a result claim with a traceable table locator.",
            },
            "evidence_basis": "Full paper source text.",
            "limitations": [],
        }
        route = SimpleNamespace(provider="openai", model="gpt-test", task_type="reason")

        with patch.object(service, "OPENAI_API_KEY", "test-key"), patch.object(
            service,
            "ANTHROPIC_API_KEY",
            "",
        ), patch.object(
            service,
            "build_analysis_context",
            return_value="AI Radar context",
        ), patch.object(
            service,
            "execute_text_json_task",
            return_value=(parsed, route),
        ):
            result = service.generate_deep_project_match_analysis(
                signal={"title": "benchmark paper", "summary": "Paper reports results in Table 2"},
                selected_model="chatgpt",
                source_depth_tier="full_source",
                source_text="The paper reports benchmark results in Table 2.",
            )

        self.assertEqual(result["hypothesis_status"], "source_grounded")
        self.assertEqual(result["differentiated_insight_status"], "source_grounded")
        self.assertNotIn(service.SOURCE_CLAIM_LIMIT_NOTE, result["suspected_differentiated_insight"])
        self.assertEqual(
            result["source_claim_reading"]["claims"][0]["source_assertion_type"],
            "result_with_data",
        )
        self.assertEqual(result["source_claim_reading"]["claims"][0]["evidence_locator"], "paper Table 2")
        self.assertTrue(result["source_claim_reading"]["claims"][0]["can_support_differentiated_insight"])


if __name__ == "__main__":
    unittest.main()
