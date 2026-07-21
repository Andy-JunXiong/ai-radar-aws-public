import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.model_attribution_analytics_service import (  # noqa: E402
    classify_model_provenance,
    summarize_model_attribution,
)


def provenance(
    *,
    provider="openai",
    model_id="gpt-test",
    route_key="insight.synthesize",
    task_type="insight",
    fingerprint="a" * 64,
):
    return {
        "provider": provider,
        "model_id": model_id,
        "model_version": "",
        "task_type": task_type,
        "route_key": route_key,
        "router_source": "env",
        "prompt_template_id": "signal_insight",
        "prompt_template_version": "v1",
        "inference_params": {
            "temperature": 0.3,
            "max_tokens": 1800,
            "top_p": None,
            "stop_sequences": [],
        },
        "deterministic_fingerprint": fingerprint,
        "generated_at": "2026-05-22T00:00:00+00:00",
        "provenance_schema_version": 1,
    }


class ModelAttributionAnalyticsServiceTests(unittest.TestCase):
    def test_summary_counts_v1_legacy_malformed_and_manual_unverified_records(self):
        summary = summarize_model_attribution(
            generated_at="2026-05-22T00:00:00+00:00",
            candidates=[
                {
                    "signal_id": "sig-v1",
                    "produced_by_model": provenance(model_id="gpt-5.5"),
                    "verification_metadata": {
                        "verification_status": "not_verifiable",
                        "review_priority": "do not act",
                        "blocked_downstream_actions": ["project_takeaway_candidate"],
                        "allowed_downstream_actions": ["watch_only"],
                    },
                },
                {
                    "signal_id": "sig-manual",
                    "candidate_source": "unverified_manual_entry",
                },
                {
                    "signal_id": "sig-malformed",
                    "produced_by_model": {
                        "provenance_schema_version": 1,
                        "provider": "openai",
                        "model_id": "gpt-5.5",
                    },
                },
            ],
            review_records=[
                {
                    "signal_id": "sig-review",
                    "outcome": "confirmed",
                    "produced_by_model": provenance(model_id="gpt-5.5"),
                }
            ],
            signals=[{"signal_id": "sig-legacy"}],
        )

        self.assertEqual(summary["schema_version"], 1)
        self.assertEqual(summary["coverage"]["total_records"], 5)
        self.assertEqual(summary["coverage"]["v1_records"], 2)
        self.assertEqual(summary["coverage"]["attribution_eligible_records"], 2)
        self.assertEqual(summary["coverage"]["legacy_v0_records"], 2)
        self.assertEqual(summary["coverage"]["malformed_records"], 1)
        self.assertEqual(summary["coverage"]["manual_unverified_records"], 1)
        self.assertEqual(summary["excluded"]["legacy_v0"], 2)
        self.assertEqual(summary["excluded"]["malformed"], 1)
        self.assertEqual(summary["excluded"]["manual_unverified"], 1)

        by_model = summary["by_model"]
        self.assertEqual(by_model, [{"provider": "openai", "model_id": "gpt-5.5", "count": 2}])
        self.assertEqual(summary["review_outcomes"][0]["outcome"], "confirmed")
        self.assertEqual(summary["review_outcomes"][0]["count"], 1)
        self.assertEqual(summary["gate_outcomes"][0]["verification_status"], "not_verifiable")
        self.assertEqual(summary["gate_outcomes"][0]["blocked_downstream_actions"], ["project_takeaway_candidate"])

        candidate_family = next(item for item in summary["by_record_family"] if item["record_family"] == "candidate")
        self.assertEqual(candidate_family["total_records"], 3)
        self.assertEqual(candidate_family["v1_records"], 1)
        self.assertEqual(candidate_family["legacy_v0_records"], 1)
        self.assertEqual(candidate_family["malformed_records"], 1)
        self.assertEqual(candidate_family["manual_unverified_records"], 1)

    def test_nested_v1_provenance_is_eligible_without_loose_model_fields(self):
        summary = summarize_model_attribution(
            candidates=[
                {
                    "signal_id": "sig-nested",
                    "provider_used": "openai",
                    "model_used": "gpt-loose",
                    "verification_metadata": {
                        "verified_insight": {
                            "produced_by_model": provenance(
                                provider="anthropic",
                                model_id="claude-test",
                                fingerprint="b" * 64,
                            )
                        }
                    },
                }
            ],
        )

        self.assertEqual(summary["coverage"]["v1_records"], 1)
        self.assertEqual(summary["by_model"][0]["provider"], "anthropic")
        self.assertEqual(summary["by_model"][0]["model_id"], "claude-test")

    def test_loose_model_fields_without_v1_provenance_remain_legacy(self):
        summary = summarize_model_attribution(
            signals=[
                {
                    "signal_id": "sig-loose",
                    "provider_used": "openai",
                    "model_used": "gpt-5.5",
                }
            ]
        )

        self.assertEqual(summary["coverage"]["legacy_v0_records"], 1)
        self.assertEqual(summary["coverage"]["attribution_eligible_records"], 0)
        self.assertEqual(summary["by_model"], [])

    def test_provenance_alone_does_not_create_gate_outcome(self):
        summary = summarize_model_attribution(
            candidates=[
                {
                    "signal_id": "sig-no-gate",
                    "produced_by_model": provenance(),
                }
            ],
        )

        self.assertEqual(summary["coverage"]["v1_records"], 1)
        self.assertEqual(summary["by_model"][0]["count"], 1)
        self.assertEqual(summary["gate_outcomes"], [])

    def test_classify_model_provenance_treats_invalid_schema_as_malformed(self):
        self.assertEqual(
            classify_model_provenance({"produced_by_model": {"provenance_schema_version": 99}})["state"],
            "malformed",
        )


if __name__ == "__main__":
    unittest.main()
