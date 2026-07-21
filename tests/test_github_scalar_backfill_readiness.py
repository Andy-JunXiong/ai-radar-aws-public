import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_github_scalar_backfill_readiness import (  # noqa: E402
    build_github_scalar_backfill_readiness_report,
    github_scalar_backfill_readiness_exit_code,
)


class GithubScalarBackfillReadinessTests(unittest.TestCase):
    def test_report_separates_local_standardization_from_live_api_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "signals.json"
            path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "id": "historical",
                                "title": "example/historical",
                                "url": "https://github.com/example/historical",
                                "source": "github",
                                "published_at": "2026-06-01T00:00:00Z",
                                "metadata": {
                                    "repo_name": "example/historical",
                                    "repo_stars": 500,
                                    "created_at": "2026-06-01T00:00:00Z",
                                },
                            },
                            {
                                "id": "complete",
                                "title": "example/complete",
                                "url": "https://github.com/example/complete",
                                "source": "github",
                                "metadata": {
                                    "repo_name": "example/complete",
                                    "canonical_scalars": {
                                        "stars": 1000,
                                        "license": "MIT",
                                        "archived": False,
                                        "created_at": "2026-06-01T00:00:00Z",
                                        "updated_at": "2026-06-20T00:00:00Z",
                                    },
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = build_github_scalar_backfill_readiness_report(
                signal_files=[path],
                root=root,
                include_records=True,
            )

        summary = report["summary"]
        self.assertEqual(summary["github_record_count"], 2)
        self.assertEqual(summary["refresh_state_counts"]["needs_live_github_api"], 1)
        self.assertEqual(summary["refresh_state_counts"]["already_complete"], 1)
        self.assertEqual(summary["local_standardization_scalar_counts"]["stars"], 1)
        self.assertEqual(summary["local_standardization_scalar_counts"]["created_at"], 1)
        self.assertEqual(summary["live_api_required_scalar_counts"]["license"], 1)
        self.assertEqual(summary["live_api_required_scalar_counts"]["archived"], 1)
        self.assertEqual(summary["live_api_required_scalar_counts"]["updated_at"], 1)

    def test_summary_only_omits_records_and_exit_code_can_fail_on_live_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "signals.json"
            path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "id": "partial",
                                "title": "example/partial",
                                "url": "https://github.com/example/partial",
                                "source": "github",
                                "metadata": {"repo_name": "example/partial", "repo_stars": 50},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = build_github_scalar_backfill_readiness_report(
                signal_files=[path],
                root=root,
                include_records=False,
            )

        self.assertNotIn("records", report)
        self.assertEqual(github_scalar_backfill_readiness_exit_code(report), 0)
        self.assertEqual(
            github_scalar_backfill_readiness_exit_code(report, fail_on_live_required=True),
            1,
        )


if __name__ == "__main__":
    unittest.main()
