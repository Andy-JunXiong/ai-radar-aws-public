import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_github_scalar_coverage import (  # noqa: E402
    build_github_scalar_coverage_report,
    github_scalar_coverage_exit_code,
)


class GithubScalarCoverageReportTests(unittest.TestCase):
    def test_report_counts_complete_and_partial_github_scalar_coverage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "signals.json"
            path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "id": "complete",
                                "title": "example/complete",
                                "url": "https://github.com/example/complete",
                                "source": "github",
                                "published_at": "2026-06-01T00:00:00Z",
                                "metadata": {
                                    "repo_name": "example/complete",
                                    "repo_stars": 1000,
                                    "license_spdx_id": "MIT",
                                    "archived": False,
                                    "created_at": "2026-06-01T00:00:00Z",
                                    "updated_at": "2026-06-20T00:00:00Z",
                                },
                            },
                            {
                                "id": "partial",
                                "title": "example/partial",
                                "url": "https://github.com/example/partial",
                                "source": "github",
                                "published_at": "2026-06-02T00:00:00Z",
                                "metadata": {
                                    "repo_name": "example/partial",
                                    "repo_stars": 50,
                                    "created_at": "2026-06-02T00:00:00Z",
                                },
                            },
                            {
                                "id": "rss",
                                "title": "Non GitHub",
                                "source": "rss",
                                "url": "https://example.com/article",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = build_github_scalar_coverage_report(
                signal_files=[path],
                root=root,
                include_records=True,
            )

        summary = report["summary"]
        self.assertEqual(summary["github_record_count"], 2)
        self.assertEqual(summary["rows_with_scalar_resolution"], 2)
        self.assertEqual(
            summary["coverage_state_counts"]["complete_core_scalar_coverage"],
            1,
        )
        self.assertEqual(
            summary["coverage_state_counts"]["partial_historical_github_coverage"],
            1,
        )
        self.assertEqual(summary["missing_scalar_counts"]["license"], 1)
        self.assertEqual(summary["missing_scalar_counts"]["archived"], 1)
        self.assertEqual(summary["missing_scalar_counts"]["updated_at"], 1)

    def test_summary_only_omits_record_rows_and_exit_code_can_fail_on_gaps(self):
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

            report = build_github_scalar_coverage_report(
                signal_files=[path],
                root=root,
                include_records=False,
            )

        self.assertNotIn("records", report)
        self.assertEqual(github_scalar_coverage_exit_code(report), 0)
        self.assertEqual(github_scalar_coverage_exit_code(report, fail_on_gaps=True), 1)


if __name__ == "__main__":
    unittest.main()
