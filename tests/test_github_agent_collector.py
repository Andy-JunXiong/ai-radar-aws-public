import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.evidence_pack_service import build_signal_evidence_pack  # noqa: E402
from signal_collectors.github_agent_collector import _normalize_repo_signal  # noqa: E402


class GithubAgentCollectorTests(unittest.TestCase):
    def test_normalized_signal_preserves_canonical_github_scalars(self):
        signal = _normalize_repo_signal(
            {
                "full_name": "example/agentkit",
                "html_url": "https://github.com/example/agentkit",
                "description": "Agent framework for tests.",
                "created_at": "2026-06-01T00:00:00Z",
                "updated_at": "2026-06-20T00:00:00Z",
                "stargazers_count": 842,
                "language": "Python",
                "license": {"spdx_id": "AGPL-3.0"},
                "archived": False,
                "owner": {"login": "example"},
                "topics": ["agent"],
            },
            ["ai agent"],
        )

        self.assertIsNotNone(signal)
        metadata = signal["metadata"]
        self.assertEqual(metadata["repo_name"], "example/agentkit")
        self.assertEqual(metadata["repo_stars"], 842)
        self.assertEqual(metadata["license_spdx_id"], "AGPL-3.0")
        self.assertFalse(metadata["archived"])
        self.assertEqual(metadata["updated_at"], "2026-06-20T00:00:00Z")
        self.assertTrue(metadata["canonical_scalars_resolved_at"])

    def test_normalized_signal_builds_canonical_scalar_evidence_pack_item(self):
        signal = _normalize_repo_signal(
            {
                "full_name": "example/agentkit",
                "html_url": "https://github.com/example/agentkit",
                "description": "Agent framework for tests.",
                "created_at": "2026-06-01T00:00:00Z",
                "updated_at": "2026-06-20T00:00:00Z",
                "stargazers_count": 842,
                "language": "Python",
                "license": {"spdx_id": "AGPL-3.0"},
                "archived": False,
                "owner": {"login": "example"},
                "topics": ["agent"],
            },
            ["ai agent"],
        )

        evidence_pack = build_signal_evidence_pack(signal)
        scalar_item = next(
            item
            for item in evidence_pack["evidence_items"]
            if item["source_field"] == "canonical_scalars"
        )

        self.assertEqual(scalar_item["provenance"], "canonical_api_observed")
        self.assertIn("stars=842", scalar_item["content"])
        self.assertIn("license=AGPL-3.0", scalar_item["content"])
        self.assertIn("archived=False", scalar_item["content"])


if __name__ == "__main__":
    unittest.main()
