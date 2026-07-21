import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_insight_eval_seed_cases import build_seed_case_template, check_seed_cases


class InsightEvalSeedCaseTests(unittest.TestCase):
    def test_empty_case_directory_needs_seed_cases(self):
        with TemporaryDirectory() as tmp:
            report = check_seed_cases(Path(tmp), root=Path(tmp))

            self.assertEqual(report["case_count"], 0)
            self.assertEqual(report["readiness"], "needs_seed_cases")
            self.assertEqual(report["min_accepted_seeds"], 20)
            self.assertEqual(report["remaining_accepted_seed_count"], 20)
            self.assertIn("Add human-selected accepted seed cases", report["readiness_reasons"][0])
            self.assertIn("strict_greater_than_gate", report["not_for"])

    def test_valid_case_counts_as_partial_seed_set(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_path = root / "case-001.json"
            case_path.write_text(
                json.dumps(
                    {
                        "case_id": "case-001",
                        "schema_version": "insight_eval_case.v1",
                        "status": "accepted_seed",
                        "source_boundary": "human_seeded",
                        "input": {
                            "query_or_signal_summary": "A concise test signal summary.",
                            "source_refs": ["human-note:case-001"],
                        },
                        "expected": {
                            "verification_status": "verified",
                            "requires_model_provenance": True,
                            "notes": "Human selected this as a trusted baseline case.",
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root)

            self.assertEqual(report["case_count"], 1)
            self.assertEqual(report["accepted_seed_count"], 1)
            self.assertEqual(report["finding_count"], 0)
            self.assertEqual(report["readiness"], "partial_seed_set")
            self.assertEqual(report["remaining_accepted_seed_count"], 19)
            self.assertEqual(report["source_boundary_counts"], {"human_seeded": 1})
            self.assertEqual(report["accepted_seed_source_boundary_counts"], {"human_seeded": 1})
            self.assertEqual(
                report["expected_field_counts"],
                {
                    "notes": 1,
                    "requires_model_provenance": 1,
                    "verification_status": 1,
                },
            )
            self.assertEqual(
                report["accepted_seed_expected_field_counts"],
                {
                    "notes": 1,
                    "requires_model_provenance": 1,
                    "verification_status": 1,
                },
            )

    def test_invalid_case_reports_schema_fixes_needed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.json").write_text("{}", encoding="utf-8")

            report = check_seed_cases(root, root=root)

            self.assertGreater(report["finding_count"], 0)
            self.assertEqual(report["readiness"], "schema_fixes_needed")

    def test_seed_case_template_is_valid_seed_candidate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_path = root / "template.json"
            case_path.write_text(
                json.dumps(build_seed_case_template(case_id="case-template")),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root)

            self.assertEqual(report["case_count"], 1)
            self.assertEqual(report["accepted_seed_count"], 0)
            self.assertEqual(report["finding_count"], 0)
            self.assertEqual(report["readiness"], "needs_seed_cases")
            self.assertEqual(report["status_counts"], {"seed_candidate": 1})
            self.assertEqual(report["source_boundary_counts"], {"human_seeded": 1})
            self.assertEqual(
                report["expected_field_counts"],
                {
                    "max_unsupported_or_contradicted_claims": 1,
                    "notes": 1,
                    "required_blocked_actions": 1,
                    "requires_model_provenance": 1,
                    "verification_status": 1,
                },
            )

    def test_seed_case_template_normalizes_invalid_options(self):
        template = build_seed_case_template(
            case_id="",
            status="bad",
            source_boundary="bad",
        )

        self.assertEqual(template["case_id"], "case-template")
        self.assertEqual(template["status"], "seed_candidate")
        self.assertEqual(template["source_boundary"], "human_seeded")

    def test_template_content_cannot_be_marked_as_accepted_seed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = build_seed_case_template(
                case_id="case-template",
                status="accepted_seed",
            )
            (root / "bad-template.json").write_text(
                json.dumps(template),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root)

            self.assertEqual(report["accepted_seed_count"], 1)
            self.assertEqual(report["readiness"], "schema_fixes_needed")
            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("accepted_seed_uses_template_case_id", codes)
            self.assertIn("accepted_seed_has_placeholder_summary", codes)
            self.assertIn("accepted_seed_has_placeholder_source_refs", codes)
            self.assertIn("accepted_seed_has_placeholder_notes", codes)

    def test_accepted_seed_requires_source_refs_and_human_notes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "missing-trust-context.json").write_text(
                json.dumps(
                    {
                        "case_id": "case-002",
                        "schema_version": "insight_eval_case.v1",
                        "status": "accepted_seed",
                        "source_boundary": "human_seeded",
                        "input": {
                            "query_or_signal_summary": "A concise test signal summary.",
                        },
                        "expected": {
                            "verification_status": "verified",
                            "requires_model_provenance": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root)

            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("accepted_seed_missing_source_refs", codes)
            self.assertIn("accepted_seed_missing_human_notes", codes)
            self.assertEqual(report["readiness"], "schema_fixes_needed")

    def test_min_accepted_seed_threshold_can_be_configured_for_local_planning(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "case-001.json").write_text(
                json.dumps(
                    {
                        "case_id": "case-001",
                        "schema_version": "insight_eval_case.v1",
                        "status": "accepted_seed",
                        "source_boundary": "human_seeded",
                        "input": {
                            "query_or_signal_summary": "A concise test signal summary.",
                            "source_refs": ["human-note:case-001"],
                        },
                        "expected": {
                            "verification_status": "verified",
                            "requires_model_provenance": True,
                            "notes": "Human selected this as a trusted baseline case.",
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root, min_accepted_seeds=1)

            self.assertEqual(report["readiness"], "ready_for_deterministic_eval")
            self.assertEqual(report["remaining_accepted_seed_count"], 0)
            self.assertEqual(report["min_accepted_seeds"], 1)

    def test_invalid_min_accepted_seed_threshold_uses_default(self):
        with TemporaryDirectory() as tmp:
            report = check_seed_cases(Path(tmp), root=Path(tmp), min_accepted_seeds=0)

            self.assertEqual(report["min_accepted_seeds"], 20)
            self.assertEqual(report["remaining_accepted_seed_count"], 20)

    def test_duplicate_case_ids_are_reported_as_schema_fixes_needed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = {
                "case_id": "case-001",
                "schema_version": "insight_eval_case.v1",
                "status": "seed_candidate",
                "source_boundary": "human_seeded",
                "input": {
                    "query_or_signal_summary": "A concise test signal summary.",
                    "source_refs": ["human-note:case-001"],
                },
                "expected": {
                    "verification_status": "verified",
                    "requires_model_provenance": True,
                    "notes": "Human selected this as a trusted baseline case.",
                },
            }
            (root / "case-001-a.json").write_text(json.dumps(case), encoding="utf-8")
            (root / "case-001-b.json").write_text(json.dumps(case), encoding="utf-8")

            report = check_seed_cases(root, root=root)

            self.assertEqual(report["readiness"], "schema_fixes_needed")
            self.assertIn(
                "duplicate_case_id",
                {finding["code"] for finding in report["findings"]},
            )

    def test_invalid_optional_input_and_expected_field_types_are_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad-types.json").write_text(
                json.dumps(
                    {
                        "case_id": "case-003",
                        "schema_version": "insight_eval_case.v1",
                        "status": "seed_candidate",
                        "source_boundary": "human_seeded",
                        "input": {
                            "query_or_signal_summary": "A concise test signal summary.",
                            "source_refs": ["ok", ""],
                        },
                        "expected": {
                            "verification_status": 123,
                            "required_blocked_actions": ["low_risk_action_candidate", ""],
                            "max_unsupported_or_contradicted_claims": -1,
                            "requires_model_provenance": "yes",
                            "notes": ["not", "a", "string"],
                            "unexpected": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = check_seed_cases(root, root=root)

            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("invalid_input_source_refs", codes)
            self.assertIn("invalid_expected_verification_status", codes)
            self.assertIn("invalid_expected_required_blocked_actions", codes)
            self.assertIn("invalid_expected_max_unsupported_or_contradicted_claims", codes)
            self.assertIn("invalid_expected_requires_model_provenance", codes)
            self.assertIn("invalid_expected_notes", codes)
            self.assertIn("unknown_expected_field", codes)
            self.assertEqual(report["readiness"], "schema_fixes_needed")


if __name__ == "__main__":
    unittest.main()
