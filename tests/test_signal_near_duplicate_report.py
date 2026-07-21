import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_signal_near_duplicates import (  # noqa: E402
    build_signal_near_duplicate_report,
    signal_near_duplicate_exit_code,
)


BEDROCK_EXCERPT = (
    "In this post, we explore how Amazon Bedrock Data Automation can accurately extract "
    "information from four common types of financial documents: bank statements, W-2 forms, "
    "1099-B tax forms, and vendor contracts."
)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SignalNearDuplicateReportTests(unittest.TestCase):
    def test_reports_category_vs_article_duplicate_and_prefers_article_url(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            collected = root / "data" / "output" / "collected_signals.json"
            _write_json(
                collected,
                [
                    {
                        "id": "category-record",
                        "title": "Artificial Intelligence | Artificial Intelligence",
                        "source": "aws_ai",
                        "source_url": "https://aws.amazon.com/blogs/machine-learning/category/artificial-intelligence/",
                        "published_at": "2026-05-27T21:28:53+00:00",
                        "source_excerpt": BEDROCK_EXCERPT,
                        "source_excerpt_length": 1200,
                    },
                    {
                        "id": "article-record",
                        "title": "Process financial documents using Amazon Bedrock Data Automation",
                        "source": "aws_ml",
                        "source_url": (
                            "https://aws.amazon.com/blogs/machine-learning/"
                            "process-financial-documents-using-amazon-bedrock-data-automation/"
                        ),
                        "published_at": "2026-05-27T21:28:53+00:00",
                        "summary": BEDROCK_EXCERPT,
                    },
                ],
            )

            report = build_signal_near_duplicate_report(signal_files=[collected], root=root)

        self.assertEqual(report["report_boundary"]["mode"], "read_only_local_signal_output_check")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["deduplicates_records"])
        self.assertEqual(report["summary"]["duplicate_group_count"], 1)
        self.assertEqual(report["summary"]["category_vs_article_group_count"], 1)
        group = report["groups"][0]
        self.assertEqual(group["duplicate_type"], "category_vs_article")
        self.assertEqual(group["distinct_url_count"], 2)
        self.assertEqual(group["preferred_record"]["record_id"], "article-record")
        self.assertIn("process-financial-documents", group["preferred_record"]["normalized_url"])
        self.assertEqual(
            group["cleanup_recommendation"]["safe_action"],
            "prefer_canonical_for_display_and_insight_generation",
        )
        self.assertFalse(group["cleanup_recommendation"]["requires_human_review"])
        self.assertEqual(group["cleanup_recommendation"]["preferred_record_id"], "article-record")
        self.assertEqual(group["cleanup_recommendation"]["demote_candidate_ids"], ["category-record"])
        self.assertEqual(
            report["summary"]["cleanup_recommendation_counts"],
            {"prefer_canonical_for_display_and_insight_generation": 1},
        )
        self.assertEqual(report["summary"]["groups_requiring_human_review"], 0)

    def test_same_url_repeated_across_files_is_not_reported_as_near_duplicate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "data" / "output" / "signals.json"
            rss = root / "data" / "output" / "rss_signals.json"
            record = {
                "title": "Process financial documents using Amazon Bedrock Data Automation",
                "source": "aws_ml",
                "source_url": (
                    "https://aws.amazon.com/blogs/machine-learning/"
                    "process-financial-documents-using-amazon-bedrock-data-automation/"
                ),
                "summary": BEDROCK_EXCERPT,
            }
            _write_json(signals, [record])
            _write_json(rss, [dict(record, source="rss")])

            report = build_signal_near_duplicate_report(signal_files=[signals, rss], root=root)

        self.assertEqual(report["summary"]["duplicate_group_count"], 0)
        self.assertEqual(report["summary"]["readiness"], "no_near_duplicates_found")

    def test_scans_wrapped_signals_payload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrapped = root / "wrapped.json"
            _write_json(
                wrapped,
                {
                    "signals": [
                        {
                            "title": "Category Title",
                            "source_url": "https://example.com/category/ai/",
                            "content": "The same durable source text appears in both records for testing duplicate detection.",
                        },
                        {
                            "title": "Specific Article Title",
                            "source_url": "https://example.com/articles/specific-article/",
                            "summary": "The same durable source text appears in both records for testing duplicate detection.",
                        },
                    ]
                },
            )

            report = build_signal_near_duplicate_report(signal_files=[wrapped], root=root)

        self.assertEqual(report["summary"]["duplicate_group_count"], 1)
        self.assertEqual(report["groups"][0]["duplicate_type"], "category_vs_article")

    def test_summary_only_omits_groups_but_keeps_counts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "signals.json"
            _write_json(
                signals,
                [
                    {
                        "title": "Category Title",
                        "source_url": "https://example.com/category/ai/",
                        "content": "This shared source text has enough words for duplicate grouping and report summaries.",
                    },
                    {
                        "title": "Article Title",
                        "source_url": "https://example.com/articles/article/",
                        "content": "This shared source text has enough words for duplicate grouping and report summaries.",
                    },
                ],
            )

            report = build_signal_near_duplicate_report(
                signal_files=[signals],
                root=root,
                include_records=False,
            )

        self.assertEqual(report["summary"]["duplicate_group_count"], 1)
        self.assertEqual(report["groups"], [])

    def test_non_category_duplicate_requires_human_review(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals = root / "signals.json"
            shared_content = (
                "This shared source text has enough words for duplicate grouping and advisory "
                "cleanup policy testing across two article URLs."
            )
            _write_json(
                signals,
                [
                    {
                        "id": "article-a",
                        "title": "Article A",
                        "source_url": "https://example.com/articles/a/",
                        "content": shared_content,
                    },
                    {
                        "id": "article-b",
                        "title": "Article B",
                        "source_url": "https://example.com/articles/b/",
                        "content": shared_content,
                    },
                ],
            )

            report = build_signal_near_duplicate_report(signal_files=[signals], root=root)

        group = report["groups"][0]
        self.assertEqual(group["duplicate_type"], "same_content_different_url")
        self.assertEqual(group["cleanup_recommendation"]["safe_action"], "review_before_cleanup")
        self.assertTrue(group["cleanup_recommendation"]["requires_human_review"])
        self.assertEqual(report["summary"]["cleanup_recommendation_counts"], {"review_before_cleanup": 1})
        self.assertEqual(report["summary"]["groups_requiring_human_review"], 1)

    def test_exit_code_is_advisory_by_default_and_strict_when_requested(self):
        report = {"summary": {"duplicate_group_count": 1}}

        self.assertEqual(signal_near_duplicate_exit_code(report, fail_on_findings=False), 0)
        self.assertEqual(signal_near_duplicate_exit_code(report, fail_on_findings=True), 1)


if __name__ == "__main__":
    unittest.main()
