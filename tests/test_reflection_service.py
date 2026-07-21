import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import reflection_service  # noqa: E402


class ReflectionServiceTests(unittest.TestCase):
    def test_find_related_reflections_matches_topics(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_1",
                    title="AI Agents need better memory",
                    tags=["ai agents", "memory"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                    model_dump=lambda mode="json": {
                        "id": "refl_1",
                        "title": "AI Agents need better memory",
                        "tags": ["ai agents", "memory"],
                        "source": "manual",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                ),
                SimpleNamespace(
                    id="refl_2",
                    title="Property market notes",
                    tags=["property"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                    model_dump=lambda mode="json": {
                        "id": "refl_2",
                        "title": "Property market notes",
                        "tags": ["property"],
                        "source": "manual",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                ),
            ]
        )

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            result = reflection_service.find_related_reflections(topics=["ai agents"], limit=3)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["reflections"][0]["id"], "refl_1")
        self.assertIn("ai agents", result["reflections"][0]["matched_topics"])
        self.assertGreater(result["reflections"][0]["match_score"], 0)

    def test_find_related_reflections_uses_token_overlap_aliases(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_3",
                    title="Agentic memory patterns",
                    tags=["context"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                    model_dump=lambda mode="json": {
                        "id": "refl_3",
                        "title": "Agentic memory patterns",
                        "tags": ["context"],
                        "source": "manual",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ]
        )

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            result = reflection_service.find_related_reflections(topics=["ai agents"], q="memory", limit=3)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["reflections"][0]["id"], "refl_3")
        self.assertIn("memory", result["reflections"][0]["matched_terms"])

    def test_find_related_reflections_for_signal_derives_topics(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_4",
                    title="Agent orchestration pain points",
                    tags=["ai agents", "friction"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                    model_dump=lambda mode="json": {
                        "id": "refl_4",
                        "title": "Agent orchestration pain points",
                        "tags": ["ai agents", "friction"],
                        "source": "manual",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ]
        )
        signal = {
            "title": "Developers complain about agent orchestration failures",
            "summary": "A growing set of AI agent builders report bugs and reliability pain.",
            "topic": "AI Agents",
            "signal_type": "friction",
        }

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            result = reflection_service.find_related_reflections_for_signal(signal, limit=3)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["reflections"][0]["id"], "refl_4")
        self.assertIn("ai agents", result["signal_topics"])
        self.assertIn("friction", result["signal_topics"])

    def test_get_related_manual_sessions_matches_reflection_tags(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_manual_1",
                    title="Agent memory reflection",
                    tags=["ai agents", "memory"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                )
            ]
        )
        fake_sessions = [
            {
                "session_id": "session_1",
                "title": "Agent memory review",
                "analysis_status": "completed",
                "upload_reason": "Compare against roadmap",
                "intended_use": "Project review context",
                "cognitive_layer": "L2",
                "analysis": {
                    "summary": "We reviewed agent orchestration and context window problems.",
                    "why_it_matters": "Memory and retrieval are still weak points.",
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            with patch.object(reflection_service, "_load_manual_sessions", return_value=fake_sessions):
                result = reflection_service.get_related_manual_sessions("refl_manual_1", limit=5)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["session_id"], "session_1")
        self.assertEqual(result[0]["upload_reason"], "Compare against roadmap")
        self.assertEqual(result[0]["intended_use"], "Project review context")
        self.assertEqual(result[0]["cognitive_layer"], "L2")
        self.assertIn("memory", result[0]["matched_tags"])

    def test_get_relationship_analytics_summarizes_matches(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_a",
                    title="Agent notes",
                    tags=["ai agents"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                ),
                SimpleNamespace(
                    id="refl_b",
                    title="Memory notes",
                    tags=["memory"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                ),
            ]
        )

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            with patch.object(
                reflection_service,
                "get_related_signals",
                side_effect=[
                    [{"matched_tags": ["ai agents"]}],
                    [],
                ],
            ):
                with patch.object(
                    reflection_service,
                    "get_related_manual_sessions",
                    side_effect=[
                        [{"matched_tags": ["ai agents"]}],
                        [{"matched_tags": ["memory"]}],
                    ],
                ):
                    result = reflection_service.get_relationship_analytics(days=30, limit=5)

        self.assertEqual(result["total_reflections"], 2)
        self.assertEqual(result["total_signal_matches"], 1)
        self.assertEqual(result["total_manual_matches"], 2)
        self.assertEqual(result["top_reflections"][0]["id"], "refl_a")
        self.assertEqual(result["top_relationship_tags"][0]["tag"], "ai agents")

    def test_get_vnext_backfill_preview_returns_missing_field_suggestions(self):
        fake_index = SimpleNamespace(
            reflections=[
                SimpleNamespace(
                    id="refl_backfill_1",
                    title="Agent memory",
                    tags=["ai agents", "memory"],
                    source=SimpleNamespace(value="manual"),
                    timestamp=datetime.now(timezone.utc),
                    model_dump=lambda mode="json": {
                        "id": "refl_backfill_1",
                        "title": "Agent memory",
                        "tags": ["ai agents", "memory"],
                        "thesis": None,
                        "key_claims": [],
                        "final_takeaway": None,
                    },
                )
            ]
        )

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            with patch.object(
                reflection_service,
                "get_reflection_full",
                return_value={
                    "metadata": {"id": "refl_backfill_1"},
                    "content": "Memory matters because agent state breaks across steps. Durable memory will become a product bottleneck.",
                },
            ):
                result = reflection_service.get_vnext_backfill_preview(limit=5)

        self.assertEqual(result["total_candidates"], 1)
        self.assertEqual(result["suggestions"][0]["id"], "refl_backfill_1")
        self.assertIn("thesis", result["suggestions"][0]["missing_fields"])

    def test_create_vnext_backfill_draft_writes_local_file(self):
        with TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir)
            with patch.object(reflection_service, "BACKFILL_DRAFTS_DIR", target_dir):
                with patch.object(
                    reflection_service,
                    "get_reflection_full",
                    return_value={
                        "metadata": {
                            "id": "refl_apply_1",
                            "title": "Agent memory",
                            "github_path": "reflections/agent-memory.md",
                            "github_url": "https://example.com/reflections/agent-memory",
                        },
                        "content": "Memory matters because agent state breaks across steps. Durable memory will become a product bottleneck.",
                    },
                ):
                    with patch.object(
                        reflection_service,
                        "get_vnext_backfill_suggestion",
                        return_value={
                            "id": "refl_apply_1",
                            "missing_fields": ["thesis", "final_takeaway"],
                            "suggested_thesis": "Memory matters.",
                            "suggested_final_takeaway": "Durable memory is becoming critical.",
                            "suggested_frontmatter_patch": "thesis: Memory matters.\nfinal_takeaway: Durable memory is becoming critical.",
                        },
                    ):
                        result = reflection_service.create_vnext_backfill_draft("refl_apply_1")
                        self.assertIsNotNone(result)
                        assert result is not None
                        self.assertTrue(Path(result["file_path"]).exists())
                        self.assertIn("thesis:", Path(result["file_path"]).read_text(encoding="utf-8"))

    def test_create_vnext_backfill_drafts_batch_creates_multiple_files(self):
        with patch.object(
            reflection_service,
            "get_vnext_backfill_preview",
            return_value={
                "suggestions": [
                    {"id": "refl_1"},
                    {"id": "refl_2"},
                ]
            },
        ):
            with patch.object(
                reflection_service,
                "create_vnext_backfill_draft",
                side_effect=[
                    {"reflection_id": "refl_1", "file_path": "a.md"},
                    {"reflection_id": "refl_2", "file_path": "b.md"},
                ],
            ):
                result = reflection_service.create_vnext_backfill_drafts_batch(limit=2)

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(len(result["drafts"]), 2)

    def test_apply_vnext_backfill_to_source_updates_frontmatter(self):
        content = """---
id: refl_apply_live
title: Agent memory
timestamp: 2026-04-14T10:00:00Z
source: manual
tags:
  - ai agents
  - memory
---

Body text here.
"""

        fake_client = SimpleNamespace(
            update_file_content=lambda **kwargs: {
                "commit": {"sha": "commit123"},
                "content": {"html_url": "https://github.com/example/refl_apply_live"},
                "kwargs": kwargs,
            }
        )

        with patch.object(
            reflection_service,
            "get_reflection_full",
            return_value={
                "metadata": {
                    "id": "refl_apply_live",
                    "github_path": "reflections/agent-memory.md",
                },
                "content": content,
            },
        ):
            with patch.object(
                reflection_service,
                "get_vnext_backfill_suggestion",
                return_value={
                    "suggested_thesis": "Memory matters.",
                    "suggested_key_claims": ["Durable state is missing."],
                    "suggested_counterpoints": [],
                    "suggested_open_questions": [],
                    "suggested_final_takeaway": "Memory is becoming critical.",
                },
            ):
                with patch.object(reflection_service, "GitHubReflectionClient", return_value=fake_client):
                    result = reflection_service.apply_vnext_backfill_to_source("refl_apply_live")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["changed_fields"], ["thesis", "key_claims", "final_takeaway"])
        self.assertEqual(result["commit_sha"], "commit123")



if __name__ == "__main__":
    unittest.main()
