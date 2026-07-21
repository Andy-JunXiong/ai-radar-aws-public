import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_verification_metadata_contract import (  # noqa: E402
    build_verification_contract_report,
    scan_insight_records,
    scan_project_improvements_dir,
    scan_signal_lifecycle_dir,
)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class VerificationMetadataContractReportTests(unittest.TestCase):
    def test_scans_signal_and_manual_insight_records_with_path_aware_contract(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            sessions_dir = root / "manual" / "sessions"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-ok",
                        "synthesized_insight": "Useful insight.",
                        "verification": {
                            "verification_status": "partially_verified",
                            "evidence_quality": {"level": "sufficient"},
                            "blocked_downstream_actions": ["low_risk_action_candidate"],
                        },
                    },
                    {"signal_id": "sig-pending", "status": "pending"},
                ],
            )
            _write_json(
                sessions_dir / "manual-1.json",
                {
                    "session_id": "manual-1",
                    "analysis_status": "completed",
                    "policy_metadata": {
                        "verification": {
                            "verification_status": "partially_verified",
                            "blocked_downstream_actions": ["low_risk_action_candidate"],
                        }
                    },
                },
            )

            rows = scan_insight_records(
                signals_file=signals_file,
                manual_sessions_dir=sessions_dir,
                root=root,
            )

        self.assertEqual(len(rows), 2)
        rows_by_id = {row.signal_id: row for row in rows}
        self.assertTrue(rows_by_id["sig-ok"].contract_ok)
        self.assertEqual(rows_by_id["sig-ok"].evidence_level, "sufficient")
        self.assertFalse(rows_by_id["manual-1"].contract_ok)
        self.assertEqual(rows_by_id["manual-1"].findings[0]["code"], "missing_evidence_level")

    def test_scans_project_takeaway_records_and_reports_warning_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "projects"
            _write_json(
                project_dir / "ai_radar.json",
                {
                    "project_id": "ai_radar",
                    "items": [
                        {
                            "id": "item-1",
                            "signal_id": "sig-1",
                            "verification_metadata": {
                                "verification_status": "knowledge_convergence_review_candidate",
                                "blocked_downstream_actions": [],
                                "claim_support_summary": {},
                            },
                        }
                    ],
                },
            )

            rows = scan_project_improvements_dir(project_dir, root=root)

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].contract_ok)
        self.assertEqual(rows[0].warning_count, 1)
        self.assertEqual(rows[0].findings[0]["code"], "knowledge_convergence_missing_action_block")
        self.assertEqual(rows[0].project_id, "ai_radar")

    def test_scans_lifecycle_verification_support_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            lifecycle_dir = root / "lifecycle"
            _write_json(
                lifecycle_dir / "sig-1.json",
                {
                    "signal_id": "sig-1",
                    "events": [
                        {
                            "event_id": "evt-insight",
                            "event_type": "insight_generated",
                            "support": {"stored_fingerprint": "abc"},
                        },
                        {
                            "event_id": "evt-verification",
                            "event_type": "verification_completed",
                            "support": {
                                "verification_status": "partially_verified",
                                "blocked_downstream_actions": ["low_risk_action_candidate"],
                                "claim_support_summary": {"inferred": 1},
                            },
                        },
                    ],
                },
            )

            rows = scan_signal_lifecycle_dir(lifecycle_dir, root=root)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].record_id, "evt-verification")
        self.assertEqual(rows[0].context, "lifecycle_support_snapshot")
        self.assertTrue(rows[0].contract_ok)

    def test_build_report_summarizes_selected_sources_without_writes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            sessions_dir = root / "manual" / "sessions"
            project_dir = root / "projects"
            lifecycle_dir = root / "lifecycle"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-insight",
                        "synthesized_insight": "Useful insight.",
                        "verification": {
                            "verification_status": "verified",
                            "evidence_quality": {"level": "thin"},
                            "blocked_downstream_actions": [],
                        },
                    }
                ],
            )
            _write_json(
                project_dir / "ai_radar.json",
                {
                    "items": [
                        {
                            "signal_id": "sig-project",
                            "verification_metadata": {},
                        }
                    ]
                },
            )
            _write_json(
                lifecycle_dir / "sig-1.json",
                {
                    "events": [
                        {
                            "event_type": "verification_completed",
                            "support": {
                                "verification_status": "partially_verified",
                                "blocked_downstream_actions": [],
                            },
                        }
                    ]
                },
            )

            report = build_verification_contract_report(
                signals_file=signals_file,
                manual_sessions_dir=sessions_dir,
                project_improvements_dir=project_dir,
                signal_lifecycle_dir=lifecycle_dir,
                sources=None,
                root=root,
            )

        self.assertEqual(report["report_boundary"]["mode"], "read_only")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertEqual(report["summary"]["record_count"], 3)
        self.assertEqual(report["summary"]["source_counts"]["insight_records"], 1)
        self.assertEqual(report["summary"]["source_counts"]["project_takeaway"], 1)
        self.assertEqual(report["summary"]["source_counts"]["signal_lifecycle"], 1)
        self.assertGreaterEqual(report["summary"]["finding_count"], 2)
        self.assertIn("verified_status_with_low_evidence", report["summary"]["finding_code_counts"])

    def test_build_report_can_limit_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            sessions_dir = root / "manual" / "sessions"
            project_dir = root / "projects"
            lifecycle_dir = root / "lifecycle"
            _write_json(
                signals_file,
                [
                    {
                        "verification": {
                            "verification_status": "partially_verified",
                            "evidence_quality": {"level": "sufficient"},
                            "blocked_downstream_actions": [],
                        }
                    }
                ],
            )
            _write_json(
                project_dir / "ai_radar.json",
                {"items": [{"verification_metadata": {}}]},
            )

            report = build_verification_contract_report(
                signals_file=signals_file,
                manual_sessions_dir=sessions_dir,
                project_improvements_dir=project_dir,
                signal_lifecycle_dir=lifecycle_dir,
                sources={"project_takeaway"},
                root=root,
            )

        self.assertEqual(report["sources"], ["project_takeaway"])
        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"][0]["source"], "project_takeaway")

    def test_build_report_can_omit_rows_for_summary_only_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "projects"
            _write_json(
                project_dir / "ai_radar.json",
                {"items": [{"signal_id": "sig-project", "verification_metadata": {}}]},
            )

            report = build_verification_contract_report(
                signals_file=root / "signals.json",
                manual_sessions_dir=root / "manual" / "sessions",
                project_improvements_dir=project_dir,
                signal_lifecycle_dir=root / "lifecycle",
                sources={"project_takeaway"},
                include_rows=False,
                root=root,
            )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"], [])


if __name__ == "__main__":
    unittest.main()
