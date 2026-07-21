import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence.tracking.agent_friction_tracking import (  # noqa: E402
    build_agent_friction_tracking_report,
    build_agent_watch_tracking_state,
    build_friction_tracking_state,
)


class AgentFrictionTrackingTests(unittest.TestCase):
    def test_agent_tracking_marks_new_and_heating_repos(self):
        previous = {
            "items": [
                {
                    "entity_id": "https://github.com/example/agentkit",
                    "title": "example/agentkit",
                    "canonical_url": "https://github.com/example/agentkit",
                    "first_seen_at": "2026-05-29T00:00:00+00:00",
                    "last_seen_at": "2026-05-29T00:00:00+00:00",
                    "seen_days": 1,
                    "current_rank": 4,
                    "current_metric": 100,
                    "current_score": 0.55,
                }
            ]
        }
        current = {
            "items": [
                {
                    "entity_id": "https://github.com/example/agentkit",
                    "title": "example/agentkit",
                    "canonical_url": "https://github.com/example/agentkit",
                    "agent_watch_score": 0.72,
                    "repo_stars": 180,
                    "source": "github",
                    "source_type": "github_agent",
                },
                {
                    "entity_id": "https://github.com/example/newagent",
                    "title": "example/newagent",
                    "canonical_url": "https://github.com/example/newagent",
                    "agent_watch_score": 0.62,
                    "repo_stars": 25,
                    "source": "github",
                    "source_type": "github_agent",
                },
            ]
        }

        state = build_agent_watch_tracking_state(
            current,
            previous,
            generated_at="2026-05-30T00:00:00+00:00",
        )

        by_id = {item["entity_id"]: item for item in state["items"]}
        self.assertEqual(by_id["https://github.com/example/agentkit"]["status"], "heating")
        self.assertEqual(by_id["https://github.com/example/agentkit"]["metric_delta_1d"], 80)
        self.assertEqual(by_id["https://github.com/example/agentkit"]["seen_days"], 2)
        self.assertEqual(by_id["https://github.com/example/newagent"]["status"], "new")
        self.assertEqual(state["counts_by_status"], {"heating": 1, "new": 1})
        self.assertEqual(state["report"]["heating"][0]["entity_id"], "https://github.com/example/agentkit")

    def test_tracking_keeps_absent_entities_as_cooling_or_dropped(self):
        previous = {
            "items": [
                {
                    "entity_id": "https://github.com/example/oldagent",
                    "title": "example/oldagent",
                    "canonical_url": "https://github.com/example/oldagent",
                    "first_seen_at": "2026-05-20T00:00:00+00:00",
                    "last_seen_at": "2026-05-26T00:00:00+00:00",
                    "seen_days": 3,
                    "current_metric": 120,
                    "current_score": 0.5,
                }
            ]
        }

        state = build_agent_watch_tracking_state(
            {"items": []},
            previous,
            generated_at="2026-05-30T00:00:00+00:00",
        )

        self.assertEqual(state["items"][0]["status"], "dropped")
        self.assertEqual(state["items"][0]["missed_days"], 4)

    def test_friction_tracking_clusters_recurring_pain(self):
        current = {
            "signals": [
                {
                    "title": "Agent workflow fails on auth",
                    "url": "https://github.com/example/project/issues/1",
                    "source": "github",
                    "source_type": "github_friction",
                    "friction_subtopic": "reliability",
                    "friction_score": 0.8,
                    "metadata": {"repo_name": "example/project", "comments": 20},
                },
                {
                    "title": "Agent workflow fails on retry",
                    "url": "https://github.com/example/project/issues/2",
                    "source": "github",
                    "source_type": "github_friction",
                    "friction_subtopic": "reliability",
                    "friction_score": 0.75,
                    "metadata": {"repo_name": "example/project", "comments": 12},
                },
            ]
        }

        state = build_friction_tracking_state(current, generated_at="2026-05-30T00:00:00+00:00")

        self.assertEqual(state["counts_by_status"], {"new": 2})
        self.assertEqual(
            state["report"]["recurring_pain_clusters"][0],
            {"pain_cluster_key": "reliability:example/project", "active_signal_count": 2},
        )

    def test_combined_report_surfaces_topic_overlap(self):
        agent_state = {
            "items": [
                {
                    "entity_id": "https://github.com/example/reliability-agent",
                    "title": "example/reliability-agent",
                    "canonical_url": "https://github.com/example/reliability-agent",
                    "status": "heating",
                    "momentum_score": 0.7,
                    "current_score": 0.7,
                    "metric_name": "repo_stars",
                    "current_metric": 200,
                    "metric_delta_1d": 80,
                    "tags": ["reliability"],
                }
            ],
            "counts_by_status": {"heating": 1},
            "report": {"heating": []},
        }
        friction_state = {
            "items": [
                {
                    "entity_id": "https://github.com/example/project/issues/1",
                    "title": "Agent workflow fails on auth",
                    "canonical_url": "https://github.com/example/project/issues/1",
                    "status": "new",
                    "friction_subtopic": "reliability",
                    "momentum_score": 0.8,
                    "current_score": 0.8,
                    "metric_name": "comments",
                    "current_metric": 20,
                    "metric_delta_1d": 20,
                }
            ],
            "counts_by_status": {"new": 1},
            "report": {"new_today": []},
        }

        report = build_agent_friction_tracking_report(
            agent_state,
            friction_state,
            generated_at="2026-05-30T00:00:00+00:00",
        )

        self.assertIn("sustained", report["agent_watch"])
        self.assertIn("cooling_or_dropped", report["agent_watch"])
        self.assertIn("fastest_growing", report["friction_signals"])
        self.assertIn("cooling_or_dropped", report["friction_signals"])
        self.assertEqual(len(report["convergence_candidates"]), 1)
        self.assertEqual(report["convergence_candidates"][0]["overlapping_friction_topics"], ["reliability"])


if __name__ == "__main__":
    unittest.main()
