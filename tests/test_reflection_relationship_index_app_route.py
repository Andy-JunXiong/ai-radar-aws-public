import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.main import app  # noqa: E402
from app.routes import reflection as reflection_route  # noqa: E402


class ReflectionRelationshipIndexAppRouteTests(unittest.TestCase):
    def test_relationship_index_route_uses_static_path_not_detail_path(self):
        with patch.object(
            reflection_route,
            "get_explicit_relationship_index",
            return_value={
                "schema_version": 1,
                "scope": "reflection_explicit_links",
                "nodes": [],
                "edges": [],
                "summary": {"node_count": 0, "edge_count": 0, "unresolved_edge_count": 0},
            },
        ):
            response = TestClient(app).get("/reflection/relationships")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scope"], "reflection_explicit_links")

    def test_relationship_detail_route_returns_404_for_missing_reflection(self):
        with patch.object(
            reflection_route,
            "get_explicit_relationships_for_reflection",
            return_value=None,
        ):
            response = TestClient(app).get("/reflection/missing/relationships")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
