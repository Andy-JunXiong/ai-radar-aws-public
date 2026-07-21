import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_operational_import_boundary import (  # noqa: E402
    build_operational_import_boundary_report,
    operational_import_boundary_exit_code,
)


class OperationalImportBoundaryTests(unittest.TestCase):
    def test_report_allows_normal_verification_imports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "claim_verification_service.py"
            path.write_text(
                "from app.services.evidence_pack_service import build_evidence_pack\n",
                encoding="utf-8",
            )

            report = build_operational_import_boundary_report(targets=[path], root=root)

        self.assertEqual(report["summary"]["violation_count"], 0)
        self.assertEqual(operational_import_boundary_exit_code(report), 0)
        self.assertEqual(operational_import_boundary_exit_code(report, fail_on_violations=True), 0)

    def test_report_flags_direct_operational_script_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "claim_verification_service.py"
            path.write_text("import scripts.radar_doctor\n", encoding="utf-8")

            report = build_operational_import_boundary_report(targets=[path], root=root)

        self.assertEqual(report["summary"]["violation_count"], 1)
        self.assertEqual(operational_import_boundary_exit_code(report), 0)
        self.assertEqual(operational_import_boundary_exit_code(report, fail_on_violations=True), 1)
        violation = report["violations"][0]
        self.assertEqual(violation["imported_module"], "scripts.radar_doctor")
        self.assertEqual(violation["matched_prefix"], "scripts.radar_doctor")

    def test_report_flags_importfrom_alias_under_prohibited_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "project_intelligence_service.py"
            path.write_text(
                "from app.services import source_health_service\n",
                encoding="utf-8",
            )

            report = build_operational_import_boundary_report(targets=[path], root=root)

        self.assertEqual(report["summary"]["violation_count"], 1)
        violation = report["violations"][0]
        self.assertEqual(violation["imported_module"], "app.services.source_health_service")
        self.assertEqual(violation["matched_prefix"], "app.services.source_health_service")

    def test_summary_only_omits_violation_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "projects.py"
            path.write_text(
                "from scripts.check_github_scalar_coverage import build_github_scalar_coverage_report\n",
                encoding="utf-8",
            )

            report = build_operational_import_boundary_report(
                targets=[path],
                root=root,
                include_records=False,
            )

        self.assertEqual(report["summary"]["violation_count"], 1)
        self.assertNotIn("violations", report)


if __name__ == "__main__":
    unittest.main()
