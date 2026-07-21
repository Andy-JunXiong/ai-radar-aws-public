import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.model_provenance_service import (  # noqa: E402
    build_model_provenance,
    normalize_model_provenance,
)


class ModelProvenanceServiceTests(unittest.TestCase):
    def test_build_model_provenance_writes_v1_and_full_sha256_fingerprint(self):
        result = build_model_provenance(
            provider="openai",
            model_id="gpt-5.5",
            task_type="insight",
            route_key="insight.synthesize",
            router_source="env_router",
            prompt_template_id="signal_insight",
            prompt_template_version="v1",
            inference_params={
                "temperature": 0.3,
                "max_tokens": 1800,
                "top_p": None,
                "stop_sequences": [],
            },
            generated_at="2026-05-22T00:00:00+00:00",
        )

        self.assertEqual(result["provenance_schema_version"], 1)
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model_id"], "gpt-5.5")
        self.assertEqual(result["router_source"], "env")
        self.assertEqual(result["generated_at"], "2026-05-22T00:00:00+00:00")
        self.assertEqual(len(result["deterministic_fingerprint"]), 64)

    def test_missing_model_provenance_reads_as_legacy_without_mutating_input(self):
        source = {"verification_status": "verified"}

        result = normalize_model_provenance(source.get("produced_by_model"))

        self.assertEqual(
            result,
            {
                "provenance_schema_version": 0,
                "provenance_completeness": "legacy",
            },
        )
        self.assertNotIn("produced_by_model", source)


if __name__ == "__main__":
    unittest.main()
