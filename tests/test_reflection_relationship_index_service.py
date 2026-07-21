import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services import reflection_service  # noqa: E402
from app.services.reflection_relationship_index_service import (  # noqa: E402
    build_reflection_relationship_index,
    get_reflection_relationships,
)


def _reflection(reflection_id: str, *, related: list[str] | None = None):
    return SimpleNamespace(
        id=reflection_id,
        title=f"Reflection {reflection_id}",
        tags=["ai agents"],
        source=SimpleNamespace(value="manual"),
        timestamp=datetime.now(timezone.utc),
        related=related or [],
    )


class ReflectionRelationshipIndexServiceTests(unittest.TestCase):
    def test_builds_explicit_frontmatter_relationship_edges(self):
        index = build_reflection_relationship_index(
            [
                _reflection("refl_a", related=["refl_b", "missing_refl"]),
                _reflection("refl_b"),
            ]
        )

        self.assertEqual(index["scope"], "reflection_explicit_links")
        self.assertEqual(index["summary"]["node_count"], 2)
        self.assertEqual(index["summary"]["edge_count"], 2)
        self.assertEqual(index["summary"]["unresolved_edge_count"], 1)
        edge = index["edges"][0]
        self.assertEqual(edge["source_id"], "refl_a")
        self.assertEqual(edge["target_id"], "refl_b")
        self.assertEqual(edge["type"], "related_reflection")
        self.assertFalse(edge["metadata"]["auto_extracted"])
        self.assertEqual(edge["metadata"]["evidence_role"], "cognitive_context_not_evidence")

    def test_relationship_lookup_returns_outbound_and_inbound_edges(self):
        index = build_reflection_relationship_index(
            [
                _reflection("refl_a", related=["refl_b"]),
                _reflection("refl_b", related=["missing_refl"]),
            ]
        )

        result = get_reflection_relationships(index, "refl_b")

        self.assertEqual(result["reflection_id"], "refl_b")
        self.assertEqual(result["summary"]["outbound_count"], 1)
        self.assertEqual(result["summary"]["inbound_count"], 1)
        self.assertEqual(result["summary"]["unresolved_outbound_count"], 1)
        self.assertEqual(result["inbound_edges"][0]["source_id"], "refl_a")

    def test_reflection_service_uses_current_index_without_mutating_sources(self):
        fake_index = SimpleNamespace(
            reflections=[
                _reflection("refl_a", related=["refl_b"]),
                _reflection("refl_b"),
            ]
        )

        with patch.object(reflection_service, "load_reflection_index", return_value=fake_index):
            result = reflection_service.get_explicit_relationships_for_reflection("refl_b")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["summary"]["inbound_count"], 1)
        self.assertEqual(result["summary"]["outbound_count"], 0)


if __name__ == "__main__":
    unittest.main()
