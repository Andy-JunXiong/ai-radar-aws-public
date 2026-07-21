import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.strategic_synthesis_service import (  # noqa: E402
    _project_relevance_matches,
    _topic_tokens_from_item,
    build_strategic_synthesis_response,
)


class StrategicSynthesisServiceTests(unittest.TestCase):
    def test_builds_topics_supply_demand_and_review_quality(self):
        payload = build_strategic_synthesis_response(
            radar_intelligence={
                "strategic_priority": {
                    "items": {
                        "strategic_priority_topics": [
                            {"topic": "Agent Infrastructure", "priority_score": 9.2},
                            {"topic": "Evaluation", "priority_score": 7.5},
                        ]
                    }
                },
                "agent_watch": {
                    "count": 2,
                    "signals": [
                        {
                            "title": "Agent runtime framework",
                            "summary": "Evaluation runtime framework adoption is rising.",
                            "url": "https://example.com/agent",
                            "source": "github",
                            "agent_subtopic": "evaluation",
                            "agent_watch_score": 0.91,
                        }
                    ],
                },
                "friction_signals": {
                    "count": 3,
                    "signals": [
                        {
                            "title": "Teams struggle with eval reliability",
                            "summary": "Evaluation remains painful.",
                            "url": "https://example.com/friction",
                            "source": "hn",
                            "friction_subtopic": "evaluation",
                            "matched_keywords": ["eval reliability"],
                            "friction_score": 0.87,
                        }
                    ],
                },
            },
            review_summary={
                "total_records": 5,
                "actionable_count": 2,
                "watch_count": 1,
                "manual_record_count": 1,
                "blocked_action_rate": 0.2,
                "unsupported_claim_count": 1,
                "latest_reviewed_at": "2026-05-07T01:00:00+00:00",
            },
            calibration_summary={
                "total_events": 7,
                "actionable_event_count": 3,
                "manual_event_count": 2,
                "unsupported_claim_count": 2,
                "latest_event_at": "2026-05-07T02:00:00+00:00",
            },
            projects=[
                {
                    "project_id": "ai_radar",
                    "name": "AI Radar",
                    "enabled": True,
                    "status": "active",
                    "topics": ["evaluation", "agent infrastructure"],
                    "description": "Intelligence system for agent evaluation and project review.",
                }
            ],
        )

        self.assertEqual(payload["synthesis_type"], "strategic_synthesis_mvp")
        self.assertEqual(payload["summary"]["strategic_topic_count"], 2)
        self.assertEqual(payload["summary"]["agent_watch_count"], 2)
        self.assertEqual(payload["summary"]["friction_signal_count"], 3)
        self.assertEqual(payload["summary"]["convergence_brief_count"], 1)
        self.assertEqual(payload["summary"]["review_record_count"], 5)
        self.assertEqual(payload["summary"]["calibration_event_count"], 7)
        self.assertEqual(payload["summary"]["manual_source_event_count"], 3)
        self.assertEqual(payload["strategic_topics"][0]["topic"], "Agent Infrastructure")
        self.assertEqual(payload["supply_demand"]["agent_watch_highlights"][0]["title"], "Agent runtime framework")
        self.assertEqual(payload["supply_demand"]["friction_highlights"][0]["title"], "Teams struggle with eval reliability")
        brief = payload["supply_demand"]["convergence_briefs"][0]
        self.assertEqual(brief["confidence"], "high")
        self.assertEqual(brief["pair_type"], "topic_overlap")
        self.assertTrue(brief["cluster_id"].startswith("knowledge-convergence-"))
        self.assertEqual(brief["action_gate"], "human_review_required")
        self.assertIn("evaluation", brief["shared_topics"])
        self.assertEqual(brief["agent_watch_item"]["entity_id"], "https://example.com/agent")
        self.assertEqual(brief["friction_item"]["entity_id"], "https://example.com/friction")
        self.assertEqual(brief["review_readiness"]["status"], "ready_for_project_review")
        self.assertEqual(brief["review_readiness"]["matched_project_count"], 1)
        self.assertEqual(brief["project_relevance"]["matched_projects"][0]["project_id"], "ai_radar")
        self.assertEqual(brief["project_relevance"]["matched_projects"][0]["match_type"], "shared_topic")
        self.assertIn("evaluation", brief["project_relevance"]["matched_projects"][0]["matched_topics"])
        self.assertIn("evaluation", brief["project_relevance"]["matched_projects"][0]["shared_topic_matches"])
        self.assertIn("AI Radar", brief["project_relevance"]["project_takeaway_map"])
        self.assertEqual(brief["evidence_profile"]["source_count"], 2)
        self.assertGreaterEqual(brief["quality"]["score"], 70)
        self.assertEqual(brief["quality"]["label"], "Strong review candidate")
        self.assertGreaterEqual(brief["quality"]["factors"]["fit_score"], 10)
        self.assertEqual(brief["quality"]["factors"]["penalty"], 0)
        self.assertIn("shared_topic_project_match_count", brief["quality"]["factors"])
        self.assertEqual(brief["evidence_profile"]["quality_score"], brief["quality"]["score"])
        self.assertIn("Supply:", brief["supply_read"])
        self.assertIn("Demand:", brief["demand_read"])
        self.assertIn("supply-side movement", brief["why_paired"])
        self.assertIn("demand-side pain", brief["why_paired"])
        self.assertIn("evaluation", brief["why_paired"])
        self.assertIn("review context only", brief["review_boundary"])
        self.assertIn("does not create verified evidence", brief["review_boundary"])
        self.assertTrue(payload["review_quality"]["ops_summary"]["achieved"])
        self.assertTrue(
            any(
                "3 manual-source review/calibration events" in item
                for item in payload["review_quality"]["ops_summary"]["achieved"]
            )
        )
        self.assertTrue(payload["review_quality"]["ops_summary"]["gaps"])
        self.assertIn("Review watched items", payload["review_quality"]["ops_summary"]["next_focus"][0])

    def test_handles_missing_inputs_without_failure(self):
        payload = build_strategic_synthesis_response(radar_intelligence=None)

        self.assertEqual(payload["summary"]["strategic_topic_count"], 0)
        self.assertEqual(payload["summary"]["agent_watch_count"], 0)
        self.assertEqual(payload["summary"]["friction_signal_count"], 0)
        self.assertEqual(payload["strategic_topics"], [])
        self.assertEqual(payload["supply_demand"]["agent_watch_highlights"], [])
        self.assertEqual(payload["supply_demand"]["friction_highlights"], [])
        self.assertEqual(payload["supply_demand"]["convergence_briefs"], [])
        self.assertTrue(payload["review_quality"]["ops_summary"]["next_focus"])

    def test_builds_exploratory_pair_when_no_topic_overlap_exists(self):
        payload = build_strategic_synthesis_response(
            radar_intelligence={
                "agent_watch": {
                    "count": 1,
                    "signals": [
                        {
                            "title": "Agent runtime framework",
                            "summary": "A new runtime appears.",
                            "url": "https://example.com/agent",
                            "source": "github",
                            "agent_watch_score": 0.2,
                        }
                    ],
                },
                "friction_signals": {
                    "count": 1,
                    "signals": [
                        {
                            "title": "Billing issue",
                            "summary": "Users report billing errors.",
                            "url": "https://example.com/friction",
                            "source": "hn",
                            "friction_score": 0.2,
                        }
                    ],
                },
            }
        )

        briefs = payload["supply_demand"]["convergence_briefs"]
        self.assertEqual(len(briefs), 1)
        self.assertEqual(briefs[0]["pair_type"], "exploratory")
        self.assertEqual(briefs[0]["confidence"], "low")
        self.assertEqual(briefs[0]["review_readiness"]["status"], "needs_more_evidence")
        self.assertEqual(briefs[0]["quality"]["label"], "Needs stronger evidence")
        self.assertGreater(briefs[0]["quality"]["factors"]["penalty"], 0)
        self.assertIn("watch-only", briefs[0]["why_paired"])
        self.assertIn("topic overlap is still weak", briefs[0]["why_paired"])
        self.assertIn("review context only", briefs[0]["review_boundary"])

    def test_project_matching_ignores_single_generic_context_overlap(self):
        payload = build_strategic_synthesis_response(
            radar_intelligence={
                "strategic_priority": {
                    "items": {
                        "strategic_priority_topics": [
                            {"topic": "Evaluation", "priority_score": 8.5},
                        ]
                    }
                },
                "agent_watch": {
                    "signals": [
                        {
                            "title": "Evaluation runtime framework",
                            "summary": "Evaluation workflow reliability is improving.",
                            "url": "https://example.com/agent",
                            "source": "github",
                            "agent_watch_score": 0.9,
                        }
                    ],
                },
                "friction_signals": {
                    "signals": [
                        {
                            "title": "Teams struggle with eval reliability",
                            "summary": "Evaluation workflow reliability remains painful.",
                            "url": "https://example.com/friction",
                            "source": "hn",
                            "friction_score": 0.88,
                        }
                    ],
                },
            },
            projects=[
                {
                    "project_id": "eval_ops",
                    "name": "Eval Ops",
                    "enabled": True,
                    "topics": ["evaluation", "workflow"],
                    "description": "Evaluation reliability for agent workflow review.",
                },
                {
                    "project_id": "generic_intel",
                    "name": "Generic Intelligence",
                    "enabled": True,
                    "topics": ["intelligence"],
                    "description": "General intelligence project for user systems.",
                },
            ],
        )

        brief = payload["supply_demand"]["convergence_briefs"][0]
        project_ids = [item["project_id"] for item in brief["project_relevance"]["matched_projects"]]
        self.assertIn("eval_ops", project_ids)
        self.assertNotIn("generic_intel", project_ids)
        self.assertEqual(brief["review_readiness"]["status"], "ready_for_project_review")

    def test_project_matching_requires_three_context_terms_without_shared_topic(self):
        matches = _project_relevance_matches(
            shared_topics=["developer tooling"],
            agent_item={"topic_tokens": ["developer tooling", "infrastructure", "native"]},
            friction_item={"topic_tokens": ["developer tooling", "runtime", "security"]},
            projects=[
                {
                    "project_id": "thin_context",
                    "name": "Thin Context",
                    "enabled": True,
                    "topics": ["infrastructure"],
                    "description": "AI-native infrastructure.",
                },
                {
                    "project_id": "strong_context",
                    "name": "Strong Context",
                    "enabled": True,
                    "topics": ["runtime security infrastructure"],
                    "description": "AI-native runtime infrastructure.",
                },
            ],
        )

        project_ids = [item["project_id"] for item in matches]

        self.assertNotIn("thin_context", project_ids)
        self.assertIn("strong_context", project_ids)
        strong_match = next(item for item in matches if item["project_id"] == "strong_context")
        self.assertEqual(strong_match["match_type"], "context_overlap")
        self.assertGreaterEqual(len(strong_match["context_matches"]), 3)

    def test_project_matching_requires_context_for_broad_shared_topic(self):
        matches = _project_relevance_matches(
            shared_topics=["infrastructure"],
            agent_item={"topic_tokens": ["infrastructure", "runtime", "security", "deployment"]},
            friction_item={"topic_tokens": ["infrastructure", "deployment"]},
            projects=[
                {
                    "project_id": "thin_infrastructure",
                    "name": "Thin Infrastructure",
                    "enabled": True,
                    "topics": ["infrastructure"],
                    "description": "Infrastructure research.",
                },
                {
                    "project_id": "supported_infrastructure",
                    "name": "Supported Infrastructure",
                    "enabled": True,
                    "topics": ["runtime security deployment infrastructure"],
                    "description": "Runtime security deployment infrastructure.",
                },
            ],
        )

        project_ids = [item["project_id"] for item in matches]

        self.assertNotIn("thin_infrastructure", project_ids)
        self.assertIn("supported_infrastructure", project_ids)
        supported_match = next(item for item in matches if item["project_id"] == "supported_infrastructure")
        self.assertEqual(supported_match["match_type"], "shared_topic")
        self.assertGreaterEqual(len(supported_match["context_matches"]), 3)

    def test_project_matching_excludes_non_active_projects_from_current_review(self):
        matches = _project_relevance_matches(
            shared_topics=["automation", "workflow"],
            agent_item={"topic_tokens": ["automation", "workflow", "dashboard"]},
            friction_item={"topic_tokens": ["automation", "workflow", "diagnostics"]},
            projects=[
                {
                    "project_id": "on_hold_property",
                    "name": "AI Property Intelligence",
                    "enabled": True,
                    "status": "on_hold",
                    "topics": ["automation", "workflow"],
                    "description": "Property intelligence workflow automation.",
                },
                {
                    "project_id": "active_ops",
                    "name": "Active Ops",
                    "enabled": True,
                    "status": "active",
                    "topics": ["automation", "workflow"],
                    "description": "Current workflow automation diagnostics.",
                },
            ],
        )

        project_ids = [item["project_id"] for item in matches]

        self.assertIn("active_ops", project_ids)
        self.assertNotIn("on_hold_property", project_ids)

    def test_topic_tokens_filter_distribution_noise(self):
        tokens = _topic_tokens_from_item(
            {
                "title": "Launch HN: Open source GitHub traction for developer tools",
                "summary": "Everyone on the team is sharing the GitHub source link.",
                "matched_keywords": ["HN traction", "developer workflow"],
            }
        )

        self.assertIn("developer tooling", tokens)
        self.assertIn("workflow", tokens)
        self.assertNotIn("github", tokens)
        self.assertNotIn("open", tokens)
        self.assertNotIn("source", tokens)
        self.assertNotIn("traction", tokens)

    def test_topic_tokens_filter_modal_and_connector_noise(self):
        tokens = _topic_tokens_from_item(
            {
                "title": "But this may not preserve state",
                "summary": "More workflow context without project evidence yet.",
                "matched_keywords": ["may not", "state"],
            }
        )

        self.assertIn("workflow", tokens)
        self.assertNotIn("but", tokens)
        self.assertNotIn("may", tokens)
        self.assertNotIn("not", tokens)
        self.assertNotIn("more", tokens)
        self.assertNotIn("without", tokens)
        self.assertNotIn("yet", tokens)
        self.assertNotIn("state", tokens)

    def test_convergence_shared_topics_ignore_distribution_noise(self):
        payload = build_strategic_synthesis_response(
            radar_intelligence={
                "agent_watch": {
                    "signals": [
                        {
                            "title": "Open source GitHub developer tool gains traction",
                            "summary": "Developer workflow support is improving.",
                            "url": "https://example.com/agent",
                            "source": "github",
                            "agent_watch_score": 0.9,
                        }
                    ],
                },
                "friction_signals": {
                    "signals": [
                        {
                            "title": "Launch HN: GitHub source workflow for developer teams",
                            "summary": "Developer workflow setup remains painful.",
                            "url": "https://example.com/friction",
                            "source": "hn",
                            "friction_score": 0.88,
                        }
                    ],
                },
            }
        )

        brief = payload["supply_demand"]["convergence_briefs"][0]

        self.assertIn("developer tooling", brief["shared_topics"])
        self.assertIn("workflow", brief["shared_topics"])
        self.assertNotIn("github", brief["shared_topics"])
        self.assertNotIn("open", brief["shared_topics"])
        self.assertNotIn("source", brief["shared_topics"])
        self.assertNotIn("traction", brief["shared_topics"])


if __name__ == "__main__":
    unittest.main()
