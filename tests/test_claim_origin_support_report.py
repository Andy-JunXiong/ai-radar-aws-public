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

from scripts.check_claim_origin_support import build_claim_origin_support_report  # noqa: E402


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _evidence_item(content, *, evidence_id="ev_1"):
    return {
        "evidence_id": evidence_id,
        "source_id": "sig-1",
        "source_field": "summary",
        "content": content,
        "provenance": "source_excerpt",
        "traceable": True,
    }


def _collector_summary_item(content, *, evidence_id="ev_summary"):
    return {
        "evidence_id": evidence_id,
        "source_id": "sig-1",
        "source_field": "summary",
        "content": content,
        "provenance": "collector_extracted",
        "traceable": True,
    }


class ClaimOriginSupportReportTests(unittest.TestCase):
    def test_report_rebuilds_claim_verification_without_writes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-quoted",
                        "source": "github",
                        "generation_mode": "llm",
                        "provider_used": "chatgpt",
                        "model_used": "gpt-test",
                        "why_it_matters": "The repo added enterprise deployment docs.",
                        "evidence_pack": {
                            "summary_provenance": "source_excerpt",
                            "evidence_items": [
                                _evidence_item(
                                    "The repo added enterprise deployment docs. Setup guidance followed."
                                )
                            ]
                        },
                        "verification": {
                            "verification_status": "partially_verified",
                            "claim_support_summary": {"directly_supported": 1},
                        },
                    },
                    {
                        "signal_id": "sig-borrowed",
                        "source": "aws_ml",
                        "generation_mode": "llm",
                        "produced_by_model": {
                            "provider": "anthropic",
                            "model_id": "claude-test",
                        },
                        "why_it_matters": "The product launch proves durable memory is now solved.",
                        "raw_content": "Fuller local raw source text was available for this synthetic fixture.",
                        "evidence_pack": {
                            "summary_provenance": "collector_extracted",
                            "evidence_items": [
                                _collector_summary_item(
                                    "Product launch notes discuss durable memory integrations.",
                                    evidence_id="ev_2",
                                )
                            ]
                        },
                    },
                ],
            )

            report = build_claim_origin_support_report(
                signal_files=[signals_file],
                manual_sessions_dir=root / "manual_sessions",
                root=root,
            )

        self.assertEqual(report["report_boundary"]["mode"], "read_only")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["regenerates_llm_output"])
        self.assertEqual(report["summary"]["record_count"], 2)
        self.assertEqual(report["summary"]["claim_count"], 2)
        self.assertEqual(report["summary"]["quoted_count"], 1)
        self.assertEqual(report["summary"]["direct_supported_count"], 1)
        self.assertEqual(report["summary"]["token_only_inferred_count"], 1)
        self.assertEqual(report["summary"]["generation_mode_counts"], {"llm": 2})
        self.assertEqual(report["summary"]["provider_counts"], {"anthropic": 1, "chatgpt": 1})
        self.assertEqual(
            report["summary"]["summary_provenance_counts"],
            {"collector_extracted": 1, "source_excerpt": 1},
        )
        self.assertEqual(report["summary"]["records_with_source_excerpt"], 1)
        self.assertEqual(report["summary"]["records_with_full_text_like_field"], 1)
        self.assertEqual(report["summary"]["source_text_field_counts"], {"raw_content": 1})
        self.assertEqual(
            report["summary"]["evidence_item_provenance_counts"],
            {"collector_extracted": 1, "source_excerpt": 1},
        )
        rows_by_id = {row["record_id"]: row for row in report["rows"]}
        self.assertEqual(rows_by_id["sig-quoted"]["origin_counts"], {"quoted": 1})
        self.assertEqual(rows_by_id["sig-quoted"]["signal_source"], "github")
        self.assertEqual(rows_by_id["sig-quoted"]["provider"], "chatgpt")
        self.assertEqual(rows_by_id["sig-quoted"]["model"], "gpt-test")
        self.assertTrue(rows_by_id["sig-quoted"]["has_source_excerpt"])
        self.assertFalse(rows_by_id["sig-quoted"]["has_full_text_like_field"])
        self.assertEqual(rows_by_id["sig-borrowed"]["origin_counts"], {"inferred": 1})
        self.assertEqual(rows_by_id["sig-borrowed"]["support_counts"], {"inferred": 1})
        self.assertEqual(rows_by_id["sig-borrowed"]["provider"], "anthropic")
        self.assertEqual(rows_by_id["sig-borrowed"]["model"], "claude-test")
        self.assertFalse(rows_by_id["sig-borrowed"]["has_source_excerpt"])
        self.assertTrue(rows_by_id["sig-borrowed"]["has_full_text_like_field"])

    def test_fixture_proves_quoted_positive_source_excerpt_path(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "claim_origin" / "quoted_positive_signals.json"

        report = build_claim_origin_support_report(
            signal_files=[fixture],
            manual_sessions_dir=REPO_ROOT / "tests" / "fixtures" / "claim_origin" / "empty_manual_sessions",
            root=REPO_ROOT,
        )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["summary"]["claim_count"], 1)
        self.assertEqual(report["summary"]["quoted_count"], 1)
        self.assertEqual(report["summary"]["direct_supported_count"], 1)
        self.assertEqual(report["summary"]["origin_counts"], {"quoted": 1})
        self.assertEqual(report["summary"]["support_counts"], {"directly_supported": 1})
        self.assertEqual(report["summary"]["records_with_source_excerpt"], 1)
        self.assertEqual(report["rows"][0]["record_id"], "fixture-quoted-positive")
        self.assertEqual(report["rows"][0]["origin_counts"], {"quoted": 1})

    def test_cli_summary_only_reports_quoted_positive_fixture(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "claim_origin" / "quoted_positive_signals.json"
        empty_manual_dir = REPO_ROOT / "tests" / "fixtures" / "claim_origin" / "empty_manual_sessions"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_claim_origin_support.py",
                "--signal-file",
                str(fixture),
                "--manual-sessions-dir",
                str(empty_manual_dir),
                "--summary-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertIn("records: 1 claims=1 quoted=1 inferred=0 token_only_inferred=0", result.stdout)
        self.assertIn("support: directly_supported=1", result.stdout)
        self.assertIn("source_excerpt_records=1", result.stdout)

    def test_report_can_omit_rows_for_summary_only_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_file = root / "signals.json"
            _write_json(
                signals_file,
                [
                    {
                        "signal_id": "sig-1",
                        "why_it_matters": "The repo added enterprise deployment docs.",
                        "evidence_pack": {
                            "evidence_items": [
                                _evidence_item("The repo added enterprise deployment docs.")
                            ]
                        },
                    }
                ],
            )

            report = build_claim_origin_support_report(
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
                                    _evidence_item("The repo added enterprise deployment docs.")
                                ]
                            },
                        }
                    ]
                },
            )

            report = build_claim_origin_support_report(
                signal_files=[signals_file],
                manual_sessions_dir=root / "manual_sessions",
                root=root,
            )

        self.assertEqual(report["summary"]["record_count"], 1)
        self.assertEqual(report["rows"][0]["record_id"], "sig-wrapped")


if __name__ == "__main__":
    unittest.main()
