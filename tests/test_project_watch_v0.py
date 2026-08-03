import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
TEST_TMP_ROOT = REPO_ROOT / ".tmp-tests"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402
from app.services import project_watch_service  # noqa: E402


@contextmanager
def watch_temp_dir():
    path = TEST_TMP_ROOT / f"project_watch_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    previous = project_watch_service.PROJECT_WATCH_ITEMS_DIR
    project_watch_service.PROJECT_WATCH_ITEMS_DIR = path
    try:
        yield path
    finally:
        project_watch_service.PROJECT_WATCH_ITEMS_DIR = previous
        shutil.rmtree(path, ignore_errors=True)


def watch_allowed_verification():
    return {
        "verification_status": "weakly_supported",
        "allowed_downstream_actions": ["watch_only"],
        "blocked_downstream_actions": ["low_risk_action_candidate"],
        "claim_support_summary": {"inferred": 1},
    }


def create_watch(*, next_review_at="2026-08-01T00:00:00+00:00"):
    return project_watch_service.create_project_watch_item(
        "ai_radar",
        origin_signal_id="sig-watch-1",
        origin_signal_title="MemoryMesh protocol launch",
        watch_question="Will the MemoryMesh protocol gain independent adoption?",
        watch_reason="Memory interoperability may matter but is not ready for stronger use.",
        success_criteria="Two independent products adopt the MemoryMesh protocol.",
        exit_criteria="No MemoryMesh adoption after two review cycles.",
        next_review_at=next_review_at,
        verification_metadata=watch_allowed_verification(),
    )


