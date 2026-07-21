import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_github_scalar_live_refresh import (  # noqa: E402
    build_github_scalar_live_refresh_report,
    github_scalar_live_refresh_exit_code,
)


class GithubScalarLiveRefreshTests(unittest.TestCase):
    def test_live_refresh_report_uses_fetcher_without_writing_records(self):
        fetched_repos: list[str] = []

        def fake_fetcher(repo_name: str):
            fetched_repos.append(repo_name)
            return {
                "full_name": repo_name,
                "stargazers_count": 842,
                "license": {"spdx_id": "AGPL-3.0"},
                "archived": False,
                "created_at": "2026-06-01T00:00:00Z",
                "updated_at": "2026-06-20T00:00:00Z",
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "signals.json"
            original_payload = {
                "signals": [
                    {
                        "id": "partial",
                        "title": "example/partial",
                        "url": "https://github.com/example/partial",
                        "source": "github",
                        "published_at": "2026-06-01T00:00:00Z",
                        "metadata": {
                            "repo_name": "example/partial",
                            "repo_stars": 500,
                            "created_at": "2026-06-01T00:00:00Z",
                        },
                    }
                ]
            }
            path.write_text(json.dumps(original_payload), encoding="utf-8")

            report = build_github_scalar_live_refresh_report(
                signal_files=[path],
                root=root,
                max_records=5,
                fetcher=fake_fetcher,
                include_records=True,
            )
            after_payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(after_payload, original_payload)
        self.assertEqual(fetched_repos, ["example/partial"])
        summary = report["summary"]
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["fetched_record_count"], 1)
        self.assertEqual(summary["fetch_status_counts"]["fetched_would_change"], 1)
        self.assertEqual(summary["would_add_scalar_counts"]["license"], 1)
        self.assertEqual(summary["would_add_scalar_counts"]["archived"], 1)
        self.assertEqual(summary["would_add_scalar_counts"]["updated_at"], 1)
        self.assertEqual(summary["would_update_scalar_counts"]["stars"], 1)
        self.assertEqual(summary["scalar_conflict_counts"]["stars"], 1)

    def test_live_refresh_respects_max_records_and_summary_only(self):
        fetched_repos: list[str] = []

        def fake_fetcher(repo_name: str):
            fetched_repos.append(repo_name)
            return {
                "stargazers_count": 10,
                "license": {"spdx_id": "MIT"},
                "archived": False,
                "created_at": "2026-06-01T00:00:00Z",
                "updated_at": "2026-06-20T00:00:00Z",
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "signals.json"
            path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "id": "one",
                                "title": "example/one",
                                "url": "https://github.com/example/one",
                                "source": "github",
                                "metadata": {"repo_name": "example/one"},
                            },
                            {
                                "id": "two",
                                "title": "example/two",
                                "url": "https://github.com/example/two",
                                "source": "github",
                                "metadata": {"repo_name": "example/two"},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = build_github_scalar_live_refresh_report(
                signal_files=[path],
                root=root,
                max_records=1,
                fetcher=fake_fetcher,
                include_records=False,
            )

        self.assertEqual(fetched_repos, ["example/one"])
        self.assertNotIn("records", report)
        self.assertEqual(report["summary"]["candidate_count"], 2)
        self.assertEqual(report["summary"]["fetched_record_count"], 1)
        self.assertEqual(github_scalar_live_refresh_exit_code(report), 0)


if __name__ == "__main__":
    unittest.main()
