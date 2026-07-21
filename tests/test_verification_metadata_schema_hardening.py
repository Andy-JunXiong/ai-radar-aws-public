import textwrap
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_verification_metadata_schema_hardening import (
    scan_paths,
    summarize_findings,
)


class VerificationMetadataSchemaHardeningAuditTests(unittest.TestCase):
    def test_flags_schema_default_and_empty_call_site(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sample.py"
            path.write_text(
                textwrap.dedent(
                    """
                    class ProjectTakeawayCandidateRequest:
                        verification_metadata: dict = {}

                    def build_payload():
                        return ProjectTakeawayCandidateRequest(verification_metadata={})
                    """
                ),
                encoding="utf-8",
            )

            findings = scan_paths([path], root=root)
            codes = {finding.code for finding in findings}

            self.assertIn("schema_default_empty_dict", codes)
            self.assertIn("empty_dict_call_site", codes)

    def test_flags_function_default_none_as_migration_touchpoint(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "service.py"
            path.write_text(
                textwrap.dedent(
                    """
                    def add_signal_to_project_improvements(*, verification_metadata=None):
                        return verification_metadata
                    """
                ),
                encoding="utf-8",
            )

            findings = scan_paths([path], root=root)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].code, "function_default_none")

    def test_summary_stays_in_migration_audit_boundary(self):
        summary = summarize_findings([])

        self.assertEqual(summary["schema_hardening_readiness"], "no_static_default_or_empty_call_sites_found")
        self.assertEqual(summary["decision_boundary"], "migration_risk_audit_only")
        self.assertIn("runtime_behavior_change", summary["not_for"])


if __name__ == "__main__":
    unittest.main()