class ProjectWatchServiceTests(unittest.TestCase):
    def test_create_requires_watch_eligibility_and_keeps_signal_as_origin(self):
        with watch_temp_dir():
            item = create_watch()

        self.assertEqual(item["watch_kind"], "evidence_followup")
        self.assertEqual(item["origin_type"], "signal")
        self.assertEqual(item["origin_signal_id"], "sig-watch-1")
        self.assertEqual(item["state"], "active")
        self.assertNotIn("verification_snapshot", item)
        self.assertNotIn("action_policy_snapshot", item)

    def test_create_rejects_explicit_watch_block_even_when_allowed_is_conflicted(self):
        blocked = {
            **watch_allowed_verification(),
            "blocked_downstream_actions": ["watch_only", "low_risk_action_candidate"],
        }
        with watch_temp_dir(), self.assertRaisesRegex(ValueError, "Watch"):
            project_watch_service.create_project_watch_item(
                "ai_radar",
                origin_signal_id="sig-blocked",
                origin_signal_title="Blocked",
                watch_question="Question",
                watch_reason="Reason",
                success_criteria="Success",
                exit_criteria="Exit",
                next_review_at="2026-08-02",
                verification_metadata=blocked,
            )

    def test_observation_is_server_enforced_review_context_only(self):
        with watch_temp_dir():
            created = create_watch()
            updated = project_watch_service.add_project_watch_observation(
                "ai_radar",
                created["watch_id"],
                summary="A second source appeared, but it has not been verified.",
                source_signal_id="sig-watch-2",
                next_review_at="2026-08-20",
            )

        observation = updated["observations"][0]
        self.assertEqual(observation["evidence_role"], "review_context_only")
        self.assertEqual(updated["observation_count"], 1)
        self.assertNotIn("verification_status", updated)
        self.assertNotIn("action_eligibility", updated)
        self.assertNotIn("candidate_source", updated)

    def test_due_items_sort_first_and_all_active_remain_visible(self):
        with watch_temp_dir():
            create_watch(next_review_at="2026-08-01T00:00:00+00:00")
            second = project_watch_service.create_project_watch_item(
                "ai_radar",
                origin_signal_id="sig-watch-future",
                origin_signal_title="Future Watch",
                watch_question="Future question",
                watch_reason="Future reason",
                success_criteria="Future success",
                exit_criteria="Future exit",
                next_review_at="2027-08-01T00:00:00+00:00",
                verification_metadata=watch_allowed_verification(),
            )
            items = project_watch_service.list_project_watch_items(
                "ai_radar",
                state="active",
                now=datetime(2026, 8, 2, tzinfo=timezone.utc),
            )

        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["is_due"])
        self.assertEqual(items[1]["watch_id"], second["watch_id"])
        self.assertFalse(items[1]["is_due"])

    def test_resolve_requires_basis_and_note_without_changing_evidence(self):
        with watch_temp_dir():
            created = create_watch()
            with self.assertRaisesRegex(ValueError, "Resolution note"):
                project_watch_service.resolve_project_watch_item(
                    "ai_radar",
                    created["watch_id"],
                    resolution_basis="success_criteria_met",
                    resolution_note="",
                )
            resolved = project_watch_service.resolve_project_watch_item(
                "ai_radar",
                created["watch_id"],
                resolution_basis="success_criteria_met",
                resolution_note="The reviewer recorded that the stated success criterion was met.",
            )

        self.assertEqual(resolved["state"], "resolved")
        self.assertEqual(resolved["resolution_basis"], "success_criteria_met")
        self.assertNotIn("verification_status", resolved)
        self.assertNotIn("action_eligibility", resolved)

    def test_matcher_creates_one_explainable_unseen_candidate_and_deduplicates(self):
        related_signal = {
            "signal_id": "sig-related",
            "title": "MemoryMesh protocol gains independent adoption",
            "summary": "Two products adopt MemoryMesh interoperability for AI Radar workflows.",
            "subscription_project_links": [{"project_id": "ai_radar"}],
        }
        with watch_temp_dir():
            created = create_watch()
            first = project_watch_service.match_signal_to_active_project_watches(
                related_signal,
                project_ids=["ai_radar"],
            )
            second = project_watch_service.match_signal_to_active_project_watches(
                related_signal,
                project_ids=["ai_radar"],
            )
            listed = project_watch_service.list_project_watch_items("ai_radar", state="active")

        self.assertEqual(first["created_count"], 1)
        self.assertGreaterEqual(len(first["matches"][0]["match_reasons"]), 2)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["existing_count"], 1)
        self.assertEqual(listed[0]["watch_id"], created["watch_id"])
        self.assertEqual(listed[0]["new_match_count"], 1)
        self.assertTrue(listed[0]["has_new_matches"])
        candidate = listed[0]["related_signal_candidates"][0]
        self.assertEqual(candidate["candidate_role"], "review_candidate_only")
        self.assertEqual(candidate["status"], "unseen")
        self.assertIn("title_anchor_terms", {reason["code"] for reason in candidate["match_reasons"]})

    def test_matcher_requires_title_anchor_and_does_not_treat_same_project_as_enough(self):
        with watch_temp_dir():
            create_watch()
            result = project_watch_service.match_signal_to_active_project_watches(
                {
                    "signal_id": "sig-generic-project",
                    "title": "Quarterly product roadmap update",
                    "summary": "The project has a new tool and more context for review.",
                    "subscription_project_links": [{"project_id": "ai_radar"}],
                },
                project_ids=["ai_radar"],
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["matches"], [])

    def test_matcher_ignores_generated_interpretation_fields(self):
        with watch_temp_dir():
            create_watch()
            result = project_watch_service.match_signal_to_active_project_watches(
                {
                    "signal_id": "sig-generated-only",
                    "title": "Video editor release",
                    "summary": "A creator application added timeline shortcuts.",
                    "synthesized_insight": "MemoryMesh protocol adoption may validate the Watch.",
                    "relevance_to_projects": "AI Radar should review MemoryMesh evidence.",
                },
                project_ids=["ai_radar"],
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["matches"], [])

    def test_matcher_does_not_qualify_on_weak_prompt_anchor_alone(self):
        with watch_temp_dir():
            create_watch()
            result = project_watch_service.match_signal_to_active_project_watches(
                {
                    "signal_id": "sig-prompt-cache",
                    "title": "Explicit prompt caching arrives",
                    "summary": "The cache reduces inference cost for repeated prompts.",
                },
                project_ids=["ai_radar"],
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["matches"], [])

    def test_matcher_normalizes_eval_and_harness_inflections(self):
        with watch_temp_dir():
            project_watch_service.create_project_watch_item(
                "ai_radar",
                origin_signal_id="sig-eval-origin",
                origin_signal_title="Prompt evaluation harness launch",
                watch_question="Will practitioner-built eval harnesses become repeatable?",
                watch_reason="A repeatable evaluation workflow may become a team standard.",
                success_criteria="Independent prompt eval tools adopt the harness pattern.",
                exit_criteria="No repeatable evaluation workflow appears.",
                next_review_at="2026-08-20",
                verification_metadata=watch_allowed_verification(),
            )
            result = project_watch_service.match_signal_to_active_project_watches(
                {
                    "signal_id": "sig-evals",
                    "title": "Independent prompt evals add reusable harnesses",
                    "summary": "Teams compare prompt evaluation workflows across tools.",
                },
                project_ids=["ai_radar"],
            )

        self.assertEqual(result["created_count"], 1)
        reasons = result["matches"][0]["match_reasons"]
        title_reason = next(reason for reason in reasons if reason["code"] == "title_anchor_terms")
        self.assertIn("eval", title_reason["matched_terms"])
        self.assertIn("harness", title_reason["matched_terms"])

    def test_matcher_does_not_create_candidate_for_unrelated_signal(self):
        with watch_temp_dir():
            create_watch()
            result = project_watch_service.match_signal_to_active_project_watches(
                {
                    "signal_id": "sig-unrelated",
                    "title": "Weather station maintenance",
                    "summary": "A sensor battery replacement schedule.",
                },
                project_ids=["ai_radar"],
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["matches"], [])

    def test_accept_match_adds_review_context_observation_and_clears_attention(self):
        related_signal = {
            "signal_id": "sig-related",
            "title": "MemoryMesh protocol gains independent adoption",
            "summary": "Two products adopt MemoryMesh interoperability for AI Radar workflows.",
            "subscription_project_links": [{"project_id": "ai_radar"}],
        }
        with watch_temp_dir():
            created = create_watch()
            project_watch_service.match_signal_to_active_project_watches(related_signal, project_ids=["ai_radar"])
            reviewed = project_watch_service.review_project_watch_match(
                "ai_radar",
                created["watch_id"],
                "sig-related",
                decision="accept",
                review_note="Relevant to the Watch question, pending verification.",
            )

        self.assertEqual(reviewed["candidate"]["status"], "accepted")
        self.assertEqual(reviewed["observation"]["evidence_role"], "review_context_only")
        self.assertEqual(reviewed["item"]["new_match_count"], 0)
        self.assertEqual(reviewed["item"]["observation_count"], 1)
        self.assertNotIn("verification_status", reviewed["item"])
        self.assertNotIn("action_eligibility", reviewed["item"])

    def test_ignore_match_does_not_add_observation(self):
        related_signal = {
            "signal_id": "sig-related",
            "title": "MemoryMesh protocol gains independent adoption",
            "summary": "Two products adopt MemoryMesh interoperability for AI Radar workflows.",
            "subscription_project_links": [{"project_id": "ai_radar"}],
        }
        with watch_temp_dir():
            created = create_watch()
            project_watch_service.match_signal_to_active_project_watches(related_signal, project_ids=["ai_radar"])
            reviewed = project_watch_service.review_project_watch_match(
                "ai_radar",
                created["watch_id"],
                "sig-related",
                decision="ignore",
            )

        self.assertEqual(reviewed["candidate"]["status"], "ignore")
        self.assertIsNone(reviewed["observation"])
        self.assertEqual(reviewed["item"]["observation_count"], 0)

    def test_accept_match_requires_reviewer_note(self):
        related_signal = {
            "signal_id": "sig-related",
            "title": "MemoryMesh protocol gains independent adoption",
            "summary": "Two products adopt MemoryMesh interoperability for AI Radar workflows.",
            "subscription_project_links": [{"project_id": "ai_radar"}],
        }
        with watch_temp_dir():
            created = create_watch()
            project_watch_service.match_signal_to_active_project_watches(related_signal, project_ids=["ai_radar"])
            with self.assertRaisesRegex(ValueError, "reviewer note"):
                project_watch_service.review_project_watch_match(
                    "ai_radar",
                    created["watch_id"],
                    "sig-related",
                    decision="accept",
                )


class ProjectWatchRouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_watch_routes_keep_admin_guard(self):
        response = TestClient(app).get("/projects/watch-items")
        self.assertEqual(response.status_code, 401)

    def test_create_route_uses_server_signal_verification(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        created = {"watch_id": "watch_route", "state": "active"}
        signal = {
            "signal_id": "sig-route",
            "title": "Route signal",
            "policy_metadata": {"verification": watch_allowed_verification()},
        }
        with patch("app.routes.projects.get_project", return_value={"project_id": "ai_radar"}), patch(
            "app.routes.projects.get_signal_by_id", return_value=signal
        ), patch("app.routes.projects.create_project_watch_item", return_value=created) as create:
            response = TestClient(app).post(
                "/projects/ai_radar/watch-items",
                json={
                    "origin_signal_id": "sig-route",
                    "watch_question": "Question",
                    "watch_reason": "Reason",
                    "success_criteria": "Success",
                    "exit_criteria": "Exit",
                    "next_review_at": "2026-08-20",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"], created)
        self.assertEqual(create.call_args.kwargs["verification_metadata"], watch_allowed_verification())

    def test_match_decision_route_delegates_to_guarded_watch_service(self):
        app.dependency_overrides[require_admin_auth] = lambda: None
        result = {
            "item": {"watch_id": "watch_route", "new_match_count": 0},
            "candidate": {"signal_id": "sig-related", "status": "accepted"},
            "observation": {"evidence_role": "review_context_only"},
        }
        with patch("app.routes.projects.get_project", return_value={"project_id": "ai_radar"}), patch(
            "app.routes.projects.review_project_watch_match", return_value=result
        ) as review:
            response = TestClient(app).post(
                "/projects/ai_radar/watch-items/watch_route/matches/sig-related/decision",
                json={"decision": "accept", "review_note": "Relevant, pending verification."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["observation"]["evidence_role"], "review_context_only")
        review.assert_called_once_with(
            "ai_radar",
            "watch_route",
            "sig-related",
            decision="accept",
            review_note="Relevant, pending verification.",
        )


if __name__ == "__main__":
    unittest.main()
