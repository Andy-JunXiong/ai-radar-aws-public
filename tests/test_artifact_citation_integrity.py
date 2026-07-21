import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_artifact_citation_integrity import (  # noqa: E402
    artifact_citation_exit_code,
    check_artifact_citation_integrity,
    validate_artifact_markdown,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


VALID_ARTIFACT = """# Example Brief

## Sources

- `docs/codex-assessments/example.md`
- `scripts/check_artifact_citation_integrity.py`

## Inference Boundary

This is an interpretation boundary.

## Evidence Status

Repo-grounded context only.

## Actionability Boundary

Advisory only; no runtime enforcement.
"""


class ArtifactCitationIntegrityTests(unittest.TestCase):
    def test_valid_artifact_has_no_findings(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "codex-assessments" / "valid.md"
            row, findings = validate_artifact_markdown(VALID_ARTIFACT, path=path, root=root)

        self.assertTrue(row.artifact_ok)
        self.assertEqual(row.finding_count, 0)
        self.assertEqual(findings, [])
        self.assertEqual(
            row.present_sections,
            ["sources", "inference_boundary", "evidence_status", "actionability_boundary"],
        )

    def test_missing_required_sections_report_errors_and_warning(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "codex-assessments" / "thin.md"
            row, findings = validate_artifact_markdown(
                "# Thin Brief\n\nThis has a conclusion but no citation boundary.\n",
                path=path,
                root=root,
            )

        codes = {finding.code for finding in findings}
        self.assertFalse(row.artifact_ok)
        self.assertIn("missing_source_citations", codes)
        self.assertIn("missing_inference_boundary", codes)
        self.assertIn("missing_evidence_status", codes)
        self.assertIn("missing_actionability_boundary", codes)
        self.assertEqual(row.error_count, 3)
        self.assertEqual(row.warning_count, 1)

    def test_source_heading_without_reference_warns(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "codex-assessments" / "source-lite.md"
            artifact = VALID_ARTIFACT.replace(
                "- `docs/codex-assessments/example.md`\n- `scripts/check_artifact_citation_integrity.py`",
                "General conversation context",
            )
            row, findings = validate_artifact_markdown(artifact, path=path, root=root)

        self.assertTrue(row.artifact_ok)
        self.assertEqual(row.warning_count, 1)
        self.assertEqual(findings[0].code, "source_section_without_reference")

    def test_check_directory_returns_read_only_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "docs" / "codex-assessments"
            _write_text(artifact_dir / "valid.md", VALID_ARTIFACT)
            _write_text(artifact_dir / "missing.md", "# Missing\n")

            report = check_artifact_citation_integrity([artifact_dir], root=root)

        self.assertEqual(report["schema_version"], "artifact_citation_report.v1")
        self.assertEqual(report["report_boundary"]["mode"], "read_only")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["hard_enforcement"])
        self.assertIn("required_section_groups", report)
        self.assertEqual(report["summary"]["artifact_count"], 2)
        self.assertEqual(report["summary"]["artifact_ok_count"], 1)
        self.assertEqual(report["summary"]["readiness"], "citation_retrofit_needed")
        json.dumps(report)

    def test_exit_code_is_advisory_by_default_and_strict_when_requested(self):
        report = {
            "summary": {
                "finding_count": 1,
            }
        }

        self.assertEqual(artifact_citation_exit_code(report, fail_on_gaps=False), 0)
        self.assertEqual(artifact_citation_exit_code(report, fail_on_gaps=True), 1)


if __name__ == "__main__":
    unittest.main()
