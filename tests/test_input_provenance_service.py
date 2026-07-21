import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.services.input_provenance_service import build_input_provenance_snapshot  # noqa: E402


class InputProvenanceServiceTests(unittest.TestCase):
    def test_builds_snapshot_from_existing_signal_and_context_fields(self):
        snapshot = build_input_provenance_snapshot(
            signal={
                "published_at": "2026-06-12T00:00:00+00:00",
                "collected_at": "2026-06-12T02:00:00+00:00",
                "source_excerpt": "source text",
            },
            context_scope="user_specific",
            user_context_captured_at="2026-06-13T00:00:00+00:00",
            project_repo_snapshot={
                "scanned_at": "2026-06-12T00:00:00+00:00",
                "status": "fresh",
            },
            project_context_cache={"fetched_at": "2026-06-13T00:00:00+00:00"},
            project_context_cache_ttl_hours=12,
            captured_at="2026-06-13T01:00:00+00:00",
            now="2026-06-13T01:00:00+00:00",
        )

        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["captured_at"], "2026-06-13T01:00:00+00:00")
        self.assertEqual(snapshot["signal"]["published_at"], "2026-06-12T00:00:00+00:00")
        self.assertEqual(snapshot["signal"]["source_excerpt_length"], len("source text"))
        self.assertEqual(snapshot["user_context"]["context_scope"], "user_specific")
        self.assertEqual(snapshot["project_context"]["repo_snapshot_status"], "fresh")
        self.assertEqual(snapshot["project_context_cache"]["ttl_hours"], 12.0)
        self.assertEqual(snapshot["freshness"]["stale_flags"], [])
        self.assertEqual(snapshot["freshness"]["freshness_penalty"], 0)
        self.assertEqual(snapshot["freshness"]["summary"], "No stale input detected.")

    def test_marks_stale_inputs_with_bounded_penalty(self):
        snapshot = build_input_provenance_snapshot(
            signal={"published_at": "2026-04-01T00:00:00+00:00"},
            project_repo_snapshot={
                "scanned_at": "2026-05-01T00:00:00+00:00",
                "status": "stale",
            },
            project_context_cache={"fetched_at": "2026-06-12T00:00:00+00:00"},
            project_context_cache_ttl_hours=12,
            now="2026-06-13T13:00:00+00:00",
        )

        self.assertEqual(
            snapshot["freshness"]["stale_flags"],
            [
                "signal_timestamp_stale",
                "project_repo_snapshot_status_stale",
                "project_repo_snapshot_stale",
                "project_context_cache_stale",
            ],
        )
        self.assertEqual(snapshot["freshness"]["freshness_penalty"], 0.4)
        self.assertIn("signal_timestamp_stale", snapshot["freshness"]["summary"])

    def test_invalid_timestamps_are_visible_without_throwing(self):
        snapshot = build_input_provenance_snapshot(
            signal={"published_at": "not-a-date"},
            project_repo_snapshot={"scanned_at": "also-not-a-date"},
            project_context_cache={"fetched_at": "bad-cache-date"},
            now="2026-06-13T00:00:00+00:00",
        )

        self.assertEqual(
            snapshot["freshness"]["stale_flags"],
            [
                "signal_timestamp_invalid",
                "project_repo_snapshot_timestamp_invalid",
                "project_context_cache_timestamp_invalid",
            ],
        )
        self.assertEqual(snapshot["freshness"]["freshness_penalty"], 0.3)

    def test_explicit_source_excerpt_length_wins_over_text_length(self):
        snapshot = build_input_provenance_snapshot(
            signal={"source_excerpt": "longer source text", "source_excerpt_length": "7"},
            now="2026-06-13T00:00:00+00:00",
        )

        self.assertEqual(snapshot["signal"]["source_excerpt_length"], 7)

    def test_building_snapshot_does_not_mutate_inputs(self):
        signal = {"published_at": "2026-04-01T00:00:00+00:00"}
        repo_snapshot = {"status": "stale", "scanned_at": "2026-05-01T00:00:00+00:00"}
        cache = {"fetched_at": "2026-06-12T00:00:00+00:00"}

        build_input_provenance_snapshot(
            signal=signal,
            project_repo_snapshot=repo_snapshot,
            project_context_cache=cache,
            now="2026-06-13T13:00:00+00:00",
        )

        self.assertEqual(signal, {"published_at": "2026-04-01T00:00:00+00:00"})
        self.assertEqual(repo_snapshot, {"status": "stale", "scanned_at": "2026-05-01T00:00:00+00:00"})
        self.assertEqual(cache, {"fetched_at": "2026-06-12T00:00:00+00:00"})


if __name__ == "__main__":
    unittest.main()
