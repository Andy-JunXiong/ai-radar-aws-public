import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
BASELINE_PATH = REPO_ROOT / "docs" / "notes" / "baselines" / "util-json-repair-golden-cases.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.registry import json_repair_prompts  # noqa: E402


REQUIRED_EDGE_CASES = {
    "trailing_comma",
    "missing_closing_brace",
    "fenced_markdown",
    "commentary_before_after_json",
    "partially_truncated_json",
    "wrong_quote_style",
    "bom_encoding_noise",
    "extra_and_missing_keys",
}


class UtilJsonRepairBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_baseline_metadata_identifies_curated_non_production_scope(self):
        self.assertEqual(self.baseline["baseline_id"], "util-json-repair-curated-goldens-v0")
        self.assertEqual(self.baseline["skill_name"], "util-json-repair")
        self.assertEqual(self.baseline["skill_version"], "v1")
        self.assertEqual(self.baseline["baseline_type"], "hand_constructed")
        self.assertIn("not production artifacts", self.baseline["source_note"])

    def test_baseline_covers_required_repair_edge_cases(self):
        cases = self.baseline["cases"]
        edge_cases = {case["edge_case"] for case in cases}

        self.assertEqual(len(cases), 8)
        self.assertEqual(edge_cases, REQUIRED_EDGE_CASES)

    def test_each_case_returns_exact_requested_keys_with_valid_expected_json(self):
        seen_ids = set()
        for case in self.baseline["cases"]:
            with self.subTest(case_id=case.get("id")):
                self.assertNotIn(case["id"], seen_ids)
                seen_ids.add(case["id"])

                requested_keys = case["requested_keys"]
                expected_json = case["expected_json"]

                self.assertIsInstance(case["raw_text"], str)
                self.assertTrue(case["raw_text"].strip())
                self.assertIsInstance(requested_keys, list)
                self.assertTrue(requested_keys)
                self.assertEqual(set(expected_json.keys()), set(requested_keys))
                self.assertEqual(list(expected_json.keys()), requested_keys)
                self.assertTrue(case["repair_expectation"])
                self.assertTrue(case["risk_note"])

                json.dumps(expected_json, ensure_ascii=False)

    def test_prompt_contract_mentions_each_requested_key_and_exact_key_rule(self):
        sample_case = self.baseline["cases"][0]
        system_prompt, user_prompt = json_repair_prompts(
            raw_text=sample_case["raw_text"],
            keys=sample_case["requested_keys"],
        )

        self.assertIn("exactly these keys", system_prompt)
        self.assertIn("Return valid JSON only", system_prompt)
        for key in sample_case["requested_keys"]:
            self.assertIn(key, system_prompt)
        self.assertIn(sample_case["raw_text"], user_prompt)


if __name__ == "__main__":
    unittest.main()
