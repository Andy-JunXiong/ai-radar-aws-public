import sys
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app.main_summary_v2 as pipeline  # noqa: E402
from signal_collectors.merge_signals import normalize_signal  # noqa: E402


preserve_signal_history_fields = pipeline.preserve_signal_history_fields


def test_preserve_signal_history_keeps_first_seen_collected_at_in_raw_payload():
    existing = {
        "title": "Railway: The Agent-Native Cloud",
        "source": "latent_space",
        "url": "https://www.latent.space/p/railway",
        "published_at": "2026-05-20T22:42:06+00:00",
        "collected_at": "2026-05-21T08:42:06+10:00",
        "raw": {
            "collected_at": "2026-05-21T08:42:06+10:00",
        },
        "status": "analyzed",
        "topic": "AI Infrastructure",
        "insight_status": "archived_only",
        "insight_status_label": "Archived signal only",
    }
    incoming = {
        "title": "Railway: The Agent-Native Cloud",
        "source": "latent_space",
        "url": "https://www.latent.space/p/railway",
        "published_at": "2026-05-20T22:42:06+00:00",
        "collected_at": "2026-05-25T07:32:44+10:00",
        "raw": {
            "collected_at": "2026-05-25T07:32:44+10:00",
        },
        "status": "pending",
    }

    [merged] = preserve_signal_history_fields([incoming], [existing])

    assert merged["collected_at"] == "2026-05-21T08:42:06+10:00"
    assert merged["raw"]["collected_at"] == "2026-05-21T08:42:06+10:00"
    assert merged["status"] == "analyzed"
    assert merged["topic"] == "AI Infrastructure"
    assert merged["insight_status"] == "archived_only"


def test_preserve_signal_history_uses_incoming_raw_collected_at_for_new_signal():
    incoming = {
        "title": "New RSS Item",
        "source": "latent_space",
        "url": "https://www.latent.space/p/new-item",
        "published_at": "2026-05-25T01:00:00+00:00",
        "raw": {
            "collected_at": "2026-05-25T12:00:00+10:00",
        },
    }

    [merged] = preserve_signal_history_fields([incoming], [])

    assert merged["collected_at"] == "2026-05-25T12:00:00+10:00"
    assert merged["raw"]["collected_at"] == "2026-05-25T12:00:00+10:00"
    assert merged["status"] == "pending"


def test_merge_normalize_preserves_bounded_source_excerpt():
    source_text = "Official article paragraph. " * 80
    normalized = normalize_signal(
        {
            "title": "Official source update",
            "summary": "A short collector summary.",
            "content": source_text,
            "url": "https://example.com/source",
            "source": "openai",
            "author": "OpenAI",
            "category": "AI Model",
            "published_at": "2026-05-28T00:00:00+00:00",
        },
        source_type_fallback="official",
    )

    assert normalized["source_excerpt"] == source_text[:1200]
    assert normalized["source_excerpt_length"] == 1200


def test_merge_normalize_does_not_promote_summary_content_to_source_excerpt():
    normalized = normalize_signal(
        {
            "title": "Summary-only RSS item",
            "summary": "The same text appears in content.",
            "content": "The same text appears in content.",
            "url": "https://example.com/rss",
            "source": "rss",
            "author": "Feed",
            "category": "RSS",
        },
        source_type_fallback="rss",
    )

    assert "source_excerpt" not in normalized


def test_pipeline_preserves_source_excerpt_from_collected_file_to_output(tmp_path, monkeypatch):
    collected_file = tmp_path / "collected_signals.json"
    source_excerpt = "Canonical source excerpt. " * 70
    collected_file.write_text(
        json.dumps(
            [
                {
                    "title": "Official source update",
                    "summary": "A short collector summary.",
                    "source_excerpt": source_excerpt,
                    "url": "https://example.com/source",
                    "source": "openai",
                    "author": "OpenAI",
                    "category": "AI Model",
                    "published_at": "2026-05-28T00:00:00+00:00",
                    "collected_at": "2026-05-28T01:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "COLLECTOR_SIGNALS_FILE", collected_file)

    [signal] = pipeline.load_signals_from_file()
    enriched_signals, _ = pipeline.enrich_and_filter_signals([signal])
    output = pipeline.signal_to_output_dict(enriched_signals[0])

    assert output["source_excerpt"] == source_excerpt[:1200]
    assert output["source_excerpt_length"] == 1200
    assert "content" not in output
