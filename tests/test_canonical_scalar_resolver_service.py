import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_scalar_resolver_service import (  # noqa: E402
    build_canonical_scalar_resolution,
    scalar_resolution_text,
)


class CanonicalScalarResolverServiceTests(unittest.TestCase):
    def test_builds_github_scalar_resolution_from_existing_metadata(self):
        result = build_canonical_scalar_resolution(
            {
                "url": "https://github.com/example/agentkit",
                "collected_at": "2026-06-24T00:00:00+00:00",
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
        )

        self.assertEqual(result["entity_type"], "github_repo")
        self.assertEqual(result["entity_id"], "example/agentkit")
        self.assertEqual(result["canonical_source"], "github_api")
        self.assertEqual(result["summary"]["mismatch"], 1)
        self.assertEqual(result["summary"]["platform_delta"], 1)
        statuses = {item["name"]: item["status"] for item in result["scalars"]}
        self.assertEqual(statuses["stars"], "mismatch")
        self.assertEqual(statuses["license"], "platform_delta")
        licenses = {item["name"]: item for item in result["scalars"]}
        self.assertEqual(licenses["license"]["resolution_confidence"], "medium")
        self.assertFalse(licenses["license"]["can_contradict_claim"])
        self.assertIn("license_detection_not_definitive", licenses["license"]["resolution_notes"])

    def test_license_noassertion_is_uncertain_not_mismatch(self):
        result = build_canonical_scalar_resolution(
            {
                "url": "https://github.com/example/agentkit",
                "metadata": {
                    "repo_name": "example/agentkit",
                    "license_spdx_id": "NOASSERTION",
                    "claimed_scalars": {"license": "MIT"},
                },
            }
        )

        license_item = next(item for item in result["scalars"] if item["name"] == "license")
        self.assertEqual(license_item["status"], "uncertain")
        self.assertEqual(license_item["resolution_confidence"], "low")
        self.assertFalse(license_item["can_contradict_claim"])
        self.assertIn("github_license_noassertion_or_unknown", license_item["resolution_notes"])
        self.assertEqual(result["summary"]["uncertain"], 1)

    def test_resolution_text_is_a_traceable_api_observation(self):
        result = build_canonical_scalar_resolution(
            {
                "url": "https://github.com/example/agentkit",
                "metadata": {
                    "repo_stars": 842,
                    "license": "AGPL-3.0",
                },
            }
        )

        text = scalar_resolution_text(result)

        self.assertIn("github_api observed example/agentkit", text)
        self.assertIn("stars=842", text)
        self.assertIn("license=AGPL-3.0", text)

    def test_returns_empty_when_no_canonical_scalar_exists(self):
        self.assertEqual(
            build_canonical_scalar_resolution({"url": "https://github.com/example/agentkit"}),
            {},
        )


if __name__ == "__main__":
    unittest.main()
