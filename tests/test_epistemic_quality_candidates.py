import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_epistemic_quality_candidates import (  # noqa: E402
    build_epistemic_quality_report,
    evaluate_epistemic_quality_candidate,
)


class EpistemicQualityCandidateTests(unittest.TestCase):
    def test_inflated_terms_without_boundary_language_become_advisory_candidate(self):
        row = evaluate_epistemic_quality_candidate(
            {
                "signal_id": "sig-1",
                "title": "A revolutionary AI paradigm",
                "summary": "This production breakthrough solved agent memory.",
            }
        )

        assert row is not None
        self.assertEqual(row.knowledge_honesty, "low")
        self.assertEqual(row.primary_issue, "overconfident_framing")
        self.assertIn("inflated_terms_without_boundary_language", row.advisory_reasons)

    def test_boundary_language_softens_but_still_reports_review_candidate(self):
        row = evaluate_epistemic_quality_candidate(
            {
                "signal_id": "sig-2",
                "title": "Early demo suggests a new agent paradigm",
                "summary": "The result could become useful, but it remains experimental.",
            }
        )

        assert row is not None
        self.assertEqual(row.knowledge_honesty, "medium")
        self.assertEqual(row.primary_issue, "framing_needs_review")

    def test_long_content_has_transmission_density_issue(self):
        row = evaluate_epistemic_quality_candidate(
            {
                "signal_id": "sig-3",
                "title": "Dense but not inflated",
                "summary": "Detailed operational note. " * 90,
            }
        )

        assert row is not None
        self.assertEqual(row.knowledge_honesty, "unknown")
        self.assertEqual(row.transmission_adaptability, "medium")
        self.assertEqual(row.primary_issue, "transmission_density_review")

    def test_report_is_read_only_and_accepts_wrapped_signals_payload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            signal_file = root / "signals.json"
            signal_file.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "signal_id": "sig-1",
                                "title": "A revolutionary AI paradigm",
                                "summary": "This breakthrough solved agent memory.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = build_epistemic_quality_report(signal_files=[signal_file], root=root)

        self.assertEqual(report["report_boundary"]["mode"], "read_only")
        self.assertFalse(report["report_boundary"]["writes_data"])
        self.assertFalse(report["report_boundary"]["uses_llm_scorer"])
        self.assertFalse(report["report_boundary"]["changes_gates"])
        self.assertEqual(report["summary"]["candidate_count"], 1)
        self.assertEqual(report["rows"][0]["signal_id"], "sig-1")


if __name__ == "__main__":
    unittest.main()
