import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.main import app  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402
from app.services import final_takeaway_artifact_service as service  # noqa: E402


class FinalTakeawayRoutesTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def _authorize(self):
        app.dependency_overrides[require_admin_auth] = lambda: None

    def test_external_synthesis_source_route_keeps_admin_guard(self):
        response = TestClient(app).post(
            "/final-takeaways/external-synthesis-sources",
            json={"signal_id": "sig-1", "source_text": "External review."},
        )

        self.assertEqual(response.status_code, 401)

    def test_external_synthesis_source_route_creates_lists_and_loads_source(self):
        self._authorize()
        client = TestClient(app)

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(service, "BASE_DIR", Path(temp_dir)):
            create_response = client.post(
                "/final-takeaways/external-synthesis-sources",
                json={
                    "signal_id": "sig-1",
                    "source_text": "<h1>External Review</h1><script>alert('x')</script><p>Keep this.</p>",
                    "source_file": "review.html",
                    "content_type": "text/html",
                    "metadata": {"tool": "claude"},
                },
            )

            self.assertEqual(create_response.status_code, 200)
            source = create_response.json()["source"]
            self.assertEqual(source["record_type"], "external_synthesis_source")
            self.assertEqual(source["source_kind"], "external_html")
            self.assertEqual(source["evidence_boundary"], "review_context_not_verified_evidence")
            self.assertNotIn("<script", source["source_text"])
            self.assertNotIn("alert", source["source_text"])

            list_response = client.get("/final-takeaways/external-synthesis-sources?signal_id=sig-1")
            detail_response = client.get(
                f"/final-takeaways/external-synthesis-sources/{source['external_synthesis_source_id']}"
            )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["items"]), 1)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.json()["source"]["external_synthesis_source_id"],
            source["external_synthesis_source_id"],
        )


if __name__ == "__main__":
    unittest.main()
