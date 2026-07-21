import json
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "docs" / "governance" / "source-excerpt-preservation-contract.schema.json"
ADVISORY_CHECKERS_PATH = REPO_ROOT / "docs" / "governance" / "advisory-checkers.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_source_excerpt_preservation_contract import (  # noqa: E402
    check_source_excerpt_preservation_contract,
    source_excerpt_contract_exit_code,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _write_minimal_contract_files(root: Path, *, pipeline_output_extra: str = "") -> None:
    _write_text(
        root / "signal_collectors" / "official_collector.py",
        """
        def parse_article_page():
            body_text = "Official article body"
            source_excerpt = body_text[:1200] if body_text else ""
            return {
                "source_excerpt": source_excerpt,
                "source_excerpt_length": len(source_excerpt),
            }
        """,
    )
    _write_text(
        root / "signal_collectors" / "merge_signals.py",
        """
        MAX_SOURCE_EXCERPT_CHARS = 1200
        SOURCE_EXCERPT_FIELDS = ("source_excerpt", "raw_content", "raw_text", "article_body", "content")

        def bounded_source_excerpt(item, summary):
            normalized_summary = summary.lower()
            for field in SOURCE_EXCERPT_FIELDS:
                value = item.get(field, "")
                if field == "content" and value.lower() == normalized_summary:
                    continue
                return value[:MAX_SOURCE_EXCERPT_CHARS]
            return ""

        def normalize_signal(item):
            source_excerpt = bounded_source_excerpt(item, item.get("summary", ""))
            normalized = {}
            normalized["source_excerpt"] = source_excerpt
            return normalized
        """,
    )
    _write_text(
        root / "app" / "main_summary_v2.py",
        f"""
        MAX_SOURCE_EXCERPT_CHARS = 1200

        def _copy_source_excerpt_to_signal(signal, item):
            return None

        def load_signals_from_file():
            signal = object()
            item = {{}}
            _copy_source_excerpt_to_signal(signal, item)
            return [signal]

        def enrich_and_filter_signals():
            signal = object()
            item = {{}}
            _copy_source_excerpt_to_signal(signal, item)
            return [signal]

        def signal_to_output_dict(signal):
            source_excerpt = "source text"
            data = {{}}
            data["source_excerpt"] = source_excerpt
            data["source_excerpt_length"] = len(source_excerpt)
            {pipeline_output_extra}
            return data
        """,
    )


class SourceExcerptPreservationContractTests(unittest.TestCase):
    def test_current_repo_contract_is_ok(self):
        report = check_source_excerpt_preservation_contract(REPO_ROOT)

        self.assertEqual(report["schema_version"], "source_excerpt_preservation_contract.v1")
        self.assertEqual(report["report_boundary"]["mode"], "read_only_static_contract_check")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["runs_ingestion"])
        self.assertEqual(report["summary"]["readiness"], "contract_ok")
        self.assertEqual(report["findings"], [])

    def test_current_report_matches_published_schema_shape(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = check_source_excerpt_preservation_contract(REPO_ROOT)

        self.assertEqual(report["schema_version"], schema["properties"]["schema_version"]["const"])
        self.assertEqual(
            report["report_boundary"]["mode"],
            schema["properties"]["report_boundary"]["properties"]["mode"]["const"],
        )
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["runs_ingestion"])
        self.assertFalse(report["report_boundary"]["hard_enforcement"])
        self.assertEqual(report["contract"]["canonical_field"], "source_excerpt")
        self.assertEqual(report["contract"]["max_source_excerpt_chars"], 1200)
        self.assertIn(report["summary"]["readiness"], {"contract_ok", "contract_gap_found"})
        for field in schema["required"]:
            self.assertIn(field, report)
        json.dumps(report)

    def test_advisory_checker_index_documents_source_excerpt_command_and_schema(self):
        markdown = ADVISORY_CHECKERS_PATH.read_text(encoding="utf-8")

        self.assertIn("## Source Excerpt Preservation Contract", markdown)
        self.assertIn("python scripts/check_source_excerpt_preservation_contract.py --format text", markdown)
        self.assertIn("docs/governance/source-excerpt-preservation-contract.schema.json", markdown)
        self.assertIn("not a fresh ingestion run", markdown)

    def test_missing_merge_summary_guard_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_contract_files(root)
            merge_path = root / "signal_collectors" / "merge_signals.py"
            merge_path.write_text(
                merge_path.read_text(encoding="utf-8").replace(
                    'if field == "content" and value.lower() == normalized_summary:',
                    'if False:',
                ),
                encoding="utf-8",
            )

            report = check_source_excerpt_preservation_contract(root)

        codes = {finding["code"] for finding in report["findings"]}
        self.assertEqual(report["summary"]["readiness"], "contract_gap_found")
        self.assertIn("merge_rejects_summary_content", codes)

    def test_pipeline_output_full_text_like_field_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_contract_files(root, pipeline_output_extra='data["raw_text"] = "too much"')

            report = check_source_excerpt_preservation_contract(root)

        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("pipeline_output_preserves_full_text_like_field", codes)

    def test_exit_code_is_advisory_by_default_and_strict_when_requested(self):
        report = {"summary": {"error_count": 1}}

        self.assertEqual(source_excerpt_contract_exit_code(report, fail_on_gaps=False), 0)
        self.assertEqual(source_excerpt_contract_exit_code(report, fail_on_gaps=True), 1)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
