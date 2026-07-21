import json
import subprocess
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

from scripts.check_presentation_fidelity_audit import build_presentation_fidelity_audit_report  # noqa: E402


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _evidence_item(content, *, metadata=None, evidence_id="ev_1"):
    return {
        "evidence_id": evidence_id,
        "source_id": "sig-1",
        "source_field": "source_excerpt",
        "content": content,
        "provenance": "source_excerpt",
        "traceable": True,
        "metadata": metadata or {},
    }


def _source_limit_metadata():
    return {
        "source_stated_limits_status": "limits_present",
        "source_stated_limits": [
            {
                "text": (
                    "The review is an in-framework simulated review, not external peer review "
                    "or an external quality claim; hallucinated citations are known to exist."
                ),
                "source_field": "source_excerpt",
                "source_span": None,
                "limit_type": None,
            }
        ],
        "source_stated_confidence": {
            "raw_text": "Hallucinated citations are known to exist.",
            "normalized_label": "limited",
        },
    }


class PresentationFidelityAuditReportTests(unittest.TestCase):
    def test_report_surfaces_exceeded_limits_and_coverage_gaps_without_writes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-exceeded",
                        "source": "manual",
                        "generation_mode": "llm",
                        "why_it_matters": "Deli AutoResearch received peer review 8.5/10.",
                        "evidence_pack": {
                            "source_type": "manual",
                            "evidence_items": [
                                _evidence_item(
                                    "Deli AutoResearch reports an in-framework simulated review score of 8.5/10.",
                                    metadata=_source_limit_metadata(),
                                )
                            ],
                        },
                    },
                    {
                        "signal_id": "sig-absent",
                        "source": "rss",
                        "generation_mode": "llm",
                        "why_it_matters": "The project received peer review 8.5/10.",
                        "evidence_pack": {
                            "source_type": "rss",
                            "evidence_items": [
                                _evidence_item("The project received peer review 8.5/10.", evidence_id="ev_2")
                            ],
                        },
                    },
                    {
                        "signal_id": "sig-not-applicable",
                        "source": "github",
                        "generation_mode": "llm",
                        "why_it_matters": "The repo added enterprise deployment docs.",
                        "evidence_pack": {
                            "source_type": "github",
                            "evidence_items": [
                                _evidence_item(
                                    "The repo added enterprise deployment docs.",
                                    evidence_id="ev_3",
                                    metadata={"source_stated_limits_status": "limits_not_applicable"},
                                )
                            ],
                        },
                    },
                ],
            )

            report = build_presentation_fidelity_audit_report(
                signal_files=[signals_file],
                manual_sessions_dir=root / "manual_sessions",
                root=root,
            )

        boundary = report["report_boundary"]
        self.assertEqual(boundary["mode"], "read_only")
        self.assertFalse(boundary["writes_data"])
        self.assertFalse(boundary["regenerates_llm_output"])
        self.assertFalse(boundary["changes_project_takeaway_gate"])
        self.assertFalse(boundary["changes_source_scoring"])
        self.assertFalse(boundary["detects_hop_level_deletion"])
        self.assertEqual(report["summary"]["record_count"], 3)
        self.assertEqual(report["summary"]["claim_count"], 3)
        self.assertEqual(report["summary"]["exceeded_claim_count"], 1)
        self.assertEqual(report["summary"]["absent_unknown_claim_count"], 1)
        self.assertEqual(report["summary"]["not_applicable_claim_count"], 1)
        self.assertEqual(report["summary"]["coverage_gap_record_count"], 1)
        self.assertEqual(report["summary"]["exceeded_record_count"], 1)
        self.assertEqual(
            report["summary"]["exceeded_reason_counts"],
            {"peer_review_claim_exceeds_simulated_review_limit": 1, "quality_score_claim_exceeds_source_limit": 1},
        )
        rows_by_id = {row["record_id"]: row for row in report["rows"]}
        self.assertEqual(rows_by_id["sig-exceeded"]["coverage_state"], "exceeded_limit_detected")
        self.assertEqual(rows_by_id["sig-absent"]["coverage_state"], "coverage_gap_present")
        self.assertEqual(rows_by_id["sig-not-applicable"]["coverage_state"], "limits_not_applicable")

    def test_report_can_omit_rows_for_summary_only_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-1",
                        "why_it_matters": "The project received peer review 8.5/10.",
                        "evidence_pack": {
                            "evidence_items": [
                                _evidence_item("The project received peer review 8.5/10.")
                            ]
                        },
                    }
                ],
            )

            report = build_presentation_fidelity_audit_report(
                signal_files=[signals_file],
                manual_sessions_dir=root / "manual_sessions",
                include_rows=False,
                root=root,
            )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"], [])

    def test_report_scans_wrapped_signals_payload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                {
                    "signals": [
                        {
                            "signal_id": "sig-wrapped",
                            "why_it_matters": "The repo added enterprise deployment docs.",
                            "evidence_pack": {
                                "evidence_items": [
                                    _evidence_item(
                                        "The repo added enterprise deployment docs.",
                                        metadata={"source_stated_limits_status": "limits_not_applicable"},
                                    )
                                ]
                            },
                        }
                    ]
                },
            )

            report = build_presentation_fidelity_audit_report(
                signal_files=[signals_file],
                manual_sessions_dir=root / "manual_sessions",
                root=root,
            )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"][0]["record_id"], "sig-wrapped")
        self.assertEqual(report["rows"][0]["coverage_state"], "limits_not_applicable")

    def test_report_scans_manual_session_nested_analysis_fields(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions_dir = root / "manual_sessions"
            session_file = sessions_dir / "session-1.json"
            _write_json(
                session_file,
                {
                    "session_id": "session-1",
                    "title": "Manual Session",
                    "analysis": {
                        "why_it_matters": (
                            "The excerpt reports an in-framework simulated review score of 8.5/10 "
                            "while explicitly warning that it is not external peer review."
                        )
                    },
                    "evidence_pack": {
                        "source_type": "manual",
                        "evidence_items": [
                            _evidence_item(
                                "The excerpt reports an in-framework simulated review score of 8.5/10.",
                                metadata=_source_limit_metadata(),
                            )
                        ],
                    },
                },
            )

            report = build_presentation_fidelity_audit_report(
                signal_files=[],
                manual_sessions_dir=sessions_dir,
                root=root,
            )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"][0]["record_id"], "session-1")
        self.assertEqual(report["summary"]["limits_state_counts"]["limits_present_and_exceeded"], 1)
        self.assertEqual(report["rows"][0]["coverage_state"], "exceeded_limit_detected")

    def test_cli_summary_only_reports_fidelity_counts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-exceeded",
                        "why_it_matters": "Deli AutoResearch received peer review 8.5/10.",
                        "evidence_pack": {
                            "evidence_items": [
                                _evidence_item(
                                    "Deli AutoResearch reports an in-framework simulated review score of 8.5/10.",
                                    metadata=_source_limit_metadata(),
                                )
                            ]
                        },
                    }
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_presentation_fidelity_audit.py",
                    "--signal-file",
                    str(signals_file),
                    "--manual-sessions-dir",
                    str(root / "manual_sessions"),
                    "--summary-only",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )

        self.assertIn("records: 1 claims=1 exceeded=1 absent_unknown=0", result.stdout)
        self.assertIn("limits_present_and_exceeded=1", result.stdout)
        self.assertIn("peer_review_claim_exceeds_simulated_review_limit=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
